# Backend Architecture

> **Part of:** [Flux Architecture Documentation](./README.md)
> **Updated:** Python FastAPI + SQLAlchemy 2.0 + Lambda

---

## Overview

The backend is built with **Python 3.12, FastAPI, and SQLAlchemy 2.0**, deployed as AWS Lambda functions behind API Gateway. This architecture provides:

- **High Performance**: FastAPI is one of the fastest Python frameworks (comparable to Node.js)
- **Auto Documentation**: OpenAPI schema generated automatically
- **Type Safety**: Python type hints + Pydantic validation
- **Async Support**: Full async/await for I/O operations
- **ML Integration**: Seamless integration with Python ML pipeline

---

## Application Structure

**Location:** `apps/api/`

```
apps/api/
├── src/
│   ├── main.py                      # FastAPI app entry point
│   ├── config.py                    # Settings (Pydantic BaseSettings)
│   ├── dependencies.py              # FastAPI dependencies (auth, db)
│   ├── routers/                     # API route handlers
│   │   ├── auth.py
│   │   ├── forecasts.py
│   │   ├── menu.py
│   │   ├── procurement.py
│   │   └── ...
│   ├── services/                    # Business logic layer
│   │   ├── forecast_service.py
│   │   ├── pos_sync_service.py
│   │   └── ...
│   ├── models/                      # SQLAlchemy ORM models
│   │   ├── restaurant.py
│   │   ├── forecast.py
│   │   └── ...
│   ├── schemas/                     # Pydantic schemas
│   │   ├── forecast.py
│   │   └── ...
│   ├── adapters/                    # External service integrations
│   │   ├── pos/
│   │   │   ├── square.py
│   │   │   ├── toast.py
│   │   │   └── ...
│   │   └── ml/
│   │       └── sagemaker_adapter.py
│   ├── db/                          # Database utilities
│   │   ├── session.py
│   │   └── base.py
│   ├── core/                        # Core utilities
│   │   ├── security.py
│   │   ├── exceptions.py
│   │   ├── logging.py
│   │   └── cache.py
│   ├── tasks/                       # Celery background tasks
│   │   ├── forecast_tasks.py
│   │   └── pos_sync_tasks.py
│   └── handlers/                    # Lambda entry points
│       ├── api_handler.py           # Main API (Mangum)
│       ├── pos_sync_handler.py      # SQS-triggered
│       └── forecast_handler.py      # EventBridge-triggered
├── alembic/                         # Database migrations
│   └── versions/
├── tests/
├── pyproject.toml                   # Poetry dependencies
└── pytest.ini
```

---

## Layer Responsibilities

### 1. Handlers (Lambda Entry Points)

**Thin handlers** that parse Lambda events and delegate to services.

**Main API Handler (Mangum Adapter):**
```python
# apps/api/src/handlers/api_handler.py
from mangum import Mangum
from src.main import app

# Mangum wraps FastAPI for AWS Lambda
handler = Mangum(app, lifespan="off")
```

**SQS-Triggered Handler:**
```python
# apps/api/src/handlers/pos_sync_handler.py
from aws_lambda_typing import events

def handler(event: events.SQSEvent, context):
    """Process POS sync messages from SQS."""
    from src.services.pos_sync_service import POSSyncService
    from src.db.session import get_session

    service = POSSyncService()

    for record in event["Records"]:
        message = json.loads(record["body"])

        async with get_session() as db:
            await service.sync_transactions(
                db=db,
                restaurant_id=message["restaurant_id"],
                provider=message["provider"],
            )
```

### 2. Routers (API Endpoints)

**FastAPI path operations** with Pydantic validation and dependency injection.

```python
# apps/api/src/routers/forecasts.py
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.dependencies import get_current_user, get_db
from src.schemas.forecast import ForecastResponse, ForecastCreate
from src.services.forecast_service import ForecastService
from src.models.user import User

router = APIRouter()

@router.get("/", response_model=list[ForecastResponse])
async def list_forecasts(
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[ForecastResponse]:
    """List forecasts for current user's restaurant."""
    service = ForecastService(db)
    forecasts = await service.list_forecasts(
        restaurant_id=current_user.restaurant_id,
        limit=limit,
        offset=offset,
    )
    return forecasts

@router.post("/", response_model=ForecastResponse, status_code=status.HTTP_201_CREATED)
async def create_forecast(
    forecast_data: ForecastCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> ForecastResponse:
    """Generate new forecast."""
    service = ForecastService(db)
    forecast = await service.create_forecast(
        restaurant_id=current_user.restaurant_id,
        data=forecast_data,
    )
    return forecast
```

### 3. Services (Business Logic)

**Fat services** containing all business logic, transactions, and orchestration.

