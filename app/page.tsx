"use client"
import { useState, useEffect, useCallback } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import PrimeMinisterSection from "@/components/prime-minister-section"
import MinisterSection from "@/components/minister-section"
import DepartmentsDropdown from "@/components/departments-dropdown"
import {
  fetchDepartmentConfigs,
  fetchMinisterDetails,
  fetchPromisesForDepartment,
  fetchEvidenceItemsForPromises
} from "@/lib/data"
import type {
  DepartmentConfig,
  DepartmentPageData,
  MinisterDetails,
  PromiseData,
  EvidenceItem,
  Metric,
  PrimeMinister,
} from "@/lib/types"
import { Skeleton } from "@/components/ui/skeleton"

const DEFAULT_PLACEHOLDER_AVATAR = "/placeholder.svg?height=100&width=100"

// Static data for the Prime Minister section
const staticPrimeMinisterData: PrimeMinister = {
  name: "Mark Carney", // Example Name
  title: "Prime Minister",
  avatarUrl: "/placeholder.svg?height=200&width=200", // Example avatar
  guidingMetrics: [
    {
      title: "GDP Per Capita",
      data: [45000, 44800, 45200, 45600, 45400, 45800, 46000],
      goal: 48000,
    },
  ],
}

// Define the preferred order for main tabs
// IMPORTANT: These strings MUST exactly match the 'fullName' field 
// in your Firestore 'department_config' collection documents.
// Double-check casing, spacing, and exact wording (e.g., 'and' vs '&').
const MAIN_TAB_ORDER: string[] = [
  "Infrastructure Canada", // CORRECTED - Assuming this is the name in Firestore
  "National Defence",
  "Health Canada",         // CORRECTED - Based on user screenshot
  "Finance Canada",
  "Immigration, Refugees and Citizenship Canada",
  "Employment and Social Development Canada",
]

// Define a darker border color, e.g., a dark gray from Tailwind's palette or black
const DARK_BORDER_COLOR = "border-neutral-700"; // Or use 'border-black'
const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400"; // Slightly less prominent for the overall bottom
const NAV_LINK_TEXT_COLOR = "text-neutral-800";
const NAV_LINK_ACTIVE_TEXT_COLOR = "text-[#8b2332]"; // Your brand red

