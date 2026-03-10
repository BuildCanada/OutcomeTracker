"use client";

import { useMemo } from "react";
import { useParams } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
} from "chart.js";
import { Line } from "react-chartjs-2";
import type {
  CommitmentListing,
  CommitmentsResponse,
} from "@/lib/commitment-types";
import type { BurnUpResponse } from "../../page";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

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

export default function PolicyAreaPage() {
  const params = useParams();
  const slug = params.slug as string;

  const { data: burnUp, isLoading: burnUpLoading } = useSWR<BurnUpResponse>(
    slug ? `/tracker/api/burndown/1?policy_area_slug=${slug}` : null,
    { revalidateIfStale: false },
  );

  // Fetch commitments for this policy area (use search to get all)
  const { data: commitData, isLoading: listLoading } =
    useSWR<CommitmentsResponse>(
      slug
        ? `/tracker/api/v1/commitments.json?per_page=100&policy_area=${slug}`
        : null,
      { revalidateIfStale: false },
    );

  const commitments = commitData?.commitments ?? [];
  const policyAreaName = burnUp?.policy_area?.name ?? slug;
  const isLoading = burnUpLoading || listLoading;

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
          {isLoading ? <Skeleton className="h-9 w-64" /> : policyAreaName}
        </h2>
        {burnUp && (
          <p className="mt-1 text-sm text-gray-500">
            {burnUp.total_commitments} commitment
            {burnUp.total_commitments !== 1 ? "s" : ""} in this policy area
          </p>
        )}
      </div>

      {/* Burn-up chart */}
      {burnUp ? (
        <PolicyBurnUpChart data={burnUp} />
      ) : (
        <Skeleton className="h-96" />
      )}

      {/* Commitment list */}
      <div>
        <h3 className="text-xl font-semibold mb-4">Commitments</h3>
        {listLoading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-20" />
            ))}
          </div>
        ) : commitments.length === 0 ? (
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

function PolicyBurnUpChart({ data }: { data: BurnUpResponse }) {
  const chartData = useMemo(() => {
    const mandateStart =
      data.mandate_start ?? data.series[0]?.date ?? "2025-04-28";
    const mandateEnd = data.mandate_end ?? "2029-10-15";
    const start = new Date(mandateStart + "T00:00:00");
    const end = new Date(mandateEnd + "T00:00:00");
    const sampleDates: string[] = [];
    for (const d = new Date(start); d <= end; d.setDate(d.getDate() + 7)) {
      sampleDates.push(d.toISOString().slice(0, 10));
    }
    const lastSample = sampleDates[sampleDates.length - 1];
    if (lastSample !== mandateEnd) {
      sampleDates.push(mandateEnd);
    }

    const sortedSeries = [...data.series].sort((a, b) =>
      a.date.localeCompare(b.date),
    );

    function valueAt(date: string) {
      let best = { scope: 0, started: 0, completed: 0 };
      for (const pt of sortedSeries) {
        if (pt.date <= date) best = pt;
        else break;
      }
      return best;
    }

    const today = new Date().toISOString().slice(0, 10);

    const scopeLine: (number | null)[] = [];
    const startedLine: (number | null)[] = [];
    const completedLine: (number | null)[] = [];
    const latestScope = sortedSeries[sortedSeries.length - 1]?.scope ?? 0;

    for (const date of sampleDates) {
      if (date <= today) {
        const v = valueAt(date);
        scopeLine.push(v.scope);
        startedLine.push(v.started);
        completedLine.push(v.completed);
      } else {
        scopeLine.push(latestScope);
        startedLine.push(null);
        completedLine.push(null);
      }
    }

    const labels = sampleDates.map((d) => {
      const dt = new Date(d + "T00:00:00");
      return dt.toLocaleDateString("en-CA", {
        month: "short",
        year: "2-digit",
      });
    });

    const latest = sortedSeries[sortedSeries.length - 1] ?? {
      scope: 0,
      started: 0,
      completed: 0,
    };

    return {
      labels,
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
        Progress
      </h3>

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
            labels: chartData.labels,
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
