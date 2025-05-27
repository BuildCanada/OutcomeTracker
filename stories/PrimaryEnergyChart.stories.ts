import type { Meta, StoryObj } from '@storybook/react';
import PrimaryEnergyChart from '../components/charts/PrimaryEnergyChart';

const meta = {
  title: 'Charts/PrimaryEnergyChart',
  component: PrimaryEnergyChart,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays primary energy production data from StatCan with configurable energy sources, targets, and trend analysis. Used for tracking Canada\'s total energy production and exports.'
      }
    }
  },
  tags: ['autodocs'],
  argTypes: {
    title: {
      control: 'text',
      description: 'Chart title',
      defaultValue: 'Total Primary Energy Production',
    },
    category: {
      control: 'select',
      options: [
        'Primary energy',
        'Coal',
        'Coke',
        'Crude oil',
        'Natural gas',
        'Natural gas liquids',
        'Primary electricity, hydro, nuclear, and other renewables',
        'Refined petroleum products',
        'Renewable fuels',
        'Secondary electricity, thermal',
        'Secondary energy',
        'Total primary and secondary energy'
      ],
      description: 'Energy source/category to display production data for',
    },
    startYear: {
      control: { type: 'number', min: 2010, max: 2024, step: 1 },
      description: 'Starting year for the data range',
    },
    endYear: {
      control: { type: 'number', min: 2010, max: 2024, step: 1 },
      description: 'Ending year for the data range',
    },
    monthlyData: {
      control: 'boolean',
      description: 'Show monthly data points vs annual aggregation',
    },
    showTarget: {
      control: 'boolean',
      description: 'Display target line on the chart',
    },
    targetValue: {
      control: { type: 'number', min: 1000000, max: 5000000, step: 100000 },
      description: 'Target energy production value (in terajoules)',
    },
    showTrend: {
      control: 'boolean',
      description: 'Display 12-month moving average trend line',
    },
  },
} satisfies Meta<typeof PrimaryEnergyChart>;

export default meta;
type Story = StoryObj<typeof meta>;

export const TotalPrimaryEnergy: Story = {
  args: {
    title: 'Total Primary Energy Production',
    category: 'Primary energy',
    startYear: 2015,
    endYear: 2024,
    monthlyData: true,
    showTarget: false,
    targetValue: 2500000,
    showTrend: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Default configuration showing total primary energy production in Canada with 12-month moving average trend line.'
      }
    }
  }
};

export const CrudeOilProduction: Story = {
  args: {
    title: 'Crude Oil Production',
    category: 'Crude oil',
    startYear: 2015,
    endYear: 2024,
    monthlyData: true,
    showTarget: true,
    targetValue: 1200000,
    showTrend: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows crude oil production trends with target line and moving average for Canada\'s largest energy export.'
      }
    }
  }
};

export const NaturalGasProduction: Story = {
  args: {
    title: 'Natural Gas Production',
    category: 'Natural gas',
    startYear: 2015,
    endYear: 2024,
    monthlyData: true,
    showTarget: false,
    targetValue: 800000,
    showTrend: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Natural gas production data showing seasonal variations and long-term trends.'
      }
    }
  }
};

export const RenewableEnergy: Story = {
  args: {
    title: 'Renewable Energy Production',
    category: 'Primary electricity, hydro, nuclear, and other renewables',
    startYear: 2015,
    endYear: 2024,
    monthlyData: true,
    showTarget: true,
    targetValue: 200000,
    showTrend: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Tracks renewable energy production including hydro, nuclear, wind, and solar sources.'
      }
    }
  }
};

export const WithTarget: Story = {
  args: {
    title: 'Primary Energy with Production Target',
    category: 'Primary energy',
    startYear: 2020,
    endYear: 2024,
    monthlyData: true,
    showTarget: true,
    targetValue: 2800000,
    showTrend: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows primary energy production with a target line for goal tracking without trend smoothing.'
      }
    }
  }
};

export const LongTermTrends: Story = {
  args: {
    title: 'Long-term Energy Production (10 Years)',
    category: 'Primary energy',
    startYear: 2014,
    endYear: 2024,
    monthlyData: true,
    showTarget: false,
    targetValue: 2500000,
    showTrend: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Extended time range to show long-term energy production trends and cyclical patterns.'
      }
    }
  }
};

export const AnnualView: Story = {
  args: {
    title: 'Annual Energy Production Summary',
    category: 'Primary energy',
    startYear: 2015,
    endYear: 2024,
    monthlyData: false,
    showTarget: true,
    targetValue: 2500000,
    showTrend: false,
  },
  parameters: {
    docs: {
      description: {
        story: 'Annual aggregated view for high-level trend analysis without monthly fluctuations.'
      }
    }
  }
};

export const MultipleEnergyTypes: Story = {
  args: {
    title: 'Coal Production',
    category: 'Coal',
    startYear: 2015,
    endYear: 2024,
    monthlyData: true,
    showTarget: false,
    targetValue: 100000,
    showTrend: true,
  },
  parameters: {
    docs: {
      description: {
        story: 'Example of tracking a specific energy source (coal) to analyze sector-specific trends.'
      }
    }
  }
};