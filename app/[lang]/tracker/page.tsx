import { firestoreAdmin } from "@/lib/firebaseAdmin"; // Server-side Firestore
// "use client" // REMOVE THIS - This page will now be a Server Component primarily

// Client-side imports are now in HomePageClient.tsx
// import { useState, useEffect, useCallback } from "react" // MOVED
// import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs" // MOVED
// import PrimeMinisterSection from "@/components/PrimeMinisterSection" // MOVED to HomePageClient
// import MinisterSection from "@/components/MinisterSection" // MOVED to HomePageClient
// import DepartmentsDropdown from "@/components/DepartmentsDropdown" // No longer needed

// Data fetching functions are used by HomePageClient, but types might be needed here or there.
// import {
//   fetchMinisterDetails,
//   fetchPromisesForDepartment,
//   fetchEvidenceItemsForPromises
// } from "@/lib/data" 

import HomePageClient from "@/components/HomePageClient"; // NEW IMPORT
import { Timestamp } from "firebase-admin/firestore"; // Import admin Timestamp
import { fetchMinisterForDepartmentInSessionAdmin } from "@/lib/server-utils"; // MOVED FUNCTION

import type {
  DepartmentConfig,
  // DepartmentPageData, // Used by HomePageClient
  // MinisterDetails, // Used by HomePageClient
  // PromiseData, // Used by HomePageClient
  // EvidenceItem, // Used by HomePageClient
  // Metric, // Not actively used in current server component logic
  PrimeMinister,
  ParliamentSession,
  MinisterInfo, // NEW IMPORT
  Member // NEW IMPORT (for internal use in fetchMinisterForDepartmentInSessionAdmin)
  // ParliamentaryPosition // Not directly used in Home, but Member uses it
} from "@/lib/types"
// import { Skeleton } from "@/components/ui/skeleton" // MOVED to HomePageClient

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
// This constant is not currently used in the logic to sort initialMainTabConfigs but kept for potential future use.
const MAIN_TAB_ORDER: string[] = [
  "Infrastructure Canada", 
  "National Defence",
  "Health Canada",        
  "Finance Canada",
  "Immigration, Refugees and Citizenship Canada",
  "Employment and Social Development Canada",
];

// Define a darker border color, e.g., a dark gray from Tailwind's palette or black
const DARK_BORDER_COLOR = "border-neutral-700"; 
const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400"; 
const NAV_LINK_TEXT_COLOR = "text-neutral-800";
const NAV_LINK_ACTIVE_TEXT_COLOR = "text-[#8b2332]"; 

// Client-side component to handle the dynamic parts that need state and effects
// MOVED to PromiseTracker/components/HomePageClient.tsx

// --- Server-Side Data Fetching and Main Page Component ---

// Function to fetch minister details (REVISED to use department_ministers)
// MOVED to lib/server-utils.ts
// async function fetchMinisterForDepartmentInSessionAdmin(
// ... entire function removed ...
// )

async function getGlobalSessionData(): Promise<ParliamentSession | null> {
  try {
    const globalConfigDoc = await firestoreAdmin.doc('admin_settings/global_config').get();
    let currentSessionNumberString;
    if (globalConfigDoc.exists && globalConfigDoc.data()?.current_selected_parliament_session) {
      currentSessionNumberString = String(globalConfigDoc.data()?.current_selected_parliament_session);
    } else {
      console.warn("[Server] Global config or current_selected_parliament_session not found, attempting to use 'is_current_for_tracking'.");
      const fallbackSessionQuery = await firestoreAdmin.collection('parliament_session').where('is_current_for_tracking', '==', true).limit(1).get();
      if (!fallbackSessionQuery.empty) {
        currentSessionNumberString = fallbackSessionQuery.docs[0].id;
      } else {
        console.error("[Server] No default or fallback session found.");
        return null;
      }
    }
    const sessionDoc = await firestoreAdmin.collection('parliament_session').doc(currentSessionNumberString).get();
    if (!sessionDoc.exists) {
      console.error(`[Server] Parliament session document ${currentSessionNumberString} not found.`);
      return null; 
    }
    const sessionData = sessionDoc.data();
    if (!sessionData) return null;

    const serializedSessionData = { ...sessionData };
    for (const key of ['start_date', 'end_date', 'election_date_preceding', 'election_called_date']) {
      if (serializedSessionData[key] instanceof Timestamp) {
        serializedSessionData[key] = (serializedSessionData[key] as Timestamp).toDate().toISOString();
      } else if (typeof serializedSessionData[key] === 'string' && !serializedSessionData[key].includes('T')) {
        // If it's a date string without time, ensure it can be parsed by new Date()
        // This might not be necessary if Firestore always gives ISO strings or Timestamps
      }
    }
    
    if (typeof serializedSessionData.governing_party_code !== 'string') {
        // console.warn(`[Server] governing_party_code is missing or not a string for session ${sessionDoc.id}.`);
        //  serializedSessionData.governing_party_code = null; // Keep as is, or default if strictly needed elsewhere
    }

    return { id: sessionDoc.id, ...serializedSessionData } as ParliamentSession;
  } catch (error) {
    console.error("[Server] Error fetching global session data:", error);
    return null;
  }
}

