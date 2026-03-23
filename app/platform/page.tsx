"use client";

import { useMemo, useState, useRef } from "react";
import dynamic from "next/dynamic";
import useSWR from "swr";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  CommitmentListing,
  CommitmentsResponse,
  DepartmentWithMinister,
} from "@/lib/commitment-types";
import type { BurnUpResponse } from "@/lib/commitment-types";

const BurnUpChart = dynamic(() => import("@/components/ChartLine"), {
  ssr: false,
});

const SOURCE_TYPE_PARAM = "source_type=platform_document";

const STATUS_COLOR: Record<string, string> = {
  not_started: "bg-gray-300",
  in_progress: "bg-amber-400",
  completed: "bg-[#8b2332]",
  abandoned: "bg-black",
};

const STATUS_LABEL: Record<string, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  completed: "Completed",
  abandoned: "Abandoned",
};

const LEGEND_STATUSES = [
  "not_started",
  "in_progress",
  "completed",
  "abandoned",
];

interface MinistryGroup {
  name: string;
  slug: string;
  commitments: CommitmentListing[];
  statusCounts: Record<string, number>;
  minister?: DepartmentWithMinister["minister"];
}

interface DashboardResponse {
  total_commitments: number;
  status_counts: Record<string, number>;
}

export default function PlatformPage() {
  const { data: dashboard } = useSWR<DashboardResponse>(
    `/tracker/api/dashboard/1/at_a_glance?${SOURCE_TYPE_PARAM}`,
    { revalidateIfStale: false },
  );

  const { data: burnUp } = useSWR<BurnUpResponse>(
    `/tracker/api/burndown/1?${SOURCE_TYPE_PARAM}`,
    { revalidateIfStale: false },
  );

  const { data: departments } = useSWR<DepartmentWithMinister[]>(
    `/tracker/api/v1/departments.json`,
    { revalidateIfStale: false },
  );

  const { data: allCommitmentsData, isLoading } = useSWR<CommitmentsResponse>(
    `/tracker/api/v1/commitments.json?per_page=1000&${SOURCE_TYPE_PARAM}`,
    { revalidateIfStale: false },
  );

  const commitments = allCommitmentsData?.commitments ?? [];
  const totalCommitments =
    dashboard?.total_commitments ??
    allCommitmentsData?.meta?.total_count ??
    commitments.length;

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

  const dashCounts = dashboard?.status_counts ?? {};
  const notStarted =
    dashCounts["not_started"] ?? statusCounts["not_started"] ?? 0;
  const inProgress =
    dashCounts["in_progress"] ?? statusCounts["in_progress"] ?? 0;
  const completed = dashCounts["completed"] ?? statusCounts["completed"] ?? 0;
  const abandoned = dashCounts["abandoned"] ?? statusCounts["abandoned"] ?? 0;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">Election Platform</h2>
        <p className="mt-1 text-sm text-gray-500">
          Tracking progress on {totalCommitments} commitments from the election
          platform
        </p>
      </div>

      {isLoading ? (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-28" />
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <MetricCard
            label="Not Started"
            value={notStarted}
            subtitle="no action taken"
            color="gray"
            href={`/commitments?status=not_started&${SOURCE_TYPE_PARAM}`}
          />
          <MetricCard
            label="In Progress"
            value={inProgress}
            subtitle="actively being worked on"
            color="amber"
            href={`/commitments?status=in_progress&${SOURCE_TYPE_PARAM}`}
          />
          <MetricCard
            label="Completed"
            value={completed}
            subtitle={`of ${totalCommitments} commitments`}
            color="red"
            href={`/commitments?status=completed&${SOURCE_TYPE_PARAM}`}
          />
          <MetricCard
            label="Abandoned"
            value={abandoned}
            subtitle="no longer pursued"
            color="black"
            href={`/commitments?status=abandoned&${SOURCE_TYPE_PARAM}`}
          />
        </div>
      )}

      {/* Burn-up chart */}
      {burnUp && (
        <BurnUpChart
          data={burnUp as never}
          statusCounts={dashboard?.status_counts}
        />
      )}

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
          href={`/commitments?${SOURCE_TYPE_PARAM}`}
          className="border border-[#d3c7b9] px-4 py-2 text-gray-600 hover:bg-gray-50 hover:text-[#8b2332] transition-colors"
        >
          Explore Platform Commitments
        </Link>
      </div>
    </div>
  );
}

/* -- Metric Card -------------------------------------------------- */

