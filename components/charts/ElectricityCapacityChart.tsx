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
import electricityCapacityData from "@/metrics/statscan/electricity-capacity.json";

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

interface ChartDataset {
  label: string;
  data: number[];
  borderColor: string;
  backgroundColor: string;
  tension: number;
  borderWidth?: number;
  borderDash?: number[];
  pointRadius?: number;
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
  const capacityDataObj = electricityCapacityData as any;
  const capacityData = capacityDataObj.data["National Electricity Capacity"]?.["Total Capacity (GW)"] || [];

  // Filter data by year range
  const filteredData = capacityData.filter((dataPoint: [string, number]) => {
    const year = parseInt(dataPoint[0]);
    return year >= startYear && year <= endYear;
  });

  // Get labels (years)
  const labels = filteredData.map((dataPoint: [string, number]) => dataPoint[0]);

  // Get capacity values
  const capacityValues = filteredData.map(
    (dataPoint: [string, number]) => dataPoint[1]
  );

  // Calculate linear trend line if requested
  let trendValues: number[] = [];
  if (showTrend && capacityValues.length > 1) {
    // Calculate linear regression
    const n = capacityValues.length;
    const sumX = labels.reduce((sum, _, index) => sum + index, 0);
    const sumY = capacityValues.reduce((sum: number, val: number) => sum + val, 0);
    const sumXY = capacityValues.reduce((sum: number, val: number, index: number) => sum + (index * val), 0);
    const sumX2 = labels.reduce((sum, _, index) => sum + (index * index), 0);

    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;

    trendValues = labels.map((_, index) => intercept + slope * index);
  }

  // Configure datasets for the chart
  const datasets: ChartDataset[] = [
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

  // Add trend line if requested
  if (showTrend && trendValues.length > 0) {
    datasets.push({
      label: "Trend",
      data: trendValues,
      borderColor: "rgb(255, 140, 0)",
      backgroundColor: "rgba(255, 140, 0, 0.5)",
      tension: 0,
      borderDash: [5, 5],
      pointRadius: 0,
      borderWidth: 2,
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
          callback: function (value: any) {
            return `${value.toFixed(0)} GW`;
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