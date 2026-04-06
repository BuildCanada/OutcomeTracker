"use client";

import { useMemo, useState } from "react";
import useSWR from "swr";
import { useParams } from "next/navigation";
import Link from "next/link";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ChevronRight,
  ExternalLink,
  MessageSquare,
  Hammer,
  Clock,
  AlertTriangle,
  FileText,
  ArrowRightLeft,
  CheckCircle,
  BookOpen,
  Megaphone,
  Wrench,
} from "lucide-react";

// ── Types matching the API response from GET /commitments/:id ───────────────

interface Source {
  id: number;
  title: string;
  source_type: string;
  url?: string;
  date?: string;
}

interface CommitmentSource {
  id: number;
  section: string | null;
  reference: string | null;
  excerpt: string | null;
  relevance_note: string | null;
  created_at: string | null;
  source: Source;
}

interface CriterionAssessment {
  id: number;
  previous_status: string;
  new_status: string;
  evidence_notes: string | null;
  assessed_at: string;
  source?: Source;
}

interface Criterion {
  id: number;
  category: string;
  description: string;
  verification_method: string | null;
  status: string;
  evidence_notes: string | null;
  assessed_at: string | null;
  position: number;
  assessments: CriterionAssessment[];
}

interface TimelineEvent {
  id: number;
  event_type: string;
  action_type: string | null;
  title: string;
  description: string | null;
  occurred_at: string;
  source: Source | null;
}

interface Revision {
  id: number;
  title: string;
  description: string;
  original_text: string | null;
  target_date: string | null;
  change_summary: string | null;
  revision_date: string;
  source: Source | null;
}

interface StatusChange {
  id: number;
  previous_status: string;
  new_status: string;
  changed_at: string;
  reason: string | null;
  source: Source | null;
}

interface FeedItemData {
  id: number;
  event_type: string;
  title: string;
  summary: string | null;
  occurred_at: string;
  source?: Source;
  evidence_notes?: string;
}

interface CommitmentDetail {
  id: number;
  title: string;
  description: string;
  original_text: string | null;
  commitment_type: string;
  status: string;
  date_promised: string | null;
  target_date: string | null;
  last_assessed_at: string | null;
  region_code: string | null;
  party_code: string | null;
  metadata: Record<string, unknown> | null;
  policy_area: { id: number; name: string; slug: string } | null;
  government: { id: number; name: string; slug: string };
  parent: { id: number; title: string } | null;
  children: { id: number; title: string; status: string }[];
  sources: CommitmentSource[];
  criteria: Criterion[];
  departments: {
    id: number;
    display_name: string;
    is_lead: boolean;
  }[];
  lead_department: { id: number; display_name: string; slug: string } | null;
  timeline: TimelineEvent[];
  announcements: TimelineEvent[];
  actions: TimelineEvent[];
  revisions: Revision[];
  status_history: StatusChange[];
  recent_feed: FeedItemData[];
}

// ── Constants ───────────────────────────────────────────────────────────────

const STATUS_LABELS: Record<string, string> = {
  not_started: "Not Started",
  in_progress: "In Progress",
  completed: "Completed",
  broken: "Broken",
};

