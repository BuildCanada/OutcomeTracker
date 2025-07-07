"use client";

import React from "react";
import { DepartmentSlug } from "@/lib/types";
import GDPPerCapitaChart from "@/components/charts/GDPPerCapitaChart";
import CapitalFormationChart from "@/components/charts/CapitalFormationChart";
import NPRPopulationChart from "@/components/charts/NPRPopulationChart";
import AnnualizedHousingChart from "./charts/AnnualizedHousingChart";
import ProductivityChart from "@/components/charts/ProductivityChart";
import PrimaryEnergyChart from "@/components/charts/PrimaryEnergyChart";
import LabourProductivityGrowthChart from "@/components/charts/LabourProductivityGrowthChart";
import ChartWithSource from "@/components/charts/ChartWithSource";
import DefenseSpendingChart from "@/components/charts/DefenseSpendingChart";
import CFTAExceptionsChart from "./charts/CFTAExceptionsChart";
import FederalPhysicianSupplyChart from "./charts/FederalPhysicianSupplyChart";
import FederalPhysicianSupplyPerCapitaChart from "./charts/FederalPhysicianSupplyPerCapitaChart";
import ElectricityCapacityChart from "./charts/ElectricityCapacityChart";
import ElectricityProductionChart from "./charts/ElectricityProductionChart";

interface MetricData {
  metric: string;
  definition: string;
  target2029: string;
  dataSource: string;
  dataSourceUrl?: string;
  targetSource?: string;
  targetSourceUrl?: string;
  brendanStatus: string;
}

interface DepartmentMetricsProps {
  departmentSlug: DepartmentSlug;
}

// Mapping of department slugs to their display names and metrics
const DEPARTMENT_METRICS: Record<
  string,
  { displayName: string; metrics: MetricData[] }
