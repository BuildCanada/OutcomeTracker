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
  getCountFromServer
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
    return departments.sort((a, b) => a.shortName.localeCompare(b.shortName)); // Sort alphabetically by shortName
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
 * Fetches promises for a specific department that are from mandate letters.
 * @param departmentFullName The full name of the department (e.g., "Finance Canada").
 * @returns An array of PromiseData objects.
 */
export async function fetchPromisesForDepartment(departmentFullName: string): Promise<PromiseData[]> {
  // Check if db is initialized
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchPromisesForDepartment.");
    return [];
  }
  console.log(`Fetching promises for department: ${departmentFullName}`);
  try {
    const promisesCol = collection(db, 'promises'); // db is now guaranteed to be non-null here
    const q = query(
      promisesCol,
      where('responsible_department_lead', '==', departmentFullName),
      where('source_type', '==', 'Mandate Letter Commitment (Structured)')
    );

    const querySnapshot = await getDocs(q);
    const promises = querySnapshot.docs.map(docSnapshot => {
        const data = docSnapshot.data();
        return {
            id: docSnapshot.id,
            text: data.text || '', // Provide default or handle potential missing field
            responsible_department_lead: data.responsible_department_lead || '', // Provide default
            source_type: data.source_type || '', // Provide default
            commitment_history_rationale: data.commitment_history_rationale || undefined,
            date_issued: data.date_issued || undefined, // Include optional fields
            candidate_or_government: data.candidate_or_government || undefined, // Include optional fields
            // Ensure all required fields from PromiseData are present or handled
        } as PromiseData; // Correctly assert the type
    });

    console.log(`Fetched ${promises.length} promises for ${departmentFullName}`);
    return promises;
  } catch (error) {
    console.error(`Error fetching promises for ${departmentFullName}:`, error);
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