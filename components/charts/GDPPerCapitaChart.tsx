// GDPPerCapitaChart.tsx

"use client";

import React from "react";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Chart,
  Scale,
} from "chart.js/auto";
import { getRelativePosition } from "chart.js/helpers";
import type { Plugin } from "chart.js";
import useSWR from "swr";
import { calculatePerCapita } from "./utils/PerCapitaCalculator";
import {
  getPrimaryLineStyling,
  getTargetLineStyling,
  getTrendLineStyling,
} from "./utils/styling";
import { calculateLinearTrend } from "./utils/trendCalculator";
import { LineChartDataset } from "@/components/charts/types";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

// =========================
// Milestone Types & Helpers
// =========================

// Rich tooltip content shape
type MilestoneTooltip = {
  title?: string;
  lines?: string[]; // Simple lines of text
  items?: Array<{ key: string; value: string | number }>; // Key/Value rows
};

// Types for milestone configuration
type Milestone = {
  // For category scales: label string or index number; for time/linear: value in domain
  x: string | number | Date;

  // Display label (shown under the icon by default if desired)
  label: string;

  // Accent color for icon border/fill and label
  color?: string;

  // Icon geometry
  iconWidth?: number; // px width of the milestone icon rectangle
  iconHeight?: number; // px height of the milestone icon rectangle
  iconRadius?: number; // corner radius of the rectangle

  // Vertical spacing from axis baseline
  offsetPx?: number;

  // Optional tooltip content
  tooltip?: MilestoneTooltip;

  // Optional custom background and border styling
  fillColor?: string; // icon fill color (defaults to color with alpha)
  borderColor?: string; // icon border color (defaults to color)
  borderWidth?: number; // icon border width
};

interface GDPPerCapitaChartProps {
  title?: string;
  gdpMeasure?: string;
  startYear?: number;
  endYear?: number;
  quarterlyData?: boolean;
  showAnnual?: boolean;
  showTarget?: boolean;
  targetValue?: number;
  showTrend?: boolean;
}

// Helpers to robustly find scales
function getXYScales(chart: Chart): {
  xScale: Scale | undefined;
  yScale: Scale | undefined;
} {
  const scales = chart.scales;
  const xScale =
    scales["x"] ??
    (Object.values(scales).find((s) => s.isHorizontal()) as Scale | undefined);
  const yScale =
    scales["y"] ??
    (Object.values(scales).find((s) => !s.isHorizontal()) as Scale | undefined);
  return { xScale, yScale };
}

// Resolve X pixel robustly
function resolveXPixel(chart: Chart, x: string | number | Date): number | null {
  const { xScale } = getXYScales(chart);
  if (!xScale) {
    console.warn("[milestone-plugin] No x scale found.");
    return null;
  }

  if (xScale.type === "category") {
    const labels = chart.data.labels as string[] | undefined;
    if (!labels || labels.length === 0) {
      console.warn("[milestone-plugin] Category labels are empty.");
      return null;
    }

    if (typeof x === "string") {
      const idx = labels.indexOf(x);
      if (idx === -1) {
        console.warn(
          `[milestone-plugin] Milestone label not found in labels: "${x}".`,
        );
        return null;
      }
      return xScale.getPixelForTick(idx);
    } else if (typeof x === "number") {
      const idx = Math.round(x);
      if (idx < 0 || idx >= labels.length) {
        console.warn(
          `[milestone-plugin] Milestone index out of bounds: ${idx} (labels length ${labels.length}).`,
        );
        return null;
      }
      return xScale.getPixelForTick(idx);
    } else {
      console.warn(
        "[milestone-plugin] Date provided for category scale; pass label string or index.",
      );
      return null;
    }
  }

  // time/linear scales
  const value =
    xScale.type === "linear" && typeof x !== "number" ? Number(x) : x;
  if (xScale.type === "linear" && !Number.isFinite(value as number)) {
    console.warn(`[milestone-plugin] Non-finite linear value: ${String(x)}`);
    return null;
  }

  const px = xScale.getPixelForValue(value as any);
  if (!Number.isFinite(px)) {
    console.warn(
      `[milestone-plugin] getPixelForValue produced non-finite for ${String(x)} on ${xScale.type} scale.`,
    );
    return null;
  }
  return px;
}

