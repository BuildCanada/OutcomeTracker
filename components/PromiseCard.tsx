"use client";

import { useState } from "react";
import type { PromiseData, EvidenceItem } from "@/lib/types";
import { Timestamp } from "firebase/firestore";
import { CalendarDaysIcon, ListChecksIcon, TrendingUpIcon, XIcon, CheckIcon, PlusIcon, MinusIcon } from "lucide-react";
import PromiseModal from "./PromiseModal";

interface PromiseCardProps {
  promise: PromiseData;
  evidenceItems: EvidenceItem[];
  departmentShortName?: string;
}

const formatDate = (dateInput: EvidenceItem['evidence_date']): string | null => {
  if (!dateInput) return null;
  let dateObj: Date;

  if (dateInput instanceof Timestamp) {
    dateObj = dateInput.toDate();
  } else if (typeof dateInput === 'object' && dateInput !== null && 
             typeof (dateInput as any).seconds === 'number' && 
             typeof (dateInput as any).nanoseconds === 'number') { // Handle serialized Timestamp
    dateObj = new Date((dateInput as any).seconds * 1000);
  } else if (typeof dateInput === 'string') {
    // Prefer parsing YYYY-MM-DD as local date components to avoid UTC issues with new Date(str)
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
      const [year, month, day] = dateInput.split('-').map(Number);
      dateObj = new Date(year, month - 1, day);
    } else {
      dateObj = new Date(dateInput); // For other string formats like ISO with timezone
    }
  } else {
    console.warn("[PromiseCard formatDate] Unknown dateInput type:", dateInput);
    return null;
  }

  if (isNaN(dateObj.getTime())) {
    console.warn("[PromiseCard formatDate] Invalid date constructed for input:", dateInput);
    return null;
  }

  return dateObj.toLocaleDateString("en-CA", { year: "numeric", month: "short", day: "numeric" });
};

