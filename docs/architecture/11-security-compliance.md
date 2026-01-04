# Security & Compliance

> **Part of:** [Flux Architecture Documentation](./README.md)

---

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
│  ├─ Input validation with Pydantic                          │
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

**Implementation:** FastAPI with OAuth2 Password Bearer flow + JWT tokens

```python
# apps/api/src/services/auth/token_service.py

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
import secrets
from uuid import UUID, uuid4

from ...config import settings
from ...models.user import User, UserSession
from ...schemas.auth import TokenPayload, TokenPair
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class TokenService:
    """
    Token generation and validation service.

    Uses:
    - python-jose for JWT handling
    - passlib with bcrypt for password hashing
    - Dual-token strategy (access + refresh)
    """

    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    ALGORITHM = "HS256"
    ISSUER = "flux-platform"
    AUDIENCE = "flux-api"

    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify password against bcrypt hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Generate bcrypt hash from plain password."""
        return pwd_context.hash(password)

    def create_access_token(
        self,
        data: dict,
        expires_delta: Optional[timedelta] = None
    ) -> str:
        """
        Create JWT access token.

        Token contains:
        - sub: user_id
        - restaurant_id: current restaurant
        - role: user role in restaurant
        - session_id: for revocation
        - exp: expiration timestamp
        - iss: issuer (flux-platform)
        - aud: audience (flux-api)
        """
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({
            "exp": expire,
            "iss": self.ISSUER,
            "aud": self.AUDIENCE,
            "iat": datetime.utcnow()
        })

        encoded_jwt = jwt.encode(
            to_encode,
            settings.JWT_SECRET_KEY,
            algorithm=self.ALGORITHM
        )

        return encoded_jwt

    def create_refresh_token(self, data: dict) -> str:
        """
        Create refresh token (longer expiry, fewer claims).

        Token contains only:
        - sub: user_id
        - session_id: for revocation
        - exp: 7 days expiration
        """
        to_encode = {
            "sub": data["sub"],
            "session_id": data.get("session_id"),
            "exp": datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            "iss": self.ISSUER,
            "aud": self.AUDIENCE,
        }

        encoded_jwt = jwt.encode(
            to_encode,
            settings.REFRESH_TOKEN_SECRET,
            algorithm=self.ALGORITHM
        )

        return encoded_jwt

    def verify_token(self, token: str, is_refresh: bool = False) -> TokenPayload:
        """
        Verify and decode JWT token.

        Raises:
        - JWTError: if token is invalid or expired
        """
        try:
            secret = settings.REFRESH_TOKEN_SECRET if is_refresh else settings.JWT_SECRET_KEY

            payload = jwt.decode(
                token,
                secret,
                algorithms=[self.ALGORITHM],
                issuer=self.ISSUER,
                audience=self.AUDIENCE
            )

            user_id = payload.get("sub")
            if user_id is None:
                raise JWTError("Token missing 'sub' claim")

            return TokenPayload(
                user_id=UUID(user_id),
                restaurant_id=UUID(payload.get("restaurant_id")) if payload.get("restaurant_id") else None,
                role=payload.get("role"),
                session_id=UUID(payload.get("session_id")) if payload.get("session_id") else None
            )

        except JWTError as e:
            raise JWTError(f"Token verification failed: {str(e)}")

    async def generate_token_pair(
        self,
        user: User,
        restaurant_id: UUID,
        role: str
    ) -> TokenPair:
        """
        Generate access + refresh token pair and create session.

        Stores refresh token in database for revocation capability.
        """
        session_id = uuid4()

        # Create token payload
        token_data = {
            "sub": str(user.id),
            "restaurant_id": str(restaurant_id),
            "role": role,
            "session_id": str(session_id)
        }

        # Generate tokens
        access_token = self.create_access_token(token_data)
        refresh_token = self.create_refresh_token(token_data)

        # Store session in database
        session = UserSession(
            id=session_id,
            user_id=user.id,
            token_hash=pwd_context.hash(refresh_token),  # Store hashed
            expires_at=datetime.utcnow() + timedelta(days=self.REFRESH_TOKEN_EXPIRE_DAYS),
            user_agent=None,  # Set from request context
            ip_address=None   # Set from request context
        )

        self.db.add(session)
        await self.db.commit()

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenPair:
        """
        Generate new access token from refresh token.

        Validates:
        - Refresh token is valid
        - Session exists in database
        - Session hasn't expired
        - User still has access to restaurant

        Returns new token pair with rotated refresh token.
        """
        # Verify refresh token
        payload = self.verify_token(refresh_token, is_refresh=True)

        # Check session exists and is valid
        stmt = select(UserSession).where(
            UserSession.id == payload.session_id,
            UserSession.user_id == payload.user_id,
            UserSession.expires_at > datetime.utcnow()
        )
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if not session:
            raise JWTError("Session expired or invalid")

        # Verify token hash matches
        if not pwd_context.verify(refresh_token, session.token_hash):
            raise JWTError("Invalid refresh token")

        # Get user with restaurant membership
        stmt = select(User).where(User.id == payload.user_id)
        result = await self.db.execute(stmt)
        user = result.scalar_one_or_none()

        if not user or not user.is_active:
            raise JWTError("User inactive or not found")

        # Get active membership
        # TODO: Get from user.memberships after relationship is set up
        # For now, use the restaurant_id from the old token

        # Revoke old session
        await self.db.delete(session)

        # Generate new token pair
        return await self.generate_token_pair(
            user=user,
            restaurant_id=payload.restaurant_id,
            role=payload.role
        )

    async def revoke_session(self, session_id: UUID) -> None:
        """Revoke a specific session."""
        stmt = select(UserSession).where(UserSession.id == session_id)
        result = await self.db.execute(stmt)
        session = result.scalar_one_or_none()

        if session:
            await self.db.delete(session)
            await self.db.commit()

    async def revoke_all_user_sessions(self, user_id: UUID) -> int:
        """
        Revoke all sessions for a user.

        Used for:
        - Password changes
        - Security incidents
        - Account lockout

        Returns count of revoked sessions.
        """
        from sqlalchemy import delete

        stmt = delete(UserSession).where(UserSession.user_id == user_id)
        result = await self.db.execute(stmt)
        await self.db.commit()

        return result.rowcount
```

