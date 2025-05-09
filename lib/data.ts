import {
  collection,
  getDocs,
  doc,
  getDoc,
  query,
  where,
  FirestoreError,
} from "firebase/firestore";
import { db } from "./firebase"; // Your Firebase instance
import type {
  DepartmentConfig,
  MinisterDetails,
  PromiseData,
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
export const fetchPromisesForDepartment = async (
  departmentFullName: string
): Promise<PromiseData[]> => {
  if (!db) {
    console.error("Firestore instance (db) is not available in fetchPromisesForDepartment.");
    return [];
  }
  if (!departmentFullName) {
    console.error("departmentFullName is required for fetchPromisesForDepartment");
    return [];
  }

  console.log(`Fetching promises for department: "${departmentFullName}"`);

  try {
    const promisesCollectionRef = collection(db, "promises_2021_mandate");
    const q = query(
      promisesCollectionRef,
      where("responsible_department_lead", "==", departmentFullName),
      where("source_type", "==", "Mandate Letter Commitment (Structured)")
    );

    const snapshot = await getDocs(q);
    const promises: PromiseData[] = snapshot.docs.map((doc) => ({
      promise_id: doc.id, // Use Firestore document ID as promise_id
      ...(doc.data() as Omit<PromiseData, "promise_id">),
    }));
    console.log(`Fetched ${promises.length} promises for "${departmentFullName}":`, promises);
    return promises;
  } catch (error) {
    console.error(`Error fetching promises for "${departmentFullName}":`, error);
    if (error instanceof FirestoreError) {
      console.error("Firestore error details:", error.code, error.message);
    }
    return [];
  }
};

// Note: The old hardcoded `primeMinister` and `categories` data and their exports
// have been removed as per the plan to fetch data dynamically.
// Guiding metrics are also intended to be dynamic or associated with fetched minister/department data.
