"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { ShareIcon, ArrowLeftIcon } from "lucide-react";
import type { PromiseData } from "@/lib/types";
import PromiseProgressTimeline from "./PromiseProgressTimeline";
import ShareModal from "./ShareModal";
import { Timestamp } from 'firebase/firestore';

interface PromiseDetailClientProps {
  promise: PromiseData;
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
    return typeof date === "string" ? date : "Invalid date";
  }
};

export default function PromiseDetailClient({ promise }: PromiseDetailClientProps) {
  const [isShareModalOpen, setIsShareModalOpen] = useState(false);
  const router = useRouter();

  const {
    text,
    concise_title,
    what_it_means_for_canadians,
    intended_impact_and_objectives,
    background_and_context,
    commitment_history_rationale,
    progress_score = 0,
    progress_summary,
    evidence,
    responsible_department_lead,
    category,
    date_issued,
  } = promise;

  // Get the last updated date from evidence items
  const lastUpdateDate = evidence && evidence.length > 0 
    ? (() => {
        const sorted = [...evidence].sort((a, b) => {
          const getDateMillis = (dateInput: any): number => {
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

  const isDelivered = progress_score === 5;

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header with navigation and share button */}
      <div className="bg-white border-b border-gray-200">
        <div className="max-w-4xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <Button
              variant="ghost"
              onClick={() => router.back()}
              className="flex items-center text-gray-600 hover:text-gray-900"
            >
              <ArrowLeftIcon className="mr-2 h-4 w-4" />
              Back to Tracker
            </Button>
            <Button
              onClick={() => setIsShareModalOpen(true)}
              className="flex items-center bg-[#8b2332] hover:bg-[#7a1f2b] text-white"
            >
              <ShareIcon className="mr-2 h-4 w-4" />
              Share this Promise
            </Button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
          {/* Promise header */}
          <div className="border-b border-gray-200 p-6">
            <h1 className="text-3xl font-bold text-gray-900 mb-4 break-words">
              {concise_title || text}
            </h1>

            {/* Promise metadata */}
            <div className="flex flex-wrap gap-4 text-sm text-gray-600 mb-4">
              {responsible_department_lead && (
                <div>
                  <span className="font-medium">Department:</span> {responsible_department_lead}
                </div>
              )}
              {category && (
                <div>
                  <span className="font-medium">Category:</span> {category}
                </div>
              )}
              {date_issued && (
                <div>
                  <span className="font-medium">Date Issued:</span> {formatDate(date_issued)}
                </div>
              )}
            </div>

            {/* Description */}
            {intended_impact_and_objectives && (
              <div className="text-lg text-gray-700 mb-4 break-words">
                {intended_impact_and_objectives}
              </div>
            )}

            {/* Original Text */}
            {concise_title && (
              <div className="text-sm italic text-gray-500 break-words">
                <span className="font-medium">Original Text:</span> {text}
              </div>
            )}

            {/* Last Updated Date */}
            {lastUpdateDate && (
              <div className="text-xs text-gray-400 mt-4">
                Last Updated: {lastUpdateDate}
              </div>
            )}
          </div>

          <div className="p-6 space-y-8">
            {/* What this means for Canadians Section */}
            {what_it_means_for_canadians && (
              <section>
                <h2 className="text-xl font-bold text-gray-900 mb-3">
                  What This Means for Canadians
                </h2>
                <div className="text-gray-700 leading-relaxed break-words whitespace-pre-line">
                  {Array.isArray(what_it_means_for_canadians) ? (
                    <ul className="list-disc pl-5 space-y-2">
                      {what_it_means_for_canadians.map((item, index) => (
                        <li key={index} className="break-words">
                          {item}
                        </li>
                      ))}
                    </ul>
                  ) : (
                    <p>{what_it_means_for_canadians}</p>
                  )}
                </div>
              </section>
            )}

            {/* Progress Section */}
            {(progress_score > 0 || progress_summary) && (
              <section className="border-t border-gray-200 pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-4">
                  Progress Status
                </h2>
                <div className="flex items-start space-x-4">
                  <div className="flex-shrink-0">
                    <div className={`w-4 h-4 rounded-full ${
                      progress_score === 0 ? 'bg-gray-400' :
                      progress_score === 1 ? 'bg-red-500' :
                      progress_score === 2 ? 'bg-yellow-400' :
                      progress_score === 3 ? 'bg-yellow-300' :
                      progress_score === 4 ? 'bg-lime-400' :
                      'bg-green-600'
                    }`}></div>
                  </div>
                  <div>
                    <div className="font-medium text-gray-900 mb-2">
                      {progress_score === 0 ? "Not Started" : 
                       progress_score === 5 ? "Complete" : "In Progress"}
                    </div>
                    {progress_summary && (
                      <p className="text-gray-700 leading-relaxed whitespace-pre-line break-words">
                        {progress_summary}
                      </p>
                    )}
                  </div>
                </div>
              </section>
            )}
            
            {/* Timeline Section */}
            <section className="border-t border-gray-200 pt-6">
              <h2 className="text-xl font-bold text-gray-900 mb-4">
                Timeline of Government Actions
              </h2>
              <PromiseProgressTimeline promise={promise} />
            </section>

            {/* Background Section */}
            {background_and_context && (
              <section className="border-t border-gray-200 pt-6">
                <h2 className="text-xl font-bold text-gray-900 mb-3">
                  Background
                </h2>
                <p className="text-gray-700 leading-relaxed whitespace-pre-line break-words">
                  {background_and_context}
                </p>
              </section>
            )}
          </div>
        </div>
      </div>

      {/* Share Modal */}
      <ShareModal
        isOpen={isShareModalOpen}
        onClose={() => setIsShareModalOpen(false)}
        shareUrl={typeof window !== 'undefined' ? window.location.href : ''}
        promiseTitle={concise_title || text}
      />
    </div>
  );
} 