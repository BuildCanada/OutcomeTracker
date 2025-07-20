# FederalPhysicianSupplyChart Component

## Overview

The `FederalPhysicianSupplyChart` component displays federal physician supply data for Canada as a line chart. It visualizes the total number of physicians across the country from 2019-2023, providing insights into healthcare workforce trends at the national level.

## Features

- **Line Chart Visualization**: Shows physician supply trends over time
- **Interactive Tooltips**: Displays detailed information with formatted numbers
- **Responsive Design**: Adapts to different screen sizes
- **Configurable Time Range**: Allows filtering by start and end years
- **Professional Styling**: Uses blue color scheme appropriate for healthcare data
- **Formatted Numbers**: Large numbers displayed with proper comma separators

## Props

| Prop        | Type     | Default                      | Description                    |
| ----------- | -------- | ---------------------------- | ------------------------------ |
| `title`     | `string` | `"Federal Physician Supply"` | Chart title                    |
| `startYear` | `number` | `2019`                       | Starting year for data display |
| `endYear`   | `number` | `2023`                       | Ending year for data display   |
| `height`    | `number` | `400`                        | Chart height in pixels         |

## Data Source

The component uses data from the Canadian Institute for Health Information (CIHI) located at:

```
/metrics/cihi/physician_supply.json
```

### Data Structure

```json
{
  "Canada": {
    "Physician Supply": [
      [2019, 91372],
      [2020, 92173],
      [2021, 94119],
      [2022, 96020],
      [2023, 97384]
    ]
  }
}
```

## Usage

### Basic Usage

```tsx
import FederalPhysicianSupplyChart from "@/components/charts/FederalPhysicianSupplyChart";

function HealthDashboard() {
  return (
    <div className="w-full h-96">
      <FederalPhysicianSupplyChart />
    </div>
  );
}
```

### With Custom Props

```tsx
<FederalPhysicianSupplyChart
  title="Department of Health - Physician Supply Metrics"
  startYear={2021}
  endYear={2023}
  height={500}
/>
```

### In Department Context

```tsx
<div className="bg-white border rounded-lg p-6">
  <FederalPhysicianSupplyChart
    title="Canada Physician Workforce Trends"
    height={450}
  />
</div>
```

## Key Insights from the Data

- **Consistent Growth**: Physician supply has grown steadily from 91,372 in 2019 to 97,384 in 2023
- **Annual Increase**: Average annual growth of approximately 1.6%
- **Healthcare Capacity**: Represents significant expansion of healthcare workforce capacity
- **Post-Pandemic Recovery**: Continued growth through 2020-2023 period despite global challenges

## Department Context

This component is specifically designed for the **Department of Health** and provides:

- Federal-level physician supply metrics
- Workforce planning insights
- Healthcare capacity monitoring
- Policy impact visualization

## Technical Details

- Built with Chart.js and react-chartjs-2
- Uses line chart visualization for trend analysis
- Implements responsive design patterns
- Blue color scheme (`rgb(54, 162, 235)`) for professional healthcare presentation
- Formatted tooltips with comma-separated numbers
- Smooth line tension for better visual appeal

## Accessibility

- High contrast blue color scheme for visibility
- Detailed tooltip information for screen readers
- Proper axis labeling and titles
- Keyboard navigation support through Chart.js
- Semantic chart structure

## Related Components

- Provincial physician supply charts (if implemented)
- Healthcare metrics dashboards
- Department of Health specific visualizations
- Medical workforce analytics components

## Performance Considerations

- Lightweight data structure (5 data points)
- Efficient rendering with Chart.js
- Minimal re-renders with proper props handling
- Responsive without heavy computations
