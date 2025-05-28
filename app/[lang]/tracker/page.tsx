import { firestoreAdmin } from "@/lib/firebaseAdmin"; // Server-side Firestore
import HomePageClient from "@/components/HomePageClient"; // NEW IMPORT
import { Timestamp } from "firebase-admin/firestore"; // Import admin Timestamp
import { fetchMinisterForDepartmentInSessionAdmin } from "@/lib/server-utils"; // MOVED FUNCTION

import type {
  DepartmentConfig,
  PrimeMinister,
  ParliamentSession,
  MinisterInfo, // NEW IMPORT
  Member // NEW IMPORT (for internal use in fetchMinisterForDepartmentInSessionAdmin)
} from "@/lib/types"

const DEFAULT_PLACEHOLDER_AVATAR = "/placeholder.svg?height=100&width=100";

// Static data for the Prime Minister section, to be made dynamic based on session of parliament
const staticPrimeMinisterData: PrimeMinister = {
  name: "Justin Trudeau", // Example Name
  title: "Prime Minister, 44th Parliament of Canada",
  avatarUrl: "/placeholder.svg?height=200&width=200", // Example avatar
};

// Define a darker border color, e.g., a dark gray from Tailwind's palette or black
const DARK_BORDER_COLOR = "border-neutral-700"; 
const HEADER_BOTTOM_BORDER_COLOR = "border-neutral-400"; 
const NAV_LINK_TEXT_COLOR = "text-neutral-800";
const NAV_LINK_ACTIVE_TEXT_COLOR = "text-[#8b2332]"; 

// --- Server-Side Data Fetching and Main Page Component ---

async function getGlobalSessionData(): Promise<ParliamentSession | null> {
  try {
    const globalConfigDoc = await firestoreAdmin.doc('admin_settings/global_config').get();
    let currentSessionNumberString;
    if (globalConfigDoc.exists && globalConfigDoc.data()?.current_selected_parliament_session) {
      currentSessionNumberString = String(globalConfigDoc.data()?.current_selected_parliament_session);
    } else {
      console.warn("[Server] Global config or current_selected_parliament_session not found, using most recent session as fallback.");
      // Fallback to the most recent session (highest parliament_number)
      const recentSessionQuery = await firestoreAdmin.collection('parliament_session')
        .orderBy('parliament_number', 'desc')
        .limit(1)
        .get();
      
      if (!recentSessionQuery.empty) {
        currentSessionNumberString = recentSessionQuery.docs[0].id;
      } else {
        console.error("[Server] No parliament sessions found.");
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
  let pageTitle = "Outcomes Tracker"; // Default title

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
      // Set Finance as the initial active tab
      initialActiveTabId = 'finance-canada';
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
          console.log(`[Server LCP Debug] Pre-fetched minister info for tab '${result.value.id}': ${result.value.info?.name}`);
          if (result.value.id === 'artificial-intelligence-and-digital-innovation') {
            console.log(`[Server LCP DEBUG - AI & Innovation Tab MinisterInfo]: parliament_session_id: ${globalSession?.id}, minister_info_payload: ${JSON.stringify(result.value.info, null, 2)}`);
          }
        } else if (result.status === 'rejected') {
          // Log error for specific department if its minister fetch failed
          // We need to find which config.id corresponds to the failed promise.
          // This requires a bit more effort if ministerFetchPromises doesn't directly carry the id upon rejection.
          // For now, logging the reason.
          console.error(`[Server LCP Error] Failed to pre-fetch minister for a tab. Reason:`, result.reason);
        } else if (result.status === 'fulfilled' && result.value && !result.value.info) {
           // Handle cases where the fetch was successful but no minister info was returned (logged by utility fn)
           initialMinisterInfos[result.value.id] = null; // Explicitly set to null
           console.log(`[Server LCP Debug] Pre-fetched minister for tab '${result.value.id}': No minister info returned (null).`);
        }
      });

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
  } : { 
    name: "N/A", 
    title: "Prime Minister data unavailable", 
    avatarUrl: staticPrimeMinisterData.avatarUrl, 
  };

  // Add Prime Minister as a department
  const primeMinisterDepartment: DepartmentConfig = {
    id: 'prime-minister',
    official_full_name: 'Office of the Prime Minister',
    display_short_name: 'Prime Minister',
    bc_priority: 1,
    is_prime_minister: true,
    department_slug: 'prime-minister',
    display_order: 1 // Prime Minister is first
  };

  // Define display order for other departments
  const departmentDisplayOrder: Record<string, number> = {
    'finance-canada': 2,
    'infrastructure-canada': 3, // Housing
    'national-defence': 4,
    'immigration-refugees-and-citizenship-canada': 5, // Immigration
    'treasury-board-of-canada-secretariat': 6, // Government
    'natural-resources-canada': 7, // Energy
    'innovation-science-and-economic-development-canada': 8,
    'artificial-intelligence-and-digital-innovation': 8, // Also Innovation
    'health-canada': 9
  };

  // Add display_order to all department configs and override display names where needed
  // Ensure all departments get a display_order, defaulting if not in map
  const allDepartmentConfigsWithOrder = initialAllDepartmentConfigs.map(config => {
    const baseConfig = {
      ...config,
      display_order: departmentDisplayOrder[config.id] ?? 999 // Use nullish coalescing for safety
    };

    return baseConfig;
  });

  // Combine Prime Minister and all other departments
  const allDepartmentsCombined = [primeMinisterDepartment, ...allDepartmentConfigsWithOrder];

  // Sort the combined list entirely by display_order
  const sortedAllDepartmentConfigs = allDepartmentsCombined
    .sort((a, b) => (a.display_order ?? 999) - (b.display_order ?? 999));

  // Filter to get main tab configs (bc_priority === 1) from the fully sorted list
  let mainTabConfigsWithPM = sortedAllDepartmentConfigs.filter(config => config.bc_priority === 1);

  // Apply parliament-based filtering for ISED/AIDI on the server
  if (currentSessionId?.startsWith("44")) {
    mainTabConfigsWithPM = mainTabConfigsWithPM.filter(
      config => config.id !== 'artificial-intelligence-and-digital-innovation'
    );
  } else if (currentSessionId?.startsWith("45")) {
    mainTabConfigsWithPM = mainTabConfigsWithPM.filter(
      config => config.id !== 'innovation-science-and-economic-development-canada'
    );
  } else {
    const aidiExists = mainTabConfigsWithPM.some(c => c.id === 'artificial-intelligence-and-digital-innovation');
    if (aidiExists) {
      mainTabConfigsWithPM = mainTabConfigsWithPM.filter(config => config.id !== 'innovation-science-and-economic-development-canada');
    }
  }

  // Add PM to minister infos
  const ministerInfosWithPM = {
    ...initialMinisterInfos,
    'prime-minister': {
      name: dynamicPrimeMinisterData.name,
      title: dynamicPrimeMinisterData.title,
      avatarUrl: dynamicPrimeMinisterData.avatarUrl,
      positionStart: globalSession?.start_date,
      positionEnd: globalSession?.end_date || undefined,
      effectiveDepartmentOfficialFullName: 'Office of the Prime Minister',
    }
  };

  return <HomePageClient 
            initialAllDepartmentConfigs={sortedAllDepartmentConfigs}
            initialMainTabConfigs={mainTabConfigsWithPM}
            initialMinisterInfos={ministerInfosWithPM}
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
