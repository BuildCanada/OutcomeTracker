"use client";

import { useParams, useRouter } from "next/navigation";
import useSWR from "swr";
import { Skeleton } from "@/components/ui/skeleton";
import PromiseModal from "@/components/PromiseModal";
import { PromiseDetail } from "@/lib/types";
import React from "react";

export default function PromisePage() {
  const params = useParams<{
    department: string;
    promise_id: string;
  }>();
  const router = useRouter();

  const { promise_id } = params;

  // Fetch the promise data from the API
  const {
    data: promise,
    error,
    isLoading,
  } = useSWR<PromiseDetail>(
    promise_id ? `/tracker/api/v1/promises/${promise_id}.json` : null,
    {
      revalidateIfStale: false,
    },
  );

  // Handle close modal - navigate to parent department page
  const handleClose = () => {
    router.push(`/${params.department}`, { scroll: false });
  };

  // Only show loading if we don't have data AND we're loading
  const shouldShowLoading = isLoading && !promise;

  // Loading state
  if (shouldShowLoading) {
    return (
      <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
        <div className="bg-white p-8 rounded-lg mx-4 max-w-3xl w-full h-[90vh]">
          <Skeleton className="h-8 w-3/4 mb-4" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-4 w-2/3 mb-4" />
          <Skeleton className="h-32 w-full" />

          <Skeleton className="h-8 w-3/4 mb-4 mt-4" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-4 w-2/3 mb-4" />
          <Skeleton className="h-32 w-full" />

          <Skeleton className="h-8 w-3/4 mb-4 mt-4" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-4 w-full mb-2" />
          <Skeleton className="h-4 w-2/3 mb-4" />
          <Skeleton className="h-32 w-full" />
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
        <div className="bg-white p-8 rounded-lg max-w-md w-full mx-4 text-center">
          <h2 className="text-xl font-semibold text-red-600 mb-4">
            Error Loading Promise
          </h2>
          <p className="text-gray-600 mb-4">
            We couldn&apos;t load the promise details. Please try again.
          </p>
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  // Promise not found
  if (!promise) {
    return (
      <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50">
        <div className="bg-white p-8 rounded-lg max-w-md w-full mx-4 text-center">
          <h2 className="text-xl font-semibold text-gray-800 mb-4">
            Promise Not Found
          </h2>
          <p className="text-gray-600 mb-4">
            The promise you&apos;re looking for doesn&apos;t exist or has been
            removed.
          </p>
          <button
            onClick={handleClose}
            className="px-4 py-2 bg-blue-500 text-white rounded hover:bg-blue-600 transition-colors"
          >
            Go Back
          </button>
        </div>
      </div>
    );
  }

  // Render the PromiseModal with the fetched data
  return (
    <PromiseModal
      promise={promise}
      isOpen={true}
      onClose={handleClose}
      departmentSlug={params.department}
    />
  );
}
