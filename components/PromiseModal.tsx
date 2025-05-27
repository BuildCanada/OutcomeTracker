"use client";

import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from "@/components/ui/dialog"
import type { PromiseData, RationaleEvent, EvidenceItem } from "@/lib/types"
import { CalendarIcon, FileTextIcon, UsersIcon, LinkIcon, TrendingUpIcon, ChevronDownIcon, ChevronRightIcon, CheckCircle2Icon, XIcon } from "lucide-react"
import { Timestamp } from 'firebase/firestore';
import PromiseProgressTimeline from './PromiseProgressTimeline';
import React, { useState } from 'react';

interface PromiseModalProps {
  promise: PromiseData;
  isOpen: boolean;
  onClose: () => void;
}

// Helper to format Firestore Timestamp or ISO string date
const formatDate = (date: Timestamp | string | undefined): string => {
  if (!date) return "Date unknown";
  try {
    const jsDate = date instanceof Timestamp ? date.toDate() : new Date(date);
    return jsDate.toLocaleDateString("en-CA", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch (e) {
    console.error("Error formatting date:", date, e);
    return typeof date === "string" ? date : "Invalid date"; // Fallback for unparsable strings
  }
};

// Helper to format YYYY-MM-DD date string
const formatSimpleDate = (dateString: string | undefined): string => {
  if (!dateString) return "Date unknown";
  try {
    const [year, month, day] = dateString.split("-");
    const date = new Date(parseInt(year), parseInt(month) - 1, parseInt(day));
    return date.toLocaleDateString("en-CA", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch (e) {
    console.error("Error formatting simple date:", dateString, e);
    return dateString; // Fallback
  }
};

// Progress dot color scale (red to green) - moved here for use in modal
const progressDotColors = [
  "bg-red-500",      // Score 1
  "bg-yellow-400", // Score 2
  "bg-yellow-300", // Score 3
  "bg-lime-400",   // Score 4
  "bg-green-600",  // Score 5
];

// Helper function to get SVG arc path for pie fill
function getPieArcPath(cx: number, cy: number, r: number, startAngle: number, endAngle: number): string {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return [
    "M", cx, cy,
    "L", start.x, start.y,
    "A", r, r, 0, largeArcFlag, 0, end.x, end.y,
    "Z"
  ].join(" ");
}

function polarToCartesian(cx: number, cy: number, r: number, angleInDegrees: number): { x: number; y: number } {
  var angleInRadians = (angleInDegrees-90) * Math.PI / 180.0;
  return {
    x: cx + (r * Math.cos(angleInRadians)),
    y: cy + (r * Math.sin(angleInRadians))
  };
}

function getPieColor(progressScore: number): string {
  const colorMap = [
    '#ef4444', // red-500
    '#facc15', // yellow-400
    '#fde047', // yellow-300
    '#a3e635', // lime-400
    '#16a34a', // green-600
  ];
  return colorMap[Math.max(0, Math.min(progressScore - 1, 4))];
}

export default function PromiseModal({ promise, isOpen, onClose }: PromiseModalProps) {
  const { text, commitment_history_rationale, date_issued, concise_title, what_it_means_for_canadians, intended_impact_and_objectives, background_and_context, progress_score = 0, progress_summary, evidence } = promise;

  const [isRationaleExpanded, setIsRationaleExpanded] = useState(false);

  // Get the last updated date from evidence items
  const lastUpdateDate = evidence && evidence.length > 0 
    ? (() => {
        const sorted = [...evidence].sort((a, b) => {
          const getDateMillis = (dateInput: EvidenceItem['evidence_date']): number => {
            if (!dateInput) return NaN;
            let d: Date;
            if (dateInput instanceof Timestamp) {
              d = dateInput.toDate();
            } else if (typeof dateInput === 'object' && dateInput !== null && 
                      typeof (dateInput as any).seconds === 'number' &&
                      typeof (dateInput as any).nanoseconds === 'number') {
              d = new Date((dateInput as any).seconds * 1000);
            } else if (typeof dateInput === 'string') {
              if (/^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
                const [year, month, day] = dateInput.split('-').map(Number);
                d = new Date(year, month - 1, day);
              } else {
                d = new Date(dateInput);
              }
            } else {
              return NaN;
            }
            return d.getTime();
          };

          const dateAMillis = getDateMillis(a.evidence_date);
          const dateBMillis = getDateMillis(b.evidence_date);

          if (isNaN(dateAMillis) && isNaN(dateBMillis)) return 0;
          if (isNaN(dateAMillis)) return 1;
          if (isNaN(dateBMillis)) return -1;

          return dateBMillis - dateAMillis; // Descending
        });
        return formatDate(sorted[0].evidence_date);
      })()
    : null;

  // ADDED: Log the received promise object, especially its evidence array
  console.log("[PromiseModal Debug] Received promise:", promise);
  if (promise && promise.evidence) {
    console.log("[PromiseModal Debug] Promise evidence array:", promise.evidence);
    console.log(`[PromiseModal Debug] Number of evidence items in modal: ${promise.evidence.length}`);
  } else {
    console.log("[PromiseModal Debug] Promise evidence array is missing or empty.");
  }

  // Ensure promise object and its nested evidence array are available
  if (!promise) {
    // This case should ideally be handled before calling PromiseModal
    // or by ensuring isOpen is false if promise is null/undefined.
    return null; 
  }

  const isDelivered = progress_score === 5;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 max-w-3xl w-full max-h-[90vh] overflow-y-auto overflow-x-hidden bg-white p-0 border shadow-xl z-50">
        {/* Header */}
        <DialogHeader className="border-b border-[#d3c7b9] p-6">
          {/* Title */}
          <DialogTitle className="text-2xl font-bold text-[#222222] mb-2 break-words">
            {concise_title || text}
          </DialogTitle>

          {/* Description */}
          {intended_impact_and_objectives && (
            <div className="text-base text-gray-700 mb-2 break-words">
              {intended_impact_and_objectives}
            </div>
          )}

          {/* Original Text */}
          {concise_title && (
            <div className="text-sm italic text-gray-500 mb-2 break-words">
              <span className="font-medium">Original Text:</span> {text}
            </div>
          )}

          {/* Last Updated Date */}
          {lastUpdateDate && (
            <DialogDescription className="text-xs text-gray-400">
              Last Updated: {lastUpdateDate}
            </DialogDescription>
          )}
        </DialogHeader>

        <div className="p-6 space-y-8 break-words overflow-x-hidden">
          {/* What this means for Canadians Section */}
          {what_it_means_for_canadians && (
            <section>
              <h3 className="text-xl font-bold text-[#222222] mb-3 flex items-center">
                <UsersIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
                What This Means for Canadians
              </h3>
              <ul className="text-[#333333] leading-relaxed space-y-2 list-disc pl-5 break-words">
                {Array.isArray(what_it_means_for_canadians) ? (
                  what_it_means_for_canadians.map((item, index) => (
                    <li key={index} className="break-words whitespace-pre-line">
                      {item}
                    </li>
                  ))
                ) : (
                  <li className="break-words whitespace-pre-line">{what_it_means_for_canadians}</li>
                )}
              </ul>
            </section>
          )}

          {/* Progress Section */}
          {(progress_score > 0 || progress_summary) && (
            <section className="border-t border-[#d3c7b9] pt-6">
              <h3 className="text-xl font-bold text-[#222222] mb-4 flex items-center">
                {/* Progress SVG indicator as section icon */}
                <span className="mr-2 w-6 h-6 inline-flex items-center justify-center">
                  <svg className="w-6 h-6" viewBox="0 0 24 24">
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      fill={getPieColor(progress_score)}
                      stroke={getPieColor(progress_score)}
                      strokeWidth="2"
                    />
                    {progress_score < 5 && progress_score > 0 && (
                      <path
                        d={getPieArcPath(12, 12, 10, 0, (1 - progress_score / 5) * 360)}
                        fill="#fff"
                      />
                    )}
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      fill="none"
                      stroke={getPieColor(progress_score)}
                      strokeWidth="2"
                    />
                  </svg>
                </span>
                {progress_score === 0 ? "Not started" : progress_score === 5 ? "Complete" : "In Progress"}
              </h3>
              <div className="flex items-start">
                {/* No status label here anymore */}
                <div className="flex flex-col items-center pt-1"></div>
                <p className="text-[#333333] leading-relaxed whitespace-pre-line flex-1 break-words">
                  {progress_summary || ""}
                </p>
              </div>
            </section>
          )}
          
          {/* Timeline and Evidence Details Section - Existing Component */}
          <section className="border-t border-[#d3c7b9] pt-6">
             <h3 className="text-xl font-bold text-[#222222] mb-4 flex items-center">
                <CalendarIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
                Timeline
              </h3>
            <PromiseProgressTimeline promise={promise} /> 
          </section>

          {/* Background Section */}
          {(background_and_context || (commitment_history_rationale && commitment_history_rationale.length > 0)) && (
            <section className="border-t border-[#d3c7b9] pt-6">
              <h3 className="text-xl font-bold text-[#222222] mb-3 flex items-center">
                <FileTextIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
                Background
              </h3>
              {background_and_context && (
                <div className="mb-4">
                  <p className="text-[#333333] leading-relaxed whitespace-pre-line break-words">
                    {background_and_context}
                  </p>
                </div>
              )}

              {commitment_history_rationale && commitment_history_rationale.length > 0 && (
                <div>
                  <button 
                    onClick={() => setIsRationaleExpanded(!isRationaleExpanded)}
                    className="flex items-center text-xs text-[#0056b3] hover:underline focus:outline-none mb-2"
                    aria-expanded={isRationaleExpanded}
                  >
                    {isRationaleExpanded ? <ChevronDownIcon className="mr-1 h-4 w-4" /> : <ChevronRightIcon className="mr-1 h-4 w-4" />}
                    More Details of Preceding Events
                  </button>
                  {isRationaleExpanded && (
                    <div className="space-y-3 pl-2 border-l-2 border-gray-900">
                      {commitment_history_rationale.map(
                        (event: RationaleEvent, index: number) => (
                          <div
                            key={index}
                            className="border p-3 bg-gray-50"
                          >
                            <p className="text-xs font-medium mb-0.5">
                              {formatSimpleDate(event.date)}
                            </p>
                            <p className="text-sm text-[#333333] mb-1 break-words">{event.action}</p>
                            <a
                              href={event.source_url}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="text-xs text-[#0056b3] font-mono hover:underline inline-flex items-center"
                            >
                              <LinkIcon className="mr-1 h-3 w-3" /> Source
                            </a>
                          </div>
                        ),
                      )}
                    </div>
                  )}
                </div>
              )}
            </section>
          )}

        </div>
      </DialogContent>
    </Dialog>
  );
}