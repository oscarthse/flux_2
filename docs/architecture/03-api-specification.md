# API Specification

> **Part of:** [Flux Architecture Documentation](./README.md)

---

This section defines all FastAPI routers and endpoints that make up the Flux API. The API is organized into logical routers by domain, with type safety enforced through Pydantic schemas and OpenAPI code generation for the frontend.

### API Architecture Overview

**API Style:** REST + OpenAPI 3.1 (FastAPI)
**Transport:** HTTP (GET, POST, PUT, DELETE) to `/api/v1/[resource]`
**Authentication:** JWT bearer tokens (OAuth2 with Password flow)
**Rate Limiting:** 100 requests/min per user, 1000 requests/min per restaurant
**Caching Strategy:** React Query on frontend, Redis on backend

**Key Design Principles:**
- All endpoints are authenticated by default (use `Depends(get_current_user)`)
- Input/output validation using Pydantic v2 schemas
- Multi-tenant isolation via dependency injection (automatically sets `restaurant_id`)
- Consistent error handling with HTTP status codes and structured error responses
- Pagination using cursor-based approach for large datasets
- Real-time updates via WebSocket endpoints where appropriate
- Auto-generated OpenAPI documentation at `/docs`

### FastAPI Dependencies & Middleware

**Dependency Setup:**

```python
# apps/api/src/dependencies/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from ..config import settings
from ..db.session import get_db
from ..schemas.auth import TokenData, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Verify JWT token and return current user.
    Sets PostgreSQL RLS context variables for multi-tenant isolation.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.ALGORITHM]
        )
        user_id: str = payload.get("sub")
        restaurant_id: str = payload.get("restaurant_id")
        role: str = payload.get("role")

        if user_id is None or restaurant_id is None:
            raise credentials_exception

        token_data = TokenData(
            user_id=user_id,
            restaurant_id=restaurant_id,
            role=role
        )
    except JWTError:
        raise credentials_exception

    # Set PostgreSQL RLS context for multi-tenant isolation
    await db.execute(
        text("SET LOCAL app.current_restaurant_id = :restaurant_id"),
        {"restaurant_id": token_data.restaurant_id}
    )
    await db.execute(
        text("SET LOCAL app.current_user_id = :user_id"),
        {"user_id": token_data.user_id}
    )

    # Fetch user from database
    from ..services.user import UserService
    user_service = UserService(db)
    user = await user_service.get_by_id(token_data.user_id)

    if user is None:
        raise credentials_exception

    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure user account is active."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

def require_role(allowed_roles: list[str]):
    """
    Dependency factory for role-based access control.
    Usage: Depends(require_role(["admin", "manager"]))
    """
    async def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions"
            )
        return current_user
    return role_checker
```

**Middleware:**

```python
# apps/api/src/middleware/rate_limit.py
from fastapi import Request, HTTPException, status
from redis import asyncio as aioredis
import time

class RateLimitMiddleware:
    """
    Rate limiting middleware using Redis.
    - 100 requests/min per user
    - 1000 requests/min per restaurant
    """
    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def __call__(self, request: Request, call_next):
        # Extract user/restaurant from token if present
        user_id = getattr(request.state, 'user_id', None)
        restaurant_id = getattr(request.state, 'restaurant_id', None)

        if user_id:
            # Check user rate limit
            user_key = f"rate_limit:user:{user_id}"
            user_count = await self.redis.incr(user_key)
            if user_count == 1:
                await self.redis.expire(user_key, 60)  # 1 minute window

            if user_count > 100:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="User rate limit exceeded (100 req/min)"
                )

        if restaurant_id:
            # Check restaurant rate limit
            restaurant_key = f"rate_limit:restaurant:{restaurant_id}"
            restaurant_count = await self.redis.incr(restaurant_key)
            if restaurant_count == 1:
                await self.redis.expire(restaurant_key, 60)

            if restaurant_count > 1000:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Restaurant rate limit exceeded (1000 req/min)"
                )

        response = await call_next(request)
        return response
```

**Error Handling:**

```python
# apps/api/src/middleware/error_handler.py
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError
import structlog

logger = structlog.get_logger()

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic validation errors."""
    logger.warning("validation_error", errors=exc.errors(), body=exc.body)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Invalid input data",
            "details": exc.errors()
        }
    )

async def integrity_error_handler(request: Request, exc: IntegrityError):
    """Handle database integrity constraint violations."""
    logger.error("database_integrity_error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={
            "error": "conflict",
            "message": "Database constraint violation",
            "details": str(exc.orig)
        }
    )

async def generic_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler."""
    logger.exception("unhandled_error", error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred"
        }
    )
```

---

## Routers

### 1. Authentication Router

**Base Path:** `/api/v1/auth`
**Description:** User authentication, registration, and token management