```python
# apps/api/src/services/forecast_service.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.forecast import Forecast, ForecastRun
from src.schemas.forecast import ForecastCreate
from src.core.logging import get_logger
from src.core.exceptions import NotFoundError

logger = get_logger(__name__)

class ForecastService:
    """Business logic for forecasting."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_forecasts(
        self,
        restaurant_id: str,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Forecast]:
        """List forecasts for restaurant."""
        logger.info(
            "Listing forecasts",
            extra={"restaurant_id": restaurant_id, "limit": limit}
        )

        query = (
            select(Forecast)
            .where(Forecast.restaurant_id == restaurant_id)
            .limit(limit)
            .offset(offset)
            .order_by(Forecast.forecast_date.desc())
        )

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def create_forecast(
        self,
        restaurant_id: str,
        data: ForecastCreate,
    ) -> Forecast:
        """Generate new forecast."""
        try:
            # Create forecast run
            forecast_run = ForecastRun(
                restaurant_id=restaurant_id,
                status="IN_PROGRESS",
            )
            self.db.add(forecast_run)
            await self.db.flush()

            # Create forecast
            forecast = Forecast(
                forecast_run_id=forecast_run.id,
                restaurant_id=restaurant_id,
                **data.dict(),
            )
            self.db.add(forecast)

            # Update status
            forecast_run.status = "COMPLETED"

            await self.db.commit()
            await self.db.refresh(forecast)

            logger.info("Forecast created", extra={"forecast_id": forecast.id})
            return forecast

        except Exception as e:
            await self.db.rollback()
            logger.error("Forecast creation failed", extra={"error": str(e)})
            raise
```

### 4. Models (SQLAlchemy ORM)

**Database models** using SQLAlchemy 2.0 with type hints.

```python
# apps/api/src/models/forecast.py
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import ForeignKey, String, Float, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.db.base import Base

class ForecastRun(Base):
    """Forecast generation run."""

    __tablename__ = "forecast_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    restaurant_id: Mapped[UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        index=True,
    )
    forecast_date: Mapped[datetime]
    status: Mapped[str] = mapped_column(String(50))
    model_version: Mapped[str] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    forecasts: Mapped[list["Forecast"]] = relationship(
        back_populates="forecast_run",
        cascade="all, delete-orphan"
    )
    restaurant: Mapped["Restaurant"] = relationship(back_populates="forecast_runs")

class Forecast(Base):
    """Individual forecast prediction."""

    __tablename__ = "forecasts"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    forecast_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("forecast_runs.id", ondelete="CASCADE"),
        index=True,
    )
    restaurant_id: Mapped[UUID] = mapped_column(
        ForeignKey("restaurants.id", ondelete="CASCADE"),
        index=True,
    )
    menu_item_id: Mapped[UUID] = mapped_column(
        ForeignKey("menu_items.id", ondelete="CASCADE")
    )
    forecast_date: Mapped[datetime] = mapped_column(index=True)
    predicted_quantity: Mapped[float] = mapped_column(Float)
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    forecast_run: Mapped["ForecastRun"] = relationship(back_populates="forecasts")
    restaurant: Mapped["Restaurant"] = relationship(back_populates="forecasts")
    menu_item: Mapped["MenuItem"] = relationship(back_populates="forecasts")
```

### 5. Schemas (Pydantic Models)

**API request/response models** with validation.

```python
# apps/api/src/schemas/forecast.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

class ForecastBase(BaseModel):
    """Base forecast schema."""
    menu_item_id: UUID
    forecast_date: datetime
    predicted_quantity: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)

class ForecastCreate(ForecastBase):
    """Schema for creating forecast."""
    pass

class ForecastResponse(ForecastBase):
    """Schema for forecast response."""
    id: UUID
    restaurant_id: UUID
    forecast_run_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True  # SQLAlchemy 2.0
```

---

## Dependency Injection

FastAPI's dependency system provides:
- Database sessions
- Authentication
- Multi-tenant context
- Caching

```python
# apps/api/src/dependencies.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from jose import JWTError, jwt

from src.db.session import get_session
from src.models.user import User
from src.core.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_db() -> AsyncSession:
    """Get database session."""
    async with get_session() as session:
        yield session

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Get current authenticated user."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
    )

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception

    # Set RLS context
    await db.execute(
        "SET LOCAL app.current_restaurant_id = :restaurant_id",
        {"restaurant_id": str(user.restaurant_id)}
    )

    return user
```

---

## Database Access Patterns

### Async Sessions

```python
# apps/api/src/db/session.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from src.core.config import settings

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

@asynccontextmanager
async def get_session():
    """Get async database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
```

### Row-Level Security (RLS)

```python
# Set RLS context per request
await db.execute(
    "SET LOCAL app.current_restaurant_id = :id",
    {"id": str(restaurant_id)}
)

# All subsequent queries are automatically filtered by RLS
forecasts = await db.execute(
    select(Forecast).where(Forecast.forecast_date >= start_date)
)
```

---

## Background Jobs (Celery)

