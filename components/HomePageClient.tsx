"use client";

import { useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import PrimeMinisterSection from "@/components/PrimeMinisterSection";
import MinisterSection from "@/components/MinisterSection";
import {
  fetchMinisterDetails,
  fetchPromisesForDepartment,
  fetchEvidenceItemsForPromises
} from "@/lib/data";
import type {
  DepartmentConfig,
  DepartmentPageData,
  MinisterDetails,
  PromiseData,
  EvidenceItem,
  PrimeMinister
} from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

// Define a darker border color, e.g., a dark gray from Tailwind's palette or black
// const DARK_BORDER_COLOR = "border-neutral-700"; // Or use 'border-black' - Retaining for context if needed by styles below
// const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400"; // Slightly less prominent for the overall bottom
// const NAV_LINK_TEXT_COLOR = "text-neutral-800";
// const NAV_LINK_ACTIVE_TEXT_COLOR = "text-[#8b2332]"; // Your brand red - Retaining for context if needed by styles below


// Client-side component to handle the dynamic parts that need state and effects
export default function HomePageClient({ 
  initialAllDepartmentConfigs, 
  initialMainTabConfigs,
  initialActiveTabId,
  initialError,
  currentSessionId, // Pass the fetched currentSessionId (string, e.g., "44")
  dynamicPrimeMinisterData, // Pass the fetched PM data
  pageTitle // Pass the dynamic page title
}: {
  initialAllDepartmentConfigs: DepartmentConfig[];
  initialMainTabConfigs: DepartmentConfig[];
  initialActiveTabId: string;
  initialError?: string | null;
  currentSessionId: string | null; // session ID like "44"
  dynamicPrimeMinisterData: PrimeMinister;
  pageTitle: string;
}) {
  const [allDepartmentConfigs, setAllDepartmentConfigs] = useState<DepartmentConfig[]>(initialAllDepartmentConfigs);
  const [mainTabConfigs, setMainTabConfigs] = useState<DepartmentConfig[]>(initialMainTabConfigs);
  
  const [activeTabId, setActiveTabId] = useState<string>(initialActiveTabId);
  const [activeDepartmentData, setActiveDepartmentData] = useState<DepartmentPageData | null>(null);

  // isLoadingConfig is effectively handled by server component rendering or suspense
  const [isLoadingTabData, setIsLoadingTabData] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(initialError || null);

  useEffect(() => {
    setAllDepartmentConfigs(initialAllDepartmentConfigs);
    setMainTabConfigs(initialMainTabConfigs);
    if(initialActiveTabId) setActiveTabId(initialActiveTabId);
    else if (initialMainTabConfigs.length > 0) setActiveTabId(initialMainTabConfigs[0].id); // Fallback if initialActiveTabId was empty
    else setActiveTabId(""); // No tabs, no active ID
  }, [initialAllDepartmentConfigs, initialMainTabConfigs, initialActiveTabId]);

  useEffect(() => {
    if (!activeTabId || !currentSessionId) { 
        if(!currentSessionId && activeTabId && !error) setError("No active parliamentary session selected for data fetching.");
        setActiveDepartmentData(null); // Clear data if no session or tab
        return;
    }
    const loadTabData = async () => {
      setIsLoadingTabData(true);
      setError(null);
      setActiveDepartmentData(null); 
      
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
        const [ministerDetailsData, allPromisesForDept] = await Promise.all([
          fetchMinisterDetails(departmentFullName), 
          fetchPromisesForDepartment(departmentFullName, currentSessionId) 
        ]);
        let allEvidenceForDept: EvidenceItem[] = [];
        if (allPromisesForDept.length > 0) {
          const promiseIds = allPromisesForDept.map(p => p.id);
          allEvidenceForDept = await fetchEvidenceItemsForPromises(promiseIds);
        }
        const promisesWithEvidence = allPromisesForDept.map(promise => {
          const relevantEvidence = allEvidenceForDept.filter(evidence => 
            evidence.promise_ids && evidence.promise_ids.includes(promise.id)
          );
          return { ...promise, evidence: relevantEvidence };
        });
        setActiveDepartmentData({
          ministerDetails: ministerDetailsData,
          promises: promisesWithEvidence,
          evidenceItems: allEvidenceForDept
        });
      } catch (err) {
        console.error(`Error fetching data for department ${departmentFullName} (Session: ${currentSessionId}):`, err);
        setError(`Failed to load data for ${departmentFullName}.`);
      } finally {
        setIsLoadingTabData(false);
      }
    };
    loadTabData();
  }, [activeTabId, allDepartmentConfigs, currentSessionId]);

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
                    className="flex-grow whitespace-normal h-auto flex items-center justify-center text-center border border-b-0 border-l-0 first:border-l border-[#d3c7b9] bg-white px-3 py-3 text-xs sm:text-sm uppercase tracking-wider data-[state=active]:bg-[#8b2332] data-[state=active]:text-white data-[state=active]:border-[#8b2332] data-[state=active]:border-b-transparent data-[state=active]:relative data-[state=active]:-mb-[1px] rounded-none rounded-t-md focus-visible:ring-offset-0 focus-visible:ring-2 focus-visible:ring-[#8b2332] focus:z-10 hover:bg-gray-50"
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
                forceMount // Keep content mounted for better UX if desired, or remove for perf.
              >
                {activeTabId === dept.id && (
                  isLoadingTabData ? (
                    <div className="space-y-4">
                      <Skeleton className="h-20 w-1/2 bg-gray-200" /> 
                      <Skeleton className="h-8 w-1/3 bg-gray-200" />
                      <Skeleton className="h-40 w-full bg-gray-200" />
                    </div>
                  ) : error && !activeDepartmentData ? (
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