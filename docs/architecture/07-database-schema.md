# Database Schema v2

> **Part of:** [Flux Architecture Documentation](./README.md)
> **Updated:** December 2024 - Comprehensive schema for all algorithms

---

## Overview

**Implementation:** SQLAlchemy 2.0 (Python) with Alembic for migrations
**Location:** `apps/api/src/models/` (Python model definitions)
**Database:** PostgreSQL 16+
**Multi-tenancy:** Row-Level Security (RLS) via `restaurant_id` on all tables

---

## Table Summary (28 Tables)

| Domain | Tables | Purpose |
|--------|--------|---------|
| **Core** | users, restaurants, data_uploads | Authentication, tenancy |
| **Menu** | menu_categories, menu_items | Products sold |
| **Ingredients** | ingredient_categories, ingredients, recipes | Recipe costing |
| **Transactions** | transactions, transaction_items | Sales data |
| **Inventory** | inventory, inventory_movements | Stock tracking with expiry |
| **Labor** | employee_roles, employees, skills, employee_skills, shift_templates, employee_availability, scheduled_shifts | Scheduling |
| **Forecasting** | demand_forecasts, staffing_forecasts | ML predictions |
| **Promotions** | promotions, price_elasticity | Dynamic pricing |
| **External** | weather_data, local_events | Forecast inputs |
| **Settings** | restaurant_settings, algorithm_runs | Config and audit |

---

## Model Files

| File | Models |
|------|--------|
| `user.py` | User |
| `restaurant.py` | Restaurant |
| `menu.py` | MenuCategory, MenuItem |
| `ingredient.py` | IngredientCategory, Ingredient, Recipe |
| `transaction.py` | Transaction, TransactionItem |
| `inventory.py` | Inventory, InventoryMovement |
| `employee.py` | EmployeeRole, Employee, Skill, EmployeeSkill, ShiftTemplate, EmployeeAvailability, ScheduledShift |
| `forecast.py` | DemandForecast, StaffingForecast |
| `promotion.py` | Promotion, PriceElasticity |
| `external.py` | WeatherData, LocalEvent |
| `settings.py` | RestaurantSettings, AlgorithmRun |

---

## Key Entity Relationships

```
User ──┬── owns ──► Restaurant
       │
       └── works_at ──► Employee (optional)

Restaurant ──┬── has ──► MenuCategory ──► MenuItem
             │                              │
             │                              └── Recipe ◄── Ingredient
             │
             ├── has ──► Transaction ──► TransactionItem
             │
             ├── has ──► Inventory ──► InventoryMovement
             │
             ├── has ──► Employee ──┬── EmployeeSkill ◄── Skill
             │                      ├── EmployeeAvailability
             │                      └── ScheduledShift
             │
             ├── has ──► DemandForecast (per MenuItem)
             ├── has ──► StaffingForecast (per hour)
             ├── has ──► Promotion (per MenuItem)
             └── has ──► LocalEvent
```

---

## Key Design Decisions

### 1. Multi-Tenancy
All tables include `restaurant_id` foreign key. RLS policies isolate data per tenant.

### 2. Flexible JSONB Fields
- `demand_forecasts.factors` - Explainability (weather contribution, seasonality)
- `algorithm_runs.input_params` / `output_summary` - Algorithm audit
- `restaurant_settings.setting_value` - Extensible configuration

### 3. Audit Trail
- `inventory_movements` tracks all stock changes
- `algorithm_runs` logs every ML/optimization execution
- All tables have `created_at` / `updated_at`

### 4. Extensibility
- Generic `restaurant_settings` table for future config
- JSONB fields avoid schema migrations for new features
- Separate tables for weather/events allow easy addition of new external data sources

---

## Migrations

```bash
# View current state
cd apps/api && uv run alembic current

# Apply all migrations
cd apps/api && uv run alembic upgrade head

# Create new migration
cd apps/api && uv run alembic revision --autogenerate -m "description"
```

### Migration History
| Revision | Description |
|----------|-------------|
| 001_initial_schema | Users, restaurants, base tables |
| 002_transactions | Transaction and transaction_items |
| 003_comprehensive_schema | Full v2 schema (25+ new tables) |

---

**See also:**
- [Algorithm Architecture](./13-algorithm-architecture.md) - How algorithms use this data
- [database_schema_v2.sql](./database_schema_v2.sql) - Raw SQL reference
