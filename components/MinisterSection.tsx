"use client";

import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { Minister, PromiseListing } from "@/lib/types";
import PromiseCard, { getProgressTooltip } from "./PromiseCard";
import { useState } from "react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";

const DEFAULT_MINISTER_NAME = "Minister Information Not Available";
const DEFAULT_AVATAR_FALLBACK_INITIALS = "N/A";

const getFallbackInitials = (name: string) => {
  if (name === DEFAULT_MINISTER_NAME) return DEFAULT_AVATAR_FALLBACK_INITIALS;
  return name
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase();
};

export function Commitments({
  promises,
  departmentSlug,
}: {
  promises: PromiseListing[];
  departmentSlug: string;
}) {
  const [progressFilter, setProgressFilter] = useState<string>("all");
  const [impactFilter, setImpactFilter] = useState<string>("all");
  const [alignmentFilter, setAlignmentFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<string>("default");

  // pagination
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [promisesPerPage] = useState<number>(10);
  const startIndex = (currentPage - 1) * promisesPerPage;
  const endIndex = startIndex + promisesPerPage;
  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
  };

  // Filter promises based on selected filters
  const sortedPromises = sortPromises(
    promises,
    progressFilter,
    impactFilter,
    alignmentFilter,
    sortBy,
  );

  const currentPagePromises = sortedPromises.slice(startIndex, endIndex);
  const totalPromises = sortedPromises.length;

  return (
    <div className="my-8">
      <div className="flex flex-wrap gap-2 justify-between items-center mb-6">
        <h3 className="text-2xl font-semibold">Commitments</h3>
        <div className="flex flex-wrap gap-4">
          <Select value={progressFilter} onValueChange={setProgressFilter}>
            <SelectTrigger className="w-[180px] text-xs rounded-none">
              <SelectValue placeholder="Progress" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all">All Progress</SelectItem>
              <SelectItem value="complete">Complete</SelectItem>
              <SelectItem value="in_progress">In Progress</SelectItem>
              <SelectItem value="not_started">Not Started</SelectItem>
            </SelectContent>
          </Select>

          <Select value={impactFilter} onValueChange={setImpactFilter}>
            <SelectTrigger className="w-[180px] text-xs rounded-none">
              <SelectValue placeholder="Impact" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all">All Impact</SelectItem>
              <SelectItem value="high">High Impact</SelectItem>
              <SelectItem value="medium">Medium Impact</SelectItem>
              <SelectItem value="low">Low Impact</SelectItem>
            </SelectContent>
          </Select>

          <Select value={alignmentFilter} onValueChange={setAlignmentFilter}>
            <SelectTrigger className="w-[180px] text-xs rounded-none">
              <SelectValue placeholder="Alignment" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="all">All Alignment</SelectItem>
              <SelectItem value="aligned">Aligned</SelectItem>
              <SelectItem value="neutral">Neutral</SelectItem>
              <SelectItem value="not_aligned">Not Aligned</SelectItem>
            </SelectContent>
          </Select>

          <Select value={sortBy} onValueChange={setSortBy}>
            <SelectTrigger className="w-[180px] text-xs rounded-none">
              <SelectValue placeholder="Sort by" />
            </SelectTrigger>
            <SelectContent className="rounded-none">
              <SelectItem value="default">Default Sort</SelectItem>
              <SelectItem value="last_updated">Last Updated</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>

      {currentPagePromises && currentPagePromises.length > 0 ? (
        <div className="grid grid-cols-1 gap-6">
          {currentPagePromises.map((promise: PromiseListing) => (
            <PromiseCard
              key={promise.id}
              promise={promise}
              departmentSlug={departmentSlug}
            />
          ))}
          <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4 p-4 border-t border-[#d3c7b9]">
            {/* Page Info */}
            <div className="text-sm text-gray-600">
              Showing {(currentPage - 1) * promisesPerPage + 1} to{" "}
              {Math.min(currentPage * promisesPerPage, totalPromises)} of{" "}
              {totalPromises} promises
            </div>

            {/* Navigation Buttons */}
            {totalPromises > promisesPerPage && (
              <div className="flex items-center gap-2">
                <button
                  onClick={() => handlePageChange(currentPage - 1)}
                  disabled={currentPage === 1}
                  className="px-3 py-1 text-sm border border-[#d3c7b9] hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Previous
                </button>

                <span className="px-3 py-1 text-sm">
                  Page {currentPage} of{" "}
                  {Math.ceil(totalPromises / promisesPerPage)}
                </span>

                <button
                  onClick={() => handlePageChange(currentPage + 1)}
                  disabled={
                    currentPage >= Math.ceil(totalPromises / promisesPerPage)
                  }
                  className="px-3 py-1 text-sm border border-[#d3c7b9] hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        </div>
      ) : (
        <p className="text-gray-600 italic">
          No commitments match the selected filters.
        </p>
      )}
    </div>
  );
}

function sortPromises(
  promises: PromiseListing[],
  progressFilter: string,
  impactFilter: string,
  alignmentFilter: string,
  sortBy: string,
) {
  const filteredPromises = promises.filter((promise) => {
    // Progress filter
    if (progressFilter !== "all") {
      const progressScore = promise.progress_score || 1;
      if (progressFilter === "complete" && progressScore !== 5) return false;
      if (
        progressFilter === "in_progress" &&
        (progressScore === 1 || progressScore === 5)
      )
        return false;
      if (progressFilter === "not_started" && progressScore !== 1) return false;
    }

    // Impact filter
    if (impactFilter !== "all") {
      const impactRank = promise.bc_promise_rank?.toLowerCase() || "";
      const impactNum = Number(promise.bc_promise_rank) || 0;

      if (
        impactFilter === "high" &&
        !(impactRank === "strong" || impactNum >= 8)
      )
        return false;
      if (
        impactFilter === "medium" &&
        !(impactRank === "medium" || (impactNum >= 5 && impactNum < 8))
      )
        return false;
      if (
        impactFilter === "low" &&
        !(impactRank === "low" || (impactNum > 0 && impactNum < 5))
      )
        return false;
    }

    // Alignment filter
    if (alignmentFilter !== "all") {
      const direction = promise.bc_promise_direction?.toLowerCase() || "";
      if (alignmentFilter === "aligned" && direction !== "positive")
        return false;
      if (alignmentFilter === "neutral" && direction !== "neutral")
        return false;
      if (alignmentFilter === "not_aligned" && direction !== "negative")
        return false;
    }

    return true;
  });

  // Sort promises based on selected sort option
  const sortedPromises = [...filteredPromises].sort((a, b) => {
    if (sortBy === "last_updated") {
      // Sort by last evidence date (descending)
      const lastDateA = getLastEvidenceDate(a);
      const lastDateB = getLastEvidenceDate(b);
      return lastDateB - lastDateA;
    } else {
      // Default sort: progress score (descending) -> impact (descending) -> last evidence date (descending)
      const progressA = a.progress_score || 1;
      const progressB = b.progress_score || 1;
      if (progressA !== progressB) return progressB - progressA;

      const impactA = getImpactScore(a);
      const impactB = getImpactScore(b);
      if (impactA !== impactB) return impactB - impactA;

      const lastDateA = getLastEvidenceDate(a);
      const lastDateB = getLastEvidenceDate(b);
      return lastDateB - lastDateA;
    }
  });
  return sortedPromises;
}

export function MinisterHeader({
  minister,
  promises,
}: {
  minister: Minister;
  promises: PromiseListing[];
}) {
  const ministerName = `${minister.first_name} ${minister.last_name}`;
  const ministerTitle = minister.title;
  const avatarUrl = minister.avatar_url;

  return (
    <div className="flex flex-col md:flex-row md:items-start mb-8 w-full">
      <div className="flex items-center mb-4 md:mb-0">
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
            <span className="text-2xl text-gray-500">
              {getFallbackInitials(ministerName)}
            </span>
          </div>
        )}
        <div>
          <h2 className="text-3xl">{ministerName}</h2>
          <p className="mt-1 text-sm font-mono">{ministerTitle}</p>
          <div className="mt-1">
            <ProgressIndicator promises={promises} />
          </div>
        </div>
      </div>
    </div>
  );
}

const getLastEvidenceDate = (promise: PromiseListing): number => {
  if (!promise.last_evidence_date) return 0;
  return new Date(promise.last_evidence_date).getTime();
};

const getImpactScore = (promise: PromiseListing): number => {
  const impactRank = promise.bc_promise_rank?.toLowerCase() || "";
  const impactNum = Number(promise.bc_promise_rank) || 0;

  if (impactRank === "strong" || impactNum >= 8) return 3;
  if (impactRank === "medium" || (impactNum >= 5 && impactNum < 8)) return 2;
  if (impactRank === "low" || (impactNum > 0 && impactNum < 5)) return 1;
  return 0;
};

const progressColor = (score: number | null): string => {
  if (score === null) return "bg-gray-300";
  if (score === 1) return "bg-gray-300";
  if (score === 2) return "bg-amber-300";
  if (score === 3) return "bg-orange-300";
  if (score === 4) return "bg-lime-400";
  if (score === 5) return "bg-green-600";
  return "bg-green-500";
};

const ProgressIndicator = ({ promises }: { promises: PromiseListing[] }) => {
  const [hoveredIndex, setHoveredIndex] = useState<number | null>(null);

  // Sort promises by progress score (lowest to highest)
  promises = [...promises].sort((a, b) => {
    const progressA = a.progress_score || 0;
    const progressB = b.progress_score || 0;
    return progressA - progressB;
  });

  return (
    <div className="w-full md:w-72">
      <div className="flex h-4 w-full rounded border border-gray-200">
        {promises.map((p, index) => {
          // Add a tiny right border except for the last chunk (to view each promise easily)
          const border =
            index < promises.length - 1 ? "border-r border-white" : "";

          return (
            <div
              key={p.id}
              className={`h-full flex-1 min-w-0 ${progressColor(p.progress_score)} ${border} cursor-help relative`}
              style={{ minWidth: 0 }}
              onMouseEnter={() => setHoveredIndex(index)}
              onMouseLeave={() => setHoveredIndex(null)}
            >
              {/* Tooltip on hover */}
              {hoveredIndex === index && (
                <div className="absolute w-min z-20 p-2 bg-white border border-gray-200 shadow-lg text-sm top-full mt-1 right-0">
                  <div className="font-medium whitespace-nowrap">
                    {p.concise_title}
                  </div>
                  <div>
                    {getProgressTooltip(p.progress_score ?? 1)} (
                    {p.progress_score ?? 1}/5)
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
