import { Meta, StoryObj } from "@storybook/react";
import PopulationChart from "@/components/charts/PopulationChart";
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

const meta: Meta<typeof PopulationChart> = {
  title: "Charts/PopulationChart",
  component: PopulationChart,
  parameters: {
    layout: "centered",
    docs: {
      canvas: { height: 500, width: 900 },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    region: {
      control: "select",
      options: [
        "Canada",
        "Ontario",
        "Quebec",
        "British Columbia",
        "Alberta",
        "Manitoba",
        "Saskatchewan",
        "Nova Scotia",
        "New Brunswick",
        "Newfoundland and Labrador",
        "Prince Edward Island",
        "Yukon",
        "Northwest Territories",
        "Nunavut",
      ],
    },
    startYear: {
      control: { type: "number", min: 1946, max: 2023 },
    },
    endYear: {
      control: { type: "number", min: 1946, max: 2023 },
    },
    showGoal: {
      control: "boolean",
    },
    goalValue: {
      control: "number",
    },
  },
};

export default meta;
type Story = StoryObj<typeof PopulationChart>;

export const Default: Story = {
  args: {
    title: "Canada Population",
    region: "Canada",
    startYear: 2000,
    endYear: 2023,
    showGoal: false,
    goalValue: 40000000,
  },
  render: (args) => (
    <ChartWrapper>
      <PopulationChart {...args} />
    </ChartWrapper>
  ),
};

export const WithGoal: Story = {
  args: {
    title: "Canada Population with Goal",
    region: "Canada",
    startYear: 2000,
    endYear: 2026,
    showGoal: true,
    goalValue: 40000000,
  },
  render: (args) => (
    <ChartWrapper>
      <PopulationChart {...args} />
    </ChartWrapper>
  ),
};

export const Provincial: Story = {
  args: {
    title: "Ontario Population",
    region: "Ontario",
    startYear: 2000,
    endYear: 2023,
    showGoal: false,
  },
  render: (args) => (
    <ChartWrapper>
      <PopulationChart {...args} />
    </ChartWrapper>
  ),
};

export const HistoricalData: Story = {
  args: {
    title: "Canada Historical Population",
    region: "Canada",
    startYear: 1950,
    endYear: 2023,
    showGoal: false,
  },
  render: (args) => (
    <ChartWrapper>
      <PopulationChart {...args} />
    </ChartWrapper>
  ),
};
