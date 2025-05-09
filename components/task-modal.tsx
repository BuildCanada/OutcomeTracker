"use client"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import { Badge } from "@/components/ui/badge"
import type { Task } from "@/lib/types"
import { CalendarIcon, FileTextIcon, UsersIcon } from "lucide-react"

interface TaskModalProps {
  task: Task
  isOpen: boolean
  onClose: () => void
}

export default function TaskModal({ task, isOpen, onClose }: TaskModalProps) {
  const { title, description, impact, status, lastUpdate, timeline, relatedBills } = task

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
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[90vh] overflow-y-auto bg-white p-0">
        <DialogHeader className="border-b border-[#d3c7b9] p-6">
          <div className="flex flex-wrap gap-2 mb-2">
            <Badge variant="outline" className={statusColors[status.id]}>
              {status.label}
            </Badge>
            <Badge variant="outline" className={impactColors[impact.level]}>
              {impact.label}
            </Badge>
          </div>
          <DialogTitle className="text-2xl font-bold text-[#222222]">{title}</DialogTitle>
          <DialogDescription className="text-[#555555] mt-2">{lastUpdate}</DialogDescription>
        </DialogHeader>

        <div className="p-6 space-y-8">
          {/* Promise Description */}
          <section>
            <h3 className="text-xl font-bold text-[#222222] mb-4">About This Promise</h3>
            <p className="text-[#333333] leading-relaxed">{description}</p>
          </section>

          {/* Impact on Canadians */}
          <section className="border-t border-[#d3c7b9] pt-8">
            <h3 className="text-xl font-bold text-[#222222] mb-4 flex items-center">
              <UsersIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
              Impact on Canadians
            </h3>
            <p className="text-[#333333] leading-relaxed">{impact.description}</p>
          </section>

          {/* Related Bills */}
          {relatedBills && relatedBills.length > 0 && (
            <section className="border-t border-[#d3c7b9] pt-8">
              <h3 className="text-xl font-bold text-[#222222] mb-4 flex items-center">
                <FileTextIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
                Related Bills
              </h3>
              <div className="space-y-4">
                {relatedBills.map((bill, index) => (
                  <div key={index} className="border border-[#d3c7b9] p-4">
                    <h4 className="font-bold text-[#222222]">{bill.name}</h4>
                    <p className="text-sm text-[#555555] mb-2">{bill.status}</p>
                    <p className="text-[#333333]">{bill.description}</p>
                  </div>
                ))}
              </div>
            </section>
          )}

          {/* Timeline */}
          <section className="border-t border-[#d3c7b9] pt-8">
            <h3 className="text-xl font-bold text-[#222222] mb-4 flex items-center">
              <CalendarIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
              Timeline
            </h3>
            <div className="relative border-l-2 border-[#d3c7b9] pl-6 space-y-6">
              {timeline.map((event, index) => (
                <div key={index} className="relative">
                  <div className="absolute -left-[29px] h-4 w-4 rounded-full bg-[#8b2332]"></div>
                  <div className="mb-1 text-sm font-medium text-[#8b2332]">{event.date}</div>
                  <h4 className="font-bold text-[#222222]">{event.title}</h4>
                  <p className="text-[#333333]">{event.description}</p>
                </div>
              ))}
            </div>
          </section>
        </div>
      </DialogContent>
    </Dialog>
  )
}