```python
# apps/api/src/routers/auth.py
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import timedelta

from ..db.session import get_db
from ..schemas.auth import (
    UserRegisterRequest,
    UserResponse,
    Token,
    PasswordResetRequest,
    PasswordResetConfirm
)
from ..services.auth import AuthService
from ..config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    data: UserRegisterRequest,
    db: AsyncSession = Depends(get_db)
) -> UserResponse:
    """
    Register a new user account.

    Creates user, sends verification email, and returns user object.
    Password must be at least 8 characters with uppercase, lowercase, and number.
    """
    service = AuthService(db)
    user = await service.register_user(
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        restaurant_name=data.restaurant_name
    )
    return user

@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
) -> Token:
    """
    Login with email and password.

    Returns JWT access token (expires in 30 min) and refresh token (expires in 7 days).
    Access token should be sent in Authorization header: `Bearer <token>`
    """
    service = AuthService(db)
    user = await service.authenticate_user(form_data.username, form_data.password)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = service.create_access_token(
        data={
            "sub": str(user.id),
            "restaurant_id": str(user.restaurant_id),
            "role": user.role
        },
        expires_delta=access_token_expires
    )

    refresh_token = service.create_refresh_token(data={"sub": str(user.id)})

    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )

@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
) -> Token:
    """
    Get new access token using refresh token.

    Refresh tokens are valid for 7 days and can only be used once.
    """
    service = AuthService(db)
    new_tokens = await service.refresh_access_token(refresh_token)
    return new_tokens

@router.post("/logout")
async def logout(
    refresh_token: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Logout and invalidate refresh token.

    Access tokens cannot be invalidated (they expire naturally after 30 min).
    """
    service = AuthService(db)
    await service.revoke_refresh_token(refresh_token)
    return {"message": "Successfully logged out"}

@router.post("/password-reset")
async def request_password_reset(
    data: PasswordResetRequest,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Request password reset email.

    Sends email with reset token valid for 1 hour.
    Returns success even if email doesn't exist (security best practice).
    """
    service = AuthService(db)
    await service.request_password_reset(data.email)
    return {"message": "If email exists, password reset link has been sent"}

@router.post("/password-reset/confirm")
async def confirm_password_reset(
    data: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Confirm password reset with token from email.

    Token expires after 1 hour. New password must meet security requirements.
    """
    service = AuthService(db)
    await service.confirm_password_reset(data.token, data.new_password)
    return {"message": "Password successfully reset"}

@router.post("/verify-email/{token}")
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Verify email address with token from registration email.

    Token expires after 24 hours.
    """
    service = AuthService(db)
    await service.verify_email(token)
    return {"message": "Email successfully verified"}
```

---

### 2. Forecasts Router

**Base Path:** `/api/v1/forecasts`
**Description:** Demand forecasting management and predictions

```python
# apps/api/src/routers/forecasts.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date, datetime

from ..db.session import get_db
from ..dependencies.auth import get_current_active_user
from ..schemas.auth import User
from ..schemas.forecasts import (
    ForecastResponse,
    ForecastCreateRequest,
    ForecastUpdateRequest,
    ForecastPredictionRequest,
    ForecastPredictionResponse,
    ForecastAccuracyMetrics,
    ForecastListResponse
)
from ..services.forecasts import ForecastService

router = APIRouter(
    prefix="/api/v1/forecasts",
    tags=["forecasts"],
    dependencies=[Depends(get_current_active_user)]
)

@router.get("", response_model=ForecastListResponse)
async def list_forecasts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    category: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ForecastListResponse:
    """
    List all forecasts for the current restaurant.

    Supports filtering by:
    - category: forecast category (e.g., 'revenue', 'labor', 'inventory')
    - date_from/date_to: forecast date range

    Returns paginated results with cursor for next page.
    """
    service = ForecastService(db)
    forecasts, total = await service.list_forecasts(
        restaurant_id=current_user.restaurant_id,
        skip=skip,
        limit=limit,
        category=category,
        date_from=date_from,
        date_to=date_to
    )

    return ForecastListResponse(
        items=forecasts,
        total=total,
        skip=skip,
        limit=limit
    )

@router.get("/{forecast_id}", response_model=ForecastResponse)
async def get_forecast(
    forecast_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ForecastResponse:
    """
    Get a specific forecast by ID.

    Returns 404 if forecast doesn't exist or belongs to different restaurant.
    """
    service = ForecastService(db)
    forecast = await service.get_forecast(forecast_id, current_user.restaurant_id)

    if not forecast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forecast not found"
        )

    return forecast

@router.post("", response_model=ForecastResponse, status_code=status.HTTP_201_CREATED)
async def create_forecast(
    data: ForecastCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ForecastResponse:
    """
    Create a new forecast configuration.

    Triggers async model training job if training_config is provided.
    """
    service = ForecastService(db)
    forecast = await service.create_forecast(
        restaurant_id=current_user.restaurant_id,
        created_by=current_user.id,
        data=data
    )

    return forecast

@router.put("/{forecast_id}", response_model=ForecastResponse)
async def update_forecast(
    forecast_id: UUID,
    data: ForecastUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ForecastResponse:
    """
    Update an existing forecast configuration.

    Re-trains model if training_config changes.
    """
    service = ForecastService(db)
    forecast = await service.update_forecast(
        forecast_id=forecast_id,
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    if not forecast:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forecast not found"
        )

    return forecast

@router.delete("/{forecast_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_forecast(
    forecast_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> None:
    """
    Delete a forecast.

    Cascades to delete all predictions and training jobs.
    Requires 'admin' or 'manager' role.
    """
    if current_user.role not in ["admin", "manager"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions"
        )

    service = ForecastService(db)
    success = await service.delete_forecast(forecast_id, current_user.restaurant_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Forecast not found"
        )

@router.post("/{forecast_id}/predict", response_model=ForecastPredictionResponse)
async def get_prediction(
    forecast_id: UUID,
    data: ForecastPredictionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ForecastPredictionResponse:
    """
    Get forecast prediction for a specific date range.

    Returns cached predictions if available and fresh (< 1 hour old).
    Otherwise triggers new prediction job.

    Response includes:
    - predictions: time-series data points
    - confidence_intervals: upper/lower bounds
    - metadata: model version, generated_at, etc.
    """
    service = ForecastService(db)
    prediction = await service.get_prediction(
        forecast_id=forecast_id,
        restaurant_id=current_user.restaurant_id,
        start_date=data.start_date,
        end_date=data.end_date,
        granularity=data.granularity
    )

    return prediction

@router.get("/{forecast_id}/accuracy", response_model=ForecastAccuracyMetrics)
async def get_accuracy_metrics(
    forecast_id: UUID,
    days_back: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ForecastAccuracyMetrics:
    """
    Calculate forecast accuracy metrics.

    Compares historical predictions vs actual values for the last N days.

    Returns:
    - MAPE (Mean Absolute Percentage Error)
    - RMSE (Root Mean Squared Error)
    - MAE (Mean Absolute Error)
    - Accuracy score (0-100%)
    """
    service = ForecastService(db)
    metrics = await service.calculate_accuracy(
        forecast_id=forecast_id,
        restaurant_id=current_user.restaurant_id,
        days_back=days_back
    )

    if not metrics:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Insufficient data to calculate accuracy"
        )

    return metrics

@router.post("/{forecast_id}/retrain", status_code=status.HTTP_202_ACCEPTED)
async def retrain_model(
    forecast_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Trigger model retraining job.

    Returns 202 Accepted with job_id for tracking progress.
    Training typically takes 5-30 minutes depending on data volume.
    """
    service = ForecastService(db)
    job_id = await service.trigger_retraining(
        forecast_id=forecast_id,
        restaurant_id=current_user.restaurant_id
    )

    return {
        "message": "Training job started",
        "job_id": str(job_id),
        "status_endpoint": f"/api/v1/jobs/{job_id}"
    }
```

