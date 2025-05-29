import { firestoreAdmin } from "@/lib/firebaseAdmin";
import type { DepartmentConfig } from "@/lib/types";
import { Timestamp } from "firebase-admin/firestore";

export const ALL_DEPT_CONFIGS: DepartmentConfig[] = [
  {
    id: "prime-minister",
    official_full_name: "Office of the Prime Minister",
    display_short_name: "Prime Minister",
    bc_priority: 1,
    is_prime_minister: true,
    department_slug: "prime-minister",
    display_order: 1,
  },
  {
    id: "finance-canada",
    notes: null,
    official_full_name: "Finance Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "finance-canada",
    bc_priority: 1,
    display_short_name: "Finance",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "deputy prime minister and minister of finance",
      "minister of finance",
      "minister of finance and national revenue",
    ],
    display_order: 2,
  },
  {
    id: "infrastructure-canada",
    notes: null,
    official_full_name: "Infrastructure Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "infrastructure-canada",
    bc_priority: 1,
    display_short_name: "Housing",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of housing and diversity and inclusion",
      "minister of intergovernmental affairs, infrastructure and communities",
      "minister of housing and infrastructure",
    ],
    display_order: 3,
  },
  {
    id: "national-defence",
    notes: null,
    official_full_name: "National Defence",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "national-defence",
    bc_priority: 1,
    display_short_name: "Defence",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of national defence",
      "secretary of state (defence procurement)",
    ],
    display_order: 4,
  },
  {
    id: "immigration-refugees-and-citizenship-canada",
    notes: null,
    official_full_name: "Immigration, Refugees and Citizenship Canada",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: ["minister of immigration, refugees and citizenship"],
    department_slug: "immigration-refugees-and-citizenship-canada",
    bc_priority: 1,
    display_short_name: "Immigration",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 5,
  },
  {
    id: "treasury-board-of-canada-secretariat",
    notes: null,
    official_full_name: "Treasury Board of Canada Secretariat",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: [
      "minister of citizens' services",
      "president of the treasury board",
      "treasury board of canada secretariat",
    ],
    department_slug: "treasury-board-of-canada-secretariat",
    bc_priority: 1,
    display_short_name: "Government Transformation",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 6,
  },
  {
    id: "natural-resources-canada",
    notes: null,
    official_full_name: "Natural Resources Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "natural-resources-canada",
    bc_priority: 1,
    display_short_name: "Energy",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of natural resources",
      "natural resources canada",
      "minister of energy and natural resources",
    ],
    display_order: 7,
  },
  {
    id: "artificial-intelligence-and-digital-innovation",
    bc_priority: 1,
    department_slug: "artificial-intelligence-and-digital-innovation",
    display_short_name: "Innovation",
    last_updated_at: "2025-05-17T20:39:27.226Z",
    last_updated_by: "Manual",
    notes: "",
    official_full_name: "Artificial Intelligence and Digital Innovation",
    name_variants: [
      "minister of innovation, science and industry",
      "minister of artificial intelligence and digital innovation",
    ],
    display_order: 8,
  },
  {
    id: "innovation-science-and-economic-development-canada",
    notes: null,
    official_full_name: "Innovation, Science and Economic Development Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "innovation-science-and-economic-development-canada",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    updated_at: "2025-05-17T21:14:30.910Z",
    name_variants: [
      "secretary of state (small business and tourism)",
      "minister of innovation, science and industry",
      "Secretary of State (Small Business and Tourism)",
      "minister of tourism and associate minister of finance",
      "minister of industry",
    ],
    display_short_name: "Innovation",
    bc_priority: 1,
    display_order: 8,
  },
  {
    id: "health-canada",
    notes: null,
    official_full_name: "Health Canada",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: [
      "minister of health",
      "minister of mental health and addictions and associate minister of health",
    ],
    department_slug: "health-canada",
    bc_priority: 1,
    display_short_name: "Health",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 9,
  },
  {
    id: "atlantic-canada-opportunities-agency",
    notes: "Added by populate_new_department_configs.py script",
    official_full_name: "Atlantic Canada Opportunities Agency",
    department_slug: "atlantic-canada-opportunities-agency",
    name_variants: [
      "minister responsible for the atlantic canada opportunities agency",
      "Minister responsible for the Atlantic Canada Opportunities Agency",
    ],
    bc_priority: 2,
    minister_of_state: false,
    display_short_name: "ACOA",
    updated_at: "2025-05-17T21:14:30.687Z",
    created_at: "2025-05-17T21:14:30.687Z",
    display_order: 999,
  },
  {
    id: "agriculture-and-agri-food-canada",
    notes: null,
    official_full_name: "Agriculture and Agri-Food Canada",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: ["minister of agriculture and agri-food"],
    department_slug: "agriculture-and-agri-food-canada",
    bc_priority: 2,
    display_short_name: "Agriculture",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 999,
  },
  {
    id: "canada-economic-development-for-quebec-regions",
    notes: "Added by populate_new_department_configs.py script",
    official_full_name: "Canada Economic Development for Quebec Regions",
    department_slug: "canada-economic-development-for-quebec-regions",
    name_variants: [
      "minister responsible for canada economic development for quebec regions",
      "Minister responsible for Canada Economic Development for Quebec Regions",
    ],
    bc_priority: 2,
    minister_of_state: false,
    display_short_name: "CED Quebec",
    updated_at: "2025-05-17T21:14:30.625Z",
    created_at: "2025-05-17T21:14:30.625Z",
    display_order: 999,
  },
  {
    id: "crown-indigenous-relations-and-northern-affairs-canada",
    notes: null,
    official_full_name:
      "Crown-Indigenous Relations and Northern Affairs Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "crown-indigenous-relations-and-northern-affairs-canada",
    bc_priority: 2,
    display_short_name: "Crown-Indigenous Relations",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of crown-indigenous relations",
      "minister of northern affairs, minister responsible for prairies economic development canada and minister responsible for the canadian northern economic development agency",
      "minister of northern affairs, minister responsible for prairies economic development canada, and minister responsible for the canadian northern economic development agency",
      "minister of northern and arctic affairs",
      "minister of northern and arctic affairs and minister responsible for the canadian northern economic development agency",
    ],
    display_order: 999,
  },
  {
    id: "emergency-preparedness-canada",
    notes: null,
    official_full_name: "Emergency Preparedness Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "emergency-preparedness-canada",
    bc_priority: 2,
    display_short_name: "Emergency Preparedness",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "president of the king's privy council for canada and minister of emergency preparedness",
      "minister of emergency management and community resilience",
    ],
    display_order: 999,
  },
  {
    id: "employment-and-social-development-canada",
    notes: null,
    official_full_name: "Employment and Social Development Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "employment-and-social-development-canada",
    bc_priority: 2,
    display_short_name: "Employment",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of employment, workforce development and disability inclusion",
      "minister of seniors",
      "minister of jobs and families",
      "secretary of state (labour)",
      "secretary of state (seniors)",
      "secretary of state (children and youth)",
      "minister of labour",
      "minister of families, children and social development",
      "Secretary of State (Children and Youth)",
    ],
    updated_at: "2025-05-17T21:14:30.797Z",
    display_order: 999,
  },
  {
    id: "environment-and-climate-change-canada",
    notes: null,
    official_full_name: "Environment and Climate Change Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "environment-and-climate-change-canada",
    bc_priority: 2,
    display_short_name: "Environment",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of environment and climate change",
      "secretary of state (nature)",
      "environment and climate change canada",
    ],
    display_order: 999,
  },
  {
    id: "federal-economic-development-agency-for-southern-ontario",
    notes: null,
    official_full_name:
      "Federal Economic Development Agency for Southern Ontario",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: [
      "minister responsible for the federal economic development agency for southern ontario",
    ],
    department_slug: "federal-economic-development-agency-for-southern-ontario",
    bc_priority: 2,
    display_short_name: "FedDev Ontario",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 999,
  },
  {
    id: "fisheries-and-oceans-canada",
    notes: null,
    official_full_name: "Fisheries and Oceans Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "fisheries-and-oceans-canada",
    bc_priority: 2,
    display_short_name: "Fisheries",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of fisheries, oceans and canadian coast guard",
      "minister of fisheries, oceans and the canadian coast guard",
      "minister of fisheries",
    ],
    display_order: 999,
  },
  {
    id: "global-affairs-canada",
    notes: null,
    official_full_name: "Global Affairs Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "global-affairs-canada",
    bc_priority: 2,
    display_short_name: "Foreign Affairs",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of international trade, export promotion, small business and economic development",
      "minister of foreign affairs",
      "Secretary of State (International Development)",
      "minister of international trade",
      "secretary of state (international development)",
      "Minister of International Trade",
      "minister of international development and minister responsible for the pacific economic development agency of canada",
      "minister responsible for pacific economic development canada",
      "ministre of foreign affairs",
    ],
    updated_at: "2025-05-17T21:14:30.836Z",
    display_order: 999,
  },
  {
    id: "women-and-gender-equality-canada",
    notes: null,
    official_full_name: "Women and Gender Equality Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "women-and-gender-equality-canada",
    bc_priority: 2,
    display_short_name: "Gender Equality",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister for women and gender equality and youth",
      "women and gender equality canada",
      "minister of women and gender equality",
    ],
    display_order: 999,
  },
  {
    id: "canadian-heritage",
    notes: null,
    official_full_name: "Canadian Heritage",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "canadian-heritage",
    bc_priority: 2,
    display_short_name: "Heritage",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of canadian heritage",
      "minister of canadian heritage and quebec lieutenant",
      "minister of official languages",
      "minister of official languages and minister responsible for the atlantic canada opportunities agency",
      "minister of sport and minister responsible for the economic development agency of canada for the regions of quebec",
      "minister of sport and physical activity",
      "minister of canadian identity and culture",
    ],
    display_order: 999,
  },
  {
    id: "indigenous-services-canada",
    notes: null,
    official_full_name: "Indigenous Services Canada",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: [
      "minister of indigenous services",
      "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario",
      "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario and minister responsible for the federal economic development agency for northern ontario",
      "minister of indigenous services and minister responsible for the federal economic development agency for northern ontario canada",
    ],
    department_slug: "indigenous-services-canada",
    bc_priority: 2,
    display_short_name: "Indigenous Services",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 999,
  },
  {
    id: "justice-canada",
    notes: null,
    official_full_name: "Justice Canada",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: ["minister of justice and attorney general of canada"],
    department_slug: "justice-canada",
    bc_priority: 2,
    display_short_name: "Justice",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 999,
  },
  {
    id: "multiple-departments-needs-review",
    notes: null,
    official_full_name: "Multiple Departments - Needs Review",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "multiple-departments-needs-review",
    bc_priority: 2,
    display_short_name: "Multiple",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "president of the queen's privy council for canada and minister of emergency preparedness president of the treasury board",
      "all other ministers",
    ],
    display_order: 999,
  },
  {
    id: "privy-council-office",
    notes: null,
    official_full_name: "Privy Council Office",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: ["leader of the government in the house of commons"],
    department_slug: "privy-council-office",
    bc_priority: 2,
    display_short_name: "Privy Council",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 999,
  },
  {
    id: "privy-council-office-intergovernmental-affairs-secretariat",
    notes: "Added by populate_new_department_configs.py script",
    official_full_name:
      "Privy Council Office / Intergovernmental Affairs Secretariat",
    department_slug:
      "privy-council-office-intergovernmental-affairs-secretariat",
    bc_priority: 2,
    minister_of_state: false,
    display_short_name: "Privy Council / IGA",
    updated_at: "2025-05-17T21:14:30.746Z",
    created_at: "2025-05-17T21:14:30.746Z",
    name_variants: [
      "president of the king's privy council for canada and minister responsible for canada-u.s. trade, intergovernmental affairs and one canadian economy",
      "President of the King's Privy Council for Canada and Minister responsible for Canada-U.S. Trade, Intergovernmental Affairs and One Canadian Economy",
      "president of the king’s privy council for canada and minister responsible for canada-u.s. trade, intergovernmental affairs and one canadian economy",
    ],
    display_order: 999,
  },
  {
    id: "public-services-and-procurement-canada",
    notes: null,
    official_full_name: "Public Services and Procurement Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "public-services-and-procurement-canada",
    bc_priority: 2,
    display_short_name: "Procurement",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of public services and procurement",
      "public services and procurement canada",
      "minister of government transformation, public works and procurement",
    ],
    display_order: 999,
  },
  {
    id: "public-safety-canada",
    notes: null,
    official_full_name: "Public Safety Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "public-safety-canada",
    bc_priority: 2,
    display_short_name: "Public Safety",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of public safety",
      "minister of public safety, democratic institutions and intergovernmental affairs",
      "president of the queen's privy council and minister of emergency preparedness",
      "president of the queen's privy council for canada and minister of emergency preparedness",
      "public safety canada",
      "secretary of state (combatting crime)",
    ],
    display_order: 999,
  },
  {
    id: "canada-revenue-agency",
    notes: null,
    official_full_name: "Canada Revenue Agency",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "canada-revenue-agency",
    bc_priority: 2,
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_short_name: "Revenue",
    name_variants: [
      "minister of national revenue",
      "secretary of state (canada revenue agency and financial institutions)",
    ],
    display_order: 999,
  },
  {
    id: "rural-economic-development",
    bc_priority: 2,
    created_at: "2025-05-20T15:58:08.007Z",
    department_slug: "rural-economic-development",
    display_short_name: "Rural Development",
    "minister of state": false,
    name_variants: [
      "Secretary of State (Rural Development)",
      "secretary of state (rural development)",
    ],
    notes: "manual",
    official_full_name: "Rural Economic Development",
    updated_at: "2025-05-20T16:00:45.454Z",
    display_order: 999,
  },
  {
    id: "transport-canada",
    notes: null,
    official_full_name: "Transport Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "transport-canada",
    bc_priority: 2,
    display_short_name: "Transport",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of transport",
      "transport canada",
      "minister of transport and internal trade",
    ],
    display_order: 999,
  },
  {
    id: "veterans-affairs-canada",
    notes: null,
    official_full_name: "Veterans Affairs Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "veterans-affairs-canada",
    bc_priority: 2,
    display_short_name: "Veterans Affairs",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of veteran's affairs",
      "minister of veterans affairs and associate minister of national defence",
      "veterans affairs canada",
      "minister of veterans affairs",
    ],
    display_order: 999,
  },
];