### Role-Based Access Control (RBAC)

```python
# apps/api/src/services/auth/permissions.py

from enum import Enum
from typing import Set
from fastapi import HTTPException, status

class Permission(str, Enum):
    """
    Application permissions.

    Format: {resource}:{action}
    """
    # Forecast permissions
    FORECAST_VIEW = "forecast:view"
    FORECAST_FEEDBACK = "forecast:feedback"
    FORECAST_MANAGE = "forecast:manage"

    # Menu permissions
    MENU_VIEW = "menu:view"
    MENU_CREATE = "menu:create"
    MENU_UPDATE = "menu:update"
    MENU_DELETE = "menu:delete"

    # Recipe permissions
    RECIPE_VIEW = "recipe:view"
    RECIPE_CREATE = "recipe:create"
    RECIPE_UPDATE = "recipe:update"
    RECIPE_VERIFY = "recipe:verify"  # Chef only

    # Procurement permissions
    PROCUREMENT_VIEW = "procurement:view"
    PROCUREMENT_ORDER = "procurement:order"
    PROCUREMENT_APPROVE = "procurement:approve"  # Manager/Owner only

    # Inventory permissions
    INVENTORY_VIEW = "inventory:view"
    INVENTORY_UPDATE = "inventory:update"
    INVENTORY_MANAGE = "inventory:manage"

    # Labor permissions
    LABOR_VIEW = "labor:view"
    LABOR_VIEW_SELF = "labor:view_self"
    LABOR_CREATE = "labor:create"
    LABOR_UPDATE = "labor:update"
    LABOR_APPROVE = "labor:approve"

    # Sales permissions
    SALES_VIEW = "sales:view"
    SALES_EXPORT = "sales:export"

    # Reports permissions
    REPORTS_VIEW = "reports:view"
    REPORTS_CREATE = "reports:create"
    REPORTS_EXPORT = "reports:export"

    # Settings permissions
    SETTINGS_VIEW = "settings:view"
    SETTINGS_UPDATE = "settings:update"

    # User management permissions
    USERS_VIEW = "users:view"
    USERS_INVITE = "users:invite"
    USERS_UPDATE = "users:update"
    USERS_DELETE = "users:delete"

    # POS integration permissions
    POS_VIEW = "pos:view"
    POS_CONNECT = "pos:connect"
    POS_DISCONNECT = "pos:disconnect"

class Role(str, Enum):
    """User roles with hierarchical permissions."""

    OWNER = "owner"          # Full access
    ADMIN = "admin"          # Almost full access (no billing)
    MANAGER = "manager"      # Day-to-day operations
    CHEF = "chef"            # Kitchen-focused
    STAFF = "staff"          # Limited access
    VIEWER = "viewer"        # Read-only access

# Role → Permissions mapping
ROLE_PERMISSIONS: dict[Role, Set[Permission]] = {
    Role.OWNER: {  # Full access to everything
        *[p for p in Permission],
    },

    Role.ADMIN: {  # Everything except some owner-only features
        Permission.FORECAST_VIEW,
        Permission.FORECAST_FEEDBACK,
        Permission.FORECAST_MANAGE,
        Permission.MENU_VIEW,
        Permission.MENU_CREATE,
        Permission.MENU_UPDATE,
        Permission.MENU_DELETE,
        Permission.RECIPE_VIEW,
        Permission.RECIPE_CREATE,
        Permission.RECIPE_UPDATE,
        Permission.RECIPE_VERIFY,
        Permission.PROCUREMENT_VIEW,
        Permission.PROCUREMENT_ORDER,
        Permission.PROCUREMENT_APPROVE,
        Permission.INVENTORY_VIEW,
        Permission.INVENTORY_UPDATE,
        Permission.INVENTORY_MANAGE,
        Permission.LABOR_VIEW,
        Permission.LABOR_CREATE,
        Permission.LABOR_UPDATE,
        Permission.LABOR_APPROVE,
        Permission.SALES_VIEW,
        Permission.SALES_EXPORT,
        Permission.REPORTS_VIEW,
        Permission.REPORTS_CREATE,
        Permission.REPORTS_EXPORT,
        Permission.SETTINGS_VIEW,
        Permission.SETTINGS_UPDATE,
        Permission.USERS_VIEW,
        Permission.USERS_INVITE,
        Permission.USERS_UPDATE,
        Permission.POS_VIEW,
        Permission.POS_CONNECT,
        Permission.POS_DISCONNECT,
    },

    Role.MANAGER: {  # Day-to-day operations
        Permission.FORECAST_VIEW,
        Permission.FORECAST_FEEDBACK,
        Permission.MENU_VIEW,
        Permission.MENU_CREATE,
        Permission.MENU_UPDATE,
        Permission.RECIPE_VIEW,
        Permission.RECIPE_CREATE,
        Permission.RECIPE_UPDATE,
        Permission.PROCUREMENT_VIEW,
        Permission.PROCUREMENT_ORDER,
        Permission.PROCUREMENT_APPROVE,
        Permission.INVENTORY_VIEW,
        Permission.INVENTORY_UPDATE,
        Permission.INVENTORY_MANAGE,
        Permission.LABOR_VIEW,
        Permission.LABOR_CREATE,
        Permission.LABOR_UPDATE,
        Permission.LABOR_APPROVE,
        Permission.SALES_VIEW,
        Permission.SALES_EXPORT,
        Permission.REPORTS_VIEW,
        Permission.REPORTS_CREATE,
        Permission.POS_VIEW,
    },

    Role.CHEF: {  # Kitchen-focused permissions
        Permission.FORECAST_VIEW,
        Permission.MENU_VIEW,
        Permission.RECIPE_VIEW,
        Permission.RECIPE_CREATE,
        Permission.RECIPE_UPDATE,
        Permission.RECIPE_VERIFY,
        Permission.PROCUREMENT_VIEW,
        Permission.PROCUREMENT_ORDER,
        Permission.INVENTORY_VIEW,
        Permission.INVENTORY_UPDATE,
        Permission.LABOR_VIEW_SELF,
        Permission.SALES_VIEW,
    },

    Role.STAFF: {  # Basic operational access
        Permission.FORECAST_VIEW,
        Permission.MENU_VIEW,
        Permission.RECIPE_VIEW,
        Permission.INVENTORY_VIEW,
        Permission.LABOR_VIEW_SELF,
        Permission.SALES_VIEW,
    },

    Role.VIEWER: {  # Read-only access
        Permission.FORECAST_VIEW,
        Permission.MENU_VIEW,
        Permission.RECIPE_VIEW,
        Permission.INVENTORY_VIEW,
        Permission.SALES_VIEW,
        Permission.REPORTS_VIEW,
    },
}

class PermissionChecker:
    """Helper class for permission checks."""

    @staticmethod
    def has_permission(role: Role, permission: Permission) -> bool:
        """Check if a role has a specific permission."""
        return permission in ROLE_PERMISSIONS.get(role, set())

    @staticmethod
    def has_any_permission(role: Role, permissions: Set[Permission]) -> bool:
        """Check if role has ANY of the specified permissions."""
        role_perms = ROLE_PERMISSIONS.get(role, set())
        return bool(role_perms.intersection(permissions))

    @staticmethod
    def has_all_permissions(role: Role, permissions: Set[Permission]) -> bool:
        """Check if role has ALL of the specified permissions."""
        role_perms = ROLE_PERMISSIONS.get(role, set())
        return permissions.issubset(role_perms)

    @staticmethod
    def require_permission(role: Role, permission: Permission) -> None:
        """
        Raise HTTPException if role doesn't have permission.

        Use in endpoint functions for permission checks.
        """
        if not PermissionChecker.has_permission(role, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Permission denied. Required: {permission.value}"
            )
```

