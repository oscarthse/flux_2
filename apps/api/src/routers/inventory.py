"""
Inventory router for stockout and availability tracking.
"""
from datetime import date
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.core.deps import get_current_user
from src.db.session import get_db
from src.models.inventory import InventorySnapshot
from src.models.menu import MenuItem
from src.models.restaurant import Restaurant
from src.models.user import User


router = APIRouter(prefix="/inventory", tags=["inventory"])


# Schemas
class SnapshotCreate(BaseModel):
    menu_item_id: UUID
    date: date
    available_qty: Optional[int] = None
    stockout_flag: bool = False
    source: str = "manual"


class MarkStockoutRequest(BaseModel):
    menu_item_id: UUID
    date: date


class SnapshotResponse(BaseModel):
    id: UUID
    menu_item_id: UUID
    date: date
    available_qty: Optional[int]
    stockout_flag: str
    source: str

    class Config:
        from_attributes = True


class StockoutListResponse(BaseModel):
    stockouts: List[SnapshotResponse]


@router.post("/snapshots", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
def create_snapshot(
    snapshot: SnapshotCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Record daily inventory availability for a menu item.

    Use this to track how many units were available at start of day
    and whether the item sold out.
    """
    # Get user's restaurant
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    # Verify menu item belongs to restaurant
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == snapshot.menu_item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()
    if not menu_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

    # Check for existing snapshot
    existing = db.query(InventorySnapshot).filter(
        InventorySnapshot.restaurant_id == restaurant.id,
        InventorySnapshot.menu_item_id == snapshot.menu_item_id,
        InventorySnapshot.date == snapshot.date
    ).first()

    if existing:
        # Update existing
        existing.available_qty = snapshot.available_qty
        existing.stockout_flag = 'Y' if snapshot.stockout_flag else 'N'
        existing.source = snapshot.source
        db.commit()
        db.refresh(existing)
        return existing

    # Create new
    db_snapshot = InventorySnapshot(
        restaurant_id=restaurant.id,
        menu_item_id=snapshot.menu_item_id,
        date=snapshot.date,
        available_qty=snapshot.available_qty,
        stockout_flag='Y' if snapshot.stockout_flag else 'N',
        source=snapshot.source
    )
    db.add(db_snapshot)
    db.commit()
    db.refresh(db_snapshot)

    return db_snapshot


@router.post("/mark-stockout", response_model=SnapshotResponse, status_code=status.HTTP_201_CREATED)
def mark_stockout(
    request: MarkStockoutRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Quick endpoint to flag a menu item as sold out on a specific date.

    This is a convenience wrapper around the snapshots endpoint.
    """
    # Get user's restaurant
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    # Verify menu item belongs to restaurant
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == request.menu_item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()
    if not menu_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Menu item not found")

    # Check for existing snapshot
    existing = db.query(InventorySnapshot).filter(
        InventorySnapshot.restaurant_id == restaurant.id,
        InventorySnapshot.menu_item_id == request.menu_item_id,
        InventorySnapshot.date == request.date
    ).first()

    if existing:
        existing.stockout_flag = 'Y'
        existing.source = 'manual'
        db.commit()
        db.refresh(existing)
        return existing

    # Create new stockout record
    db_snapshot = InventorySnapshot(
        restaurant_id=restaurant.id,
        menu_item_id=request.menu_item_id,
        date=request.date,
        stockout_flag='Y',
        source='manual'
    )
    db.add(db_snapshot)
    db.commit()
    db.refresh(db_snapshot)

    return db_snapshot


@router.get("/stockouts", response_model=StockoutListResponse)
def list_stockouts(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List stockout events for the restaurant.

    Useful for displaying in a calendar view.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    query = db.query(InventorySnapshot).filter(
        InventorySnapshot.restaurant_id == restaurant.id,
        InventorySnapshot.stockout_flag == 'Y'
    )

    if start_date:
        query = query.filter(InventorySnapshot.date >= start_date)
    if end_date:
        query = query.filter(InventorySnapshot.date <= end_date)

    stockouts = query.order_by(InventorySnapshot.date.desc()).limit(100).all()

    return StockoutListResponse(stockouts=stockouts)


# Detection schemas
class DetectedStockout(BaseModel):
    menu_item_id: Optional[UUID] = None
    item_name: str
    detected_date: date
    confidence: float
    reason: str


class DetectStockoutsRequest(BaseModel):
    days_to_analyze: int = 30
    save_results: bool = False  # If True, save detected stockouts to InventorySnapshot


class DetectStockoutsResponse(BaseModel):
    detected_stockouts: List[DetectedStockout]
    total_detected: int
    saved_count: int = 0


@router.post("/detect-stockouts", response_model=DetectStockoutsResponse)
def detect_stockouts(
    request: DetectStockoutsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run velocity-based stockout detection on recent transaction history.

    Analyzes item sales patterns to infer likely stockout events.
    Only flags high-velocity items (>= 3 units/day) with zero sales,
    avoiding false positives for naturally low-velocity items.

    Set `save_results=true` to automatically save detected stockouts
    to InventorySnapshot table.
    """
    from src.services.stockout_detection import StockoutDetectionService

    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Restaurant not found")

    # Run detection
    detection_service = StockoutDetectionService(db)
    results = detection_service.detect_likely_stockouts(
        restaurant_id=restaurant.id,
        days_to_analyze=request.days_to_analyze
    )

    # Convert to response format
    detected = [
        DetectedStockout(
            menu_item_id=r.menu_item_id,
            item_name=r.item_name,
            detected_date=r.detected_date,
            confidence=r.confidence,
            reason=r.reason
        )
        for r in results
    ]

    saved_count = 0

    # Optionally save results
    if request.save_results:
        for result in results:
            if not result.menu_item_id:
                continue  # Can't save without menu_item_id

            # Check if already exists
            existing = db.query(InventorySnapshot).filter(
                InventorySnapshot.restaurant_id == restaurant.id,
                InventorySnapshot.menu_item_id == result.menu_item_id,
                InventorySnapshot.date == result.detected_date
            ).first()

            if existing:
                if existing.stockout_flag != 'Y':
                    existing.stockout_flag = 'Y'
                    existing.source = 'inferred'
                    saved_count += 1
            else:
                new_snapshot = InventorySnapshot(
                    restaurant_id=restaurant.id,
                    menu_item_id=result.menu_item_id,
                    date=result.detected_date,
                    stockout_flag='Y',
                    source='inferred'
                )
                db.add(new_snapshot)
                saved_count += 1

        db.commit()

    return DetectStockoutsResponse(
        detected_stockouts=detected,
        total_detected=len(detected),
        saved_count=saved_count
    )
