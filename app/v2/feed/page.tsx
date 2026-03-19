"use client";

import { useState } from "react";
import useSWR from "swr";
import Link from "next/link";
import { Rss, ArrowRightLeft, AlertTriangle, Clock } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { FeedItem, FeedResponse } from "@/lib/commitment-types";

const EVENT_TYPE_LABELS: Record<string, string> = {
  event: "Event",
  status_change: "Status Change",
  drift: "Drift",
};

const EVENT_TYPE_STYLES: Record<string, { badge: string; dot: string }> = {
  event: {
    badge: "bg-blue-50 text-blue-700",
    dot: "bg-blue-500",
  },
  status_change: {
    badge: "bg-[#faf0f1] text-[#8b2332]",
    dot: "bg-[#8b2332]",
  },
  drift: {
    badge: "bg-orange-50 text-orange-700",
    dot: "bg-orange-500",
  },
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

function formatDate(dateStr: string): string {
  const d = new Date(dateStr.includes("T") ? dateStr : dateStr + "T00:00:00");
  return d.toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export default function FeedPage() {
  const [eventType, setEventType] = useState("all");
  const [since, setSince] = useState("");
  const [until, setUntil] = useState("");
  const [page, setPage] = useState(1);
  const perPage = 50;

  const qs = buildQueryString({
    event_type: eventType,
    since,
    until,
    page,
    per_page: perPage,
  });

  const { data, isLoading } = useSWR<FeedResponse>(
    `/tracker/api/v1/feed.json${qs ? `?${qs}` : ""}`,
  );

  const feedItems = data?.feed_items ?? [];
  const totalCount = data?.meta?.total_count ?? 0;
  const totalPages = Math.ceil(totalCount / perPage);

  const rssUrl = `/tracker/api/v1/feed.rss${qs ? `?${qs}` : ""}`;

  return (
    <div>
      <div className="flex items-start justify-between mb-6">
        <div>
          <h2 className="text-3xl font-bold">Activity Feed</h2>
          <p className="text-sm text-gray-500 mt-1">
            Tracking changes across all government commitments
          </p>
        </div>
        <a
          href={rssUrl}
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-mono border border-[#d3c7b9] hover:bg-gray-50 transition-colors"
        >
          <Rss className="w-3.5 h-3.5" />
          RSS
        </a>
      </div>

      {/* Filters */}
      <div className="flex flex-wrap gap-3 mb-6">
        <Select
          value={eventType}
          onValueChange={(v) => {
            setEventType(v);
            setPage(1);
          }}
        >
          <SelectTrigger className="w-[180px] text-xs rounded-none">
            <SelectValue placeholder="Event Type" />
          </SelectTrigger>
          <SelectContent className="rounded-none">
            <SelectItem value="all">All Types</SelectItem>
            {Object.entries(EVENT_TYPE_LABELS).map(([value, label]) => (
              <SelectItem key={value} value={value}>
                {label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">From</span>
          <Input
            type="date"
            className="w-[160px] text-xs rounded-none"
            value={since}
            onChange={(e) => {
              setSince(e.target.value);
              setPage(1);
            }}
          />
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">Until</span>
          <Input
            type="date"
            className="w-[160px] text-xs rounded-none"
            value={until}
            onChange={(e) => {
              setUntil(e.target.value);
              setPage(1);
            }}
          />
        </div>

        {(eventType !== "all" || since || until) && (
          <button
            onClick={() => {
              setEventType("all");
              setSince("");
              setUntil("");
              setPage(1);
            }}
            className="px-3 py-1.5 text-xs text-gray-500 hover:text-gray-900 transition-colors"
          >
            Clear filters
          </button>
        )}
      </div>

      {/* Results count */}
      <p className="text-sm text-gray-500 mb-4">
        {isLoading
          ? "Loading..."
          : `${totalCount} item${totalCount !== 1 ? "s" : ""}`}
      </p>

      {/* Feed timeline */}
      {isLoading ? (
        <div className="space-y-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      ) : feedItems.length === 0 ? (
        <p className="text-gray-600 italic py-8">
          No activity found.
          {(eventType !== "all" || since || until) &&
            " Try adjusting your filters."}
        </p>
      ) : (
        <div className="relative">
          {/* Timeline line */}
          <div className="absolute left-[15px] top-2 bottom-2 w-0.5 bg-gray-200" />

          <div className="space-y-0">
            {feedItems.map((fi) => (
              <FeedItemRow key={fi.id} item={fi} />
            ))}
          </div>
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

function FeedItemIcon({ type }: { type: string }) {
  const size = "w-3.5 h-3.5";
  switch (type) {
    case "status_change":
      return <ArrowRightLeft className={`${size} text-green-600`} />;
    case "drift":
      return <AlertTriangle className={`${size} text-orange-600`} />;
    default:
      return <Clock className={`${size} text-blue-600`} />;
  }
}

function FeedItemRow({ item: fi }: { item: FeedItem }) {
  const style = EVENT_TYPE_STYLES[fi.event_type] ?? {
    badge: "bg-gray-100 text-gray-700",
    dot: "bg-gray-400",
  };

  return (
    <div className="relative flex gap-4 py-3">
      {/* Dot */}
      <div className="relative z-10 flex-shrink-0 w-[31px] flex justify-center">
        <div
          className={`w-7 h-7 rounded-full flex items-center justify-center ${
            fi.event_type === "event"
              ? "bg-blue-100"
              : fi.event_type === "status_change"
                ? "bg-[#faf0f1]"
                : fi.event_type === "drift"
                  ? "bg-orange-100"
                  : "bg-gray-100"
          }`}
        >
          <FeedItemIcon type={fi.event_type} />
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0 border border-[#cdc4bd] bg-white p-4 hover:border-gray-400 transition-colors">
        <div className="flex items-start justify-between gap-2 mb-1">
          <div className="flex items-center gap-2">
            <span
              className={`inline-flex items-center px-2 py-0.5 text-xs font-medium ${style.badge}`}
            >
              {EVENT_TYPE_LABELS[fi.event_type] ?? fi.event_type}
            </span>
            {fi.policy_area && (
              <span className="text-xs text-gray-400">
                {fi.policy_area.name}
              </span>
            )}
          </div>
          <span className="text-xs text-gray-400 flex-shrink-0 tabular-nums">
            {formatDate(fi.occurred_at)}
          </span>
        </div>

        <p className="text-sm font-medium text-gray-900">{fi.title}</p>

        {fi.summary && (
          <p className="text-xs text-gray-500 mt-1 line-clamp-2">
            {fi.summary}
          </p>
        )}

        <div className="mt-2">
          <Link
            href={`/v2/commitments/${fi.commitment.id}`}
            className="text-xs text-[#8b2332] hover:underline"
          >
            {fi.commitment.title}
          </Link>
        </div>
      </div>
    </div>
  );
}