---

### 3. Menu Items Router

**Base Path:** `/api/v1/menu-items`
**Description:** Menu item management and categorization

```python
# apps/api/src/routers/menu_items.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ..db.session import get_db
from ..dependencies.auth import get_current_active_user, require_role
from ..schemas.auth import User
from ..schemas.menu_items import (
    MenuItemResponse,
    MenuItemCreateRequest,
    MenuItemUpdateRequest,
    MenuItemListResponse,
    MenuItemBulkImportRequest,
    MenuItemBulkImportResponse
)
from ..services.menu_items import MenuItemService

router = APIRouter(
    prefix="/api/v1/menu-items",
    tags=["menu-items"],
    dependencies=[Depends(get_current_active_user)]
)

@router.get("", response_model=MenuItemListResponse)
async def list_menu_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    category: str | None = None,
    search: str | None = None,
    is_active: bool | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> MenuItemListResponse:
    """
    List all menu items for the restaurant.

    Supports filtering by:
    - category: menu category name
    - search: fuzzy search on item name
    - is_active: filter active/inactive items
    """
    service = MenuItemService(db)
    items, total = await service.list_items(
        restaurant_id=current_user.restaurant_id,
        skip=skip,
        limit=limit,
        category=category,
        search=search,
        is_active=is_active
    )

    return MenuItemListResponse(items=items, total=total, skip=skip, limit=limit)

@router.get("/{item_id}", response_model=MenuItemResponse)
async def get_menu_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> MenuItemResponse:
    """Get a specific menu item by ID."""
    service = MenuItemService(db)
    item = await service.get_item(item_id, current_user.restaurant_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    return item

@router.post("", response_model=MenuItemResponse, status_code=status.HTTP_201_CREATED)
async def create_menu_item(
    data: MenuItemCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> MenuItemResponse:
    """
    Create a new menu item.

    Requires 'admin' or 'manager' role.
    """
    service = MenuItemService(db)
    item = await service.create_item(
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    return item

@router.put("/{item_id}", response_model=MenuItemResponse)
async def update_menu_item(
    item_id: UUID,
    data: MenuItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> MenuItemResponse:
    """
    Update an existing menu item.

    Requires 'admin' or 'manager' role.
    """
    service = MenuItemService(db)
    item = await service.update_item(
        item_id=item_id,
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    return item

@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_menu_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
) -> None:
    """
    Delete a menu item.

    Requires 'admin' role. Soft delete (sets is_active=false).
    """
    service = MenuItemService(db)
    success = await service.delete_item(item_id, current_user.restaurant_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

@router.post("/bulk-import", response_model=MenuItemBulkImportResponse)
async def bulk_import_menu_items(
    data: MenuItemBulkImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> MenuItemBulkImportResponse:
    """
    Bulk import menu items from array.

    Validates all items before importing. Returns summary of created/updated/failed items.
    """
    service = MenuItemService(db)
    result = await service.bulk_import(
        restaurant_id=current_user.restaurant_id,
        items=data.items
    )

    return result

@router.post("/import-csv", response_model=MenuItemBulkImportResponse)
async def import_menu_items_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> MenuItemBulkImportResponse:
    """
    Import menu items from CSV file.

    CSV format:
    name,category,price,cost,description,is_active
    Burger,Entrees,12.99,4.50,Classic beef burger,true
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be CSV format"
        )

    service = MenuItemService(db)
    result = await service.import_from_csv(
        restaurant_id=current_user.restaurant_id,
        file=file
    )

    return result
```

