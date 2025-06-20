// lib/data-flat.ts
// Updated data access layer for flat promises collection structure

import {
  collection,
  getDocs,
  doc,
  getDoc,
  query,
  where,
  FirestoreError,
  limit,
  orderBy,
  Timestamp,
  getCountFromServer,
  documentId
} from "firebase/firestore";
import { db } from "./firebase"; // Your Firebase instance
import type {
  DepartmentConfig,
  MinisterDetails,
  PromiseData,
  EvidenceItem,
} from "./types";
// Functions fetchParliamentSessionDates and fetchEvidenceItemsByIds 
// will be implemented below from the legacy version


/**
 * Get promise counts by party and region for analytics.
 * @param parliamentSessionId The parliament session ID
 * @param regionCode The region code (default: "Canada")
 * @returns Object with counts by party
 */
export async function getPromiseCountsByParty(
  parliamentSessionId: string,
  regionCode: string = "Canada"
): Promise<Record<string, number>> {
  if (!db) {
    console.error("Firestore instance (db) is not available in getPromiseCountsByParty.");
    return {};
  }

  const partyCounts: Record<string, number> = {};
  const knownParties = ["LPC", "CPC", "NDP", "BQ", "GP"];

  try {
    for (const partyCode of knownParties) {
      const q = query(
        collection(db, "promises"),
        where('parliament_session_id', '==', parliamentSessionId),
        where('party_code', '==', partyCode),
        where('region_code', '==', regionCode),
        where('status', '==', 'active')  
      );

      const countSnapshot = await getCountFromServer(q);
      partyCounts[partyCode] = countSnapshot.data().count;
    }

    return partyCounts;
  } catch (error) {
    console.error('Error getting promise counts by party:', error);
    return {};
  }
}

/**
 * Fetch promises for multiple departments efficiently.
 * @param departmentNames Array of department names
 * @param parliamentSessionId The parliament session ID
 * @param governingPartyCode The party code
 * @param regionCode The region code
 * @returns Array of promises across all departments
 */
export async function fetchPromisesForMultipleDepartments(
  departmentNames: string[],
  parliamentSessionId: string,
  governingPartyCode: string,
  regionCode: string = "Canada"
): Promise<PromiseData[]> {
  if (!db || !departmentNames.length) {
    return [];
  }

  try {
    // Use 'in' query for multiple departments (up to 30 items)
    const batchSize = 30; // Firestore 'in' query limit
    const allPromises: PromiseData[] = [];

    for (let i = 0; i < departmentNames.length; i += batchSize) {
      const batch = departmentNames.slice(i, i + batchSize);
      
      const q = query(
        collection(db, "promises"),
        where('responsible_department_lead', 'in', batch),
        where('parliament_session_id', '==', parliamentSessionId),
        where('party_code', '==', governingPartyCode),
        where('region_code', '==', regionCode),
        where('bc_promise_rank', 'in', ["strong", "medium", "Strong", "Medium"]),
        where('status', '==', 'active') // Exclude deleted promises
      );

      const querySnapshot = await getDocs(q);
      querySnapshot.docs.forEach(doc => {
        const data = doc.data();
        allPromises.push({
          id: doc.id,
          text: data.text || '',
          responsible_department_lead: data.responsible_department_lead || '',
          linked_evidence_ids: data.linked_evidence_ids || [],
          parliament_session_id: data.parliament_session_id,
          region_code: data.region_code,
          party_code: data.party_code,
          bc_promise_rank: data.bc_promise_rank,
          bc_promise_direction: data.bc_promise_direction,
          progress_score: data.progress_score,
          progress_summary: data.progress_summary,
          source_type: data.source_type || undefined,
          source_url: data.source_url || undefined,
          concise_title: data.concise_title ?? undefined,
          description: data.description ?? undefined,
          what_it_means_for_canadians: data.what_it_means_for_canadians ?? undefined,
          intended_impact_and_objectives: data.intended_impact_and_objectives ?? undefined,
          background_and_context: data.background_and_context ?? undefined,
          evidence: [], // Populate separately if needed
        } as PromiseData);
      });
    }

    return allPromises;
  } catch (error) {
    console.error('Error fetching promises for multiple departments:', error);
    return [];
  }
}

