# Flux Product Requirements Document (PRD)

## Goals and Background Context

### Goals

- Reduce food waste in independent restaurants by 30-50% through AI-powered demand forecasting and inventory optimization
- Optimize labor costs by 3-7% through intelligent scheduling based on predictive analytics
- Deliver 5:1 ROI for restaurant operators (€1 saved for every €0.20 spent on Flux)
- Achieve zero-burden data integration that works despite messy POS data
- Enable restaurant operators to make data-driven decisions without requiring technical expertise
- Build a defensible competitive moat through proprietary recipe database and cross-platform intelligence

### Background Context

The restaurant industry faces significant operational challenges: food waste averages 8-12% of purchases, labor costs consume 32% of revenue, and operators spend 10-15 hours weekly on manual inventory and scheduling tasks. Despite near-universal POS adoption (95% penetration), most independent restaurants lack predictive intelligence to optimize operations.

Flux addresses this gap as a middleware intelligence layer that sits between existing POS systems and restaurant operations. By applying AI/ML to transaction data, Flux provides demand forecasting, inventory optimization, and labor scheduling recommendations—enabling independent restaurant owners (1-5 locations, €300K-€5M revenue) to achieve efficiency gains previously available only to large chains. The platform is designed with a "zero-burden" philosophy, working effectively despite incomplete or inconsistent data through smart defaults, progressive enhancement, and explainable AI recommendations.

### Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-12-17 | 1.0 | Initial PRD based on comprehensive market research | John (PM) |
| 2025-12-18 | 1.1 | Updated technical stack to Python/FastAPI and Terraform | Winston (Architect) |
| 2025-12-23 | 1.2 | De-prioritized POS API integration for MVP; switched from Poetry to uv. | Winston (Architect) |
---

## Requirements

### Functional Requirements

**FR1 (MVP)**: The system shall support manual CSV ingestion of historical transaction data, with intelligent parsing of standard export formats from major POS systems.

**FR1.1 (Post-MVP)**: The system shall integrate with major POS providers (Toast, Square, Lightspeed, Clover, Revel) via OAuth authentication and API connections to automatically ingest historical transaction data.

**FR2**: The system shall generate demand forecasts for individual menu items with accuracy targets of ±25% (zero-effort setup), ±15% (minimal operator input), ±8% (light effort), and ±5% (engaged usage).

**FR3**: The system shall automatically extract and categorize ingredients from transaction data, creating a baseline ingredient list requiring minimal manual validation.

**FR4**: The system shall provide "Recipe Explosion" functionality that breaks down menu items into component ingredients with quantities, using a proprietary database of 10,000+ standard recipes with one-click confirmation.

**FR5**: The system shall calculate a Data Health Score (0-100%) evaluating completeness (40%), consistency (30%), timeliness (20%), and accuracy (10%) of restaurant data.

**FR6**: The system shall generate weekly procurement recommendations prioritized by impact/effort ratio, showing exactly what quantities to order for each ingredient.

**FR7**: The system shall provide explainable AI for all recommendations, showing the specific factors (historical patterns, weather correlations, seasonality, events) that drove each prediction.

**FR8**: The system shall support "Hybrid Mode" allowing operators to review and approve all recommendations during a 90-day trust-building period.

**FR9**: The system shall generate labor scheduling recommendations based on predicted customer traffic, showing optimal staffing levels by day/shift.

**FR10**: The system shall provide real-time inventory alerts for expiring ingredients with dynamic pricing suggestions to minimize waste.

**FR11**: The system shall calculate and display true menu item profitability including COGS, labor allocation, and overhead, not just food cost percentages.

**FR12**: The system shall offer "5-Minute Mondays" micro-tasks (time-boxed, gamified) that progressively improve data quality without overwhelming operators.

**FR13**: The system shall support passive data collection via invoice OCR, photo upload of handwritten recipes, and pattern learning to minimize manual data entry.

**FR14**: The system shall generate monthly savings reports quantifying waste reduction, labor optimization, and total ROI achieved.

**FR15**: The system shall provide cross-location intelligence for multi-location restaurant groups (3-5 locations), including inventory transfer recommendations and performance benchmarking.

**FR18**: The system shall provide mobile-responsive interface optimized for on-the-go decision-making, supporting both iOS and Android browsers.

