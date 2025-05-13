// lib/types.ts

import { Timestamp } from "firebase/firestore";

// --- Data structures from Firestore ---

export interface DepartmentConfig {
  id: string; // Document ID (sanitized shortName)
  shortName: string; // e.g., "Environment"
  fullName: string;  // e.g., "Environment and Climate Change Canada"
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
  text: string;
  responsible_department_lead: string;
  source_type: string;
  commitment_history_rationale?: RationaleEvent[]; // Added optional field
  date_issued?: string; // Optional
  candidate_or_government?: string; // Optional
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
  ministerDetails: MinisterDetails | null;
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
  evidence_id: string; // Document ID
  promise_ids: string[];
  evidence_source_type: string;
  evidence_date: Timestamp | string; // Firestore Timestamp or ISO string
  title_or_summary: string;
  description_or_details?: string;
  source_url?: string;
  source_document_raw_id?: string;
  linked_departments?: string[];
  status_impact_on_promise?: string;
  ingested_at: Timestamp; // Firestore Timestamp
  additional_metadata?: Record<string, any>;
}