/**
 * Search promises by text content across parties/regions.
 * @param searchTerm The search term
 * @param parliamentSessionId The parliament session ID
 * @param partyCode Optional party filter
 * @param regionCode Optional region filter
 * @param limitCount Maximum results to return
 * @returns Array of matching promises
 */
export async function searchPromisesByText(
  searchTerm: string,
  parliamentSessionId: string,
  partyCode?: string,
  regionCode?: string,
  limitCount: number = 50
): Promise<PromiseData[]> {
  if (!db || !searchTerm.trim()) {
    return [];
  }

  try {
    let q = query(
      collection(db, "promises"),
      where('parliament_session_id', '==', parliamentSessionId),
      where('status', '==', 'active') // Exclude deleted promises
    );

    if (partyCode) {
      q = query(q, where('party_code', '==', partyCode));
    }
    if (regionCode) {
      q = query(q, where('region_code', '==', regionCode));
    }

    q = query(q, limit(limitCount));

    const querySnapshot = await getDocs(q);
    const matchingPromises: PromiseData[] = [];

    // Note: Firestore doesn't support full-text search natively
    // This is a simple client-side filter - consider using Algolia or similar for production
    querySnapshot.docs.forEach(doc => {
      const data = doc.data();
      const text = data.text || '';
      
      if (text.toLowerCase().includes(searchTerm.toLowerCase())) {
        matchingPromises.push({
          id: doc.id,
          text: text,
          responsible_department_lead: data.responsible_department_lead || '',
          parliament_session_id: data.parliament_session_id,
          region_code: data.region_code,
          party_code: data.party_code,
          bc_promise_rank: data.bc_promise_rank,
          linked_evidence_ids: data.linked_evidence_ids || [],
          evidence: [], // Populate separately if needed
        } as PromiseData);
      }
    });

    return matchingPromises;
  } catch (error) {
    console.error('Error searching promises by text:', error);
    return [];
  }
}

/**
 * Fetches evidence items by their IDs from the evidence_items collection.
 * @param evidenceDocIds Array of evidence document IDs
 * @param sessionStartDate Optional session start date for filtering
 * @param sessionEndDate Optional session end date for filtering
 * @returns Array of EvidenceItem objects
 */
export const fetchEvidenceItemsByIds = async (
  evidenceDocIds: string[],
  sessionStartDate: string | null,
  sessionEndDate: string | null
): Promise<EvidenceItem[]> => {
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchEvidenceItemsByIds.");
    return [];
  }
  if (!evidenceDocIds || evidenceDocIds.length === 0) {
    return [];
  }

  const allEvidenceItems: EvidenceItem[] = [];
  const idChunks: string[][] = [];
  const MAX_IDS_PER_QUERY = 30; // Firestore 'in' query limit

  for (let i = 0; i < evidenceDocIds.length; i += MAX_IDS_PER_QUERY) {
    idChunks.push(evidenceDocIds.slice(i, i + MAX_IDS_PER_QUERY));
  }

  try {
    const evidenceCol = collection(db, 'evidence_items');
    for (const chunk of idChunks) {
      if (chunk.length === 0) continue;
      const q = query(evidenceCol, where(documentId(), 'in', chunk))
        .withConverter<EvidenceItem>({
          toFirestore: (data: EvidenceItem) => data,
          fromFirestore: (snapshot, options) => {
            const data = snapshot.data(options);
            return {
              id: snapshot.id, 
              evidence_id: data.evidence_id || snapshot.id,
              promise_ids: data.promise_ids || [],
              evidence_source_type: data.evidence_source_type || '',
              evidence_date: data.evidence_date, // Keep as fetched (Timestamp, string, or undefined)
              title_or_summary: data.title_or_summary || '',
              description_or_details: data.description_or_details || undefined,
              source_url: data.source_url || undefined,
              source_document_raw_id: data.source_document_raw_id || undefined,
              linked_departments: data.linked_departments || [],
              status_impact_on_promise: data.status_impact_on_promise || undefined,
              ingested_at: data.ingested_at, 
              additional_metadata: data.additional_metadata || undefined,
            } as EvidenceItem;
          }
        });
      const querySnapshot = await getDocs(q);
      querySnapshot.docs.forEach(docSnapshot => {
        allEvidenceItems.push(docSnapshot.data());
      });
    }

    const sStartDateObj = sessionStartDate ? new Date(sessionStartDate + "T00:00:00Z") : null;
    const sEndDateObj = sessionEndDate ? new Date(sessionEndDate + "T23:59:59Z") : null;

    const filteredEvidenceItems = allEvidenceItems.filter(item => {
      if (!item.evidence_date) {
        return false; 
      }

      let evidenceDateObj: Date;

      if (item.evidence_date instanceof Timestamp) { // Check for actual Timestamp instance first
        evidenceDateObj = item.evidence_date.toDate();
      } else if (typeof item.evidence_date === 'object' && item.evidence_date !== null && 
                 typeof (item.evidence_date as any).seconds === 'number' && 
                 typeof (item.evidence_date as any).nanoseconds === 'number') {
        // Handle serialized Timestamp plain object
        evidenceDateObj = new Date((item.evidence_date as any).seconds * 1000);
      } else if (typeof item.evidence_date === 'string') {
        // Handle date string
        const dateStr = item.evidence_date.includes('T') ? item.evidence_date : item.evidence_date + "T00:00:00Z";
        evidenceDateObj = new Date(dateStr);
      } else {
        return false;
      }

      if (isNaN(evidenceDateObj.getTime())) {
        return false;
      }
      
      if (sStartDateObj && evidenceDateObj < sStartDateObj) {
        return false;
      }
      if (sEndDateObj && evidenceDateObj > sEndDateObj) {
        return false;
      }
      return true;
    });

    return filteredEvidenceItems;
  } catch (error) {
    console.error('Error fetching evidence items by IDs:', error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return [];
  }
};

