"use client";

import { useMemo } from "react";
import dynamic from "next/dynamic";
import useSWR from "swr";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  CommitmentListing,
  CommitmentsResponse,
  DepartmentWithMinister,
} from "@/lib/commitment-types";

const BurnUpChart = dynamic(() => import("@/components/ChartLine"), {
  ssr: false,
});

const STATUS_COLOR: Record<string, string> = {
  implemented: "bg-green-500",
  in_progress: "bg-yellow-400",
  partially_implemented: "bg-yellow-600",
  not_started: "bg-gray-300",
  abandoned: "bg-red-500",
};

const STATUS_LABEL: Record<string, string> = {
  implemented: "Implemented",
  in_progress: "In Progress",
  partially_implemented: "Partially Implemented",
  not_started: "Not Started",
  abandoned: "Abandoned",
};

const LEGEND_STATUSES = [
  "implemented",
  "in_progress",
  "partially_implemented",
  "not_started",
  "abandoned",
];

interface MinistryGroup {
  name: string;
  slug: string;
  commitments: CommitmentListing[];
  statusCounts: Record<string, number>;
  minister?: DepartmentWithMinister["minister"];
}

export interface BurnUpResponse {
  government: { id: number; name: string };
  mandate_start: string | null;
  mandate_end: string | null;
  total_commitments: number;
  policy_area: { id: number; name: string; slug: string } | null;
  series: { date: string; scope: number; started: number; completed: number }[];
}

export default function V2HomePage() {
  const { data: burnUp } = useSWR<BurnUpResponse>(`/tracker/api/burndown/1`, {
    revalidateIfStale: false,
  });

  const { data: departments } = useSWR<DepartmentWithMinister[]>(
    `/tracker/api/v1/departments.json`,
    { revalidateIfStale: false },
  );

  const { data: page1, isLoading } = useSWR<CommitmentsResponse>(
    `/tracker/api/v1/commitments.json?per_page=100&page=1`,
    { revalidateIfStale: false },
  );
  const { data: page2 } = useSWR<CommitmentsResponse>(
    `/tracker/api/v1/commitments.json?per_page=100&page=2`,
    { revalidateIfStale: false },
  );
  const { data: page3 } = useSWR<CommitmentsResponse>(
    `/tracker/api/v1/commitments.json?per_page=100&page=3`,
    { revalidateIfStale: false },
  );

  const commitments = useMemo(
    () => [
      ...(page1?.commitments ?? []),
      ...(page2?.commitments ?? []),
      ...(page3?.commitments ?? []),
    ],
    [page1, page2, page3],
  );
  const totalCommitments = page1?.meta?.total_count ?? commitments.length;

  const statusCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const c of commitments) {
      counts[c.status] = (counts[c.status] ?? 0) + 1;
    }
    return counts;
  }, [commitments]);

  const deptBySlug = useMemo(() => {
    const map: Record<string, DepartmentWithMinister> = {};
    for (const d of departments ?? []) {
      map[d.slug] = d;
    }
    return map;
  }, [departments]);

  const ministries = useMemo(() => {
    const groups: Record<string, MinistryGroup> = {};
    for (const c of commitments) {
      const name = c.lead_department?.display_name ?? "Unassigned";
      const slug = c.lead_department?.slug ?? "unassigned";
      if (!groups[name]) {
        groups[name] = {
          name,
          slug,
          commitments: [],
          statusCounts: {},
          minister: deptBySlug[slug]?.minister,
        };
      }
      groups[name].commitments.push(c);
      groups[name].statusCounts[c.status] =
        (groups[name].statusCounts[c.status] ?? 0) + 1;
    }
    return Object.values(groups).sort((a, b) => {
      if (a.name === "Unassigned") return 1;
      if (b.name === "Unassigned") return -1;
      return b.commitments.length - a.commitments.length;
    });
  }, [commitments, deptBySlug]);

  const notStarted = statusCounts["not_started"] ?? 0;
  const completed =
    (statusCounts["implemented"] ?? 0) +
    (statusCounts["partially_implemented"] ?? 0);
  const inProgress = statusCounts["in_progress"] ?? 0;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">
          Accountability Overview
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Tracking progress on {totalCommitments} government commitments
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <MetricCard
            label="Not Started"
            value={notStarted}
            subtitle="no action taken"
            color="gray"
          />
          <MetricCard
            label="Completed"
            value={completed}
            subtitle={`of ${totalCommitments} commitments`}
            color="green"
          />
          <MetricCard
            label="Started"
            value={inProgress}
            subtitle="actively being worked on"
            color="amber"
          />
        </div>
      )}

      {/* Burn-up chart */}
      {burnUp && <BurnUpChart data={burnUp as never} />}

      {/* Ministries grid */}
      <div>
        <h3 className="text-xl font-semibold mb-4">By Ministry</h3>
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {ministries.map((m) => (
              <MinistryCard key={m.name} ministry={m} />
            ))}
          </div>
        )}
      </div>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href="/v2/commitments"
          className="border border-[#d3c7b9] px-4 py-2 text-gray-600 hover:bg-gray-50 hover:text-[#8b2332] transition-colors"
        >
          Explore All Commitments
        </Link>
      </div>
    </div>
  );
}

