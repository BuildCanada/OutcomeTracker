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
import {
  getPrimaryLineStyling,
  getTargetLineStyling,
  getTrendLineStyling,
} from "@/components/charts/utils/styling";
import { LineChartDataset } from "@/components/charts/types";
import useSWR from "swr";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface PrimaryEnergyChartProps {
  title?: string;
  category?: string;
  startYear?: number;
  endYear?: number;
  monthlyData?: boolean;
  showTarget?: boolean;
  targetValue?: number;
  showTrend?: boolean;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function PrimaryEnergyChart({
  title = "Total Primary Energy Production",
  category = "Total energy",
  startYear = 2015,
  endYear = 2025,
  monthlyData = true,
  showTarget = false,
  targetValue = 2500000,
  showTrend = true,
}: PrimaryEnergyChartProps) {
  const {
    data: energyData,
    error,
    isLoading,
  } = useSWR(
    "/tracker/api/v1/statcan_datasets/consolidated-energy-statistics-monthly",
    fetcher,
  );

  if (isLoading) {
    return <div>Loading energy data...</div>;
  }

  if (error || !energyData) {
    return <div>Error loading energy data</div>;
  }

  // Transform the new API data format
  const apiData = energyData.current_data || [];

  // Filter data by fuel type, production characteristic, and year range
  const filteredData = apiData
    .filter((item: any) => {
      const year = parseInt(item.REF_DATE.split("-")[0]);
      return (
        year >= startYear &&
        year <= endYear &&
        item["Fuel type"] === category &&
        item["Supply and demand characteristics"] === "Production"
      );
    })
    .map((item: any) => [item.REF_DATE, item.VALUE])
    .sort((a: any, b: any) => a[0].localeCompare(b[0]));

  // Format dates for display
  const labels = filteredData.map((dataPoint: [string, number]) => {
    const dateStr = dataPoint[0];
    if (monthlyData) {
      const [year, month] = dateStr.split("-");
      // Convert month number to month name
      const monthNames = [
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
      ];
      const monthIndex = parseInt(month) - 1;
      return `${year}-${monthNames[monthIndex]}`;
    } else {
      return dateStr.split("-")[0]; // Just show year
    }
  });

  // Get energy production values (convert from terajoules to petajoules for readability)
  const energyValues = filteredData.map(
    (dataPoint: [string, number]) => dataPoint[1] / 1000,
  );

  // Calculate moving average for trend line if requested
  let trendValues: number[] = [];
  if (showTrend) {
    const period = 12; // 12-month moving average
    trendValues = energyValues
      .map((_: number, index: number, array: number[]) => {
        if (index < period - 1) return null;

        let sum = 0;
        for (let i = 0; i < period; i++) {
          sum += array[index - i];
        }
        return sum / period;
      })
      .filter((val: any) => val !== null) as number[];

    // Pad beginning with nulls to align with original data
    const padding = new Array(period - 1).fill(null);
    trendValues = [...padding, ...trendValues];
  }

  // Configure datasets for the chart
  const datasets: LineChartDataset[] = [
    {
      label: `${category} Production`,
      data: energyValues,
      ...getPrimaryLineStyling(),
      tension: 0.3,
    },
  ];

  // Add trend line if requested
  if (showTrend) {
    datasets.push({
      label: "12-Month Moving Average",
      data: trendValues,
      ...getTrendLineStyling(),
    });
  }

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: "Target",
      data: Array(labels.length).fill(targetValue / 1000), // Convert target to petajoules
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
            if (context.dataset.label.includes("Target")) {
              return `${context.dataset.label}: ${(context.parsed.y * 1000).toLocaleString()} TJ`;
            }
            return `${context.dataset.label}: ${(context.parsed.y * 1000).toLocaleString()} TJ`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: "Energy Production (Petajoules)",
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
            return `${value.toLocaleString()} PJ`;
          },
        },
      },
      x: {
        title: {
          display: true,
          text: monthlyData ? "Year-Month" : "Year",
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