**FR19**: The system shall send push notifications for critical alerts (expiring inventory, unexpected demand surges, data quality issues requiring attention).

**FR20**: The system shall support multi-language interface (English, Spanish initially) with plans for additional EU languages.

**FR21**: The system shall implement industry benchmarking (anonymous data sharing across Flux customers) to provide insights like "Your food cost is 4% higher than similar restaurants."

**FR22**: The system shall allow operators to export all their operational data in standard formats (CSV, JSON) to ensure data portability and ownership.

### Non-Functional Requirements

**NFR1**: The system shall achieve 99.5% uptime SLA for core forecasting and dashboard functionality (excluding scheduled maintenance windows).

**NFR2**: The system shall process CSV data ingestion and generate initial forecasts within 24 hours of account activation.

**NFR3 (Post-MVP)**: The system shall support real-time data synchronization with POS systems (15-minute sync intervals minimum), with graceful degradation to batch processing if real-time unavailable.

**NFR4**: The system shall maintain forecast accuracy within ±5% for 95th percentile of engaged users (those completing data hygiene tasks).

**NFR5**: The system shall comply with GDPR, CCPA/CPRA, and EU AI Act requirements for data privacy, user consent, and algorithmic transparency.

**NFR6**: The system shall encrypt all data in transit (TLS 1.3) and at rest (AES-256), with separate encryption keys per customer.

**NFR7**: The system shall provide explainability documentation for all AI recommendations sufficient to meet EU AI Act transparency requirements.

**NFR8**: The system shall scale to support 10,000 concurrent restaurant customers with < 2 second page load times (p95) for dashboard views.

**NFR9**: The system shall maintain prediction model retraining cycles of maximum 48 hours to incorporate new operational data.

**NFR10**: The system shall implement role-based access control (Owner, Manager, Chef, Staff) with granular permissions for multi-user restaurant accounts.

**NFR11**: The system shall support disaster recovery with RPO (Recovery Point Objective) < 1 hour and RTO (Recovery Time Objective) < 4 hours.

**NFR12**: The system shall maintain operational logs for all predictions and recommendations for minimum 2 years to support auditing and model improvement.

**NFR13**: The system shall achieve mobile responsiveness passing Google Core Web Vitals metrics (LCP < 2.5s, FID < 100ms, CLS < 0.1).

**NFR14**: The system shall support API rate limiting (1000 requests/hour per customer) to prevent abuse while allowing legitimate high-frequency integrations.

**NFR15**: The system shall maintain data residency options for EU customers (EU-only data storage) to comply with regional regulations.

---

## User Interface Design Goals

### Overall UX Vision

Flux delivers a "zero-burden intelligence" experience that feels like having a data analyst on staff without the complexity. The interface prioritizes **actionable insights over raw data**, presenting recommendations in plain language ("Order 12kg salmon, not your usual 15kg") rather than charts requiring interpretation. The design philosophy embraces progressive disclosure: new users see simple, high-confidence recommendations, while experienced users can drill into detailed analytics and model explanations. Mobile-first design acknowledges that restaurant owners make decisions on-the-go, often in loud, chaotic environments—so UI elements are thumb-friendly, high-contrast, and minimize text input.

### Key Interaction Paradigms

1. **Recommendation-First Dashboard**: Home screen prioritizes 3-5 actionable recommendations (procurement, scheduling, pricing) with one-tap approval/modification, relegating analytics to secondary navigation.

2. **Explainability on Demand**: Every recommendation includes a collapsible "Why?" section showing the factors behind predictions—tapping reveals layered detail from summary to full model breakdown.

3. **Hybrid Approval Workflow**: During onboarding (first 90 days), all recommendations require explicit operator approval, building trust; system transitions to auto-execution with exception-based review once trust is established.

4. **5-Minute Micro-Tasks**: Gamified weekly tasks ("5-Minute Mondays") appear as dismissible cards with progress indicators, rewarding data hygiene improvements with visible forecast accuracy gains.

5. **Swipe-Based Ingredient Management**: Recipe confirmation uses Tinder-style swipe interface (swipe right to accept smart default, swipe left to customize, swipe up to skip).

