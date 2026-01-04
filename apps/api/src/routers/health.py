"""
Health check router with database and Redis connectivity verification.
"""
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
import redis

from src.db.session import get_db
from src.core.config import get_settings

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check():
    """Basic health check - always returns OK."""
    return {"status": "ok"}


@router.get("/api/health")
def api_health_check(db: Session = Depends(get_db)):
    """
    Comprehensive health check verifying:
    - Database connectivity
    - Redis connectivity (if configured)

    Returns 200 if all critical services are healthy.
    Returns 503 if any critical service is down.
    """
    health_status = {
        "status": "ok",
        "services": {}
    }
    is_healthy = True

    # Check PostgreSQL
    try:
        db.execute(text("SELECT 1"))
        health_status["services"]["database"] = {"status": "ok"}
    except Exception as e:
        health_status["services"]["database"] = {"status": "error", "message": str(e)}
        is_healthy = False

    # Check Redis (optional - don't fail if not configured)
    try:
        redis_client = redis.Redis(host="localhost", port=6379, socket_connect_timeout=2)
        redis_client.ping()
        health_status["services"]["redis"] = {"status": "ok"}
    except redis.ConnectionError:
        health_status["services"]["redis"] = {"status": "unavailable", "message": "Redis not connected"}
        # Redis is optional for now, don't fail health check
    except Exception as e:
        health_status["services"]["redis"] = {"status": "error", "message": str(e)}

    if not is_healthy:
        health_status["status"] = "unhealthy"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=health_status
        )

    return health_status