---

### 4. Sales Data Router

**Base Path:** `/api/v1/sales`
**Description:** Sales data ingestion and querying

```python
# apps/api/src/routers/sales.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, date

from ..db.session import get_db
from ..dependencies.auth import get_current_active_user
from ..schemas.auth import User
from ..schemas.sales import (
    SalesDataResponse,
    SalesDataCreateRequest,
    SalesDataBulkCreateRequest,
    SalesAggregateResponse,
    SalesListResponse
)
from ..services.sales import SalesService

router = APIRouter(
    prefix="/api/v1/sales",
    tags=["sales"],
    dependencies=[Depends(get_current_active_user)]
)

@router.get("", response_model=SalesListResponse)
async def list_sales(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    menu_item_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> SalesListResponse:
    """
    List sales transactions.

    Supports filtering by:
    - date_from/date_to: transaction timestamp range
    - menu_item_id: specific menu item

    Uses TimescaleDB hypertable for efficient time-series queries.
    """
    service = SalesService(db)
    sales, total = await service.list_sales(
        restaurant_id=current_user.restaurant_id,
        skip=skip,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        menu_item_id=menu_item_id
    )

    return SalesListResponse(items=sales, total=total, skip=skip, limit=limit)

@router.post("", response_model=SalesDataResponse, status_code=status.HTTP_201_CREATED)
async def create_sale(
    data: SalesDataCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> SalesDataResponse:
    """
    Record a single sales transaction.

    Typically called by POS webhook integrations.
    """
    service = SalesService(db)
    sale = await service.create_sale(
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    return sale

@router.post("/bulk", response_model=dict, status_code=status.HTTP_201_CREATED)
async def bulk_create_sales(
    data: SalesDataBulkCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> dict:
    """
    Bulk create sales transactions.

    Optimized for importing historical data or batch processing.
    Uses COPY for efficient bulk inserts into TimescaleDB.
    """
    service = SalesService(db)
    created_count = await service.bulk_create_sales(
        restaurant_id=current_user.restaurant_id,
        sales=data.sales
    )

    return {
        "created": created_count,
        "message": f"Successfully created {created_count} sales records"
    }

@router.get("/aggregate", response_model=SalesAggregateResponse)
async def get_sales_aggregates(
    date_from: date,
    date_to: date,
    granularity: str = Query("day", regex="^(hour|day|week|month)$"),
    group_by: str | None = Query(None, regex="^(category|menu_item|hour_of_day|day_of_week)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> SalesAggregateResponse:
    """
    Get aggregated sales metrics.

    Leverages TimescaleDB continuous aggregates for fast queries.

    Parameters:
    - granularity: time bucket size (hour, day, week, month)
    - group_by: optional grouping dimension (category, menu_item, hour_of_day, day_of_week)

    Returns:
    - total_revenue
    - transaction_count
    - items_sold
    - average_transaction_value
    - time_series data points
    """
    service = SalesService(db)
    aggregates = await service.get_aggregates(
        restaurant_id=current_user.restaurant_id,
        date_from=date_from,
        date_to=date_to,
        granularity=granularity,
        group_by=group_by
    )

    return aggregates

@router.get("/top-items", response_model=list[dict])
async def get_top_selling_items(
    date_from: date,
    date_to: date,
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> list[dict]:
    """
    Get top-selling menu items for a date range.

    Returns items ranked by total revenue.
    """
    service = SalesService(db)
    top_items = await service.get_top_items(
        restaurant_id=current_user.restaurant_id,
        date_from=date_from,
        date_to=date_to,
        limit=limit
    )

    return top_items
```

---

### 5. Inventory Router

**Base Path:** `/api/v1/inventory`
**Description:** Inventory tracking and optimization

