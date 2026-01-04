# Flux Architecture Documentation

> **Comprehensive technical architecture for the Flux restaurant SaaS platform**
>
> _Last Updated: December 18, 2025 | Version 1.1_

---

## 📖 Overview

This directory contains the complete architecture documentation for **Flux** - a serverless, multi-tenant SaaS platform for restaurant demand forecasting powered by machine learning. The documentation has been organized into focused, digestible sections for easy navigation and maintenance.

### Key Characteristics

- **Platform**: AWS Serverless (Lambda, RDS, SageMaker)
- **Scale**: 10,000 restaurants, 50M+ daily transactions
- **Tech Stack**: Next.js 15, FastAPI, PostgreSQL, Python, TypeScript
- **Architecture**: Multi-tenant with Row-Level Security, Event-Driven, ML-powered

---

## 📚 Documentation Structure

The architecture is divided into 12 focused documents, each covering a specific aspect of the system:

### 1. [High Level Overview](./01-high-level-overview.md) (21 KB)
**Start here** - Introduction, system architecture diagram, platform choices, tech stack, and team implications.

**Key Topics:**
- Technical summary and integration points
- Repository structure (Turborepo monorepo)
- Architectural patterns (Serverless, Multi-tenant, Adapter, Event-Driven)
- Complete technology stack with version specifications
- Impact on hiring, onboarding, and maintenance

---

### 2. [Data Models](./02-data-models.md) (53 KB)
Complete data model with all 24 entities, relationships, storage calculations, and GDPR compliance.

**Key Topics:**
- Scale targets (10K restaurants, 1.44B transactions)
- Multi-tenancy strategy with Row-Level Security
- Core business entities (Restaurant, User, Transaction, MenuItem)
- ML/forecasting entities (Forecast, ForecastRun, ForecastExplanation)
- Procurement entities (ProcurementRecommendation, Supplier)
- Storage calculations and indexing strategies

---

### 3. [API Specification](./03-api-specification.md) (96 KB)
REST API specification with OpenAPI, defining all endpoints, request/response schemas, and business logic.

**Key Topics:**
- Auth Router (registration, login, JWT)
- Menu Router (CRUD with pagination)
- Forecast Router (with SHAP explanations)
- Recipe Router (ingredient explosion)
- Transaction Router (POS data)
- Procurement Router (recommendations)
- POS Router (sync operations)
- User & Restaurant Routers

---

### 4. [Components](./04-components.md) (45 KB)
Frontend and backend component architecture using Atomic Design and service patterns.

**Key Topics:**
- **Frontend**: Atoms, Molecules, Organisms, Templates, Feature Modules
- **Backend**: Lambda handlers, Service layer, Adapter pattern
- Component composition patterns
- Code examples for each layer

---

### 5. [External APIs](./05-external-apis.md) (22 KB)
Integration architecture for POS systems, payments, communications, and analytics.

**Key Topics:**
- POS integrations (Toast, Square, Clover, Lightspeed)
- Payment processing (Stripe)
- Communication services (SendGrid, Twilio)
- Analytics & monitoring (Datadog)
- ML/AI services (AWS SageMaker)
- Integration matrix and resilience patterns

---

### 6. [Core Workflows](./06-workflows.md) (46 KB)
Sequence diagrams for 7 critical user and system workflows.

**Key Topics:**
1. User registration & onboarding
2. Forecast generation (scheduled)
3. POS transaction sync
4. Procurement recommendation flow
5. Forecast explanation & feedback
6. Team member invitation
7. Data health monitoring

---

### 7. [Database Schema](./07-database-schema.md) (25 KB)
Complete SQLAlchemy model definitions and Alembic migration strategy.

**Key Topics:**
- Full SQLAlchemy models (24 entities)
- Multi-tenancy with Row-Level Security
- Indexing strategy for query performance
- TimescaleDB compression policies
- Cascade behavior and constraints
- Enums for type safety

---

