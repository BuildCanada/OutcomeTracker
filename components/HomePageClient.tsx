"use client";
import { useState } from "react";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";

import FAQModal from "@/components/FAQModal";
import type {
  DepartmentWithMinister,
  MinisterInfo,
} from "@/lib/commitment-types";

function SidebarLogo() {
  return (
    <div className="mb-6">
      <Link href="/v2" className="block">
        <img
          src="https://cdn.prod.website-files.com/679d23fc682f2bf860558c9a/679d23fc682f2bf860558cc6_build_canada-wordmark.svg"
          alt="Build Canada"
          className="bg-[#932f2f] h-12 w-auto p-3"
        />
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

function DefaultSidebar({ pageTitle }: { pageTitle: string }) {
  const [isFAQModalOpen, setIsFAQModalOpen] = useState(false);

  const { data: departments } = useSWR<DepartmentWithMinister[]>(
    `/tracker/api/v1/departments.json`,
    { revalidateIfStale: false },
  );

  const pmDept = departments?.find((d) => d.slug === "prime-minister-office");

  return (
    <div className="col-span-1">
      <div className="mb-6">
        <a href="/" className="block">
          <img
            src="https://cdn.prod.website-files.com/679d23fc682f2bf860558c9a/679d23fc682f2bf860558cc6_build_canada-wordmark.svg"
            alt="Build Canada"
            className="bg-[#932f2f] h-12 w-auto p-3"
          />
        </a>
      </div>
      <h1 className="text-4xl lg:text-5xl font-bold mb-8">{pageTitle}</h1>
      {pmDept?.minister ? (
        <div className="mb-8">
          <MinisterCard
            minister={pmDept.minister}
            departmentName={pmDept.display_name}
          />
        </div>
      ) : (
        <div className="mb-8">
          <p className="text-gray-900 mb-6">
            A non-partisan platform tracking progress of key commitments during
            the 45th Parliament of Canada.
          </p>
        </div>
      )}
      <button
        onClick={() => setIsFAQModalOpen(true)}
        className="font-mono text-sm text-[#8b2332] hover:text-[#721c28] transition-colors"
      >
        FAQ
      </button>
      <FAQModal
        isOpen={isFAQModalOpen}
        onClose={() => setIsFAQModalOpen(false)}
      />
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
}: {
  minister: MinisterInfo;
  departmentName: string;
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
          <p className="text-sm text-gray-600 mt-0.5">{minister.title}</p>
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
