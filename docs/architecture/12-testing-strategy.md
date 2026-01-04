# Testing Strategy

> **Part of:** [Flux Architecture Documentation](./README.md)
> **Updated:** pytest for Python backend, Vitest for TypeScript frontend

---

### 10.1 Test Pyramid Overview

```
                    ┌─────────────┐
                    │   E2E (5%)  │  - Full user journeys
                    │             │  - Playwright
                    └─────────────┘
                  ┌───────────────────┐
                  │ Integration (20%) │  - API endpoints
                  │                   │  - Database queries
                  │                   │  - External API mocks
                  └───────────────────┘
              ┌─────────────────────────────┐
              │      Unit Tests (75%)       │  - Pure functions
              │                             │  - Business logic
              │                             │  - Components
              └─────────────────────────────┘
```

**Test Coverage Targets:**
- Overall: ≥85%
- Critical paths (auth, forecasting, POS sync): ≥95%
- UI components: ≥80%
- Business logic services: ≥90%

### 10.2 Unit Testing

**Backend Framework:** pytest (Python)
**Frontend Framework:** Vitest (TypeScript)

**Example: Backend Unit Test (Python)**
```python
# apps/api/tests/services/test_item_matcher.py
import pytest
from src.services.pos.item_matcher import ItemMatcher

def test_exact_match_returns_100_percent_confidence():
    matcher = ItemMatcher()
    result = matcher.fuzzy_match('Grilled Chicken Sandwich', 'Grilled Chicken Sandwich')
    assert result.confidence == 1.0
    assert result.is_match is True

def test_similar_names_high_confidence():
    matcher = ItemMatcher()
    result = matcher.fuzzy_match('Grilled Chicken Sandwich', 'Grilled Chkn Sandwich')
    assert result.confidence > 0.85
    assert result.is_match is True
```

**Example: Frontend Unit Test (TypeScript)**
```typescript
// apps/web/src/components/molecules/__tests__/MetricCard.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetricCard } from '../MetricCard';

describe('MetricCard', () => {
  it('should render the title and value correctly', () => {
    render(<MetricCard title="Revenue" value="$1,234" />);
    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('$1,234')).toBeInTheDocument();
  });

  it('should show a positive percentage change', () => {
    render(<MetricCard title="Revenue" value="$1,234" change={5.2} />);
    const changeEl = screen.getByText('+5.2%');
    expect(changeEl).toBeInTheDocument();
    expect(changeEl).toHaveClass('text-green-600');
  });
});
```

### 10.3 Integration Testing

**Framework:** pytest + httpx + Testcontainers (for PostgreSQL)

**Example: API Integration Test (FastAPI Router)**
```python
# apps/api/tests/routers/test_forecasts_integration.py
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from testcontainers.postgres import PostgresContainer

from src.main import app
from src.models import Base
# ... other model imports

# Setup test database container
@pytest.fixture(scope="module")
def postgres_container():
    with PostgresContainer("postgres:15-alpine") as postgres:
        yield postgres

@pytest.fixture(scope="module")
async def db_engine(postgres_container):
    db_url = postgres_container.get_connection_url().replace("psycopg2", "asyncpg")
    engine = create_async_engine(db_url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()

@pytest.fixture
async def authenticated_client(db_session):
    # Mock dependencies for auth and db
    # ...
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.mark.asyncio
async def test_list_forecasts(authenticated_client, db_session):
    # Arrange: create test data in db_session
    # ...

    # Act
    response = await authenticated_client.get("/forecasts/")

    # Assert
    assert response.status_code == 200
    assert len(response.json()) > 0
```

### 10.4 End-to-End (E2E) Testing

**Framework:** Playwright

**Example: User Registration Flow**
```typescript
// tests/e2e/auth.spec.ts
import { test, expect } from '@playwright/test';

test('should allow a new user to register', async ({ page }) => {
  await page.goto('/register');
  
  await page.fill('input[name="email"]', 'test@example.com');
  await page.fill('input[name="password"]', 'Password123!');
  await page.fill('input[name="restaurantName"]', 'The Test Kitchen');
  await page.click('button[type="submit"]');

  await expect(page).toHaveURL('/dashboard');
  await expect(page.locator('h1')).toContainText('Welcome, The Test Kitchen');
});
```

### 10.5 Load & Performance Testing

**Framework:** k6

**Example: API Load Test**
```javascript
// tests/load/forecast_api.k6.js
import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '1m', target: 50 },
    { duration: '3m', target: 50 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    'http_req_duration': ['p(95)<500'], // 95% of requests must be under 500ms
  },
};

export default function () {
  const headers = { 'Authorization': `Bearer ${__ENV.AUTH_TOKEN}` };
  const res = http.get(`${__ENV.API_URL}/forecasts/`, { headers });
  check(res, { 'status is 200': (r) => r.status === 200 });
  sleep(1);
}
```

### 10.6 Test Data Management

**Factory Pattern for Test Data (Python)**
```python
# tests/factories.py
import factory
from faker import Faker
from src.models import Restaurant, User

fake = Faker()

class RestaurantFactory(factory.alchemy.SQLAlchemyModelFactory):
    class Meta:
        model = Restaurant
        sqlalchemy_session_persistence = "commit"

    id = factory.LazyFunction(uuid.uuid4)
    name = factory.LazyFunction(fake.company)
```

### 10.7 CI/CD Test Integration

**GitHub Actions Workflow**
```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  backend-tests:
    name: Backend Tests (Python)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.12'
      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh
      - run: uv pip install -r apps/api/requirements.txt
        working-directory: ./
      - run: uv run pytest
        working-directory: ./apps/api

  frontend-tests:
    name: Frontend Tests (TypeScript)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'
      - run: npm ci
      - run: npm run test:unit --workspace=apps/web
```

### 10.8 Test Coverage Reporting

**Tooling:** Codecov

**Codecov Configuration**
```yaml
# codecov.yml
coverage:
  status:
    project:
      default:
        target: 85%
        threshold: 2%
    patch:
      default:
        target: 90%
```

---
---

**Previous:** [← Security & Compliance](./11-security-compliance.md)
