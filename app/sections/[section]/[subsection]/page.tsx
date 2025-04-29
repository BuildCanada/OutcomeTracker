import Link from "next/link"
import { notFound } from "next/navigation"
import { ChevronRight } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import Timeline from "@/components/timeline"

// Helper function to get promise data
async function getPromiseData() {
  // In a real app, this would fetch from an API or database
  const promises = await import("@/data/promises.json").then((module) => module.default.promises)
  return promises
}

// Generate mock timeline events for a promise
function generateMockTimelineEvents(promise) {
  const events = []
  const statuses = ["Not Started", "In Progress", "Partially Complete", "Complete"]
  const currentStatus = statuses[Math.floor(Math.random() * statuses.length)]

  // Generate 0-4 random events based on the current status
  const eventCount = Math.floor(Math.random() * 5)

  const eventTypes = [
    "Legislation tabled",
    "First reading passed",
    "Committee review",
    "Second reading passed",
    "Royal assent",
    "Regulation created",
    "Regulation amended",
    "Funding allocated",
    "Program launched",
    "Implementation begun",
    "Progress report published",
  ]

  const startDate = new Date(2023, 0, 1)
  const endDate = new Date()

  for (let i = 0; i < eventCount; i++) {
    const randomEventType = eventTypes[Math.floor(Math.random() * eventTypes.length)]
    const randomDate = new Date(startDate.getTime() + Math.random() * (endDate.getTime() - startDate.getTime()))

    events.push({
      id: i,
      title: randomEventType,
      description: `Action taken related to: "${promise.promise_text.substring(0, 100)}..."`,
      date: randomDate.toISOString().split("T")[0],
      status: i === eventCount - 1 ? currentStatus : "Completed",
    })
  }

  // Sort events by date
  return events.sort((a, b) => new Date(a.date) - new Date(b.date))
}

export default async function SubsectionPage({ params }) {
  const { section, subsection } = params
  const sectionName = section.charAt(0).toUpperCase() + section.slice(1)
  const subsectionName = decodeURIComponent(subsection)
    .split("-")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ")

  const promises = await getPromiseData()
  const subsectionPromises = promises.filter(
    (promise) =>
      promise.section.toLowerCase() === section.toLowerCase() &&
      promise.subsection.toLowerCase() === decodeURIComponent(subsection).toLowerCase(),
  )

  if (subsectionPromises.length === 0) {
    notFound()
  }

  // Status badges with appropriate colors
  const statusBadges = {
    "Not Started": <Badge variant="outline">Not Started</Badge>,
    "In Progress": <Badge className="bg-status-inProgress text-white">In Progress</Badge>,
    "Partially Complete": <Badge className="bg-status-partial text-white">Partially Complete</Badge>,
    Complete: <Badge className="bg-status-complete text-white">Complete</Badge>,
  }

  return (
    <main className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <Link href="/" className="hover:underline text-canada-red">
            Home
          </Link>
          <ChevronRight className="h-4 w-4" />
          <Link href={`/sections/${section}`} className="hover:underline text-canada-red">
            {sectionName}
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span>{subsectionName}</span>
        </div>
        <h1 className="text-4xl font-bold">{subsectionName}</h1>
        <p className="text-xl text-muted-foreground mt-2">
          Timeline of actions for {subsectionPromises.length} promises
        </p>
      </div>

      <div className="space-y-12">
        {subsectionPromises.map((promise) => {
          // Generate mock timeline events
          const timelineEvents = generateMockTimelineEvents(promise)

          // Determine current status based on the last event
          const currentStatus =
            timelineEvents.length > 0 ? timelineEvents[timelineEvents.length - 1].status : "Not Started"

          return (
            <div key={promise.source_ref} className="space-y-4">
              <Card className="overflow-hidden border-canada-red">
                <CardHeader className="bg-canada-cream border-b border-canada-red">
                  <div className="flex justify-between items-start">
                    <CardTitle className="text-xl text-canada-red">{promise.promise_text}</CardTitle>
                    <div className="ml-4">{statusBadges[currentStatus]}</div>
                  </div>
                  <div className="text-sm text-muted-foreground mt-2">
                    Source: Page {promise.source_page}, Ref {promise.source_ref}
                  </div>
                </CardHeader>
                <CardContent className="p-6">
                  <Timeline events={timelineEvents} />
                </CardContent>
              </Card>
            </div>
          )
        })}
      </div>
    </main>
  )
}