// Utility to draw rounded rect
function drawRoundedRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  const radius = Math.max(0, Math.min(r, Math.min(w, h) / 2));
  ctx.beginPath();
  ctx.moveTo(x + radius, y);
  ctx.lineTo(x + w - radius, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + radius);
  ctx.lineTo(x + w, y + h - radius);
  ctx.quadraticCurveTo(x + w, y + h, x + w - radius, y + h);
  ctx.lineTo(x + radius, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - radius);
  ctx.lineTo(x, y + radius);
  ctx.quadraticCurveTo(x, y, x + radius, y);
  ctx.closePath();
}

// ==================
// Milestone Plugin
// ==================

// Internal structure to track draw bounds for hit-testing
type MilestoneBox = {
  left: number;
  right: number;
  top: number;
  bottom: number;
  idx: number; // milestone index
};

// We keep hover state on the chart instance via a WeakMap to avoid global leaks
const hoverStateMap = new WeakMap<Chart, { hoveredIdx: number | null }>();

const MilestonePlugin: Plugin = {
  id: "milestone-plugin",

  beforeInit(chart) {
    hoverStateMap.set(chart, { hoveredIdx: null });
  },

  afterEvent(chart, args, pluginOptions) {
    // Handle pointer movement for icon hover detection
    const e = args.event;
    if (!e) return;

    const pluginOpts = pluginOptions as { milestones?: Milestone[] };
    const milestones = pluginOpts?.milestones ?? [];
    if (milestones.length === 0) return;

    const state = hoverStateMap.get(chart);
    if (!state) return;

    // Handle mouse leave - clear hover state when mouse leaves chart area
    if (e.type === "mouseout") {
      if (state.hoveredIdx !== null) {
        state.hoveredIdx = null;
        // Trigger external tooltip to hide immediately
        const el = createOrGetTooltipEl(chart);
        el.style.display = "none";
      }
      return;
    }

    // Only process mousemove and mouseenter events
    if (e.type !== "mousemove" && e.type !== "mouseenter") return;

    const boxes: MilestoneBox[] =
      ((chart as any).$milestoneBoxes as MilestoneBox[]) || [];
    if (boxes.length === 0) {
      if (state.hoveredIdx !== null) {
        state.hoveredIdx = null;
        const el = createOrGetTooltipEl(chart);
        el.style.display = "none";
      }
      return;
    }

    const canvasPosition = getRelativePosition(e, chart);
    const { x, y } = canvasPosition;

    // Find top-most matching box
    let hovered: number | null = null;
    for (let i = 0; i < boxes.length; i++) {
      const b = boxes[i];
      if (x >= b.left && x <= b.right && y >= b.top && y <= b.bottom) {
        hovered = b.idx;
        break;
      }
    }

    if (hovered !== state.hoveredIdx) {
      state.hoveredIdx = hovered;
      // Don't trigger chart.update() - just update tooltip directly
      requestAnimationFrame(() => {
        externalTooltipHandler({ chart });
      });
    }
  },

  afterDraw(chart, _args, pluginOptions) {
    const pluginOpts = pluginOptions as { milestones?: Milestone[] };
    const milestones = pluginOpts?.milestones ?? [];
    if (milestones.length === 0) return;

    const { xScale, yScale } = getXYScales(chart);
    if (!xScale || !yScale) {
      console.warn("[milestone-plugin] Missing x/y scales.");
      return;
    }

    const ctx = chart.ctx as CanvasRenderingContext2D;
    const axisY = yScale.bottom;

    // Track placed bounding boxes to avoid horizontal overlap and for hit-testing
    const placedBoxes: Array<{ left: number; right: number }> = [];
    const hitBoxes: MilestoneBox[] = [];

    milestones.forEach((m, i) => {
      const xPx = resolveXPixel(chart, m.x);
      if (xPx === null) {
        console.warn(
          `[milestone-plugin] Skipping milestone #${i} "${m.label}" — unresolved x:`,
          m.x,
        );
        return;
      }

      const color = m.color ?? "#2563eb";
      const borderColor = m.borderColor ?? color;
      const borderWidth = m.borderWidth ?? 1;
      const offsetPx = m.offsetPx ?? 6;

      // Icon geometry
      const iconWidth = m.iconWidth ?? 16;
      const iconHeight = m.iconHeight ?? 10;
      const iconRadius = m.iconRadius ?? 3;

      // Compute baseline placement under the axis
      let iconY = axisY + offsetPx;
      const iconX = xPx - iconWidth / 2;

      // Collision avoidance: stack icons downward if overlapping horizontally
      const maxStackLevels = 4;
      let stackLevel = 0;
      while (stackLevel < maxStackLevels) {
        const iconLeft = iconX;
        const iconRight = iconX + iconWidth;
        const overlaps = placedBoxes.some(
          (b) => !(iconRight < b.left || iconLeft > b.right),
        );
        if (!overlaps) {
          placedBoxes.push({ left: iconLeft, right: iconRight });
          break;
        }
        stackLevel += 1;
        iconY += iconHeight + 4; // stack downward
      }

      // Clip to chart area + extra below so icons show
      const chartArea = chart.chartArea;
      ctx.save();
      ctx.beginPath();
      ctx.rect(
        chartArea.left,
        chartArea.top,
        chartArea.width,
        chartArea.height + 200,
      );
      ctx.clip();

      // Fill defaults: use transparent variant of color if no explicit fillColor
      const fillColor = m.fillColor ?? `${color}33`; // ~20% alpha if hex-6, okay for simple tint

      // Draw rounded rectangle icon
      drawRoundedRect(ctx, iconX, iconY, iconWidth, iconHeight, iconRadius);
      ctx.fillStyle = fillColor;
      ctx.fill();
      ctx.lineWidth = borderWidth;
      ctx.strokeStyle = borderColor;
      ctx.stroke();

      // Hit-test box
      hitBoxes.push({
        left: iconX,
        right: iconX + iconWidth,
        top: iconY,
        bottom: iconY + iconHeight,
        idx: i,
      });

      ctx.restore();
    });

    // Store hit boxes on chart for afterEvent to use
    // We attach to a reserved property namespace to avoid collisions
    (chart as any).$milestoneBoxes = hitBoxes;
  },
};

