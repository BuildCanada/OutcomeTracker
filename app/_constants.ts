// Define display order for other departments
export const DEPARTMENT_DISPLAY_ORDER: Record<string, number> = {
  "prime-minister-office": 1, // Prime Minister is first
  "finance-canada": 2,
  "infrastructure-canada": 3, // Housing
  "national-defence": 4,
  "immigration-refugees-and-citizenship-canada": 5, // Immigration
  "public-services-and-procurement-canada": 6, // Government Transformation
  "natural-resources-canada": 7, // Energy
  "transport-canada": 8, // Internal Trade
  "innovation-science-and-economic-development-canada": 9, // Industry
  "artificial-intelligence-and-digital-innovation": 10, // Digital Innovation
  "health-canada": 11,
};

export const DEPARTMENTS: { slug: string; name: string }[] = [
  { slug: "prime-minister-office", name: "Prime Minister" },
  { slug: "finance-canada", name: "Finance" },
  { slug: "infrastructure-canada", name: "Housing" },
  { slug: "national-defence", name: "Defence" },
  {
    slug: "immigration-refugees-and-citizenship-canada",
    name: "Immigration",
  },
  {
    slug: "public-services-and-procurement-canada",
    name: "Government Transformation",
  },
  { slug: "natural-resources-canada", name: "Energy" },
  { slug: "transport-canada", name: "Internal Trade" },
  {
    slug: "innovation-science-and-economic-development-canada",
    name: "Industry",
  },
  {
    slug: "artificial-intelligence-and-digital-innovation",
    name: "Digital Innovation",
  },
  { slug: "health-canada", name: "Health" },
];
