#!/usr/bin/env python
# PromiseTracker/scripts/linking_jobs/link_evidence_to_promises.py
# Links existing evidence_items to relevant promises in promises_dev collection
# using hybrid approach: departmental matching, keyword overlap, and LLM assessment

import firebase_admin
from firebase_admin import firestore, credentials
import os
from google import genai
from google.genai.types import GenerationConfig
import time
import asyncio
import logging
import traceback
from dotenv import load_dotenv
import json
import argparse
from datetime import datetime, timezone
import uuid
import re

# --- Load Environment Variables ---
load_dotenv()
# --- End Load Environment Variables ---

# --- Logger Setup ---
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S')
logger = logging.getLogger("link_evidence_to_promises")
# --- End Logger Setup ---

# --- Firebase Configuration ---
db = None
if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app()
        project_id = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Default]')
        logger.info(f"Connected to CLOUD Firestore (Project: {project_id}) using default credentials.")
        db = firestore.client()
    except Exception as e_default:
        logger.warning(f"Cloud Firestore init with default creds failed: {e_default}. Attempting service account.")
        cred_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
        if cred_path:
            try:
                logger.info(f"Attempting Firebase init with service account key from env var: {cred_path}")
                cred = credentials.Certificate(cred_path)
                app_name = 'link_evidence_app'
                try:
                    firebase_admin.initialize_app(cred, name=app_name)
                except ValueError:
                    app_name_unique = f"{app_name}_{str(time.time())}"
                    firebase_admin.initialize_app(cred, name=app_name_unique)
                    app_name = app_name_unique

                project_id_sa = os.getenv('FIREBASE_PROJECT_ID', '[Not Set - Using Service Account]')
                logger.info(f"Connected to CLOUD Firestore (Project: {project_id_sa}) via service account.")
                db = firestore.client(app=firebase_admin.get_app(name=app_name))
            except Exception as e_sa:
                logger.critical(f"Firebase init with service account key from {cred_path} failed: {e_sa}", exc_info=True)
        else:
            logger.warning("FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable not set, and default creds failed.")

if db is None:
    logger.critical("CRITICAL: Failed to obtain Firestore client. Exiting.")
    exit("Exiting: Firestore client not available.")
# --- End Firebase Configuration ---

# --- Gemini Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.critical("GEMINI_API_KEY not found in environment variables or .env file.")
    exit("Exiting: Missing GEMINI_API_KEY.")

# Ensure GOOGLE_API_KEY is set for genai.Client()
if "GOOGLE_API_KEY" not in os.environ and GEMINI_API_KEY:
    os.environ["GOOGLE_API_KEY"] = GEMINI_API_KEY

LLM_MODEL_NAME = os.getenv("GEMINI_MODEL_EVIDENCE_LINKING", "models/gemini-2.5-pro-preview-05-20")
GENERATION_CONFIG_DICT = {
    "temperature": 0.1,
    "top_p": 0.95,
    "top_k": 64,
    "max_output_tokens": 8192,
    "response_mime_type": "application/json",
}

client = None
try:
    client = genai.Client()
    logger.info(f"Successfully initialized Gemini Client with model: {LLM_MODEL_NAME}")
except Exception as e:
    logger.critical(f"Failed to initialize Gemini client: {e}", exc_info=True)
    exit("Exiting: Gemini client initialization failed.")
# --- End Gemini Configuration ---

# --- Constants ---
PROMISES_COLLECTION = 'promises_dev'
EVIDENCE_ITEMS_COLLECTION = 'evidence_items_test'  # or evidence_items
POTENTIAL_LINKS_COLLECTION = 'potential_links_dev'

# Threshold values for pre-LLM filtering
KEYWORD_JACCARD_THRESHOLD = 0.1
KEYWORD_COMMON_COUNT_THRESHOLD = 2
MAX_CANDIDATE_PROMISES_FOR_LLM = 10

# Rate limiting
RATE_LIMIT_DELAY_SECONDS = 2
LLM_RETRY_DELAY = 5
MAX_LLM_RETRIES = 2
# --- End Constants ---