6. **Contextual Notifications**: Push notifications include actionable buttons ("Adjust Order," "View Details") allowing resolution without full app navigation.

### Core Screens and Views

1. **Dashboard (Home)**: Priority recommendations, weekly savings summary, data health score, quick access to procurement/scheduling.
2. **Data Upload View (MVP)**: Simple CSV upload interface with instructions and templates.
3. **Demand Forecast View**: Weekly calendar showing predicted sales by menu item, with confidence intervals and weather/event overlays.
4. **Procurement Planner**: Ingredient list with recommended order quantities, one-tap supplier integration, expiration alerts.
5. **Labor Scheduler**: Staff scheduling interface with predicted demand curves, optimization suggestions, shift approval workflow.
6. **Menu Profitability Analyzer**: Sortable table of menu items with true profitability (COGS + labor + overhead), highlighting winners and losers.
7. **Recipe Library**: Browse/search 10,000+ standard recipes, ingredient breakdown visualization, one-click customization.
8. **Data Health Center**: Data quality dashboard showing completeness scores by category, prioritized improvement tasks.
9. **Savings Report**: Monthly ROI summary with waste reduction, labor optimization, and cost savings breakdowns.
10. **Settings & Integrations**: POS connection management, supplier integrations, user roles, notification preferences.

### Accessibility

**Target: WCAG AA Compliance**

- High contrast ratios (4.5:1 for body text, 3:1 for large text)
- Keyboard navigation support for all interactive elements
- Screen reader compatibility for visually impaired operators
- Touch targets minimum 44×44 pixels for mobile usability
- Alternative text for all data visualizations and charts

### Branding

