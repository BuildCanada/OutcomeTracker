"use client";

import { useState } from 'react';
import type { PromiseData, EvidenceItem } from "@/lib/types";
import { Timestamp } from "firebase/firestore";
import { CalendarDaysIcon, ListChecksIcon } from "lucide-react";
import PromiseModal from './PromiseModal';

interface PromiseCardProps {
  promise: PromiseData;
  evidenceItems: EvidenceItem[];
  departmentShortName?: string;
}

const formatDate = (dateInput: Timestamp | string | undefined): string | null => {
  if (!dateInput) return null;
  let dateObj: Date;
  if (dateInput instanceof Timestamp) {
    dateObj = dateInput.toDate();
  } else if (typeof dateInput === 'string') {
    dateObj = new Date(dateInput);
    if (isNaN(dateObj.getTime())) {
      const parts = dateInput.split('-');
      if (parts.length === 3) {
        dateObj = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
      }
      if (isNaN(dateObj.getTime())) return null;
    }
  } else {
    return null;
  }
  return dateObj.toLocaleDateString('en-CA', { year: 'numeric', month: 'short', day: 'numeric' });
};

export default function PromiseCard({ promise, evidenceItems, departmentShortName }: PromiseCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);

  // --- DEBUG LOGS ---
  console.log(`[PromiseCard Debug] Promise ID: ${promise.id}, Promise FullPath: ${promise.fullPath}`);
  if (promise.evidence && promise.evidence.length > 0) {
    console.log(`[PromiseCard Debug] Promise ID: ${promise.id} has promise.evidence with ${promise.evidence.length} items. First item ID: ${promise.evidence[0]?.id}`);
  } else {
    console.log(`[PromiseCard Debug] Promise ID: ${promise.id} - promise.evidence is empty or undefined.`);
  }
  // Log the evidenceItems prop for comparison/diagostics if still needed, though we aim to rely less on it.
  if (evidenceItems && evidenceItems.length > 0) {
    console.log(`[PromiseCard Debug] evidenceItems prop for promise ${promise.id} (showing promise_ids of first 3):`, 
      evidenceItems.slice(0, 3).map(ei => ({ id: ei.id, promise_ids: ei.promise_ids }))
    );
  } else {
    console.log(`[PromiseCard Debug] evidenceItems prop for promise ${promise.id} is empty or undefined.`);
  }
  // --- END DEBUG LOGS ---

  // Use promise.evidence directly, as it should be populated by the data fetching layer.
  const relevantEvidenceForThisPromise = promise.evidence || [];

  // --- DEBUG LOGS ---
  console.log(`[PromiseCard Debug] Promise ID: ${promise.id} - relevantEvidenceForThisPromise (from promise.evidence) count: ${relevantEvidenceForThisPromise.length}`);
  if (relevantEvidenceForThisPromise.length > 0) {
    console.log(`[PromiseCard Debug] Promise ID: ${promise.id} - First relevant evidence (from promise.evidence):`, relevantEvidenceForThisPromise[0]);
  }
  // --- END DEBUG LOGS ---

  // Use linked_evidence_ids for the count if available, otherwise fallback to the length of promise.evidence.
  const evidenceCount = promise.linked_evidence_ids?.length ?? relevantEvidenceForThisPromise.length;

  let dateRangeString: string | null = null;
  // Date range calculation now uses relevantEvidenceForThisPromise (which is promise.evidence)
  if (relevantEvidenceForThisPromise.length > 0) {
    // Sort relevant evidence by date to find the first and last dates
    const sortedEvidenceForDateRange = [...relevantEvidenceForThisPromise].sort((a, b) => {
      const dateA = a.evidence_date instanceof Timestamp ? a.evidence_date.toMillis() : new Date(a.evidence_date as string).getTime();
      const dateB = b.evidence_date instanceof Timestamp ? b.evidence_date.toMillis() : new Date(b.evidence_date as string).getTime();
      if (isNaN(dateA) && isNaN(dateB)) return 0;
      if (isNaN(dateA)) return 1;
      if (isNaN(dateB)) return -1;
      return dateA - dateB;
    });

    const firstDate = formatDate(sortedEvidenceForDateRange[0]?.evidence_date);
    const lastDate = formatDate(sortedEvidenceForDateRange[sortedEvidenceForDateRange.length - 1]?.evidence_date);

    if (firstDate && lastDate) {
      if (firstDate === lastDate) {
        dateRangeString = firstDate;
      } else {
        dateRangeString = `${firstDate} - ${lastDate}`;
      }
    } else if (firstDate) {
      dateRangeString = firstDate;
    }
  }

  // Prepare the promise data specifically for the modal.
  // Since promise.evidence is already what we need, we can pass the promise object directly
  // if PromiseModal is designed to use promise.evidence.
  // For clarity, we ensure promiseForModal has the correct evidence array.
  const promiseForModal: PromiseData = {
    ...promise, // This spread includes promise.evidence if it's populated
    // If 'promise' object passed to modal already has 'evidence' populated correctly,
    // this explicit setting might be redundant, but ensures clarity.
    evidence: relevantEvidenceForThisPromise, 
  };

  const handleCardClick = () => {
    console.log("[PromiseCard Debug onClick] Opening modal for promise ID:", promiseForModal.id, "Text:", promiseForModal.text?.substring(0,30), "Evidence count in modal data:", promiseForModal.evidence?.length);
    setIsModalOpen(true);
  };

  return (
    <>
      <div 
        className="bg-white shadow-md rounded-lg p-5 border-l-4 border-canada-red flex flex-col gap-3 hover:shadow-lg transition-shadow cursor-pointer"
        onClick={handleCardClick}
      >
        <div className="flex justify-between items-center">
          {departmentShortName && (
            <span className="bg-gray-100 text-gray-700 px-3 py-1 rounded-full text-xs font-medium">
              {departmentShortName}
            </span>
          )}
        </div>
        <h3 className="text-lg font-semibold text-gray-800 leading-tight">
          {promise.text}
        </h3>
        <div className="mt-auto pt-3 flex justify-between items-center text-sm text-gray-600 border-t border-gray-100">
          <div className="flex items-center gap-2">
            {dateRangeString ? (
              <>
                <CalendarDaysIcon className="w-4 h-4 text-gray-500" />
                <span>{dateRangeString}</span>
              </>
            ) : (
              <div className="h-5"></div> // Placeholder for consistent height
            )}
          </div>
          <div className="flex items-center gap-2">
            <ListChecksIcon className="w-4 h-4 text-gray-500" />
            <span>{evidenceCount} progress updates</span>
          </div>
        </div>
      </div>
      {/* 
        When PromiseModal is opened, it receives the `promise` object.
        The data fetching layer MUST ensure that `promise.evidence` is populated correctly 
        with EvidenceItem[] specific to THIS promise, typically by resolving `promise.linked_evidence_ids`.
        If promise.evidence is not populated correctly, the timeline in the modal will be empty or wrong.
      */}
      <PromiseModal
        promise={promiseForModal} // Pass the updated promise object
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
} 