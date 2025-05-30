import { NextRequest, NextResponse } from 'next/server';
import admin from 'firebase-admin';
import * as cheerio from 'cheerio';
import { GoogleGenAI } from '@google/genai';
import { getSourceTypeMappingForBackend, isValidSourceType, getSourceTypeLabel } from '@/lib/evidence-source-types';

// Initialize Firebase Admin if not already initialized
if (!admin.apps.length) {
  const projectId = process.env.FIREBASE_PROJECT_ID;
  const clientEmail = process.env.FIREBASE_CLIENT_EMAIL;
  const privateKey = process.env.FIREBASE_PRIVATE_KEY?.replace(/\\n/g, '\n');

  if (!projectId || !clientEmail || !privateKey) {
    console.warn('Firebase credentials not fully configured. Some functionality may be limited.');
    // Initialize with minimal config for build time
    admin.initializeApp({
      projectId: projectId || 'placeholder-project-id'
    });
  } else {
    admin.initializeApp({
      credential: admin.credential.cert({
        projectId,
        clientEmail,
        privateKey,
      }),
    });
  }
}

const db = admin.firestore();

// Initialize Gemini with the new SDK
const genAI = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY || '' });

// Evidence item type
interface EvidenceItem {
  id: string;
  evidence_id?: string;
  title_or_summary?: string;
  description_or_details?: string;
  source_url?: string;
  evidence_source_type?: string;
  promise_ids?: string[];
  parliament_session_id?: string;
  evidence_date?: any;
  ingested_at?: any;
  promise_linking_status?: string;
  creation_method?: string;
  created_by?: string;
  [key: string]: any;
}

// Get evidence source type mapping from centralized config
const EVIDENCE_SOURCE_TYPE_MAPPING = getSourceTypeMappingForBackend();

// Scrape webpage content
async function scrapeWebpage(url: string): Promise<{ title: string; content: string; error?: string }> {
  try {
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (compatible; PromiseTracker/1.0; +https://promise-tracker.ca)'
      }
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`);
    }

    const html = await response.text();
    const $ = cheerio.load(html);

    // Remove script, style, and other non-content elements
    $('script, style, nav, header, footer, aside, .advertisement, .ads, #comments').remove();

    // Extract title
    const title = $('title').text().trim() || 
                  $('h1').first().text().trim() || 
                  $('meta[property="og:title"]').attr('content') || '';

    // Extract main content
    let content = '';
    
    // Try common content selectors
    const contentSelectors = [
      'main',
      'article', 
      '.content',
      '.main-content',
      '.post-content',
      '.entry-content',
      '#content',
      'body'
    ];

    for (const selector of contentSelectors) {
      const contentEl = $(selector);
      if (contentEl.length > 0) {
        content = contentEl.text().trim();
        if (content.length > 200) break; // Good content found
      }
    }

    // Clean up the content
    content = content
      .replace(/\s+/g, ' ')
      .replace(/\n\s*\n/g, '\n')
      .trim()
      .substring(0, 8000); // Limit for LLM processing

    return { title, content };
  } catch (error) {
    console.error('Error scraping webpage:', error);
    return { 
      title: '', 
      content: '', 
      error: error instanceof Error ? error.message : 'Unknown scraping error' 
    };
  }
}

// Call Gemini LLM for content analysis
async function analyzeContent(url: string, title: string, content: string, parliamentSessionId: string) {
  try {
    const prompt = `You are analyzing a Canadian government webpage to create a structured evidence item for promise tracking.

URL: ${url}
Title: ${title}
Content: ${content.substring(0, 4000)}...
Parliament Session: ${parliamentSessionId}

Please analyze this content and return a JSON object with the following structure:

{
  "title_or_summary": "A concise, descriptive title/summary (max 150 chars)",
  "description_or_details": "A detailed description of what this evidence shows and its significance (2-3 sentences)",
  "evidence_source_type": "One of: news_release_canada, government_announcement, policy_document, legislation, budget_document, ministerial_statement, canada_gazette, orders_in_council, report, other",
  "key_concepts": ["array", "of", "relevant", "keywords", "and", "concepts"],
  "potential_relevance_score": "High, Medium, or Low",
  "sponsoring_department_standardized": "The government department responsible (if identifiable)"
}

For evidence_source_type, choose based on these guidelines:
- "news_release_canada": Official news releases from canada.ca or gc.ca domains
- "government_announcement": General government announcements and statements
- "policy_document": Policy papers, strategy documents, white papers
- "legislation": Bills, acts, legislative documents from parl.ca
- "budget_document": Budget-related documents and announcements
- "ministerial_statement": Statements from specific ministers
- "canada_gazette": Regulatory publications (if from gazette.gc.ca)
- "orders_in_council": Executive orders and regulatory decisions
- "report": Research reports, studies, commissioned reports
- "other": If none of the above categories fit

Focus on:
- Government actions, announcements, or policy changes
- Programs, initiatives, or funding announcements  
- Legislative or regulatory updates
- How this might relate to government promises or commitments
- Use clear, concise language
`;

    const response = await genAI.models.generateContent({
      model: "gemini-2.5-flash-preview-05-20",
      contents: prompt
    });
    
    // Extract text from response
    let responseText = response.text;
    
    if (!responseText) {
      throw new Error('Empty response from LLM');
    }

    // Strip markdown formatting if present
    if (responseText.includes('```json')) {
      const jsonMatch = responseText.match(/```json\s*([\s\S]*?)\s*```/);
      if (jsonMatch && jsonMatch[1]) {
        responseText = jsonMatch[1].trim();
      }
    } else if (responseText.includes('```')) {
      // Handle cases where it might just be ``` without json
      const codeMatch = responseText.match(/```\s*([\s\S]*?)\s*```/);
      if (codeMatch && codeMatch[1]) {
        responseText = codeMatch[1].trim();
      }
    }
    
    try {
      const parsed = JSON.parse(responseText);
      
      // Validate that the suggested source type is valid
      if (parsed.evidence_source_type && !isValidSourceType(parsed.evidence_source_type)) {
        console.warn(`LLM suggested invalid source type: ${parsed.evidence_source_type}, defaulting to 'other'`);
        parsed.evidence_source_type = 'other';
      }
      
      return parsed;
    } catch (parseError) {
      console.error('Error parsing LLM response:', parseError);
      console.error('Raw LLM response:', response.text);
      console.error('Cleaned response text:', responseText);
      throw new Error('Invalid JSON response from LLM');
    }
  } catch (error) {
    console.error('Error calling Gemini LLM:', error);
    throw error;
  }
}

