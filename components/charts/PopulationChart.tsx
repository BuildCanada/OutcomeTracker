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
} from "chart.js";
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

interface PopulationChartProps {
  title?: string;
  region?: string;
  startYear?: number;
  endYear?: number;
  showGoal?: boolean;
  goalValue?: number;
}

export default function PopulationChart({
  title = "Population Growth",
  region = "Canada",
  startYear = 2010,
  endYear = 2030,
  showGoal = false,
  goalValue = 40000000,
}: PopulationChartProps) {
  // Get data for selected region
  const regionData = populationData.data[region] || [];
  console.log({ populationData });
  // Filter data by year range
  const filteredData = regionData.filter(([dateStr]) => {
    const year = parseInt(dateStr.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Format the data for the chart
  const labels = filteredData.map(([dateStr]) => {
    const [year, month] = dateStr.split("-");
    return `${year}-${month}`;
  });

  const populationValues = filteredData.map(([_, value]) => value);

  const datasets = [
    {
      label: `${region} Population`,
      data: populationValues,
      borderColor: "rgb(34, 34, 34)",
      backgroundColor: "rgba(34, 34, 34, 0.5)",
      tension: 0.3,
    },
  ];

  if (showGoal) {
    datasets.push({
      label: "Population Goal",
      data: Array(labels.length).fill(goalValue),
      borderColor: "rgb(139, 35, 50)",
      backgroundColor: "rgba(139, 35, 50, 0.5)",
      borderDash: [5, 5],
    });
  }

  const chartData = {
    labels,
    datasets,
  };

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: "top" as const,
      },
      title: {
        display: true,
        text: title,
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: "Population",
        },
      },
      x: {
        title: {
          display: true,
          text: "Year-Month",
        },
      },
    },
  };

  return <Line data={chartData} options={options} />;
}
