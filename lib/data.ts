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
  // Metric, // Keep if guidingMetrics are still needed for fallback
} from "./types";

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
export const fetchDepartmentConfigs = async (): Promise<DepartmentConfig[]> => {
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
    console.log("Fetched department configs:", departments);
    return departments.sort((a, b) => {
      // Ensure properties exist and are strings, providing a fallback.
      const nameA = (a && typeof a.display_short_name === 'string') ? a.display_short_name : "";
      const nameB = (b && typeof b.display_short_name === 'string') ? b.display_short_name : "";

      // Removed console.log from here for performance
      // Removed redundant type checks as nameA and nameB are guaranteed to be strings here
      return nameA.localeCompare(nameB);
    });
  } catch (error) {
    console.error("Error fetching department configs:", error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return []; // Return empty array on error
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

  console.log(`Fetching minister details for doc ID: ${ministerDocId} (from department: "${departmentFullName}")`);

  try {
    const ministerDocRef = doc(db, "mandate_letters_fulltext", ministerDocId);
    const docSnap = await getDoc(ministerDocRef);

    if (docSnap.exists()) {
      const ministerData = docSnap.data() as MinisterDetails;
      console.log(`Found minister details for ${departmentFullName}:`, ministerData);
      // Ensure avatarUrl is at least an empty string or placeholder if not present
      return { ...ministerData, avatarUrl: ministerData.avatarUrl || "/placeholder.svg?height=100&width=100" };
    } else {
      console.warn(`No minister details found for department: "${departmentFullName}" (doc ID: ${ministerDocId})`);
      return null;
    }
  } catch (error) {
    console.error(`Error fetching minister details for "${departmentFullName}":`, error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return null;
  }
};

/**
 * Fetches specific evidence items from Firestore by their document IDs.
 * Handles batching for queries with more than 30 document IDs.
 * @param evidenceDocIds An array of evidence document IDs.
 * @returns An array of EvidenceItem objects.
 */
export const fetchEvidenceItemsByIds = async (evidenceDocIds: string[]): Promise<EvidenceItem[]> => {
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
      const q = query(evidenceCol, where(documentId(), 'in', chunk));
      const querySnapshot = await getDocs(q);
      querySnapshot.docs.forEach(docSnapshot => {
        if (docSnapshot.exists()) {
          const data = docSnapshot.data();
          // Ensure Timestamps are correctly handled, provide defaults for missing fields
          const evidenceDate = data.evidence_date instanceof Timestamp ? data.evidence_date : Timestamp.now();
          const ingestedAt = data.ingested_at instanceof Timestamp ? data.ingested_at : Timestamp.now();

          allEvidenceItems.push({
            id: docSnapshot.id,
            evidence_id: data.evidence_id || docSnapshot.id, // Fallback if specific field is missing
            title_or_summary: data.title_or_summary || '',
            evidence_date: evidenceDate,
            source_url: data.source_url || '',
            description_or_details: data.description_or_details || '',
            promise_ids: data.promise_ids || [],
            evidence_source_type: data.evidence_source_type || '',
            source_document_raw_id: data.source_document_raw_id || undefined,
            linked_departments: data.linked_departments || [],
            status_impact_on_promise: data.status_impact_on_promise || undefined,
            ingested_at: ingestedAt,
            additional_metadata: data.additional_metadata || {},
          } as EvidenceItem);
        }
      });
    }
    console.log(`Fetched ${allEvidenceItems.length} evidence items for ${evidenceDocIds.length} IDs.`);
    return allEvidenceItems;
  } catch (error) {
    console.error('Error fetching evidence items by IDs:', error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return [];
  }
};

/**
 * Fetches promises for a specific department that are from mandate letters.
 * Also fetches linked evidence items for each promise.
 * @param departmentFullName The full name of the department (e.g., "Finance Canada").
 * @returns An array of PromiseData objects, with linked evidence included.
 */
export async function fetchPromisesForDepartment(
  departmentFullName: string,
  parliamentSessionId: string | null,
  governingPartyCode: string | null
): Promise<PromiseData[]> {
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchPromisesForDepartment.");
    return [];
  }
  if (!parliamentSessionId) {
    console.warn("parliamentSessionId not provided to fetchPromisesForDepartment. No promises will be fetched.");
    return [];
  }
  if (!governingPartyCode) {
    console.warn("governingPartyCode not provided to fetchPromisesForDepartment. No promises will be fetched.");
    return [];
  }

  // Define constants for collection structure (ideally from env or shared config)
  const TARGET_PROMISES_COLLECTION_ROOT = process.env.NEXT_PUBLIC_PROMISES_TARGET_COLLECTION || "promises";
  const DEFAULT_REGION_CODE = "Canada";

  console.log(`Fetching promises for department: ${departmentFullName}, session: ${parliamentSessionId}, party: ${governingPartyCode}`);
  
  try {
    const promisesColPath = `${TARGET_PROMISES_COLLECTION_ROOT}/${DEFAULT_REGION_CODE}/${governingPartyCode}`;
    console.log(`Querying promises collection path: ${promisesColPath}`);

    const promisesCol = collection(db, promisesColPath);
    const q = query(
      promisesCol,
      where('responsible_department_lead', '==', departmentFullName),
      where('parliament_session_id', '==', parliamentSessionId)
    );

    const querySnapshot = await getDocs(q);
    const promisesWithEvidence: PromiseData[] = [];

    for (const docSnapshot of querySnapshot.docs) {
      const data = docSnapshot.data();
      const promise: PromiseData = {
        id: docSnapshot.id,
        fullPath: `${promisesColPath}/${docSnapshot.id}`,
        text: data.text || '',
        responsible_department_lead: data.responsible_department_lead || '',
        source_type: data.source_type || '',
        date_issued: data.date_issued || undefined,
        linked_evidence_ids: data.linked_evidence_ids || [],
        evidence: [],
        commitment_history_rationale: data.commitment_history_rationale || [],
      };

      if (promise.linked_evidence_ids && promise.linked_evidence_ids.length > 0) {
        console.log(`Fetching evidence for promise ID ${promise.id} with ${promise.linked_evidence_ids.length} linked IDs.`);
        promise.evidence = await fetchEvidenceItemsByIds(promise.linked_evidence_ids);
        console.log(`Fetched ${promise.evidence.length} evidence items for promise ID ${promise.id}.`);
      }
      promisesWithEvidence.push(promise);
    }

    console.log(`Fetched ${promisesWithEvidence.length} promises with their evidence for ${departmentFullName}`);
    return promisesWithEvidence;
  } catch (error) {
    console.error(`Error fetching promises for ${departmentFullName}:`, error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return [];
  }
}

// Updated function to fetch evidence items with batching for promise IDs
export async function fetchEvidenceItemsForPromises(promiseIds: string[]): Promise<EvidenceItem[]> {
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchEvidenceItemsForPromises.");
    return [];
  }
  if (!promiseIds || promiseIds.length === 0) {
    console.log('No promise IDs provided, skipping evidence fetch.');
    return [];
  }
  console.log(`Fetching evidence items for ${promiseIds.length} promise IDs.`);

  const MAX_IDS_PER_QUERY = 30;
  const allEvidenceItems: EvidenceItem[] = [];
  const idChunks: string[][] = [];

  // Split promiseIds into chunks of MAX_IDS_PER_QUERY
  for (let i = 0; i < promiseIds.length; i += MAX_IDS_PER_QUERY) {
    idChunks.push(promiseIds.slice(i, i + MAX_IDS_PER_QUERY));
  }

  console.log(`Split into ${idChunks.length} chunks for fetching evidence.`);

  try {
    const evidenceCol = collection(db, 'evidence_items');
    
    // Create an array of query promises
    const queryPromises = idChunks.map(chunk => {
      const q = query(
          evidenceCol,
          where('promise_ids', 'array-contains-any', chunk),
          orderBy('evidence_date', 'desc') // Keep ordering if needed, requires index
      );
      return getDocs(q);
    });

    // Execute all queries in parallel
    const querySnapshots = await Promise.all(queryPromises);

    // Process results from all snapshots
    querySnapshots.forEach(snapshot => {
      snapshot.docs.forEach(docSnapshot => {
        const data = docSnapshot.data();
        // Avoid adding duplicates if an evidence item links multiple promises across chunks
        if (!allEvidenceItems.some(item => item.evidence_id === docSnapshot.id)) {
            allEvidenceItems.push({
                evidence_id: docSnapshot.id,
                promise_ids: data.promise_ids || [],
                evidence_source_type: data.evidence_source_type || '',
                evidence_date: data.evidence_date, 
                title_or_summary: data.title_or_summary || '',
                description_or_details: data.description_or_details || undefined,
                source_url: data.source_url || undefined,
                source_document_raw_id: data.source_document_raw_id || undefined,
                linked_departments: data.linked_departments || undefined,
                status_impact_on_promise: data.status_impact_on_promise || undefined,
                ingested_at: data.ingested_at,
                additional_metadata: data.additional_metadata || undefined,
            } as EvidenceItem);
        }
      });
    });

    // Optional: Re-sort all items combined if consistent order is critical
    allEvidenceItems.sort((a, b) => {
        const dateA = a.evidence_date instanceof Timestamp ? a.evidence_date.toMillis() : new Date(a.evidence_date).getTime();
        const dateB = b.evidence_date instanceof Timestamp ? b.evidence_date.toMillis() : new Date(b.evidence_date).getTime();
        if (isNaN(dateA) && isNaN(dateB)) return 0;
        if (isNaN(dateA)) return 1;
        if (isNaN(dateB)) return -1;
        return dateB - dateA; // Descending
    });

    console.log(`Fetched ${allEvidenceItems.length} unique evidence items across ${idChunks.length} chunks.`);
    return allEvidenceItems;

  } catch (error) {
    console.error('Error fetching evidence items in chunks:', error);
    // Provide more context if it's an index error
    if (error instanceof FirestoreError && error.code === 'failed-precondition') {
        console.error('Firestore Index Error: This query likely requires a composite index. Please check the Firebase console.');
        // Potentially re-throw or return a specific error indicator
    }
    return []; // Return empty on error
  }
}

// Note: The old hardcoded `