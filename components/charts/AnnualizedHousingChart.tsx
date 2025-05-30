"use client";

import { Chart } from "react-chartjs-2";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
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
  BarElement,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

// Define props for the component
interface AnnualizedHousingChartProps {
  title?: string;
  category?: string;
  startYear?: number;
  endYear?: number;
  showTarget?: boolean;
  targetValue?: number;
}

// Type for bar dataset
interface BarDataset {
  type?: "bar";
  label: string;
  data: number[];
  backgroundColor: string;
  borderColor?: string;
  borderWidth?: number;
  hoverBackgroundColor?: string;
}

// Type for line dataset
interface LineDataset {
  type: "line";
  label: string;
  data: number[];
  borderColor: string;
  backgroundColor: string;
  borderWidth?: number;
  borderDash?: number[];
  tension?: number;
  pointRadius?: number;
  pointHoverRadius?: number;
}

// Combined dataset type
type ChartDataset = BarDataset | LineDataset;

export default function AnnualizedHousingChart({
  title = "Annualized Housing Starts",
  category = "Total units",
  startYear = 2010,
  endYear = 2029,
  showTarget = false,
  targetValue = 300000,
}: AnnualizedHousingChartProps) {
  // Get data for selected housing category
  const housingData = housingStartsData as any;
  const categoryData = housingData.data[category] || [];

  // Filter data by year range
  const filteredData = categoryData.filter((dataPoint: [string, number]) => {
    const dateStr = dataPoint[0];
    const year = parseInt(dateStr.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Calculate trailing 12-month sums for each month
  const trailingData: { date: string; sum: number }[] = [];

  filteredData.forEach(
    (dataPoint: [string, number], index: number, array: [string, number][]) => {
      if (index >= 11) {
        // Need at least 12 months of data
        const date = dataPoint[0];
        let sum = 0;

        // Sum the current month and previous 11 months
        for (let i = 0; i < 12; i++) {
          sum += array[index - i][1];
        }

        trailingData.push({
          date,
          sum,
        });
      }
    },
  );

  // Format dates for display and get annualized values
  const labels = trailingData.map((item) => {
    const [year, month] = item.date.split("-");
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
  });

  const annualizedValues = trailingData.map((item) => item.sum);

  // Configure datasets for the chart
  const datasets: ChartDataset[] = [
    {
      type: "bar",
      label: `Annualized ${category}`,
      data: annualizedValues,
      backgroundColor: "rgba(53, 162, 235, 0.7)",
      borderColor: "rgb(53, 162, 235)",
      borderWidth: 1,
      hoverBackgroundColor: "rgba(53, 162, 235, 0.9)",
    },
  ];

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      type: "line",
      label: "Target (500,000)",
      data: Array(labels.length).fill(targetValue),
      borderColor: "rgb(255, 99, 132)",
      backgroundColor: "rgba(255, 99, 132, 0.3)",
      borderWidth: 2,
      borderDash: [5, 5],
      tension: 0.1,
      pointRadius: 0,
      pointHoverRadius: 4,
    });
  }

  const chartData = {
    labels,
    datasets,
  };

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    elements: {
      line: {
        fill: false,
      },
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
            return `${context.dataset.label}: ${context.parsed.y.toLocaleString()} units`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: "Total Units",
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
          text: "Year-Month",
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
      <Chart type="bar" data={chartData} options={options} />
    </div>
  );
}
