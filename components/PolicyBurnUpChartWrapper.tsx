"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";
import type { BurnUpResponse } from "@/lib/commitment-types";

const PolicyBurnUpChart = dynamic(
  () => import("@/components/PolicyBurnUpChart"),
  { ssr: false, loading: () => <Skeleton className="h-96" /> },
);

export default function PolicyBurnUpChartWrapper({
  data,
}: {
  data: BurnUpResponse;
}) {
  return <PolicyBurnUpChart data={data} />;
}