```python
# apps/api/src/routers/inventory.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date

from ..db.session import get_db
from ..dependencies.auth import get_current_active_user, require_role
from ..schemas.auth import User
from ..schemas.inventory import (
    InventoryItemResponse,
    InventoryItemCreateRequest,
    InventoryItemUpdateRequest,
    InventoryTransactionResponse,
    InventoryTransactionCreateRequest,
    InventoryListResponse,
    InventoryAlertResponse,
    InventoryOptimizationRequest,
    InventoryOptimizationResponse
)
from ..services.inventory import InventoryService

router = APIRouter(
    prefix="/api/v1/inventory",
    tags=["inventory"],
    dependencies=[Depends(get_current_active_user)]
)

@router.get("/items", response_model=InventoryListResponse)
async def list_inventory_items(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    category: str | None = None,
    low_stock_only: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> InventoryListResponse:
    """
    List all inventory items.

    Supports filtering by:
    - category: ingredient category
    - low_stock_only: only items below reorder threshold
    """
    service = InventoryService(db)
    items, total = await service.list_items(
        restaurant_id=current_user.restaurant_id,
        skip=skip,
        limit=limit,
        category=category,
        low_stock_only=low_stock_only
    )

    return InventoryListResponse(items=items, total=total, skip=skip, limit=limit)

@router.get("/items/{item_id}", response_model=InventoryItemResponse)
async def get_inventory_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> InventoryItemResponse:
    """Get a specific inventory item by ID."""
    service = InventoryService(db)
    item = await service.get_item(item_id, current_user.restaurant_id)

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )

    return item

@router.post("/items", response_model=InventoryItemResponse, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(
    data: InventoryItemCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> InventoryItemResponse:
    """
    Create a new inventory item.

    Requires 'admin' or 'manager' role.
    """
    service = InventoryService(db)
    item = await service.create_item(
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    return item

@router.put("/items/{item_id}", response_model=InventoryItemResponse)
async def update_inventory_item(
    item_id: UUID,
    data: InventoryItemUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> InventoryItemResponse:
    """
    Update an inventory item.

    Requires 'admin' or 'manager' role.
    """
    service = InventoryService(db)
    item = await service.update_item(
        item_id=item_id,
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Inventory item not found"
        )

    return item

@router.post("/transactions", response_model=InventoryTransactionResponse, status_code=status.HTTP_201_CREATED)
async def record_inventory_transaction(
    data: InventoryTransactionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> InventoryTransactionResponse:
    """
    Record an inventory transaction (purchase, usage, adjustment, waste).

    Automatically updates inventory levels and triggers reorder alerts if needed.
    """
    service = InventoryService(db)
    transaction = await service.create_transaction(
        restaurant_id=current_user.restaurant_id,
        user_id=current_user.id,
        data=data
    )

    return transaction

@router.get("/alerts", response_model=list[InventoryAlertResponse])
async def get_inventory_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> list[InventoryAlertResponse]:
    """
    Get active inventory alerts.

    Returns items that are:
    - Below reorder threshold (low stock)
    - Expired or expiring soon (< 7 days)
    - Overstocked (> max stock level)
    """
    service = InventoryService(db)
    alerts = await service.get_alerts(restaurant_id=current_user.restaurant_id)

    return alerts

@router.post("/optimize", response_model=InventoryOptimizationResponse)
async def optimize_inventory(
    data: InventoryOptimizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> InventoryOptimizationResponse:
    """
    Get ML-powered inventory optimization recommendations.

    Analyzes:
    - Historical usage patterns
    - Forecast demand
    - Lead times
    - Shelf life

    Returns:
    - Recommended order quantities
    - Optimal reorder points
    - Expected cost savings
    """
    service = InventoryService(db)
    optimization = await service.optimize_inventory(
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    return optimization
```

---

### 6. Labor Management Router

**Base Path:** `/api/v1/labor`
**Description:** Employee scheduling and labor cost optimization

```python
# apps/api/src/routers/labor.py
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import datetime, date

from ..db.session import get_db
from ..dependencies.auth import get_current_active_user, require_role
from ..schemas.auth import User
from ..schemas.labor import (
    EmployeeResponse,
    EmployeeCreateRequest,
    EmployeeUpdateRequest,
    ShiftResponse,
    ShiftCreateRequest,
    ShiftUpdateRequest,
    ShiftListResponse,
    TimeOffRequestResponse,
    TimeOffRequestCreateRequest,
    LaborCostSummaryResponse,
    ScheduleOptimizationRequest,
    ScheduleOptimizationResponse
)
from ..services.labor import LaborService

router = APIRouter(
    prefix="/api/v1/labor",
    tags=["labor"],
    dependencies=[Depends(get_current_active_user)]
)

# Employee endpoints
@router.get("/employees", response_model=list[EmployeeResponse])
async def list_employees(
    is_active: bool | None = None,
    role: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> list[EmployeeResponse]:
    """
    List all employees for the restaurant.

    Supports filtering by is_active and role.
    """
    service = LaborService(db)
    employees = await service.list_employees(
        restaurant_id=current_user.restaurant_id,
        is_active=is_active,
        role=role
    )

    return employees

@router.post("/employees", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    data: EmployeeCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> EmployeeResponse:
    """
    Create a new employee.

    Requires 'admin' or 'manager' role.
    """
    service = LaborService(db)
    employee = await service.create_employee(
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    return employee

# Shift endpoints
@router.get("/shifts", response_model=ShiftListResponse)
async def list_shifts(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    date_from: date | None = None,
    date_to: date | None = None,
    employee_id: UUID | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ShiftListResponse:
    """
    List all shifts for the restaurant.

    Supports filtering by:
    - date_from/date_to: shift date range
    - employee_id: specific employee
    """
    service = LaborService(db)
    shifts, total = await service.list_shifts(
        restaurant_id=current_user.restaurant_id,
        skip=skip,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
        employee_id=employee_id
    )

    return ShiftListResponse(items=shifts, total=total, skip=skip, limit=limit)

@router.post("/shifts", response_model=ShiftResponse, status_code=status.HTTP_201_CREATED)
async def create_shift(
    data: ShiftCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> ShiftResponse:
    """
    Create a new shift.

    Validates:
    - Employee availability
    - No overlapping shifts
    - Labor law compliance (max hours, breaks, etc.)

    Requires 'admin' or 'manager' role.
    """
    service = LaborService(db)
    shift = await service.create_shift(
        restaurant_id=current_user.restaurant_id,
        created_by=current_user.id,
        data=data
    )

    return shift

@router.put("/shifts/{shift_id}", response_model=ShiftResponse)
async def update_shift(
    shift_id: UUID,
    data: ShiftUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> ShiftResponse:
    """
    Update an existing shift.

    Re-validates constraints.
    Requires 'admin' or 'manager' role.
    """
    service = LaborService(db)
    shift = await service.update_shift(
        shift_id=shift_id,
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    if not shift:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shift not found"
        )

    return shift

@router.delete("/shifts/{shift_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shift(
    shift_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> None:
    """
    Delete a shift.

    Only allows deleting future shifts.
    Requires 'admin' or 'manager' role.
    """
    service = LaborService(db)
    success = await service.delete_shift(shift_id, current_user.restaurant_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Shift not found or already in the past"
        )

# Labor analytics endpoints
@router.get("/costs/summary", response_model=LaborCostSummaryResponse)
async def get_labor_cost_summary(
    date_from: date,
    date_to: date,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> LaborCostSummaryResponse:
    """
    Get labor cost summary for a date range.

    Returns:
    - Total labor cost
    - Labor cost as % of revenue
    - Hours worked by role
    - Overtime hours/cost
    - Average hourly cost
    """
    service = LaborService(db)
    summary = await service.get_cost_summary(
        restaurant_id=current_user.restaurant_id,
        date_from=date_from,
        date_to=date_to
    )

    return summary

@router.post("/optimize-schedule", response_model=ScheduleOptimizationResponse)
async def optimize_schedule(
    data: ScheduleOptimizationRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> ScheduleOptimizationResponse:
    """
    Get ML-powered schedule optimization recommendations.

    Analyzes:
    - Forecast demand
    - Employee availability and preferences
    - Labor costs
    - Labor laws and compliance

    Returns:
    - Recommended shift assignments
    - Expected cost savings
    - Coverage gaps
    """
    service = LaborService(db)
    optimization = await service.optimize_schedule(
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    return optimization

# Time-off endpoints
@router.post("/time-off", response_model=TimeOffRequestResponse, status_code=status.HTTP_201_CREATED)
async def request_time_off(
    data: TimeOffRequestCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> TimeOffRequestResponse:
    """
    Request time off.

    Employees can request time off for themselves.
    """
    service = LaborService(db)
    request = await service.create_time_off_request(
        restaurant_id=current_user.restaurant_id,
        employee_id=current_user.employee_id,
        data=data
    )

    return request

@router.put("/time-off/{request_id}/approve", response_model=TimeOffRequestResponse)
async def approve_time_off(
    request_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> TimeOffRequestResponse:
    """
    Approve time-off request.

    Requires 'admin' or 'manager' role.
    """
    service = LaborService(db)
    request = await service.approve_time_off(
        request_id=request_id,
        restaurant_id=current_user.restaurant_id,
        approved_by=current_user.id
    )

    if not request:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Time-off request not found"
        )

    return request
```

