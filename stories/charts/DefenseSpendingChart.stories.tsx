import type { Meta, StoryObj } from '@storybook/react';
import DefenseSpendingChart from '../../components/charts/DefenseSpendingChart';

const meta = {
  title: 'Charts/DefenseSpendingChart',
  component: DefenseSpendingChart,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays Canada\'s military expenditure as a percentage of GDP over time, with NATO\'s 2% target line. Uses World Bank data from 1960-2023.'
      }
    }
  },
  argTypes: {
    title: {
      control: 'text',
      description: 'Chart title'
    },
    startYear: {
      control: { type: 'number', min: 1960, max: 2023, step: 1 },
      description: 'Starting year for data display'
    },
    endYear: {
      control: { type: 'number', min: 1960, max: 2023, step: 1 },
      description: 'Ending year for data display'
    },
    showTarget: {
      control: 'boolean',
      description: 'Show NATO 2% target line'
    },
    targetValue: {
      control: { type: 'number', min: 0, max: 5, step: 0.1 },
      description: 'Target percentage value'
    }
  },
  decorators: [
    (Story) => (
      <div style={{ height: '500px', width: '100%' }}>
        <Story />
      </div>
    ),
  ],
} satisfies Meta<typeof DefenseSpendingChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: 'Defense Spending (% of GDP)',
    startYear: 2000,
    endYear: 2024,
    showTarget: true,
    targetValue: 2.0,
  },
};

export const LongTermTrend: Story = {
  args: {
    title: 'Canada Defense Spending - Long Term Trend',
    startYear: 1960,
    endYear: 2023,
    showTarget: true,
    targetValue: 2.0,
  },
};

export const RecentYears: Story = {
  args: {
    title: 'Recent Defense Spending Trends',
    startYear: 2015,
    endYear: 2023,
    showTarget: true,
    targetValue: 2.0,
  },
};

export const WithoutTarget: Story = {
  args: {
    title: 'Defense Spending Without Target Line',
    startYear: 2000,
    endYear: 2023,
    showTarget: false,
  },
};

export const CustomTarget: Story = {
  args: {
    title: 'Defense Spending with Custom Target',
    startYear: 2000,
    endYear: 2023,
    showTarget: true,
    targetValue: 1.5,
  },
};