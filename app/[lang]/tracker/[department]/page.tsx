"use client";

import DepartmentMetrics from "@/components/DepartmentMetrics";
import MinisterSection, {
  Commitments,
  MinisterHeader,
} from "@/components/MinisterSection";
import { Skeleton } from "@/components/ui/skeleton";
import { useDepartments } from "@/context/DepartmentContext";
import { fetchPromisesForDepartment, fetchPromisesSummary } from "@/lib/data";
import { DepartmentSlug, MinisterInfo, PromiseData } from "@/lib/types";
import React, { Usable } from "react";
import { useEffect, useState } from "react";
import { set } from "react-hook-form";

export default function Page({
  params,
}: Readonly<{
  params: Usable<{ lang: string; department: DepartmentSlug }>;
}>) {
  const { department } = React.use(params);

  const { allDeptConfigs, mainTabConfigs, sessionId, governingParty } =
    useDepartments();

  const [ministerInfo, setMinisterInfo] = useState<MinisterInfo | null>();
  const [promises, setPromises] = useState<PromiseData[]>([]);
  const [promisesLoading, setPromisesLoading] = useState<boolean>(true);

  const currentDepartment = allDeptConfigs.find(
    (dept) => dept.id === department,
  );

  // Load minister data
  useEffect(() => {
    const loadMinisterInfo = async () => {
      const response = await fetch(
        `/api/minister-info?departmentId=${department}&sessionId=${45}`,
      );
      if (department === "prime-minister") {
        setMinisterInfo(await response.json());
      } else {
        setMinisterInfo(await response.json());
      }
    };
    loadMinisterInfo();
  }, [department]);

  useEffect(() => {
    const loadPromises = async () => {
      if (!currentDepartment) return;
      const fullPromises = await fetchPromisesForDepartment(
        currentDepartment.official_full_name,
        sessionId,
        governingParty,
        "Canada",
        ministerInfo?.effectiveDepartmentOfficialFullName,
        {
          limit: 50, // Load more promises
          includeEvidence: true, // Include evidence
          offset: 0,
        },
      );
      setPromises(fullPromises);
      setPromisesLoading(false);
    };
    loadPromises();
  }, [currentDepartment]);

  useEffect(() => {
    const loadPromiseSummaries = async () => {
      if (!currentDepartment) return;
      const promiseSummaries = await fetchPromisesSummary(
        currentDepartment.official_full_name,
        sessionId,
        governingParty,
        "Canada",
        10, // Initial limit for fast loading
      );
      setPromises((prev) => {
        if (prev.length === 0) {
          return promiseSummaries as PromiseData[];
        }
        return prev;
      });
      setPromisesLoading(false);
    };
    loadPromiseSummaries();
  }, [currentDepartment]);

  console.log(ministerInfo);

  if (!ministerInfo || !currentDepartment) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-20 w-1/2 bg-gray-200" />
        <Skeleton className="h-8 w-1/3 bg-gray-200" />
        <Skeleton className="h-40 w-full bg-gray-200" />
      </div>
    );
  }

  const promisesComponent = promisesLoading ? (
    <Skeleton className="h-40 w-full bg-gray-200" />
  ) : (
    <Commitments
      promises={promises}
      evidenceItems={[]}
      departmentShortName={currentDepartment.display_short_name}
    />
  );

  return (
    <div className="space-y-4">
      {JSON.stringify(ministerInfo)}
      {ministerInfo ? (
        <MinisterHeader ministerInfo={ministerInfo} />
      ) : (
        <Skeleton className="h-20 w-1/2 bg-gray-200" />
      )}

      <div className="space-y-4">
        <h3 className="text-2xl">Key Metrics</h3>
        <DepartmentMetrics departmentSlug={department} />
      </div>

      {department !== "prime-minister" && promisesComponent}
    </div>
  );
  J;
}
