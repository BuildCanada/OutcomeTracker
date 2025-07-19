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
import { calculateLinearTrend } from "@/components/charts/utils/trendCalculator";
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

interface ProductivityChartProps {
  title?: string;
  sector?: string;
  startYear?: number;
  endYear?: number;
  quarterlyData?: boolean;
  showTarget?: boolean;
  targetValue?: number;
  showGrowthRate?: boolean;
  showTrend?: boolean;
}

export default function ProductivityChart({
  title = "Public Service Productivity",
  sector = "Non-business sector and others",
  startYear = 2015,
  endYear = 2024,
  quarterlyData = true,
  showTarget = true,
  targetValue = 120,
  showGrowthRate = false,
  showTrend = true,
}: ProductivityChartProps) {
  // Get data for selected sector
  const productivityDataObj = labourProductivityData as any;
  const sectorData = productivityDataObj.data[sector] || [];

  // Filter data by year range
  const filteredData = sectorData.filter((dataPoint: [string, number]) => {
    const dateStr = dataPoint[0];
    const year = parseInt(dateStr.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Format dates for display
  const labels = filteredData.map((dataPoint: [string, number]) => {
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

  // Get productivity values
  const productivityValues = filteredData.map(
    (dataPoint: [string, number]) => dataPoint[1],
  );

  // Calculate year-over-year growth rates if requested
  let growthRates: number[] = [];
  if (showGrowthRate) {
    growthRates = productivityValues
      .map((value: number, index: number) => {
        if (index < 4) return null; // Need at least 4 quarters for YoY comparison
        const previousYearValue = productivityValues[index - 4];
        if (previousYearValue === 0) return null;
        return ((value - previousYearValue) / previousYearValue) * 100;
      })
      .filter((val: any) => val !== null) as number[];

    // Pad beginning with nulls to align with original data
    const padding = new Array(4).fill(null);
    growthRates = [...padding, ...growthRates];
  }

  const datasets: LineChartDataset[] = [
    {
      label: "Productivity Index",
      data: productivityValues,
      ...getPrimaryLineStyling(),
    },
  ];

  // Calculate linear trend if requested
  if (showTrend && productivityValues.length > 1) {
    const trendValues = calculateLinearTrend(productivityValues);
    datasets.push({
      label: "Trend",
      data: trendValues,
      ...getTrendLineStyling(),
    });
  }

  // Add growth rate line if requested
  if (showGrowthRate) {
    datasets.push({
      label: "YoY Growth Rate (%)",
      data: growthRates,
      ...getTrendLineStyling(),
    });
  }

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: "Target (20% increase)",
      data: Array(labels.length).fill(targetValue),
      ...getTargetLineStyling(),
    });
  }

  const chartData = {
    labels,
    datasets,
  };

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
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
            if (context.dataset.label.includes("Growth Rate")) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`;
            } else if (context.dataset.label.includes("Target")) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}`;
            }
            return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
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
      },
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
