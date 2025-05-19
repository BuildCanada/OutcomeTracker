"use client";

import { useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import PrimeMinisterSection from "@/components/PrimeMinisterSection";
import MinisterSection from "@/components/MinisterSection";
import {
  fetchPromisesForDepartment,
  fetchEvidenceItemsForPromises
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
  const [currentMinisterInfo, setCurrentMinisterInfo] = useState<MinisterInfo | null | undefined>(undefined); // Allow undefined for pending state

  // isLoadingConfig is effectively handled by server component rendering or suspense
  const [isLoadingTabData, setIsLoadingTabData] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(initialError || null);

  useEffect(() => {
    setAllDepartmentConfigs(initialAllDepartmentConfigs);
    setMainTabConfigs(initialMainTabConfigs);
    setMinisterInfos(initialMinisterInfos);
    if(initialActiveTabId) {
      setActiveTabId(initialActiveTabId);
      // currentMinisterInfo will be set by the effect watching [activeTabId, ministerInfos]
    } else if (initialMainTabConfigs.length > 0) {
      const firstTabId = initialMainTabConfigs[0].id;
      setActiveTabId(firstTabId);
      // currentMinisterInfo will be set by the effect watching [activeTabId, ministerInfos]
    } else {
      setActiveTabId("");
      setCurrentMinisterInfo(null); // No tabs, no minister
    }
  }, [initialAllDepartmentConfigs, initialMainTabConfigs, initialActiveTabId, initialMinisterInfos]);

  // Effect to set currentMinisterInfo based on activeTabId and cached ministerInfos
  useEffect(() => {
    if (activeTabId) {
      if (ministerInfos.hasOwnProperty(activeTabId)) {
        setCurrentMinisterInfo(ministerInfos[activeTabId]);
        // activeDepartmentData will be updated by loadPromiseDataForTab effect
      } else {
        // Data is not yet fetched/cached for this tab. Minister info is pending.
        setCurrentMinisterInfo(undefined); 
        setActiveDepartmentData(null); // Clear stale department data immediately
      }
    } else {
      setCurrentMinisterInfo(null); // No active tab
      setActiveDepartmentData(null); // Clear department data if no tab is active
    }
  }, [activeTabId, ministerInfos]);

  // New useEffect for fetching minister info if not cached
  useEffect(() => {
    const fetchMinisterDataForTab = async () => {
      if (!activeTabId || !currentSessionId) {
        return;
      }

      // If minister info is already loaded and cached for this tab, don't refetch.
      // The other useEffect [activeTabId, ministerInfos] will set currentMinisterInfo.
      if (ministerInfos.hasOwnProperty(activeTabId)) {
        return;
      }

      console.log(`[HomePageClient] Minister info for ${activeTabId} not cached. Fetching...`);
      setIsLoadingTabData(true); // Indicate that tab data is now loading (covers minister part)
      setError(null); // Clear previous general errors

      try {
        const response = await fetch(`/api/minister-info?departmentId=${activeTabId}&sessionId=${currentSessionId}`);
        if (!response.ok) {
          let errorMsg = `Error fetching minister: ${response.statusText}`;
          try {
              const errorData = await response.json();
              errorMsg = errorData.error || errorMsg;
          } catch (e) { /* ignore json parsing error for error object */ }
          throw new Error(errorMsg);
        }
        const data: MinisterInfo | null = await response.json();
        
        setMinisterInfos(prevInfos => ({
          ...prevInfos,
          [activeTabId]: data,
        }));
        // currentMinisterInfo will be updated by the effect watching [activeTabId, ministerInfos]
        // No need to set setIsLoadingTabData(false) here; loadPromiseDataForTab will handle it.
      } catch (err: any) {
        console.error(`[HomePageClient] Failed to fetch minister info for ${activeTabId}:`, err);
        setError(err.message || "Failed to load minister information.");
        setMinisterInfos(prevInfos => ({
          ...prevInfos,
          [activeTabId]: null, // Cache null on error to prevent retries and allow promise loading (if applicable)
        }));
        // setIsLoadingTabData(false) will be handled by loadPromiseDataForTab.
      }
    };

    fetchMinisterDataForTab();
  }, [activeTabId, currentSessionId]); // ministerInfos is intentionally not a dependency here

  useEffect(() => {
    if (!activeTabId || !currentSessionId) { 
        if(!currentSessionId && activeTabId && !error) setError("No active parliamentary session selected for data fetching.");
        setActiveDepartmentData(null);
        return;
    }

    // If currentMinisterInfo is undefined, it means minister data is being fetched or hasn't been fetched yet.
    // Wait for it to become defined (either MinisterInfo or null).
    if (currentMinisterInfo === undefined) {
      // Minister info is pending, don't load promises yet.
      // setIsLoadingTabData(true) would have been set by the minister fetching effect if it started.
      return;
    }

    const loadPromiseDataForTab = async () => {
      setIsLoadingTabData(true);
      setError(null);
      
      const selectedConfig = allDepartmentConfigs.find(c => c.id === activeTabId);
      if (!selectedConfig) {
        setError("Could not find configuration for the selected department.");
        setIsLoadingTabData(false);
        return;
      }
      const departmentFullName = selectedConfig.official_full_name;
      if (!departmentFullName || typeof departmentFullName !== 'string') {
        setError(`Department full name is missing or invalid for ID: ${activeTabId}`);
        setIsLoadingTabData(false);
        return;
      }

      try {
        // Fetch promises; each promise will have its .fullPath and .evidence populated by this function call.
        const promisesForDept = await fetchPromisesForDepartment(departmentFullName, currentSessionId, currentGoverningPartyCode);
        
        // Optionally, create a flat, unique list of all evidence items for the displayed promises 
        // if this flat list is needed elsewhere (e.g., for a global evidence view or other components).
        // PromiseCard will use its own promise.evidence for its modal timeline.
        const allEvidenceItemsForDeptFlat = promisesForDept.reduce((acc, promise) => {
          if (promise.evidence) {
            // Add evidence items to the accumulator if they are not already present (based on evidence ID)
            promise.evidence.forEach(ev => {
              if (!acc.find(existingEv => existingEv.id === ev.id)) {
                acc.push(ev);
              }
            });
          }
          return acc;
        }, [] as EvidenceItem[]);

        setActiveDepartmentData({
          ministerInfo: currentMinisterInfo,
          promises: promisesForDept, // Each promise already has .fullPath and .evidence populated
          evidenceItems: allEvidenceItemsForDeptFlat // A flat, unique list of evidence items for this department view
        });

      } catch (err) {
        console.error(`Error fetching promise data for department ${departmentFullName} (Session: ${currentSessionId}):`, err);
        setError(`Failed to load promise data for ${departmentFullName}.`);
        setActiveDepartmentData({ ministerInfo: currentMinisterInfo, promises: [], evidenceItems: []}); 
      } finally {
        setIsLoadingTabData(false);
      }
    };
    loadPromiseDataForTab();
  }, [activeTabId, allDepartmentConfigs, currentSessionId, currentGoverningPartyCode, currentMinisterInfo]);

  // const handleDropdownSelect = useCallback((departmentId: string) => { setActiveTabId(departmentId); }, []); // Removed

  // Actual JSX rendering for the client component
  return (
    <div className="min-h-screen bg-[#f8f2ea] font-sans">
      {/* Header is now part of the RootLayout or specific AdminLayout */}
      <div className="container mx-auto max-w-5xl px-4 py-12">
        <h1 className="mb-12 text-center text-5xl font-bold text-[#222222]">{pageTitle}</h1>
        <PrimeMinisterSection primeMinister={dynamicPrimeMinisterData} />
        {error && !isLoadingTabData && <div className="text-red-500 text-center my-4">Error: {error}</div>} {/* Show general error if not loading tab data */}
        
        {mainTabConfigs.length > 0 ? (
          <Tabs value={activeTabId} onValueChange={setActiveTabId} className="mt-16">
            <div className="flex justify-between items-end border-b border-[#d3c7b9] mb-[-1px]">
              <TabsList className="inline-flex items-stretch bg-transparent p-0 h-auto flex-grow">
                {mainTabConfigs.map((dept) => (
                  <TabsTrigger key={dept.id} value={dept.id} 
                    className="flex-1 whitespace-normal h-auto flex items-center justify-center text-center border border-b-0 border-l-0 first:border-l border-[#d3c7b9] bg-white px-3 py-3 text-xs sm:text-sm uppercase tracking-wider data-[state=active]:bg-[#8b2332] data-[state=active]:text-white data-[state=active]:border-[#8b2332] data-[state=active]:border-b-transparent data-[state=active]:relative data-[state=active]:-mb-[1px] rounded-none rounded-t-md focus-visible:ring-offset-0 focus-visible:ring-2 focus-visible:ring-[#8b2332] focus:z-10 hover:bg-gray-50"
                  >
                    {dept.display_short_name}
                  </TabsTrigger>
                ))}
              </TabsList>
              {/* Dropdown removed */}
            </div>
            {mainTabConfigs.map((dept) => (
              <TabsContent key={dept.id} value={dept.id} 
                className="border border-t-0 border-[#d3c7b9] bg-white p-6 data-[state=inactive]:hidden mt-0 rounded-b-md shadow-sm"
                forceMount
              >
                {activeTabId === dept.id && (
                  isLoadingTabData ? (
                    <div className="space-y-4">
                      <Skeleton className="h-20 w-1/2 bg-gray-200" /> 
                      <Skeleton className="h-8 w-1/3 bg-gray-200" />
                      <Skeleton className="h-40 w-full bg-gray-200" />
                    </div>
                  ) : error && !activeDepartmentData?.promises.length ? (
                    <div className="text-center py-10 text-red-600 bg-red-100 border border-red-400 p-4">
                      {`Error loading data for ${dept.display_short_name}: ${error}`}
                    </div>
                  ) : activeDepartmentData ? (
                    <MinisterSection 
                      departmentPageData={activeDepartmentData}
                      departmentFullName={dept.official_full_name}
                      departmentShortName={dept.display_short_name}
                    />
                  ) : (
                    <div className="text-center py-10 text-gray-500">No data available for {dept.display_short_name} in this session.</div>
                  )
                )}
              </TabsContent>
            ))}
          </Tabs>
        ) : (
          !initialError && <div className="text-center my-4">No priority departments configured or found.</div>
        )}
      </div>
    </div>
  );
} 