---

### 7. POS Integration Router

**Base Path:** `/api/v1/pos`
**Description:** POS system integration and webhook handling

```python
# apps/api/src/routers/pos.py
from fastapi import APIRouter, Depends, HTTPException, status, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from ..db.session import get_db
from ..dependencies.auth import get_current_active_user, require_role
from ..schemas.auth import User
from ..schemas.pos import (
    POSConnectionResponse,
    POSConnectionCreateRequest,
    POSConnectionUpdateRequest,
    POSSyncStatusResponse,
    POSWebhookPayload
)
from ..services.pos import POSService

router = APIRouter(
    prefix="/api/v1/pos",
    tags=["pos"],
    dependencies=[Depends(get_current_active_user)]
)

@router.get("/connections", response_model=list[POSConnectionResponse])
async def list_pos_connections(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> list[POSConnectionResponse]:
    """
    List all POS connections for the restaurant.

    Supports: Toast, Square, Lightspeed, Clover, Revel
    """
    service = POSService(db)
    connections = await service.list_connections(
        restaurant_id=current_user.restaurant_id
    )

    return connections

@router.post("/connections", response_model=POSConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_pos_connection(
    data: POSConnectionCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
) -> POSConnectionResponse:
    """
    Create a new POS connection.

    Initiates OAuth flow for supported providers.
    Requires 'admin' role.
    """
    service = POSService(db)
    connection = await service.create_connection(
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    return connection

@router.put("/connections/{connection_id}", response_model=POSConnectionResponse)
async def update_pos_connection(
    connection_id: UUID,
    data: POSConnectionUpdateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
) -> POSConnectionResponse:
    """
    Update POS connection settings.

    Requires 'admin' role.
    """
    service = POSService(db)
    connection = await service.update_connection(
        connection_id=connection_id,
        restaurant_id=current_user.restaurant_id,
        data=data
    )

    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="POS connection not found"
        )

    return connection

@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pos_connection(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin"]))
) -> None:
    """
    Delete a POS connection.

    Requires 'admin' role.
    """
    service = POSService(db)
    success = await service.delete_connection(connection_id, current_user.restaurant_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="POS connection not found"
        )

@router.post("/connections/{connection_id}/sync", response_model=POSSyncStatusResponse, status_code=status.HTTP_202_ACCEPTED)
async def trigger_pos_sync(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(["admin", "manager"]))
) -> POSSyncStatusResponse:
    """
    Trigger manual sync from POS system.

    Fetches:
    - Menu items
    - Sales data
    - Inventory levels (if supported)

    Returns 202 Accepted with job_id for tracking progress.
    """
    service = POSService(db)
    sync_status = await service.trigger_sync(
        connection_id=connection_id,
        restaurant_id=current_user.restaurant_id
    )

    return sync_status

@router.get("/connections/{connection_id}/sync-status", response_model=POSSyncStatusResponse)
async def get_sync_status(
    connection_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> POSSyncStatusResponse:
    """
    Get current sync status for a POS connection.

    Returns:
    - Last sync timestamp
    - Sync status (idle, syncing, error)
    - Records synced
    - Error details (if any)
    """
    service = POSService(db)
    status = await service.get_sync_status(
        connection_id=connection_id,
        restaurant_id=current_user.restaurant_id
    )

    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="POS connection not found"
        )

    return status

@router.post("/webhooks/{provider}", status_code=status.HTTP_200_OK, include_in_schema=False)
async def handle_pos_webhook(
    provider: str,
    request: Request,
    x_webhook_signature: str | None = Header(None),
    db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Handle incoming webhooks from POS providers.

    Validates webhook signature and processes events.
    NOT authenticated (uses webhook signature instead).
    """
    service = POSService(db)

    # Read raw body for signature verification
    body = await request.body()

    # Verify webhook signature
    is_valid = await service.verify_webhook_signature(
        provider=provider,
        signature=x_webhook_signature,
        body=body
    )

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid webhook signature"
        )

    # Parse and process webhook
    payload = await request.json()
    await service.process_webhook(provider=provider, payload=payload)

    return {"status": "ok"}
```

