"""
Restaurant settings endpoints.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text
from pydantic import BaseModel
import json

from src.db.session import get_db
from src.routers.auth import get_current_user
from src.models.user import User
from src.models.restaurant import Restaurant

router = APIRouter(prefix="/api/settings", tags=["settings"])


class FeatureSettings(BaseModel):
    """Feature flags and settings"""
    waste_factors_enabled: bool = True


@router.get("/features", response_model=FeatureSettings)
def get_feature_settings(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get feature flags for current restaurant"""
    # Get user's restaurant
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # Check if waste_factors_enabled setting exists
    result = db.execute(
        text("""
            SELECT setting_value
            FROM restaurant_settings
            WHERE restaurant_id = :restaurant_id
            AND setting_key = 'waste_factors_enabled'
        """),
        {"restaurant_id": restaurant.id}
    ).fetchone()

    if result:
        return FeatureSettings(waste_factors_enabled=result[0].get('enabled', True))

    # Default: waste factors enabled
    return FeatureSettings(waste_factors_enabled=True)


@router.put("/features", response_model=FeatureSettings)
def update_feature_settings(
    settings: FeatureSettings,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update feature flags for current restaurant"""
    # Get user's restaurant
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")

    # Check if setting exists
    existing = db.execute(
        text("""
            SELECT id FROM restaurant_settings
            WHERE restaurant_id = :restaurant_id
            AND setting_key = 'waste_factors_enabled'
        """),
        {"restaurant_id": restaurant.id}
    ).fetchone()

    if existing:
        # Update existing
        db.execute(
            text("""
                UPDATE restaurant_settings
                SET setting_value = CAST(:setting_value AS JSONB), updated_at = NOW()
                WHERE restaurant_id = :restaurant_id
                AND setting_key = 'waste_factors_enabled'
            """),
            {
                "restaurant_id": restaurant.id,
                "setting_value": json.dumps({"enabled": settings.waste_factors_enabled})
            }
        )
    else:
        # Insert new
        db.execute(
            text("""
                INSERT INTO restaurant_settings (restaurant_id, setting_key, setting_value)
                VALUES (:restaurant_id, 'waste_factors_enabled', CAST(:setting_value AS JSONB))
            """),
            {
                "restaurant_id": restaurant.id,
                "setting_value": json.dumps({"enabled": settings.waste_factors_enabled})
            }
        )

    db.commit()
    return settings
