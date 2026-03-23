"use client";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";
import type {
  DashboardResponse,
  DepartmentWithMinister,
  MinisterInfo,
} from "@/lib/commitment-types";

function SidebarLogo() {
  return (
    <div className="flex items-start gap-3 mb-8">
      <a href="https://www.buildcanada.com" className="flex-shrink-0 mt-1">
        <img
          src="/tracker/buildcanada-logo-square.svg"
          alt="Build Canada"
          className="h-[4.5rem] w-[4.5rem]"
        />
      </a>
      <Link href="/v2">
        <h1 className="text-4xl font-bold leading-none">
          Outcomes
          <br />
          Tracker
        </h1>
      </Link>
    </div>
  );
}

export const Sidebar = ({ pageTitle }: { pageTitle: string }) => {
  const pathname = usePathname();

  const ministryMatch = pathname?.match(/\/v2\/ministries\/([^/]+)/);
  const commitmentMatch = pathname?.match(/\/v2\/commitments\/(\d+)/);

  if (ministryMatch) {
    return <MinisterSidebarBySlug slug={ministryMatch[1]} />;
  }

  if (commitmentMatch) {
    return <MinisterSidebarByCommitment commitmentId={commitmentMatch[1]} />;
  }

  return <DefaultSidebar pageTitle={pageTitle} />;
};

// eslint-disable-next-line @typescript-eslint/no-unused-vars
function DefaultSidebar({ pageTitle }: { pageTitle: string }) {
  const { data: departments } = useSWR<DepartmentWithMinister[]>(
    `/tracker/api/v1/departments.json`,
    { revalidateIfStale: false },
  );

  const pmDept = departments?.find(
    (d) => d.slug === "prime-minister-and-privy-council",
  );

  const { data: dashboard } = useSWR<DashboardResponse>(
    `/tracker/api/dashboard/1/at_a_glance`,
    { revalidateIfStale: false },
  );
  const dashCounts = dashboard?.status_counts ?? {};
  const notStarted = dashCounts["not_started"] ?? 0;
  const inProgress = dashCounts["in_progress"] ?? 0;
  const completed = dashCounts["completed"] ?? 0;
  const abandoned = dashCounts["abandoned"] ?? 0;

  return (
    <div className="col-span-1">
      <div className="flex items-start gap-3 mb-8">
        <a href="https://www.buildcanada.com" className="flex-shrink-0 mt-1">
          <img
            src="/tracker/buildcanada-logo-square.svg"
            alt="Build Canada"
            className="h-[4.5rem] w-[4.5rem]"
          />
        </a>
        <h1 className="text-4xl font-bold leading-none">
          Outcomes
          <br />
          Tracker
        </h1>
      </div>
      <p className="text-gray-900 mb-6">
        Tracking Mark Carney&apos;s agenda from commitment to completion.{" "}
        <Link
          href="/v2/faq"
          className="text-[#8b2332] hover:text-[#721c28] transition-colors"
        >
          FAQ
        </Link>
      </p>
      <div className="mb-8">
        <blockquote className="text-gray-900 italic border-l-4 border-[#8b2332] pl-4">
          <p className="mb-1">We are in the biggest crisis of our lifetime.</p>
          <p className="mb-1">
            Now is the time for ambition, to be bold, to meet this crisis with
            the overwhelming, positive force of a united Canada.
          </p>
          <p>Now is the time to build, and my government is getting to work.</p>
          <div className="flex items-start gap-3 mt-4 not-italic">
            {pmDept?.minister?.avatar_url && (
              <div className="w-[70px] h-[70px] flex-shrink-0 bg-gray-100 overflow-hidden">
                <img
                  src={pmDept.minister.avatar_url}
                  alt="Mark Carney"
                  className="w-full h-full object-cover object-[center_25%]"
                />
              </div>
            )}
            <div>
              <a
                href="https://x.com/MarkJCarney/status/1921642068255904001"
                className="text-lg font-bold hover:text-[#8b2332] transition-colors leading-tight block"
                target="_blank"
                rel="noopener noreferrer"
              >
                Mark Carney
              </a>
              <p className="text-sm text-gray-500 mt-0.5">May 11, 2025</p>
              {pmDept?.minister?.email && (
                <p className="text-xs text-gray-400 mt-1">
                  <a
                    href={`mailto:${pmDept.minister.email}`}
                    className="hover:text-gray-600 transition-colors"
                  >
                    {pmDept.minister.email}
                  </a>
                </p>
              )}
            </div>
          </div>
        </blockquote>
      </div>
      {dashboard && (
        <div className="hidden min-[730px]:grid grid-cols-4 gap-4 mb-6 lg:hidden">
          <BigCard
            label="Not Started"
            value={notStarted}
            color="white"
            border="black"
            textColor="text-black"
            labelColor="text-black"
            href="/v2/commitments?status=not_started"
          />
          <BigCard
            label="In Progress"
            value={inProgress}
            color="#fbbf24"
            border="black"
            textColor="text-black"
            labelColor="text-black"
            href="/v2/commitments?status=in_progress"
          />
          <BigCard
            label="Completed"
            value={completed}
            color="#8b2332"
            border="white"
            textColor="text-white"
            labelColor="text-white"
            href="/v2/commitments?status=completed"
          />
          <BigCard
            label="Abandoned"
            value={abandoned}
            color="black"
            border="white"
            textColor="text-white"
            labelColor="text-white"
            href="/v2/commitments?status=abandoned"
          />
        </div>
      )}
      {dashboard && (
        <div className="grid grid-cols-4 gap-2 mb-6 min-[730px]:hidden">
          <CompactCard
            label="Not Started"
            value={notStarted}
            color="white"
            border="black"
            textColor="text-black"
            href="/v2/commitments?status=not_started"
          />
          <CompactCard
            label="In Progress"
            value={inProgress}
            color="#fbbf24"
            border="black"
            textColor="text-black"
            href="/v2/commitments?status=in_progress"
          />
          <CompactCard
            label="Completed"
            value={completed}
            color="#8b2332"
            border="white"
            textColor="text-white"
            href="/v2/commitments?status=completed"
          />
          <CompactCard
            label="Abandoned"
            value={abandoned}
            color="black"
            border="white"
            textColor="text-white"
            href="/v2/commitments?status=abandoned"
          />
        </div>
      )}
    </div>
  );
}

