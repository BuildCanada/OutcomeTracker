"use client";

import React from "react";
import { DepartmentSlug } from "@/lib/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { ExternalLink } from "lucide-react";
import GDPPerCapitaChart from "@/components/charts/GDPPerCapitaChart";
import CapitalFormationChart from "@/components/charts/CapitalFormationChart";
import BalanceSheetChart from "@/components/charts/BalanceSheetChart";
import HousingStartsChart from "@/components/charts/HousingStartsChart";
import NPRPopulationChart from "@/components/charts/NPRPopulationChart";
import AnnualizedHousingChart from "./charts/AnnualizedHousingChart";
import ProductivityChart from "@/components/charts/ProductivityChart";
import PrimaryEnergyChart from "@/components/charts/PrimaryEnergyChart";
import LabourProductivityGrowthChart from "@/components/charts/LabourProductivityGrowthChart";
import DefenseSpendingChart from "@/components/charts/DefenseSpendingChart";

interface MetricData {
  metric: string;
  definition: string;
  target2029: string;
  dataSource: string;
  dataSourceUrl?: string;
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
  "prime-minister": {
    displayName: "Prime Minister",
    metrics: [
      {
        metric: "GDP per capita",
        definition: "Gross domestic product per person",
        target2029: "",
        dataSource:
          "GDP (quarterly) [Statcan] → Gross domestic product at market prices (chained 2017 dollars) [Population (quarterly) [Statcan]] → Canada",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610010401",
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
        dataSource:
          "Gross fixed capital formation (quarterly) [Statcan] → Gross fixed capital formation MINUS Residential structures (chained 2017 dollars) GDP (above)",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610010401",
        brendanStatus: "Done, need to add to finance page",
      },
      // {
      //   metric: "Operating Deficit",
      //   definition: "Net operating balance?",
      //   target2029: "$61.9B/year → $0",
      //   dataSource:
      //     "Operations and Balance Sheet (quarterly) [Statcan] → Net operating balance (federal government)",
      //   dataSourceUrl:
      //     "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1010001501",
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
        dataSource:
          "Housing starts (monthly) [StatCan] → Housing starts, Total units",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3410014301",
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
        dataSource:
          "Permanent Residents (monthly) [IRCC] → Canada - Permanent Residents by Province/Territory and Immigration Category → Total Population (above)",
        dataSourceUrl:
          "https://open.canada.ca/data/en/dataset/f7e5498e-0ad8-4417-85c9-9b8aff9b9eda",
        brendanStatus: "",
      },
      {
        metric: "% NPR population",
        definition:
          "Proportion of the Canadian population that is made up of non-permanent residents",
        target2029: "6.2% → 5%",
        dataSource:
          "NPR population (quarterly) [Statcan] → Total, non-permanent residents (Canada) Population (above)",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1710012101",
        brendanStatus: "Done, need to add to immigration",
      },
      {
        metric: "Relative median income of very recent immigrants",
        definition:
          "Median total income of very recent immigrants (5 years or less) as a percentage of total income of a persons born in Canada",
        target2029: "80% → 100%",
        dataSource:
          "Median income by selected demographic characteristics (annual) [Statcan] → Total Income, Very recent immigrants (5 years or less)",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=1110009101",
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
        dataSource:
          "Military expenditure (% of GDP) [World Bank] → Canada",
        dataSourceUrl:
          "https://data.worldbank.org/indicator/MS.MIL.XPND.GD.ZS?locations=CA",
        brendanStatus: "Done, chart added",
      },
      {
        metric: "% towards modernization",
        definition:
          "Percentage of defence budget spent towards modernizing equipment and R&D",
        target2029: "18.6% → 25%",
        dataSource: "PBO or Department of National Defence Budget disclosures",
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
        dataSource:
          "Consolidated energy statistics (monthly) [Statcan] → Primary energy, Production",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=2510007901",
        brendanStatus: "",
      },
      {
        metric: "Time to approval",
        definition:
          "Time to approve major energy and natural resource projects",
        target2029: "5 years → 2 years",
        dataSource: "?",
        brendanStatus: "",
      },
    ],
  },
  "treasury-board-of-canada-secretariat": {
    displayName: "Government Transformation",
    metrics: [
      {
        metric: "Public service productivity",
        definition: "",
        target2029: "20% increase",
        dataSource:
          "Labour productivity (non-business sectors) (quarterly) [Statcan] → Non-business sector and others",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610020701",
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
        dataSource: "Labour productivity [Statcan] → Labour productivity",
        dataSourceUrl:
          "https://www150.statcan.gc.ca/t1/tbl1/en/tv.action?pid=3610020601",
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
        dataSource:
          "Supply, Distribution and Migration of Physicians in Canada – Data Tables (yearly) [CIHI] → Canada, Physician Supply Population (above)",
        dataSourceUrl:
          "https://www.cihi.ca/en/access-data-and-reports/data-tables",
        brendanStatus: "",
      },
    ],
  },
};