/**
 * Get migration status and statistics.
 * @returns Migration statistics
 */
export async function getMigrationStatus(): Promise<{
  isCompleted: boolean;
  totalDocuments: number;
  migratedDocuments: number;
  failedDocuments: number;
  lastMigrationDate?: string;
}> {
  if (!db) {
    return {
      isCompleted: false,
      totalDocuments: 0,
      migratedDocuments: 0,
      failedDocuments: 0
    };
  }

  try {
    // Check if any documents have migration metadata
    const q = query(
      collection(db, "promises"),
      where('migration_metadata.migration_version', '==', '1.0'),
      limit(1)
    );

    const snapshot = await getDocs(q);
    const isCompleted = snapshot.docs.length > 0;

    if (!isCompleted) {
      return {
        isCompleted: false,
        totalDocuments: 0,
        migratedDocuments: 0,
        failedDocuments: 0
      };
    }

    // Get counts
    const totalQuery = query(collection(db, "promises"));
    const totalSnapshot = await getCountFromServer(totalQuery);

    const migratedQuery = query(
      collection(db, "promises"),
      where('migration_metadata.migration_version', '==', '1.0')
    );
    const migratedSnapshot = await getCountFromServer(migratedQuery);

    return {
      isCompleted: true,
      totalDocuments: totalSnapshot.data().count,
      migratedDocuments: migratedSnapshot.data().count,
      failedDocuments: 0, // Would need to check migration_tracking collection for failures
    };
  } catch (error) {
    console.error('Error getting migration status:', error);
    return {
      isCompleted: false,
      totalDocuments: 0,
      migratedDocuments: 0,
      failedDocuments: 0
    };
  }
}

/**
 * Sanitizes a full department name to be used as a Firestore document ID.
 * Converts to lowercase, replaces spaces and multiple hyphens with a single hyphen,
 * and removes other non-alphanumeric characters (except hyphens).
 * @param name The full department name string.
 * @returns A sanitized string suitable for Firestore document IDs.
 */
const sanitizeFullNameForDocId = (name: string): string => {
  if (!name) return "";
  return name
    .toLowerCase()
    .replace(/\s+/g, "-") // Replace spaces with hyphens
    .replace(/--+/g, "-") // Replace multiple hyphens with a single one
    .replace(/[^a-z0-9-]/g, "") // Remove non-alphanumeric characters except hyphens
    .replace(/^-+|-+$/g, ""); // Trim leading/trailing hyphens
};

/**
 * Fetches the list of department configurations from Firestore.
 * These are used to populate the main navigation tabs.
 */

// Simple in-memory cache for department configs
let departmentConfigsCache: DepartmentConfig[] | null = null;
let departmentConfigsCacheTime: number = 0;
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

