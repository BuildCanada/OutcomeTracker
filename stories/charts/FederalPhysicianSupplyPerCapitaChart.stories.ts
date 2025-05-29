import type { Meta, StoryObj } from '@storybook/react';
import FederalPhysicianSupplyPerCapitaChart from '../../components/charts/FederalPhysicianSupplyPerCapitaChart';

const meta = {
  title: 'Charts/FederalPhysicianSupplyPerCapitaChart',
  component: FederalPhysicianSupplyPerCapitaChart,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays federal physician supply per capita data over time as a line chart with target line. Shows physicians per 1,000 people in Canada from 2019-2023 based on CIHI and StatCan data.'
      }
    }
  },
  argTypes: {
    title: {
      control: 'text',
      description: 'Chart title'
    },
    startYear: {
      control: { type: 'number', min: 2019, max: 2023, step: 1 },
      description: 'Starting year for data display'
    },
    endYear: {
      control: { type: 'number', min: 2019, max: 2023, step: 1 },
      description: 'Ending year for data display'
    },
    height: {
      control: { type: 'number', min: 300, max: 800, step: 50 },
      description: 'Chart height in pixels'
    },
    showTarget: {
      control: 'boolean',
      description: 'Show/hide target line'
    },
    targetValue: {
      control: { type: 'number', min: 2.0, max: 5.0, step: 0.1 },
      description: 'Target value for physicians per 1,000 people'
    }
  },
  decorators: [
    (Story) => (
      <div style={{ height: '600px', width: '100%' }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof FederalPhysicianSupplyPerCapitaChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: 'Federal Physician Supply Per Capita',
    startYear: 2019,
    endYear: 2023,
    height: 400,
    showTarget: true,
    targetValue: 3.5,
  },
};

export const WithTarget: Story = {
  args: {
    title: 'Canada Physician Supply per 1,000 People (Target: 3.5)',
    startYear: 2019,
    endYear: 2023,
    height: 400,
    showTarget: true,
    targetValue: 3.5,
  },
};

export const NoTarget: Story = {
  args: {
    title: 'Physician Supply Per Capita - Current Trends',
    startYear: 2019,
    endYear: 2023,
    height: 400,
    showTarget: false,
  },
};

export const RecentYears: Story = {
  args: {
    title: 'Recent Per Capita Physician Supply Trends',
    startYear: 2021,
    endYear: 2023,
    height: 400,
    showTarget: true,
    targetValue: 3.5,
  },
};

export const Tall: Story = {
  args: {
    title: 'Federal Physician Supply Per Capita - Detailed View',
    startYear: 2019,
    endYear: 2023,
    height: 600,
    showTarget: true,
    targetValue: 3.5,
  },
};

export const Compact: Story = {
  args: {
    title: 'Physicians per 1K Population',
    startYear: 2019,
    endYear: 2023,
    height: 300,
    showTarget: true,
    targetValue: 3.5,
  },
};

export const HealthDepartmentView: Story = {
  args: {
    title: 'Department of Health - Physician Density Target',
    startYear: 2019,
    endYear: 2023,
    height: 450,
    showTarget: true,
    targetValue: 3.5,
  },
};

export const AlternativeTarget: Story = {
  args: {
    title: 'Physician Supply with Alternative Target',
    startYear: 2019,
    endYear: 2023,
    height: 400,
    showTarget: true,
    targetValue: 3.0,
  },
};