// Register plugin globally so hooks run
ChartJS.register(MilestonePlugin as any);

// ============================
// Custom External Tooltip Impl
// ============================

/**
 * External tooltip draws a DOM tooltip over the canvas.
 * - Shows milestone tooltip when hovering a milestone icon
 * - Hides when not hovering
 * - Positions near the icon with smart clamping
 *
 * Security note: No user-provided HTML is injected; we only set textContent.
 */
function createOrGetTooltipEl(chart: Chart): HTMLDivElement {
  const canvas = chart.canvas;
  const parent = canvas?.parentNode as HTMLElement | null;
  if (!parent)
    throw new Error("Chart canvas has no parentNode for tooltip container.");

  let el = parent.querySelector<HTMLDivElement>(".milestone-tooltip");
  if (!el) {
    el = document.createElement("div");
    el.className = "milestone-tooltip";
    el.style.position = "absolute";
    el.style.pointerEvents = "none";
    el.style.background = "#111827"; // gray-900
    el.style.color = "#fff";
    el.style.border = "1px solid #374151"; // gray-700
    el.style.borderRadius = "8px";
    el.style.padding = "8px 10px";
    el.style.boxShadow = "0 8px 16px rgba(0,0,0,0.25)";
    el.style.fontFamily =
      "system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif";
    el.style.fontSize = "12px";
    el.style.lineHeight = "1.4";
    el.style.zIndex = "1000";
    el.style.transform = "translate(-50%, -100%)"; // default: center above
    el.style.maxWidth = "280px";
    el.style.display = "none";
    parent.appendChild(el);
  }
  return el;
}

