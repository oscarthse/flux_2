# Frontend Architecture

> **Part of:** [Flux Architecture Documentation](./README.md)

---

## Application Structure

**Location:** `apps/web/`

```
apps/web/
├── src/
│   ├── app/                      # Next.js 14 App Router
│   │   ├── (auth)/              # Auth route group
│   │   │   ├── login/
│   │   │   ├── register/
│   │   │   └── layout.tsx
│   │   ├── (dashboard)/         # Protected route group
│   │   │   ├── dashboard/
│   │   │   ├── forecasts/
│   │   │   ├── procurement/
│   │   │   ├── menu/
│   │   │   ├── team/
│   │   │   ├── settings/
│   │   │   └── layout.tsx       # Dashboard layout with sidebar
│   │   ├── (marketing)/         # Public route group
│   │   │   ├── page.tsx         # Landing page
│   │   │   ├── pricing/
│   │   │   └── layout.tsx
│   │   ├── api/                 # Next.js API routes
│   │   │   └── webhooks/       # Webhook handlers only (API proxied to FastAPI)
│   │   └── layout.tsx           # Root layout
│   ├── components/              # React components (Atomic Design)
│   │   ├── atoms/
│   │   ├── molecules/
│   │   ├── organisms/
│   │   ├── templates/
│   │   └── features/
│   ├── lib/                     # Utilities
│   │   ├── api-client/         # Auto-generated OpenAPI client
│   │   ├── auth.ts             # Auth utilities
│   │   └── utils.ts
│   ├── hooks/                   # Custom React hooks
│   │   ├── use-restaurant.ts
│   │   ├── use-forecasts.ts
│   │   └── use-toast.ts
│   ├── providers/               # Context providers
│   │   ├── query-provider.tsx  # React Query provider
│   │   └── toast-provider.tsx
│   └── styles/
│       └── globals.css
├── public/
└── next.config.js
```

## Routing Strategy

### Route Groups

Next.js 14 App Router with three route groups:

**1. (auth) - Authentication Routes**
```typescript
// apps/web/src/app/(auth)/layout.tsx

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="max-w-md w-full">
        <div className="text-center mb-8">
          <h1 className="text-3xl font-bold">Flux</h1>
          <p className="text-gray-600 mt-2">Restaurant Intelligence Platform</p>
        </div>
        {children}
      </div>
    </div>
  );
}
```

**2. (dashboard) - Protected Routes**
```typescript
// apps/web/src/app/(dashboard)/layout.tsx

import { redirect } from 'next/navigation';
import { getServerSession } from 'next-auth';
import { authOptions } from '@/lib/auth';
import { Sidebar } from '@/components/organisms/Sidebar';
import { TopNav } from '@/components/organisms/TopNav';

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const session = await getServerSession(authOptions);

  if (!session) {
    redirect('/login');
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <div className="pl-64">
        <TopNav user={session.user} />
        <main className="p-8">
          {children}
        </main>
      </div>
    </div>
  );
}
```

**3. (marketing) - Public Routes**
```typescript
// apps/web/src/app/(marketing)/layout.tsx

import { Header } from '@/components/organisms/Header';
import { Footer } from '@/components/organisms/Footer';

export default function MarketingLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        {children}
      </main>
      <Footer />
    </div>
  );
}
```

### Dynamic Routes

**Forecast Detail Page:**
```typescript
// apps/web/src/app/(dashboard)/forecasts/[id]/page.tsx

import { notFound } from 'next/navigation';
import { ForecastsService } from '@/lib/api-client';
import { ForecastDetailView } from '@/components/features/ForecastDetailView';

interface PageProps {
  params: { id: string };
}

export default async function ForecastDetailPage({ params }: PageProps) {
  try {
    const forecast = await api.forecast.getWithExplanation.query({
      forecastId: params.id,
    });

    return <ForecastDetailView forecast={forecast} />;
  } catch (error) {
    notFound();
  }
}

export async function generateMetadata({ params }: PageProps) {
  const forecast = await api.forecast.getWithExplanation.query({
    forecastId: params.id,
  });

  return {
    title: `Forecast: ${forecast.forecast.menuItemName} | Flux`,
  };
}
```

## State Management

### OpenAPI Client + React Query

Primary state management through auto-generated OpenAPI TypeScript client and React Query:

