"use client";

import dynamic from "next/dynamic";
import { Skeleton } from "@/components/ui/skeleton";
import type { BurnUpResponse } from "@/lib/commitment-types";

const BurnUpChart = dynamic(() => import("@/components/ChartLine"), {
  ssr: false,
  loading: () => <Skeleton className="h-96" />,
});

export default function BurnUpChartWrapper({
  data,
  statusCounts,
}: {
  data: BurnUpResponse;
  statusCounts?: Record<string, number>;
}) {
  return <BurnUpChart data={data} statusCounts={statusCounts} />;
}
