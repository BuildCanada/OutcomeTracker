"use client";

import { useState } from "react";
import type { PromiseListing } from "@/lib/types";
import { Timestamp } from "firebase/firestore";
import { TrendingUpIcon, XIcon, MinusIcon } from "lucide-react";
import PromiseModal from "./PromiseModal";

const formatDate = (dateInput: Timestamp | string): string | null => {
  if (!dateInput) return null;
  let dateObj: Date;

  if (dateInput instanceof Timestamp) {
    dateObj = dateInput.toDate();
  } else if (
    typeof dateInput === "object" &&
    dateInput !== null &&
    typeof (dateInput as any).seconds === "number" &&
    typeof (dateInput as any).nanoseconds === "number"
  ) {
    // Handle serialized Timestamp plain object
    dateObj = new Date((dateInput as any).seconds * 1000);
  } else if (typeof dateInput === "string") {
    // Prefer parsing YYYY-MM-DD as local date components to avoid UTC issues with new Date(str)
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
      const [year, month, day] = dateInput.split("-").map(Number);
      dateObj = new Date(year, month - 1, day);
    } else {
      dateObj = new Date(dateInput); // For other string formats like ISO with timezone
    }
  } else {
    console.warn("[PromiseCard formatDate] Unknown dateInput type:", dateInput);
    return null;
  }

  if (isNaN(dateObj.getTime())) {
    console.warn(
      "[PromiseCard formatDate] Invalid date constructed for input:",
      dateInput,
    );
    return null;
  }

  return dateObj.toLocaleDateString("en-CA", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
};

const getDateMillis = (dateInput: Timestamp | string): number => {
  if (!dateInput) return NaN;
  let d: Date;
  if (dateInput instanceof Timestamp) {
    d = dateInput.toDate();
  } else if (
    typeof dateInput === "object" &&
    dateInput !== null &&
    typeof (dateInput as any).seconds === "number" &&
    typeof (dateInput as any).nanoseconds === "number"
  ) {
    // Handle serialized Timestamp
    d = new Date((dateInput as any).seconds * 1000);
  } else if (typeof dateInput === "string") {
    if (/^\d{4}-\d{2}-\d{2}$/.test(dateInput)) {
      const [year, month, day] = dateInput.split("-").map(Number);
      d = new Date(year, month - 1, day);
    } else {
      d = new Date(dateInput);
    }
  } else {
    return NaN; // Unknown type
  }
  return d.getTime();
};