# Government platform context for LLM prompts
GOVERNMENT_PLATFORM_CONTEXT = """
The Liberal Party of Canada (LPC) won the 44th Parliament election in 2021, forming the government. 
This analysis focuses on linking government evidence items (bills, announcements, policy updates, etc.) 
to specific promises made during the 44th Parliament session.
"""


def calculate_keyword_overlap(evidence_keywords: list, promise_keywords: list) -> dict:
    """
    Calculates Jaccard index and common keyword count between evidence and promise keywords.
    """
    if not evidence_keywords or not promise_keywords:
        return {"jaccard": 0.0, "common_count": 0}
    
    # Convert to lowercase sets for case-insensitive comparison
    set_evidence = set(k.lower().strip() for k in evidence_keywords if isinstance(k, str) and k.strip())
    set_promise = set(k.lower().strip() for k in promise_keywords if isinstance(k, str) and k.strip())
    
    intersection_len = len(set_evidence.intersection(set_promise))
    union_len = len(set_evidence.union(set_promise))
    
    jaccard = intersection_len / union_len if union_len > 0 else 0.0
    common_count = intersection_len
    
    return {"jaccard": jaccard, "common_count": common_count}


def check_departmental_match(evidence_departments: list, promise_responsible_dept: str, promise_relevant_depts: list) -> bool:
    """
    Determines if there's a departmental match between evidence and promise.
    """
    if not evidence_departments:
        return True  # If no departments specified in evidence, consider it a match
    
    evidence_depts_lower = set(dept.lower().strip() for dept in evidence_departments if isinstance(dept, str))
    
    # Check responsible department
    if promise_responsible_dept and promise_responsible_dept.lower().strip() in evidence_depts_lower:
        return True
    
    # Check relevant departments
    if promise_relevant_depts:
        promise_depts_lower = set(dept.lower().strip() for dept in promise_relevant_depts if isinstance(dept, str))
        if evidence_depts_lower.intersection(promise_depts_lower):
            return True
    
    return False


async def fetch_unlinked_evidence_items(parliament_session_target: str, evidence_source_type_filter: str = None, 
                                       limit: int = None) -> list[firestore.DocumentSnapshot]:
    """
    Fetches evidence items that need linking processing.
    """
    logger.info(f"Fetching unlinked evidence items for parliament session: {parliament_session_target}")
    
    try:
        # Build base query
        query = db.collection(EVIDENCE_ITEMS_COLLECTION).where(
            filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_target)
        ).where(
            filter=firestore.FieldFilter("linking_status", "in", [None, "pending_linking"])
        )
        
        # Add source type filter if specified
        if evidence_source_type_filter:
            query = query.where(
                filter=firestore.FieldFilter("evidence_source_type", "==", evidence_source_type_filter)
            )
        
        # Apply limit if specified
        if limit:
            query = query.limit(limit)
        
        # Execute query
        evidence_docs = list(await asyncio.to_thread(query.stream))
        logger.info(f"Found {len(evidence_docs)} evidence items to process")
        
        return evidence_docs
        
    except Exception as e:
        logger.error(f"Error fetching evidence items: {e}", exc_info=True)
        return []


