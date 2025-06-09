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
import defenseData from "@/metrics/worldbank/defense-spending.json";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface DefenseSpendingChartProps {
  title?: string;
  startYear?: number;
  endYear?: number;
  showTarget?: boolean;
  targetValue?: number;
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

export default function DefenseSpendingChart({
  title = "Military expenditure (% of GDP)",
  startYear = 2000,
  endYear = 2029,
  showTarget = true,
  targetValue = 2.0,
}: DefenseSpendingChartProps) {
  // Get defense spending data
  const defenseDataObj = defenseData as any;
  const militaryExpenditureData =
    defenseDataObj.data["Military expenditure (% of GDP)"] || [];

  // Filter data by year range
  const filteredData = militaryExpenditureData.filter(function (item: any) {
    const year = parseInt(item[0]);
    return year >= startYear && year <= endYear;
  });

  // Extract labels and values
  const labels = filteredData.map(function (item: any) {
    return item[0]; // Year as string
  });

  const chartValues = filteredData.map(function (item: any) {
    return item[1]; // Defense spending percentage
  });

  const datasets: ChartDataset[] = [
    {
      label: "Defence Spending (% of GDP)",
      data: chartValues,
      borderColor: "rgb(54, 162, 235)",
      backgroundColor: "rgba(54, 162, 235, 0.1)",
      tension: 0.3,
    },
  ];

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: "NATO Target (2%)",
      data: Array(labels.length).fill(targetValue),
      borderColor: "rgb(255, 99, 132)",
      backgroundColor: "rgba(255, 99, 132, 0.5)",
      borderWidth: 2,
      borderDash: [5, 5],
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
            }
            return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        max: Math.max(3.0, targetValue ? targetValue + 0.5 : 3.0),
        title: {
          display: true,
          text: "Percentage of GDP (%)",
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
          maxRotation: 45,
          minRotation: 0,
          padding: 5,
          autoSkip: true,
          maxTicksLimit: 15,
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
