# Core Workflows

> **Part of:** [Flux Architecture Documentation](./README.md)

---

## User Registration & Onboarding

**Description:** New restaurant owner signs up and connects their POS system.

```mermaid
sequenceDiagram
    actor User
    participant Web as Next.js App
    participant API as FastAPI
    participant Auth as OAuth2/JWT
    participant DB as PostgreSQL
    participant POS as Square API

    User->>Web: Navigate to /register
    Web->>User: Show registration form

    User->>Web: Submit email, password, restaurant name
    Web->>API: POST /api/v1/auth/register

    API->>DB: BEGIN TRANSACTION
    API->>DB: Create User record
    API->>DB: Create Restaurant record
    API->>DB: Create RestaurantMembership (role: OWNER)
    API->>DB: COMMIT TRANSACTION

    API->>Auth: Generate JWT token
    API-->>Web: { "token": "...", ... }

    Web->>Web: Store token in cookie
    Web->>User: Redirect to /onboarding/connect-pos

    User->>Web: Select "Square POS"
    Web->>API: POST /api/v1/pos/connections

    API->>DB: Create POSIntegration (status: PENDING)
    API-->>Web: { "auth_url": "...", "integration_id": "..." }

    Web->>User: Redirect to Square OAuth
    User->>POS: Authorize app access
    POS->>Web: Redirect to /integrations/callback?code=...&state=...

    Web->>API: POST /api/v1/pos/callback/square?code=...
    API->>POS: Exchange code for access token
    POS-->>API: { "access_token": "...", ... }

    API->>DB: Update POSIntegration (status: CONNECTED)
    API->>DB: Create SyncJob (type: INITIAL_SYNC)
    API-->>Web: { "success": true }

    Web->>User: Redirect to /dashboard

    Note over API,DB: Background worker starts initial sync
```

---

## Forecast Generation (Scheduled)

**Description:** Daily automated forecast generation via EventBridge rule.

```mermaid
sequenceDiagram
    participant EB as EventBridge
    participant Lambda as Forecast Scheduler
    participant DB as PostgreSQL
    participant SQS as SQS Queue
    participant SM as SageMaker
    participant Worker as Forecast Worker

    EB->>Lambda: Trigger `forecast-scheduler` (cron: 0 2 * * *)

    Lambda->>DB: SELECT restaurants WHERE status = 'ACTIVE'
    DB-->>Lambda: List of restaurants

    loop For each restaurant
        Lambda->>SQS: Send message { restaurantId, forecastDate }
    end

    SQS->>Worker: Batch of 10 forecast requests

    loop For each request in batch
        Worker->>DB: Fetch historical data (90 days)
        Worker->>Worker: Feature engineering
        Worker->>SM: InvokeEndpoint(features)
        SM-->>Worker: { "predictions": [...], "shap_values": [...] }
        Worker->>DB: BEGIN TRANSACTION
        Worker->>DB: INSERT Forecasts and Explanations
        Worker->>DB: COMMIT TRANSACTION
    end

    Worker-->>SQS: Delete batch from queue
```

---

## POS Transaction Sync

**Description:** Background worker syncs transactions from POS systems.

```mermaid
sequenceDiagram
    participant Webhook as POS Webhook
    participant API as Webhook Handler
    participant SQS as SQS Queue
    participant Worker as Sync Worker
    participant POS as Square API
    participant DB as PostgreSQL

    alt Real-time webhook trigger
        Webhook->>API: POST /api/v1/webhooks/square
        API->>API: Verify HMAC signature
        API->>SQS: Send message { provider, payload }
        API-->>Webhook: 200 OK
    else Scheduled polling (fallback)
        Note over API: EventBridge triggers every 15 minutes
        API->>SQS: Send message { provider, syncType: 'INCREMENTAL' }
    end

    SQS->>Worker: Trigger Lambda with batch
    loop For each sync message
        Worker->>DB: Get POSIntegration credentials
        Worker->>POS: GET /v2/orders?start=...
        alt Token expired (401)
            Worker->>POS: POST /oauth2/token (refresh)
            Worker->>DB: Update POSIntegration tokens
            Worker->>POS: Retry GET /v2/orders
        end
        POS-->>Worker: List of orders
        Worker->>DB: UPSERT Transactions and TransactionItems
        Worker->>DB: Update last_synced_at
    end
```