export default function PromiseCard({ promise, evidenceItems }: PromiseCardProps) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [showProgressTooltip, setShowProgressTooltip] = useState(false);
  const [showImpactTooltip, setShowImpactTooltip] = useState(false);
  const [showAlignmentTooltip, setShowAlignmentTooltip] = useState(false);
  const [showProgressModal, setShowProgressModal] = useState(false);

  // Use promise.evidence directly, as it should be populated by the data fetching layer.
  const relevantEvidenceForThisPromise = promise.evidence || [];

  // Use linked_evidence_ids for the count if available, otherwise fallback to the length of promise.evidence.
  // const evidenceCount = promise.linked_evidence_ids?.length ?? relevantEvidenceForThisPromise.length;
  // Correctly count only the filtered evidence items passed in promise.evidence
  const evidenceCount = relevantEvidenceForThisPromise.length;

  // Find the most recent evidence date for "Last Update"
  let lastUpdateDate: string | null = null;
  if (relevantEvidenceForThisPromise.length > 0) {
    const sorted = [...relevantEvidenceForThisPromise].sort((a, b) => {
      const getDateMillis = (dateInput: EvidenceItem['evidence_date']): number => {
        if (!dateInput) return NaN; 
        let d: Date;
        if (dateInput instanceof Timestamp) {
          d = dateInput.toDate();
        } else if (typeof dateInput === 'object' && dateInput !== null && 
                   typeof (dateInput as any).seconds === 'number' &&
                   typeof (dateInput as any).nanoseconds === 'number') { // Handle serialized Timestamp
          d = new Date((dateInput as any).seconds * 1000);
        } else if (typeof dateInput === 'string') {
          if (/^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
            const [year, month, day] = dateInput.split('-').map(Number);
            d = new Date(year, month - 1, day);
          } else {
            d = new Date(dateInput);
          }
        } else {
          return NaN; // Unknown type
        }
        return d.getTime();
      };

      const dateAMillis = getDateMillis(a.evidence_date);
      const dateBMillis = getDateMillis(b.evidence_date);

      if (isNaN(dateAMillis) && isNaN(dateBMillis)) return 0;
      if (isNaN(dateAMillis)) return 1; // Treat NaN as earlier (pushes it to the end of a descending sort)
      if (isNaN(dateBMillis)) return -1; // Treat NaN as earlier

      return dateBMillis - dateAMillis; // Descending
    });
    if (sorted[0]) {
        lastUpdateDate = formatDate(sorted[0].evidence_date);
    }
  }

  // Prepare the promise data specifically for the modal.
  const promiseForModal: PromiseData = {
    ...promise,
    evidence: relevantEvidenceForThisPromise,
  };

  const handleCardClick = () => {
    setIsModalOpen(true);
  };

  // Progress Indicator
  const progressScore = promise.progress_score || 0; // 1-5
  const progressSummary = promise.progress_summary || "No progress summary available.";
  const isDelivered = progressScore === 5;

  // Impact Indicator
  const impactRankRaw = promise.bc_promise_rank ?? '';
  const impactRationale = promise.bc_promise_rank_rationale || "No rationale provided.";
  let impactLabel = "";
  let impactBgColor = "";
  let impactIcon = null;
  let impactRankStr = String(impactRankRaw).toLowerCase();
  let impactRankNum = Number(impactRankRaw);
  if (impactRankStr === 'strong' || impactRankNum >= 8) {
    impactLabel = "High Impact";
    impactBgColor = "bg-yellow-200 text-yellow-800";
    impactIcon = <PlusIcon className="w-4 h-4 text-yellow-800" />;
  } else if (impactRankStr === 'medium' || (impactRankNum >= 5 && impactRankNum < 8)) {
    impactLabel = "Medium Impact";
    impactBgColor = "bg-yellow-100 text-yellow-800";
    impactIcon = <PlusIcon className="w-4 h-4 text-yellow-800" />;
  } else if (impactRankStr === 'low' || (impactRankNum > 0 && impactRankNum < 5)) {
    impactLabel = "Low Impact";
    impactBgColor = "bg-gray-100 text-gray-600";
    impactIcon = <MinusIcon className="w-4 h-4 text-gray-600" />;
  }

  // Alignment Indicator
  const alignmentDirection = promise.bc_promise_direction;
  let alignmentLabel = "";
  let alignmentColor = "";
  let alignmentBg = "";
  let alignmentIcon = null;
  switch (alignmentDirection) {
    case "positive":
      alignmentLabel = "Aligned";
      alignmentColor = "text-green-700";
      alignmentBg = "bg-green-50";
      alignmentIcon = <TrendingUpIcon className="w-4 h-4 text-green-600" />;
      break;
    case "neutral":
      alignmentLabel = "Neutral";
      alignmentColor = "text-gray-600";
      alignmentBg = "bg-gray-100";
      alignmentIcon = <MinusIcon className="w-4 h-4 text-gray-400" />;
      break;
    case "negative":
      alignmentLabel = "Not Aligned";
      alignmentColor = "text-red-700";
      alignmentBg = "bg-red-50";
      alignmentIcon = <MinusIcon className="w-4 h-4 text-red-600" />;
      break;
    default:
      alignmentLabel = "Unknown";
      alignmentColor = "text-gray-400";
      alignmentBg = "bg-gray-50";
      alignmentIcon = <MinusIcon className="w-4 h-4 text-gray-400" />;
  }
  const alignmentTooltip = `Alignment with building Canada: ${alignmentLabel}`;

  // Progress dot color scale (red to green)
  const dotColors = [
    "bg-red-500",
    "bg-yellow-400",
    "bg-yellow-300",
    "bg-lime-400",
    "bg-green-600"
  ];

  return (
    <>
      <div
        className="bg-white border border-[#cdc4bd] flex flex-col cursor-pointer focus:outline-none focus:ring-2 focus:ring-gray-300 group relative"
        tabIndex={0}
        aria-label={promise.text}
        onClick={handleCardClick}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') handleCardClick(); }}
      >
        <div className="p-6 pb-4 flex-1">
          <div className="text-lg font-bold text-[#111827] leading-snug mb-8">
            {promise.text}
          </div>
          {/* Impact & Alignment indicators, bottom right, side by side */}
          <div className="absolute right-6 bottom-16 flex flex-row items-center gap-2 z-10">
            {/* Impact */}
            {impactLabel && (
              <div className="relative">
                <div
                  className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold ${impactBgColor} cursor-help`}
                  onMouseEnter={() => setShowImpactTooltip(true)}
                  onMouseLeave={() => setShowImpactTooltip(false)}
                  onFocus={() => setShowImpactTooltip(true)}
                  onBlur={() => setShowImpactTooltip(false)}
                  tabIndex={0}
                  aria-label={`Impact: ${impactLabel}`}
                >
                  {impactIcon}
                  {impactLabel}
                </div>
                {showImpactTooltip && (
                  <div className="absolute z-20 p-2 bg-white border border-gray-200 rounded shadow-lg text-sm max-w-xs top-full mt-1 right-0 animate-fade-in">
                    {impactRationale}
                  </div>
                )}
              </div>
            )}
            {/* Alignment */}
            <div className="relative">
              <div
                className={`flex items-center gap-1 px-2 py-1 rounded-full text-xs font-semibold ${alignmentBg} ${alignmentColor} cursor-help`}
                onMouseEnter={() => setShowAlignmentTooltip(true)}
                onMouseLeave={() => setShowAlignmentTooltip(false)}
                onFocus={() => setShowAlignmentTooltip(true)}
                onBlur={() => setShowAlignmentTooltip(false)}
                tabIndex={0}
                aria-label={`Alignment: ${alignmentLabel}`}
              >
                {alignmentIcon}
                {alignmentLabel}
              </div>
              {showAlignmentTooltip && (
                <div className="absolute z-20 p-2 bg-white border border-gray-200 rounded shadow-lg text-sm max-w-xs top-full mt-1 right-0 animate-fade-in">
                  {alignmentTooltip}
                </div>
              )}
            </div>
          </div>
        </div>
        {/* Progress and meta bar */}
        <div className="bg-gray-50 border-t border-[#cdc4bd] px-6 py-3 flex items-center justify-between">
          {/* Progress dots and checkmark */}
          <div className="flex items-center gap-2 relative">
            <div
              className="flex gap-1 cursor-pointer focus:outline-none"
              onMouseEnter={() => setShowProgressTooltip(true)}
              onMouseLeave={() => setShowProgressTooltip(false)}
              onFocus={() => setShowProgressTooltip(true)}
              onBlur={() => setShowProgressTooltip(false)}
              tabIndex={0}
              aria-label={`Commitment Progress`}
              onClick={e => { e.stopPropagation(); setShowProgressModal(true); }}
              onKeyDown={e => { if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); setShowProgressModal(true); } }}
            >
              {[1, 2, 3, 4, 5].map((dot, idx) => (
                <div
                  key={dot}
                  className={`w-0.5 h-4 ${dot <= progressScore ? dotColors[progressScore - 1] : "bg-gray-300"}`}
                />
              ))}
            </div>
            {isDelivered && (
              <CheckIcon className="w-4 h-4 text-green-600 ml-2" aria-label="Delivered" />
            )}
            {showProgressTooltip && (
              <div className="absolute z-20 p-2 bg-white border border-gray-200 rounded shadow-lg text-sm max-w-xs top-full mt-1 left-0 animate-fade-in">
                Commitment Progress
              </div>
            )}
          </div>
          {/* Last update and progress updates */}
          <div className="flex items-center gap-4 text-sm text-gray-600">
            <div className="flex items-center gap-1">
              <CalendarDaysIcon className="w-4 h-4 text-gray-400" />
              <span>Last Update: {lastUpdateDate || "N/A"}</span>
            </div>
            <div className="flex items-center gap-1">
              <ListChecksIcon className="w-4 h-4 text-gray-400" />
              <span>{evidenceCount} progress updates</span>
            </div>
          </div>
        </div>
      </div>
      {/* Progress Summary Modal */}
      {showProgressModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-30">
          <div className="bg-white rounded-lg shadow-lg max-w-md w-full p-6 relative animate-fade-in">
            <button
              className="absolute top-3 right-3 text-gray-400 hover:text-gray-700 focus:outline-none"
              onClick={() => setShowProgressModal(false)}
              aria-label="Close progress summary"
            >
              <XIcon className="w-5 h-5" />
            </button>
            <h2 className="text-lg font-bold mb-4">Commitment Progress</h2>
            <div className="text-gray-800 whitespace-pre-line">{progressSummary}</div>
          </div>
        </div>
      )}
      <PromiseModal promise={promiseForModal} isOpen={isModalOpen} onClose={() => setIsModalOpen(false)} />
    </>
  );
} 