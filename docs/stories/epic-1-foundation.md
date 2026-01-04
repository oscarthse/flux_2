# Epic 1: Foundation & Authentication Infrastructure

**Status:** Done
**Epic Goal**: Establish production-ready infrastructure on AWS with a serverless architecture, implement a CI/CD pipeline via GitHub Actions, and deliver a user authentication system with email/password registration. This epic delivers a deployable application with a health-check endpoint and user registration, laying the foundation for all subsequent features.

---

## User Stories

### Story 1.1: Project Setup & Monorepo Configuration

**As a developer,**
**I want a fully configured monorepo with Turborepo and workspace structure,**
**so that I can develop frontend and backend services with shared code and coordinated builds.**

#### Dev Notes
- Initialize the project as a `pnpm` workspace.
- Set up `apps/web` as a Next.js application.
- Set up `apps/api` as a Python application.
- Configure `uv` for Python dependency management in `apps/api`.
- Set up shared `packages/ui` for React components and `packages/config` for shared linting/styling configurations.

#### Tasks
- [x] Initialize `pnpm` monorepo.
- [x] Create Next.js `web` application.
- [x] Create Python `api` application with FastAPI.
- [x] Configure `uv` in `apps/api`.
- [x] Configure Turborepo for `dev`, `build`, `test`, `lint` scripts.
- [x] Set up ESLint, Prettier, Ruff, and Black.
- [x] Create initial `README.md`.

---

### Story 1.2: AWS Infrastructure Setup with Terraform

**As a DevOps engineer,**
**I want AWS infrastructure provisioned via Terraform including VPC, RDS PostgreSQL, S3, and API Gateway,**
**so that the application has production-grade cloud resources with infrastructure-as-code.**

#### Dev Notes
- Create a modular Terraform setup in the `infrastructure/` directory.
- Use Terraform workspaces for `dev`, `staging`, and `prod`.
- The database should be in a private subnet for security.
- Use AWS Secrets Manager for all credentials.

#### Tasks
- [x] Create Terraform module for VPC with public/private subnets.
- [x] Create Terraform module for RDS PostgreSQL with TimescaleDB extension.
- [x] Create Terraform module for S3 buckets (app data, logs).
- [x] Create Terraform module for API Gateway with Lambda integration.
- [x] Create Terraform module for basic IAM roles and security groups.
- [x] Configure `backend.tf` to use S3 for state storage.

---

### Story 1.3: CI/CD Pipeline with GitHub Actions

**As a developer,**
**I want an automated CI/CD pipeline that runs tests, builds artifacts, and deploys to AWS on push to `main`,**
**so that code changes are validated and deployed safely without manual intervention.**

#### Dev Notes
- The pipeline should clearly separate build, test, and deploy stages.
- Use GitHub Actions with OIDC for secure AWS authentication.
- A PR should trigger tests and linting, but not deployment.
- A push to `main` should deploy to `staging`.
- Production deployments should be manual.

#### Tasks
- [x] Create a GitHub Actions workflow file.
- [x] Add a `test` job that runs `ruff`, `mypy`, `pytest`, and `vitest`.
- [x] Add a `build` job that builds the Next.js app and creates the Python Lambda package.
- [x] Add a `deploy-staging` job that runs `terraform apply` for the staging environment.
- [x] Add a `deploy-production` job with a manual `workflow_dispatch` trigger.
- [x] Configure secrets for AWS credentials and other environment variables.

---

### Story 1.4: Database Schema & SQLAlchemy ORM Setup

**As a backend developer,**
**I want the PostgreSQL database schema defined with SQLAlchemy ORM and Alembic for migrations,**
**so that I can perform type-safe database operations and manage schema changes.**

#### Dev Notes
- The initial schema will focus on users, restaurants, and a way to track data uploads. POS connections will be added later.
- RLS policies are critical for multi-tenancy.
- A seed script is essential for local development and testing.

#### Tasks
- [x] Define SQLAlchemy ORM models for `User`, `Restaurant`, `DataUpload`.
- [x] Set up Alembic for database migrations.
- [x] Create an initial migration for the core tables.
- [x] Write a script to apply RLS policies to the tables.
- [x] Create a seed script to populate the development database with test data.

---