async def fetch_candidate_promises(evidence_data: dict, parliament_session_id: str) -> list[dict]:
    """
    Fetches candidate promises based on departmental matching and keyword overlap.
    Returns list of promise candidates with scores.
    """
    evidence_departments = evidence_data.get('linked_departments', [])
    
    # Get evidence keywords based on type
    evidence_keywords = []
    if evidence_data.get('evidence_source_type') == "Bill Event (LEGISinfo)":
        evidence_keywords = evidence_data.get('bill_extracted_keywords_concepts', [])
    else:
        evidence_keywords = evidence_data.get('key_concepts', [])
    
    logger.debug(f"Fetching candidate promises for parliament session: {parliament_session_id}")
    
    try:
        # Query promises for the parliament session
        promises_query = db.collection(PROMISES_COLLECTION).where(
            filter=firestore.FieldFilter("parliament_session_id", "==", parliament_session_id)
        )
        
        promise_docs = list(await asyncio.to_thread(promises_query.stream))
        logger.info(f"Found {len(promise_docs)} total promises for session {parliament_session_id}")
        
        candidates = []
        
        for promise_doc in promise_docs:
            promise_data = promise_doc.to_dict()
            promise_data['promise_id'] = promise_doc.id
            
            # A. Departmental Match
            dept_match = check_departmental_match(
                evidence_departments,
                promise_data.get('responsible_department_lead'),
                promise_data.get('relevant_departments', [])
            )
            
            # If evidence has specific departments but no match, skip
            if not dept_match and evidence_departments:
                continue
            
            # B. Keyword/Concept Overlap
            promise_keywords = promise_data.get('extracted_keywords_concepts', [])
            keyword_overlap = calculate_keyword_overlap(evidence_keywords, promise_keywords)
            
            # Check if meets threshold for consideration
            jaccard_score = keyword_overlap["jaccard"]
            common_count = keyword_overlap["common_count"]
            
            is_candidate = (
                jaccard_score >= KEYWORD_JACCARD_THRESHOLD or
                common_count >= KEYWORD_COMMON_COUNT_THRESHOLD
            )
            
            if is_candidate:
                combined_score = jaccard_score + (common_count * 0.1)
                candidates.append({
                    'promise_data': promise_data,
                    'keyword_overlap': keyword_overlap,
                    'combined_score': combined_score
                })
        
        # Sort by combined score and limit to top candidates
        candidates.sort(key=lambda x: x['combined_score'], reverse=True)
        candidates = candidates[:MAX_CANDIDATE_PROMISES_FOR_LLM]
        
        logger.info(f"Found {len(candidates)} candidate promises after filtering")
        return candidates
        
    except Exception as e:
        logger.error(f"Error fetching candidate promises: {e}", exc_info=True)
        return []


