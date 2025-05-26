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

  let tenureString = "";
  const formattedStartDate = formatDate(positionStart);
  const formattedEndDate = formatDate(positionEnd);

  if (formattedStartDate && formattedEndDate) {
    tenureString = `${formattedStartDate} - ${formattedEndDate}`;
  } else if (formattedStartDate) {
    tenureString = `Since ${formattedStartDate}`;
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
    <div>
      {/* Minister Info Header */}
      <div className="flex items-center mb-8">
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
          <h2 className="text-3xl">{ministerName}</h2>
          <p className="mt-1 text-sm font-mono">{ministerTitle}, {tenureString}</p>
        </div>
      </div>

      {/* Key Metrics Placeholder Section */}
      <div>
        <h3 className="text-2xl mb-4">Key Performance Indicators & Metrics</h3>
        <div className="mb-8">
          <div className="bg-gray-50 border border-dashed border-gray-300 p-8 text-center flex items-center justify-center" style={{ minHeight: '20vh' }}>
            <p className="text-gray-400 italic text-lg">[Placeholder: Charts and key metrics for {ministerInfo?.effectiveDepartmentOfficialFullName || departmentFullName} will be displayed here.]</p>
          </div>
        </div>

        {/* Promises Section */}
        <div className="mb-8">
          <h3 className="text-2xl font-semibold mb-6">Commitments</h3>
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
    </div>
  )
} 