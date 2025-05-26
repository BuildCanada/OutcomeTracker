import { Meta, StoryObj } from "@storybook/react";
import AnnualizedHousingChart from "@/components/charts/AnnualizedHousingChart";
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

const meta: Meta<typeof AnnualizedHousingChart> = {
  title: "Charts/AnnualizedHousingChart",
  component: AnnualizedHousingChart,
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
      control: { type: "number", min: 1990, max: 2025 },
    },
    endYear: {
      control: { type: "number", min: 1990, max: 2025 },
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
type Story = StoryObj<typeof AnnualizedHousingChart>;

export const Default: Story = {
  args: {
    title: "Annualized Housing Starts (Trailing 12 Months)",
    category: "Total units",
    startYear: 2010,
    endYear: 2023,
    showTarget: false,
    targetValue: 400000,
  },
  render: (args) => (
    <ChartWrapper>
      <AnnualizedHousingChart {...args} />
    </ChartWrapper>
  ),
};

export const WithTarget: Story = {
  args: {
    title: "Annualized Housing Starts vs Target",
    category: "Total units",
    startYear: 2015,
    endYear: 2023,
    showTarget: true,
    targetValue: 500000,
  },
  render: (args) => (
    <ChartWrapper>
      <AnnualizedHousingChart {...args} />
    </ChartWrapper>
  ),
};

export const ApartmentUnits: Story = {
  args: {
    title: "Annualized Apartment & Other Units",
    category: "Apartment and other units",
    startYear: 2015,
    endYear: 2023,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <AnnualizedHousingChart {...args} />
    </ChartWrapper>
  ),
};

export const RowUnits: Story = {
  args: {
    title: "Annualized Row Units",
    category: "Row units",
    startYear: 2015,
    endYear: 2023,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <AnnualizedHousingChart {...args} />
    </ChartWrapper>
  ),
};

export const LongTerm: Story = {
  args: {
    title: "Long-term Annualized Housing Starts",
    category: "Total units",
    startYear: 2000,
    endYear: 2023,
    showTarget: true,
    targetValue: 300000,
  },
  render: (args) => (
    <ChartWrapper>
      <AnnualizedHousingChart {...args} />
    </ChartWrapper>
  ),
};

export const RecentYears: Story = {
  args: {
    title: "Recent Annualized Housing Starts",
    category: "Total units",
    startYear: 2020,
    endYear: 2023,
    showTarget: true,
    targetValue: 300000,
  },
  render: (args) => (
    <ChartWrapper>
      <AnnualizedHousingChart {...args} />
    </ChartWrapper>
  ),
};