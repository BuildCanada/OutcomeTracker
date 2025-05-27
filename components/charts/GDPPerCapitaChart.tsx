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
import populationData from "@/metrics/statscan/population.json";
import {
  calculatePerCapita,
  TimeSeriesDataPoint,
} from "./utils/PerCapitaCalculator";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface GDPPerCapitaChartProps {
  title?: string;
  gdpMeasure?: string;
  startYear?: number;
  endYear?: number;
  quarterlyData?: boolean;
  showAnnual?: boolean;
  showTarget?: boolean;
  targetValue?: number;
}

export default function GDPPerCapitaChart({
  title = "GDP Per Capita",
  gdpMeasure = "Gross domestic product at market prices",
  startYear = 1961,
  endYear = 2023,
  quarterlyData = true,
  showAnnual = false,
  showTarget = false,
  targetValue = 50,
}: GDPPerCapitaChartProps) {
  // Get data sources
  const gdpMetricData = (gdpData as any).data[gdpMeasure] || [];
  const populationCanadaData = (populationData as any).data["Canada"] || [];

  // Calculate per capita values (in thousands of dollars)
  const perCapitaValues = calculatePerCapita(
    gdpMetricData,
    populationCanadaData,
    1000,
  );

  // Filter data by year range
  const filteredData = perCapitaValues.filter((dataPoint) => {
    const year = parseInt(dataPoint.date.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Format dates for display
  const labels = filteredData.map((dataPoint) => {
    if (quarterlyData) {
      const [year, month] = dataPoint.date.split("-");
      // Convert month number to quarter (01->Q1, 04->Q2, 07->Q3, 10->Q4)
      const quarter = Math.floor(parseInt(month) / 3) + 1;
      return `${year} Q${quarter}`;
    } else {
      return dataPoint.date.split("-")[0]; // Just show year
    }
  });

  // GDP per capita values
  const perCapitaDataValues = filteredData.map((dataPoint) => dataPoint.value);

  // Calculate annual average if requested
  let annualAverages: number[] = [];
  if (showAnnual && quarterlyData) {
    // Group data by year to calculate averages
    const yearlyGroups: Record<string, number[]> = {};

    filteredData.forEach((dataPoint) => {
      const year = dataPoint.date.split("-")[0];
      if (!yearlyGroups[year]) yearlyGroups[year] = [];
      yearlyGroups[year].push(dataPoint.value);
    });

    // For each quarter datapoint, find its year's average
    annualAverages = filteredData.map((dataPoint) => {
      const year = dataPoint.date.split("-")[0];
      const yearValues = yearlyGroups[year] || [];
      if (yearValues.length === 0) return 0;
      return yearValues.reduce((sum, val) => sum + val, 0) / yearValues.length;
    });
  }

  // Define dataset interface to prevent TS errors
  interface ChartDataset {
    label: string;
    data: number[];
    borderColor: string;
    backgroundColor: string;
    tension: number;
    borderWidth?: number;
    borderDash?: number[];
  }

  const datasets: ChartDataset[] = [
    {
      label: "GDP Per Capita",
      data: perCapitaDataValues,
      borderColor: "rgb(53, 162, 235)",
      backgroundColor: "rgba(53, 162, 235, 0.5)",
      tension: 0.3,
    },
  ];

  if (showAnnual && quarterlyData) {
    datasets.push({
      label: "Annual Average",
      data: annualAverages,
      borderColor: "rgb(255, 99, 132)",
      backgroundColor: "rgba(255, 99, 132, 0.5)",
      borderWidth: 2,
      tension: 0,
      borderDash: [5, 5],
    });
  }

  // Add target line if requested
  if (showTarget) {
    datasets.push({
      label: "Target",
      data: Array(labels.length).fill(targetValue),
      borderColor: "rgb(75, 192, 192)",
      backgroundColor: "rgba(75, 192, 192, 0.5)",
      borderWidth: 2,
      tension: 0,
      borderDash: [10, 5],
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
            // Different format for target value
            if (context.dataset.label === "Target") {
              return `${context.dataset.label}: $${context.parsed.y.toLocaleString()}`;
            }
            return `${context.dataset.label}: $${context.parsed.y.toLocaleString()} per person`;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: `${gdpMeasure} Per Capita (thousands $)`,
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
            return `$${value.toLocaleString()}`;
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
