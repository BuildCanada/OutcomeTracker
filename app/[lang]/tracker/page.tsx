"use client"
import { useState, useEffect, useCallback } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import PrimeMinisterSection from "@/components/PrimeMinisterSection"
import MinisterSection from "@/components/MinisterSection"
import DepartmentsDropdown from "@/components/DepartmentsDropdown"
import {
  fetchDepartmentConfigs,
  fetchMinisterDetails,
  fetchPromisesForDepartment,
  fetchEvidenceItemsForPromises,
} from "@/lib/data";
import type {
  DepartmentConfig,
  DepartmentPageData,
  MinisterDetails,
  PromiseData,
  EvidenceItem,
  Metric,
  PrimeMinister,
} from "@/lib/types";
import { Skeleton } from "@/components/ui/skeleton";

const DEFAULT_PLACEHOLDER_AVATAR = "/placeholder.svg?height=100&width=100";

// Static data for the Prime Minister section, to be made dynamic based on session of parliament
const staticPrimeMinisterData: PrimeMinister = {
  name: "Justin Trudeau", // Example Name
  title: "Prime Minister, 44th Parliament of Canada",
  avatarUrl: "/placeholder.svg?height=200&width=200", // Example avatar
  guidingMetrics: [
    {
      title: "GDP Per Capita",
      data: [45000, 44800, 45200, 45600, 45400, 45800, 46000],
      goal: 48000,
    },
  ],
};

// Define the preferred order for main tabs
// IMPORTANT: These strings MUST exactly match the 'fullName' field
// in your Firestore 'department_config' collection documents.
// Double-check casing, spacing, and exact wording (e.g., 'and' vs '&').
const MAIN_TAB_ORDER: string[] = [
  "Infrastructure Canada", // CORRECTED - Assuming this is the name in Firestore
  "National Defence",
  "Health Canada", // CORRECTED - Based on user screenshot
  "Finance Canada",
  "Immigration, Refugees and Citizenship Canada",
  "Employment and Social Development Canada",
];

// Define a darker border color, e.g., a dark gray from Tailwind's palette or black
const DARK_BORDER_COLOR = "border-neutral-700"; // Or use 'border-black'
const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400"; // Slightly less prominent for the overall bottom
const NAV_LINK_TEXT_COLOR = "text-neutral-800";
const NAV_LINK_ACTIVE_TEXT_COLOR = "text-[#8b2332]"; // Your brand red