const getStatusBadgeVariant = (status: string) => {
  if (status.toLowerCase().includes("done")) {
    return "default";
  }
  if (status.toLowerCase().includes("need")) {
    return "secondary";
  }
  if (status === "") {
    return "outline";
  }
  return "destructive";
};

const renderChartsForDepartment = (departmentSlug: DepartmentSlug) => {
  switch (departmentSlug) {
    case "prime-minister":
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border bg-white">
            <GDPPerCapitaChart title="GDP Per Capita" startYear={2015} />
          </div>
        </div>
      );

    case "finance-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border bg-white">
            <CapitalFormationChart
              title="% of GDP in capital-focused investment"
              startYear={2015}
              showTarget={true}
              targetValue={17}
            />
          </div>
          {/* <div className="border bg-white">
            <BalanceSheetChart
              title="Operating Balance"
              categories={["Net operating balance"]}
              startDate="2015-01"
            />
          </div> */}
        </div>
      );

    case "infrastructure-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border bg-white">
            <AnnualizedHousingChart
              category="Total units"
              endYear={2029}
              startYear={2015}
              targetValue={500000}
              showTarget
              title="Trailing 12 Month Housing Starts"
            />
          </div>
        </div>
      );

    case "immigration-refugees-and-citizenship-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border bg-white">
            <NPRPopulationChart
              title="NPR % of Population"
              startYear={2015}
              showTarget={true}
              targetValue={5}
            />
          </div>
          {/*<div className="border flex items-center justify-center text-muted-foreground">*/}
          {/*  <div className="text-center">*/}
          {/*    <h4 className="font-medium mb-2">PR Admissions Chart</h4>*/}
          {/*    <p>Chart coming soon</p>*/}
          {/*  </div>*/}
          {/*</div>*/}
        </div>
      );

    case "treasury-board-of-canada-secretariat":
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border bg-white">
            <ProductivityChart
              title="Public Service Productivity"
              sector="Non-business sector and others"
              startYear={2015}
              endYear={2024}
              showTarget={true}
              targetValue={120}
              showGrowthRate={false}
            />
          </div>
        </div>
      );

    case "natural-resources-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border bg-white">
            <PrimaryEnergyChart
              title="Total Primary Energy Production"
              category="Primary energy"
              startYear={2015}
              monthlyData={true}
              showTrend={false}
              showTarget={true}
              targetValue={3000000}
            />
          </div>
        </div>
      );

    case "innovation-science-and-economic-development-canada":
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border bg-white">
            <LabourProductivityGrowthChart
              title="Labour Productivity Growth"
              sector="Total economy"
              startYear={2015}
              endYear={2024}
              quarterlyData={true}
              showTarget={true}
              targetValue={2.0}
              showProductivityIndex={false}
            />
          </div>
        </div>
      );

    case "national-defence":
      return (
        <div className="col-span-1 lg:col-span-2">
          <div className="border bg-white">
            <DefenseSpendingChart
              title="Defense Spending (% of GDP)"
              startYear={2000}
              endYear={2024}
              showTarget={true}
              targetValue={2.0}
            />
          </div>
        </div>
      );

    default:
      const deptData = DEPARTMENT_METRICS[departmentSlug];
      return (
        deptData?.metrics.map((metric, index) => (
          <div
            key={index}
            className="border flex items-center justify-center text-muted-foreground"
          >
            <div className="text-center">
              <h4 className="font-medium mb-2">{metric.metric}</h4>
              <p>Chart coming soon</p>
            </div>
          </div>
        )) || []
      );
  }
};

export default function DepartmentMetrics({
  departmentSlug,
}: DepartmentMetricsProps) {
  const departmentData = DEPARTMENT_METRICS[departmentSlug];

  if (!departmentData) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Guiding Metrics</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            No metrics data available for this department yet. {departmentSlug}
          </p>
        </CardContent>
      </Card>
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
