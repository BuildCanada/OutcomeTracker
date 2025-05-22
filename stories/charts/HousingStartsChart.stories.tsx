import { Meta, StoryObj } from "@storybook/react";
import HousingStartsChart from "@/components/charts/HousingStartsChart";
import React from "react";
import housingStartsData from "@/metrics/statscan/housing-starts.json";

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

// Get available housing categories from the data
const availableCategories = Object.keys((housingStartsData as any).data);

const meta: Meta<typeof HousingStartsChart> = {
  title: "Charts/HousingStartsChart",
  component: HousingStartsChart,
  parameters: {
    layout: "centered",
    docs: {
      canvas: { height: 500, width: 900 },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    category: {
      control: "select",
      options: availableCategories,
    },
    startYear: {
      control: { type: "number", min: 1988, max: 2025 },
    },
    endYear: {
      control: { type: "number", min: 1988, max: 2025 },
    },
    monthlyData: {
      control: "boolean",
    },
    showTrend: {
      control: "boolean",
    },
  },
};

export default meta;
type Story = StoryObj<typeof HousingStartsChart>;

export const Default: Story = {
  args: {
    title: "Total Housing Starts in Canada",
    category: "Total units",
    startYear: 2010,
    endYear: 2023,
    monthlyData: true,
    showTrend: false,
  },
  render: (args) => (
    <ChartWrapper>
      <HousingStartsChart {...args} />
    </ChartWrapper>
  ),
};

export const WithTrend: Story = {
  args: {
    title: "Housing Starts with 12-Month Trend",
    category: "Total units",
    startYear: 2010,
    endYear: 2023,
    monthlyData: true,
    showTrend: true,
  },
  render: (args) => (
    <ChartWrapper>
      <HousingStartsChart {...args} />
    </ChartWrapper>
  ),
};

export const ApartmentUnits: Story = {
  args: {
    title: "Apartment and Other Units",
    category: "Apartment and other units",
    startYear: 2010,
    endYear: 2023,
    monthlyData: true,
    showTrend: false,
  },
  render: (args) => (
    <ChartWrapper>
      <HousingStartsChart {...args} />
    </ChartWrapper>
  ),
};

export const RowUnits: Story = {
  args: {
    title: "Row Units",
    category: "Row units",
    startYear: 2010,
    endYear: 2023,
    monthlyData: true,
    showTrend: false,
  },
  render: (args) => (
    <ChartWrapper>
      <HousingStartsChart {...args} />
    </ChartWrapper>
  ),
};

export const YearlyView: Story = {
  args: {
    title: "Yearly Housing Starts",
    category: "Total units",
    startYear: 2000,
    endYear: 2023,
    monthlyData: false,
    showTrend: false,
  },
  render: (args) => (
    <ChartWrapper>
      <HousingStartsChart {...args} />
    </ChartWrapper>
  ),
};

export const HistoricalView: Story = {
  args: {
    title: "Historical Housing Starts (1990-Present)",
    category: "Total units",
    startYear: 1990,
    endYear: 2023,
    monthlyData: false,
    showTrend: false,
  },
  render: (args) => (
    <ChartWrapper>
      <HousingStartsChart {...args} />
    </ChartWrapper>
  ),
};