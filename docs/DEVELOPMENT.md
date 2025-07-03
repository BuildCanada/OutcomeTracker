# Development Guide

## Prerequisites

- **Node.js**: Version 18.x or higher
- **pnpm**: Version 8.x or higher
- **Git**: For version control
- **VS Code** (recommended): With TypeScript and Tailwind extensions

## Initial Setup

### 1. Clone the Repository
```bash
git clone https://github.com/BuildCanada/OutcomeTracker.git
cd OutcomeTracker
```

### 2. Install Dependencies
```bash
pnpm install
```

### 3. Environment Variables
Create a `.env` file in the root directory:

```bash
# Create .env file
touch .env
```

Add the following content:
```env
# API Configuration
NEXT_PUBLIC_API_URL=https://www.buildcanada.com/tracker/api/v1  # Production API
# NEXT_PUBLIC_API_URL=http://localhost:3000/                    # Local API

# Analytics (optional)
# NEXT_PUBLIC_SIMPLE_ANALYTICS_ID=your-analytics-id

# Feature Flags (optional)
# NEXT_PUBLIC_ENABLE_ANALYTICS=true
```

### 4. Start Development Server
```bash
# Using Turbopack (faster, recommended)
pnpm turbo

# Using standard Next.js
pnpm dev
```

The application will be available at [http://localhost:4444/tracker](http://localhost:4444/tracker)

## Development Scripts

```bash
# Development
pnpm dev          # Start development server
pnpm turbo        # Start with Turbopack
pnpm build        # Build for production
pnpm start        # Start production server

# Testing & Quality
pnpm lint         # Run ESLint
pnpm type-check   # TypeScript type checking
pnpm test         # Run tests (when configured)

# Storybook
pnpm storybook    # Start Storybook dev server
pnpm build-storybook  # Build Storybook
```

## Code Style Guide

### TypeScript
```typescript
// ✅ DO: Use explicit types
interface PromiseData {
  id: number;
  title: string;
  progress: number;
}

// ❌ DON'T: Use 'any' type
const data: any = fetchData();

// ✅ DO: Use const assertions for constants
const DEPARTMENTS = ['finance', 'health'] as const;

// ✅ DO: Destructure props with types
interface Props {
  title: string;
  count: number;
}
const Component: React.FC<Props> = ({ title, count }) => {
  // ...
};
```

### React Components
```typescript
// ✅ DO: Use functional components with TypeScript
interface ButtonProps {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary';
}

export const Button: React.FC<ButtonProps> = ({ 
  label, 
  onClick, 
  variant = 'primary' 
}) => {
  return (
    <button 
      className={cn('px-4 py-2', {
        'bg-primary': variant === 'primary',
        'bg-secondary': variant === 'secondary'
      })}
      onClick={onClick}
    >
      {label}
    </button>
  );
};

// ✅ DO: Use custom hooks for logic
function usePromiseData(id: number) {
  const { data, error } = useSWR(`/api/promises/${id}`);
  return {
    promise: data,
    isLoading: !error && !data,
    isError: error
  };
}
```

### File Organization
```
components/
├── PromiseCard/
│   ├── PromiseCard.tsx      # Component implementation
│   ├── PromiseCard.test.tsx # Tests
│   ├── PromiseCard.stories.tsx # Storybook stories
│   └── index.ts            # Export
```

## Working with SWR

### Basic Data Fetching
```typescript
import useSWR from 'swr';

function DepartmentPage({ slug }: { slug: string }) {
  const { data, error, mutate } = useSWR(
    `/tracker/api/v1/departments/${slug}.json`,
    {
      revalidateIfStale: false,
      revalidateOnFocus: false
    }
  );

  if (error) return <div>Failed to load</div>;
  if (!data) return <Skeleton />;

  return <DepartmentView data={data} />;
}
```

### Prefetching
```typescript
// Prefetch on hover
<Link 
  href={`/${department.slug}`}
  onMouseEnter={() => {
    mutate(`/tracker/api/v1/departments/${department.slug}.json`);
  }}
>
  {department.name}
</Link>
```

## Adding New Features

### 1. New Chart Component
```typescript
// components/charts/NewMetricChart.tsx
import { ChartWithSource } from './ChartWithSource';
import metricData from '@/metrics/source/metric.json';

export function NewMetricChart() {
  // Process data
  const chartData = processMetricData(metricData);
  
  return (
    <ChartWithSource
      title="New Metric"
      source="Data Source"
      sourceUrl="https://source.url"
    >
      <Line data={chartData} options={options} />
    </ChartWithSource>
  );
}
```

### 2. New Department
1. Add to `DepartmentSlug` type in `lib/types.ts`
2. Add to `DEPARTMENTS` array in `app/[department]/_constants.ts`
3. Ensure API has corresponding department data

### 3. New Promise Feature
```typescript
// components/PromiseFeature.tsx
interface PromiseFeatureProps {
  promiseId: number;
}

export function PromiseFeature({ promiseId }: PromiseFeatureProps) {
  const { data: promise } = useSWR(`/api/promises/${promiseId}`);
  
  // Implementation
}
```

## Testing

### Unit Tests with Vitest
```typescript
// Button.test.tsx
import { render, screen } from '@testing-library/react';
import { Button } from './Button';

describe('Button', () => {
  it('renders with label', () => {
    render(<Button label="Click me" onClick={() => {}} />);
    expect(screen.getByText('Click me')).toBeInTheDocument();
  });
});
```

### Storybook Stories
```typescript
// Button.stories.tsx
import type { Meta, StoryObj } from '@storybook/react';
import { Button } from './Button';

const meta: Meta<typeof Button> = {
  title: 'UI/Button',
  component: Button,
};

export default meta;

export const Primary: StoryObj<typeof Button> = {
  args: {
    label: 'Primary Button',
    variant: 'primary',
  },
};
```

## Debugging

### Common Issues

1. **API Connection Failed**
   - Check `.env` file has correct `NEXT_PUBLIC_API_URL`
   - Ensure API is running if using local backend

2. **TypeScript Errors**
   ```bash
   pnpm tsc --noEmit  # Check for type errors
   ```

3. **Build Failures**
   ```bash
   rm -rf .next node_modules
   pnpm install
   pnpm build
   ```

### Debug Tools
- React Developer Tools
- Next.js built-in error overlay
- Chrome DevTools Network tab for API calls
- SWR DevTools for cache inspection

## Performance Tips

1. **Use Dynamic Imports**
   ```typescript
   const HeavyChart = dynamic(() => import('./HeavyChart'), {
     loading: () => <Skeleton />,
     ssr: false
   });
   ```

2. **Optimize Images**
   ```typescript
   import Image from 'next/image';
   
   <Image 
     src="/image.jpg" 
     alt="Description"
     width={800}
     height={600}
     priority={isAboveFold}
   />
   ```

3. **Memoize Expensive Computations**
   ```typescript
   const processedData = useMemo(() => {
     return heavyDataProcessing(rawData);
   }, [rawData]);
   ```

## Git Workflow

### Branch Naming
- `feature/add-new-chart`
- `fix/promise-loading-error`
- `docs/update-readme`
- `refactor/optimize-api-calls`

### Commit Messages
```bash
# Good
git commit -m "feat: add GDP per capita chart"
git commit -m "fix: resolve promise modal closing issue"
git commit -m "docs: update development setup guide"

# Bad
git commit -m "fixed stuff"
git commit -m "WIP"
```

### Pull Request Process
1. Create feature branch from `main`
2. Make changes following style guide
3. Test thoroughly
4. Submit PR with clear description
5. Address review feedback
6. Merge after approval 