### Story 1.5: Authentication Service with JWT

**As a backend developer,**
**I want authentication API endpoints for user registration and login,**
**so that users can securely access the application.**

#### Dev Notes
- Use `passlib` for password hashing.
- Use `python-jose` for creating and validating JWTs.
- Store refresh tokens in the database to allow for revocation.

#### Tasks
- [x] Implement `POST /api/auth/register` endpoint.
- [x] Implement `POST /api/auth/login` endpoint.
- [x] Implement `POST /api/auth/refresh` endpoint.
- [x] Implement `POST /api/auth/logout` endpoint.
- [x] Create authentication middleware (FastAPI dependency) to protect routes.
- [x] Add unit and integration tests for all authentication flows.

---

### Story 1.6: CSV Data Ingestion (MVP)

**As a restaurant owner,**
**I want to upload my historical sales data via a CSV file,**
**so that I can get started with Flux without a direct POS integration.**

#### Dev Notes
- The upload will be a multi-step process: upload to S3, trigger a Lambda, parse, and ingest.
- Use Pydantic for validating the structure of the CSV rows.
- Provide clear feedback to the user on the status of their upload.

#### Tasks
- [ ] Create a UI component for file uploads in the Next.js app.
- [x] Implement `POST /api/data/upload` endpoint (simplified: direct upload, no S3).
- [ ] Frontend uploads the file directly to S3 using the presigned URL.
- [ ] Create a Lambda function triggered by S3 `put` events in the upload bucket.
- [x] Implement the parsing and validation logic (in API, not Lambda for MVP).
- [x] Ingest valid data into the `Transaction` and `TransactionItem` tables.
- [x] Create a `DataUpload` record to track the status and errors of the upload.
- [x] Implement an endpoint for the frontend to poll for the upload status.

---

### Story 1.7: Health Check Endpoint

**As a DevOps engineer,**
**I want a health check endpoint that verifies API and database connectivity,**
**so that monitoring systems can detect service degradation.**

#### Dev Notes
- This endpoint should be public and require no authentication.
- It should provide a quick status check of critical downstream services (database, cache).

#### Tasks
- [x] Implement `GET /api/health` in the FastAPI application.
- [x] The endpoint should check for a successful connection to PostgreSQL and Redis.
- [x] Return a 200 status with a JSON body indicating the status of each service.
- [x] Return a 503 status if a critical service (like the database) is down.

---

### Story 1.8: User Dashboard Skeleton

**As a restaurant owner,**
**I want a basic dashboard UI after login that displays my restaurant name and data upload status,**
**so that I can verify my account setup and see ingestion progress.**

#### Dev Notes
- This is the initial landing page after login. It should be simple and provide immediate, relevant information.
- The UI should be built with components from the shared `ui` package.

#### Tasks
- [x] Create a login page at `/login`.
- [x] Create a registration page at `/register`.
- [x] Create a protected dashboard page at `/dashboard`.
- [x] The dashboard should display the user's email (restaurant coming in later epic).
- [x] Add a component to the dashboard that shows the status of the latest data upload.
- [x] Create a basic navigation layout (Sidebar + Header).
- [ ] Write an E2E test to verify the login flow and dashboard display.

---

## Dev Agent Record

### Agent Model Used
- model:

### Debug Log References
-

### Completion Notes
- Story 1.1 is complete. The basic monorepo structure is in place with pnpm, Turborepo, Next.js, and FastAPI.
- Story 1.4 is complete. Database schema with Alembic migration, RLS policies, and seed script. Docker Compose for local PostgreSQL.
- Story 1.5 is complete. JWT-based auth with register, login, logout, refresh endpoints and `get_current_user` middleware.
- Initial linting and formatting tools are configured.

### File List
- `pnpm-workspace.yaml`
- `package.json`
- `apps/web/**`
- `apps/api/**`
- `turbo.json`
- `.prettierrc.json`
- `README.md`
- `docker-compose.yml`
- `apps/api/migrations/`
- `apps/api/scripts/`
- `apps/api/src/core/`
- `apps/api/src/routers/auth.py`

### Change Log
- Initial project setup.
- Story 1.4: Database setup with Alembic migrations, RLS policies, seed script.
- Story 1.5: JWT authentication service with all endpoints.
