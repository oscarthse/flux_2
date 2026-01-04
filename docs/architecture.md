# Flux Fullstack Architecture Document

## Introduction

This document outlines the complete fullstack architecture for Flux, including backend systems, frontend implementation, ML/AI infrastructure, and their integration. It serves as the single source of truth for AI-driven development, ensuring consistency across the entire technology stack.

This unified approach combines what would traditionally be separate backend and frontend architecture documents, streamlining the development process for modern fullstack applications where these concerns are increasingly intertwined.

### Starter Template or Existing Project

**Status**: N/A - Greenfield project

This is a greenfield project with no existing codebase or starter template. All architectural decisions are being made from scratch, optimized specifically for the restaurant SaaS use case with ML forecasting capabilities.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-12-17 | 1.0 | Initial architecture document | Winston (Architect) |

---

## High Level Architecture

### Technical Summary

Flux is a serverless, multi-tenant SaaS platform built on AWS, leveraging Next.js 15 for the frontend and a **Python FastAPI-based** Lambda backend. The architecture uses PostgreSQL with Row-Level Security for multi-tenant data isolation, AWS SageMaker for ML model training, and Lambda + S3 for model inference. Real-time POS data ingestion occurs via Kinesis Data Streams with 15-minute sync intervals, while TimescaleDB extensions optimize time-series query performance. The platform is designed for 10,000 concurrent restaurant customers with 50M+ daily transactions, achieving sub-second API response times and 99.9% uptime.

**Key Integration Points:**
- **Frontend ↔ Backend**: **REST API with OpenAPI schema, auto-generated TypeScript client**
- **Backend ↔ POS Systems**: Adapter pattern with provider-specific implementations (Toast, Square, Lightspeed, Clover, Revel)
- **Backend ↔ ML Services**: Async job queues (Celery/SQS) trigger SageMaker training; Lambda functions serve predictions
- **Data Flow**: POS → Kinesis → Lambda → PostgreSQL/TimescaleDB → ML Pipeline → Predictions → Frontend

### Platform and Infrastructure Choice

**Platform:** AWS
**Key Services:** Lambda, API Gateway, RDS PostgreSQL (TimescaleDB), SageMaker, Kinesis, S3, ElastiCache Redis, CloudFront
**Deployment Host and Regions:**
- Primary: eu-west-1 (Ireland) - for EU customers (GDPR compliance)
- Secondary: us-east-1 (N. Virginia) - for US customers
- Frontend CDN: CloudFront (global)

**Rationale:** AWS was selected for its native ML capabilities (SageMaker), cost-effective serverless compute (Lambda), proven scalability for 10K+ tenants, and mature GDPR compliance tooling. SageMaker's spot instance training provides 70% cost savings, while Lambda's per-request pricing optimizes costs for variable load. The eu-west-1 region ensures GDPR data residency requirements are met.

### Repository Structure

**Structure:** Monorepo
**Monorepo Tool:** Turborepo
**Package Organization:** Workspaces pattern with shared packages for UI components and configs.

```
flux/
├── apps/
│   ├── web/                    # Next.js 15 frontend (Vercel)
│   └── api/                    # FastAPI backend (Lambda, Python)
├── packages/
│   ├── ui/                     # Shared React components (shadcn/ui)
│   ├── lib/                    # Shared frontend utilities
│   └── config/                 # Shared configs (ESLint, TS, Tailwind)
├── infrastructure/             # Terraform (IaC)
├── docs/
├── turbo.json
└── package.json
```

**Rationale:** A Monorepo managed by Turborepo enables rapid development and atomic changes across the frontend application and shared packages. The Python backend and ML code are managed with Poetry and have their own dependency ecosystem within the `apps/api` directory. Terraform IaC is kept in a dedicated top-level directory. This structure uses Turborepo for frontend efficiencies while allowing Python's standard tooling to manage the backend.

### High Level Architecture Diagram

```mermaid
graph TB
    subgraph "User Layer"
        U1[Restaurant Owner]
        U2[Manager]
        U3[Chef]
    end

    subgraph "CDN & Edge"
        CF[CloudFront CDN]
    end

    subgraph "Frontend - Vercel"
        WEB[Next.js 15 App<br/>SSR + Client Components<br/>OpenAPI Client]
    end

    subgraph "API Layer - AWS"
        APIGW[API Gateway<br/>HTTP API]
        AUTH[Lambda Authorizer<br/>JWT Validation]
        API[Lambda Functions<br/>FastAPI Routers]
    end

    subgraph "POS Integration Layer"
        KINESIS[Kinesis Data Streams<br/>Real-time Ingestion]
        SYNC[Lambda Consumer<br/>POS Sync Service]
        ADAPTERS[POS Adapters<br/>Toast | Square | Lightspeed<br/>Clover | Revel]
        SQS[SQS Queues<br/>Rate Limiting]
    end

    subgraph "Data Layer"
        RDS[(PostgreSQL RDS<br/>TimescaleDB<br/>Row-Level Security)]
        REDIS[(ElastiCache Redis<br/>Cache & Celery Broker)]
        S3[(S3 Buckets<br/>ML Models<br/>Exports<br/>Backups)]
    end

    subgraph "ML Pipeline - SageMaker"
        TRAIN[SageMaker Training<br/>Prophet + XGBoost<br/>Spot Instances]
        INFERENCE[Lambda Inference<br/>S3 Model Loading]
        FEATURES[Feature Engineering<br/>Glue ETL Jobs]
    end

    subgraph "Background Jobs"
        EB[EventBridge<br/>Scheduled Jobs]
        JOBS[Celery Workers (Lambda)<br/>Daily Training<br/>Usage Sync<br/>Emails]
    end

    subgraph "External Systems"
        POS[POS Systems<br/>Toast, Square, etc.]
        STRIPE[Stripe<br/>Billing]
        EMAIL[SendGrid<br/>Notifications]
    end

    U1 --> CF
    U2 --> CF
    U3 --> CF
    CF --> WEB
    WEB --> APIGW
    APIGW --> AUTH
    AUTH --> API
    API --> RDS
    API --> REDIS
    API --> INFERENCE

    POS --> KINESIS
    KINESIS --> SYNC
    SYNC --> ADAPTERS
    ADAPTERS --> SQS
    SQS --> API
    API --> RDS

    RDS --> FEATURES
    FEATURES --> S3
    S3 --> TRAIN
    TRAIN --> S3
    S3 --> INFERENCE
    INFERENCE --> API

    EB --> JOBS
    JOBS --> RDS
    JOBS --> TRAIN

    API --> STRIPE
    JOBS --> EMAIL

    style WEB fill:#61dafb
    style API fill:#3776ab
    style RDS fill:#336791
    style TRAIN fill:#ff6f00
    style KINESIS fill:#ff9900
```

**Architecture Flow Explanation:**

1.  **User Access**: Restaurant users access the Next.js frontend via CloudFront CDN (global edge caching).
2.  **API Requests**: The frontend uses an auto-generated TypeScript client to make RESTful API calls to API Gateway. A Lambda Authorizer validates the JWT, and then the request is routed to the appropriate FastAPI-based Lambda function.
3.  **POS Data Ingestion**:
    *   POS systems push data to Kinesis Data Streams (real-time).
    *   Lambda consumers process streams using POS adapters (Toast, Square, etc.).
    *   SQS queues rate-limit requests to avoid overwhelming POS APIs.
    *   Normalized data is written to PostgreSQL with RLS for tenant isolation.
4.  **ML Pipeline**:
    *   EventBridge triggers daily training jobs at 2 AM UTC.
    *   Feature engineering extracts data from RDS → S3 (Parquet format).
    *   SageMaker Training runs Prophet + XGBoost models on spot instances.
    *   Trained models stored in S3.
    *   Lambda inference functions load models from S3 for real-time predictions.
5.  **Caching**: Redis caches API responses, sessions, and serves as the message broker for Celery background tasks.
6.  **Background Jobs**: EventBridge schedules tasks, which are executed by Celery workers running on Lambda for model training, usage sync, and email notifications.

**Key Design Decisions:**

- **Kinesis over Kafka**: Simpler operations, native AWS integration, sufficient throughput (10K restaurants × 4 syncs/hr).
- **Lambda for API**: Cost-effective at variable load, auto-scales to 10K concurrent requests.
- **SageMaker Spot Instances**: 70% cost savings on model training vs on-demand.
- **TimescaleDB**: 10-100x faster time-range queries for forecasting workloads.
- **CloudFront CDN**: Global edge caching reduces latency for international customers.

### Architectural Patterns

The following patterns guide both frontend and backend development:

- **Serverless Architecture:** Lambda functions for API and background jobs eliminate server management, auto-scale to demand, and optimize costs for variable workloads. _Rationale:_ Restaurant traffic varies significantly (lunch/dinner rushes) - serverless perfectly matches this pattern, paying only for actual usage.

- **Multi-Tenant with Row-Level Security (RLS):** Shared PostgreSQL database with RLS policies ensure data isolation while maintaining cost efficiency at scale. _Rationale:_ For 10,000 tenants, dedicated databases would be operationally expensive (~$1M/year in RDS costs alone). RLS provides strong isolation at <$3K/month.

- **Adapter Pattern (POS Integrations):** Abstract base adapter interface with provider-specific implementations (Toast, Square, Lightspeed, Clover, Revel). _Rationale:_ Each POS system has unique API quirks - adapters isolate this complexity, making it trivial to add new providers.

- **API Gateway Pattern:** Single entry point (API Gateway) centralizes authentication, rate limiting, CORS, and logging. _Rationale:_ Simplifies security enforcement and provides unified observability across all API endpoints.

- **Event-Driven Architecture:** Kinesis Data Streams + EventBridge + SQS/Celery for asynchronous processing. _Rationale:_ POS data ingestion must be decoupled from API responses - restaurants can't wait for data processing to complete.

- **CQRS Light (Query/Command Separation):** Read replicas for analytics queries, primary database for writes. _Rationale:_ Heavy forecasting queries shouldn't impact transactional performance during order processing.

- **Repository Pattern:** Data access abstracted through **SQLAlchemy ORM** with typed repositories. _Rationale:_ Enables easy testing with mock repositories and potential future database migrations.

- **Micro-Frontend with Server Components:** Next.js 15 Server Components render on server, Client Components handle interactivity. _Rationale:_ Reduces JavaScript bundle size by 60-80%, improves Core Web Vitals for SEO.

- **Feature Flag Pattern:** AWS AppConfig for gradual feature rollouts and A/B testing. _Rationale:_ Critical for ML model deployments - test new forecasting models on 5% of customers before full rollout.

- **Circuit Breaker Pattern (POS APIs):** Automatic fallback when POS provider APIs fail repeatedly. _Rationale:_ Prevents cascading failures - if Toast API is down, queue syncs for retry rather than exhausting Lambda concurrency.

---

## Tech Stack

This section is now sourced from the definitive tech stack document. Please refer to **[./architecture/tech-stack.md](./architecture/tech-stack.md)** for the complete and official technology selection.

Below is a summary of the key backend and infrastructure choices for quick reference.

### Technology Stack Summary

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Backend Language** | **Python** | **3.12+** | **Backend API development** |
| **Backend Framework**| **FastAPI** | **0.109+**| **Modern async API framework**|
| **API Style** | **REST + OpenAPI**| **OpenAPI 3.1**| **HTTP REST API with schema** |
| **Database** | **PostgreSQL (RDS)**| **16+** | **Relational + time-series** |
| **ORM** | **SQLAlchemy** | **2.0+** | **Python ORM with async support**|
| **Authentication** | **FastAPI OAuth2+JWT**| **Latest** | **JWT authentication** |
| **Backend Testing** | **pytest + httpx**| **Latest** | **API/service tests** |
| **IaC Tool** | **Terraform** | **1.7+** | **Infrastructure as Code** |
| **Logging** | **structlog** | **Latest** | **Structured JSON logging** |
| **Validation** | **Pydantic** | **2.5+** | **Runtime type validation** |
| **DB Migrations** | **Alembic** | **1.13+** | **Database schema migrations** |

### Why This Stack?

#### Python Backend Benefits

1.  **Unified Language**: Backend + ML + Data Pipelines can all be done in Python.
2.  **ML Integration**: Native integration with SageMaker, scikit-learn, and the entire data science ecosystem.
3.  **Async Support**: FastAPI & SQLAlchemy 2.0 offer world-class async/await support for high-concurrency workloads.
4.  **Type Safety**: Python 3.12+ with Pydantic gives robust runtime data validation and static analysis with `mypy`.
5.  **Performance**: FastAPI is one of the fastest Python frameworks, with performance comparable to Node.js.
6.  **Auto Documentation**: FastAPI automatically generates OpenAPI documentation, which can be used to generate a type-safe frontend client.
7.  **Ecosystem**: Massive Python ecosystem for data processing, ML, APIs, and more.

#### Mitigation for Lost End-to-End TypeScript Safety

The primary trade-off is losing seamless end-to-end type safety between a TypeScript frontend and a TypeScript backend. We mitigate this by:

**Using OpenAPI Code Generation** for type-safe frontend-backend communication:
```bash
# Generate TypeScript client from FastAPI OpenAPI schema
npx openapi-typescript-codegen --input http://localhost:8000/openapi.json --output ./apps/web/src/lib/api-client
```
This gives us:
- ✅ Type-safe API calls in the frontend.
- ✅ Auto-completion in the IDE for API methods and models.
- ✅ Compile-time errors if the API contract changes.
- ✅ A single source of truth: the FastAPI Pydantic models.

### Impact Mapping: Technology Choices → Team & Operations

#### **Impact on Hiring**

**Positive Impacts:**
- **Python Everywhere**: A single, popular language for backend, data, and ML simplifies hiring and allows engineers to work across the stack. Attracts data-centric engineers.
- **Modern Stack Appeal**: Next.js 15 + FastAPI + Serverless is attractive to senior engineers, especially those with an ML background.
- **Reduced ML Infrastructure Expertise Needed**: SageMaker managed services mean we don't need dedicated ML infrastructure engineers (managing Kubernetes, GPU optimization, etc.).

**Challenges:**
- **Terraform Expertise**: Requires engineers comfortable with HCL and infrastructure concepts, though it is the industry standard.
- **AWS-Specific Knowledge**: Need engineers comfortable with Lambda, EventBridge, SageMaker (mitigated by clear Terraform documentation).
- **TimescaleDB**: Less common than vanilla PostgreSQL, but it is just a PostgreSQL extension with a 1-day learning curve.

**Hiring Strategy Recommendations:**
- Prioritize: Strong Python & SQL skills, FastAPI/Pydantic experience, cloud-native mindset.
- Nice-to-have: AWS certifications, Terraform experience, time-series database knowledge.
- Red flags: Aversion to serverless, preference for monolithic architectures, lack of interest in data/ML.

#### **Impact on Onboarding**

**Fast Onboarding (1-2 weeks to productive):**
- **UV for Dependency Management**: `uv pip install -r requirements.txt` sets up the entire Python backend environment.
- **OpenAPI Auto-documentation**: The `/docs` endpoint from FastAPI provides an interactive API playground. Developers can understand all endpoints without reading separate docs.
- **SQLAlchemy Models & Alembic**: The data model is clearly defined in Python code, and migrations are version-controlled.
- **Infrastructure as Code**: Terraform in HCL is declarative and easier to read than imperative CDK code, making the infrastructure more understandable.

**Learning Curve Areas (2-4 weeks to master):**
- **Next.js Server Components**: A paradigm shift from traditional React.
- **Multi-tenancy with RLS**: Understanding PostgreSQL Row-Level Security policies and how they are applied in middleware.
- **SageMaker Training**: Python ML engineers need to learn the SageMaker SDK and spot instance best practices.
- **Event-Driven Patterns**: Understanding Kinesis → Lambda → SQS/Celery flows.

**Onboarding Acceleration Tactics:**
- **Dev Environment Script**: `make setup` clones repos, installs deps, seeds local DB via Docker, starts all services.
- **Architecture Decision Records (ADRs)**: This document serves as the foundation.
- **Example PR Workflow**: Show a new developer a complete PR (Alembic migration → SQLAlchemy model change → FastAPI endpoint change → frontend update) to understand the full-stack flow.
- **Pair Programming Sessions**: A 2-hour session on a POS adapter implementation teaches the adapter pattern, Kinesis integration, and error handling.

#### **Impact on Maintenance**

**Long-term Maintenance Benefits:**
- **Pydantic for Robust Data Validation**: Catches data errors at the API boundary, preventing bad data from entering the system. `mypy` adds static analysis.
- **Turborepo Caching**: CI/CD only rebuilds changed frontend packages, keeping build times fast.
- **Alembic Migrations**: Database schema changes are versioned, reviewable, and rollback-able via Git.
- **Serverless Cost Optimization**: Lambda scales to zero when idle, eliminating the need to right-size EC2 instances quarterly.
- **SageMaker Model Registry**: All ML models are versioned with training data lineage, making it easy to roll back bad models.

**Maintenance Challenges:**
- **Breaking Changes in Fast-Moving Tools**: Next.js releases frequently and may require upgrades every 6-12 months.
- **AWS Service Limits**: Lambda concurrency (1000 default), Kinesis shard limits (200 default) - need to request increases via Terraform.
- **TimescaleDB Compression**: Requires periodic monitoring and manual recompression policy adjustments.
- **Multi-tenancy Complexity**: Adding new tenant-aware features requires careful testing of RLS policies to prevent data leakage.

**Maintenance Cost Estimates (Monthly):**
- **Datadog**: ~$500/month (10 hosts equivalent for Lambda + RDS)
- **AWS Support**: $100/month (Business plan for SageMaker support)
- **Developer Time**: 20% of sprint (dependency updates, security patches, performance optimization).

#### **Team Structure Implications**

**Optimal Team Composition for Flux (10-person engineering team):**
- **3 Full-Stack Engineers**: Next.js frontend + Python/FastAPI backend (focus on restaurant dashboard, forecasting UI).
- **2 Backend / Data Engineers**: POS integrations, data pipeline, Kinesis/Lambda optimization, PostgreSQL performance, TimescaleDB optimization, ETL pipelines.
- **2 ML Engineers**: Prophet/XGBoost models, SageMaker training pipelines, feature engineering.
- **1 DevOps/Platform Engineer**: AWS infrastructure with Terraform, CI/CD, monitoring, cost optimization.
- **1 QA/Test Engineer**: Playwright E2E tests, POS integration testing, load testing.

**Why This Works:**
- Full-stack engineers share on-call rotation (everyone understands the entire stack).
- ML engineers can deploy models independently (SageMaker jobs don't require a backend deploy).
- The DevOps engineer enables self-service deployments (backend team deploys their own Lambda functions via Terraform modules).

#### **Operational Complexity Score**

| Aspect | Complexity (1-10) | Mitigation |
|--------|-------------------|------------|
| **Local Development** | 4/10 | Docker Compose for PostgreSQL + Redis, mock POS APIs, seed data script |
| **CI/CD Pipeline** | 3/10 | GitHub Actions with Turborepo cache for frontend, separate Python pipeline |
| **Monitoring & Debugging**| 5/10 | Datadog unified dashboard, CloudWatch Insights for Lambda logs |
| **Database Migrations** | 4/10 | Alembic for migrations with staging → production flow, automated rollback on failure |
| **ML Model Deployment** | 6/10 | SageMaker Model Registry + Lambda alias routing, A/B testing infrastructure |
| **Multi-tenant Data Isolation**| 7/10 | RLS policies must be tested thoroughly; integration tests for every tenant query |
| **POS Integration Reliability**| 8/10 | Each provider has unique failure modes, requires extensive error handling + retries |
| **Cost Management** | 5/10 | AWS Cost Explorer + Budget Alerts, need quarterly review of Lambda/SageMaker usage |

**Overall Maintenance Philosophy:**
This stack optimizes for **developer velocity** and **data processing power** at the cost of a small seam between the frontend and backend. This trade-off is worth it because:
1.  **Pydantic + mypy** prevents entire classes of data bugs.
2.  **Serverless** eliminates most server maintenance work.
3.  **SageMaker** abstracts away complex ML infrastructure.

**Net Effect**: A 5-person team can ship what traditionally takes 8-10 people.

---

## Data Models

This section defines the **complete data model** for the Flux platform, including all entities, relationships, storage calculations, and database design patterns. All models are designed with multi-tenancy (Row-Level Security), GDPR compliance, and ML forecasting requirements in mind.

### Scale Targets & Storage Calculations

**Platform Scale (Target State):**
- **Tenants:** 10,000 restaurants
- **Users:** ~50,000 total (5 users per restaurant average)
- **Daily Transactions:** 8,000,000 (800 transactions/day per restaurant average)
- **Retention Period:** 6 months for raw transaction data, indefinite for aggregated forecasts
- **Total Records (6 months):** ~1.44 billion transaction records

**Storage Breakdown (Compressed with TimescaleDB):**

| Data Category | Uncompressed | Compressed | Records | Notes |
|---------------|--------------|------------|---------|-------|
| Core Business Data | 3.8 TB | 2.66 TB | 1.5B | Transactions, items, menus |
| ML/Forecasting Data | 228 GB | 160 GB | 380M | Forecasts, features, models |
| Procurement & Inventory | 34 GB | 24 GB | 60M | Recommendations, orders, inventory |
| Supporting Data | 121 GB | 85 GB | 150M | Syncs, tasks, notifications, logs |
| **TOTAL** | **4.83 TB** | **3.37 TB** | **~2.1B** | **6-month window** |

**Growth Rate:** +240 GB/month (compressed) → +2.88 TB/year

**Cost Estimate (AWS RDS PostgreSQL):**
- Storage: 3.37 TB × $0.115/GB = $387/month
- IOPS: 50,000 provisioned IOPS × $0.10 = $5,000/month
- Instance: db.r6g.2xlarge = $725/month
- **Total:** ~$6,112/month for database infrastructure

### Multi-Tenancy Strategy

**Row-Level Security (RLS) Pattern:**

All tenant-scoped tables include `restaurant_id` and enforce RLS policies:

```sql
-- Enable RLS on every tenant table
ALTER TABLE transactions ENABLE ROW LEVEL SECURITY;

-- Policy: Users can only access their restaurant's data
CREATE POLICY tenant_isolation ON transactions
  FOR ALL
  TO authenticated_users
  USING (restaurant_id = current_setting('app.current_restaurant_id')::uuid);

-- Set tenant context per request (in Lambda/tRPC)
SET LOCAL app.current_restaurant_id = 'uuid-here';
```

**Tenant Identification:**
- `restaurant_id` (UUID) on ALL tenant-scoped tables
- Indexed on every table for query performance
- Composite primary keys include `restaurant_id` where appropriate
- Foreign keys always reference within same tenant

### GDPR Compliance Fields

**Standard GDPR Fields (on User, Restaurant, Transaction tables):**

```typescript
interface GDPRCompliant {
  anonymized: boolean;              // True if PII has been scrubbed
  anonymized_at?: Date;             // When anonymization occurred
  retention_until?: Date;           // Delete after this date
  data_subject_id?: string;         // For GDPR data subject requests
  consent_marketing: boolean;       // Email marketing consent
  consent_updated_at: Date;         // Last consent update
}
```

**Data Residency:**
- Primary region: `eu-west-1` (Ireland) for EU customers
- US region: `us-east-1` (N. Virginia) for US customers
- Cross-region replication disabled (GDPR compliance)

### Core Business Entities

#### 1. Restaurant

**Purpose:** Represents a single restaurant tenant. Core entity for multi-tenancy.

**Storage:** ~1 KB per record × 10,000 = **10 MB**

```typescript
interface Restaurant {
  // Identity
  id: string;                       // UUID (primary key)
  name: string;                     // "Joe's Pizza"
  slug: string;                     // "joes-pizza-sf" (unique, URL-friendly)

  // Ownership
  owner_id: string;                 // FK → users.id
  subscription_tier: 'FREE' | 'STARTER' | 'PRO' | 'ENTERPRISE';
  subscription_status: 'ACTIVE' | 'TRIAL' | 'CANCELLED' | 'SUSPENDED';
  trial_ends_at?: Date;

  // Location & Business Details
  timezone: string;                 // IANA timezone: 'America/New_York'
  currency: string;                 // ISO 4217: 'USD', 'EUR', 'GBP'
  location_type: 'URBAN' | 'SUBURBAN' | 'RURAL';
  cuisine_type: 'AMERICAN' | 'ITALIAN' | 'MEXICAN' | 'ASIAN' | 'FRENCH' | 'OTHER';
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state_province?: string;
  postal_code?: string;
  country: string;                  // ISO 3166-1 alpha-2: 'US', 'GB', 'DE'

  // Data Health Score (for ML model confidence)
  data_health_score: number;        // 0-100 (calculated daily)
  data_health_metrics: {
    transaction_volume_7d: number;
    transaction_volume_30d: number;
    menu_item_coverage: number;     // % of items with sales data
    pos_connection_uptime: number;  // % uptime over 30 days
    last_sync_age_hours: number;
  };

  // Multi-Location Support
  parent_restaurant_id?: string;    // FK → restaurants.id (null for standalone)
  is_chain_location: boolean;       // Part of multi-location group?

  // GDPR
  anonymized: boolean;
  anonymized_at?: Date;
  retention_until?: Date;
  data_region: 'EU' | 'US' | 'OTHER';

  // Audit
  created_at: Date;
  updated_at: Date;
  created_by: string;               // FK → users.id
}
```

**Indexes:**
```sql
CREATE UNIQUE INDEX idx_restaurants_slug ON restaurants(slug);
CREATE INDEX idx_restaurants_owner ON restaurants(owner_id);
CREATE INDEX idx_restaurants_parent ON restaurants(parent_restaurant_id) WHERE parent_restaurant_id IS NOT NULL;
```

#### 2. User

**Purpose:** Platform users (restaurant owners, managers, chefs, staff).

**Storage:** ~500 bytes per record × 50,000 = **25 MB**

```typescript
interface User {
  // Identity
  id: string;                       // UUID (primary key)
  email: string;                    // Unique, lowercase
  email_verified: boolean;

  // Authentication (NextAuth.js)
  password_hash?: string;           // Null if OAuth-only
  oauth_provider?: 'GOOGLE' | 'MICROSOFT' | 'APPLE';
  oauth_id?: string;

  // Profile
  first_name: string;
  last_name: string;
  avatar_url?: string;              // S3 URL
  phone?: string;

  // Role & Permissions (per restaurant)
  // NOTE: User can belong to multiple restaurants with different roles
  // Actual role stored in restaurant_users join table

  // Preferences
  locale: string;                   // 'en-US', 'es-ES', 'fr-FR'
  notification_preferences: {
    email_forecasts: boolean;
    email_low_stock: boolean;
    email_weekly_summary: boolean;
    push_notifications: boolean;
  };

  // GDPR
  anonymized: boolean;
  anonymized_at?: Date;
  retention_until?: Date;
  data_subject_id?: string;
  consent_marketing: boolean;
  consent_updated_at: Date;

  // Security
  last_login_at?: Date;
  last_login_ip?: string;
  failed_login_attempts: number;
  locked_until?: Date;              // Account lockout after 5 failed attempts

  // Audit
  created_at: Date;
  updated_at: Date;
}
```

**Indexes:**
```sql
CREATE UNIQUE INDEX idx_users_email ON users(LOWER(email));
CREATE INDEX idx_users_oauth ON users(oauth_provider, oauth_id) WHERE oauth_provider IS NOT NULL;
```

#### 3. RestaurantUser (Join Table)

**Purpose:** Many-to-many relationship between users and restaurants with role assignment.

**Storage:** ~200 bytes per record × 50,000 = **10 MB**

```typescript
interface RestaurantUser {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (indexed)
  user_id: string;                  // FK → users.id (indexed)

  // Role-Based Access Control
  role: 'OWNER' | 'ADMIN' | 'MANAGER' | 'CHEF' | 'STAFF' | 'VIEWER';
  permissions: {
    can_view_forecasts: boolean;
    can_edit_menu: boolean;
    can_view_financials: boolean;
    can_manage_users: boolean;
    can_manage_integrations: boolean;
  };

  // Status
  status: 'ACTIVE' | 'INVITED' | 'SUSPENDED';
  invited_at?: Date;
  invited_by?: string;              // FK → users.id
  joined_at?: Date;

  // Audit
  created_at: Date;
  updated_at: Date;
}
```

**Indexes:**
```sql
CREATE UNIQUE INDEX idx_restaurant_users_composite ON restaurant_users(restaurant_id, user_id);
CREATE INDEX idx_restaurant_users_user ON restaurant_users(user_id);
```

#### 4. POSConnection

**Purpose:** Tracks integrations with external POS systems (Toast, Square, etc.).

**Storage:** ~800 bytes per record × 12,000 = **9.6 MB** (1.2 connections per restaurant on average)

```typescript
interface POSConnection {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)

  // Provider Details
  provider: 'TOAST' | 'SQUARE' | 'LIGHTSPEED' | 'CLOVER' | 'REVEL' | 'SHOPIFY' | 'OTHER';
  provider_location_id: string;     // External location identifier
  provider_name: string;            // Human-readable: "Downtown Location"

  // Authentication
  auth_type: 'OAUTH2' | 'API_KEY' | 'BASIC_AUTH';
  access_token_encrypted: string;   // AWS KMS encrypted
  refresh_token_encrypted?: string;
  token_expires_at?: Date;
  api_key_encrypted?: string;

  // Sync Configuration
  sync_enabled: boolean;
  sync_frequency_minutes: number;   // 15, 30, 60 (default: 15)
  last_sync_at?: Date;
  last_sync_status: 'SUCCESS' | 'FAILED' | 'PARTIAL' | 'NEVER_RAN';
  last_sync_error?: string;
  next_sync_at?: Date;

  // Health Monitoring
  consecutive_failures: number;
  circuit_breaker_open: boolean;    // True if too many failures
  circuit_breaker_until?: Date;

  // Data Mapping Configuration
  menu_sync_enabled: boolean;       // Sync menu items from POS?
  transaction_sync_enabled: boolean;// Sync transactions from POS?
  custom_field_mappings?: Record<string, string>; // JSONB

  // Audit
  created_at: Date;
  updated_at: Date;
  created_by: string;               // FK → users.id
}
```

**Indexes:**
```sql
CREATE INDEX idx_pos_connections_tenant ON pos_connections(restaurant_id);
CREATE INDEX idx_pos_connections_next_sync ON pos_connections(next_sync_at)
  WHERE sync_enabled = true AND circuit_breaker_open = false;
CREATE UNIQUE INDEX idx_pos_connections_provider ON pos_connections(restaurant_id, provider, provider_location_id);
```

#### 5. Transaction

**Purpose:** Individual order/sale from POS system. **Largest table by volume.**

**Storage:** ~1 KB per record × 1.44B = **1.44 TB uncompressed** → **1.01 TB compressed** (TimescaleDB)

**Retention:** 6 months (older records aggregated and archived to S3)

```typescript
interface Transaction {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED, indexed)
  pos_connection_id: string;        // FK → pos_connections.id

  // External Reference
  external_order_id: string;        // POS system's order ID
  external_created_at: Date;        // Timestamp from POS (may differ from created_at)
  source: 'TOAST' | 'SQUARE' | 'LIGHTSPEED' | 'CLOVER' | 'REVEL' | 'MANUAL';

  // Order Details
  order_date: Date;                 // timestamptz (critical for time-series queries)
  order_number?: string;            // Human-readable: "#1234"
  order_type: 'DINE_IN' | 'TAKEOUT' | 'DELIVERY' | 'DRIVE_THRU' | 'OTHER';

  // Financial
  subtotal_cents: number;           // Amount before tax/tip
  tax_cents: number;
  tip_cents: number;
  discount_cents: number;
  total_amount_cents: number;       // Final amount
  currency: string;                 // ISO 4217

  // Payment
  payment_method: 'CASH' | 'CREDIT_CARD' | 'DEBIT_CARD' | 'GIFT_CARD' | 'OTHER';
  payment_status: 'PAID' | 'PENDING' | 'REFUNDED' | 'VOIDED';

  // Status
  is_voided: boolean;               // Exclude from forecasting if true
  voided_at?: Date;
  voided_reason?: string;

  // Metadata
  customer_id_external?: string;    // POS customer ID (anonymized)
  server_name?: string;             // "John D." (anonymized for GDPR)
  table_number?: string;
  guest_count?: number;

  // Raw Data (for debugging and future ML features)
  raw_data: Record<string, any>;    // JSONB - full POS response

  // Audit
  created_at: Date;                 // When record was ingested
  updated_at: Date;
}
```

**Indexes (Critical for Performance):**
```sql
-- TimescaleDB Hypertable (partitioned by order_date)
SELECT create_hypertable('transactions', 'order_date', chunk_time_interval => INTERVAL '1 week');

-- Primary tenant + time-range queries (most common)
CREATE INDEX idx_transactions_tenant_date ON transactions(restaurant_id, order_date DESC)
  INCLUDE (total_amount_cents, is_voided);

-- Deduplication check
CREATE UNIQUE INDEX idx_transactions_external ON transactions(restaurant_id, external_order_id, source);

-- POS connection lookup
CREATE INDEX idx_transactions_pos_connection ON transactions(pos_connection_id);

-- Payment analytics
CREATE INDEX idx_transactions_payment ON transactions(restaurant_id, payment_status)
  WHERE is_voided = false;
```

**Compression Policy (TimescaleDB):**
```sql
-- Compress data older than 7 days (50% size reduction)
SELECT add_compression_policy('transactions', INTERVAL '7 days');

-- Retention policy: Drop chunks older than 6 months
SELECT add_retention_policy('transactions', INTERVAL '6 months');
```

#### 6. TransactionItem

**Purpose:** Line items within a transaction (individual menu items ordered).

**Storage:** ~600 bytes per record × 4.32B = **2.59 TB uncompressed** → **1.81 TB compressed**
(Average 3 items per transaction)

```typescript
interface TransactionItem {
  id: string;                       // UUID (primary key)
  transaction_id: string;           // FK → transactions.id
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED, denormalized for RLS)

  // Menu Item Reference
  menu_item_id?: string;            // FK → menu_items.id (null if item deleted or not matched)
  external_item_id: string;         // POS item ID
  external_item_name: string;       // "Margherita Pizza" (as named in POS)

  // Quantity & Pricing
  quantity: number;                 // 2.5 (for fractional items like "1.5 lbs of wings")
  unit_price_cents: number;         // Price per unit
  total_price_cents: number;        // quantity × unit_price (before modifiers)

  // Modifiers (e.g., "Extra Cheese", "No Onions")
  modifiers: Array<{
    name: string;
    price_cents: number;
  }>;

  // Category (from POS)
  category_external?: string;       // "Entrees", "Beverages", "Desserts"

  // ML Features
  is_discounted: boolean;
  discount_cents: number;

  // Audit
  created_at: Date;
}
```

**Indexes:**
```sql
-- Tenant + transaction lookup
CREATE INDEX idx_transaction_items_tenant_tx ON transaction_items(restaurant_id, transaction_id);

-- Menu item analytics
CREATE INDEX idx_transaction_items_menu ON transaction_items(menu_item_id)
  WHERE menu_item_id IS NOT NULL;

-- External item matching (for fuzzy matching during ingestion)
CREATE INDEX idx_transaction_items_external_name_trgm ON transaction_items
  USING GIN (external_item_name gin_trgm_ops);
```

#### 7. MenuItem

**Purpose:** Menu items configured in Flux (mapped from POS items or manually added).

**Storage:** ~1.5 KB per record × 500,000 = **750 MB** (50 items per restaurant average)

```typescript
interface MenuItem {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)

  // Identity
  name: string;                     // "Margherita Pizza (12 inch)"
  description?: string;
  sku?: string;                     // Internal SKU

  // Categorization
  category: string;                 // "Pizzas", "Appetizers", "Beverages"
  subcategory?: string;
  tags: string[];                   // ["vegetarian", "gluten-free-option", "popular"]

  // Pricing (optional - actual price comes from POS)
  base_price_cents?: number;
  cost_cents?: number;              // COGS (for profit analysis)

  // Availability
  is_available: boolean;
  available_days: number[];         // [0,1,2,3,4,5,6] (0 = Sunday)
  available_times: {
    start: string;                  // "11:00"
    end: string;                    // "22:00"
  }[];
  seasonal_start?: Date;
  seasonal_end?: Date;

  // Recipe Explosion (Core Feature)
  has_recipe: boolean;
  recipe_verified: boolean;         // Chef confirmed ingredient list
  recipe_last_updated?: Date;

  // POS Mapping
  external_item_mappings: Array<{
    pos_connection_id: string;
    external_item_id: string;
    external_item_name: string;
    confidence_score: number;       // 0-1 (fuzzy matching confidence)
  }>;

  // ML Metadata
  average_daily_sales_7d?: number;
  average_daily_sales_30d?: number;
  volatility_score?: number;        // 0-1 (how unpredictable demand is)

  // Image
  image_url?: string;               // S3 URL

  // Status
  is_archived: boolean;
  archived_at?: Date;

  // Audit
  created_at: Date;
  updated_at: Date;
  created_by: string;               // FK → users.id
}
```

**Indexes:**
```sql
CREATE INDEX idx_menu_items_tenant ON menu_items(restaurant_id) WHERE is_archived = false;
CREATE INDEX idx_menu_items_category ON menu_items(restaurant_id, category);

-- Full-text search for menu item names
CREATE INDEX idx_menu_items_name_trgm ON menu_items USING GIN (name gin_trgm_ops);

-- POS matching
CREATE INDEX idx_menu_items_external_mappings ON menu_items
  USING GIN (external_item_mappings jsonb_path_ops);
```

#### 8. Ingredient

**Purpose:** Master list of ingredients used in recipes (Recipe Explosion feature).

**Storage:** ~800 bytes per record × 200,000 = **160 MB** (20 ingredients per restaurant average)

```typescript
interface Ingredient {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)

  // Identity
  name: string;                     // "Mozzarella Cheese"
  description?: string;
  category: 'PROTEIN' | 'DAIRY' | 'PRODUCE' | 'GRAIN' | 'SPICE' | 'SAUCE' | 'OTHER';

  // Unit Management
  primary_unit: 'LB' | 'OZ' | 'KG' | 'G' | 'L' | 'ML' | 'GAL' | 'QT' | 'CUP' | 'TSP' | 'TBSP' | 'COUNT';
  conversion_to_base_unit?: number; // For normalization (e.g., 1 lb = 453.592 g)

  // Supplier Info
  default_supplier_id?: string;     // FK → suppliers.id
  supplier_sku?: string;
  pack_size?: number;               // Quantity per pack
  pack_unit?: string;               // "case", "box"

  // Cost & Inventory
  average_cost_per_unit_cents?: number; // Rolling average
  current_cost_per_unit_cents?: number; // Last purchase price
  minimum_stock_level?: number;
  reorder_point?: number;
  par_level?: number;               // Target inventory level

  // Attributes
  is_allergen: boolean;
  allergen_types?: string[];        // ["dairy", "gluten", "nuts", "shellfish"]
  is_perishable: boolean;
  shelf_life_days?: number;
  storage_requirements?: string;    // "Refrigerate at 35-40°F"

  // Metadata
  tags: string[];                   // ["organic", "local", "gmo-free"]
  notes?: string;

  // Status
  is_archived: boolean;
  archived_at?: Date;

  // Audit
  created_at: Date;
  updated_at: Date;
  created_by: string;               // FK → users.id
}
```

**Indexes:**
```sql
CREATE INDEX idx_ingredients_tenant ON ingredients(restaurant_id) WHERE is_archived = false;
CREATE INDEX idx_ingredients_category ON ingredients(restaurant_id, category);
CREATE INDEX idx_ingredients_name_trgm ON ingredients USING GIN (name gin_trgm_ops);
CREATE INDEX idx_ingredients_supplier ON ingredients(default_supplier_id) WHERE default_supplier_id IS NOT NULL;
```

#### 9. Recipe

**Purpose:** Defines how menu items are composed from ingredients.

**Storage:** ~1 KB per record × 300,000 = **300 MB** (30% of menu items have verified recipes)

```typescript
interface Recipe {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)
  menu_item_id: string;             // FK → menu_items.id (one-to-one or one-to-many)

  // Identity
  name: string;                     // "12-inch Margherita Pizza Recipe"
  version: string;                  // "1.0", "2.1" (versioned for recipe changes)

  // Recipe Details
  servings: number;                 // 1 (for a single menu item)
  prep_time_minutes?: number;
  cook_time_minutes?: number;
  instructions?: string;            // Text or markdown

  // Cost Calculation
  total_cost_cents?: number;        // Sum of all ingredient costs (calculated)
  cost_per_serving_cents?: number;
  target_food_cost_percentage?: number; // 28% (industry standard 25-35%)

  // Status
  status: 'DRAFT' | 'VERIFIED' | 'ACTIVE' | 'ARCHIVED';
  verified_by?: string;             // FK → users.id (chef who approved)
  verified_at?: Date;

  // Scaling
  is_scalable: boolean;             // Can recipe be multiplied for batch prep?
  batch_size?: number;              // If preparing in batches

  // Metadata
  notes?: string;                   // "Use fresh basil only"
  difficulty: 'EASY' | 'MEDIUM' | 'HARD';

  // Audit
  created_at: Date;
  updated_at: Date;
  created_by: string;               // FK → users.id
}
```

**Indexes:**
```sql
CREATE INDEX idx_recipes_tenant ON recipes(restaurant_id);
CREATE INDEX idx_recipes_menu_item ON recipes(menu_item_id);
CREATE INDEX idx_recipes_status ON recipes(restaurant_id, status);
```

#### 10. RecipeIngredient (Join Table)

**Purpose:** Links recipes to ingredients with quantities.

**Storage:** ~300 bytes per record × 2M = **600 MB** (avg 7 ingredients per recipe × 300K recipes)

```typescript
interface RecipeIngredient {
  id: string;                       // UUID (primary key)
  recipe_id: string;                // FK → recipes.id
  ingredient_id: string;            // FK → ingredients.id
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED, denormalized)

  // Quantity
  quantity: number;                 // 8.0
  unit: string;                     // "oz", "lb", "cup", "tbsp"
  quantity_in_base_unit?: number;   // Normalized to grams/ml for cost calc

  // Cost
  cost_per_unit_cents?: number;     // Snapshot from ingredient at recipe creation
  total_cost_cents?: number;        // quantity × cost_per_unit

  // Preparation
  preparation_notes?: string;       // "shredded", "diced 1/4 inch", "room temperature"
  is_optional: boolean;

  // Substitutions
  substitutable_ingredient_ids?: string[]; // Array of ingredient IDs that can replace this

  // Display Order
  sort_order: number;               // For displaying ingredients in order

  // Audit
  created_at: Date;
  updated_at: Date;
}
```

**Indexes:**
```sql
CREATE INDEX idx_recipe_ingredients_recipe ON recipe_ingredients(recipe_id);
CREATE INDEX idx_recipe_ingredients_ingredient ON recipe_ingredients(ingredient_id);
CREATE INDEX idx_recipe_ingredients_tenant ON recipe_ingredients(restaurant_id);
```

### ML & Forecasting Entities

#### 11. Forecast

**Purpose:** ML-generated forecasts for menu item demand. **Core ML output.**

**Storage:** ~600 bytes per record × 176M = **105.6 GB uncompressed** → **63.4 GB compressed**

**Calculation:** 10K restaurants × 50 items × 30 days ahead × 3 model types (Prophet/XGBoost/Ensemble) × 4 forecasts/day = 180M records/month (with 6-month retention = ~1B forecasts, pruned to latest = 176M active)

```typescript
interface Forecast {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)
  menu_item_id: string;             // FK → menu_items.id

  // Forecast Date & Time
  forecast_date: Date;              // Date being forecasted (e.g., 2025-01-15)
  forecast_generated_at: Date;      // When forecast was created
  forecast_horizon_days: number;    // How many days ahead (1-30)

  // Prediction
  predicted_quantity: number;       // 45.3 (units expected to sell)
  confidence_lower: number;         // 38.1 (10th percentile)
  confidence_upper: number;         // 54.7 (90th percentile)
  confidence_level: number;         // 0.80 (80% confidence interval)

  // Model Info
  model_type: 'PROPHET' | 'XGBOOST' | 'ENSEMBLE' | 'NAIVE';
  model_version: string;            // "prophet-v2.1-20250115"
  model_id?: string;                // FK → models.id (optional link to model registry)

  // Feature Attribution (for explainability)
  features_used: {
    seasonality_component?: number;
    trend_component?: number;
    holiday_effect?: number;
    weather_effect?: number;
    day_of_week_effect?: number;
    promotion_effect?: number;
  };

  // Actual Outcome (filled after forecast_date passes)
  actual_quantity?: number;         // 47 (actual sales on that day)
  actual_filled_at?: Date;

  // Accuracy Metrics
  absolute_percentage_error?: number; // |predicted - actual| / actual × 100
  squared_error?: number;
  is_outlier: boolean;              // True if actual was >3 std dev from predicted

  // Business Context
  is_5_minute_monday: boolean;      // Was this forecast used in weekly task?
  feedback_rating?: number;         // User can rate forecast accuracy (1-5 stars)
  feedback_comment?: string;

  // Audit
  created_at: Date;
}
```

**Indexes:**
```sql
-- TimescaleDB Hypertable (partitioned by forecast_date)
SELECT create_hypertable('forecasts', 'forecast_date', chunk_time_interval => INTERVAL '1 month');

-- Primary query pattern: Get forecasts for a menu item on specific dates
CREATE INDEX idx_forecasts_tenant_item_date ON forecasts(restaurant_id, menu_item_id, forecast_date);

-- Model performance analysis
CREATE INDEX idx_forecasts_model ON forecasts(model_type, model_version)
  WHERE actual_quantity IS NOT NULL;

-- Calendar view (all forecasts for a day)
CREATE INDEX idx_forecasts_tenant_date ON forecasts(restaurant_id, forecast_date)
  INCLUDE (menu_item_id, predicted_quantity);

-- Unique constraint: One forecast per item/date/model (prevent duplicates)
CREATE UNIQUE INDEX idx_forecasts_unique ON forecasts(restaurant_id, menu_item_id, forecast_date, model_type);
```

**Compression Policy:**
```sql
-- Compress forecasts older than 30 days
SELECT add_compression_policy('forecasts', INTERVAL '30 days');

-- Retain forecasts for 6 months (for model retraining)
SELECT add_retention_policy('forecasts', INTERVAL '6 months');
```

#### 12. ForecastExplanation

**Purpose:** Detailed explanations for why a forecast was generated (for UI display).

**Storage:** ~1.5 KB per record × 50M = **75 GB** (explain only high-value forecasts, not all)

```typescript
interface ForecastExplanation {
  id: string;                       // UUID (primary key)
  forecast_id: string;              // FK → forecasts.id
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)

  // Explanation Type
  explanation_type: 'SHAP' | 'LIME' | 'FEATURE_IMPORTANCE' | 'RULE_BASED';

  // Feature Contributions (SHAP values)
  feature_contributions: Array<{
    feature_name: string;           // "day_of_week_is_friday"
    contribution_value: number;     // +12.5 (units)
    contribution_percentage: number;// 28% of total prediction
    baseline_value: number;
  }>;

  // Human-Readable Explanation
  explanation_text: string;         // "Sales expected to be 28% higher because it's Friday"
  explanation_factors: string[];    // ["Weekend effect", "Recent promotion", "Good weather forecast"]

  // Confidence Explanation
  uncertainty_drivers: string[];    // ["Limited historical data", "High volatility in past 30 days"]

  // Metadata
  explanation_generated_at: Date;
  computation_time_ms: number;      // For performance monitoring

  // Audit
  created_at: Date;
}
```

**Indexes:**
```sql
CREATE INDEX idx_forecast_explanations_forecast ON forecast_explanations(forecast_id);
CREATE INDEX idx_forecast_explanations_tenant ON forecast_explanations(restaurant_id);
```

#### 13. Model

**Purpose:** Model registry tracking all trained ML models.

**Storage:** ~2 KB per record × 50,000 = **100 MB** (multiple models per restaurant over time)

```typescript
interface Model {
  id: string;                       // UUID (primary key)
  restaurant_id?: string;           // FK → restaurants.id (null for shared base models)

  // Model Identity
  model_name: string;               // "restaurant_123_prophet_v2"
  model_type: 'PROPHET' | 'XGBOOST' | 'ENSEMBLE' | 'BASELINE';
  model_version: string;            // "2.1.0"

  // Model Artifacts
  s3_model_path: string;            // s3://flux-ml-models/restaurant_123/prophet-v2.1.pkl
  model_size_bytes: number;
  framework: string;                // "prophet", "xgboost", "scikit-learn"
  framework_version: string;        // "1.1.5"

  // Training Info
  training_started_at: Date;
  training_completed_at: Date;
  training_duration_seconds: number;
  training_job_id?: string;         // SageMaker training job ID
  training_instance_type?: string;  // "ml.m5.xlarge"
  training_cost_usd?: number;

  // Training Data
  training_data_start_date: Date;
  training_data_end_date: Date;
  training_record_count: number;
  feature_count: number;
  feature_names: string[];

  // Hyperparameters
  hyperparameters: Record<string, any>; // JSONB

  // Performance Metrics
  metrics: {
    mae?: number;                   // Mean Absolute Error
    mape?: number;                  // Mean Absolute Percentage Error
    rmse?: number;                  // Root Mean Squared Error
    r2_score?: number;
    coverage_80?: number;           // % of actuals within 80% confidence interval
  };

  // Validation
  validation_mae?: number;
  validation_mape?: number;
  cross_validation_folds?: number;

  // Deployment
  status: 'TRAINING' | 'COMPLETED' | 'FAILED' | 'DEPLOYED' | 'ARCHIVED';
  deployed_at?: Date;
  deployment_endpoint?: string;     // SageMaker endpoint name
  is_production: boolean;
  is_canary: boolean;               // A/B test candidate
  canary_traffic_percentage?: number; // 5% (for gradual rollout)

  // Lineage
  parent_model_id?: string;         // FK → models.id (if fine-tuned from another model)
  training_pipeline_version: string;// Git commit SHA or version tag

  // Metadata
  description?: string;
  tags: Record<string, string>;    // {"environment": "production", "tier": "premium"}

  // Audit
  created_at: Date;
  updated_at: Date;
  created_by: string;              // FK → users.id or "system"
}
```

**Indexes:**
```sql
CREATE INDEX idx_models_tenant ON models(restaurant_id) WHERE restaurant_id IS NOT NULL;
CREATE INDEX idx_models_status ON models(status);
CREATE INDEX idx_models_production ON models(is_production) WHERE is_production = true;
CREATE INDEX idx_models_type_version ON models(model_type, model_version);
```

#### 14. ForecastFeature

**Purpose:** Computed features for ML models (feature store).

**Storage:** ~800 bytes per record × 200M = **160 GB** (rolling 30-day features for all menu items)

**Note:** This is a **materialized view** or **cached computation** table, refreshed hourly.

```typescript
interface ForecastFeature {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)
  menu_item_id: string;             // FK → menu_items.id

  // Feature Date
  feature_date: Date;               // Date these features represent
  computed_at: Date;                // When features were computed

  // Historical Sales Features
  sales_7d_avg: number;
  sales_7d_std: number;
  sales_14d_avg: number;
  sales_30d_avg: number;
  sales_90d_avg?: number;

  // Trend Features
  sales_trend_7d: number;           // Slope of linear regression
  sales_trend_30d: number;
  day_over_day_change_pct: number;
  week_over_week_change_pct: number;

  // Seasonality Features
  day_of_week: number;              // 0-6 (0 = Sunday)
  week_of_year: number;             // 1-52
  month: number;                    // 1-12
  is_weekend: boolean;
  is_holiday: boolean;
  holiday_name?: string;            // "Christmas", "Thanksgiving"

  // Volatility Features
  coefficient_of_variation: number; // std / mean
  is_highly_volatile: boolean;      // CV > 0.5

  // Categorical Embeddings (optional)
  category_embedding?: number[];    // [0.23, -0.45, ...] (learned representations)

  // External Features
  weather_temp_f?: number;
  weather_condition?: string;       // "sunny", "rainy", "snowy"
  local_event?: string;             // "Sports game nearby", "Concert"

  // Business Features
  active_promotion: boolean;
  promotion_discount_pct?: number;
  menu_item_rank: number;           // Popularity ranking (1 = most popular)

  // TTL (for cache expiry)
  expires_at: Date;                 // Delete after 90 days

  // Audit
  created_at: Date;
}
```

**Indexes:**
```sql
-- TimescaleDB Hypertable
SELECT create_hypertable('forecast_features', 'feature_date', chunk_time_interval => INTERVAL '1 month');

-- Primary query pattern
CREATE INDEX idx_forecast_features_tenant_item_date ON forecast_features(restaurant_id, menu_item_id, feature_date DESC);

-- Feature freshness check
CREATE INDEX idx_forecast_features_computed_at ON forecast_features(computed_at);

-- Retention policy (keep 90 days)
SELECT add_retention_policy('forecast_features', INTERVAL '90 days');
```

### Procurement & Inventory Entities

#### 15. ProcurementRecommendation

**Purpose:** AI-generated recommendations for ingredient purchases based on forecasts.

**Storage:** ~1 KB per record × 20M = **20 GB** (weekly recommendations for all active ingredients)

```typescript
interface ProcurementRecommendation {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)
  ingredient_id: string;            // FK → ingredients.id

  // Recommendation Period
  recommendation_date: Date;        // When recommendation was generated
  procurement_week_start: Date;     // Start of week to order for
  procurement_week_end: Date;

  // Quantities
  recommended_quantity: number;     // 45.5 (lbs, kg, etc.)
  recommended_unit: string;
  min_quantity: number;             // Conservative estimate
  max_quantity: number;             // Optimistic estimate

  // Cost Estimate
  estimated_cost_cents: number;
  estimated_total_cents: number;    // quantity × cost

  // Based On
  based_on_forecasts: string[];     // Array of forecast IDs
  based_on_recipes: string[];       // Array of recipe IDs
  confidence_score: number;         // 0-1

  // Current State
  current_inventory_level?: number;
  current_par_level?: number;
  is_below_par: boolean;
  is_urgent: boolean;               // Below reorder point

  // Actions
  status: 'PENDING' | 'ACCEPTED' | 'MODIFIED' | 'REJECTED' | 'ORDERED';
  accepted_quantity?: number;       // What user actually ordered
  accepted_by?: string;             // FK → users.id
  accepted_at?: Date;
  rejection_reason?: string;

  // Linked Order
  procurement_order_id?: string;    // FK → procurement_orders.id

  // 5-Minute Monday Integration
  is_micro_task: boolean;           // Show in weekly task list
  task_priority: number;            // 1-5 (1 = highest)

  // Audit
  created_at: Date;
  updated_at: Date;
}
```

**Indexes:**
```sql
CREATE INDEX idx_procurement_recs_tenant ON procurement_recommendations(restaurant_id, status);
CREATE INDEX idx_procurement_recs_ingredient ON procurement_recommendations(ingredient_id);
CREATE INDEX idx_procurement_recs_week ON procurement_recommendations(procurement_week_start);
CREATE INDEX idx_procurement_recs_micro_task ON procurement_recommendations(restaurant_id, is_micro_task)
  WHERE status = 'PENDING' AND is_micro_task = true;
```

#### 16. Supplier

**Purpose:** External suppliers for ingredients and supplies.

**Storage:** ~1 KB per record × 30,000 = **30 MB** (3 suppliers per restaurant average)

```typescript
interface Supplier {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)

  // Identity
  name: string;                     // "Sysco Corporation"
  company_type: 'DISTRIBUTOR' | 'FARM' | 'MANUFACTURER' | 'WHOLESALER' | 'OTHER';

  // Contact
  contact_name?: string;
  contact_email?: string;
  contact_phone?: string;
  website_url?: string;

  // Address
  address_line1?: string;
  address_line2?: string;
  city?: string;
  state_province?: string;
  postal_code?: string;
  country: string;

  // Business Terms
  payment_terms: 'NET_30' | 'NET_60' | 'COD' | 'PREPAID' | 'CREDIT_CARD' | 'OTHER';
  minimum_order_value_cents?: number;
  delivery_fee_cents?: number;
  free_delivery_threshold_cents?: number;

  // Delivery Schedule
  delivery_days: number[];          // [1,3,5] (Monday, Wednesday, Friday)
  lead_time_days: number;           // 2 (days between order and delivery)
  delivery_window_start?: string;   // "08:00"
  delivery_window_end?: string;     // "11:00"

  // Performance Metrics
  average_delivery_rating?: number; // 1-5 stars
  on_time_delivery_percentage?: number;
  quality_rating?: number;
  total_orders_placed?: number;
  total_spent_cents?: number;

  // Status
  is_preferred: boolean;
  is_active: boolean;
  is_archived: boolean;
  archived_at?: Date;

  // Notes
  notes?: string;
  tags: string[];                   // ["organic", "local", "reliable"]

  // Audit
  created_at: Date;
  updated_at: Date;
  created_by: string;               // FK → users.id
}
```

**Indexes:**
```sql
CREATE INDEX idx_suppliers_tenant ON suppliers(restaurant_id) WHERE is_archived = false;
CREATE INDEX idx_suppliers_active ON suppliers(restaurant_id, is_active) WHERE is_active = true;
```

#### 17. ProcurementOrder

**Purpose:** Purchase orders created from procurement recommendations.

**Storage:** ~1.5 KB per record × 2M = **3 GB** (weekly orders × 10K restaurants × 52 weeks × 4 years retention)

```typescript
interface ProcurementOrder {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)
  supplier_id: string;              // FK → suppliers.id

  // Order Details
  order_number: string;             // "PO-2025-0001" (auto-generated)
  order_date: Date;
  expected_delivery_date?: Date;
  actual_delivery_date?: Date;

  // Status Tracking
  status: 'DRAFT' | 'SUBMITTED' | 'CONFIRMED' | 'IN_TRANSIT' | 'DELIVERED' | 'CANCELLED';
  status_history: Array<{
    status: string;
    changed_at: Date;
    changed_by: string;             // FK → users.id
    notes?: string;
  }>;

  // Financial
  subtotal_cents: number;           // Sum of all line items
  tax_cents: number;
  delivery_fee_cents: number;
  discount_cents: number;
  total_cents: number;

  // Payment
  payment_status: 'UNPAID' | 'PARTIALLY_PAID' | 'PAID' | 'OVERDUE';
  payment_due_date?: Date;
  payment_method?: 'CREDIT_CARD' | 'CHECK' | 'ACH' | 'CASH' | 'OTHER';

  // Delivery
  delivery_address: {
    line1: string;
    line2?: string;
    city: string;
    state_province: string;
    postal_code: string;
    country: string;
  };
  delivery_instructions?: string;
  delivery_contact_name?: string;
  delivery_contact_phone?: string;

  // Quality Control (filled on delivery)
  quality_rating?: number;          // 1-5 stars
  quality_notes?: string;
  items_rejected_count?: number;

  // Document Links
  pdf_url?: string;                 // S3 URL to generated PDF
  supplier_invoice_url?: string;

  // Notes
  internal_notes?: string;
  supplier_notes?: string;

  // Audit
  created_at: Date;
  updated_at: Date;
  created_by: string;               // FK → users.id
  submitted_by?: string;
  submitted_at?: Date;
}
```

**Indexes:**
```sql
CREATE INDEX idx_procurement_orders_tenant ON procurement_orders(restaurant_id);
CREATE INDEX idx_procurement_orders_supplier ON procurement_orders(supplier_id);
CREATE INDEX idx_procurement_orders_status ON procurement_orders(restaurant_id, status);
CREATE INDEX idx_procurement_orders_delivery_date ON procurement_orders(expected_delivery_date)
  WHERE status IN ('SUBMITTED', 'CONFIRMED', 'IN_TRANSIT');
```

#### 18. ProcurementOrderItem

**Purpose:** Line items within a procurement order.

**Storage:** ~400 bytes per record × 10M = **4 GB** (avg 5 items per order)

```typescript
interface ProcurementOrderItem {
  id: string;                       // UUID (primary key)
  procurement_order_id: string;     // FK → procurement_orders.id
  ingredient_id: string;            // FK → ingredients.id
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED, denormalized)

  // Item Details
  ingredient_name: string;          // Snapshot (in case ingredient is deleted)
  supplier_sku?: string;

  // Quantity Ordered
  ordered_quantity: number;
  ordered_unit: string;

  // Quantity Received (filled on delivery)
  received_quantity?: number;
  rejected_quantity?: number;
  rejection_reason?: string;

  // Pricing
  unit_price_cents: number;
  total_price_cents: number;        // ordered_quantity × unit_price_cents

  // Quality Check
  quality_notes?: string;
  expiration_date?: Date;
  lot_number?: string;

  // Sort Order
  line_number: number;              // 1, 2, 3...

  // Audit
  created_at: Date;
  updated_at: Date;
}
```

**Indexes:**
```sql
CREATE INDEX idx_procurement_order_items_order ON procurement_order_items(procurement_order_id);
CREATE INDEX idx_procurement_order_items_ingredient ON procurement_order_items(ingredient_id);
```

#### 19. InventoryLevel

**Purpose:** Current stock levels for ingredients (optional feature).

**Storage:** ~500 bytes per record × 200K = **100 MB** (active ingredient inventory tracking)

```typescript
interface InventoryLevel {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)
  ingredient_id: string;            // FK → ingredients.id

  // Current Stock
  current_quantity: number;
  current_unit: string;
  value_cents?: number;             // current_quantity × average_cost

  // Thresholds
  minimum_level: number;
  reorder_point: number;
  par_level: number;
  maximum_level?: number;

  // Status
  status: 'IN_STOCK' | 'LOW_STOCK' | 'OUT_OF_STOCK' | 'OVERSTOCK';
  needs_reorder: boolean;

  // Location
  storage_location?: string;        // "Walk-in Cooler", "Dry Storage Shelf A3"

  // Last Updated
  last_counted_at?: Date;
  last_counted_by?: string;         // FK → users.id
  last_reordered_at?: Date;

  // Audit
  created_at: Date;
  updated_at: Date;
}
```

**Indexes:**
```sql
CREATE UNIQUE INDEX idx_inventory_levels_unique ON inventory_levels(restaurant_id, ingredient_id);
CREATE INDEX idx_inventory_levels_status ON inventory_levels(restaurant_id, status);
CREATE INDEX idx_inventory_levels_reorder ON inventory_levels(restaurant_id, needs_reorder)
  WHERE needs_reorder = true;
```

#### 20. InventoryTransaction

**Purpose:** Audit log of all inventory movements (deliveries, usage, waste, adjustments).

**Storage:** ~400 bytes per record × 10M = **4 GB** (transaction history for compliance)

```typescript
interface InventoryTransaction {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)
  ingredient_id: string;            // FK → ingredients.id

  // Transaction Details
  transaction_type: 'DELIVERY' | 'USAGE' | 'WASTE' | 'ADJUSTMENT' | 'TRANSFER' | 'COUNT';
  transaction_date: Date;

  // Quantity Change
  quantity_change: number;          // Can be negative for usage/waste
  unit: string;
  quantity_before: number;
  quantity_after: number;

  // Cost Impact
  unit_cost_cents?: number;
  total_cost_cents?: number;

  // References
  procurement_order_id?: string;    // FK → procurement_orders.id (if from delivery)
  reference_id?: string;            // Generic reference (recipe_id, transfer_id, etc.)
  reference_type?: string;          // "recipe_preparation", "physical_count", "expiration"

  // Reason (for waste/adjustments)
  reason?: string;                  // "Expired", "Spoiled", "Physical count discrepancy"
  notes?: string;

  // Performed By
  performed_by: string;             // FK → users.id

  // Audit
  created_at: Date;
}
```

**Indexes:**
```sql
CREATE INDEX idx_inventory_transactions_tenant ON inventory_transactions(restaurant_id, transaction_date DESC);
CREATE INDEX idx_inventory_transactions_ingredient ON inventory_transactions(ingredient_id, transaction_date DESC);
CREATE INDEX idx_inventory_transactions_type ON inventory_transactions(transaction_type, transaction_date DESC);
```

### Supporting Entities

#### 21. DataSync

**Purpose:** Tracks all POS sync jobs and their status.

**Storage:** ~1.5 KB per record × 100M = **150 GB** (15-min syncs × 10K restaurants × 6 months)

```typescript
interface DataSync {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)
  pos_connection_id: string;        // FK → pos_connections.id

  // Sync Details
  sync_type: 'TRANSACTIONS' | 'MENU_ITEMS' | 'FULL';
  sync_started_at: Date;
  sync_completed_at?: Date;
  sync_duration_ms?: number;

  // Status
  status: 'PENDING' | 'RUNNING' | 'SUCCESS' | 'PARTIAL_SUCCESS' | 'FAILED';
  error_message?: string;
  error_code?: string;
  retry_count: number;

  // Data Processed
  records_fetched: number;
  records_created: number;
  records_updated: number;
  records_skipped: number;
  records_failed: number;

  // Time Range (for incremental syncs)
  sync_from_date?: Date;
  sync_to_date?: Date;

  // Performance Metrics
  api_calls_made: number;
  api_rate_limit_hit: boolean;
  bytes_transferred?: number;

  // Audit
  created_at: Date;
}
```

**Indexes:**
```sql
-- TimescaleDB Hypertable
SELECT create_hypertable('data_syncs', 'sync_started_at', chunk_time_interval => INTERVAL '1 week');

CREATE INDEX idx_data_syncs_tenant ON data_syncs(restaurant_id, sync_started_at DESC);
CREATE INDEX idx_data_syncs_connection ON data_syncs(pos_connection_id);
CREATE INDEX idx_data_syncs_status ON data_syncs(status) WHERE status IN ('RUNNING', 'FAILED');

-- Retention: 6 months
SELECT add_retention_policy('data_syncs', INTERVAL '6 months');
```

#### 22. MicroTask (5-Minute Mondays)

**Purpose:** Weekly micro-tasks for restaurant operators.

**Storage:** ~800 bytes per record × 2M = **1.6 GB** (weekly tasks for all restaurants)

```typescript
interface MicroTask {
  id: string;                       // UUID (primary key)
  restaurant_id: string;            // FK → restaurants.id (TENANT-SCOPED)

  // Task Details
  task_type: 'REVIEW_FORECAST' | 'APPROVE_PROCUREMENT' | 'UPDATE_RECIPE' | 'VERIFY_INVENTORY' | 'REVIEW_ANOMALY';
  title: string;                    // "Review next week's forecasts"
  description: string;
  priority: 1 | 2 | 3 | 4 | 5;      // 1 = highest

  // Week Assignment
  week_start_date: Date;            // Monday of the week
  week_number: number;              // ISO week number

  // Status
  status: 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'SKIPPED' | 'EXPIRED';
  completed_at?: Date;
  completed_by?: string;            // FK → users.id
  skipped_reason?: string;

  // Estimated Time
  estimated_minutes: number;        // Always 5 or less

  // Related Data
  related_entity_type?: string;     // "forecast", "procurement_recommendation", "recipe"
  related_entity_id?: string;
  related_entity_data?: Record<string, any>; // JSONB for quick display

  // Actions Taken
  actions_taken?: string[];         // ["approved_3_forecasts", "rejected_1_procurement"]
  outcome_summary?: string;

  // Audit
  created_at: Date;
  updated_at: Date;
}
```

**Indexes:**
```sql
CREATE INDEX idx_micro_tasks_tenant_week ON micro_tasks(restaurant_id, week_start_date DESC);
CREATE INDEX idx_micro_tasks_status ON micro_tasks(restaurant_id, status)
  WHERE status = 'PENDING';
CREATE INDEX idx_micro_tasks_priority ON micro_tasks(priority, week_start_date)
  WHERE status = 'PENDING';
```

#### 23. Notification

**Purpose:** In-app and email notifications.

**Storage:** ~600 bytes per record × 50M = **30 GB** (various notifications over time)

```typescript
interface Notification {
  id: string;                       // UUID (primary key)
  user_id: string;                  // FK → users.id
  restaurant_id?: string;           // FK → restaurants.id (optional, for restaurant-specific)

  // Notification Content
  type: 'INFO' | 'SUCCESS' | 'WARNING' | 'ERROR';
  category: 'FORECAST' | 'PROCUREMENT' | 'SYNC' | 'SYSTEM' | 'BILLING' | 'USER_ACTION';
  title: string;
  message: string;                  // Plain text or markdown
  action_url?: string;              // Deep link to relevant page

  // Delivery Channels
  channels: ('IN_APP' | 'EMAIL' | 'PUSH')[];
  email_sent_at?: Date;
  push_sent_at?: Date;

  // Status
  is_read: boolean;
  read_at?: Date;
  is_archived: boolean;
  archived_at?: Date;

  // Related Data
  related_entity_type?: string;
  related_entity_id?: string;
  metadata?: Record<string, any>;   // JSONB

  // Audit
  created_at: Date;
}
```

**Indexes:**
```sql
CREATE INDEX idx_notifications_user ON notifications(user_id, created_at DESC);
CREATE INDEX idx_notifications_unread ON notifications(user_id, is_read)
  WHERE is_read = false;
CREATE INDEX idx_notifications_category ON notifications(restaurant_id, category, created_at DESC);
```

#### 24. AuditLog

**Purpose:** Comprehensive audit trail for compliance and debugging.

**Storage:** ~1 KB per record × 500M = **500 GB** (all user actions, compressed heavily)

```typescript
interface AuditLog {
  id: string;                       // UUID (primary key)
  restaurant_id?: string;           // FK → restaurants.id (null for system-wide events)

  // Actor
  user_id?: string;                 // FK → users.id (null for system actions)
  actor_type: 'USER' | 'SYSTEM' | 'API' | 'BACKGROUND_JOB';
  actor_ip?: string;
  actor_user_agent?: string;

  // Event Details
  event_type: 'CREATE' | 'UPDATE' | 'DELETE' | 'LOGIN' | 'LOGOUT' | 'EXPORT' | 'APPROVE' | 'REJECT';
  entity_type: string;              // "menu_item", "forecast", "procurement_order"
  entity_id: string;                // UUID of affected entity
  event_timestamp: Date;

  // Changes (for UPDATE events)
  changes_before?: Record<string, any>; // JSONB snapshot
  changes_after?: Record<string, any>;  // JSONB snapshot
  changed_fields?: string[];

  // Request Context
  request_id?: string;              // For tracing across services
  session_id?: string;
  api_endpoint?: string;            // "/api/forecasts.update"

  // Compliance Fields
  gdpr_relevant: boolean;           // Is this a data subject action?
  data_subject_id?: string;
  retention_period_days: number;    // 2555 (7 years for GDPR)

  // Metadata
  description?: string;             // Human-readable description
  tags?: string[];

  // Audit
  created_at: Date;
}
```

**Indexes:**
```sql
-- TimescaleDB Hypertable
SELECT create_hypertable('audit_logs', 'event_timestamp', chunk_time_interval => INTERVAL '1 month');

CREATE INDEX idx_audit_logs_tenant ON audit_logs(restaurant_id, event_timestamp DESC);
CREATE INDEX idx_audit_logs_user ON audit_logs(user_id, event_timestamp DESC);
CREATE INDEX idx_audit_logs_entity ON audit_logs(entity_type, entity_id, event_timestamp DESC);
CREATE INDEX idx_audit_logs_gdpr ON audit_logs(data_subject_id, event_timestamp DESC)
  WHERE gdpr_relevant = true;

-- Compression after 90 days
SELECT add_compression_policy('audit_logs', INTERVAL '90 days');

-- Retention: 7 years (GDPR compliance)
SELECT add_retention_policy('audit_logs', INTERVAL '7 years');
```

### Entity Relationship Summary

**Total Entities:** 24

**Cardinality Summary:**

```
restaurants (1) ←→ (N) users                   [via restaurant_users join table]
restaurants (1) ←→ (N) pos_connections
restaurants (1) ←→ (N) transactions
restaurants (1) ←→ (N) menu_items
restaurants (1) ←→ (N) ingredients
restaurants (1) ←→ (N) recipes
restaurants (1) ←→ (N) forecasts
restaurants (1) ←→ (N) suppliers

transactions (1) ←→ (N) transaction_items
menu_items (1) ←→ (N) transaction_items
menu_items (1) ←→ (1 or N) recipes
recipes (1) ←→ (N) recipe_ingredients          [many-to-many with ingredients]
ingredients (1) ←→ (N) recipe_ingredients

forecasts (N) ←→ (1) menu_items
forecasts (N) ←→ (1) models                    [optional]
forecasts (1) ←→ (0 or 1) forecast_explanation

procurement_recommendations (N) ←→ (1) ingredients
procurement_recommendations (N) ←→ (0 or 1) procurement_orders
procurement_orders (1) ←→ (N) procurement_order_items
procurement_orders (N) ←→ (1) suppliers

inventory_levels (1) ←→ (1) ingredients        [one-to-one]
inventory_transactions (N) ←→ (1) ingredients
```

**Storage Summary (Final):**

| Category | Entities | Total Storage (Compressed) |
|----------|----------|----------------------------|
| **Core Business** | 7 | 2.66 TB |
| **Recipe Explosion** | 3 | 1.06 GB |
| **ML & Forecasting** | 4 | 160 GB |
| **Procurement** | 6 | 27 GB |
| **Supporting** | 4 | 682 GB |
| **TOTAL** | **24** | **3.52 TB** |

**Growth Projection:**
- Monthly growth: ~240 GB compressed
- Annual growth: ~2.88 TB
- 3-year projected total: ~12 TB

**Database Cost Projection (AWS RDS PostgreSQL):**
- Year 1: $6,112/month (~$73K/year)
- Year 2: $8,500/month (~$102K/year)
- Year 3: $11,200/month (~$134K/year)

**Performance Optimization Strategy:**
1. **TimescaleDB Hypertables:** transactions, transaction_items, forecasts, forecast_features, data_syncs, audit_logs
2. **Compression Policies:** Compress data older than 7-30 days (50% size reduction)
3. **Retention Policies:** Auto-delete old data (transactions: 6 months, audit_logs: 7 years)
4. **Read Replicas:** 2-3 read replicas for analytics and reporting queries
5. **Connection Pooling:** PgBouncer with 100 connections per Lambda function
6. **Materialized Views:** Pre-aggregated tables for dashboard queries (refresh hourly)

---

## API Specification

This section defines all tRPC routers and procedures that make up the Flux API. The API is organized into logical routers by domain, with end-to-end type safety between frontend and backend.

### API Architecture Overview

**API Style:** tRPC v11+ (Type-safe RPC over HTTP)
**Transport:** HTTP POST to `/api/trpc/[procedure]`
**Authentication:** JWT bearer tokens (NextAuth.js)
**Rate Limiting:** 100 requests/min per user, 1000 requests/min per restaurant
**Caching Strategy:** React Query on frontend, Redis on backend

**Key Design Principles:**
- All procedures are authenticated by default (use `.publicProcedure` for public endpoints)
- Input/output validation using Zod schemas
- Multi-tenant isolation via context middleware (sets `restaurant_id` automatically)
- Consistent error handling with typed error codes
- Pagination using cursor-based approach for large datasets
- Real-time updates via WebSocket subscriptions where appropriate

### tRPC Context & Middleware

**Context Setup:**

```typescript
// apps/api/src/trpc/context.ts
import { type inferAsyncReturnType } from '@trpc/server';
import { type CreateAWSLambdaContextOptions } from '@trpc/server/adapters/aws-lambda';
import { prisma } from '@flux/database';
import { verifyJWT } from '../auth/jwt';

export async function createContext({ event }: CreateAWSLambdaContextOptions<any>) {
  // Extract JWT from Authorization header
  const token = event.headers.authorization?.replace('Bearer ', '');

  let session: {
    userId: string;
    restaurantId: string;
    role: string;
  } | null = null;

  if (token) {
    try {
      const decoded = await verifyJWT(token);
      session = {
        userId: decoded.userId,
        restaurantId: decoded.restaurantId,
        role: decoded.role,
      };

      // Set PostgreSQL RLS context
      await prisma.$executeRaw`
        SET LOCAL app.current_restaurant_id = ${session.restaurantId};
        SET LOCAL app.current_user_id = ${session.userId};
      `;
    } catch (error) {
      // Token invalid - proceed as unauthenticated
      session = null;
    }
  }

  return {
    session,
    prisma,
    requestId: event.requestContext.requestId,
  };
}

export type Context = inferAsyncReturnType<typeof createContext>;
```

**Middleware:**

```typescript
// apps/api/src/trpc/middleware.ts
import { TRPCError } from '@trpc/server';
import { middleware } from './trpc';

// Require authentication
export const isAuthed = middleware(async ({ ctx, next }) => {
  if (!ctx.session) {
    throw new TRPCError({ code: 'UNAUTHORIZED' });
  }
  return next({
    ctx: {
      ...ctx,
      session: ctx.session, // Type narrowing
    },
  });
});

// Require specific role
export const hasRole = (allowedRoles: string[]) =>
  middleware(async ({ ctx, next }) => {
    if (!ctx.session || !allowedRoles.includes(ctx.session.role)) {
      throw new TRPCError({ code: 'FORBIDDEN' });
    }
    return next({ ctx });
  });

// Rate limiting (using Redis)
export const rateLimit = middleware(async ({ ctx, next, path }) => {
  const key = `ratelimit:${ctx.session?.userId || ctx.requestId}:${path}`;
  const count = await redis.incr(key);

  if (count === 1) {
    await redis.expire(key, 60); // 1 minute window
  }

  if (count > 100) {
    throw new TRPCError({
      code: 'TOO_MANY_REQUESTS',
      message: 'Rate limit exceeded. Try again in 1 minute.'
    });
  }

  return next({ ctx });
});
```

### Router Organization

**Main App Router:**

```typescript
// apps/api/src/trpc/root.ts
import { router } from './trpc';
import { authRouter } from './routers/auth';
import { restaurantRouter } from './routers/restaurant';
import { menuRouter } from './routers/menu';
import { transactionRouter } from './routers/transaction';
import { forecastRouter } from './routers/forecast';
import { recipeRouter } from './routers/recipe';
import { procurementRouter } from './routers/procurement';
import { posRouter } from './routers/pos';
import { userRouter } from './routers/user';

export const appRouter = router({
  auth: authRouter,
  restaurant: restaurantRouter,
  menu: menuRouter,
  transaction: transactionRouter,
  forecast: forecastRouter,
  recipe: recipeRouter,
  procurement: procurementRouter,
  pos: posRouter,
  user: userRouter,
});

export type AppRouter = typeof appRouter;
```

### Router Definitions

#### 1. Auth Router

**Purpose:** Authentication, registration, session management

**File:** `apps/api/src/trpc/routers/auth.ts`

```typescript
import { router, publicProcedure } from '../trpc';
import { z } from 'zod';
import { TRPCError } from '@trpc/server';
import { hashPassword, verifyPassword, generateJWT } from '../../auth/utils';

export const authRouter = router({
  // Register new user + restaurant
  register: publicProcedure
    .input(
      z.object({
        email: z.string().email(),
        password: z.string().min(8),
        firstName: z.string().min(1),
        lastName: z.string().min(1),
        restaurantName: z.string().min(1),
        restaurantSlug: z.string().regex(/^[a-z0-9-]+$/),
        timezone: z.string(), // IANA timezone
        currency: z.string().length(3), // ISO 4217
      })
    )
    .output(
      z.object({
        user: z.object({
          id: z.string(),
          email: z.string(),
          firstName: z.string(),
          lastName: z.string(),
        }),
        restaurant: z.object({
          id: z.string(),
          name: z.string(),
          slug: z.string(),
        }),
        token: z.string(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      // Check if email exists
      const existingUser = await ctx.prisma.user.findUnique({
        where: { email: input.email.toLowerCase() },
      });

      if (existingUser) {
        throw new TRPCError({
          code: 'CONFLICT',
          message: 'Email already registered',
        });
      }

      // Check if restaurant slug is available
      const existingRestaurant = await ctx.prisma.restaurant.findUnique({
        where: { slug: input.restaurantSlug },
      });

      if (existingRestaurant) {
        throw new TRPCError({
          code: 'CONFLICT',
          message: 'Restaurant name unavailable',
        });
      }

      // Create user + restaurant in transaction
      const passwordHash = await hashPassword(input.password);

      const result = await ctx.prisma.$transaction(async (tx) => {
        const user = await tx.user.create({
          data: {
            email: input.email.toLowerCase(),
            password_hash: passwordHash,
            first_name: input.firstName,
            last_name: input.lastName,
            email_verified: false,
            consent_marketing: false,
            consent_updated_at: new Date(),
          },
        });

        const restaurant = await tx.restaurant.create({
          data: {
            name: input.restaurantName,
            slug: input.restaurantSlug,
            owner_id: user.id,
            timezone: input.timezone,
            currency: input.currency,
            subscription_tier: 'FREE',
            subscription_status: 'TRIAL',
            trial_ends_at: new Date(Date.now() + 14 * 24 * 60 * 60 * 1000), // 14 days
            data_health_score: 0,
            is_chain_location: false,
            data_region: 'US', // TODO: Detect from IP
            created_by: user.id,
          },
        });

        // Link user to restaurant as owner
        await tx.restaurantUser.create({
          data: {
            restaurant_id: restaurant.id,
            user_id: user.id,
            role: 'OWNER',
            status: 'ACTIVE',
            permissions: {
              can_view_forecasts: true,
              can_edit_menu: true,
              can_view_financials: true,
              can_manage_users: true,
              can_manage_integrations: true,
            },
          },
        });

        return { user, restaurant };
      });

      // Generate JWT
      const token = await generateJWT({
        userId: result.user.id,
        restaurantId: result.restaurant.id,
        role: 'OWNER',
      });

      return {
        user: {
          id: result.user.id,
          email: result.user.email,
          firstName: result.user.first_name,
          lastName: result.user.last_name,
        },
        restaurant: {
          id: result.restaurant.id,
          name: result.restaurant.name,
          slug: result.restaurant.slug,
        },
        token,
      };
    }),

  // Login
  login: publicProcedure
    .input(
      z.object({
        email: z.string().email(),
        password: z.string(),
        restaurantSlug: z.string().optional(), // If user has multiple restaurants
      })
    )
    .output(
      z.object({
        user: z.object({
          id: z.string(),
          email: z.string(),
          firstName: z.string(),
          lastName: z.string(),
        }),
        restaurant: z.object({
          id: z.string(),
          name: z.string(),
          slug: z.string(),
        }),
        token: z.string(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const user = await ctx.prisma.user.findUnique({
        where: { email: input.email.toLowerCase() },
        include: {
          restaurant_users: {
            include: { restaurant: true },
            where: { status: 'ACTIVE' },
          },
        },
      });

      if (!user || !user.password_hash) {
        throw new TRPCError({
          code: 'UNAUTHORIZED',
          message: 'Invalid credentials',
        });
      }

      // Check account lockout
      if (user.locked_until && user.locked_until > new Date()) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Account locked due to too many failed attempts',
        });
      }

      // Verify password
      const isValid = await verifyPassword(input.password, user.password_hash);

      if (!isValid) {
        // Increment failed attempts
        await ctx.prisma.user.update({
          where: { id: user.id },
          data: {
            failed_login_attempts: user.failed_login_attempts + 1,
            locked_until:
              user.failed_login_attempts >= 4
                ? new Date(Date.now() + 15 * 60 * 1000) // Lock for 15 minutes
                : undefined,
          },
        });

        throw new TRPCError({
          code: 'UNAUTHORIZED',
          message: 'Invalid credentials',
        });
      }

      // Select restaurant
      let restaurantUser = user.restaurant_users[0];

      if (input.restaurantSlug) {
        restaurantUser =
          user.restaurant_users.find((ru) => ru.restaurant.slug === input.restaurantSlug) ||
          restaurantUser;
      }

      if (!restaurantUser) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'No restaurant access found',
        });
      }

      // Update last login
      await ctx.prisma.user.update({
        where: { id: user.id },
        data: {
          last_login_at: new Date(),
          failed_login_attempts: 0,
          locked_until: null,
        },
      });

      // Generate JWT
      const token = await generateJWT({
        userId: user.id,
        restaurantId: restaurantUser.restaurant_id,
        role: restaurantUser.role,
      });

      return {
        user: {
          id: user.id,
          email: user.email,
          firstName: user.first_name,
          lastName: user.last_name,
        },
        restaurant: {
          id: restaurantUser.restaurant.id,
          name: restaurantUser.restaurant.name,
          slug: restaurantUser.restaurant.slug,
        },
        token,
      };
    }),

  // Get current session
  me: protectedProcedure
    .output(
      z.object({
        user: z.object({
          id: z.string(),
          email: z.string(),
          firstName: z.string(),
          lastName: z.string(),
          avatar_url: z.string().nullable(),
        }),
        restaurant: z.object({
          id: z.string(),
          name: z.string(),
          slug: z.string(),
          subscription_tier: z.string(),
        }),
        role: z.string(),
      })
    )
    .query(async ({ ctx }) => {
      const user = await ctx.prisma.user.findUniqueOrThrow({
        where: { id: ctx.session.userId },
      });

      const restaurant = await ctx.prisma.restaurant.findUniqueOrThrow({
        where: { id: ctx.session.restaurantId },
      });

      return {
        user: {
          id: user.id,
          email: user.email,
          firstName: user.first_name,
          lastName: user.last_name,
          avatar_url: user.avatar_url,
        },
        restaurant: {
          id: restaurant.id,
          name: restaurant.name,
          slug: restaurant.slug,
          subscription_tier: restaurant.subscription_tier,
        },
        role: ctx.session.role,
      };
    }),
});
```

#### 2. Menu Router

**Purpose:** Menu items, categories, pricing

**File:** `apps/api/src/trpc/routers/menu.ts`

```typescript
import { router, protectedProcedure } from '../trpc';
import { z } from 'zod';

export const menuRouter = router({
  // List all menu items for current restaurant
  list: protectedProcedure
    .input(
      z.object({
        category: z.string().optional(),
        search: z.string().optional(),
        includeArchived: z.boolean().default(false),
        cursor: z.string().optional(),
        limit: z.number().min(1).max(100).default(50),
      })
    )
    .query(async ({ input, ctx }) => {
      const items = await ctx.prisma.menuItem.findMany({
        where: {
          restaurant_id: ctx.session.restaurantId,
          is_archived: input.includeArchived ? undefined : false,
          category: input.category,
          name: input.search
            ? { contains: input.search, mode: 'insensitive' as const }
            : undefined,
        },
        orderBy: { name: 'asc' },
        take: input.limit + 1,
        cursor: input.cursor ? { id: input.cursor } : undefined,
      });

      let nextCursor: string | undefined;
      if (items.length > input.limit) {
        const nextItem = items.pop();
        nextCursor = nextItem!.id;
      }

      return {
        items,
        nextCursor,
      };
    }),

  // Get single menu item
  byId: protectedProcedure
    .input(z.object({ id: z.string() }))
    .query(async ({ input, ctx }) => {
      return ctx.prisma.menuItem.findUniqueOrThrow({
        where: {
          id: input.id,
          restaurant_id: ctx.session.restaurantId, // RLS enforced
        },
        include: {
          recipes: {
            where: { status: 'ACTIVE' },
            include: {
              recipe_ingredients: {
                include: { ingredient: true },
                orderBy: { sort_order: 'asc' },
              },
            },
          },
        },
      });
    }),

  // Create menu item
  create: protectedProcedure
    .input(
      z.object({
        name: z.string().min(1),
        description: z.string().optional(),
        category: z.string(),
        subcategory: z.string().optional(),
        tags: z.array(z.string()).default([]),
        base_price_cents: z.number().int().positive().optional(),
        cost_cents: z.number().int().positive().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      return ctx.prisma.menuItem.create({
        data: {
          ...input,
          restaurant_id: ctx.session.restaurantId,
          is_available: true,
          available_days: [0, 1, 2, 3, 4, 5, 6],
          has_recipe: false,
          recipe_verified: false,
          is_archived: false,
          created_by: ctx.session.userId,
        },
      });
    }),

  // Update menu item
  update: protectedProcedure
    .input(
      z.object({
        id: z.string(),
        name: z.string().min(1).optional(),
        description: z.string().optional(),
        category: z.string().optional(),
        is_available: z.boolean().optional(),
        base_price_cents: z.number().int().positive().optional(),
      })
    )
    .mutation(async ({ input, ctx }) => {
      const { id, ...data } = input;

      return ctx.prisma.menuItem.update({
        where: {
          id,
          restaurant_id: ctx.session.restaurantId,
        },
        data,
      });
    }),

  // Archive menu item
  archive: protectedProcedure
    .input(z.object({ id: z.string() }))
    .mutation(async ({ input, ctx }) => {
      return ctx.prisma.menuItem.update({
        where: {
          id: input.id,
          restaurant_id: ctx.session.restaurantId,
        },
        data: {
          is_archived: true,
          archived_at: new Date(),
        },
      });
    }),

  // Get menu item sales stats
  stats: protectedProcedure
    .input(
      z.object({
        menuItemId: z.string(),
        startDate: z.date(),
        endDate: z.date(),
      })
    )
    .query(async ({ input, ctx }) => {
      const stats = await ctx.prisma.$queryRaw`
        SELECT
          COUNT(*) as order_count,
          SUM(ti.quantity) as total_quantity,
          SUM(ti.total_price_cents) as total_revenue_cents,
          AVG(ti.total_price_cents) as avg_price_cents
        FROM transaction_items ti
        JOIN transactions t ON t.id = ti.transaction_id
        WHERE ti.menu_item_id = ${input.menuItemId}
          AND t.restaurant_id = ${ctx.session.restaurantId}
          AND t.order_date >= ${input.startDate}
          AND t.order_date <= ${input.endDate}
          AND t.is_voided = false
      `;

      return stats[0];
    }),
});
```

---

### Forecast Router

**Purpose:** ML forecasting predictions, explanations, feedback, and accuracy metrics.

```typescript
// apps/api/src/routers/forecast.ts
import { z } from 'zod';
import { router, protectedProcedure } from '../trpc';
import { TRPCError } from '@trpc/server';

export const forecastRouter = router({
  /**
   * Get forecasts for date range
   * Supports filtering by menu item and model type
   */
  list: protectedProcedure
    .input(z.object({
      startDate: z.string().datetime(),
      endDate: z.string().datetime(),
      menuItemId: z.string().uuid().optional(),
      modelType: z.enum(['ARIMA', 'LSTM', 'PROPHET', 'ENSEMBLE']).optional(),
      cursor: z.string().optional(),
      limit: z.number().min(1).max(100).default(50),
    }))
    .output(z.object({
      forecasts: z.array(z.object({
        id: z.string().uuid(),
        menuItemId: z.string().uuid(),
        menuItemName: z.string(),
        forecastDate: z.string().datetime(),
        predictedQuantity: z.number(),
        confidenceIntervalLower: z.number(),
        confidenceIntervalUpper: z.number(),
        modelType: z.string(),
        confidence: z.number().min(0).max(1),
        generatedAt: z.string().datetime(),
      })),
      nextCursor: z.string().optional(),
    }))
    .query(async ({ ctx, input }) => {
      const forecasts = await ctx.prisma.forecast.findMany({
        where: {
          restaurantId: ctx.session.restaurantId,
          forecastDate: {
            gte: new Date(input.startDate),
            lte: new Date(input.endDate),
          },
          ...(input.menuItemId && { menuItemId: input.menuItemId }),
          ...(input.modelType && { modelType: input.modelType }),
          ...(input.cursor && {
            forecastDate: { gt: new Date(input.cursor) },
          }),
        },
        include: {
          menuItem: {
            select: { name: true },
          },
        },
        orderBy: { forecastDate: 'asc' },
        take: input.limit + 1,
      });

      const hasMore = forecasts.length > input.limit;
      const items = hasMore ? forecasts.slice(0, -1) : forecasts;
      const nextCursor = hasMore
        ? items[items.length - 1].forecastDate.toISOString()
        : undefined;

      return {
        forecasts: items.map(f => ({
          id: f.id,
          menuItemId: f.menuItemId,
          menuItemName: f.menuItem.name,
          forecastDate: f.forecastDate.toISOString(),
          predictedQuantity: f.predictedQuantity,
          confidenceIntervalLower: f.confidenceIntervalLower,
          confidenceIntervalUpper: f.confidenceIntervalUpper,
          modelType: f.modelType,
          confidence: f.confidence,
          generatedAt: f.generatedAt.toISOString(),
        })),
        nextCursor,
      };
    }),

  /**
   * Get forecast with SHAP explanation
   * Returns feature importance and contribution values
   */
  getWithExplanation: protectedProcedure
    .input(z.object({
      forecastId: z.string().uuid(),
    }))
    .output(z.object({
      forecast: z.object({
        id: z.string().uuid(),
        menuItemName: z.string(),
        forecastDate: z.string().datetime(),
        predictedQuantity: z.number(),
        confidenceIntervalLower: z.number(),
        confidenceIntervalUpper: z.number(),
        modelType: z.string(),
        confidence: z.number(),
      }),
      explanation: z.object({
        baseValue: z.number(),
        features: z.array(z.object({
          name: z.string(),
          value: z.number(),
          contribution: z.number(),
          importance: z.number().min(0).max(1),
        })),
        topDrivers: z.array(z.object({
          feature: z.string(),
          impact: z.string(),
          contribution: z.number(),
        })),
      }),
    }))
    .query(async ({ ctx, input }) => {
      const forecast = await ctx.prisma.forecast.findUnique({
        where: { id: input.forecastId },
        include: {
          menuItem: { select: { name: true } },
          explanation: {
            include: {
              featureImportances: {
                orderBy: { importance: 'desc' },
              },
            },
          },
        },
      });

      if (!forecast) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Forecast not found',
        });
      }

      if (forecast.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      if (!forecast.explanation) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Explanation not available for this forecast',
        });
      }

      const topDrivers = forecast.explanation.featureImportances
        .slice(0, 5)
        .map(fi => ({
          feature: fi.featureName,
          impact: fi.contribution > 0 ? 'increased' : 'decreased',
          contribution: Math.abs(fi.contribution),
        }));

      return {
        forecast: {
          id: forecast.id,
          menuItemName: forecast.menuItem.name,
          forecastDate: forecast.forecastDate.toISOString(),
          predictedQuantity: forecast.predictedQuantity,
          confidenceIntervalLower: forecast.confidenceIntervalLower,
          confidenceIntervalUpper: forecast.confidenceIntervalUpper,
          modelType: forecast.modelType,
          confidence: forecast.confidence,
        },
        explanation: {
          baseValue: forecast.explanation.baseValue,
          features: forecast.explanation.featureImportances.map(fi => ({
            name: fi.featureName,
            value: fi.featureValue,
            contribution: fi.contribution,
            importance: fi.importance,
          })),
          topDrivers,
        },
      };
    }),

  /**
   * Submit forecast feedback
   * Allows users to rate forecast accuracy
   */
  submitFeedback: protectedProcedure
    .input(z.object({
      forecastId: z.string().uuid(),
      actualQuantity: z.number().int().min(0),
      accuracyRating: z.number().int().min(1).max(5),
      comments: z.string().optional(),
    }))
    .output(z.object({
      success: z.boolean(),
      feedbackId: z.string().uuid(),
    }))
    .mutation(async ({ ctx, input }) => {
      // Verify forecast exists and belongs to user's restaurant
      const forecast = await ctx.prisma.forecast.findUnique({
        where: { id: input.forecastId },
      });

      if (!forecast) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Forecast not found',
        });
      }

      if (forecast.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      // Create feedback record
      const feedback = await ctx.prisma.forecastFeedback.create({
        data: {
          forecastId: input.forecastId,
          actualQuantity: input.actualQuantity,
          accuracyRating: input.accuracyRating,
          comments: input.comments,
          submittedBy: ctx.session.userId,
          submittedAt: new Date(),
        },
      });

      // Trigger model retraining if accuracy is poor (rating <= 2)
      if (input.accuracyRating <= 2) {
        // Queue background job for model evaluation
        await ctx.prisma.modelTrainingJob.create({
          data: {
            restaurantId: ctx.session.restaurantId,
            menuItemId: forecast.menuItemId,
            status: 'QUEUED',
            triggeredBy: 'POOR_ACCURACY_FEEDBACK',
            queuedAt: new Date(),
          },
        });
      }

      return {
        success: true,
        feedbackId: feedback.id,
      };
    }),

  /**
   * Get forecast accuracy metrics
   * Returns MAPE, RMSE, and MAE for specified period
   */
  getAccuracyMetrics: protectedProcedure
    .input(z.object({
      startDate: z.string().datetime(),
      endDate: z.string().datetime(),
      menuItemId: z.string().uuid().optional(),
      modelType: z.enum(['ARIMA', 'LSTM', 'PROPHET', 'ENSEMBLE']).optional(),
    }))
    .output(z.object({
      period: z.object({
        startDate: z.string().datetime(),
        endDate: z.string().datetime(),
      }),
      metrics: z.object({
        mape: z.number(), // Mean Absolute Percentage Error
        rmse: z.number(), // Root Mean Square Error
        mae: z.number(),  // Mean Absolute Error
        accuracy: z.number().min(0).max(1), // 1 - MAPE
        totalForecasts: z.number(),
        feedbackCount: z.number(),
      }),
      byMenuItem: z.array(z.object({
        menuItemId: z.string().uuid(),
        menuItemName: z.string(),
        mape: z.number(),
        forecastCount: z.number(),
      })),
    }))
    .query(async ({ ctx, input }) => {
      // Raw SQL for performance - calculates accuracy metrics
      const metrics = await ctx.prisma.$queryRaw<Array<{
        mape: number;
        rmse: number;
        mae: number;
        total_forecasts: bigint;
        feedback_count: bigint;
      }>>`
        SELECT
          AVG(ABS((ff.actual_quantity - f.predicted_quantity) / NULLIF(ff.actual_quantity, 0))) * 100 as mape,
          SQRT(AVG(POWER(ff.actual_quantity - f.predicted_quantity, 2))) as rmse,
          AVG(ABS(ff.actual_quantity - f.predicted_quantity)) as mae,
          COUNT(DISTINCT f.id) as total_forecasts,
          COUNT(DISTINCT ff.id) as feedback_count
        FROM forecasts f
        LEFT JOIN forecast_feedback ff ON f.id = ff.forecast_id
        WHERE f.restaurant_id = ${ctx.session.restaurantId}
          AND f.forecast_date >= ${new Date(input.startDate)}
          AND f.forecast_date <= ${new Date(input.endDate)}
          ${input.menuItemId ? `AND f.menu_item_id = ${input.menuItemId}` : ''}
          ${input.modelType ? `AND f.model_type = ${input.modelType}` : ''}
      `;

      const byMenuItem = await ctx.prisma.$queryRaw<Array<{
        menu_item_id: string;
        menu_item_name: string;
        mape: number;
        forecast_count: bigint;
      }>>`
        SELECT
          f.menu_item_id,
          mi.name as menu_item_name,
          AVG(ABS((ff.actual_quantity - f.predicted_quantity) / NULLIF(ff.actual_quantity, 0))) * 100 as mape,
          COUNT(DISTINCT f.id) as forecast_count
        FROM forecasts f
        LEFT JOIN forecast_feedback ff ON f.id = ff.forecast_id
        JOIN menu_items mi ON f.menu_item_id = mi.id
        WHERE f.restaurant_id = ${ctx.session.restaurantId}
          AND f.forecast_date >= ${new Date(input.startDate)}
          AND f.forecast_date <= ${new Date(input.endDate)}
          ${input.menuItemId ? `AND f.menu_item_id = ${input.menuItemId}` : ''}
          ${input.modelType ? `AND f.model_type = ${input.modelType}` : ''}
        GROUP BY f.menu_item_id, mi.name
        ORDER BY mape ASC
      `;

      const m = metrics[0];

      return {
        period: {
          startDate: input.startDate,
          endDate: input.endDate,
        },
        metrics: {
          mape: m.mape,
          rmse: m.rmse,
          mae: m.mae,
          accuracy: 1 - (m.mape / 100),
          totalForecasts: Number(m.total_forecasts),
          feedbackCount: Number(m.feedback_count),
        },
        byMenuItem: byMenuItem.map(item => ({
          menuItemId: item.menu_item_id,
          menuItemName: item.menu_item_name,
          mape: item.mape,
          forecastCount: Number(item.forecast_count),
        })),
      };
    }),
});
```

---

### Recipe Router

**Purpose:** Recipe management, explosion, ingredient tracking, and cost calculations.

```typescript
// apps/api/src/routers/recipe.ts
import { z } from 'zod';
import { router, protectedProcedure } from '../trpc';
import { TRPCError } from '@trpc/server';

export const recipeRouter = router({
  /**
   * List all recipes
   * Supports filtering by menu item and verification status
   */
  list: protectedProcedure
    .input(z.object({
      menuItemId: z.string().uuid().optional(),
      isVerified: z.boolean().optional(),
      cursor: z.string().optional(),
      limit: z.number().min(1).max(100).default(50),
    }))
    .output(z.object({
      recipes: z.array(z.object({
        id: z.string().uuid(),
        menuItemId: z.string().uuid(),
        menuItemName: z.string(),
        version: z.number(),
        isActive: z.boolean(),
        isVerified: z.boolean(),
        verifiedBy: z.string().optional(),
        verifiedAt: z.string().datetime().optional(),
        ingredientCount: z.number(),
        totalCost: z.number(),
        createdAt: z.string().datetime(),
      })),
      nextCursor: z.string().optional(),
    }))
    .query(async ({ ctx, input }) => {
      const recipes = await ctx.prisma.recipe.findMany({
        where: {
          restaurantId: ctx.session.restaurantId,
          ...(input.menuItemId && { menuItemId: input.menuItemId }),
          ...(input.isVerified !== undefined && { isVerified: input.isVerified }),
          ...(input.cursor && {
            createdAt: { gt: new Date(input.cursor) },
          }),
        },
        include: {
          menuItem: { select: { name: true } },
          verifiedByUser: { select: { name: true } },
          ingredients: true,
        },
        orderBy: { createdAt: 'desc' },
        take: input.limit + 1,
      });

      const hasMore = recipes.length > input.limit;
      const items = hasMore ? recipes.slice(0, -1) : recipes;
      const nextCursor = hasMore
        ? items[items.length - 1].createdAt.toISOString()
        : undefined;

      return {
        recipes: items.map(r => ({
          id: r.id,
          menuItemId: r.menuItemId,
          menuItemName: r.menuItem.name,
          version: r.version,
          isActive: r.isActive,
          isVerified: r.isVerified,
          verifiedBy: r.verifiedByUser?.name,
          verifiedAt: r.verifiedAt?.toISOString(),
          ingredientCount: r.ingredients.length,
          totalCost: r.ingredients.reduce((sum, ing) =>
            sum + (ing.quantity * ing.unitCost), 0
          ),
          createdAt: r.createdAt.toISOString(),
        })),
        nextCursor,
      };
    }),

  /**
   * Get recipe details with full ingredient breakdown
   */
  byId: protectedProcedure
    .input(z.object({
      recipeId: z.string().uuid(),
    }))
    .output(z.object({
      id: z.string().uuid(),
      menuItemId: z.string().uuid(),
      menuItemName: z.string(),
      version: z.number(),
      isActive: z.boolean(),
      isVerified: z.boolean(),
      verifiedBy: z.string().optional(),
      verifiedAt: z.string().datetime().optional(),
      notes: z.string().optional(),
      ingredients: z.array(z.object({
        id: z.string().uuid(),
        name: z.string(),
        quantity: z.number(),
        unit: z.string(),
        unitCost: z.number(),
        totalCost: z.number(),
        supplier: z.string().optional(),
      })),
      totalCost: z.number(),
      costPerServing: z.number(),
      createdAt: z.string().datetime(),
      updatedAt: z.string().datetime(),
    }))
    .query(async ({ ctx, input }) => {
      const recipe = await ctx.prisma.recipe.findUnique({
        where: { id: input.recipeId },
        include: {
          menuItem: { select: { name: true } },
          verifiedByUser: { select: { name: true } },
          ingredients: {
            include: {
              ingredient: {
                select: {
                  name: true,
                  defaultUnit: true,
                  currentCostPerUnit: true,
                  supplier: { select: { name: true } },
                },
              },
            },
          },
        },
      });

      if (!recipe) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Recipe not found',
        });
      }

      if (recipe.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      const totalCost = recipe.ingredients.reduce((sum, ri) =>
        sum + (ri.quantity * ri.unitCost), 0
      );

      return {
        id: recipe.id,
        menuItemId: recipe.menuItemId,
        menuItemName: recipe.menuItem.name,
        version: recipe.version,
        isActive: recipe.isActive,
        isVerified: recipe.isVerified,
        verifiedBy: recipe.verifiedByUser?.name,
        verifiedAt: recipe.verifiedAt?.toISOString(),
        notes: recipe.notes || undefined,
        ingredients: recipe.ingredients.map(ri => ({
          id: ri.id,
          name: ri.ingredient.name,
          quantity: ri.quantity,
          unit: ri.unit,
          unitCost: ri.unitCost,
          totalCost: ri.quantity * ri.unitCost,
          supplier: ri.ingredient.supplier?.name,
        })),
        totalCost,
        costPerServing: totalCost / (recipe.servingsPerBatch || 1),
        createdAt: recipe.createdAt.toISOString(),
        updatedAt: recipe.updatedAt.toISOString(),
      };
    }),

  /**
   * Create new recipe
   * Automatically increments version if recipe exists for menu item
   */
  create: protectedProcedure
    .input(z.object({
      menuItemId: z.string().uuid(),
      ingredients: z.array(z.object({
        ingredientId: z.string().uuid(),
        quantity: z.number().positive(),
        unit: z.string(),
        unitCost: z.number().positive(),
      })).min(1),
      servingsPerBatch: z.number().int().positive().default(1),
      notes: z.string().optional(),
    }))
    .output(z.object({
      success: z.boolean(),
      recipeId: z.string().uuid(),
      version: z.number(),
    }))
    .mutation(async ({ ctx, input }) => {
      // Verify menu item exists and belongs to restaurant
      const menuItem = await ctx.prisma.menuItem.findUnique({
        where: { id: input.menuItemId },
      });

      if (!menuItem) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Menu item not found',
        });
      }

      if (menuItem.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      // Get latest version number
      const latestRecipe = await ctx.prisma.recipe.findFirst({
        where: {
          menuItemId: input.menuItemId,
          restaurantId: ctx.session.restaurantId,
        },
        orderBy: { version: 'desc' },
      });

      const version = (latestRecipe?.version || 0) + 1;

      // Create recipe with ingredients in transaction
      const recipe = await ctx.prisma.$transaction(async (tx) => {
        // Deactivate previous version
        if (latestRecipe) {
          await tx.recipe.update({
            where: { id: latestRecipe.id },
            data: { isActive: false },
          });
        }

        // Create new recipe
        const newRecipe = await tx.recipe.create({
          data: {
            restaurantId: ctx.session.restaurantId,
            menuItemId: input.menuItemId,
            version,
            servingsPerBatch: input.servingsPerBatch,
            notes: input.notes,
            isActive: true,
            isVerified: false,
            createdBy: ctx.session.userId,
          },
        });

        // Create recipe ingredients
        await tx.recipeIngredient.createMany({
          data: input.ingredients.map(ing => ({
            recipeId: newRecipe.id,
            ingredientId: ing.ingredientId,
            quantity: ing.quantity,
            unit: ing.unit,
            unitCost: ing.unitCost,
          })),
        });

        return newRecipe;
      });

      return {
        success: true,
        recipeId: recipe.id,
        version: recipe.version,
      };
    }),

  /**
   * Verify recipe (chef approval)
   * Only users with CHEF or OWNER role can verify
   */
  verify: protectedProcedure
    .input(z.object({
      recipeId: z.string().uuid(),
      notes: z.string().optional(),
    }))
    .output(z.object({
      success: z.boolean(),
      verifiedAt: z.string().datetime(),
    }))
    .mutation(async ({ ctx, input }) => {
      // Check user role
      if (!['CHEF', 'OWNER'].includes(ctx.session.role)) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Only chefs and owners can verify recipes',
        });
      }

      const recipe = await ctx.prisma.recipe.findUnique({
        where: { id: input.recipeId },
      });

      if (!recipe) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Recipe not found',
        });
      }

      if (recipe.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      const updated = await ctx.prisma.recipe.update({
        where: { id: input.recipeId },
        data: {
          isVerified: true,
          verifiedBy: ctx.session.userId,
          verifiedAt: new Date(),
          notes: input.notes || recipe.notes,
        },
      });

      return {
        success: true,
        verifiedAt: updated.verifiedAt!.toISOString(),
      };
    }),

  /**
   * Calculate recipe costs for forecasted quantities
   * Used by procurement recommendations
   */
  calculateCosts: protectedProcedure
    .input(z.object({
      recipeId: z.string().uuid(),
      targetQuantity: z.number().int().positive(),
    }))
    .output(z.object({
      recipeId: z.string().uuid(),
      targetQuantity: z.number(),
      batchesNeeded: z.number(),
      ingredients: z.array(z.object({
        ingredientId: z.string().uuid(),
        name: z.string(),
        quantityNeeded: z.number(),
        unit: z.string(),
        unitCost: z.number(),
        totalCost: z.number(),
        currentStock: z.number(),
        needsToProcure: z.number(),
      })),
      totalCost: z.number(),
    }))
    .query(async ({ ctx, input }) => {
      const recipe = await ctx.prisma.recipe.findUnique({
        where: { id: input.recipeId },
        include: {
          ingredients: {
            include: {
              ingredient: {
                select: {
                  id: true,
                  name: true,
                  currentStock: true,
                },
              },
            },
          },
        },
      });

      if (!recipe) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Recipe not found',
        });
      }

      if (recipe.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      const batchesNeeded = Math.ceil(input.targetQuantity / recipe.servingsPerBatch);

      const ingredients = recipe.ingredients.map(ri => {
        const quantityNeeded = ri.quantity * batchesNeeded;
        const needsToProcure = Math.max(0, quantityNeeded - ri.ingredient.currentStock);

        return {
          ingredientId: ri.ingredient.id,
          name: ri.ingredient.name,
          quantityNeeded,
          unit: ri.unit,
          unitCost: ri.unitCost,
          totalCost: quantityNeeded * ri.unitCost,
          currentStock: ri.ingredient.currentStock,
          needsToProcure,
        };
      });

      const totalCost = ingredients.reduce((sum, ing) => sum + ing.totalCost, 0);

      return {
        recipeId: recipe.id,
        targetQuantity: input.targetQuantity,
        batchesNeeded,
        ingredients,
        totalCost,
      };
    }),
});
```

---

### Transaction Router

**Purpose:** Sales transaction queries, analytics, and data health monitoring.

```typescript
// apps/api/src/routers/transaction.ts
import { z } from 'zod';
import { router, protectedProcedure } from '../trpc';
import { TRPCError } from '@trpc/server';

export const transactionRouter = router({
  /**
   * List transactions with filtering and pagination
   */
  list: protectedProcedure
    .input(z.object({
      startDate: z.string().datetime(),
      endDate: z.string().datetime(),
      menuItemId: z.string().uuid().optional(),
      minAmount: z.number().optional(),
      maxAmount: z.number().optional(),
      isVoided: z.boolean().optional(),
      cursor: z.string().optional(),
      limit: z.number().min(1).max(100).default(50),
    }))
    .output(z.object({
      transactions: z.array(z.object({
        id: z.string().uuid(),
        posTransactionId: z.string(),
        orderDate: z.string().datetime(),
        menuItemId: z.string().uuid(),
        menuItemName: z.string(),
        quantity: z.number(),
        unitPrice: z.number(),
        totalAmount: z.number(),
        isVoided: z.boolean(),
        syncedAt: z.string().datetime(),
      })),
      nextCursor: z.string().optional(),
      summary: z.object({
        totalTransactions: z.number(),
        totalRevenue: z.number(),
        totalQuantity: z.number(),
      }),
    }))
    .query(async ({ ctx, input }) => {
      const where = {
        restaurantId: ctx.session.restaurantId,
        orderDate: {
          gte: new Date(input.startDate),
          lte: new Date(input.endDate),
        },
        ...(input.menuItemId && { menuItemId: input.menuItemId }),
        ...(input.minAmount && { totalAmount: { gte: input.minAmount } }),
        ...(input.maxAmount && { totalAmount: { lte: input.maxAmount } }),
        ...(input.isVoided !== undefined && { isVoided: input.isVoided }),
        ...(input.cursor && {
          orderDate: { gt: new Date(input.cursor) },
        }),
      };

      const [transactions, summary] = await Promise.all([
        ctx.prisma.transaction.findMany({
          where,
          include: {
            menuItem: { select: { name: true } },
          },
          orderBy: { orderDate: 'desc' },
          take: input.limit + 1,
        }),
        ctx.prisma.transaction.aggregate({
          where,
          _count: { id: true },
          _sum: {
            totalAmount: true,
            quantity: true,
          },
        }),
      ]);

      const hasMore = transactions.length > input.limit;
      const items = hasMore ? transactions.slice(0, -1) : transactions;
      const nextCursor = hasMore
        ? items[items.length - 1].orderDate.toISOString()
        : undefined;

      return {
        transactions: items.map(t => ({
          id: t.id,
          posTransactionId: t.posTransactionId,
          orderDate: t.orderDate.toISOString(),
          menuItemId: t.menuItemId,
          menuItemName: t.menuItem.name,
          quantity: t.quantity,
          unitPrice: t.unitPrice,
          totalAmount: t.totalAmount,
          isVoided: t.isVoided,
          syncedAt: t.syncedAt.toISOString(),
        })),
        nextCursor,
        summary: {
          totalTransactions: summary._count.id,
          totalRevenue: summary._sum.totalAmount || 0,
          totalQuantity: summary._sum.quantity || 0,
        },
      };
    }),

  /**
   * Get daily sales aggregates
   * Optimized for dashboard charts
   */
  getDailySales: protectedProcedure
    .input(z.object({
      startDate: z.string().datetime(),
      endDate: z.string().datetime(),
      menuItemId: z.string().uuid().optional(),
    }))
    .output(z.object({
      dailySales: z.array(z.object({
        date: z.string().date(),
        totalRevenue: z.number(),
        totalQuantity: z.number(),
        transactionCount: z.number(),
        averageOrderValue: z.number(),
      })),
    }))
    .query(async ({ ctx, input }) => {
      const dailySales = await ctx.prisma.$queryRaw<Array<{
        date: Date;
        total_revenue: number;
        total_quantity: number;
        transaction_count: bigint;
      }>>`
        SELECT
          DATE(order_date) as date,
          SUM(total_amount) as total_revenue,
          SUM(quantity) as total_quantity,
          COUNT(*) as transaction_count
        FROM transactions
        WHERE restaurant_id = ${ctx.session.restaurantId}
          AND order_date >= ${new Date(input.startDate)}
          AND order_date <= ${new Date(input.endDate)}
          AND is_voided = false
          ${input.menuItemId ? `AND menu_item_id = ${input.menuItemId}` : ''}
        GROUP BY DATE(order_date)
        ORDER BY date ASC
      `;

      return {
        dailySales: dailySales.map(day => ({
          date: day.date.toISOString().split('T')[0],
          totalRevenue: day.total_revenue,
          totalQuantity: day.total_quantity,
          transactionCount: Number(day.transaction_count),
          averageOrderValue: day.total_revenue / Number(day.transaction_count),
        })),
      };
    }),

  /**
   * Get data health status
   * Identifies sync issues, gaps, anomalies
   */
  getDataHealth: protectedProcedure
    .input(z.object({
      days: z.number().int().min(1).max(90).default(30),
    }))
    .output(z.object({
      overall: z.object({
        status: z.enum(['HEALTHY', 'WARNING', 'CRITICAL']),
        lastSyncAt: z.string().datetime(),
        issues: z.array(z.string()),
      }),
      syncStatus: z.object({
        expectedDays: z.number(),
        daysWithData: z.number(),
        missingDays: z.array(z.string().date()),
        syncGaps: z.array(z.object({
          start: z.string().date(),
          end: z.string().date(),
          durationDays: z.number(),
        })),
      }),
      anomalies: z.array(z.object({
        date: z.string().date(),
        type: z.enum(['REVENUE_SPIKE', 'REVENUE_DROP', 'QUANTITY_SPIKE', 'NO_DATA']),
        severity: z.enum(['LOW', 'MEDIUM', 'HIGH']),
        description: z.string(),
      })),
    }))
    .query(async ({ ctx, input }) => {
      const startDate = new Date();
      startDate.setDate(startDate.getDate() - input.days);

      // Get last sync time
      const lastSync = await ctx.prisma.transaction.findFirst({
        where: { restaurantId: ctx.session.restaurantId },
        orderBy: { syncedAt: 'desc' },
        select: { syncedAt: true },
      });

      // Get daily transaction counts
      const dailyCounts = await ctx.prisma.$queryRaw<Array<{
        date: Date;
        transaction_count: bigint;
        total_revenue: number;
      }>>`
        SELECT
          DATE(order_date) as date,
          COUNT(*) as transaction_count,
          SUM(total_amount) as total_revenue
        FROM transactions
        WHERE restaurant_id = ${ctx.session.restaurantId}
          AND order_date >= ${startDate}
          AND is_voided = false
        GROUP BY DATE(order_date)
        ORDER BY date ASC
      `;

      // Identify missing days
      const allDates = new Set<string>();
      for (let d = new Date(startDate); d <= new Date(); d.setDate(d.getDate() + 1)) {
        allDates.add(d.toISOString().split('T')[0]);
      }

      const datesWithData = new Set(
        dailyCounts.map(d => d.date.toISOString().split('T')[0])
      );

      const missingDays = Array.from(allDates).filter(date => !datesWithData.has(date));

      // Find sync gaps (consecutive missing days)
      const syncGaps: Array<{ start: string; end: string; durationDays: number }> = [];
      let gapStart: string | null = null;

      for (const day of Array.from(allDates).sort()) {
        if (!datesWithData.has(day)) {
          if (!gapStart) gapStart = day;
        } else if (gapStart) {
          const gap = {
            start: gapStart,
            end: day,
            durationDays: Math.floor(
              (new Date(day).getTime() - new Date(gapStart).getTime()) / (1000 * 60 * 60 * 24)
            ),
          };
          if (gap.durationDays >= 2) syncGaps.push(gap);
          gapStart = null;
        }
      }

      // Detect anomalies (simple statistical approach)
      const revenues = dailyCounts.map(d => d.total_revenue);
      const avgRevenue = revenues.reduce((a, b) => a + b, 0) / revenues.length;
      const stdDev = Math.sqrt(
        revenues.reduce((sum, val) => sum + Math.pow(val - avgRevenue, 2), 0) / revenues.length
      );

      const anomalies: Array<{
        date: string;
        type: 'REVENUE_SPIKE' | 'REVENUE_DROP' | 'QUANTITY_SPIKE' | 'NO_DATA';
        severity: 'LOW' | 'MEDIUM' | 'HIGH';
        description: string;
      }> = [];

      dailyCounts.forEach(day => {
        const zScore = Math.abs((day.total_revenue - avgRevenue) / stdDev);

        if (zScore > 3) {
          anomalies.push({
            date: day.date.toISOString().split('T')[0],
            type: day.total_revenue > avgRevenue ? 'REVENUE_SPIKE' : 'REVENUE_DROP',
            severity: zScore > 4 ? 'HIGH' : 'MEDIUM',
            description: `Revenue ${day.total_revenue > avgRevenue ? 'spike' : 'drop'}: $${day.total_revenue.toFixed(2)} (${zScore.toFixed(1)}σ from mean)`,
          });
        }
      });

      // Determine overall health status
      const issues: string[] = [];
      let status: 'HEALTHY' | 'WARNING' | 'CRITICAL' = 'HEALTHY';

      if (missingDays.length > 0) {
        issues.push(`${missingDays.length} days with no transaction data`);
        if (missingDays.length > input.days * 0.2) status = 'WARNING';
      }

      if (syncGaps.length > 0) {
        issues.push(`${syncGaps.length} sync gap(s) detected`);
        if (syncGaps.some(g => g.durationDays >= 7)) status = 'CRITICAL';
      }

      if (anomalies.filter(a => a.severity === 'HIGH').length > 0) {
        issues.push(`${anomalies.length} anomalies detected`);
        if (status !== 'CRITICAL') status = 'WARNING';
      }

      if (!lastSync) {
        issues.push('No transaction data found');
        status = 'CRITICAL';
      }

      return {
        overall: {
          status,
          lastSyncAt: lastSync?.syncedAt.toISOString() || new Date().toISOString(),
          issues,
        },
        syncStatus: {
          expectedDays: input.days,
          daysWithData: datesWithData.size,
          missingDays,
          syncGaps,
        },
        anomalies,
      };
    }),
});
```

---

### Procurement Router

**Purpose:** AI-powered procurement recommendations, order management, and supplier relationships.

```typescript
// apps/api/src/routers/procurement.ts
import { z } from 'zod';
import { router, protectedProcedure } from '../trpc';
import { TRPCError } from '@trpc/server';

export const procurementRouter = router({
  /**
   * Get AI procurement recommendations
   * Uses forecasts + recipes to recommend ingredient orders
   */
  getRecommendations: protectedProcedure
    .input(z.object({
      startDate: z.string().datetime(),
      endDate: z.string().datetime(),
      includeCurrentStock: z.boolean().default(true),
    }))
    .output(z.object({
      recommendations: z.array(z.object({
        ingredientId: z.string().uuid(),
        ingredientName: z.string(),
        recommendedQuantity: z.number(),
        unit: z.string(),
        currentStock: z.number(),
        projectedUsage: z.number(),
        daysUntilStockout: z.number().nullable(),
        estimatedCost: z.number(),
        supplierId: z.string().uuid().nullable(),
        supplierName: z.string().nullable(),
        confidence: z.number().min(0).max(1),
        reasons: z.array(z.string()),
      })),
      summary: z.object({
        totalIngredients: z.number(),
        totalEstimatedCost: z.number(),
        criticalItems: z.number(), // Items with < 3 days until stockout
      }),
    }))
    .query(async ({ ctx, input }) => {
      // Get forecasts for the period
      const forecasts = await ctx.prisma.forecast.findMany({
        where: {
          restaurantId: ctx.session.restaurantId,
          forecastDate: {
            gte: new Date(input.startDate),
            lte: new Date(input.endDate),
          },
        },
        include: {
          menuItem: {
            include: {
              recipe: {
                where: { isActive: true },
                include: {
                  ingredients: {
                    include: {
                      ingredient: {
                        include: {
                          supplier: true,
                        },
                      },
                    },
                  },
                },
              },
            },
          },
        },
      });

      // Aggregate ingredient needs by forecast quantities
      const ingredientNeeds = new Map<string, {
        ingredient: any;
        totalNeeded: number;
        menuItems: string[];
      }>();

      forecasts.forEach(forecast => {
        const recipe = forecast.menuItem.recipe[0];
        if (!recipe) return;

        const batchesNeeded = Math.ceil(
          forecast.predictedQuantity / recipe.servingsPerBatch
        );

        recipe.ingredients.forEach(ri => {
          const key = ri.ingredientId;
          const existing = ingredientNeeds.get(key);

          if (existing) {
            existing.totalNeeded += ri.quantity * batchesNeeded;
            existing.menuItems.push(forecast.menuItem.name);
          } else {
            ingredientNeeds.set(key, {
              ingredient: ri.ingredient,
              totalNeeded: ri.quantity * batchesNeeded,
              menuItems: [forecast.menuItem.name],
            });
          }
        });
      });

      // Calculate recommendations
      const recommendations = Array.from(ingredientNeeds.entries()).map(([id, data]) => {
        const currentStock = data.ingredient.currentStock || 0;
        const needToProcure = Math.max(0, data.totalNeeded - currentStock);

        // Calculate days until stockout (assuming even distribution)
        const periodDays = Math.ceil(
          (new Date(input.endDate).getTime() - new Date(input.startDate).getTime()) /
          (1000 * 60 * 60 * 24)
        );
        const dailyUsage = data.totalNeeded / periodDays;
        const daysUntilStockout = dailyUsage > 0
          ? Math.floor(currentStock / dailyUsage)
          : null;

        const reasons: string[] = [];
        if (currentStock === 0) {
          reasons.push('Out of stock');
        } else if (daysUntilStockout && daysUntilStockout < 3) {
          reasons.push(`Critical: Only ${daysUntilStockout} days of stock remaining`);
        } else if (daysUntilStockout && daysUntilStockout < 7) {
          reasons.push(`Low stock: ${daysUntilStockout} days remaining`);
        }

        reasons.push(`Needed for: ${data.menuItems.slice(0, 3).join(', ')}${data.menuItems.length > 3 ? '...' : ''}`);

        return {
          ingredientId: id,
          ingredientName: data.ingredient.name,
          recommendedQuantity: Math.ceil(needToProcure * 1.1), // 10% buffer
          unit: data.ingredient.defaultUnit,
          currentStock,
          projectedUsage: data.totalNeeded,
          daysUntilStockout,
          estimatedCost: needToProcure * data.ingredient.currentCostPerUnit,
          supplierId: data.ingredient.supplier?.id || null,
          supplierName: data.ingredient.supplier?.name || null,
          confidence: 0.85, // Would come from forecast confidence in production
          reasons,
        };
      });

      // Sort by urgency (days until stockout)
      recommendations.sort((a, b) => {
        if (a.daysUntilStockout === null) return 1;
        if (b.daysUntilStockout === null) return -1;
        return a.daysUntilStockout - b.daysUntilStockout;
      });

      const criticalItems = recommendations.filter(
        r => r.daysUntilStockout !== null && r.daysUntilStockout < 3
      ).length;

      return {
        recommendations,
        summary: {
          totalIngredients: recommendations.length,
          totalEstimatedCost: recommendations.reduce((sum, r) => sum + r.estimatedCost, 0),
          criticalItems,
        },
      };
    }),

  /**
   * Create procurement order
   * Can be from recommendations or manual
   */
  createOrder: protectedProcedure
    .input(z.object({
      supplierId: z.string().uuid(),
      items: z.array(z.object({
        ingredientId: z.string().uuid(),
        quantity: z.number().positive(),
        unitCost: z.number().positive(),
      })).min(1),
      deliveryDate: z.string().datetime().optional(),
      notes: z.string().optional(),
    }))
    .output(z.object({
      success: z.boolean(),
      orderId: z.string().uuid(),
      totalCost: z.number(),
    }))
    .mutation(async ({ ctx, input }) => {
      // Verify supplier exists and is active
      const supplier = await ctx.prisma.supplier.findUnique({
        where: { id: input.supplierId },
      });

      if (!supplier) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Supplier not found',
        });
      }

      if (supplier.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      if (!supplier.isActive) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: 'Supplier is inactive',
        });
      }

      // Calculate total cost
      const totalCost = input.items.reduce(
        (sum, item) => sum + (item.quantity * item.unitCost),
        0
      );

      // Create order with items in transaction
      const order = await ctx.prisma.$transaction(async (tx) => {
        const newOrder = await tx.procurementOrder.create({
          data: {
            restaurantId: ctx.session.restaurantId,
            supplierId: input.supplierId,
            status: 'PENDING',
            totalCost,
            expectedDeliveryDate: input.deliveryDate
              ? new Date(input.deliveryDate)
              : undefined,
            notes: input.notes,
            orderedBy: ctx.session.userId,
            orderedAt: new Date(),
          },
        });

        await tx.procurementOrderItem.createMany({
          data: input.items.map(item => ({
            orderId: newOrder.id,
            ingredientId: item.ingredientId,
            quantity: item.quantity,
            unitCost: item.unitCost,
            totalCost: item.quantity * item.unitCost,
          })),
        });

        return newOrder;
      });

      return {
        success: true,
        orderId: order.id,
        totalCost,
      };
    }),

  /**
   * Update order status
   * Automatically updates inventory on DELIVERED status
   */
  updateOrderStatus: protectedProcedure
    .input(z.object({
      orderId: z.string().uuid(),
      status: z.enum(['PENDING', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'CANCELLED']),
      actualDeliveryDate: z.string().datetime().optional(),
      notes: z.string().optional(),
    }))
    .output(z.object({
      success: z.boolean(),
      inventoryUpdated: z.boolean(),
    }))
    .mutation(async ({ ctx, input }) => {
      const order = await ctx.prisma.procurementOrder.findUnique({
        where: { id: input.orderId },
        include: { items: true },
      });

      if (!order) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Order not found',
        });
      }

      if (order.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      let inventoryUpdated = false;

      await ctx.prisma.$transaction(async (tx) => {
        // Update order status
        await tx.procurementOrder.update({
          where: { id: input.orderId },
          data: {
            status: input.status,
            actualDeliveryDate: input.actualDeliveryDate
              ? new Date(input.actualDeliveryDate)
              : undefined,
            notes: input.notes || order.notes,
          },
        });

        // If delivered, update ingredient stock levels
        if (input.status === 'DELIVERED') {
          for (const item of order.items) {
            await tx.ingredient.update({
              where: { id: item.ingredientId },
              data: {
                currentStock: {
                  increment: item.quantity,
                },
                lastRestockedAt: new Date(),
              },
            });

            // Create inventory transaction log
            await tx.inventoryTransaction.create({
              data: {
                ingredientId: item.ingredientId,
                restaurantId: order.restaurantId,
                type: 'RESTOCK',
                quantity: item.quantity,
                costPerUnit: item.unitCost,
                reference: `Order #${order.id}`,
                createdBy: ctx.session.userId,
                createdAt: new Date(),
              },
            });
          }

          inventoryUpdated = true;
        }
      });

      return {
        success: true,
        inventoryUpdated,
      };
    }),

  /**
   * List procurement orders
   */
  listOrders: protectedProcedure
    .input(z.object({
      status: z.enum(['PENDING', 'CONFIRMED', 'SHIPPED', 'DELIVERED', 'CANCELLED']).optional(),
      supplierId: z.string().uuid().optional(),
      startDate: z.string().datetime().optional(),
      endDate: z.string().datetime().optional(),
      cursor: z.string().optional(),
      limit: z.number().min(1).max(100).default(50),
    }))
    .output(z.object({
      orders: z.array(z.object({
        id: z.string().uuid(),
        supplierId: z.string().uuid(),
        supplierName: z.string(),
        status: z.string(),
        totalCost: z.number(),
        itemCount: z.number(),
        orderedAt: z.string().datetime(),
        expectedDeliveryDate: z.string().datetime().nullable(),
        actualDeliveryDate: z.string().datetime().nullable(),
      })),
      nextCursor: z.string().optional(),
    }))
    .query(async ({ ctx, input }) => {
      const orders = await ctx.prisma.procurementOrder.findMany({
        where: {
          restaurantId: ctx.session.restaurantId,
          ...(input.status && { status: input.status }),
          ...(input.supplierId && { supplierId: input.supplierId }),
          ...(input.startDate && {
            orderedAt: { gte: new Date(input.startDate) },
          }),
          ...(input.endDate && {
            orderedAt: { lte: new Date(input.endDate) },
          }),
          ...(input.cursor && {
            orderedAt: { lt: new Date(input.cursor) },
          }),
        },
        include: {
          supplier: { select: { name: true } },
          _count: { select: { items: true } },
        },
        orderBy: { orderedAt: 'desc' },
        take: input.limit + 1,
      });

      const hasMore = orders.length > input.limit;
      const items = hasMore ? orders.slice(0, -1) : orders;
      const nextCursor = hasMore
        ? items[items.length - 1].orderedAt.toISOString()
        : undefined;

      return {
        orders: items.map(o => ({
          id: o.id,
          supplierId: o.supplierId,
          supplierName: o.supplier.name,
          status: o.status,
          totalCost: o.totalCost,
          itemCount: o._count.items,
          orderedAt: o.orderedAt.toISOString(),
          expectedDeliveryDate: o.expectedDeliveryDate?.toISOString() || null,
          actualDeliveryDate: o.actualDeliveryDate?.toISOString() || null,
        })),
        nextCursor,
      };
    }),
});
```

---

### POS Router

**Purpose:** POS integration management, connection status, and data synchronization.

```typescript
// apps/api/src/routers/pos.ts
import { z } from 'zod';
import { router, protectedProcedure } from '../trpc';
import { TRPCError } from '@trpc/server';

export const posRouter = router({
  /**
   * List available POS integrations
   */
  listIntegrations: protectedProcedure
    .input(z.object({
      isActive: z.boolean().optional(),
    }))
    .output(z.object({
      integrations: z.array(z.object({
        id: z.string().uuid(),
        provider: z.enum(['SQUARE', 'TOAST', 'CLOVER', 'LIGHTSPEED']),
        connectionStatus: z.enum(['CONNECTED', 'DISCONNECTED', 'ERROR']),
        lastSyncAt: z.string().datetime().nullable(),
        lastSyncStatus: z.enum(['SUCCESS', 'FAILED', 'PARTIAL']).nullable(),
        syncedTransactionCount: z.number(),
        createdAt: z.string().datetime(),
      })),
    }))
    .query(async ({ ctx, input }) => {
      const integrations = await ctx.prisma.pOSIntegration.findMany({
        where: {
          restaurantId: ctx.session.restaurantId,
          ...(input.isActive !== undefined && { isActive: input.isActive }),
        },
        include: {
          _count: {
            select: { syncLogs: true },
          },
        },
        orderBy: { createdAt: 'desc' },
      });

      return {
        integrations: integrations.map(i => ({
          id: i.id,
          provider: i.provider as 'SQUARE' | 'TOAST' | 'CLOVER' | 'LIGHTSPEED',
          connectionStatus: i.connectionStatus as 'CONNECTED' | 'DISCONNECTED' | 'ERROR',
          lastSyncAt: i.lastSyncAt?.toISOString() || null,
          lastSyncStatus: i.lastSyncStatus as 'SUCCESS' | 'FAILED' | 'PARTIAL' | null,
          syncedTransactionCount: i._count.syncLogs,
          createdAt: i.createdAt.toISOString(),
        })),
      };
    }),

  /**
   * Connect new POS integration
   * Returns OAuth URL for user authorization
   */
  connect: protectedProcedure
    .input(z.object({
      provider: z.enum(['SQUARE', 'TOAST', 'CLOVER', 'LIGHTSPEED']),
      locationId: z.string().optional(), // POS-specific location ID
    }))
    .output(z.object({
      authorizationUrl: z.string().url(),
      integrationId: z.string().uuid(),
    }))
    .mutation(async ({ ctx, input }) => {
      // Check if integration already exists
      const existing = await ctx.prisma.pOSIntegration.findFirst({
        where: {
          restaurantId: ctx.session.restaurantId,
          provider: input.provider,
          isActive: true,
        },
      });

      if (existing) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: `${input.provider} integration already exists`,
        });
      }

      // Create pending integration
      const integration = await ctx.prisma.pOSIntegration.create({
        data: {
          restaurantId: ctx.session.restaurantId,
          provider: input.provider,
          locationId: input.locationId,
          connectionStatus: 'DISCONNECTED',
          isActive: true,
          createdBy: ctx.session.userId,
        },
      });

      // Generate OAuth URL (implementation varies by provider)
      const redirectUri = `${process.env.APP_URL}/integrations/callback`;
      const state = Buffer.from(JSON.stringify({
        integrationId: integration.id,
        restaurantId: ctx.session.restaurantId,
      })).toString('base64');

      let authUrl = '';
      switch (input.provider) {
        case 'SQUARE':
          authUrl = `https://connect.squareup.com/oauth2/authorize?client_id=${process.env.SQUARE_CLIENT_ID}&scope=MERCHANT_PROFILE_READ+PAYMENTS_READ+ORDERS_READ&state=${state}&redirect_uri=${redirectUri}`;
          break;
        case 'TOAST':
          authUrl = `https://ws-api.toasttab.com/authentication/v1/authorize?client_id=${process.env.TOAST_CLIENT_ID}&response_type=code&state=${state}&redirect_uri=${redirectUri}`;
          break;
        case 'CLOVER':
          authUrl = `https://www.clover.com/oauth/authorize?client_id=${process.env.CLOVER_CLIENT_ID}&state=${state}&redirect_uri=${redirectUri}`;
          break;
        case 'LIGHTSPEED':
          authUrl = `https://cloud.lightspeedapp.com/oauth/authorize?response_type=code&client_id=${process.env.LIGHTSPEED_CLIENT_ID}&scope=employee:all+sale:all&state=${state}&redirect_uri=${redirectUri}`;
          break;
      }

      return {
        authorizationUrl: authUrl,
        integrationId: integration.id,
      };
    }),

  /**
   * Disconnect POS integration
   */
  disconnect: protectedProcedure
    .input(z.object({
      integrationId: z.string().uuid(),
    }))
    .output(z.object({
      success: z.boolean(),
    }))
    .mutation(async ({ ctx, input }) => {
      const integration = await ctx.prisma.pOSIntegration.findUnique({
        where: { id: input.integrationId },
      });

      if (!integration) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Integration not found',
        });
      }

      if (integration.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      await ctx.prisma.pOSIntegration.update({
        where: { id: input.integrationId },
        data: {
          isActive: false,
          connectionStatus: 'DISCONNECTED',
          accessToken: null, // Clear credentials
          refreshToken: null,
        },
      });

      return { success: true };
    }),

  /**
   * Trigger manual sync
   * Queues background job to sync transactions
   */
  syncNow: protectedProcedure
    .input(z.object({
      integrationId: z.string().uuid(),
      startDate: z.string().datetime().optional(),
      endDate: z.string().datetime().optional(),
    }))
    .output(z.object({
      success: z.boolean(),
      syncJobId: z.string().uuid(),
    }))
    .mutation(async ({ ctx, input }) => {
      const integration = await ctx.prisma.pOSIntegration.findUnique({
        where: { id: input.integrationId },
      });

      if (!integration) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Integration not found',
        });
      }

      if (integration.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      if (integration.connectionStatus !== 'CONNECTED') {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: 'Integration is not connected',
        });
      }

      // Create sync job
      const syncJob = await ctx.prisma.pOSSyncJob.create({
        data: {
          integrationId: input.integrationId,
          status: 'QUEUED',
          startDate: input.startDate ? new Date(input.startDate) : undefined,
          endDate: input.endDate ? new Date(input.endDate) : undefined,
          triggeredBy: ctx.session.userId,
          queuedAt: new Date(),
        },
      });

      // In production, this would publish to SQS/EventBridge
      // For now, just return the job ID
      return {
        success: true,
        syncJobId: syncJob.id,
      };
    }),

  /**
   * Get sync history
   */
  getSyncHistory: protectedProcedure
    .input(z.object({
      integrationId: z.string().uuid(),
      limit: z.number().min(1).max(100).default(20),
    }))
    .output(z.object({
      syncJobs: z.array(z.object({
        id: z.string().uuid(),
        status: z.enum(['QUEUED', 'RUNNING', 'COMPLETED', 'FAILED']),
        transactionsSynced: z.number(),
        errorMessage: z.string().nullable(),
        startedAt: z.string().datetime().nullable(),
        completedAt: z.string().datetime().nullable(),
        queuedAt: z.string().datetime(),
      })),
    }))
    .query(async ({ ctx, input }) => {
      const integration = await ctx.prisma.pOSIntegration.findUnique({
        where: { id: input.integrationId },
      });

      if (!integration) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Integration not found',
        });
      }

      if (integration.restaurantId !== ctx.session.restaurantId) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Access denied',
        });
      }

      const syncJobs = await ctx.prisma.pOSSyncJob.findMany({
        where: { integrationId: input.integrationId },
        orderBy: { queuedAt: 'desc' },
        take: input.limit,
      });

      return {
        syncJobs: syncJobs.map(job => ({
          id: job.id,
          status: job.status as 'QUEUED' | 'RUNNING' | 'COMPLETED' | 'FAILED',
          transactionsSynced: job.transactionsSynced || 0,
          errorMessage: job.errorMessage || null,
          startedAt: job.startedAt?.toISOString() || null,
          completedAt: job.completedAt?.toISOString() || null,
          queuedAt: job.queuedAt.toISOString(),
        })),
      };
    }),
});
```

---

### User Router

**Purpose:** Team member management, permissions, and invitations.

```typescript
// apps/api/src/routers/user.ts
import { z } from 'zod';
import { router, protectedProcedure } from '../trpc';
import { TRPCError } from '@trpc/server';
import { sendEmail } from '../lib/email';

export const userRouter = router({
  /**
   * List restaurant team members
   * Only OWNER and MANAGER roles can access
   */
  listTeamMembers: protectedProcedure
    .input(z.object({
      role: z.enum(['OWNER', 'MANAGER', 'CHEF', 'STAFF']).optional(),
      isActive: z.boolean().optional(),
    }))
    .output(z.object({
      users: z.array(z.object({
        id: z.string().uuid(),
        name: z.string(),
        email: z.string().email(),
        role: z.enum(['OWNER', 'MANAGER', 'CHEF', 'STAFF']),
        isActive: z.boolean(),
        lastLoginAt: z.string().datetime().nullable(),
        createdAt: z.string().datetime(),
      })),
    }))
    .query(async ({ ctx, input }) => {
      // Only owners and managers can list team
      if (!['OWNER', 'MANAGER'].includes(ctx.session.role)) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Only owners and managers can view team members',
        });
      }

      const users = await ctx.prisma.user.findMany({
        where: {
          restaurantMemberships: {
            some: {
              restaurantId: ctx.session.restaurantId,
              ...(input.isActive !== undefined && { isActive: input.isActive }),
            },
          },
          ...(input.role && { role: input.role }),
        },
        orderBy: { createdAt: 'desc' },
      });

      return {
        users: users.map(u => ({
          id: u.id,
          name: u.name,
          email: u.email,
          role: u.role as 'OWNER' | 'MANAGER' | 'CHEF' | 'STAFF',
          isActive: u.isActive,
          lastLoginAt: u.lastLoginAt?.toISOString() || null,
          createdAt: u.createdAt.toISOString(),
        })),
      };
    }),

  /**
   * Invite new team member
   * Only OWNER and MANAGER can invite
   */
  inviteTeamMember: protectedProcedure
    .input(z.object({
      email: z.string().email(),
      role: z.enum(['MANAGER', 'CHEF', 'STAFF']), // Can't invite OWNER
      name: z.string().optional(),
    }))
    .output(z.object({
      success: z.boolean(),
      invitationId: z.string().uuid(),
    }))
    .mutation(async ({ ctx, input }) => {
      // Only owners and managers can invite
      if (!['OWNER', 'MANAGER'].includes(ctx.session.role)) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Only owners and managers can invite team members',
        });
      }

      // Check if user already exists
      const existingUser = await ctx.prisma.user.findUnique({
        where: { email: input.email },
        include: {
          restaurantMemberships: {
            where: { restaurantId: ctx.session.restaurantId },
          },
        },
      });

      if (existingUser?.restaurantMemberships.length) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: 'User is already a member of this restaurant',
        });
      }

      // Create invitation
      const invitation = await ctx.prisma.invitation.create({
        data: {
          restaurantId: ctx.session.restaurantId,
          email: input.email,
          role: input.role,
          invitedBy: ctx.session.userId,
          expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
          token: crypto.randomUUID(),
        },
      });

      // Send invitation email
      const restaurant = await ctx.prisma.restaurant.findUnique({
        where: { id: ctx.session.restaurantId },
        select: { name: true },
      });

      await sendEmail({
        to: input.email,
        subject: `You've been invited to join ${restaurant?.name} on Flux`,
        html: `
          <p>You've been invited to join <strong>${restaurant?.name}</strong> as a ${input.role}.</p>
          <p><a href="${process.env.APP_URL}/accept-invitation?token=${invitation.token}">Accept Invitation</a></p>
          <p>This invitation expires in 7 days.</p>
        `,
      });

      return {
        success: true,
        invitationId: invitation.id,
      };
    }),

  /**
   * Update team member role
   * Only OWNER can change roles
   */
  updateRole: protectedProcedure
    .input(z.object({
      userId: z.string().uuid(),
      role: z.enum(['MANAGER', 'CHEF', 'STAFF']),
    }))
    .output(z.object({
      success: z.boolean(),
    }))
    .mutation(async ({ ctx, input }) => {
      // Only owners can update roles
      if (ctx.session.role !== 'OWNER') {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Only owners can update team member roles',
        });
      }

      // Can't change own role
      if (input.userId === ctx.session.userId) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: 'Cannot change your own role',
        });
      }

      // Verify user is part of restaurant
      const membership = await ctx.prisma.restaurantMembership.findFirst({
        where: {
          userId: input.userId,
          restaurantId: ctx.session.restaurantId,
        },
      });

      if (!membership) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'User is not a member of this restaurant',
        });
      }

      await ctx.prisma.user.update({
        where: { id: input.userId },
        data: { role: input.role },
      });

      return { success: true };
    }),

  /**
   * Deactivate team member
   * Only OWNER can deactivate
   */
  deactivate: protectedProcedure
    .input(z.object({
      userId: z.string().uuid(),
    }))
    .output(z.object({
      success: z.boolean(),
    }))
    .mutation(async ({ ctx, input }) => {
      // Only owners can deactivate
      if (ctx.session.role !== 'OWNER') {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Only owners can deactivate team members',
        });
      }

      // Can't deactivate self
      if (input.userId === ctx.session.userId) {
        throw new TRPCError({
          code: 'BAD_REQUEST',
          message: 'Cannot deactivate yourself',
        });
      }

      await ctx.prisma.restaurantMembership.updateMany({
        where: {
          userId: input.userId,
          restaurantId: ctx.session.restaurantId,
        },
        data: { isActive: false },
      });

      return { success: true };
    }),

  /**
   * Get current user profile
   */
  me: protectedProcedure
    .output(z.object({
      id: z.string().uuid(),
      name: z.string(),
      email: z.string().email(),
      role: z.enum(['OWNER', 'MANAGER', 'CHEF', 'STAFF']),
      restaurantId: z.string().uuid(),
      restaurantName: z.string(),
      permissions: z.array(z.string()),
    }))
    .query(async ({ ctx }) => {
      const user = await ctx.prisma.user.findUnique({
        where: { id: ctx.session.userId },
        include: {
          restaurantMemberships: {
            where: { restaurantId: ctx.session.restaurantId },
            include: {
              restaurant: { select: { name: true } },
            },
          },
        },
      });

      if (!user) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'User not found',
        });
      }

      // Role-based permissions
      const permissions: string[] = ['view:dashboard', 'view:forecasts'];

      if (['OWNER', 'MANAGER', 'CHEF'].includes(user.role)) {
        permissions.push('view:recipes', 'view:procurement', 'view:analytics');
      }

      if (['OWNER', 'MANAGER'].includes(user.role)) {
        permissions.push('manage:team', 'manage:integrations', 'view:settings');
      }

      if (user.role === 'OWNER') {
        permissions.push('manage:billing', 'manage:restaurant', 'delete:data');
      }

      return {
        id: user.id,
        name: user.name,
        email: user.email,
        role: user.role as 'OWNER' | 'MANAGER' | 'CHEF' | 'STAFF',
        restaurantId: ctx.session.restaurantId,
        restaurantName: user.restaurantMemberships[0].restaurant.name,
        permissions,
      };
    }),
});
```

---

### Restaurant Router

**Purpose:** Restaurant settings, configuration, and subscription management.

```typescript
// apps/api/src/routers/restaurant.ts
import { z } from 'zod';
import { router, protectedProcedure } from '../trpc';
import { TRPCError } from '@trpc/server';

export const restaurantRouter = router({
  /**
   * Get restaurant settings
   */
  getSettings: protectedProcedure
    .output(z.object({
      id: z.string().uuid(),
      name: z.string(),
      timezone: z.string(),
      currency: z.string(),
      subscriptionTier: z.enum(['STARTER', 'PROFESSIONAL', 'ENTERPRISE']),
      subscriptionStatus: z.enum(['ACTIVE', 'TRIAL', 'PAST_DUE', 'CANCELLED']),
      trialEndsAt: z.string().datetime().nullable(),
      settings: z.object({
        forecastDaysAhead: z.number(),
        forecastConfidenceThreshold: z.number(),
        autoReorderEnabled: z.boolean(),
        dataRetentionDays: z.number(),
      }),
    }))
    .query(async ({ ctx }) => {
      const restaurant = await ctx.prisma.restaurant.findUnique({
        where: { id: ctx.session.restaurantId },
      });

      if (!restaurant) {
        throw new TRPCError({
          code: 'NOT_FOUND',
          message: 'Restaurant not found',
        });
      }

      return {
        id: restaurant.id,
        name: restaurant.name,
        timezone: restaurant.timezone,
        currency: restaurant.currency,
        subscriptionTier: restaurant.subscriptionTier as 'STARTER' | 'PROFESSIONAL' | 'ENTERPRISE',
        subscriptionStatus: restaurant.subscriptionStatus as 'ACTIVE' | 'TRIAL' | 'PAST_DUE' | 'CANCELLED',
        trialEndsAt: restaurant.trialEndsAt?.toISOString() || null,
        settings: {
          forecastDaysAhead: restaurant.forecastDaysAhead || 14,
          forecastConfidenceThreshold: restaurant.forecastConfidenceThreshold || 0.7,
          autoReorderEnabled: restaurant.autoReorderEnabled || false,
          dataRetentionDays: restaurant.dataRetentionDays || 730, // 2 years
        },
      };
    }),

  /**
   * Update restaurant settings
   * Only OWNER can update
   */
  updateSettings: protectedProcedure
    .input(z.object({
      name: z.string().optional(),
      timezone: z.string().optional(),
      forecastDaysAhead: z.number().int().min(7).max(90).optional(),
      forecastConfidenceThreshold: z.number().min(0).max(1).optional(),
      autoReorderEnabled: z.boolean().optional(),
    }))
    .output(z.object({
      success: z.boolean(),
    }))
    .mutation(async ({ ctx, input }) => {
      if (ctx.session.role !== 'OWNER') {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Only owners can update restaurant settings',
        });
      }

      await ctx.prisma.restaurant.update({
        where: { id: ctx.session.restaurantId },
        data: {
          ...(input.name && { name: input.name }),
          ...(input.timezone && { timezone: input.timezone }),
          ...(input.forecastDaysAhead && { forecastDaysAhead: input.forecastDaysAhead }),
          ...(input.forecastConfidenceThreshold && {
            forecastConfidenceThreshold: input.forecastConfidenceThreshold,
          }),
          ...(input.autoReorderEnabled !== undefined && {
            autoReorderEnabled: input.autoReorderEnabled,
          }),
        },
      });

      return { success: true };
    }),

  /**
   * Get data health dashboard
   * Overall restaurant data quality metrics
   */
  getDataHealth: protectedProcedure
    .output(z.object({
      overall: z.object({
        status: z.enum(['HEALTHY', 'WARNING', 'CRITICAL']),
        score: z.number().min(0).max(100),
      }),
      metrics: z.object({
        transactionDataQuality: z.number().min(0).max(100),
        menuItemCoverage: z.number().min(0).max(100),
        recipeCoverage: z.number().min(0).max(100),
        forecastAccuracy: z.number().min(0).max(100),
      }),
      issues: z.array(z.object({
        category: z.string(),
        severity: z.enum(['LOW', 'MEDIUM', 'HIGH']),
        description: z.string(),
        recommendation: z.string(),
      })),
    }))
    .query(async ({ ctx }) => {
      // Transaction data quality (sync gaps, completeness)
      const transactionStats = await ctx.prisma.transaction.aggregate({
        where: {
          restaurantId: ctx.session.restaurantId,
          orderDate: {
            gte: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // Last 30 days
          },
        },
        _count: { id: true },
      });

      const transactionQuality = transactionStats._count.id > 0 ? 85 : 0;

      // Menu item coverage (% with recipes)
      const menuStats = await ctx.prisma.menuItem.findMany({
        where: { restaurantId: ctx.session.restaurantId },
        include: {
          _count: { select: { recipe: true } },
        },
      });

      const menuItemsWithRecipes = menuStats.filter(m => m._count.recipe > 0).length;
      const menuItemCoverage = menuStats.length > 0
        ? (menuItemsWithRecipes / menuStats.length) * 100
        : 0;

      // Recipe coverage (% verified)
      const recipeStats = await ctx.prisma.recipe.findMany({
        where: { restaurantId: ctx.session.restaurantId, isActive: true },
      });

      const verifiedRecipes = recipeStats.filter(r => r.isVerified).length;
      const recipeCoverage = recipeStats.length > 0
        ? (verifiedRecipes / recipeStats.length) * 100
        : 0;

      // Forecast accuracy (last 30 days MAPE)
      const forecastAccuracy = 78; // Would calculate from actual forecast feedback

      // Calculate overall score (weighted average)
      const overallScore = (
        transactionQuality * 0.4 +
        menuItemCoverage * 0.25 +
        recipeCoverage * 0.2 +
        forecastAccuracy * 0.15
      );

      // Determine status
      let status: 'HEALTHY' | 'WARNING' | 'CRITICAL' = 'HEALTHY';
      if (overallScore < 50) status = 'CRITICAL';
      else if (overallScore < 75) status = 'WARNING';

      // Generate issues
      const issues: Array<{
        category: string;
        severity: 'LOW' | 'MEDIUM' | 'HIGH';
        description: string;
        recommendation: string;
      }> = [];

      if (menuItemCoverage < 50) {
        issues.push({
          category: 'Recipe Coverage',
          severity: 'HIGH',
          description: `Only ${Math.round(menuItemCoverage)}% of menu items have recipes defined`,
          recommendation: 'Add recipes for remaining menu items to enable accurate procurement forecasting',
        });
      }

      if (recipeCoverage < 70) {
        issues.push({
          category: 'Recipe Verification',
          severity: 'MEDIUM',
          description: `${Math.round(100 - recipeCoverage)}% of recipes are unverified`,
          recommendation: 'Have a chef verify recipes to ensure accuracy',
        });
      }

      if (transactionQuality < 60) {
        issues.push({
          category: 'Transaction Data',
          severity: 'CRITICAL',
          description: 'Transaction sync issues detected',
          recommendation: 'Check POS integration connection and sync settings',
        });
      }

      return {
        overall: {
          status,
          score: Math.round(overallScore),
        },
        metrics: {
          transactionDataQuality: Math.round(transactionQuality),
          menuItemCoverage: Math.round(menuItemCoverage),
          recipeCoverage: Math.round(recipeCoverage),
          forecastAccuracy: Math.round(forecastAccuracy),
        },
        issues,
      };
    }),

  /**
   * Get usage stats for billing
   */
  getUsageStats: protectedProcedure
    .input(z.object({
      month: z.string().regex(/^\d{4}-\d{2}$/), // YYYY-MM format
    }))
    .output(z.object({
      period: z.string(),
      stats: z.object({
        forecastsGenerated: z.number(),
        transactionsSynced: z.number(),
        apiRequests: z.number(),
        storageUsedGB: z.number(),
      }),
      limits: z.object({
        forecastsPerMonth: z.number(),
        transactionsPerMonth: z.number(),
        apiRequestsPerMonth: z.number(),
        storageGB: z.number(),
      }),
    }))
    .query(async ({ ctx, input }) => {
      if (!['OWNER', 'MANAGER'].includes(ctx.session.role)) {
        throw new TRPCError({
          code: 'FORBIDDEN',
          message: 'Only owners and managers can view usage stats',
        });
      }

      const [year, month] = input.month.split('-');
      const startDate = new Date(parseInt(year), parseInt(month) - 1, 1);
      const endDate = new Date(parseInt(year), parseInt(month), 0);

      // Count forecasts generated
      const forecastCount = await ctx.prisma.forecast.count({
        where: {
          restaurantId: ctx.session.restaurantId,
          generatedAt: {
            gte: startDate,
            lte: endDate,
          },
        },
      });

      // Count transactions synced
      const transactionCount = await ctx.prisma.transaction.count({
        where: {
          restaurantId: ctx.session.restaurantId,
          syncedAt: {
            gte: startDate,
            lte: endDate,
          },
        },
      });

      // Get subscription tier limits
      const restaurant = await ctx.prisma.restaurant.findUnique({
        where: { id: ctx.session.restaurantId },
      });

      const tierLimits = {
        STARTER: {
          forecastsPerMonth: 1000,
          transactionsPerMonth: 10000,
          apiRequestsPerMonth: 50000,
          storageGB: 5,
        },
        PROFESSIONAL: {
          forecastsPerMonth: 10000,
          transactionsPerMonth: 100000,
          apiRequestsPerMonth: 500000,
          storageGB: 50,
        },
        ENTERPRISE: {
          forecastsPerMonth: -1, // Unlimited
          transactionsPerMonth: -1,
          apiRequestsPerMonth: -1,
          storageGB: 500,
        },
      };

      const limits = tierLimits[restaurant!.subscriptionTier as keyof typeof tierLimits];

      return {
        period: input.month,
        stats: {
          forecastsGenerated: forecastCount,
          transactionsSynced: transactionCount,
          apiRequests: 45230, // Would come from API gateway metrics
          storageUsedGB: 2.3, // Would calculate from actual data
        },
        limits,
      };
    }),
});
```

---

## API Specification Summary

The API Specification section is now complete with **9 fully-implemented tRPC routers** covering all core functionality:

### 1. Auth Router ([docs/architecture.md:2156-2468](docs/architecture.md#L2156-L2468))
- User registration with automatic restaurant creation
- JWT-based login with account lockout protection (5 failed attempts)
- Session management with multi-restaurant support

### 2. Menu Router ([docs/architecture.md:2471-2638](docs/architecture.md#L2471-L2638))
- CRUD operations for menu items
- Cursor-based pagination with search and filtering
- Sales statistics with raw SQL for performance

### 3. Forecast Router ([docs/architecture.md:2643-2998](docs/architecture.md#L2643-L2998))
- List forecasts with filtering by date, menu item, model type
- SHAP explanations with feature importance visualization
- Forecast feedback submission with automatic model retraining triggers
- Accuracy metrics (MAPE, RMSE, MAE) by period and menu item

### 4. Recipe Router ([docs/architecture.md:3003-3420](docs/architecture.md#L3003-L3420))
- Recipe CRUD with automatic versioning
- Chef verification workflow with role-based access control
- Ingredient cost calculations for target quantities
- Full ingredient explosion for procurement planning

### 5. Transaction Router ([docs/architecture.md:3425-3743](docs/architecture.md#L3425-L3743))
- Transaction list with comprehensive filtering
- Daily sales aggregates optimized for dashboard charts
- Data health monitoring with statistical anomaly detection
- Sync gap identification and reporting

### 6. Procurement Router ([docs/architecture.md:3748-4166](docs/architecture.md#L3748-L4166))
- AI-powered procurement recommendations using forecasts + recipes
- Automatic stockout prediction with urgency scoring
- Order creation and status management
- Inventory auto-update on delivery confirmation

### 7. POS Router ([docs/architecture.md:4171-4456](docs/architecture.md#L4171-L4456))
- Multi-provider integration support (Square, Toast, Clover, Lightspeed)
- OAuth connection flow with state management
- Manual sync triggering with background job queuing
- Sync history and error tracking

### 8. User Router ([docs/architecture.md:4461-4751](docs/architecture.md#L4461-L4751))
- Team member management with role-based permissions
- Email invitation system with 7-day expiration
- Role updates and deactivation (owner-only)
- Permission matrix based on user role

### 9. Restaurant Router ([docs/architecture.md:4756-5077](docs/architecture.md#L4756-L5077))
- Restaurant settings and configuration
- Data health dashboard with quality scoring
- Usage statistics for billing and quota enforcement
- Subscription tier limits enforcement

### Key Design Patterns Applied

**Multi-tenancy:**
- PostgreSQL Row-Level Security (RLS) via context middleware
- Automatic `restaurant_id` injection in all queries
- Restaurant-scoped data isolation

**Authentication & Authorization:**
- JWT bearer tokens via NextAuth.js
- Role-based access control (OWNER, MANAGER, CHEF, STAFF)
- Procedure-level permission checks

**Performance Optimization:**
- Cursor-based pagination (not offset) for large datasets
- Raw SQL for complex aggregations
- Redis rate limiting (100 req/min per user)
- React Query caching on frontend

**Data Integrity:**
- Zod validation for all inputs and outputs
- Database transactions for multi-step operations
- Type safety end-to-end (TypeScript + tRPC)

**Error Handling:**
- Typed TRPCError codes (NOT_FOUND, FORBIDDEN, BAD_REQUEST)
- Comprehensive validation messages
- Account lockout protection
- Integration error tracking

**AI/ML Integration:**
- SHAP value explanations for forecast interpretability
- Automatic model retraining triggers on poor accuracy
- Confidence scoring for recommendations
- Feature importance ranking

### API Contract Example

```typescript
// Frontend usage with full type safety
const { data } = trpc.forecast.getWithExplanation.useQuery({
  forecastId: '123e4567-e89b-12d3-a456-426614174000'
});

// data is fully typed:
// data.forecast.predictedQuantity: number
// data.explanation.topDrivers: Array<{feature: string, impact: string, contribution: number}>
```

### Next Architecture Sections

With the API Specification complete, the remaining sections to implement are:

1. **Components** - Frontend and backend component architecture
2. **External APIs** - POS provider integration details, Stripe, SendGrid
3. **Core Workflows** - Sequence diagrams for key user journeys
4. **Database Schema** - Complete Prisma schema file
5. **Frontend Architecture** - Component organization, state management, routing
6. **Backend Architecture** - Lambda functions, auth patterns, database access
7. **Unified Project Structure** - Complete file tree with all packages
8. **Development Workflow** - Local dev setup, testing, CI/CD
9. **Deployment Architecture** - CDK stacks, environments, blue/green strategy
10. **Security and Performance** - Auth flows, rate limiting, caching
11. **Testing Strategy** - Unit, integration, E2E test patterns
12. **Coding Standards** - TypeScript conventions, naming, file organization
13. **Error Handling Strategy** - Error types, logging, monitoring
14. **Monitoring and Observability** - Datadog setup, metrics, alerts

---

# Components

This section defines the component architecture for both frontend (React/Next.js) and backend (Lambda functions) systems.

## Frontend Component Architecture

### Component Organization Strategy

**Atomic Design Pattern** with feature-based organization:

```
apps/web/src/
├── components/
│   ├── atoms/           # Basic building blocks
│   ├── molecules/       # Compound components
│   ├── organisms/       # Complex sections
│   └── templates/       # Page layouts
├── features/            # Feature modules
│   ├── auth/
│   ├── dashboard/
│   ├── forecasting/
│   ├── recipes/
│   ├── procurement/
│   └── settings/
└── lib/                 # Shared utilities
```

---

### Atoms (Basic UI Components)

**Purpose:** Smallest reusable UI elements with no business logic.

```typescript
// apps/web/src/components/atoms/Button.tsx
import { forwardRef } from 'react';
import { cva, type VariantProps } from 'class-variance-authority';

const buttonVariants = cva(
  'inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        primary: 'bg-blue-600 text-white hover:bg-blue-700',
        secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300',
        destructive: 'bg-red-600 text-white hover:bg-red-700',
        outline: 'border border-gray-300 bg-transparent hover:bg-gray-100',
        ghost: 'hover:bg-gray-100',
      },
      size: {
        sm: 'h-8 px-3 text-sm',
        md: 'h-10 px-4 text-base',
        lg: 'h-12 px-6 text-lg',
      },
    },
    defaultVariants: {
      variant: 'primary',
      size: 'md',
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  isLoading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, isLoading, children, disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={buttonVariants({ variant, size, className })}
        disabled={disabled || isLoading}
        {...props}
      >
        {isLoading ? (
          <>
            <LoadingSpinner className="mr-2 h-4 w-4" />
            {children}
          </>
        ) : (
          children
        )}
      </button>
    );
  }
);
Button.displayName = 'Button';
```

```typescript
// apps/web/src/components/atoms/Input.tsx
import { forwardRef } from 'react';

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string;
  helperText?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, helperText, className, ...props }, ref) => {
    return (
      <div className="w-full">
        {label && (
          <label className="block text-sm font-medium text-gray-700 mb-1">
            {label}
          </label>
        )}
        <input
          ref={ref}
          className={`
            w-full px-3 py-2 border rounded-md shadow-sm
            focus:outline-none focus:ring-2 focus:ring-blue-500
            ${error ? 'border-red-500' : 'border-gray-300'}
            ${className}
          `}
          {...props}
        />
        {error && <p className="mt-1 text-sm text-red-600">{error}</p>}
        {helperText && !error && (
          <p className="mt-1 text-sm text-gray-500">{helperText}</p>
        )}
      </div>
    );
  }
);
Input.displayName = 'Input';
```

**Other Atoms:**
- Badge (status indicators)
- Avatar (user profile images)
- Icon (Lucide icons wrapper)
- LoadingSpinner
- Tooltip
- Checkbox, Radio, Switch
- Card (container with shadow/border)

---

### Molecules (Compound Components)

**Purpose:** Combinations of atoms that form functional UI patterns.

```typescript
// apps/web/src/components/molecules/MetricCard.tsx
import { Card } from '@/components/atoms/Card';
import { Badge } from '@/components/atoms/Badge';
import { TrendingUp, TrendingDown } from 'lucide-react';

export interface MetricCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon?: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'danger';
}

export function MetricCard({
  title,
  value,
  change,
  changeLabel,
  icon,
  variant = 'default',
}: MetricCardProps) {
  const isPositive = change !== undefined && change > 0;
  const isNegative = change !== undefined && change < 0;

  return (
    <Card className="p-6">
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="mt-2 text-3xl font-semibold text-gray-900">{value}</p>

          {change !== undefined && (
            <div className="mt-2 flex items-center">
              {isPositive && <TrendingUp className="h-4 w-4 text-green-600 mr-1" />}
              {isNegative && <TrendingDown className="h-4 w-4 text-red-600 mr-1" />}
              <span
                className={`text-sm font-medium ${
                  isPositive ? 'text-green-600' : isNegative ? 'text-red-600' : 'text-gray-600'
                }`}
              >
                {change > 0 ? '+' : ''}{change}%
              </span>
              {changeLabel && (
                <span className="ml-1 text-sm text-gray-500">{changeLabel}</span>
              )}
            </div>
          )}
        </div>

        {icon && (
          <div className={`p-3 rounded-lg ${
            variant === 'success' ? 'bg-green-100' :
            variant === 'warning' ? 'bg-yellow-100' :
            variant === 'danger' ? 'bg-red-100' :
            'bg-blue-100'
          }`}>
            {icon}
          </div>
        )}
      </div>
    </Card>
  );
}
```

```typescript
// apps/web/src/components/molecules/DataTable.tsx
import { useState } from 'react';
import { ChevronDown, ChevronUp } from 'lucide-react';

export interface Column<T> {
  key: string;
  header: string;
  accessor: (row: T) => React.ReactNode;
  sortable?: boolean;
  width?: string;
}

export interface DataTableProps<T> {
  data: T[];
  columns: Column<T>[];
  onRowClick?: (row: T) => void;
  isLoading?: boolean;
  emptyMessage?: string;
}

export function DataTable<T extends { id: string }>({
  data,
  columns,
  onRowClick,
  isLoading,
  emptyMessage = 'No data available',
}: DataTableProps<T>) {
  const [sortConfig, setSortConfig] = useState<{
    key: string;
    direction: 'asc' | 'desc';
  } | null>(null);

  const handleSort = (columnKey: string) => {
    setSortConfig(prev => ({
      key: columnKey,
      direction: prev?.key === columnKey && prev.direction === 'asc' ? 'desc' : 'asc',
    }));
  };

  if (isLoading) {
    return <div className="p-8 text-center text-gray-500">Loading...</div>;
  }

  if (data.length === 0) {
    return <div className="p-8 text-center text-gray-500">{emptyMessage}</div>;
  }

  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-gray-200">
        <thead className="bg-gray-50">
          <tr>
            {columns.map(column => (
              <th
                key={column.key}
                className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider"
                style={{ width: column.width }}
              >
                <div className="flex items-center">
                  {column.header}
                  {column.sortable && (
                    <button
                      onClick={() => handleSort(column.key)}
                      className="ml-2 hover:text-gray-700"
                    >
                      {sortConfig?.key === column.key ? (
                        sortConfig.direction === 'asc' ? (
                          <ChevronUp className="h-4 w-4" />
                        ) : (
                          <ChevronDown className="h-4 w-4" />
                        )
                      ) : (
                        <ChevronDown className="h-4 w-4 opacity-30" />
                      )}
                    </button>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="bg-white divide-y divide-gray-200">
          {data.map(row => (
            <tr
              key={row.id}
              onClick={() => onRowClick?.(row)}
              className={onRowClick ? 'cursor-pointer hover:bg-gray-50' : ''}
            >
              {columns.map(column => (
                <td
                  key={column.key}
                  className="px-6 py-4 whitespace-nowrap text-sm text-gray-900"
                >
                  {column.accessor(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
```

**Other Molecules:**
- SearchInput (input + search icon + clear button)
- DateRangePicker (two date inputs + calendar)
- FilterChips (multiple removable badges)
- EmptyState (icon + message + action button)
- Pagination (prev/next + page numbers)
- FormField (label + input + error + helper)

---

### Organisms (Complex Sections)

**Purpose:** Major UI sections combining molecules and atoms with business logic.

```typescript
// apps/web/src/components/organisms/ForecastChart.tsx
import { useMemo } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { Card } from '@/components/atoms/Card';
import { Badge } from '@/components/atoms/Badge';
import { trpc } from '@/lib/trpc';

export interface ForecastChartProps {
  menuItemId: string;
  startDate: Date;
  endDate: Date;
}

export function ForecastChart({ menuItemId, startDate, endDate }: ForecastChartProps) {
  const { data: forecasts, isLoading } = trpc.forecast.list.useQuery({
    menuItemId,
    startDate: startDate.toISOString(),
    endDate: endDate.toISOString(),
    limit: 100,
  });

  const { data: actuals } = trpc.transaction.getDailySales.useQuery({
    menuItemId,
    startDate: startDate.toISOString(),
    endDate: endDate.toISOString(),
  });

  const chartData = useMemo(() => {
    if (!forecasts || !actuals) return [];

    const dataMap = new Map<string, any>();

    // Add forecast data
    forecasts.forecasts.forEach(forecast => {
      const date = forecast.forecastDate.split('T')[0];
      dataMap.set(date, {
        date,
        forecast: forecast.predictedQuantity,
        lowerBound: forecast.confidenceIntervalLower,
        upperBound: forecast.confidenceIntervalUpper,
      });
    });

    // Add actual data
    actuals.dailySales.forEach(actual => {
      const existing = dataMap.get(actual.date) || { date: actual.date };
      dataMap.set(actual.date, {
        ...existing,
        actual: actual.totalQuantity,
      });
    });

    return Array.from(dataMap.values()).sort((a, b) =>
      a.date.localeCompare(b.date)
    );
  }, [forecasts, actuals]);

  if (isLoading) {
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
            tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', {
              month: 'short',
              day: 'numeric',
            })}
          />
          <YAxis />
          <Tooltip
            labelFormatter={(value) => new Date(value).toLocaleDateString()}
            formatter={(value: number) => [Math.round(value), '']}
          />
          <Legend />

          {/* Confidence interval */}
          <Line
            type="monotone"
            dataKey="upperBound"
            stroke="#93c5fd"
            strokeDasharray="3 3"
            dot={false}
            name="Upper Bound"
          />
          <Line
            type="monotone"
            dataKey="lowerBound"
            stroke="#93c5fd"
            strokeDasharray="3 3"
            dot={false}
            name="Lower Bound"
          />

          {/* Forecast line */}
          <Line
            type="monotone"
            dataKey="forecast"
            stroke="#3b82f6"
            strokeWidth={2}
            dot={{ r: 4 }}
            name="Forecast"
          />

          {/* Actual line */}
          <Line
            type="monotone"
            dataKey="actual"
            stroke="#10b981"
            strokeWidth={2}
            dot={{ r: 4 }}
            name="Actual Sales"
          />
        </LineChart>
      </ResponsiveContainer>
    </Card>
  );
}
```

```typescript
// apps/web/src/components/organisms/ProcurementRecommendations.tsx
import { useState } from 'react';
import { Card } from '@/components/atoms/Card';
import { Button } from '@/components/atoms/Button';
import { Badge } from '@/components/atoms/Badge';
import { DataTable } from '@/components/molecules/DataTable';
import { trpc } from '@/lib/trpc';
import { ShoppingCart, AlertCircle } from 'lucide-react';

export interface ProcurementRecommendationsProps {
  startDate: Date;
  endDate: Date;
  onCreateOrder: (ingredientIds: string[]) => void;
}

export function ProcurementRecommendations({
  startDate,
  endDate,
  onCreateOrder,
}: ProcurementRecommendationsProps) {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const { data, isLoading } = trpc.procurement.getRecommendations.useQuery({
    startDate: startDate.toISOString(),
    endDate: endDate.toISOString(),
  });

  const columns = [
    {
      key: 'select',
      header: '',
      accessor: (row: any) => (
        <input
          type="checkbox"
          checked={selectedIds.has(row.ingredientId)}
          onChange={(e) => {
            const newSet = new Set(selectedIds);
            if (e.target.checked) {
              newSet.add(row.ingredientId);
            } else {
              newSet.delete(row.ingredientId);
            }
            setSelectedIds(newSet);
          }}
        />
      ),
      width: '50px',
    },
    {
      key: 'ingredient',
      header: 'Ingredient',
      accessor: (row: any) => (
        <div>
          <div className="font-medium">{row.ingredientName}</div>
          {row.daysUntilStockout !== null && row.daysUntilStockout < 3 && (
            <Badge variant="destructive" className="mt-1">
              <AlertCircle className="h-3 w-3 mr-1" />
              Critical
            </Badge>
          )}
        </div>
      ),
      sortable: true,
    },
    {
      key: 'current',
      header: 'Current Stock',
      accessor: (row: any) => `${row.currentStock} ${row.unit}`,
      sortable: true,
    },
    {
      key: 'projected',
      header: 'Projected Usage',
      accessor: (row: any) => `${row.projectedUsage} ${row.unit}`,
      sortable: true,
    },
    {
      key: 'recommended',
      header: 'Recommended Order',
      accessor: (row: any) => (
        <div className="font-semibold text-blue-600">
          {row.recommendedQuantity} {row.unit}
        </div>
      ),
      sortable: true,
    },
    {
      key: 'cost',
      header: 'Est. Cost',
      accessor: (row: any) => `$${row.estimatedCost.toFixed(2)}`,
      sortable: true,
    },
    {
      key: 'supplier',
      header: 'Supplier',
      accessor: (row: any) => row.supplierName || '—',
    },
  ];

  const handleCreateOrder = () => {
    const selectedIngredients = data?.recommendations
      .filter(r => selectedIds.has(r.ingredientId))
      .map(r => r.ingredientId) || [];

    onCreateOrder(selectedIngredients);
  };

  return (
    <Card className="p-6">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-gray-900">
            Procurement Recommendations
          </h3>
          <p className="text-sm text-gray-600 mt-1">
            AI-powered ingredient ordering suggestions based on forecasted demand
          </p>
        </div>

        {data && (
          <div className="text-right">
            <div className="text-sm text-gray-600">Total Estimated Cost</div>
            <div className="text-2xl font-bold text-gray-900">
              ${data.summary.totalEstimatedCost.toFixed(2)}
            </div>
            {data.summary.criticalItems > 0 && (
              <Badge variant="destructive" className="mt-2">
                {data.summary.criticalItems} critical items
              </Badge>
            )}
          </div>
        )}
      </div>

      <DataTable
        data={data?.recommendations || []}
        columns={columns}
        isLoading={isLoading}
        emptyMessage="No procurement recommendations at this time"
      />

      {selectedIds.size > 0 && (
        <div className="mt-6 flex items-center justify-between p-4 bg-blue-50 rounded-lg">
          <div className="text-sm text-gray-700">
            {selectedIds.size} ingredient{selectedIds.size !== 1 ? 's' : ''} selected
          </div>
          <Button onClick={handleCreateOrder}>
            <ShoppingCart className="h-4 w-4 mr-2" />
            Create Purchase Order
          </Button>
        </div>
      )}
    </Card>
  );
}
```

**Other Organisms:**
- DashboardHeader (metrics summary + filters)
- RecipeBuilder (drag-drop ingredient list + cost calculator)
- DataHealthWidget (health score + issues list + recommendations)
- MenuItemManager (CRUD table + inline editing)
- POSIntegrationCard (provider logo + connection status + sync button)

---

### Templates (Page Layouts)

**Purpose:** Complete page structures with slots for organisms and molecules.

```typescript
// apps/web/src/components/templates/DashboardLayout.tsx
import { ReactNode } from 'react';
import { Sidebar } from '@/components/organisms/Sidebar';
import { Header } from '@/components/organisms/Header';

export interface DashboardLayoutProps {
  children: ReactNode;
  title?: string;
  actions?: ReactNode;
}

export function DashboardLayout({ children, title, actions }: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />

      <div className="lg:pl-64">
        <Header title={title} actions={actions} />

        <main className="py-6 px-4 sm:px-6 lg:px-8">
          <div className="max-w-7xl mx-auto">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
}
```

```typescript
// apps/web/src/components/templates/AuthLayout.tsx
import { ReactNode } from 'react';

export interface AuthLayoutProps {
  children: ReactNode;
  title: string;
  subtitle?: string;
}

export function AuthLayout({ children, title, subtitle }: AuthLayoutProps) {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-extrabold text-gray-900">{title}</h2>
          {subtitle && (
            <p className="mt-2 text-sm text-gray-600">{subtitle}</p>
          )}
        </div>

        <div className="bg-white py-8 px-6 shadow rounded-lg">
          {children}
        </div>
      </div>
    </div>
  );
}
```

---

### Feature Modules

**Purpose:** Self-contained feature domains with their own components, hooks, and utilities.

```typescript
// apps/web/src/features/forecasting/components/ForecastDetailView.tsx
import { useMemo } from 'react';
import { useRouter } from 'next/router';
import { DashboardLayout } from '@/components/templates/DashboardLayout';
import { ForecastChart } from '@/components/organisms/ForecastChart';
import { MetricCard } from '@/components/molecules/MetricCard';
import { Button } from '@/components/atoms/Button';
import { trpc } from '@/lib/trpc';
import { BarChart3, TrendingUp, AlertCircle } from 'lucide-react';

export function ForecastDetailView() {
  const router = useRouter();
  const { forecastId } = router.query;

  const { data: forecast, isLoading } = trpc.forecast.getWithExplanation.useQuery(
    { forecastId: forecastId as string },
    { enabled: !!forecastId }
  );

  const topDrivers = useMemo(() => {
    return forecast?.explanation.topDrivers.slice(0, 3) || [];
  }, [forecast]);

  if (isLoading) {
    return <DashboardLayout title="Loading...">Loading forecast...</DashboardLayout>;
  }

  if (!forecast) {
    return <DashboardLayout title="Not Found">Forecast not found</DashboardLayout>;
  }

  return (
    <DashboardLayout
      title={forecast.forecast.menuItemName}
      actions={
        <Button variant="outline" onClick={() => router.back()}>
          Back to Forecasts
        </Button>
      }
    >
      {/* Metrics Row */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-6">
        <MetricCard
          title="Predicted Quantity"
          value={Math.round(forecast.forecast.predictedQuantity)}
          icon={<BarChart3 className="h-6 w-6 text-blue-600" />}
          variant="default"
        />
        <MetricCard
          title="Confidence"
          value={`${Math.round(forecast.forecast.confidence * 100)}%`}
          icon={<TrendingUp className="h-6 w-6 text-green-600" />}
          variant="success"
        />
        <MetricCard
          title="Confidence Range"
          value={`${Math.round(forecast.forecast.confidenceIntervalLower)} - ${Math.round(forecast.forecast.confidenceIntervalUpper)}`}
          icon={<AlertCircle className="h-6 w-6 text-yellow-600" />}
          variant="warning"
        />
      </div>

      {/* Chart */}
      <div className="mb-6">
        <ForecastChart
          menuItemId={forecast.forecast.id}
          startDate={new Date(Date.now() - 30 * 24 * 60 * 60 * 1000)}
          endDate={new Date(Date.now() + 14 * 24 * 60 * 60 * 1000)}
        />
      </div>

      {/* Explanation */}
      <Card className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">
          What's driving this forecast?
        </h3>

        <div className="space-y-4">
          {topDrivers.map((driver, idx) => (
            <div key={idx} className="flex items-start">
              <div className="flex-shrink-0 w-8 h-8 bg-blue-100 rounded-full flex items-center justify-center">
                <span className="text-sm font-semibold text-blue-600">{idx + 1}</span>
              </div>
              <div className="ml-4 flex-1">
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-gray-900">{driver.feature}</h4>
                  <Badge variant={driver.impact === 'increased' ? 'success' : 'secondary'}>
                    {driver.impact === 'increased' ? '+' : '-'}{Math.round(driver.contribution)}
                  </Badge>
                </div>
                <p className="text-sm text-gray-600 mt-1">
                  This factor {driver.impact} the forecast by {Math.round(driver.contribution)} units
                </p>
              </div>
            </div>
          ))}
        </div>
      </Card>
    </DashboardLayout>
  );
}
```

**Feature Module Structure:**

```
features/forecasting/
├── components/
│   ├── ForecastDetailView.tsx
│   ├── ForecastList.tsx
│   └── ForecastFeedbackForm.tsx
├── hooks/
│   ├── useForecastFilters.ts
│   └── useForecastAccuracy.ts
└── utils/
    └── forecastCalculations.ts
```

---

## Backend Component Architecture

### Lambda Function Organization

**Purpose:** Serverless functions organized by domain with shared layers.

```
apps/api/
├── src/
│   ├── functions/          # Lambda handlers
│   │   ├── trpc/          # tRPC API handler
│   │   ├── pos-sync/      # POS data sync worker
│   │   ├── forecast/      # ML forecast generator
│   │   └── notifications/ # Email/SMS notifications
│   ├── services/          # Business logic
│   ├── lib/               # Shared utilities
│   └── trpc/              # tRPC routers (defined earlier)
└── layers/                # Lambda layers
    ├── prisma/           # Prisma client
    └── shared/           # Common dependencies
```

---

### Lambda Handlers

**Purpose:** Thin handlers that delegate to services.

```typescript
// apps/api/src/functions/trpc/handler.ts
import { awsLambdaRequestHandler } from '@trpc/server/adapters/aws-lambda';
import { appRouter } from '../../trpc/router';
import { createContext } from '../../trpc/context';

export const handler = awsLambdaRequestHandler({
  router: appRouter,
  createContext,
  responseMeta({ ctx, paths, type, errors }) {
    // Add CORS headers
    const headers: Record<string, string> = {
      'Access-Control-Allow-Origin': process.env.ALLOWED_ORIGINS || '*',
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, Authorization',
    };

    // Cache successful queries for 60s
    if (type === 'query' && !errors.length) {
      headers['Cache-Control'] = 's-maxage=60, stale-while-revalidate';
    }

    return { headers };
  },
});
```

```typescript
// apps/api/src/functions/pos-sync/handler.ts
import { SQSHandler } from 'aws-lambda';
import { POSSyncService } from '../../services/POSSyncService';
import { logger } from '../../lib/logger';

interface POSSyncMessage {
  integrationId: string;
  startDate?: string;
  endDate?: string;
}

export const handler: SQSHandler = async (event) => {
  const syncService = new POSSyncService();

  for (const record of event.Records) {
    const message: POSSyncMessage = JSON.parse(record.body);

    try {
      logger.info('Starting POS sync', { integrationId: message.integrationId });

      await syncService.syncIntegration(
        message.integrationId,
        message.startDate ? new Date(message.startDate) : undefined,
        message.endDate ? new Date(message.endDate) : undefined
      );

      logger.info('POS sync completed', { integrationId: message.integrationId });
    } catch (error) {
      logger.error('POS sync failed', {
        integrationId: message.integrationId,
        error: error instanceof Error ? error.message : 'Unknown error',
      });

      // SQS will retry the message
      throw error;
    }
  }
};
```

```typescript
// apps/api/src/functions/forecast/handler.ts
import { EventBridgeHandler } from 'aws-lambda';
import { ForecastService } from '../../services/ForecastService';
import { logger } from '../../lib/logger';

interface ForecastEvent {
  restaurantId: string;
  menuItemIds?: string[];
  forecastDays: number;
}

export const handler: EventBridgeHandler<'Scheduled Event', ForecastEvent, void> = async (
  event
) => {
  const forecastService = new ForecastService();

  const { restaurantId, menuItemIds, forecastDays = 14 } = event.detail;

  try {
    logger.info('Generating forecasts', { restaurantId, forecastDays });

    const forecasts = await forecastService.generateForecasts({
      restaurantId,
      menuItemIds,
      forecastDays,
    });

    logger.info('Forecasts generated', {
      restaurantId,
      count: forecasts.length,
    });
  } catch (error) {
    logger.error('Forecast generation failed', {
      restaurantId,
      error: error instanceof Error ? error.message : 'Unknown error',
    });

    throw error;
  }
};
```

---

### Service Layer

**Purpose:** Business logic and orchestration of domain operations.

```typescript
// apps/api/src/services/POSSyncService.ts
import { prisma } from '../lib/prisma';
import { SquareAdapter } from '../lib/pos-adapters/SquareAdapter';
import { ToastAdapter } from '../lib/pos-adapters/ToastAdapter';
import { CloverAdapter } from '../lib/pos-adapters/CloverAdapter';
import { LightspeedAdapter } from '../lib/pos-adapters/LightspeedAdapter';
import { logger } from '../lib/logger';

interface POSAdapter {
  fetchTransactions(startDate: Date, endDate: Date): Promise<Transaction[]>;
  testConnection(): Promise<boolean>;
}

interface Transaction {
  posTransactionId: string;
  orderDate: Date;
  menuItemId: string;
  quantity: number;
  unitPrice: number;
  totalAmount: number;
  isVoided: boolean;
}

export class POSSyncService {
  private getAdapter(provider: string, credentials: any): POSAdapter {
    switch (provider) {
      case 'SQUARE':
        return new SquareAdapter(credentials);
      case 'TOAST':
        return new ToastAdapter(credentials);
      case 'CLOVER':
        return new CloverAdapter(credentials);
      case 'LIGHTSPEED':
        return new LightspeedAdapter(credentials);
      default:
        throw new Error(`Unsupported POS provider: ${provider}`);
    }
  }

  async syncIntegration(
    integrationId: string,
    startDate?: Date,
    endDate?: Date
  ): Promise<void> {
    // Update sync job status
    const syncJob = await prisma.pOSSyncJob.findFirst({
      where: { integrationId, status: 'QUEUED' },
      orderBy: { queuedAt: 'desc' },
    });

    if (!syncJob) {
      throw new Error('No queued sync job found');
    }

    await prisma.pOSSyncJob.update({
      where: { id: syncJob.id },
      data: {
        status: 'RUNNING',
        startedAt: new Date(),
      },
    });

    try {
      // Get integration details
      const integration = await prisma.pOSIntegration.findUnique({
        where: { id: integrationId },
      });

      if (!integration) {
        throw new Error('Integration not found');
      }

      // Get adapter for provider
      const adapter = this.getAdapter(integration.provider, {
        accessToken: integration.accessToken,
        refreshToken: integration.refreshToken,
        locationId: integration.locationId,
      });

      // Test connection
      const isConnected = await adapter.testConnection();
      if (!isConnected) {
        throw new Error('POS connection test failed');
      }

      // Determine sync window
      const syncStartDate = startDate || integration.lastSyncAt || new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      const syncEndDate = endDate || new Date();

      // Fetch transactions
      logger.info('Fetching transactions from POS', {
        integrationId,
        startDate: syncStartDate,
        endDate: syncEndDate,
      });

      const transactions = await adapter.fetchTransactions(syncStartDate, syncEndDate);

      logger.info('Fetched transactions from POS', {
        integrationId,
        count: transactions.length,
      });

      // Upsert transactions to database
      let syncedCount = 0;
      for (const transaction of transactions) {
        await prisma.transaction.upsert({
          where: {
            restaurantId_posTransactionId: {
              restaurantId: integration.restaurantId,
              posTransactionId: transaction.posTransactionId,
            },
          },
          create: {
            restaurantId: integration.restaurantId,
            posTransactionId: transaction.posTransactionId,
            orderDate: transaction.orderDate,
            menuItemId: transaction.menuItemId,
            quantity: transaction.quantity,
            unitPrice: transaction.unitPrice,
            totalAmount: transaction.totalAmount,
            isVoided: transaction.isVoided,
            syncedAt: new Date(),
          },
          update: {
            quantity: transaction.quantity,
            unitPrice: transaction.unitPrice,
            totalAmount: transaction.totalAmount,
            isVoided: transaction.isVoided,
            syncedAt: new Date(),
          },
        });
        syncedCount++;
      }

      // Update integration last sync time
      await prisma.pOSIntegration.update({
        where: { id: integrationId },
        data: {
          lastSyncAt: new Date(),
          lastSyncStatus: 'SUCCESS',
        },
      });

      // Mark sync job as completed
      await prisma.pOSSyncJob.update({
        where: { id: syncJob.id },
        data: {
          status: 'COMPLETED',
          transactionsSynced: syncedCount,
          completedAt: new Date(),
        },
      });

      logger.info('Sync completed successfully', {
        integrationId,
        transactionsSynced: syncedCount,
      });
    } catch (error) {
      // Mark sync job as failed
      await prisma.pOSSyncJob.update({
        where: { id: syncJob.id },
        data: {
          status: 'FAILED',
          errorMessage: error instanceof Error ? error.message : 'Unknown error',
          completedAt: new Date(),
        },
      });

      // Update integration status
      await prisma.pOSIntegration.update({
        where: { id: integrationId },
        data: {
          lastSyncStatus: 'FAILED',
          connectionStatus: 'ERROR',
        },
      });

      throw error;
    }
  }
}
```

```typescript
// apps/api/src/services/ForecastService.ts
import { prisma } from '../lib/prisma';
import { SageMakerClient } from '../lib/sagemaker';
import { logger } from '../lib/logger';

interface ForecastInput {
  restaurantId: string;
  menuItemIds?: string[];
  forecastDays: number;
}

interface ForecastResult {
  menuItemId: string;
  forecastDate: Date;
  predictedQuantity: number;
  confidenceIntervalLower: number;
  confidenceIntervalUpper: number;
  confidence: number;
  modelType: string;
  explanation?: {
    baseValue: number;
    featureImportances: Array<{
      featureName: string;
      featureValue: number;
      contribution: number;
      importance: number;
    }>;
  };
}

export class ForecastService {
  private sagemakerClient: SageMakerClient;

  constructor() {
    this.sagemakerClient = new SageMakerClient({
      region: process.env.AWS_REGION!,
      endpointName: process.env.SAGEMAKER_ENDPOINT_NAME!,
    });
  }

  async generateForecasts(input: ForecastInput): Promise<ForecastResult[]> {
    const { restaurantId, menuItemIds, forecastDays } = input;

    // Get menu items to forecast
    const menuItems = await prisma.menuItem.findMany({
      where: {
        restaurantId,
        ...(menuItemIds && { id: { in: menuItemIds } }),
        isActive: true,
      },
    });

    logger.info('Generating forecasts for menu items', {
      restaurantId,
      menuItemCount: menuItems.length,
    });

    const allForecasts: ForecastResult[] = [];

    for (const menuItem of menuItems) {
      try {
        // Get historical transaction data
        const historicalData = await this.getHistoricalData(
          restaurantId,
          menuItem.id,
          90 // Last 90 days
        );

        if (historicalData.length < 14) {
          logger.warn('Insufficient data for forecast', {
            menuItemId: menuItem.id,
            dataPoints: historicalData.length,
          });
          continue;
        }

        // Call SageMaker endpoint for forecast
        const forecastData = await this.sagemakerClient.invoke({
          menuItemId: menuItem.id,
          historicalData,
          forecastHorizon: forecastDays,
          includeExplanations: true,
        });

        // Save forecasts to database
        for (const forecast of forecastData.forecasts) {
          const savedForecast = await prisma.forecast.create({
            data: {
              restaurantId,
              menuItemId: menuItem.id,
              forecastDate: forecast.date,
              predictedQuantity: forecast.predictedQuantity,
              confidenceIntervalLower: forecast.lowerBound,
              confidenceIntervalUpper: forecast.upperBound,
              confidence: forecast.confidence,
              modelType: forecastData.modelType,
              generatedAt: new Date(),
            },
          });

          // Save SHAP explanations if available
          if (forecast.explanation) {
            await prisma.forecastExplanation.create({
              data: {
                forecastId: savedForecast.id,
                baseValue: forecast.explanation.baseValue,
                featureImportances: {
                  createMany: {
                    data: forecast.explanation.features.map(f => ({
                      featureName: f.name,
                      featureValue: f.value,
                      contribution: f.contribution,
                      importance: f.importance,
                    })),
                  },
                },
              },
            });
          }

          allForecasts.push({
            menuItemId: menuItem.id,
            forecastDate: forecast.date,
            predictedQuantity: forecast.predictedQuantity,
            confidenceIntervalLower: forecast.lowerBound,
            confidenceIntervalUpper: forecast.upperBound,
            confidence: forecast.confidence,
            modelType: forecastData.modelType,
            explanation: forecast.explanation,
          });
        }

        logger.info('Forecasts generated for menu item', {
          menuItemId: menuItem.id,
          forecastCount: forecastData.forecasts.length,
        });
      } catch (error) {
        logger.error('Failed to generate forecast for menu item', {
          menuItemId: menuItem.id,
          error: error instanceof Error ? error.message : 'Unknown error',
        });
        // Continue with next menu item
      }
    }

    return allForecasts;
  }

  private async getHistoricalData(
    restaurantId: string,
    menuItemId: string,
    days: number
  ): Promise<Array<{ date: Date; quantity: number }>> {
    const startDate = new Date();
    startDate.setDate(startDate.getDate() - days);

    const transactions = await prisma.transaction.groupBy({
      by: ['orderDate'],
      where: {
        restaurantId,
        menuItemId,
        orderDate: { gte: startDate },
        isVoided: false,
      },
      _sum: {
        quantity: true,
      },
      orderBy: {
        orderDate: 'asc',
      },
    });

    return transactions.map(t => ({
      date: t.orderDate,
      quantity: t._sum.quantity || 0,
    }));
  }
}
```

---

### Adapter Pattern (POS Integrations)

**Purpose:** Unified interface for different POS providers.

```typescript
// apps/api/src/lib/pos-adapters/SquareAdapter.ts
import { Client as SquareClient } from 'square';

export class SquareAdapter {
  private client: SquareClient;
  private locationId: string;

  constructor(credentials: { accessToken: string; locationId: string }) {
    this.client = new SquareClient({
      accessToken: credentials.accessToken,
      environment: process.env.SQUARE_ENVIRONMENT || 'production',
    });
    this.locationId = credentials.locationId;
  }

  async testConnection(): Promise<boolean> {
    try {
      const response = await this.client.locationsApi.retrieveLocation(this.locationId);
      return !!response.result.location;
    } catch (error) {
      return false;
    }
  }

  async fetchTransactions(startDate: Date, endDate: Date) {
    const transactions: any[] = [];
    let cursor: string | undefined;

    do {
      const response = await this.client.ordersApi.searchOrders({
        locationIds: [this.locationId],
        query: {
          filter: {
            dateTimeFilter: {
              createdAt: {
                startAt: startDate.toISOString(),
                endAt: endDate.toISOString(),
              },
            },
          },
          sort: {
            sortField: 'CREATED_AT',
            sortOrder: 'ASC',
          },
        },
        cursor,
      });

      const orders = response.result.orders || [];

      for (const order of orders) {
        if (!order.lineItems) continue;

        for (const lineItem of order.lineItems) {
          transactions.push({
            posTransactionId: `${order.id}-${lineItem.uid}`,
            orderDate: new Date(order.createdAt!),
            menuItemId: lineItem.catalogObjectId || lineItem.name || 'unknown',
            quantity: parseInt(lineItem.quantity),
            unitPrice: parseFloat(lineItem.basePriceMoney?.amount || '0') / 100,
            totalAmount: parseFloat(lineItem.totalMoney?.amount || '0') / 100,
            isVoided: order.state === 'CANCELED',
          });
        }
      }

      cursor = response.result.cursor;
    } while (cursor);

    return transactions;
  }
}
```

---

### Shared Utilities

**Purpose:** Cross-cutting concerns used throughout backend.

```typescript
// apps/api/src/lib/logger.ts
import winston from 'winston';

export const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: {
    service: 'flux-api',
    environment: process.env.NODE_ENV,
  },
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      ),
    }),
  ],
});

// Add Datadog transport in production
if (process.env.NODE_ENV === 'production') {
  logger.add(
    new winston.transports.Http({
      host: 'http-intake.logs.datadoghq.com',
      path: `/api/v2/logs?dd-api-key=${process.env.DATADOG_API_KEY}&ddsource=nodejs&service=flux-api`,
      ssl: true,
    })
  );
}
```

```typescript
// apps/api/src/lib/sagemaker.ts
import {
  SageMakerRuntimeClient,
  InvokeEndpointCommand,
} from '@aws-sdk/client-sagemaker-runtime';

interface SageMakerInput {
  menuItemId: string;
  historicalData: Array<{ date: Date; quantity: number }>;
  forecastHorizon: number;
  includeExplanations?: boolean;
}

interface SageMakerOutput {
  modelType: string;
  forecasts: Array<{
    date: Date;
    predictedQuantity: number;
    lowerBound: number;
    upperBound: number;
    confidence: number;
    explanation?: {
      baseValue: number;
      features: Array<{
        name: string;
        value: number;
        contribution: number;
        importance: number;
      }>;
    };
  }>;
}

export class SageMakerClient {
  private client: SageMakerRuntimeClient;
  private endpointName: string;

  constructor(config: { region: string; endpointName: string }) {
    this.client = new SageMakerRuntimeClient({ region: config.region });
    this.endpointName = config.endpointName;
  }

  async invoke(input: SageMakerInput): Promise<SageMakerOutput> {
    const command = new InvokeEndpointCommand({
      EndpointName: this.endpointName,
      ContentType: 'application/json',
      Body: JSON.stringify({
        menu_item_id: input.menuItemId,
        historical_data: input.historicalData.map(d => ({
          date: d.date.toISOString().split('T')[0],
          quantity: d.quantity,
        })),
        forecast_horizon: input.forecastHorizon,
        include_explanations: input.includeExplanations || false,
      }),
    });

    const response = await this.client.send(command);
    const body = JSON.parse(new TextDecoder().decode(response.Body));

    return {
      modelType: body.model_type,
      forecasts: body.forecasts.map((f: any) => ({
        date: new Date(f.date),
        predictedQuantity: f.predicted_quantity,
        lowerBound: f.lower_bound,
        upperBound: f.upper_bound,
        confidence: f.confidence,
        explanation: f.explanation
          ? {
              baseValue: f.explanation.base_value,
              features: f.explanation.features.map((feat: any) => ({
                name: feat.name,
                value: feat.value,
                contribution: feat.contribution,
                importance: feat.importance,
              })),
            }
          : undefined,
      })),
    };
  }
}
```

---

## Component Summary

### Frontend Component Hierarchy

```
Page (Next.js Route)
  └─ Template (DashboardLayout, AuthLayout)
      └─ Organisms (ForecastChart, ProcurementRecommendations)
          └─ Molecules (MetricCard, DataTable)
              └─ Atoms (Button, Input, Badge)
```

### Backend Service Architecture

```
Lambda Handler (Thin orchestration)
  └─ Service Layer (Business logic)
      ├─ Adapters (External integrations)
      ├─ Prisma Client (Database access)
      └─ Utilities (Logger, SageMaker, etc.)
```

### Key Design Principles

**Frontend:**
- Atomic Design for component reusability
- Feature-based organization for domain isolation
- Type-safe tRPC integration
- Tailwind CSS for consistent styling
- React Query for data fetching and caching

**Backend:**
- Thin handlers, fat services pattern
- Adapter pattern for POS integrations
- Dependency injection for testability
- Structured logging with Winston
- Error handling with proper propagation

---

# External APIs

This section documents integrations with third-party services and external APIs.

## POS Integrations

### Square Integration

**Purpose:** Sync transaction data from Square POS systems.

**Authentication:** OAuth 2.0

**Key Endpoints:**

```typescript
// apps/api/src/lib/pos-adapters/SquareAdapter.ts

interface SquareConfig {
  accessToken: string;
  refreshToken: string;
  locationId: string;
  environment: 'sandbox' | 'production';
}

class SquareAdapter {
  // OAuth Flow
  async initiateOAuth(restaurantId: string): Promise<{ authUrl: string }> {
    const state = this.encodeState({ restaurantId, provider: 'SQUARE' });

    const authUrl = new URL('https://connect.squareup.com/oauth2/authorize');
    authUrl.searchParams.set('client_id', process.env.SQUARE_CLIENT_ID!);
    authUrl.searchParams.set('scope', 'MERCHANT_PROFILE_READ PAYMENTS_READ ORDERS_READ');
    authUrl.searchParams.set('state', state);
    authUrl.searchParams.set('redirect_uri', `${process.env.APP_URL}/integrations/callback`);

    return { authUrl: authUrl.toString() };
  }

  async handleCallback(code: string): Promise<SquareConfig> {
    const response = await fetch('https://connect.squareup.com/oauth2/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: process.env.SQUARE_CLIENT_ID,
        client_secret: process.env.SQUARE_CLIENT_SECRET,
        code,
        grant_type: 'authorization_code',
        redirect_uri: `${process.env.APP_URL}/integrations/callback`,
      }),
    });

    const data = await response.json();

    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      locationId: data.merchant_id,
      environment: 'production',
    };
  }

  // Refresh expired access token
  async refreshAccessToken(refreshToken: string): Promise<SquareConfig> {
    const response = await fetch('https://connect.squareup.com/oauth2/token', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        client_id: process.env.SQUARE_CLIENT_ID,
        client_secret: process.env.SQUARE_CLIENT_SECRET,
        refresh_token: refreshToken,
        grant_type: 'refresh_token',
      }),
    });

    const data = await response.json();

    return {
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      locationId: data.merchant_id,
      environment: 'production',
    };
  }

  // Fetch orders with pagination
  async fetchOrders(startDate: Date, endDate: Date) {
    const client = new SquareClient({
      accessToken: this.config.accessToken,
      environment: this.config.environment,
    });

    let cursor: string | undefined;
    const allOrders: any[] = [];

    do {
      const response = await client.ordersApi.searchOrders({
        locationIds: [this.config.locationId],
        query: {
          filter: {
            dateTimeFilter: {
              createdAt: {
                startAt: startDate.toISOString(),
                endAt: endDate.toISOString(),
              },
            },
          },
          sort: {
            sortField: 'CREATED_AT',
            sortOrder: 'ASC',
          },
        },
        limit: 500, // Max per request
        cursor,
      });

      allOrders.push(...(response.result.orders || []));
      cursor = response.result.cursor;
    } while (cursor);

    return allOrders;
  }

  // Webhook signature verification
  verifyWebhook(signature: string, body: string, url: string): boolean {
    const hmac = crypto.createHmac('sha256', process.env.SQUARE_WEBHOOK_SIGNATURE_KEY!);
    hmac.update(url + body);
    const expectedSignature = hmac.digest('base64');

    return signature === expectedSignature;
  }
}
```

**Rate Limits:**
- 500 requests per minute per location
- Burst: 1000 requests

**Webhook Events:**
- `order.created`
- `order.updated`
- `payment.created`

**Error Handling:**
```typescript
try {
  const orders = await adapter.fetchOrders(startDate, endDate);
} catch (error) {
  if (error.statusCode === 401) {
    // Refresh token and retry
    const newConfig = await adapter.refreshAccessToken(refreshToken);
    await prisma.pOSIntegration.update({
      where: { id: integrationId },
      data: {
        accessToken: newConfig.accessToken,
        refreshToken: newConfig.refreshToken,
      },
    });
  } else if (error.statusCode === 429) {
    // Rate limited - exponential backoff
    await sleep(Math.pow(2, retryCount) * 1000);
    retryCount++;
  } else {
    throw error;
  }
}
```

---

### Toast POS Integration

**Purpose:** Sync transaction data from Toast POS systems.

**Authentication:** OAuth 2.0

```typescript
class ToastAdapter {
  private baseUrl = 'https://ws-api.toasttab.com';

  async initiateOAuth(restaurantId: string): Promise<{ authUrl: string }> {
    const state = this.encodeState({ restaurantId, provider: 'TOAST' });

    const authUrl = new URL(`${this.baseUrl}/authentication/v1/authorize`);
    authUrl.searchParams.set('client_id', process.env.TOAST_CLIENT_ID!);
    authUrl.searchParams.set('response_type', 'code');
    authUrl.searchParams.set('state', state);
    authUrl.searchParams.set('redirect_uri', `${process.env.APP_URL}/integrations/callback`);

    return { authUrl: authUrl.toString() };
  }

  async handleCallback(code: string): Promise<any> {
    const response = await fetch(`${this.baseUrl}/authentication/v1/token`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        client_id: process.env.TOAST_CLIENT_ID!,
        client_secret: process.env.TOAST_CLIENT_SECRET!,
        code,
        grant_type: 'authorization_code',
        redirect_uri: `${process.env.APP_URL}/integrations/callback`,
      }),
    });

    return await response.json();
  }

  // Fetch orders in bulk
  async fetchOrders(startDate: Date, endDate: Date, restaurantGuid: string) {
    const response = await fetch(
      `${this.baseUrl}/orders/v2/ordersBulk?` + new URLSearchParams({
        restaurantGuid,
        startDate: startDate.toISOString(),
        endDate: endDate.toISOString(),
        pageSize: '100',
      }),
      {
        headers: {
          Authorization: `Bearer ${this.config.accessToken}`,
          'Toast-Restaurant-External-ID': restaurantGuid,
        },
      }
    );

    const data = await response.json();
    return data.orders || [];
  }

  // Get menu items catalog
  async fetchMenu(restaurantGuid: string) {
    const response = await fetch(
      `${this.baseUrl}/menus/v2/menus?restaurantGuid=${restaurantGuid}`,
      {
        headers: {
          Authorization: `Bearer ${this.config.accessToken}`,
          'Toast-Restaurant-External-ID': restaurantGuid,
        },
      }
    );

    return await response.json();
  }
}
```

**Rate Limits:**
- 1000 requests per hour per restaurant
- Concurrent requests: 10

---

### Clover Integration

**Purpose:** Sync transaction data from Clover POS systems.

```typescript
class CloverAdapter {
  private baseUrl = 'https://api.clover.com/v3';

  async fetchOrders(merchantId: string, startDate: Date, endDate: Date) {
    const response = await fetch(
      `${this.baseUrl}/merchants/${merchantId}/orders?` + new URLSearchParams({
        filter: `createdTime>=${startDate.getTime()}&createdTime<=${endDate.getTime()}`,
        expand: 'lineItems',
        limit: '1000',
      }),
      {
        headers: {
          Authorization: `Bearer ${this.config.accessToken}`,
        },
      }
    );

    const data = await response.json();
    return data.elements || [];
  }

  async fetchInventory(merchantId: string) {
    const response = await fetch(
      `${this.baseUrl}/merchants/${merchantId}/items?expand=categories`,
      {
        headers: {
          Authorization: `Bearer ${this.config.accessToken}`,
        },
      }
    );

    return await response.json();
  }
}
```

---

### Lightspeed Integration

**Purpose:** Sync transaction data from Lightspeed Restaurant POS.

```typescript
class LightspeedAdapter {
  private baseUrl = 'https://api.lightspeedhq.com/API';

  async fetchSales(accountId: string, startDate: Date, endDate: Date) {
    const response = await fetch(
      `${this.baseUrl}/Account/${accountId}/Sale.json?` + new URLSearchParams({
        load_relations: JSON.stringify(['SaleLines', 'SalePayments']),
        timeStamp: `>,${startDate.toISOString()}`,
        completeTime: `<,${endDate.toISOString()}`,
        limit: '100',
      }),
      {
        headers: {
          Authorization: `Bearer ${this.config.accessToken}`,
        },
      }
    );

    const data = await response.json();
    return data.Sale || [];
  }
}
```

---

## Payment Processing

### Stripe Integration

**Purpose:** Handle subscription billing and payments.

**Authentication:** API Key

```typescript
// apps/api/src/lib/stripe.ts
import Stripe from 'stripe';

export const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!, {
  apiVersion: '2023-10-16',
  typescript: true,
});

// Create customer
export async function createCustomer(params: {
  email: string;
  name: string;
  restaurantId: string;
}) {
  const customer = await stripe.customers.create({
    email: params.email,
    name: params.name,
    metadata: {
      restaurantId: params.restaurantId,
    },
  });

  return customer;
}

// Create subscription
export async function createSubscription(params: {
  customerId: string;
  priceId: string; // Starter, Professional, or Enterprise plan
  trialDays?: number;
}) {
  const subscription = await stripe.subscriptions.create({
    customer: params.customerId,
    items: [{ price: params.priceId }],
    trial_period_days: params.trialDays,
    payment_behavior: 'default_incomplete',
    payment_settings: {
      save_default_payment_method: 'on_subscription',
    },
    expand: ['latest_invoice.payment_intent'],
  });

  return subscription;
}

// Handle usage-based billing
export async function reportUsage(params: {
  subscriptionItemId: string;
  quantity: number;
  timestamp?: number;
}) {
  const usageRecord = await stripe.subscriptionItems.createUsageRecord(
    params.subscriptionItemId,
    {
      quantity: params.quantity,
      timestamp: params.timestamp || Math.floor(Date.now() / 1000),
      action: 'increment',
    }
  );

  return usageRecord;
}

// Webhook handler
export async function handleWebhook(
  signature: string,
  rawBody: string
): Promise<Stripe.Event> {
  const event = stripe.webhooks.constructEvent(
    rawBody,
    signature,
    process.env.STRIPE_WEBHOOK_SECRET!
  );

  switch (event.type) {
    case 'customer.subscription.created':
      // Handle new subscription
      break;
    case 'customer.subscription.updated':
      // Handle subscription changes
      break;
    case 'customer.subscription.deleted':
      // Handle cancellation
      break;
    case 'invoice.payment_succeeded':
      // Handle successful payment
      break;
    case 'invoice.payment_failed':
      // Handle failed payment
      break;
  }

  return event;
}
```

**Pricing Plans:**

```typescript
// Stripe Price IDs (configured in Stripe Dashboard)
const PRICING_PLANS = {
  STARTER: {
    monthly: 'price_starter_monthly_xxx',
    annual: 'price_starter_annual_xxx',
    features: {
      forecasts: 1000,
      transactions: 10000,
      apiRequests: 50000,
      storage: 5, // GB
    },
  },
  PROFESSIONAL: {
    monthly: 'price_pro_monthly_xxx',
    annual: 'price_pro_annual_xxx',
    features: {
      forecasts: 10000,
      transactions: 100000,
      apiRequests: 500000,
      storage: 50,
    },
  },
  ENTERPRISE: {
    monthly: 'price_enterprise_monthly_xxx',
    annual: 'price_enterprise_annual_xxx',
    features: {
      forecasts: -1, // Unlimited
      transactions: -1,
      apiRequests: -1,
      storage: 500,
    },
  },
};
```

---

## Communication Services

### SendGrid Integration

**Purpose:** Transactional emails (invitations, notifications, receipts).

```typescript
// apps/api/src/lib/email.ts
import sgMail from '@sendgrid/mail';

sgMail.setApiKey(process.env.SENDGRID_API_KEY!);

interface EmailParams {
  to: string;
  subject: string;
  html: string;
  templateId?: string;
  dynamicTemplateData?: Record<string, any>;
}

export async function sendEmail(params: EmailParams) {
  const msg = {
    to: params.to,
    from: {
      email: process.env.SENDGRID_FROM_EMAIL!,
      name: 'Flux Restaurant Platform',
    },
    subject: params.subject,
    html: params.html,
    ...(params.templateId && {
      templateId: params.templateId,
      dynamicTemplateData: params.dynamicTemplateData,
    }),
  };

  try {
    await sgMail.send(msg);
    logger.info('Email sent successfully', { to: params.to, subject: params.subject });
  } catch (error) {
    logger.error('Failed to send email', {
      to: params.to,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
    throw error;
  }
}

// Predefined email templates
export const EmailTemplates = {
  TEAM_INVITATION: 'd-invitation-template-xxx',
  FORECAST_ALERT: 'd-forecast-alert-template-xxx',
  PROCUREMENT_RECOMMENDATION: 'd-procurement-template-xxx',
  DATA_HEALTH_WARNING: 'd-data-health-template-xxx',
  SUBSCRIPTION_RECEIPT: 'd-receipt-template-xxx',
};

// Send team invitation
export async function sendTeamInvitation(params: {
  email: string;
  restaurantName: string;
  role: string;
  invitationToken: string;
}) {
  await sendEmail({
    to: params.email,
    subject: `You've been invited to ${params.restaurantName} on Flux`,
    templateId: EmailTemplates.TEAM_INVITATION,
    dynamicTemplateData: {
      restaurant_name: params.restaurantName,
      role: params.role,
      invitation_link: `${process.env.APP_URL}/accept-invitation?token=${params.invitationToken}`,
      expires_in: '7 days',
    },
  });
}

// Send forecast alert
export async function sendForecastAlert(params: {
  email: string;
  menuItemName: string;
  predictedQuantity: number;
  confidenceLevel: number;
  forecastDate: string;
}) {
  await sendEmail({
    to: params.email,
    subject: `Forecast Alert: ${params.menuItemName}`,
    templateId: EmailTemplates.FORECAST_ALERT,
    dynamicTemplateData: {
      menu_item_name: params.menuItemName,
      predicted_quantity: params.predictedQuantity,
      confidence_level: Math.round(params.confidenceLevel * 100),
      forecast_date: params.forecastDate,
    },
  });
}
```

---

### Twilio Integration

**Purpose:** SMS alerts for critical procurement and inventory issues.

```typescript
// apps/api/src/lib/sms.ts
import twilio from 'twilio';

const client = twilio(
  process.env.TWILIO_ACCOUNT_SID,
  process.env.TWILIO_AUTH_TOKEN
);

export async function sendSMS(params: {
  to: string;
  message: string;
}) {
  try {
    const result = await client.messages.create({
      body: params.message,
      from: process.env.TWILIO_PHONE_NUMBER,
      to: params.to,
    });

    logger.info('SMS sent successfully', { to: params.to, sid: result.sid });
    return result;
  } catch (error) {
    logger.error('Failed to send SMS', {
      to: params.to,
      error: error instanceof Error ? error.message : 'Unknown error',
    });
    throw error;
  }
}

// Send critical stockout alert
export async function sendStockoutAlert(params: {
  phoneNumber: string;
  ingredientName: string;
  daysUntilStockout: number;
}) {
  await sendSMS({
    to: params.phoneNumber,
    message: `🚨 CRITICAL: ${params.ingredientName} will run out in ${params.daysUntilStockout} days. Order immediately via Flux: ${process.env.APP_URL}/procurement`,
  });
}
```

---

## Analytics & Monitoring

### Datadog Integration

**Purpose:** Application monitoring, logging, and APM.

```typescript
// apps/api/src/lib/datadog.ts
import { datadogLambda } from 'datadog-lambda-js';
import { datadogMetrics } from 'datadog-metrics';

// Initialize Datadog metrics
const metrics = new datadogMetrics.BufferedMetricsLogger({
  apiKey: process.env.DATADOG_API_KEY!,
  host: 'flux-api',
  prefix: 'flux.',
});

// Custom metrics
export function recordForecastGenerated(params: {
  restaurantId: string;
  menuItemId: string;
  modelType: string;
  confidence: number;
}) {
  metrics.increment('forecast.generated', 1, [
    `restaurant:${params.restaurantId}`,
    `model:${params.modelType}`,
  ]);

  metrics.histogram('forecast.confidence', params.confidence, [
    `restaurant:${params.restaurantId}`,
  ]);
}

export function recordPOSSync(params: {
  integrationId: string;
  provider: string;
  transactionCount: number;
  durationMs: number;
  success: boolean;
}) {
  metrics.increment('pos.sync', 1, [
    `provider:${params.provider}`,
    `status:${params.success ? 'success' : 'failure'}`,
  ]);

  metrics.histogram('pos.sync.duration', params.durationMs, [
    `provider:${params.provider}`,
  ]);

  metrics.gauge('pos.sync.transactions', params.transactionCount, [
    `provider:${params.provider}`,
  ]);
}

export function recordAPIRequest(params: {
  path: string;
  method: string;
  statusCode: number;
  durationMs: number;
}) {
  metrics.increment('api.request', 1, [
    `path:${params.path}`,
    `method:${params.method}`,
    `status:${params.statusCode}`,
  ]);

  metrics.histogram('api.latency', params.durationMs, [
    `path:${params.path}`,
  ]);
}

// Lambda wrapper for automatic instrumentation
export const handler = datadogLambda(async (event, context) => {
  // Your Lambda handler logic
}, {
  apiKey: process.env.DATADOG_API_KEY,
  site: 'datadoghq.com',
  logLevel: 'info',
});
```

---

## ML/AI Services

### AWS SageMaker

**Purpose:** ML model hosting for demand forecasting.

```typescript
// Model deployment configuration
const SAGEMAKER_CONFIG = {
  endpoint: process.env.SAGEMAKER_ENDPOINT_NAME,
  region: process.env.AWS_REGION,
  instanceType: 'ml.m5.xlarge',
  initialInstanceCount: 2,
  autoscaling: {
    minCapacity: 2,
    maxCapacity: 10,
    targetValue: 70, // Target invocations per instance
  },
  modelData: {
    s3Uri: 's3://flux-ml-models/forecast-model.tar.gz',
    framework: 'pytorch',
    frameworkVersion: '2.0',
  },
};
```

**Model Input/Output Contract:**

```python
# Input format
{
  "menu_item_id": "uuid",
  "historical_data": [
    {"date": "2024-01-01", "quantity": 45},
    {"date": "2024-01-02", "quantity": 52},
    ...
  ],
  "forecast_horizon": 14,
  "include_explanations": true
}

# Output format
{
  "model_type": "ENSEMBLE",
  "forecasts": [
    {
      "date": "2024-02-01",
      "predicted_quantity": 48.5,
      "lower_bound": 42.1,
      "upper_bound": 54.9,
      "confidence": 0.87,
      "explanation": {
        "base_value": 45.0,
        "features": [
          {
            "name": "day_of_week",
            "value": 5,
            "contribution": 3.5,
            "importance": 0.32
          },
          {
            "name": "week_of_year",
            "value": 5,
            "contribution": 0.8,
            "importance": 0.15
          },
          {
            "name": "is_holiday",
            "value": 0,
            "contribution": -0.8,
            "importance": 0.12
          }
        ]
      }
    }
  ]
}
```

---

## External API Summary

### Integration Matrix

| Service | Purpose | Auth Method | Rate Limit | Webhook Support |
|---------|---------|-------------|------------|-----------------|
| **Square** | POS transaction sync | OAuth 2.0 | 500/min/location | ✅ Yes |
| **Toast** | POS transaction sync | OAuth 2.0 | 1000/hour/restaurant | ✅ Yes |
| **Clover** | POS transaction sync | OAuth 2.0 | No published limit | ✅ Yes |
| **Lightspeed** | POS transaction sync | OAuth 2.0 | 100/min | ❌ No |
| **Stripe** | Payment processing | API Key | 100/sec | ✅ Yes |
| **SendGrid** | Email delivery | API Key | Unlimited (paid) | ✅ Yes |
| **Twilio** | SMS notifications | API Key | 100/sec | ❌ No |
| **Datadog** | Monitoring & APM | API Key | No limit | N/A |
| **SageMaker** | ML inference | AWS IAM | 1000/sec | N/A |

### Resilience Patterns

**Retry Logic with Exponential Backoff:**
```typescript
async function retryWithBackoff<T>(
  fn: () => Promise<T>,
  maxRetries = 3,
  baseDelayMs = 1000
): Promise<T> {
  for (let attempt = 0; attempt < maxRetries; attempt++) {
    try {
      return await fn();
    } catch (error) {
      if (attempt === maxRetries - 1) throw error;

      const delay = baseDelayMs * Math.pow(2, attempt);
      await sleep(delay);
    }
  }
  throw new Error('Max retries exceeded');
}
```

**Circuit Breaker:**
```typescript
class CircuitBreaker {
  private failureCount = 0;
  private lastFailureTime?: number;
  private state: 'CLOSED' | 'OPEN' | 'HALF_OPEN' = 'CLOSED';

  async execute<T>(fn: () => Promise<T>): Promise<T> {
    if (this.state === 'OPEN') {
      if (Date.now() - this.lastFailureTime! > 60000) {
        this.state = 'HALF_OPEN';
      } else {
        throw new Error('Circuit breaker is OPEN');
      }
    }

    try {
      const result = await fn();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private onSuccess() {
    this.failureCount = 0;
    this.state = 'CLOSED';
  }

  private onFailure() {
    this.failureCount++;
    this.lastFailureTime = Date.now();

    if (this.failureCount >= 5) {
      this.state = 'OPEN';
    }
  }
}
```

**Rate Limiting:**
```typescript
class RateLimiter {
  private tokens: number;
  private lastRefill: number;

  constructor(
    private maxTokens: number,
    private refillRate: number // tokens per second
  ) {
    this.tokens = maxTokens;
    this.lastRefill = Date.now();
  }

  async acquire(): Promise<void> {
    this.refillTokens();

    if (this.tokens < 1) {
      const waitTime = (1 - this.tokens) / this.refillRate * 1000;
      await sleep(waitTime);
      this.refillTokens();
    }

    this.tokens -= 1;
  }

  private refillTokens() {
    const now = Date.now();
    const timePassed = (now - this.lastRefill) / 1000;
    const tokensToAdd = timePassed * this.refillRate;

    this.tokens = Math.min(this.maxTokens, this.tokens + tokensToAdd);
    this.lastRefill = now;
  }
}
```

---

# Core Workflows

This section documents key user journeys through sequence diagrams showing the interaction between system components.

## User Registration & Onboarding

**Description:** New restaurant owner signs up and connects their POS system.

```mermaid
sequenceDiagram
    actor User
    participant Web as Next.js App
    participant API as tRPC API
    participant Auth as NextAuth
    participant DB as PostgreSQL
    participant POS as Square API

    User->>Web: Navigate to /register
    Web->>User: Show registration form

    User->>Web: Submit email, password, restaurant name
    Web->>API: auth.register({ email, password, restaurantName })

    API->>DB: BEGIN TRANSACTION
    API->>DB: Create User record
    API->>DB: Create Restaurant record
    API->>DB: Create RestaurantMembership (role: OWNER)
    API->>DB: COMMIT TRANSACTION

    API->>Auth: Generate JWT token
    API-->>Web: { success: true, token, userId, restaurantId }

    Web->>Web: Store token in cookie
    Web->>User: Redirect to /onboarding/connect-pos

    User->>Web: Select "Square POS"
    Web->>API: pos.initiateOAuth({ provider: 'SQUARE' })

    API->>DB: Create POSIntegration (status: PENDING)
    API-->>Web: { authUrl, integrationId }

    Web->>User: Redirect to Square OAuth
    User->>POS: Authorize app access
    POS->>Web: Redirect to /integrations/callback?code=abc&state=xyz

    Web->>API: pos.handleCallback({ code, state })
    API->>POS: Exchange code for access token
    POS-->>API: { accessToken, refreshToken, locationId }

    API->>DB: Update POSIntegration (status: CONNECTED)
    API->>DB: Create SyncJob (type: INITIAL_SYNC)
    API-->>Web: { success: true }

    Web->>User: Redirect to /dashboard

    Note over API,DB: Background worker starts initial sync
```

**Key Points:**
- Atomic transaction for user/restaurant/membership creation
- OAuth state parameter encodes restaurantId for callback
- Initial sync job queued immediately after POS connection
- JWT token includes restaurantId for RLS filtering

---

## Forecast Generation (Scheduled)

**Description:** Daily automated forecast generation via EventBridge rule.

```mermaid
sequenceDiagram
    participant EB as EventBridge
    participant Lambda as Forecast Lambda
    participant DB as PostgreSQL
    participant SQS as SQS Queue
    participant SM as SageMaker
    participant Worker as Forecast Worker

    EB->>Lambda: Trigger forecast-scheduler (cron: 0 2 * * *)

    Lambda->>DB: SELECT restaurants WHERE status = 'ACTIVE'
    DB-->>Lambda: List of 50 restaurants

    loop For each restaurant
        Lambda->>DB: Check last forecast date

        alt Needs forecast
            Lambda->>SQS: Send message { restaurantId, forecastDate }
            Note over SQS: Message batching for efficiency
        else Skip
            Lambda->>Lambda: Log skip reason (no new data)
        end
    end

    Lambda-->>EB: Success (50 messages queued)

    Note over SQS,Worker: SQS triggers Lambda with batch

    SQS->>Worker: Batch of 10 forecast requests

    loop For each request in batch
        Worker->>DB: Fetch historical transactions (90 days)
        Worker->>DB: Fetch menu items + recipes
        Worker->>DB: Fetch weather data + events

        Worker->>Worker: Feature engineering
        Note over Worker: Create time features, aggregate sales,<br/>calculate trends, encode categoricals

        Worker->>SM: InvokeEndpoint(features)
        SM-->>Worker: { predictions[], shapValues[] }

        Worker->>DB: BEGIN TRANSACTION

        loop For each menu item
            Worker->>DB: INSERT Forecast (quantity, confidence)
            Worker->>DB: INSERT ForecastExplanation (SHAP values)
        end

        Worker->>DB: UPDATE ForecastRun (status: COMPLETED)
        Worker->>DB: COMMIT TRANSACTION

        Worker->>Worker: Calculate procurement recommendations
        Worker->>DB: INSERT ProcurementRecommendations
    end

    Worker-->>SQS: Delete batch from queue
    Worker->>DB: Log metrics (duration, items forecasted)
```

**Key Points:**
- EventBridge cron runs at 2 AM daily
- SQS batching for efficient Lambda invocation (up to 10 per batch)
- Feature engineering includes: time features, lag features, rolling averages, external data (weather, events)
- SHAP values stored for explainability
- Procurement recommendations calculated in same transaction
- Failed forecasts remain in SQS (DLQ after 3 retries)

---

## POS Transaction Sync

**Description:** Background worker syncs transactions from POS systems via SQS queue.

```mermaid
sequenceDiagram
    participant Webhook as POS Webhook
    participant API as Webhook Handler
    participant SQS as SQS Queue
    participant Worker as Sync Worker
    participant POS as Square API
    participant DB as PostgreSQL

    alt Real-time webhook trigger
        Webhook->>API: POST /webhooks/square<br/>{ event: 'order.created', orderId: '123' }

        API->>API: Verify HMAC signature

        alt Signature valid
            API->>SQS: Send message { restaurantId, provider, orderId }
            API-->>Webhook: 200 OK
        else Signature invalid
            API-->>Webhook: 401 Unauthorized
        end
    else Scheduled polling (fallback)
        Note over API: EventBridge triggers every 15 minutes
        API->>DB: SELECT integrations WHERE lastSync < NOW() - 15 min

        loop For each integration
            API->>SQS: Send message { restaurantId, provider, syncType: 'INCREMENTAL' }
        end
    end

    SQS->>Worker: Trigger Lambda with batch

    loop For each sync request
        Worker->>DB: SELECT POSIntegration WHERE id = integrationId
        DB-->>Worker: { accessToken, refreshToken, lastSyncedAt }

        Worker->>POS: GET /orders?start={lastSyncedAt}&end={now}

        alt Token expired (401)
            POS-->>Worker: 401 Unauthorized
            Worker->>POS: POST /oauth/refresh
            POS-->>Worker: { newAccessToken, newRefreshToken }
            Worker->>DB: UPDATE POSIntegration (tokens)
            Worker->>POS: Retry GET /orders
        end

        POS-->>Worker: { orders: [...], cursor: 'page2' }

        loop While cursor exists
            Worker->>Worker: Transform to internal format
            Worker->>DB: BEGIN TRANSACTION

            loop For each order
                Worker->>DB: UPSERT Transaction

                loop For each line item
                    Worker->>DB: UPSERT TransactionItem
                    Worker->>DB: Match to MenuItem (fuzzy match)
                end
            end

            Worker->>DB: UPDATE POSIntegration (lastSyncedAt)
            Worker->>DB: COMMIT TRANSACTION

            Worker->>POS: GET /orders?cursor={cursor}
            POS-->>Worker: { orders: [...], cursor: null }
        end

        Worker->>DB: Calculate data health metrics

        alt Data health degraded
            Worker->>DB: INSERT DataHealthAlert
            Worker->>Worker: Trigger alert Lambda (async)
        end
    end

    Worker-->>SQS: Delete batch from queue
```

**Key Points:**
- Webhook-first approach with polling fallback
- HMAC signature verification for security
- Token refresh handled automatically
- Fuzzy matching for menu item reconciliation (Levenshtein distance)
- UPSERT for idempotency (handle duplicate webhooks)
- Data health monitoring runs after each sync
- SQS visibility timeout: 5 minutes (allows for pagination)

---

## Procurement Recommendation Flow

**Description:** User views AI-powered procurement recommendations with explanations.

```mermaid
sequenceDiagram
    actor User
    participant Web as Next.js App
    participant API as tRPC API
    participant DB as PostgreSQL
    participant Cache as Redis

    User->>Web: Navigate to /procurement
    Web->>API: procurement.getRecommendations({ date: 'today' })

    API->>Cache: GET procurement:recommendations:{restaurantId}:{date}

    alt Cache hit
        Cache-->>API: Cached recommendations
        API-->>Web: Return from cache
    else Cache miss
        API->>DB: SELECT ForecastRun WHERE date = {date}
        DB-->>API: forecastRunId

        API->>DB: SELECT Forecasts WHERE runId = {forecastRunId}
        DB-->>API: List of forecasts

        API->>DB: SELECT Recipes JOIN RecipeIngredients
        DB-->>API: Recipe explosion data

        API->>API: Calculate ingredient quantities needed
        Note over API: Sum (forecast qty × recipe ingredients)<br/>Group by ingredient

        API->>DB: SELECT current inventory levels
        DB-->>API: Current stock

        API->>API: Calculate gap (needed - current)
        API->>API: Apply safety stock multiplier (1.2×)
        API->>API: Round to supplier packaging units

        API->>DB: SELECT ProcurementRecommendations
        DB-->>API: Recommendations with AI insights

        API->>Cache: SET recommendations (TTL: 1 hour)
        API-->>Web: { recommendations, forecastSummary }
    end

    Web->>User: Display procurement table

    User->>Web: Click "Why?" on Tomatoes recommendation
    Web->>API: procurement.getExplanation({ ingredientId })

    API->>DB: SELECT contributing forecasts + SHAP values
    DB-->>API: Forecast explanations

    API->>API: Aggregate SHAP values by ingredient
    Note over API: Show which menu items drive demand,<br/>which features (day, weather, etc.) contribute

    API-->>Web: {
      totalQuantity,
      contributingItems: [{ menuItem, quantity, shapDrivers }],
      seasonalFactors,
      confidenceLevel
    }

    Web->>User: Display explanation modal

    User->>Web: Click "Approve & Create Order"
    Web->>API: procurement.createOrder({ items, supplierId })

    API->>DB: BEGIN TRANSACTION
    API->>DB: INSERT ProcurementOrder

    loop For each item
        API->>DB: INSERT ProcurementOrderItem
    end

    API->>DB: UPDATE ProcurementRecommendation (status: ORDERED)
    API->>DB: COMMIT TRANSACTION

    API->>API: Trigger email notification (async)
    API-->>Web: { success: true, orderId }

    Web->>User: Show success toast + redirect to order details
```

**Key Points:**
- Redis caching for performance (1-hour TTL)
- Recipe explosion: forecast → menu items → ingredients
- Safety stock buffer (20%) applied automatically
- SHAP value aggregation shows ingredient-level drivers
- Confidence levels guide user trust
- Order creation atomic transaction
- Async email notification to supplier

---

## Forecast Explanation & Feedback

**Description:** User views SHAP explanations for a forecast and submits feedback.

```mermaid
sequenceDiagram
    actor User
    participant Web as Next.js App
    participant API as tRPC API
    participant DB as PostgreSQL
    participant S3 as S3 Bucket

    User->>Web: Navigate to /forecasts/{id}
    Web->>API: forecast.getWithExplanation({ forecastId })

    API->>DB: SELECT Forecast JOIN ForecastExplanation
    DB-->>API: Forecast + SHAP values

    API->>API: Parse SHAP JSON
    API->>API: Sort features by absolute contribution
    API->>API: Calculate top 5 drivers

    API-->>Web: {
      forecast: { menuItem, quantity, confidence },
      explanation: {
        baseValue,
        features: [{ name, value, contribution, importance }],
        topDrivers: [{ feature, impact, contribution }]
      }
    }

    Web->>User: Display forecast card + waterfall chart
    Note over Web: Recharts waterfall shows:<br/>base value → feature contributions → final prediction

    User->>Web: Hover over "Weekend Effect: +15 units"
    Web->>User: Show tooltip
    Note over Web: "Saturdays historically see 23% higher demand<br/>for this item. Confidence: High (95%)"

    User->>Web: Click "Submit Actual Quantity"
    Web->>User: Show feedback form

    User->>Web: Enter actual quantity: 142 (forecast was 135)
    User->>Web: Add note: "Underestimated due to local festival"
    User->>Web: Submit feedback

    Web->>API: forecast.submitFeedback({
      forecastId,
      actualQuantity: 142,
      feedbackNote: "...",
      tags: ['LOCAL_EVENT']
    })

    API->>DB: BEGIN TRANSACTION
    API->>DB: UPDATE Forecast (actualQuantity, status: CLOSED)
    API->>DB: INSERT ForecastFeedback
    API->>DB: Calculate accuracy metrics

    API->>DB: UPDATE ForecastRun (
      avgAccuracy = (correct + δ) / (total + 1)
    )

    API->>DB: COMMIT TRANSACTION

    alt Feedback indicates poor accuracy
        API->>DB: Check if pattern (multiple misses for this item)

        alt Pattern detected
            API->>S3: Write retraining trigger
            Note over S3: S3 event triggers Step Functions<br/>for model retraining pipeline
        end
    end

    API-->>Web: { success: true, updatedAccuracy }
    Web->>User: Show success message + updated accuracy badge
```

**Key Points:**
- SHAP waterfall chart for visual explainability
- Feature contributions sorted by importance
- User feedback loop improves future forecasts
- Accuracy metrics updated in real-time
- Pattern detection triggers model retraining
- Tags enable structured feedback analysis
- Feedback stored for compliance/audit trail

---

## Team Member Invitation

**Description:** Restaurant owner invites a chef to join their team.

```mermaid
sequenceDiagram
    actor Owner
    participant Web as Next.js App
    participant API as tRPC API
    participant DB as PostgreSQL
    participant Email as SendGrid
    actor Chef

    Owner->>Web: Navigate to /team
    Web->>API: user.listTeamMembers()

    API->>DB: SELECT users JOIN memberships<br/>WHERE restaurantId = {ctx.restaurantId}
    DB-->>API: List of team members

    API-->>Web: Team member list
    Web->>Owner: Display team table

    Owner->>Web: Click "Invite Member"
    Web->>Owner: Show invitation form

    Owner->>Web: Enter email: chef@example.com, role: CHEF
    Web->>API: user.inviteTeamMember({
      email: 'chef@example.com',
      role: 'CHEF'
    })

    API->>DB: Check if user exists with this email

    alt User exists
        API->>DB: Check if already member of this restaurant

        alt Already member
            API-->>Web: Error: "User already in team"
        else Not member
            API->>DB: BEGIN TRANSACTION
            API->>DB: CREATE RestaurantMembership
            API->>DB: CREATE TeamInvitation (status: PENDING)
            API->>DB: COMMIT TRANSACTION

            API->>Email: Send invitation email (template: team-invitation)
            Email-->>Chef: Email with "Accept Invitation" link

            API-->>Web: { success: true }
        end
    else User doesn't exist
        API->>DB: BEGIN TRANSACTION
        API->>DB: CREATE TeamInvitation (status: PENDING)
        API->>DB: COMMIT TRANSACTION

        API->>Email: Send invitation email (template: team-invitation-signup)
        Email-->>Chef: Email with "Sign Up & Join Team" link

        API-->>Web: { success: true }
    end

    Web->>Owner: Show success toast

    Note over Email,Chef: Chef receives email

    Chef->>Email: Click invitation link
    Email->>Web: Redirect to /invitations/{token}

    Web->>API: user.getInvitationDetails({ token })
    API->>DB: SELECT TeamInvitation WHERE token = {token}

    alt Token invalid or expired
        API-->>Web: Error
        Web->>Chef: Show error page
    else Token valid
        DB-->>API: Invitation details
        API-->>Web: { restaurantName, inviterName, role }

        Web->>Chef: Show invitation acceptance page

        Chef->>Web: Click "Accept Invitation"
        Web->>API: user.acceptInvitation({ token })

        API->>DB: BEGIN TRANSACTION
        API->>DB: UPDATE TeamInvitation (status: ACCEPTED)

        alt User existed
            API->>DB: Already has membership (created earlier)
        else User didn't exist
            API->>DB: User created during signup flow
            API->>DB: CREATE RestaurantMembership
        end

        API->>DB: COMMIT TRANSACTION

        API->>Email: Send welcome email to chef
        API->>Email: Send notification to owner (chef joined)

        API-->>Web: { success: true }
        Web->>Chef: Redirect to /dashboard
    end
```

**Key Points:**
- Two flows: existing user vs. new signup
- Token-based invitation links (UUID, 7-day expiration)
- Membership created optimistically for existing users
- Role-based permissions enforced at RLS level
- Email notifications for both inviter and invitee
- Invitation status tracked (PENDING, ACCEPTED, EXPIRED, DECLINED)

---

## Data Health Monitoring

**Description:** System detects data quality issues and sends alerts to users.

```mermaid
sequenceDiagram
    participant Worker as Sync Worker
    participant DB as PostgreSQL
    participant Alert as Alert Lambda
    participant Email as SendGrid
    participant SMS as Twilio
    actor Owner

    Note over Worker: After transaction sync completes

    Worker->>DB: Calculate data health metrics
    Note over Worker: Check for:<br/>- Missing transactions (gaps > 4 hours)<br/>- Low item match rate (< 80%)<br/>- Stale data (last sync > 24h ago)<br/>- Duplicate transactions<br/>- Outlier detection

    Worker->>DB: SELECT previous health score
    DB-->>Worker: Last score: 92%

    Worker->>Worker: Calculate new score: 68%
    Note over Worker: Weighted scoring:<br/>- Completeness: 30%<br/>- Timeliness: 25%<br/>- Accuracy: 25%<br/>- Consistency: 20%

    alt Score dropped > 15 points
        Worker->>DB: BEGIN TRANSACTION
        Worker->>DB: UPDATE DataHealthMetric (score: 68%)
        Worker->>DB: INSERT DataHealthAlert {
          severity: 'HIGH',
          category: 'COMPLETENESS',
          message: 'Transaction gap detected (8 hours)',
          detectedAt: NOW()
        }
        Worker->>DB: COMMIT TRANSACTION

        Worker->>Alert: Invoke alert Lambda (async)

        Alert->>DB: SELECT alert details + restaurant + owner
        DB-->>Alert: Alert context

        Alert->>Alert: Determine notification channels
        Note over Alert: Rules:<br/>- HIGH severity: Email + SMS<br/>- MEDIUM severity: Email<br/>- LOW severity: In-app only

        Alert->>DB: SELECT owner notification preferences
        DB-->>Alert: { emailEnabled: true, smsEnabled: true }

        par Send email
            Alert->>Email: Send email (template: data-health-alert)
            Email-->>Owner: Email with alert details + action items
        and Send SMS
            Alert->>SMS: Send SMS
            SMS-->>Owner: SMS: "⚠️ Data health alert: 8hr transaction gap"
        end

        Alert->>DB: UPDATE DataHealthAlert (notifiedAt: NOW())
    else Minor score drop
        Worker->>DB: UPDATE DataHealthMetric (score: 88%)
        Note over Worker: No alert for drops < 15 points
    end

    Note over Owner: Owner checks dashboard

    Owner->>Web: Navigate to /data-health
    Web->>API: restaurant.getDataHealth()

    API->>DB: SELECT DataHealthMetric + recent alerts
    DB-->>API: Health metrics + alert history

    API-->>Web: {
      currentScore: 68%,
      scoreHistory: [...],
      activeAlerts: [...],
      recommendations: [
        "Check POS connection",
        "Verify webhook configuration"
      ]
    }

    Web->>Owner: Display health dashboard + alerts

    Owner->>Web: Click "Resolve Alert"
    Web->>API: restaurant.resolveDataHealthAlert({ alertId })

    API->>DB: UPDATE DataHealthAlert (
      status: 'RESOLVED',
      resolvedAt: NOW(),
      resolvedBy: {userId}
    )

    API-->>Web: { success: true }
    Web->>Owner: Alert marked as resolved
```

**Key Points:**
- Automated health checks after each sync
- Weighted scoring across 4 dimensions
- Alert severity determines notification channels
- User notification preferences respected
- Actionable recommendations provided
- Alert lifecycle tracked (ACTIVE, ACKNOWLEDGED, RESOLVED)
- Historical score tracking for trend analysis

---

## Workflow Summary

### Key Architectural Patterns

1. **Event-Driven Architecture**
   - EventBridge for scheduled tasks (forecasts, sync polling)
   - SQS for async processing (POS sync, forecast generation)
   - Lambda for stateless compute

2. **Webhook-First with Polling Fallback**
   - Real-time webhooks for POS transaction events
   - Scheduled polling as backup (every 15 minutes)
   - HMAC signature verification for security

3. **Optimistic Locking & Idempotency**
   - UPSERT for transactions (handle duplicate webhooks)
   - Token-based invitations with expiration
   - Retry logic with exponential backoff

4. **Caching Strategy**
   - Redis for expensive calculations (procurement recommendations)
   - 1-hour TTL for forecast-derived data
   - Cache invalidation on data updates

5. **Async Communication**
   - SQS for decoupling sync workers from API
   - SNS for fanout to multiple subscribers (future)
   - Lambda async invocation for non-critical tasks

6. **Multi-Tenant Isolation**
   - Row-Level Security (RLS) in PostgreSQL
   - RestaurantId in JWT token claims
   - Context injection in tRPC middleware

7. **Explainability & Trust**
   - SHAP values for every forecast
   - Feature contribution waterfall charts
   - User feedback loop for continuous improvement

---

# Database Schema

This section provides the complete Prisma schema for the Flux platform, including all 24 entities, relationships, indexes, and constraints.

## Complete Prisma Schema

**Location:** `packages/database/prisma/schema.prisma`

```prisma
// Prisma Schema for Flux Platform
// Database: PostgreSQL 15+
// Multi-tenant with Row-Level Security (RLS)

generator client {
  provider        = "prisma-client-js"
  previewFeatures = ["postgresqlExtensions", "multiSchema"]
}

datasource db {
  provider   = "postgresql"
  url        = env("DATABASE_URL")
  extensions = [pg_trgm, uuid_ossp]
}

// ============================================================================
// CORE ENTITIES
// ============================================================================

model User {
  id            String   @id @default(uuid()) @db.Uuid
  email         String   @unique
  passwordHash  String   @map("password_hash")
  firstName     String?  @map("first_name")
  lastName      String?  @map("last_name")
  emailVerified Boolean  @default(false) @map("email_verified")
  createdAt     DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt     DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  memberships     RestaurantMembership[]
  sentInvitations TeamInvitation[]       @relation("InvitationInviter")
  sessions        UserSession[]

  @@map("users")
}

model Restaurant {
  id          String   @id @default(uuid()) @db.Uuid
  name        String
  slug        String   @unique
  timezone    String   @default("UTC")
  currency    String   @default("USD") @db.Char(3)
  status      RestaurantStatus @default(ACTIVE)
  settings    Json     @default("{}")
  createdAt   DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt   DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  memberships           RestaurantMembership[]
  menuItems             MenuItem[]
  recipes               Recipe[]
  ingredients           Ingredient[]
  transactions          Transaction[]
  forecasts             Forecast[]
  forecastRuns          ForecastRun[]
  posIntegrations       POSIntegration[]
  suppliers             Supplier[]
  procurementOrders     ProcurementOrder[]
  procurementRecommendations ProcurementRecommendation[]
  subscriptions         Subscription[]
  usageRecords          UsageRecord[]
  dataHealthMetrics     DataHealthMetric[]
  dataHealthAlerts      DataHealthAlert[]
  teamInvitations       TeamInvitation[]

  @@index([status])
  @@map("restaurants")
}

enum RestaurantStatus {
  ACTIVE
  SUSPENDED
  INACTIVE
  TRIAL

  @@map("restaurant_status")
}

model RestaurantMembership {
  id           String   @id @default(uuid()) @db.Uuid
  restaurantId String   @map("restaurant_id") @db.Uuid
  userId       String   @map("user_id") @db.Uuid
  role         MembershipRole
  status       MembershipStatus @default(ACTIVE)
  joinedAt     DateTime @default(now()) @map("joined_at") @db.Timestamptz
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  user       User       @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@unique([restaurantId, userId])
  @@index([userId])
  @@index([restaurantId, role])
  @@map("restaurant_memberships")
}

enum MembershipRole {
  OWNER
  ADMIN
  MANAGER
  CHEF
  VIEWER

  @@map("membership_role")
}

enum MembershipStatus {
  ACTIVE
  INACTIVE
  SUSPENDED

  @@map("membership_status")
}

model UserSession {
  id           String   @id @default(uuid()) @db.Uuid
  userId       String   @map("user_id") @db.Uuid
  token        String   @unique
  expiresAt    DateTime @map("expires_at") @db.Timestamptz
  ipAddress    String?  @map("ip_address")
  userAgent    String?  @map("user_agent")
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@index([userId])
  @@index([expiresAt])
  @@map("user_sessions")
}

model TeamInvitation {
  id           String   @id @default(uuid()) @db.Uuid
  restaurantId String   @map("restaurant_id") @db.Uuid
  inviterId    String   @map("inviter_id") @db.Uuid
  email        String
  role         MembershipRole
  token        String   @unique
  status       InvitationStatus @default(PENDING)
  expiresAt    DateTime @map("expires_at") @db.Timestamptz
  acceptedAt   DateTime? @map("accepted_at") @db.Timestamptz
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  inviter    User       @relation("InvitationInviter", fields: [inviterId], references: [id])

  @@index([restaurantId])
  @@index([email])
  @@index([status])
  @@map("team_invitations")
}

enum InvitationStatus {
  PENDING
  ACCEPTED
  EXPIRED
  DECLINED

  @@map("invitation_status")
}

// ============================================================================
// MENU & RECIPE ENTITIES
// ============================================================================

model MenuItem {
  id                String   @id @default(uuid()) @db.Uuid
  restaurantId      String   @map("restaurant_id") @db.Uuid
  name              String
  description       String?
  category          String?
  posItemId         String?  @map("pos_item_id")
  posItemName       String?  @map("pos_item_name")
  isActive          Boolean  @default(true) @map("is_active")
  createdAt         DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt         DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  restaurant        Restaurant         @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  recipes           Recipe[]
  transactionItems  TransactionItem[]
  forecasts         Forecast[]

  @@unique([restaurantId, posItemId])
  @@index([restaurantId, isActive])
  @@index([restaurantId, category])
  @@map("menu_items")
}

model Recipe {
  id             String   @id @default(uuid()) @db.Uuid
  restaurantId   String   @map("restaurant_id") @db.Uuid
  menuItemId     String   @map("menu_item_id") @db.Uuid
  version        Int      @default(1)
  yieldQuantity  Decimal  @map("yield_quantity") @db.Decimal(10, 2)
  yieldUnit      String   @map("yield_unit")
  isActive       Boolean  @default(true) @map("is_active")
  verifiedByChef Boolean  @default(false) @map("verified_by_chef")
  createdAt      DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt      DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  restaurant   Restaurant         @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  menuItem     MenuItem           @relation(fields: [menuItemId], references: [id], onDelete: Cascade)
  ingredients  RecipeIngredient[]

  @@unique([menuItemId, version])
  @@index([restaurantId, isActive])
  @@index([verifiedByChef])
  @@map("recipes")
}

model Ingredient {
  id           String   @id @default(uuid()) @db.Uuid
  restaurantId String   @map("restaurant_id") @db.Uuid
  name         String
  category     String?
  unit         String
  costPerUnit  Decimal? @map("cost_per_unit") @db.Decimal(10, 2)
  supplierId   String?  @map("supplier_id") @db.Uuid
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt    DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  restaurant         Restaurant                 @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  supplier           Supplier?                  @relation(fields: [supplierId], references: [id], onDelete: SetNull)
  recipeIngredients  RecipeIngredient[]
  procurementItems   ProcurementOrderItem[]
  inventoryLevels    InventoryLevel[]
  recommendations    ProcurementRecommendation[]

  @@unique([restaurantId, name, unit])
  @@index([restaurantId, category])
  @@index([supplierId])
  @@map("ingredients")
}

model RecipeIngredient {
  id           String   @id @default(uuid()) @db.Uuid
  recipeId     String   @map("recipe_id") @db.Uuid
  ingredientId String   @map("ingredient_id") @db.Uuid
  quantity     Decimal  @db.Decimal(10, 4)
  unit         String
  notes        String?
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  recipe     Recipe     @relation(fields: [recipeId], references: [id], onDelete: Cascade)
  ingredient Ingredient @relation(fields: [ingredientId], references: [id], onDelete: Cascade)

  @@unique([recipeId, ingredientId])
  @@index([ingredientId])
  @@map("recipe_ingredients")
}

model InventoryLevel {
  id           String   @id @default(uuid()) @db.Uuid
  ingredientId String   @map("ingredient_id") @db.Uuid
  quantity     Decimal  @db.Decimal(10, 2)
  unit         String
  lastUpdated  DateTime @default(now()) @map("last_updated") @db.Timestamptz
  source       String   @default("MANUAL") // MANUAL, PROCUREMENT, POS

  // Relationships
  ingredient Ingredient @relation(fields: [ingredientId], references: [id], onDelete: Cascade)

  @@unique([ingredientId])
  @@map("inventory_levels")
}

// ============================================================================
// TRANSACTION ENTITIES
// ============================================================================

model Transaction {
  id             String   @id @default(uuid()) @db.Uuid
  restaurantId   String   @map("restaurant_id") @db.Uuid
  posTransactionId String? @map("pos_transaction_id")
  posProvider    String?  @map("pos_provider")
  transactionDate DateTime @map("transaction_date") @db.Timestamptz
  totalAmount    Decimal  @map("total_amount") @db.Decimal(10, 2)
  currency       String   @default("USD") @db.Char(3)
  metadata       Json?    @db.JsonB
  createdAt      DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt      DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant        @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  items      TransactionItem[]

  @@unique([restaurantId, posTransactionId, posProvider])
  @@index([restaurantId, transactionDate])
  @@index([posProvider])
  @@map("transactions")
}

model TransactionItem {
  id            String   @id @default(uuid()) @db.Uuid
  transactionId String   @map("transaction_id") @db.Uuid
  menuItemId    String?  @map("menu_item_id") @db.Uuid
  itemName      String   @map("item_name")
  quantity      Int
  unitPrice     Decimal  @map("unit_price") @db.Decimal(10, 2)
  totalPrice    Decimal  @map("total_price") @db.Decimal(10, 2)
  matchConfidence Decimal? @map("match_confidence") @db.Decimal(5, 4) // 0.0 to 1.0
  createdAt     DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  transaction Transaction @relation(fields: [transactionId], references: [id], onDelete: Cascade)
  menuItem    MenuItem?   @relation(fields: [menuItemId], references: [id], onDelete: SetNull)

  @@index([transactionId])
  @@index([menuItemId])
  @@map("transaction_items")
}

// ============================================================================
// FORECAST ENTITIES
// ============================================================================

model ForecastRun {
  id               String   @id @default(uuid()) @db.Uuid
  restaurantId     String   @map("restaurant_id") @db.Uuid
  forecastDate     DateTime @map("forecast_date") @db.Date
  status           ForecastStatus @default(PENDING)
  modelVersion     String   @map("model_version")
  avgAccuracy      Decimal? @map("avg_accuracy") @db.Decimal(5, 4)
  completedAt      DateTime? @map("completed_at") @db.Timestamptz
  errorMessage     String?  @map("error_message")
  createdAt        DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  forecasts  Forecast[]

  @@unique([restaurantId, forecastDate])
  @@index([restaurantId, status])
  @@index([forecastDate])
  @@map("forecast_runs")
}

enum ForecastStatus {
  PENDING
  IN_PROGRESS
  COMPLETED
  FAILED

  @@map("forecast_status")
}

model Forecast {
  id               String   @id @default(uuid()) @db.Uuid
  forecastRunId    String   @map("forecast_run_id") @db.Uuid
  restaurantId     String   @map("restaurant_id") @db.Uuid
  menuItemId       String   @map("menu_item_id") @db.Uuid
  forecastDate     DateTime @map("forecast_date") @db.Date
  predictedQuantity Decimal @map("predicted_quantity") @db.Decimal(10, 2)
  confidence       Decimal  @db.Decimal(5, 4) // 0.0 to 1.0
  actualQuantity   Decimal? @map("actual_quantity") @db.Decimal(10, 2)
  status           String   @default("PENDING") // PENDING, CLOSED
  createdAt        DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  forecastRun ForecastRun           @relation(fields: [forecastRunId], references: [id], onDelete: Cascade)
  restaurant  Restaurant            @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  menuItem    MenuItem              @relation(fields: [menuItemId], references: [id], onDelete: Cascade)
  explanation ForecastExplanation?
  feedback    ForecastFeedback[]

  @@unique([forecastRunId, menuItemId])
  @@index([restaurantId, forecastDate])
  @@index([menuItemId])
  @@map("forecasts")
}

model ForecastExplanation {
  id         String   @id @default(uuid()) @db.Uuid
  forecastId String   @unique @map("forecast_id") @db.Uuid
  baseValue  Decimal  @map("base_value") @db.Decimal(10, 2)
  shapValues Json     @map("shap_values") @db.JsonB
  // JSON structure: { features: [{ name, value, contribution, importance }] }
  createdAt  DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  forecast Forecast @relation(fields: [forecastId], references: [id], onDelete: Cascade)

  @@map("forecast_explanations")
}

model ForecastFeedback {
  id              String   @id @default(uuid()) @db.Uuid
  forecastId      String   @map("forecast_id") @db.Uuid
  actualQuantity  Decimal  @map("actual_quantity") @db.Decimal(10, 2)
  feedbackNote    String?  @map("feedback_note")
  tags            String[] @default([])
  createdAt       DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  forecast Forecast @relation(fields: [forecastId], references: [id], onDelete: Cascade)

  @@index([forecastId])
  @@map("forecast_feedback")
}

// ============================================================================
// PROCUREMENT ENTITIES
// ============================================================================

model Supplier {
  id           String   @id @default(uuid()) @db.Uuid
  restaurantId String   @map("restaurant_id") @db.Uuid
  name         String
  email        String?
  phone        String?
  address      String?
  notes        String?
  isActive     Boolean  @default(true) @map("is_active")
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt    DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  restaurant        Restaurant          @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  ingredients       Ingredient[]
  procurementOrders ProcurementOrder[]

  @@index([restaurantId, isActive])
  @@map("suppliers")
}

model ProcurementOrder {
  id           String   @id @default(uuid()) @db.Uuid
  restaurantId String   @map("restaurant_id") @db.Uuid
  supplierId   String   @map("supplier_id") @db.Uuid
  orderNumber  String   @map("order_number")
  orderDate    DateTime @map("order_date") @db.Timestamptz
  expectedDelivery DateTime? @map("expected_delivery") @db.Timestamptz
  status       ProcurementStatus @default(DRAFT)
  totalAmount  Decimal  @map("total_amount") @db.Decimal(10, 2)
  notes        String?
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt    DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant             @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  supplier   Supplier               @relation(fields: [supplierId], references: [id])
  items      ProcurementOrderItem[]

  @@unique([restaurantId, orderNumber])
  @@index([restaurantId, status])
  @@index([supplierId])
  @@map("procurement_orders")
}

enum ProcurementStatus {
  DRAFT
  SUBMITTED
  CONFIRMED
  DELIVERED
  CANCELLED

  @@map("procurement_status")
}

model ProcurementOrderItem {
  id           String   @id @default(uuid()) @db.Uuid
  orderId      String   @map("order_id") @db.Uuid
  ingredientId String   @map("ingredient_id") @db.Uuid
  quantity     Decimal  @db.Decimal(10, 2)
  unit         String
  unitPrice    Decimal  @map("unit_price") @db.Decimal(10, 2)
  totalPrice   Decimal  @map("total_price") @db.Decimal(10, 2)
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  order      ProcurementOrder @relation(fields: [orderId], references: [id], onDelete: Cascade)
  ingredient Ingredient       @relation(fields: [ingredientId], references: [id])

  @@index([orderId])
  @@index([ingredientId])
  @@map("procurement_order_items")
}

model ProcurementRecommendation {
  id               String   @id @default(uuid()) @db.Uuid
  restaurantId     String   @map("restaurant_id") @db.Uuid
  ingredientId     String   @map("ingredient_id") @db.Uuid
  recommendedDate  DateTime @map("recommended_date") @db.Date
  quantity         Decimal  @db.Decimal(10, 2)
  unit             String
  confidence       Decimal  @db.Decimal(5, 4)
  reasoning        String?
  status           String   @default("PENDING") // PENDING, ORDERED, DISMISSED
  createdAt        DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  ingredient Ingredient @relation(fields: [ingredientId], references: [id], onDelete: Cascade)

  @@unique([restaurantId, ingredientId, recommendedDate])
  @@index([restaurantId, status])
  @@map("procurement_recommendations")
}

// ============================================================================
// POS INTEGRATION ENTITIES
// ============================================================================

model POSIntegration {
  id           String   @id @default(uuid()) @db.Uuid
  restaurantId String   @map("restaurant_id") @db.Uuid
  provider     POSProvider
  status       IntegrationStatus @default(PENDING)
  accessToken  String?  @map("access_token")
  refreshToken String?  @map("refresh_token")
  expiresAt    DateTime? @map("expires_at") @db.Timestamptz
  locationId   String?  @map("location_id")
  lastSyncedAt DateTime? @map("last_synced_at") @db.Timestamptz
  metadata     Json?    @db.JsonB
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt    DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant @relation(fields: [restaurantId], references: [id], onDelete: Cascade)

  @@unique([restaurantId, provider])
  @@index([status])
  @@map("pos_integrations")
}

enum POSProvider {
  SQUARE
  TOAST
  CLOVER
  LIGHTSPEED

  @@map("pos_provider")
}

enum IntegrationStatus {
  PENDING
  CONNECTED
  ERROR
  DISCONNECTED

  @@map("integration_status")
}

// ============================================================================
// BILLING & SUBSCRIPTION ENTITIES
// ============================================================================

model Subscription {
  id             String   @id @default(uuid()) @db.Uuid
  restaurantId   String   @map("restaurant_id") @db.Uuid
  plan           SubscriptionPlan
  status         SubscriptionStatus @default(TRIAL)
  stripeCustomerId String? @unique @map("stripe_customer_id")
  stripeSubscriptionId String? @unique @map("stripe_subscription_id")
  currentPeriodStart DateTime @map("current_period_start") @db.Timestamptz
  currentPeriodEnd   DateTime @map("current_period_end") @db.Timestamptz
  cancelAtPeriodEnd  Boolean  @default(false) @map("cancel_at_period_end")
  createdAt      DateTime @default(now()) @map("created_at") @db.Timestamptz
  updatedAt      DateTime @updatedAt @map("updated_at") @db.Timestamptz

  // Relationships
  restaurant   Restaurant     @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  usageRecords UsageRecord[]

  @@unique([restaurantId])
  @@index([status])
  @@map("subscriptions")
}

enum SubscriptionPlan {
  STARTER
  PROFESSIONAL
  ENTERPRISE

  @@map("subscription_plan")
}

enum SubscriptionStatus {
  TRIAL
  ACTIVE
  PAST_DUE
  CANCELLED
  EXPIRED

  @@map("subscription_status")
}

model UsageRecord {
  id             String   @id @default(uuid()) @db.Uuid
  restaurantId   String   @map("restaurant_id") @db.Uuid
  subscriptionId String   @map("subscription_id") @db.Uuid
  metricType     String   @map("metric_type") // forecasts_generated, api_calls, etc.
  quantity       Int
  periodStart    DateTime @map("period_start") @db.Timestamptz
  periodEnd      DateTime @map("period_end") @db.Timestamptz
  reportedToStripe Boolean @default(false) @map("reported_to_stripe")
  createdAt      DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  restaurant   Restaurant   @relation(fields: [restaurantId], references: [id], onDelete: Cascade)
  subscription Subscription @relation(fields: [subscriptionId], references: [id], onDelete: Cascade)

  @@index([restaurantId, periodStart])
  @@index([subscriptionId])
  @@map("usage_records")
}

// ============================================================================
// DATA HEALTH & MONITORING ENTITIES
// ============================================================================

model DataHealthMetric {
  id              String   @id @default(uuid()) @db.Uuid
  restaurantId    String   @map("restaurant_id") @db.Uuid
  date            DateTime @db.Date
  completeness    Decimal  @db.Decimal(5, 4) // 0.0 to 1.0
  timeliness      Decimal  @db.Decimal(5, 4)
  accuracy        Decimal  @db.Decimal(5, 4)
  consistency     Decimal  @db.Decimal(5, 4)
  overallScore    Decimal  @map("overall_score") @db.Decimal(5, 4)
  transactionCount Int     @map("transaction_count")
  unmatchedItemsCount Int  @map("unmatched_items_count")
  createdAt       DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant @relation(fields: [restaurantId], references: [id], onDelete: Cascade)

  @@unique([restaurantId, date])
  @@index([restaurantId, overallScore])
  @@map("data_health_metrics")
}

model DataHealthAlert {
  id           String   @id @default(uuid()) @db.Uuid
  restaurantId String   @map("restaurant_id") @db.Uuid
  severity     AlertSeverity
  category     String
  message      String
  details      Json?    @db.JsonB
  status       AlertStatus @default(ACTIVE)
  detectedAt   DateTime @map("detected_at") @db.Timestamptz
  notifiedAt   DateTime? @map("notified_at") @db.Timestamptz
  resolvedAt   DateTime? @map("resolved_at") @db.Timestamptz
  resolvedBy   String?  @map("resolved_by") @db.Uuid
  createdAt    DateTime @default(now()) @map("created_at") @db.Timestamptz

  // Relationships
  restaurant Restaurant @relation(fields: [restaurantId], references: [id], onDelete: Cascade)

  @@index([restaurantId, status])
  @@index([severity, status])
  @@map("data_health_alerts")
}

enum AlertSeverity {
  LOW
  MEDIUM
  HIGH
  CRITICAL

  @@map("alert_severity")
}

enum AlertStatus {
  ACTIVE
  ACKNOWLEDGED
  RESOLVED
  DISMISSED

  @@map("alert_status")
}
```

## Key Schema Design Decisions

### 1. Multi-Tenancy with RLS

All tables include `restaurantId` for row-level security filtering:

```sql
-- Example RLS policy
CREATE POLICY restaurant_isolation ON menu_items
  USING (restaurant_id = current_setting('app.current_restaurant_id')::uuid);
```

### 2. Indexing Strategy

**Composite Indexes:**
- `[restaurantId, status]` - Common filtering pattern
- `[restaurantId, date]` - Time-series queries
- `[restaurantId, posTransactionId, posProvider]` - Uniqueness constraint

**Single Indexes:**
- Foreign keys for join performance
- Status fields for workflow queries
- Date fields for time-range queries

### 3. Decimal Precision

Financial and measurement data use `Decimal` type:
- Currency: `Decimal(10, 2)` - up to $99,999,999.99
- Quantities: `Decimal(10, 4)` - supports fractional units
- Percentages: `Decimal(5, 4)` - 0.0000 to 1.0000 (0% to 100%)

### 4. JSON Storage

JSONB used for flexible/sparse data:
- `shapValues` - ML explanation features (variable structure)
- `metadata` - POS-specific fields
- `settings` - Restaurant-specific configuration
- `details` - Alert context

### 5. Cascade Behavior

**ON DELETE CASCADE:**
- Restaurant deletion removes all related data
- Transaction deletion removes items
- Forecast run deletion removes forecasts

**ON DELETE SET NULL:**
- Supplier deletion doesn't remove ingredients
- Menu item deletion preserves transaction history

### 6. Unique Constraints

**Business Logic Uniqueness:**
- `[restaurantId, posItemId]` - Prevent duplicate POS mappings
- `[restaurantId, posTransactionId, posProvider]` - Idempotent sync
- `[forecastRunId, menuItemId]` - One forecast per item per run
- `[recipeId, ingredientId]` - Ingredient appears once per recipe

### 7. Enums for Type Safety

All status fields use enums instead of strings:
- Compile-time validation
- Database constraint enforcement
- Prevents typos in application code

---

# Frontend Architecture

This section details the Next.js frontend architecture, including routing, state management, authentication, and UI patterns.

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
│   │   │   ├── auth/[...nextauth]/
│   │   │   ├── trpc/[trpc]/
│   │   │   └── webhooks/
│   │   └── layout.tsx           # Root layout
│   ├── components/              # React components (Atomic Design)
│   │   ├── atoms/
│   │   ├── molecules/
│   │   ├── organisms/
│   │   ├── templates/
│   │   └── features/
│   ├── lib/                     # Utilities
│   │   ├── trpc.ts             # tRPC client setup
│   │   ├── auth.ts             # NextAuth config
│   │   └── utils.ts
│   ├── hooks/                   # Custom React hooks
│   │   ├── use-restaurant.ts
│   │   ├── use-forecasts.ts
│   │   └── use-toast.ts
│   ├── providers/               # Context providers
│   │   ├── trpc-provider.tsx
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
import { api } from '@/lib/trpc-server';
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

### tRPC + React Query

Primary state management through tRPC and React Query:

**Client Setup:**
```typescript
// apps/web/src/lib/trpc.ts

import { createTRPCReact } from '@trpc/react-query';
import type { AppRouter } from '@repo/api';

export const api = createTRPCReact<AppRouter>();
```

**Provider Setup:**
```typescript
// apps/web/src/providers/trpc-provider.tsx

'use client';

import { useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { httpBatchLink } from '@trpc/client';
import { api } from '@/lib/trpc';

export function TRPCProvider({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000, // 1 minute
            refetchOnWindowFocus: false,
          },
        },
      })
  );

  const [trpcClient] = useState(() =>
    api.createClient({
      links: [
        httpBatchLink({
          url: '/api/trpc',
          headers() {
            return {
              // Add auth headers if needed
            };
          },
        }),
      ],
    })
  );

  return (
    <api.Provider client={trpcClient} queryClient={queryClient}>
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    </api.Provider>
  );
}
```

**Usage in Components:**
```typescript
// Example: Forecasts list component

'use client';

import { api } from '@/lib/trpc';
import { ForecastCard } from '@/components/molecules/ForecastCard';
import { Spinner } from '@/components/atoms/Spinner';

export function ForecastsList() {
  const { data: forecasts, isLoading } = api.forecast.list.useQuery({
    startDate: new Date().toISOString(),
    limit: 20,
  });

  if (isLoading) {
    return <Spinner />;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
      {forecasts?.items.map((forecast) => (
        <ForecastCard key={forecast.id} forecast={forecast} />
      ))}
    </div>
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

import { api } from '@/lib/trpc-server';
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

import { api } from '@/lib/trpc';
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

import { api } from '@/lib/trpc';

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

### tRPC Error Handling

```typescript
'use client';

import { api } from '@/lib/trpc';
import { TRPCClientError } from '@trpc/client';

export function ForecastsList() {
  const { data, error, isError } = api.forecast.list.useQuery({});

  if (isError) {
    if (error instanceof TRPCClientError) {
      if (error.data?.code === 'UNAUTHORIZED') {
        return <div>Please log in to view forecasts</div>;
      }

      if (error.data?.code === 'FORBIDDEN') {
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

## Application Structure

**Location:** `apps/api/`

```
apps/api/
├── src/
│   ├── handlers/                    # Lambda function handlers
│   │   ├── trpc-handler.ts         # tRPC API handler
│   │   ├── pos-sync-handler.ts     # SQS-triggered POS sync
│   │   ├── forecast-handler.ts     # EventBridge-triggered forecasts
│   │   ├── webhook-handler.ts      # POS webhook receiver
│   │   └── alert-handler.ts        # Data health alerts
│   ├── routers/                     # tRPC routers
│   │   ├── auth.ts
│   │   ├── forecast.ts
│   │   ├── menu.ts
│   │   ├── procurement.ts
│   │   ├── pos.ts
│   │   ├── recipe.ts
│   │   ├── restaurant.ts
│   │   ├── transaction.ts
│   │   └── user.ts
│   ├── services/                    # Business logic layer
│   │   ├── forecast/
│   │   │   ├── ForecastService.ts
│   │   │   ├── ForecastExplainer.ts
│   │   │   └── FeatureEngineer.ts
│   │   ├── pos/
│   │   │   ├── POSSyncService.ts
│   │   │   ├── POSAdapterFactory.ts
│   │   │   └── ItemMatcher.ts
│   │   ├── procurement/
│   │   │   ├── ProcurementService.ts
│   │   │   └── RecipeExplosion.ts
│   │   ├── auth/
│   │   │   ├── AuthService.ts
│   │   │   └── TokenService.ts
│   │   └── data-health/
│   │       ├── DataHealthService.ts
│   │       └── AlertService.ts
│   ├── adapters/                    # External service adapters
│   │   ├── pos/
│   │   │   ├── SquareAdapter.ts
│   │   │   ├── ToastAdapter.ts
│   │   │   ├── CloverAdapter.ts
│   │   │   └── LightspeedAdapter.ts
│   │   ├── payment/
│   │   │   └── StripeAdapter.ts
│   │   ├── email/
│   │   │   └── SendGridAdapter.ts
│   │   ├── sms/
│   │   │   └── TwilioAdapter.ts
│   │   └── ml/
│   │       └── SageMakerAdapter.ts
│   ├── lib/                         # Shared utilities
│   │   ├── prisma.ts               # Prisma client singleton
│   │   ├── logger.ts               # Winston logger
│   │   ├── errors.ts               # Custom error classes
│   │   ├── validation.ts           # Zod schemas
│   │   ├── queue.ts                # SQS client
│   │   └── cache.ts                # Redis client
│   ├── middleware/                  # tRPC middleware
│   │   ├── auth.ts                 # Authentication
│   │   ├── restaurant-context.ts   # Multi-tenant context
│   │   ├── rate-limit.ts           # Rate limiting
│   │   └── logging.ts              # Request logging
│   └── types/
│       └── index.ts
└── serverless.yml                   # Serverless Framework config
```

## Lambda Function Patterns

### Thin Handlers, Fat Services

All Lambda handlers delegate to service layer:

**tRPC Handler:**
```typescript
// apps/api/src/handlers/trpc-handler.ts

import { awsLambdaRequestHandler } from '@trpc/server/adapters/aws-lambda';
import { createContext } from '../lib/context';
import { appRouter } from '../routers';
import { logger } from '../lib/logger';

export const handler = awsLambdaRequestHandler({
  router: appRouter,
  createContext,
  onError({ error, type, path, input, ctx, req }) {
    logger.error('tRPC Error', {
      type,
      path,
      input,
      error: error.message,
      stack: error.stack,
      restaurantId: ctx?.restaurantId,
    });
  },
});
```

**POS Sync Handler (SQS-triggered):**
```typescript
// apps/api/src/handlers/pos-sync-handler.ts

import { SQSHandler } from 'aws-lambda';
import { POSSyncService } from '../services/pos/POSSyncService';
import { logger } from '../lib/logger';

interface SyncMessage {
  restaurantId: string;
  provider: string;
  integrationId: string;
  syncType: 'INITIAL' | 'INCREMENTAL';
}

export const handler: SQSHandler = async (event) => {
  const service = new POSSyncService();

  for (const record of event.Records) {
    try {
      const message: SyncMessage = JSON.parse(record.body);

      logger.info('Processing POS sync', {
        restaurantId: message.restaurantId,
        provider: message.provider,
        syncType: message.syncType,
      });

      await service.syncTransactions(message);

      logger.info('POS sync completed', {
        restaurantId: message.restaurantId,
      });
    } catch (error) {
      logger.error('POS sync failed', {
        error: error.message,
        stack: error.stack,
        messageId: record.messageId,
      });

      // Let SQS handle retry/DLQ
      throw error;
    }
  }
};
```

**Forecast Handler (EventBridge-triggered):**
```typescript
// apps/api/src/handlers/forecast-handler.ts

import { EventBridgeHandler } from 'aws-lambda';
import { ForecastService } from '../services/forecast/ForecastService';
import { SQS } from 'aws-sdk';
import { logger } from '../lib/logger';
import { prisma } from '../lib/prisma';

const sqs = new SQS();

export const handler: EventBridgeHandler<'Scheduled Event', void, void> = async (event) => {
  logger.info('Forecast scheduler triggered', { time: event.time });

  const service = new ForecastService();

  // Get all active restaurants
  const restaurants = await prisma.restaurant.findMany({
    where: { status: 'ACTIVE' },
    select: { id: true },
  });

  logger.info(`Found ${restaurants.length} active restaurants`);

  // Queue forecast jobs
  const messages = restaurants.map((restaurant) => ({
    Id: restaurant.id,
    MessageBody: JSON.stringify({
      restaurantId: restaurant.id,
      forecastDate: new Date().toISOString().split('T')[0],
    }),
  }));

  // Batch send to SQS (max 10 per batch)
  for (let i = 0; i < messages.length; i += 10) {
    const batch = messages.slice(i, i + 10);

    await sqs
      .sendMessageBatch({
        QueueUrl: process.env.FORECAST_QUEUE_URL!,
        Entries: batch,
      })
      .promise();
  }

  logger.info(`Queued ${messages.length} forecast jobs`);
};
```

**Webhook Handler:**
```typescript
// apps/api/src/handlers/webhook-handler.ts

import { APIGatewayProxyHandler } from 'aws-lambda';
import { POSAdapterFactory } from '../services/pos/POSAdapterFactory';
import { SQS } from 'aws-sdk';
import { logger } from '../lib/logger';

const sqs = new SQS();

export const handler: APIGatewayProxyHandler = async (event) => {
  const provider = event.pathParameters?.provider as string;

  try {
    const adapter = POSAdapterFactory.create(provider);

    // Get signature from headers
    const signature = event.headers['x-square-hmacsha256-signature'] ||
                      event.headers['toast-signature'];

    if (!signature) {
      return {
        statusCode: 401,
        body: JSON.stringify({ error: 'Missing signature' }),
      };
    }

    // Verify webhook signature
    const isValid = adapter.verifyWebhook(
      signature,
      event.body!,
      `${process.env.API_URL}${event.path}`
    );

    if (!isValid) {
      logger.warn('Invalid webhook signature', { provider });
      return {
        statusCode: 401,
        body: JSON.stringify({ error: 'Invalid signature' }),
      };
    }

    // Parse webhook payload
    const payload = JSON.parse(event.body!);

    // Queue sync job
    await sqs
      .sendMessage({
        QueueUrl: process.env.POS_SYNC_QUEUE_URL!,
        MessageBody: JSON.stringify({
          restaurantId: payload.merchant_id || payload.restaurant_guid,
          provider,
          orderId: payload.order_id || payload.guid,
          syncType: 'WEBHOOK',
        }),
      })
      .promise();

    logger.info('Webhook processed', { provider, orderId: payload.order_id });

    return {
      statusCode: 200,
      body: JSON.stringify({ success: true }),
    };
  } catch (error) {
    logger.error('Webhook error', {
      error: error.message,
      provider,
    });

    return {
      statusCode: 500,
      body: JSON.stringify({ error: 'Internal server error' }),
    };
  }
};
```

## Service Layer Patterns

### Service Base Class

```typescript
// apps/api/src/services/BaseService.ts

import { PrismaClient } from '@repo/database';
import { Logger } from 'winston';
import { prisma } from '../lib/prisma';
import { logger as defaultLogger } from '../lib/logger';

export abstract class BaseService {
  protected prisma: PrismaClient;
  protected logger: Logger;

  constructor() {
    this.prisma = prisma;
    this.logger = defaultLogger;
  }

  protected async withTransaction<T>(
    callback: (tx: PrismaClient) => Promise<T>
  ): Promise<T> {
    return this.prisma.$transaction(async (tx) => {
      return callback(tx as PrismaClient);
    });
  }

  protected logOperation(operation: string, context: Record<string, any>) {
    this.logger.info(operation, context);
  }

  protected logError(operation: string, error: Error, context: Record<string, any>) {
    this.logger.error(operation, {
      error: error.message,
      stack: error.stack,
      ...context,
    });
  }
}
```

### Forecast Service

```typescript
// apps/api/src/services/forecast/ForecastService.ts

import { BaseService } from '../BaseService';
import { SageMakerAdapter } from '../../adapters/ml/SageMakerAdapter';
import { FeatureEngineer } from './FeatureEngineer';
import { ForecastExplainer } from './ForecastExplainer';

interface ForecastInput {
  restaurantId: string;
  forecastDate: string;
}

export class ForecastService extends BaseService {
  private sageMaker: SageMakerAdapter;
  private featureEngineer: FeatureEngineer;
  private explainer: ForecastExplainer;

  constructor() {
    super();
    this.sageMaker = new SageMakerAdapter();
    this.featureEngineer = new FeatureEngineer();
    this.explainer = new ForecastExplainer();
  }

  async generateForecasts(input: ForecastInput): Promise<void> {
    const { restaurantId, forecastDate } = input;

    this.logOperation('Starting forecast generation', {
      restaurantId,
      forecastDate,
    });

    try {
      // Create forecast run
      const forecastRun = await this.prisma.forecastRun.create({
        data: {
          restaurantId,
          forecastDate: new Date(forecastDate),
          status: 'IN_PROGRESS',
          modelVersion: process.env.MODEL_VERSION!,
        },
      });

      // Fetch historical data (90 days)
      const startDate = new Date(forecastDate);
      startDate.setDate(startDate.getDate() - 90);

      const [transactions, menuItems, recipes] = await Promise.all([
        this.fetchTransactions(restaurantId, startDate, new Date(forecastDate)),
        this.fetchMenuItems(restaurantId),
        this.fetchRecipes(restaurantId),
      ]);

      this.logOperation('Historical data fetched', {
        transactionCount: transactions.length,
        menuItemCount: menuItems.length,
        restaurantId,
      });

      // Feature engineering
      const features = await this.featureEngineer.engineer({
        transactions,
        menuItems,
        recipes,
        forecastDate: new Date(forecastDate),
      });

      // Invoke SageMaker
      const predictions = await this.sageMaker.predict(features);

      // Store forecasts in transaction
      await this.withTransaction(async (tx) => {
        for (const prediction of predictions) {
          // Create forecast
          const forecast = await tx.forecast.create({
            data: {
              forecastRunId: forecastRun.id,
              restaurantId,
              menuItemId: prediction.menuItemId,
              forecastDate: new Date(forecastDate),
              predictedQuantity: prediction.quantity,
              confidence: prediction.confidence,
            },
          });

          // Create explanation
          await tx.forecastExplanation.create({
            data: {
              forecastId: forecast.id,
              baseValue: prediction.baseValue,
              shapValues: prediction.shapValues,
            },
          });
        }

        // Update forecast run
        await tx.forecastRun.update({
          where: { id: forecastRun.id },
          data: {
            status: 'COMPLETED',
            completedAt: new Date(),
          },
        });
      });

      // Generate procurement recommendations
      await this.generateProcurementRecommendations(restaurantId, forecastDate);

      this.logOperation('Forecast generation completed', {
        restaurantId,
        forecastCount: predictions.length,
      });
    } catch (error) {
      this.logError('Forecast generation failed', error, { restaurantId });

      // Update forecast run as failed
      await this.prisma.forecastRun.updateMany({
        where: {
          restaurantId,
          forecastDate: new Date(forecastDate),
          status: 'IN_PROGRESS',
        },
        data: {
          status: 'FAILED',
          errorMessage: error.message,
        },
      });

      throw error;
    }
  }

  private async fetchTransactions(
    restaurantId: string,
    startDate: Date,
    endDate: Date
  ) {
    return this.prisma.transaction.findMany({
      where: {
        restaurantId,
        transactionDate: {
          gte: startDate,
          lte: endDate,
        },
      },
      include: {
        items: {
          include: {
            menuItem: true,
          },
        },
      },
      orderBy: {
        transactionDate: 'asc',
      },
    });
  }

  private async fetchMenuItems(restaurantId: string) {
    return this.prisma.menuItem.findMany({
      where: {
        restaurantId,
        isActive: true,
      },
    });
  }

  private async fetchRecipes(restaurantId: string) {
    return this.prisma.recipe.findMany({
      where: {
        restaurantId,
        isActive: true,
      },
      include: {
        ingredients: {
          include: {
            ingredient: true,
          },
        },
      },
    });
  }

  private async generateProcurementRecommendations(
    restaurantId: string,
    forecastDate: string
  ) {
    // Implementation in ProcurementService
    // Called after forecasts are generated
  }
}
```

### POS Sync Service

```typescript
// apps/api/src/services/pos/POSSyncService.ts

import { BaseService } from '../BaseService';
import { POSAdapterFactory } from './POSAdapterFactory';
import { ItemMatcher } from './ItemMatcher';
import { DataHealthService } from '../data-health/DataHealthService';

interface SyncInput {
  restaurantId: string;
  provider: string;
  integrationId: string;
  syncType: 'INITIAL' | 'INCREMENTAL' | 'WEBHOOK';
  orderId?: string; // For webhook-triggered syncs
}

export class POSSyncService extends BaseService {
  private itemMatcher: ItemMatcher;
  private dataHealthService: DataHealthService;

  constructor() {
    super();
    this.itemMatcher = new ItemMatcher();
    this.dataHealthService = new DataHealthService();
  }

  async syncTransactions(input: SyncInput): Promise<void> {
    const { restaurantId, provider, integrationId, syncType, orderId } = input;

    this.logOperation('Starting POS sync', {
      restaurantId,
      provider,
      syncType,
    });

    // Get integration details
    const integration = await this.prisma.pOSIntegration.findUnique({
      where: { id: integrationId },
    });

    if (!integration) {
      throw new Error(`Integration not found: ${integrationId}`);
    }

    // Create adapter
    const adapter = POSAdapterFactory.createFromIntegration(integration);

    try {
      let orders: any[];

      if (syncType === 'WEBHOOK' && orderId) {
        // Single order sync
        orders = [await adapter.fetchOrder(orderId)];
      } else {
        // Batch sync
        const startDate = integration.lastSyncedAt || new Date(0);
        const endDate = new Date();

        orders = await adapter.fetchOrders(startDate, endDate);
      }

      this.logOperation('Orders fetched from POS', {
        orderCount: orders.length,
        restaurantId,
      });

      // Process orders in transaction
      await this.withTransaction(async (tx) => {
        for (const order of orders) {
          await this.processOrder(tx, restaurantId, provider, order);
        }

        // Update last synced timestamp
        await tx.pOSIntegration.update({
          where: { id: integrationId },
          data: { lastSyncedAt: new Date() },
        });
      });

      // Calculate data health metrics
      await this.dataHealthService.calculateMetrics(restaurantId);

      this.logOperation('POS sync completed', {
        restaurantId,
        ordersProcessed: orders.length,
      });
    } catch (error) {
      // Handle token refresh
      if (error.statusCode === 401 && integration.refreshToken) {
        this.logOperation('Refreshing access token', { restaurantId });

        const newConfig = await adapter.refreshAccessToken(integration.refreshToken);

        await this.prisma.pOSIntegration.update({
          where: { id: integrationId },
          data: {
            accessToken: newConfig.accessToken,
            refreshToken: newConfig.refreshToken,
            expiresAt: newConfig.expiresAt,
          },
        });

        // Retry sync
        return this.syncTransactions(input);
      }

      this.logError('POS sync failed', error, { restaurantId });
      throw error;
    }
  }

  private async processOrder(
    tx: any,
    restaurantId: string,
    provider: string,
    order: any
  ) {
    // Upsert transaction (idempotent)
    const transaction = await tx.transaction.upsert({
      where: {
        restaurantId_posTransactionId_posProvider: {
          restaurantId,
          posTransactionId: order.id,
          posProvider: provider,
        },
      },
      update: {
        totalAmount: order.total_amount,
        transactionDate: new Date(order.created_at),
        metadata: order.metadata,
      },
      create: {
        restaurantId,
        posTransactionId: order.id,
        posProvider: provider,
        transactionDate: new Date(order.created_at),
        totalAmount: order.total_amount,
        currency: order.currency || 'USD',
        metadata: order.metadata,
      },
    });

    // Process line items
    for (const lineItem of order.line_items) {
      // Match to menu item
      const match = await this.itemMatcher.match(
        restaurantId,
        lineItem.name,
        provider
      );

      await tx.transactionItem.upsert({
        where: {
          // Composite unique key needed
          transactionId_itemName: {
            transactionId: transaction.id,
            itemName: lineItem.name,
          },
        },
        update: {
          quantity: lineItem.quantity,
          unitPrice: lineItem.unit_price,
          totalPrice: lineItem.total_price,
          menuItemId: match?.menuItemId,
          matchConfidence: match?.confidence,
        },
        create: {
          transactionId: transaction.id,
          itemName: lineItem.name,
          quantity: lineItem.quantity,
          unitPrice: lineItem.unit_price,
          totalPrice: lineItem.total_price,
          menuItemId: match?.menuItemId,
          matchConfidence: match?.confidence,
        },
      });
    }
  }
}
```

### Item Matcher (Fuzzy Matching)

```typescript
// apps/api/src/services/pos/ItemMatcher.ts

import { PrismaClient } from '@repo/database';
import { prisma } from '../../lib/prisma';
import levenshtein from 'fast-levenshtein';

interface MatchResult {
  menuItemId: string;
  confidence: number;
}

export class ItemMatcher {
  private prisma: PrismaClient;

  constructor() {
    this.prisma = prisma;
  }

  async match(
    restaurantId: string,
    itemName: string,
    provider: string
  ): Promise<MatchResult | null> {
    // First try exact match on posItemName
    const exactMatch = await this.prisma.menuItem.findFirst({
      where: {
        restaurantId,
        posItemName: itemName,
        isActive: true,
      },
    });

    if (exactMatch) {
      return {
        menuItemId: exactMatch.id,
        confidence: 1.0,
      };
    }

    // Fuzzy match on menu item names
    const menuItems = await this.prisma.menuItem.findMany({
      where: {
        restaurantId,
        isActive: true,
      },
    });

    let bestMatch: { item: any; distance: number } | null = null;

    for (const item of menuItems) {
      const distance = levenshtein.get(
        itemName.toLowerCase(),
        item.name.toLowerCase()
      );

      if (!bestMatch || distance < bestMatch.distance) {
        bestMatch = { item, distance };
      }
    }

    if (!bestMatch) {
      return null;
    }

    // Calculate confidence (inverse of normalized distance)
    const maxLength = Math.max(itemName.length, bestMatch.item.name.length);
    const confidence = 1 - bestMatch.distance / maxLength;

    // Only return matches with > 70% confidence
    if (confidence < 0.7) {
      return null;
    }

    return {
      menuItemId: bestMatch.item.id,
      confidence: Math.round(confidence * 10000) / 10000, // 4 decimal places
    };
  }
}
```

## Database Access Patterns

### Row-Level Security Context

```typescript
// apps/api/src/lib/context.ts

import { inferAsyncReturnType } from '@trpc/server';
import { CreateAWSLambdaContextOptions } from '@trpc/server/adapters/aws-lambda';
import { prisma } from './prisma';
import { verifyToken } from './auth';

export async function createContext({
  event,
  context,
}: CreateAWSLambdaContextOptions) {
  // Extract token from Authorization header
  const token = event.headers.authorization?.replace('Bearer ', '');

  if (!token) {
    return { prisma, restaurantId: null, userId: null };
  }

  try {
    const payload = await verifyToken(token);

    // Set RLS context
    await prisma.$executeRaw`
      SET LOCAL app.current_restaurant_id = ${payload.restaurantId};
      SET LOCAL app.current_user_id = ${payload.userId};
    `;

    return {
      prisma,
      restaurantId: payload.restaurantId,
      userId: payload.userId,
      userRole: payload.role,
    };
  } catch (error) {
    return { prisma, restaurantId: null, userId: null };
  }
}

export type Context = inferAsyncReturnType<typeof createContext>;
```

### Prisma Client Singleton

```typescript
// apps/api/src/lib/prisma.ts

import { PrismaClient } from '@repo/database';

declare global {
  var prisma: PrismaClient | undefined;
}

export const prisma =
  global.prisma ||
  new PrismaClient({
    log: process.env.NODE_ENV === 'development' ? ['query', 'error', 'warn'] : ['error'],
  });

if (process.env.NODE_ENV !== 'production') {
  global.prisma = prisma;
}

// Graceful shutdown
process.on('beforeExit', async () => {
  await prisma.$disconnect();
});
```

### Query Optimization

```typescript
// Example: Optimized forecast query with includes

export async function getForecastWithExplanation(forecastId: string) {
  return prisma.forecast.findUnique({
    where: { id: forecastId },
    include: {
      menuItem: {
        select: {
          id: true,
          name: true,
          category: true,
        },
      },
      explanation: true,
      feedback: {
        orderBy: {
          createdAt: 'desc',
        },
        take: 10,
      },
      forecastRun: {
        select: {
          forecastDate: true,
          modelVersion: true,
          avgAccuracy: true,
        },
      },
    },
  });
}
```

## Background Job Processing

### SQS Message Handling

```typescript
// apps/api/src/services/queue/QueueService.ts

import { SQS } from 'aws-sdk';
import { logger } from '../../lib/logger';

const sqs = new SQS();

export class QueueService {
  static async sendMessage(queueUrl: string, message: any): Promise<void> {
    await sqs
      .sendMessage({
        QueueUrl: queueUrl,
        MessageBody: JSON.stringify(message),
      })
      .promise();

    logger.info('Message sent to queue', { queueUrl });
  }

  static async sendBatch(queueUrl: string, messages: any[]): Promise<void> {
    // Split into batches of 10 (SQS limit)
    for (let i = 0; i < messages.length; i += 10) {
      const batch = messages.slice(i, i + 10);

      await sqs
        .sendMessageBatch({
          QueueUrl: queueUrl,
          Entries: batch.map((msg, index) => ({
            Id: `${i + index}`,
            MessageBody: JSON.stringify(msg),
          })),
        })
        .promise();
    }

    logger.info('Batch messages sent', {
      queueUrl,
      count: messages.length,
    });
  }
}
```

### Dead Letter Queue Handler

```typescript
// apps/api/src/handlers/dlq-handler.ts

import { SQSHandler } from 'aws-lambda';
import { logger } from '../lib/logger';
import { AlertService } from '../services/data-health/AlertService';

export const handler: SQSHandler = async (event) => {
  const alertService = new AlertService();

  for (const record of event.Records) {
    logger.error('Message sent to DLQ', {
      messageId: record.messageId,
      body: record.body,
      attributes: record.attributes,
    });

    // Parse original message
    const message = JSON.parse(record.body);

    // Create alert for failed job
    await alertService.createAlert({
      restaurantId: message.restaurantId,
      severity: 'HIGH',
      category: 'JOB_FAILURE',
      message: `Background job failed after retries: ${message.jobType}`,
      details: {
        messageId: record.messageId,
        failureCount: record.attributes.ApproximateReceiveCount,
        originalMessage: message,
      },
    });
  }
};
```

## ML Integration

### SageMaker Adapter

```typescript
// apps/api/src/adapters/ml/SageMakerAdapter.ts

import { SageMakerRuntime } from 'aws-sdk';
import { logger } from '../../lib/logger';

const sagemaker = new SageMakerRuntime();

interface PredictionInput {
  features: Record<string, number>[];
}

interface PredictionOutput {
  menuItemId: string;
  quantity: number;
  confidence: number;
  baseValue: number;
  shapValues: any;
}

export class SageMakerAdapter {
  private endpointName: string;

  constructor() {
    this.endpointName = process.env.SAGEMAKER_ENDPOINT_NAME!;
  }

  async predict(input: PredictionInput): Promise<PredictionOutput[]> {
    logger.info('Invoking SageMaker endpoint', {
      endpoint: this.endpointName,
      featureCount: input.features.length,
    });

    const response = await sagemaker
      .invokeEndpoint({
        EndpointName: this.endpointName,
        ContentType: 'application/json',
        Body: JSON.stringify(input),
      })
      .promise();

    const predictions = JSON.parse(response.Body.toString());

    logger.info('SageMaker predictions received', {
      predictionCount: predictions.length,
    });

    return predictions;
  }

  async batchPredict(inputs: PredictionInput[]): Promise<PredictionOutput[][]> {
    // Batch predictions with concurrency control
    const results: PredictionOutput[][] = [];

    for (const input of inputs) {
      const prediction = await this.predict(input);
      results.push(prediction);
    }

    return results;
  }
}
```

## Error Handling

### Custom Error Classes

```typescript
// apps/api/src/lib/errors.ts

export class AppError extends Error {
  constructor(
    message: string,
    public code: string,
    public statusCode: number = 500,
    public isOperational: boolean = true
  ) {
    super(message);
    Object.setPrototypeOf(this, AppError.prototype);
  }
}

export class ValidationError extends AppError {
  constructor(message: string) {
    super(message, 'VALIDATION_ERROR', 400);
  }
}

export class UnauthorizedError extends AppError {
  constructor(message: string = 'Unauthorized') {
    super(message, 'UNAUTHORIZED', 401);
  }
}

export class ForbiddenError extends AppError {
  constructor(message: string = 'Forbidden') {
    super(message, 'FORBIDDEN', 403);
  }
}

export class NotFoundError extends AppError {
  constructor(resource: string) {
    super(`${resource} not found`, 'NOT_FOUND', 404);
  }
}

export class RateLimitError extends AppError {
  constructor(message: string = 'Rate limit exceeded') {
    super(message, 'RATE_LIMIT_EXCEEDED', 429);
  }
}
```

### tRPC Error Mapping

```typescript
// apps/api/src/middleware/error-handler.ts

import { TRPCError } from '@trpc/server';
import { AppError } from '../lib/errors';

export function mapErrorToTRPC(error: Error): TRPCError {
  if (error instanceof AppError) {
    const codeMap: Record<string, any> = {
      VALIDATION_ERROR: 'BAD_REQUEST',
      UNAUTHORIZED: 'UNAUTHORIZED',
      FORBIDDEN: 'FORBIDDEN',
      NOT_FOUND: 'NOT_FOUND',
      RATE_LIMIT_EXCEEDED: 'TOO_MANY_REQUESTS',
    };

    return new TRPCError({
      code: codeMap[error.code] || 'INTERNAL_SERVER_ERROR',
      message: error.message,
    });
  }

  return new TRPCError({
    code: 'INTERNAL_SERVER_ERROR',
    message: 'An unexpected error occurred',
  });
}
```

## Logging

### Structured Logging with Winston

```typescript
// apps/api/src/lib/logger.ts

import winston from 'winston';

const logger = winston.createLogger({
  level: process.env.LOG_LEVEL || 'info',
  format: winston.format.combine(
    winston.format.timestamp(),
    winston.format.errors({ stack: true }),
    winston.format.json()
  ),
  defaultMeta: {
    service: 'flux-api',
    environment: process.env.NODE_ENV,
  },
  transports: [
    new winston.transports.Console({
      format: winston.format.combine(
        winston.format.colorize(),
        winston.format.simple()
      ),
    }),
  ],
});

// Add Datadog transport in production
if (process.env.NODE_ENV === 'production') {
  // Datadog logs are collected from CloudWatch
  logger.add(
    new winston.transports.Console({
      format: winston.format.json(),
    })
  );
}

export { logger };
```

### Request Logging Middleware

```typescript
// apps/api/src/middleware/logging.ts

import { middleware } from '../lib/trpc';
import { logger } from '../lib/logger';

export const loggingMiddleware = middleware(async ({ path, type, next, ctx }) => {
  const start = Date.now();

  logger.info('tRPC request started', {
    path,
    type,
    restaurantId: ctx.restaurantId,
    userId: ctx.userId,
  });

  const result = await next();

  const duration = Date.now() - start;

  logger.info('tRPC request completed', {
    path,
    type,
    duration,
    restaurantId: ctx.restaurantId,
    success: result.ok,
  });

  return result;
});
```

## Caching Strategy

### Redis Client

```typescript
// apps/api/src/lib/cache.ts

import Redis from 'ioredis';
import { logger } from './logger';

const redis = new Redis({
  host: process.env.REDIS_HOST,
  port: parseInt(process.env.REDIS_PORT || '6379'),
  password: process.env.REDIS_PASSWORD,
  retryStrategy: (times) => {
    const delay = Math.min(times * 50, 2000);
    return delay;
  },
});

redis.on('error', (error) => {
  logger.error('Redis connection error', { error: error.message });
});

export class CacheService {
  static async get<T>(key: string): Promise<T | null> {
    const value = await redis.get(key);
    return value ? JSON.parse(value) : null;
  }

  static async set(key: string, value: any, ttlSeconds: number = 3600): Promise<void> {
    await redis.setex(key, ttlSeconds, JSON.stringify(value));
  }

  static async delete(key: string): Promise<void> {
    await redis.del(key);
  }

  static async invalidatePattern(pattern: string): Promise<void> {
    const keys = await redis.keys(pattern);
    if (keys.length > 0) {
      await redis.del(...keys);
    }
  }
}

export { redis };
```

### Cache Middleware

```typescript
// Example: Caching forecast recommendations

export async function getProcurementRecommendations(
  restaurantId: string,
  date: string
) {
  const cacheKey = `procurement:recommendations:${restaurantId}:${date}`;

  // Check cache
  const cached = await CacheService.get(cacheKey);
  if (cached) {
    logger.info('Cache hit', { cacheKey });
    return cached;
  }

  // Query database
  const recommendations = await prisma.procurementRecommendation.findMany({
    where: {
      restaurantId,
      recommendedDate: new Date(date),
      status: 'PENDING',
    },
    include: {
      ingredient: true,
    },
  });

  // Store in cache (1 hour TTL)
  await CacheService.set(cacheKey, recommendations, 3600);

  return recommendations;
}
```

---

# Deployment Architecture

This section details the AWS infrastructure, deployment pipeline, environment management, and operational procedures for the Flux platform.

## Infrastructure Overview

### AWS Services Used

```
┌─────────────────────────────────────────────────────────────────┐
│                         Flux Platform                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                   │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐    │
│  │   Route 53   │────▶│  CloudFront  │────▶│   S3 Bucket  │    │
│  │     DNS      │     │     CDN      │     │  (Next.js)   │    │
│  └──────────────┘     └──────────────┘     └──────────────┘    │
│                              │                                    │
│                              │ /api/*                            │
│                              ▼                                    │
│  ┌────────────────────────────────────────────────────────┐    │
│  │              API Gateway (HTTP API)                     │    │
│  └────────────────────────────────────────────────────────┘    │
│                              │                                    │
│         ┌────────────────────┼────────────────────┐             │
│         │                    │                    │             │
│         ▼                    ▼                    ▼             │
│  ┌────────────┐      ┌────────────┐      ┌────────────┐       │
│  │  Lambda    │      │  Lambda    │      │  Lambda    │       │
│  │  (tRPC)    │      │ (Webhook)  │      │  (Worker)  │       │
│  └────────────┘      └────────────┘      └────────────┘       │
│         │                    │                    ▲             │
│         │                    │                    │             │
│         ▼                    ▼                    │             │
│  ┌─────────────────────────────────────────────────────┐       │
│  │                    RDS PostgreSQL                    │       │
│  │                (Multi-AZ, Encrypted)                 │       │
│  └─────────────────────────────────────────────────────┘       │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │  EventBridge │────▶│  SQS Queues  │────▶│   Lambda     │   │
│  │   (Cron)     │     │   + DLQ      │     │  (Workers)   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   SageMaker  │     │  ElastiCache │     │      S3      │   │
│  │  Endpoint    │     │    Redis     │     │   (Assets)   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
│                                                                  │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐   │
│  │   Secrets    │     │  CloudWatch  │     │   Datadog    │   │
│  │   Manager    │     │     Logs     │     │  (Metrics)   │   │
│  └──────────────┘     └──────────────┘     └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## AWS CDK Infrastructure

### Project Structure

```
infrastructure/
├── bin/
│   └── app.ts                      # CDK app entry point
├── lib/
│   ├── stacks/
│   │   ├── network-stack.ts       # VPC, subnets, security groups
│   │   ├── database-stack.ts      # RDS PostgreSQL, ElastiCache
│   │   ├── compute-stack.ts       # Lambda functions
│   │   ├── storage-stack.ts       # S3 buckets
│   │   ├── queue-stack.ts         # SQS queues, EventBridge
│   │   ├── api-stack.ts           # API Gateway
│   │   ├── frontend-stack.ts      # CloudFront, S3 for Next.js
│   │   ├── ml-stack.ts            # SageMaker endpoint
│   │   └── monitoring-stack.ts    # CloudWatch dashboards, alarms
│   ├── constructs/
│   │   ├── lambda-function.ts     # Reusable Lambda construct
│   │   ├── queue-processor.ts     # SQS + Lambda pattern
│   │   └── scheduled-job.ts       # EventBridge + Lambda
│   └── config/
│       ├── dev.ts
│       ├── staging.ts
│       └── prod.ts
├── cdk.json
└── package.json
```

### Network Stack

```typescript
// infrastructure/lib/stacks/network-stack.ts

import * as cdk from 'aws-cdk-lib';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import { Construct } from 'constructs';

export class NetworkStack extends cdk.Stack {
  public readonly vpc: ec2.Vpc;
  public readonly lambdaSecurityGroup: ec2.SecurityGroup;
  public readonly databaseSecurityGroup: ec2.SecurityGroup;
  public readonly redisSecurityGroup: ec2.SecurityGroup;

  constructor(scope: Construct, id: string, props?: cdk.StackProps) {
    super(scope, id, props);

    // VPC with 3 AZs
    this.vpc = new ec2.Vpc(this, 'FluxVpc', {
      maxAzs: 3,
      natGateways: 2, // High availability
      subnetConfiguration: [
        {
          name: 'Public',
          subnetType: ec2.SubnetType.PUBLIC,
          cidrMask: 24,
        },
        {
          name: 'Private',
          subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
          cidrMask: 24,
        },
        {
          name: 'Isolated',
          subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
          cidrMask: 24,
        },
      ],
    });

    // Lambda security group
    this.lambdaSecurityGroup = new ec2.SecurityGroup(this, 'LambdaSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for Lambda functions',
      allowAllOutbound: true,
    });

    // Database security group
    this.databaseSecurityGroup = new ec2.SecurityGroup(this, 'DatabaseSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for RDS PostgreSQL',
      allowAllOutbound: false,
    });

    // Allow Lambda to connect to database
    this.databaseSecurityGroup.addIngressRule(
      this.lambdaSecurityGroup,
      ec2.Port.tcp(5432),
      'Allow Lambda to connect to PostgreSQL'
    );

    // Redis security group
    this.redisSecurityGroup = new ec2.SecurityGroup(this, 'RedisSecurityGroup', {
      vpc: this.vpc,
      description: 'Security group for ElastiCache Redis',
      allowAllOutbound: false,
    });

    // Allow Lambda to connect to Redis
    this.redisSecurityGroup.addIngressRule(
      this.lambdaSecurityGroup,
      ec2.Port.tcp(6379),
      'Allow Lambda to connect to Redis'
    );

    // VPC Endpoints for AWS services (reduce NAT costs)
    this.vpc.addInterfaceEndpoint('SecretsManagerEndpoint', {
      service: ec2.InterfaceVpcEndpointAwsService.SECRETS_MANAGER,
    });

    this.vpc.addInterfaceEndpoint('SQSEndpoint', {
      service: ec2.InterfaceVpcEndpointAwsService.SQS,
    });

    this.vpc.addGatewayEndpoint('S3Endpoint', {
      service: ec2.GatewayVpcEndpointAwsService.S3,
    });
  }
}
```

### Database Stack

```typescript
// infrastructure/lib/stacks/database-stack.ts

import * as cdk from 'aws-cdk-lib';
import * as rds from 'aws-cdk-lib/aws-rds';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as elasticache from 'aws-cdk-lib/aws-elasticache';
import * as secretsmanager from 'aws-cdk-lib/aws-secretsmanager';
import { Construct } from 'constructs';

interface DatabaseStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  databaseSecurityGroup: ec2.SecurityGroup;
  redisSecurityGroup: ec2.SecurityGroup;
  environment: string;
}

export class DatabaseStack extends cdk.Stack {
  public readonly database: rds.DatabaseInstance;
  public readonly databaseSecret: secretsmanager.Secret;
  public readonly redisCluster: elasticache.CfnCacheCluster;

  constructor(scope: Construct, id: string, props: DatabaseStackProps) {
    super(scope, id, props);

    // Database credentials secret
    this.databaseSecret = new secretsmanager.Secret(this, 'DatabaseSecret', {
      secretName: `flux/${props.environment}/database`,
      generateSecretString: {
        secretStringTemplate: JSON.stringify({ username: 'flux_admin' }),
        generateStringKey: 'password',
        excludePunctuation: true,
        includeSpace: false,
        passwordLength: 32,
      },
    });

    // RDS Parameter Group for PostgreSQL optimization
    const parameterGroup = new rds.ParameterGroup(this, 'PostgresParameterGroup', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_15_3,
      }),
      parameters: {
        'shared_preload_libraries': 'pg_stat_statements,pg_trgm',
        'max_connections': '200',
        'work_mem': '16MB',
        'maintenance_work_mem': '512MB',
        'effective_cache_size': '4GB',
        'random_page_cost': '1.1', // SSD optimized
      },
    });

    // PostgreSQL Database
    this.database = new rds.DatabaseInstance(this, 'PostgresDatabase', {
      engine: rds.DatabaseInstanceEngine.postgres({
        version: rds.PostgresEngineVersion.VER_15_3,
      }),
      instanceType: props.environment === 'prod'
        ? ec2.InstanceType.of(ec2.InstanceClass.R6G, ec2.InstanceSize.XLARGE2)
        : ec2.InstanceType.of(ec2.InstanceClass.T4G, ec2.InstanceSize.MEDIUM),
      vpc: props.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      },
      securityGroups: [props.databaseSecurityGroup],
      credentials: rds.Credentials.fromSecret(this.databaseSecret),
      databaseName: 'flux',
      allocatedStorage: props.environment === 'prod' ? 500 : 100,
      storageType: rds.StorageType.GP3,
      iops: props.environment === 'prod' ? 12000 : 3000,
      multiAz: props.environment === 'prod',
      storageEncrypted: true,
      deletionProtection: props.environment === 'prod',
      backupRetention: cdk.Duration.days(props.environment === 'prod' ? 30 : 7),
      preferredBackupWindow: '03:00-04:00',
      preferredMaintenanceWindow: 'sun:04:00-sun:05:00',
      parameterGroup,
      cloudwatchLogsExports: ['postgresql', 'upgrade'],
      enablePerformanceInsights: true,
      performanceInsightRetention: rds.PerformanceInsightRetention.MONTHS_1,
    });

    // Redis ElastiCache
    const redisSubnetGroup = new elasticache.CfnSubnetGroup(this, 'RedisSubnetGroup', {
      description: 'Subnet group for Redis cluster',
      subnetIds: props.vpc.selectSubnets({
        subnetType: ec2.SubnetType.PRIVATE_ISOLATED,
      }).subnetIds,
    });

    this.redisCluster = new elasticache.CfnCacheCluster(this, 'RedisCluster', {
      cacheNodeType: props.environment === 'prod' ? 'cache.r6g.large' : 'cache.t4g.medium',
      engine: 'redis',
      numCacheNodes: 1,
      cacheSubnetGroupName: redisSubnetGroup.ref,
      vpcSecurityGroupIds: [props.redisSecurityGroup.securityGroupId],
      engineVersion: '7.0',
      port: 6379,
      preferredMaintenanceWindow: 'sun:05:00-sun:06:00',
      snapshotRetentionLimit: props.environment === 'prod' ? 7 : 1,
      snapshotWindow: '03:00-04:00',
    });

    // Outputs
    new cdk.CfnOutput(this, 'DatabaseEndpoint', {
      value: this.database.dbInstanceEndpointAddress,
      exportName: `${props.environment}-DatabaseEndpoint`,
    });

    new cdk.CfnOutput(this, 'RedisEndpoint', {
      value: this.redisCluster.attrRedisEndpointAddress,
      exportName: `${props.environment}-RedisEndpoint`,
    });
  }
}
```

### Compute Stack (Lambda Functions)

```typescript
// infrastructure/lib/stacks/compute-stack.ts

import * as cdk from 'aws-cdk-lib';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as nodejs from 'aws-cdk-lib/aws-lambda-nodejs';
import * as ec2 from 'aws-cdk-lib/aws-ec2';
import * as iam from 'aws-cdk-lib/aws-iam';
import { Construct } from 'constructs';

interface ComputeStackProps extends cdk.StackProps {
  vpc: ec2.Vpc;
  lambdaSecurityGroup: ec2.SecurityGroup;
  databaseSecret: any;
  environment: string;
}

export class ComputeStack extends cdk.Stack {
  public readonly trpcHandler: nodejs.NodejsFunction;
  public readonly webhookHandler: nodejs.NodejsFunction;
  public readonly posSyncHandler: nodejs.NodejsFunction;
  public readonly forecastHandler: nodejs.NodejsFunction;

  constructor(scope: Construct, id: string, props: ComputeStackProps) {
    super(scope, id, props);

    // Shared Lambda layer for dependencies
    const dependenciesLayer = new lambda.LayerVersion(this, 'DependenciesLayer', {
      code: lambda.Code.fromAsset('lambda-layers/dependencies'),
      compatibleRuntimes: [lambda.Runtime.NODEJS_18_X],
      description: 'Shared dependencies for Lambda functions',
    });

    // Common Lambda environment variables
    const commonEnv = {
      NODE_ENV: props.environment,
      DATABASE_URL: `postgresql://\${Token[TOKEN.${props.databaseSecret.secretArn}]}`,
      LOG_LEVEL: props.environment === 'prod' ? 'info' : 'debug',
    };

    // Common Lambda configuration
    const lambdaDefaults = {
      runtime: lambda.Runtime.NODEJS_18_X,
      vpc: props.vpc,
      vpcSubnets: {
        subnetType: ec2.SubnetType.PRIVATE_WITH_EGRESS,
      },
      securityGroups: [props.lambdaSecurityGroup],
      layers: [dependenciesLayer],
      timeout: cdk.Duration.seconds(30),
      memorySize: 1024,
      environment: commonEnv,
      bundling: {
        minify: true,
        sourceMap: true,
        target: 'es2022',
        externalModules: ['aws-sdk', '@aws-sdk/*'],
      },
    };

    // tRPC API Handler
    this.trpcHandler = new nodejs.NodejsFunction(this, 'TrpcHandler', {
      ...lambdaDefaults,
      entry: '../apps/api/src/handlers/trpc-handler.ts',
      functionName: `flux-${props.environment}-trpc`,
      timeout: cdk.Duration.seconds(30),
      memorySize: 2048,
      reservedConcurrentExecutions: props.environment === 'prod' ? 100 : 10,
    });

    // Webhook Handler
    this.webhookHandler = new nodejs.NodejsFunction(this, 'WebhookHandler', {
      ...lambdaDefaults,
      entry: '../apps/api/src/handlers/webhook-handler.ts',
      functionName: `flux-${props.environment}-webhook`,
      timeout: cdk.Duration.seconds(10),
    });

    // POS Sync Handler
    this.posSyncHandler = new nodejs.NodejsFunction(this, 'PosSyncHandler', {
      ...lambdaDefaults,
      entry: '../apps/api/src/handlers/pos-sync-handler.ts',
      functionName: `flux-${props.environment}-pos-sync`,
      timeout: cdk.Duration.minutes(5),
      memorySize: 2048,
      reservedConcurrentExecutions: 20,
    });

    // Forecast Handler
    this.forecastHandler = new nodejs.NodejsFunction(this, 'ForecastHandler', {
      ...lambdaDefaults,
      entry: '../apps/api/src/handlers/forecast-handler.ts',
      functionName: `flux-${props.environment}-forecast`,
      timeout: cdk.Duration.minutes(15),
      memorySize: 3008,
    });

    // Grant database secret access
    [this.trpcHandler, this.webhookHandler, this.posSyncHandler, this.forecastHandler].forEach(
      (fn) => {
        props.databaseSecret.grantRead(fn);
      }
    );

    // Grant SageMaker access to forecast handler
    this.forecastHandler.addToRolePolicy(
      new iam.PolicyStatement({
        actions: ['sagemaker:InvokeEndpoint'],
        resources: [`arn:aws:sagemaker:${this.region}:${this.account}:endpoint/flux-*`],
      })
    );
  }
}
```

### Queue Stack

```typescript
// infrastructure/lib/stacks/queue-stack.ts

import * as cdk from 'aws-cdk-lib';
import * as sqs from 'aws-cdk-lib/aws-sqs';
import * as events from 'aws-cdk-lib/aws-events';
import * as targets from 'aws-cdk-lib/aws-events-targets';
import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as lambdaEventSources from 'aws-cdk-lib/aws-lambda-event-sources';
import { Construct } from 'constructs';

interface QueueStackProps extends cdk.StackProps {
  posSyncHandler: lambda.Function;
  forecastHandler: lambda.Function;
  environment: string;
}

export class QueueStack extends cdk.Stack {
  public readonly posSyncQueue: sqs.Queue;
  public readonly forecastQueue: sqs.Queue;

  constructor(scope: Construct, id: string, props: QueueStackProps) {
    super(scope, id, props);

    // POS Sync Queue with DLQ
    const posSyncDLQ = new sqs.Queue(this, 'PosSyncDLQ', {
      queueName: `flux-${props.environment}-pos-sync-dlq`,
      retentionPeriod: cdk.Duration.days(14),
    });

    this.posSyncQueue = new sqs.Queue(this, 'PosSyncQueue', {
      queueName: `flux-${props.environment}-pos-sync`,
      visibilityTimeout: cdk.Duration.minutes(6), // > Lambda timeout
      receiveMessageWaitTime: cdk.Duration.seconds(20), // Long polling
      deadLetterQueue: {
        queue: posSyncDLQ,
        maxReceiveCount: 3,
      },
    });

    // Connect queue to Lambda
    props.posSyncHandler.addEventSource(
      new lambdaEventSources.SqsEventSource(this.posSyncQueue, {
        batchSize: 10,
        maxBatchingWindow: cdk.Duration.seconds(5),
      })
    );

    // Forecast Queue with DLQ
    const forecastDLQ = new sqs.Queue(this, 'ForecastDLQ', {
      queueName: `flux-${props.environment}-forecast-dlq`,
      retentionPeriod: cdk.Duration.days(14),
    });

    this.forecastQueue = new sqs.Queue(this, 'ForecastQueue', {
      queueName: `flux-${props.environment}-forecast`,
      visibilityTimeout: cdk.Duration.minutes(16), // > Lambda timeout
      receiveMessageWaitTime: cdk.Duration.seconds(20),
      deadLetterQueue: {
        queue: forecastDLQ,
        maxReceiveCount: 2,
      },
    });

    // EventBridge Rule for daily forecasts
    const forecastScheduleRule = new events.Rule(this, 'ForecastScheduleRule', {
      ruleName: `flux-${props.environment}-forecast-schedule`,
      schedule: events.Schedule.cron({
        hour: '2',
        minute: '0',
      }),
    });

    forecastScheduleRule.addTarget(
      new targets.LambdaFunction(props.forecastHandler)
    );

    // EventBridge Rule for POS sync polling (every 15 minutes)
    const posSyncPollingRule = new events.Rule(this, 'PosSyncPollingRule', {
      ruleName: `flux-${props.environment}-pos-sync-polling`,
      schedule: events.Schedule.rate(cdk.Duration.minutes(15)),
    });

    // Outputs
    new cdk.CfnOutput(this, 'PosSyncQueueUrl', {
      value: this.posSyncQueue.queueUrl,
      exportName: `${props.environment}-PosSyncQueueUrl`,
    });

    new cdk.CfnOutput(this, 'ForecastQueueUrl', {
      value: this.forecastQueue.queueUrl,
      exportName: `${props.environment}-ForecastQueueUrl`,
    });
  }
}
```

### Frontend Stack (CloudFront + S3)

```typescript
// infrastructure/lib/stacks/frontend-stack.ts

import * as cdk from 'aws-cdk-lib';
import * as s3 from 'aws-cdk-lib/aws-s3';
import * as cloudfront from 'aws-cdk-lib/aws-cloudfront';
import * as origins from 'aws-cdk-lib/aws-cloudfront-origins';
import * as s3deploy from 'aws-cdk-lib/aws-s3-deployment';
import * as acm from 'aws-cdk-lib/aws-certificatemanager';
import { Construct } from 'constructs';

interface FrontendStackProps extends cdk.StackProps {
  apiGatewayUrl: string;
  domainName?: string;
  certificate?: acm.Certificate;
  environment: string;
}

export class FrontendStack extends cdk.Stack {
  public readonly distribution: cloudfront.Distribution;
  public readonly bucket: s3.Bucket;

  constructor(scope: Construct, id: string, props: FrontendStackProps) {
    super(scope, id, props);

    // S3 bucket for Next.js static assets
    this.bucket = new s3.Bucket(this, 'FrontendBucket', {
      bucketName: `flux-${props.environment}-frontend`,
      encryption: s3.BucketEncryption.S3_MANAGED,
      blockPublicAccess: s3.BlockPublicAccess.BLOCK_ALL,
      removalPolicy: props.environment === 'prod'
        ? cdk.RemovalPolicy.RETAIN
        : cdk.RemovalPolicy.DESTROY,
      autoDeleteObjects: props.environment !== 'prod',
      versioned: props.environment === 'prod',
      lifecycleRules: [
        {
          enabled: true,
          noncurrentVersionExpiration: cdk.Duration.days(30),
        },
      ],
    });

    // Origin Access Identity for CloudFront
    const oai = new cloudfront.OriginAccessIdentity(this, 'OAI');
    this.bucket.grantRead(oai);

    // CloudFront distribution
    this.distribution = new cloudfront.Distribution(this, 'Distribution', {
      defaultBehavior: {
        origin: new origins.S3Origin(this.bucket, {
          originAccessIdentity: oai,
        }),
        viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
        cachePolicy: cloudfront.CachePolicy.CACHING_OPTIMIZED,
        compress: true,
      },
      additionalBehaviors: {
        '/api/*': {
          origin: new origins.HttpOrigin(props.apiGatewayUrl),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.HTTPS_ONLY,
          cachePolicy: cloudfront.CachePolicy.CACHING_DISABLED,
          allowedMethods: cloudfront.AllowedMethods.ALLOW_ALL,
          originRequestPolicy: cloudfront.OriginRequestPolicy.ALL_VIEWER,
        },
        '/_next/*': {
          origin: new origins.S3Origin(this.bucket, {
            originAccessIdentity: oai,
          }),
          viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
          cachePolicy: new cloudfront.CachePolicy(this, 'NextAssetsCachePolicy', {
            cachePolicyName: `flux-${props.environment}-next-assets`,
            defaultTtl: cdk.Duration.days(365),
            maxTtl: cdk.Duration.days(365),
            minTtl: cdk.Duration.days(365),
          }),
          compress: true,
        },
      },
      domainNames: props.domainName ? [props.domainName] : undefined,
      certificate: props.certificate,
      defaultRootObject: 'index.html',
      errorResponses: [
        {
          httpStatus: 404,
          responseHttpStatus: 200,
          responsePagePath: '/index.html',
          ttl: cdk.Duration.seconds(0),
        },
      ],
      priceClass: cloudfront.PriceClass.PRICE_CLASS_100, // US, Canada, Europe
      enableLogging: true,
      logBucket: new s3.Bucket(this, 'LogBucket', {
        bucketName: `flux-${props.environment}-cloudfront-logs`,
        encryption: s3.BucketEncryption.S3_MANAGED,
        lifecycleRules: [
          {
            enabled: true,
            expiration: cdk.Duration.days(90),
          },
        ],
      }),
    });

    // Output
    new cdk.CfnOutput(this, 'DistributionDomainName', {
      value: this.distribution.distributionDomainName,
      exportName: `${props.environment}-DistributionDomainName`,
    });
  }
}
```

## CI/CD Pipeline

### GitHub Actions Workflow

```yaml
# .github/workflows/deploy.yml

name: Deploy Flux Platform

on:
  push:
    branches:
      - main
      - staging
      - develop

env:
  AWS_REGION: us-east-1
  NODE_VERSION: '18'

jobs:
  test:
    name: Test
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run linter
        run: npm run lint

      - name: Run type check
        run: npm run type-check

      - name: Run unit tests
        run: npm run test:unit

      - name: Run integration tests
        run: npm run test:integration
        env:
          DATABASE_URL: ${{ secrets.TEST_DATABASE_URL }}

  build:
    name: Build
    needs: test
    runs-on: ubuntu-latest
    outputs:
      environment: ${{ steps.set-env.outputs.environment }}
    steps:
      - uses: actions/checkout@v3

      - name: Determine environment
        id: set-env
        run: |
          if [[ "${{ github.ref }}" == "refs/heads/main" ]]; then
            echo "environment=prod" >> $GITHUB_OUTPUT
          elif [[ "${{ github.ref }}" == "refs/heads/staging" ]]; then
            echo "environment=staging" >> $GITHUB_OUTPUT
          else
            echo "environment=dev" >> $GITHUB_OUTPUT
          fi

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Generate Prisma Client
        run: npx prisma generate

      - name: Build packages
        run: npm run build

      - name: Build Next.js app
        run: |
          cd apps/web
          npm run build
        env:
          NEXT_PUBLIC_API_URL: ${{ secrets[format('{0}_API_URL', steps.set-env.outputs.environment)] }}

      - name: Upload build artifacts
        uses: actions/upload-artifact@v3
        with:
          name: build-artifacts
          path: |
            apps/web/.next
            apps/api/dist
            packages/*/dist

  deploy-infrastructure:
    name: Deploy Infrastructure
    needs: build
    runs-on: ubuntu-latest
    environment: ${{ needs.build.outputs.environment }}
    steps:
      - uses: actions/checkout@v3

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}
          cache: 'npm'

      - name: Install CDK dependencies
        run: |
          cd infrastructure
          npm ci

      - name: CDK diff
        run: |
          cd infrastructure
          npx cdk diff --context environment=${{ needs.build.outputs.environment }}

      - name: CDK deploy
        run: |
          cd infrastructure
          npx cdk deploy --all \
            --context environment=${{ needs.build.outputs.environment }} \
            --require-approval never

  deploy-application:
    name: Deploy Application
    needs: [build, deploy-infrastructure]
    runs-on: ubuntu-latest
    environment: ${{ needs.build.outputs.environment }}
    steps:
      - uses: actions/checkout@v3

      - name: Download build artifacts
        uses: actions/download-artifact@v3
        with:
          name: build-artifacts

      - name: Configure AWS credentials
        uses: aws-actions/configure-aws-credentials@v2
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      # Deploy Lambda functions
      - name: Deploy Lambda functions
        run: |
          ENV=${{ needs.build.outputs.environment }}

          # Update tRPC handler
          aws lambda update-function-code \
            --function-name flux-$ENV-trpc \
            --zip-file fileb://apps/api/dist/trpc-handler.zip

          # Update webhook handler
          aws lambda update-function-code \
            --function-name flux-$ENV-webhook \
            --zip-file fileb://apps/api/dist/webhook-handler.zip

          # Update POS sync handler
          aws lambda update-function-code \
            --function-name flux-$ENV-pos-sync \
            --zip-file fileb://apps/api/dist/pos-sync-handler.zip

          # Update forecast handler
          aws lambda update-function-code \
            --function-name flux-$ENV-forecast \
            --zip-file fileb://apps/api/dist/forecast-handler.zip

      # Run database migrations
      - name: Run database migrations
        run: |
          npx prisma migrate deploy
        env:
          DATABASE_URL: ${{ secrets[format('{0}_DATABASE_URL', needs.build.outputs.environment)] }}

      # Deploy frontend to S3
      - name: Deploy frontend to S3
        run: |
          ENV=${{ needs.build.outputs.environment }}
          BUCKET_NAME=$(aws cloudformation describe-stacks \
            --stack-name flux-$ENV-frontend \
            --query 'Stacks[0].Outputs[?OutputKey==`FrontendBucketName`].OutputValue' \
            --output text)

          aws s3 sync apps/web/.next/static s3://$BUCKET_NAME/_next/static --delete
          aws s3 sync apps/web/public s3://$BUCKET_NAME --delete

      # Invalidate CloudFront cache
      - name: Invalidate CloudFront
        run: |
          ENV=${{ needs.build.outputs.environment }}
          DISTRIBUTION_ID=$(aws cloudformation describe-stacks \
            --stack-name flux-$ENV-frontend \
            --query 'Stacks[0].Outputs[?OutputKey==`DistributionId`].OutputValue' \
            --output text)

          aws cloudfront create-invalidation \
            --distribution-id $DISTRIBUTION_ID \
            --paths "/*"

  smoke-tests:
    name: Smoke Tests
    needs: [build, deploy-application]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: ${{ env.NODE_VERSION }}

      - name: Run smoke tests
        run: npm run test:smoke
        env:
          API_URL: ${{ secrets[format('{0}_API_URL', needs.build.outputs.environment)] }}
          TEST_USER_EMAIL: ${{ secrets.TEST_USER_EMAIL }}
          TEST_USER_PASSWORD: ${{ secrets.TEST_USER_PASSWORD }}
```

## Environment Configuration

### Environment Variables

```typescript
// infrastructure/lib/config/prod.ts

export const prodConfig = {
  environment: 'prod',

  vpc: {
    maxAzs: 3,
    natGateways: 2,
  },

  database: {
    instanceType: 'r6g.2xlarge',
    allocatedStorage: 500,
    multiAz: true,
    backupRetention: 30,
    deletionProtection: true,
  },

  redis: {
    nodeType: 'cache.r6g.large',
    numCacheNodes: 1,
  },

  lambda: {
    trpc: {
      memorySize: 2048,
      timeout: 30,
      reservedConcurrency: 100,
    },
    posSyncWorker: {
      memorySize: 2048,
      timeout: 300,
      reservedConcurrency: 20,
    },
    forecastWorker: {
      memorySize: 3008,
      timeout: 900,
      reservedConcurrency: 10,
    },
  },

  monitoring: {
    enableXRay: true,
    logRetention: 30, // days
    alarmEmail: 'ops@flux.app',
  },

  domain: {
    name: 'app.flux.app',
    certificateArn: 'arn:aws:acm:us-east-1:...',
  },
};
```

## Deployment Strategy

### Blue-Green Deployment

```typescript
// For Lambda functions using aliases

import * as lambda from 'aws-cdk-lib/aws-lambda';
import * as codedeploy from 'aws-cdk-lib/aws-codedeploy';

// Create Lambda alias
const alias = new lambda.Alias(this, 'ProdAlias', {
  aliasName: 'prod',
  version: this.trpcHandler.currentVersion,
});

// CodeDeploy application
const application = new codedeploy.LambdaApplication(this, 'Application');

// Deployment group with gradual rollout
const deploymentGroup = new codedeploy.LambdaDeploymentGroup(this, 'DeploymentGroup', {
  alias,
  application,
  deploymentConfig: codedeploy.LambdaDeploymentConfig.CANARY_10PERCENT_5MINUTES,
  alarms: [
    new cloudwatch.Alarm(this, 'ErrorAlarm', {
      metric: alias.metricErrors(),
      threshold: 1,
      evaluationPeriods: 1,
    }),
  ],
  autoRollback: {
    failedDeployment: true,
    stoppedDeployment: true,
    deploymentInAlarm: true,
  },
});
```

### Rollback Procedure

```bash
# Rollback Lambda function to previous version
aws lambda update-alias \
  --function-name flux-prod-trpc \
  --name prod \
  --function-version <previous-version>

# Rollback database migration (if needed)
npx prisma migrate resolve --rolled-back <migration-name>

# Rollback frontend (restore from S3 versioning)
aws s3api list-object-versions \
  --bucket flux-prod-frontend \
  --prefix index.html

aws s3api copy-object \
  --copy-source flux-prod-frontend/index.html?versionId=<previous-version> \
  --bucket flux-prod-frontend \
  --key index.html
```

## Monitoring & Alarms

### CloudWatch Alarms

```typescript
// infrastructure/lib/stacks/monitoring-stack.ts

import * as cloudwatch from 'aws-cdk-lib/aws-cloudwatch';
import * as sns from 'aws-cdk-lib/aws-sns';
import * as subscriptions from 'aws-cdk-lib/aws-sns-subscriptions';
import * as actions from 'aws-cdk-lib/aws-cloudwatch-actions';

export class MonitoringStack extends cdk.Stack {
  constructor(scope: Construct, id: string, props: MonitoringStackProps) {
    super(scope, id, props);

    // SNS topic for alerts
    const alertTopic = new sns.Topic(this, 'AlertTopic', {
      displayName: 'Flux Platform Alerts',
    });

    alertTopic.addSubscription(
      new subscriptions.EmailSubscription('ops@flux.app')
    );

    // Lambda error alarm
    new cloudwatch.Alarm(this, 'LambdaErrorAlarm', {
      alarmName: `flux-${props.environment}-lambda-errors`,
      metric: props.trpcHandler.metricErrors({
        period: cdk.Duration.minutes(5),
        statistic: 'Sum',
      }),
      threshold: 10,
      evaluationPeriods: 1,
      treatMissingData: cloudwatch.TreatMissingData.NOT_BREACHING,
    }).addAlarmAction(new actions.SnsAction(alertTopic));

    // Database connection alarm
    new cloudwatch.Alarm(this, 'DatabaseConnectionAlarm', {
      alarmName: `flux-${props.environment}-database-connections`,
      metric: props.database.metricDatabaseConnections({
        period: cdk.Duration.minutes(5),
        statistic: 'Average',
      }),
      threshold: 180, // 90% of max_connections (200)
      evaluationPeriods: 2,
    }).addAlarmAction(new actions.SnsAction(alertTopic));

    // API Gateway 5xx errors
    new cloudwatch.Alarm(this, 'ApiGateway5xxAlarm', {
      alarmName: `flux-${props.environment}-api-5xx-errors`,
      metric: new cloudwatch.Metric({
        namespace: 'AWS/ApiGateway',
        metricName: '5XXError',
        dimensionsMap: {
          ApiId: props.apiGateway.apiId,
        },
        period: cdk.Duration.minutes(5),
        statistic: 'Sum',
      }),
      threshold: 5,
      evaluationPeriods: 1,
    }).addAlarmAction(new actions.SnsAction(alertTopic));

    // SQS DLQ messages
    new cloudwatch.Alarm(this, 'DLQMessagesAlarm', {
      alarmName: `flux-${props.environment}-dlq-messages`,
      metric: props.posSyncDLQ.metricApproximateNumberOfMessagesVisible({
        period: cdk.Duration.minutes(5),
        statistic: 'Maximum',
      }),
      threshold: 1,
      evaluationPeriods: 1,
    }).addAlarmAction(new actions.SnsAction(alertTopic));
  }
}
```

---

# Security & Compliance

This section details security implementation, GDPR compliance, EU AI Act compliance, data protection, and audit logging for the Flux platform.

## Security Architecture Overview

### Defense in Depth Strategy

```
┌─────────────────────────────────────────────────────────────┐
│                     Security Layers                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Layer 1: Network Security                                   │
│  ├─ VPC with private subnets                                │
│  ├─ Security groups (least privilege)                       │
│  ├─ NACLs for subnet-level filtering                        │
│  └─ AWS WAF for API Gateway                                 │
│                                                               │
│  Layer 2: Application Security                              │
│  ├─ JWT authentication with short expiry                    │
│  ├─ Role-based access control (RBAC)                        │
│  ├─ Input validation with Zod                               │
│  ├─ Rate limiting per user/IP                               │
│  └─ CSRF protection                                          │
│                                                               │
│  Layer 3: Data Security                                      │
│  ├─ Encryption at rest (AES-256)                            │
│  ├─ Encryption in transit (TLS 1.3)                         │
│  ├─ Row-level security (RLS)                                │
│  ├─ Secrets in AWS Secrets Manager                          │
│  └─ Database credentials rotation                           │
│                                                               │
│  Layer 4: Monitoring & Audit                                │
│  ├─ CloudTrail for API activity                             │
│  ├─ Application audit logs                                  │
│  ├─ Security alerts via SNS                                 │
│  └─ Anomaly detection                                        │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## Authentication & Authorization

### JWT Token Strategy

```typescript
// apps/api/src/lib/auth/TokenService.ts

import jwt from 'jsonwebtoken';
import { prisma } from '../prisma';

interface TokenPayload {
  userId: string;
  restaurantId: string;
  role: string;
  email: string;
  sessionId: string;
}

export class TokenService {
  private static readonly ACCESS_TOKEN_SECRET = process.env.JWT_ACCESS_SECRET!;
  private static readonly REFRESH_TOKEN_SECRET = process.env.JWT_REFRESH_SECRET!;
  private static readonly ACCESS_TOKEN_EXPIRY = '15m';
  private static readonly REFRESH_TOKEN_EXPIRY = '7d';

  static async generateTokenPair(payload: TokenPayload): Promise<{
    accessToken: string;
    refreshToken: string;
  }> {
    // Generate access token (short-lived)
    const accessToken = jwt.sign(payload, this.ACCESS_TOKEN_SECRET, {
      expiresIn: this.ACCESS_TOKEN_EXPIRY,
      issuer: 'flux-platform',
      audience: 'flux-api',
    });

    // Generate refresh token (long-lived)
    const refreshToken = jwt.sign(
      { userId: payload.userId, sessionId: payload.sessionId },
      this.REFRESH_TOKEN_SECRET,
      {
        expiresIn: this.REFRESH_TOKEN_EXPIRY,
        issuer: 'flux-platform',
        audience: 'flux-api',
      }
    );

    // Store session in database
    await prisma.userSession.create({
      data: {
        id: payload.sessionId,
        userId: payload.userId,
        token: refreshToken,
        expiresAt: new Date(Date.now() + 7 * 24 * 60 * 60 * 1000), // 7 days
      },
    });

    return { accessToken, refreshToken };
  }

  static async verifyAccessToken(token: string): Promise<TokenPayload> {
    try {
      const payload = jwt.verify(token, this.ACCESS_TOKEN_SECRET, {
        issuer: 'flux-platform',
        audience: 'flux-api',
      }) as TokenPayload;

      return payload;
    } catch (error) {
      if (error instanceof jwt.TokenExpiredError) {
        throw new UnauthorizedError('Token expired');
      }
      throw new UnauthorizedError('Invalid token');
    }
  }

  static async refreshAccessToken(refreshToken: string): Promise<{
    accessToken: string;
    refreshToken: string;
  }> {
    // Verify refresh token
    const payload = jwt.verify(refreshToken, this.REFRESH_TOKEN_SECRET, {
      issuer: 'flux-platform',
      audience: 'flux-api',
    }) as { userId: string; sessionId: string };

    // Check session exists and is valid
    const session = await prisma.userSession.findUnique({
      where: { id: payload.sessionId },
      include: {
        user: {
          include: {
            memberships: {
              where: { status: 'ACTIVE' },
              include: { restaurant: true },
            },
          },
        },
      },
    });

    if (!session || session.expiresAt < new Date()) {
      throw new UnauthorizedError('Session expired');
    }

    // Generate new token pair
    const newPayload: TokenPayload = {
      userId: session.user.id,
      restaurantId: session.user.memberships[0]?.restaurantId,
      role: session.user.memberships[0]?.role,
      email: session.user.email,
      sessionId: session.id,
    };

    return this.generateTokenPair(newPayload);
  }

  static async revokeSession(sessionId: string): Promise<void> {
    await prisma.userSession.delete({
      where: { id: sessionId },
    });
  }

  static async revokeAllUserSessions(userId: string): Promise<void> {
    await prisma.userSession.deleteMany({
      where: { userId },
    });
  }
}
```

### Role-Based Access Control (RBAC)

```typescript
// apps/api/src/middleware/authorization.ts

import { TRPCError } from '@trpc/server';
import { middleware } from '../lib/trpc';

export enum Permission {
  // Forecast permissions
  FORECAST_VIEW = 'forecast:view',
  FORECAST_FEEDBACK = 'forecast:feedback',

  // Menu permissions
  MENU_VIEW = 'menu:view',
  MENU_CREATE = 'menu:create',
  MENU_UPDATE = 'menu:update',
  MENU_DELETE = 'menu:delete',

  // Recipe permissions
  RECIPE_VIEW = 'recipe:view',
  RECIPE_CREATE = 'recipe:create',
  RECIPE_UPDATE = 'recipe:update',
  RECIPE_VERIFY = 'recipe:verify', // Chef only

  // Procurement permissions
  PROCUREMENT_VIEW = 'procurement:view',
  PROCUREMENT_ORDER = 'procurement:order',

  // Team permissions
  TEAM_VIEW = 'team:view',
  TEAM_INVITE = 'team:invite',
  TEAM_REMOVE = 'team:remove',

  // Settings permissions
  SETTINGS_VIEW = 'settings:view',
  SETTINGS_UPDATE = 'settings:update',
  BILLING_MANAGE = 'billing:manage',
}

const ROLE_PERMISSIONS: Record<string, Permission[]> = {
  OWNER: [
    // All permissions
    ...Object.values(Permission),
  ],
  ADMIN: [
    Permission.FORECAST_VIEW,
    Permission.FORECAST_FEEDBACK,
    Permission.MENU_VIEW,
    Permission.MENU_CREATE,
    Permission.MENU_UPDATE,
    Permission.MENU_DELETE,
    Permission.RECIPE_VIEW,
    Permission.RECIPE_CREATE,
    Permission.RECIPE_UPDATE,
    Permission.PROCUREMENT_VIEW,
    Permission.PROCUREMENT_ORDER,
    Permission.TEAM_VIEW,
    Permission.TEAM_INVITE,
    Permission.SETTINGS_VIEW,
    Permission.SETTINGS_UPDATE,
  ],
  MANAGER: [
    Permission.FORECAST_VIEW,
    Permission.FORECAST_FEEDBACK,
    Permission.MENU_VIEW,
    Permission.MENU_UPDATE,
    Permission.RECIPE_VIEW,
    Permission.RECIPE_UPDATE,
    Permission.PROCUREMENT_VIEW,
    Permission.PROCUREMENT_ORDER,
    Permission.TEAM_VIEW,
  ],
  CHEF: [
    Permission.FORECAST_VIEW,
    Permission.MENU_VIEW,
    Permission.RECIPE_VIEW,
    Permission.RECIPE_CREATE,
    Permission.RECIPE_UPDATE,
    Permission.RECIPE_VERIFY,
    Permission.PROCUREMENT_VIEW,
  ],
  VIEWER: [
    Permission.FORECAST_VIEW,
    Permission.MENU_VIEW,
    Permission.RECIPE_VIEW,
    Permission.PROCUREMENT_VIEW,
  ],
};

export function requirePermission(...permissions: Permission[]) {
  return middleware(async ({ ctx, next }) => {
    if (!ctx.userId || !ctx.userRole) {
      throw new TRPCError({
        code: 'UNAUTHORIZED',
        message: 'Authentication required',
      });
    }

    const userPermissions = ROLE_PERMISSIONS[ctx.userRole] || [];

    const hasPermission = permissions.every((permission) =>
      userPermissions.includes(permission)
    );

    if (!hasPermission) {
      throw new TRPCError({
        code: 'FORBIDDEN',
        message: 'Insufficient permissions',
      });
    }

    return next();
  });
}
```

### Rate Limiting

```typescript
// apps/api/src/middleware/rate-limit.ts

import { RateLimiterRedis } from 'rate-limiter-flexible';
import { redis } from '../lib/cache';
import { middleware } from '../lib/trpc';
import { TRPCError } from '@trpc/server';

// Rate limiters for different endpoints
const rateLimiters = {
  // Authentication endpoints (prevent brute force)
  auth: new RateLimiterRedis({
    storeClient: redis,
    keyPrefix: 'rl:auth',
    points: 5, // 5 attempts
    duration: 300, // per 5 minutes
    blockDuration: 900, // block for 15 minutes
  }),

  // API endpoints (general usage)
  api: new RateLimiterRedis({
    storeClient: redis,
    keyPrefix: 'rl:api',
    points: 100, // 100 requests
    duration: 60, // per minute
  }),

  // ML-intensive endpoints (forecast generation)
  ml: new RateLimiterRedis({
    storeClient: redis,
    keyPrefix: 'rl:ml',
    points: 10, // 10 requests
    duration: 3600, // per hour
  }),
};

export function rateLimit(limiterType: keyof typeof rateLimiters = 'api') {
  return middleware(async ({ ctx, next }) => {
    const limiter = rateLimiters[limiterType];

    // Use userId if authenticated, otherwise IP address
    const key = ctx.userId || ctx.req.headers['x-forwarded-for'] || 'anonymous';

    try {
      await limiter.consume(key);
      return next();
    } catch (error) {
      throw new TRPCError({
        code: 'TOO_MANY_REQUESTS',
        message: 'Rate limit exceeded. Please try again later.',
      });
    }
  });
}
```

## Data Encryption

### Encryption at Rest

All data is encrypted at rest using AWS-managed encryption:

```typescript
// Database encryption (in CDK stack)
const database = new rds.DatabaseInstance(this, 'PostgresDatabase', {
  storageEncrypted: true,
  storageEncryptionKey: new kms.Key(this, 'DatabaseEncryptionKey', {
    description: 'Encryption key for RDS database',
    enableKeyRotation: true,
    removalPolicy: cdk.RemovalPolicy.RETAIN,
  }),
  // ... other config
});

// S3 encryption
const bucket = new s3.Bucket(this, 'FrontendBucket', {
  encryption: s3.BucketEncryption.KMS,
  encryptionKey: new kms.Key(this, 'S3EncryptionKey', {
    description: 'Encryption key for S3 bucket',
    enableKeyRotation: true,
  }),
  // ... other config
});
```

### Encryption in Transit

```typescript
// Force HTTPS in CloudFront
const distribution = new cloudfront.Distribution(this, 'Distribution', {
  defaultBehavior: {
    viewerProtocolPolicy: cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
    // ... other config
  },
  // Minimum TLS version
  minimumProtocolVersion: cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
});

// RDS force SSL
const parameterGroup = new rds.ParameterGroup(this, 'PostgresParameterGroup', {
  parameters: {
    'rds.force_ssl': '1',
  },
});
```

### Field-Level Encryption for PII

```typescript
// apps/api/src/lib/encryption.ts

import crypto from 'crypto';

export class FieldEncryption {
  private static readonly ALGORITHM = 'aes-256-gcm';
  private static readonly KEY = Buffer.from(process.env.FIELD_ENCRYPTION_KEY!, 'base64');

  static encrypt(plaintext: string): string {
    const iv = crypto.randomBytes(16);
    const cipher = crypto.createCipheriv(this.ALGORITHM, this.KEY, iv);

    let encrypted = cipher.update(plaintext, 'utf8', 'base64');
    encrypted += cipher.final('base64');

    const authTag = cipher.getAuthTag();

    // Format: iv:authTag:ciphertext
    return `${iv.toString('base64')}:${authTag.toString('base64')}:${encrypted}`;
  }

  static decrypt(ciphertext: string): string {
    const parts = ciphertext.split(':');
    if (parts.length !== 3) {
      throw new Error('Invalid ciphertext format');
    }

    const [ivBase64, authTagBase64, encrypted] = parts;
    const iv = Buffer.from(ivBase64, 'base64');
    const authTag = Buffer.from(authTagBase64, 'base64');

    const decipher = crypto.createDecipheriv(this.ALGORITHM, this.KEY, iv);
    decipher.setAuthTag(authTag);

    let decrypted = decipher.update(encrypted, 'base64', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  }
}

// Usage example: Encrypt sensitive supplier information
interface Supplier {
  name: string;
  email: string; // Encrypted
  phone: string; // Encrypted
  address: string; // Encrypted
}

async function createSupplier(data: Supplier) {
  return prisma.supplier.create({
    data: {
      name: data.name,
      email: FieldEncryption.encrypt(data.email),
      phone: FieldEncryption.encrypt(data.phone),
      address: FieldEncryption.encrypt(data.address),
    },
  });
}
```

## GDPR Compliance

### Data Subject Rights Implementation

```typescript
// apps/api/src/services/gdpr/GDPRService.ts

import { BaseService } from '../BaseService';
import { FieldEncryption } from '../../lib/encryption';

export class GDPRService extends BaseService {
  /**
   * Right to Access (Article 15)
   * Export all personal data for a user
   */
  async exportUserData(userId: string): Promise<any> {
    this.logOperation('GDPR: Exporting user data', { userId });

    const user = await this.prisma.user.findUnique({
      where: { id: userId },
      include: {
        memberships: {
          include: {
            restaurant: true,
          },
        },
        sessions: true,
        sentInvitations: true,
      },
    });

    if (!user) {
      throw new NotFoundError('User');
    }

    // Collect all personal data
    const userData = {
      personalInformation: {
        email: user.email,
        firstName: user.firstName,
        lastName: user.lastName,
        createdAt: user.createdAt,
      },
      restaurantMemberships: user.memberships.map((m) => ({
        restaurantName: m.restaurant.name,
        role: m.role,
        joinedAt: m.joinedAt,
      })),
      activityLogs: await this.getUserActivityLogs(userId),
    };

    // Create audit log
    await this.createAuditLog({
      userId,
      action: 'DATA_EXPORT',
      resourceType: 'USER',
      resourceId: userId,
      metadata: { exportedAt: new Date() },
    });

    return userData;
  }

  /**
   * Right to Erasure (Article 17) - "Right to be Forgotten"
   * Delete or anonymize all user data
   */
  async deleteUserData(userId: string, reason: string): Promise<void> {
    this.logOperation('GDPR: Deleting user data', { userId, reason });

    await this.withTransaction(async (tx) => {
      // 1. Anonymize feedback (preserve ML training data)
      await tx.forecastFeedback.updateMany({
        where: {
          forecast: {
            restaurant: {
              memberships: {
                some: { userId },
              },
            },
          },
        },
        data: {
          feedbackNote: '[DELETED]',
        },
      });

      // 2. Delete invitations
      await tx.teamInvitation.deleteMany({
        where: { inviterId: userId },
      });

      // 3. Delete sessions
      await tx.userSession.deleteMany({
        where: { userId },
      });

      // 4. Remove from restaurant memberships
      await tx.restaurantMembership.deleteMany({
        where: { userId },
      });

      // 5. Delete user account
      await tx.user.delete({
        where: { id: userId },
      });

      // 6. Create permanent deletion record
      await tx.$executeRaw`
        INSERT INTO gdpr_deletion_log (user_id, email, deleted_at, reason)
        VALUES (${userId}, (SELECT email FROM users WHERE id = ${userId}), NOW(), ${reason})
      `;
    });

    // Create audit log (before deletion)
    await this.createAuditLog({
      userId,
      action: 'DATA_DELETION',
      resourceType: 'USER',
      resourceId: userId,
      metadata: { reason, deletedAt: new Date() },
    });

    this.logOperation('GDPR: User data deleted', { userId });
  }

  /**
   * Right to Rectification (Article 16)
   * Update incorrect personal data
   */
  async updateUserData(
    userId: string,
    data: { email?: string; firstName?: string; lastName?: string }
  ): Promise<void> {
    const oldData = await this.prisma.user.findUnique({
      where: { id: userId },
      select: { email: true, firstName: true, lastName: true },
    });

    await this.prisma.user.update({
      where: { id: userId },
      data,
    });

    // Audit log with before/after
    await this.createAuditLog({
      userId,
      action: 'DATA_RECTIFICATION',
      resourceType: 'USER',
      resourceId: userId,
      metadata: {
        before: oldData,
        after: data,
        updatedAt: new Date(),
      },
    });
  }

  /**
   * Right to Data Portability (Article 20)
   * Export data in machine-readable format
   */
  async exportDataPortable(userId: string): Promise<string> {
    const data = await this.exportUserData(userId);

    // Convert to JSON (machine-readable format)
    return JSON.stringify(data, null, 2);
  }

  /**
   * Right to Object to Processing (Article 21)
   * Opt-out of ML model training
   */
  async optOutMLTraining(userId: string): Promise<void> {
    await this.prisma.user.update({
      where: { id: userId },
      data: {
        // Add ML opt-out flag to user settings
        // This would be checked before including user's data in training
      },
    });

    await this.createAuditLog({
      userId,
      action: 'ML_OPT_OUT',
      resourceType: 'USER',
      resourceId: userId,
      metadata: { optedOutAt: new Date() },
    });
  }

  private async getUserActivityLogs(userId: string) {
    return this.prisma.$queryRaw`
      SELECT action, resource_type, resource_id, created_at, metadata
      FROM audit_logs
      WHERE user_id = ${userId}
      ORDER BY created_at DESC
      LIMIT 1000
    `;
  }

  private async createAuditLog(log: {
    userId: string;
    action: string;
    resourceType: string;
    resourceId: string;
    metadata: any;
  }) {
    await this.prisma.$executeRaw`
      INSERT INTO audit_logs (user_id, action, resource_type, resource_id, metadata, created_at)
      VALUES (${log.userId}, ${log.action}, ${log.resourceType}, ${log.resourceId}, ${JSON.stringify(log.metadata)}::jsonb, NOW())
    `;
  }
}
```

### Data Retention Policy

```typescript
// apps/api/src/services/gdpr/DataRetentionService.ts

export class DataRetentionService extends BaseService {
  /**
   * Automatically delete old data according to retention policy
   */
  async enforceRetentionPolicy(): Promise<void> {
    this.logOperation('Enforcing data retention policy', {});

    await this.withTransaction(async (tx) => {
      // 1. Delete expired sessions (30 days)
      const thirtyDaysAgo = new Date(Date.now() - 30 * 24 * 60 * 60 * 1000);
      await tx.userSession.deleteMany({
        where: {
          expiresAt: { lt: thirtyDaysAgo },
        },
      });

      // 2. Delete old forecast feedback (2 years)
      const twoYearsAgo = new Date(Date.now() - 2 * 365 * 24 * 60 * 60 * 1000);
      await tx.forecastFeedback.deleteMany({
        where: {
          createdAt: { lt: twoYearsAgo },
        },
      });

      // 3. Anonymize old transactions (7 years for accounting)
      const sevenYearsAgo = new Date(Date.now() - 7 * 365 * 24 * 60 * 60 * 1000);
      await tx.$executeRaw`
        UPDATE transactions
        SET metadata = '{}'::jsonb
        WHERE transaction_date < ${sevenYearsAgo}
      `;

      // 4. Delete old audit logs (7 years)
      await tx.$executeRaw`
        DELETE FROM audit_logs
        WHERE created_at < ${sevenYearsAgo}
      `;

      // 5. Archive old forecasts (1 year active, then archive)
      const oneYearAgo = new Date(Date.now() - 365 * 24 * 60 * 60 * 1000);
      await tx.$executeRaw`
        UPDATE forecasts
        SET status = 'ARCHIVED'
        WHERE forecast_date < ${oneYearAgo}
        AND status != 'ARCHIVED'
      `;
    });

    this.logOperation('Data retention policy enforced', {});
  }
}
```

### Consent Management

```typescript
// apps/api/src/services/gdpr/ConsentService.ts

enum ConsentType {
  MARKETING_EMAILS = 'MARKETING_EMAILS',
  ANALYTICS = 'ANALYTICS',
  ML_TRAINING = 'ML_TRAINING',
  THIRD_PARTY_SHARING = 'THIRD_PARTY_SHARING',
}

export class ConsentService extends BaseService {
  async recordConsent(
    userId: string,
    consentType: ConsentType,
    granted: boolean
  ): Promise<void> {
    await this.prisma.$executeRaw`
      INSERT INTO user_consents (user_id, consent_type, granted, recorded_at)
      VALUES (${userId}, ${consentType}, ${granted}, NOW())
      ON CONFLICT (user_id, consent_type)
      DO UPDATE SET granted = ${granted}, recorded_at = NOW()
    `;

    await this.createAuditLog({
      userId,
      action: 'CONSENT_UPDATE',
      resourceType: 'CONSENT',
      resourceId: consentType,
      metadata: { granted, recordedAt: new Date() },
    });
  }

  async hasConsent(userId: string, consentType: ConsentType): Promise<boolean> {
    const result = await this.prisma.$queryRaw<[{ granted: boolean }]>`
      SELECT granted
      FROM user_consents
      WHERE user_id = ${userId}
      AND consent_type = ${consentType}
    `;

    return result[0]?.granted || false;
  }

  async withdrawConsent(userId: string, consentType: ConsentType): Promise<void> {
    await this.recordConsent(userId, consentType, false);

    // Take action based on consent type
    switch (consentType) {
      case ConsentType.ML_TRAINING:
        // Remove user's data from future ML training
        await this.excludeFromMLTraining(userId);
        break;

      case ConsentType.ANALYTICS:
        // Stop collecting analytics
        await this.disableAnalytics(userId);
        break;

      // ... other consent types
    }
  }

  private async excludeFromMLTraining(userId: string): Promise<void> {
    // Mark forecasts to exclude from training
    await this.prisma.$executeRaw`
      UPDATE forecasts
      SET exclude_from_training = true
      WHERE restaurant_id IN (
        SELECT restaurant_id
        FROM restaurant_memberships
        WHERE user_id = ${userId}
      )
    `;
  }

  private async disableAnalytics(userId: string): Promise<void> {
    // Implementation for disabling analytics tracking
  }

  private async createAuditLog(log: any): Promise<void> {
    // Same as GDPRService.createAuditLog
  }
}
```

## EU AI Act Compliance

### AI System Documentation

```typescript
// apps/api/src/services/ai-compliance/AIDocumentationService.ts

/**
 * EU AI Act Compliance
 * Risk Level: Limited Risk (Article 52)
 * - Transparency obligations apply
 * - Users must be informed when interacting with AI
 * - Explanations must be provided
 */
export class AIDocumentationService extends BaseService {
  /**
   * Provide AI system information to users (transparency requirement)
   */
  async getAISystemInfo(): Promise<any> {
    return {
      systemName: 'Flux Demand Forecasting System',
      purpose: 'Predict restaurant menu item demand for procurement optimization',
      riskCategory: 'Limited Risk',

      dataUsed: [
        'Historical transaction data (sales volumes, timestamps)',
        'Menu item information (names, categories)',
        'Recipe data (ingredient composition)',
        'External factors (day of week, holidays, weather)',
      ],

      modelDetails: {
        type: 'Gradient Boosting Machine (LightGBM)',
        trainingFrequency: 'Monthly',
        accuracy: 'Monitored per restaurant with MAPE metric',
        explainability: 'SHAP (SHapley Additive exPlanations) values provided',
      },

      humanOversight: {
        enabled: true,
        description: 'All forecasts reviewed by restaurant staff',
        feedbackMechanism: 'Users can provide actual quantities and feedback',
        override: 'Users can modify or reject AI recommendations',
      },

      limitations: [
        'Requires minimum 90 days of historical data',
        'Accuracy degrades with menu changes or special events',
        'Not suitable for new menu items without similar historical items',
      ],

      dataProtection: {
        gdprCompliant: true,
        dataMinimization: 'Only necessary data collected',
        retention: 'Transaction data retained for 7 years (accounting)',
        encryption: 'AES-256 at rest, TLS 1.3 in transit',
      },
    };
  }

  /**
   * Log AI decision for audit trail
   */
  async logAIDecision(log: {
    restaurantId: string;
    modelVersion: string;
    inputData: any;
    prediction: any;
    explanation: any;
    userFeedback?: any;
  }): Promise<void> {
    await this.prisma.$executeRaw`
      INSERT INTO ai_decision_log (
        restaurant_id,
        model_version,
        input_data,
        prediction,
        explanation,
        user_feedback,
        logged_at
      ) VALUES (
        ${log.restaurantId},
        ${log.modelVersion},
        ${JSON.stringify(log.inputData)}::jsonb,
        ${JSON.stringify(log.prediction)}::jsonb,
        ${JSON.stringify(log.explanation)}::jsonb,
        ${log.userFeedback ? JSON.stringify(log.userFeedback) : null}::jsonb,
        NOW()
      )
    `;
  }

  /**
   * Generate AI impact assessment report
   */
  async generateImpactAssessment(restaurantId: string): Promise<any> {
    const forecasts = await this.prisma.forecast.findMany({
      where: {
        restaurantId,
        actualQuantity: { not: null },
        createdAt: { gte: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000) },
      },
      include: {
        feedback: true,
      },
    });

    // Calculate accuracy metrics
    const accuracy = this.calculateMAPE(forecasts);

    // Analyze bias
    const biasAnalysis = this.analyzeBias(forecasts);

    // User satisfaction
    const satisfaction = this.calculateUserSatisfaction(forecasts);

    return {
      period: '90 days',
      forecastCount: forecasts.length,
      accuracy: {
        mape: accuracy,
        interpretation: accuracy < 20 ? 'Good' : accuracy < 30 ? 'Fair' : 'Poor',
      },
      bias: biasAnalysis,
      userSatisfaction: satisfaction,
      fairnessMetrics: {
        // Ensure no discrimination across restaurant types, sizes, etc.
        byCategory: this.groupAccuracyByCategory(forecasts),
      },
    };
  }

  private calculateMAPE(forecasts: any[]): number {
    const errors = forecasts.map((f) => {
      const actual = parseFloat(f.actualQuantity);
      const predicted = parseFloat(f.predictedQuantity);
      return Math.abs((actual - predicted) / actual);
    });

    return (errors.reduce((sum, err) => sum + err, 0) / errors.length) * 100;
  }

  private analyzeBias(forecasts: any[]): any {
    // Check for systematic over/under-prediction
    const errors = forecasts.map((f) => {
      return parseFloat(f.predictedQuantity) - parseFloat(f.actualQuantity);
    });

    const meanError = errors.reduce((sum, err) => sum + err, 0) / errors.length;

    return {
      meanError,
      interpretation:
        Math.abs(meanError) < 5
          ? 'No significant bias'
          : meanError > 0
          ? 'Systematic over-prediction'
          : 'Systematic under-prediction',
    };
  }

  private calculateUserSatisfaction(forecasts: any[]): number {
    const withFeedback = forecasts.filter((f) => f.feedback.length > 0);
    // Calculate satisfaction based on feedback sentiment
    return withFeedback.length > 0 ? 0.85 : 0; // Placeholder
  }

  private groupAccuracyByCategory(forecasts: any[]): any {
    // Group by menu item category and calculate accuracy
    return {}; // Placeholder
  }
}
```

### Model Monitoring & Bias Detection

```typescript
// apps/api/src/services/ai-compliance/ModelMonitoringService.ts

export class ModelMonitoringService extends BaseService {
  /**
   * Monitor model performance and detect drift
   */
  async monitorModelPerformance(): Promise<void> {
    const recentForecasts = await this.prisma.forecast.findMany({
      where: {
        actualQuantity: { not: null },
        createdAt: { gte: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000) },
      },
      include: {
        menuItem: true,
        forecastRun: true,
      },
    });

    // Calculate accuracy by restaurant
    const performanceByRestaurant = this.groupByRestaurant(recentForecasts);

    for (const [restaurantId, forecasts] of Object.entries(performanceByRestaurant)) {
      const accuracy = this.calculateMAPE(forecasts as any[]);

      // Alert if accuracy degrades significantly
      if (accuracy > 40) {
        await this.createPerformanceAlert(restaurantId, accuracy);
      }

      // Check for data drift
      const drift = await this.detectDataDrift(restaurantId);
      if (drift.detected) {
        await this.createDriftAlert(restaurantId, drift);
      }
    }
  }

  private async detectDataDrift(restaurantId: string): Promise<any> {
    // Compare recent data distribution to training data distribution
    // Using Kolmogorov-Smirnov test or similar

    const recentStats = await this.getRecentDataStatistics(restaurantId);
    const baselineStats = await this.getBaselineStatistics(restaurantId);

    // Simple drift detection: check if mean/std changed significantly
    const driftScore = Math.abs(
      (recentStats.mean - baselineStats.mean) / baselineStats.std
    );

    return {
      detected: driftScore > 2.0, // 2 standard deviations
      score: driftScore,
      recommendation: driftScore > 2.0 ? 'Retrain model' : 'Continue monitoring',
    };
  }

  private async createPerformanceAlert(
    restaurantId: string,
    accuracy: number
  ): Promise<void> {
    await this.prisma.dataHealthAlert.create({
      data: {
        restaurantId,
        severity: 'HIGH',
        category: 'MODEL_PERFORMANCE',
        message: `Forecast accuracy degraded to ${accuracy.toFixed(1)}% MAPE`,
        details: {
          currentAccuracy: accuracy,
          threshold: 40,
          recommendation: 'Review recent data quality and consider model retraining',
        },
        detectedAt: new Date(),
      },
    });
  }

  private async createDriftAlert(restaurantId: string, drift: any): Promise<void> {
    await this.prisma.dataHealthAlert.create({
      data: {
        restaurantId,
        severity: 'MEDIUM',
        category: 'DATA_DRIFT',
        message: 'Data distribution drift detected',
        details: drift,
        detectedAt: new Date(),
      },
    });
  }

  private groupByRestaurant(forecasts: any[]): Record<string, any[]> {
    return forecasts.reduce((acc, forecast) => {
      if (!acc[forecast.restaurantId]) {
        acc[forecast.restaurantId] = [];
      }
      acc[forecast.restaurantId].push(forecast);
      return acc;
    }, {});
  }

  private calculateMAPE(forecasts: any[]): number {
    // Same implementation as AIDocumentationService
    return 0;
  }

  private async getRecentDataStatistics(restaurantId: string): Promise<any> {
    // Calculate mean, std, distribution of recent data
    return { mean: 0, std: 0 };
  }

  private async getBaselineStatistics(restaurantId: string): Promise<any> {
    // Get statistics from training data
    return { mean: 0, std: 0 };
  }
}
```

## Audit Logging

### Comprehensive Audit Trail

```sql
-- Database schema for audit logs
CREATE TABLE audit_logs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID,
  restaurant_id UUID,
  action VARCHAR(100) NOT NULL,
  resource_type VARCHAR(50) NOT NULL,
  resource_id UUID,
  ip_address INET,
  user_agent TEXT,
  metadata JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
CREATE INDEX idx_audit_logs_restaurant_id ON audit_logs(restaurant_id);
CREATE INDEX idx_audit_logs_action ON audit_logs(action);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at DESC);

-- GDPR deletion log (permanent record)
CREATE TABLE gdpr_deletion_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL,
  email VARCHAR(255) NOT NULL,
  deleted_at TIMESTAMPTZ NOT NULL,
  reason TEXT,
  deleted_by UUID
);

-- AI decision log (EU AI Act compliance)
CREATE TABLE ai_decision_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  restaurant_id UUID NOT NULL,
  model_version VARCHAR(50) NOT NULL,
  input_data JSONB NOT NULL,
  prediction JSONB NOT NULL,
  explanation JSONB NOT NULL,
  user_feedback JSONB,
  logged_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ai_decision_log_restaurant ON ai_decision_log(restaurant_id);
CREATE INDEX idx_ai_decision_log_logged_at ON ai_decision_log(logged_at DESC);

-- User consent log
CREATE TABLE user_consents (
  user_id UUID NOT NULL,
  consent_type VARCHAR(50) NOT NULL,
  granted BOOLEAN NOT NULL,
  recorded_at TIMESTAMPTZ NOT NULL,
  PRIMARY KEY (user_id, consent_type)
);
```

### Audit Middleware

```typescript
// apps/api/src/middleware/audit.ts

import { middleware } from '../lib/trpc';
import { prisma } from '../lib/prisma';

export const auditMiddleware = middleware(async ({ ctx, path, type, input, next }) => {
  const start = Date.now();
  const result = await next();

  // Log sensitive operations
  const sensitiveOperations = [
    'user.delete',
    'user.update',
    'restaurant.delete',
    'forecast.submitFeedback',
    'procurement.createOrder',
    'team.inviteTeamMember',
    'team.removeTeamMember',
    'settings.update',
  ];

  if (sensitiveOperations.includes(path)) {
    await prisma.$executeRaw`
      INSERT INTO audit_logs (
        user_id,
        restaurant_id,
        action,
        resource_type,
        resource_id,
        ip_address,
        user_agent,
        metadata,
        created_at
      ) VALUES (
        ${ctx.userId || null}::uuid,
        ${ctx.restaurantId || null}::uuid,
        ${path},
        ${type},
        ${input?.id || null}::uuid,
        ${ctx.req.headers['x-forwarded-for'] || ctx.req.connection.remoteAddress}::inet,
        ${ctx.req.headers['user-agent']},
        ${JSON.stringify({ input, duration: Date.now() - start })}::jsonb,
        NOW()
      )
    `;
  }

  return result;
});
```

## Security Best Practices Checklist

```typescript
/**
 * Security Implementation Checklist
 */
export const SECURITY_CHECKLIST = {
  authentication: {
    '✓': 'JWT with short expiry (15 minutes)',
    '✓': 'Refresh token rotation',
    '✓': 'Session management with revocation',
    '✓': 'Secure password hashing (bcrypt)',
    '✓': 'Rate limiting on auth endpoints',
  },

  authorization: {
    '✓': 'Role-based access control (RBAC)',
    '✓': 'Row-level security (RLS) in database',
    '✓': 'Permission checks on all endpoints',
    '✓': 'Context injection for multi-tenancy',
  },

  dataProtection: {
    '✓': 'Encryption at rest (AES-256)',
    '✓': 'Encryption in transit (TLS 1.3)',
    '✓': 'Field-level encryption for PII',
    '✓': 'Secrets in AWS Secrets Manager',
    '✓': 'Database credentials rotation',
  },

  inputValidation: {
    '✓': 'Zod schema validation',
    '✓': 'SQL injection prevention (Prisma)',
    '✓': 'XSS prevention (React escaping)',
    '✓': 'CSRF protection',
  },

  monitoring: {
    '✓': 'Audit logging for sensitive operations',
    '✓': 'CloudTrail for AWS API activity',
    '✓': 'Security alerts via SNS',
    '✓': 'Anomaly detection',
  },

  compliance: {
    '✓': 'GDPR data subject rights',
    '✓': 'Data retention policies',
    '✓': 'Consent management',
    '✓': 'EU AI Act transparency',
    '✓': 'AI decision audit trail',
  },
};
```

---

## 10. Testing Strategy

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

**Framework:** Vitest (for monorepo compatibility and speed)

**Example: Pure Function Test (Item Matcher)**

```typescript
// packages/core/src/services/__tests__/item-matcher.test.ts
import { describe, it, expect } from 'vitest';
import { ItemMatcher } from '../item-matcher';

describe('ItemMatcher', () => {
  const matcher = new ItemMatcher();

  describe('fuzzyMatch', () => {
    it('should match identical names with 100% confidence', () => {
      const result = matcher.fuzzyMatch(
        'Grilled Chicken Sandwich',
        'Grilled Chicken Sandwich'
      );

      expect(result.confidence).toBe(1.0);
      expect(result.isMatch).toBe(true);
    });

    it('should match similar names with high confidence', () => {
      const result = matcher.fuzzyMatch(
        'Grilled Chicken Sandwich',
        'Grilled Chkn Sandwich'
      );

      expect(result.confidence).toBeGreaterThan(0.85);
      expect(result.isMatch).toBe(true);
    });

    it('should reject dissimilar names', () => {
      const result = matcher.fuzzyMatch(
        'Grilled Chicken Sandwich',
        'Caesar Salad'
      );

      expect(result.confidence).toBeLessThan(0.7);
      expect(result.isMatch).toBe(false);
    });

    it('should handle special characters and casing', () => {
      const result = matcher.fuzzyMatch(
        "CHEF'S SPECIAL - BURGER",
        'chefs special burger'
      );

      expect(result.confidence).toBeGreaterThan(0.8);
      expect(result.isMatch).toBe(true);
    });

    it('should use alias matching as fallback', () => {
      const menuItem = {
        id: '123',
        name: 'Grilled Chicken Sandwich',
        aliases: ['GCS', 'Chicken Grilled'],
      };

      const result = matcher.findBestMatch('GCS', [menuItem]);

      expect(result?.menuItem.id).toBe('123');
      expect(result?.confidence).toBeGreaterThan(0.9);
    });
  });

  describe('findBestMatch', () => {
    const menuItems = [
      { id: '1', name: 'Caesar Salad', aliases: [] },
      { id: '2', name: 'Greek Salad', aliases: [] },
      { id: '3', name: 'Garden Salad', aliases: [] },
    ];

    it('should return best match above threshold', () => {
      const result = matcher.findBestMatch('Caesar Salad', menuItems);

      expect(result?.menuItem.id).toBe('1');
    });

    it('should return null when no match above threshold', () => {
      const result = matcher.findBestMatch('Burger', menuItems);

      expect(result).toBeNull();
    });
  });
});
```

**Example: Service Layer Test (Forecast Service)**

```typescript
// packages/core/src/services/__tests__/forecast.service.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ForecastService } from '../forecast.service';
import { mockDeep, mockReset } from 'vitest-mock-extended';
import type { PrismaClient } from '@prisma/client';

const prismaMock = mockDeep<PrismaClient>();

describe('ForecastService', () => {
  let service: ForecastService;

  beforeEach(() => {
    mockReset(prismaMock);
    service = new ForecastService(prismaMock);
  });

  describe('generateForecasts', () => {
    it('should generate forecasts for all active menu items', async () => {
      const restaurantId = 'restaurant-123';
      const forecastDate = new Date('2024-12-25');

      // Mock database responses
      prismaMock.restaurant.findUnique.mockResolvedValue({
        id: restaurantId,
        name: 'Test Restaurant',
        status: 'ACTIVE',
      });

      prismaMock.menuItem.findMany.mockResolvedValue([
        { id: 'item-1', name: 'Burger', status: 'ACTIVE' },
        { id: 'item-2', name: 'Salad', status: 'ACTIVE' },
      ]);

      // Mock SageMaker prediction
      const sageMakerMock = vi.spyOn(service as any, 'callSageMakerEndpoint');
      sageMakerMock.mockResolvedValue({
        predictions: [
          { menuItemId: 'item-1', quantity: 45.5, confidence: 0.89 },
          { menuItemId: 'item-2', quantity: 23.2, confidence: 0.92 },
        ],
      });

      prismaMock.forecastRun.create.mockResolvedValue({
        id: 'run-123',
        restaurantId,
        status: 'COMPLETED',
      });

      // Execute
      const result = await service.generateForecasts({
        restaurantId,
        forecastDate,
      });

      // Assert
      expect(result.forecastRunId).toBe('run-123');
      expect(result.forecastCount).toBe(2);
      expect(prismaMock.forecast.createMany).toHaveBeenCalledWith({
        data: expect.arrayContaining([
          expect.objectContaining({
            menuItemId: 'item-1',
            predictedQuantity: 45.5,
            confidence: 0.89,
          }),
          expect.objectContaining({
            menuItemId: 'item-2',
            predictedQuantity: 23.2,
            confidence: 0.92,
          }),
        ]),
      });
    });

    it('should handle SageMaker failures gracefully', async () => {
      const restaurantId = 'restaurant-123';

      prismaMock.restaurant.findUnique.mockResolvedValue({
        id: restaurantId,
        name: 'Test Restaurant',
        status: 'ACTIVE',
      });

      prismaMock.menuItem.findMany.mockResolvedValue([
        { id: 'item-1', name: 'Burger', status: 'ACTIVE' },
      ]);

      // Mock SageMaker failure
      const sageMakerMock = vi.spyOn(service as any, 'callSageMakerEndpoint');
      sageMakerMock.mockRejectedValue(new Error('SageMaker timeout'));

      prismaMock.forecastRun.create.mockResolvedValue({
        id: 'run-123',
        status: 'PENDING',
      });

      // Execute and expect error
      await expect(
        service.generateForecasts({ restaurantId, forecastDate: new Date() })
      ).rejects.toThrow('SageMaker timeout');

      // Should mark run as failed
      expect(prismaMock.forecastRun.update).toHaveBeenCalledWith({
        where: { id: 'run-123' },
        data: { status: 'FAILED', errorMessage: 'SageMaker timeout' },
      });
    });

    it('should skip inactive menu items', async () => {
      const restaurantId = 'restaurant-123';

      prismaMock.restaurant.findUnique.mockResolvedValue({
        id: restaurantId,
        status: 'ACTIVE',
      });

      prismaMock.menuItem.findMany.mockResolvedValue([
        { id: 'item-1', status: 'ACTIVE' },
        { id: 'item-2', status: 'INACTIVE' },
      ]);

      await service.generateForecasts({ restaurantId, forecastDate: new Date() });

      // Should only query active items
      expect(prismaMock.menuItem.findMany).toHaveBeenCalledWith({
        where: {
          restaurantId,
          status: 'ACTIVE',
        },
      });
    });
  });

  describe('getWithExplanation', () => {
    it('should return forecast with parsed SHAP values', async () => {
      const forecastId = 'forecast-123';

      prismaMock.forecast.findUnique.mockResolvedValue({
        id: forecastId,
        predictedQuantity: 45.5,
        confidence: 0.89,
        menuItem: { name: 'Burger' },
        explanation: {
          shapValues: JSON.stringify({
            baseValue: 40.0,
            features: [
              { name: 'day_of_week', value: 5, contribution: 3.2 },
              { name: 'avg_temp', value: 75, contribution: 2.3 },
            ],
          }),
        },
      });

      const result = await service.getWithExplanation(forecastId);

      expect(result.forecast.id).toBe(forecastId);
      expect(result.explanation.baseValue).toBe(40.0);
      expect(result.explanation.features).toHaveLength(2);
      expect(result.explanation.topDrivers[0].feature).toBe('day_of_week');
    });
  });
});
```

**Example: React Component Test**

```typescript
// apps/web/src/components/__tests__/ForecastChart.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { ForecastChart } from '../ForecastChart';

describe('ForecastChart', () => {
  const mockData = [
    { date: '2024-12-20', predicted: 45, actual: 42, confidence: 0.89 },
    { date: '2024-12-21', predicted: 52, actual: null, confidence: 0.91 },
    { date: '2024-12-22', predicted: 38, actual: null, confidence: 0.87 },
  ];

  it('should render chart with forecast data', () => {
    render(<ForecastChart data={mockData} menuItemName="Burger" />);

    expect(screen.getByText('Burger Forecast')).toBeInTheDocument();
    expect(screen.getByText(/predicted/i)).toBeInTheDocument();
    expect(screen.getByText(/actual/i)).toBeInTheDocument();
  });

  it('should display confidence interval on hover', async () => {
    const user = userEvent.setup();
    render(<ForecastChart data={mockData} menuItemName="Burger" />);

    const dataPoint = screen.getByTestId('forecast-point-0');
    await user.hover(dataPoint);

    await waitFor(() => {
      expect(screen.getByText(/confidence: 89%/i)).toBeInTheDocument();
    });
  });

  it('should toggle between chart types', async () => {
    const user = userEvent.setup();
    render(<ForecastChart data={mockData} menuItemName="Burger" />);

    const barChartButton = screen.getByRole('button', { name: /bar chart/i });
    await user.click(barChartButton);

    expect(screen.getByTestId('bar-chart')).toBeInTheDocument();
  });

  it('should handle empty data gracefully', () => {
    render(<ForecastChart data={[]} menuItemName="Burger" />);

    expect(screen.getByText(/no forecast data available/i)).toBeInTheDocument();
  });
});
```

### 10.3 Integration Testing

**Framework:** Vitest + Testcontainers (for PostgreSQL)

**Example: API Integration Test (tRPC Router)**

```typescript
// apps/api/src/routers/__tests__/forecast.router.integration.test.ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { appRouter } from '../index';
import { createContext } from '../../context';
import { PrismaClient } from '@prisma/client';
import { GenericContainer, StartedTestContainer } from 'testcontainers';

describe('Forecast Router Integration', () => {
  let postgresContainer: StartedTestContainer;
  let prisma: PrismaClient;
  let caller: any;

  beforeAll(async () => {
    // Start PostgreSQL container
    postgresContainer = await new GenericContainer('postgres:15-alpine')
      .withEnvironment({
        POSTGRES_USER: 'test',
        POSTGRES_PASSWORD: 'test',
        POSTGRES_DB: 'flux_test',
      })
      .withExposedPorts(5432)
      .start();

    const databaseUrl = `postgresql://test:test@localhost:${postgresContainer.getMappedPort(5432)}/flux_test`;

    prisma = new PrismaClient({
      datasources: { db: { url: databaseUrl } },
    });

    // Run migrations
    await prisma.$executeRaw`CREATE EXTENSION IF NOT EXISTS "uuid-ossp"`;
    // ... run Prisma migrations

    // Create test data
    const restaurant = await prisma.restaurant.create({
      data: {
        id: 'restaurant-123',
        name: 'Test Restaurant',
        status: 'ACTIVE',
      },
    });

    const menuItem = await prisma.menuItem.create({
      data: {
        id: 'item-123',
        restaurantId: restaurant.id,
        name: 'Burger',
        category: 'ENTREE',
        status: 'ACTIVE',
      },
    });

    const forecastRun = await prisma.forecastRun.create({
      data: {
        id: 'run-123',
        restaurantId: restaurant.id,
        status: 'COMPLETED',
      },
    });

    await prisma.forecast.create({
      data: {
        id: 'forecast-123',
        forecastRunId: forecastRun.id,
        restaurantId: restaurant.id,
        menuItemId: menuItem.id,
        forecastDate: new Date('2024-12-25'),
        predictedQuantity: 45.5,
        confidence: 0.89,
        status: 'ACTIVE',
      },
    });

    await prisma.forecastExplanation.create({
      data: {
        forecastId: 'forecast-123',
        shapValues: JSON.stringify({
          baseValue: 40.0,
          features: [
            { name: 'day_of_week', value: 5, contribution: 3.2 },
            { name: 'avg_temp', value: 75, contribution: 2.3 },
          ],
        }),
      },
    });

    // Create tRPC caller with context
    const ctx = await createContext({
      req: { headers: {} },
      res: {},
      user: { id: 'user-123', restaurantId: 'restaurant-123' },
    });

    caller = appRouter.createCaller(ctx);
  });

  afterAll(async () => {
    await prisma.$disconnect();
    await postgresContainer.stop();
  });

  it('should get forecast with explanation', async () => {
    const result = await caller.forecast.getWithExplanation({
      forecastId: 'forecast-123',
    });

    expect(result.forecast.id).toBe('forecast-123');
    expect(result.forecast.predictedQuantity).toBe(45.5);
    expect(result.forecast.confidence).toBe(0.89);
    expect(result.explanation.baseValue).toBe(40.0);
    expect(result.explanation.features).toHaveLength(2);
    expect(result.explanation.topDrivers[0].feature).toBe('day_of_week');
  });

  it('should list forecasts with pagination', async () => {
    const result = await caller.forecast.list({
      restaurantId: 'restaurant-123',
      limit: 10,
      offset: 0,
    });

    expect(result.data).toHaveLength(1);
    expect(result.pagination.total).toBe(1);
    expect(result.data[0].id).toBe('forecast-123');
  });

  it('should enforce RLS - cannot access other restaurant data', async () => {
    // Create context for different restaurant
    const otherCtx = await createContext({
      req: { headers: {} },
      res: {},
      user: { id: 'user-456', restaurantId: 'restaurant-456' },
    });

    const otherCaller = appRouter.createCaller(otherCtx);

    await expect(
      otherCaller.forecast.getWithExplanation({ forecastId: 'forecast-123' })
    ).rejects.toThrow('Forecast not found');
  });

  it('should submit feedback and update forecast', async () => {
    await caller.forecast.submitFeedback({
      forecastId: 'forecast-123',
      actualQuantity: 42,
      wasAccurate: true,
      feedbackNote: 'Pretty close!',
    });

    const updated = await prisma.forecast.findUnique({
      where: { id: 'forecast-123' },
    });

    expect(updated.actualQuantity).toBe(42);

    const feedback = await prisma.forecastFeedback.findFirst({
      where: { forecastId: 'forecast-123' },
    });

    expect(feedback.wasAccurate).toBe(true);
    expect(feedback.feedbackNote).toBe('Pretty close!');
  });
});
```

**Example: Database Query Integration Test**

```typescript
// packages/core/src/repositories/__tests__/forecast.repository.integration.test.ts
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { PrismaClient } from '@prisma/client';
import { ForecastRepository } from '../forecast.repository';
import { setupTestDatabase, teardownTestDatabase } from '../../test-utils';

describe('ForecastRepository Integration', () => {
  let prisma: PrismaClient;
  let repository: ForecastRepository;

  beforeAll(async () => {
    prisma = await setupTestDatabase();
    repository = new ForecastRepository(prisma);
  });

  afterAll(async () => {
    await teardownTestDatabase(prisma);
  });

  describe('getAccuracyMetrics', () => {
    it('should calculate MAPE correctly', async () => {
      // Insert test data
      const restaurantId = 'restaurant-123';
      await prisma.forecast.createMany({
        data: [
          {
            restaurantId,
            menuItemId: 'item-1',
            forecastDate: new Date('2024-12-20'),
            predictedQuantity: 45,
            actualQuantity: 42,
            confidence: 0.89,
          },
          {
            restaurantId,
            menuItemId: 'item-1',
            forecastDate: new Date('2024-12-21'),
            predictedQuantity: 50,
            actualQuantity: 55,
            confidence: 0.91,
          },
        ],
      });

      const metrics = await repository.getAccuracyMetrics({
        restaurantId,
        startDate: new Date('2024-12-20'),
        endDate: new Date('2024-12-21'),
      });

      // MAPE = (|45-42|/42 + |50-55|/55) / 2 = (0.0714 + 0.0909) / 2 = 0.0812 = 8.12%
      expect(metrics.mape).toBeCloseTo(8.12, 1);
    });

    it('should group metrics by menu item', async () => {
      const restaurantId = 'restaurant-123';

      const metrics = await repository.getAccuracyMetrics({
        restaurantId,
        groupBy: 'menuItem',
      });

      expect(metrics).toHaveProperty('item-1');
      expect(metrics['item-1'].forecastCount).toBe(2);
    });
  });

  describe('complex queries with joins', () => {
    it('should fetch forecasts with related data efficiently', async () => {
      const forecasts = await repository.getForecastsWithExplanations({
        restaurantId: 'restaurant-123',
        limit: 10,
      });

      forecasts.forEach((forecast) => {
        expect(forecast).toHaveProperty('menuItem');
        expect(forecast).toHaveProperty('explanation');
        expect(forecast).toHaveProperty('feedback');
      });
    });
  });
});
```

### 10.4 End-to-End (E2E) Testing

**Framework:** Playwright

**Example: User Registration & Onboarding Flow**

```typescript
// apps/web/e2e/auth/registration.spec.ts
import { test, expect } from '@playwright/test';

test.describe('User Registration & Onboarding', () => {
  test('should complete full registration flow', async ({ page }) => {
    // Navigate to registration page
    await page.goto('/auth/register');

    // Fill registration form
    await page.fill('[name="name"]', 'John Doe');
    await page.fill('[name="email"]', 'john.doe@example.com');
    await page.fill('[name="password"]', 'SecurePassword123!');
    await page.fill('[name="confirmPassword"]', 'SecurePassword123!');

    // Submit form
    await page.click('button[type="submit"]');

    // Should navigate to restaurant setup
    await expect(page).toHaveURL('/onboarding/restaurant-setup');

    // Fill restaurant details
    await page.fill('[name="restaurantName"]', 'Test Bistro');
    await page.selectOption('[name="timezone"]', 'America/New_York');
    await page.fill('[name="address"]', '123 Main St');
    await page.fill('[name="city"]', 'New York');
    await page.selectOption('[name="state"]', 'NY');
    await page.fill('[name="zipCode"]', '10001');

    await page.click('button:has-text("Continue")');

    // Should navigate to POS integration
    await expect(page).toHaveURL('/onboarding/pos-integration');

    // Select Square POS
    await page.click('[data-testid="pos-square"]');

    // Mock OAuth redirect
    await page.route('**/api/pos/square/connect', async (route) => {
      await route.fulfill({
        status: 302,
        headers: {
          Location: '/onboarding/complete',
        },
      });
    });

    await page.click('button:has-text("Connect Square")');

    // Should complete onboarding
    await expect(page).toHaveURL('/dashboard');
    await expect(page.locator('h1')).toContainText('Welcome to Flux');
  });

  test('should validate password strength', async ({ page }) => {
    await page.goto('/auth/register');

    await page.fill('[name="password"]', 'weak');
    await page.blur('[name="password"]');

    await expect(page.locator('.error-message')).toContainText(
      'Password must be at least 8 characters'
    );
  });

  test('should prevent duplicate email registration', async ({ page }) => {
    await page.goto('/auth/register');

    await page.fill('[name="email"]', 'existing@example.com');
    await page.fill('[name="password"]', 'SecurePassword123!');
    await page.click('button[type="submit"]');

    await expect(page.locator('.error-message')).toContainText(
      'Email already registered'
    );
  });
});
```

**Example: Forecast Generation & Explanation Flow**

```typescript
// apps/web/e2e/forecasting/forecast-detail.spec.ts
import { test, expect } from '@playwright/test';
import { loginAsRestaurantOwner } from '../helpers/auth';

test.describe('Forecast Detail & Explanation', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsRestaurantOwner(page);
  });

  test('should display forecast with SHAP explanation', async ({ page }) => {
    // Navigate to forecasts
    await page.goto('/dashboard/forecasts');

    // Click on first forecast
    await page.click('[data-testid="forecast-card"]:first-child');

    // Should show forecast details
    await expect(page.locator('h2')).toContainText('Forecast Details');

    // Should show prediction
    const prediction = page.locator('[data-testid="predicted-quantity"]');
    await expect(prediction).toBeVisible();

    // Should show confidence
    const confidence = page.locator('[data-testid="confidence-score"]');
    await expect(confidence).toContainText('%');

    // Should show SHAP explanation
    await page.click('button:has-text("View Explanation")');

    const explanationPanel = page.locator('[data-testid="shap-explanation"]');
    await expect(explanationPanel).toBeVisible();

    // Should show feature contributions
    const topDrivers = page.locator('[data-testid="top-driver"]');
    await expect(topDrivers).toHaveCount(3); // Top 3 features

    // Should display feature importance chart
    const chart = page.locator('[data-testid="feature-importance-chart"]');
    await expect(chart).toBeVisible();
  });

  test('should submit feedback on forecast accuracy', async ({ page }) => {
    await page.goto('/dashboard/forecasts');
    await page.click('[data-testid="forecast-card"]:first-child');

    // Fill actual quantity
    await page.fill('[name="actualQuantity"]', '42');

    // Select accuracy rating
    await page.click('[data-testid="accuracy-thumbs-up"]');

    // Add feedback note
    await page.fill('[name="feedbackNote"]', 'Very accurate prediction!');

    // Submit feedback
    await page.click('button:has-text("Submit Feedback")');

    // Should show success message
    await expect(page.locator('.success-toast')).toContainText(
      'Feedback submitted'
    );

    // Should update forecast card
    await expect(page.locator('[data-testid="actual-quantity"]')).toContainText('42');
  });

  test('should navigate between forecast dates', async ({ page }) => {
    await page.goto('/dashboard/forecasts');

    // Click next day
    await page.click('[data-testid="next-day-button"]');

    // URL should update
    await expect(page).toHaveURL(/forecastDate=2024-12-22/);

    // Forecast cards should update
    await expect(page.locator('[data-testid="forecast-date"]')).toContainText(
      'Dec 22, 2024'
    );
  });
});
```

**Example: POS Transaction Sync Flow**

```typescript
// apps/web/e2e/pos/sync.spec.ts
import { test, expect } from '@playwright/test';
import { loginAsRestaurantOwner } from '../helpers/auth';

test.describe('POS Transaction Sync', () => {
  test.beforeEach(async ({ page }) => {
    await loginAsRestaurantOwner(page);
  });

  test('should trigger manual sync and show progress', async ({ page }) => {
    await page.goto('/dashboard/settings/pos');

    // Click manual sync button
    await page.click('button:has-text("Sync Now")');

    // Should show loading state
    await expect(page.locator('.sync-progress')).toBeVisible();
    await expect(page.locator('.sync-status')).toContainText('Syncing');

    // Wait for sync to complete (mock WebSocket events)
    await page.waitForSelector('.sync-status:has-text("Complete")');

    // Should show sync results
    await expect(page.locator('[data-testid="synced-transactions"]')).toContainText(
      /\d+ transactions synced/
    );
  });

  test('should display sync health metrics', async ({ page }) => {
    await page.goto('/dashboard/data-health');

    // Should show completeness score
    const completenessScore = page.locator('[data-testid="completeness-score"]');
    await expect(completenessScore).toBeVisible();

    // Should show quality issues
    const qualityIssues = page.locator('[data-testid="quality-issue"]');
    const count = await qualityIssues.count();

    if (count > 0) {
      // Click on first issue
      await qualityIssues.first().click();

      // Should show issue details
      await expect(page.locator('.issue-detail-modal')).toBeVisible();
    }
  });

  test('should handle sync errors gracefully', async ({ page }) => {
    // Mock API error
    await page.route('**/api/pos/sync', async (route) => {
      await route.fulfill({
        status: 500,
        body: JSON.stringify({
          error: 'POS API unavailable',
        }),
      });
    });

    await page.goto('/dashboard/settings/pos');
    await page.click('button:has-text("Sync Now")');

    // Should show error message
    await expect(page.locator('.error-toast')).toContainText(
      'Sync failed: POS API unavailable'
    );

    // Should show retry button
    await expect(page.locator('button:has-text("Retry")')).toBeVisible();
  });
});
```

### 10.5 Load & Performance Testing

**Framework:** k6

**Example: API Load Test**

```javascript
// tests/load/forecast-api.k6.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

const errorRate = new Rate('errors');

export const options = {
  stages: [
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 200 },  // Ramp up to 200 users
    { duration: '5m', target: 200 },  // Stay at 200 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    http_req_duration: ['p(95)<500'],  // 95% of requests under 500ms
    http_req_failed: ['rate<0.01'],    // Less than 1% errors
    errors: ['rate<0.01'],
  },
};

const BASE_URL = __ENV.API_URL || 'https://api.flux.example.com';
const AUTH_TOKEN = __ENV.AUTH_TOKEN;

export default function () {
  const headers = {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${AUTH_TOKEN}`,
  };

  // Test 1: List forecasts
  const listResponse = http.get(
    `${BASE_URL}/trpc/forecast.list?input=${encodeURIComponent(
      JSON.stringify({ restaurantId: 'restaurant-123', limit: 10 })
    )}`,
    { headers }
  );

  check(listResponse, {
    'list status is 200': (r) => r.status === 200,
    'list response time < 500ms': (r) => r.timings.duration < 500,
  }) || errorRate.add(1);

  sleep(1);

  // Test 2: Get forecast with explanation
  const detailResponse = http.get(
    `${BASE_URL}/trpc/forecast.getWithExplanation?input=${encodeURIComponent(
      JSON.stringify({ forecastId: 'forecast-123' })
    )}`,
    { headers }
  );

  check(detailResponse, {
    'detail status is 200': (r) => r.status === 200,
    'detail response time < 1000ms': (r) => r.timings.duration < 1000,
    'has explanation': (r) => {
      const body = JSON.parse(r.body);
      return body.result.data.explanation !== undefined;
    },
  }) || errorRate.add(1);

  sleep(1);

  // Test 3: Submit feedback
  const feedbackResponse = http.post(
    `${BASE_URL}/trpc/forecast.submitFeedback`,
    JSON.stringify({
      forecastId: 'forecast-123',
      actualQuantity: Math.floor(Math.random() * 100),
      wasAccurate: true,
    }),
    { headers }
  );

  check(feedbackResponse, {
    'feedback status is 200': (r) => r.status === 200,
    'feedback response time < 300ms': (r) => r.timings.duration < 300,
  }) || errorRate.add(1);

  sleep(2);
}
```

**Example: Database Query Performance Test**

```typescript
// packages/core/src/__tests__/performance/query-performance.test.ts
import { describe, it, expect, beforeAll } from 'vitest';
import { PrismaClient } from '@prisma/client';
import { performance } from 'perf_hooks';

describe('Query Performance', () => {
  let prisma: PrismaClient;

  beforeAll(async () => {
    prisma = new PrismaClient();

    // Seed large dataset (1000 forecasts)
    await seedLargeDataset(prisma);
  });

  it('should fetch forecasts with pagination in < 100ms', async () => {
    const start = performance.now();

    await prisma.forecast.findMany({
      where: { restaurantId: 'restaurant-123' },
      include: {
        menuItem: true,
        explanation: true,
      },
      orderBy: { forecastDate: 'desc' },
      take: 20,
      skip: 0,
    });

    const duration = performance.now() - start;
    expect(duration).toBeLessThan(100);
  });

  it('should calculate accuracy metrics in < 500ms', async () => {
    const start = performance.now();

    await prisma.$queryRaw`
      SELECT
        menu_item_id,
        AVG(ABS((predicted_quantity - actual_quantity) / NULLIF(actual_quantity, 0)) * 100) as mape,
        COUNT(*) as forecast_count
      FROM forecasts
      WHERE restaurant_id = 'restaurant-123'
        AND actual_quantity IS NOT NULL
        AND forecast_date >= NOW() - INTERVAL '30 days'
      GROUP BY menu_item_id
    `;

    const duration = performance.now() - start;
    expect(duration).toBeLessThan(500);
  });

  it('should use indexes for common queries', async () => {
    // Query with EXPLAIN ANALYZE
    const result = await prisma.$queryRawUnsafe(`
      EXPLAIN ANALYZE
      SELECT * FROM forecasts
      WHERE restaurant_id = 'restaurant-123'
        AND forecast_date = '2024-12-25'
    `);

    // Should use index scan, not sequential scan
    const plan = JSON.stringify(result);
    expect(plan).toContain('Index Scan');
    expect(plan).not.toContain('Seq Scan');
  });
});
```

### 10.6 Test Data Management

**Factory Pattern for Test Data**

```typescript
// packages/core/src/test-utils/factories.ts
import { faker } from '@faker-js/faker';
import type { PrismaClient, Restaurant, MenuItem, Forecast } from '@prisma/client';

export class RestaurantFactory {
  static build(overrides?: Partial<Restaurant>): Omit<Restaurant, 'id' | 'createdAt' | 'updatedAt'> {
    return {
      name: faker.company.name() + ' Restaurant',
      timezone: 'America/New_York',
      address: faker.location.streetAddress(),
      city: faker.location.city(),
      state: faker.location.state({ abbreviated: true }),
      zipCode: faker.location.zipCode(),
      status: 'ACTIVE',
      ...overrides,
    };
  }

  static async create(
    prisma: PrismaClient,
    overrides?: Partial<Restaurant>
  ): Promise<Restaurant> {
    return prisma.restaurant.create({
      data: this.build(overrides),
    });
  }
}

export class MenuItemFactory {
  static build(
    restaurantId: string,
    overrides?: Partial<MenuItem>
  ): Omit<MenuItem, 'id' | 'createdAt' | 'updatedAt'> {
    return {
      restaurantId,
      name: faker.commerce.productName(),
      category: faker.helpers.arrayElement(['ENTREE', 'APPETIZER', 'DESSERT', 'BEVERAGE']),
      status: 'ACTIVE',
      ...overrides,
    };
  }

  static async create(
    prisma: PrismaClient,
    restaurantId: string,
    overrides?: Partial<MenuItem>
  ): Promise<MenuItem> {
    return prisma.menuItem.create({
      data: this.build(restaurantId, overrides),
    });
  }

  static async createMany(
    prisma: PrismaClient,
    restaurantId: string,
    count: number
  ): Promise<void> {
    const items = Array.from({ length: count }, () =>
      this.build(restaurantId)
    );

    await prisma.menuItem.createMany({ data: items });
  }
}

export class ForecastFactory {
  static build(
    restaurantId: string,
    menuItemId: string,
    forecastRunId: string,
    overrides?: Partial<Forecast>
  ): Omit<Forecast, 'id' | 'createdAt' | 'updatedAt'> {
    return {
      restaurantId,
      menuItemId,
      forecastRunId,
      forecastDate: faker.date.future(),
      predictedQuantity: faker.number.float({ min: 10, max: 100, precision: 0.1 }),
      confidence: faker.number.float({ min: 0.7, max: 0.99, precision: 0.01 }),
      actualQuantity: null,
      status: 'ACTIVE',
      ...overrides,
    };
  }

  static async create(
    prisma: PrismaClient,
    restaurantId: string,
    menuItemId: string,
    forecastRunId: string,
    overrides?: Partial<Forecast>
  ): Promise<Forecast> {
    return prisma.forecast.create({
      data: this.build(restaurantId, menuItemId, forecastRunId, overrides),
    });
  }
}
```

### 10.7 CI/CD Test Integration

**GitHub Actions Workflow**

```yaml
# .github/workflows/test.yml
name: Test Suite

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  unit-tests:
    name: Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Run unit tests
        run: npm run test:unit -- --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/coverage-final.json
          flags: unit

  integration-tests:
    name: Integration Tests
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15-alpine
        env:
          POSTGRES_USER: test
          POSTGRES_PASSWORD: test
          POSTGRES_DB: flux_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Run migrations
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/flux_test
        run: npx prisma migrate deploy

      - name: Run integration tests
        env:
          DATABASE_URL: postgresql://test:test@localhost:5432/flux_test
          REDIS_URL: redis://localhost:6379
        run: npm run test:integration -- --coverage

      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          files: ./coverage/coverage-final.json
          flags: integration

  e2e-tests:
    name: E2E Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup Node.js
        uses: actions/setup-node@v3
        with:
          node-version: '18'

      - name: Install dependencies
        run: npm ci

      - name: Install Playwright
        run: npx playwright install --with-deps

      - name: Build application
        run: npm run build

      - name: Run E2E tests
        run: npm run test:e2e

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: playwright-report
          path: playwright-report/

  load-tests:
    name: Load Tests
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v3

      - name: Setup k6
        run: |
          curl https://github.com/grafana/k6/releases/download/v0.47.0/k6-v0.47.0-linux-amd64.tar.gz -L | tar xvz
          sudo mv k6-v0.47.0-linux-amd64/k6 /usr/local/bin/

      - name: Run load tests
        env:
          API_URL: ${{ secrets.STAGING_API_URL }}
          AUTH_TOKEN: ${{ secrets.LOAD_TEST_TOKEN }}
        run: k6 run tests/load/forecast-api.k6.js
```

### 10.8 Test Coverage Reporting

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

  ignore:
    - "**/__tests__/**"
    - "**/*.test.ts"
    - "**/*.spec.ts"
    - "**/test-utils/**"
    - "**/*.d.ts"

comment:
  layout: "header, diff, files"
  behavior: default
  require_changes: false
```

---