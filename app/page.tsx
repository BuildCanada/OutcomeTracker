"use client"
import { useState, useEffect } from "react"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import PrimeMinisterSection from "@/components/prime-minister-section"
import MinisterSection from "@/components/minister-section"
import DepartmentsDropdown from "@/components/departments-dropdown"
import {
  fetchDepartmentConfigs,
  fetchMinisterDetails,
  fetchPromisesForDepartment,
} from "@/lib/data"
import type {
  DepartmentConfig,
  DepartmentPageData,
  MinisterDetails,
  PromiseData,
  Metric,
  PrimeMinister,
} from "@/lib/types"

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

// Define the desired order and names for the main tabs
// Ensure these shortNames exactly match what's in your Firestore 'department_config' collection
const DESIRED_MAIN_TAB_SHORT_NAMES_ORDER: string[] = [
  "Infrastructure", // Assuming this covers Housing based on common_utils.py mapping
  "Defence",
  "Health",
  "Finance",
  "Immigration",
  "Employment",
]

export default function Home() {
  const [departmentConfigs, setDepartmentConfigs] = useState<DepartmentConfig[]>([])
  const [mainTabConfigs, setMainTabConfigs] = useState<DepartmentConfig[]>([])
  const [dropdownTabConfigs, setDropdownTabConfigs] = useState<DepartmentConfig[]>([])
  
  const [activeTabId, setActiveTabId] = useState<string>("")
  const [activeDepartmentData, setActiveDepartmentData] = useState<DepartmentPageData | null>(null)

  const [isLoadingConfigs, setIsLoadingConfigs] = useState<boolean>(true)
  const [isLoadingContent, setIsLoadingContent] = useState<boolean>(false)
  const [error, setError] = useState<string | null>(null)

  // Fetch initial department configurations for tabs
  useEffect(() => {
    const loadConfigs = async () => {
      setIsLoadingConfigs(true)
      setError(null)
      try {
        const configs = await fetchDepartmentConfigs()
        if (configs && configs.length > 0) {
          setDepartmentConfigs(configs)

          const orderedMainTabs: DepartmentConfig[] = []
          const remainingForDropdown: DepartmentConfig[] = []

          // Create a map for quick lookup of desired main tabs
          const desiredMainSet = new Set(DESIRED_MAIN_TAB_SHORT_NAMES_ORDER)

          // Populate orderedMainTabs based on DESIRED_MAIN_TAB_SHORT_NAMES_ORDER
          for (const shortName of DESIRED_MAIN_TAB_SHORT_NAMES_ORDER) {
            const foundConfig = configs.find(c => c.shortName === shortName)
            if (foundConfig) {
              orderedMainTabs.push(foundConfig)
            }
          }

          // Populate remainingForDropdown with configs not in orderedMainTabs
          for (const config of configs) {
            if (!orderedMainTabs.find(mt => mt.id === config.id)) {
              remainingForDropdown.push(config)
            }
          }
          // remainingForDropdown is already sorted alphabetically from fetchDepartmentConfigs

          setMainTabConfigs(orderedMainTabs)
          setDropdownTabConfigs(remainingForDropdown)
          
          // Set initial active tab to the first of the *ordered* main tabs, or first available config
          setActiveTabId(orderedMainTabs[0]?.id || configs[0]?.id || "")
        } else {
          setError("No department configurations found.")
        }
      } catch (err) {
        console.error("Failed to load department configs:", err)
        setError("Failed to load department configurations.")
      }
      setIsLoadingConfigs(false)
    }
    loadConfigs()
  }, [])

  // Fetch content for the active tab when activeTabId changes
  useEffect(() => {
    if (!activeTabId || departmentConfigs.length === 0) {
      // If no active tab or configs not loaded, clear content and don't fetch
      setActiveDepartmentData(null)
      return
    }

    const selectedConfig = departmentConfigs.find(c => c.id === activeTabId)

    if (!selectedConfig) {
      // Should not happen if activeTabId is derived from departmentConfigs
      console.warn(`No config found for activeTabId: ${activeTabId}`)
      setActiveDepartmentData(null)
      setError("Could not find configuration for the selected department.")
      return
    }

    const loadDepartmentContent = async () => {
      setIsLoadingContent(true)
      setError(null)
      try {
        const ministerDetailsData = await fetchMinisterDetails(selectedConfig.fullName)
        const promisesData = await fetchPromisesForDepartment(selectedConfig.fullName)

        // Placeholder for guiding metrics - to be replaced with actual data later
        const guidingMetricsPlaceholder: Metric[] = [
          {
            title: "Placeholder Metric (e.g., Emissions Reduction Mt CO2e)",
            data: [730, 720, 710, 700, 690, 680, 670],
            goal: 500,
          },
        ]

        setActiveDepartmentData({
          id: selectedConfig.id,
          shortName: selectedConfig.shortName,
          fullName: selectedConfig.fullName,
          ministerDetails: ministerDetailsData ? 
            { ...ministerDetailsData, avatarUrl: ministerDetailsData.avatarUrl || DEFAULT_PLACEHOLDER_AVATAR } : 
            { avatarUrl: DEFAULT_PLACEHOLDER_AVATAR } as MinisterDetails,
          promises: promisesData,
          guidingMetrics: guidingMetricsPlaceholder, // Use placeholder for now
        })

      } catch (err) {
        console.error(`Failed to load content for ${selectedConfig.shortName}:`, err)
        setError(`Failed to load content for ${selectedConfig.shortName}.`)
        setActiveDepartmentData(null) // Clear data on error
      }
      setIsLoadingContent(false)
    }

    loadDepartmentContent()
  }, [activeTabId, departmentConfigs])

  const handleTabChange = (tabId: string) => {
    setActiveTabId(tabId)
  }
  
  // The handleDepartmentSelect for the dropdown will now directly set the activeTabId
  const handleDropdownSelect = (departmentId: string) => {
    setActiveTabId(departmentId)
  }

  if (isLoadingConfigs) {
    return <div className="min-h-screen flex items-center justify-center bg-[#f8f2ea]">Loading configurations...</div>
  }

  return (
    <main className="min-h-screen bg-[#f8f2ea] font-sans">
      <header className="border-b border-[#d3c7b9] bg-white">
        <div className="mx-auto flex max-w-7xl items-center">
          <div className="bg-[#8b2332] p-4 text-white">
            <h1 className="text-xl font-bold">Build Canada</h1>
          </div>
          <nav className="flex flex-1 justify-around border-l border-[#d3c7b9]">
            <a href="#" className="border-r border-[#d3c7b9] px-8 py-4 text-sm font-medium uppercase tracking-wider">
              Memos
            </a>
            <a
              href="#"
              className="border-r border-[#d3c7b9] px-8 py-4 text-sm font-medium uppercase tracking-wider text-[#8b2332]"
            >
              Platform Tracker
            </a>
            <a href="#" className="border-r border-[#d3c7b9] px-8 py-4 text-sm font-medium uppercase tracking-wider">
              About
            </a>
            <a href="#" className="px-8 py-4 text-sm font-medium uppercase tracking-wider">
              Contact
            </a>
          </nav>
        </div>
      </header>

      <div className="container mx-auto max-w-5xl px-4 py-12">
        <h1 className="mb-12 text-center text-5xl font-bold text-[#222222]">Outcomes Tracker</h1>

        <PrimeMinisterSection primeMinister={staticPrimeMinisterData} />

        {error && <div className="text-red-500 text-center my-4">Error: {error}</div>}

        {departmentConfigs.length > 0 && (
          <Tabs value={activeTabId} onValueChange={handleTabChange} className="mt-16">
            <TabsList className="grid w-full grid-cols-3 md:grid-cols-7 bg-transparent p-0">
              {mainTabConfigs.map((config) => (
                <TabsTrigger
                  key={config.id}
                  value={config.id}
                  className="border border-[#d3c7b9] bg-white px-3 py-3 text-sm uppercase whitespace-normal data-[state=active]:bg-[#8b2332] data-[state=active]:text-white h-full flex items-center justify-center text-center"
                >
                  {config.shortName}
                </TabsTrigger>
              ))}
              {dropdownTabConfigs.length > 0 && (
                <div
                   className={`border border-[#d3c7b9] ${!mainTabConfigs.find(mc => mc.id === activeTabId) && activeTabId ? "bg-[#8b2332] text-white" : "bg-white"}`}
                >
                  <DepartmentsDropdown 
                    departments={dropdownTabConfigs} 
                    onSelectDepartment={handleDropdownSelect} 
                    isActive={!mainTabConfigs.find(mc => mc.id === activeTabId) && !!activeTabId} 
                  />
                </div>
              )}
            </TabsList>

            {/* Single TabsContent area that updates based on activeTabId and activeDepartmentData */} 
            {activeTabId && (
                <TabsContent
                    key={activeTabId} // Ensures re-render on tab change
                    value={activeTabId} 
                    className="border border-t-0 border-[#d3c7b9] bg-white p-6"
                >
                    {isLoadingContent && <div>Loading department details...</div>}
                    {!isLoadingContent && activeDepartmentData && (
                        <MinisterSection departmentPageData={activeDepartmentData} />
                    )}
                    {!isLoadingContent && !activeDepartmentData && !error && (
                        <div>Select a department to see details.</div>
                    )}
                     {/* Error specific to content loading could be displayed here too */} 
                </TabsContent>
            )}
          </Tabs>
        )}
        {!isLoadingConfigs && departmentConfigs.length === 0 && !error && (
           <div className="text-center my-4">No departments to display.</div>
        )}
      </div>
    </main>
  )
}
