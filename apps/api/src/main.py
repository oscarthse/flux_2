from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging

from src.routers.auth import router as auth_router
from src.routers.health import router as health_router
from src.routers.data import router as data_router

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Flux API",
    description="Restaurant intelligence platform API - Demand forecasting, inventory optimization, and staffing intelligence for restaurants.",
    version="0.1.0",
)


# Global exception handler for unhandled errors
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected server errors with structured response."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "internal_server_error",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": request.headers.get("X-Request-ID"),
        }
    )

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for now
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
from src.routers.inventory import router as inventory_router
from src.routers.menu import router as menu_router
from src.routers.promotions import router as promotions_router
from src.routers.operating_hours import router as operating_hours_router
from src.routers.recipes import router as recipes_router
from src.routers.forecast import router as forecast_router
from src.routers.settings import router as settings_router

app.include_router(health_router)
app.include_router(auth_router, prefix="/api")
app.include_router(data_router, prefix="/api")
app.include_router(inventory_router, prefix="/api")
app.include_router(menu_router, prefix="/api")
app.include_router(promotions_router, prefix="/api")
app.include_router(operating_hours_router, prefix="/api")
app.include_router(recipes_router, prefix="/api")
app.include_router(forecast_router, prefix="/api")
app.include_router(settings_router)

@app.get("/")
def read_root():
    return {
        "message": "Welcome to Flux API",
        "docs": "/docs",
        "health": "/health"
    }