### 8. [Frontend Architecture](./08-frontend-architecture.md) (22 KB)
Next.js 15 App Router architecture with routing, state management, and patterns.

**Key Topics:**
- Application structure (route groups, dynamic routes)
- Routing strategy (Server/Client components)
- State management (React Query, Zustand)
- Authentication (NextAuth.js with JWT)
- Data fetching patterns
- UI component patterns
- Performance optimizations
- Error handling and accessibility

---

### 9. [Backend Architecture](./09-backend-architecture.md) (32 KB)
Lambda-based Python backend with service patterns, background jobs, and ML integration.

**Key Topics:**
- Lambda function patterns (thin handlers, fat services)
- Service layer architecture with FastAPI
- Database access patterns with SQLAlchemy and RLS
- Background job processing (Celery, SQS, EventBridge)
- ML integration with SageMaker
- Error handling and logging
- Caching strategy (Redis)

---

### 10. [Deployment](./10-deployment.md) (36 KB)
Terraform infrastructure, CI/CD pipeline, and deployment strategies.

**Key Topics:**
- Infrastructure overview (VPC, Lambda, RDS, S3)
- Terraform modules (Network, Database, Compute, Queue, Frontend)
- GitHub Actions CI/CD workflow
- Environment configuration (dev, staging, prod)
- Blue-green deployment strategy
- Rollback procedures
- Monitoring and alarms (CloudWatch)

---

### 11. [Security & Compliance](./11-security-compliance.md) (36 KB)
Defense-in-depth security architecture with GDPR and EU AI Act compliance.

**Key Topics:**
- Authentication & authorization (JWT, RBAC, rate limiting)
- Data encryption (at rest, in transit, field-level)
- GDPR compliance (all 5 data subject rights)
- EU AI Act compliance (transparency, explainability)
- Audit logging
- Security best practices checklist

---

### 12. [Testing Strategy](./12-testing-strategy.md) (36 KB)
Comprehensive testing approach with unit, integration, E2E, and load tests.

**Key Topics:**
- Test pyramid (75% unit, 20% integration, 5% E2E)
- Unit testing with pytest
- Integration testing with Testcontainers
- E2E testing with Playwright
- Load testing with k6
- Test data management (factories)
- CI/CD test integration
- Coverage reporting (Codecov)

---

## 🎯 Quick Navigation

### By Role

**Frontend Developers:**
1. [High Level Overview](./01-high-level-overview.md) - Tech stack
2. [Components](./04-components.md) - Frontend components
3. [Frontend Architecture](./08-frontend-architecture.md) - Next.js patterns
4. [API Specification](./03-api-specification.md) - Available endpoints (OpenAPI)

**Backend Developers:**
1. [Data Models](./02-data-models.md) - Database schema
2. [API Specification](./03-api-specification.md) - FastAPI routers
3. [Backend Architecture](./09-backend-architecture.md) - Lambda patterns
4. [External APIs](./05-external-apis.md) - Third-party integrations

**ML Engineers:**
1. [Data Models](./02-data-models.md) - Forecast entities
2. [API Specification](./03-api-specification.md) - Forecast router
3. [Backend Architecture](./09-backend-architecture.md) - ML integration
4. [Core Workflows](./06-workflows.md) - Forecast generation flow

**DevOps/Platform Engineers:**
1. [High Level Overview](./01-high-level-overview.md) - Infrastructure choice
2. [Deployment](./10-deployment.md) - Terraform modules
3. [Security & Compliance](./11-security-compliance.md) - Security architecture
4. [Testing Strategy](./12-testing-strategy.md) - CI/CD integration

**Product/Business:**
1. [High Level Overview](./01-high-level-overview.md) - System overview
2. [Core Workflows](./06-workflows.md) - User journeys
3. [Data Models](./02-data-models.md) - Scale and storage costs

### By Topic

