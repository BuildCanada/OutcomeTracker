"use client";

import { useCallback, useRef, useState } from "react";
import useSWR from "swr";
import { Search, ChevronUp, ChevronDown } from "lucide-react";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import type {
  CommitmentListing,
  CommitmentsResponse,
} from "@/lib/commitment-types";
import Link from "next/link";

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  partially_implemented: "Partially Implemented",
  implemented: "Implemented",
  abandoned: "Abandoned",
  superseded: "Superseded",
};

const STATUS_COLORS: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-700",
  in_progress: "bg-amber-100 text-amber-800",
  partially_implemented: "bg-orange-100 text-orange-800",
  implemented: "bg-green-100 text-green-800",
  abandoned: "bg-red-100 text-red-800",
  superseded: "bg-purple-100 text-purple-800",
};

const TYPE_LABELS: Record<string, string> = {
  legislative: "Legislative",
  spending: "Spending",
  procedural: "Procedural",
  institutional: "Institutional",
  diplomatic: "Diplomatic",
  aspirational: "Aspirational",
  outcome: "Outcome",
};

function buildQueryString(params: Record<string, string | number>) {
  const searchParams = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== "" && value !== "all") {
      searchParams.set(key, String(value));
    }
  }
  return searchParams.toString();
}

export default function CommitmentsPage() {
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [commitmentType, setCommitmentType] = useState("all");
  const [sort, setSort] = useState("");
  const [direction, setDirection] = useState("desc");
  const [page, setPage] = useState(1);
  const perPage = 50;

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const handleSearchChange = useCallback((value: string) => {
    setSearch(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      setDebouncedSearch(value);
      setPage(1);
    }, 300);
  }, []);

  const qs = buildQueryString({
    q: debouncedSearch,
    status,
    commitment_type: commitmentType,
    sort,
    direction,
    page,
    per_page: perPage,
  });

  const { data, isLoading } = useSWR<CommitmentsResponse>(
    `/tracker/api/v1/commitments.json${qs ? `?${qs}` : ""}`,
  );

  const commitments = data?.commitments ?? [];
  const totalCount = data?.meta?.total_count ?? 0;
  const totalPages = Math.ceil(totalCount / perPage);

  function toggleSort(field: string) {
    if (sort === field) {
      setDirection((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSort(field);
      setDirection("desc");
    }
    setPage(1);
  }

  function SortIcon({ field }: { field: string }) {
    if (sort !== field) return null;
    return direction === "asc" ? (
      <ChevronUp className="w-3 h-3 inline ml-0.5" />
    ) : (
      <ChevronDown className="w-3 h-3 inline ml-0.5" />
    );
  }

  return (
    <div>
      <h2 className="text-3xl font-bold mb-6">Explore Commitments</h2>

      {/* Search + Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <div className="relative flex-1 min-w-[200px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
          <Input
            className="pl-9 rounded-none"
            placeholder="Search commitments..."
            value={search}
            onChange={(e) => handleSearchChange(e.target.value)}
          />
        </div>

        <Select
          value={status}
          onValueChange={(v) => {
            setStatus(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[180px] text-xs rounded-none">
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent className="rounded-none">
            <SelectItem value="all">All Statuses</SelectItem>
            {Object.entries(STATUS_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select
          value={commitmentType}
          onValueChange={(v) => {
            setCommitmentType(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[180px] text-xs rounded-none">
            <SelectValue placeholder="Type" />
          </SelectTrigger>
          <SelectContent className="rounded-none">
            <SelectItem value="all">All Types</SelectItem>
            {Object.entries(TYPE_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Sort bar */}
      <div className="flex items-center gap-4 text-xs font-mono text-gray-500 mb-4 border-b border-[#d3c7b9] pb-2">
        <span className="mr-2">Sort by:</span>
        {[
          { field: "title", label: "Title" },
          { field: "status", label: "Status" },
          { field: "date_promised", label: "Date Promised" },
          { field: "last_assessed_at", label: "Last Assessed" },
        ].map(({ field, label }) => (
          <button
            key={field}
            onClick={() => toggleSort(field)}
            className={`hover:text-gray-900 transition-colors ${sort === field ? "text-gray-900 font-semibold" : ""}`}
          >
            {label}
            <SortIcon field={field} />
          </button>
        ))}
      </div>

      {/* Results count */}
      <p className="text-sm text-gray-500 mb-4">
        {isLoading
          ? "Loading..."
          : `${totalCount} commitment${totalCount !== 1 ? "s" : ""} found`}
      </p>

      {/* Commitment list */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-24 w-full" />
          ))}
        </div>
      ) : commitments.length === 0 ? (
        <p className="text-gray-600 italic py-8">
          No commitments match your search and filters.
        </p>
      ) : (
        <div className="space-y-3">
          {commitments.map((c: CommitmentListing) => (
            <CommitmentRow key={c.id} commitment={c} />
          ))}
        </div>
      )}

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4 p-4 border-t border-[#d3c7b9]">
          <div className="text-sm text-gray-600">
            Showing {(page - 1) * perPage + 1} to{" "}
            {Math.min(page * perPage, totalCount)} of {totalCount}
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-3 py-1 text-sm border border-[#d3c7b9] hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Previous
            </button>
            <span className="px-3 py-1 text-sm">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page >= totalPages}
              className="px-3 py-1 text-sm border border-[#d3c7b9] hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

function CommitmentRow({ commitment: c }: { commitment: CommitmentListing }) {
  const statusLabel = STATUS_LABELS[c.status] ?? c.status;
  const statusColor = STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-700";
  const typeLabel = TYPE_LABELS[c.commitment_type] ?? c.commitment_type;

  return (
    <Link
      href={`/v2/commitments/${c.id}`}
      className="block bg-white border border-[#cdc4bd] hover:border-gray-400 transition-colors"
    >
      <div className="p-5">
        <div className="flex flex-col md:flex-row md:items-start gap-3">
          {/* Status + Type pills */}
          <div className="flex flex-wrap gap-2 md:w-[200px] md:flex-shrink-0">
            <span
              className={`inline-flex items-center px-2.5 py-0.5 text-xs font-medium ${statusColor}`}
            >
              {statusLabel}
            </span>
            <span className="inline-flex items-center px-2.5 py-0.5 text-xs font-medium bg-blue-50 text-blue-700">
              {typeLabel}
            </span>
          </div>

          {/* Title + Description */}
          <div className="flex-1 min-w-0">
            <h3 className="text-base font-semibold text-gray-900 leading-snug">
              {c.title}
            </h3>
            <p className="text-sm text-gray-600 mt-1 line-clamp-2">
              {c.description}
            </p>
          </div>

          {/* Meta */}
          <div className="md:w-[180px] md:flex-shrink-0 text-right space-y-1">
            {c.policy_area && (
              <p className="text-xs text-gray-500">{c.policy_area.name}</p>
            )}
            {c.lead_department && (
              <p className="text-xs text-gray-400">
                {c.lead_department.display_name}
              </p>
            )}
            {c.date_promised && (
              <p className="text-xs text-gray-400">
                Promised:{" "}
                {new Date(c.date_promised + "T00:00:00").toLocaleDateString(
                  "en-CA",
                  {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  },
                )}
              </p>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
