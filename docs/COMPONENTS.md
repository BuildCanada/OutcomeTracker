# Components Guide

## Overview

The Outcome Tracker uses a component-based architecture with React and TypeScript. Components are organized by feature and follow consistent patterns for maintainability.

## Component Categories

### 1. Layout Components

#### Header
```typescript
// components/header.tsx
interface HeaderProps {
  // No props currently
}
```
- Global navigation header
- Responsive mobile menu
- Consistent across all pages

#### Department Layout
```typescript
// app/[department]/layout.tsx
```
- Wraps department pages
- Handles department data fetching
- Renders minister info and navigation pills

### 2. Core Feature Components

#### DepartmentMetrics
```typescript
// components/DepartmentMetrics.tsx
interface DepartmentMetricsProps {
  departmentSlug: DepartmentSlug;
}
```
- Displays key performance indicators
- Dynamically loads relevant charts
- Responsive grid layout

**Usage:**
```tsx
<DepartmentMetrics departmentSlug="finance-canada" />
```

#### MinisterSection
```typescript
// components/MinisterSection.tsx
interface MinisterHeaderProps {
  minister: Minister;
}
```
- Shows minister avatar and details
- Displays tenure information
- Links to official pages

#### PromiseCard
```typescript
// components/PromiseCard.tsx
interface PromiseCardProps {
  promise: PromiseListing;
  departmentSlug: string;
}
```
- Individual promise display
- Progress indicator
- Click to open details modal

**Features:**
- Color-coded progress bars
- Hover effects
- Accessible keyboard navigation

### 3. Modal Components

#### PromiseModal
```typescript
// components/PromiseModal.tsx
interface PromiseModalProps {
  promiseId: number;
  onClose: () => void;
}
```
- Full promise details
- Evidence timeline
- Progress tracking

**Sections:**
- Promise text and metadata
- What it means for Canadians
- Evidence and timeline
- Related documents

#### ShareModal
```typescript
// components/ShareModal.tsx
interface ShareModalProps {
  isOpen: boolean;
  onClose: () => void;
  promiseTitle: string;
  promiseUrl: string;
}
```
- Social sharing options
- Copy link functionality
- Analytics tracking

#### FAQModal
```typescript
// components/FAQModal.tsx
interface FAQModalProps {
  isOpen: boolean;
  onClose: () => void;
}
```
- Frequently asked questions
- Methodology explanation
- Contact information

### 4. Chart Components

All charts follow a consistent pattern and use Chart.js:

#### Base Pattern
```typescript
interface ChartProps {
  title?: string;
  startYear?: number;
  endYear?: number;
  region?: string;
  showGoal?: boolean;
}
```

#### Available Charts

**PopulationChart**
- Population trends over time
- Regional filtering
- Goal line overlay

**GDPChart / GDPPerCapitaChart**
- Economic growth visualization
- Total vs per capita views
- Quarterly data points

**HousingStartsChart**
- Housing construction metrics
- Seasonally adjusted data
- Regional breakdown

**DefenseSpendingChart**
- Military expenditure trends
- International comparisons
- % of GDP calculations

**PrimaryEnergyChart**
- Energy production/consumption
- By type breakdown
- Import/export balance

**LabourProductivityGrowthChart**
- Productivity trends
- Industry comparisons
- Year-over-year changes

#### Chart Wrapper Component
```typescript
// components/charts/ChartWithSource.tsx
interface ChartWithSourceProps {
  title: string;
  source: string;
  sourceUrl?: string;
  children: React.ReactNode;
}
```
- Consistent chart container
- Source attribution
- Responsive sizing

### 5. UI Components (shadcn/ui)

Pre-built accessible components from shadcn/ui:

#### Button
```tsx
import { Button } from "@/components/ui/button"

<Button variant="default" size="md">
  Click me
</Button>
```

**Variants:** `default`, `destructive`, `outline`, `secondary`, `ghost`, `link`

#### Card
```tsx
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"

<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
  </CardHeader>
  <CardContent>Content</CardContent>
</Card>
```

#### Dialog
```tsx
import { Dialog, DialogContent, DialogHeader } from "@/components/ui/dialog"

<Dialog open={isOpen} onOpenChange={setIsOpen}>
  <DialogContent>
    <DialogHeader>Title</DialogHeader>
    {/* Content */}
  </DialogContent>
</Dialog>
```

#### Badge
```tsx
import { Badge } from "@/components/ui/badge"

<Badge variant="default">Status</Badge>
```

**Variants:** `default`, `secondary`, `outline`, `destructive`

#### Skeleton
```tsx
import { Skeleton } from "@/components/ui/skeleton"

<Skeleton className="h-10 w-full" />
```
- Loading placeholder
- Smooth animations
- Customizable dimensions

### 6. Utility Components

#### SWRProvider
```typescript
// components/SWRProvider.tsx
```
- Configures SWR globally
- Sets up error handling
- Manages cache settings

#### SimpleAnalytics
```typescript
// components/SimpleAnalytics.tsx
```
- Privacy-focused analytics
- Page view tracking
- Custom event support

## Component Best Practices

### 1. TypeScript Props
Always define explicit prop types:
```typescript
interface ComponentProps {
  required: string;
  optional?: number;
  withDefault?: boolean;
}

export function Component({ 
  required, 
  optional, 
  withDefault = true 
}: ComponentProps) {
  // ...
}
```

### 2. Accessibility
- Use semantic HTML
- Include ARIA labels
- Ensure keyboard navigation
- Test with screen readers

### 3. Performance
```typescript
// Memoize expensive components
const ExpensiveComponent = React.memo(({ data }) => {
  // ...
});

// Use dynamic imports for heavy components
const HeavyChart = dynamic(() => import('./HeavyChart'), {
  loading: () => <Skeleton />,
  ssr: false
});
```

### 4. Error Boundaries
```typescript
function ComponentWithError() {
  if (!data) {
    return <ErrorState message="No data available" />;
  }
  
  try {
    return <DataDisplay data={data} />;
  } catch (error) {
    return <ErrorState message="Failed to display data" />;
  }
}
```

### 5. Responsive Design
```tsx
// Use Tailwind responsive utilities
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  {/* Content */}
</div>

// Custom hook for mobile detection
const isMobile = useMobile();
```

## Creating New Components

### 1. Component Structure
```typescript
// components/NewComponent/NewComponent.tsx
import { FC } from 'react';
import { cn } from '@/lib/utils';

interface NewComponentProps {
  className?: string;
  // other props
}

export const NewComponent: FC<NewComponentProps> = ({ 
  className,
  ...props 
}) => {
  return (
    <div className={cn('default-styles', className)}>
      {/* Component content */}
    </div>
  );
};

// components/NewComponent/index.ts
export { NewComponent } from './NewComponent';
```

### 2. Add Stories
```typescript
// components/NewComponent/NewComponent.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { NewComponent } from './NewComponent';

const meta: Meta<typeof NewComponent> = {
  title: 'Components/NewComponent',
  component: NewComponent,
};

export default meta;

export const Default: StoryObj<typeof NewComponent> = {
  args: {
    // default props
  },
};
```

### 3. Add Tests
```typescript
// components/NewComponent/NewComponent.test.tsx
import { render, screen } from '@testing-library/react';
import { NewComponent } from './NewComponent';

describe('NewComponent', () => {
  it('renders correctly', () => {
    render(<NewComponent />);
    // assertions
  });
});
```

## Component Documentation

Each component should include:
1. **Purpose**: What the component does
2. **Props**: All available props with types
3. **Usage**: Example implementation
4. **Variants**: Different states/styles
5. **Accessibility**: ARIA and keyboard support 