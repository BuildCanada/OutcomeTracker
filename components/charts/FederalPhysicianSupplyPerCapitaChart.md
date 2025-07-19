# FederalPhysicianSupplyPerCapitaChart Component

## Overview

The `FederalPhysicianSupplyPerCapitaChart` component displays federal physician supply per capita data for Canada as a line chart with an optional target line. It visualizes the number of physicians per 1,000 people from 2019-2023, providing insights into healthcare workforce density and progress toward policy targets.

## Features

- **Line Chart with Target**: Shows physician density trends with configurable target line
- **Per Capita Calculation**: Automatically calculates physicians per 1,000 people using CIHI and StatCan data
- **Interactive Tooltips**: Displays detailed information with proper decimal formatting
- **Responsive Design**: Adapts to different screen sizes
- **Configurable Time Range**: Allows filtering by start and end years
- **Target Visualization**: Dashed red line showing policy targets (default: 3.5 per 1,000)
- **Professional Styling**: Blue for actual data, red for targets

## Props

| Prop          | Type      | Default                                 | Description                        |
| ------------- | --------- | --------------------------------------- | ---------------------------------- |
| `title`       | `string`  | `"Federal Physician Supply Per Capita"` | Chart title                        |
| `startYear`   | `number`  | `2019`                                  | Starting year for data display     |
| `endYear`     | `number`  | `2023`                                  | Ending year for data display       |
| `height`      | `number`  | `400`                                   | Chart height in pixels             |
| `showTarget`  | `boolean` | `true`                                  | Show/hide target line              |
| `targetValue` | `number`  | `3.5`                                   | Target physicians per 1,000 people |

## Data Sources

The component uses data from two sources:

1. **CIHI Physician Supply**: `/metrics/cihi/physician_supply.json`
2. **StatCan Population**: `/metrics/statscan/population.json`

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

```json
{
  "data": {
    "Canada": [
      ["2019-01", 37336956.0],
      ["2020-01", 37928208.0],
      ["2021-01", 38058291.0],
      ["2022-01", 38566032.0],
      ["2023-01", 39527986.0]
    ]
  }
}
```

## Usage

### Basic Usage

```tsx
import FederalPhysicianSupplyPerCapitaChart from "@/components/charts/FederalPhysicianSupplyPerCapitaChart";

function HealthDashboard() {
  return (
    <div className="w-full h-96">
      <FederalPhysicianSupplyPerCapitaChart />
    </div>
  );
}
```

### With Custom Target

```tsx
<FederalPhysicianSupplyPerCapitaChart
  title="Department of Health - Physician Density Target"
  targetValue={3.5}
  showTarget={true}
  height={500}
/>
```

### Without Target Line

```tsx
<FederalPhysicianSupplyPerCapitaChart
  title="Current Physician Density Trends"
  showTarget={false}
  startYear={2021}
  endYear={2023}
/>
```

## Key Insights from the Data

- **Current Density**: ~2.46 physicians per 1,000 people in 2023
- **Growth Trend**: Steady increase from ~2.45 (2019) to ~2.46 (2023)
- **Target Gap**: Approximately 1.04 physicians per 1,000 people below target
- **Policy Implications**: Significant expansion needed to reach 3.5 target

## Department Context

This component is specifically designed for the **Department of Health** and provides:

- Healthcare workforce density metrics
- Progress tracking toward policy targets
- International comparison context
- Resource planning insights

## Technical Details

- **Calculation**: (Total Physicians / Total Population) × 1,000
- **Data Matching**: Uses January 1st population data for each year
- **Built with Chart.js**: Uses react-chartjs-2 for interactive visualizations
- **Color Scheme**: Blue for actual data, red dashed line for targets
- **Responsive**: Automatic scaling and axis adjustment
- **Precision**: Displays values to 2 decimal places

## Target Context

The default target of 3.5 physicians per 1,000 people represents:

- **Policy Goal**: Federal healthcare workforce expansion target
- **International Benchmark**: Aligned with developed nation standards
- **Healthcare Capacity**: Improved access and reduced wait times

## Accessibility

- High contrast color scheme for visibility
- Detailed tooltip information for screen readers
- Proper axis labeling with units
- Keyboard navigation support through Chart.js
- Clear distinction between actual and target data

## Related Components

- `FederalPhysicianSupplyChart` - Absolute physician counts
- Provincial physician density charts (if implemented)
- Healthcare capacity metrics
- Department of Health dashboards

## Performance Considerations

- Lightweight calculation (5 data points)
- Efficient data joining between physician and population datasets
- Minimal re-renders with proper props handling
- Responsive without heavy computations
