# API Integration Guide

## Overview

The Outcome Tracker frontend integrates with a separate backend API ([OutcomeTrackerAPI](https://github.com/BuildCanada/OutcomeTrackerAPI)) that provides promise tracking data, department information, and evidence updates.

## API Configuration

### Environment Setup
```bash
# .env
NEXT_PUBLIC_API_URL=https://www.buildcanada.com/tracker/api/v1  # Production
# NEXT_PUBLIC_API_URL=http://localhost:3000/                    # Local development
```

### Base URL Structure
```typescript
const API_BASE = process.env.NEXT_PUBLIC_API_URL;
// Results in: https://www.buildcanada.com/tracker/api/v1
```

## Data Fetching with SWR

### SWR Configuration
```typescript
// components/SWRProvider.tsx
const swrConfig = {
  fetcher: (url: string) => fetch(url).then(res => res.json()),
  revalidateOnFocus: false,
  revalidateIfStale: false,
  shouldRetryOnError: false,
};
```

### Basic Usage Pattern
```typescript
import useSWR from 'swr';

function useData(endpoint: string) {
  const { data, error, mutate } = useSWR(
    `${API_BASE}${endpoint}`,
    {
      revalidateIfStale: false,
    }
  );

  return {
    data,
    isLoading: !error && !data,
    isError: error,
    mutate,
  };
}
```

## API Endpoints

### 1. Departments List
```http
GET /tracker/api/v1/departments.json
```

**Response:**
```json
[
  {
    "id": 1,
    "display_name": "Prime Minister's Office",
    "official_name": "Office of the Prime Minister",
    "slug": "prime-minister-office",
    "priority": 1,
    "government_id": 101,
    "created_at": "2024-01-01T00:00:00Z",
    "updated_at": "2024-01-01T00:00:00Z"
  }
  // ... more departments
]
```

**Usage:**
```typescript
const { data: departments } = useSWR<DepartmentListing[]>(
  '/tracker/api/v1/departments.json'
);
```

### 2. Department Details
```http
GET /tracker/api/v1/departments/{slug}.json
```

**Parameters:**
- `slug`: Department identifier (e.g., `finance-canada`)

**Response:**
```json
{
  "display_name": "Finance Canada",
  "official_name": "Department of Finance Canada",
  "slug": "finance-canada",
  "minister": {
    "first_name": "Jane",
    "last_name": "Doe",
    "title": "Minister of Finance",
    "order_of_precedence": 3,
    "started_at": "2021-10-26",
    "ended_at": null,
    "avatar_url": "/avatars/jane-doe.jpg",
    "person_short_honorific": "Hon."
  },
  "promises": [
    {
      "id": 12345,
      "concise_title": "Reduce federal deficit",
      "description": "Work towards balanced budget",
      "text": "Full promise text...",
      "progress_score": 45,
      "progress_summary": "Initial steps taken",
      "last_evidence_date": "2024-03-15",
      "bc_promise_direction": "positive",
      "bc_promise_rank": "high",
      "bc_promise_rank_rationale": "Critical for fiscal health"
    }
    // ... more promises
  ]
}
```

**Usage:**
```typescript
const { data: department } = useSWR<Department>(
  `/tracker/api/v1/departments/${slug}.json`
);
```

### 3. Promise Details
```http
GET /tracker/api/v1/promises/{id}.json
```

**Parameters:**
- `id`: Promise identifier (numeric)

**Response:**
```json
{
  "id": 12345,
  "text": "We will work with all parties to reduce the federal deficit...",
  "description": "Commitment to fiscal responsibility",
  "concise_title": "Reduce federal deficit",
  "source_type": "mandate_letter",
  "source_url": "https://pm.gc.ca/...",
  "date_issued": "2021-12-16",
  "progress_score": 45,
  "progress_summary": "Budget 2024 shows deficit reduction path",
  "what_it_means_for_canadians": "Lower deficits mean...",
  "commitment_history_rationale": [
    {
      "date": "2024-03-15",
      "action": "Budget 2024 released",
      "source_url": "https://budget.gc.ca/2024/"
    }
  ],
  "evidences": [
    {
      "id": 98765,
      "title": "Budget 2024: Deficit Projections",
      "summary": "Government projects declining deficit...",
      "source_url": "https://budget.gc.ca/2024/",
      "published_at": "2024-03-15",
      "impact": "positive",
      "impact_magnitude": "moderate",
      "impact_reason": "Shows concrete steps"
    }
  ],
  "last_evidence_date": "2024-03-15"
}
```

**Usage:**
```typescript
const { data: promise } = useSWR<PromiseDetail>(
  `/tracker/api/v1/promises/${promiseId}.json`
);
```

## Data Prefetching

### Hover Prefetching
```typescript
// Prefetch department data on hover
<Link 
  href={`/${department.slug}`}
  onMouseEnter={async () => {
    const data = await fetch(`/tracker/api/v1/departments/${department.slug}.json`)
      .then(res => res.json());
    mutate(`/tracker/api/v1/departments/${department.slug}.json`, data);
  }}
>
  {department.name}
</Link>
```

### Route Prefetching
```typescript
// Prefetch common routes
useEffect(() => {
  // Prefetch popular departments
  const popularDepartments = ['prime-minister-office', 'finance-canada'];
  popularDepartments.forEach(slug => {
    mutate(`/tracker/api/v1/departments/${slug}.json`);
  });
}, []);
```

## Error Handling

### Global Error Handler
```typescript
function useSafeData<T>(endpoint: string) {
  const { data, error } = useSWR<T>(endpoint);
  
  if (error) {
    console.error('API Error:', error);
    // Log to error tracking service
    trackError(error, { endpoint });
  }
  
  return {
    data,
    isLoading: !error && !data,
    isError: error,
    errorMessage: error?.message || 'Failed to load data',
  };
}
```

### Component Error States
```typescript
function DepartmentView({ slug }: { slug: string }) {
  const { data, isLoading, isError, errorMessage } = useSafeData(
    `/tracker/api/v1/departments/${slug}.json`
  );

  if (isLoading) return <LoadingState />;
  if (isError) return <ErrorState message={errorMessage} />;
  if (!data) return <EmptyState />;

  return <DepartmentContent data={data} />;
}
```

## Caching Strategy

### SWR Cache Configuration
```typescript
// Global cache settings
const cacheConfig = {
  // Keep data fresh for 5 minutes
  dedupingInterval: 5 * 60 * 1000,
  
  // Don't revalidate on window focus
  revalidateOnFocus: false,
  
  // Keep stale data while revalidating
  revalidateIfStale: true,
  
  // Show stale data immediately
  suspense: false,
};
```

### Manual Cache Updates
```typescript
// Update cache after user action
async function updatePromiseProgress(promiseId: number, newScore: number) {
  // Optimistic update
  mutate(
    `/tracker/api/v1/promises/${promiseId}.json`,
    (current: PromiseDetail) => ({
      ...current,
      progress_score: newScore,
    }),
    false
  );
  
  // API call
  await updatePromiseAPI(promiseId, newScore);
  
  // Revalidate
  mutate(`/tracker/api/v1/promises/${promiseId}.json`);
}
```

## API Response Types

### Type Generation
```typescript
// lib/types.ts
// Keep types in sync with API responses

// Use strict typing
interface APIResponse<T> {
  data: T;
  meta?: {
    total: number;
    page: number;
    per_page: number;
  };
  errors?: Array<{
    code: string;
    message: string;
  }>;
}
```

### Type Guards
```typescript
function isDepartment(data: any): data is Department {
  return (
    typeof data === 'object' &&
    'slug' in data &&
    'promises' in data &&
    Array.isArray(data.promises)
  );
}

// Usage
const { data } = useSWR('/api/departments/finance-canada.json');
if (isDepartment(data)) {
  // TypeScript knows data is Department
}
```

## Performance Optimization

### Request Deduplication
```typescript
// SWR automatically deduplicates identical requests
// These will result in only one API call:
const { data: data1 } = useSWR('/api/departments.json');
const { data: data2 } = useSWR('/api/departments.json');
```

### Conditional Fetching
```typescript
// Only fetch when needed
const shouldFetch = isLoggedIn && hasPermission;
const { data } = useSWR(
  shouldFetch ? '/api/sensitive-data.json' : null
);
```

### Pagination
```typescript
function usePaginatedData(page: number) {
  const { data, error } = useSWR(
    `/api/promises?page=${page}&per_page=20`
  );
  
  return {
    promises: data?.data || [],
    totalPages: Math.ceil((data?.meta?.total || 0) / 20),
    isLoading: !error && !data,
  };
}
```

## Testing API Integration

### Mock API Responses
```typescript
// __mocks__/api.ts
export const mockDepartment: Department = {
  slug: 'test-department',
  display_name: 'Test Department',
  promises: [
    {
      id: 1,
      concise_title: 'Test Promise',
      // ... other fields
    },
  ],
};
```

### Test Implementation
```typescript
// DepartmentView.test.tsx
import { render, screen } from '@testing-library/react';
import { SWRConfig } from 'swr';

test('displays department data', async () => {
  render(
    <SWRConfig value={{ provider: () => new Map() }}>
      <DepartmentView slug="test-department" />
    </SWRConfig>
  );
  
  expect(await screen.findByText('Test Department')).toBeInTheDocument();
});
```

## Security Considerations

1. **CORS**: API must allow frontend domain
2. **HTTPS**: Always use secure connections
3. **Rate Limiting**: Implement client-side throttling
4. **Authentication**: Add auth headers when required
5. **Input Validation**: Validate all user inputs before API calls 