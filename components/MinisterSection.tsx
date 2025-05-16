'use client'

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
// import MetricChart from "./MetricChart" // CORRECTED IMPORT PATH and assuming it will be in the same dir
// TaskCard is for the old Task type, we'll display promises differently for now
// import TaskCard from "@/components/task-card"
import type { DepartmentPageData, PromiseData, MinisterDetails, EvidenceItem } from "@/lib/types"
import Image from 'next/image'
import PromiseCard from "./PromiseCard" // CORRECTED IMPORT PATH
// import PromiseProgressTimeline from './PromiseProgressTimeline'; // Removed this import

interface MinisterSectionProps {
  departmentPageData: DepartmentPageData | null
  departmentFullName: string
  departmentShortName?: string
}

const DEFAULT_MINISTER_NAME = "Minister Information Not Available"
const DEFAULT_MINISTER_TITLE = "Title Not Available"
const DEFAULT_AVATAR_FALLBACK_INITIALS = "N/A"

export default function MinisterSection({ departmentPageData, departmentFullName, departmentShortName }: MinisterSectionProps) {
  if (!departmentPageData) {
    return (
      <div className="text-center py-10">
        <p className="text-gray-500">Loading details for {departmentFullName}...</p>
        {/* You could add a spinner here */}
      </div>
    )
  }

  const { ministerDetails, promises, evidenceItems } = departmentPageData
  const ministerName = 
    ministerDetails?.minister_full_name_from_blog || 
    (ministerDetails?.minister_first_name && ministerDetails?.minister_last_name ? `${ministerDetails.minister_first_name} ${ministerDetails.minister_last_name}` : null) || 
    DEFAULT_MINISTER_NAME
  const ministerTitle = ministerDetails?.minister_title_scraped_pm_gc_ca || ministerDetails?.minister_title_from_blog || DEFAULT_MINISTER_TITLE
  const avatarUrl = ministerDetails?.avatarUrl // Already has a default from page.tsx if originally null/undefined
  
  const getFallbackInitials = (name: string) => {
    if (name === DEFAULT_MINISTER_NAME) return DEFAULT_AVATAR_FALLBACK_INITIALS
    return name
      .split(" ")
      .map((n) => n[0])
      .join("")
      .toUpperCase()
  }

  return (
    <div className="bg-white">
      {/* Minister Info Header */}
      <div className="mb-8 p-6 border border-[#d3c7b9] bg-[#fdfaf6]">
        <div className="flex items-center">
          {/* Placeholder for minister image - can be added later */}
          {/* <Image src={minister.avatarUrl || "/placeholder-avatar.png"} alt={`Portrait of ${ministerName}`} width={80} height={80} className="rounded-full mr-6" /> */}
    <div>
            <h2 className="text-3xl font-bold text-[#222222]">{ministerName}</h2>
            <p className="text-lg text-[#555555]">{ministerTitle}</p>
            <p className="text-sm text-[#8b2332]">{departmentFullName}</p>
          </div>
        </div>
      </div>

      {/* Promises Section */}
      <div className="mb-8 px-2">
        <h3 className="text-2xl font-semibold text-[#222222] mb-6">Mandate Letter Commitments:</h3>
        {promises && promises.length > 0 ? (
          <div className="grid grid-cols-1 gap-6">
            {[...promises].sort((a, b) => {
              const countA = a.linked_evidence_ids?.length || 0;
              const countB = b.linked_evidence_ids?.length || 0;
              return countB - countA; // Sort in descending order
            }).map((promise: PromiseData) => (
              <PromiseCard 
                key={promise.id} 
                promise={promise} 
                evidenceItems={evidenceItems || []}
                departmentShortName={departmentShortName ? departmentShortName : undefined}
              />
            ))}
          </div>
        ) : (
          <p className="text-gray-600 italic">No specific mandate letter commitments found for this department.</p>
        )}
      </div>

      {/* Guiding Metrics Section (Placeholder) */}
      {/* 
      <div className="border-t border-[#d3c7b9] pt-8 mt-8 px-2">
        <h3 className="text-2xl font-semibold text-[#222222] mb-4">Key Performance Indicators & Metrics</h3>
        <p className="text-gray-500 italic">[Guiding metrics and performance indicators related to this department's portfolio will be displayed here.]</p>
      </div>
      */}
    </div>
  )
} 