import type { Meta, StoryObj } from '@storybook/react';
import FederalPhysicianSupplyChart from '../../components/charts/FederalPhysicianSupplyChart';

const meta = {
  title: 'Charts/FederalPhysicianSupplyChart',
  component: FederalPhysicianSupplyChart,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays federal physician supply data over time as a line chart. Shows the total number of physicians in Canada from 2019-2023 based on CIHI data.'
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
    }
  },
  decorators: [
    (Story) => (
      <div style={{ height: '600px', width: '100%' }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof FederalPhysicianSupplyChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: 'Federal Physician Supply',
    startYear: 2019,
    endYear: 2023,
    height: 400,
  },
};

export const FullRange: Story = {
  args: {
    title: 'Canada Physician Supply (2019-2023)',
    startYear: 2019,
    endYear: 2023,
    height: 400,
  },
};

export const RecentYears: Story = {
  args: {
    title: 'Recent Physician Supply Trends',
    startYear: 2021,
    endYear: 2023,
    height: 400,
  },
};

export const Tall: Story = {
  args: {
    title: 'Federal Physician Supply - Detailed View',
    startYear: 2019,
    endYear: 2023,
    height: 600,
  },
};

export const Compact: Story = {
  args: {
    title: 'Physician Supply',
    startYear: 2019,
    endYear: 2023,
    height: 300,
  },
};

export const HealthDepartmentView: Story = {
  args: {
    title: 'Department of Health - Physician Supply Metrics',
    startYear: 2019,
    endYear: 2023,
    height: 450,
  },
};