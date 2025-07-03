# Data Sources & Metrics

## Overview

The Outcome Tracker aggregates data from multiple authoritative sources to provide comprehensive metrics on Canadian government performance and economic indicators.

## Data Sources

### 1. Statistics Canada (StatsCan)
Primary source for Canadian economic and demographic data.

**Metrics Retrieved:**
- **Population Data** (`/metrics/statscan/population.json`)
  - Total population by region
  - Monthly updates
  - Historical data from 1971
  
- **GDP Data** (`/metrics/statscan/gdp.json`)
  - Gross Domestic Product
  - Quarterly updates
  - Chained 2017 dollars
  
- **Housing Starts** (`/metrics/statscan/housing-starts.json`)
  - New housing construction
  - Monthly data by region
  - Urban vs rural breakdown
  
- **Labour Productivity** (`/metrics/statscan/labour-productivity.json`)
  - Output per hour worked
  - Quarterly updates
  - By industry sector
  
- **Balance Sheets** (`/metrics/statscan/balance-sheets.json`)
  - National balance sheet accounts
  - Quarterly data
  - Assets and liabilities
  
- **Primary Energy** (`/metrics/statscan/primary-energy.json`)
  - Energy production and consumption
  - Annual data
  - By energy type

### 2. World Bank
International comparative data and global indicators.

**Metrics Retrieved:**
- **Defense Spending** (`/metrics/worldbank/defense-spending.json`)
  - Military expenditure as % of GDP
  - Annual data
  - International comparisons

### 3. Canadian Federation of Independent Business (CFIB)
Business and trade-related metrics.

**Metrics Retrieved:**
- **CFTA Exceptions** (`/metrics/cfib/cfta-expections.json`)
  - Canadian Free Trade Agreement exceptions
  - By province/territory
  - Regulatory barriers

### 4. Canadian Institute for Health Information (CIHI)
Healthcare system performance metrics.

**Metrics Retrieved:**
- **Physician Supply** (`/metrics/cihi/physician_supply.json`)
  - Number of physicians by specialty
  - Provincial distribution
  - Per capita calculations

## Data Update Process

### Automated Updates via GitHub Actions
```yaml
# .github/workflows/update-metrics.yml
schedule:
  - cron: '0 0 * * 0'  # Weekly on Sundays

jobs:
  update-metrics:
    steps:
      - Fetch latest data from APIs
      - Process and validate
      - Update JSON files
      - Commit changes
```

### Manual Updates
For data sources without APIs:
1. Download latest data files
2. Run processing scripts
3. Validate output
4. Create PR with updates

## Metric Calculations

### Per Capita Calculations
```typescript
// components/charts/utils/PerCapitaCalculator.ts
export class PerCapitaCalculator {
  static calculate(value: number, population: number): number {
    return (value / population) * 1000000; // Per million
  }
}
```

### Growth Rate Calculations
```typescript
function calculateGrowthRate(current: number, previous: number): number {
  return ((current - previous) / previous) * 100;
}
```

### Moving Averages
```typescript
function movingAverage(data: number[], period: number): number[] {
  return data.map((_, idx) => {
    if (idx < period - 1) return null;
    const slice = data.slice(idx - period + 1, idx + 1);
    return slice.reduce((a, b) => a + b) / period;
  });
}
```

## Chart Components

Each metric has a corresponding chart component:

### Population Chart
- **Component**: `PopulationChart.tsx`
- **Data**: Monthly population by region
- **Features**: 
  - Regional filtering
  - Goal line overlay
  - Historical comparison

### GDP Chart
- **Component**: `GDPChart.tsx` & `GDPPerCapitaChart.tsx`
- **Data**: Quarterly GDP in chained dollars
- **Features**:
  - Total and per capita views
  - Recession indicators
  - Trend analysis

### Housing Charts
- **Component**: `HousingStartsChart.tsx` & `AnnualizedHousingChart.tsx`
- **Data**: Monthly housing starts
- **Features**:
  - Seasonally adjusted
  - Regional breakdown
  - Annualized projections

### Energy Chart
- **Component**: `PrimaryEnergyChart.tsx`
- **Data**: Annual energy production/consumption
- **Features**:
  - By energy type
  - Import/export balance
  - Renewable vs non-renewable

## Promise Tracking Data

### Promise Structure
```json
{
  "id": 12345,
  "text": "Original promise text",
  "concise_title": "Short descriptive title",
  "department_slug": "finance-canada",
  "progress_score": 75,
  "progress_summary": "Legislation introduced",
  "evidences": [
    {
      "title": "Bill C-XX introduced",
      "source_url": "https://parl.ca/...",
      "published_at": "2024-01-15",
      "impact": "positive",
      "impact_magnitude": "significant"
    }
  ]
}
```

### Progress Score Calculation
- **0-20**: Not started or minimal action
- **21-40**: Initial steps taken
- **41-60**: Substantial progress
- **61-80**: Mostly complete
- **81-100**: Fully implemented

### Evidence Types
1. **Legislative**: Bills, acts, regulations
2. **Financial**: Budget allocations, spending
3. **Policy**: Orders in Council, directives
4. **Operational**: Program launches, hiring
5. **Results**: Measurable outcomes

## Data Quality & Validation

### Validation Rules
```typescript
interface ValidationRule {
  field: string;
  type: 'required' | 'numeric' | 'date' | 'range';
  constraints?: any;
}

const GDP_VALIDATION: ValidationRule[] = [
  { field: 'date', type: 'date' },
  { field: 'value', type: 'numeric' },
  { field: 'value', type: 'range', constraints: { min: 0 } }
];
```

### Data Integrity Checks
1. **Completeness**: No missing required fields
2. **Consistency**: Values within expected ranges
3. **Timeliness**: Data not older than threshold
4. **Accuracy**: Cross-reference with source

## API Data Format

### Department Endpoint
```json
GET /api/v1/departments/{slug}.json

{
  "display_name": "Finance Canada",
  "official_name": "Department of Finance Canada",
  "slug": "finance-canada",
  "minister": {
    "first_name": "Jane",
    "last_name": "Doe",
    "title": "Minister of Finance"
  },
  "promises": [...]
}
```

### Promise Detail Endpoint
```json
GET /api/v1/promises/{id}.json

{
  "id": 12345,
  "text": "Full promise text...",
  "progress_score": 75,
  "evidences": [...],
  "timeline": [...]
}
```

## Adding New Metrics

### 1. Create Data Source
```bash
# Add new JSON file
touch metrics/newsource/metric-name.json
```

### 2. Define Data Structure
```typescript
interface NewMetricData {
  source: string;
  lastUpdated: string;
  data: {
    [key: string]: Array<[string, number]>;
  };
}
```

### 3. Create Chart Component
```typescript
// components/charts/NewMetricChart.tsx
import data from '@/metrics/newsource/metric-name.json';

export function NewMetricChart() {
  // Implementation
}
```

### 4. Add to Department Metrics
```typescript
// components/DepartmentMetrics.tsx
const METRIC_COMPONENTS = {
  'new-metric': NewMetricChart,
  // ...
};
```

## Data Privacy & Security

- No personally identifiable information (PII)
- All data from public sources
- API rate limiting implemented
- CORS policies enforced
- SSL/TLS for all connections 