export const MAIN_DEPT_CONFIGS: DepartmentConfig[] = [
  {
    id: "prime-minister",
    official_full_name: "Office of the Prime Minister",
    display_short_name: "Prime Minister",
    bc_priority: 1,
    is_prime_minister: true,
    department_slug: "prime-minister",
    display_order: 1,
  },
  {
    id: "finance-canada",
    notes: null,
    official_full_name: "Finance Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "finance-canada",
    bc_priority: 1,
    display_short_name: "Finance",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "deputy prime minister and minister of finance",
      "minister of finance",
      "minister of finance and national revenue",
    ],
    display_order: 2,
  },
  {
    id: "infrastructure-canada",
    notes: null,
    official_full_name: "Infrastructure Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "infrastructure-canada",
    bc_priority: 1,
    display_short_name: "Housing",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of housing and diversity and inclusion",
      "minister of intergovernmental affairs, infrastructure and communities",
      "minister of housing and infrastructure",
    ],
    display_order: 3,
  },
  {
    id: "national-defence",
    notes: null,
    official_full_name: "National Defence",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "national-defence",
    bc_priority: 1,
    display_short_name: "Defence",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of national defence",
      "secretary of state (defence procurement)",
    ],
    display_order: 4,
  },
  {
    id: "immigration-refugees-and-citizenship-canada",
    notes: null,
    official_full_name: "Immigration, Refugees and Citizenship Canada",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: ["minister of immigration, refugees and citizenship"],
    department_slug: "immigration-refugees-and-citizenship-canada",
    bc_priority: 1,
    display_short_name: "Immigration",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 5,
  },
  {
    id: "treasury-board-of-canada-secretariat",
    notes: null,
    official_full_name: "Treasury Board of Canada Secretariat",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: [
      "minister of citizens' services",
      "president of the treasury board",
      "treasury board of canada secretariat",
    ],
    department_slug: "treasury-board-of-canada-secretariat",
    bc_priority: 1,
    display_short_name: "Government Transformation",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 6,
  },
  {
    id: "natural-resources-canada",
    notes: null,
    official_full_name: "Natural Resources Canada",
    last_updated_by: "System Migration Script - Initial Population",
    department_slug: "natural-resources-canada",
    bc_priority: 1,
    display_short_name: "Energy",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    name_variants: [
      "minister of natural resources",
      "natural resources canada",
      "minister of energy and natural resources",
    ],
    display_order: 7,
  },
  {
    id: "artificial-intelligence-and-digital-innovation",
    bc_priority: 1,
    department_slug: "artificial-intelligence-and-digital-innovation",
    display_short_name: "Innovation",
    last_updated_at: "2025-05-17T20:39:27.226Z",
    last_updated_by: "Manual",
    notes: "",
    official_full_name: "Artificial Intelligence and Digital Innovation",
    name_variants: [
      "minister of innovation, science and industry",
      "minister of artificial intelligence and digital innovation",
    ],
    display_order: 8,
  },
  {
    id: "health-canada",
    notes: null,
    official_full_name: "Health Canada",
    last_updated_by: "System Migration Script - Initial Population",
    name_variants: [
      "minister of health",
      "minister of mental health and addictions and associate minister of health",
    ],
    department_slug: "health-canada",
    bc_priority: 1,
    display_short_name: "Health",
    last_updated_at: "2025-05-16T18:43:26.723Z",
    display_order: 9,
  },
];

