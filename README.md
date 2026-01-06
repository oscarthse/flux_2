# Flux - Restaurant Intelligence Platform

Flux is an AI-powered restaurant management platform that helps restaurants reduce food waste, optimize labor scheduling, and improve profitability through advanced demand forecasting and recipe intelligence.

## Table of Contents

- [Architecture Overview](#architecture-overview)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Database Schema](#database-schema)
- [Mathematical Models](#mathematical-models)
- [API Reference](#api-reference)
- [Development Workflow](#development-workflow)
- [Test Credentials](#test-credentials)

---

## Architecture Overview

Flux is a monorepo containing:
- **Backend API** (Python/FastAPI) - RESTful API with ML forecasting engine
- **Frontend Web App** (Next.js 15 + React) - Dashboard for restaurant operators
- **PostgreSQL Database** (TimescaleDB) - Time-series optimized data storage
- **Redis** (Optional) - Token blacklist and caching

```
flux/
├── apps/
│   ├── api/              # FastAPI backend
│   │   ├── src/
│   │   │   ├── routers/  # API endpoints
│   │   │   ├── models/   # SQLAlchemy ORM models
│   │   │   ├── services/ # Business logic & ML models
│   │   │   └── core/     # Auth, security, config
│   │   ├── alembic/      # Database migrations
│   │   └── scripts/      # Seed data, utilities
│   └── web/              # Next.js frontend
│       ├── src/
│       │   ├── app/      # App Router pages
│       │   ├── features/ # Feature modules
│       │   └── lib/      # Utilities & API client
├── docs/                 # Architecture, PRD, stories
├── infrastructure/       # Terraform IaC (AWS deployment)
└── docker-compose.yml    # Local development stack
```

---

## Tech Stack

### Backend
- **Runtime**: Python 3.13
- **Framework**: FastAPI 0.112+ with async/await
- **ORM**: SQLAlchemy 2.0 (declarative models)
- **Database**: PostgreSQL 16 (TimescaleDB) via psycopg2
- **Migrations**: Alembic
- **Auth**: JWT tokens with bcrypt password hashing, refresh token rotation
- **ML/Data Science**: NumPy 2.4, SciPy 1.14, pandas 2.3, scikit-learn 1.8
- **AI Services**: OpenAI API (GPT-4o-mini for menu OCR)
- **Package Manager**: uv (Astral's fast Python package manager)

### Frontend
- **Framework**: Next.js 15.1 (App Router, React Server Components)
- **UI**: Tailwind CSS 3.4 + shadcn/ui components
- **Icons**: Lucide React
- **HTTP Client**: Native fetch API
- **Package Manager**: pnpm

### Infrastructure
- **Database**: TimescaleDB (PostgreSQL 16 with time-series extensions)
- **Cache/Sessions**: Redis 7
- **Deployment**: AWS (Terraform IaC in `/infrastructure`)
- **Containers**: Docker & Docker Compose for local development

---

## Getting Started

### Prerequisites

Install these tools before starting:
- **Node.js 18+** and **pnpm** (`npm install -g pnpm`)
- **Python 3.12+** and **uv** ([installation guide](https://docs.astral.sh/uv/))
- **Docker Desktop** (for PostgreSQL and Redis)
- **Git**

### Installation

1. **Clone the repository:**
   ```bash
   git clone <your-repo-url>
   cd flux
   ```

2. **Install frontend dependencies:**
   ```bash
   pnpm install
   ```

3. **Start PostgreSQL and Redis:**
   ```bash
   docker compose up -d
   ```

   This starts:
   - PostgreSQL on `localhost:5432`
   - Redis on `localhost:6379`

4. **Set up the backend:**
   ```bash
   cd apps/api

   # Install Python dependencies
   uv pip install -e ".[dev]"

   # Create .env file (copy from .env.example)
   cp .env.example .env
   # Edit .env and add your OpenAI API key and JWT secret

   # Run database migrations
   uv run alembic upgrade head
   ```

5. **Create test user (via registration endpoint):**
   ```bash
   # Backend must be running first (see step 6)
   curl -X POST http://localhost:8000/api/v1/auth/register \
     -H "Content-Type: application/json" \
     -d '{"email": "test@flux.com", "password": "password123"}'
   ```

6. **Start development servers:**

   **Terminal 1 - Backend:**
   ```bash
   cd apps/api
   uv run uvicorn src.main:app --reload --port 8000
   ```

   **Terminal 2 - Frontend:**
   ```bash
   cd apps/web
   pnpm dev
   ```

   Access the application at:
   - Frontend: http://localhost:3000
   - Backend API: http://localhost:8000
   - API Docs: http://localhost:8000/docs (Swagger UI)

---

## Database Schema

Flux uses PostgreSQL 16 (TimescaleDB) with the following core tables:

### Core Entities

```
┌─────────────────┐
│     users       │
├─────────────────┤
│ id (UUID)       │
│ email (unique)  │
│ hashed_password │
│ created_at      │
└─────────────────┘
        │
        │ 1:N
        ▼
┌─────────────────┐
│  restaurants    │
├─────────────────┤
│ id (UUID)       │
│ name            │
│ owner_id (FK)   │
│ timezone        │
└─────────────────┘
```

### Menu & Recipes

```
restaurants 1:N menu_items
                    │
                    │ N:M (via recipes)
                    ▼
              ingredients
                    │
                    │ waste_factor
                    │ unit_cost
                    │ shelf_life_days
                    ▼
    ingredient_cost_history (time-series pricing)
```

### Transactions (Sales Data)

```
restaurants 1:N transactions
                    │
                    │ 1:N
                    ▼
            transaction_items
                    │
                    │ (menu_item_name)
                    ▼
             menu_items (linked by name)
```

### Forecasting

```
restaurants 1:N demand_forecasts
                    │
                    ├─ forecast_date
                    ├─ menu_item_name
                    ├─ predicted_quantity (mean)
                    ├─ p10_quantity (10th percentile)
                    ├─ p50_quantity (median)
                    ├─ p90_quantity (90th percentile)
                    └─ model_name
```

### Key Tables

| Table | Purpose | Key Fields |
|-------|---------|------------|
| `users` | User accounts | email, hashed_password |
| `restaurants` | Restaurant profiles | name, owner_id, timezone |
| `menu_items` | Dishes sold | name, price, category, auto_created |
| `ingredients` | Recipe components | name, unit_cost, waste_factor, shelf_life_days |
| `recipes` | Menu item → Ingredients | menu_item_id, ingredient_id, quantity, unit |
| `transactions` | Sales records | transaction_date, total_amount, is_promo |
| `transaction_items` | Line items | menu_item_name, quantity, unit_price |
| `demand_forecasts` | Predicted demand | forecast_date, predicted_quantity, p10/p50/p90 |
| `operating_hours` | Restaurant schedule | day_of_week, open_time, close_time |
| `data_uploads` | CSV import tracking | status, row_count, errors |
| `settings` | Feature flags | key, value, restaurant_id |

**Important Notes:**
- All primary keys use `UUID` for distributed scalability
- `transaction_items.menu_item_name` is a string (denormalized) for flexibility during import
- `auto_created` flag on `menu_items` tracks items created from transaction imports
- Timestamps use server-side defaults (`func.now()`)

For complete schema details, see [docs/architecture/07-database-schema.md](docs/architecture/07-database-schema.md)

---

## Mathematical Models

### 1. Demand Forecasting: Hierarchical Bayesian Negative Binomial

**Location**: `apps/api/src/services/forecasting/bayesian.py`

Flux uses a **custom-built Bayesian forecasting model** (not Prophet or XGBoost) based on Poisson-Gamma conjugate priors.

#### Mathematical Foundation

**Prior Distribution:**
```
λ ~ Gamma(α, β)
```
where λ is the daily demand rate

**Likelihood:**
```
y | λ ~ Poisson(λ)
```
where y is observed daily sales

**Posterior Distribution (after observing data):**
```
λ | y ~ Gamma(α_post, β_post)

where:
  α_post = α_prior + Σy_i
  β_post = β_prior + n
```

**Predictive Distribution:**
```
y_pred ~ NegativeBinomial(n=α_post, p=β_post/(β_post+1))
```

#### Seasonality Adjustment

The model uses **deseasonalization/reseasonalization** to handle day-of-week patterns:

1. **Calculate seasonal multipliers** from historical data:
   ```
   M_dow = (mean_sales_on_dow) / (global_mean_sales)

   with conservative capping: M ∈ [0.3, 3.0]
   and shrinkage for low-data days: M' = αM + (1-α)·1.0
   ```

2. **Deseasonalize history** before Bayesian update:
   ```
   y'_i = y_i / M_dow(i)
   ```

3. **Fit Bayesian model** to deseasonalized data (base demand)

4. **Reseasonalize forecasts** using Monte Carlo sampling:
   ```
   1. Sample: base_samples ~ NegBin(α_post, β_post)
   2. Scale: scaled_samples = base_samples × M_future_dow
   3. Compute quantiles from scaled_samples
   ```

#### Hierarchical Priors

The model learns priors at multiple levels:
- **Global Prior**: Weak prior (α=2.0, β=0.5) for all items
- **Category Prior**: Learned from all items in category (e.g., "Entrees")
- **Item Posterior**: Updated with item-specific sales data

**Cold Start Logic:**
- New items with <5 days history → use Category Prior
- Items with 5-30 days → blend Category + Item data
- Items with 30+ days → primarily Item-specific posterior

#### Outputs

For each forecast date, the model returns:
- **mean**: Expected demand (E[y])
- **p10**: 10th percentile (optimistic scenario)
- **p50**: Median (50th percentile)
- **p90**: 90th percentile (conservative ordering threshold)
- **p99**: 99th percentile (stockout prevention)
- **confidence_score**: 0-1 based on data quantity (sigmoid function)
- **logic_trigger**: Explainability string (e.g., "Seasonality 1.8x, Cold Start")

**Why This Model?**
- Handles low-frequency items (many days with 0 sales)
- Provides full probability distributions (not just point estimates)
- Interpretable parameters (α = total observed demand, β = observation count)
- Fast inference (closed-form posteriors, no MCMC needed)
- Incorporates domain knowledge via priors

### 2. COGS Calculation with Waste Factors

**Location**: `apps/api/src/services/costing.py` (implementation), `apps/web/src/features/recipes/ProfitabilityDashboard.tsx` (UI)

**Formula:**
```
COGS_with_waste = Σ (ingredient_qty × ingredient_unit_cost × (1 + waste_factor))

where:
  waste_factor ∈ [0, 0.60]  (0% to 60% waste)

Example:
  10 kg tomatoes @ $2/kg with 15% waste factor:
  Cost = 10 × $2 × 1.15 = $23 (instead of $20 without waste)
```

**Profit Margin:**
```
Margin = (Menu_Price - COGS_with_waste) / Menu_Price × 100%
```

**Toggle Feature**: Waste factor can be enabled/disabled per restaurant via Settings API

### 3. Feature Engineering for Forecasting

**Location**: `apps/api/src/services/features.py`

Transforms raw transaction data into ML-ready features:
- **Day-of-week encoding** (one-hot: 7 features)
- **Holiday indicators** (binary flag)
- **Promotion flags** (from `transactions.is_promo`)
- **Weather data** (placeholder for external API integration)
- **Lag features** (sales from 7/14/28 days ago)
- **Rolling statistics** (7-day moving average, std dev)

For algorithm details, see [docs/architecture/13-algorithm-architecture.md](docs/architecture/13-algorithm-architecture.md)

---

## API Reference

Base URL: `http://localhost:8000/api/v1`

### Authentication

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/auth/register` | POST | No | Create new user account |
| `/auth/login` | POST | No | Login and get JWT tokens |
| `/auth/refresh` | POST | No | Refresh access token (rotates refresh token) |
| `/auth/logout` | POST | Yes | Logout (client discards tokens) |
| `/auth/me` | GET | Yes | Get current user profile |

**Request/Response Examples:**

**Register:**
```bash
POST /api/v1/auth/register
Content-Type: application/json

{
  "email": "chef@restaurant.com",
  "password": "securepassword123"
}

# Response:
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer"
}
```

**Login:**
```bash
POST /api/v1/auth/login
Content-Type: application/json

{
  "email": "chef@restaurant.com",
  "password": "securepassword123"
}

# Response: (same as register)
```

**Protected Requests:**
```bash
GET /api/v1/auth/me
Authorization: Bearer <access_token>

# Response:
{
  "id": "uuid",
  "email": "chef@restaurant.com",
  "created_at": "2026-01-01T00:00:00Z"
}
```

### Data Ingestion

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/data/uploads` | POST | Upload CSV file (transactions) |
| `/data/uploads` | GET | List all uploads with status |
| `/data/uploads/{id}` | GET | Get upload details |

**CSV Upload Example:**
```bash
POST /api/v1/data/uploads
Authorization: Bearer <token>
Content-Type: multipart/form-data

file=@transactions.csv

# Expected CSV Format:
date,item,quantity,price
2026-01-01,Caesar Salad,15,12.50
2026-01-01,Ribeye Steak,8,42.00
```

### Menu & Recipes

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/menu/items` | GET | List all menu items |
| `/menu/items` | POST | Create menu item |
| `/menu/items/{id}` | PUT | Update menu item |
| `/recipes/menu/upload-photo` | POST | Upload menu photo for OCR extraction |
| `/recipes/confirm` | GET | Get unconfirmed recipe suggestions |
| `/recipes/confirm` | POST | Confirm recipe with ingredients |
| `/recipes` | GET | List confirmed recipes |

**Menu Photo Upload:**
```bash
POST /api/v1/recipes/menu/upload-photo
Authorization: Bearer <token>
Content-Type: multipart/form-data

file=@menu_photo.jpg

# Response:
{
  "items": [
    {
      "name": "Caesar Salad",
      "category": "Appetizers",
      "description": "Romaine, croutons, parmesan, caesar dressing",
      "price": 12.50,
      "confidence": 0.95
    },
    ...
  ],
  "total_items": 15,
  "message": "Successfully extracted 15 menu items and created 15 new items in your menu"
}
```

**Recipe Confirmation:**
```bash
POST /api/v1/recipes/confirm
Authorization: Bearer <token>
Content-Type: application/json

{
  "menu_item_id": "uuid",
  "ingredients": [
    {
      "ingredient_id": "uuid",
      "quantity": 150,
      "unit": "g"
    },
    ...
  ]
}
```

### Forecasting

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/forecast/demand` | POST | Generate demand forecast |
| `/forecast/demand` | GET | Retrieve existing forecasts |

**Generate Forecast:**
```bash
POST /api/v1/forecast/demand
Authorization: Bearer <token>
Content-Type: application/json

{
  "menu_item_name": "Caesar Salad",
  "days_ahead": 7
}

# Response:
{
  "forecasts": [
    {
      "date": "2026-01-07",
      "mean": 18.5,
      "p10": 12.0,
      "p50": 18.0,
      "p90": 26.0,
      "confidence_score": 0.87,
      "model_name": "BayesianSeasonal_v1 (Seasonality 1.2x)"
    },
    ...
  ]
}
```

### Settings

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/settings` | GET | Get all restaurant settings |
| `/settings` | PUT | Update settings (batch) |

**Example Settings:**
```bash
PUT /api/v1/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "waste_factor_enabled": true,
  "forecast_confidence_threshold": 0.7
}
```

### Operating Hours

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/operating-hours` | GET | Get restaurant schedule |
| `/operating-hours` | POST | Set operating hours |

**Full API documentation**: http://localhost:8000/docs (Swagger UI when server is running)

---

## Development Workflow

### Database Migrations

Create a new migration after model changes:
```bash
cd apps/api
uv run alembic revision --autogenerate -m "Add waste_factor to ingredients"
uv run alembic upgrade head
```

Rollback:
```bash
uv run alembic downgrade -1
```

### Running Tests

```bash
cd apps/api
uv run pytest
```

### Code Quality

**Backend (Python):**
```bash
cd apps/api
uv run black src/          # Format code
uv run ruff check src/     # Lint
uv run mypy src/           # Type checking
```

**Frontend (TypeScript):**
```bash
cd apps/web
pnpm lint                  # ESLint
pnpm type-check            # TypeScript validation
```

### Adding Dependencies

**Backend:**
```bash
cd apps/api
uv pip install <package-name>
# Update pyproject.toml manually to persist
```

**Frontend:**
```bash
cd apps/web
pnpm add <package-name>
```

### Environment Variables

**Backend** (`apps/api/.env`):
```bash
# OpenAI API Key for menu OCR and recipe estimation
OPENAI_API_KEY=sk-...

# JWT Secret (generate with: openssl rand -base64 32)
JWT_SECRET_KEY=your-secret-key-here

# Database
DATABASE_URL=postgresql://flux:fluxpassword@localhost:5432/flux_dev

# Redis (optional - for token blacklist)
REDIS_URL=redis://localhost:6379/0
```

**Frontend** (`apps/web/.env.local`):
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

**IMPORTANT**: Never commit `.env` files. Use `.env.example` as a template.

---

## Test Credentials

### Development Users

You can create test users via the registration endpoint or use these pre-seeded accounts (if seed script runs successfully):

| Email | Password | Restaurant | Notes |
|-------|----------|------------|-------|
| `chef@laboqueria.es` | `password123` | La Boqueria Bites | Default test account |
| `owner@eixample.cat` | `password123` | Eixample Elegance | Multi-restaurant test |

**Create New Test User:**
```bash
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "newuser@test.com", "password": "password123"}'
```

### Database Access

```bash
# Connect to local PostgreSQL
psql postgresql://flux:fluxpassword@localhost:5432/flux_dev

# Useful queries:
SELECT * FROM users;
SELECT * FROM restaurants;
SELECT * FROM menu_items LIMIT 10;
SELECT * FROM demand_forecasts ORDER BY created_at DESC LIMIT 10;
```

---

## Project Status

### Completed Features

- ✅ User authentication (JWT with refresh tokens)
- ✅ Restaurant management
- ✅ CSV transaction import with auto-menu item creation
- ✅ Menu photo upload with GPT-4o Vision OCR
- ✅ Recipe confirmation workflow
- ✅ Ingredient management with waste factors
- ✅ COGS calculation with waste factor toggle
- ✅ Hierarchical Bayesian demand forecasting
- ✅ Operating hours management
- ✅ Settings & feature flags system
- ✅ Profitability dashboard

### Roadmap

See detailed stories in:
- [Epic 1: Foundation](docs/stories/epic-1-foundation.md)
- [Epic 2: Data Ingestion](docs/stories/epic-2-data-ingestion.md)
- [Epic 3: Recipe Intelligence](docs/stories/epic-3-recipe-intelligence.md)
- [Epic 4: Demand Forecasting](docs/stories/epic-4-demand-forecasting.md)

**Upcoming:**
- Labor forecasting (hours needed based on demand)
- Inventory tracking with automated low-stock alerts
- Weather API integration for demand adjustments
- Mobile app (React Native)
- Multi-location support with role-based access

---

## Architecture Documentation

For deeper technical details, see:
- [PRD - Product Requirements](docs/prd.md)
- [High-Level Architecture](docs/architecture/01-high-level-overview.md)
- [Database Schema](docs/architecture/07-database-schema.md)
- [Algorithm Architecture](docs/architecture/13-algorithm-architecture.md)
- [API Specification](docs/architecture/03-api-specification.md)
- [Security & Compliance](docs/architecture/11-security-compliance.md)

---

## Support

For questions or issues:
1. Check the [API documentation](http://localhost:8000/docs)
2. Review architecture docs in `/docs`
3. Contact the development team

---

## License

Proprietary - All Rights Reserved
EOFREADME