> = {
  "prime-minister-office": {
    displayName: "Prime Minister",
    metrics: [
      {
        metric: "GDP per capita",
        definition: "Gross domestic product per person",
        target2029: "",
        dataSource: "Statcan",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610010401",
        targetSource: "Statcan",
        targetSourceUrl: "https://www150.statcan.gc.ca/n1/pub/36-28-0001/2024004/article/00001-eng.htm",
        brendanStatus: "Done, need to add to PM page",
      },
    ],
  },
  "finance-canada": {
    displayName: "Finance",
    metrics: [
      {
        metric: "% of GDP in capital-focused public and private investment",
        definition:
          'Gross fixed capital formation (excluding "Residential structures") as a percentage of GDP',
        target2029: "11% → 17%",
        dataSource: "Statcan",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610010401",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "Done, need to add to finance page",
      },
      // {
      //   metric: "Operating Deficit",
      //   definition: "Net operating balance?",
      //   target2029: "$61.9B/year → $0",
      //   dataSource: "Statcan",
      //   dataSourceUrl:
      //     "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1010001501",
      //   targetSource: "Liberal Party",
      //   targetSourceUrl: "https://liberal.ca/wp-content/uploads/sites/292/2025/04/Canada-Strong.pdf",
      //   brendanStatus:
      //     "Graph looks weird, need to verify how numbers are reported.",
      // },
    ],
  },
  "infrastructure-canada": {
    displayName: "Housing",
    metrics: [
      {
        metric: "Housing starts",
        definition:
          "Number of residential units that have started in a give time frame",
        target2029: "250k/year → 500k/year",
        dataSource: "Statcan",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410014301",
        targetSource: "Liberal Party",
        targetSourceUrl: "https://liberal.ca/housing-plan/",
        brendanStatus: "Done, need to add to housing page",
      },
    ],
  },
  "immigration-refugees-and-citizenship-canada": {
    displayName: "Immigration",
    metrics: [
      {
        metric: "% of PR admissions",
        definition: "PR admissions as a share of total Canadian population",
        target2029: "1.2% → 1%",
        dataSource: "IRCC",
        dataSourceUrl:
          "https://open.canada.ca/data/en/dataset/f7e5498e-0ad8-4417-85c9-9b8aff9b9eda",
        targetSource: "Liberal Party",
        targetSourceUrl:
          "https://liberal.ca/wp-content/uploads/sites/292/2025/04/Canada-Strong.pdf/notices/supplementary-immigration-levels-2024-2026.html",
        brendanStatus: "",
      },
      {
        metric: "% NPR population",
        definition:
          "Proportion of the Canadian population that is made up of non-permanent residents",
        target2029: "6.2% → 5%",
        dataSource: "Statcan",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1710012101",
        targetSource: "Liberal Party",
        targetSourceUrl:
          "https://liberal.ca/wp-content/uploads/sites/292/2025/04/Canada-Strong.pdf",
        brendanStatus: "Done, need to add to immigration",
      },
      {
        metric: "Relative median income of very recent immigrants",
        definition:
          "Median total income of very recent immigrants (5 years or less) as a percentage of total income of a persons born in Canada",
        target2029: "80% → 100%",
        dataSource: "Statcan",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110009101",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "",
      },
    ],
  },
  "national-defence": {
    displayName: "Defence",
    metrics: [
      {
        metric: "% of GDP spent",
        definition: "Percentage of GDP spent towards defence",
        target2029: "1.37% → 2%",
        dataSource: "World Bank",
        dataSourceUrl:
          "https://data.worldbank.org/indicator/MS.MIL.XPND.GD.ZS?locations=CA",
        targetSource: "Liberal Party",
        targetSourceUrl:
          "https://liberal.ca/wp-content/uploads/sites/292/2025/04/Canada-Strong.pdf",
        brendanStatus: "Done, chart added",
      },
      {
        metric: "% towards modernization",
        definition:
          "Percentage of defence budget spent towards modernizing equipment and R&D",
        target2029: "18.6% → 25%",
        dataSource: "PBO or Department of National Defence Budget disclosures",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "",
      },
    ],
  },
  "natural-resources-canada": {
    displayName: "Energy",
    metrics: [
      {
        metric: "Energy exports",
        definition: "",
        target2029: "Xx → xx",
        dataSource: "Statcan",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2510007901",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "",
      },
      {
        metric: "Time to approval",
        definition:
          "Time to approve major energy and natural resource projects",
        target2029: "5 years → 2 years",
        dataSource: "?",
        targetSource: "Liberal Party",
        targetSourceUrl:
          "https://www.canada.ca/en/natural-resources-canada/news/2025/05/speech-minister-tim-hodgson-at-the-calgary-chamber-of-commerce.html",
        brendanStatus: "",
      },
    ],
  },
  "public-services-and-procurement-canada": {
    displayName: "Government Transformation",
    metrics: [
      {
        metric: "Public service productivity",
        definition: "",
        target2029: "20% increase",
        dataSource: "Statcan",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610020701",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "",
      },
    ],
  },
  "innovation-science-and-economic-development-canada": {
    displayName: "Innovation",
    metrics: [
      {
        metric: "Labour Productivity Growth",
        definition:
          "Labour productivity is a measure of real gross domestic product (GDP) per hour worked.",
        target2029: "<1% → 2% YoY",
        dataSource: "Statcan",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610020601",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "",
      },
    ],
  },
  "health-canada": {
    displayName: "Health",
    metrics: [
      {
        metric: "Physicians per capita",
        definition: "Physician Supply as a share of total population",
        target2029: "2.43 per 1000 people → 3.5",
        dataSource: "CIHI",
        dataSourceUrl:
          "https://www.cihi.ca/en/access-data-and-reports/data-tables",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "",
      },
      {
        metric: "Total Federal Physician Supply",
        definition: "Total number of physicians in Canada",
        target2029: "",
        dataSource: "CIHI",
        dataSourceUrl:
          "https://www.cihi.ca/en/access-data-and-reports/data-tables",
        targetSource: "",
        targetSourceUrl: "",
        brendanStatus: "",
      },
    ],
  },
  "transport-canada": {
    displayName: "Transport & Internal Trade",
    metrics: [
      {
        metric: "CFTA Exceptions",
        definition:
          "Number of exceptions to the Canadian Free Trade Agreement by province and territory",
        target2029: "Reduce interprovincial trade barriers → 50% reduction",
        dataSource: "Canadian Federation of Independent Business",
        dataSourceUrl: "https://www.cfib-fcei.ca/",
        targetSource: "Liberal Party",
        targetSourceUrl: "https://liberal.ca/wp-content/uploads/sites/292/2025/04/Canada-Strong.pdf",
        brendanStatus: "Done, chart added",
      },
    ],
  },
  "artificial-intelligence-and-digital-innovation": {
    displayName: "Digital Innovation",
    metrics: [
      {
        metric: "National Electricity Capacity",
        definition: "Total electricity generating capacity in Canada",
        target2029: "145.96 GW → 175.15 GW (20% increase)",
        dataSource: "Statistics Canada",
        dataSourceUrl: "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2510002201",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "Done, chart added",
      },
      {
        metric: "National Electricity Production",
        definition: "Total electricity generated in Canada (annualized)",
        target2029: "626 TWh/year → 751 TWh/year (20% above 2020-2024 avg)",
        dataSource: "Statistics Canada",
        dataSourceUrl: "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2510001501",
        targetSource: "Build Canada",
        targetSourceUrl: "",
        brendanStatus: "Done, chart added",
      },
    ],
  },
};