// Generate evidence ID following the pattern from processing jobs
function generateEvidenceId(parliamentSessionId: string): string {
  const dateStr = new Date().toISOString().split('T')[0].replace(/-/g, '');
  const sessionStr = parliamentSessionId || 'unknown';
  const randomHash = Math.random().toString(36).substring(2, 12);
  return `${dateStr}_${sessionStr}_Manual_${randomHash}`;
}

// Check if an evidence item with the same URL already exists
async function checkForDuplicateUrl(sourceUrl: string, parliamentSessionId: string): Promise<{ exists: boolean; existingItem?: any }> {
  try {
    const query = await db.collection('evidence_items')
      .where('parliament_session_id', '==', parliamentSessionId)
      .where('source_url', '==', sourceUrl)
      .limit(1)
      .get();

    if (!query.empty) {
      const existingDoc = query.docs[0];
      return {
        exists: true,
        existingItem: {
          id: existingDoc.id,
          ...existingDoc.data()
        }
      };
    }

    return { exists: false };
  } catch (error) {
    console.error('Error checking for duplicate URL:', error);
    // Don't block creation if we can't check - just log the error
    return { exists: false };
  }
}

// Function to trigger progress rescoring for specific promises
async function triggerPromiseRescoring(promiseIds: string[]) {
  if (!promiseIds || promiseIds.length === 0) return;
  
  try {
    console.log(`Triggering progress rescoring for ${promiseIds.length} promises:`, promiseIds);
    
    for (const promiseId of promiseIds) {
      // Get all evidence items linked to this promise
      const evidenceQuery = await db.collection('evidence_items')
        .where('promise_ids', 'array-contains', promiseId)
        .get();
      
      const evidenceCount = evidenceQuery.size;
      
      // Simple progress scoring based on evidence count
      // This is a simplified version - can be enhanced later
      let progressScore = 0;
      if (evidenceCount > 0) {
        // Calculate score based on evidence count (0-100 scale)
        progressScore = Math.min(evidenceCount * 10, 100);
      }
      
      // Update the promise with the new score
      await db.collection('promises').doc(promiseId).update({
        progress_score: progressScore,
        evidence_count: evidenceCount,
        last_scored_at: admin.firestore.FieldValue.serverTimestamp()
      });
      
      console.log(`Updated promise ${promiseId}: score=${progressScore}, evidence_count=${evidenceCount}`);
    }
  } catch (error) {
    console.error('Error triggering promise rescoring:', error);
    // Don't throw - we don't want rescoring errors to break evidence operations
  }
}

