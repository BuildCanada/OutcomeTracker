import type { Metadata } from "next";
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

// Cache-bust the OG image URL every 4 hours so social crawlers re-fetch
export async function generateMetadata(): Promise<Metadata> {
  const slot = Math.floor(Date.now() / (4 * 60 * 60 * 1000));
  return {
    openGraph: {
      images: [`/tracker/opengraph-image?v=${slot}`],
    },
  };
}

export default async function HomePage() {
  const [dashboard, burnUp, departments, commitmentsData] = await Promise.all([
    fetchApi<DashboardResponse>("/api/dashboard/1/at_a_glance"),
    fetchApi<BurnUpResponse>("/api/burndown/1"),
    fetchApi<DepartmentWithMinister[]>("/api/v1/departments.json"),
    fetchApi<CommitmentsResponse>("/api/v1/commitments.json?per_page=1000"),
  ]);

  const commitments = commitmentsData.commitments;
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
  const broken = dashCounts["broken"] ?? 0;

  return (
    <div className="space-y-8">
      <div className="hidden lg:grid grid-cols-4 gap-4">
        <MetricCard
          label="Not Started"
          value={notStarted}
          color="gray"
          href="/commitments?status=not_started"
        />
        <MetricCard
          label="In Progress"
          value={inProgress}
          color="amber"
          href="/commitments?status=in_progress"
        />
        <MetricCard
          label="Completed"
          value={completed}
          color="green"
          href="/commitments?status=completed"
        />
        <MetricCard
          label="Broken"
          value={broken}
          color="red"
          href="/commitments?status=broken"
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
          href="/commitments"
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
  color,
  href,
}: {
  label: string;
  value: number;
  color: "gray" | "amber" | "green" | "red";
  href: string;
}) {
  const colorMap = {
    gray: {
      outer: "white",
      inner: "black",
      text: "text-black",
      sub: "text-gray-700",
      label: "text-black",
    },
    amber: {
      outer: "#fbbf24",
      inner: "black",
      text: "text-black",
      sub: "text-black/70",
      label: "text-black",
    },
    green: {
      outer: "#356643",
      inner: "white",
      text: "text-white",
      sub: "text-white/70",
      label: "text-white",
    },
    red: {
      outer: "#8b2332",
      inner: "white",
      text: "text-white",
      sub: "text-white/70",
      label: "text-white",
    },
  };
  const c = colorMap[color];

  return (
    <Link
      href={href}
      className="hover:opacity-80 transition-opacity aspect-square"
      style={{
        backgroundColor: c.outer,
        padding: "6px",
      }}
    >
      <div
        className="h-full flex flex-col justify-between"
        style={{
          border: `4px solid ${c.inner}`,
        }}
      >
        <p
          className={`text-sm font-bold uppercase tracking-wider ${c.label} m-4`}
        >
          {label}
        </p>
        <p
          className={`text-7xl font-extrabold ${c.text} text-right mr-2 max-[400px]:text-5xl`}
        >
          {value}
        </p>
      </div>
    </Link>
  );
}
