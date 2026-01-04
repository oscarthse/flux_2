# Source Tree Structure

> **Part of:** [Flux Architecture Documentation](./README.md)
> **Updated:** Python-first backend with FastAPI + Terraform

---

## Repository Structure

**Structure:** Monorepo
**Monorepo Tool:** Turborepo
**Package Organization:** Workspaces pattern for frontend, Python apps use `uv`.

```
flux/
├── apps/
│   ├── web/                    # Next.js 15 frontend (TypeScript)
│   └── api/                    # FastAPI backend (Python)
├── packages/
│   ├── ui/                     # Shared React components (TypeScript)
│   └── config/                 # Shared configs (ESLint, Tailwind)
├── infrastructure/             # Terraform (HCL)
├── docs/
├── turbo.json
└── package.json
```

**Rationale:** A Monorepo managed with Turborepo for frontend development enables code reuse and atomic changes. The Python backend (`apps/api/`) is managed with `uv`. This structure uses Turborepo for frontend efficiencies while allowing Python's standard tooling to manage the backend.

---

## Frontend Structure (apps/web/)

```
apps/web/
├── src/
│   ├── app/                      # Next.js 15 App Router
│   │   ├── (auth)/              # Auth route group (login, register)
│   │   ├── (dashboard)/         # Protected route group
│   │   │   └── layout.tsx       # Dashboard layout with sidebar
│   │   ├── (marketing)/         # Public route group (landing page, etc.)
│   │   └── layout.tsx           # Root layout
│   ├── components/              # React components (Atomic Design)
│   ├── lib/
│   │   ├── api-client/          # Generated TypeScript API client from OpenAPI
│   │   └── hooks/               # Custom React hooks
│   └── providers/               # Context providers (e.g., TanStack Query)
└── package.json
```

---

## Backend Structure (apps/api/)

```
apps/api/
├── src/
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Settings (Pydantic BaseSettings)
│   ├── dependencies.py              # FastAPI dependencies (auth, db session)
│   ├── routers/                     # API route handlers (endpoints)
│   │   ├── auth.py
│   │   └── forecasts.py
│   ├── services/                    # Business logic layer
│   │   ├── forecast_service.py
│   │   └── pos_sync_service.py
│   ├── adapters/                    # External service integrations
│   │   ├── pos/
│   │   └── ml/
│   ├── models/                      # SQLAlchemy ORM models
│   │   └── forecast.py
│   ├── schemas/                     # Pydantic schemas (API models)
│   │   └── forecast.py
│   ├── db/                          # Database utilities
│   │   └── session.py
│   └── core/                        # Core utilities (security, logging)
├── alembic/                         # Database migrations
│   └── versions/
├── tests/
└── pyproject.toml                   # Project metadata and dependencies for uv
```

### Backend Layer Responsibilities

- **main.py**: FastAPI app initialization, middleware, and router registration.
- **routers/**: Defines API path operations (e.g., `@router.get("/forecasts")`). Handles request/response and calls services.
- **services/**: Contains the core business logic, orchestrating data access and external calls.
- **models/**: Defines the database tables using SQLAlchemy ORM.
- **schemas/**: Defines the shape of API data using Pydantic for validation and serialization.
- **adapters/**: Isolates external API clients (e.g., for POS systems or SageMaker).
- **db/**: Manages the database session and connection pooling.
- **alembic/**: Handles database schema migrations.

---

## Infrastructure (Terraform)

```
infrastructure/
├── environments/
│   ├── dev/
│   │   ├── main.tf
│   │   └── terraform.tfvars
│   └── prod/
│       ├── main.tf
│       └── terraform.tfvars
├── modules/
│   ├── network/                 # VPC, subnets, NAT gateway
│   ├── database/                # RDS PostgreSQL, ElastiCache
│   ├── compute/                 # Lambda functions, API Gateway
│   └── storage/                 # S3 buckets
├── backend.tf                   # Terraform state backend (S3)
└── providers.tf                 # AWS provider configuration
```

---

**Related:**
- [Tech Stack →](./tech-stack.md)
- [Coding Standards →](./coding-standards.md)