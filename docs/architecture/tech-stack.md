# Tech Stack

> **Part of:** [Flux Architecture Documentation](./README.md)
> **Updated:** Python-first backend with FastAPI

---

## Technology Stack

This is the **DEFINITIVE** technology selection for the entire project. All development must use these exact versions.

| Category | Technology | Version | Purpose | Rationale |
|----------|-----------|---------|---------|-----------|
| Frontend Language | TypeScript | 5.3+ | Type-safe frontend development | Strong typing for UI, catches errors at compile time |
| Frontend Framework | Next.js | 15+ (App Router) | React meta-framework with SSR | Server Components reduce bundle 60-80%, Vercel deployment optimized |
| UI Component Library | shadcn/ui + Radix UI | Latest | Accessible component primitives | Unstyled primitives + Tailwind = full customization, WCAG AA accessible |
| State Management | TanStack Query + Zustand | Query v5, Zustand v4 | Server state + client state | React Query handles API caching, Zustand for UI state (lightweight vs Redux) |
| **Backend Language** | **Python** | **3.12+** | **Backend API development** | **Unified language with ML pipeline, async support, strong ecosystem** |
| **Backend Framework** | **FastAPI** | **0.109+** | **Modern async API framework** | **Auto OpenAPI docs, Pydantic validation, async/await, high performance** |
| **API Style** | **REST + OpenAPI** | **OpenAPI 3.1** | **HTTP REST API with schema** | **Auto-generated client, standard REST patterns, FastAPI native** |
| **Database** | **PostgreSQL (RDS)** | **16+ with TimescaleDB** | **Relational + time-series** | **ACID transactions, TimescaleDB 10-100x faster for forecasts, mature RLS** |
| **ORM** | **SQLAlchemy** | **2.0+** | **Python ORM with async support** | **Industry standard, async/await, migration support via Alembic, type hints** |
| Cache | Redis (ElastiCache) | 7.x | Session storage & API caching | Sub-millisecond latency, 15-min aggregations cached, rate limiting state |
| File Storage | AWS S3 | N/A | ML models, exports, backups | $0.023/GB/month, 99.999999999% durability, lifecycle policies for archival |
| Authentication | **FastAPI OAuth2 + JWT** | **Latest** | **JWT authentication** | **Built-in FastAPI support, OAuth2 flows, JWT tokens** |
| Frontend Testing | Vitest + Testing Library | Latest | Unit/integration tests | 10x faster than Jest, ESM native, same API as Jest |
| **Backend Testing** | **pytest + httpx** | **Latest** | **API/service tests** | **Python standard, async support, FastAPI test client** |
| E2E Testing | Playwright | Latest | Critical user journeys | Cross-browser, auto-wait, screenshot/video recording, parallel execution |
| Build Tool | Turborepo | 2.x | Monorepo orchestration | Remote caching 10x faster builds, task pipelines, incremental builds |
| Bundler | Next.js (Turbopack) | Built-in | Frontend bundling | 700x faster than Webpack, native to Next.js 15 |
| **IaC Tool** | **Terraform** | **1.7+** | **Infrastructure as Code** | **Industry standard, mature, multi-cloud, excellent AWS support** |
| CI/CD | GitHub Actions | N/A | Continuous integration | Free for public repos, native GitHub integration, matrix builds |
| Monitoring | Datadog | N/A | APM + logs + metrics | Unified observability, Lambda auto-instrumentation, AI-powered alerting |
| **Logging** | **structlog** | **Latest** | **Structured JSON logging** | **Python structured logging, fast, JSON native, context binding** |
| CSS Framework | Tailwind CSS | 4.x | Utility-first styling | Rapid development, purges unused CSS, works with Server Components |
| **ML Framework** | **scikit-learn + Prophet + XGBoost** | **Latest** | **Time-series forecasting** | **Prophet for seasonal, XGBoost for advanced, scikit-learn for pipelines** |
| ML Platform | AWS SageMaker | N/A | Model training & serving | Spot instances (70% savings), managed infrastructure, auto-scaling |
| Data Pipeline | Kinesis + Glue | N/A | Stream processing + ETL | Kinesis for real-time, Glue for batch transformations to Parquet |
| **Validation** | **Pydantic** | **2.5+** | **Runtime type validation** | **FastAPI native, type hints, JSON schema generation, performance** |
| Date/Time | **pendulum** | **3.x** | **Date manipulation** | **Python timezone library, better than datetime, Laravel-inspired API** |
| Charts | Recharts | 2.x | Data visualization | React-first, composable, handles time-series forecasts |
| Forms | React Hook Form | 7.x | Form state management | Minimal re-renders, Zod integration, better perf than Formik |
| **Task Queue** | **Celery + Redis** | **5.3+** | **Background job processing** | **Python standard, distributed tasks, SQS backend support** |
| **DB Migrations** | **Alembic** | **1.13+** | **Database schema migrations** | **SQLAlchemy migrations, version control, auto-generation** |
| **HTTP Client** | **httpx** | **0.26+** | **Async HTTP client** | **Async/sync support, HTTP/2, replaces requests, test client** |

---

## Platform & Infrastructure

**Platform:** AWS

**Key Services:**
- Lambda (compute) - Python 3.12 runtime
- API Gateway (HTTP API) - REST endpoints
- RDS PostgreSQL with TimescaleDB (database)
- SageMaker (ML training/inference)
- Kinesis Data Streams (real-time data ingestion)
- S3 (object storage)
- ElastiCache Redis (caching + Celery broker)
- CloudFront (CDN)
- SQS (message queues for Celery)
- EventBridge (scheduled jobs)

