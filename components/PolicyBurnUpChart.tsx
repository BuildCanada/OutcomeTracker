"use client";

import { useMemo } from "react";
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
import type { BurnUpResponse } from "@/lib/commitment-types";

ChartJS.register(
  TimeScale,
  LinearScale,
  PointElement,
  LineElement,
  Filler,
  Tooltip,
  Legend,
);

export default function PolicyBurnUpChart({ data }: { data: BurnUpResponse }) {
  const chartData = useMemo(() => {
    const mandateStart =
      data.mandate_start ?? data.series[0]?.date ?? "2025-04-28";
    const mandateEnd = data.mandate_end ?? "2029-10-15";

    const sortedSeries = [...data.series].sort((a, b) =>
      a.date.localeCompare(b.date),
    );
    const today = new Date().toISOString().slice(0, 10);
    const latestScope = sortedSeries[sortedSeries.length - 1]?.scope ?? 0;

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
          <span className="inline-block w-2.5 h-2.5 bg-pine-600 mr-1.5" />
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
                borderColor: "#356643",
                backgroundColor: "rgba(53, 102, 67, 0.10)",
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
            interaction: { mode: "index", intersect: false },
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
                time: { unit: "month", displayFormats: { month: "MMM yy" } },
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
          <span className="inline-block w-5 h-0.5 bg-pine-600" />
          Completed
        </span>
      </div>
    </div>
  );
}
