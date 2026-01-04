# Flux

Flux is a restaurant intelligence platform that uses AI to help restaurants reduce food waste, optimize labor, and improve profitability.

## Getting Started

### Prerequisites
- Node.js 18+
- pnpm (`npm install -g pnpm`)
- Python 3.12+
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Docker & Docker Compose

### Setup

1. **Install dependencies:**
   ```bash
   pnpm install
   ```

2. **Start PostgreSQL:**
   ```bash
   docker compose up -d postgres
   ```

3. **Set up the API:**
   ```bash
   cd apps/api
   uv pip install -e ".[dev]"
   uv run alembic upgrade head
   uv run python scripts/seed.py
   ```

4. **Run the development servers:**
   ```bash
   # API (from apps/api)
   uv run uvicorn src.main:app --reload --port 8000

   # Web (from apps/web)
   pnpm dev
   ```

## Project Structure

```
├── apps/
│   ├── api/          # Python/FastAPI backend
│   └── web/          # Next.js frontend
├── infrastructure/   # Terraform IaC
└── docs/             # PRD, architecture, stories
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/api/auth/register` | POST | Create account |
| `/api/auth/login` | POST | Get JWT tokens |
| `/api/auth/refresh` | POST | Refresh access token |
| `/api/auth/me` | GET | Get current user (protected) |

## Test Credentials

| Email | Password |
|-------|----------|
| chef@laboqueria.es | password123 |
| owner@eixample.cat | password123 |
