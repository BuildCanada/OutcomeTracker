import { Meta, StoryObj } from "@storybook/react";
import BalanceSheetChart from "@/components/charts/BalanceSheetChart";
import React from "react";

// Wrapper component to provide proper spacing and dimensions
const ChartWrapper = (props: React.PropsWithChildren) => (
  <div
    style={{
      width: "800px",
      height: "500px",
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

const meta: Meta<typeof BalanceSheetChart> = {
  title: "Charts/BalanceSheetChart",
  component: BalanceSheetChart,
  parameters: {
    layout: "centered",
    docs: {
      canvas: { height: 500, width: 900 },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    categories: {
      control: "multi-select",
      options: [
        "Revenue",
        "Expense",
        "Net operating balance",
        "Net acquisition of non-financial assets",
        "Net lending or borrowing",
        "Net worth",
        "Financial assets",
        "Liabilities",
        "Net financial worth",
        "Non-financial assets",
        "Total expenditure",
      ],
    },
    startDate: {
      control: "text",
    },
    endDate: {
      control: "text",
    },
    showThousands: {
      control: "boolean",
    },
  },
};

export default meta;
type Story = StoryObj<typeof BalanceSheetChart>;

export const Default: Story = {
  args: {
    title: "Government Revenue and Expense",
    categories: ["Revenue", "Expense"],
    startDate: "2010-01",
    endDate: "2023-10",
    showThousands: true,
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetChart {...args} />
    </ChartWrapper>
  ),
};

export const FinancialPosition: Story = {
  args: {
    title: "Government Financial Position",
    categories: ["Financial assets", "Liabilities", "Net financial worth"],
    startDate: "2015-01",
    endDate: "2023-10",
    showThousands: true,
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetChart {...args} />
    </ChartWrapper>
  ),
};

export const BudgetBalances: Story = {
  args: {
    title: "Government Budget Balances",
    categories: ["Net operating balance", "Net lending or borrowing"],
    startDate: "2010-01",
    endDate: "2023-10",
    showThousands: true,
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetChart {...args} />
    </ChartWrapper>
  ),
};

export const LongTermTrends: Story = {
  args: {
    title: "Long-term Government Revenue and Expense",
    categories: ["Revenue", "Expense", "Total expenditure"],
    startDate: "1990-10",
    endDate: "2023-10",
    showThousands: true,
  },
  render: (args) => (
    <ChartWrapper>
      <BalanceSheetChart {...args} />
    </ChartWrapper>
  ),
};