```python
# apps/api/src/tasks/forecast_tasks.py
from celery import Celery
from src.services.forecast_service import ForecastService
from src.db.session import get_session

celery_app = Celery(
    "flux",
    broker="redis://localhost:6379/0",
    backend="redis://localhost:6379/0",
)

@celery_app.task
async def generate_daily_forecasts():
    """Generate forecasts for all restaurants (scheduled task)."""
    from src.models.restaurant import Restaurant

    async with get_session() as db:
        # Get all active restaurants
        result = await db.execute(
            select(Restaurant).where(Restaurant.status == "ACTIVE")
        )
        restaurants = result.scalars().all()

        # Queue individual forecast tasks
        for restaurant in restaurants:
            generate_forecast.delay(str(restaurant.id))

@celery_app.task
async def generate_forecast(restaurant_id: str):
    """Generate forecast for single restaurant."""
    async with get_session() as db:
        service = ForecastService(db)
        await service.create_forecast(restaurant_id, {...})
```

---

## Error Handling

```python
# apps/api/src/core/exceptions.py
from fastapi import HTTPException, status

class AppException(Exception):
    """Base application exception."""

    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)

class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, resource: str):
        super().__init__(
            message=f"{resource} not found",
            status_code=status.HTTP_404_NOT_FOUND
        )

# Exception handler in main.py
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )
```

---

## Logging (structlog)

```python
# apps/api/src/core/logging.py
import structlog
import logging

def configure_logging():
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        logger_factory=structlog.PrintLoggerFactory(),
    )

def get_logger(name: str):
    """Get logger instance."""
    return structlog.get_logger(name)

# Usage
from src.core.logging import get_logger

logger = get_logger(__name__)

logger.info(
    "Forecast created",
    forecast_id=str(forecast.id),
    restaurant_id=str(restaurant_id),
)
```

---

## Caching Strategy

```python
# apps/api/src/core/cache.py
from redis import asyncio as aioredis
import json

class CacheService:
    def __init__(self):
        self.redis = aioredis.from_url("redis://localhost:6379")

    async def get(self, key: str):
        """Get cached value."""
        value = await self.redis.get(key)
        return json.loads(value) if value else None

    async def set(self, key: str, value: any, ttl: int = 3600):
        """Set cached value with TTL."""
        await self.redis.setex(key, ttl, json.dumps(value))

    async def invalidate(self, pattern: str):
        """Invalidate cache by pattern."""
        keys = await self.redis.keys(pattern)
        if keys:
            await self.redis.delete(*keys)

# Usage in service
async def get_forecasts(restaurant_id: str):
    cache = CacheService()
    cache_key = f"forecasts:{restaurant_id}"

    # Check cache
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Query database
    forecasts = await db.execute(...)

    # Store in cache (1 hour)
    await cache.set(cache_key, forecasts, ttl=3600)

    return forecasts
```

---

## POS Adapters (External APIs)

```python
# apps/api/src/adapters/pos/base.py
from abc import ABC, abstractmethod

class BasePOSAdapter(ABC):
    """Base class for all POS adapters."""

    @abstractmethod
    async def fetch_orders(self, start_date, end_date):
        """Fetch orders from POS system."""
        pass

    @abstractmethod
    async def verify_webhook(self, signature, payload, url):
        """Verify webhook signature."""
        pass

# apps/api/src/adapters/pos/square.py
from square.client import Client
from src.adapters.pos.base import BasePOSAdapter

class SquareAdapter(BasePOSAdapter):
    """Square POS integration."""

    def __init__(self, access_token: str):
        self.client = Client(access_token=access_token)

    async def fetch_orders(self, start_date, end_date):
        """Fetch orders from Square API."""
        result = self.client.orders.search_orders(
            body={
                "location_ids": [self.location_id],
                "query": {
                    "filter": {
                        "date_time_filter": {
                            "created_at": {
                                "start_at": start_date.isoformat(),
                                "end_at": end_date.isoformat(),
                            }
                        }
                    }
                }
            }
        )

        return [self._normalize_order(order) for order in result.body["orders"]]

    def _normalize_order(self, order):
        """Normalize Square order to standard format."""
        return {
            "id": order["id"],
            "created_at": order["created_at"],
            "total_amount": order["total_money"]["amount"] / 100,
            "line_items": [
                {
                    "name": item["name"],
                    "quantity": item["quantity"],
                    "unit_price": item["base_price_money"]["amount"] / 100,
                }
                for item in order["line_items"]
            ],
        }
```

---

## Testing

```python
# apps/api/tests/test_services/test_forecast_service.py
import pytest
from uuid import uuid4

from src.services.forecast_service import ForecastService
from src.schemas.forecast import ForecastCreate

@pytest.mark.asyncio
async def test_create_forecast(db_session, test_restaurant):
    """Test forecast creation."""
    service = ForecastService(db_session)

    forecast_data = ForecastCreate(
        menu_item_id=uuid4(),
        forecast_date="2025-12-20",
        predicted_quantity=100.0,
        confidence=0.95,
    )

    forecast = await service.create_forecast(
        restaurant_id=test_restaurant.id,
        data=forecast_data,
    )

    assert forecast.id is not None
    assert forecast.predicted_quantity == 100.0
```

---

**Previous:** [← Frontend Architecture](./08-frontend-architecture.md)
**Next:** [Deployment →](./10-deployment.md)
