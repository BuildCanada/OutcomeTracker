import { Meta, StoryObj } from "@storybook/react";
import BalanceSheetsChart from "@/components/charts/BalanceSheetsChart";
import React from "react";
import balanceSheetsData from "@/metrics/statscan/balance-sheets.json";

// Wrapper component to provide proper spacing and dimensions
const ChartWrapper = (props: React.PropsWithChildren) => (
  <div
    style={{
      width: "900px",
      height: "550px",
      padding: "40px",
      margin: "20px 0",
      display: "flex",
      flexDirection: "column",
      justifyContent: "center",
    }}
  >
    {props.children}
  </div>
);

// Get available categories from the data for the control options
const availableCategories = Object.keys(balanceSheetsData.data);

const meta: Meta<typeof BalanceSheetsChart> = {
  title: "Charts/BalanceSheetsChart",
  component: BalanceSheetsChart,
  parameters: {
    layout: "centered",
    docs: {
      canvas: { height: 600, width: 1000 },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    category: {
      control: "select",
      options: availableCategories,
    },
    comparisonCategory: {
      control: "select",
      options: availableCategories,
    },
    startYear: {
      control: { type: "number", min: 1990, max: 2023 },
    },
    endYear: {
      control: { type: "number", min: 1990, max: 2023 },
    },
    showComparison: {
      control: "boolean",
    },
  },
};

export default meta;
type Story = StoryObj<typeof BalanceSheetsChart>;

export const Default: Story = {
  args: {
    title: "Government Revenue (2010-2023)",
    category: "Revenue",
    startYear: 2010,
    endYear: 2023,
    showComparison: false,
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetsChart {...args} />
    </ChartWrapper>
  ),
};

export const WithComparison: Story = {
  args: {
    title: "Revenue vs Expense (2010-2023)",
    category: "Revenue",
    startYear: 2010,
    endYear: 2023,
    showComparison: true,
    comparisonCategory: "Expense",
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetsChart {...args} />
    </ChartWrapper>
  ),
};

export const TaxesBreakdown: Story = {
  args: {
    title: "Taxes Breakdown (2015-2023)",
    category: "Taxes",
    startYear: 2015,
    endYear: 2023,
    showComparison: true,
    comparisonCategory: "Taxes on goods and services",
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetsChart {...args} />
    </ChartWrapper>
  ),
};

export const HistoricalData: Story = {
  args: {
    title: "Historical Net Worth (1990-2023)",
    category: "Net worth",
    startYear: 1990,
    endYear: 2023,
    showComparison: false,
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetsChart {...args} />
    </ChartWrapper>
  ),
};

export const RevenueVsExpenseLongTerm: Story = {
  args: {
    title: "Revenue vs Expense (Long-term)",
    category: "Revenue",
    startYear: 1990,
    endYear: 2023,
    showComparison: true,
    comparisonCategory: "Expense",
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetsChart {...args} />
    </ChartWrapper>
  ),
};