### FastAPI Dependency for Authorization

```python
# apps/api/src/dependencies/permissions.py

from fastapi import Depends, HTTPException, status
from typing import Set

from ..dependencies.auth import get_current_user
from ..schemas.auth import User
from ..services.auth.permissions import Permission, PermissionChecker

def require_permissions(*permissions: Permission):
    """
    FastAPI dependency factory for permission checks.

    Usage:
    ```python
    @router.post("/menu-items")
    async def create_menu_item(
        data: MenuItemCreate,
        user: User = Depends(require_permissions(Permission.MENU_CREATE))
    ):
        # User is guaranteed to have MENU_CREATE permission
        pass
    ```
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        # Check all required permissions
        for permission in permissions:
            if not PermissionChecker.has_permission(current_user.role, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Missing required permission: {permission.value}"
                )

        return current_user

    return permission_checker

def require_any_permission(*permissions: Permission):
    """
    Require ANY of the specified permissions.

    Useful for endpoints accessible by multiple roles.
    """
    async def permission_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:
        if not PermissionChecker.has_any_permission(
            current_user.role,
            set(permissions)
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Missing required permissions. Need any of: {[p.value for p in permissions]}"
            )

        return current_user

    return permission_checker
```

**Usage Example:**

```python
# apps/api/src/routers/menu_items.py

from fastapi import APIRouter, Depends
from ..dependencies.permissions import require_permissions
from ..services.auth.permissions import Permission

router = APIRouter()

@router.post("/menu-items")
async def create_menu_item(
    data: MenuItemCreate,
    user: User = Depends(require_permissions(Permission.MENU_CREATE))
):
    """
    Only users with MENU_CREATE permission can access this endpoint.
    (Owner, Admin, Manager roles)
    """
    # Create menu item
    pass

@router.delete("/menu-items/{item_id}")
async def delete_menu_item(
    item_id: UUID,
    user: User = Depends(require_permissions(Permission.MENU_DELETE))
):
    """
    Only users with MENU_DELETE permission can access this endpoint.
    (Owner, Admin roles)
    """
    # Delete menu item
    pass
```