export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { 
      source_url, 
      title_or_summary, 
      description_or_details, 
      evidence_source_type, 
      selected_promise_ids = [],
      creation_mode,
      parliament_session_id 
    } = body;

    console.log('POST /api/admin/evidence called with:', { 
      creation_mode, 
      source_url, 
      parliament_session_id,
      selected_promise_ids 
    });

    if (!source_url) {
      return NextResponse.json({ error: 'Source URL is required' }, { status: 400 });
    }

    if (!parliament_session_id) {
      return NextResponse.json({ error: 'Parliament session ID is required' }, { status: 400 });
    }

    // Check for duplicate URL
    const duplicateCheck = await checkForDuplicateUrl(source_url, parliament_session_id);
    if (duplicateCheck.exists) {
      return NextResponse.json({ 
        error: 'An evidence item with this URL already exists',
        duplicate: true,
        existing_item: duplicateCheck.existingItem
      }, { status: 409 }); // 409 Conflict status
    }

    const evidenceId = generateEvidenceId(parliament_session_id);
    const timestamp = admin.firestore.Timestamp.now();

    if (creation_mode === 'manual') {
      // Manual mode: use provided data directly
      if (!title_or_summary || !description_or_details || !evidence_source_type) {
        return NextResponse.json({ 
          error: 'Manual mode requires title_or_summary, description_or_details, and evidence_source_type' 
        }, { status: 400 });
      }

      const evidenceData = {
        evidence_id: evidenceId,
        promise_ids: selected_promise_ids,
        parliament_session_id,
        evidence_source_type: EVIDENCE_SOURCE_TYPE_MAPPING[evidence_source_type] || evidence_source_type,
        evidence_source_type_key: evidence_source_type,  // Add key for frontend form
        evidence_date: timestamp,
        title_or_summary,
        description_or_details,
        source_url,
        linked_departments: [],
        ingested_at: timestamp,
        promise_linking_status: 'manual_admin_linked',
        creation_method: 'manual_admin',
        created_by: 'admin_interface'
      };

      await db.collection('evidence_items').doc(evidenceId).set(evidenceData);
      console.log(`Successfully wrote evidence item to database: ${evidenceId}`);

      await triggerPromiseRescoring(selected_promise_ids);

      return NextResponse.json({ 
        success: true, 
        evidence_id: evidenceId,
        message: 'Evidence item created successfully',
        evidence_data: evidenceData  // Return the full evidence data for frontend
      });

    } else {
      // Automated mode: scrape and analyze with LLM
      console.log('Starting automated processing for URL:', source_url);
      
      // Step 1: Scrape the webpage
      const scrapedData = await scrapeWebpage(source_url);
      if (scrapedData.error) {
        return NextResponse.json({ 
          error: `Failed to scrape webpage: ${scrapedData.error}` 
        }, { status: 400 });
      }

      if (!scrapedData.content || scrapedData.content.length < 100) {
        return NextResponse.json({ 
          error: 'Insufficient content found on webpage' 
        }, { status: 400 });
      }

      console.log('Scraped content length:', scrapedData.content.length);

      // Step 2: Analyze with Gemini LLM
      const analysisResult = await analyzeContent(
        source_url, 
        scrapedData.title, 
        scrapedData.content, 
        parliament_session_id
      );

      console.log('LLM analysis result:', analysisResult);
      console.log('LLM suggested source type:', analysisResult.evidence_source_type);

      // Step 3: Create evidence item with LLM analysis
      const suggestedSourceTypeKey = analysisResult.evidence_source_type || 'other';
      console.log('Using source type key:', suggestedSourceTypeKey);
      console.log('Mapped to label:', EVIDENCE_SOURCE_TYPE_MAPPING[suggestedSourceTypeKey]);
      
      const evidenceData = {
        evidence_id: evidenceId,
        promise_ids: selected_promise_ids,
        parliament_session_id,
        evidence_source_type: EVIDENCE_SOURCE_TYPE_MAPPING[suggestedSourceTypeKey] || EVIDENCE_SOURCE_TYPE_MAPPING['other'],
        evidence_source_type_key: suggestedSourceTypeKey,  // Include key for frontend form
        evidence_date: timestamp,
        title_or_summary: analysisResult.title_or_summary || scrapedData.title,
        description_or_details: analysisResult.description_or_details || 'Automated analysis of government webpage content',
        source_url,
        linked_departments: analysisResult.sponsoring_department_standardized ? [analysisResult.sponsoring_department_standardized] : [],
        ingested_at: timestamp,
        potential_relevance_score: analysisResult.potential_relevance_score || 'Medium',
        key_concepts: analysisResult.key_concepts || [],
        promise_linking_status: 'manual_admin_linked',
        creation_method: 'automated_admin',
        created_by: 'admin_interface',
        llm_analysis_raw: analysisResult,
        scraped_title: scrapedData.title,
        scraped_content_length: scrapedData.content.length
      };

      console.log('Evidence data being saved:', {
        evidence_source_type: evidenceData.evidence_source_type,
        evidence_source_type_key: evidenceData.evidence_source_type_key
      });

      await db.collection('evidence_items').doc(evidenceId).set(evidenceData);
      console.log(`Successfully wrote evidence item to database: ${evidenceId}`);

      await triggerPromiseRescoring(selected_promise_ids);

      return NextResponse.json({ 
        success: true, 
        evidence_id: evidenceId,
        message: 'Evidence item created successfully with automated analysis',
        analysis: analysisResult,
        evidence_data: evidenceData  // Return the full evidence data for frontend
      });
    }

  } catch (error) {
    console.error('Error in POST /api/admin/evidence:', error);
    return NextResponse.json({ 
      error: error instanceof Error ? error.message : 'Internal server error' 
    }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const parliamentSessionId = searchParams.get('parliament_session_id');
    const search = searchParams.get('search');
    const limit = parseInt(searchParams.get('limit') || '50');

    if (!parliamentSessionId) {
      return NextResponse.json({ error: 'Parliament session ID is required' }, { status: 400 });
    }

    let query = db.collection('evidence_items')
      .where('parliament_session_id', '==', parliamentSessionId);

    if (search) {
      // Note: Firestore doesn't support full-text search natively
      // This is a basic implementation - you might want to use Algolia or similar for better search
      const evidenceItems = await query.limit(200).get();
      const searchLower = search.toLowerCase();
      
      const filteredItems = evidenceItems.docs
        .map(doc => ({ id: doc.id, ...doc.data() } as EvidenceItem))
        .filter((item: EvidenceItem) => 
          item.title_or_summary?.toLowerCase().includes(searchLower) ||
          item.description_or_details?.toLowerCase().includes(searchLower) ||
          item.source_url?.toLowerCase().includes(searchLower)
        )
        .slice(0, limit);

      return NextResponse.json({ evidence_items: filteredItems });
    } else {
      const evidenceItems = await query.limit(limit).get();
      const items = evidenceItems.docs.map(doc => ({ id: doc.id, ...doc.data() } as EvidenceItem));
      return NextResponse.json({ evidence_items: items });
    }

  } catch (error) {
    console.error('Error in GET /api/admin/evidence:', error);
    return NextResponse.json({ 
      error: error instanceof Error ? error.message : 'Internal server error' 
    }, { status: 500 });
  }
}

