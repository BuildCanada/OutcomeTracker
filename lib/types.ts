// lib/types.ts

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
  promise_id: string;
  text: string;
  responsible_department_lead?: string | null; // Full department name
  relevant_departments?: string[];
  source_type?: string; // Should be "Mandate Letter Commitment (Structured)"
  // Add any other fields from promises_2021_mandate you might want to display
  // status, impact, lastUpdate, timeline, relatedBills could be added later if needed
  // For now, focusing on the core promise text as requested.
  status?: { id: string; label: string }; // Example, if you add status later
  lastUpdate?: string; // Example
}

// --- UI-specific data structures ---

export interface Metric {
  title: string;
  data: number[];
  goal: number;
}

// This will represent the combined data needed to render a department's page/tab content
export interface DepartmentPageData {
  id: string; // from DepartmentConfig.id (e.g., "environment")
  shortName: string; // from DepartmentConfig.shortName (e.g., "Environment")
  fullName: string; // from DepartmentConfig.fullName (e.g., "Environment and Climate Change Canada")
  ministerDetails: MinisterDetails | null;
  promises: PromiseData[];
  guidingMetrics: Metric[]; // Keeping as is for now
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