function MetricCard({
  label,
  value,
  subtitle,
  color,
  href,
}: {
  label: string;
  value: number;
  subtitle: string;
  color: "gray" | "amber" | "red" | "black";
  href: string;
}) {
  const colorMap = {
    gray: {
      bg: "bg-gray-50 border-gray-200",
      text: "text-gray-800",
      sub: "text-gray-400",
      label: "text-gray-500",
    },
    amber: {
      bg: "bg-amber-50 border-amber-200",
      text: "text-amber-600",
      sub: "text-amber-400",
      label: "text-amber-500",
    },
    red: {
      bg: "bg-[#faf0f1] border-[#e8bfc4]",
      text: "text-[#8b2332]",
      sub: "text-[#b5616e]",
      label: "text-[#a34450]",
    },
    black: {
      bg: "bg-gray-100 border-gray-300",
      text: "text-black",
      sub: "text-gray-500",
      label: "text-gray-600",
    },
  };
  const c = colorMap[color];

  return (
    <Link
      href={href}
      className={`border p-6 ${c.bg} hover:opacity-80 transition-opacity`}
    >
      <p
        className={`text-xs font-semibold uppercase tracking-wider ${c.label}`}
      >
        {label}
      </p>
      <p className={`mt-2 text-4xl font-extrabold ${c.text}`}>{value}</p>
      <p className={`mt-1 text-sm ${c.sub}`}>{subtitle}</p>
    </Link>
  );
}

/* -- Ministry Card ------------------------------------------------ */

function MinistryCard({ ministry }: { ministry: MinistryGroup }) {
  const total = ministry.commitments.length;
  const counts = ministry.statusCounts;
  const minister = ministry.minister;

  const WAFFLE_ORDER = ["completed", "in_progress", "not_started", "abandoned"];
  const waffleRank = Object.fromEntries(WAFFLE_ORDER.map((s, i) => [s, i]));
  const sorted = [...ministry.commitments].sort(
    (a, b) => (waffleRank[a.status] ?? 99) - (waffleRank[b.status] ?? 99),
  );

  return (
    <div className="border border-[#cdc4bd] bg-white p-5">
      {/* Header: photo + name + count */}
      <div className="flex items-center gap-3 mb-3">
        {minister && (
          <div className="flex-shrink-0 w-12 h-12 bg-gray-100 overflow-hidden">
            {minister.avatar_url ? (
              <img
                src={minister.avatar_url}
                alt={`${minister.first_name} ${minister.last_name}`}
                className="w-full h-full object-cover object-[center_25%]"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm font-semibold">
                {minister.first_name[0]}
                {minister.last_name[0]}
              </div>
            )}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <Link
            href={`/ministries/${ministry.slug}`}
            className="text-base font-semibold hover:text-[#8b2332] transition-colors leading-tight block"
          >
            {ministry.name}
          </Link>
          {minister && (
            <p className="text-xs text-gray-500 leading-tight mt-0.5">
              {minister.first_name} {minister.last_name}
            </p>
          )}
        </div>
        <span className="flex-shrink-0 text-xs text-gray-500 font-mono self-start">
          {total} commitment{total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Waffle chart */}
      <div className="flex flex-wrap gap-0.5 mb-3">
        {sorted.map((c) => (
          <CommitmentSquare key={c.id} commitment={c} />
        ))}
      </div>

      {/* Legend */}
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
  );
}

/* -- Commitment Square with Hovercard ------------------------------ */

function CommitmentSquare({
  commitment: c,
}: {
  commitment: CommitmentListing;
}) {
  const [show, setShow] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setShow(true);
  };

  const handleLeave = () => {
    timeoutRef.current = setTimeout(() => setShow(false), 150);
  };

  return (
    <div
      className="relative"
      style={{ zIndex: show ? 20 : undefined }}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <Link
        href={`/commitments/${c.id}`}
        className={`block w-3 h-3 ${STATUS_COLOR[c.status] ?? "bg-gray-200"} hover:ring-2 hover:ring-[#8b2332] hover:ring-offset-1 transition-shadow relative z-10`}
      />
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 bg-white border border-gray-200 shadow-lg rounded-md p-3 text-xs pointer-events-none z-30">
          <p className="font-semibold text-gray-900 leading-snug mb-1.5">
            {c.title}
          </p>
          <div className="space-y-0.5 text-gray-500">
            <p>
              <span className="text-gray-400">Promised:</span>{" "}
              {c.date_promised
                ? new Date(c.date_promised + "T00:00:00").toLocaleDateString(
                    "en-CA",
                    {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    },
                  )
                : "\u2014"}
            </p>
            <p>
              <span className="text-gray-400">Status:</span>{" "}
              {STATUS_LABEL[c.status] ?? c.status}
            </p>
          </div>
          <div className="absolute left-1/2 -translate-x-1/2 top-full w-2 h-2 bg-white border-r border-b border-gray-200 -rotate-45 -mt-1" />
        </div>
      )}
    </div>
  );
}