export default function Home() {
  const [allDepartmentConfigs, setAllDepartmentConfigs] = useState<DepartmentConfig[]>([])
  const [mainTabConfigs, setMainTabConfigs] = useState<DepartmentConfig[]>([])
  const [dropdownTabConfigs, setDropdownTabConfigs] = useState<DepartmentConfig[]>([])
  
  const [activeTabId, setActiveTabId] = useState<string>("")
  const [activeDepartmentData, setActiveDepartmentData] = useState<DepartmentPageData | null>(null)

  const [isLoadingConfig, setIsLoadingConfig] = useState<boolean>(true)
  const [isLoadingTabData, setIsLoadingTabData] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch all department configs on initial mount
  useEffect(() => {
    const loadConfigs = async () => {
      setIsLoadingConfig(true)
      setError(null)
      try {
        const configs = await fetchDepartmentConfigs()
        setAllDepartmentConfigs(configs)

        // Separate configs based on MAIN_TAB_ORDER
        const mainTabs = MAIN_TAB_ORDER.map(fullName => 
          configs.find(c => c.fullName === fullName)
        ).filter((c): c is DepartmentConfig => c !== undefined)

        const mainTabIds = new Set(mainTabs.map(c => c.id))
        const dropdownTabs = configs.filter(c => !mainTabIds.has(c.id))

        setMainTabConfigs(mainTabs)
        setDropdownTabConfigs(dropdownTabs)
        
        // Set the first main tab as active by default if available
        if (mainTabs.length > 0) {
          setActiveTabId(mainTabs[0].id)
        } else if (configs.length > 0) {
          // Fallback to the first config if no main tabs match
          setActiveTabId(configs[0].id)
        }
      } catch (err) {
        console.error("Error fetching department configs:", err)
        setError("Failed to load department configurations.")
      } finally {
        setIsLoadingConfig(false)
      }
    }
    loadConfigs()
  }, [])

  // Fetch data for the active tab whenever activeTabId changes
  useEffect(() => {
    if (!activeTabId) return // Don't fetch if no tab is selected

    const loadTabData = async () => {
      setIsLoadingTabData(true)
      setError(null)
      setActiveDepartmentData(null) // Clear previous data
      
      const selectedConfig = allDepartmentConfigs.find(c => c.id === activeTabId)
      if (!selectedConfig) {
        setError("Could not find configuration for the selected department.")
        setIsLoadingTabData(false)
        return
      }

      const departmentFullName = selectedConfig.fullName

      try {
        // Fetch minister details and promises in parallel
        const [ministerDetails, promises] = await Promise.all([
          fetchMinisterDetails(departmentFullName),
          fetchPromisesForDepartment(departmentFullName)
        ])

        let evidenceItems: EvidenceItem[] = []
        if (promises.length > 0) {
          const promiseIds = promises.map(p => p.id)
          evidenceItems = await fetchEvidenceItemsForPromises(promiseIds)
        }

        setActiveDepartmentData({
          ministerDetails,
          promises,
          evidenceItems
        })

      } catch (err) {
        console.error(`Error fetching data for department ${departmentFullName}:`, err)
        setError(`Failed to load data for ${departmentFullName}.`)
        // Keep activeDepartmentData as null or set to an error state if needed
      } finally {
        setIsLoadingTabData(false)
      }
    }

    loadTabData()
  }, [activeTabId, allDepartmentConfigs])

  // Handler for dropdown selection
  const handleDropdownSelect = useCallback((departmentId: string) => {
    setActiveTabId(departmentId)
    // Optional: Scroll to tabs section if needed
    // document.getElementById('department-tabs')?.scrollIntoView({ behavior: 'smooth' });
  }, [])

  if (isLoadingConfig) {
    return <div className="min-h-screen flex items-center justify-center bg-[#f8f2ea]">Loading configurations...</div>
  }

  return (
    <main className="min-h-screen bg-[#f8f2ea] font-sans">
      <header className={`sticky top-0 z-50 bg-white shadow-sm ${HEADER_BOTTOM_BORDER_COLOR} border-b`}>
        <div className={`mx-auto flex max-w-7xl items-stretch`}>
          <div className={`bg-[#8b2332] p-4 flex items-center ${DARK_BORDER_COLOR} border-r`}> 
            <h1 className="text-xl font-bold text-white">Build Canada</h1>
          </div>
          <nav className="flex flex-1 items-stretch">
            <a 
              href="#"
              className={`flex items-center ${DARK_BORDER_COLOR} border-r px-6 py-4 text-sm font-medium uppercase tracking-wider ${NAV_LINK_TEXT_COLOR} hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#8b2332] transition-colors duration-150 ease-in-out md:px-8`}
            >
              Memos
            </a>
            <a
              href="#"
              className={`flex items-center ${DARK_BORDER_COLOR} border-r px-6 py-4 text-sm font-medium uppercase tracking-wider ${NAV_LINK_ACTIVE_TEXT_COLOR} hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#8b2332] transition-colors duration-150 ease-in-out md:px-8`}
            >
              Platform Tracker
            </a>
            <a 
              href="/about"
              className={`flex items-center ${DARK_BORDER_COLOR} border-r px-6 py-4 text-sm font-medium uppercase tracking-wider ${NAV_LINK_TEXT_COLOR} hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#8b2332] transition-colors duration-150 ease-in-out md:px-8`}
            >
              About
            </a>
            <a 
              href="/contact"
              className={`flex items-center ${DARK_BORDER_COLOR} border-r px-6 py-4 text-sm font-medium uppercase tracking-wider ${NAV_LINK_TEXT_COLOR} hover:bg-gray-100 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-[#8b2332] transition-colors duration-150 ease-in-out md:px-8`}
            >
              Contact
            </a>
          </nav>
        </div>
      </header>

      <div className="container mx-auto max-w-5xl px-4 py-12">
        <h1 className="mb-12 text-center text-5xl font-bold text-[#222222]">Outcomes Tracker</h1>

        <PrimeMinisterSection primeMinister={staticPrimeMinisterData} />

        {error && <div className="text-red-500 text-center my-4">Error: {error}</div>}

        {allDepartmentConfigs.length > 0 && (
          <Tabs value={activeTabId} onValueChange={setActiveTabId} className="mt-16">
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
                    isActive={!!activeTabId && !mainTabConfigs.some(mt => mt.id === activeTabId)}
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
                    />
                  ) : (
                    <div className="text-center py-10 text-gray-500">Select a department.</div>
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
  )
}
