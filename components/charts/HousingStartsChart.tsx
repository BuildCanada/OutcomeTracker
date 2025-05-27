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
import housingStartsData from "@/metrics/statscan/housing-starts.json";

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

// Define props for the component
interface HousingStartsChartProps {
  title?: string;
  category?: string;
  startYear?: number;
  endYear?: number;
  monthlyData?: boolean;
  showTrend?: boolean;
}

// Type for datasets
interface ChartDataset {
  label: string;
  data: number[];
  borderColor: string;
  backgroundColor: string;
  tension: number;
  borderDash?: number[];
}

export default function HousingStartsChart({
  title = "Housing Starts",
  category = "Total housing starts",
  startYear = 2010,
  endYear = 2023,
  monthlyData = true,
  showTrend = false,
}: HousingStartsChartProps) {
  // Get data for selected housing category
  const housingData = housingStartsData as any;
  const categoryData = housingData.data[category] || [];

  // Filter data by year range
  const filteredData = categoryData.filter((dataPoint: [string, number]) => {
    const dateStr = dataPoint[0];
    const year = parseInt(dateStr.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

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
      // Group by year by aggregating values
      return dateStr.split("-")[0];
    }
  });

  // Get housing starts values
  const housingValues = filteredData.map(
    (dataPoint: [string, number]) => dataPoint[1],
  );

  // Calculate moving average for trend line if requested
  let trendValues: number[] = [];
  if (showTrend) {
    const period = 12; // 12-month moving average
    trendValues = housingValues
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
  const datasets: ChartDataset[] = [
    {
      label: `${category}`,
      data: housingValues,
      borderColor: "rgb(53, 162, 235)",
      backgroundColor: "rgba(53, 162, 235, 0.5)",
      tension: 0.3,
    },
  ];

  // Add trend line if requested
  if (showTrend) {
    datasets.push({
      label: "12-Month Moving Average",
      data: trendValues,
      borderColor: "rgb(255, 99, 132)",
      backgroundColor: "rgba(255, 99, 132, 0.5)",
      tension: 0.5,
      borderDash: [5, 5],
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
            return `${context.dataset.label}: ${context.parsed.y.toLocaleString()} units`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: "Number of Housing Starts",
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
            return value.toLocaleString();
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
