'use client'

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
import type { DepartmentPageData, PromiseData, MinisterInfo, EvidenceItem } from "@/lib/types"
import Image from 'next/image'
import PromiseCard from "./PromiseCard" 

interface MinisterSectionProps {
  departmentPageData: DepartmentPageData | null
  departmentFullName: string
  departmentShortName?: string
}

const DEFAULT_MINISTER_NAME = "Minister Information Not Available"
const DEFAULT_MINISTER_TITLE = "Title Not Available"
const DEFAULT_AVATAR_FALLBACK_INITIALS = "N/A"

// Helper function to format dates, similar to PromiseCard
const formatDate = (dateString: string | undefined | null): string | null => {
  if (!dateString) return null;
  const dateObj = new Date(dateString);
  if (isNaN(dateObj.getTime())) return null;
  return dateObj.toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' });
};

export default function MinisterSection({ departmentPageData, departmentFullName, departmentShortName }: MinisterSectionProps) {
  if (!departmentPageData) {
    return (
      <div className="text-center py-10">
        <p className="text-gray-500">Loading details for {departmentFullName}...</p>
        {/* You could add a spinner here */}
      </div>
    )
  }

  const { ministerInfo, promises, evidenceItems } = departmentPageData!
  const ministerName = ministerInfo?.name || DEFAULT_MINISTER_NAME
  const ministerTitle = ministerInfo?.title || DEFAULT_MINISTER_TITLE
  const avatarUrl = ministerInfo?.avatarUrl
  const positionStart = ministerInfo?.positionStart;
  const positionEnd = ministerInfo?.positionEnd;

  // Use the effective department name if available, otherwise fall back to the prop
  const displayDepartmentFullName = ministerInfo?.effectiveDepartmentOfficialFullName || departmentFullName;

  let tenureString = "";
  const formattedStartDate = formatDate(positionStart);
  const formattedEndDate = formatDate(positionEnd);

  if (formattedStartDate && formattedEndDate) {
    tenureString = `Portfolio held: ${formattedStartDate} - ${formattedEndDate}`;
  } else if (formattedStartDate) {
    tenureString = `Portfolio held: Since ${formattedStartDate}`;
  }
  
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
          {avatarUrl ? (
             <Avatar className="h-20 w-20 mr-6 bg-gray-100">
               <AvatarImage 
                 src={avatarUrl} 
                 alt={`Official portrait of ${ministerName}`} 
                 className="object-cover"
               />
               <AvatarFallback>{getFallbackInitials(ministerName)}</AvatarFallback>
             </Avatar>
          ) : (
            <div className="h-20 w-20 mr-6 flex items-center justify-center bg-gray-200">
              <span className="text-2xl text-gray-500">{getFallbackInitials(ministerName)}</span>
            </div>
          )}
          <div>
            <h2 className="text-3xl font-bold text-[#222222]">{ministerName}</h2>
            <p className="text-lg text-[#555555]">{ministerTitle}</p>
            <p className="text-sm text-[#8b2332]">{displayDepartmentFullName}</p>
            {tenureString && (
              <p className="text-xs text-gray-500 mt-1">{tenureString}</p>
            )}
          </div>
        </div>
      </div>

      {/* Key Metrics Placeholder Section */}
      <div className="border-t border-[#d3c7b9] pt-8 mt-12 px-2 mb-8">
        <h3 className="text-2xl font-semibold text-[#222222] mb-4">Key Performance Indicators & Metrics</h3>
        <div className="bg-gray-50 border border-dashed border-gray-300 rounded-lg p-8 text-center flex items-center justify-center" style={{ minHeight: '20vh' }}>
          <p className="text-gray-400 italic text-lg">[Placeholder: Charts and key metrics for {ministerInfo?.effectiveDepartmentOfficialFullName || departmentFullName} will be displayed here.]</p>
        </div>
      </div>

      {/* Promises Section */}
      <div className="mb-8 px-2">
        <h3 className="text-2xl font-semibold text-[#222222] mb-6">Commitments:</h3>
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

    </div>
  )
} 