const STATUS_COLORS: Record<string, string> = {
  not_started: "bg-gray-100 text-gray-700",
  in_progress: "bg-amber-100 text-amber-800",
  completed: "bg-pine-50 text-pine-700",
  broken: "bg-[#faf0f1] text-[#8b2332]",
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

function formatDate(dateStr: string): string {
  const d = new Date(dateStr.includes("T") ? dateStr : dateStr + "T00:00:00");
  return d.toLocaleDateString("en-CA", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

// ── Page Component ──────────────────────────────────────────────────────────

export default function CommitmentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const { data: commitment, isLoading } = useSWR<CommitmentDetail>(
    `/tracker/api/v1/commitments/${id}.json`,
  );

  const TIMELINE_PAGE_SIZE = 10;
  const [timelinePage, setTimelinePage] = useState(1);

  // Build unified activity timeline — must be called before any early return
  const activityTimeline = useMemo(() => {
    if (!commitment) return [];

    const c = commitment;
    const sources = c.sources ?? [];
    const timeline = c.timeline ?? [];
    const statusHistory = c.status_history ?? [];
    const criteria = c.criteria ?? [];
    const revisions = c.revisions ?? [];

    const items: {
      date: string;
      type:
        | "promised"
        | "source"
        | "event_announcement"
        | "event_action"
        | "status_change"
        | "criterion"
        | "revision"
        | "assessed";
      title: string;
      detail?: string;
      url?: string;
      source?: Source | null;
      sourceType?: string;
    }[] = [];

    for (const cs of sources) {
      items.push({
        date: cs.source.date ?? c.date_promised ?? "",
        type: "source",
        title: cs.source.title,
        detail: cs.relevance_note ?? cs.excerpt ?? undefined,
        url: cs.source.url,
        sourceType: cs.source.source_type,
      });
    }

    for (const ev of timeline) {
      items.push({
        date: ev.occurred_at,
        type:
          ev.action_type === "concrete_action"
            ? "event_action"
            : "event_announcement",
        title: ev.title,
        detail: ev.description ?? undefined,
        source: ev.source,
      });
    }

    for (const sh of statusHistory) {
      const prev = STATUS_LABELS[sh.previous_status] ?? sh.previous_status;
      const next = STATUS_LABELS[sh.new_status] ?? sh.new_status;
      items.push({
        date: sh.changed_at,
        type: "status_change",
        title: `Status changed: ${prev} → ${next}`,
        detail: sh.reason ?? undefined,
        source: sh.source,
      });
    }

    for (const cr of criteria) {
      for (const a of cr.assessments ?? []) {
        const prev = a.previous_status?.replace("_", " ") ?? "unassessed";
        const next = a.new_status?.replace("_", " ") ?? "assessed";
        items.push({
          date: a.assessed_at,
          type: "criterion",
          title: `Criterion assessed: ${prev} → ${next}`,
          detail: cr.description,
          source: a.source ?? null,
        });
      }
    }

    for (const rev of revisions) {
      items.push({
        date: rev.revision_date,
        type: "revision",
        title: "Commitment text revised",
        detail: rev.change_summary ?? undefined,
        source: rev.source ?? null,
      });
    }

    items.sort((a, b) => b.date.localeCompare(a.date));
    return items.filter((item) => item.type !== "criterion");
  }, [commitment]);

  if (isLoading || !commitment) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-60 w-full" />
      </div>
    );
  }

  const c = commitment;
  const statusLabel = STATUS_LABELS[c.status] ?? c.status;
  const statusColor = STATUS_COLORS[c.status] ?? "bg-gray-100 text-gray-700";
  const typeLabel = TYPE_LABELS[c.commitment_type] ?? c.commitment_type;

  const criteria = c.criteria ?? [];
  const completionCriteria = criteria.filter(
    (cr: Criterion) => cr.category === "completion",
  );
  const progressCriteria = criteria.filter(
    (cr: Criterion) => cr.category === "progress",
  );

  const announcements = c.announcements ?? [];
  const actions = c.actions ?? [];
  const timeline = c.timeline ?? [];
  const revisions = c.revisions ?? [];
  const statusHistory = c.status_history ?? [];
  const children = c.children ?? [];

  const talkCount = announcements.length;
  const actionCount = actions.length;

  const timelinePageCount = Math.ceil(
    activityTimeline.length / TIMELINE_PAGE_SIZE,
  );
  const pagedTimeline = activityTimeline.slice(
    0,
    timelinePage * TIMELINE_PAGE_SIZE,
  );

  return (
    <div className="space-y-6">
      {/* Breadcrumbs */}
      <nav className="flex items-center text-sm text-gray-400 gap-1">
        <Link href="/" className="hover:text-[#8b2332] transition-colors">
          Overview
        </Link>
        {c.lead_department && (
          <>
            <ChevronRight className="w-3 h-3" />
            <Link
              href={`/ministries/${c.lead_department.slug}`}
              className="hover:text-[#8b2332] transition-colors"
            >
              {c.lead_department.display_name}
            </Link>
          </>
        )}
        <ChevronRight className="w-3 h-3" />
        <span className="text-gray-600 truncate max-w-xs">{c.title}</span>
      </nav>

      {/* Header */}
      <div className="border border-[#cdc4bd] bg-white p-6">
        <h1 className="text-2xl font-bold tracking-tight mb-3">{c.title}</h1>

        <div className="flex flex-wrap gap-2 mb-3">
          <span
            className={`inline-flex items-center px-2.5 py-0.5 text-xs font-medium ${statusColor}`}
          >
            {statusLabel}
          </span>
          <span className="inline-flex items-center px-2.5 py-0.5 text-xs font-medium bg-blue-50 text-blue-700">
            {typeLabel}
          </span>
          {c.lead_department && (
            <span className="inline-flex items-center px-2.5 py-0.5 text-xs font-medium bg-gray-100 text-gray-700">
              {c.lead_department.display_name}
            </span>
          )}
        </div>

        <p className="text-sm text-gray-600 mb-3">{c.description}</p>

        <div className="flex flex-wrap gap-4 text-sm text-gray-500">
          {c.date_promised && (
            <span>
              <span className="font-medium text-gray-700">Promised:</span>{" "}
              {formatDate(c.date_promised)}
            </span>
          )}
          {c.target_date && (
            <span>
              <span className="font-medium text-gray-700">Target:</span>{" "}
              {formatDate(c.target_date)}
            </span>
          )}
          {c.policy_area && (
            <span>
              <span className="font-medium text-gray-700">Policy area:</span>{" "}
              {c.policy_area.name}
            </span>
          )}
          {c.last_assessed_at && (
            <span>
              <span className="font-medium text-gray-700">Last assessed:</span>{" "}
              {formatDate(c.last_assessed_at)}
            </span>
          )}
        </div>

        {c.original_text && (
          <div className="mt-4 bg-blue-50 border-l-4 border-blue-300 px-4 py-3">
            <p className="text-sm text-gray-700 italic">
              &ldquo;{c.original_text}&rdquo;
            </p>
          </div>
        )}

        {children.length > 0 && (
          <div className="mt-3">
            <span className="text-sm font-medium text-gray-700">
              Sub-commitments:
            </span>
            <div className="mt-1 space-y-1">
              {children.map(
                (child: { id: number; title: string; status: string }) => (
                  <Link
                    key={child.id}
                    href={`/commitments/${child.id}`}
                    className="block text-sm text-gray-600 hover:text-[#8b2332]"
                  >
                    {child.title}{" "}
                    <span className="text-xs text-gray-400">
                      ({STATUS_LABELS[child.status] ?? child.status})
                    </span>
                  </Link>
                ),
              )}
            </div>
          </div>
        )}
      </div>

      {/* Criteria Assessment — second card, after header */}
      {(progressCriteria.length > 0 || completionCriteria.length > 0) && (
        <div className="border border-[#cdc4bd] bg-white p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-5">
            Criteria Assessment
          </h2>
          <div className="space-y-6">
            {progressCriteria.length > 0 && (
              <CriteriaSection
                title="Progress Criteria"
                criteria={progressCriteria}
              />
            )}
            {completionCriteria.length > 0 && (
              <div
                className={
                  progressCriteria.length > 0
                    ? "border-t border-gray-100 pt-5"
                    : ""
                }
              >
                <CriteriaSection
                  title="Completion Criteria"
                  criteria={completionCriteria}
                />
              </div>
            )}
          </div>
        </div>
      )}

      {/* Activity Timeline (paginated) */}
      {activityTimeline.length > 0 && (
        <div className="border border-[#cdc4bd] bg-white p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-6">
            Activity Timeline ({activityTimeline.length})
          </h2>
          <div className="relative">
            {/* Vertical line */}
            <div className="absolute left-[15px] top-2 bottom-2 w-0.5 bg-gray-200" />

            <div className="space-y-0">
              {pagedTimeline.map((item, idx) => (
                <div key={idx} className="relative flex gap-4 py-3">
                  {/* Icon */}
                  <div className="relative z-10 flex-shrink-0 w-[31px] flex justify-center">
                    <div
                      className={`w-7 h-7 rounded-full flex items-center justify-center ${TIMELINE_ICON_STYLE[item.type]?.bg ?? "bg-gray-100"}`}
                    >
                      <TimelineIcon type={item.type} />
                    </div>
                  </div>

                  {/* Content */}
                  <div className="flex-1 min-w-0 pt-0.5">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium text-gray-900">
                          {item.title}
                        </p>
                        {item.sourceType && (
                          <span className="inline-flex items-center px-1.5 py-0.5 text-[10px] font-medium bg-blue-100 text-blue-700 rounded flex-shrink-0">
                            {item.sourceType.replace(/_/g, " ")}
                          </span>
                        )}
                      </div>
                      <span className="text-xs text-gray-400 flex-shrink-0 tabular-nums">
                        {formatDate(item.date)}
                      </span>
                    </div>
                    {item.detail && (
                      <p className="text-xs text-gray-500 mt-0.5 line-clamp-2">
                        {item.detail}
                      </p>
                    )}
                    {(item.source || item.url) && (
                      <SourceAttribution
                        source={item.source}
                        fallbackUrl={item.url}
                      />
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {timelinePage < timelinePageCount && (
            <button
              onClick={() => setTimelinePage((p) => p + 1)}
              className="mt-4 w-full py-2 text-sm font-medium text-gray-500 hover:text-[#8b2332] border border-gray-200 hover:border-[#cdc4bd] transition-colors"
            >
              Show more ({activityTimeline.length - pagedTimeline.length}{" "}
              remaining)
            </button>
          )}
        </div>
      )}

      {/* Talk vs. Changed */}
      {(talkCount > 0 || actionCount > 0) && (
        <div className="border border-[#cdc4bd] bg-white p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-4">
            Talk vs. Changed
          </h2>
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div className="border border-amber-200 bg-amber-50 p-4">
              <div className="flex items-center gap-2 mb-1">
                <MessageSquare className="w-4 h-4 text-amber-600" />
                <span className="text-xs font-semibold uppercase text-amber-600">
                  Talk
                </span>
              </div>
              <p className="text-3xl font-bold text-amber-700">{talkCount}</p>
              <p className="text-xs text-amber-500">
                announcement{talkCount !== 1 ? "s" : ""}
              </p>
            </div>
            <div className="border border-[#e8bfc4] bg-[#faf0f1] p-4">
              <div className="flex items-center gap-2 mb-1">
                <Hammer className="w-4 h-4 text-[#8b2332]" />
                <span className="text-xs font-semibold uppercase text-[#8b2332]">
                  Changed
                </span>
              </div>
              <p className="text-3xl font-bold text-[#8b2332]">{actionCount}</p>
              <p className="text-xs text-[#b5616e]">
                concrete action{actionCount !== 1 ? "s" : ""}
              </p>
            </div>
          </div>

          {/* Ratio bar */}
          {talkCount + actionCount > 0 && (
            <div className="flex h-4 overflow-hidden mb-4">
              <div
                className="bg-amber-400"
                style={{
                  width: `${(talkCount / (talkCount + actionCount)) * 100}%`,
                }}
                title={`Talk: ${talkCount}`}
              />
              <div
                className="bg-[#8b2332]"
                style={{
                  width: `${(actionCount / (talkCount + actionCount)) * 100}%`,
                }}
                title={`Action: ${actionCount}`}
              />
            </div>
          )}

          {/* Announcements list */}
          {announcements.length > 0 && (
            <div className="mb-4">
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                Announcements
              </h3>
              <div className="space-y-2">
                {announcements.map((e: TimelineEvent) => (
                  <div key={e.id} className="flex gap-3 text-sm">
                    <span className="text-xs text-gray-400 w-24 flex-shrink-0">
                      {formatDate(e.occurred_at)}
                    </span>
                    <div>
                      <p className="text-gray-700">{e.title}</p>
                      {e.source && <SourceAttribution source={e.source} />}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Actions list */}
          {actions.length > 0 && (
            <div>
              <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-2">
                Concrete Actions
              </h3>
              <div className="space-y-2">
                {actions.map((e: TimelineEvent) => (
                  <div key={e.id} className="flex gap-3 text-sm">
                    <span className="text-xs text-gray-400 w-24 flex-shrink-0">
                      {formatDate(e.occurred_at)}
                    </span>
                    <div>
                      <p className="text-gray-700">{e.title}</p>
                      {e.source && <SourceAttribution source={e.source} />}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Timeline */}
      {timeline.length > 0 && (
        <div className="border border-[#cdc4bd] bg-white p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-6">
            Timeline
          </h2>
          <div className="relative">
            <div className="absolute left-[100px] top-0 bottom-0 w-0.5 bg-gray-200" />
            {timeline.map((event: TimelineEvent, idx: number) => (
              <div
                key={event.id}
                className={`relative flex gap-4 pb-6 px-2 py-3 ${
                  idx % 2 === 0 ? "" : "bg-gray-50/50"
                }`}
              >
                <div className="w-[80px] flex-shrink-0 text-right">
                  <span className="text-xs font-medium text-gray-500">
                    {formatDate(event.occurred_at)}
                  </span>
                </div>
                <div className="relative flex-shrink-0 w-5 flex justify-center">
                  <div
                    className={`w-3 h-3 rounded-full border-2 border-white ring-2 z-10 ${
                      event.action_type === "concrete_action"
                        ? "bg-[#8b2332] ring-[#e8bfc4]"
                        : "bg-blue-500 ring-blue-200"
                    }`}
                  />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-gray-900">
                    {event.title}
                  </p>
                  {event.description && (
                    <p className="text-sm text-gray-600 mt-0.5">
                      {event.description}
                    </p>
                  )}
                  <div className="flex flex-wrap gap-2 mt-1">
                    {event.action_type && (
                      <span
                        className={`text-xs px-2 py-0.5 ${
                          event.action_type === "concrete_action"
                            ? "bg-gray-100 text-gray-700"
                            : "bg-amber-100 text-amber-700"
                        }`}
                      >
                        {event.action_type === "concrete_action"
                          ? "Action"
                          : "Announcement"}
                      </span>
                    )}
                    {event.source && (
                      <SourceAttribution source={event.source} />
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Criteria section moved above header */}

      {/* Drift / Revisions */}
      {revisions.length > 0 && (
        <div className="border border-[#cdc4bd] bg-white p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-4">
            <AlertTriangle className="w-4 h-4 inline mr-1" />
            Commitment Drift ({revisions.length} revision
            {revisions.length !== 1 ? "s" : ""})
          </h2>
          <div className="space-y-4">
            {revisions.map((rev: Revision) => (
              <div
                key={rev.id}
                className="border border-orange-200 bg-orange-50 p-4"
              >
                <div className="flex items-start justify-between mb-2">
                  <span className="text-xs font-medium text-orange-700">
                    {formatDate(rev.revision_date)}
                  </span>
                  {rev.source && <SourceAttribution source={rev.source} />}
                </div>
                {rev.change_summary && (
                  <p className="text-sm text-gray-700 font-medium mb-2">
                    {rev.change_summary}
                  </p>
                )}
                <div className="text-xs text-gray-500 space-y-1">
                  {rev.title && (
                    <p>
                      <span className="font-medium">Previous title:</span>{" "}
                      {rev.title}
                    </p>
                  )}
                  {rev.target_date && (
                    <p>
                      <span className="font-medium">Previous target:</span>{" "}
                      {formatDate(rev.target_date)}
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Status History */}
      {statusHistory.length > 0 && (
        <div className="border border-[#cdc4bd] bg-white p-6">
          <h2 className="text-sm font-semibold uppercase tracking-wider text-gray-500 mb-4">
            <Clock className="w-4 h-4 inline mr-1" />
            Status History
          </h2>
          <div className="space-y-2">
            {statusHistory.map((sh: StatusChange) => (
              <div
                key={sh.id}
                className="py-2 border-b border-gray-50 last:border-0"
              >
                <div className="flex items-center gap-3 text-sm">
                  <span className="text-xs text-gray-400 w-32 flex-shrink-0">
                    {formatDate(sh.changed_at)}
                  </span>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[sh.previous_status] ?? "bg-gray-100 text-gray-700"}`}
                  >
                    {STATUS_LABELS[sh.previous_status] ?? sh.previous_status}
                  </span>
                  <span className="text-gray-400">&rarr;</span>
                  <span
                    className={`inline-flex items-center px-2 py-0.5 text-xs font-medium ${STATUS_COLORS[sh.new_status] ?? "bg-gray-100 text-gray-700"}`}
                  >
                    {STATUS_LABELS[sh.new_status] ?? sh.new_status}
                  </span>
                </div>
                {sh.reason && (
                  <p className="text-xs text-gray-500 mt-1 ml-[140px]">
                    {sh.reason}
                  </p>
                )}
                {sh.source && (
                  <div className="ml-[140px]">
                    <SourceAttribution source={sh.source} />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Recent Feed — hidden */}
    </div>
  );
}

// ── Timeline Icon Helpers ────────────────────────────────────────────────────

const TIMELINE_ICON_STYLE: Record<string, { bg: string }> = {
  promised: { bg: "bg-blue-100" },
  source: { bg: "bg-blue-50" },
  event_announcement: { bg: "bg-amber-100" },
  event_action: { bg: "bg-[#faf0f1]" },
  status_change: { bg: "bg-purple-100" },
  criterion: { bg: "bg-emerald-100" },
  revision: { bg: "bg-orange-100" },
  assessed: { bg: "bg-gray-100" },
};

function TimelineIcon({ type }: { type: string }) {
  const size = "w-3.5 h-3.5";
  switch (type) {
    case "promised":
      return <Megaphone className={`${size} text-blue-600`} />;
    case "source":
      return <FileText className={`${size} text-blue-500`} />;
    case "event_announcement":
      return <MessageSquare className={`${size} text-amber-600`} />;
    case "event_action":
      return <Wrench className={`${size} text-green-600`} />;
    case "status_change":
      return <ArrowRightLeft className={`${size} text-purple-600`} />;
    case "criterion":
      return <CheckCircle className={`${size} text-emerald-600`} />;
    case "revision":
      return <AlertTriangle className={`${size} text-orange-600`} />;
    case "assessed":
      return <BookOpen className={`${size} text-gray-500`} />;
    default:
      return <Clock className={`${size} text-gray-400`} />;
  }
}

// ── Source Attribution Component ────────────────────────────────────────────

function SourceAttribution({
  source,
  fallbackUrl,
}: {
  source?: Source | null;
  fallbackUrl?: string;
}) {
  const url = source?.url ?? fallbackUrl;
  const title = source?.title;

  if (!title && !url) return null;

  return (
    <div className="mt-1">
      {url ? (
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1 text-xs text-blue-600 hover:text-[#8b2332] hover:underline"
        >
          <ExternalLink className="w-3 h-3" />
          {title ?? "View source"}
        </a>
      ) : (
        <span className="text-xs text-gray-400">{title}</span>
      )}
    </div>
  );
}

// ── Criteria Section Component ──────────────────────────────────────────────

function CriteriaSection({
  title,
  criteria,
}: {
  title: string;
  criteria: Criterion[];
}) {
  return (
    <div>
      <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-3">
        {title}
      </h3>
      <ul className="space-y-2.5">
        {criteria.map((cr) => (
          <li key={cr.id} className="flex items-start gap-2.5">
            <div className="flex-shrink-0 mt-0.5">
              {cr.status === "met" ? (
                <div className="w-5 h-5 bg-pine-600 flex items-center justify-center">
                  <svg
                    className="w-3.5 h-3.5 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={3}
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                </div>
              ) : cr.status === "not_met" ? (
                <div className="w-5 h-5 bg-[#8b2332] flex items-center justify-center">
                  <svg
                    className="w-3.5 h-3.5 text-white"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={3}
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                </div>
              ) : (
                <div className="w-5 h-5 border-2 border-gray-300" />
              )}
            </div>
            <div>
              <p
                className={`text-sm ${
                  cr.status === "met" ? "text-gray-900" : "text-gray-500"
                }`}
              >
                {cr.description}
              </p>
              {cr.evidence_notes && (
                <p className="text-xs text-gray-400 mt-0.5">
                  {cr.evidence_notes}
                </p>
              )}
              {cr.assessed_at && (
                <p className="text-xs text-gray-400 mt-0.5">
                  Assessed: {formatDate(cr.assessed_at)}
                </p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
