import type { Meta, StoryObj } from '@storybook/react';
import DepartmentMetrics from '../components/DepartmentMetrics';

const meta = {
  title: 'Components/DepartmentMetrics',
  component: DepartmentMetrics,
  parameters: {
    layout: 'padded',
    docs: {
      description: {
        component: 'Displays government department metrics with interactive charts and targets. Features real data from StatCan for key departments including Prime Minister (GDP per capita), Finance (capital formation & balance), Housing (starts), and Immigration (NPR population).'
      }
    }
  },
  tags: ['autodocs'],
  argTypes: {
    departmentSlug: {
      control: 'select',
      options: [
        'privy-council-office',
        'finance-canada',
        'infrastructure-canada',
        'immigration-refugees-and-citizenship-canada',
        'national-defence',
        'natural-resources-canada',
        'treasury-board-of-canada-secretariat',
        'innovation-science-and-economic-development-canada',
        'health-canada',
        'invalid-department'
      ],
      description: 'The department slug to display metrics for. Prime Minister, Finance, Housing, and Immigration have interactive charts.',
    },
  },
} satisfies Meta<typeof DepartmentMetrics>;

export default meta;
type Story = StoryObj<typeof meta>;

export const PrimeMinister: Story = {
  args: {
    departmentSlug: 'privy-council-office',
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows GDP per capita metrics with interactive chart and target line.'
      }
    }
  }
};

export const Finance: Story = {
  args: {
    departmentSlug: 'finance-canada',
  },
  parameters: {
    docs: {
      description: {
        story: 'Displays capital formation percentage of GDP and operating balance charts with real StatCan data.'
      }
    }
  }
};

export const Housing: Story = {
  args: {
    departmentSlug: 'infrastructure-canada',
  },
  parameters: {
    docs: {
      description: {
        story: 'Features housing starts data with trend analysis and 500k/year target visualization.'
      }
    }
  }
};

export const Immigration: Story = {
  args: {
    departmentSlug: 'immigration-refugees-and-citizenship-canada',
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows NPR population percentage chart with 5% target line and placeholder for PR admissions chart.'
      }
    }
  }
};

export const Defence: Story = {
  args: {
    departmentSlug: 'national-defence',
  },
};

export const Energy: Story = {
  args: {
    departmentSlug: 'natural-resources-canada',
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows total primary energy production chart with real StatCan data including crude oil, natural gas, and renewable sources with trend analysis.'
      }
    }
  }
};



export const Innovation: Story = {
  args: {
    departmentSlug: 'innovation-science-and-economic-development-canada',
  },
};

export const Health: Story = {
  args: {
    departmentSlug: 'health-canada',
  },
};

export const GovernmentTransformation: Story = {
  args: {
    departmentSlug: 'treasury-board-of-canada-secretariat',
  },
  parameters: {
    docs: {
      description: {
        story: 'Shows public service productivity chart with real labour productivity data for the non-business sector and 20% increase target.'
      }
    }
  }
};

export const NoDepartmentData: Story = {
  args: {
    departmentSlug: 'invalid-department' as any,
  },
  parameters: {
    docs: {
      description: {
        story: 'Demonstrates graceful fallback UI when no metrics data is available for a department.'
      }
    }
  }
};