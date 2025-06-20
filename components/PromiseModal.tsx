import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import type { RationaleEvent, PromiseDetail } from "@/lib/types";
import {
  CalendarIcon,
  FileTextIcon,
  UsersIcon,
  LinkIcon,
  ChevronDownIcon,
  ChevronRightIcon,
  PaperclipIcon,
  ShareIcon,
} from "lucide-react";
import { Timestamp } from "firebase/firestore";
import PromiseProgressTimeline from "./PromiseProgressTimeline";
import {
  Popover,
  PopoverTrigger,
  PopoverContent,
} from "@/components/ui/popover";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/use-toast";
import { CopyIcon } from "lucide-react";
import React, { useState, useEffect, useMemo } from "react";

interface PromiseModalProps {
  promise: PromiseDetail;
  isOpen: boolean;
  onClose: () => void;
}

// Helper to format Firestore Timestamp or ISO string date
const formatDate = (date: Timestamp | string | undefined): string => {
  if (!date) return "Date unknown";
  try {
    let jsDate: Date;
    if (date instanceof Timestamp) {
      jsDate = date.toDate();
    } else if (
      typeof date === "object" &&
      date !== null &&
      typeof (date as any).seconds === "number" &&
      typeof (date as any).nanoseconds === "number"
    ) {
      // Handle serialized Timestamp objects
      jsDate = new Date((date as any).seconds * 1000);
    } else if (typeof date === "string") {
      // Handle YYYY-MM-DD format
      if (/^\d{4}-\d{2}-\d{2}$/.test(date)) {
        const [year, month, day] = date.split("-").map(Number);
        jsDate = new Date(year, month - 1, day);
      } else {
        jsDate = new Date(date);
      }
    } else {
      return "Invalid date format";
    }

    if (isNaN(jsDate.getTime())) {
      return "Invalid date";
    }

    return jsDate.toLocaleDateString("en-CA", {
      year: "numeric",
      month: "long",
      day: "numeric",
    });
  } catch (e) {
    console.error("Error formatting date:", date, e);
    return "Invalid date";
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
  "bg-yellow-300", // Score 1
  "bg-amber-300", // Score 2
  "bg-orange-300", // Score 3
  "bg-lime-400", // Score 4
  "bg-green-600", // Score 5
];

// Helper function to get SVG arc path for pie fill
function getPieArcPath(
  cx: number,
  cy: number,
  r: number,
  startAngle: number,
  endAngle: number,
): string {
  const start = polarToCartesian(cx, cy, r, endAngle);
  const end = polarToCartesian(cx, cy, r, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? "0" : "1";
  return [
    "M",
    cx,
    cy,
    "L",
    start.x,
    start.y,
    "A",
    r,
    r,
    0,
    largeArcFlag,
    0,
    end.x,
    end.y,
    "Z",
  ].join(" ");
}

function polarToCartesian(
  cx: number,
  cy: number,
  r: number,
  angleInDegrees: number,
): { x: number; y: number } {
  var angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
  return {
    x: cx + r * Math.cos(angleInRadians),
    y: cy + r * Math.sin(angleInRadians),
  };
}

function getPieColor(progressScore: number): string {
  const colorMap = [
    "#fde047", // yellow-300
    "#fcd34d", // amber-300
    "#ffb86a", // orange-300
    "#a3e635", // lime-400
    "#16a34a", // green-600
  ];
  return colorMap[Math.max(0, Math.min(progressScore - 1, 4))];
}

export default function PromiseModal({
  promise,
  isOpen,
  onClose,
}: PromiseModalProps) {
  const {
    text,
    commitment_history_rationale,
    concise_title,
    description,
    what_it_means_for_canadians,
    progress_score = 0,
    progress_summary,
    last_evidence_data,
  } = promise;

  const [isRationaleExpanded, setIsRationaleExpanded] = useState(false);
  const [isSharePopoverOpen, setIsSharePopoverOpen] = useState(false);
  const [isCopying, setIsCopying] = useState(false);
  const { toast } = useToast();

  return (
    <>
      <Dialog open={isOpen} onOpenChange={onClose}>
        <DialogContent className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 max-w-3xl w-full max-h-[90vh] overflow-y-auto overflow-x-hidden bg-white p-0 border shadow-xl z-50">
          {/* Header */}
          <DialogHeader className="border-b border-[#d3c7b9] p-6 relative">
            {/* Title */}
            <DialogTitle className="text-2xl font-bold text-[#222222] mb-2 break-words pr-24">
              {concise_title || text}
            </DialogTitle>

            {/* Description */}
            {description && (
              <div className="text-base text-gray-700 mb-2 break-words">
                {description}
              </div>
            )}

            {/* Last Updated Date */}
            {last_evidence_data && (
              <DialogDescription className="text-xs text-gray-400">
                Last Updated: {last_evidence_data}
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
                      <li
                        key={index}
                        className="break-words whitespace-pre-line"
                      >
                        {item}
                      </li>
                    ))
                  ) : (
                    <li className="break-words whitespace-pre-line">
                      {what_it_means_for_canadians}
                    </li>
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
                          d={getPieArcPath(
                            12,
                            12,
                            10,
                            0,
                            (1 - progress_score / 5) * 360,
                          )}
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
                  {progress_score === 0
                    ? "Not started"
                    : progress_score === 5
                      ? "Complete"
                      : "In Progress"}
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
            {(description ||
              (commitment_history_rationale &&
                commitment_history_rationale.length > 0)) && (
              <section className="border-t border-[#d3c7b9] pt-6">
                <h3 className="text-xl font-bold text-[#222222] mb-3 flex items-center">
                  <FileTextIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
                  Background
                </h3>
                {description && (
                  <div className="mb-4">
                    <p className="text-[#333333] leading-relaxed whitespace-pre-line break-words">
                      {description}
                    </p>
                  </div>
                )}

                {commitment_history_rationale &&
                  commitment_history_rationale.length > 0 && (
                    <div>
                      <button
                        onClick={() =>
                          setIsRationaleExpanded(!isRationaleExpanded)
                        }
                        className="flex items-center text-xs text-[#0056b3] hover:underline focus:outline-none mb-2"
                        aria-expanded={isRationaleExpanded}
                      >
                        <span>
                          {isRationaleExpanded ? (
                            <ChevronDownIcon className="h-4 w-4" />
                          ) : (
                            <ChevronRightIcon className="h-4 w-4" />
                          )}
                        </span>
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
                                <p className="text-sm text-[#333333] mb-1 break-words">
                                  {event.action}
                                </p>
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

            {/* Original Text */}
            <section className="border-t border-[#d3c7b9] pt-6">
              <h3 className="text-xl font-bold text-[#222222] mb-3 flex items-center">
                <PaperclipIcon className="mr-2 h-5 w-5 text-[#8b2332]" />
                Original Text
              </h3>
              {concise_title && (
                <div>
                  <blockquote className="text-sm italic break-words border-l-4 border-[#8b2332] bg-gray-50 px-4 py-3 mb-3 text-gray-700">
                    {text}
                  </blockquote>
                </div>
              )}
              {/* Always show source URL if it exists, regardless of concise_title */}
              {promise.source_url && (
                <div className="mt-3">
                  <a
                    href={promise.source_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 hover:underline text-xs font-mono inline-flex items-center gap-1"
                  >
                    <svg
                      xmlns="http://www.w3.org/2000/svg"
                      className="h-4 w-4 inline-block"
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M18 13v6a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6m5-3h3m0 0v6m0-6L10 14"
                      />
                    </svg>
                    View Source
                  </a>
                </div>
              )}
            </section>
          </div>

          {/* Modal Footer */}
          <div className="border-t border-[#d3c7b9] px-6 py-4 bg-white flex justify-end sticky bottom-0 z-10">
            <Popover
              open={isSharePopoverOpen}
              onOpenChange={setIsSharePopoverOpen}
            >
              <PopoverTrigger asChild>
                <button
                  className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 text-sm font-medium text-gray-700 hover:bg-gray-50 transition-colors"
                  aria-label="Share this promise"
                >
                  <ShareIcon className="w-4 h-4" />
                  Share
                </button>
              </PopoverTrigger>
              <PopoverContent
                align="end"
                className="bg-white shadow-lg border w-80 p-4 z-50"
              >
                <div className="space-y-4">
                  {/* Header */}
                  <div className="text-lg font-semibold text-gray-900">
                    Share to
                  </div>
                  {/* Social Media Buttons */}
                  <div className="flex flex-row gap-3 justify-between">
                    {/* Twitter/X Button */}
                    <button
                      onClick={() => {
                        const shareText =
                          typeof concise_title !== "undefined" && concise_title
                            ? concise_title
                            : typeof text !== "undefined" && text
                              ? text
                              : promise && promise.text
                                ? promise.text
                                : "";
                        const url = encodeURIComponent(
                          typeof window !== "undefined"
                            ? `${window.location.origin}/promise/${promise.id}`
                            : "",
                        );
                        const tweetText = encodeURIComponent(
                          `Check out this promise: ${shareText.slice(0, 100)}`,
                        );
                        window.open(
                          `https://twitter.com/intent/tweet?url=${url}&text=${tweetText}`,
                          "_blank",
                          "noopener,noreferrer",
                        );
                      }}
                      className="flex flex-col items-center p-2 hover:bg-gray-50 rounded-lg transition-colors"
                    >
                      <div className="w-10 h-10 flex items-center justify-center">
                        <svg
                          className="w-5 h-5"
                          viewBox="0 0 24 24"
                          fill="currentColor"
                        >
                          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                        </svg>
                      </div>
                      <span className="text-xs font-medium mt-1">X</span>
                    </button>
                    {/* Facebook Button */}
                    <button
                      onClick={() => {
                        const shareText =
                          typeof concise_title !== "undefined" && concise_title
                            ? concise_title
                            : typeof text !== "undefined" && text
                              ? text
                              : promise && promise.text
                                ? promise.text
                                : "";
                        const url = encodeURIComponent(
                          typeof window !== "undefined"
                            ? `${window.location.origin}/promise/${promise.id}`
                            : "",
                        );
                        const fbText = encodeURIComponent(
                          `Check out this promise: ${shareText.slice(0, 100)}`,
                        );
                        window.open(
                          `https://www.facebook.com/sharer/sharer.php?u=${url}&quote=${fbText}`,
                          "_blank",
                          "noopener,noreferrer",
                        );
                      }}
                      className="flex flex-col items-center p-2 hover:bg-gray-50 rounded-lg transition-colors"
                    >
                      <div className="w-10 h-10 flex items-center justify-center">
                        <svg
                          className="w-5 h-5"
                          viewBox="0 0 24 24"
                          fill="currentColor"
                        >
                          <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
                        </svg>
                      </div>
                      <span className="text-xs font-medium mt-1">Facebook</span>
                    </button>
                    {/* LinkedIn Button */}
                    <button
                      onClick={() => {
                        const shareText =
                          typeof concise_title !== "undefined" && concise_title
                            ? concise_title
                            : typeof text !== "undefined" && text
                              ? text
                              : promise && promise.text
                                ? promise.text
                                : "";
                        const url = encodeURIComponent(
                          typeof window !== "undefined"
                            ? `${window.location.origin}/promise/${promise.id}`
                            : "",
                        );
                        const title = encodeURIComponent(
                          `Government Promise: ${shareText.slice(0, 100)}`,
                        );
                        const summary = encodeURIComponent(
                          `Check out this promise: ${shareText.slice(0, 100)}`,
                        );
                        window.open(
                          `https://www.linkedin.com/sharing/share-offsite/?url=${url}&title=${title}&summary=${summary}`,
                          "_blank",
                          "noopener,noreferrer",
                        );
                      }}
                      className="flex flex-col items-center p-2 hover:bg-gray-50 rounded-lg transition-colors"
                    >
                      <div className="w-10 h-10 flex items-center justify-center">
                        <svg
                          className="w-5 h-5"
                          viewBox="0 0 24 24"
                          fill="currentColor"
                        >
                          <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
                        </svg>
                      </div>
                      <span className="text-xs font-medium mt-1">LinkedIn</span>
                    </button>
                  </div>
                  {/* Copy Link Section */}
                  <div className="space-y-2">
                    <div className="text-sm font-medium text-gray-700">
                      Copy link
                    </div>
                    <div className="flex space-x-2">
                      <Input
                        value={
                          typeof window !== "undefined"
                            ? `${window.location.origin}/promise/${promise.id}`
                            : ""
                        }
                        readOnly
                        className="flex-1 text-sm bg-gray-50 border-gray-200"
                        placeholder="Loading..."
                      />
                      <Button
                        onClick={async () => {
                          const shareUrl =
                            typeof window !== "undefined"
                              ? `${window.location.origin}/promise/${promise.id}`
                              : "";
                          setIsCopying(true);
                          try {
                            await navigator.clipboard.writeText(shareUrl);
                            toast({
                              title: "Link copied!",
                              description:
                                "The promise link has been copied to your clipboard.",
                            });
                          } catch (error) {
                            toast({
                              title: "Copy failed",
                              description:
                                "Failed to copy the link. Please try again.",
                              variant: "destructive",
                            });
                          } finally {
                            setIsCopying(false);
                          }
                        }}
                        disabled={isCopying}
                        variant="outline"
                        size="sm"
                        className="flex-shrink-0 px-3"
                      >
                        <CopyIcon className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
