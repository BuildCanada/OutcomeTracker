import { Badge } from "@/components/ui/badge"

interface TimelineEvent {
  id: number
  title: string
  description: string
  date: string
  status: string
}

interface TimelineProps {
  events: TimelineEvent[]
}

export default function Timeline({ events }: TimelineProps) {
  if (events.length === 0) {
    return <div className="text-center py-8 text-muted-foreground">No actions have been taken on this promise yet.</div>
  }

  // Format date to be more readable
  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return date.toLocaleDateString("en-CA", {
      year: "numeric",
      month: "long",
      day: "numeric",
    })
  }

  // Status badges with appropriate colors
  const statusBadges = {
    "Not Started": <Badge variant="outline">Not Started</Badge>,
    "In Progress": <Badge className="bg-status-inProgress text-white">In Progress</Badge>,
    "Partially Complete": <Badge className="bg-status-partial text-white">Partially Complete</Badge>,
    Complete: <Badge className="bg-status-complete text-white">Complete</Badge>,
    Completed: <Badge className="bg-status-notStarted text-white">Completed</Badge>,
  }

  return (
    <div className="relative">
      <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-canada-red/20" />

      <div className="space-y-8">
        {events.map((event, index) => (
          <div key={event.id} className="relative pl-10">
            <div className="absolute left-0 top-1 w-8 h-8 rounded-full bg-canada-cream border-2 border-canada-red flex items-center justify-center">
              <div className="w-4 h-4 rounded-full bg-canada-red" />
            </div>

            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-medium text-canada-red">{event.title}</h3>
                {statusBadges[event.status]}
              </div>
              <p className="text-sm text-muted-foreground">{formatDate(event.date)}</p>
              <p className="text-sm">{event.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