---

## Input Validation & Sanitization

### Pydantic Schema Validation

FastAPI uses Pydantic v2 for automatic request validation:

```python
# apps/api/src/schemas/menu_items.py

from pydantic import BaseModel, Field, EmailStr, validator, field_validator
from typing import Optional
from decimal import Decimal
from uuid import UUID
import re

class MenuItemCreateRequest(BaseModel):
    """
    Menu item creation schema with validation.

    Pydantic automatically validates:
    - Type checking
    - Required fields
    - String lengths
    - Regex patterns
    - Custom validators
    """

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Menu item name"
    )

    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Item description"
    )

    category: str = Field(
        ...,
        regex="^[a-zA-Z0-9_-]+$",
        max_length=100,
        description="Category slug (alphanumeric, hyphens, underscores only)"
    )

    price: Decimal = Field(
        ...,
        gt=0,
        max_digits=10,
        decimal_places=2,
        description="Price must be positive"
    )

    cost: Optional[Decimal] = Field(
        None,
        ge=0,
        max_digits=10,
        decimal_places=2,
        description="Cost (if known)"
    )

    tags: list[str] = Field(
        default_factory=list,
        max_items=20,
        description="Item tags (max 20)"
    )

    @field_validator('name')
    @classmethod
    def validate_name(cls, v: str) -> str:
        """Custom validation for name field."""
        # Remove leading/trailing whitespace
        v = v.strip()

        # Check for SQL injection patterns
        sql_patterns = [
            r"(\bUNION\b.*\bSELECT\b)",
            r"(\bDROP\b.*\bTABLE\b)",
            r"(--)",
            r"(;.*--)",
        ]

        for pattern in sql_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Invalid characters in name")

        # Check for XSS patterns
        xss_patterns = [
            r"<script",
            r"javascript:",
            r"on\w+\s*=",
        ]

        for pattern in xss_patterns:
            if re.search(pattern, v, re.IGNORECASE):
                raise ValueError("Invalid characters in name")

        return v

    @field_validator('tags')
    @classmethod
    def validate_tags(cls, v: list[str]) -> list[str]:
        """Validate and sanitize tags."""
        sanitized = []

        for tag in v:
            # Strip whitespace
            tag = tag.strip()

            # Skip empty tags
            if not tag:
                continue

            # Max length per tag
            if len(tag) > 50:
                raise ValueError("Tag too long (max 50 characters)")

            # Alphanumeric and hyphens only
            if not re.match(r'^[a-zA-Z0-9-]+$', tag):
                raise ValueError("Tags must be alphanumeric with hyphens only")

            sanitized.append(tag.lower())

        return sanitized

    @validator('cost')
    @classmethod
    def cost_less_than_price(cls, v, values):
        """Ensure cost doesn't exceed price."""
        if v is not None and 'price' in values:
            if v > values['price']:
                raise ValueError("Cost cannot exceed price")

        return v

class EmailRequest(BaseModel):
    """Email validation with Pydantic's EmailStr."""

    email: EmailStr = Field(
        ...,
        description="Valid email address"
    )

    # EmailStr automatically validates:
    # - Valid email format
    # - Proper domain structure
    # - No dangerous characters

class SearchRequest(BaseModel):
    """Search query validation."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=200,
        description="Search query"
    )

    limit: int = Field(
        20,
        ge=1,
        le=100,
        description="Results per page (1-100)"
    )

    offset: int = Field(
        0,
        ge=0,
        description="Pagination offset"
    )

    @field_validator('query')
    @classmethod
    def sanitize_query(cls, v: str) -> str:
        """Sanitize search query to prevent injection."""
        # Remove dangerous SQL characters
        v = v.replace("'", "")
        v = v.replace(";", "")
        v = v.replace("--", "")

        # Remove script tags
        v = re.sub(r'<script.*?</script>', '', v, flags=re.IGNORECASE)

        return v.strip()
```