**Generate Client from FastAPI:**
```bash
# From frontend directory - run after backend changes
npx openapi-typescript-codegen \
  --input http://localhost:8000/openapi.json \
  --output ./src/lib/api-client \
  --client axios

# This generates:
# - src/lib/api-client/services/ForecastsService.ts
# - src/lib/api-client/services/MenuItemsService.ts
# - src/lib/api-client/models/ForecastResponse.ts
# - etc.
```

**API Client Configuration:**
```typescript
// apps/web/src/lib/api-client/config.ts

import { OpenAPI } from './core/OpenAPI';

// Configure base URL and auth
OpenAPI.BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

OpenAPI.TOKEN = async () => {
  // Get JWT token from session/cookies
  if (typeof window !== 'undefined') {
    return localStorage.getItem('access_token') || '';
  }
  return '';
};

// Add request interceptor for auth headers
OpenAPI.HEADERS = async () => {
  const token = await OpenAPI.TOKEN();
  return {
    'Authorization': token ? `Bearer ${token}` : '',
    'Content-Type': 'application/json',
  };
};
```

**Provider Setup:**
```typescript
// apps/web/src/providers/query-provider.tsx

'use client';

import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
            retry: 1,
          },
          mutations: {
            retry: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

**Usage in Components:**
```typescript
// Example: Forecasts list component

'use client';

import { useQuery } from '@tanstack/react-query';
import { ForecastsService } from '@/lib/api-client';
import { ForecastCard } from '@/components/molecules/ForecastCard';
import { Spinner } from '@/components/atoms/Spinner';

export function ForecastsList() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['forecasts', { limit: 20 }],
    queryFn: () => ForecastsService.listForecasts({
      limit: 20,
      category: 'revenue'
    }),
  });

  if (isLoading) {
    return <Spinner />;
  }

  if (error) {
    return <div>Error loading forecasts: {error.message}</div>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {data?.items.map((forecast) => (
        <ForecastCard key={forecast.id} forecast={forecast} />
      ))}
    </div>
  );
}
```

**Mutations Example:**
```typescript
'use client';

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { MenuItemsService } from '@/lib/api-client';
import type { MenuItemCreateRequest } from '@/lib/api-client';

export function CreateMenuItem() {
  const queryClient = useQueryClient();

  const createMutation = useMutation({
    mutationFn: (data: MenuItemCreateRequest) =>
      MenuItemsService.createMenuItem({ data }),
    onSuccess: () => {
      // Invalidate and refetch menu items
      queryClient.invalidateQueries({ queryKey: ['menu-items'] });
    },
  });

  const handleSubmit = (formData: MenuItemCreateRequest) => {
    createMutation.mutate(formData);
  };

  return (
    <form onSubmit={(e) => {
      e.preventDefault();
      handleSubmit({
        name: 'Burger',
        category: 'entrees',
        price: 12.99
      });
    }}>
      {/* Form fields */}
      <button type="submit" disabled={createMutation.isPending}>
        {createMutation.isPending ? 'Creating...' : 'Create Item'}
      </button>
    </form>
  );
}
```

### Local State with Zustand

For complex UI state (e.g., multi-step forms, filters):

```typescript
// apps/web/src/stores/procurement-store.ts

import { create } from 'zustand';

interface ProcurementStore {
  selectedDate: Date;
  filters: {
    category?: string;
    confidence?: number;
  };
  setSelectedDate: (date: Date) => void;
  setFilters: (filters: Partial<ProcurementStore['filters']>) => void;
  clearFilters: () => void;
}

export const useProcurementStore = create<ProcurementStore>((set) => ({
  selectedDate: new Date(),
  filters: {},
  setSelectedDate: (date) => set({ selectedDate: date }),
  setFilters: (filters) =>
    set((state) => ({
      filters: { ...state.filters, ...filters },
    })),
  clearFilters: () => set({ filters: {} }),
}));
```

**Usage:**
```typescript
'use client';

import { useProcurementStore } from '@/stores/procurement-store';
import { DatePicker } from '@/components/atoms/DatePicker';

export function ProcurementFilters() {
  const { selectedDate, setSelectedDate, filters, setFilters } = useProcurementStore();

  return (
    <div className="flex gap-4">
      <DatePicker value={selectedDate} onChange={setSelectedDate} />

      <Select
        value={filters.category}
        onValueChange={(category) => setFilters({ category })}
      >
        <SelectOption value="produce">Produce</SelectOption>
        <SelectOption value="meat">Meat</SelectOption>
        <SelectOption value="dairy">Dairy</SelectOption>
      </Select>
    </div>
  );
}
```

## Authentication

### NextAuth.js Configuration

```typescript
// apps/web/src/lib/auth.ts

