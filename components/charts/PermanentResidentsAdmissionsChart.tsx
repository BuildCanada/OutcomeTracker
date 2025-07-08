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
import permanentResidentsAdmissionsData from "@/metrics/statscan/components-population-growth.json";
import populationData from "@/metrics/statscan/population.json";
import { getPrimaryLineStyling, getTargetLineStyling } from "@/components/charts/utils/styling";
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

interface PermanentResidentsAdmissionsChartProps {
  title?: string;
  startYear?: number;
  endYear?: number;
  quarterlyData?: boolean;
  showTarget?: boolean;
  targetValue?: number;
}

export default function PermanentResidentsAdmissionsChart({
  title = "Permanent Residents Admissions (% of Population)",
  startYear = 2021,
  endYear = new Date().getFullYear(),
  quarterlyData = true,
  showTarget = true,
  targetValue = 1.0,
}: PermanentResidentsAdmissionsChartProps) {
  // Get data sources
  const prAdmissionsDataObj = permanentResidentsAdmissionsData as any;
  const populationDataObj = populationData as any;
  const immigrantsData = prAdmissionsDataObj.data["Immigrants"] || [];
  const totalPopulation = populationDataObj.data["Canada"] || [];

  // Build a lookup for total population data
  const populationLookup: Record<string, number> = {};
  // @ts-ignore
  totalPopulation.forEach(function (item: any) {
    populationLookup[item[0]] = item[1];
  });

  // Calculate annualized immigrants (sum of last 4 quarters) and percentage
  const annualizedData: Array<{ date: string, value: number }> = [];

  // Group immigrants data by year-quarter for easier processing
  const immigrantsByQuarter: Record<string, number> = {};
  // @ts-ignore
  immigrantsData.forEach(function (item: any) {
    immigrantsByQuarter[item[0]] = item[1];
  });

  // Calculate annualized values (sum of 4 quarters)
  const quarters = Object.keys(immigrantsByQuarter).sort();

  for (let i = 3; i < quarters.length; i++) {
    const currentQuarter = quarters[i];
    const [year, month] = currentQuarter.split("-");
    const currentMonth = parseInt(month);

    // For each quarter, we need the current quarter plus the previous 3 quarters
    let q1, q2, q3, q4;

    if (currentMonth === 1) {
      // Q1: current Q1 + previous year Q4, Q3, Q2
      q1 = immigrantsByQuarter[`${year}-01`];
      q2 = immigrantsByQuarter[`${parseInt(year) - 1}-10`];
      q3 = immigrantsByQuarter[`${parseInt(year) - 1}-07`];
      q4 = immigrantsByQuarter[`${parseInt(year) - 1}-04`];
    } else if (currentMonth === 4) {
      // Q2: current Q2 + current Q1 + previous year Q4, Q3
      q1 = immigrantsByQuarter[`${year}-04`];
      q2 = immigrantsByQuarter[`${year}-01`];
      q3 = immigrantsByQuarter[`${parseInt(year) - 1}-10`];
      q4 = immigrantsByQuarter[`${parseInt(year) - 1}-07`];
    } else if (currentMonth === 7) {
      // Q3: current Q3, Q2, Q1 + previous year Q4
      q1 = immigrantsByQuarter[`${year}-07`];
      q2 = immigrantsByQuarter[`${year}-04`];
      q3 = immigrantsByQuarter[`${year}-01`];
      q4 = immigrantsByQuarter[`${parseInt(year) - 1}-10`];
    } else if (currentMonth === 10) {
      // Q4: current Q4, Q3, Q2, Q1
      q1 = immigrantsByQuarter[`${year}-10`];
      q2 = immigrantsByQuarter[`${year}-07`];
      q3 = immigrantsByQuarter[`${year}-04`];
      q4 = immigrantsByQuarter[`${year}-01`];
    }

    // Only calculate if we have all 4 quarters
    if (q1 && q2 && q3 && q4) {
      const annualizedImmigrants = q1 + q2 + q3 + q4;
      const populationValue = populationLookup[currentQuarter];

      if (populationValue) {
        const percentage = (annualizedImmigrants / populationValue) * 100;
        annualizedData.push({
          date: currentQuarter,
          value: percentage,
        });
      }
    }
  }

  // Filter data by year range
  // @ts-ignore
  const filteredData = annualizedData.filter(function (item) {
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

  const datasets: LineChartDataset[] = [
    {
      label: "PR Admissions %",
      data: chartValues,
      ...getPrimaryLineStyling(),
    },
  ];

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
          text: "Permanent Residents (% of Population)",
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
