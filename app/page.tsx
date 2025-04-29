import Link from "next/link"
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card"
import { ArrowRight } from "lucide-react"

// Helper function to get promise data
async function getPromiseData() {
  // In a real app, this would fetch from an API or database
  // For this demo, we'll use the mock data
  const promises = await import("@/data/promises.json").then((module) => module.default.promises)
  return promises
}

// Helper to group promises by section and subsection
function groupPromisesBySection(promises) {
  return promises.reduce((acc, promise) => {
    if (!acc[promise.section]) {
      acc[promise.section] = {
        promises: [],
        subsections: {},
      }
    }

    acc[promise.section].promises.push(promise)

    if (!acc[promise.section].subsections[promise.subsection]) {
      acc[promise.section].subsections[promise.subsection] = []
    }

    acc[promise.section].subsections[promise.subsection].push(promise)

    return acc
  }, {})
}

// Helper to calculate progress for promises
function calculateProgress(promises) {
  // In a real app, this would come from a database
  // For this demo, we'll generate random statuses
  const statuses = ["Not Started", "In Progress", "Partially Complete", "Complete"]
  const statusCounts = {
    "Not Started": 0,
    "In Progress": 0,
    "Partially Complete": 0,
    Complete: 0,
  }

  promises.forEach((promise) => {
    // Assign a random status for demo purposes
    const randomStatus = statuses[Math.floor(Math.random() * statuses.length)]
    statusCounts[randomStatus]++
  })

  return statusCounts
}

export default async function Home() {
  const promises = await getPromiseData()
  const sectionGroups = groupPromisesBySection(promises)

  return (
    <main className="container mx-auto py-8 px-4">
      <div className="mb-8 text-center">
        <h1 className="text-4xl font-bold mb-2">Canada's Promise Tracker</h1>
        <p className="text-xl text-muted-foreground">
          Tracking the progress of the Canadian federal government's promises
        </p>
      </div>

      <div className="space-y-12">
        {Object.entries(sectionGroups).map(([section, data]) => {
          const { promises, subsections } = data
          const sectionProgress = calculateProgress(promises)
          const totalPromises = promises.length
          const completePercentage = Math.round((sectionProgress["Complete"] / totalPromises) * 100)

          return (
            <div key={section} className="space-y-6">
              <Card className="overflow-hidden border-canada-red">
                <CardHeader className="section-header">
                  <div className="flex justify-between items-center">
                    <div>
                      <CardTitle className="text-2xl">{section}</CardTitle>
                      <CardDescription className="text-white opacity-90">
                        {Object.keys(subsections).length} subsections, {totalPromises} promises
                      </CardDescription>
                    </div>
                    <div className="text-right">
                      <div className="text-xl font-bold">{completePercentage}% Complete</div>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="pt-6">
                  <div className="space-y-4">
                    <div className="progress-bar-container">
                      <div className="progress-bar-complete" style={{ width: `${completePercentage}%` }} />
                      <div
                        className="progress-bar-partial"
                        style={{
                          width: `${Math.round((sectionProgress["Partially Complete"] / totalPromises) * 100)}%`,
                          left: `${completePercentage}%`,
                        }}
                      />
                      <div
                        className="progress-bar-inProgress"
                        style={{
                          width: `${Math.round((sectionProgress["In Progress"] / totalPromises) * 100)}%`,
                          left: `${completePercentage + Math.round((sectionProgress["Partially Complete"] / totalPromises) * 100)}%`,
                        }}
                      />
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
                      <div className="flex items-center gap-2">
                        <div className="status-indicator status-complete"></div>
                        <span>Complete: {sectionProgress["Complete"]}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="status-indicator status-partial"></div>
                        <span>Partial: {sectionProgress["Partially Complete"]}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="status-indicator status-inProgress"></div>
                        <span>In Progress: {sectionProgress["In Progress"]}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="status-indicator status-notStarted"></div>
                        <span>Not Started: {sectionProgress["Not Started"]}</span>
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Subsections */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {Object.entries(subsections).map(([subsection, subsectionPromises]) => {
                  const subsectionProgress = calculateProgress(subsectionPromises)
                  const totalSubsectionPromises = subsectionPromises.length
                  const subsectionCompletePercentage = Math.round(
                    (subsectionProgress["Complete"] / totalSubsectionPromises) * 100,
                  )

                  return (
                    <Card key={`${section}-${subsection}`} className="overflow-hidden border-canada-navy">
                      <CardHeader className="subsection-header">
                        <CardTitle className="text-lg">{subsection}</CardTitle>
                        <CardDescription className="text-white opacity-90">
                          {totalSubsectionPromises} promises
                        </CardDescription>
                      </CardHeader>
                      <CardContent className="pt-4">
                        <div className="space-y-3">
                          <div className="flex justify-between text-sm">
                            <span>Progress</span>
                            <span>{subsectionCompletePercentage}% Complete</span>
                          </div>
                          <div className="progress-bar-container">
                            <div
                              className="progress-bar-complete"
                              style={{ width: `${subsectionCompletePercentage}%` }}
                            />
                            <div
                              className="progress-bar-partial"
                              style={{
                                width: `${Math.round((subsectionProgress["Partially Complete"] / totalSubsectionPromises) * 100)}%`,
                                left: `${subsectionCompletePercentage}%`,
                              }}
                            />
                            <div
                              className="progress-bar-inProgress"
                              style={{
                                width: `${Math.round((subsectionProgress["In Progress"] / totalSubsectionPromises) * 100)}%`,
                                left: `${subsectionCompletePercentage + Math.round((subsectionProgress["Partially Complete"] / totalSubsectionPromises) * 100)}%`,
                              }}
                            />
                          </div>

                          <div className="grid grid-cols-2 gap-1 text-xs">
                            <div className="flex items-center gap-1">
                              <div className="status-indicator status-complete w-2 h-2"></div>
                              <span>Complete: {subsectionProgress["Complete"]}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <div className="status-indicator status-partial w-2 h-2"></div>
                              <span>Partial: {subsectionProgress["Partially Complete"]}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <div className="status-indicator status-inProgress w-2 h-2"></div>
                              <span>In Progress: {subsectionProgress["In Progress"]}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <div className="status-indicator status-notStarted w-2 h-2"></div>
                              <span>Not Started: {subsectionProgress["Not Started"]}</span>
                            </div>
                          </div>
                        </div>
                      </CardContent>
                      <CardFooter className="bg-muted flex justify-end py-2">
                        <Link
                          href={`/sections/${section.toLowerCase()}/${encodeURIComponent(subsection.toLowerCase())}`}
                          className="text-sm font-medium text-canada-red hover:underline flex items-center"
                        >
                          View Timeline <ArrowRight className="ml-1 h-4 w-4" />
                        </Link>
                      </CardFooter>
                    </Card>
                  )
                })}
              </div>
            </div>
          )
        })}
      </div>
    </main>
  )
}