export const fetchDepartmentConfigs = async (): Promise<DepartmentConfig[]> => {
  // Check cache first
  const now = Date.now();
  if (departmentConfigsCache && (now - departmentConfigsCacheTime) < CACHE_DURATION) {
    return departmentConfigsCache;
  }

  if (!db) {
    console.error("Firestore instance (db) is not available in fetchDepartmentConfigs.");
    return [];
  }
  try {
    const departmentCollectionRef = collection(db, "department_config");
    const snapshot = await getDocs(departmentCollectionRef);
    const departments: DepartmentConfig[] = snapshot.docs.map((doc) => ({
      id: doc.id,
      ...(doc.data() as Omit<DepartmentConfig, "id">),
    }));
    
    const sortedDepartments = departments.sort((a, b) => {
      // Ensure properties exist and are strings, providing a fallback.
      const nameA = (a && typeof a.display_short_name === 'string') ? a.display_short_name : "";
      const nameB = (b && typeof b.display_short_name === 'string') ? b.display_short_name : "";
      return nameA.localeCompare(nameB);
    });
    
    // Update cache
    departmentConfigsCache = sortedDepartments;
    departmentConfigsCacheTime = now;
    
    return sortedDepartments;
  } catch (error) {
    console.error("Error fetching department configs:", error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return []; // Return empty array on error
  }
};

/**
 * Fetches the start and end dates for a specific parliament session.
 * @param parliament_session_id The ID of the parliament session (e.g., "44").
 * @returns An object with sessionStartDate and sessionEndDate, or null if not found/error.
 */
export const fetchParliamentSessionDates = async (
  parliament_session_id: string
): Promise<{ sessionStartDate: string | null; sessionEndDate: string | null } | null> => {
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchParliamentSessionDates.");
    return null;
  }
  if (!parliament_session_id) {
    console.error("parliament_session_id is required for fetchParliamentSessionDates");
    return null;
  }

  console.log(`Fetching session dates for parliament_session_id: ${parliament_session_id}`);
  try {
    const sessionDocRef = doc(db, "parliament_session", parliament_session_id);
    const docSnap = await getDoc(sessionDocRef);

    if (docSnap.exists()) {
      const data = docSnap.data();
      
      let sessionStartDate: string | null = null;
      if (data?.election_called_date instanceof Timestamp) {
        sessionStartDate = data.election_called_date.toDate().toISOString().split('T')[0]; // YYYY-MM-DD
      } else if (typeof data?.election_called_date === 'string') {
        // Fallback if it's still a string, though ideally it should be a Timestamp
        console.warn(`[fetchParliamentSessionDates] election_called_date for session ${parliament_session_id} is a string, expected Timestamp.`);
        sessionStartDate = data.election_called_date;
      }

      let sessionEndDate: string | null = null;
      if (data?.end_date instanceof Timestamp) {
        sessionEndDate = data.end_date.toDate().toISOString().split('T')[0]; // YYYY-MM-DD
      } else if (typeof data?.end_date === 'string') {
        // Fallback for string, or if it represents "current" conceptually via absence/null
        console.warn(`[fetchParliamentSessionDates] end_date for session ${parliament_session_id} is a string, expected Timestamp or null.`);
        sessionEndDate = data.end_date; 
      } else if (data?.end_date === null || data?.end_date === undefined) {
        sessionEndDate = null; // Explicitly null if Firestore field is null/undefined
      }

      console.log(`Session dates for ${parliament_session_id}: Start - ${sessionStartDate}, End - ${sessionEndDate}`);
      return { sessionStartDate, sessionEndDate };
    } else {
      console.warn(`No session document found for parliament_session_id: ${parliament_session_id}`);
      return null;
    }
  } catch (error) {
    console.error(`Error fetching session dates for ${parliament_session_id}:`, error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return null;
  }
};

/**
 * Fetches minister details for a specific department.
 * @param departmentFullName The full name of the department (e.g., "Environment and Climate Change Canada").
 * @returns MinisterDetails object or null if not found or on error.
 */
export const fetchMinisterDetails = async (
  departmentFullName: string
): Promise<MinisterDetails | null> => {
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchMinisterDetails.");
    return null;
  }
  if (!departmentFullName) {
    console.error("departmentFullName is required for fetchMinisterDetails");
    return null;
  }

  const ministerDocId = sanitizeFullNameForDocId(departmentFullName);
  if (!ministerDocId) {
    console.error(`Could not generate a valid document ID from departmentFullName: "${departmentFullName}"`);
    return null;
  }

  console.log(`Fetching minister details for department: ${departmentFullName}`);
  try {
    const ministerDocRef = doc(db, "ministers", ministerDocId);
    const docSnap = await getDoc(ministerDocRef);

    if (docSnap.exists()) {
      const data = docSnap.data();
      return {
        minister_first_name: data?.minister_first_name || null,
        minister_last_name: data?.minister_last_name || null,
        minister_full_name_from_blog: data?.minister_full_name_from_blog || null,
        minister_title_from_blog: data?.minister_title_from_blog || null,
        minister_title_scraped_pm_gc_ca: data?.minister_title_scraped_pm_gc_ca || null,
        standardized_department_or_title: data?.standardized_department_or_title || null,
        letter_url: data?.letter_url || null,
        avatarUrl: data?.avatarUrl || undefined,
      };
    } else {
      console.warn(`No minister document found for department: ${departmentFullName}`);
      return null;
    }
  } catch (error) {
    console.error(`Error fetching minister details for department: ${departmentFullName}`, error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return null;
  }
};

/**
 * Fetches a lightweight summary of promises for a department (no evidence items).
 * Optimized for faster initial page loads.
 * @param departmentFullName The full name of the department
 * @param parliamentSessionId The parliament session ID  
 * @param governingPartyCode The party code
 * @param regionCode The region code (default: "Canada")
 * @param limitCount Maximum number of promises to return (default: 10)
 * @returns Array of PromiseData objects without evidence
 */
export async function fetchPromisesSummary(
  departmentFullName: string,
  parliamentSessionId: string | null,
  governingPartyCode: string | null,
  regionCode: string = "Canada",
  limitCount: number = 10
): Promise<PromiseData[]> {
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchPromisesSummary.");
    return [];
  }
  if (!parliamentSessionId) {
    console.warn("parliamentSessionId not provided to fetchPromisesSummary. No promises will be fetched.");
    return [];
  }
  if (!governingPartyCode) {
    console.warn("governingPartyCode not provided to fetchPromisesSummary. No promises will be fetched.");
    return [];
  }

  const departmentNameToQuery = departmentFullName;

  // Try to find the ministerial title from department configs (same logic as fetchPromisesForDepartment)
  let nameVariantsToTry: string[] = [departmentNameToQuery];
  
  try {
    const departmentConfigs = await fetchDepartmentConfigs();
    const matchingConfig = departmentConfigs.find(config => 
      config.official_full_name === departmentNameToQuery
    );
    
    if (matchingConfig && matchingConfig.name_variants && matchingConfig.name_variants.length > 0) {
      // Add all name variants to try, including different cases
      nameVariantsToTry = [
        departmentNameToQuery,
        ...matchingConfig.name_variants,
        // Try title case versions (proper title case with lowercase articles/prepositions)
        ...matchingConfig.name_variants.map(variant => 
          variant.split(' ').map(word => {
            // Handle special cases for proper title casing
            if (word.toLowerCase() === 'and' || word.toLowerCase() === 'of' || word.toLowerCase() === 'the') {
              return word.toLowerCase();
            }
            return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
          }).join(' ')
        ),
        // Also try versions where ALL words are capitalized (in case the above doesn't work)
        ...matchingConfig.name_variants.map(variant => 
          variant.split(' ').map(word => 
            word.charAt(0).toUpperCase() + word.slice(1).toLowerCase()
          ).join(' ')
        )
      ];
    }
  } catch (error) {
    console.error(`[fetchPromisesSummary] Error fetching department configs:`, error);
    // Continue with original name if config fetch fails
  }
  
  try {
    // Query the flat promises collection with filters
    const promisesCol = collection(db, "promises");
    
    // Try each name variant until we find results (same logic as fetchPromisesForDepartment)
    for (const titleToTry of nameVariantsToTry) {
      let q = query(
        promisesCol,
        where('responsible_department_lead', '==', titleToTry),
        where('parliament_session_id', '==', parliamentSessionId),
        where('party_code', '==', governingPartyCode),
        where('region_code', '==', regionCode),
        where('bc_promise_rank', 'in', ["strong", "medium", "weak", "Strong", "Medium", "Weak"]),
        // Temporarily removed status filter until migration is complete
        // where('status', '==', 'active'), // Exclude deleted promises
        orderBy('date_issued', 'desc'),
        limit(limitCount)
      );

      const finalQuery = q.withConverter<PromiseData>({
        toFirestore: (data: PromiseData) => data, // Not used for reads
        fromFirestore: (snapshot, options) => {
          const data = snapshot.data(options);
          
          // Extract linked_evidence_ids from linked_evidence array
          let linkedEvidenceIds: string[] = [];
          if (data.linked_evidence && Array.isArray(data.linked_evidence)) {
            linkedEvidenceIds = data.linked_evidence.map((item: any) => item.evidence_id).filter(Boolean);
          } else if (data.linked_evidence_ids && Array.isArray(data.linked_evidence_ids)) {
            // Fallback to direct linked_evidence_ids if it exists
            linkedEvidenceIds = data.linked_evidence_ids.filter(Boolean);
          }
          
          return {
            id: snapshot.id,
            text: data.text || '',
            responsible_department_lead: data.responsible_department_lead || '',
            commitment_history_rationale: data.commitment_history_rationale || [],
            date_issued: data.date_issued || undefined,
            linked_evidence_ids: linkedEvidenceIds, // Properly extracted evidence IDs
            parliament_session_id: data.parliament_session_id || undefined,
            progress_score: data.progress_score ?? undefined,
            progress_summary: data.progress_summary ?? undefined,
            bc_promise_rank: data.bc_promise_rank ?? undefined,
            bc_promise_rank_rationale: data.bc_promise_rank_rationale ?? undefined,
            bc_promise_direction: data.bc_promise_direction ?? undefined,
            evidence: [], // Will be populated later
            
            // New flat structure fields
            region_code: data.region_code || undefined,
            party_code: data.party_code || undefined,
            migration_metadata: data.migration_metadata || undefined,
            source_type: data.source_type || undefined,
            source_url: data.source_url || undefined,
            
            // Explanation fields
            concise_title: data.concise_title ?? undefined,
            description: data.description ?? undefined,
            what_it_means_for_canadians: data.what_it_means_for_canadians ?? undefined,
            intended_impact_and_objectives: data.intended_impact_and_objectives ?? undefined,
            background_and_context: data.background_and_context ?? undefined,
          } as PromiseData;
        }
      });

      const querySnapshot = await getDocs(finalQuery);
      
      if (querySnapshot.docs.length > 0) {
        const promises: PromiseData[] = [];

        // Process each promise and fetch its most recent evidence date
        for (const docSnapshot of querySnapshot.docs) {
          const promise = docSnapshot.data();
          
          // For each promise, fetch the most recent evidence date if it has linked evidence
          if (promise.linked_evidence_ids && promise.linked_evidence_ids.length > 0) {
            try {
              // Query evidence items for this promise and get only the most recent one
              const evidenceQuery = query(
                collection(db, 'evidence_items'),
                where(documentId(), 'in', promise.linked_evidence_ids.slice(0, 30)), // Firestore limit
                orderBy('evidence_date', 'desc'),
                limit(1)
              );
              
              const evidenceSnapshot = await getDocs(evidenceQuery);
              if (evidenceSnapshot.docs.length > 0) {
                const mostRecentEvidence = evidenceSnapshot.docs[0].data();
                // Add just the most recent evidence to show the date
                promise.evidence = [{
                  id: evidenceSnapshot.docs[0].id,
                  evidence_id: evidenceSnapshot.docs[0].id,
                  evidence_date: mostRecentEvidence.evidence_date,
                  title_or_summary: mostRecentEvidence.title_or_summary || '',
                  promise_ids: mostRecentEvidence.promise_ids || [],
                  evidence_source_type: mostRecentEvidence.evidence_source_type || '',
                  description_or_details: undefined,
                  source_url: undefined,
                  source_document_raw_id: undefined,
                  linked_departments: mostRecentEvidence.linked_departments || [],
                  status_impact_on_promise: undefined,
                  ingested_at: mostRecentEvidence.ingested_at,
                  additional_metadata: undefined,
                }];
              } else {
                promise.evidence = [];
              }
            } catch (evidenceError) {
              console.warn(`Failed to fetch evidence date for promise ${promise.id}:`, evidenceError);
              promise.evidence = [];
            }
          } else {
            promise.evidence = [];
          }

          promises.push(promise);
        }
        
        return promises;
      }
    }
    
    // If we get here, none of the variants returned results
    return [];
  } catch (error) {
    console.error(`Error fetching promise summaries for ${departmentFullName}:`, error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return [];
  }
}
