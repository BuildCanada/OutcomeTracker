"use client";

import { useState, useRef } from "react";
import Link from "next/link";
import type { CommitmentListing, MinistryGroup } from "@/lib/commitment-types";

const STATUS_COLOR: Record<string, string> = {
  not_started: "bg-gray-300",
  in_progress: "bg-amber-400",
  completed: "bg-[#8b2332]",
  abandoned: "bg-black",
};

const STATUS_LABEL: Record<string, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  completed: "Completed",
  abandoned: "Abandoned",
};

const LEGEND_STATUSES = [
  "not_started",
  "in_progress",
  "completed",
  "abandoned",
];
const WAFFLE_ORDER = ["completed", "in_progress", "not_started", "abandoned"];

export function MinistryGrid({ ministries }: { ministries: MinistryGroup[] }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {ministries.map((m) => (
        <MinistryCard key={m.name} ministry={m} />
      ))}
    </div>
  );
}

function MinistryCard({ ministry }: { ministry: MinistryGroup }) {
  const total = ministry.commitments.length;
  const counts = ministry.statusCounts;
  const minister = ministry.minister;

  const waffleRank = Object.fromEntries(WAFFLE_ORDER.map((s, i) => [s, i]));
  const sorted = [...ministry.commitments].sort(
    (a, b) => (waffleRank[a.status] ?? 99) - (waffleRank[b.status] ?? 99),
  );

  return (
    <div className="border border-[#cdc4bd] bg-white p-5">
      {/* Header: photo + name + count */}
      <div className="flex items-center gap-3 mb-3">
        {minister && (
          <div className="flex-shrink-0 w-12 h-12 bg-gray-100 overflow-hidden">
            {minister.avatar_url ? (
              <img
                src={minister.avatar_url}
                alt={`${minister.first_name} ${minister.last_name}`}
                className="w-full h-full object-cover object-[center_25%]"
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm font-semibold">
                {minister.first_name[0]}
                {minister.last_name[0]}
              </div>
            )}
          </div>
        )}
        <div className="flex-1 min-w-0">
          <Link
            href={`/ministries/${ministry.slug}`}
            className="text-base font-semibold hover:text-[#8b2332] transition-colors leading-tight block"
          >
            {ministry.name}
          </Link>
          {minister && (
            <p className="text-xs text-gray-500 leading-tight mt-0.5">
              {minister.first_name} {minister.last_name}
            </p>
          )}
          <span className="lg:hidden text-xs text-gray-500 font-mono mt-0.5 block">
            {total} commitment{total !== 1 ? "s" : ""}
          </span>
        </div>
        <span className="hidden lg:block flex-shrink-0 text-xs text-gray-500 font-mono self-start">
          {total} commitment{total !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Waffle chart */}
      <div className="flex flex-wrap gap-0.5 mb-3">
        {sorted.map((c) => (
          <CommitmentSquare key={c.id} commitment={c} />
        ))}
      </div>

      {/* Legend */}
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-gray-500">
        {LEGEND_STATUSES.map((s) => {
          const count = counts[s] ?? 0;
          if (count === 0) return null;
          return (
            <span key={s}>
              {STATUS_LABEL[s]}: {count}
            </span>
          );
        })}
      </div>
    </div>
  );
}

function CommitmentSquare({
  commitment: c,
}: {
  commitment: CommitmentListing;
}) {
  const [show, setShow] = useState(false);
  const timeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleEnter = () => {
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    setShow(true);
  };

  const handleLeave = () => {
    timeoutRef.current = setTimeout(() => setShow(false), 150);
  };

  return (
    <div
      className="relative"
      style={{ zIndex: show ? 20 : undefined }}
      onMouseEnter={handleEnter}
      onMouseLeave={handleLeave}
    >
      <Link
        href={`/commitments/${c.id}`}
        className={`block w-3 h-3 ${STATUS_COLOR[c.status] ?? "bg-gray-200"} hover:ring-2 hover:ring-[#8b2332] hover:ring-offset-1 transition-shadow relative z-10`}
      />
      {show && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 w-64 bg-white border border-gray-200 shadow-lg rounded-md p-3 text-xs pointer-events-none z-30">
          <p className="font-semibold text-gray-900 leading-snug mb-1.5">
            {c.title}
          </p>
          <div className="space-y-0.5 text-gray-500">
            <p>
              <span className="text-gray-400">Promised:</span>{" "}
              {c.date_promised
                ? new Date(c.date_promised + "T00:00:00").toLocaleDateString(
                    "en-CA",
                    {
                      year: "numeric",
                      month: "short",
                      day: "numeric",
                    },
                  )
                : "\u2014"}
            </p>
            <p>
              <span className="text-gray-400">Status:</span>{" "}
              {STATUS_LABEL[c.status] ?? c.status}
            </p>
          </div>
          <div className="absolute left-1/2 -translate-x-1/2 top-full w-2 h-2 bg-white border-r border-b border-gray-200 -rotate-45 -mt-1" />
        </div>
      )}
    </div>
  );
}
