import { DepartmentPillLinks, Sidebar } from "@/components/HomePageClient";
import { DepartmentProvider } from "@/context/DepartmentContext";
import { firestoreAdmin } from "@/lib/firebaseAdmin";
import { DepartmentConfig } from "@/lib/types";
import { Timestamp } from "firebase-admin/firestore";
import { DEPARTMENT_DISPLAY_ORDER } from "./_constants";

const CURRENT_SESSION_NUMBER = "45";

export default async function Layout({
  children,
}: Readonly<{
  children: React.ReactNode;
  params: { lang: string; department?: string };
}>) {
  const sessionDoc = await firestoreAdmin
    .collection("parliament_session")
    .doc(CURRENT_SESSION_NUMBER)
    .get();
  const sessionData = sessionDoc.data();

  const [allDeptConfigs, mainTabConfigsWithPM] = await fetchDeptConfigs(
    CURRENT_SESSION_NUMBER,
  );
  return (
    <div className="min-h-screen">
      <div className="container px-4 py-12">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <Sidebar pageTitle="Outcomes Tracker" />
          <div className="col-span-3">
            <DepartmentProvider
              allDeptConfigs={allDeptConfigs}
              mainTabConfigs={mainTabConfigsWithPM}
              sessionId={CURRENT_SESSION_NUMBER}
              governingParty={sessionData?.governing_party_code}
            >
              <DepartmentPillLinks mainTabConfigs={mainTabConfigsWithPM} />
              {children}
            </DepartmentProvider>
          </div>
        </div>
      </div>
    </div>
  );
}

const fetchDeptConfigs = async (currentSessionId?: string | null) => {
  // To speed this up, this is manually cached
  //

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
    {
      id: "prime-minister",
      official_full_name: "Office of the Prime Minister",
      display_short_name: "Prime Minister",
      bc_priority: 1,
      is_prime_minister: true,
      department_slug: "prime-minister",
      display_order: 1, // Prime Minister is first
    } as DepartmentConfig,
    ...allDepartmentConfigsWithOrder,
  ];

  let mainDeptConfigs = allDeptConfigs.sort(
    (a, b) => (a.display_order ?? 999) - (b.display_order ?? 999),
  );

  mainDeptConfigs = mainDeptConfigs.filter(
    (config) => config.bc_priority === 1,
  );

  return [allDeptConfigs, mainDeptConfigs];
};
