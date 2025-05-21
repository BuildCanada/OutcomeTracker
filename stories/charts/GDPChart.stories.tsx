import { Meta, StoryObj } from "@storybook/react";
import GDPChart from "@/components/charts/GDPChart";
import React from "react";
import gdpData from "@/metrics/statscan/gdp.json";

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

// Get available metrics from the GDP data for the control options
const availableMetrics = Object.keys(gdpData.data);

const meta: Meta<typeof GDPChart> = {
  title: "Charts/GDPChart",
  component: GDPChart,
  parameters: {
    layout: "centered",
    docs: {
      canvas: { height: 500, width: 900 },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    metric: {
      control: "select",
      options: availableMetrics,
    },
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
      control: "number",
    },
  },
};

export default meta;
type Story = StoryObj<typeof GDPChart>;

export const Default: Story = {
  args: {
    title: "Canadian GDP",
    metric: "Gross domestic product at market prices",
    startYear: 2010,
    endYear: 2023,
    quarterlyData: true,
    showTarget: false,
    targetValue: 2500000,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPChart {...args} />
    </ChartWrapper>
  ),
};

export const WithTarget: Story = {
  args: {
    title: "Canadian GDP with Target",
    metric: "Gross domestic product at market prices",
    startYear: 2015,
    endYear: 2023,
    quarterlyData: true,
    showTarget: true,
    targetValue: 2500000,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPChart {...args} />
    </ChartWrapper>
  ),
};

export const YearlyView: Story = {
  args: {
    title: "Canadian GDP (Yearly)",
    metric: "Gross domestic product at market prices",
    startYear: 2000,
    endYear: 2023,
    quarterlyData: false,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPChart {...args} />
    </ChartWrapper>
  ),
};

export const LongTermTrend: Story = {
  args: {
    title: "Canadian GDP (1990-present)",
    metric: "Gross domestic product at market prices",
    startYear: 1990,
    endYear: 2023,
    quarterlyData: true,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPChart {...args} />
    </ChartWrapper>
  ),
};

export const ExportsView: Story = {
  args: {
    title: "Canadian Exports",
    metric: "Exports of goods and services",
    startYear: 2010,
    endYear: 2023,
    quarterlyData: true,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPChart {...args} />
    </ChartWrapper>
  ),
};