---

## Procurement Recommendation Flow

**Description:** User views AI-powered procurement recommendations.

```mermaid
sequenceDiagram
    actor User
    participant Web as Next.js App
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Cache as Redis

    User->>Web: Navigate to /procurement
    Web->>API: GET /api/v1/procurement/recommendations

    API->>Cache: GET procurement:recommendations:{id}
    alt Cache hit
        Cache-->>API: Cached recommendations
        API-->>Web: Return from cache
    else Cache miss
        API->>DB: Get Forecasts, Recipes, Inventory
        API->>API: Calculate ingredient needs
        API->>DB: Store recommendations
        API->>Cache: SET recommendations (TTL: 1 hour)
        API-->>Web: Return new recommendations
    end

    Web->>User: Display procurement table
    User->>Web: Click "Why?"
    Web->>API: GET /api/v1/procurement/recommendations/{id}/explanation
    API->>DB: Get SHAP values from explanation
    API-->>Web: Return explanation data
    Web->>User: Display explanation modal
```

---

## Forecast Explanation & Feedback

**Description:** User views SHAP explanations for a forecast and submits feedback.

```mermaid
sequenceDiagram
    actor User
    participant Web as Next.js App
    participant API as FastAPI
    participant DB as PostgreSQL

    User->>Web: Navigate to /forecasts/{id}
    Web->>API: GET /api/v1/forecasts/{id}?include=explanation
    API->>DB: SELECT Forecast JOIN ForecastExplanation
    DB-->>API: Forecast + SHAP values
    API->>API: Format SHAP values into top drivers
    API-->>Web: Return forecast and explanation
    Web->>User: Display forecast and waterfall chart

    User->>Web: Submit actual quantity
    Web->>API: POST /api/v1/forecasts/{id}/feedback
    API->>DB: BEGIN TRANSACTION
    API->>DB: UPDATE Forecast with actual quantity
    API->>DB: INSERT ForecastFeedback
    API->>DB: COMMIT TRANSACTION
    API-->>Web: { "success": true }
    Web->>User: Show success message
```

---

## Team Member Invitation

**Description:** Restaurant owner invites a chef to join their team.

```mermaid
sequenceDiagram
    actor Owner
    participant Web as Next.js App
    participant API as FastAPI
    participant DB as PostgreSQL
    participant Email as SendGrid

    Owner->>Web: Navigate to /team
    Web->>API: GET /api/v1/users/team

    Owner->>Web: Click "Invite Member"
    Web->>API: POST /api/v1/users/invitations

    API->>DB: Create TeamInvitation record
    API->>Email: Send invitation email
    Email-->>Chef: Email with "Accept Invitation" link

    Chef->>Email: Clicks link
    Email->>Web: Redirect to /invitations/{token}

    Web->>API: POST /api/v1/users/invitations/{token}/accept
    API->>DB: Update TeamInvitation status
    API->>DB: Create RestaurantMembership
    API-->>Web: { "success": true }
    Web->>Chef: Redirect to /dashboard
```

---

## Data Health Monitoring

**Description:** System detects data quality issues and alerts users.

```mermaid
sequenceDiagram
    participant Worker as Sync Worker
    participant DB as PostgreSQL
    participant Alert as Alert Lambda
    participant Email as SendGrid

    Note over Worker: After transaction sync completes
    Worker->>DB: Calculate data health metrics
    Worker->>DB: Get previous health score

    alt Score dropped significantly
        Worker->>DB: UPDATE DataHealthMetric, INSERT DataHealthAlert
        Worker->>Alert: Invoke alert Lambda (async)
        Alert->>Email: Send email (template: data-health-alert)
    end
    
    actor User
    participant Web as Next.js App
    participant API as FastAPI
    
    User->>Web: Navigate to /data-health
    Web->>API: GET /api/v1/restaurants/data-health
    API->>DB: Get health metrics and alerts
    API-->>Web: Return health data
    Web->>User: Display health dashboard
```