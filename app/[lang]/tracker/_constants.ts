import { firestoreAdmin } from "@/lib/firebaseAdmin";
import type { DepartmentConfig } from "@/lib/types";
import { Timestamp } from "firebase-admin/firestore";


// Define display order for other departments
export const DEPARTMENT_DISPLAY_ORDER: Record<string, number> = {
  'prime-minister-office': 1, // Prime Minister is first
  'finance-canada': 2,
  'infrastructure-canada': 3, // Housing
  'national-defence': 4,
  'immigration-refugees-and-citizenship-canada': 5, // Immigration
  'treasury-board-of-canada-secretariat': 6, // Government
  'natural-resources-canada': 7, // Energy
  'transport-canada': 8, // Internal Trade
  'innovation-science-and-economic-development-canada': 9, // Industry
  'artificial-intelligence-and-digital-innovation': 10, // Digital Innovation
  'health-canada': 11,
};

export const fetchDeptConfigs = async (currentSessionId?: string | null) => {

  // return [ALL_DEPT_CONFIGS, MAIN_DEPT_CONFIGS];
  let initialAllDepartmentConfigs: DepartmentConfig[] = [];
  let initialMainTabConfigs: DepartmentConfig[] = [];
  const t0 = Date.now();

  const configsSnapshot = await firestoreAdmin
    .collection("department_config")
    .get();
  console.log(
    `[Server LCP Timing] department_config fetch took ${Date.now() - t0} ms`,
  );
  initialAllDepartmentConfigs = configsSnapshot.docs
    .map((doc) => {
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
    .sort((a, b) =>
      (a.display_short_name || "").localeCompare(b.display_short_name || ""),
    );

  console.log(
    `[Server LCP Debug] Fetched ${initialAllDepartmentConfigs.length} total department configs.`,
  );

  initialMainTabConfigs = initialAllDepartmentConfigs.filter(
    (c) => c.bc_priority === 1,
  );
  console.log(
    `[Server LCP Debug] Filtered to ${initialMainTabConfigs.length} main tab department configs.`,
  );

  const allDepartmentConfigsWithOrder = initialAllDepartmentConfigs.map(
    (config) => {
      const baseConfig = {
        ...config,
        display_order: DEPARTMENT_DISPLAY_ORDER[config.id] ?? 999, // Use nullish coalescing for safety
      };

      return baseConfig;
    },
  );

  const allDeptConfigs = [
    ...allDepartmentConfigsWithOrder,
  ];

  let mainDeptConfigs = allDeptConfigs.sort(
    (a, b) => (a.display_order ?? 999) - (b.display_order ?? 999),
  );

  mainDeptConfigs = mainDeptConfigs.filter(
    (config) => config.bc_priority === 1,
  );

  // use these to generate the constants above

  return [allDeptConfigs, mainDeptConfigs];
};