async def assess_relevance_with_llm(evidence_data: dict, promise_data: dict) -> dict | None:
    """
    Uses LLM to assess relevance between an evidence item and a promise.
    Returns assessment dict following the specified JSON structure or None on failure.
    """
    evidence_id = evidence_data.get('evidence_id', 'N/A')
    promise_id = promise_data.get('promise_id', 'N/A')
    
    # Prepare evidence keywords based on type
    evidence_keywords = []
    if evidence_data.get('evidence_source_type') == "Bill Event (LEGISinfo)":
        evidence_keywords = evidence_data.get('bill_extracted_keywords_concepts', [])
    else:
        evidence_keywords = evidence_data.get('key_concepts', [])
    
    # Construct the LLM prompt with all required placeholders
    prompt = f"""{GOVERNMENT_PLATFORM_CONTEXT}

TASK: Assess the relevance between a government evidence item and a specific political promise to determine if they should be linked.

PROMISE INFORMATION:
- Promise Text: "{promise_data.get('text', 'N/A')}"
- Promise Keywords: {json.dumps(promise_data.get('extracted_keywords_concepts', []))}
- Responsible Department: "{promise_data.get('responsible_department_lead', 'N/A')}"
- Relevant Departments: {json.dumps(promise_data.get('relevant_departments', []))}
- Parliament Session: "{promise_data.get('parliament_session_id', 'N/A')}"

EVIDENCE INFORMATION:
- Evidence Type: "{evidence_data.get('evidence_source_type', 'N/A')}"
- Evidence Title/Summary: "{evidence_data.get('title_or_summary', 'N/A')}"
- Evidence Description/Details: "{evidence_data.get('description_or_details', 'N/A')[:500]}..."
- Evidence Keywords: {json.dumps(evidence_keywords)}
- Evidence Date: "{evidence_data.get('evidence_date', 'N/A')}"
- Linked Departments: {json.dumps(evidence_data.get('linked_departments', []))}

INSTRUCTIONS:
Analyze if this evidence item represents a direct action, implementation step, or significant development related to fulfilling the government promise. Consider scope, intent, departments, timing, and policy alignment.

Respond with a JSON object containing exactly these fields:
{{
  "is_directly_related": boolean,
  "relevance_score": "High" | "Medium" | "Low" | "Not Related",
  "explanation": "1-3 sentence justification for the score and relation",
  "link_type_suggestion": "Legislative Step" | "Funding Announcement" | "Program Launch" | "Policy Update" | "Consultation" | "Appointment" | "Regulation Enacted" | "General Information",
  "status_impact_suggestion": "In Progress" | "Milestone Achieved" | "Commitment Fulfilled" | "No Change" | "Information Only"
}}"""

    for attempt in range(MAX_LLM_RETRIES + 1):
        try:
            logger.debug(f"Calling LLM for evidence {evidence_id} <-> promise {promise_id} (attempt {attempt + 1})")
            
            response = await client.aio.models.generate_content(
                model=LLM_MODEL_NAME,
                contents=prompt,
                config=GenerationConfig(**GENERATION_CONFIG_DICT)
            )
            
            # Parse the JSON response
            response_text = response.text.strip()
            
            # Clean potential markdown formatting
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            
            assessment = json.loads(response_text.strip())
            
            # Validate response structure
            required_fields = ["is_directly_related", "relevance_score", "explanation"]
            if not all(field in assessment for field in required_fields):
                logger.warning(f"LLM response missing required fields for {evidence_id} <-> {promise_id}: {assessment}")
                if attempt < MAX_LLM_RETRIES:
                    continue
                return None
            
            # Validate enum values
            valid_relevance_scores = ["High", "Medium", "Low", "Not Related"]
            if assessment.get("relevance_score") not in valid_relevance_scores:
                logger.warning(f"Invalid relevance score for {evidence_id} <-> {promise_id}: {assessment.get('relevance_score')}")
                if attempt < MAX_LLM_RETRIES:
                    continue
                return None
            
            logger.info(f"LLM Assessment for {evidence_id} <-> {promise_id}: {assessment['relevance_score']} (directly_related: {assessment['is_directly_related']})")
            return assessment
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for {evidence_id} <-> {promise_id} (attempt {attempt + 1}): {e}. Response: {response_text if 'response_text' in locals() else 'N/A'}")
        except Exception as e:
            logger.error(f"Error calling LLM for {evidence_id} <-> {promise_id} (attempt {attempt + 1}): {e}", exc_info=True)
        
        if attempt < MAX_LLM_RETRIES:
            logger.info(f"Retrying LLM call in {LLM_RETRY_DELAY}s...")
            await asyncio.sleep(LLM_RETRY_DELAY)
    
    return None


async def create_potential_link(evidence_data: dict, promise_data: dict, keyword_overlap: dict, 
                               llm_assessment: dict, parliament_session_id: str) -> str | None:
    """
    Creates a potential link document in the potential_links_dev collection.
    Returns the created link ID or None on failure.
    """
    try:
        potential_link_id = str(uuid.uuid4())
        
        # Create link data with all required fields
        link_data = {
            'potential_link_id': potential_link_id,
            'promise_id': promise_data.get('promise_id'),
            'evidence_id': evidence_data.get('evidence_id'),
            'parliament_session_id': parliament_session_id,
            'promise_text_snippet': promise_data.get('text', '')[:150],
            'evidence_title_or_summary': evidence_data.get('title_or_summary', ''),
            'keyword_overlap_score_calculated': keyword_overlap,
            'llm_is_directly_related': llm_assessment.get('is_directly_related'),
            'llm_relevance_score': llm_assessment.get('relevance_score'),
            'llm_explanation': llm_assessment.get('explanation'),
            'llm_link_type_suggestion': llm_assessment.get('link_type_suggestion'),
            'llm_status_impact_suggestion': llm_assessment.get('status_impact_suggestion'),
            'link_status': 'pending_review',
            'created_at': firestore.SERVER_TIMESTAMP,
            'llm_model_used': LLM_MODEL_NAME
        }
        
        # Create the document
        doc_ref = db.collection(POTENTIAL_LINKS_COLLECTION).document(potential_link_id)
        await asyncio.to_thread(doc_ref.set, link_data)
        
        logger.info(f"Created potential link {potential_link_id}: {evidence_data.get('evidence_id')} <-> {promise_data.get('promise_id')}")
        return potential_link_id
        
    except Exception as e:
        logger.error(f"Error creating potential link: {e}", exc_info=True)
        return None


