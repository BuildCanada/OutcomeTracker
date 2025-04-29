import Link from "next/link"
import { notFound } from "next/navigation"
import { ChevronRight } from "lucide-react"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"

// Helper function to get promise data
async function getPromiseData() {
  // In a real app, this would fetch from an API or database
  const promises = await import("@/data/promises.json").then((module) => module.default.promises)
  return promises
}

// Helper to group promises by subsection
function groupPromisesBySubsection(promises) {
  return promises.reduce((acc, promise) => {
    if (!acc[promise.subsection]) {
      acc[promise.subsection] = []
    }

    acc[promise.subsection].push(promise)

    return acc
  }, {})
}

export default async function SectionPage({ params }) {
  const { section } = params
  const sectionName = section.charAt(0).toUpperCase() + section.slice(1)

  const promises = await getPromiseData()
  const sectionPromises = promises.filter((promise) => promise.section.toLowerCase() === section.toLowerCase())

  if (sectionPromises.length === 0) {
    notFound()
  }

  const subsectionGroups = groupPromisesBySubsection(sectionPromises)

  // Status badges with appropriate colors
  const statusBadges = {
    "Not Started": <Badge variant="outline">Not Started</Badge>,
    "In Progress": <Badge className="bg-blue-500">In Progress</Badge>,
    "Partially Complete": <Badge className="bg-yellow-500">Partially Complete</Badge>,
    Complete: <Badge className="bg-green-500">Complete</Badge>,
  }

  return (
    <main className="container mx-auto py-8 px-4">
      <div className="mb-8">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-2">
          <Link href="/" className="hover:underline">
            Home
          </Link>
          <ChevronRight className="h-4 w-4" />
          <span>{sectionName}</span>
        </div>
        <h1 className="text-4xl font-bold">{sectionName}</h1>
        <p className="text-xl text-muted-foreground mt-2">
          Tracking progress on {sectionPromises.length} promises across {Object.keys(subsectionGroups).length}{" "}
          subsections
        </p>
      </div>

      <div className="space-y-10">
        {Object.entries(subsectionGroups).map(([subsection, promises]) => (
          <div key={subsection} className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-2xl font-bold">{subsection}</h2>
              <Link href={`/sections/${section}/${encodeURIComponent(subsection.toLowerCase())}`}>
                <Button variant="outline">View Timeline</Button>
              </Link>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {promises.map((promise) => {
                // Generate a random status for demo purposes
                const statuses = ["Not Started", "In Progress", "Partially Complete", "Complete"]
                const randomStatus = statuses[Math.floor(Math.random() * statuses.length)]

                return (
                  <Card key={promise.source_ref} className="overflow-hidden">
                    <CardContent className="p-6">
                      <div className="flex flex-col gap-2">
                        <div className="flex justify-between items-start">
                          <p className="font-medium flex-1">{promise.promise_text}</p>
                          <div className="ml-4">{statusBadges[randomStatus]}</div>
                        </div>
                        <div className="text-sm text-muted-foreground">
                          Source: Page {promise.source_page}, Ref {promise.source_ref}
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                )
              })}
            </div>
          </div>
        ))}
      </div>
    </main>
  )
}
