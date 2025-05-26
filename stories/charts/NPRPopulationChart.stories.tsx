import { Meta, StoryObj } from "@storybook/react";
import NPRPopulationChart from "@/components/charts/NPRPopulationChart";
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

const meta: Meta<typeof NPRPopulationChart> = {
  title: "Charts/NPRPopulationChart",
  component: NPRPopulationChart,
  parameters: {
    layout: "centered",
    docs: {
      canvas: { height: 500, width: 900 },
    },
  },
  tags: ["autodocs"],
  argTypes: {
    startYear: {
      control: { type: "number", min: 2021, max: 2025 },
    },
    endYear: {
      control: { type: "number", min: 2021, max: 2025 },
    },
    quarterlyData: {
      control: "boolean",
    },
    showTarget: {
      control: "boolean",
    },
    targetValue: {
      control: { type: "number", min: 0, max: 10 },
    },

  },
};

export default meta;
type Story = StoryObj<typeof NPRPopulationChart>;

export const Default: Story = {
  args: {
    title: "Proportion of the Canadian population that is made up of non-permanent residents",
    startYear: 2021,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 5.0,
  },
  render: (args) => (
    <ChartWrapper>
      <NPRPopulationChart {...args} />
    </ChartWrapper>
  ),
};

export const WithoutTarget: Story = {
  args: {
    title: "NPR Population % (No Target)",
    startYear: 2021,
    endYear: 2024,
    quarterlyData: true,
    showTarget: false,
  },
  render: (args) => (
    <ChartWrapper>
      <NPRPopulationChart {...args} />
    </ChartWrapper>
  ),
};

export const WithTarget: Story = {
  args: {
    title: "NPR Population % vs Target",
    startYear: 2021,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 5.0,
  },
  render: (args) => (
    <ChartWrapper>
      <NPRPopulationChart {...args} />
    </ChartWrapper>
  ),
};

export const RecentData: Story = {
  args: {
    title: "Recent NPR Population Trends",
    startYear: 2023,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 5.0,
  },
  render: (args) => (
    <ChartWrapper>
      <NPRPopulationChart {...args} />
    </ChartWrapper>
  ),
};