import { Meta, StoryObj } from "@storybook/react";
import GDPPerCapitaChart from "@/components/charts/GDPPerCapitaChart";
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

// Get available GDP measures from the data
const availableGDPMeasures = Object.keys((gdpData as any).data);

const meta: Meta<typeof GDPPerCapitaChart> = {
  title: "Charts/GDPPerCapitaChart",
  component: GDPPerCapitaChart,
  parameters: {
    layout: "centered",
    docs: {
      canvas: { height: 500, width: 900 },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    gdpMeasure: {
      control: "select",
      options: availableGDPMeasures,
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
    showAnnual: {
      control: "boolean",
    },
    showTarget: {
      control: "boolean",
    },
    targetValue: {
      control: { type: "number", min: 0, max: 200 },
    },
  },
};

export const WithTarget: Story = {
  args: {
    title: "GDP Per Capita with Target",
    gdpMeasure: "Gross domestic product at market prices",
    startYear: 2010,
    endYear: 2023,
    quarterlyData: true,
    showAnnual: false,
    showTarget: true,
    targetValue: 65,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPPerCapitaChart {...args} />
    </ChartWrapper>
  ),
};

export const AlternativeMeasure: Story = {
  args: {
    title: "Household Consumption Per Capita",
    gdpMeasure: "Household final consumption expenditure",
    startYear: 2005,
    endYear: 2023,
    quarterlyData: true,
    showAnnual: false,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPPerCapitaChart {...args} />
    </ChartWrapper>
  ),
};

export default meta;
type Story = StoryObj<typeof GDPPerCapitaChart>;

export const Default: Story = {
  args: {
    title: "Canadian GDP Per Capita",
    gdpMeasure: "Gross domestic product at market prices",
    startYear: 2000,
    endYear: 2023,
    quarterlyData: true,
    showAnnual: false,
    showTarget: false,
    targetValue: 50,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPPerCapitaChart {...args} />
    </ChartWrapper>
  ),
};

export const WithAnnualAverage: Story = {
  args: {
    title: "GDP Per Capita with Annual Average",
    gdpMeasure: "Gross domestic product at market prices",
    startYear: 2010,
    endYear: 2023,
    quarterlyData: true,
    showAnnual: true,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPPerCapitaChart {...args} />
    </ChartWrapper>
  ),
};

export const LongTermTrend: Story = {
  args: {
    title: "Long-term GDP Per Capita Trend",
    gdpMeasure: "Gross domestic product at market prices",
    startYear: 1970,
    endYear: 2023,
    quarterlyData: false,
    showAnnual: false,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPPerCapitaChart {...args} />
    </ChartWrapper>
  ),
};

export const HistoricalView: Story = {
  args: {
    title: "Historical GDP Per Capita (1961-Present)",
    gdpMeasure: "Gross domestic product at market prices",
    startYear: 1961,
    endYear: 2023,
    quarterlyData: false,
    showAnnual: false,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPPerCapitaChart {...args} />
    </ChartWrapper>
  ),
};

export const RecentYears: Story = {
  args: {
    title: "Recent GDP Per Capita Growth",
    gdpMeasure: "Gross domestic product at market prices",
    startYear: 2018,
    endYear: 2023,
    quarterlyData: true,
    showAnnual: true,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <GDPPerCapitaChart {...args} />
    </ChartWrapper>
  ),
};