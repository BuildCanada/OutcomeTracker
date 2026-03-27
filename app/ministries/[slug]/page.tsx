import type { Metadata } from "next";
import Link from "next/link";
import BurnUpChartWrapper from "@/components/BurnUpChartWrapper";
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
  broken: "Broken",
};

const STATUS_COLORS: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-700",
  in_progress: "bg-amber-100 text-amber-800",
  completed: "bg-[#faf0f1] text-[#8b2332]",
  broken: "bg-gray-200 text-black",
};

// Cache-bust the OG image URL every 4 hours so social crawlers re-fetch
export async function generateMetadata({
  params,
}: {
  params: Promise<{ slug: string }>;
}): Promise<Metadata> {
  const { slug } = await params;
  const slot = Math.floor(Date.now() / (4 * 60 * 60 * 1000));
  return {
    openGraph: {
      images: [`/tracker/ministries/${slug}/opengraph-image?v=${slot}`],
    },
  };
}

export default async function MinistryPage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  const [burnUp, commitmentsData] = await Promise.all([
    fetchApi<BurnUpResponse>(`/api/burndown/1?department_slug=${slug}`),
    fetchApi<CommitmentsResponse>(
      `/api/v1/commitments.json?per_page=1000&lead_department=${slug}`,
    ),
  ]);

  const commitments = commitmentsData.commitments;
  const totalCount = commitmentsData.meta.total_count;

  const dept = commitments.find((c) => c.lead_department)?.lead_department;
  const ministryName =
    dept?.display_name ??
    slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

  const statusCounts: Record<string, number> = {};
  for (const c of commitments) {
    statusCounts[c.status] = (statusCounts[c.status] ?? 0) + 1;
  }

  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/"
          className="text-xs text-gray-400 hover:text-[#8b2332] transition-colors"
        >
          &larr; Overview
        </Link>
        <h2 className="mt-2 text-3xl font-bold tracking-tight">
          {ministryName}
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          {totalCount} commitment{totalCount !== 1 ? "s" : ""} under this
          ministry
        </p>
      </div>

      {/* Burn-up chart */}
      <BurnUpChartWrapper
        data={burnUp}
        statusCounts={commitments.length > 0 ? statusCounts : undefined}
      />

      {/* Status summary */}
      {commitments.length > 0 && (
        <div className="flex flex-wrap gap-3">
          {Object.entries(statusCounts)
            .sort(([a], [b]) => a.localeCompare(b))
            .map(([status, count]) => (
              <span
                key={status}
                className={`inline-flex items-center px-3 py-1 text-sm font-medium ${STATUS_COLORS[status] ?? "bg-gray-100 text-gray-700"}`}
              >
                {STATUS_LABELS[status] ?? status}: {count}
              </span>
            ))}
        </div>
      )}

      {/* Commitment list */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Commitments</h3>
        {commitments.length === 0 ? (
          <p className="text-gray-500 italic">
            No commitments found for this ministry.
          </p>
        ) : (
          <div className="space-y-3">
            {commitments.map((c: CommitmentListing) => (
              <Link
                key={c.id}
                href={`/commitments/${c.id}`}
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
                    {c.policy_area && (
                      <span className="text-xs text-gray-400 mt-1 inline-block">
                        {c.policy_area.name}
                      </span>
                    )}
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
