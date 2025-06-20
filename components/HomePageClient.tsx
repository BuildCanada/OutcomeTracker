"use client";

import { useState } from "react";

import type { DepartmentListing } from "@/lib/types";

import Link from "next/link";
import { useParams } from "next/navigation";

import FAQModal from "@/components/FAQModal";
import useSWR from "swr";
import { DEPARTMENT_DISPLAY_ORDER } from "@/app/[lang]/tracker/_constants";

export const Sidebar = ({ pageTitle }: { pageTitle: string }) => {
  const [isFAQModalOpen, setIsFAQModalOpen] = useState(false);

  return (
    <div className="col-span-1">
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
};

export function DepartmentPillLinks() {
  const { data: departments } = useSWR<DepartmentListing[]>(
    "/api/v1/departments",
  );

  const filteredDepartments = departments
    ?.filter((department) => DEPARTMENT_DISPLAY_ORDER[department.slug] != null)
    ?.sort(
      (a, b) =>
        DEPARTMENT_DISPLAY_ORDER[a.slug] - DEPARTMENT_DISPLAY_ORDER[b.slug],
    );

  const params = useParams<{ lang: string; department: string }>();

  const activeTabId = params.department;

  return (
    <div className="flex flex-wrap gap-2 mb-8">
      {filteredDepartments?.map((dept) => (
        <Link
          key={dept.id}
          href={`/en/tracker/${dept.slug}`}
          className={`px-4 py-2 text-sm font-mono transition-colors
                        ${
                          activeTabId === dept.slug
                            ? "bg-[#8b2332] text-white"
                            : "bg-white text-[#222222] border border-[#d3c7b9] hover:bg-gray-50"
                        }`}
        >
          {dept.display_name}
        </Link>
      ))}
    </div>
  );
}
