"use client";

import { useState, useEffect, useCallback } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import PrimeMinisterSection from "@/components/PrimeMinisterSection";
import MinisterSection from "@/components/MinisterSection";
import {
  fetchPromisesForDepartment,
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

// Define Department IDs as constants
const ISED_DEPARTMENT_ID = 'innovation-science-and-economic-development-canada';
const AIDI_DEPARTMENT_ID = 'artificial-intelligence-and-digital-innovation';

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

  useEffect(() => {
    setAllDepartmentConfigs(initialAllDepartmentConfigs);
    // setMainTabConfigs(initialMainTabConfigs); // We will set this after filtering
    setMinisterInfos(initialMinisterInfos);

    let filteredMainTabConfigs = initialMainTabConfigs;

    // Parlament-based filtering for ISED/AIDI
    if (currentSessionId?.startsWith("44")) {
      console.log("[HomePageClient] Parliament 44 detected, filtering to show ISED and hide AIDI for 'Innovation' tab.");
      filteredMainTabConfigs = initialMainTabConfigs.filter(
        config => config.id !== AIDI_DEPARTMENT_ID
      );
    } else if (currentSessionId?.startsWith("45")) {
      console.log("[HomePageClient] Parliament 45 detected, filtering to show AIDI and hide ISED for 'Innovation' tab.");
      filteredMainTabConfigs = initialMainTabConfigs.filter(
        config => config.id !== ISED_DEPARTMENT_ID
      );
    } else {
      // Default behavior for other/unknown parliaments: prefer AIDI if it exists
      const aidiExists = initialMainTabConfigs.some(c => c.id === AIDI_DEPARTMENT_ID);
      if (aidiExists) {
        console.log("[HomePageClient] Defaulting to AIDI for 'Innovation' tab (hiding ISED if present).");
        filteredMainTabConfigs = initialMainTabConfigs.filter(config => config.id !== ISED_DEPARTMENT_ID);
      }
    }

    setMainTabConfigs(filteredMainTabConfigs);

    if(initialActiveTabId && filteredMainTabConfigs.some(c => c.id === initialActiveTabId)) {
      setActiveTabId(initialActiveTabId);
    } else if (filteredMainTabConfigs.length > 0) {
      setActiveTabId(filteredMainTabConfigs[0].id);
    } else {
      setActiveTabId("");
      setCurrentMinisterInfo(null); 
    }
  }, [initialAllDepartmentConfigs, initialMainTabConfigs, initialActiveTabId, initialMinisterInfos, currentSessionId]);

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
      // setActiveDepartmentData(null); // Clear previous tab's data immediately - this can cause a flash of loading state, let skeleton handle it

      let ministerInfoForThisTab = ministerInfos[thisTabId]; // Try to get from cache first

      // 1. Fetch Minister Info if not cached for THIS tab ID
      if (!ministerInfos.hasOwnProperty(thisTabId)) {
        console.log(`[HomePageClient] Minister info for ${thisTabId} not cached. Fetching...`);
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
          // setCurrentMinisterInfo will be updated by the separate effect watching ministerInfos
        } catch (err: any) {
          if (activeTabId !== thisTabId) return; // Tab changed, abort
          console.error(`[HomePageClient] Failed to fetch minister info for ${thisTabId}:`, err);
          setError(err.message || "Failed to load minister information.");
          setMinisterInfos(prev => ({ ...prev, [thisTabId]: null })); // Cache null on error
          setIsLoadingTabData(false);
          setActiveDepartmentData({ ministerInfo: null, promises: [], evidenceItems: [] }); // Show error state for promises too
          return; // Stop if minister fetch fails
        }
      } else {
        console.log(`[HomePageClient] Minister info for ${thisTabId} found in cache.`);
      }
      
      // Ensure we are using the most up-to-date minister info for the *current* thisTabId,
      // especially if it was just fetched and setMinisterInfos was called.
      // The separate effect listening to ministerInfos will update currentMinisterInfo, 
      // but for this specific load sequence, we use ministerInfoForThisTab directly if it was fetched,
      // or the cached value if it was already there.
      const finalMinisterInfoToUse = ministerInfos.hasOwnProperty(thisTabId) ? ministerInfos[thisTabId] : ministerInfoForThisTab;

      // 2. Fetch Promises using the (now hopefully correct) minister info for thisTabId
      const selectedConfig = allDepartmentConfigs.find(c => c.id === thisTabId);
      if (!selectedConfig) {
        if (activeTabId !== thisTabId) return; // Tab changed
        setError("Could not find configuration for the selected department.");
        setIsLoadingTabData(false);
        return;
      }
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
        
        console.log(`[HomePageClient] Fetching promises for dept: ${departmentFullName}, session: ${currentSessionId}, party: ${currentGoverningPartyCode}, override: ${effectiveDepartmentFullNameOverride}`);
        const promisesForDept = await fetchPromisesForDepartment(
          departmentFullName, 
          currentSessionId, 
          currentGoverningPartyCode,
          effectiveDepartmentFullNameOverride
        );
        
        // Log the promises and their evidence arrays as returned from fetchPromisesForDepartment
        console.log("[HomePageClient DEBUG] promisesForDept from fetchPromisesForDepartment:", JSON.parse(JSON.stringify(promisesForDept)));

        const allEvidenceItemsForDeptFlat = promisesForDept.reduce((acc, promise) => {
          if (promise.evidence) {
            promise.evidence.forEach(ev => {
              if (!acc.find(existingEv => existingEv.id === ev.id)) acc.push(ev);
            });
          }
          return acc;
        }, [] as EvidenceItem[]);

        if (activeTabId !== thisTabId) return; // Tab changed during promise fetch, abort

        console.log(`[HomePageClient] Setting active department data for ${thisTabId} with minister:`, finalMinisterInfoToUse?.name, `and ${promisesForDept.length} promises.`);
        setActiveDepartmentData({
          ministerInfo: finalMinisterInfoToUse,
          promises: promisesForDept,
          evidenceItems: allEvidenceItemsForDeptFlat
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
  }, [activeTabId, currentSessionId, currentGoverningPartyCode, allDepartmentConfigs, ministerInfos, error]); // Added ministerInfos and error

  // Actual JSX rendering for the client component
  return (
    <div className="min-h-screen bg-[#f8f2ea]">
      {/* Header is now part of the RootLayout or specific AdminLayout */}
      <div className="container mx-auto max-w-5xl px-4 py-12">
        <h1 className="mb-12 text-center text-5xl font-bold text-[#222222]">{pageTitle}</h1>
        <PrimeMinisterSection primeMinister={dynamicPrimeMinisterData} />
        {error && !isLoadingTabData && activeDepartmentData?.promises.length === 0 && <div className="text-red-500 text-center my-4">Error: {error}</div>} {/* Show general error if not loading tab data AND no promises loaded*/}
        
        {mainTabConfigs.length > 0 ? (
          <div className="mt-16">
            {/* Pills Container */}
            <div className="flex flex-wrap gap-2 mb-8">
              {mainTabConfigs.map((dept) => (
                <button
                  key={dept.id}
                  onClick={() => setActiveTabId(dept.id)}
                  className={`px-4 py-2 rounded-full text-sm font-medium transition-colors
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
            <div className="border border-[#d3c7b9] bg-white p-6 rounded-md shadow-sm">
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
                    <MinisterSection 
                      departmentPageData={activeDepartmentData}
                      departmentFullName={dept.official_full_name}
                      departmentShortName={dept.display_short_name}
                    />
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
  );
} 