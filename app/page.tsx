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

import type {
  DepartmentConfig,
  // DepartmentPageData, // Used by HomePageClient
  // MinisterDetails, // Used by HomePageClient
  // PromiseData, // Used by HomePageClient
  // EvidenceItem, // Used by HomePageClient
  // Metric, // Not actively used in current server component logic
  PrimeMinister,
  ParliamentSession // Added import for ParliamentSession type
} from "@/lib/types"
// import { Skeleton } from "@/components/ui/skeleton" // MOVED to HomePageClient

const DEFAULT_PLACEHOLDER_AVATAR = "/placeholder.svg?height=100&width=100"

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
}

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
]

// Define a darker border color, e.g., a dark gray from Tailwind's palette or black
const DARK_BORDER_COLOR = "border-neutral-700"; 
const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400"; 
const NAV_LINK_TEXT_COLOR = "text-neutral-800";
const NAV_LINK_ACTIVE_TEXT_COLOR = "text-[#8b2332]"; 

// Client-side component to handle the dynamic parts that need state and effects
// MOVED to PromiseTracker/components/HomePageClient.tsx

// --- Server-Side Data Fetching and Main Page Component ---

async function getGlobalSessionData(): Promise<ParliamentSession | null> {
  try {
    const globalConfigDoc = await firestoreAdmin.doc('admin_settings/global_config').get();
    let currentSessionNumberString;
    if (globalConfigDoc.exists && globalConfigDoc.data()?.current_selected_parliament_session) {
      currentSessionNumberString = String(globalConfigDoc.data()?.current_selected_parliament_session);
    } else {
      console.warn("Global config or current_selected_parliament_session not found, attempting to use 'is_current_for_tracking'.");
      const fallbackSessionQuery = await firestoreAdmin.collection('parliament_session').where('is_current_for_tracking', '==', true).limit(1).get();
      if (!fallbackSessionQuery.empty) {
        currentSessionNumberString = fallbackSessionQuery.docs[0].id;
      } else {
        console.error("No default or fallback session found.");
        return null;
      }
    }
    const sessionDoc = await firestoreAdmin.collection('parliament_session').doc(currentSessionNumberString).get();
    if (!sessionDoc.exists) {
      console.error(`Parliament session document ${currentSessionNumberString} not found.`);
      return null; 
    }
    const sessionData = sessionDoc.data();
    if (!sessionData) return null;

    // Ensure date fields are serialized if they are Timestamps
    const serializedSessionData = { ...sessionData };
    for (const key of ['start_date', 'end_date', 'election_date_preceding', 'election_called_date']) {
      if (serializedSessionData[key] instanceof Timestamp) {
        serializedSessionData[key] = (serializedSessionData[key] as Timestamp).toDate().toISOString();
      }
    }
    
    return { id: sessionDoc.id, ...serializedSessionData } as ParliamentSession;
  } catch (error) {
    console.error("Error fetching global session data:", error);
    return null;
  }
}

export default async function Home() {
  const globalSession = await getGlobalSessionData();
  const currentSessionId = globalSession ? globalSession.id : null;

  let initialAllDepartmentConfigs: DepartmentConfig[] = [];
  let initialMainTabConfigs: DepartmentConfig[] = [];
  let initialActiveTabId: string = "";
  let serverError: string | null = null;

  try {
    const configsSnapshot = await firestoreAdmin.collection("department_config").get();
    initialAllDepartmentConfigs = configsSnapshot.docs.map(doc => {
        const data = doc.data();
        let lastUpdatedAtStr: string | undefined = undefined;
        if (data.last_updated_at) {
            if (data.last_updated_at instanceof Timestamp) {
                lastUpdatedAtStr = data.last_updated_at.toDate().toISOString();
            } else if (typeof data.last_updated_at === 'string') {
                lastUpdatedAtStr = data.last_updated_at;
            }
        }
        return { 
            id: doc.id, 
            ...data,
            last_updated_at: lastUpdatedAtStr // Override with serialized version
        } as DepartmentConfig;
    })
    .sort((a, b) => (a.display_short_name || "").localeCompare(b.display_short_name || ""));

    initialMainTabConfigs = initialAllDepartmentConfigs.filter(c => c.bc_priority === 1);
    // If specific order for priority tabs is needed beyond alpha, sort initialMainTabConfigs here.
    // Example using MAIN_TAB_ORDER (would need adjustment if display_short_name is used for tabs but MAIN_TAB_ORDER has official_full_name)
    // initialMainTabConfigs.sort((a, b) => {
    //   const indexA = MAIN_TAB_ORDER.indexOf(a.official_full_name);
    //   const indexB = MAIN_TAB_ORDER.indexOf(b.official_full_name);
    //   if (indexA === -1 && indexB === -1) return (a.display_short_name || "").localeCompare(b.display_short_name || ""); // both not in order, sort alpha
    //   if (indexA === -1) return 1; // a not in order, b is; b comes first
    //   if (indexB === -1) return -1; // b not in order, a is; a comes first
    //   return indexA - indexB; // both in order, sort by order
    // });


    if (initialMainTabConfigs.length > 0) {
      initialActiveTabId = initialMainTabConfigs[0].id;
    } else {
      serverError = "No priority departments found."; // Set error if no priority tabs
      // console.warn("No departments with bc_priority === 1 found. No default active tab.");
    }
  } catch (err: any) {
    console.error("Error fetching initial department configs on server:", err);
    serverError = "Failed to load department configurations.";
  }

  const pageTitle = globalSession ? 
    `Outcomes Tracker - ${globalSession.session_label || `Parliament ${globalSession.parliament_number}`}` :
    "Outcomes Tracker";

  const dynamicPrimeMinisterData: PrimeMinister = globalSession ? {
    name: globalSession.prime_minister_name || "N/A",
    title: globalSession.prime_minister_name ? 
           `Prime Minister, ${globalSession.session_label || `Parliament ${globalSession.parliament_number}`}` :
           (globalSession.session_label || `Parliament ${globalSession.parliament_number}`),
    avatarUrl: "/placeholder.svg?height=200&width=200", // Consistent with staticPrimeMinisterData for PM section
    guidingMetrics: staticPrimeMinisterData.guidingMetrics, // USE STATIC DATA FOR NOW
  } : { 
    name: "N/A", 
    title: "Prime Minister data unavailable", 
    avatarUrl: staticPrimeMinisterData.avatarUrl, // Fallback to static placeholder for PM
    guidingMetrics: staticPrimeMinisterData.guidingMetrics // USE STATIC DATA FOR NOW
  };

  // Pass server-fetched data to the client component
  return <HomePageClient 
            initialAllDepartmentConfigs={initialAllDepartmentConfigs}
            initialMainTabConfigs={initialMainTabConfigs}
            initialActiveTabId={initialActiveTabId}
            initialError={serverError}
            currentSessionId={currentSessionId}
            dynamicPrimeMinisterData={dynamicPrimeMinisterData}
            pageTitle={pageTitle}
        />;
}