const renderChartsForDepartment = (departmentSlug: DepartmentSlug) => {
  const departmentData = DEPARTMENT_METRICS[departmentSlug];
  if (!departmentData) return [];

  switch (departmentSlug) {
    case "prime-minister-office":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <GDPPerCapitaChart title="Growth in GDP per capita" showTarget={true} targetValue={2.0} startYear={2021} />
          </ChartWithSource>
        </div>
      );

    case "finance-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <CapitalFormationChart
              title="% of GDP in capital-focused investment"
              startYear={2015}
              showTarget={true}
              targetValue={17}
            />
          </ChartWithSource>
        </div>
      );

    case "infrastructure-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <AnnualizedHousingChart
              category="Total units"
              endYear={2029}
              startYear={2015}
              targetValue={500000}
              showTarget
              title="Annualized Housing Starts (Trailing 12 Months)"
            />
          </ChartWithSource>
        </div>
      );

    case "immigration-refugees-and-citizenship-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[1].dataSource}
            dataSourceUrl={departmentData.metrics[1].dataSourceUrl}
            targetSource={departmentData.metrics[1].targetSource}
            targetSourceUrl={departmentData.metrics[1].targetSourceUrl}
          >
            <NPRPopulationChart
              title="Non-Permanent Residents as % of Population"
              startYear={2015}
              showTarget={true}
              targetValue={5}
            />
          </ChartWithSource>
        </div>
      );

    case "treasury-board-of-canada-secretariat":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <ProductivityChart
              title="Public Service Productivity"
              sector="Non-business sector and others"
              startYear={2015}
              endYear={2024}
              showTarget={true}
              targetValue={120}
              showGrowthRate={false}
            />
          </ChartWithSource>
        </div>
      );

    case "public-services-and-procurement-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <ProductivityChart
              title="Public Service Productivity"
              sector="Non-business sector and others"
              startYear={2015}
              endYear={2024}
              showTarget={true}
              targetValue={120}
              showGrowthRate={false}
            />
          </ChartWithSource>
        </div>
      );

    case "natural-resources-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <PrimaryEnergyChart
              title="Total Primary Energy Production"
              category="Primary energy"
              startYear={2015}
              endYear={2029}
              monthlyData={true}
              showTrend={false}
              showTarget={true}
              targetValue={3000000}
            />
          </ChartWithSource>
        </div>
      );

    case "innovation-science-and-economic-development-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <LabourProductivityGrowthChart
              title="Labour Productivity Growth"
              sector="Total economy"
              startYear={2015}
              endYear={2029}
              quarterlyData={true}
              showTarget={true}
              targetValue={2.0}
              showProductivityIndex={false}
            />
          </ChartWithSource>
        </div>
      );

    case "national-defence":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <DefenseSpendingChart
              title="Defence Spending (% of GDP)"
              startYear={2000}
              endYear={2029}
              showTarget={true}
              targetValue={2.0}
            />
          </ChartWithSource>
        </div>
      );

    case "transport-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <ChartWithSource
            dataSource={departmentData.metrics[0].dataSource}
            dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
            targetSource={departmentData.metrics[0].targetSource}
            targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
          >
            <CFTAExceptionsChart
              title="CFTA Exceptions by Province/Territory"
              showLegend={true}
              height={500}
            />
          </ChartWithSource>
        </div>
      );

    case "health-canada":
      return (
        <>
          <div className="col-span-1">
            <ChartWithSource
              dataSource={departmentData.metrics[0].dataSource}
              dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
              targetSource={departmentData.metrics[0].targetSource}
              targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
            >
              <FederalPhysicianSupplyPerCapitaChart
                title="Physicians per 1,000 People"
                startYear={2019}
                endYear={2029}
                height={450}
                showTarget={true}
                targetValue={2.8}
              />
            </ChartWithSource>
          </div>
          <div className="col-span-1">
            <ChartWithSource
              dataSource={departmentData.metrics[1].dataSource}
              dataSourceUrl={departmentData.metrics[1].dataSourceUrl}
              targetSource={departmentData.metrics[1].targetSource}
              targetSourceUrl={departmentData.metrics[1].targetSourceUrl}
            >
              <FederalPhysicianSupplyChart
                title="Total Federal Physician Supply"
                startYear={2019}
                endYear={2029}
                height={450}
              />
            </ChartWithSource>
          </div>
        </>
      );

    case "artificial-intelligence-and-digital-innovation":
      return (
        <>
          <div className="col-span-1">
            <ChartWithSource
              dataSource={departmentData.metrics[0].dataSource}
              dataSourceUrl={departmentData.metrics[0].dataSourceUrl}
              targetSource={departmentData.metrics[0].targetSource}
              targetSourceUrl={departmentData.metrics[0].targetSourceUrl}
            >
              <ElectricityCapacityChart
                title="National Electricity Capacity"
                startYear={2015}
                endYear={2023}
                showTarget={true}
                targetValue={175.15}
                showTrend={true}
              />
            </ChartWithSource>
          </div>
          <div className="col-span-1">
            <ChartWithSource
              dataSource={departmentData.metrics[1].dataSource}
              dataSourceUrl={departmentData.metrics[1].dataSourceUrl}
              targetSource={departmentData.metrics[1].targetSource}
              targetSourceUrl={departmentData.metrics[1].targetSourceUrl}
            >
              <ElectricityProductionChart
                title="National Electricity Production"
                startYear={2015}
                endYear={2024}
                showTarget={true}
                targetValue={751}
                showTrend={true}
              />
            </ChartWithSource>
          </div>
        </>
      );

    default:
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border p-8 flex items-center justify-center">
            <p className="text-muted-foreground">Coming soon</p>
          </div>
        </div>
      );
  }
};

