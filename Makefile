.PHONY: install dev api web test migrate db-up

# Default target
dev:
	@make -j2 api web

# Installation
install:
	@echo "Installing API dependencies..."
	cd apps/api && uv sync --extra dev
	@echo "Installing Web dependencies..."
	cd apps/web && pnpm install

# Run Services
api:
	@echo "Starting API..."
	cd apps/api && uv run fastapi dev src/main.py

web:
	@echo "Starting Web..."
	cd apps/web && pnpm dev

# Database
migrate:
	@echo "Running migrations..."
	cd apps/api && uv run alembic upgrade head

# Testing
test:
	@echo "Running API tests..."
	cd apps/api && uv run --extra dev pytest
	@echo "Running Web tests..."
	cd apps/web && pnpm test