**Multi-Tenancy:**
- [Data Models § Multi-Tenancy Strategy](./02-data-models.md#multi-tenancy-strategy)
- [Database Schema § RLS Setup](./07-database-schema.md)
- [Backend Architecture § Database Access Patterns](./09-backend-architecture.md#database-access-patterns)

**ML/AI Forecasting:**
- [Data Models § ML Entities](./02-data-models.md)
- [API Specification § Forecast Router](./03-api-specification.md)
- [Backend Architecture § ML Integration](./09-backend-architecture.md#ml-integration)
- [Core Workflows § Forecast Generation](./06-workflows.md)

**POS Integrations:**
- [External APIs § POS Integrations](./05-external-apis.md#pos-integrations)
- [Backend Architecture § Service Layer](./09-backend-architecture.md#service-layer-patterns)
- [Core Workflows § POS Transaction Sync](./06-workflows.md)

**Security & Compliance:**
- [Security & Compliance](./11-security-compliance.md) - Full section
- [Data Models § GDPR Fields](./02-data-models.md#gdpr-compliance-fields)
- [Backend Architecture § Error Handling](./09-backend-architecture.md#error-handling)

---

## 📊 Document Metrics

| Document | Size | Lines | Key Sections |
|----------|------|-------|--------------|
| 01-high-level-overview.md | 21 KB | ~600 | 3 |
| 02-data-models.md | 53 KB | ~1,600 | 24 entities |
| 03-api-specification.md | 96 KB | ~3,000 | 9 routers |
| 04-components.md | 45 KB | ~1,600 | 2 (Frontend/Backend) |
| 05-external-apis.md | 22 KB | ~900 | 9 integrations |
| 06-workflows.md | 46 KB | ~700 | 7 workflows |
| 07-database-schema.md | 25 KB | ~750 | SQLAlchemy Models & Alembic |
| 08-frontend-architecture.md | 22 KB | ~950 | 9 subsections |
| 09-backend-architecture.md | 32 KB | ~1,300 | 8 subsections |
| 10-deployment.md | 36 KB | ~1,070 | 8 subsections |
| 11-security-compliance.md | 36 KB | ~1,280 | 8 subsections |
| 12-testing-strategy.md | 36 KB | ~1,285 | 8 subsections |
| **TOTAL** | **~470 KB** | **~15,000** | **12 documents** |

---

## 🔄 Version History

| Version | Date | Changes | Author |
|---------|------|---------|--------|
| 1.0 | 2025-12-17 | Initial comprehensive architecture | Winston (Architect) |
| 1.1 | 2025-12-18 | Split into modular documents & updated to Python/Terraform stack | Winston (Architect) |

---

## 📝 Contributing

When updating the architecture:

1. **Update the relevant section file** - Not the old monolithic `architecture.md`
2. **Maintain cross-references** - Update links between documents
3. **Update this README** - If adding new sections or major changes
4. **Update version history** - Document what changed and why

---

## ❓ FAQ

**Q: Why split the architecture into multiple files?**
A: Better navigation, faster loading, easier maintenance, clearer responsibility boundaries, and reduced merge conflicts.

**Q: Which file should I read first?**
A: Start with [01-high-level-overview.md](./01-high-level-overview.md) for context, then jump to the section relevant to your role.

**Q: Where are the database models defined?**
A: [07-database-schema.md](./07-database-schema.md) contains the complete SQLAlchemy models and Alembic migration strategy.

**Q: How do I find all the API endpoints?**
A: [03-api-specification.md](./03-api-specification.md) lists all 9 FastAPI routers with full OpenAPI schemas.

**Q: Where are the deployment instructions?**
A: [10-deployment.md](./10-deployment.md) covers Terraform infrastructure, CI/CD, and deployment strategies.

---

## 📞 Support

For questions about this architecture:
- **Technical Questions**: Review the relevant section, check cross-references
- **Clarifications**: Open an issue with the specific document and section
- **Suggestions**: Submit a PR with proposed changes

---

**Ready to dive in?** → [Start with High Level Overview](./01-high-level-overview.md)