export default function Home() {
  const [allDepartmentConfigs, setAllDepartmentConfigs] = useState<
    DepartmentConfig[]
  >([]);
  const [mainTabConfigs, setMainTabConfigs] = useState<DepartmentConfig[]>([]);
  const [dropdownTabConfigs, setDropdownTabConfigs] = useState<
    DepartmentConfig[]
  >([]);

  const [activeTabId, setActiveTabId] = useState<string>("");
  const [activeDepartmentData, setActiveDepartmentData] =
    useState<DepartmentPageData | null>(null);

  const [isLoadingConfig, setIsLoadingConfig] = useState<boolean>(true);
  const [isLoadingTabData, setIsLoadingTabData] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  // Fetch all department configs on initial mount
  useEffect(() => {
    const loadConfigs = async () => {
      setIsLoadingConfig(true);
      setError(null);
      try {
        const configs = await fetchDepartmentConfigs();
        setAllDepartmentConfigs(configs);

        // Separate configs based on MAIN_TAB_ORDER
        const mainTabs = MAIN_TAB_ORDER.map((fullName) =>
          configs.find((c) => c.fullName === fullName),
        ).filter((c): c is DepartmentConfig => c !== undefined);

        const mainTabIds = new Set(mainTabs.map((c) => c.id));
        const dropdownTabs = configs.filter((c) => !mainTabIds.has(c.id));

        setMainTabConfigs(mainTabs);
        setDropdownTabConfigs(dropdownTabs);

        // Set the first main tab as active by default if available
        if (mainTabs.length > 0) {
          setActiveTabId(mainTabs[0].id);
        } else if (configs.length > 0) {
          // Fallback to the first config if no main tabs match
          setActiveTabId(configs[0].id);
        }
      } catch (err) {
        console.error("Error fetching department configs:", err);
        setError("Failed to load department configurations.");
      } finally {
        setIsLoadingConfig(false);
      }
    };
    loadConfigs();
  }, []);

  // Fetch data for the active tab whenever activeTabId changes
  useEffect(() => {
    if (!activeTabId) return; // Don't fetch if no tab is selected

    const loadTabData = async () => {
      setIsLoadingTabData(true);
      setError(null);
      setActiveDepartmentData(null); // Clear previous data

      const selectedConfig = allDepartmentConfigs.find(
        (c) => c.id === activeTabId,
      );
      if (!selectedConfig) {
        setError("Could not find configuration for the selected department.");
        setIsLoadingTabData(false);
        return;
      }

      const departmentFullName = selectedConfig.fullName;

      try {
        // Fetch minister details and all promises for the department
        const [ministerDetailsData, allPromisesForDept] = await Promise.all([
          fetchMinisterDetails(departmentFullName),
          fetchPromisesForDepartment(departmentFullName)
        ]);

        let allEvidenceForDept: EvidenceItem[] = [];
        if (allPromisesForDept.length > 0) {
          const promiseIds = allPromisesForDept.map(p => p.id);
          allEvidenceForDept = await fetchEvidenceItemsForPromises(promiseIds);
        }

        // Now, map through allPromisesForDept and attach relevant evidence to each promise
        const promisesWithEvidence = allPromisesForDept.map(promise => {
          const relevantEvidence = allEvidenceForDept.filter(evidence => 
            evidence.promise_ids && evidence.promise_ids.includes(promise.id)
          );
          return {
            ...promise,
            evidence: relevantEvidence // Populate the promise.evidence field
          };
        });

        setActiveDepartmentData({
          ministerDetails: ministerDetailsData,
          promises: promisesWithEvidence, // Use promises that now have their .evidence field populated
          evidenceItems: allEvidenceForDept // Keep all evidence for the department if needed elsewhere, though modal now uses promise.evidence
        });

      } catch (err) {
        console.error(
          `Error fetching data for department ${departmentFullName}:`,
          err,
        );
        setError(`Failed to load data for ${departmentFullName}.`);
        // Keep activeDepartmentData as null or set to an error state if needed
      } finally {
        setIsLoadingTabData(false);
      }
    };

    loadTabData();
  }, [activeTabId, allDepartmentConfigs]);

  // Handler for dropdown selection
  const handleDropdownSelect = useCallback((departmentId: string) => {
    setActiveTabId(departmentId);
    // Optional: Scroll to tabs section if needed
    // document.getElementById('department-tabs')?.scrollIntoView({ behavior: 'smooth' });
  }, []);

  if (isLoadingConfig) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        Loading configurations...
      </div>
    );
  }

  return (
    <main className="min-h-screen bg-background font-sans">
      <div className="container mx-auto max-w-5xl px-4 py-12">
        <h1 className="mb-12 text-center text-5xl font-bold text-[#222222]">Outcomes Tracker - 44th Parliament of Canada</h1>

        <PrimeMinisterSection primeMinister={staticPrimeMinisterData} />

        {error && (
          <div className="text-red-500 text-center my-4">Error: {error}</div>
        )}

        {allDepartmentConfigs.length > 0 && (
          <Tabs
            value={activeTabId}
            onValueChange={setActiveTabId}
            className="mt-16"
          >
            <div className="flex justify-between items-end border-b border-[#d3c7b9] mb-[-1px]">
              <TabsList className="inline-flex items-stretch bg-transparent p-0 h-auto flex-grow">
                {mainTabConfigs.map((dept) => (
                  <TabsTrigger
                    key={dept.id}
                    value={dept.id}
                    className="flex-grow whitespace-normal h-auto flex items-center justify-center text-center border border-b-0 border-l-0 first:border-l border-[#d3c7b9] bg-white px-3 py-3 text-xs sm:text-sm uppercase tracking-wider data-[state=active]:bg-[#8b2332] data-[state=active]:text-white data-[state=active]:border-[#8b2332] data-[state=active]:border-b-transparent data-[state=active]:relative data-[state=active]:-mb-[1px] rounded-none rounded-t-md focus-visible:ring-offset-0 focus-visible:ring-2 focus-visible:ring-[#8b2332] focus:z-10 hover:bg-gray-50"
                  >
                    {dept.shortName}
                  </TabsTrigger>
                ))}
              </TabsList>
              {dropdownTabConfigs.length > 0 && (
                <div className="relative flex-shrink-0 border border-b-0 border-[#d3c7b9] rounded-t-md overflow-hidden self-stretch">
                  <DepartmentsDropdown
                    departments={dropdownTabConfigs}
                    onSelectDepartment={handleDropdownSelect}
                    isActive={
                      !!activeTabId &&
                      !mainTabConfigs.some((mt) => mt.id === activeTabId)
                    }
                    className="h-full"
                  />
                </div>
              )}
            </div>

            {allDepartmentConfigs.map((dept) => (
              <TabsContent
                key={dept.id}
                value={dept.id}
                className="border border-t-0 border-[#d3c7b9] bg-white p-6 data-[state=inactive]:hidden mt-0 rounded-b-md shadow-sm"
                forceMount
              >
                {activeTabId === dept.id ? (
                  isLoadingTabData ? (
                    <div className="space-y-4">
                      <Skeleton className="h-20 w-1/2 bg-gray-200" />
                      <Skeleton className="h-8 w-1/3 bg-gray-200" />
                      <Skeleton className="h-40 w-full bg-gray-200" />
                      <Skeleton className="h-40 w-full bg-gray-200" />
                    </div>
                  ) : error ? (
                    <div className="text-center py-10 text-red-600 bg-red-100 border border-red-400 p-4">
                      {error}
                    </div>
                  ) : activeDepartmentData ? (
                    <MinisterSection
                      departmentPageData={activeDepartmentData}
                      departmentFullName={dept.fullName}
                      departmentShortName={dept.shortName}
                    />
                  ) : (
                    <div className="text-center py-10 text-gray-500">
                      Select a department.
                    </div>
                  )
                ) : null}
              </TabsContent>
            ))}
          </Tabs>
        )}
        {!isLoadingConfig && allDepartmentConfigs.length === 0 && !error && (
          <div className="text-center my-4">No departments to display.</div>
        )}
      </div>
    </main>
  );
}