**Deployment Regions:**
- Primary: eu-west-1 (Ireland) - for EU customers (GDPR compliance)
- Secondary: us-east-1 (N. Virginia) - for US customers
- Frontend CDN: CloudFront (global)

---

## Key Integration Points

- **Frontend ↔ Backend**: REST API with OpenAPI schema, auto-generated TypeScript client
- **Backend ↔ POS Systems**: Adapter pattern with provider-specific implementations (Toast, Square, Lightspeed, Clover, Revel)
- **Backend ↔ ML Services**: Celery tasks trigger SageMaker training; Lambda functions serve predictions
- **Data Flow**: POS → Kinesis → Lambda → PostgreSQL/TimescaleDB → ML Pipeline → Predictions → Frontend

---

## Architectural Patterns

- **Serverless Architecture**: Lambda functions for API and background jobs (Python runtime)
- **Multi-Tenant with Row-Level Security (RLS)**: Shared PostgreSQL with RLS policies
- **Adapter Pattern**: POS integrations with provider-specific implementations
- **API Gateway Pattern**: Single entry point for auth, rate limiting, CORS, logging
- **Event-Driven Architecture**: Kinesis + EventBridge + SQS/Celery for async processing
- **CQRS Light**: Read replicas for analytics, primary for writes
- **Repository Pattern**: Data access through SQLAlchemy ORM
- **Micro-Frontend with Server Components**: Next.js 15 Server/Client component split
- **Feature Flag Pattern**: Environment-based feature flags
- **Circuit Breaker Pattern**: Automatic fallback for POS API failures (using tenacity library)

---

## Python Package Management

**Package Manager:** uv

**Rationale:** `uv` is an extremely fast Python package installer and resolver, written in Rust. It is a drop-in replacement for `pip` and `pip-tools` workflows and is significantly faster than both `pip` and `Poetry`.

**Example `pyproject.toml`:**
```toml
[project]
name = "flux-api"
version = "0.1.0"
dependencies = [
    "fastapi>=0.109.0",
    "uvicorn[standard]>=0.27.0",
    "sqlalchemy>=2.0.25",
    "alembic>=1.13.0",
    "pydantic>=2.5.0",
    "python-jose[cryptography]>=3.3.0",
    "passlib[bcrypt]>=1.7.4",
]

[project.optional-dependencies]
dev = [
    "pytest",
    "pytest-asyncio",
    "httpx",
]
```

---

## Frontend-Backend Communication

### OpenAPI Schema Generation

FastAPI automatically generates OpenAPI 3.1 schema:

**Backend (FastAPI):**
```python
# Automatic OpenAPI schema at /docs
@app.get("/forecasts", response_model=List[ForecastResponse])
async def list_forecasts(
    limit: int = 20,
    current_user: User = Depends(get_current_user)
):
    return await forecast_service.list(current_user.restaurant_id, limit)
```

**Frontend (Auto-generated TypeScript client):**
```typescript
// Generated using openapi-typescript-codegen or similar
import { ForecastsService } from '@/lib/api-client';

const forecasts = await ForecastsService.listForecasts({ limit: 20 });
```

---

## Development Tools

| Tool | Purpose |
|------|---------|
| **Black** | Python code formatter (opinionated) |
| **Ruff** | Fast Python linter (replaces flake8, isort, etc.) |
| **mypy** | Static type checker for Python |
| **pytest** | Testing framework |
| **pytest-asyncio** | Async test support |
| **pytest-cov** | Coverage reporting |
| **Faker** | Test data generation |
| **factory-boy** | Test fixtures |

---

## Why This Stack?

### Python Backend Benefits

1. **Unified Language**: Backend + ML + Infrastructure all in Python
2. **ML Integration**: Native integration with SageMaker, scikit-learn, pandas
3. **Async Support**: FastAPI/SQLAlchemy 2.0 both support async/await
4. **Type Safety**: Python 3.12+ type hints + Pydantic validation
5. **Performance**: FastAPI is one of the fastest Python frameworks (comparable to Node.js)
6. **Auto Documentation**: OpenAPI docs generated automatically
7. **Ecosystem**: Massive Python ecosystem for data processing, ML, APIs

### Trade-offs vs TypeScript Backend

**Lost:**
- ❌ End-to-end type safety (TypeScript frontend ↔ TypeScript backend)
- ❌ Shared types between frontend/backend without codegen

**Gained:**
- ✅ Python everywhere (simpler team, ML engineers can contribute to backend)
- ✅ Better ML integration (same language)
- ✅ More concise code (Python vs TypeScript)
- ✅ Stronger data science ecosystem

### Mitigation Strategy

**Use OpenAPI Code Generation** for type-safe frontend-backend communication:
```bash
# Generate TypeScript client from FastAPI OpenAPI schema
npx openapi-typescript-codegen --input http://localhost:8000/openapi.json --output ./src/lib/api-client
```

This gives you:
- ✅ Type-safe API calls in frontend
- ✅ Auto-completion in TypeScript
- ✅ Compile-time errors if API changes
- ✅ Single source of truth (FastAPI models)

---

**Related:**
- [Coding Standards →](./coding-standards.md)
- [Source Tree →](./source-tree.md)