export default function DepartmentMetrics({
  departmentSlug,
}: DepartmentMetricsProps) {
  const departmentData = DEPARTMENT_METRICS[departmentSlug];

  if (!departmentData) {
    return (
      <div className="col-span-1 lg:col-span-2">
        <div className="border p-8 flex items-center justify-center">
          <p className="text-muted-foreground">Coming soon</p>
        </div>
      </div>
    );
  }

  //         {/* <div className="overflow-x-auto">
  //   <Table>
  //     <TableHeader>
  //       <TableRow>
  //         <TableHead className="min-w-[150px]">Metric</TableHead>
  //         <TableHead className="min-w-[200px]">Definition</TableHead>
  //         <TableHead className="min-w-[120px]">2029 Target</TableHead>
  //         <TableHead className="min-w-[250px]">Data Source</TableHead>
  //         <TableHead className="min-w-[150px]">Status</TableHead>
  //       </TableRow>
  //     </TableHeader>
  //     <TableBody>
  //       {departmentData.metrics.map((metric, index) => (
  //         <TableRow key={index}>
  //           <TableCell className="font-medium">{metric.metric}</TableCell>
  //           <TableCell>{metric.definition}</TableCell>
  //           <TableCell>{metric.target2029}</TableCell>
  //           <TableCell>
  //             {metric.dataSourceUrl ? (
  //               <a
  //                 href={metric.dataSourceUrl}
  //                 target="_blank"
  //                 rel="noopener noreferrer"
  //                 className="text-blue-600 hover:text-blue-800 underline inline-flex items-center gap-1"
  //               >
  //                 {metric.dataSource}
  //                 <ExternalLink className="h-3 w-3" />
  //               </a>
  //             ) : (
  //               metric.dataSource
  //             )}
  //           </TableCell>
  //           <TableCell>
  //             {metric.brendanStatus ? (
  //               <Badge variant={getStatusBadgeVariant(metric.brendanStatus)}>
  //                 {metric.brendanStatus}
  //               </Badge>
  //             ) : (
  //               <Badge variant="outline">Pending</Badge>
  //             )}
  //           </TableCell>
  //         </TableRow>
  //       ))}
  //     </TableBody>
  //   </Table>
  // </div> */}

  return (
    <div className="mt-8">
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {renderChartsForDepartment(departmentSlug)}
      </div>
    </div>
  );
}
