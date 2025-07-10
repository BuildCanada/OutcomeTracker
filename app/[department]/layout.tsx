"use client";

import DepartmentMetrics from "@/components/DepartmentMetrics";
import { Commitments, MinisterHeader } from "@/components/MinisterSection";
import { Skeleton } from "@/components/ui/skeleton";

import { Department, DepartmentSlug } from "@/lib/types";
import React, { Usable } from "react";
import useSWR from "swr";
import { DEPARTMENTS } from "./_constants";
import Link from "next/link";
import { mutate } from "swr";

// For Deparment preload/mutate on hover
async function fetcher(...args: Parameters<typeof fetch>) {
  return (await fetch(...args)).json();
}

export default function Layout({
  children,
  params,
}: Readonly<{
  children: React.ReactNode;
  params: Usable<{ department: DepartmentSlug }>;
}>) {
  const { department: slug } = React.use(params);

  const { data: department } = useSWR<Department>(
    `/tracker/api/v1/departments/${slug}.json`,
    {
      revalidateIfStale: false,
    }
  );

  if (!department) {
    return <Skeleton className="h-10 w-full" />;
  }

  return (
    <>
      <DepartmentPillLinks currentDepartmentSlug={slug} />

      <div className="space-y-4">
        {department.minister && (
          <MinisterHeader minister={department.minister} promises={department.promises} />
        )}
        <div className="space-y-4">
          <h3 className="text-2xl">Key Metrics</h3>
          <DepartmentMetrics departmentSlug={slug} />
        </div>
        <Commitments
          promises={department.promises}
          departmentSlug={department.slug}
        />
      </div>
      {children}
    </>
  );
}
function DepartmentPillLinks({
  currentDepartmentSlug,
}: {
  currentDepartmentSlug: DepartmentSlug;
}) {
  // const { data: departments } = useSWR<DepartmentListing[]>(
  //   "/api/v1/departments.json",
  // );

  // const filteredDepartments = departments
  //   ?.filter((department) => DEPARTMENT_DISPLAY_ORDER[department.slug] != null)
  //   ?.sort(
  //     (a, b) =>
  //       DEPARTMENT_DISPLAY_ORDER[a.slug] - DEPARTMENT_DISPLAY_ORDER[b.slug],
  //   );

  // const params = useParams<{department: string }>();

  // const activeTabId = currentDepartmentSlug;

  return (
    <div className="flex flex-wrap gap-2 mb-8">
      {DEPARTMENTS.map(({ slug, name }) => {
        return (
          <Link
            key={slug}
            href={`/${slug}`}
            className={`px-4 py-2 text-sm font-mono transition-colors
              ${currentDepartmentSlug == slug
                ? "bg-[#8b2332] text-white"
                : "bg-white text-[#222222] border border-[#d3c7b9] hover:bg-gray-50"
              }`}
            onMouseEnter={async () => { // Prefetch department data on hover
              const data = await fetcher(`/tracker/api/v1/departments/${slug}.json`);
              mutate(`/tracker/api/v1/departments/${slug}.json`, data);
            }}
            scroll={false}
          >
            {name}
          </Link>
        );
      })}
    </div>
  );
}
