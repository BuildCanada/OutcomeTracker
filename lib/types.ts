// lib/types.ts

import { Timestamp } from "firebase/firestore";

// --- Data structures from Firestore ---

export interface ParliamentSession {
  id: string; // parliament_number, e.g., "44"
  parliament_number: string;
  session_label: string;
  start_date: string;
  end_date?: string | null;
  prime_minister_name?: string;
  governing_party?: string;
  governing_party_code?: string;
  election_date_preceding?: string | null;
  election_called_date?: string | null;
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
  effectiveDepartmentOfficialFullName?: string; // Added for remapped department name
  effectiveDepartmentId?: string; // Added for remapped department ID
}

export interface DepartmentConfig {
  id: string; // Firestore document ID (e.g., "health-canada")
  display_short_name: string; // New: e.g., "Health" (used for sorting and display)
  official_full_name: string; // New: e.g., "Health Canada"
  official_full_name_en?: string;
  official_full_name_fr?: string;
  department_slug: DepartmentSlug; // New: e.g., "health-canada" (often same as id)
  display_order?: number; // Used for manual ordering of departments

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

  // Field for historical remapping
  historical_mapping?: {
    [parliamentSessionId: string]: {
      // e.g., "44-1"
      minister_lookup_slug: string; // The department_slug to use for minister lookup in that session
      promise_query_department_name: string; // The official_full_name to use for promise queries in that session
      promise_query_slug_override?: string; // Optional: if promise query needs a slug different from minister_lookup_slug
    };
  };

  is_prime_minister?: boolean; // Add this field to identify PM department
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
  category?: string; // Primary policy category (e.g., "Economy", "Healthcare", "Environment")
  source_type?: string; // Made optional as it's not used client-side
  commitment_history_rationale?: RationaleEvent[]; // Added optional field
  date_issued?: string; // Optional
  linked_evidence_ids?: string[];
  evidence?: EvidenceItem[];
  parliament_session_id?: string; // Ensure this field exists on your promise docs if filtering by it
  progress_score?: number;
  progress_summary?: string;
  bc_promise_rank?: string;
  bc_promise_rank_rationale?: string;
  bc_promise_direction?: string;
  concise_title?: string;
  what_it_means_for_canadians?: string;
  intended_impact_and_objectives?: string;
  background_and_context?: string;
  description?: string;

  // NEW FIELDS FOR FLAT STRUCTURE MIGRATION
  region_code?: string; // e.g., "Canada" - region identifier
  party_code?: string; // e.g., "LPC", "CPC", "NDP", "BQ" - party identifier
  migration_metadata?: {
    migrated_at?: Timestamp | string;
    source_path?: string; // Original subcollection path
    migration_version?: string;
    original_id?: string; // Original document ID if changed
    conflict_resolved?: boolean; // True if ID conflict was resolved
    new_id?: string; // New ID if conflict was resolved
  };
}

export type DepartmentSlug =
  | "prime-minister"
  | "agriculture-and-agri-food-canada"
  | "artificial-intelligence-and-digital-innovation"
  | "atlantic-canada-opportunities-agency"
  | "canada-economic-development-for-quebec-regions"
  | "canada-revenue-agency"
  | "canadian-heritage"
  | "crown-indigenous-relations-and-northern-affairs-canada"
  | "emergency-preparedness-canada"
  | "employment-and-social-development-canada"
  | "environment-and-climate-change-canada"
  | "federal-economic-development-agency-for-southern-ontario"
  | "finance-canada"
  | "fisheries-and-oceans-canada"
  | "global-affairs-canada"
  | "health-canada"
  | "immigration-refugees-and-citizenship-canada"
  | "indigenous-services-canada"
  | "infrastructure-canada"
  | "innovation-science-and-economic-development-canada"
  | "justice-canada"
  | "multiple-departments-needs-review"
  | "national-defence"
  | "natural-resources-canada"
  | "privy-council-office"
  | "privy-council-office-intergovernmental-affairs-secretariat"
  | "public-safety-canada"
  | "public-services-and-procurement-canada"
  | "rural-economic-development"
  | "transport-canada"
  | "treasury-board-of-canada-secretariat"
  | "veterans-affairs-canada"
  | "women-and-gender-equality-canada";

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

// PrimeMinister can be kept if there's a separate PM section with hardcoded/different data source
export interface PrimeMinister {
  name: string;
  title: string;
  avatarUrl: string;
  positionStart?: string;
  positionEnd?: string;
  effectiveDepartmentOfficialFullName?: string;
}

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