async def process_single_evidence_item(evidence_doc: firestore.DocumentSnapshot, parliament_session_id: str, dry_run: bool = False) -> dict:
    """
    Processes a single evidence item for linking to promises.
    Returns processing statistics.
    """
    evidence_id = evidence_doc.id
    evidence_data = evidence_doc.to_dict()
    evidence_data['evidence_id'] = evidence_id
    
    stats = {
        'evidence_id': evidence_id,
        'candidates_found': 0,
        'llm_assessments_made': 0,
        'potential_links_created': 0,
        'status': 'processed',
        'error': None
    }
    
    logger.info(f"Processing evidence item: {evidence_id} ({evidence_data.get('evidence_source_type')})")
    
    try:
        # A. Fetch Candidate Promises (Pre-LLM Filtering)
        candidates = await fetch_candidate_promises(evidence_data, parliament_session_id)
        stats['candidates_found'] = len(candidates)
        
        if not candidates:
            logger.info(f"No candidate promises found for evidence {evidence_id}")
            stats['status'] = 'no_candidates_found'
            return stats
        
        # B. LLM-Powered Relevance Assessment
        for candidate in candidates:
            promise_data = candidate['promise_data']
            keyword_overlap = candidate['keyword_overlap']
            
            # Call LLM for assessment
            llm_assessment = await assess_relevance_with_llm(evidence_data, promise_data)
            stats['llm_assessments_made'] += 1
            
            if llm_assessment is None:
                logger.warning(f"LLM assessment failed for {evidence_id} <-> {promise_data.get('promise_id')}")
                continue
            
            # C. Store Potential Links (only if directly related and High/Medium relevance)
            if (llm_assessment.get('is_directly_related') and 
                llm_assessment.get('relevance_score') in ['High', 'Medium']):
                
                if not dry_run:
                    link_id = await create_potential_link(
                        evidence_data, promise_data, keyword_overlap, 
                        llm_assessment, parliament_session_id
                    )
                    
                    if link_id:
                        stats['potential_links_created'] += 1
                else:
                    logger.info(f"[DRY RUN] Would create link: {evidence_id} <-> {promise_data.get('promise_id')} ({llm_assessment.get('relevance_score')})")
                    stats['potential_links_created'] += 1
            
            # Rate limiting between LLM calls
            await asyncio.sleep(1)
        
        logger.info(f"Completed processing {evidence_id}: {stats['potential_links_created']} links created from {stats['candidates_found']} candidates")
        
    except Exception as e:
        logger.error(f"Error processing evidence item {evidence_id}: {e}", exc_info=True)
        stats['status'] = 'error'
        stats['error'] = str(e)
    
    return stats


async def update_evidence_linking_status(evidence_id: str, status: str, error_message: str = None, dry_run: bool = False):
    """
    Updates the linking status of an evidence item.
    """
    try:
        update_data = {
            'linking_status': status,
            'linking_processed_at': firestore.SERVER_TIMESTAMP
        }
        
        if error_message:
            update_data['linking_error_message'] = error_message[:500]
        
        if not dry_run:
            doc_ref = db.collection(EVIDENCE_ITEMS_COLLECTION).document(evidence_id)
            await asyncio.to_thread(doc_ref.update, update_data)
            logger.debug(f"Updated evidence {evidence_id} status to: {status}")
        else:
            logger.info(f"[DRY RUN] Would update evidence {evidence_id} status to: {status}")
        
    except Exception as e:
        logger.error(f"Failed to update status for evidence {evidence_id}: {e}", exc_info=True)


