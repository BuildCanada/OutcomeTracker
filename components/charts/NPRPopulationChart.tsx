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
import nprData from "@/metrics/statscan/non-permanent-residents.json";
import populationData from "@/metrics/statscan/population.json";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface NPRPopulationChartProps {
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
  tension: number;
  borderWidth?: number;
  borderDash?: number[];
  pointRadius?: number;
}

export default function NPRPopulationChart({
  title = "Proportion of the Canadian population that is made up of non-permanent residents",
  startYear = 2021,
  endYear = new Date().getFullYear(),
  quarterlyData = true,
  showTarget = true,
  targetValue = 5.0,
}: NPRPopulationChartProps) {
  // Get data sources
  const nprDataObj = nprData as any;
  const populationDataObj = populationData as any;
  const totalNPR = nprDataObj.data["Total, non-permanent residents"] || [];
  const totalPopulation = populationDataObj.data["Canada"] || [];

  // Build a lookup for total population data
  const populationLookup: Record<string, number> = {};
  // @ts-ignore
  totalPopulation.forEach(function (item: any) {
    populationLookup[item[0]] = item[1];
  });

  // Calculate NPR percentage of total population
  // @ts-ignore
  const percentageData = totalNPR
    .map(function (item: any) {
      const dateStr = item[0];
      const nprValue = item[1];
      const totalPopValue = populationLookup[dateStr];

      // Skip if we don't have matching population data
      if (!totalPopValue) return null;

      // Calculate as percentage
      const percentage = (nprValue / totalPopValue) * 100;

      return {
        date: dateStr,
        value: percentage,
      };
    })
    .filter(function (item: any) {
      return item !== null;
    });

  // Filter data by year range
  // @ts-ignore
  const filteredData = percentageData.filter(function (item) {
    const year = parseInt(item.date.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Format dates for display
  // @ts-ignore
  const labels = filteredData.map(function (item) {
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
  const chartValues = filteredData.map(function (item) {
    return item.value;
  });

  const datasets: ChartDataset[] = [
    {
      label: "NPR %",
      data: chartValues,
      borderColor: "rgb(53, 162, 235)",
      backgroundColor: "rgba(53, 162, 235, 0.5)",
      tension: 0.3,
    },
  ];

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: "Target (5%)",
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
            // Different format for target values
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
        beginAtZero: false,
        title: {
          display: true,
          text: "Percentage of Total Population (%)",
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
