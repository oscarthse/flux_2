from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from typing import List, Optional
from datetime import date, timedelta
from uuid import UUID
from decimal import Decimal
from pydantic import BaseModel

from src.db.session import get_db
from src.services.forecast import ForecastService
from src.services.features import FeatureEngineeringService
from src.models.forecast import DemandForecast
from src.models.user import User
from src.core.deps import get_current_user

router = APIRouter(prefix="/forecast", tags=["forecast"])

class GenerateForecastRequest(BaseModel):
    menu_item_name: str
    days_ahead: int = 7
    category: Optional[str] = None

class ForecastPoint(BaseModel):
    date: date
    mean: float
    p10: float
    p50: float
    p90: float

class HistoryPoint(BaseModel):
    date: date
    quantity: float
    stockout: bool

class ForecastResponse(BaseModel):
    history: List[HistoryPoint]
    forecast: List[ForecastPoint]

@router.post("/generate", response_model=List[ForecastPoint])
def generate_forecast(
    req: GenerateForecastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Trigger generation of a probabilistic forecast.
    """
    # Assuming user has a restaurant (linked via owner?)
    # For MVP, finding first restaurant owned by user
    from src.models.restaurant import Restaurant
    restaurant = db.execute(select(Restaurant).where(Restaurant.owner_id == current_user.id)).scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found for user")

    service = ForecastService(db)
    results = service.generate_forecasts(
        restaurant_id=restaurant.id,
        menu_item_name=req.menu_item_name,
        days_ahead=req.days_ahead,
        category=req.category
    )

    return [
        ForecastPoint(
            date=r.forecast_date,
            mean=float(r.predicted_quantity),
            p10=float(r.p10_quantity or r.predicted_quantity),
            p50=float(r.p50_quantity or r.predicted_quantity),
            p90=float(r.p90_quantity or r.predicted_quantity)
        )
        for r in results
    ]

@router.get("/", response_model=ForecastResponse)
def get_forecast_data(
    menu_item_name: str,
    days_history: int = 30,
    days_forecast: int = 7,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get combined history and forecast for visualization.
    """
    from src.models.restaurant import Restaurant
    restaurant = db.execute(select(Restaurant).where(Restaurant.owner_id == current_user.id)).scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # 1. Fetch History (using FeatureService for consistency)
    feature_service = FeatureEngineeringService(db)

    # Lookup ID from name
    from src.models.menu import MenuItem
    item = db.execute(select(MenuItem).where(MenuItem.name == menu_item_name, MenuItem.restaurant_id == restaurant.id)).scalar_one_or_none()
    item_id = item.id if item else None

    df = feature_service.create_training_dataset(
        restaurant_id=restaurant.id,
        menu_item_id=item_id,
        days_history=days_history
    )

    history_points = []
    if not df.empty:
        # df index is date
        for dt, row in df.iterrows():
            history_points.append(HistoryPoint(
                date=dt.date(),
                quantity=float(row['quantity']), # Raw quantity
                stockout=bool(row['stockout'])
            ))

    # 2. Fetch Forecasts from DB
    today = date.today()
    stmt = select(DemandForecast).where(
        DemandForecast.restaurant_id == restaurant.id,
        DemandForecast.menu_item_name == menu_item_name,
        DemandForecast.forecast_date >= today, # Ensure future
        DemandForecast.forecast_date <= today + timedelta(days=days_forecast)
    ).order_by(DemandForecast.forecast_date)

    forecasts = db.execute(stmt).scalars().all()

    # Deduplicate by date (take latest created_at if multiple? or just latest query)
    # Order By defaults to insertion order usually but forecast_date explicitly
    # Use dictionary to keep latest
    forecast_map = {}
    for f in forecasts:
        forecast_map[f.forecast_date] = f

    forecast_points = []
    for dt in sorted(forecast_map.keys()):
        f = forecast_map[dt]
        forecast_points.append(ForecastPoint(
            date=f.forecast_date,
            mean=float(f.predicted_quantity),
            p10=float(f.p10_quantity or 0),
            p50=float(f.p50_quantity or 0),
            p90=float(f.p90_quantity or 0)
        ))

    return ForecastResponse(history=history_points, forecast=forecast_points)
