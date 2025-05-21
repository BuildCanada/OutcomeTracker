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

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
);

interface BalanceSheetsChartProps {
  title?: string;
  category?: string;
  startYear?: number;
  endYear?: number;
  showComparison?: boolean;
  comparisonCategory?: string;
}

export default function BalanceSheetsChart({
  title = "Balance Sheet Metrics",
  category = "Revenue",
  startYear = 2010,
  endYear = 2023,
  showComparison = false,
  comparisonCategory = "Expense",
}: BalanceSheetsChartProps) {
  // Get data for selected category
  const categoryData = balanceSheetsData.data[category] || [];
  
  // Filter data by year range
  const filteredData = categoryData.filter(([dateStr]) => {
    const year = parseInt(dateStr.split("-")[0]);
    return year >= startYear && year <= endYear;
  });

  // Format the data for the chart
  const labels = filteredData.map(([dateStr]) => {
    const [year, month] = dateStr.split("-");
    return `${year}-${month}`;
  });

  const categoryValues = filteredData.map(([_, value]) => value);

  const datasets = [
    {
      label: category,
      data: categoryValues,
      borderColor: "rgb(34, 34, 34)",
      backgroundColor: "rgba(34, 34, 34, 0.5)",
      tension: 0.3,
    },
  ];

  if (showComparison && comparisonCategory) {
    // Get comparison data
    const comparisonData = balanceSheetsData.data[comparisonCategory] || [];
    
    // Filter comparison data by year range
    const filteredComparisonData = comparisonData.filter(([dateStr]) => {
      const year = parseInt(dateStr.split("-")[0]);
      return year >= startYear && year <= endYear;
    });

    // Only add comparison if there's data available
    if (filteredComparisonData.length > 0) {
      const comparisonValues = filteredComparisonData.map(([_, value]) => value);
      
      datasets.push({
        label: comparisonCategory,
        data: comparisonValues,
        borderColor: "rgb(53, 162, 235)",
        backgroundColor: "rgba(53, 162, 235, 0.5)",
        tension: 0.3,
      });
    }
  }

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
          weight: 'bold',
        },
        padding: {
          top: 10,
          bottom: 20,
        },
      },
      tooltip: {
        mode: 'index' as const,
        intersect: false,
        callbacks: {
          label: function(context: any) {
            let label = context.dataset.label || '';
            if (label) {
              label += ': ';
            }
            if (context.parsed.y !== null) {
              label += new Intl.NumberFormat('en-CA', {
                style: 'currency',
                currency: 'CAD',
                notation: 'compact',
                compactDisplay: 'short',
                maximumFractionDigits: 1,
              }).format(context.parsed.y);
            }
            return label;
          }
        }
      },
    },
    scales: {
      y: {
        beginAtZero: false,
        title: {
          display: true,
          text: "Amount (CAD)",
          font: {
            size: 14,
          },
          padding: {
            bottom: 10,
          },
        },
        ticks: {
          padding: 8,
          callback: function(value: number) {
            return new Intl.NumberFormat('en-CA', {
              style: 'currency',
              currency: 'CAD',
              notation: 'compact',
              compactDisplay: 'short',
              maximumFractionDigits: 1,
            }).format(value);
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
          callback: function(value: any, index: number) {
            // Show fewer labels on x-axis for readability
            const label = this.getLabelForValue(value);
            return index % 4 === 0 ? label : '';
          }
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
      mode: 'index' as const,
      intersect: false,
    },
  };

  return (
    <div style={{ width: '100%', height: '100%', minHeight: '400px', position: 'relative' }}>
      <Line data={chartData} options={options} />
    </div>
  );
}