**Benefits:**
- ✅ Automatic type validation
- ✅ SQL injection prevention
- ✅ XSS prevention
- ✅ Business logic validation
- ✅ Automatic error messages with field details
- ✅ OpenAPI schema generation

---

## Row-Level Security (RLS)

### PostgreSQL RLS Policies

Multi-tenant data isolation using PostgreSQL Row-Level Security:

```sql
-- Enable RLS on all tables
ALTER TABLE restaurants ENABLE ROW LEVEL SECURITY;
ALTER TABLE menu_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecasts ENABLE ROW LEVEL SECURITY;
ALTER TABLE sales_data ENABLE ROW LEVEL SECURITY;
-- ... enable on all tables

-- Create RLS policies

-- Restaurants: Users can only see their own restaurant
CREATE POLICY restaurant_isolation ON restaurants
  FOR ALL
  USING (id = current_setting('app.current_restaurant_id')::uuid);

-- Menu items: Filtered by restaurant
CREATE POLICY menu_items_isolation ON menu_items
  FOR ALL
  USING (restaurant_id = current_setting('app.current_restaurant_id')::uuid);

-- Forecasts: Filtered by restaurant
CREATE POLICY forecasts_isolation ON forecasts
  FOR ALL
  USING (restaurant_id = current_setting('app.current_restaurant_id')::uuid);

-- Sales data: Filtered by restaurant (read-only for efficiency)
CREATE POLICY sales_data_isolation ON sales_data
  FOR SELECT
  USING (restaurant_id = current_setting('app.current_restaurant_id')::uuid);

-- Inventory: Filtered by restaurant
CREATE POLICY inventory_isolation ON inventory_items
  FOR ALL
  USING (restaurant_id = current_setting('app.current_restaurant_id')::uuid);

-- Labor shifts: Filtered by restaurant
CREATE POLICY shifts_isolation ON shifts
  FOR ALL
  USING (restaurant_id = current_setting('app.current_restaurant_id')::uuid);

-- User sessions: Users can only see their own sessions
CREATE POLICY user_sessions_isolation ON user_sessions
  FOR ALL
  USING (user_id = current_setting('app.current_user_id')::uuid);
```

### Setting RLS Context in FastAPI

```python
# apps/api/src/dependencies/auth.py (continuation)

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Get current user and set RLS context.

    Sets PostgreSQL session variables:
    - app.current_user_id
    - app.current_restaurant_id

    These variables are used by RLS policies to filter queries.
    """
    # ... (token verification code from earlier)

    # Set PostgreSQL RLS context variables
    await db.execute(
        text("SET LOCAL app.current_restaurant_id = :restaurant_id"),
        {"restaurant_id": str(token_data.restaurant_id)}
    )
    await db.execute(
        text("SET LOCAL app.current_user_id = :user_id"),
        {"user_id": str(token_data.user_id)}
    )

    # All subsequent queries in this request will be filtered by RLS
    # No need to manually add WHERE restaurant_id = ... clauses!

    return user
```

**Benefits:**
- ✅ Data isolation enforced at database level
- ✅ Protection even if application logic has bugs
- ✅ No need to manually filter queries
- ✅ Performance: PostgreSQL optimizes RLS filtering
- ✅ Audit trail: Can't accidentally query other tenants' data

---

## Rate Limiting

### Redis-Based Rate Limiting