function MinisterSidebarBySlug({ slug }: { slug: string }) {
  const { data: departments } = useSWR<DepartmentWithMinister[]>(
    `/tracker/api/v1/departments.json`,
    { revalidateIfStale: false },
  );

  const dept = departments?.find((d) => d.slug === slug);

  // Still loading departments
  if (!departments) {
    return (
      <div className="col-span-1">
        <SidebarLogo />
        <div className="text-sm text-gray-400">Loading...</div>
      </div>
    );
  }

  // Department found with minister
  if (dept?.minister) {
    return (
      <div className="col-span-1">
        <SidebarLogo />
        <MinisterCard
          minister={dept.minister}
          departmentName={dept.display_name}
        />
      </div>
    );
  }

  // Department found but no minister assigned — show department name
  return (
    <div className="col-span-1">
      <SidebarLogo />
      <h2 className="text-2xl font-bold">
        {dept?.display_name ??
          slug.replace(/-/g, " ").replace(/\b\w/g, (c) => c.toUpperCase())}
      </h2>
      <p className="text-sm text-gray-500 mt-1">
        No minister currently assigned
      </p>
    </div>
  );
}

interface CommitmentBrief {
  id: number;
  lead_department: { id: number; display_name: string; slug: string } | null;
  departments: { id: number; display_name: string; is_lead: boolean }[];
}

function MinisterSidebarByCommitment({
  commitmentId,
}: {
  commitmentId: string;
}) {
  const { data: commitment } = useSWR<CommitmentBrief>(
    `/tracker/api/v1/commitments/${commitmentId}.json`,
    { revalidateIfStale: false },
  );

  const deptSlug = (commitment?.lead_department as { slug?: string })?.slug;

  const { data: departments } = useSWR<DepartmentWithMinister[]>(
    `/tracker/api/v1/departments.json`,
    { revalidateIfStale: false },
  );

  const dept = deptSlug
    ? departments?.find((d) => d.slug === deptSlug)
    : undefined;

  // Still loading
  if (!commitment || !departments) {
    return (
      <div className="col-span-1">
        <SidebarLogo />
        <div className="text-sm text-gray-400">Loading...</div>
      </div>
    );
  }

  const supportingDepts = (commitment.departments ?? [])
    .filter((d) => !d.is_lead)
    .map((d) => departments?.find((dep) => dep.id === d.id))
    .filter(Boolean) as DepartmentWithMinister[];

  if (dept?.minister) {
    return (
      <div className="col-span-1">
        <SidebarLogo />
        <MinisterCard
          minister={dept.minister}
          departmentName={dept.display_name}
        />
        {supportingDepts.length > 0 && (
          <SupportingDepartments departments={supportingDepts} />
        )}
      </div>
    );
  }

  // No minister — show department name if available
  const deptName =
    dept?.display_name ?? commitment.lead_department?.display_name;
  return (
    <div className="col-span-1">
      <SidebarLogo />
      {deptName && <h2 className="text-2xl font-bold">{deptName}</h2>}
      <p className="text-sm text-gray-500 mt-1">
        No minister currently assigned
      </p>
      {supportingDepts.length > 0 && (
        <SupportingDepartments departments={supportingDepts} />
      )}
    </div>
  );
}