function externalTooltipHandler(context: any) {
  const chart: Chart = context.chart;
  const state = hoverStateMap.get(chart);
  const el = createOrGetTooltipEl(chart);

  // Always check if we should hide first
  if (!state || state.hoveredIdx === null) {
    el.style.display = "none";
    return;
  }

  // Get milestone data from chart options
  const chartOptions = chart.options as any;
  const milestones: Milestone[] =
    chartOptions?.plugins?.["milestone-plugin"]?.milestones || [];

  const boxes: MilestoneBox[] = (chart as any).$milestoneBoxes || [];
  const hoveredIdx = state.hoveredIdx;
  const hoveredBox = boxes.find((b) => b.idx === hoveredIdx);

  if (!hoveredBox || hoveredIdx >= milestones.length) {
    el.style.display = "none";
    return;
  }

  const m = milestones[hoveredIdx];
  if (!m) {
    el.style.display = "none";
    return;
  }

  // Build tooltip content
  const title = m.tooltip?.title ?? m.label;
  const lines = m.tooltip?.lines ?? [];
  const items = m.tooltip?.items ?? [];

  el.innerHTML = "";

  const titleEl = document.createElement("div");
  titleEl.textContent = String(title);
  titleEl.style.fontWeight = "600";
  titleEl.style.marginBottom = "6px";
  titleEl.style.color = m.color ?? "#fff";
  el.appendChild(titleEl);

  if (lines.length > 0) {
    const linesContainer = document.createElement("div");
    for (const line of lines) {
      const p = document.createElement("div");
      p.textContent = line;
      linesContainer.appendChild(p);
    }
    el.appendChild(linesContainer);
  }

  if (items.length > 0) {
    const list = document.createElement("div");
    list.style.marginTop = lines.length ? "6px" : "0";
    for (const { key, value } of items) {
      const row = document.createElement("div");
      const keyEl = document.createElement("span");
      keyEl.textContent = `${key}: `;
      keyEl.style.color = "#9CA3AF";
      const valEl = document.createElement("span");
      valEl.textContent = String(value);
      row.appendChild(keyEl);
      row.appendChild(valEl);
      list.appendChild(row);
    }
    el.appendChild(list);
  }

  // Fix tooltip positioning - use chart's canvas position relative to its parent
  const canvas = chart.canvas;
  const parent = canvas.parentElement!;

  // Get the canvas position relative to its parent (not the page)
  const canvasStyle = window.getComputedStyle(canvas);
  const canvasLeft = parseFloat(canvasStyle.left) || 0;
  const canvasTop = parseFloat(canvasStyle.top) || 0;

  // Calculate center of the milestone icon in canvas coordinates
  const centerX = (hoveredBox.left + hoveredBox.right) / 2;
  const iconTop = hoveredBox.top;

  // Position relative to parent container
  const left = canvasLeft + centerX;
  const top = canvasTop + iconTop - 8; // 8px gap above icon

  el.style.left = `${left}px`;
  el.style.top = `${top}px`;
  el.style.display = "block";

  // Handle edge clamping after the tooltip is visible
  requestAnimationFrame(() => {
    const parentWidth = parent.offsetWidth;
    const tooltipWidth = el.offsetWidth || 240;
    const padding = 8;

    // Check if tooltip would overflow on the left
    if (left - tooltipWidth / 2 < padding) {
      el.style.transform = "translate(0, -100%)"; // Left-align
    }
    // Check if tooltip would overflow on the right
    else if (left + tooltipWidth / 2 > parentWidth - padding) {
      el.style.transform = "translate(-100%, -100%)"; // Right-align
    }
    // Default: center the tooltip
    else {
      el.style.transform = "translate(-50%, -100%)";
    }
  });
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function GDPPerCapitaChart({
  title = "GDP Per Capita",
  gdpMeasure = "Gross domestic product at market prices",
  startYear = 1961,
  endYear = 2099,
  quarterlyData = true,
  showAnnual = false,
  showTarget = false,
  targetValue = 50,
  showTrend = true,
}: GDPPerCapitaChartProps) {
  const {
    data: gdpData,
    error: gdpError,
    isLoading: gdpLoading,
  } = useSWR("/tracker/api/v1/statcan_datasets/gdp-quarterly", fetcher);

  const {
    data: populationData,
    error: populationError,
    isLoading: populationLoading,
  } = useSWR(
    "/tracker/api/v1/statcan_datasets/population-estimates-quarterly",
    fetcher,
  );

  if (gdpLoading || populationLoading) {
    return <div>Loading GDP per capita data...</div>;
  }

  if (gdpError || populationError || !gdpData || !populationData) {
    return <div>Error loading GDP per capita data</div>;
  }

  // Transform the new API data format
  const gdpApiData = gdpData.current_data || [];
  const populationApiData = populationData.current_data || [];

  // Filter GDP data by measure
  const gdpMetricData = gdpApiData
    .filter((item: any) => {
      return item["Estimates"] === gdpMeasure;
    })
    .map((item: any) => [item.REF_DATE, item.VALUE])
    .sort((a: any, b: any) => a[0].localeCompare(b[0]));

  // Filter population data for Canada
  const populationCanadaData = populationApiData
    .filter((item: any) => {
      return item["GEO"] === "Canada";
    })
    .map((item: any) => [item.REF_DATE, item.VALUE])
    .sort((a: any, b: any) => a[0].localeCompare(b[0]));

  // Calculate per capita values (in thousands of dollars)
  const perCapitaValues = calculatePerCapita(
    gdpMetricData,
    populationCanadaData,
    1000000,
  );

  // Filter data by year range
  const filteredData = perCapitaValues.filter((dataPoint) => {
    const year = parseInt(dataPoint.date.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Calculate year-over-year growth rates
  const growthRates: (number | null)[] = filteredData.map(
    (dataPoint, index) => {
      if (index < 4) return null; // Need at least 4 quarters for YoY comparison

      const currentValue = dataPoint.value;
      const previousYearValue = filteredData[index - 4].value;

      if (
        previousYearValue === 0 ||
        previousYearValue === null ||
        currentValue === null
      )
        return null;

      return ((currentValue - previousYearValue) / previousYearValue) * 100;
    },
  );

  // Format dates for display
  let labels = filteredData.map((dataPoint) => {
    if (quarterlyData) {
      const [year, month] = dataPoint.date.split("-");
      // Convert month number to quarter (01->Q1, 04->Q2, 07->Q3, 10->Q4)
      const quarter = Math.floor(parseInt(month) / 3) + 1;
      return `${year} Q${quarter}`;
    } else {
      return dataPoint.date.split("-")[0]; // Just show year
    }
  });

  // Align labels and data arrays to start from first valid growth rate (index 4)
  labels = labels.slice(4);
  const alignedGrowthRates = growthRates.slice(4);

  // Calculate annual average if requested
  let annualAverages: number[] = [];
  if (showAnnual && quarterlyData) {
    // Group data by year to calculate averages
    const yearlyGroups: Record<string, number[]> = {};

    alignedGrowthRates.forEach((growthRate, index) => {
      if (growthRate !== null) {
        const year = labels[index].split(" ")[0]; // Extract year from "YYYY QX" format
        if (!yearlyGroups[year]) yearlyGroups[year] = [];
        yearlyGroups[year].push(growthRate);
      }
    });

    // For each quarter datapoint, find its year's average
    annualAverages = alignedGrowthRates.map((growthRate, index) => {
      if (growthRate === null) return 0;
      const year = labels[index].split(" ")[0];
      const yearValues = yearlyGroups[year] || [];
      if (yearValues.length === 0) return 0;
      return yearValues.reduce((sum, val) => sum + val, 0) / yearValues.length;
    });
  }

  const datasets: LineChartDataset[] = [
    {
      label: "YoY Growth Rate (%)",
      data: alignedGrowthRates,
      ...getPrimaryLineStyling(),
    },
  ];

  if (showAnnual && quarterlyData) {
    datasets.push({
      label: "Annual Average",
      data: annualAverages,
      ...getTargetLineStyling(),
    });
  }

  // Calculate linear trend if requested
  if (showTrend && alignedGrowthRates.length > 1) {
    const trendValues = calculateLinearTrend(alignedGrowthRates as number[]);
    datasets.push({
      label: "Trend",
      data: trendValues,
      ...getTrendLineStyling(),
    });
  }

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: `Target (${targetValue}%)`,
      data: Array(labels.length).fill(targetValue),
      ...getTargetLineStyling(),
    });
  }

  const chartData = { labels, datasets };

  // Define milestones that resolve against category labels
  const milestones: Milestone[] = [
    {
      x: 0,
      label: "Start",
      color: "#2563eb",
      iconWidth: 16,
      iconHeight: 10,
      iconRadius: 3,
      tooltip: {
        title: "Series Start",
        lines: ["First visible data point"],
        items: [
          { key: "Index", value: 0 },
          { key: "Label", value: labels[0] ?? "N/A" },
        ],
      },
    },
    {
      x: labels.length - 1,
      label: "Latest",
      color: "#16a34a",
      iconWidth: 16,
      iconHeight: 10,
      iconRadius: 3,
      tooltip: {
        title: "Latest Observation",
        items: [
          { key: "Index", value: labels.length - 1 },
          { key: "Label", value: labels[labels.length - 1] ?? "N/A" },
        ],
      },
    },
    ...(labels.includes("2025 Q1")
      ? [
          {
            x: "2025 Q1",
            label: "Carney Elected",
            color: "#e74c3c",
            iconWidth: 16,
            iconHeight: 10,
            iconRadius: 3,
            tooltip: {
              title: "Carney Elected",
              lines: ["Political event marker"],
              items: [{ key: "Period", value: "2025 Q1" }],
            },
          },
        ]
      : []),
  ];

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top" as const,
        padding: 20,
        labels: { padding: 15, font: { size: 12 } },
      },
      title: {
        display: true,
        text: title,
        font: {
          size: 16,
          weight: "bold" as const,
        },
        padding: {
          top: 10,
          bottom: 20,
        },
      },
      tooltip: {
        callbacks: {
          label: function (context: any) {
            if (
              context.dataset.label &&
              context.dataset.label.includes("Target")
            ) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`;
            }
            if (
              context.dataset.label &&
              context.dataset.label.includes("Growth Rate")
            ) {
              if (context.parsed.y === null) return null;
              return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`;
            }
            return null;
          },
        },
        // Keep default tooltips but add external handler for milestones
        external: externalTooltipHandler,
      },
      // Pass plugin-specific options keyed by the plugin id.
      "milestone-plugin": {
        milestones,
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: "Growth Rate (%)",
          font: { size: 14 },
          padding: { bottom: 10 },
        },
        ticks: {
          padding: 8,
          callback: function (value: any) {
            return `${Number(value).toFixed(1)}%`;
          },
        },
      },
      x: {
        title: {
          display: true,
          text: quarterlyData ? "Year-Quarter" : "Year",
          font: { size: 14 },
          padding: { top: 10 },
        },
        ticks: {
          maxRotation: 45,
          minRotation: 45,
          padding: 5,
          autoSkip: true,
          maxTicksLimit: 20,
        },
      },
    },
    layout: {
      // Extra bottom padding so icons under axis are visible
      padding: { left: 15, right: 15, top: 20, bottom: 50 },
    },
    interaction: { mode: "index" as const, intersect: false },
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        minHeight: "440px",
        position: "relative",
      }}
    >
      <Line data={chartData} options={options} />
    </div>
  );
}
