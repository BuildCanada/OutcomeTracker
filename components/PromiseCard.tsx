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

  // Filter evidenceItems for those relevant to the current promise
  const relevantEvidenceForThisPromise = (evidenceItems || []).filter(e => 
    e.promise_ids && e.promise_ids.includes(promise.id)
  );

  // Use linked_evidence_ids for the count if available, otherwise fallback to filtered length
  // This assumes linked_evidence_ids is the source of truth from the promise document itself.
  const evidenceCount = promise.linked_evidence_ids?.length ?? relevantEvidenceForThisPromise.length;

  let dateRangeString: string | null = null;
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

  return (
    <>
      <div 
        className="bg-white shadow-md rounded-lg p-5 border-l-4 border-canada-red flex flex-col gap-3 hover:shadow-lg transition-shadow cursor-pointer"
        onClick={() => setIsModalOpen(true)}
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
      <PromiseModal 
        promise={promise}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </>
  );
} 