/* ── Metric Card ───────────────────────────────────────────────── */

function MetricCard({
  label,
  value,
  subtitle,
  color,
}: {
  label: string;
  value: number;
  subtitle: string;
  color: "green" | "amber" | "gray";
}) {
  const colorMap = {
    green: {
      bg: "bg-green-50 border-green-200",
      text: "text-green-600",
      sub: "text-green-400",
      label: "text-green-500",
    },
    amber: {
      bg: "bg-amber-50 border-amber-200",
      text: "text-amber-600",
      sub: "text-amber-400",
      label: "text-amber-500",
    },
    gray: {
      bg: "bg-gray-50 border-gray-200",
      text: "text-gray-800",
      sub: "text-gray-400",
      label: "text-gray-500",
    },
  };
  const c = colorMap[color];

  return (
    <div className={`border p-6 ${c.bg}`}>
      <p
        className={`text-xs font-semibold uppercase tracking-wider ${c.label}`}
      >
        {label}
      </p>
      <p className={`mt-2 text-4xl font-extrabold ${c.text}`}>{value}</p>
      <p className={`mt-1 text-sm ${c.sub}`}>{subtitle}</p>
    </div>
  );
}

/* ── Ministry Card ─────────────────────────────────────────────── */

function MinistryCard({ ministry }: { ministry: MinistryGroup }) {
  const total = ministry.commitments.length;
  const counts = ministry.statusCounts;
  const minister = ministry.minister;

  const statusOrder = Object.fromEntries(LEGEND_STATUSES.map((s, i) => [s, i]));
  const sorted = [...ministry.commitments].sort(
    (a, b) => (statusOrder[a.status] ?? 99) - (statusOrder[b.status] ?? 99),
  );

  return (
    <div className="border border-[#cdc4bd] bg-white p-5 flex gap-4">
      {/* Minister photo */}
      {minister && (
        <div className="flex-shrink-0">
          <div className="w-16 h-16 bg-gray-100 overflow-hidden">
            {minister.avatar_url ? (
              <img
                src={minister.avatar_url}
                alt={`${minister.first_name} ${minister.last_name}`}
                className="w-full h-full object-cover"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-400 text-lg font-semibold">
                {minister.first_name[0]}
                {minister.last_name[0]}
              </div>
            )}
          </div>
          <p className="text-[10px] text-gray-500 mt-1 text-center leading-tight max-w-16">
            {minister.first_name} {minister.last_name}
          </p>
        </div>
      )}

      {/* Card content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-start justify-between mb-3">
          <Link
            href={`/v2/ministries/${ministry.slug}`}
            className="text-base font-semibold hover:text-[#8b2332] transition-colors"
          >
            {ministry.name}
          </Link>
          <span className="text-xs text-gray-500 font-mono">
            {total} commitment{total !== 1 ? "s" : ""}
          </span>
        </div>

        <div className="flex flex-wrap gap-0.5 mb-3">
          {sorted.map((c) => (
            <Link
              key={c.id}
              href={`/v2/commitments/${c.id}`}
              className={`block w-3 h-3 ${STATUS_COLOR[c.status] ?? "bg-gray-200"} hover:ring-2 hover:ring-[#8b2332] hover:ring-offset-1 transition-shadow`}
              title={`${c.title} — ${STATUS_LABEL[c.status] ?? c.status}`}
            />
          ))}
        </div>

        <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
          {LEGEND_STATUSES.map((s) => {
            const count = counts[s] ?? 0;
            if (count === 0) return null;
            return (
              <span key={s}>
                {STATUS_LABEL[s]}: {count}
              </span>
            );
          })}
        </div>
      </div>
    </div>
  );
}
