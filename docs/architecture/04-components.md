# Components

> **Part of:** [Flux Architecture Documentation](./README.md)

---

## Frontend Component Architecture

### Component Organization Strategy

**Atomic Design Pattern** with feature-based organization:

```
apps/web/src/
├── components/
│   ├── atoms/           # Basic building blocks (Button, Input)
│   ├── molecules/       # Compound components (MetricCard, DataTable)
│   ├── organisms/       # Complex sections (ForecastChart, Sidebar)
│   └── templates/       # Page layouts (DashboardLayout)
├── features/            # Feature-specific components, hooks, and logic
│   ├── auth/
│   ├── dashboard/
│   └── forecasting/
└── lib/                 # Shared utilities, API client
```

---

### Atoms (Basic UI Components)

**Purpose:** Smallest reusable UI elements with no business logic, styled with `class-variance-authority`.

```typescript
// apps/web/src/components/atoms/Button.tsx
import { forwardRef } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
// ... (implementation remains the same)
```

```typescript
// apps/web/src/components/atoms/Input.tsx
import { forwardRef } from 'react';
// ... (implementation remains the same)
```

**Other Atoms:** Badge, Avatar, Icon, LoadingSpinner, Tooltip, Card.

---

### Molecules (Compound Components)

**Purpose:** Combinations of atoms that form functional UI patterns.

```typescript
// apps/web/src/components/molecules/MetricCard.tsx
import { Card } from '@/components/atoms/Card';
import { TrendingUp, TrendingDown } from 'lucide-react';
// ... (implementation remains the same, it is UI-only)
```

```typescript
// apps/web/src/components/molecules/DataTable.tsx
import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';
// ... (implementation remains the same, it is UI-only)
```

---

### Organisms (Complex Sections)

**Purpose:** Major UI sections combining molecules and atoms, often with data-fetching logic.

```typescript
// apps/web/src/components/organisms/ForecastChart.tsx
import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';
import { Card } from '@/components/atoms/Card';
import { Badge } from '@/components/atoms/Badge';
import { apiClient } from '@/lib/api-client'; // Using the generated OpenAPI client

export interface ForecastChartProps {
  menuItemId: string;
  startDate: Date;
  endDate: Date;
}

export function ForecastChart({ menuItemId, startDate, endDate }: ForecastChartProps) {
  const { data: forecasts, isLoading: forecastsLoading } = useQuery({
    queryKey: ['forecasts', menuItemId, startDate, endDate],
    queryFn: () => apiClient.forecasts.listForecasts({ 
      menuItemId, 
      startDate: startDate.toISOString(), 
      endDate: endDate.toISOString(),
      limit: 100 
    }),
  });

  const { data: actuals, isLoading: actualsLoading } = useQuery({
    queryKey: ['dailySales', menuItemId, startDate, endDate],
    queryFn: () => apiClient.transactions.getDailySales({
        menuItemId,
        startDate: startDate.toISOString(),
        endDate: endDate.toISOString(),
    }),
  });

  const chartData = useMemo(() => {
    if (!forecasts || !actuals) return [];

    const dataMap = new Map<string, any>();

    forecasts.forEach(forecast => {
      const date = forecast.forecast_date.split('T')[0];
      dataMap.set(date, {
        date,
        forecast: forecast.predicted_quantity,
        lowerBound: forecast.confidence_lower,
        upperBound: forecast.confidence_upper,
      });
    });

    actuals.forEach(actual => {
      const existing = dataMap.get(actual.date) || { date: actual.date };
      dataMap.set(actual.date, {
        ...existing,
        actual: actual.total_quantity,
      });
    });

    return Array.from(dataMap.values()).sort((a, b) => a.date.localeCompare(b.date));
  }, [forecasts, actuals]);

  if (forecastsLoading || actualsLoading) {
    return (
      <Card className="p-6">
        <div className="h-80 flex items-center justify-center">
          <p className="text-gray-500">Loading forecast data...</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h3 className="text-lg font-semibold text-gray-900">Forecast vs Actual</h3>
        <div className="flex gap-2">
          <Badge variant="outline">
            <span className="inline-block w-3 h-3 bg-blue-500 rounded-full mr-2" />
            Forecast
          </Badge>
          <Badge variant="outline">
            <span className="inline-block w-3 h-3 bg-green-500 rounded-full mr-2" />
            Actual
          </Badge>
        </div>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" />
          <XAxis
            dataKey="date"
            tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
          />
          <YAxis />
          <Tooltip
            labelFormatter={(value) => new Date(value).toLocaleDateString()}
            formatter={(value: number) => [Math.round(value), '']}
          />
          <Legend />
          <Line type="monotone" dataKey="forecast" stroke="#3b82f6" strokeWidth={2} name="Forecast" />
          <Line type="monotone" dataKey="actual" stroke="#10b981" strokeWidth={2} name="Actual Sales" />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
```

