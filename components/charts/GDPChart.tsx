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
import gdpData from "@/metrics/statscan/gdp.json";

// Define TypeScript interfaces for our data structure
type GDPDataPoint = [string, number];

interface GDPDataStructure {
  data: {
    [key: string]: Array<[string, number]>;
  };
}

// Type for chart datasets
interface ChartDataset {
  label: string;
  data: number[];
  borderColor: string;
  backgroundColor: string;
  tension: number;
  borderDash?: number[];
}

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface GDPChartProps {
  title?: string;
  metric?: string;
  startYear?: number;
  endYear?: number;
  quarterlyData?: boolean;
  showTarget?: boolean;
  targetValue?: number;
}

export default function GDPChart({
  title = "GDP Growth",
  metric = "Gross domestic product at market prices",
  startYear = 2010,
  endYear = 2023,
  quarterlyData = true,
  showTarget = false,
  targetValue,
}: GDPChartProps) {
  // Get data for selected GDP metric
  const gdpDataObj = gdpData as any;
  const metricData = gdpDataObj.data[metric] || [];

  // Filter data by year range
  const filteredData = metricData.filter((dataPoint: GDPDataPoint) => {
    const dateStr = dataPoint[0];
    const year = parseInt(dateStr.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Format dates for display
  const labels = filteredData.map((dataPoint: GDPDataPoint) => {
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

  // Get GDP values
  const gdpValues = filteredData.map(
    (dataPoint: GDPDataPoint) => dataPoint[1] / 1000,
  ); // Convert to billions for readability

  const datasets: ChartDataset[] = [
    {
      label: `${metric}`,
      data: gdpValues,
      borderColor: "rgb(53, 162, 235)",
      backgroundColor: "rgba(53, 162, 235, 0.5)",
      tension: 0.3,
    },
  ];

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: "Target",
      data: Array(labels.length).fill(targetValue / 1000),
      borderColor: "rgb(255, 99, 132)",
      backgroundColor: "rgba(255, 99, 132, 0.5)",
      tension: 0.3,
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
            return `${context.dataset.label}: ${context.parsed.y.toLocaleString()} billion`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: "Value (billions CAD)",
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
