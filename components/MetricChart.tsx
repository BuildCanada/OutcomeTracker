"use client"
import { Line } from "react-chartjs-2"
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
} from "chart.js"

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend)

interface MetricChartProps {
  title: string
  data: number[]
  goal: number
}

export default function MetricChart({ title, data, goal }: MetricChartProps) {
  const months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
  const labels = months.slice(0, data.length)

  const chartData = {
    labels,
    datasets: [
      {
        label: "Actual",
        data: data,
        borderColor: "rgb(34, 34, 34)",
        backgroundColor: "rgba(34, 34, 34, 0.5)",
        tension: 0.3,
      },
      {
        label: "Goal",
        data: Array(data.length).fill(goal),
        borderColor: "rgb(139, 35, 50)",
        backgroundColor: "rgba(139, 35, 50, 0.5)",
        borderDash: [5, 5],
      },
    ],
  }

  const options = {
    responsive: true,
    plugins: {
      legend: {
        position: "top" as const,
      },
      title: {
        display: false,
      },
    },
    scales: {
      y: {
        beginAtZero: false,
      },
    },
  }

  return (
    <div>
      <h4 className="mb-2 font-medium">{title}</h4>
      <Line data={chartData} options={options} />
    </div>
  )
} 