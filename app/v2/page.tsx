"use client";

import { useMemo } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Chart as ChartJS,
  TimeScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";
import "chartjs-adapter-date-fns";
import { Line } from "react-chartjs-2";
import type {
  CommitmentListing,
  CommitmentsResponse,
} from "@/lib/commitment-types";

ChartJS.register(
  TimeScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

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

interface PolicyAreaGroup {
  name: string;
  slug: string;
  commitments: CommitmentListing[];
  statusCounts: Record<string, number>;
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

  const policyAreas = useMemo(() => {
    const groups: Record<string, PolicyAreaGroup> = {};
    for (const c of commitments) {
      const paName =
        c.policy_area && typeof c.policy_area === "object"
          ? c.policy_area.name
          : "Unassigned";
      const paSlug =
        c.policy_area && typeof c.policy_area === "object"
          ? c.policy_area.slug
          : "unassigned";
      if (!groups[paName]) {
        groups[paName] = {
          name: paName,
          slug: paSlug,
          commitments: [],
          statusCounts: {},
        };
      }
      groups[paName].commitments.push(c);
      groups[paName].statusCounts[c.status] =
        (groups[paName].statusCounts[c.status] ?? 0) + 1;
    }
    return Object.values(groups).sort((a, b) => {
      if (a.slug === "unassigned") return 1;
      if (b.slug === "unassigned") return -1;
      return b.commitments.length - a.commitments.length;
    });
  }, [commitments]);

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
      {burnUp && <BurnUpChart data={burnUp} />}

      {/* Policy Areas grid */}
      <div>
        <h3 className="text-xl font-semibold mb-4">By Policy Area</h3>
        {isLoading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {[1, 2, 3, 4].map((i) => (
              <Skeleton key={i} className="h-40" />
            ))}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {policyAreas.map((pa) => (
              <PolicyAreaCard key={pa.slug} area={pa} />
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

/* ── Burn-Up Chart ─────────────────────────────────────────────── */

export function BurnUpChart({ data }: { data: BurnUpResponse }) {
  const chartData = useMemo(() => {
    const mandateStart =
      data.mandate_start ?? data.series[0]?.date ?? "2025-04-28";
    const mandateEnd = data.mandate_end ?? "2029-10-15";

    const sortedSeries = [...data.series].sort((a, b) =>
      a.date.localeCompare(b.date),
    );
    const today = new Date().toISOString().slice(0, 10);
    const latestScope = sortedSeries[sortedSeries.length - 1]?.scope ?? 0;

    // Build {x, y} points from actual data + mandate end projection
    const scopeLine: { x: string; y: number | null }[] = [];
    const startedLine: { x: string; y: number | null }[] = [];
    const completedLine: { x: string; y: number | null }[] = [];

    for (const pt of sortedSeries) {
      if (pt.date <= today) {
        scopeLine.push({ x: pt.date, y: pt.scope });
        startedLine.push({ x: pt.date, y: pt.started });
        completedLine.push({ x: pt.date, y: pt.completed });
      }
    }

    // Extend scope line to mandate end
    scopeLine.push({ x: mandateEnd, y: latestScope });

    const latest = sortedSeries[sortedSeries.length - 1] ?? {
      scope: 0,
      started: 0,
      completed: 0,
    };

    return {
      scopeLine,
      startedLine,
      completedLine,
      latest,
      mandateStart,
      mandateEnd,
    };
  }, [data]);

  return (
    <div className="border border-[#d3c7b9] bg-white p-6">
      <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-1">
        Mandate Progress
      </h3>
      <p className="text-xs text-gray-400 mb-4">
        {new Date(chartData.mandateStart + "T00:00:00").toLocaleDateString(
          "en-CA",
          { month: "long", year: "numeric" },
        )}{" "}
        &ndash;{" "}
        {new Date(chartData.mandateEnd + "T00:00:00").toLocaleDateString(
          "en-CA",
          { month: "long", year: "numeric" },
        )}
      </p>

      {/* Summary metrics */}
      <div className="flex gap-8 mb-4">
        <div>
          <span className="inline-block w-2.5 h-2.5 bg-gray-400 mr-1.5" />
          <span className="text-xs text-gray-500">Scope</span>
          <p className="text-lg font-bold">{chartData.latest.scope}</p>
        </div>
        <div>
          <span className="inline-block w-2.5 h-2.5 bg-amber-400 mr-1.5" />
          <span className="text-xs text-gray-500">Started</span>
          <p className="text-lg font-bold">{chartData.latest.started}</p>
        </div>
        <div>
          <span className="inline-block w-2.5 h-2.5 bg-[#8b2332] mr-1.5" />
          <span className="text-xs text-gray-500">Completed</span>
          <p className="text-lg font-bold">{chartData.latest.completed}</p>
        </div>
      </div>

      <div className="h-72">
        <Line
          data={{
            datasets: [
              {
                label: "Scope",
                data: chartData.scopeLine,
                borderColor: "#9ca3af",
                borderWidth: 1.5,
                pointRadius: 0,
                fill: false,
                tension: 0.2,
                spanGaps: false,
              },
              {
                label: "Started",
                data: chartData.startedLine,
                borderColor: "#f59e0b",
                borderWidth: 2,
                pointRadius: 0,
                fill: false,
                tension: 0.2,
                spanGaps: false,
              },
              {
                label: "Completed",
                data: chartData.completedLine,
                borderColor: "#8b2332",
                backgroundColor: "rgba(139, 35, 50, 0.10)",
                borderWidth: 2.5,
                pointRadius: 0,
                fill: true,
                tension: 0.2,
                spanGaps: false,
              },
            ],
          }}
          options={{
            responsive: true,
            maintainAspectRatio: false,
            interaction: {
              mode: "index",
              intersect: false,
            },
            plugins: {
              legend: { display: false },
              tooltip: {
                mode: "index",
                intersect: false,
                filter: (item) => item.raw !== null,
              },
            },
            scales: {
              x: {
                type: "time",
                time: {
                  unit: "month",
                  displayFormats: { month: "MMM yy" },
                },
                min: chartData.mandateStart,
                max: chartData.mandateEnd,
                grid: { display: false },
                ticks: {
                  font: { size: 10 },
                  maxTicksLimit: 10,
                  autoSkip: true,
                },
              },
              y: {
                beginAtZero: true,
                grid: { color: "#f3f4f6" },
                ticks: { font: { size: 11 } },
                title: {
                  display: true,
                  text: "Commitments",
                  font: { size: 11 },
                  color: "#9ca3af",
                },
              },
            },
          }}
        />
      </div>

      <div className="mt-3 flex flex-wrap gap-x-6 gap-y-1 text-xs text-gray-400">
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-5 h-0.5 bg-gray-400" />
          Scope
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-5 h-0.5 bg-amber-400" />
          Started
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-5 h-0.5 bg-[#8b2332]" />
          Completed
        </span>
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

/* ── Policy Area Card ──────────────────────────────────────────── */

function PolicyAreaCard({ area }: { area: PolicyAreaGroup }) {
  const total = area.commitments.length;
  const counts = area.statusCounts;

  const statusOrder = Object.fromEntries(LEGEND_STATUSES.map((s, i) => [s, i]));
  const sorted = [...area.commitments].sort(
    (a, b) => (statusOrder[a.status] ?? 99) - (statusOrder[b.status] ?? 99),
  );

  return (
    <div className="border border-[#cdc4bd] bg-white p-5">
      <div className="flex items-start justify-between mb-3">
        <Link
          href={`/v2/policy-areas/${area.slug}`}
          className="text-base font-semibold hover:text-[#8b2332] transition-colors"
        >
          {area.name}
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
  );
}
