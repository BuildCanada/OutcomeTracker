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
  ChartOptions,
} from "chart.js/auto";
import electricityCapacityData from "@/metrics/statscan/electricity-capacity.json";
import { calculateLinearTrend } from "./utils/trendCalculator";
import { LineChartDataset } from "./types";
import { getTrendLineStyling } from "./utils/styling";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface ElectricityCapacityChartProps {
  title?: string;
  startYear?: number;
  endYear?: number;
  showTarget?: boolean;
  targetValue?: number;
  showTrend?: boolean;
}



export default function ElectricityCapacityChart({
  title = "National Electricity Capacity",
  startYear = 2015,
  endYear = 2023,
  showTarget = true,
  targetValue = 175.15, // 20% increase from 2020 base of 145.96 GW
  showTrend = true,
}: ElectricityCapacityChartProps) {
  // Get electricity capacity data
  const capacityDataObj = electricityCapacityData as {
    data: {
      [key: string]: {
        [key: string]: (string | number)[][]
      }
    }
  };
  const capacityData = capacityDataObj.data["National Electricity Capacity"]?.["Total Capacity (GW)"] || [];

  // Filter data by year range
  const filteredData = capacityData.filter((dataPoint) => {
    const year = parseInt(dataPoint[0] as string);
    return year >= startYear && year <= endYear;
  });

  // Get labels (years)
  const labels = filteredData.map((dataPoint) => dataPoint[0] as string);

  // Get capacity values
  const capacityValues = filteredData.map(
    (dataPoint) => dataPoint[1] as number
  );

  // Configure datasets for the chart
  const datasets: LineChartDataset[] = [
    {
      label: "Electricity Capacity",
      data: capacityValues,
      borderColor: "rgb(34, 139, 34)",
      backgroundColor: "rgba(34, 139, 34, 0.1)",
      tension: 0.3,
      borderWidth: 3,
      pointRadius: 5,
    },
  ];

  // Calculate and add trend line if requested
  if (showTrend && capacityValues.length > 1) {
    const trendValues = calculateLinearTrend(capacityValues);
    datasets.push({
      label: "Trend",
      data: trendValues,
      ...getTrendLineStyling(),
    });
  }

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: "2029 Target (20% increase from 2020)",
      data: Array(labels.length).fill(targetValue),
      borderColor: "rgb(220, 20, 60)",
      backgroundColor: "rgba(220, 20, 60, 0.5)",
      borderWidth: 2,
      borderDash: [10, 5],
      pointRadius: 0,
      tension: 0,
    });
  }

  const chartData = {
    labels,
    datasets,
  };

  const options: ChartOptions<"line"> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top" as const,
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
          label: function (context) {
            return `${context.dataset.label}: ${context.parsed.y.toFixed(2)} GW`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        min: 140,
        title: {
          display: true,
          text: "Capacity (Gigawatts)",
          font: {
            size: 14,
          },
          padding: {
            bottom: 10,
          },
        },
        ticks: {
          padding: 8,
          callback: function (value) {
            return `${Number(value).toFixed(0)} GW`;
          },
        },
      },
      x: {
        title: {
          display: true,
          text: "Year",
          font: {
            size: 14,
          },
          padding: {
            top: 10,
          },
        },
        ticks: {
          padding: 5,
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