export default async function Home() {
  const globalSession = await getGlobalSessionData();
  const currentSessionId = globalSession ? globalSession.id : null;
  const currentGoverningPartyCode = globalSession ? (globalSession.governing_party_code || null) : null;

  console.log("[Server LCP Debug] Global Session Data:", globalSession);
  console.log("[Server LCP Debug] Current Session ID:", currentSessionId);
  console.log("[Server LCP Debug] Current Governing Party Code:", currentGoverningPartyCode);

  let initialAllDepartmentConfigs: DepartmentConfig[] = [];
  let initialMainTabConfigs: DepartmentConfig[] = [];
  let initialMinisterInfos: Record<string, MinisterInfo | null> = {};
  let initialActiveTabId: string = "";
  let initialDepartmentPromises: Record<string, any[]> = {}; // Using any[] for now
  let initialEvidenceItems: Record<string, any[]> = {}; // Using any[] for now
  let serverError: string | null = null;
  let pageTitle = "Build Canada Promise Tracker"; // Default title

  try {
    const t0 = Date.now();
    const configsSnapshot = await firestoreAdmin.collection("department_config").get();
    console.log(`[Server LCP Timing] department_config fetch took ${Date.now() - t0} ms`);
    initialAllDepartmentConfigs = configsSnapshot.docs.map(doc => {
        const data = doc.data();
        const serializedData: { [key: string]: any } = {};
        for (const key in data) {
          if (data[key] instanceof Timestamp) {
            serializedData[key] = (data[key] as Timestamp).toDate().toISOString();
          } else {
            serializedData[key] = data[key];
          }
        }
        return { id: doc.id, ...serializedData } as DepartmentConfig;
    })
    .sort((a, b) => (a.display_short_name || "").localeCompare(b.display_short_name || ""));
    console.log(`[Server LCP Debug] Fetched ${initialAllDepartmentConfigs.length} total department configs.`);

    initialMainTabConfigs = initialAllDepartmentConfigs.filter(c => c.bc_priority === 1);
    console.log(`[Server LCP Debug] Filtered to ${initialMainTabConfigs.length} main tab department configs.`);

    if (globalSession && initialMainTabConfigs.length > 0) {
      initialActiveTabId = initialMainTabConfigs[0].id;
      // const initialActiveTabConfig = initialMainTabConfigs.find(c => c.id === initialActiveTabId);
      console.log(`[Server LCP Debug] Initial Active Tab ID: ${initialActiveTabId}`);

      // Pre-fetch minister info for ALL main tabs
      const ministerFetchPromises = initialMainTabConfigs.map(config => 
        fetchMinisterForDepartmentInSessionAdmin(config, globalSession)
          .then(info => ({ id: config.id, info }))
      );

      const t_minister_fetches_start = Date.now();
      const settledMinisterInfos = await Promise.allSettled(ministerFetchPromises);
      console.log(`[Server LCP Timing] Fetching all main tab ministers took ${Date.now() - t_minister_fetches_start} ms`);

      settledMinisterInfos.forEach(result => {
        if (result.status === 'fulfilled' && result.value && result.value.info) {
          initialMinisterInfos[result.value.id] = result.value.info;
          console.log(`[Server LCP Debug] Pre-fetched minister info for tab '${result.value.id}':`, result.value.info?.name);
        } else if (result.status === 'rejected') {
          // Log error for specific department if its minister fetch failed
          // The key for initialMinisterInfos won't be set, or explicitly set to null
          // We need to know which department failed. The original map had config.id.
          // This part needs careful handling if map doesn't directly give failed id.
          // For now, let's assume we can log a general error or find the id.
          console.error(`[Server LCP Error] Failed to pre-fetch minister for a tab:`, result.reason);
        }
      });

      // The code below that specifically fetched for initialActiveTabConfig is now covered by the loop above.
      // if (initialActiveTabConfig) {
      //   const t1 = Date.now();
      //   const ministerInfoForActiveTab = await fetchMinisterForDepartmentInSessionAdmin(initialActiveTabConfig, globalSession);
      //   console.log(`[Server LCP Timing] fetchMinisterForDepartmentInSessionAdmin took ${Date.now() - t1} ms`);
      //   if (ministerInfoForActiveTab) {
      //     initialMinisterInfos[initialActiveTabId] = ministerInfoForActiveTab;
      //     console.log(`[Server LCP Debug] Fetched minister info for initial active tab '${initialActiveTabId}':`, ministerInfoForActiveTab);
      //   }
      //   // At this point, we have minister info. We can decide if we need to fetch promises/evidence server-side for the first tab.
      //   // For now, let's just log the minister info.
      // }
    } else if (initialAllDepartmentConfigs.length > 0 && !initialMainTabConfigs.length) {
      // This block executes if there are department configs, but none are marked as bc_priority === 1
      // In this case, there's no initialActiveTabId or initialActiveTabConfig determined from priority tabs.
      // We might want to set a default active tab from allDepartmentConfigs or handle appropriately.
      console.warn("[Server LCP Debug] No priority tabs configured. initialActiveTabId may not be set here.");
      serverError = serverError ? serverError + " No priority tabs configured." : "No priority tabs configured.";
      // If initialActiveTabConfig was referenced here, it would be out of scope. 
      // Ensure logic here doesn't depend on it, or it's derived differently.
    } else if (!initialAllDepartmentConfigs.length) {
      serverError = serverError ? serverError + " No department configurations found." : "No department configurations found.";
    }
  } catch (err: any) {
    console.error("[Server] Error fetching initial department configs or ministers on server:", err);
    serverError = "Failed to load department or minister configurations.";
  }

  const dynamicPrimeMinisterData: PrimeMinister = globalSession ? {
    name: globalSession.prime_minister_name || "N/A",
    title: globalSession.prime_minister_name ? 
           `Prime Minister, ${globalSession.session_label || `Parliament ${globalSession.parliament_number}`}` :
           (globalSession.session_label || `Parliament ${globalSession.parliament_number}`),
    avatarUrl: "/placeholder.svg?height=200&width=200", 
    guidingMetrics: staticPrimeMinisterData.guidingMetrics, 
  } : { 
    name: "N/A", 
    title: "Prime Minister data unavailable", 
    avatarUrl: staticPrimeMinisterData.avatarUrl, 
    guidingMetrics: staticPrimeMinisterData.guidingMetrics 
  };

  return <HomePageClient 
            initialAllDepartmentConfigs={initialAllDepartmentConfigs}
            initialMainTabConfigs={initialMainTabConfigs}
            initialMinisterInfos={initialMinisterInfos} // Pass new minister data
            initialActiveTabId={initialActiveTabId}
            initialError={serverError}
            currentSessionId={currentSessionId}
            currentGoverningPartyCode={currentGoverningPartyCode} 
            dynamicPrimeMinisterData={dynamicPrimeMinisterData}
            pageTitle={pageTitle}
        />;
}

// Make sure logger is defined if used directly in the module scope (it's used in fetchMinister...Admin)
const logger = {
  info: console.log,
  warn: console.warn,
  error: console.error,
  debug: console.debug,
}; // Basic console logger for server-side scope
