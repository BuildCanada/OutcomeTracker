"use client"
import { Badge } from "@/components/ui/badge"
import { useState } from "react"
import TaskModal from "@/components/task-modal"
import type { Task } from "@/lib/types"

interface TaskCardProps {
  task: Task
}

export default function TaskCard({ task }: TaskCardProps) {
  const { title, status, impact, lastUpdate } = task
  const [isModalOpen, setIsModalOpen] = useState(false)

  const statusColors = {
    "in-progress": "bg-[#fff3cd] text-[#856404] border-[#ffeeba]",
    kept: "bg-[#d4edda] text-[#155724] border-[#c3e6cb]",
    "not-started": "bg-[#e2e3e5] text-[#383d41] border-[#d6d8db]",
  }

  const impactColors = {
    high: "bg-[#f8d7da] text-[#721c24] border-[#f5c6cb]",
    medium: "bg-[#fff3cd] text-[#856404] border-[#ffeeba]",
    low: "bg-[#d1ecf1] text-[#0c5460] border-[#bee5eb]",
  }

  return (
    <>
      <div
        className="rounded-none border border-[#d3c7b9] p-4 cursor-pointer hover:bg-[#f8f2ea] transition-colors"
        onClick={() => setIsModalOpen(true)}
      >
        <h4 className="text-lg font-medium text-[#222222]">{title}</h4>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline" className={statusColors[status.id]}>
              {status.label}
            </Badge>

            <Badge variant="outline" className={impactColors[impact.level]}>
              {impact.label}
            </Badge>
          </div>

          <span className="text-sm text-[#555555]">{lastUpdate}</span>
        </div>
      </div>

      <TaskModal task={task} isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  )
}
