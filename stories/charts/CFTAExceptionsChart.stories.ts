import type { Meta, StoryObj } from '@storybook/react';
import CFTAExceptionsChart from '../../components/charts/CFTAExceptionsChart';

const meta = {
  title: 'Charts/CFTAExceptionsChart',
  component: CFTAExceptionsChart,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays Canadian Free Trade Agreement exceptions by province/territory as a stacked area chart. Shows the number of exceptions from 2022-2024 with provinces in various shades of grey and the federal government in blue at the bottom of the stack.'
      }
    }
  },
  argTypes: {
    title: {
      control: 'text',
      description: 'Chart title'
    },
    showLegend: {
      control: 'boolean',
      description: 'Show/hide legend'
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
} satisfies Meta<typeof CFTAExceptionsChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Default: Story = {
  args: {
    title: 'Canadian Free Trade Agreement Exceptions by Province/Territory',
    showLegend: true,
    height: 400,
  },
};

export const WithoutLegend: Story = {
  args: {
    title: 'CFTA Exceptions (2022-2024)',
    showLegend: false,
    height: 400,
  },
};

export const Tall: Story = {
  args: {
    title: 'CFTA Exceptions - Detailed View',
    showLegend: true,
    height: 600,
  },
};

export const Compact: Story = {
  args: {
    title: 'CFTA Exceptions',
    showLegend: true,
    height: 300,
  },
};

export const CustomTitle: Story = {
  args: {
    title: 'Provincial Trade Barriers: CFTA Exception Trends',
    showLegend: true,
    height: 450,
  },
};