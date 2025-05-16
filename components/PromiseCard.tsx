import { useState } from 'react';
import PromiseModal from "./promise-modal"
import type { PromiseData, EvidenceItem } from "@/lib/types"

interface PromiseCardProps {
  promise: PromiseData;
  // The department-wide evidenceItems might still be passed to PromiseCard
  // if it had other uses, but for now, we assume its main role was for the modal's old timeline.
  // If PromiseCard itself doesn't use evidenceItems directly, this prop could also be removed from PromiseCardProps.
  // For this change, we focus on what it passes to PromiseModal.
  evidenceItems: EvidenceItem[]; 
}

export default function PromiseCard({ promise, evidenceItems }: PromiseCardProps) {
  const { text } = promise;
  const [isModalOpen, setIsModalOpen] = useState(false);

  // The 'promise' object passed to PromiseModal now contains promise.evidence for the timeline.
  // The 'relevantEvidence' filtering based on 'evidenceItems' is no longer needed for the modal's timeline.
  // const relevantEvidence = evidenceItems.filter(item => item.promise_ids.includes(promise.id));

  return (
    <>
      <div
        className="rounded-none border border-[#d3c7b9] p-4 cursor-pointer hover:bg-[#fdfaf6] transition-colors mb-4"
        onClick={() => setIsModalOpen(true)}
      >
        <p className="text-base text-[#222222] leading-normal">{text}</p> 
      </div>

      <PromiseModal
        promise={promise} // Pass the full promise object, which includes its own .evidence array
        // evidenceItems={relevantEvidence} // Removed: PromiseModal no longer takes this for the timeline
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  )
} 