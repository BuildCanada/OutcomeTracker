// lib/types.ts

import { Timestamp } from "firebase/firestore";

// --- Data structures from Firestore ---

export interface ParliamentSession {
  id: string; // parliament_number as string, e.g., "44"
  parliament_number: string; // e.g., "44"
  session_label: string; // e.g., "44th Parliament (2021-Present)"
  start_date: string; // ISO Date string e.g., "2021-11-22"
  end_date?: string | null; // ISO Date string or null if ongoing
  prime_minister_name?: string;
  governing_party?: string;
  governing_party_code?: string | null;
  election_date_preceding?: string | null; // ISO Date string
  election_called_date?: string | null; // ISO Date string for the election that ENDS this session
  is_current_for_tracking?: boolean;
  notes?: string | null;
}

// --- NEW TYPES FOR MINISTER FETCHING ---
export interface ParliamentaryPosition {
  title: string;      
  title_en?: string;
  title_fr?: string;
  from: string;
  to?: string | null;
}

export interface Member {
  id: string;                 
  firstName?: string;
  lastName?: string;
  party?: string;
  parliamentNumber?: number | string;
  parliamentaryPositions?: ParliamentaryPosition[];
  // avatarUrl?: string; // If you add this to your Member documents
}

export interface MinisterInfo {
  name: string;
  firstName?: string;
  lastName?: string;
  party?: string;
  title: string;       
  avatarUrl?: string;  
  positionStart?: string; // ISO date string
  positionEnd?: string | null; // ISO date string or null if ongoing
}
// --- END NEW TYPES ---

export interface DepartmentConfig {
  id: string; // Firestore document ID (e.g., "health-canada")
  display_short_name: string; // New: e.g., "Health" (used for sorting and display)
  official_full_name: string; // New: e.g., "Health Canada"
  official_full_name_en?: string;
  official_full_name_fr?: string;
  department_slug: string; // New: e.g., "health-canada" (often same as id)

  // Optional fields from screenshot and common usage:
  bc_priority?: number;
  name_variants?: string[];
  notes?: string | null;
  last_updated_at?: Timestamp | string; // Can be Timestamp or serialized string
  last_updated_by?: string;
  
  // Include other fields from your Firestore documents if needed by the application
  // For example, if 'french_name', 'category_tags', 'priority_score', 
  // 'alternative_names' from your earlier summary are indeed in Firestore and used:
  french_name?: string | null;
  category_tags?: string[] | null;
  priority_score?: number; // This was in your Phase 2 summary for department_config
  alternative_names?: string[]; // This was also in your Phase 2 summary
}

export interface MinisterDetails {
  minister_first_name?: string | null;
  minister_last_name?: string | null;
  minister_full_name_from_blog?: string | null;
  minister_title_from_blog?: string | null;
  minister_title_scraped_pm_gc_ca?: string | null;
  standardized_department_or_title?: string | null; // This should match DepartmentConfig.fullName
  letter_url?: string | null;
  // avatarUrl can be added later if available or if we use a placeholder
  avatarUrl?: string; 
}

export interface PromiseData {
  id: string; // Firestore document ID - ALIGNED with fetching logic
  fullPath?: string; // Full Firestore path for the promise document
  text: string;
  responsible_department_lead: string;
  source_type: string;
  commitment_history_rationale?: RationaleEvent[]; // Added optional field
  date_issued?: string; // Optional
  candidate_or_government?: string; // Optional
  linked_evidence_ids?: string[];
  evidence?: EvidenceItem[]; // To hold resolved evidence items
  parliament_session_id?: string; // Ensure this field exists on your promise docs if filtering by it
  // Add other relevant fields as needed
}

// --- UI-specific data structures ---

export interface Metric {
  title: string;
  data: number[];
  goal: number;
}

// This will represent the combined data needed to render a department's page/tab content
export interface DepartmentPageData {
  ministerInfo: MinisterInfo | null;
  promises: PromiseData[];
  evidenceItems: EvidenceItem[]; // Added field for evidence
}

// --- Old types that might be phased out or adapted --- 

// PrimeMinister can be kept if there's a separate PM section with hardcoded/different data source
export interface PrimeMinister {
  name: string;
  title: string;
  avatarUrl: string;
  guidingMetrics: Metric[];
}

// The old Minister type might be replaced by MinisterDetails
// export interface Minister {
//   name: string;
//   title: string;
//   avatarUrl: string;
// }

// TaskStatus, TaskImpact, TimelineEvent, Bill, Task might be removed or adapted 
// if PromiseData and future enhancements cover their roles.
// For now, commenting them out to avoid conflicts and to mark for review.

// export interface TaskStatus {
//   id: "in-progress" | "kept" | "not-started";
//   label: string;
// }

// export interface TaskImpact {
//   level: "high" | "medium" | "low";
//   label: string;
//   description: string;
// }

// export interface TimelineEvent {
//   date: string;
//   title: string;
//   description: string;
// }

// export interface Bill {
//   name: string;
//   status: string;
//   description: string;
// }

// export interface Task {
//   title: string;
//   description: string;
//   status: TaskStatus;
//   impact: TaskImpact;
//   lastUpdate: string;
//   timeline: TimelineEvent[];
//   relatedBills?: Bill[];
// }

// The old Category type will be replaced by DepartmentPageData and DepartmentConfig for tab generation
// export interface Category {
//   id: string;
//   name: string;
//   minister: Minister; // old Minister type
//   guidingMetrics: Metric[];
//   tasks: Task[]; // old Task type
// }

// Define the structure for the rationale events
export interface RationaleEvent {
  date: string; // "YYYY-MM-DD"
  action: string;
  source_url: string;
}

// Define the structure for Evidence Items
export interface EvidenceItem {
  id: string; // Firestore document ID
  evidence_id: string; // The specific 'evidence_id' field from the document data
  promise_ids: string[];
  evidence_source_type: string;
  evidence_date: Timestamp | string; // Allow string for flexibility if already serialized
  title_or_summary: string;
  description_or_details?: string;
  source_url?: string;
  source_document_raw_id?: string;
  linked_departments?: string[];
  status_impact_on_promise?: string;
  ingested_at: Timestamp | string; // Allow string for flexibility
  additional_metadata?: Record<string, any>;
}