import { NextAuthOptions } from 'next-auth';
import CredentialsProvider from 'next-auth/providers/credentials';
import { prisma } from '@repo/database';
import bcrypt from 'bcryptjs';

export const authOptions: NextAuthOptions = {
  providers: [
    CredentialsProvider({
      name: 'credentials',
      credentials: {
        email: { label: 'Email', type: 'email' },
        password: { label: 'Password', type: 'password' },
      },
      async authorize(credentials) {
        if (!credentials?.email || !credentials?.password) {
          throw new Error('Invalid credentials');
        }

        const user = await prisma.user.findUnique({
          where: { email: credentials.email },
          include: {
            memberships: {
              where: { status: 'ACTIVE' },
              include: { restaurant: true },
            },
          },
        });

        if (!user || !user.passwordHash) {
          throw new Error('Invalid credentials');
        }

        const isPasswordValid = await bcrypt.compare(
          credentials.password,
          user.passwordHash
        );

        if (!isPasswordValid) {
          throw new Error('Invalid credentials');
        }

        return {
          id: user.id,
          email: user.email,
          name: `${user.firstName} ${user.lastName}`,
          restaurantId: user.memberships[0]?.restaurantId,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) {
        token.restaurantId = user.restaurantId;
      }
      return token;
    },
    async session({ session, token }) {
      if (session.user) {
        session.user.restaurantId = token.restaurantId as string;
      }
      return session;
    },
  },
  pages: {
    signIn: '/login',
    error: '/login',
  },
  session: {
    strategy: 'jwt',
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
};
```

### Protected Routes Hook

```typescript
// apps/web/src/hooks/use-restaurant.ts

'use client';

import { useSession } from 'next-auth/react';
import { redirect } from 'next/navigation';

export function useRestaurant() {
  const { data: session, status } = useSession();

  if (status === 'loading') {
    return { restaurantId: null, isLoading: true };
  }

  if (!session || !session.user.restaurantId) {
    redirect('/login');
  }

  return {
    restaurantId: session.user.restaurantId,
    isLoading: false,
  };
}
```

## Data Fetching Patterns

### Server Components (Default)

```typescript
// apps/web/src/app/(dashboard)/dashboard/page.tsx

import { ForecastsService } from '@/lib/api-client';
import { DashboardMetrics } from '@/components/organisms/DashboardMetrics';

export default async function DashboardPage() {
  // Parallel data fetching
  const [metrics, recentForecasts, dataHealth] = await Promise.all([
    api.restaurant.getMetrics.query(),
    api.forecast.list.query({ limit: 5 }),
    api.restaurant.getDataHealth.query(),
  ]);

  return (
    <div>
      <h1 className="text-3xl font-bold mb-8">Dashboard</h1>

      <DashboardMetrics metrics={metrics} />

      <div className="grid grid-cols-2 gap-8 mt-8">
        <RecentForecasts forecasts={recentForecasts} />
        <DataHealthWidget health={dataHealth} />
      </div>
    </div>
  );
}
```

### Client Components with React Query

```typescript
// apps/web/src/components/features/ForecastDetailView.tsx

'use client';

import { useQuery } from '@tanstack/react-query';
import { ForecastsService } from '@/lib/api-client';
import { ForecastChart } from '@/components/organisms/ForecastChart';
import { ExplanationPanel } from '@/components/organisms/ExplanationPanel';

interface Props {
  forecast: {
    id: string;
    menuItemName: string;
    predictedQuantity: number;
    confidence: number;
  };
}

export function ForecastDetailView({ forecast: initialForecast }: Props) {
  // Fetch fresh data with React Query (will use initial data from server)
  const { data: forecast } = api.forecast.getWithExplanation.useQuery(
    { forecastId: initialForecast.id },
    { initialData: initialForecast }
  );

  const submitFeedbackMutation = api.forecast.submitFeedback.useMutation({
    onSuccess: () => {
      // Invalidate and refetch
      utils.forecast.getWithExplanation.invalidate();
    },
  });

  const handleSubmitFeedback = (data: FeedbackData) => {
    submitFeedbackMutation.mutate({
      forecastId: forecast.id,
      ...data,
    });
  };

  return (
    <div className="grid grid-cols-3 gap-8">
      <div className="col-span-2">
        <ForecastChart forecast={forecast} />
      </div>

      <div>
        <ExplanationPanel
          explanation={forecast.explanation}
          onSubmitFeedback={handleSubmitFeedback}
        />
      </div>
    </div>
  );
}
```

### Optimistic Updates

```typescript
// Example: Approving a procurement recommendation

'use client';

import { useQuery } from '@tanstack/react-query';
import { ForecastsService } from '@/lib/api-client';

export function ProcurementRecommendationCard({ recommendation }) {
  const utils = api.useContext();

  const approveMutation = api.procurement.approve.useMutation({
    onMutate: async (newData) => {
      // Cancel outgoing refetches
      await utils.procurement.getRecommendations.cancel();

      // Snapshot previous value
      const previousData = utils.procurement.getRecommendations.getData();

      // Optimistically update
      utils.procurement.getRecommendations.setData(
        { date: recommendation.recommendedDate },
        (old) => ({
          ...old,
          items: old?.items.map((item) =>
            item.id === recommendation.id
              ? { ...item, status: 'APPROVED' }
              : item
          ),
        })
      );

      return { previousData };
    },
    onError: (err, newData, context) => {
      // Rollback on error
      utils.procurement.getRecommendations.setData(
        { date: recommendation.recommendedDate },
        context?.previousData
      );
    },
    onSettled: () => {
      // Always refetch after error or success
      utils.procurement.getRecommendations.invalidate();
    },
  });

  return (
    <Card>
      <Button onClick={() => approveMutation.mutate({ id: recommendation.id })}>
        Approve
      </Button>
    </Card>
  );
}
```

## UI Component Patterns

### Compound Components

```typescript
// apps/web/src/components/molecules/DataTable.tsx

interface DataTableProps<T> {
  data: T[];
  children: React.ReactNode;
}

interface DataTableHeaderProps {
  children: React.ReactNode;
}

interface DataTableRowProps<T> {
  item: T;
  children: (item: T) => React.ReactNode;
}

export function DataTable<T>({ data, children }: DataTableProps<T>) {
  return (
    <table className="min-w-full divide-y divide-gray-200">
      {children}
    </table>
  );
}

DataTable.Header = function Header({ children }: DataTableHeaderProps) {
  return (
    <thead className="bg-gray-50">
      <tr>{children}</tr>
    </thead>
  );
};

DataTable.Body = function Body<T>({ data, children }: { data: T[]; children: (item: T) => React.ReactNode }) {
  return (
    <tbody className="bg-white divide-y divide-gray-200">
      {data.map((item, index) => (
        <tr key={index}>{children(item)}</tr>
      ))}
    </tbody>
  );
};

DataTable.Column = function Column({ children }: { children: React.ReactNode }) {
  return (
    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
      {children}
    </th>
  );
};

DataTable.Cell = function Cell({ children }: { children: React.ReactNode }) {
  return <td className="px-6 py-4 whitespace-nowrap">{children}</td>;
};
```

**Usage:**
```typescript
<DataTable data={forecasts}>
  <DataTable.Header>
    <DataTable.Column>Menu Item</DataTable.Column>
    <DataTable.Column>Predicted Qty</DataTable.Column>
    <DataTable.Column>Confidence</DataTable.Column>
  </DataTable.Header>

  <DataTable.Body data={forecasts}>
    {(forecast) => (
      <>
        <DataTable.Cell>{forecast.menuItemName}</DataTable.Cell>
        <DataTable.Cell>{forecast.predictedQuantity}</DataTable.Cell>
        <DataTable.Cell>
          <ConfidenceBadge value={forecast.confidence} />
        </DataTable.Cell>
      </>
    )}
  </DataTable.Body>
</DataTable>
```

### Render Props

```typescript
// apps/web/src/components/organisms/ForecastChart.tsx

interface ForecastChartProps {
  menuItemId: string;
  children?: (data: ChartData) => React.ReactNode;
}

export function ForecastChart({ menuItemId, children }: ForecastChartProps) {
  const { data, isLoading } = api.forecast.list.useQuery({ menuItemId });

  if (isLoading) return <Spinner />;

  const chartData = transformToChartData(data);

  if (children) {
    return <>{children(chartData)}</>;
  }

  return <DefaultChart data={chartData} />;
}
```

## Performance Optimizations

### Code Splitting

```typescript
// Dynamic imports for heavy components

import dynamic from 'next/dynamic';

const ForecastChart = dynamic(
  () => import('@/components/organisms/ForecastChart'),
  {
    loading: () => <ChartSkeleton />,
    ssr: false, // Disable SSR for chart (client-side only)
  }
);

const ExplanationPanel = dynamic(
  () => import('@/components/organisms/ExplanationPanel'),
  {
    loading: () => <PanelSkeleton />,
  }
);
```

### Image Optimization

```typescript
import Image from 'next/image';

<Image
  src="/dashboard-preview.png"
  alt="Dashboard Preview"
  width={1200}
  height={800}
  priority // Above fold
  placeholder="blur"
  blurDataURL="data:image/png;base64,..."
/>
```

### Memo and useMemo

```typescript
'use client';

import { memo, useMemo } from 'react';

interface ForecastCardProps {
  forecast: Forecast;
  onSelect: (id: string) => void;
}

export const ForecastCard = memo(function ForecastCard({
  forecast,
  onSelect,
}: ForecastCardProps) {
  const accuracy = useMemo(() => {
    if (!forecast.actualQuantity) return null;
    return calculateAccuracy(forecast.predictedQuantity, forecast.actualQuantity);
  }, [forecast.predictedQuantity, forecast.actualQuantity]);

  return (
    <Card onClick={() => onSelect(forecast.id)}>
      <h3>{forecast.menuItemName}</h3>
      <p>Predicted: {forecast.predictedQuantity}</p>
      {accuracy && <AccuracyBadge value={accuracy} />}
    </Card>
  );
});
```

## Error Handling

### Error Boundaries

```typescript
// apps/web/src/components/ErrorBoundary.tsx

'use client';

import { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  render() {
    if (this.state.hasError) {
      return (
        this.props.fallback || (
          <div className="p-8 text-center">
            <h2 className="text-xl font-bold text-red-600">Something went wrong</h2>
            <p className="mt-2 text-gray-600">{this.state.error?.message}</p>
            <button
              onClick={() => this.setState({ hasError: false })}
              className="mt-4 px-4 py-2 bg-blue-600 text-white rounded"
            >
              Try again
            </button>
          </div>
        )
      );
    }

    return this.props.children;
  }
}
```

### API Error Handling

```typescript
'use client';

import { useQuery } from '@tanstack/react-query';
import { ForecastsService, ApiError } from '@/lib/api-client';

export function ForecastsList() {
  const { data, error, isError } = useQuery({
    queryKey: ['forecasts'],
    queryFn: () => ForecastsService.listForecasts({}),
  });

  if (isError) {
    if (error instanceof ApiError) {
      // Handle HTTP error responses from FastAPI
      if (error.status === 401) {
        return <div>Please log in to view forecasts</div>;
      }

      if (error.status === 403) {
        return <div>You don't have permission to view forecasts</div>;
      }
    }

    return <div>Error loading forecasts: {error.message}</div>;
  }

  return <ForecastsGrid forecasts={data?.items} />;
}
```

## Accessibility

### Semantic HTML

```typescript
export function ForecastCard({ forecast }: { forecast: Forecast }) {
  return (
    <article
      className="p-6 bg-white rounded-lg shadow"
      aria-labelledby={`forecast-${forecast.id}`}
    >
      <h3 id={`forecast-${forecast.id}`} className="text-lg font-semibold">
        {forecast.menuItemName}
      </h3>

      <dl className="mt-4 space-y-2">
        <div>
          <dt className="text-sm text-gray-500">Predicted Quantity</dt>
          <dd className="text-2xl font-bold">{forecast.predictedQuantity}</dd>
        </div>

        <div>
          <dt className="text-sm text-gray-500">Confidence</dt>
          <dd>
            <meter
              value={forecast.confidence}
              min={0}
              max={1}
              optimum={0.9}
              aria-label="Forecast confidence"
            >
              {Math.round(forecast.confidence * 100)}%
            </meter>
          </dd>
        </div>
      </dl>
    </article>
  );
}
```

### Keyboard Navigation

```typescript
'use client';

import { useEffect, useRef } from 'react';

export function Modal({ isOpen, onClose, children }) {
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (isOpen) {
      closeButtonRef.current?.focus();
    }

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg p-6 max-w-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          ref={closeButtonRef}
          onClick={onClose}
          aria-label="Close modal"
          className="ml-auto block"
        >
          ×
        </button>
        {children}
      </div>
    </div>
  );
}
```

---

# Backend Architecture

This section details the backend architecture including Lambda functions, service layer patterns, database access, background workers, and ML integration.


---

**Previous:** [← Database Schema](./07-database-schema.md)
**Next:** [Backend Architecture →](./09-backend-architecture.md)