export default function PromiseCard({ promise }: { promise: PromiseListing }) {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [showProgressTooltip, setShowProgressTooltip] = useState(false);
  const [showImpactTooltip, setShowImpactTooltip] = useState(false);
  const [showAlignmentTooltip, setShowAlignmentTooltip] = useState(false);
  const [showProgressModal, setShowProgressModal] = useState(false);

  // const [loadedEvidence, setLoadedEvidence] = useState<EvidenceItem[]>(
  //   promise.evidence || [],
  // );

  // const [isLoadingEvidence, setIsLoadingEvidence] = useState(false);

  // const { sessionId } = useDepartments();

  // useEffect(() => {
  //   const loadEvidence = async () => {
  //     if (!promise?.linked_evidence_ids?.length) {
  //       setLoadedEvidence([]);
  //       return;
  //     }

  //     setIsLoadingEvidence(true);
  //     try {
  //       const sessionDates = sessionId
  //         ? await fetchParliamentSessionDates(sessionId)
  //         : null;

  //       const response = await fetch("/api/evidence", {
  //         method: "POST",
  //         headers: { "Content-Type": "application/json" },
  //         body: JSON.stringify({
  //           evidenceIds: promise.linked_evidence_ids,
  //           sessionsStartDate: sessionDates?.sessionStartDate,
  //           sessionEndDate: sessionDates?.sessionEndDate,
  //         }),
  //       });

  //       if (!response.ok) {
  //         throw new Error(`Evidence API error: ${response.statusText}`);
  //       }

  //       const data = await response.json();
  //       setLoadedEvidence(data.evidenceItems || []);
  //     } catch (error) {
  //       console.error("Error loading evidence for promise:", error);
  //       setLoadedEvidence([]);
  //     } finally {
  //       setIsLoadingEvidence(false);
  //     }
  //   };

  //   loadEvidence();
  // }, [promise?.linked_evidence_ids, sessionId]);

  // Create a combined promise object with loaded evidence for the timeline
  // const promiseWithEvidence = useMemo(() => {
  //   if (!promise) return null;

  //   return {
  //     ...promise,
  //     evidence: loadedEvidence,
  //   };
  // }, [promise, loadedEvidence]);

  // console.log({ evidence: promise.evidence });
  // Find the most recent evidence date for "Last Update"
  // let lastUpdateDate: string | null = null;
  // if (!!promiseWithEvidence && promiseWithEvidence.evidence.length > 0) {
  //   const sorted = promiseWithEvidence.evidence.sort((a, b) => {
  //     const dateAMillis = getDateMillis(a.evidence_date);
  //     const dateBMillis = getDateMillis(b.evidence_date);

  //     if (isNaN(dateAMillis) && isNaN(dateBMillis)) return 0;
  //     if (isNaN(dateAMillis)) return 1; // Treat NaN as earlier (pushes it to the end of a descending sort)
  //     if (isNaN(dateBMillis)) return -1; // Treat NaN as earlier

  //     return dateBMillis - dateAMillis; // Descending
  //   });
  //   if (sorted[0]) {
  //     lastUpdateDate = formatDate(sorted[0].evidence_date);
  //   }
  // }

  // const handleCardClick = () => {
  //   setIsModalOpen(true);
  // };

  // Progress Indicator
  const progressScore = promise.progress_score || 0; // 1-5
  const progressSummary =
    promise.progress_summary || "No progress summary available.";
  const isDelivered = progressScore === 5;

  // Human-friendly progress tooltip
  let progressTooltip = "";
  if (progressScore === 0) progressTooltip = "No progress made yet";
  else if (progressScore === 1) progressTooltip = "Early progress made";
  else if (progressScore === 2) progressTooltip = "Some progress made";
  else if (progressScore === 3) progressTooltip = "Good progress made";
  else if (progressScore === 4) progressTooltip = "Almost complete";
  else if (progressScore === 5) progressTooltip = "Complete";

  // Impact Indicator
  const impactRankRaw = promise.bc_promise_rank ?? "";
  const impactRationale =
    promise.bc_promise_rank_rationale || "No rationale provided.";
  let impactIcon = null;
  let impactRankStr = String(impactRankRaw).toLowerCase();
  let impactRankNum = Number(impactRankRaw);
  let filledBars = 0;
  let impactLevelLabel = "";
  if (impactRankStr === "strong" || impactRankNum >= 8) {
    filledBars = 3;
    impactLevelLabel = "High Impact";
  } else if (
    impactRankStr === "medium" ||
    (impactRankNum >= 5 && impactRankNum < 8)
  ) {
    filledBars = 2;
    impactLevelLabel = "Medium Impact";
  } else if (
    impactRankStr === "weak" ||
    (impactRankNum > 0 && impactRankNum < 5)
  ) {
    filledBars = 1;
    impactLevelLabel = "Low Impact";
  }
  let impactPillBg = "";
  let impactBarColor = "";
  if (filledBars === 3) {
    impactPillBg = "bg-green-50"; // same as alignment
    impactBarColor = "#166534"; // dark green
  } else if (filledBars === 2) {
    impactPillBg = "bg-yellow-50"; // very light yellow
    impactBarColor = "#ca8a04"; // burnt yellow (yellow-700)
  } else if (filledBars === 1) {
    impactPillBg = "bg-gray-100"; // light gray
    impactBarColor = "#374151"; // dark gray
  }
  // SVG for network bars
  impactIcon = (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
    >
      <rect
        x="1.5"
        y="8"
        width="1.5"
        height="4.5"
        rx="0.75"
        fill={filledBars >= 1 ? impactBarColor : "#d1d5db"}
      />
      <rect
        x="5.5"
        y="5.5"
        width="1.5"
        height="7"
        rx="0.75"
        fill={filledBars >= 2 ? impactBarColor : "#d1d5db"}
      />
      <rect
        x="9.5"
        y="3"
        width="1.5"
        height="9.5"
        rx="0.75"
        fill={filledBars >= 3 ? impactBarColor : "#d1d5db"}
      />
    </svg>
  );
  const impactTooltip = `${impactLevelLabel}${impactLevelLabel ? ": " : ""}${impactRationale}`;

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
      alignmentIcon = <TrendingUpIcon className="w-3.5 h-3.5 text-green-600" />;
      break;
    case "neutral":
      alignmentLabel = "Neutral";
      alignmentColor = "text-gray-600";
      alignmentBg = "bg-gray-100";
      alignmentIcon = <MinusIcon className="w-3.5 h-3.5 text-gray-400" />;
      break;
    case "negative":
      alignmentLabel = "Not Aligned";
      alignmentColor = "text-red-700";
      alignmentBg = "bg-red-50";
      alignmentIcon = (
        <TrendingUpIcon
          className="w-3.5 h-3.5 text-red-600"
          style={{ transform: "scaleY(-1)" }}
        />
      );
      break;
    default:
      alignmentLabel = "Unknown";
      alignmentColor = "text-gray-400";
      alignmentBg = "bg-gray-50";
      alignmentIcon = <MinusIcon className="w-3.5 h-3.5 text-gray-400" />;
  }
  const alignmentTooltip = `${alignmentLabel} with Build Canada`;

  // Progress dot color scale (red to green)
  const dotColors = [
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

  // Check if the promise is overdue (more than 90 days since 2025-05-27)
  const targetDate = new Date("2025-05-27");
  const today = new Date();
  const daysSinceTarget = Math.floor(
    (today.getTime() - targetDate.getTime()) / (1000 * 60 * 60 * 24),
  );
  const isOverdue = daysSinceTarget > 90;

  return (
    <>
      <div
        className="bg-white border border-[#cdc4bd] flex flex-col cursor-pointer focus:outline-none focus:ring-2 focus:ring-gray-300 group relative"
        tabIndex={0}
        aria-label={promise.text}
        // onClick={handleCardClick}
        // onKeyDown={(e) => {
        //   if (e.key === "Enter" || e.key === " ") handleCardClick();
        // }}
      >
        <div className="p-6">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
            {/* Progress Indicator - Column 1 */}
            <div className="flex-shrink-0 flex flex-row items-center gap-2 w-[170px]">
              <div
                className="relative w-6 h-6 cursor-pointer focus:outline-none"
                onMouseEnter={() => setShowProgressTooltip(true)}
                onMouseLeave={() => setShowProgressTooltip(false)}
                onFocus={() => setShowProgressTooltip(true)}
                onBlur={() => setShowProgressTooltip(false)}
                tabIndex={0}
                aria-label={`Commitment Progress`}
                onClick={(e) => {
                  e.stopPropagation();
                  setShowProgressModal(true);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.stopPropagation();
                    setShowProgressModal(true);
                  }
                }}
              >
                <svg className="w-6 h-6" viewBox="0 0 24 24">
                  {/* Full colored circle as background - only if progress > 0 */}
                  {progressScore > 0 && (
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      fill={getPieColor(progressScore)}
                      stroke={getPieColor(progressScore)}
                      strokeWidth="2"
                    />
                  )}
                  {/* White arc for incomplete portion (only if not complete) */}
                  {progressScore < 5 && progressScore > 0 && (
                    <path
                      d={getPieArcPath(
                        12,
                        12,
                        10,
                        0,
                        (1 - progressScore / 5) * 360,
                      )}
                      fill="#fff"
                    />
                  )}
                  {/* Outline circle */}
                  <circle
                    cx="12"
                    cy="12"
                    r="10"
                    fill="none"
                    stroke={
                      progressScore === 0
                        ? isOverdue
                          ? "#ef4444"
                          : "#d3c7b9"
                        : getPieColor(progressScore)
                    }
                    strokeWidth="2"
                  />
                </svg>
                {showProgressTooltip && (
                  <div className="absolute z-20 p-2 bg-white border border-gray-200 shadow-lg text-sm max-w-xs top-full mt-1 left-1/2 -translate-x-1/2 animate-fade-in whitespace-nowrap">
                    {progressTooltip}
                  </div>
                )}
              </div>
              <div className="flex flex-col items-start justify-start">
                <span className="text-xs font-medium text-gray-700">
                  {progressScore === 0
                    ? "Not started"
                    : progressScore === 5
                      ? "Complete"
                      : "In Progress"}
                </span>
                <span className="text-xs text-gray-400">
                  {promise.last_evidence_at
                    ? `Last update ${new Date(promise.last_evidence_at).toLocaleString()}`
                    : "No update yet"}
                </span>
              </div>
            </div>
            {/* Title and Description - Column 2 */}
            <div className="md:flex-1">
              <div className="text-lg font-semibold leading-snug">
                {promise.concise_title}
              </div>
              <div className="text-sm text-gray-600 line-clamp-2">
                {promise.description}
              </div>
            </div>
            {/* Impact and Alignment - Column 3 */}
            <div className="flex gap-2 md:w-auto md:flex-shrink-0 justify-start md:justify-end">
              {/* Impact pill */}
              {impactIcon && (
                <div className="relative">
                  <div
                    className={`flex items-center justify-center w-6 h-6 rounded-full ${impactPillBg} cursor-help`}
                    onMouseEnter={() => setShowImpactTooltip(true)}
                    onMouseLeave={() => setShowImpactTooltip(false)}
                    onFocus={() => setShowImpactTooltip(true)}
                    onBlur={() => setShowImpactTooltip(false)}
                    tabIndex={0}
                    aria-label={`Impact`}
                  >
                    {impactIcon}
                  </div>
                  {showImpactTooltip && (
                    <div className="absolute w-64 z-20 p-2 bg-white border border-gray-200 shadow-lg text-sm top-full mt-1 right-0 animate-fade-in">
                      {impactTooltip}
                    </div>
                  )}
                </div>
              )}
              {/* Alignment pill */}
              <div className="relative">
                <div
                  className={`flex items-center justify-center w-6 h-6 rounded-full ${alignmentBg} ${alignmentColor} cursor-help`}
                  onMouseEnter={() => setShowAlignmentTooltip(true)}
                  onMouseLeave={() => setShowAlignmentTooltip(false)}
                  onFocus={() => setShowAlignmentTooltip(true)}
                  onBlur={() => setShowAlignmentTooltip(false)}
                  tabIndex={0}
                  aria-label={`Alignment: ${alignmentLabel}`}
                >
                  {alignmentIcon}
                </div>
                {showAlignmentTooltip && (
                  <div className="absolute w-48 z-20 p-2 bg-white border border-gray-200 shadow-lg text-sm top-full mt-1 right-0 animate-fade-in">
                    {alignmentTooltip}
                  </div>
                )}
              </div>
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
            <div className="text-gray-800 whitespace-pre-line">
              {progressSummary}
            </div>
          </div>
        </div>
      )}
      {/* <PromiseModal
        promise={promiseWithEvidence}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      /> */}
    </>
  );
}
