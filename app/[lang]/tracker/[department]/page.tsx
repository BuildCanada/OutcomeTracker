"use client";

import DepartmentMetrics from "@/components/DepartmentMetrics";
import {
  Commitments,
  MinisterHeader,
} from "@/components/MinisterSection";
import { Skeleton } from "@/components/ui/skeleton";

import {
  Department,
  DepartmentSlug,
} from "@/lib/types";
import React, { Usable } from "react";
import useSWR from "swr";

export default function Page({
  params,
}: Readonly<{
  params: Usable<{ lang: string; department: DepartmentSlug }>;
}>) {
  const { department: slug } = React.use(params);

  const { data: department } = useSWR<Department>(
    `/api/v1/departments/${slug}`,
  );

  if (!department) {
    return <Skeleton className="h-10 w-full" />;
  }

  return (
    <div className="space-y-4">
      <MinisterHeader minister={department.minister} />
      <div className="space-y-4">
        <h3 className="text-2xl">Key Metrics</h3>
        <DepartmentMetrics departmentSlug={slug} />
      </div>
      <Commitments
        promises={department.promises}
        departmentShortName={department.display_name}
      />
    </div>
  );
}