function SupportingDepartments({
  departments,
}: {
  departments: DepartmentWithMinister[];
}) {
  return (
    <div className="mt-6 pt-6 border-t border-gray-200">
      <h3 className="text-xs font-mono text-gray-400 uppercase tracking-wider mb-4">
        Supporting Departments
      </h3>
      <div className="space-y-5">
        {departments.map((dept) => (
          <div key={dept.id}>
            <p className="text-sm font-bold mb-2">{dept.display_name}</p>
            {dept.minister ? (
              <SupportingMinisterCard minister={dept.minister} />
            ) : (
              <p className="text-xs text-gray-500">
                No minister currently assigned
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function SupportingMinisterCard({ minister }: { minister: MinisterInfo }) {
  const fullName = `${minister.first_name} ${minister.last_name}`;
  const phone = minister.phone ?? minister.hill_office?.telephone;

  return (
    <div>
      <div className="flex items-start gap-3">
        <div className="w-1/4 flex-shrink-0 aspect-square bg-gray-100 overflow-hidden">
          {minister.avatar_url ? (
            <img
              src={minister.avatar_url}
              alt={fullName}
              className="w-full h-full object-cover object-[center_25%]"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400 text-sm font-semibold">
              {minister.first_name[0]}
              {minister.last_name[0]}
            </div>
          )}
        </div>
        <div className="w-3/4">
          <h4 className="text-sm font-bold leading-tight">{fullName}</h4>
          <p className="text-xs text-gray-600 mt-0.5">{minister.title}</p>
          {phone && (
            <p className="text-xs text-gray-400 mt-1">
              <a
                href={`tel:${phone}`}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                {phone}
              </a>
            </p>
          )}
          {minister.email && (
            <p className="text-xs text-gray-400 truncate">
              <a
                href={`mailto:${minister.email}`}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                title={minister.email}
              >
                {minister.email}
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function MinisterCard({
  minister,
  departmentName,
  hideTitle = false,
}: {
  minister: MinisterInfo;
  departmentName: string;
  hideTitle?: boolean;
}) {
  const fullName = `${minister.first_name} ${minister.last_name}`;

  const phone = minister.phone ?? minister.hill_office?.telephone;

  return (
    <div>
      {/* Department name — largest text */}
      <h2 className="text-2xl font-bold mb-3">{departmentName}</h2>

      {/* Photo beside name/title/contact — same layout as supporting ministers */}
      <div className="flex items-start gap-3">
        <div className="w-1/4 flex-shrink-0 aspect-square bg-gray-100 overflow-hidden">
          {minister.avatar_url ? (
            <img
              src={minister.avatar_url}
              alt={fullName}
              className="w-full h-full object-cover object-[center_25%]"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-gray-400 text-lg font-semibold">
              {minister.first_name[0]}
              {minister.last_name[0]}
            </div>
          )}
        </div>
        <div className="w-3/4">
          <h3 className="text-lg font-bold leading-tight">{fullName}</h3>
          {!hideTitle && (
            <p className="text-sm text-gray-600 mt-0.5">{minister.title}</p>
          )}
          {phone && (
            <p className="text-xs text-gray-400 mt-1">
              <a
                href={`tel:${phone}`}
                className="text-gray-400 hover:text-gray-600 transition-colors"
              >
                {phone}
              </a>
            </p>
          )}
          {minister.email && (
            <p className="text-xs text-gray-400 truncate">
              <a
                href={`mailto:${minister.email}`}
                className="text-gray-400 hover:text-gray-600 transition-colors"
                title={minister.email}
              >
                {minister.email}
              </a>
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function CompactCard({
  label,
  value,
  color,
  border,
  textColor,
  href,
}: {
  label: string;
  value: number;
  color: string;
  border: string;
  textColor: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="hover:opacity-80 transition-opacity aspect-square"
      style={{ backgroundColor: color, padding: "3px" }}
    >
      <div
        className="h-full flex flex-col items-center justify-center"
        style={{ border: `2px solid ${border}` }}
      >
        <p
          className={`text-[10px] font-bold uppercase tracking-wider ${textColor}`}
        >
          {label}
        </p>
        <p className={`text-2xl font-extrabold ${textColor}`}>{value}</p>
      </div>
    </Link>
  );
}

function BigCard({
  label,
  value,
  color,
  border,
  textColor,
  labelColor,
  href,
}: {
  label: string;
  value: number;
  color: string;
  border: string;
  textColor: string;
  labelColor: string;
  href: string;
}) {
  return (
    <Link
      href={href}
      className="hover:opacity-80 transition-opacity aspect-square"
      style={{ backgroundColor: color, padding: "6px" }}
    >
      <div
        className="h-full flex flex-col justify-between"
        style={{ border: `4px solid ${border}` }}
      >
        <p
          className={`text-sm font-bold uppercase tracking-wider ${labelColor} m-4`}
        >
          {label}
        </p>
        <p
          className={`text-7xl font-extrabold ${textColor} text-right mr-2 max-[400px]:text-5xl`}
        >
          {value}
        </p>
      </div>
    </Link>
  );
}
