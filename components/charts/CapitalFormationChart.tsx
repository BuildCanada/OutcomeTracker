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
} from "chart.js";
import type { ChartData } from 'chart.js';
import gdpData from "@/metrics/statscan/gdp.json";

// Define types for our data
type DateValuePair = {
  date: string;
  value: number;
};

type RawDataPoint = [string, number]; // [date, value]

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend
);

interface CapitalFormationChartProps {
  title?: string;
  startYear?: number;
  endYear?: number;
  quarterlyData?: boolean;
  showTarget?: boolean;
  targetValue?: number;
}

interface ChartDataset {
  label: string;
  data: number[];
  borderColor: string;
  backgroundColor: string;
  tension?: number;
  borderWidth?: number;
  borderDash?: number[];
  pointRadius?: number;
}

export default function CapitalFormationChart({
  title = "% of GDP in capital-focused public and private investment",
  startYear = 1990,
  endYear = 2023,
  quarterlyData = true,
  showTarget = true,
  targetValue = 17,
}: CapitalFormationChartProps) {
  // Get required data series
  const gdpDataObj = gdpData as any;
  const totalGdp = gdpDataObj.data["Gross domestic product at market prices"] || [];
  const grossFixedCapital = gdpDataObj.data["Gross fixed capital formation"] || [];
  const residentialStructures = gdpDataObj.data["Residential structures"] || [];

  // Build a lookup for easier data processing
  const gdpLookup: Record<string, number> = {};
  totalGdp.forEach((item: [string, number]) => {
    gdpLookup[item[0]] = item[1];
  });

  const residentialLookup: Record<string, number> = {};
  residentialStructures.forEach((item: [string, number]) => {
    residentialLookup[item[0]] = item[1];
  });

  // Calculate capital formation excluding residential structures as % of GDP
  const percentageData = grossFixedCapital
    .map((item: RawDataPoint) => {
      const dateStr = item[0];
      const grossFixedValue = item[1];
      const gdpValue = gdpLookup[dateStr];
      const residentialValue = residentialLookup[dateStr] || 0;
      
      // Skip if we don't have matching GDP data
      if (!gdpValue) return null;
      
      // Calculate non-residential capital formation
      const nonResidentialCapital = grossFixedValue - residentialValue;
      
      // Calculate as percentage of GDP
      const percentage = (nonResidentialCapital / gdpValue) * 100;
      
      return {
        date: dateStr,
        value: percentage
      };
    })
    // @ts-ignore
    .filter(item => item !== null);

  // Filter data by year range
  // @ts-ignore
  const filteredData = percentageData.filter(function(item) {
    const year = parseInt(item.date.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Format dates for display
  // @ts-ignore
  const labels = filteredData.map(function(item) {
    if (quarterlyData) {
      const [year, month] = item.date.split("-");
      // Convert month number to quarter (01->Q1, 04->Q2, 07->Q3, 10->Q4)
      const quarter = Math.floor(parseInt(month) / 3) + 1;
      return `${year} Q${quarter}`;
    } else {
      return item.date.split("-")[0]; // Just show year
    }
  });

  // Extract values for chart
  // @ts-ignore
  const chartValues = filteredData.map(function(item) { return item.value; });

  const datasets: ChartDataset[] = [
    {
      label: "Non-residential Capital Formation % of GDP",
      data: chartValues,
      borderColor: "rgb(53, 162, 235)",
      backgroundColor: "rgba(53, 162, 235, 0.5)",
      tension: 0.3,
    },
  ];

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: "Target",
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

  const options: ChartOptions<'line'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: "top",
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
          weight: 'bold',
        },
        padding: {
          top: 10,
          bottom: 20,
        },
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            // Different format for target value
            if (context.dataset.label === "Target") {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`;
            }
            return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`;
          }
        }
      }
    },
    scales: {
      y: {
        beginAtZero: false,
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
          callback: function(value: any) {
            return `${value.toFixed(1)}%`;
          }
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
    <div style={{ width: '100%', height: '100%', minHeight: '400px', position: 'relative' }}>
      <Line data={chartData} options={options} />
    </div>
  );
}