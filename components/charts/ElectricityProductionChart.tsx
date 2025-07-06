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
import electricityProductionData from "@/metrics/statscan/electricity-production.json";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface ElectricityProductionChartProps {
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

export default function ElectricityProductionChart({
  title = "National Electricity Production",
  startYear = 2015,
  endYear = 2024,
  showTarget = true,
  targetValue = 751, // 20% above 2020-2024 average (52.17 TWh/month * 12 * 1.2)
  showTrend = true,
}: ElectricityProductionChartProps) {
  // Get electricity production data
  const productionDataObj = electricityProductionData as {
    data: {
      [key: string]: {
        [key: string]: (string | number)[][]
      }
    }
  };
  const allProductionData = productionDataObj.data["National Electricity Production"]?.["Total Production (TWh)"] || [];

  // Calculate annual totals
  const annualTotals: { [year: string]: number } = {};
  
  allProductionData.forEach((dataPoint) => {
    const dateStr = dataPoint[0] as string;
    const year = dateStr.split("-")[0];
    const value = dataPoint[1] as number;
    
    if (!annualTotals[year]) {
      annualTotals[year] = 0;
    }
    annualTotals[year] += value;
  });

  // Filter by year range and create arrays for chart
  const years: string[] = [];
  const productionValues: number[] = [];
  
  Object.keys(annualTotals)
    .sort()
    .forEach((year: string) => {
      const yearNum = parseInt(year);
      if (yearNum >= startYear && yearNum <= endYear) {
        years.push(year);
        productionValues.push(annualTotals[year]);
      }
    });

  // Calculate linear trend line if requested
  let trendValues: number[] = [];
  if (showTrend && productionValues.length > 1) {
    const n = productionValues.length;
    const sumX = years.reduce((sum: number, _: string, index: number) => sum + index, 0);
    const sumY = productionValues.reduce((sum: number, val: number) => sum + val, 0);
    const sumXY = productionValues.reduce((sum: number, val: number, index: number) => sum + (index * val), 0);
    const sumX2 = years.reduce((sum: number, _: string, index: number) => sum + (index * index), 0);

    const slope = (n * sumXY - sumX * sumY) / (n * sumX2 - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;

    trendValues = years.map((_: string, index: number) => intercept + slope * index);
  }

  // Configure datasets for the chart
  const datasets: ChartDataset[] = [
    {
      label: "Electricity Production",
      data: productionValues,
      borderColor: "rgb(30, 144, 255)", // Dodger Blue for electricity
      backgroundColor: "rgba(30, 144, 255, 0.1)",
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
      label: "2029 Target (20% above 2020-2024 avg)",
      data: Array(years.length).fill(targetValue),
      borderColor: "rgb(220, 20, 60)",
      backgroundColor: "rgba(220, 20, 60, 0.5)",
      borderWidth: 2,
      borderDash: [10, 5],
      pointRadius: 0,
      tension: 0,
    });
  }

  const chartData = {
    labels: years,
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
            return `${context.dataset.label}: ${context.parsed.y.toFixed(1)} TWh`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        min: 580,
        title: {
          display: true,
          text: "Production (Terawatt-hours)",
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
            return `${Number(value).toFixed(0)} TWh`;
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