```typescript
// apps/web/src/components/organisms/ProcurementRecommendations.tsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card } from '@/components/atoms/Card';
import { Button } from '@/components/atoms/Button';
import { DataTable } from '@/components/molecules/DataTable';
import { apiClient } from '@/lib/api-client'; // Using the generated OpenAPI client
import { ShoppingCart, AlertCircle } from 'lucide-react';

export function ProcurementRecommendations({ startDate, endDate, onCreateOrder }) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: ['procurementRecommendations', startDate, endDate],
    queryFn: () => apiClient.procurement.getRecommendations({
        startDate: startDate.toISOString(),
        endDate: endDate.toISOString(),
    }),
  });
  
  // ... (component logic and rendering remains the same)
}
```

---

### Templates (Page Layouts)

**Purpose:** Complete page structures with slots for organisms and molecules.

```typescript
// apps/web/src/components/templates/DashboardLayout.tsx
import { ReactNode } from 'react';
import { Sidebar } from '@/components/organisms/Sidebar';
import { Header } from '@/components/organisms/Header';
// ... (implementation remains the same)
```

---

## Backend Component Architecture

### Lambda Function Organization

**Purpose:** Serverless functions organized by domain with shared layers.

```
apps/api/
├── src/
│   ├── handlers/          # Lambda entry points (e.g., for Mangum)
│   ├── routers/           # FastAPI routers
│   ├── services/          # Business logic layer
│   ├── models/            # SQLAlchemy ORM models
│   ├── schemas/           # Pydantic data schemas
│   ├── adapters/          # External service integrations
│   └── core/              # Core utilities (db session, security)
├── tests/
├── alembic/               # Database migrations
└── pyproject.toml         # Dependencies (Poetry)
```

---

### Lambda Handlers

**Purpose:** Thin handlers that delegate to the main FastAPI application or a specific task.

**Main API Handler (Mangum Adapter):**
```python
# apps/api/src/handlers/api_handler.py
from mangum import Mangum
from src.main import app

# Mangum wraps the FastAPI app to make it compatible with AWS Lambda and API Gateway
handler = Mangum(app, lifespan="off")
```

**SQS-Triggered Handler (Celery Worker):**
```python
# apps/api/src/handlers/celery_handler.py
import json
from src.tasks import celery_app

def handler(event, context):
    """
    This handler processes tasks from an SQS queue via Celery.
    The event payload is passed to the corresponding Celery task.
    """
    for record in event["Records"]:
        task_body = json.loads(record["body"])
        celery_app.send_task(task_body['task'], args=[task_body['payload']])
```

---

### Service Layer

**Purpose:** Encapsulates business logic and orchestrates operations between the database and external services.

```python
# apps/api/src/services/forecast_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Forecast
from src.schemas import ForecastCreate
from src.adapters.ml_adapter import MLAdapter

class ForecastService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.ml_adapter = MLAdapter()

    async def create_forecast(self, data: ForecastCreate, restaurant_id: str) -> Forecast:
        # 1. Fetch features for the model
        features = await self._get_features_for_model(restaurant_id, data.menu_item_id)
        
        # 2. Get a prediction from the machine learning model via an adapter
        prediction = await self.ml_adapter.predict(features)

        # 3. Store the new forecast in the database
        new_forecast = Forecast(
            restaurant_id=restaurant_id,
            predicted_quantity=prediction['quantity'],
            **data.dict()
        )
        self.db.add(new_forecast)
        await self.db.commit()
        await self.db.refresh(new_forecast)
        
        return new_forecast
```

---

### Adapter Pattern (External APIs)

**Purpose:** Provides a unified interface for different external services (e.g., POS providers, ML models).

```python
# apps/api/src/adapters/pos/base.py
from abc import ABC, abstractmethod

class BasePOSAdapter(ABC):
    @abstractmethod
    async def fetch_orders(self, start_date, end_date):
        pass

# apps/api/src/adapters/pos/square.py
from square.client import Client
from .base import BasePOSAdapter

class SquareAdapter(BasePOSAdapter):
    def __init__(self, access_token: str):
        self.client = Client(access_token=access_token, environment='production')

    async def fetch_orders(self, start_date, end_date):
        # ... logic to fetch and normalize orders from Square API
        pass
```