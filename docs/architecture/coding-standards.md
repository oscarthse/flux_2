# Coding Standards

> **Part of:** [Flux Architecture Documentation](./README.md)
> **Updated:** Python-first with FastAPI, SQLAlchemy, and TypeScript frontend

---

## General Principles

### 1. Type Safety First
- **Python Type Hints**: Use Python 3.12+ type hints for all functions
- **Pydantic**: Use Pydantic models for validation
- **mypy**: Run mypy for static type checking
- **TypeScript Frontend**: Use TypeScript 5.3+ with strict mode for frontend

### 2. Code Organization
- **Single Responsibility**: Each function/class does one thing well
- **DRY (Don't Repeat Yourself)**: Extract common logic to shared utilities
- **SOLID Principles**: Follow SOLID design principles for classes
- **Layered Architecture**: Routers → Services → Models (clear separation)

### 3. Naming Conventions

#### Python (Backend + ML)
- **Files/Modules**: snake_case (`forecast_service.py`)
- **Classes**: PascalCase (`ForecastService`)
- **Functions/Methods**: snake_case (`calculate_accuracy`)
- **Constants**: UPPER_SNAKE_CASE (`API_BASE_URL`)
- **Private Members**: Prefix with underscore (`_private_method`)

#### TypeScript (Frontend)
- **Files**: kebab-case (`forecast-card.tsx`)
- **Components**: PascalCase (`ForecastCard`)
- **Functions**: camelCase (`calculateAccuracy`)
- **Constants**: UPPER_SNAKE_CASE (`API_BASE_URL`)
- **Interfaces**: PascalCase (`User`)

---

## Python Standards (Backend + ML)

### PEP 8 Style Guide

Follow [PEP 8](https://peps.python.org/pep-0008/) with these specific rules:

- **Line Length**: 88 characters (Black default)
- **Indentation**: 4 spaces
- **Imports**: Organized with `ruff` (which includes isort functionality)
- **Docstrings**: Google-style docstrings

### Type Hints

**✅ DO:**
```python
from typing import Optional, List
from pydantic import BaseModel

# Use type hints for all function signatures
async def get_user(user_id: str) -> Optional[User]:
    """Fetch user by ID.

    Args:
        user_id: The user's UUID

    Returns:
        User object if found, None otherwise

    Raises:
        DatabaseError: If database connection fails
    """
    user = await db.users.find_one({"id": user_id})
    return User(**user) if user else None

# Use Pydantic for data validation
class UserCreate(BaseModel):
    email: str
    first_name: str
    last_name: str
    password: str

    class Config:
        str_strip_whitespace = True

# Use type aliases for complex types
UserId = str
ForecastData = dict[str, float]
```

**❌ DON'T:**
```python
# Don't omit type hints
def get_user(user_id):  # ❌ No type hints
    return db.users.find_one({"id": user_id})

# Don't use bare except
try:
    result = risky_operation()
except:  # ❌ Too broad
    pass

# Don't ignore type errors
user = get_user(123)  # type: ignore  # ❌ Masking real issues
```

### FastAPI Patterns

#### Router Organization

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

#### Dependency Injection

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
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db.get(User, user_id)
    if user is None:
        raise credentials_exception

    return user
```

### Service Layer Pattern

```python
# apps/api/src/services/forecast_service.py
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from src.models.forecast import Forecast, ForecastRun
from src.schemas.forecast import ForecastCreate, ForecastResponse
from src.core.exceptions import NotFoundError
from src.core.logging import get_logger

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
            extra={
                "restaurant_id": restaurant_id,
                "limit": limit,
                "offset": offset
            }
        )

        query = (
            select(Forecast)
            .where(Forecast.restaurant_id == restaurant_id)
            .limit(limit)
            .offset(offset)
            .order_by(Forecast.forecast_date.desc())
        )

        result = await self.db.execute(query)
        forecasts = result.scalars().all()

        return list(forecasts)

    async def create_forecast(
        self,
        restaurant_id: str,
        data: ForecastCreate,
    ) -> Forecast:
        """Generate new forecast."""
        logger.info(
            "Creating forecast",
            extra={"restaurant_id": restaurant_id, "data": data.dict()}
        )

        try:
            # Create forecast run
            forecast_run = ForecastRun(
                restaurant_id=restaurant_id,
                status="IN_PROGRESS",
            )
            self.db.add(forecast_run)
            await self.db.flush()  # Get ID without committing

            # Generate forecasts (simplified)
            forecast = Forecast(
                forecast_run_id=forecast_run.id,
                restaurant_id=restaurant_id,
                **data.dict(),
            )
            self.db.add(forecast)

            # Update run status
            forecast_run.status = "COMPLETED"

            await self.db.commit()
            await self.db.refresh(forecast)

            logger.info(
                "Forecast created",
                extra={"forecast_id": forecast.id}
            )

            return forecast

        except Exception as e:
            await self.db.rollback()
            logger.error(
                "Failed to create forecast",
                extra={"restaurant_id": restaurant_id, "error": str(e)}
            )
            raise
```

### SQLAlchemy 2.0 Models

```python
# apps/api/src/models/forecast.py
from datetime import datetime
from typing import Optional
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

### Pydantic Schemas

```python
# apps/api/src/schemas/forecast.py
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, validator

class ForecastBase(BaseModel):
    """Base forecast schema."""
    menu_item_id: UUID
    forecast_date: datetime
    predicted_quantity: float = Field(gt=0, description="Must be positive")
    confidence: float = Field(ge=0, le=1, description="Between 0 and 1")

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
        from_attributes = True  # SQLAlchemy 2.0 (was orm_mode)

class ForecastWithMenuItem(ForecastResponse):
    """Forecast with menu item details."""
    menu_item_name: str
    menu_item_category: str
```

### Error Handling

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

### Logging (structlog)

```python
# apps/api/src/core/logging.py
import structlog
import logging

def configure_logging():
    """Configure structured logging."""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

def get_logger(name: str):
    """Get logger instance."""
    return structlog.get_logger(name)

# Usage in services
from src.core.logging import get_logger

logger = get_logger(__name__)

logger.info(
    "Forecast created",
    forecast_id=str(forecast.id),
    restaurant_id=str(restaurant_id),
)
```

### Async Database Sessions

```python
# apps/api/src/db/session.py
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from src.core.config import settings

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create session factory
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

---

## TypeScript Standards (Frontend)

### React Component Patterns

**Server Components (Default):**
```typescript
// apps/web/src/app/(dashboard)/forecasts/page.tsx
import { ForecastsService } from '@/lib/api-client';
import { ForecastList } from '@/components/organisms/ForecastList';

export default async function ForecastsPage() {
  const forecasts = await ForecastsService.listForecasts({ limit: 20 });

  return (
    <div>
      <h1>Forecasts</h1>
      <ForecastList forecasts={forecasts} />
    </div>
  );
}
```

**Client Components:**
```typescript
// apps/web/src/components/organisms/ForecastList.tsx
'use client';

import { useQuery } from '@tanstack/react-query';
import { ForecastsService } from '@/lib/api-client';
import { ForecastCard } from '@/components/molecules/ForecastCard';

export function ForecastList({ forecasts: initialForecasts }) {
  const { data: forecasts } = useQuery({
    queryKey: ['forecasts'],
    queryFn: () => ForecastsService.listForecasts({ limit: 20 }),
    initialData: initialForecasts,
  });

  return (
    <div className="grid grid-cols-3 gap-6">
      {forecasts?.map(forecast => (
        <ForecastCard key={forecast.id} forecast={forecast} />
      ))}
    </div>
  );
}
```

---

## Testing Standards

### Python Tests (pytest)

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
    assert forecast.confidence == 0.95
```

### Test Fixtures

```python
# apps/api/tests/conftest.py
import pytest
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from src.db.base import Base
from src.models.restaurant import Restaurant

@pytest.fixture
async def db_session():
    """Create test database session."""
    engine = create_async_engine("postgresql+asyncpg://test:test@localhost/test_db")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
```

---

## Code Formatting & Linting

### Python Tools

**pyproject.toml:**
```toml
[tool.black]
line-length = 88
target-version = ['py312']

[tool.ruff]
line-length = 88
select = ["E", "F", "I", "N", "W"]
ignore = ["E501"]

[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

**Run tools:**
```bash
# Format code
black apps/api/src

# Lint code
ruff check apps/api/src

# Type check
mypy apps/api/src

# Run tests
pytest apps/api/tests
```

---

## Git Commit Standards

```
<type>(<scope>): <subject>

<body>

<footer>
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Build/tooling

---

## Code Review Checklist

- [ ] All tests pass (`pytest`)
- [ ] No type errors (`mypy`)
- [ ] No linting errors (`ruff`)
- [ ] Code formatted (`black`)
- [ ] Docstrings added for public functions
- [ ] Error handling implemented
- [ ] Logging added for important operations
- [ ] Security best practices (input validation, auth)
- [ ] Database queries optimized
- [ ] API documented (Pydantic models)

---

**Related:**
- [Tech Stack →](./tech-stack.md)
- [Source Tree →](./source-tree.md)