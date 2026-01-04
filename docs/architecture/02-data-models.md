# Data Models

> **Part of:** [Flux Architecture Documentation](./README.md)
> **Note:** Pydantic models shown below are for documentation. Actual implementation is in SQLAlchemy ORM classes in `apps/api/src/models/`.

---

This section defines the **complete data model** for the Flux platform, using Pydantic schemas for clear, validated data structures. All models are designed with multi-tenancy (Row-Level Security), GDPR compliance, and ML forecasting requirements in mind.

### Core Pydantic Base Model

All schemas inherit from a base model to ensure consistent configuration.

```python
from pydantic import BaseModel, ConfigDict
from uuid import UUID
from datetime import datetime

class FluxBaseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

class IDModel(FluxBaseModel):
    id: UUID

class TimestampModel(FluxBaseModel):
    created_at: datetime
    updated_at: datetime
```

### Core Business Entities

#### 1. Restaurant
```python
from enum import Enum

class SubscriptionTier(str, Enum):
    FREE = "FREE"
    PRO = "PRO"

class Restaurant(IDModel, TimestampModel):
    name: str
    owner_id: UUID
    subscription_tier: SubscriptionTier
    timezone: str = "UTC"
    currency: str = "USD"
```

#### 2. User
```python
class User(IDModel, TimestampModel):
    email: str
    full_name: str
    is_active: bool
```

#### 3. Transaction (TimescaleDB Hypertable)
```python
class Transaction(IDModel, TimestampModel):
    restaurant_id: UUID
    transaction_date: datetime
    total_amount: int # Stored in cents
    source_provider: str
```

#### 4. TransactionItem
```python
class TransactionItem(IDModel, TimestampModel):
    transaction_id: UUID
    menu_item_id: UUID | None
    item_name: str
    quantity: float
    unit_price: int # Stored in cents
```

### Forecasting Entities

#### 5. Forecast
```python
class Forecast(IDModel, TimestampModel):
    restaurant_id: UUID
    menu_item_id: UUID
    forecast_date: date
    predicted_quantity: float
```

---
**Next:** [API Specification →](./03-api-specification.md)