"use client";

import { useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import MinisterSection from "@/components/MinisterSection";
import {
  fetchPromisesForDepartment,
  fetchPromisesSummary,
  // fetchEvidenceItemsForPromises // This seems unused now, consider removing if not needed elsewhere
} from "@/lib/data";
import type {
  DepartmentConfig,
  DepartmentPageData,
  MinisterInfo,
  PromiseData,
  EvidenceItem,
  PrimeMinister,
} from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import Link from "next/link";
import { useParams } from "next/navigation";

import FAQModal from "@/components/FAQModal";

// Client-side component to handle the dynamic parts that need state and effects
export default function HomePageClient({
  initialAllDepartmentConfigs,
  mainTabConfigs,
  initialMinisterInfos,
  initialActiveTabId,
  initialError,
  currentSessionId, // Pass the fetched currentSessionId (string, e.g., "44")
  currentGoverningPartyCode, // NEW: Add the party code prop
  dynamicPrimeMinisterData, // Pass the fetched PM data
  pageTitle, // Pass the dynamic page title
}: {
  initialAllDepartmentConfigs: DepartmentConfig[];
  mainTabConfigs: DepartmentConfig[];
  initialMinisterInfos: Record<string, MinisterInfo | null>;
  initialActiveTabId: string;
  initialError?: string | null;
  currentSessionId: string | null; // session ID like "44"
  currentGoverningPartyCode: string | null; // NEW: Add the party code prop
  dynamicPrimeMinisterData: PrimeMinister;
  pageTitle: string;
}) {
  const [allDepartmentConfigs, setAllDepartmentConfigs] = useState<
    DepartmentConfig[]
  >(initialAllDepartmentConfigs);
  const [ministerInfos, setMinisterInfos] =
    useState<Record<string, MinisterInfo | null>>(initialMinisterInfos);

  const [activeTabId, setActiveTabId] = useState<string>(initialActiveTabId);
  const [activeDepartmentData, setActiveDepartmentData] =
    useState<DepartmentPageData | null>(null);
  const [currentMinisterInfo, setCurrentMinisterInfo] = useState<
    MinisterInfo | null | undefined
  >(undefined);

  // isLoadingConfig is effectively handled by server component rendering or suspense
  const [isLoadingTabData, setIsLoadingTabData] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(initialError || null);

  // New state for performance optimization
  const [isShowingSummary, setIsShowingSummary] = useState<boolean>(true);
  const [isLoadingFullData, setIsLoadingFullData] = useState<boolean>(false);

  // Effect to set currentMinisterInfo based on activeTabId and cached ministerInfos
  useEffect(() => {
    if (activeTabId) {
      if (ministerInfos.hasOwnProperty(activeTabId)) {
        setCurrentMinisterInfo(ministerInfos[activeTabId]);
      } else {
        setCurrentMinisterInfo(undefined); // Mark as pending, data loading effect will fetch
      }
    } else {
      setCurrentMinisterInfo(null); // No active tab
      setActiveDepartmentData(null); // Clear department data if no tab is active
    }
  }, [activeTabId, ministerInfos]);

  // Combined effect for fetching ALL data (minister and promises) for the active tab
  useEffect(() => {
    const loadDataForActiveTab = async () => {
      if (!activeTabId || !currentSessionId) {
        setActiveDepartmentData(null); // Clear data if no tab or session
        if (!currentSessionId && activeTabId && !error) {
          //setError("No active parliamentary session selected for data fetching.");
          // console.warn("[HomePageClient] No active parliamentary session, cannot fetch tab data.");
        }
        return;
      }

      const thisTabId = activeTabId; // Capture tab ID at the start of this async operation

      setIsLoadingTabData(true);
      setError(null);

      let ministerInfoForThisTab = ministerInfos[thisTabId];

      // 1. Fetch Minister Info if not cached for THIS tab ID
      if (!ministerInfos.hasOwnProperty(thisTabId)) {
        try {
          const response = await fetch(
            `/api/minister-info?departmentId=${thisTabId}&sessionId=${currentSessionId}`,
          );
          if (!response.ok) {
            let errorMsg = `Error fetching minister for ${thisTabId}: ${response.statusText}`;
            try {
              const errorData = await response.json();
              errorMsg = errorData.error || errorMsg;
            } catch (e) {
              /* ignore */
            }
            throw new Error(errorMsg);
          }
          ministerInfoForThisTab = await response.json();

          if (activeTabId !== thisTabId) return; // Tab changed during minister fetch, abort

          setMinisterInfos((prev) => ({
            ...prev,
            [thisTabId]: ministerInfoForThisTab,
          }));
        } catch (err: any) {
          if (activeTabId !== thisTabId) return; // Tab changed, abort
          console.error(
            `[HomePageClient] Failed to fetch minister info for ${thisTabId}:`,
            err,
          );
          setError(err.message || "Failed to load minister information.");
          setMinisterInfos((prev) => ({ ...prev, [thisTabId]: null })); // Cache null on error
          setIsLoadingTabData(false);
          setActiveDepartmentData({
            ministerInfo: null,
            promises: [],
            evidenceItems: [],
          }); // Show error state for promises too
          return; // Stop if minister fetch fails
        }
      } else {
        console.log(
          `[HomePageClient] Minister info for ${thisTabId} found in cache.`,
        );
      }

      const finalMinisterInfoToUse = ministerInfos.hasOwnProperty(thisTabId)
        ? ministerInfos[thisTabId]
        : ministerInfoForThisTab;

      // 2. For Prime Minister tab, we don't need to fetch promises
      const selectedConfig = allDepartmentConfigs.find(
        (c) => c.id === thisTabId,
      );
      if (!selectedConfig) {
        if (activeTabId !== thisTabId) return; // Tab changed
        setError("Could not find configuration for the selected department.");
        setIsLoadingTabData(false);
        return;
      }

      // If this is the Prime Minister tab, just set the data without fetching promises
      if (selectedConfig.is_prime_minister) {
        if (activeTabId !== thisTabId) return; // Tab changed
        setActiveDepartmentData({
          ministerInfo: finalMinisterInfoToUse,
          promises: [], // No promises for PM
          evidenceItems: [],
        });
        setIsLoadingTabData(false);
        return;
      }

      // For other departments, fetch promises as usual
      const departmentFullName = selectedConfig.official_full_name;
      if (!departmentFullName || typeof departmentFullName !== "string") {
        if (activeTabId !== thisTabId) return; // Tab changed
        setError(
          `Department full name is missing or invalid for ID: ${thisTabId}`,
        );
        setIsLoadingTabData(false);
        return;
      }

      try {
        let effectiveDepartmentFullNameOverride: string | undefined = undefined;
        if (
          finalMinisterInfoToUse &&
          finalMinisterInfoToUse.effectiveDepartmentOfficialFullName &&
          selectedConfig &&
          finalMinisterInfoToUse.effectiveDepartmentId !== selectedConfig.id
        ) {
          effectiveDepartmentFullNameOverride =
            finalMinisterInfoToUse.effectiveDepartmentOfficialFullName;
        }

        // First, load a lightweight summary for faster initial page load
        const promiseSummaries = await fetchPromisesSummary(
          effectiveDepartmentFullNameOverride || departmentFullName,
          currentSessionId,
          currentGoverningPartyCode,
          "Canada",
          10, // Initial limit for fast loading
        );

        if (activeTabId !== thisTabId) return; // Tab changed during fetch, abort

        setActiveDepartmentData({
          ministerInfo: finalMinisterInfoToUse,
          promises: promiseSummaries as PromiseData[], // Type assertion since we know the structure
          evidenceItems: [], // Empty for performance, will load on demand
        });
        setIsShowingSummary(true); // Mark that we're showing summary data
      } catch (err: any) {
        if (activeTabId !== thisTabId) return; // Tab changed
        setError(`Failed to load promise data for ${departmentFullName}.`);
        setActiveDepartmentData({
          ministerInfo: finalMinisterInfoToUse,
          promises: [],
          evidenceItems: [],
        });
      } finally {
        if (activeTabId !== thisTabId) return; // Ensure still on the same tab before stopping loader
        setIsLoadingTabData(false);
      }
    };

    loadDataForActiveTab();
  }, [
    activeTabId,
    currentSessionId,
    currentGoverningPartyCode,
    allDepartmentConfigs,
    ministerInfos,
    error,
  ]);

  // Function to load full data with evidence when needed
  const loadFullData = useCallback(async () => {
    if (
      !activeTabId ||
      !currentSessionId ||
      !currentGoverningPartyCode ||
      isLoadingFullData
    ) {
      return;
    }

    const selectedConfig = allDepartmentConfigs.find(
      (c) => c.id === activeTabId,
    );
    if (!selectedConfig || selectedConfig.is_prime_minister) {
      return; // No promises for PM
    }

    setIsLoadingFullData(true);

    try {
      const departmentFullName = selectedConfig.official_full_name;
      let effectiveDepartmentFullNameOverride: string | undefined = undefined;

      const ministerInfo = ministerInfos[activeTabId];
      if (
        ministerInfo &&
        ministerInfo.effectiveDepartmentOfficialFullName &&
        ministerInfo.effectiveDepartmentId !== selectedConfig.id
      ) {
        effectiveDepartmentFullNameOverride =
          ministerInfo.effectiveDepartmentOfficialFullName;
      }

      console.log(
        `[HomePageClient] Loading full promise data for ${departmentFullName}`,
      );
      const fullPromises = await fetchPromisesForDepartment(
        departmentFullName,
        currentSessionId,
        currentGoverningPartyCode,
        "Canada",
        effectiveDepartmentFullNameOverride,
        {
          limit: 50, // Load more promises
          includeEvidence: true, // Include evidence
          offset: 0,
        },
      );

      const allEvidenceItemsFlat = fullPromises.reduce((acc, promise) => {
        if (promise.evidence) {
          promise.evidence.forEach((ev) => {
            if (!acc.find((existingEv) => existingEv.id === ev.id))
              acc.push(ev);
          });
        }
        return acc;
      }, [] as EvidenceItem[]);

      setActiveDepartmentData((prev) =>
        prev
          ? {
              ...prev,
              promises: fullPromises,
              evidenceItems: allEvidenceItemsFlat,
            }
          : null,
      );
      setIsShowingSummary(false);
    } catch (error) {
      console.error("Error loading full data:", error);
    } finally {
      setIsLoadingFullData(false);
    }
  }, [
    activeTabId,
    currentSessionId,
    currentGoverningPartyCode,
    allDepartmentConfigs,
    ministerInfos,
    isLoadingFullData,
  ]);

  // Actual JSX rendering for the client component
  return (
    <div className="min-h-screen">
      <div className="container px-4 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <Sidebar pageTitle={pageTitle} />

          <div className="col-span-3">
            {error &&
              !isLoadingTabData &&
              activeDepartmentData?.promises.length === 0 && (
                <div className="text-red-500 text-center my-4">
                  Error: {error}
                </div>
              )}

            {mainTabConfigs.length > 0 ? (
              <div>
                {/* Pills Container */}
                <DepartmentPills
                  {...{ mainTabConfigs, setActiveTabId, activeTabId }}
                />

                {/* Content Container */}
                <div>
                  {mainTabConfigs.map((dept) => (
                    <div
                      key={dept.id}
                      className={activeTabId === dept.id ? "block" : "hidden"}
                    >
                      {isLoadingTabData ? (
                        <div className="space-y-4">
                          <Skeleton className="h-20 w-1/2 bg-gray-200" />
                          <Skeleton className="h-8 w-1/3 bg-gray-200" />
                          <Skeleton className="h-40 w-full bg-gray-200" />
                        </div>
                      ) : error ? (
                        <div className="text-center py-10 text-red-600 bg-red-100 border border-red-400 p-4">
                          {`Error loading data for ${dept.display_short_name}: ${error}`}
                        </div>
                      ) : activeDepartmentData &&
                        activeDepartmentData.ministerInfo !== undefined ? (
                        <>
                          <MinisterSection
                            departmentPageData={activeDepartmentData}
                            departmentSlug={dept.department_slug}
                            departmentFullName={dept.official_full_name}
                            departmentShortName={dept.display_short_name}
                          />
                          {/* Load More Button for Summary Data */}
                          {isShowingSummary &&
                            !dept.is_prime_minister &&
                            activeDepartmentData.promises.length >= 10 && (
                              <div className="mt-6 text-center">
                                <button
                                  onClick={loadFullData}
                                  disabled={isLoadingFullData}
                                  className="px-6 py-3 border font-mono text-sm hover:bg-[#7a1f2b] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                >
                                  {isLoadingFullData
                                    ? "Loading Full Data..."
                                    : "LOAD MORE"}
                                </button>
                              </div>
                            )}
                        </>
                      ) : (
                        <div className="text-center py-10 text-gray-500">
                          Select a department to view details.
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              !initialError && (
                <div className="text-center my-4">
                  No priority departments configured or found.
                </div>
              )
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export const Sidebar = ({ pageTitle }: { pageTitle: string }) => {
    const [isFAQModalOpen, setIsFAQModalOpen] = useState(false);

    return (
        <div className="col-span-1">
            <h1 className="text-4xl md:text-6xl font-bold mb-8">{pageTitle}</h1>
            <div className="mb-8">
                <p className="text-gray-900">
                    A non-partisan platform tracking progress of key commitments during the
                    45th Parliament of Canada.
                </p>
                <button
                    onClick={() => setIsFAQModalOpen(true)}
                    className="font-mono text-sm text-[#8b2332] hover:text-[#721c28] transition-colors"
                >
                    FAQ
                </button>

            </div>
            <FAQModal isOpen={isFAQModalOpen} onClose={() => setIsFAQModalOpen(false)} />
        </div>
    );
};

export function DepartmentPills({
  mainTabConfigs,
  setActiveTabId,
  activeTabId,
}: {
  mainTabConfigs: DepartmentConfig[];
  setActiveTabId: (tabId: string) => void;
  activeTabId: string;
}) {
  return (
    <div className="flex flex-wrap gap-2 mb-8">
      {mainTabConfigs.map((dept) => (
        <button
          key={dept.id}
          onClick={() => setActiveTabId(dept.id)}
          className={`px-4 py-2 text-sm font-mono transition-colors
                        ${
                          activeTabId === dept.id
                            ? "bg-[#8b2332] text-white"
                            : "bg-white text-[#222222] border border-[#d3c7b9] hover:bg-gray-50"
                        }`}
        >
          {dept.display_short_name}
        </button>
      ))}
    </div>
  );
}

const DEFAULT_TAB = "finance-canada";

export function DepartmentPillLinks({
  mainTabConfigs,
}: {
  mainTabConfigs: DepartmentConfig[];
}) {
  const params = useParams<{ lang: string; department?: string }>();

  const activeTabId = params.department || DEFAULT_TAB;

  return (
    <div className="flex flex-wrap gap-2 mb-8">
      {mainTabConfigs.map((dept) => (
        <Link
          key={dept.id}
          href={`/en/tracker/${dept.id}`}
          className={`px-4 py-2 text-sm font-mono transition-colors
                        ${
                          activeTabId === dept.id
                            ? "bg-[#8b2332] text-white"
                            : "bg-white text-[#222222] border border-[#d3c7b9] hover:bg-gray-50"
                        }`}
        >
          {dept.display_short_name}
        </Link>
      ))}
    </div>
  );
}
