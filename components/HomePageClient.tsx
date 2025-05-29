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
  PrimeMinister
} from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

// Client-side component to handle the dynamic parts that need state and effects
export default function HomePageClient({ 
  initialAllDepartmentConfigs, 
  initialMainTabConfigs,
  initialMinisterInfos,
  initialActiveTabId,
  initialError,
  currentSessionId, // Pass the fetched currentSessionId (string, e.g., "44")
  currentGoverningPartyCode, // NEW: Add the party code prop
  dynamicPrimeMinisterData, // Pass the fetched PM data
  pageTitle // Pass the dynamic page title
}: {
  initialAllDepartmentConfigs: DepartmentConfig[];
  initialMainTabConfigs: DepartmentConfig[];
  initialMinisterInfos: Record<string, MinisterInfo | null>;
  initialActiveTabId: string;
  initialError?: string | null;
  currentSessionId: string | null; // session ID like "44"
  currentGoverningPartyCode: string | null; // NEW: Add the party code prop
  dynamicPrimeMinisterData: PrimeMinister;
  pageTitle: string;
}) {
  const [allDepartmentConfigs, setAllDepartmentConfigs] = useState<DepartmentConfig[]>(initialAllDepartmentConfigs);
  const [mainTabConfigs, setMainTabConfigs] = useState<DepartmentConfig[]>(initialMainTabConfigs);
  const [ministerInfos, setMinisterInfos] = useState<Record<string, MinisterInfo | null>>(initialMinisterInfos);
  
  const [activeTabId, setActiveTabId] = useState<string>(initialActiveTabId);
  const [activeDepartmentData, setActiveDepartmentData] = useState<DepartmentPageData | null>(null);
  const [currentMinisterInfo, setCurrentMinisterInfo] = useState<MinisterInfo | null | undefined>(undefined);

  // isLoadingConfig is effectively handled by server component rendering or suspense
  const [isLoadingTabData, setIsLoadingTabData] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(initialError || null);
  
  // New state for pagination
  const [currentPage, setCurrentPage] = useState<number>(1);
  const [allPromises, setAllPromises] = useState<PromiseData[]>([]);
  const [totalPromises, setTotalPromises] = useState<number>(0);
  const [promisesPerPage] = useState<number>(10);

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
    // Reset pagination when tab changes
    setCurrentPage(1);
    setTotalPromises(0);
    setAllPromises([]);
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
          const response = await fetch(`/api/minister-info?departmentId=${thisTabId}&sessionId=${currentSessionId}`);
          if (!response.ok) {
            let errorMsg = `Error fetching minister for ${thisTabId}: ${response.statusText}`;
            try { const errorData = await response.json(); errorMsg = errorData.error || errorMsg; } catch (e) { /* ignore */ }
            throw new Error(errorMsg);
          }
          ministerInfoForThisTab = await response.json();
          
          if (activeTabId !== thisTabId) return; // Tab changed during minister fetch, abort

          setMinisterInfos(prev => ({ ...prev, [thisTabId]: ministerInfoForThisTab }));
        } catch (err: any) {
          if (activeTabId !== thisTabId) return; // Tab changed, abort
          console.error(`[HomePageClient] Failed to fetch minister info for ${thisTabId}:`, err);
          setError(err.message || "Failed to load minister information.");
          setMinisterInfos(prev => ({ ...prev, [thisTabId]: null })); // Cache null on error
          setIsLoadingTabData(false);
          setActiveDepartmentData({ ministerInfo: null, promises: [], evidenceItems: [] }); // Show error state for promises too
          return; // Stop if minister fetch fails
        }
      }
      
      const finalMinisterInfoToUse = ministerInfos.hasOwnProperty(thisTabId) ? ministerInfos[thisTabId] : ministerInfoForThisTab;

      // 2. For Prime Minister tab, we don't need to fetch promises
      const selectedConfig = allDepartmentConfigs.find(c => c.id === thisTabId);
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
          evidenceItems: []
        });
        setIsLoadingTabData(false);
        return;
      }

      // For other departments, fetch promises and total count
      const departmentFullName = selectedConfig.official_full_name;
      if (!departmentFullName || typeof departmentFullName !== 'string') {
        if (activeTabId !== thisTabId) return; // Tab changed
        setError(`Department full name is missing or invalid for ID: ${thisTabId}`);
        setIsLoadingTabData(false);
        return;
      }

      try {
        let effectiveDepartmentFullNameOverride: string | undefined = undefined;
        if (finalMinisterInfoToUse && 
            finalMinisterInfoToUse.effectiveDepartmentOfficialFullName &&
            selectedConfig && 
            finalMinisterInfoToUse.effectiveDepartmentId !== selectedConfig.id) {
            effectiveDepartmentFullNameOverride = finalMinisterInfoToUse.effectiveDepartmentOfficialFullName;
        }
        
        // Get total count and all promises for pagination
        const allPromiseSummaries = await fetchPromisesSummary(
          effectiveDepartmentFullNameOverride || departmentFullName, 
          currentSessionId, 
          currentGoverningPartyCode,
          "Canada",
          1000 // Fetch all promises
        );
        
        setAllPromises(allPromiseSummaries as PromiseData[]);
        setTotalPromises(allPromiseSummaries.length);
        
        // Calculate current page promises
        const startIndex = (currentPage - 1) * promisesPerPage;
        const endIndex = startIndex + promisesPerPage;
        const currentPagePromises = allPromiseSummaries.slice(startIndex, endIndex);
        
        if (activeTabId !== thisTabId) return; // Tab changed during fetch, abort

        setActiveDepartmentData({
          ministerInfo: finalMinisterInfoToUse,
          promises: currentPagePromises,
          evidenceItems: [] // Empty for performance, will load on demand
        });

      } catch (err: any) {
        if (activeTabId !== thisTabId) return; // Tab changed
        console.error(`[HomePageClient] Error fetching promise data for department ${departmentFullName} (Session: ${currentSessionId}):`, err);
        setError(`Failed to load promise data for ${departmentFullName}.`);
        setActiveDepartmentData({ ministerInfo: finalMinisterInfoToUse, promises: [], evidenceItems: []}); 
      } finally {
        if (activeTabId !== thisTabId) return; // Ensure still on the same tab before stopping loader
        setIsLoadingTabData(false);
      }
    };

    loadDataForActiveTab();
  }, [activeTabId, currentSessionId, currentGoverningPartyCode, allDepartmentConfigs, ministerInfos, error, currentPage, promisesPerPage]);

  // Function to handle page navigation
  const handlePageChange = (newPage: number) => {
    setCurrentPage(newPage);
  };

  // Effect to update displayed promises when page changes
  useEffect(() => {
    if (allPromises.length > 0 && activeDepartmentData) {
      const startIndex = (currentPage - 1) * promisesPerPage;
      const endIndex = startIndex + promisesPerPage;
      const currentPagePromises = allPromises.slice(startIndex, endIndex);
      
      setActiveDepartmentData(prev => prev ? {
        ...prev,
        promises: currentPagePromises
      } : null);
    }
  }, [currentPage, allPromises, promisesPerPage]);

  // Actual JSX rendering for the client component
  return (
    <div className="min-h-screen">
      <div className="container px-4 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <div className="col-span-1">
            <h1 className="text-4xl md:text-6xl font-bold mb-8">{pageTitle}</h1>
            <div className="mb-8">
              <p className="text-gray-900">
                A non-partisan platform tracking progress of key commitments during the 45th Parliament of Canada.
              </p>
            </div>
          </div>

          <div className="col-span-3">
            {error && !isLoadingTabData && activeDepartmentData?.promises.length === 0 && <div className="text-red-500 text-center my-4">Error: {error}</div>}
            
            {mainTabConfigs.length > 0 ? (
              <div>
                {/* Pills Container */}
                <div className="flex flex-wrap gap-2 mb-8">
                  {mainTabConfigs.map((dept) => (
                    <button
                      key={dept.id}
                      onClick={() => setActiveTabId(dept.id)}
                      className={`px-4 py-2 text-sm font-mono transition-colors
                        ${activeTabId === dept.id 
                          ? 'bg-[#8b2332] text-white' 
                          : 'bg-white text-[#222222] border border-[#d3c7b9] hover:bg-gray-50'
                        }`}
                    >
                      {dept.display_short_name}
                    </button>
                  ))}
                </div>

                {/* Content Container */}
                <div>
                  {mainTabConfigs.map((dept) => (
                    <div
                      key={dept.id}
                      className={activeTabId === dept.id ? 'block' : 'hidden'}
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
                      ) : activeDepartmentData && activeDepartmentData.ministerInfo !== undefined ? (
                        <>
                          <MinisterSection 
                            departmentPageData={activeDepartmentData}
                            departmentSlug={dept.department_slug}
                            departmentFullName={dept.official_full_name}
                            departmentShortName={dept.display_short_name}
                          />
                          {/* Pagination Controls */}
                          {!dept.is_prime_minister && totalPromises > 0 && (
                            <div className="mt-6 flex flex-col sm:flex-row items-center justify-between gap-4 p-4 border-t border-[#d3c7b9]">
                              {/* Page Info */}
                              <div className="text-sm text-gray-600">
                                Showing {((currentPage - 1) * promisesPerPage) + 1} to {Math.min(currentPage * promisesPerPage, totalPromises)} of {totalPromises} promises
                              </div>
                              
                              {/* Navigation Buttons */}
                              {totalPromises > promisesPerPage && (
                                <div className="flex items-center gap-2">
                                  <button
                                    onClick={() => handlePageChange(currentPage - 1)}
                                    disabled={currentPage === 1}
                                    className="px-3 py-1 text-sm border border-[#d3c7b9] hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                  >
                                    Previous
                                  </button>
                                  
                                  <span className="px-3 py-1 text-sm">
                                    Page {currentPage} of {Math.ceil(totalPromises / promisesPerPage)}
                                  </span>
                                  
                                  <button
                                    onClick={() => handlePageChange(currentPage + 1)}
                                    disabled={currentPage >= Math.ceil(totalPromises / promisesPerPage)}
                                    className="px-3 py-1 text-sm border border-[#d3c7b9] hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                                  >
                                    Next
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                          {/* Load More Button for Summary Data */}
                          {/* isShowingSummary && !dept.is_prime_minister && activeDepartmentData.promises.length >= 10 && (
                            <div className="mt-6 text-center">
                              <button
                                onClick={loadFullData}
                                disabled={isLoadingFullData}
                                className="px-6 py-3 border font-mono text-sm hover:bg-[#7a1f2b] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                              >
                                {isLoadingFullData ? 'Loading Full Data...' : 'LOAD MORE'}
                              </button>
                            </div>
                          )} */}
                        </>
                      ) : (
                        <div className="text-center py-10 text-gray-500">Select a department to view details.</div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              !initialError && <div className="text-center my-4">No priority departments configured or found.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
} 