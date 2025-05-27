# DepartmentMetrics Component

A React component that displays guiding metrics for Canadian government departments based on the 2029 targets table.

## Overview

The `DepartmentMetrics` component takes a `DepartmentSlug` and renders a comprehensive metrics table showing:
- Metric names and definitions
- 2029 targets
- Data sources (with links where available)
- Implementation status

## Usage

```tsx
import DepartmentMetrics from '@/components/DepartmentMetrics'

function DepartmentPage() {
  return (
    <DepartmentMetrics departmentSlug="finance-canada" />
  )
}
```

## Props

| Prop | Type | Required | Description |
|------|------|----------|-------------|
| `departmentSlug` | `DepartmentSlug` | Yes | The department identifier to display metrics for |

## Supported Departments

The component currently supports metrics for the following departments:

- **Prime Minister** (`privy-council-office`)
  - GDP per capita
  
- **Finance** (`finance-canada`)
  - % of GDP in capital-focused public and private investment
  - Operating Deficit
  
- **Housing** (`infrastructure-canada`)
  - Housing starts
  
- **Immigration** (`immigration-refugees-and-citizenship-canada`)
  - % of PR admissions
  - % NPR population
  - Relative median income of very recent immigrants
  
- **Defence** (`national-defence`)
  - % of GDP spent
  - % towards modernization
  
- **Energy** (`natural-resources-canada`)
  - Energy exports
  - Time to approval
  
- **Government Transformation** (`treasury-board-of-canada-secretariat`)
  - Public service productivity
  
- **Innovation** (`innovation-science-and-economic-development-canada`)
  - Labour Productivity Growth
  
- **Health** (`health-canada`)
  - Physicians per capita

## Features

- **Responsive Table**: Displays metrics in a clean, scrollable table format
- **External Links**: Data sources link to StatCan and other official sources
- **Status Badges**: Visual indicators for implementation status
- **Interactive Charts**: Real data visualizations for key departments
- **Fallback UI**: Graceful handling of departments without defined metrics

## Status Badge Variants

- **Done**: Green badge for completed metrics
- **Need**: Secondary badge for metrics requiring updates
- **Pending**: Outline badge for metrics without status
- **Issues**: Destructive badge for metrics with problems

## Chart Support

The component includes real data visualizations for key departments:

- **Prime Minister**: GDP Per Capita chart with target line
- **Finance**: Capital Formation % of GDP and Operating Balance charts
- **Housing**: Housing Starts chart with trend line
- **Immigration**: NPR Population % chart with target
- **Government Transformation**: Public Service Productivity chart with 20% increase target
- **Energy**: Total Primary Energy Production chart with trend analysis

Other departments show "Chart coming soon" placeholders.

## Future Enhancements

- Add charts for remaining departments (Defence, Innovation, Health)
- Add real-time data fetching from StatCan APIs
- Implement metric history tracking
- Add export functionality for metrics data

## Dependencies

- React
- Tailwind CSS
- Radix UI components (Card, Table, Badge)
- Lucide React icons
- Chart.js and react-chartjs-2
- Existing chart components from `/components/charts/`