export async function PUT(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const evidenceId = searchParams.get('id');
    
    if (!evidenceId) {
      return NextResponse.json({ error: 'Evidence ID is required' }, { status: 400 });
    }

    const body = await request.json();
    const { 
      source_url, 
      title_or_summary, 
      description_or_details, 
      evidence_source_type, 
      selected_promise_ids = [],
      parliament_session_id
    } = body;

    if (!source_url || !title_or_summary || !description_or_details || !evidence_source_type) {
      return NextResponse.json({ 
        error: 'All fields are required for updates' 
      }, { status: 400 });
    }

    // Get current evidence item to get parliament_session_id if not provided
    const currentDoc = await db.collection('evidence_items').doc(evidenceId).get();
    if (!currentDoc.exists) {
      return NextResponse.json({ error: 'Evidence item not found' }, { status: 404 });
    }
    
    const currentData = currentDoc.data();
    const sessionId = parliament_session_id || currentData?.parliament_session_id;
    
    if (!sessionId) {
      return NextResponse.json({ error: 'Parliament session ID is required' }, { status: 400 });
    }

    // Check for duplicate URL in OTHER evidence items (exclude current item)
    const duplicateQuery = await db.collection('evidence_items')
      .where('parliament_session_id', '==', sessionId)
      .where('source_url', '==', source_url)
      .get();

    // Filter out the current item being edited
    const duplicateItems = duplicateQuery.docs.filter(doc => doc.id !== evidenceId);
    
    if (duplicateItems.length > 0) {
      const existingItem = duplicateItems[0];
      return NextResponse.json({ 
        error: 'An evidence item with this URL already exists',
        duplicate: true,
        existing_item: {
          id: existingItem.id,
          ...existingItem.data()
        }
      }, { status: 409 }); // 409 Conflict status
    }

    const updateData = {
      source_url,
      title_or_summary,
      description_or_details,
      evidence_source_type: EVIDENCE_SOURCE_TYPE_MAPPING[evidence_source_type] || evidence_source_type,
      evidence_source_type_key: evidence_source_type,  // Add key for consistency
      promise_ids: selected_promise_ids,
      updated_at: admin.firestore.Timestamp.now(),
      updated_by: 'admin_interface'
    };

    await db.collection('evidence_items').doc(evidenceId).update(updateData);

    await triggerPromiseRescoring(selected_promise_ids);

    return NextResponse.json({ 
      success: true, 
      evidence_id: evidenceId,
      message: 'Evidence item updated successfully' 
    });

  } catch (error) {
    console.error('Error in PUT /api/admin/evidence:', error);
    return NextResponse.json({ 
      error: error instanceof Error ? error.message : 'Internal server error' 
    }, { status: 500 });
  }
}

