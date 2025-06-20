export interface DepartmentListing {
  created_at: string;
  display_name: string;
  government_id: number;
  id: number;
  official_name: string;
  priority: number;
  slug: string;
  updated_at: string;
}

export interface Department {
  display_name: string;
  official_name: string;
  priority: number;
  slug: string;

  minister?: Minister;
  promises: PromiseListing[];
}

export interface Minister {
  order_of_precedence: number;
  started_at: string;
  ended_at: string | null;
  first_name: string;
  last_name: string;
  title: string;
  avatar_url: string;
  person_short_honorific: string;
}

export interface PromiseListing {
  id: number;
  concise_title: string;
  description: string;
  bc_promise_direction: string;
  bc_promise_rank: string;
  bc_promise_rank_rationale: string;
  progress_score: number | null;
  progress_summary: string;
  text: string;
  last_evidence_at: string;
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

export interface PromiseDetail {
  id: number;
  text: string;
  description: string;
  commitment_history_rationale?: RationaleEvent[];
  what_it_means_for_canadians?: string;
  concise_title: string;
  progress_score?: number;
  progress_summary?: string;
  evidences?: Evidence[];
  source_url?: string;
  last_evidence_data?: string;
  source_type: string;
  date_issued?: string;
}

export interface Evidence {
  id: number;
  title_or_summary: string;
}

export type DepartmentSlug =
  | "prime-minister-office"
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
