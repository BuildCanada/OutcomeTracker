'use client'
import { useState } from "react"
import PromiseModal from "./promise-modal" // Changed to relative path
import type { PromiseData, EvidenceItem } from "@/lib/types"

interface PromiseCardProps {
  promise: PromiseData;
  evidenceItems: EvidenceItem[]; // Pass relevant evidence items
}

export default function PromiseCard({ promise, evidenceItems }: PromiseCardProps) {
  const { text } = promise;
  const [isModalOpen, setIsModalOpen] = useState(false);

  // Filter evidence items specific to this promise
  const relevantEvidence = evidenceItems.filter(item => item.promise_ids.includes(promise.id));

  return (
    <>
      <div
        className="rounded-none border border-[#d3c7b9] p-4 cursor-pointer hover:bg-[#fdfaf6] transition-colors mb-4" // Use a slightly different hover and add margin
        onClick={() => setIsModalOpen(true)}
      >
        <p className="text-base text-[#222222] leading-normal">{text}</p> 
        {/* Removed Badges and lastUpdate for now */}
      </div>

      <PromiseModal
        promise={promise}
        evidenceItems={relevantEvidence} // Pass only relevant items
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  )
} 