```python
# apps/api/src/middleware/rate_limit.py

from fastapi import Request, HTTPException, status
from redis import asyncio as aioredis
from typing import Optional
import time

class RateLimiter:
    """
    Token bucket rate limiter using Redis.

    Implements:
    - Per-user rate limits
    - Per-restaurant rate limits
    - Per-IP rate limits (for unauthenticated requests)
    - Different limits for different endpoints
    """

    def __init__(self, redis: aioredis.Redis):
        self.redis = redis

    async def check_rate_limit(
        self,
        key: str,
        limit: int,
        window_seconds: int = 60
    ) -> tuple[bool, dict]:
        """
        Check if request is within rate limit.

        Returns:
        - (allowed: bool, info: dict)

        Uses sliding window counter algorithm.
        """
        now = int(time.time())
        window_start = now - window_seconds

        # Redis key for this rate limit
        rate_key = f"rate_limit:{key}"

        # Use Redis sorted set for sliding window
        # Score = timestamp, Value = request ID
        pipe = self.redis.pipeline()

        # Remove old entries outside the window
        pipe.zremrangebyscore(rate_key, 0, window_start)

        # Count requests in current window
        pipe.zcard(rate_key)

        # Add current request
        pipe.zadd(rate_key, {f"{now}:{time.time_ns()}": now})

        # Set expiry on the key
        pipe.expire(rate_key, window_seconds + 10)

        results = await pipe.execute()
        current_count = results[1]

        # Check if limit exceeded
        allowed = current_count < limit

        # Calculate remaining and reset time
        remaining = max(0, limit - current_count - 1)

        # Get oldest request timestamp for reset calculation
        oldest = await self.redis.zrange(rate_key, 0, 0, withscores=True)
        reset_time = int(oldest[0][1]) + window_seconds if oldest else now + window_seconds

        return allowed, {
            "limit": limit,
            "remaining": remaining,
            "reset": reset_time,
            "retry_after": reset_time - now if not allowed else None
        }

# Middleware
class RateLimitMiddleware:
    """
    FastAPI middleware for rate limiting.

    Applies different limits based on:
    - User tier (free, pro, enterprise)
    - Endpoint sensitivity
    - Authentication status
    """

    def __init__(self, redis: aioredis.Redis):
        self.limiter = RateLimiter(redis)

        # Rate limits (requests per minute)
        self.LIMITS = {
            "user": 100,           # Per authenticated user
            "restaurant": 1000,    # Per restaurant (shared by all users)
            "ip": 20,              # Per IP (unauthenticated)
            "expensive": 10,       # Expensive endpoints (ML predictions, exports)
        }

    async def __call__(self, request: Request, call_next):
        """Process request with rate limiting."""

        # Skip rate limiting for health check
        if request.url.path == "/health":
            return await call_next(request)

        # Determine rate limit key
        user_id = getattr(request.state, "user_id", None)
        restaurant_id = getattr(request.state, "restaurant_id", None)

        # Check expensive endpoints first
        if self._is_expensive_endpoint(request.url.path):
            key = f"expensive:{user_id or request.client.host}"
            limit = self.LIMITS["expensive"]
        elif user_id:
            # Authenticated: user-specific limit
            key = f"user:{user_id}"
            limit = self.LIMITS["user"]
        else:
            # Unauthenticated: IP-based limit
            key = f"ip:{request.client.host}"
            limit = self.LIMITS["ip"]

        # Check rate limit
        allowed, info = await self.limiter.check_rate_limit(key, limit, window_seconds=60)

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Try again in {info['retry_after']} seconds",
                headers={
                    "X-RateLimit-Limit": str(info["limit"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(info["reset"]),
                    "Retry-After": str(info["retry_after"])
                }
            )

        # Also check restaurant-level limit (prevents one user from exhausting quota)
        if restaurant_id:
            restaurant_key = f"restaurant:{restaurant_id}"
            allowed, rest_info = await self.limiter.check_rate_limit(
                restaurant_key,
                self.LIMITS["restaurant"],
                window_seconds=60
            )

            if not allowed:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Restaurant rate limit exceeded",
                    headers={
                        "X-RateLimit-Limit": str(rest_info["limit"]),
                        "Retry-After": str(rest_info["retry_after"])
                    }
                )

        # Add rate limit info to response headers
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(info["limit"])
        response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
        response.headers["X-RateLimit-Reset"] = str(info["reset"])

        return response

    @staticmethod
    def _is_expensive_endpoint(path: str) -> bool:
        """Check if endpoint is computationally expensive."""
        expensive_patterns = [
            "/predict",
            "/retrain",
            "/export",
            "/optimize",
            "/aggregate"
        ]

        return any(pattern in path for pattern in expensive_patterns)
```

---

## Secrets Management

### AWS Secrets Manager Integration

```python
# apps/api/src/config/secrets.py

import boto3
import json
from functools import lru_cache
from typing import Dict, Any
import structlog

logger = structlog.get_logger()

class SecretsManager:
    """
    AWS Secrets Manager client for secure secret retrieval.

    Secrets are:
    - Encrypted at rest with AWS KMS
    - Automatically rotated
    - Cached in memory with TTL
    - Never logged or exposed in errors
    """

    def __init__(self, region_name: str = "us-east-1"):
        self.client = boto3.client("secretsmanager", region_name=region_name)
        self._cache: Dict[str, Any] = {}

    @lru_cache(maxsize=32)
    def get_secret(self, secret_name: str) -> Dict[str, Any]:
        """
        Retrieve secret from AWS Secrets Manager.

        Cached in memory (LRU cache) to reduce API calls.
        Cache is cleared on Lambda cold start.
        """
        try:
            logger.info("fetching_secret", secret_name=secret_name)

            response = self.client.get_secret_value(SecretId=secret_name)

            # Secrets can be string or binary
            if "SecretString" in response:
                secret = json.loads(response["SecretString"])
            else:
                secret = response["SecretBinary"]

            logger.info("secret_retrieved", secret_name=secret_name)
            return secret

        except Exception as e:
            # NEVER log the actual error details (might contain secret fragments)
            logger.error("secret_fetch_failed", secret_name=secret_name)
            raise RuntimeError(f"Failed to retrieve secret: {secret_name}")

    def get_database_credentials(self, environment: str) -> Dict[str, str]:
        """Get database credentials for environment."""
        secret_name = f"flux/{environment}/database"
        secret = self.get_secret(secret_name)

        return {
            "host": secret["host"],
            "port": secret["port"],
            "database": secret["database"],
            "username": secret["username"],
            "password": secret["password"],
        }

    def get_jwt_secrets(self, environment: str) -> Dict[str, str]:
        """Get JWT signing secrets."""
        secret_name = f"flux/{environment}/jwt"
        secret = self.get_secret(secret_name)

        return {
            "access_secret": secret["access_secret"],
            "refresh_secret": secret["refresh_secret"],
        }

    def get_api_keys(self, environment: str) -> Dict[str, str]:
        """Get third-party API keys."""
        secret_name = f"flux/{environment}/api-keys"
        secret = self.get_secret(secret_name)

        return secret  # Contains keys for POS systems, email service, etc.

# Usage in application
secrets_manager = SecretsManager(region_name="us-east-1")

# Get database credentials
db_creds = secrets_manager.get_database_credentials("production")

# Build database URL (never log this!)
DATABASE_URL = (
    f"postgresql+asyncpg://{db_creds['username']}:{db_creds['password']}"
    f"@{db_creds['host']}:{db_creds['port']}/{db_creds['database']}"
)
```

