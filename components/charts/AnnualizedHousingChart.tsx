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
import { calculateMovingAverage } from "@/components/charts/utils/trendCalculator";
import { LineChartDataset } from "@/components/charts/types";
import useSWR from "swr";

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
interface AnnualizedHousingChartProps {
  title?: string;
  category?: string;
  startYear?: number;
  endYear?: number;
  showTarget?: boolean;
  targetValue?: number;
  showTrend?: boolean;
}

export default function AnnualizedHousingChart({
  title = "Annualized Housing Starts",
  category = "Total units",
  startYear = 2010,
  endYear = 2029,
  showTarget = false,
  targetValue = 300000,
  showTrend = true,
}: AnnualizedHousingChartProps) {
  const fetcher = (url: string) => fetch(url).then((res) => res.json());

  const {
    data: housingData,
    error,
    isLoading,
  } = useSWR(
    "/tracker/api/v1/statcan_datasets/housing-starts-monthly",
    fetcher,
  );

  if (isLoading) {
    return <div>Loading annualized housing data...</div>;
  }

  if (error || !housingData) {
    return <div>Error loading annualized housing data</div>;
  }

  // Transform the new API data format
  const apiData = housingData.current_data || [];

  // Filter data by housing type and year range
  const filteredData = apiData
    .filter((item: any) => {
      const year = parseInt(item.REF_DATE.split("-")[0]);
      return (
        year >= startYear &&
        year <= endYear &&
        item["Type of unit"] === category &&
        item.VALUE != null &&
        !isNaN(Number(item.VALUE))
      );
    })
    .map((item: any) => [item.REF_DATE, Number(item.VALUE)])
    .sort((a: any, b: any) => a[0].localeCompare(b[0]));

  // Early return if we don't have enough data
  if (filteredData.length < 12) {
    return (
      <div>
        Not enough data for annualized calculation (need at least 12 months)
      </div>
    );
  }

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
          const value = array[index - i][1];
          if (!isNaN(value) && value != null) {
            sum += value;
          }
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
  const datasets: LineChartDataset[] = [
    {
      label: `Annualized ${category}`,
      data: annualizedValues,
      ...getPrimaryLineStyling(),
    },
  ];

  // Add moving average line if requested
  if (showTrend) {
    const period = 12; // 12-month moving average
    const trendValues = calculateMovingAverage(annualizedValues, period);
    datasets.push({
      label: "12-Month Moving Average",
      data: trendValues,
      ...getTrendLineStyling(),
    });
  }

  // Add target line if requested
  if (showTarget && targetValue) {
    datasets.push({
      type: "line",
      label: "Target (500,000)",
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
      <Line data={chartData} options={options} />
    </div>
  );
}
