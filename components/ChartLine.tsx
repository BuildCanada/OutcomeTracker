"use client";

import { useMemo } from "react";
import {
  Chart as ChartJS,
  TimeScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
  Filler,
  Tooltip,
  Legend,
  _adapters,
} from "chart.js";
import {
  toDate,
  parse,
  parseISO,
  isValid,
  format,
  addYears,
  addQuarters,
  addMonths,
  addWeeks,
  addDays,
  addHours,
  addMinutes,
  addSeconds,
  addMilliseconds,
  differenceInYears,
  differenceInQuarters,
  differenceInMonths,
  differenceInWeeks,
  differenceInDays,
  differenceInHours,
  differenceInMinutes,
  differenceInSeconds,
  differenceInMilliseconds,
  startOfYear,
  startOfQuarter,
  startOfMonth,
  startOfWeek,
  startOfDay,
  startOfHour,
  startOfMinute,
  startOfSecond,
  endOfYear,
  endOfQuarter,
  endOfMonth,
  endOfWeek,
  endOfDay,
  endOfHour,
  endOfMinute,
  endOfSecond,
} from "date-fns";

// Inline the date-fns adapter using the SAME _adapters reference
_adapters._date.override({
  _id: "date-fns",
  formats: () => ({
    datetime: "MMM d, yyyy, h:mm:ss aaaa",
    millisecond: "h:mm:ss.SSS aaaa",
    second: "h:mm:ss aaaa",
    minute: "h:mm aaaa",
    hour: "ha",
    day: "MMM d",
    week: "PP",
    month: "MMM yyyy",
    quarter: "qqq - yyyy",
    year: "yyyy",
  }),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  parse(value: any, fmt: any) {
    if (value === null || typeof value === "undefined") return null;
    if (typeof value === "number" || value instanceof Date)
      value = toDate(value);
    else if (typeof value === "string") {
      value =
        typeof fmt === "string"
          ? parse(value, fmt, new Date(), this.options)
          : parseISO(value, this.options);
    }
    return isValid(value) ? value.getTime() : null;
  },
  format(time: number, fmt: string) {
    return format(time, fmt, this.options);
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  add(time: any, amount: number, unit: string) {
    switch (unit) {
      case "millisecond":
        return addMilliseconds(time, amount);
      case "second":
        return addSeconds(time, amount);
      case "minute":
        return addMinutes(time, amount);
      case "hour":
        return addHours(time, amount);
      case "day":
        return addDays(time, amount);
      case "week":
        return addWeeks(time, amount);
      case "month":
        return addMonths(time, amount);
      case "quarter":
        return addQuarters(time, amount);
      case "year":
        return addYears(time, amount);
      default:
        return time;
    }
  },
  diff(max: number, min: number, unit: string) {
    switch (unit) {
      case "millisecond":
        return differenceInMilliseconds(max, min);
      case "second":
        return differenceInSeconds(max, min);
      case "minute":
        return differenceInMinutes(max, min);
      case "hour":
        return differenceInHours(max, min);
      case "day":
        return differenceInDays(max, min);
      case "week":
        return differenceInWeeks(max, min);
      case "month":
        return differenceInMonths(max, min);
      case "quarter":
        return differenceInQuarters(max, min);
      case "year":
        return differenceInYears(max, min);
      default:
        return 0;
    }
  },
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  startOf(time: any, unit: string, weekday?: number) {
    switch (unit) {
      case "second":
        return startOfSecond(time);
      case "minute":
        return startOfMinute(time);
      case "hour":
        return startOfHour(time);
      case "day":
        return startOfDay(time);
      case "week":
        return startOfWeek(time);
      case "isoWeek":
        return startOfWeek(time, {
          weekStartsOn: +(weekday ?? 0) as 0 | 1 | 2 | 3 | 4 | 5 | 6,
        });
      case "month":
        return startOfMonth(time);
      case "quarter":
        return startOfQuarter(time);
      case "year":
        return startOfYear(time);
      default:
        return time;
    }
  },
  endOf(time: number, unit: string) {
    switch (unit) {
      case "second":
        return endOfSecond(time);
      case "minute":
        return endOfMinute(time);
      case "hour":
        return endOfHour(time);
      case "day":
        return endOfDay(time);
      case "week":
        return endOfWeek(time);
      case "month":
        return endOfMonth(time);
      case "quarter":
        return endOfQuarter(time);
      case "year":
        return endOfYear(time);
      default:
        return time;
    }
  },
});

ChartJS.register(
  TimeScale,
  LinearScale,
  PointElement,
  LineElement,
  LineController,
  Filler,
  Tooltip,
  Legend,
);

import { Chart } from "react-chartjs-2";

/* ── Types ── */

import type { BurnUpResponse, BurnUpSeries } from "@/lib/commitment-types";

/* ── BurnUpChart component ── */

export default function BurnUpChart({
  data,
  statusCounts,
}: {
  data: BurnUpResponse;
  statusCounts?: Record<string, number>;
}) {
  const chartData = useMemo(() => {
    const mandateStart =
      data.mandate_start ?? data.series[0]?.date ?? "2025-04-28";
    const mandateEnd = data.mandate_end ?? "2029-10-15";

    const sortedSeries = [...data.series].sort((a, b) =>
      a.date.localeCompare(b.date),
    );
    const today = new Date().toISOString().slice(0, 10);
    const latestScope = sortedSeries[sortedSeries.length - 1]?.scope ?? 0;

    // Build a weekly series that carries forward the last known values,
    // so the chart shows flat lines between actual change events.
    const weeklyPoints: BurnUpSeries[] = [];
    const pastPoints = sortedSeries.filter((pt) => pt.date <= today);

    if (pastPoints.length > 0) {
      let idx = 0;
      const startDate = new Date(pastPoints[0].date + "T00:00:00");
      const endDate = new Date(today + "T00:00:00");
      let current: BurnUpSeries = { ...pastPoints[0] };

      for (
        let d = new Date(startDate);
        d <= endDate;
        d.setDate(d.getDate() + 7)
      ) {
        const iso = d.toISOString().slice(0, 10);

        // Advance to consume all data points up to this date
        while (idx < pastPoints.length && pastPoints[idx].date <= iso) {
          current = pastPoints[idx];
          idx++;
        }

        weeklyPoints.push({ ...current, date: iso });
      }

      // Ensure the last actual data point is included
      const lastPt = pastPoints[pastPoints.length - 1];
      if (
        weeklyPoints.length === 0 ||
        weeklyPoints[weeklyPoints.length - 1].date !== lastPt.date
      ) {
        weeklyPoints.push(lastPt);
      }
    }

    const scopeLine = weeklyPoints.map((pt) => ({ x: pt.date, y: pt.scope }));
    const startedLine = weeklyPoints.map((pt) => ({
      x: pt.date,
      y: pt.started,
    }));
    const completedLine = weeklyPoints.map((pt) => ({
      x: pt.date,
      y: pt.completed,
    }));
    const abandonedLine = weeklyPoints.map((pt) => ({
      x: pt.date,
      y: pt.abandoned ?? 0,
    }));

    scopeLine.push({ x: mandateEnd, y: latestScope });

    const latest = sortedSeries[sortedSeries.length - 1] ?? {
      scope: 0,
      started: 0,
      completed: 0,
      abandoned: 0,
    };

    return {
      scopeLine,
      startedLine,
      completedLine,
      abandonedLine,
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

      <div className="flex gap-8 mb-4">
        <div>
          <span className="inline-block w-2.5 h-2.5 bg-gray-400 mr-1.5" />
          <span className="text-xs text-gray-500">Scope</span>
          <p className="text-lg font-bold">
            {statusCounts
              ? Object.values(statusCounts).reduce((a, b) => a + b, 0)
              : chartData.latest.scope}
          </p>
        </div>
        <div>
          <span className="inline-block w-2.5 h-2.5 bg-amber-400 mr-1.5" />
          <span className="text-xs text-gray-500">Started</span>
          <p className="text-lg font-bold">
            {statusCounts
              ? (statusCounts["in_progress"] ?? 0) +
                (statusCounts["completed"] ?? 0) +
                (statusCounts["abandoned"] ?? 0)
              : chartData.latest.started}
          </p>
        </div>
        <div>
          <span className="inline-block w-2.5 h-2.5 bg-[#8b2332] mr-1.5" />
          <span className="text-xs text-gray-500">Completed</span>
          <p className="text-lg font-bold">
            {statusCounts
              ? (statusCounts["completed"] ?? 0)
              : chartData.latest.completed}
          </p>
        </div>
        <div>
          <span className="inline-block w-2.5 h-2.5 bg-black mr-1.5" />
          <span className="text-xs text-gray-500">Abandoned</span>
          <p className="text-lg font-bold">
            {statusCounts
              ? (statusCounts["abandoned"] ?? 0)
              : chartData.latest.abandoned}
          </p>
        </div>
      </div>

      <div className="h-72">
        <Chart
          type="line"
          data={{
            datasets: [
              {
                label: "Scope",
                data: chartData.scopeLine,
                borderColor: "#9ca3af",
                borderWidth: 1.5,
                pointRadius: 0,
                fill: false,
                stepped: "before",
                spanGaps: false,
              },
              {
                label: "Started",
                data: chartData.startedLine,
                borderColor: "#f59e0b",
                borderWidth: 2,
                pointRadius: 0,
                fill: false,
                stepped: "before",
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
                stepped: "before",
                spanGaps: false,
              },
              {
                label: "Abandoned",
                data: chartData.abandonedLine,
                borderColor: "#000000",
                borderWidth: 2,
                pointRadius: 0,
                fill: false,
                stepped: "before",
                spanGaps: false,
                borderDash: [4, 3],
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
                callbacks: {
                  title: (items) => {
                    if (!items.length) return "";
                    const raw = items[0].raw as { x: string };
                    return new Date(raw.x + "T00:00:00").toLocaleDateString(
                      "en-CA",
                      { month: "long", day: "numeric", year: "numeric" },
                    );
                  },
                },
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
          <span className="inline-block w-5 h-0.5 bg-[#8b2332]" />
          Completed
        </span>
        <span className="inline-flex items-center gap-1.5">
          <span className="inline-block w-5 h-0.5 bg-black border-dashed" />
          Abandoned
        </span>
      </div>
    </div>
  );
}
