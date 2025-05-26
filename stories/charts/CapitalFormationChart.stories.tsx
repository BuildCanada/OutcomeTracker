import { Meta, StoryObj } from "@storybook/react";
import CapitalFormationChart from "@/components/charts/CapitalFormationChart";
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

const meta: Meta<typeof CapitalFormationChart> = {
  title: "Charts/CapitalFormationChart",
  component: CapitalFormationChart,
  parameters: {
    layout: "centered",
    docs: {
      canvas: { height: 500, width: 900 },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    startYear: {
      control: { type: "number", min: 1961, max: 2023 },
    },
    endYear: {
      control: { type: "number", min: 1961, max: 2023 },
    },
    quarterlyData: {
      control: "boolean",
    },
    showTarget: {
      control: "boolean",
    },
    targetValue: {
      control: { type: "number", min: 0, max: 30 },
    },
  },
};

export default meta;
type Story = StoryObj<typeof CapitalFormationChart>;

export const Default: Story = {
  args: {
    title: "% of GDP in capital-focused public and private investment",
    startYear: 2000,
    endYear: 2023,
    quarterlyData: true,
    showTarget: true,
    targetValue: 17,
  },
  render: (args) => (
    <ChartWrapper>
      <CapitalFormationChart {...args} />
    </ChartWrapper>
  ),
};

export const WithoutTarget: Story = {
  args: {
    title: "Non-residential Capital Formation as % of GDP",
    startYear: 2000,
    endYear: 2023,
    quarterlyData: true,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <CapitalFormationChart {...args} />
    </ChartWrapper>
  ),
};

export const YearlyView: Story = {
  args: {
    title: "Annual Non-residential Capital Formation % of GDP",
    startYear: 1990,
    endYear: 2023,
    quarterlyData: false,
    showTarget: true,
    targetValue: 17,
  },
  render: (args) => (
    <ChartWrapper>
      <CapitalFormationChart {...args} />
    </ChartWrapper>
  ),
};

export const HistoricalView: Story = {
  args: {
    title: "Historical Capital Investment Performance",
    startYear: 1961,
    endYear: 2023,
    quarterlyData: false,
    showTarget: true,
    targetValue: 17,
  },
  render: (args) => (
    <ChartWrapper>
      <CapitalFormationChart {...args} />
    </ChartWrapper>
  ),
};

export const RecentFocus: Story = {
  args: {
    title: "Recent Capital Investment Trends",
    startYear: 2018,
    endYear: 2023,
    quarterlyData: true,
    showTarget: true,
    targetValue: 17,
  },
  render: (args) => (
    <ChartWrapper>
      <CapitalFormationChart {...args} />
    </ChartWrapper>
  ),
};