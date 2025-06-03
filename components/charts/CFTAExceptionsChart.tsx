"use client";

import React from "react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js/auto";
import { Line } from "react-chartjs-2";
import cftaData from "@/metrics/cfib/cfta-expections.json";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
);

interface CFTAExceptionsChartProps {
  title?: string;
  showLegend?: boolean;
  height?: number;
}

// Various shades of grey for provinces
const greyColors = [
  "rgba(128, 128, 128, 0.6)",
  "rgba(160, 160, 160, 0.6)",
  "rgba(192, 192, 192, 0.6)",
  "rgba(105, 105, 105, 0.6)",
  "rgba(169, 169, 169, 0.6)",
  "rgba(112, 112, 112, 0.6)",
  "rgba(176, 176, 176, 0.6)",
  "rgba(144, 144, 144, 0.6)",
  "rgba(211, 211, 211, 0.6)",
  "rgba(119, 136, 153, 0.6)",
  "rgba(184, 184, 184, 0.6)",
  "rgba(96, 96, 96, 0.6)",
  "rgba(152, 152, 152, 0.6)",
];

const greyBorderColors = [
  "rgba(128, 128, 128, 1)",
  "rgba(160, 160, 160, 1)",
  "rgba(192, 192, 192, 1)",
  "rgba(105, 105, 105, 1)",
  "rgba(169, 169, 169, 1)",
  "rgba(112, 112, 112, 1)",
  "rgba(176, 176, 176, 1)",
  "rgba(144, 144, 144, 1)",
  "rgba(211, 211, 211, 1)",
  "rgba(119, 136, 153, 1)",
  "rgba(184, 184, 184, 1)",
  "rgba(96, 96, 96, 1)",
  "rgba(152, 152, 152, 1)",
];

// Blue color for federal government
const federalColor = "rgba(54, 162, 235, 0.8)";
const federalBorderColor = "rgba(54, 162, 235, 1)";

export default function CFTAExceptionsChart({
  title = "Canadian Free Trade Agreement Exceptions by Province/Territory",
  showLegend = true,
  height = 400,
}: CFTAExceptionsChartProps) {
  const cftaDataObj = cftaData as any;
  const data = cftaDataObj.data;

  // Extract years from the data (assuming all provinces have the same years)
  const years = data.Alberta.map((item: any) => item[0].toString());

  // Separate federal from provinces/territories
  const provinces = Object.keys(data).filter((key) => key !== "Federal");
  const federal = "Federal";

  // Sort provinces by their 2024 values (highest to lowest) for better stacking order
  const sortedProvinces = provinces.sort((a, b) => {
    const aValue2024 = data[a].find((item: any) => item[0] === 2024)?.[1] || 0;
    const bValue2024 = data[b].find((item: any) => item[0] === 2024)?.[1] || 0;
    return bValue2024 - aValue2024;
  });

  // Put federal at the bottom by adding it first
  const orderedEntities = [federal, ...sortedProvinces];

  const datasets = orderedEntities.map((entityName, index) => {
    const entityData = data[entityName];
    const values = years.map((year: string) => {
      const yearData = entityData.find(
        (item: any) => item[0].toString() === year,
      );
      return yearData ? yearData[1] : 0;
    });

    // Use blue for federal, grey for provinces
    const isFederal = entityName === "Federal";
    const backgroundColor = isFederal
      ? federalColor
      : greyColors[(index - 1) % greyColors.length];
    const borderColor = isFederal
      ? federalBorderColor
      : greyBorderColors[(index - 1) % greyBorderColors.length];

    return {
      label: entityName,
      data: values,
      backgroundColor: backgroundColor,
      borderColor: borderColor,
      borderWidth: 1,
      fill: index === 0 ? "origin" : "-1",
      tension: 0.1,
      pointRadius: 3,
      pointHoverRadius: 5,
    };
  });

  // Add target line dataset
  const targetDataset = {
    label: "Target (0 exceptions)",
    data: years.map(() => 0),
    borderColor: "rgba(255, 0, 0, 0.8)",
    backgroundColor: "rgba(255, 99, 132, 0.3)",
    borderWidth: 2,
    borderDash: [5, 5],
    fill: false,
    pointRadius: 0,
    tension: 0,
    stack: "target",
    order: 99,
  };

  const chartData = {
    labels: years,
    datasets: [...datasets, targetDataset],
  };

  const options: any = {
    responsive: true,
    maintainAspectRatio: false,
    interaction: {
      mode: "index" as const,
      intersect: false,
    },
    plugins: {
      legend: {
        display: showLegend,
        position: "right" as const,
        labels: {
          padding: 10,
          font: {
            size: 11,
          },
          usePointStyle: true,
          pointStyle: "rect",
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
        mode: "index" as const,
        intersect: false,
        callbacks: {
          title: function (context: any) {
            return `Year: ${context[0].label}`;
          },
          label: function (context: any) {
            const label = context.dataset.label || "";
            const value = context.parsed.y;
            const total = context.chart.data.datasets.reduce(
              (sum: number, dataset: any) => {
                return sum + dataset.data[context.dataIndex];
              },
              0,
            );
            return `${label}: ${value} exceptions (${((value / total) * 100).toFixed(1)}%)`;
          },
          footer: function (context: any) {
            const total = context.reduce(
              (sum: number, item: any) => sum + item.parsed.y,
              0,
            );
            return `Total: ${total} exceptions`;
          },
        },
      },
    },
    scales: {
      x: {
        stacked: true,
        title: {
          display: true,
          text: "Year",
          font: {
            size: 14,
          },
        },
        grid: {
          display: true,
          color: "rgba(0, 0, 0, 0.1)",
        },
      },
      y: {
        stacked: true,
        title: {
          display: true,
          text: "Number of Exceptions",
          font: {
            size: 14,
          },
        },
        beginAtZero: true,
        grid: {
          display: true,
          color: "rgba(0, 0, 0, 0.1)",
        },
        ticks: {
          callback: function (value: any) {
            return Math.round(value);
          },
        },
      },
    },
    elements: {
      line: {
        tension: 0.1,
      },
      point: {
        radius: 3,
        hoverRadius: 6,
      },
    },
    layout: {
      padding: {
        left: 10,
        right: 10,
        top: 10,
        bottom: 10,
      },
    },
  };

  return (
    <div
      style={{
        width: "100%",
        height: `${height}px`,
        position: "relative",
      }}
    >
      <Line data={chartData} options={options} />
    </div>
  );
}
