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
  lead_department: { id: number; display_name: string } | null;
}

export interface CommitmentsResponse {
  commitments: CommitmentListing[];
  meta: {
    total_count: number;
    page: number;
    per_page: number;
  };
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
