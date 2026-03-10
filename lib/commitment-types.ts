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
