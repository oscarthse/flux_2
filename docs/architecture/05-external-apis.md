# External APIs

> **Part of:** [Flux Architecture Documentation](./README.md)

---

This document details integrations with third-party services and external APIs, focusing on the Python adapter patterns used in the backend.

## POS Integrations

### Square Integration

**Purpose:** Sync transaction data from Square POS systems.
**Authentication:** OAuth 2.0

**Key Endpoints & Logic (Python Adapter):**
```python
# apps/api/src/adapters/pos/square_adapter.py
from datetime import datetime
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from ...config import settings
from .base_adapter import BasePOSAdapter

class SquareAdapter(BasePOSAdapter):
    def __init__(self, connection_details):
        super().__init__(connection_details)
        self.base_url = "https://connect.squareup.com"

    @retry(stop=stop_after_attempt(3), wait=wait_exponential())
    async def refresh_access_token(self):
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/oauth2/token",
                json={
                    "client_id": settings.SQUARE_CLIENT_ID,
                    "client_secret": settings.SQUARE_CLIENT_SECRET,
                    "refresh_token": self.connection.refresh_token,
                    "grant_type": "refresh_token"
                }
            )
            response.raise_for_status()
            # ... (update connection with new tokens) ...

    async def fetch_orders(self, start_date: datetime, end_date: datetime):
        all_orders = []
        cursor = None
        async with httpx.AsyncClient(headers=self.auth_headers) as client:
            while True:
                payload = {
                    "location_ids": [self.connection.location_id],
                    "query": {
                        "filter": {
                            "date_time_filter": {
                                "created_at": {
                                    "start_at": start_date.isoformat(),
                                    "end_at": end_date.isoformat(),
                                },
                            },
                        },
                        "sort": {"sort_field": "CREATED_AT", "sort_order": "ASC"},
                    },
                    "limit": 500,
                    "cursor": cursor
                }
                response = await client.post(f"{self.base_url}/v2/orders/search", json=payload)
                response.raise_for_status()
                data = response.json()
                all_orders.extend(data.get("orders", []))
                cursor = data.get("cursor")
                if not cursor:
                    break
        return all_orders

    def verify_webhook(self, signature: str, body: bytes, url: str) -> bool:
        # ... (HMAC signature verification logic) ...
        return True
```

**Rate Limits:** 500 requests/min/location
**Webhook Events:** `order.created`, `order.updated`

---

### Toast POS Integration

**Purpose:** Sync transaction data from Toast POS systems.
**Authentication:** OAuth 2.0

```python
# apps/api/src/adapters/pos/toast_adapter.py
class ToastAdapter(BasePOSAdapter):
    def __init__(self, connection_details):
        super().__init__(connection_details)
        self.base_url = 'https://ws-api.toasttab.com'

    async def fetch_orders(self, start_date: datetime, end_date: datetime):
        # ... logic to fetch orders from Toast ...
        pass
```
**Rate Limits:** 1000 requests/hour/restaurant

---

## Payment Processing

### Stripe Integration

**Purpose:** Handle subscription billing and payments.
**Authentication:** API Key

```python
# apps/api/src/adapters/payment/stripe_adapter.py
import stripe
from ...config import settings

stripe.api_key = settings.STRIPE_SECRET_KEY

class StripeAdapter:
    async def create_customer(self, email: str, name: str, restaurant_id: str):
        customer = stripe.Customer.create(
            email=email,
            name=name,
            metadata={"restaurant_id": restaurant_id},
        )
        return customer

    async def create_subscription(self, customer_id: str, price_id: str):
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": price_id}],
            payment_behavior="default_incomplete",
            expand=["latest_invoice.payment_intent"],
        )
        return subscription

    def handle_webhook(self, signature: str, payload: bytes):
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=signature,
            secret=settings.STRIPE_WEBHOOK_SECRET,
        )
        # ... logic to handle different event types ...
        return event
```

---

## Communication Services

### SendGrid Integration

**Purpose:** Transactional emails (invitations, notifications, receipts).

```python
# apps/api/src/adapters/email/sendgrid_adapter.py
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from ...config import settings

class SendGridAdapter:
    def __init__(self):
        self.client = SendGridAPIClient(settings.SENDGRID_API_KEY)

    async def send_email(self, to_email: str, subject: str, html_content: str):
        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=to_email,
            subject=subject,
            html_content=html_content
        )
        await self.client.send(message)
```

---

## Analytics & Monitoring

### Datadog Integration

**Purpose:** Application monitoring, logging, and APM.

```python
# apps/api/src/core/logging.py
import structlog
from datadog import initialize, statsd

def configure_datadog():
    initialize(api_key=settings.DATADOG_API_KEY, app_key=settings.DATADOG_APP_KEY)

def record_pos_sync(provider: str, transaction_count: int, duration_ms: float):
    statsd.increment(
        'pos.sync.count',
        tags=[f"provider:{provider}", f"env:{settings.ENVIRONMENT}"]
    )
    statsd.histogram(
        'pos.sync.duration',
        duration_ms,
        tags=[f"provider:{provider}", f"env:{settings.ENVIRONMENT}"]
    )
    statsd.gauge(
        'pos.sync.transactions',
        transaction_count,
        tags=[f"provider:{provider}", f"env:{settings.ENVIRONMENT}"]
    )
```

---

## ML/AI Services

### AWS SageMaker

**Purpose:** ML model hosting for demand forecasting.

**Model Input/Output Contract:**
```python
# Input JSON format for SageMaker endpoint
{
  "menu_item_id": "uuid-of-item",
  "historical_data": [
    {"date": "2024-01-01", "quantity": 45},
    {"date": "2024-01-02", "quantity": 52}
  ],
  "forecast_horizon": 14
}

# Output JSON format from SageMaker endpoint
{
  "model_type": "ENSEMBLE",
  "predictions": [
    {
      "date": "2024-02-01",
      "predicted_quantity": 48.5
    }
  ]
}
```

---

## External API Summary

| Service | Purpose | Auth Method |
|---|---|---|
| **Square** | POS Sync | OAuth 2.0 |
| **Toast** | POS Sync | OAuth 2.0 |
| **Stripe** | Payments | API Key |
| **SendGrid** | Email | API Key |
| **Datadog** | Monitoring | API Key |
| **SageMaker**| ML Inference| AWS IAM |

---
**Previous:** [← Components](./04-components.md)
**Next:** [Core Workflows →](./06-workflows.md)