async def main_linking_process(parliament_session_target: str, evidence_source_type_filter: str = None,
                              limit: int = None, dry_run: bool = False):
    """
    Main process for linking evidence items to promises.
    """
    logger.info("=== Starting Evidence to Promise Linking Process ===")
    logger.info(f"Parliament Session: {parliament_session_target}")
    logger.info(f"Evidence Source Filter: {evidence_source_type_filter or 'None'}")
    logger.info(f"Limit: {limit or 'None'}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info(f"Collections: {EVIDENCE_ITEMS_COLLECTION} -> {PROMISES_COLLECTION} -> {POTENTIAL_LINKS_COLLECTION}")
    
    if dry_run:
        logger.warning("*** DRY RUN MODE: No changes will be written to Firestore ***")
    
    # Fetch Unlinked Evidence Items
    evidence_docs = await fetch_unlinked_evidence_items(
        parliament_session_target, evidence_source_type_filter, limit
    )
    
    if not evidence_docs:
        logger.info("No evidence items found for processing. Exiting.")
        return
    
    # Initialize statistics
    total_stats = {
        'total_processed': 0,
        'total_candidates_found': 0,
        'total_llm_assessments': 0,
        'total_links_created': 0,
        'errors': 0,
        'no_candidates_found': 0
    }
    
    # Process each evidence item
    for i, evidence_doc in enumerate(evidence_docs):
        evidence_id = evidence_doc.id
        logger.info(f"--- Processing evidence {i+1}/{len(evidence_docs)}: {evidence_id} ---")
        
        try:
            # Process the evidence item
            stats = await process_single_evidence_item(evidence_doc, parliament_session_target, dry_run)
            
            # Update totals
            total_stats['total_processed'] += 1
            total_stats['total_candidates_found'] += stats['candidates_found']
            total_stats['total_llm_assessments'] += stats['llm_assessments_made']
            total_stats['total_links_created'] += stats['potential_links_created']
            
            if stats['status'] == 'error':
                total_stats['errors'] += 1
            elif stats['status'] == 'no_candidates_found':
                total_stats['no_candidates_found'] += 1
            
            # D. Update Evidence Item Status
            final_status = 'linking_processed'
            if stats['status'] == 'no_candidates_found':
                final_status = 'linking_completed_no_candidates_found'
            elif stats['status'] == 'error':
                final_status = 'linking_error'
            
            await update_evidence_linking_status(
                evidence_id, final_status, stats.get('error'), dry_run
            )
            
        except Exception as e:
            logger.error(f"Critical error processing evidence {evidence_id}: {e}", exc_info=True)
            total_stats['errors'] += 1
            
            await update_evidence_linking_status(
                evidence_id, 'linking_error', str(e), dry_run
            )
        
        # Rate limiting between evidence items
        if i < len(evidence_docs) - 1:
            await asyncio.sleep(RATE_LIMIT_DELAY_SECONDS)
    
    # Final summary
    logger.info("=== Evidence to Promise Linking Process Complete ===")
    logger.info(f"Total evidence items processed: {total_stats['total_processed']}")
    logger.info(f"Total candidate promises found: {total_stats['total_candidates_found']}")
    logger.info(f"Total LLM assessments made: {total_stats['total_llm_assessments']}")
    logger.info(f"Total potential links created: {total_stats['total_links_created']}")
    logger.info(f"Items with no candidates found: {total_stats['no_candidates_found']}")
    logger.info(f"Errors encountered: {total_stats['errors']}")


async def main_async_entrypoint():
    parser = argparse.ArgumentParser(description='Link existing evidence items to promises using hybrid approach.')
    parser.add_argument(
        '--parliament_session_target',
        type=str,
        required=True,
        help='Parliament session ID to target (e.g., "44")'
    )
    parser.add_argument(
        '--evidence_source_type_filter',
        type=str,
        default=None,
        help='Optional filter for evidence source type (e.g., "Bill Event (LEGISinfo)")'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit the number of evidence items to process'
    )
    parser.add_argument(
        '--dry_run',
        action='store_true',
        help='Perform dry run without making changes to Firestore'
    )
    
    args = parser.parse_args()
    
    await main_linking_process(
        parliament_session_target=args.parliament_session_target,
        evidence_source_type_filter=args.evidence_source_type_filter,
        limit=args.limit,
        dry_run=args.dry_run
    )


if __name__ == "__main__":
    asyncio.run(main_async_entrypoint()) 