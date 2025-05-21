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
import balanceSheetsData from "@/metrics/statscan/balance-sheets.json";

// Type definition for the balance sheet data
type BalanceSheetDataEntry = [string, number];
interface BalanceSheetData {
  data: Record<string, BalanceSheetDataEntry[]>;
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

interface BalanceSheetChartProps {
  title?: string;
  categories?: string[];
  startDate?: string;
  endDate?: string;
  showThousands?: boolean;
}

export default function BalanceSheetChart({
  title = "Government Balance Sheet",
  categories = ["Revenue", "Expense"],
  startDate = "2010-01",
  endDate = "2023-12",
  showThousands = true,
}: BalanceSheetChartProps) {
  // Get data for selected categories
  const allData = (balanceSheetsData as unknown as BalanceSheetData).data;
  
  // Filter data by date range
  const filteredData: Record<string, [string, number][]> = {};
  
  categories.forEach((category) => {
    if (allData[category]) {
      filteredData[category] = allData[category].filter((entry: BalanceSheetDataEntry) => {
        const [dateStr] = entry;
        return dateStr >= startDate && dateStr <= endDate;
      });
    }
  });

  // Find common dates across all selected categories
  let commonDates = Object.values(filteredData)[0]?.map(([date]) => date) || [];
  
  Object.values(filteredData).forEach((categoryData) => {
    const categoryDates = categoryData.map(([date]) => date);
    commonDates = commonDates.filter((date) => categoryDates.includes(date));
  });

  // Format the data for the chart
  const labels = commonDates;

  const datasets = categories.map((category, index) => {
    const colors = [
      { border: "rgb(34, 34, 34)", background: "rgba(34, 34, 34, 0.5)" },
      { border: "rgb(139, 35, 50)", background: "rgba(139, 35, 50, 0.5)" },
      { border: "rgb(0, 123, 255)", background: "rgba(0, 123, 255, 0.5)" },
      { border: "rgb(40, 167, 69)", background: "rgba(40, 167, 69, 0.5)" },
      { border: "rgb(255, 193, 7)", background: "rgba(255, 193, 7, 0.5)" },
    ];
    
    const colorIndex = index % colors.length;
    
    const values = commonDates.map((date) => {
      const entry = filteredData[category]?.find(([d]) => d === date);
      let value = entry ? entry[1] : 0;
      if (showThousands) {
        value = value / 1000;
      }
      return value;
    });
    
    return {
      label: category,
      data: values,
      borderColor: colors[colorIndex].border,
      backgroundColor: colors[colorIndex].background,
      tension: 0.3,
    };
  });

  const chartData = {
    labels,
    datasets,
  };

  const options = {
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
          weight: 'bold' as const,
        },
        padding: {
          top: 10,
          bottom: 20,
        },
      },
      tooltip: {
        callbacks: {
          label: function(context: any) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += showThousands 
                ? `$${context.parsed.y.toFixed(0)}k` 
                : `$${context.parsed.y.toFixed(0)}`;
            }
            return label;
          }
        }
      }
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: showThousands ? "Value ($ thousands)" : "Value ($)",
          font: {
            size: 14,
          },
          padding: {
            bottom: 10,
          },
        },
        ticks: {
          padding: 8,
          callback: function(this: any, value: any) {
            return showThousands 
              ? `$${Number(value).toFixed(0)}k` 
              : `$${Number(value).toFixed(0)}`;
          }
        },
      },
      x: {
        title: {
          display: true,
          text: "Year-Quarter",
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
    <div style={{ width: '100%', height: '100%', minHeight: '400px', position: 'relative' }}>
      <Line data={chartData} options={options as any} />
    </div>
  );
}