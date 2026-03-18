"use client";
import { useState } from "react";
import { usePathname } from "next/navigation";
import useSWR from "swr";
import Link from "next/link";

import FAQModal from "@/components/FAQModal";
import type {
  DepartmentWithMinister,
  MinisterInfo,
  HillOffice,
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
      <div className="mb-8">
        <p className="text-gray-900 mb-6">
          A non-partisan platform tracking progress of key commitments during
          the 45th Parliament of Canada.
        </p>
        <button
          onClick={() => setIsFAQModalOpen(true)}
          className="font-mono text-sm text-[#8b2332] hover:text-[#721c28] transition-colors"
        >
          FAQ
        </button>
      </div>
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

  return (
    <div>
      {/* Photo */}
      <div className="w-full aspect-square bg-gray-100 overflow-hidden mb-4">
        {minister.avatar_url ? (
          <img
            src={minister.avatar_url}
            alt={fullName}
            className="w-full h-full object-cover"
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center text-gray-400 text-4xl font-semibold">
            {minister.first_name[0]}
            {minister.last_name[0]}
          </div>
        )}
      </div>

      {/* Name and title */}
      <h2 className="text-2xl font-bold">{fullName}</h2>
      <p className="text-sm text-gray-600 mt-1">{minister.title}</p>
      <p className="text-xs text-gray-400 mt-0.5">{departmentName}</p>

      {/* Contact info */}
      <div className="mt-4 space-y-2 text-sm">
        {minister.constituency && (
          <div>
            <span className="text-xs font-mono text-gray-400 uppercase">
              Riding
            </span>
            <p className="text-gray-700">
              {minister.constituency}
              {minister.province ? `, ${minister.province}` : ""}
            </p>
          </div>
        )}
        {minister.email && (
          <div>
            <span className="text-xs font-mono text-gray-400 uppercase">
              Email
            </span>
            <p>
              <a
                href={`mailto:${minister.email}`}
                className="text-[#8b2332] hover:text-[#721c28] transition-colors break-all"
              >
                {minister.email}
              </a>
            </p>
          </div>
        )}
        {minister.hill_office && (
          <HillOfficeInfo office={minister.hill_office} />
        )}
        {minister.website && (
          <div>
            <span className="text-xs font-mono text-gray-400 uppercase">
              Website
            </span>
            <p>
              <a
                href={minister.website}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#8b2332] hover:text-[#721c28] transition-colors break-all"
              >
                {minister.website.replace(/^https?:\/\//, "")}
              </a>
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function HillOfficeInfo({ office }: { office: HillOffice }) {
  return (
    <>
      {office.telephone && (
        <div>
          <span className="text-xs font-mono text-gray-400 uppercase">
            Hill Office Phone
          </span>
          <p>
            <a
              href={`tel:${office.telephone}`}
              className="text-[#8b2332] hover:text-[#721c28] transition-colors"
            >
              {office.telephone}
            </a>
          </p>
        </div>
      )}
      {office.address && (
        <div>
          <span className="text-xs font-mono text-gray-400 uppercase">
            Hill Office
          </span>
          <p className="text-gray-700 whitespace-pre-line text-xs leading-relaxed">
            {office.address}
          </p>
        </div>
      )}
    </>
  );
}
