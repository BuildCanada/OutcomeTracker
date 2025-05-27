import type { Meta, StoryObj } from '@storybook/react';
import ProductivityChart from '../components/charts/ProductivityChart';

const meta = {
  title: 'Charts/ProductivityChart',
  component: ProductivityChart,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays labour productivity data from StatCan with configurable sectors, targets, and growth rate analysis. Used primarily for tracking public service productivity against government transformation goals.'
      }
    }
  },
  tags: ['autodocs'],
  argTypes: {
    title: {
      control: 'text',
      description: 'Chart title',
      defaultValue: 'Public Service Productivity',
    },
    sector: {
      control: 'select',
      options: [
        'Non-business sector and others',
        'Total economy',
        'Business sector, goods',
        'Business sector, services',
        'Manufacturing [31-33]',
        'Construction [23]',
        'Information and cultural industries [51]',
        'Professional, scientific and technical services [54]',
        'Public administration [91]'
      ],
      description: 'Economic sector to display productivity data for',
    },
    startYear: {
      control: { type: 'number', min: 1981, max: 2024, step: 1 },
      description: 'Starting year for the data range',
    },
    endYear: {
      control: { type: 'number', min: 1981, max: 2024, step: 1 },
      description: 'Ending year for the data range',
    },
    quarterlyData: {
      control: 'boolean',
      description: 'Show quarterly data points vs annual aggregation',
    },
    showTarget: {
      control: 'boolean',
      description: 'Display target line on the chart',
    },
    targetValue: {
      control: { type: 'number', min: 80, max: 150, step: 5 },
      description: 'Target productivity index value',
    },
    showGrowthRate: {
      control: 'boolean',
      description: 'Display year-over-year growth rate as a secondary line',
    },
  },
} satisfies Meta<typeof ProductivityChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const PublicServiceProductivity: Story = {
  args: {
    title: 'Public Service Productivity',
    sector: 'Non-business sector and others',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 120,
    showGrowthRate: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Default configuration for tracking public service productivity with 20% increase target (index 120). Uses non-business sector data which includes government operations.'
      }
    }
  }
};

export const WithGrowthRate: Story = {
  args: {
    title: 'Public Service Productivity with Growth Analysis',
    sector: 'Non-business sector and others',
    startYear: 2010,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 120,
    showGrowthRate: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows productivity index with year-over-year growth rate overlay to analyze trends and volatility in productivity improvements.'
      }
    }
  }
};

export const TotalEconomyComparison: Story = {
  args: {
    title: 'Total Economy Productivity',
    sector: 'Total economy',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 110,
    showGrowthRate: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Displays productivity for the entire economy for comparison with public sector performance.'
      }
    }
  }
};

export const BusinessSectorProductivity: Story = {
  args: {
    title: 'Business Sector Productivity',
    sector: 'Business sector, services',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 115,
    showGrowthRate: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows business sector services productivity for benchmarking against public sector performance.'
      }
    }
  }
};

export const LongTermTrends: Story = {
  args: {
    title: 'Long-term Productivity Trends (20 Years)',
    sector: 'Non-business sector and others',
    startYear: 2004,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 120,
    showGrowthRate: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Extended time range to show long-term productivity trends and cyclical patterns in public sector productivity.'
      }
    }
  }
};

export const AnnualView: Story = {
  args: {
    title: 'Annual Productivity Summary',
    sector: 'Non-business sector and others',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: false,
    showTarget: true,
    targetValue: 120,
    showGrowthRate: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Annual aggregated view for high-level trend analysis without quarterly fluctuations.'
      }
    }
  }
};

export const HighTarget: Story = {
  args: {
    title: 'Ambitious Productivity Target',
    sector: 'Non-business sector and others',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 140,
    showGrowthRate: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows what a more ambitious 40% productivity increase target would look like relative to current performance.'
      }
    }
  }
};

export const NoTarget: Story = {
  args: {
    title: 'Productivity Trends (No Target)',
    sector: 'Non-business sector and others',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: false,
    targetValue: 120,
    showGrowthRate: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Clean view of productivity trends without target line for pure data analysis.'
      }
    }
  }
};