export async function DELETE(request: NextRequest) {
  try {
    const { searchParams } = new URL(request.url);
    const evidenceId = searchParams.get('id');
    
    if (!evidenceId) {
      return NextResponse.json({ error: 'Evidence ID is required' }, { status: 400 });
    }

    // Step 1: Get the evidence item to find linked promises
    const evidenceDoc = await db.collection('evidence_items').doc(evidenceId).get();
    
    if (!evidenceDoc.exists) {
      return NextResponse.json({ error: 'Evidence item not found' }, { status: 404 });
    }

    const evidenceData = evidenceDoc.data();
    const linkedPromiseIds = evidenceData?.promise_ids || [];

    console.log(`Deleting evidence ${evidenceId}, cleaning up ${linkedPromiseIds.length} promise references`);

    // Step 2: Remove evidence reference from all linked promises
    if (linkedPromiseIds.length > 0) {
      const batch = db.batch();
      
      for (const promiseId of linkedPromiseIds) {
        try {
          const promiseRef = db.collection('promises').doc(promiseId);
          const promiseDoc = await promiseRef.get();
          
          if (promiseDoc.exists) {
            const promiseData = promiseDoc.data();
            const linkedEvidence = promiseData?.linked_evidence || [];
            
            // Remove this evidence from the linked_evidence array
            const updatedLinkedEvidence = linkedEvidence.filter((link: any) => {
              // Handle both object and string formats
              if (typeof link === 'object' && link.evidence_id) {
                return link.evidence_id !== evidenceId;
              } else if (typeof link === 'string') {
                return link !== evidenceId;
              }
              return true;
            });

            // Update the promise with cleaned linked_evidence
            batch.update(promiseRef, {
              linked_evidence: updatedLinkedEvidence,
              evidence_cleanup_timestamp: admin.firestore.Timestamp.now()
            });
            
            console.log(`Removed evidence ${evidenceId} from promise ${promiseId}`);
          }
        } catch (error) {
          console.warn(`Failed to clean up promise ${promiseId}: ${error}`);
          // Continue with other promises even if one fails
        }
      }
      
      // Commit all promise updates
      await batch.commit();
    }

    // Step 3: Delete the evidence item
    await db.collection('evidence_items').doc(evidenceId).delete();
    
    console.log(`Successfully deleted evidence ${evidenceId} and cleaned up ${linkedPromiseIds.length} promise references`);

    await triggerPromiseRescoring(linkedPromiseIds);

    return NextResponse.json({ 
      success: true, 
      message: 'Evidence item deleted successfully and references cleaned up',
      cleaned_promises: linkedPromiseIds.length
    });

  } catch (error) {
    console.error('Error in DELETE /api/admin/evidence:', error);
    return NextResponse.json({ 
      error: error instanceof Error ? error.message : 'Internal server error' 
    }, { status: 500 });
  }
} 