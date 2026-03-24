export interface CommitmentListing {
  id: number;
  title: string;
  description: string;
  commitment_type: string;
  status: string;
  date_promised: string | null;
  target_date: string | null;
  region_code: string | null;
  party_code: string | null;
  policy_area: { id: number; name: string; slug: string } | null;
  lead_department: { id: number; display_name: string; slug: string } | null;
}

export interface CommitmentsResponse {
  commitments: CommitmentListing[];
  meta: {
    total_count: number;
    page: number;
    per_page: number;
  };
}

export interface HillOffice {
  type: string;
  address: string | null;
  telephone: string | null;
  fax: string | null;
}

export interface MinisterInfo {
  first_name: string;
  last_name: string;
  title: string;
  avatar_url: string | null;
  email: string | null;
  phone: string | null;
  website: string | null;
  constituency: string | null;
  province: string | null;
  hill_office: HillOffice | null;
}

export interface DepartmentWithMinister {
  id: number;
  display_name: string;
  slug: string;
  minister: MinisterInfo | null;
}

export interface FeedItem {
  id: number;
  event_type: string;
  title: string;
  summary: string | null;
  occurred_at: string;
  commitment: {
    id: number;
    title: string;
  };
  policy_area: { id: number; name: string } | null;
}

export interface FeedResponse {
  feed_items: FeedItem[];
  meta: {
    total_count: number;
    page: number;
    per_page: number;
  };
}

export interface BurnUpSeries {
  date: string;
  scope: number;
  started: number;
  completed: number;
  broken: number;
}

export interface BurnUpResponse {
  government: { id: number; name: string };
  mandate_start: string | null;
  mandate_end: string | null;
  total_commitments: number;
  policy_area?: { id: number; name: string; slug: string } | null;
  department?: { id: number; display_name: string; slug: string } | null;
  series: BurnUpSeries[];
}

export interface DashboardResponse {
  total_commitments: number;
  status_counts: Record<string, number>;
}

export interface MinistryGroup {
  name: string;
  slug: string;
  commitments: CommitmentListing[];
  statusCounts: Record<string, number>;
  minister?: MinisterInfo | null;
}
