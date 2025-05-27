import type { Meta, StoryObj } from '@storybook/react';
import LabourProductivityGrowthChart from '../components/charts/LabourProductivityGrowthChart';

const meta = {
  title: 'Charts/LabourProductivityGrowthChart',
  component: LabourProductivityGrowthChart,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays labour productivity growth rates from StatCan with configurable sectors, targets, and year-over-year analysis. Specifically designed for tracking productivity growth against innovation targets.'
      }
    }
  },
  tags: ['autodocs'],
  argTypes: {
    title: {
      control: 'text',
      description: 'Chart title',
      defaultValue: 'Labour Productivity Growth',
    },
    sector: {
      control: 'select',
      options: [
        'Total economy',
        'Business sector, goods',
        'Business sector, services',
        'Non-business sector and others',
        'Manufacturing [31-33]',
        'Construction [23]',
        'Information and cultural industries [51]',
        'Professional, scientific and technical services [54]',
        'Finance and insurance, and holding companies',
        'Transportation and warehousing [48-49]'
      ],
      description: 'Economic sector to display productivity growth data for',
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
      description: 'Display target growth rate line on the chart',
    },
    targetValue: {
      control: { type: 'number', min: 0, max: 5, step: 0.1 },
      description: 'Target productivity growth rate percentage',
    },
    showProductivityIndex: {
      control: 'boolean',
      description: 'Show productivity index values on secondary y-axis',
    },
  },
} satisfies Meta<typeof LabourProductivityGrowthChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const InnovationTarget: Story = {
  args: {
    title: 'Labour Productivity Growth',
    sector: 'Total economy',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 2.0,
    showProductivityIndex: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Default configuration for Innovation department showing total economy productivity growth with 2% target. Focuses on year-over-year growth rates to track progress toward innovation goals.'
      }
    }
  }
};

export const WithProductivityIndex: Story = {
  args: {
    title: 'Labour Productivity Growth with Index',
    sector: 'Total economy',
    startYear: 2010,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 2.0,
    showProductivityIndex: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows both growth rates and productivity index values on dual y-axes for comprehensive productivity analysis.'
      }
    }
  }
};

export const BusinessSectorGrowth: Story = {
  args: {
    title: 'Business Sector Productivity Growth',
    sector: 'Business sector, services',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 1.5,
    showProductivityIndex: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Focuses on business sector services productivity growth for comparison with overall economy performance.'
      }
    }
  }
};

export const ManufacturingGrowth: Story = {
  args: {
    title: 'Manufacturing Productivity Growth',
    sector: 'Manufacturing [31-33]',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 2.5,
    showProductivityIndex: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Manufacturing sector productivity growth tracking with higher target reflecting innovation potential in manufacturing.'
      }
    }
  }
};

export const TechSectorGrowth: Story = {
  args: {
    title: 'Information Sector Productivity Growth',
    sector: 'Information and cultural industries [51]',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 3.0,
    showProductivityIndex: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Technology and information sector productivity growth with ambitious 3% target reflecting digital innovation potential.'
      }
    }
  }
};

export const LongTermTrends: Story = {
  args: {
    title: 'Long-term Productivity Growth (20 Years)',
    sector: 'Total economy',
    startYear: 2004,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 2.0,
    showProductivityIndex: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Extended time range to show long-term productivity growth patterns and economic cycles.'
      }
    }
  }
};

export const AnnualView: Story = {
  args: {
    title: 'Annual Productivity Growth Summary',
    sector: 'Total economy',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: false,
    showTarget: true,
    targetValue: 2.0,
    showProductivityIndex: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Annual aggregated view for high-level trend analysis without quarterly fluctuations.'
      }
    }
  }
};

export const AmbitiousTarget: Story = {
  args: {
    title: 'Ambitious Growth Target',
    sector: 'Total economy',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: true,
    targetValue: 3.5,
    showProductivityIndex: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows what a more ambitious 3.5% productivity growth target would look like relative to current performance.'
      }
    }
  }
};

export const NoTarget: Story = {
  args: {
    title: 'Productivity Growth Trends (No Target)',
    sector: 'Total economy',
    startYear: 2015,
    endYear: 2024,
    quarterlyData: true,
    showTarget: false,
    targetValue: 2.0,
    showProductivityIndex: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Clean view of productivity growth trends without target line for pure data analysis.'
      }
    }
  }
};