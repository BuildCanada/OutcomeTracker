"use client";

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
} from "chart.js/auto";
import labourProductivityData from "@/metrics/statscan/labour-productivity.json";
import {
  getPrimaryLineStyling,
  getTargetLineStyling,
  getTrendLineStyling,
} from "@/components/charts/utils/styling";
import { LineChartDataset } from "@/components/charts/types";
import { calculateLinearTrend } from "./utils/trendCalculator";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface LabourProductivityGrowthChartProps {
  title?: string;
  sector?: string;
  startYear?: number;
  endYear?: number;
  quarterlyData?: boolean;
  showTarget?: boolean;
  targetValue?: number;
  showProductivityIndex?: boolean;
  showTrend?: boolean;
}

export default function LabourProductivityGrowthChart({
  title = "Labour Productivity Growth",
  sector = "Total economy",
  startYear = 2015,
  endYear = 2024,
  quarterlyData = true,
  showTarget = true,
  targetValue = 2.0,
  showProductivityIndex = false,
  showTrend = true,
}: LabourProductivityGrowthChartProps) {
  // Get data for selected sector
  const productivityDataObj = labourProductivityData as any;
  const sectorData = productivityDataObj.data[sector] || [];

  // Filter data by year range
  const filteredData = sectorData.filter((dataPoint: [string, number]) => {
    const dateStr = dataPoint[0];
    const year = parseInt(dateStr.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Calculate year-over-year growth rates
  const growthRates: (number | null)[] = filteredData.map(
    (dataPoint: [string, number], index: number) => {
      if (index < 4) return null; // Need at least 4 quarters for YoY comparison

      const currentValue = dataPoint[1];
      const previousYearValue = filteredData[index - 4][1];

      if (
        previousYearValue === 0 ||
        previousYearValue === null ||
        currentValue === null
      )
        return null;

      return ((currentValue - previousYearValue) / previousYearValue) * 100;
    },
  );

  // Get productivity index values for secondary axis if requested
  const productivityValues = showProductivityIndex
    ? filteredData.map((dataPoint: [string, number]) => dataPoint[1])
    : [];

  // Format dates for display
  let labels = filteredData.map((dataPoint: [string, number]) => {
    const dateStr = dataPoint[0];
    if (quarterlyData) {
      const [year, month] = dateStr.split("-");
      // Convert month number to quarter (01->Q1, 04->Q2, 07->Q3, 10->Q4)
      const quarter = Math.floor(parseInt(month) / 3) + 1;
      return `${year} Q${quarter}`;
    } else {
      return dateStr.split("-")[0]; // Just show year
    }
  });

  // Align labels and data arrays to start from first valid growth rate (index 4)
  labels = labels.slice(4);
  const alignedGrowthRates = growthRates.slice(4);
  const alignedProductivityValues = showProductivityIndex
    ? productivityValues.slice(4)
    : [];

  const datasets: LineChartDataset[] = [
    {
      label: "YoY Growth Rate (%)",
      data: alignedGrowthRates,
      ...getPrimaryLineStyling({ yAxisID: "y" }),
    },
  ];

  // Calculate and add trend line
  if (showTrend && alignedGrowthRates.length > 1) {
    const trendValues = calculateLinearTrend(alignedGrowthRates as number[]);
    datasets.push({
      label: "Trend",
      data: trendValues,
      ...getTrendLineStyling(),
    });
  }

  // Add productivity index if requested
  if (showProductivityIndex) {
    datasets.push({
      label: "Productivity Index",
      data: alignedProductivityValues,
      borderColor: "rgb(156, 163, 175)",
      backgroundColor: "rgba(156, 163, 175, 0.5)",
      tension: 0.3,
      borderDash: [3, 3],
      yAxisID: "y1",
    });
  }

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: `Target (${targetValue}%)`,
      data: Array(labels.length).fill(targetValue),
      ...getTargetLineStyling({ yAxisID: "y" }),
    });
  }

  const chartData = {
    labels,
    datasets,
  };

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index" as const,
      intersect: false,
    },
    plugins: {
      legend: {
        position: "top" as const,
        padding: 20,
        labels: {
          padding: 15,
          font: {
            size: 12,
          },
        },
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
            if (context.dataset.label.includes("Target")) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`;
            } else if (context.dataset.label.includes("Growth Rate")) {
              if (context.parsed.y === null) return null;
              return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`;
            } else if (context.dataset.label.includes("Index")) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}`;
            }
            return `${context.dataset.label}: ${context.parsed.y}`;
          },
        },
      },
    },
    scales: {
      x: {
        title: {
          display: true,
          text: quarterlyData ? "Year-Quarter" : "Year",
          font: {
            size: 14,
          },
          padding: {
            top: 10,
          },
        },
        ticks: {
          maxRotation: 45,
          minRotation: 45,
          padding: 5,
          autoSkip: true,
          maxTicksLimit: 20,
        },
      },
      y: {
        type: "linear" as const,
        display: true,
        position: "left" as const,
        title: {
          display: true,
          text: "Growth Rate (%)",
          font: {
            size: 14,
          },
          padding: {
            bottom: 10,
          },
        },
        ticks: {
          padding: 8,
          callback: function (value: any) {
            return `${value.toFixed(1)}%`;
          },
        },
        grid: {
          drawOnChartArea: true,
        },
      },
      ...(showProductivityIndex && {
        y1: {
          type: "linear" as const,
          display: true,
          position: "right" as const,
          title: {
            display: true,
            text: "Productivity Index (2017=100)",
            font: {
              size: 14,
            },
            padding: {
              bottom: 10,
            },
          },
          ticks: {
            padding: 8,
            callback: function (value: any) {
              return value.toFixed(1);
            },
          },
          grid: {
            drawOnChartArea: false,
          },
        },
      }),
    },
    layout: {
      padding: {
        left: 15,
        right: 15,
        top: 20,
        bottom: 20,
      },
    },
  };

  return (
    <div
      style={{
        width: "100%",
        height: "100%",
        minHeight: "400px",
        position: "relative",
      }}
    >
      <Line data={chartData} options={options} />
    </div>
  );
}