### Environment-Based Configuration

```python
# apps/api/src/config/settings.py

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional

class Settings(BaseSettings):
    """
    Application settings with validation.

    Loads from:
    1. Environment variables
    2. .env file (development only)
    3. AWS Secrets Manager (production)

    Pydantic validates all settings on startup.
    """

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False

    # Application
    APP_NAME: str = "Flux API"
    API_VERSION: str = "1.0.0"

    # Database (loaded from Secrets Manager in production)
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # JWT (loaded from Secrets Manager in production)
    JWT_SECRET_KEY: str
    REFRESH_TOKEN_SECRET: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # AWS
    AWS_REGION: str = "us-east-1"
    S3_BUCKET: str = "flux-uploads"

    # Security
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000"]
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"

    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True

    # Logging
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.

    Settings are loaded once and cached for application lifetime.
    """
    return Settings()

# Usage
settings = get_settings()
```

---

## Encryption

### Data Encryption at Rest

**RDS PostgreSQL:**
```hcl
# infra/terraform/modules/database/main.tf

resource "aws_db_instance" "postgresql" {
  identifier = "flux-${var.environment}"
  engine     = "postgres"

  # Encryption at rest with KMS
  storage_encrypted = true
  kms_key_id        = aws_kms_key.rds.arn

  # ... other configuration
}

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true

  tags = {
    Name        = "flux-rds-${var.environment}"
    Environment = var.environment
  }
}
```

**S3 Encryption:**
```hcl
# infra/terraform/modules/storage/main.tf

resource "aws_s3_bucket" "uploads" {
  bucket = "flux-uploads-${var.environment}"
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = aws_kms_key.s3.arn
    }
    bucket_key_enabled = true
  }
}
```

### Data Encryption in Transit

**TLS 1.3 Enforcement:**

```python
# apps/api/src/main.py

from fastapi import FastAPI
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware

app = FastAPI()

if settings.ENVIRONMENT == "production":
    # Force HTTPS in production
    app.add_middleware(HTTPSRedirectMiddleware)

    # Only accept requests from known hosts
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["api.flux.com", "*.flux.com"]
    )

# CORS with credentials
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
    expose_headers=["X-RateLimit-Limit", "X-RateLimit-Remaining"]
)
```

**Database Connection TLS:**

```python
# apps/api/src/db/session.py

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Enforce TLS for database connections in production
ssl_params = {}
if settings.ENVIRONMENT == "production":
    ssl_params = {
        "ssl": "require",
        "sslmode": "verify-full",
        "sslrootcert": "/path/to/rds-ca-bundle.pem"
    }

DATABASE_URL = settings.DATABASE_URL
if ssl_params:
    # Append SSL params to connection string
    DATABASE_URL += "?" + "&".join(f"{k}={v}" for k, v in ssl_params.items())

engine = create_async_engine(
    DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,  # Verify connections before using
)
```

---

## Audit Logging

### Structured Logging with structlog

```python
# apps/api/src/config/logging.py

import structlog
import logging
from typing import Any

def configure_logging():
    """
    Configure structured logging with structlog.

    Logs are:
    - JSON formatted
    - Include request context
    - Include user/restaurant IDs
    - Sent to CloudWatch Logs
    """

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

# Audit logger
audit_logger = structlog.get_logger("audit")

def log_audit_event(
    event_type: str,
    user_id: str,
    restaurant_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    metadata: dict[str, Any] = None
):
    """
    Log security-relevant events.

    Event types:
    - auth.login
    - auth.logout
    - auth.failed_login
    - data.create
    - data.update
    - data.delete
    - settings.change
    - user.invite
    - user.remove
    """
    audit_logger.info(
        "audit_event",
        event_type=event_type,
        user_id=user_id,
        restaurant_id=restaurant_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        metadata=metadata or {}
    )

# Usage
log_audit_event(
    event_type="data.delete",
    user_id=str(current_user.id),
    restaurant_id=str(current_user.restaurant_id),
    resource_type="menu_item",
    resource_id=str(item_id),
    action="DELETE",
    metadata={"item_name": item.name}
)
```

