"use client";

import dynamic from "next/dynamic";
import { useParams } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  CommitmentListing,
  CommitmentsResponse,
} from "@/lib/commitment-types";

const BurnUpChart = dynamic(() => import("@/components/ChartLine"), {
  ssr: false,
});

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  partially_implemented: "Partially Implemented",
  implemented: "Implemented",
  abandoned: "Abandoned",
};

const STATUS_COLORS: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-700",
  in_progress: "bg-amber-100 text-amber-800",
  partially_implemented: "bg-orange-100 text-orange-800",
  implemented: "bg-green-100 text-green-800",
  abandoned: "bg-red-100 text-red-800",
};

interface BurnUpResponse {
  government: { id: number; name: string };
  mandate_start: string | null;
  mandate_end: string | null;
  total_commitments: number;
  series: { date: string; scope: number; started: number; completed: number }[];
}

export default function MinistryPage() {
  const params = useParams();
  const slug = params.slug as string;

  const { data: burnUp } = useSWR<BurnUpResponse>(
    slug ? `/tracker/api/burndown/1?department_slug=${slug}` : null,
    { revalidateIfStale: false },
  );

  const { data: page1, isLoading } = useSWR<CommitmentsResponse>(
    slug
      ? `/tracker/api/v1/commitments.json?per_page=100&lead_department=${slug}`
      : null,
    { revalidateIfStale: false },
  );
  const { data: page2 } = useSWR<CommitmentsResponse>(
    slug
      ? `/tracker/api/v1/commitments.json?per_page=100&page=2&lead_department=${slug}`
      : null,
    { revalidateIfStale: false },
  );

  const commitments = [
    ...(page1?.commitments ?? []),
    ...(page2?.commitments ?? []),
  ];
  const totalCount = page1?.meta?.total_count ?? commitments.length;

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
          href="/v2"
          className="text-xs text-gray-400 hover:text-[#8b2332] transition-colors"
        >
          &larr; Overview
        </Link>
        <h2 className="mt-2 text-3xl font-bold tracking-tight">
          {isLoading ? <Skeleton className="h-9 w-64" /> : ministryName}
        </h2>
        {!isLoading && (
          <p className="mt-1 text-sm text-gray-500">
            {totalCount} commitment{totalCount !== 1 ? "s" : ""} under this
            ministry
          </p>
        )}
      </div>

      {/* Burn-up chart */}
      {burnUp ? (
        <BurnUpChart data={burnUp as never} />
      ) : (
        <Skeleton className="h-96" />
      )}

      {/* Status summary */}
      {!isLoading && commitments.length > 0 && (
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
        {isLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : commitments.length === 0 ? (
          <p className="text-gray-500 italic">
            No commitments found for this ministry.
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
