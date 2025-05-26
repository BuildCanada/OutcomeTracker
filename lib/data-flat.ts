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
import {
  fetchParliamentSessionDates,
  fetchEvidenceItemsByIds
} from "./data";

/**
 * Fetches promises for a specific department using the flat collection structure.
 * Filters by party, region, department, and session.
 * @param departmentFullName The full name of the department (e.g., "Finance Canada").
 * @param parliamentSessionId The parliament session ID
 * @param governingPartyCode The party code (e.g., "LPC", "CPC")
 * @param regionCode The region code (default: "Canada")
 * @param effectiveDepartmentFullNameOverride Override for department name matching
 * @returns An array of PromiseData objects, with linked evidence included.
 */
export async function fetchPromisesForDepartmentFlat(
  departmentFullName: string,
  parliamentSessionId: string | null,
  governingPartyCode: string | null,
  regionCode: string = "Canada",
  effectiveDepartmentFullNameOverride?: string
): Promise<PromiseData[]> {
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchPromisesForDepartmentFlat.");
    return [];
  }
  if (!parliamentSessionId) {
    console.warn("parliamentSessionId not provided to fetchPromisesForDepartmentFlat. No promises will be fetched.");
    return [];
  }
  if (!governingPartyCode) {
    console.warn("governingPartyCode not provided to fetchPromisesForDepartmentFlat. No promises will be fetched.");
    return [];
  }

  // Get session dates for filtering (reuse existing function)
  const sessionDates = await fetchParliamentSessionDates(parliamentSessionId);
  if (!sessionDates) {
    console.warn(`Could not fetch session dates for ${parliamentSessionId}. Promises might not be filtered correctly by date.`);
  }
  const { sessionStartDate, sessionEndDate } = sessionDates || { sessionStartDate: null, sessionEndDate: null };

  const departmentNameToQuery = effectiveDepartmentFullNameOverride || departmentFullName;

  console.log(`[FLAT] Fetching promises for department: ${departmentNameToQuery}, session: ${parliamentSessionId}, party: ${governingPartyCode}, region: ${regionCode}`);
  
  try {
    // Query the flat promises collection with filters
    const promisesCol = collection(db, "promises");
    
    let q = query(
      promisesCol,
      where('responsible_department_lead', '==', departmentNameToQuery),
      where('parliament_session_id', '==', parliamentSessionId),
      where('party_code', '==', governingPartyCode),
      where('region_code', '==', regionCode),
      where('bc_promise_rank', 'in', ["strong", "medium", "Strong", "Medium"])
    );

    // Apply date filters if session dates are available
    if (sessionStartDate) {
      q = query(q, where('date_issued', '>=', sessionStartDate));
      console.log(`Applied start date filter: date_issued >= ${sessionStartDate}`);
    }
    if (sessionEndDate) {
      q = query(q, where('date_issued', '<=', sessionEndDate));
      console.log(`Applied end date filter: date_issued <= ${sessionEndDate}`);
    }

    const finalQuery = q.withConverter<PromiseData>({
      toFirestore: (data: PromiseData) => data, // Not used for reads
      fromFirestore: (snapshot, options) => {
        const data = snapshot.data(options);
        return {
          id: snapshot.id,
          text: data.text || '',
          responsible_department_lead: data.responsible_department_lead || '',
          commitment_history_rationale: data.commitment_history_rationale || [],
          date_issued: data.date_issued || undefined,
          linked_evidence_ids: data.linked_evidence_ids || [],
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
          
          // Explanation fields
          concise_title: data.concise_title ?? undefined,
          what_it_means_for_canadians: data.what_it_means_for_canadians ?? undefined,
          intended_impact_and_objectives: data.intended_impact_and_objectives ?? undefined,
          background_and_context: data.background_and_context ?? undefined,
        } as PromiseData;
      }
    });

    const querySnapshot = await getDocs(finalQuery);
    const promisesWithEvidence: PromiseData[] = [];

    for (const docSnapshot of querySnapshot.docs) {
      const promise = docSnapshot.data(); // Use the converted data directly

      if (promise.linked_evidence_ids && promise.linked_evidence_ids.length > 0) {
        // Pass session dates to the evidence fetching function
        promise.evidence = await fetchEvidenceItemsByIds(promise.linked_evidence_ids, sessionStartDate, sessionEndDate);
      }
      promisesWithEvidence.push(promise);
    }
    
    console.log(`[FLAT] Found ${promisesWithEvidence.length} promises for ${departmentNameToQuery}`);
    return promisesWithEvidence;
  } catch (error) {
    console.error(`Error fetching promises for ${departmentFullName}:`, error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return [];
  }
}

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
        where('region_code', '==', regionCode)
      );

      const countSnapshot = await getCountFromServer(q);
      partyCounts[partyCode] = countSnapshot.data().count;
    }

    console.log(`Promise counts by party for session ${parliamentSessionId}:`, partyCounts);
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
        where('bc_promise_rank', 'in', ["strong", "medium", "Strong", "Medium"])
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
          evidence: [], // Populate separately if needed
        } as PromiseData);
      });
    }

    console.log(`[FLAT] Found ${allPromises.length} promises across ${departmentNames.length} departments`);
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
      where('parliament_session_id', '==', parliamentSessionId)
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

    console.log(`[FLAT] Text search for "${searchTerm}" found ${matchingPromises.length} matches`);
    return matchingPromises;
  } catch (error) {
    console.error('Error searching promises by text:', error);
    return [];
  }
}

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

// Re-export existing functions that don't need changes
export {
  fetchDepartmentConfigs,
  fetchParliamentSessionDates,
  fetchMinisterDetails,
  fetchEvidenceItemsByIds,
  fetchEvidenceItemsForPromises
} from "./data"; 