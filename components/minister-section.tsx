import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import MetricChart from "@/components/metric-chart"
// TaskCard is for the old Task type, we'll display promises differently for now
// import TaskCard from "@/components/task-card"
import type { DepartmentPageData, PromiseData, MinisterDetails } from "@/lib/types"

interface MinisterSectionProps {
  departmentPageData: DepartmentPageData
}

const DEFAULT_MINISTER_NAME = "Minister Information Not Available"
const DEFAULT_MINISTER_TITLE = "Title Not Available"
const DEFAULT_AVATAR_FALLBACK_INITIALS = "N/A"

export default function MinisterSection({ departmentPageData }: MinisterSectionProps) {
  // Destructure with fallbacks for ministerDetails
  const minister = departmentPageData.ministerDetails || {}
  const ministerName = 
    minister.minister_full_name_from_blog || 
    (minister.minister_first_name && minister.minister_last_name ? `${minister.minister_first_name} ${minister.minister_last_name}` : null) || 
    DEFAULT_MINISTER_NAME
  const ministerTitle = minister.minister_title_scraped_pm_gc_ca || minister.minister_title_from_blog || DEFAULT_MINISTER_TITLE
  const avatarUrl = minister.avatarUrl // Already has a default from page.tsx if originally null/undefined
  
  const { guidingMetrics, promises } = departmentPageData

  const getFallbackInitials = (name: string) => {
    if (name === DEFAULT_MINISTER_NAME) return DEFAULT_AVATAR_FALLBACK_INITIALS
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
  }

  return (
    <div>
      <div className="flex items-center gap-6">
        <Avatar className="h-20 w-20 rounded-full border-4 border-[#a9d0f5]">
          <AvatarImage src={avatarUrl} alt={ministerName} />
          <AvatarFallback className="bg-[#a9d0f5] text-[#2332a9]">
            {getFallbackInitials(ministerName)}
          </AvatarFallback>
        </Avatar>

        <div>
          <h2 className="text-2xl font-bold text-[#222222]">{ministerName}</h2>
          <p className="text-[#555555]">{ministerTitle}</p>
        </div>
      </div>

      {/* Guiding Metrics section - kept as is for now */}
      {guidingMetrics && guidingMetrics.length > 0 && (
        <>
          <h3 className="mt-12 text-xl font-bold text-[#222222]">Guiding Metrics</h3>
          <div className="mt-4 w-full max-w-md border border-[#d3c7b9] p-4">
            {guidingMetrics.map((metric, index) => (
              <MetricChart key={index} title={metric.title} data={metric.data} goal={metric.goal} />
            ))}
          </div>
        </>
      )}

      <h3 className="mt-12 text-xl font-bold text-[#222222]">Promises</h3>
      <div className="mt-4 space-y-4">
        {promises && promises.length > 0 ? (
          promises.map((promise: PromiseData) => (
            // Replace with a proper PromiseCard component later
            <div key={promise.promise_id} className="rounded-lg border border-[#d3c7b9] bg-white p-4 shadow">
              <p className="text-base text-gray-700">{promise.text}</p>
              {/* You can add more details from promise object here if needed */}
              {/* e.g., <p className="text-sm text-gray-500 mt-2">Source: {promise.source_type}</p> */}
            </div>
          ))
        ) : (
          <p>No promises found for this department.</p>
        )}
      </div>
    </div>
  )
}