// Define display order for other departments
export const DEPARTMENT_DISPLAY_ORDER: Record<string, number> = {
  "finance-canada": 2,
  "infrastructure-canada": 3, // Housing
  "national-defence": 4,
  "immigration-refugees-and-citizenship-canada": 5, // Immigration
  "treasury-board-of-canada-secretariat": 6, // Government
  "natural-resources-canada": 7, // Energy
  "innovation-science-and-economic-development-canada": 8,
  "artificial-intelligence-and-digital-innovation": 8, // Also Innovation
  "health-canada": 9,
};

export const fetchDeptConfigs = async (currentSessionId?: string | null) => {
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

  // Apply parliament-based filtering for ISED/AIDI on the server
  if (currentSessionId?.startsWith("44")) {
    mainDeptConfigs = mainDeptConfigs.filter(
      (config) =>
        config.id !== "artificial-intelligence-and-digital-innovation",
    );
  } else if (currentSessionId?.startsWith("45")) {
    mainDeptConfigs = mainDeptConfigs.filter(
      (config) =>
        config.id !== "innovation-science-and-economic-development-canada",
    );
  } else {
    const aidiExists = mainDeptConfigs.some(
      (c) => c.id === "artificial-intelligence-and-digital-innovation",
    );
    if (aidiExists) {
      mainDeptConfigs = mainDeptConfigs.filter(
        (config) =>
          config.id !== "innovation-science-and-economic-development-canada",
      );
    }
  }

  mainDeptConfigs = mainDeptConfigs.filter(
    (config) => config.bc_priority === 1,
  );

  // use these to generate the constants above

  return [allDeptConfigs, mainDeptConfigs];
};
