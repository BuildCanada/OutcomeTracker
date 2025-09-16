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
import { calculatePerCapita } from "./utils/PerCapitaCalculator";
import useSWR from "swr";
import {
  getPrimaryLineStyling,
  getTargetLineStyling,
  getTrendLineStyling,
} from "./utils/styling";
import { calculateLinearTrend } from "./utils/trendCalculator";
import { LineChartDataset } from "@/components/charts/types";

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
  showTrend?: boolean;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function GDPPerCapitaChart({
  title = "GDP Per Capita",
  gdpMeasure = "Gross domestic product at market prices",
  startYear = 1961,
  endYear = 2099,
  quarterlyData = true,
  showAnnual = false,
  showTarget = false,
  targetValue = 50,
  showTrend = true,
}: GDPPerCapitaChartProps) {
  const {
    data: gdpData,
    error: gdpError,
    isLoading: gdpLoading,
  } = useSWR("/tracker/api/v1/statcan_datasets/gdp-quarterly", fetcher);

  const {
    data: populationData,
    error: populationError,
    isLoading: populationLoading,
  } = useSWR(
    "/tracker/api/v1/statcan_datasets/population-estimates-quarterly",
    fetcher,
  );

  if (gdpLoading || populationLoading) {
    return <div>Loading GDP per capita data...</div>;
  }

  if (gdpError || populationError || !gdpData || !populationData) {
    return <div>Error loading GDP per capita data</div>;
  }

  // Transform the new API data format
  const gdpApiData = gdpData.current_data || [];
  const populationApiData = populationData.current_data || [];

  // Filter GDP data by measure
  const gdpMetricData = gdpApiData
    .filter((item: any) => {
      return item["Estimates"] === gdpMeasure;
    })
    .map((item: any) => [item.REF_DATE, item.VALUE])
    .sort((a: any, b: any) => a[0].localeCompare(b[0]));

  // Filter population data for Canada
  const populationCanadaData = populationApiData
    .filter((item: any) => {
      return item["GEO"] === "Canada";
    })
    .map((item: any) => [item.REF_DATE, item.VALUE])
    .sort((a: any, b: any) => a[0].localeCompare(b[0]));

  // Calculate per capita values (in thousands of dollars)
  const perCapitaValues = calculatePerCapita(
    gdpMetricData,
    populationCanadaData,
    1000000,
  );

  // Filter data by year range
  const filteredData = perCapitaValues.filter((dataPoint) => {
    const year = parseInt(dataPoint.date.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Calculate year-over-year growth rates
  const growthRates: (number | null)[] = filteredData.map(
    (dataPoint, index) => {
      if (index < 4) return null; // Need at least 4 quarters for YoY comparison

      const currentValue = dataPoint.value;
      const previousYearValue = filteredData[index - 4].value;

      if (
        previousYearValue === 0 ||
        previousYearValue === null ||
        currentValue === null
      )
        return null;

      return ((currentValue - previousYearValue) / previousYearValue) * 100;
    },
  );

  // Format dates for display
  let labels = filteredData.map((dataPoint) => {
    if (quarterlyData) {
      const [year, month] = dataPoint.date.split("-");
      // Convert month number to quarter (01->Q1, 04->Q2, 07->Q3, 10->Q4)
      const quarter = Math.floor(parseInt(month) / 3) + 1;
      return `${year} Q${quarter}`;
    } else {
      return dataPoint.date.split("-")[0]; // Just show year
    }
  });

  // Align labels and data arrays to start from first valid growth rate (index 4)
  labels = labels.slice(4);
  const alignedGrowthRates = growthRates.slice(4);

  // Calculate annual average if requested
  let annualAverages: number[] = [];
  if (showAnnual && quarterlyData) {
    // Group data by year to calculate averages
    const yearlyGroups: Record<string, number[]> = {};

    alignedGrowthRates.forEach((growthRate, index) => {
      if (growthRate !== null) {
        const year = labels[index].split(" ")[0]; // Extract year from "YYYY QX" format
        if (!yearlyGroups[year]) yearlyGroups[year] = [];
        yearlyGroups[year].push(growthRate);
      }
    });

    // For each quarter datapoint, find its year's average
    annualAverages = alignedGrowthRates.map((growthRate, index) => {
      if (growthRate === null) return 0;
      const year = labels[index].split(" ")[0];
      const yearValues = yearlyGroups[year] || [];
      if (yearValues.length === 0) return 0;
      return yearValues.reduce((sum, val) => sum + val, 0) / yearValues.length;
    });
  }

  const datasets: LineChartDataset[] = [
    {
      label: "YoY Growth Rate (%)",
      data: alignedGrowthRates,
      ...getPrimaryLineStyling(),
    },
  ];

  if (showAnnual && quarterlyData) {
    datasets.push({
      label: "Annual Average",
      data: annualAverages,
      ...getTargetLineStyling(),
    });
  }

  // Calculate linear trend if requested
  if (showTrend && alignedGrowthRates.length > 1) {
    const trendValues = calculateLinearTrend(alignedGrowthRates as number[]);
    datasets.push({
      label: "Trend",
      data: trendValues,
      ...getTrendLineStyling(),
    });
  }

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      label: `Target (${targetValue}%)`,
      data: Array(labels.length).fill(targetValue),
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
            if (
              context.dataset.label &&
              context.dataset.label.includes("Target")
            ) {
              return `${context.dataset.label}: ${context.parsed.y.toFixed(1)}%`;
            }
            if (
              context.dataset.label &&
              context.dataset.label.includes("Growth Rate")
            ) {
              if (context.parsed.y === null) return null;
              return `${context.dataset.label}: ${context.parsed.y.toFixed(2)}%`;
            }
            return null;
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: "Growth Rate (%)",
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
    interaction: {
      mode: "index" as const,
      intersect: false,
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