---

### 8. Reports Router

**Base Path:** `/api/v1/reports`
**Description:** Business intelligence reports and exports

```python
# apps/api/src/routers/reports.py
from fastapi import APIRouter, Depends, HTTPException, status, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from datetime import date
from io import BytesIO

from ..db.session import get_db
from ..dependencies.auth import get_current_active_user
from ..schemas.auth import User
from ..schemas.reports import (
    ReportResponse,
    ReportCreateRequest,
    ReportListResponse,
    ReportExportRequest
)
from ..services.reports import ReportService

router = APIRouter(
    prefix="/api/v1/reports",
    tags=["reports"],
    dependencies=[Depends(get_current_active_user)]
)

@router.get("", response_model=ReportListResponse)
async def list_reports(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    report_type: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ReportListResponse:
    """
    List all saved reports.

    Report types:
    - sales_summary
    - labor_analysis
    - inventory_valuation
    - menu_performance
    - forecast_accuracy
    """
    service = ReportService(db)
    reports, total = await service.list_reports(
        restaurant_id=current_user.restaurant_id,
        skip=skip,
        limit=limit,
        report_type=report_type
    )

    return ReportListResponse(items=reports, total=total, skip=skip, limit=limit)

@router.get("/{report_id}", response_model=ReportResponse)
async def get_report(
    report_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ReportResponse:
    """Get a specific report by ID."""
    service = ReportService(db)
    report = await service.get_report(report_id, current_user.restaurant_id)

    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    return report

@router.post("", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def create_report(
    data: ReportCreateRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> ReportResponse:
    """
    Generate a new report.

    Heavy reports run in background and notify when complete.
    """
    service = ReportService(db)
    report = await service.create_report(
        restaurant_id=current_user.restaurant_id,
        created_by=current_user.id,
        data=data,
        background_tasks=background_tasks
    )

    return report

@router.post("/{report_id}/export")
async def export_report(
    report_id: UUID,
    format: str = Query("csv", regex="^(csv|xlsx|pdf)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
) -> StreamingResponse:
    """
    Export report to file.

    Formats: csv, xlsx, pdf
    Returns file download stream.
    """
    service = ReportService(db)
    file_data, filename, media_type = await service.export_report(
        report_id=report_id,
        restaurant_id=current_user.restaurant_id,
        format=format
    )

    if not file_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Report not found"
        )

    return StreamingResponse(
        BytesIO(file_data),
        media_type=media_type,
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
```

---

### 9. WebSocket Endpoints

**Base Path:** `/ws`
**Description:** Real-time updates via WebSocket

```python
# apps/api/src/routers/websocket.py
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import structlog

from ..db.session import get_db
from ..services.websocket import WebSocketManager

router = APIRouter(tags=["websocket"])
logger = structlog.get_logger()

# Global WebSocket manager
ws_manager = WebSocketManager()

@router.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    """
    WebSocket endpoint for real-time updates.

    Authenticate with JWT token via query param: /ws?token=<jwt>

    Client receives:
    - forecast_updated: New forecast data available
    - sales_transaction: New sales transaction recorded
    - inventory_alert: Low stock or other inventory alert
    - shift_updated: Schedule change

    Client can send:
    - subscribe: {"type": "subscribe", "channels": ["forecasts", "sales"]}
    - unsubscribe: {"type": "unsubscribe", "channels": ["sales"]}
    - ping: {"type": "ping"} -> receives {"type": "pong"}
    """
    # Verify token and extract user info
    from ..dependencies.auth import get_current_user
    try:
        # Simplified auth for WebSocket (decode token manually)
        from jose import jwt
        from ..config import settings

        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("sub")
        restaurant_id = payload.get("restaurant_id")

        if not user_id or not restaurant_id:
            await websocket.close(code=1008, reason="Invalid token")
            return
    except Exception:
        await websocket.close(code=1008, reason="Authentication failed")
        return

    # Accept connection
    await ws_manager.connect(websocket, restaurant_id, user_id)
    logger.info("websocket_connected", restaurant_id=restaurant_id, user_id=user_id)

    try:
        while True:
            # Receive messages from client
            data = await websocket.receive_json()

            message_type = data.get("type")

            if message_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif message_type == "subscribe":
                channels = data.get("channels", [])
                await ws_manager.subscribe(websocket, channels)
                await websocket.send_json({
                    "type": "subscribed",
                    "channels": channels
                })

            elif message_type == "unsubscribe":
                channels = data.get("channels", [])
                await ws_manager.unsubscribe(websocket, channels)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "channels": channels
                })

    except WebSocketDisconnect:
        ws_manager.disconnect(websocket, restaurant_id)
        logger.info("websocket_disconnected", restaurant_id=restaurant_id, user_id=user_id)
```