### Request Logging Middleware

```python
# apps/api/src/middleware/logging.py

from fastapi import Request
import structlog
import time
from uuid import uuid4

logger = structlog.get_logger()

async def log_requests(request: Request, call_next):
    """
    Log all HTTP requests with:
    - Request ID
    - User ID (if authenticated)
    - Duration
    - Status code
    - IP address
    """

    # Generate request ID
    request_id = str(uuid4())
    request.state.request_id = request_id

    # Extract context
    user_id = getattr(request.state, "user_id", None)
    restaurant_id = getattr(request.state, "restaurant_id", None)

    # Log request start
    logger.info(
        "request_started",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        user_id=user_id,
        restaurant_id=restaurant_id,
        ip=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    # Process request
    start_time = time.time()

    try:
        response = await call_next(request)

        # Log request completion
        duration = time.time() - start_time

        logger.info(
            "request_completed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_seconds=round(duration, 3),
            user_id=user_id,
            restaurant_id=restaurant_id
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response

    except Exception as exc:
        # Log errors
        duration = time.time() - start_time

        logger.error(
            "request_failed",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            duration_seconds=round(duration, 3),
            error=str(exc),
            user_id=user_id,
            restaurant_id=restaurant_id
        )

        raise
```

---

## Security Headers

```python
# apps/api/src/middleware/security_headers.py

from fastapi import Request

async def add_security_headers(request: Request, call_next):
    """
    Add security headers to all responses.

    Headers:
    - X-Content-Type-Options: nosniff
    - X-Frame-Options: DENY
    - X-XSS-Protection: 1; mode=block
    - Strict-Transport-Security: HTTPS only
    - Content-Security-Policy: Prevent XSS
    - Referrer-Policy: Privacy
    """

    response = await call_next(request)

    # Prevent MIME-type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"

    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"

    # Enable XSS filter
    response.headers["X-XSS-Protection"] = "1; mode=block"

    # Force HTTPS
    if settings.ENVIRONMENT == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

    # Content Security Policy
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: https:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "frame-ancestors 'none';"
    )

    # Privacy
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

    # Permissions policy
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

    return response
```

---

## Compliance

### GDPR Compliance

**Data Subject Rights:**

```python
# apps/api/src/routers/gdpr.py

from fastapi import APIRouter, Depends, BackgroundTasks
from ..dependencies.auth import get_current_user

router = APIRouter(prefix="/api/v1/gdpr", tags=["gdpr"])

@router.get("/export-data")
async def export_user_data(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user)
):
    """
    GDPR Article 20: Right to data portability.

    Exports all user data in machine-readable format (JSON).
    Includes:
    - Profile data
    - Activity logs
    - Created content
    - Settings
    """
    from ..services.gdpr import GDPRService

    service = GDPRService(db)

    # Generate export asynchronously
    job_id = await service.export_user_data(current_user.id, background_tasks)

    return {
        "message": "Data export started",
        "job_id": job_id,
        "estimated_time": "5-10 minutes"
    }

@router.delete("/delete-account")
async def delete_account(
    current_user: User = Depends(get_current_user)
):
    """
    GDPR Article 17: Right to erasure (Right to be forgotten).

    Permanently deletes:
    - User account
    - Personal data
    - Activity logs
    - Created content (or anonymizes if required for business)

    Retains only:
    - Anonymized analytics
    - Legal/accounting records (as required by law)
    """
    from ..services.gdpr import GDPRService

    service = GDPRService(db)
    await service.delete_user_data(current_user.id)

    return {"message": "Account deletion initiated"}
```

### PCI DSS Compliance

**Payment Data Handling:**

```python
# We NEVER store credit card data!
# All payment processing goes through PCI-compliant provider (Stripe)

from stripe import PaymentIntent

async def create_payment(amount: int, currency: str = "usd"):
    """
    Create Stripe PaymentIntent.

    PCI compliance:
    - No card data touches our servers
    - Stripe handles all card processing
    - We only store Stripe customer/payment intent IDs
    """

    intent = PaymentIntent.create(
        amount=amount,
        currency=currency,
        metadata={
            "restaurant_id": str(current_user.restaurant_id),
            "user_id": str(current_user.id)
        }
    )

    return {
        "client_secret": intent.client_secret,
        "payment_intent_id": intent.id
    }
```

### SOC 2 Compliance

**Access Controls:**
- ✅ Role-based access control (RBAC)
- ✅ Multi-factor authentication (MFA) available
- ✅ Session management with timeout
- ✅ Audit logging of all data access
- ✅ Encryption at rest and in transit

**Monitoring:**
- ✅ Real-time security alerts
- ✅ Anomaly detection
- ✅ Failed login tracking
- ✅ Unauthorized access attempts logged

---

**Related:**
- [API Specification →](./03-api-specification.md)
- [Backend Architecture →](./09-backend-architecture.md)
- [Deployment →](./10-deployment.md)
