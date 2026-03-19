import Link from "next/link";
import BurnUpChartWrapper from "@/components/BurnUpChartWrapper";
import { MinistryGrid } from "@/components/MinistryGrid";
import { fetchApi } from "@/lib/api";
import type {
  CommitmentsResponse,
  DepartmentWithMinister,
  BurnUpResponse,
  DashboardResponse,
  MinistryGroup,
} from "@/lib/commitment-types";

export default async function V2HomePage() {
  const [dashboard, burnUp, departments, commitmentsData] = await Promise.all([
    fetchApi<DashboardResponse>("/api/dashboard/1/at_a_glance"),
    fetchApi<BurnUpResponse>("/api/burndown/1"),
    fetchApi<DepartmentWithMinister[]>("/api/v1/departments.json"),
    fetchApi<CommitmentsResponse>("/api/v1/commitments.json?per_page=1000"),
  ]);

  const commitments = commitmentsData.commitments;
  const totalCommitments =
    dashboard.total_commitments ?? commitmentsData.meta.total_count;

  // Build ministry groups
  const deptBySlug: Record<string, DepartmentWithMinister> = {};
  for (const d of departments) {
    deptBySlug[d.slug] = d;
  }

  const groups: Record<string, MinistryGroup> = {};
  for (const c of commitments) {
    const name = c.lead_department?.display_name ?? "Unassigned";
    const slug = c.lead_department?.slug ?? "unassigned";
    if (!groups[name]) {
      groups[name] = {
        name,
        slug,
        commitments: [],
        statusCounts: {},
        minister: deptBySlug[slug]?.minister,
      };
    }
    groups[name].commitments.push(c);
    groups[name].statusCounts[c.status] =
      (groups[name].statusCounts[c.status] ?? 0) + 1;
  }
  const ministries = Object.values(groups).sort((a, b) => {
    if (a.name === "Unassigned") return 1;
    if (b.name === "Unassigned") return -1;
    return b.commitments.length - a.commitments.length;
  });

  const dashCounts = dashboard.status_counts ?? {};
  const notStarted = dashCounts["not_started"] ?? 0;
  const inProgress = dashCounts["in_progress"] ?? 0;
  const completed = dashCounts["completed"] ?? 0;
  const abandoned = dashCounts["abandoned"] ?? 0;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-3xl font-bold tracking-tight">
          Accountability Overview
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Tracking progress on {totalCommitments} government commitments
        </p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <MetricCard
          label="Not Started"
          value={notStarted}
          subtitle="no action taken"
          color="gray"
          href="/v2/commitments?status=not_started"
        />
        <MetricCard
          label="In Progress"
          value={inProgress}
          subtitle="actively being worked on"
          color="amber"
          href="/v2/commitments?status=in_progress"
        />
        <MetricCard
          label="Completed"
          value={completed}
          subtitle={`of ${totalCommitments} commitments`}
          color="red"
          href="/v2/commitments?status=completed"
        />
        <MetricCard
          label="Abandoned"
          value={abandoned}
          subtitle="no longer pursued"
          color="black"
          href="/v2/commitments?status=abandoned"
        />
      </div>

      {/* Burn-up chart */}
      <BurnUpChartWrapper
        data={burnUp}
        statusCounts={dashboard.status_counts}
      />

      {/* Ministries grid */}
      <div>
        <h3 className="text-xl font-semibold mb-4">By Ministry</h3>
        <MinistryGrid ministries={ministries} />
      </div>

      <div className="flex flex-wrap gap-3 text-sm">
        <Link
          href="/v2/commitments"
          className="border border-[#d3c7b9] px-4 py-2 text-gray-600 hover:bg-gray-50 hover:text-[#8b2332] transition-colors"
        >
          Explore All Commitments
        </Link>
      </div>
    </div>
  );
}

/* ── Metric Card ───────────────────────────────────────────────── */

function MetricCard({
  label,
  value,
  subtitle,
  color,
  href,
}: {
  label: string;
  value: number;
  subtitle: string;
  color: "gray" | "amber" | "red" | "black";
  href: string;
}) {
  const colorMap = {
    gray: {
      bg: "bg-gray-50 border-gray-200",
      text: "text-gray-800",
      sub: "text-gray-400",
      label: "text-gray-500",
    },
    amber: {
      bg: "bg-amber-50 border-amber-200",
      text: "text-amber-600",
      sub: "text-amber-400",
      label: "text-amber-500",
    },
    red: {
      bg: "bg-[#faf0f1] border-[#e8bfc4]",
      text: "text-[#8b2332]",
      sub: "text-[#b5616e]",
      label: "text-[#a34450]",
    },
    black: {
      bg: "bg-gray-100 border-gray-300",
      text: "text-black",
      sub: "text-gray-500",
      label: "text-gray-600",
    },
  };
  const c = colorMap[color];

  return (
    <Link
      href={href}
      className={`border p-6 ${c.bg} hover:opacity-80 transition-opacity`}
    >
      <p
        className={`text-xs font-semibold uppercase tracking-wider ${c.label}`}
      >
        {label}
      </p>
      <p className={`mt-2 text-4xl font-extrabold ${c.text}`}>{value}</p>
      <p className={`mt-1 text-sm ${c.sub}`}>{subtitle}</p>
    </Link>
  );
}