---

## Pydantic Schemas

All request/response models are defined using Pydantic v2 schemas in `apps/api/src/schemas/`.

**Example Schema File:**

```python
# apps/api/src/schemas/forecasts.py
from pydantic import BaseModel, Field, ConfigDict
from uuid import UUID
from datetime import datetime, date
from typing import Literal

class ForecastBase(BaseModel):
    """Base forecast fields."""
    name: str = Field(..., min_length=1, max_length=255)
    category: str = Field(..., regex="^(revenue|labor|inventory)$")
    description: str | None = None

class ForecastCreateRequest(ForecastBase):
    """Request to create a new forecast."""
    model_type: str = Field("prophet", regex="^(prophet|xgboost|arima)$")
    training_config: dict | None = None

class ForecastUpdateRequest(BaseModel):
    """Request to update a forecast."""
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    is_active: bool | None = None
    training_config: dict | None = None

class ForecastResponse(ForecastBase):
    """Forecast response model."""
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    restaurant_id: UUID
    created_by: UUID
    model_type: str
    model_version: str | None
    last_trained_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime

class ForecastListResponse(BaseModel):
    """Paginated forecast list response."""
    items: list[ForecastResponse]
    total: int
    skip: int
    limit: int

class ForecastPredictionRequest(BaseModel):
    """Request for forecast predictions."""
    start_date: date
    end_date: date
    granularity: Literal["hour", "day", "week", "month"] = "day"

class ForecastDataPoint(BaseModel):
    """Single forecast data point."""
    timestamp: datetime
    value: float
    lower_bound: float
    upper_bound: float

class ForecastPredictionResponse(BaseModel):
    """Forecast prediction response."""
    forecast_id: UUID
    predictions: list[ForecastDataPoint]
    model_version: str
    generated_at: datetime
    granularity: str

class ForecastAccuracyMetrics(BaseModel):
    """Forecast accuracy metrics."""
    forecast_id: UUID
    mape: float = Field(..., description="Mean Absolute Percentage Error")
    rmse: float = Field(..., description="Root Mean Squared Error")
    mae: float = Field(..., description="Mean Absolute Error")
    accuracy_score: float = Field(..., ge=0, le=100, description="Accuracy percentage (0-100)")
    evaluated_period_days: int
    data_points_evaluated: int
```

---

## OpenAPI Code Generation

The FastAPI app automatically generates an OpenAPI 3.1 schema at `/openapi.json`.

**Generate TypeScript client for frontend:**

```bash
# From frontend directory
npx openapi-typescript-codegen \
  --input http://localhost:8000/openapi.json \
  --output ./src/lib/api-client \
  --client axios

# Or using openapi-typescript for types only
npx openapi-typescript http://localhost:8000/openapi.json \
  --output ./src/lib/api-types.ts
```

**Frontend usage:**

```typescript
// Auto-generated client
import { ForecastsService } from '@/lib/api-client';

// Type-safe API calls
const forecasts = await ForecastsService.listForecasts({
  limit: 20,
  category: 'revenue'
});

// TypeScript knows the response type!
forecasts.items.forEach(forecast => {
  console.log(forecast.name); // Autocomplete works!
});
```

---

## Error Response Format

All API errors follow a consistent format:

```json
{
  "error": "validation_error",
  "message": "Invalid input data",
  "details": [
    {
      "loc": ["body", "email"],
      "msg": "value is not a valid email address",
      "type": "value_error.email"
    }
  ]
}
```

**HTTP Status Codes:**
- `200` - OK (successful GET, PUT, DELETE)
- `201` - Created (successful POST)
- `202` - Accepted (async operation started)
- `204` - No Content (successful DELETE)
- `400` - Bad Request (client error)
- `401` - Unauthorized (missing/invalid auth)
- `403` - Forbidden (insufficient permissions)
- `404` - Not Found
- `409` - Conflict (duplicate, constraint violation)
- `422` - Unprocessable Entity (validation error)
- `429` - Too Many Requests (rate limit exceeded)
- `500` - Internal Server Error

---

## API Versioning

All endpoints are prefixed with `/api/v1/`.

Future breaking changes will use `/api/v2/`, etc.

Non-breaking changes (new optional fields, new endpoints) can be added to `/api/v1/`.

---

**Related:**
- [Backend Architecture →](./09-backend-architecture.md)
- [Database Schema →](./07-database-schema.md)
- [Security & Compliance →](./11-security-compliance.md)