Flux branding conveys **professionalism with approachability**—think "Bloomberg Terminal meets Airbnb." Color palette uses deep navy (#1A2B4A) as primary, with vibrant accent colors for status indicators: success green (#10B981), warning amber (#F59E0B), critical red (#EF4444). Typography uses Inter for UI (clean, highly legible) and Tiempos Headline for hero text (warm, hospitality-appropriate). Iconography leans toward rounded, friendly shapes rather than austere corporate style, reflecting that users are small business owners, not corporate analysts.

**Logo**: Flux wordmark with subtle gradient suggesting "flow" and "intelligence." Animated logo loader shows data points converging into predictions.

**Illustration Style**: Custom illustrations for empty states, onboarding, and marketing use a flat, two-tone style with subtle texture—modern but not sterile.

### Target Device and Platforms

**Primary: Web Responsive (Desktop + Mobile)**
- Desktop optimization for deep analytics and menu planning (Chrome, Firefox, Safari, Edge)
- Mobile optimization for on-the-go procurement and scheduling decisions (iOS Safari, Android Chrome)

**Secondary: Progressive Web App (PWA)**
- Installable web app with offline access to cached forecasts and recommendations
- Push notification support for critical alerts
- Home screen icon for quick access

---

## Technical Assumptions

### Repository Structure: Monorepo

**Decision**: Single monorepo housing frontend (web app), backend (API services), and shared libraries.

**Rationale**:
- Simplifies dependency management across frontend and backend.
- Enables atomic commits spanning UI and API changes.
- Facilitates code sharing for generated API client and types.
- Supports coordinated versioning for related components.

**Tooling**: Turborepo for build orchestration.

### Service Architecture

**Decision**: Serverless-First Microservices within Monorepo

**Architecture Components**:

1. **API Gateway Layer** (AWS API Gateway)
   - Request routing, authentication, rate limiting
   - REST API endpoint with OpenAPI specification

2. **Core Services** (AWS Lambda / Serverless Functions)
   - **Auth Service**: User authentication, JWT session management
   - **Data Ingestion Service (Post-MVP)**: POS data extraction, normalization, validation
   - **CSV Ingestion Service (MVP)**: Parses and validates uploaded CSV files.
   - **Forecasting Service**: Demand prediction model execution, recommendation generation
   - **Recipe Service**: Recipe database CRUD, ingredient explosion logic
   - **Analytics Service**: Reporting, savings calculations, benchmarking
   - **Notification Service**: Push notifications, email alerts, SMS (Twilio)

3. **Data Layer**
   - **PostgreSQL (RDS)**: Relational data (users, restaurants, recipes, transactions)
   - **TimescaleDB extension**: Time-series optimization for transaction/forecast history
   - **S3**: Object storage for ML models, invoice OCR uploads, CSV uploads, exports
   - **ElastiCache (Redis)**: Session caching, real-time data sync buffers, Celery broker

4. **ML Pipeline** (Separate from request path)
   - **SageMaker**: Model training and retraining (Prophet, XGBoost, custom ensembles)
   - **Step Functions**: Orchestration of data prep → training → validation → deployment
   - **Model Registry**: Versioned model artifacts with A/B testing support

**Rationale**:
- Serverless reduces operational overhead for variable workload.
- Microservices enable independent scaling.
- Separation of ML pipeline from request path prevents model training from impacting user experience.
- Cost-efficient: pay only for compute during active usage.

**Deployment**:
- **Terraform** for infrastructure-as-code
- CI/CD via GitHub Actions with preview environments for PRs
- Blue-green deployment for zero-downtime updates

### Testing Requirements

**Decision**: Full Testing Pyramid (Unit → Integration → E2E → Manual)

**Testing Strategy**:

1. **Unit Tests** (Target: 80% code coverage)
   - All business logic, utility functions, data transformations
   - Framework: **pytest** (Python), Vitest (TypeScript)
   - Run on every commit (pre-commit hook + CI)

2. **Integration Tests** (Target: Critical paths covered)
   - API endpoint testing with mock database/external services
   - POS integration testing with fixture data from real POS exports
   - ML model validation testing (accuracy, bias, edge cases)
   - Framework: **pytest** with fixtures and Testcontainers

3. **End-to-End Tests** (Target: Core user journeys)
   - Onboarding flow (CSV upload → see first recommendations)
   - Procurement workflow (view forecast → adjust order → send to supplier)
   - Framework: Playwright or Cypress
   - Run nightly + on release candidate branches

4. **Manual Testing & QA**
   - Usability testing with real restaurant operators (5 users per feature release)
   - Accessibility audit (WCAG AA compliance verification)
   - Cross-browser/device testing (BrowserStack or manual)

5. **Model Testing (ML-Specific)**
   - Backtesting: Evaluate forecast accuracy against historical held-out data
   - A/B testing: Compare new model versions against production baseline
   - Bias audits: Ensure predictions don't discriminate by restaurant type/location
   - Performance monitoring: Track prediction accuracy drift over time (alerting if < 85% target)

### Additional Technical Assumptions and Requests

**Frontend Stack**:
- **Framework**: Next.js 14+ (React 18, Server Components, App Router)
- **Styling**: Tailwind CSS with custom design system components
- **State Management**: React Query for server state, Zustand for client state

**Backend Stack**:
- **Language**: **Python** for all services and ML pipeline
- **API Framework**: **FastAPI** (REST API with automatic OpenAPI generation)
- **Package Management**: **uv**
- **ORM**: **SQLAlchemy** (with Alembic for migrations)
- **Validation**: Pydantic for data validation and settings management
- **Authentication**: FastAPI's built-in OAuth2/JWT support

**External Integrations**:
- **Payment Processing**: Stripe for subscription billing
- **Email**: SendGrid for transactional emails (welcome, reports, alerts)
- **Observability**: Datadog or New Relic for APM, Sentry for error tracking

**Security**:
- **Secrets Management**: AWS Secrets Manager
- **API Security**: Rate limiting, request signing for POS webhooks, CORS
- **Database Security**: RLS (Row-Level Security) for multi-tenant data isolation

**DevOps**:
- **Version Control**: Git (GitHub)
- **CI/CD**: GitHub Actions
- **Infrastructure**: AWS (primary), **Terraform** for IaC

---

## Epic List

**Epic 1: Foundation & Authentication Infrastructure (MVP)**
_Goal: Establish core project infrastructure, AWS services, CI/CD pipeline, and authentication system, delivering a functional health-check endpoint and basic user registration with CSV upload._

**Epic 2: POS Data Ingestion & Normalization (Post-MVP)**
_Goal: Build robust data ingestion pipeline that connects to major POS providers (Toast, Square, Lightspeed), extracts historical transaction data, normalizes it into standardized schema, and handles sync errors gracefully._

**Epic 3: Recipe Intelligence & Ingredient Management (MVP)**
_Goal: Implement recipe database with baseline recipes, "Recipe Explosion" functionality to break down menu items into ingredients, and provide smart defaults for operator confirmation._

**Epic 4: Demand Forecasting Engine (MVP)**
_Goal: Develop ML-powered demand forecasting models (Prophet baseline, XGBoost advanced), train on ingested transaction data, and generate weekly demand forecasts with confidence intervals and explainable AI breakdowns._

**Epic 5: Procurement Recommendations (MVP)**
_Goal: Translate demand forecasts into actionable procurement recommendations (ingredient quantities), and implement a hybrid approval workflow for operators._

**Epic 6: Labor Scheduling Optimization (Post-MVP)**
_Goal: Build labor scheduling module to predict customer traffic and recommend optimal staffing levels.

**Epic 7: Analytics Dashboard & Reporting (MVP)**
_Goal: Create an analytics dashboard with menu profitability analysis, savings reports, and data health monitoring._

---

## Epic 1: Foundation & Authentication Infrastructure

**Epic Goal**: Establish production-ready infrastructure on AWS with serverless architecture, implement CI/CD pipeline via GitHub Actions, and deliver user authentication system with email/password registration. This epic delivers a deployable application with a health-check endpoint and user registration, laying the foundation for all subsequent features.

### Story 1.1: Project Setup & Monorepo Configuration

**As a developer,**
**I want a fully configured monorepo with Turborepo and workspace structure,**
**so that I can develop frontend and backend services with shared code and coordinated builds.**

#### Acceptance Criteria

1. Monorepo initialized with Turborepo, containing workspaces for `apps/web` (Next.js) and `apps/api` (Python/FastAPI).
2. TypeScript configured for frontend. Python environment managed with **uv**.
3. ESLint + Prettier configured for frontend; Ruff + Black for backend.
4. Git repository initialized with `.gitignore` and conventional commit message format.
5. `package.json` scripts support `turbo run dev`, `build`, `test`, and `lint`.
6. README.md includes setup instructions and architecture overview.

---

### Story 1.2: AWS Infrastructure Setup with Terraform

**As a DevOps engineer,**
**I want AWS infrastructure provisioned via Terraform including VPC, RDS PostgreSQL, S3, and API Gateway,**
**so that the application has production-grade cloud resources with infrastructure-as-code.**

#### Acceptance Criteria

1. Terraform project initialized in `infrastructure/` with modules for network, database, and compute.
2. VPC created with public and private subnets across 2 availability zones.
3. RDS PostgreSQL instance provisioned in private subnet with TimescaleDB extension enabled.
4. S3 bucket created for data uploads and exports with encryption at rest.
5. API Gateway (HTTP API) configured with CORS and rate limiting.
6. Secrets Manager configured for database credentials and JWT signing key.
7. Terraform workspaces (`dev`, `staging`, `prod`) used to manage environments.

---

### Story 1.3: CI/CD Pipeline with GitHub Actions

**As a developer,**
**I want automated CI/CD pipeline that runs tests, builds artifacts, and deploys to AWS on push to main,**
**so that code changes are validated and deployed safely without manual intervention.**

#### Acceptance Criteria

1. GitHub Actions workflow runs on push to all branches, executing linting and testing.
2. Pull request workflow creates preview environment.
3. Main branch workflow deploys to staging automatically after tests pass.
4. Production deployment triggered manually with an approval gate.
5. Workflow includes database migration step using **Alembic**.

---

### Story 1.4: Database Schema & SQLAlchemy ORM Setup

**As a backend developer,**
**I want PostgreSQL database schema defined with SQLAlchemy ORM including User, Restaurant, and Transaction tables,**
**so that I can perform type-safe database operations with migrations and seeders.**

#### Acceptance Criteria

1. SQLAlchemy models define `User`, `Restaurant`, `Transaction`, and `TransactionItem` tables.
2. Row-Level Security (RLS) policies configured to isolate restaurant data.
3. Alembic configured for database migrations.
4. Initial migration created and applied to development database.
5. Seed script creates test users and restaurants.

---

### Story 1.5: Authentication Service with JWT & Session Management

**As a backend developer,**
**I want authentication API endpoints for registration, login, logout, and token refresh,**
**so that users can securely access the application with JWT-based authentication.**

#### Acceptance Criteria

1. `POST /api/auth/register` endpoint creates a new user.
2. `POST /api/auth/login` endpoint validates credentials and returns JWT tokens.
3. `POST /api/auth/logout` endpoint invalidates the refresh token.
4. `POST /api/auth/refresh` endpoint issues a new access token.
5. Authentication middleware validates JWT on protected routes.

---

### Story 1.6: CSV Data Ingestion (MVP)

**As a restaurant owner,**
**I want to upload transaction data via CSV file,**
**so that I can use Flux without a direct POS integration for the MVP.**

#### Acceptance Criteria

1. `/dashboard/data/upload` page with a file upload component.
2. `POST /api/data/upload-csv` endpoint handles file upload to S3 and queues a parsing job.
3. Lambda function parses the CSV, validates data, and ingests it into `Transaction` tables.
4. UI provides feedback on upload progress, success, and errors.

---

### Story 1.7: Health Check Endpoint & Basic API Routing

**As a DevOps engineer,**
**I want a health check endpoint that verifies API and database connectivity,**
**so that monitoring systems can detect service degradation and trigger alerts.**

#### Acceptance Criteria

1. `GET /api/health` endpoint returns 200 OK with service status.
2. Health check verifies database and Redis connectivity.
3. CloudWatch alarm created to monitor the health check endpoint.

---

### Story 1.8: User Dashboard Skeleton (Next.js Frontend)

**As a restaurant owner,**
**I want a basic dashboard UI after login that displays my restaurant name and data upload status,**
**so that I can verify my account setup and see ingestion progress.**

#### Acceptance Criteria

1. Login and registration pages are functional.
2. Dashboard page (`/dashboard`) displays restaurant name and a placeholder for data status.
3. Navigation includes links to the dashboard and settings.
4. API requests use a generated OpenAPI client.
5. E2E test covers registration, login, and viewing the dashboard.

---
## Epic 2: POS Data Ingestion & Normalization (Post-MVP)

**Epic Goal**: Build production-ready data ingestion pipeline that authenticates with major POS providers (Toast, Square, Lightspeed), extracts historical transaction data (minimum 6 months), normalizes diverse POS schemas into unified Flux data model, handles sync errors gracefully, calculates data health scores (0-100% based on completeness, consistency, timeliness, accuracy), and displays ingestion progress in dashboard. This epic delivers the foundational data layer required for all forecasting and optimization features.

### Story 2.1: POS Data Sync Scheduler
### Story 2.2: Toast POS Transaction Ingestion
### Story 2.3: Square POS Transaction Ingestion
### Story 2.4: Lightspeed POS Transaction Ingestion
### Story 2.5: Data Normalization & Schema Mapping
### Story 2.6: Data Health Score Calculation
### Story 2.7: Data Health Dashboard UI
---

## Architect Prompt

```
You are Flux's Technical Architect. Using the PRD document (docs/prd.md) as your specification:

1. Design detailed system architecture including: service boundaries, REST API contracts with OpenAPI schemas, database schema with indexing strategy (using SQLAlchemy), message queue architecture (SQS/EventBridge), caching layers (Redis), and CDN configuration.
2. Define deployment architecture using Terraform: AWS region strategy, VPC design, Lambda function organization, API Gateway routing, RDS configuration (multi-AZ, read replicas), S3 bucket structure.
3. Specify security architecture: IAM roles, encryption at rest/in transit, API authentication flows (JWT + OAuth), PII data handling, GDPR compliance mechanisms.
4. Document ML pipeline architecture: SageMaker workflows, feature store design, model registry, A/B testing infrastructure, monitoring and retraining triggers.
5. Establish monitoring and observability: CloudWatch dashboards, custom metrics, alerting rules, log aggregation strategy, distributed tracing (X-Ray).
6. Create migration and rollback strategies (using Alembic), disaster recovery plan, and scaling strategy (auto-scaling policies, database partitioning).
7. Define coding standards, git workflow, and CI/CD pipeline details for a Python/FastAPI backend and TypeScript/Next.js frontend.

Output your complete technical architecture document to docs/architecture.md.
```