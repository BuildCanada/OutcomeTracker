# CFTAExceptionsChart Component

## Overview

The `CFTAExceptionsChart` component displays Canadian Free Trade Agreement (CFTA) exceptions by province and territory as a stacked area chart. It visualizes the number of trade barriers that each jurisdiction maintains from 2022-2024.

## Features

- **Stacked Area Chart**: Shows how each province/territory contributes to the total number of exceptions
- **Interactive Tooltips**: Displays detailed information including percentages and totals
- **Responsive Design**: Adapts to different screen sizes
- **Configurable Legend**: Can be shown or hidden based on requirements
- **Color-Coded Display**: Provinces/territories shown in various shades of grey, federal government in blue
- **Strategic Ordering**: Federal government positioned at bottom of stack, provinces sorted by their 2024 exception count (highest to lowest)

## Props

| Prop         | Type      | Default                                                            | Description                   |
| ------------ | --------- | ------------------------------------------------------------------ | ----------------------------- |
| `title`      | `string`  | `"Canadian Free Trade Agreement Exceptions by Province/Territory"` | Chart title                   |
| `showLegend` | `boolean` | `true`                                                             | Whether to display the legend |
| `height`     | `number`  | `400`                                                              | Chart height in pixels        |

## Data Source

The component uses data from the Canadian Federation of Independent Business (CFIB) located at:

```
/metrics/cfib/cfta-expections.json
```

### Data Structure

```json
{
  "metadata": {
    "title": "Canadian Free Trade Agreement Exceptions by Province/Territory",
    "description": "Number of exceptions to the Canadian Free Trade Agreement...",
    "source": "Canadian Federation of Independent Business (CFIB)",
    "lastUpdated": "2024",
    "unit": "Number of exceptions"
  },
  "data": {
    "Alberta": [
      [2022, 6],
      [2023, 6],
      [2024, 8]
    ],
    "Quebec": [
      [2022, 35],
      [2023, 35],
      [2024, 36]
    ]
    // ... other provinces
  }
}
```

## Usage

### Basic Usage

```tsx
import CFTAExceptionsChart from "@/components/charts/CFTAExceptionsChart";

function Dashboard() {
  return (
    <div className="w-full h-96">
      <CFTAExceptionsChart />
    </div>
  );
}
```

### With Custom Props

```tsx
<CFTAExceptionsChart
  title="Provincial Trade Barriers Over Time"
  showLegend={false}
  height={500}
/>
```

### In a Card Layout

```tsx
<div className="bg-white border rounded-lg p-6">
  <CFTAExceptionsChart title="CFTA Exceptions by Province" height={400} />
</div>
```

## Key Insights from the Data

- **Quebec** consistently has the highest number of exceptions (35-36)
- **Alberta** has the fewest exceptions, with a slight increase from 6 to 8
- **Federal government** (shown in blue at bottom) showed significant improvement, reducing from 29 to 21 exceptions in 2024
- **New Brunswick** shows an increasing trend (29 → 31)
- **Yukon** improved from 33 to 29 exceptions between 2023-2024

## Technical Details

- Built with Chart.js and react-chartjs-2
- Uses stacked area visualization with proper fill configurations
- Implements responsive design patterns
- Includes comprehensive tooltip information with percentages
- Color scheme: grey shades for provinces/territories, blue for federal government for clear distinction

## Accessibility

- Uses distinct grey shades for provinces/territories and blue for federal government
- Provides detailed tooltip information
- Supports keyboard navigation through Chart.js
- Text-based data available in tooltips for screen readers

## Related Components

- Other trade and economic charts in the `/components/charts/` directory
- Department metrics components that may incorporate trade data
