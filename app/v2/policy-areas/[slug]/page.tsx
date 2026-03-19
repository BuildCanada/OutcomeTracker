import Link from "next/link";
import PolicyBurnUpChartWrapper from "@/components/PolicyBurnUpChartWrapper";
import { fetchApi } from "@/lib/api";
import type {
  CommitmentListing,
  CommitmentsResponse,
  BurnUpResponse,
} from "@/lib/commitment-types";

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  completed: "Completed",
  abandoned: "Abandoned",
};

const STATUS_COLORS: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-700",
  in_progress: "bg-amber-100 text-amber-800",
  completed: "bg-[#faf0f1] text-[#8b2332]",
  abandoned: "bg-gray-200 text-black",
};

export default async function PolicyAreaPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  const [burnUp, commitData] = await Promise.all([
    fetchApi<BurnUpResponse>(`/api/burndown/1?policy_area_slug=${slug}`),
    fetchApi<CommitmentsResponse>(
      `/api/v1/commitments.json?per_page=1000&policy_area=${slug}`,
    ),
  ]);

  const commitments = commitData.commitments;
  const policyAreaName = burnUp.policy_area?.name ?? slug;

  return (
    <div className="space-y-8">
      {/* Breadcrumb + Header */}
      <div>
        <Link
          href="/v2"
          className="text-xs text-gray-400 hover:text-[#8b2332] transition-colors"
        >
          &larr; Overview
        </Link>
        <h2 className="mt-2 text-3xl font-bold tracking-tight">
          {policyAreaName}
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          {burnUp.total_commitments} commitment
          {burnUp.total_commitments !== 1 ? "s" : ""} in this policy area
        </p>
      </div>

      {/* Burn-up chart */}
      <PolicyBurnUpChartWrapper data={burnUp} />

      {/* Commitment list */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Commitments</h3>
        {commitments.length === 0 ? (
          <p className="text-gray-500 italic">
            No commitments found for this policy area.
          </p>
        ) : (
          <div className="space-y-3">
            {commitments.map((c: CommitmentListing) => (
              <Link
                key={c.id}
                href={`/v2/commitments/${c.id}`}
                className="block bg-white border border-[#cdc4bd] hover:border-gray-400 transition-colors p-4"
              >
                <div className="flex items-start gap-3">
                  <span
                    className={`inline-flex items-center px-2 py-0.5 text-xs font-medium flex-shrink-0 ${STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-700"}`}
                  >
                    {STATUS_LABELS[c.status] ?? c.status}
                  </span>
                  <div className="min-w-0">
                    <h4 className="text-sm font-semibold text-gray-900 leading-snug">
                      {c.title}
                    </h4>
                    <p className="text-xs text-gray-500 mt-1 line-clamp-1">
                      {c.description}
                    </p>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
