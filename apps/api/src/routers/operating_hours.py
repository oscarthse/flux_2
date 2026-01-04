"""
Operating hours router for managing weekly schedule and exceptions.

Provides endpoints for:
- Viewing/updating regular weekly schedule
- Managing service period exceptions (holidays, closures)
"""
from datetime import date, time
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.core.deps import get_current_user
from src.db.session import get_db
from src.models.operating_hours import OperatingHours, ServicePeriod
from src.models.restaurant import Restaurant
from src.models.user import User
from src.services.operating_hours import OperatingHoursService

router = APIRouter(tags=["operating-hours"])


# ============ Schemas ============

class DaySchedule(BaseModel):
    """Schedule for a single day of the week."""
    day_of_week: int  # 0=Monday, 6=Sunday
    day_name: str
    open_time: Optional[str]  # "HH:MM" or None if closed
    close_time: Optional[str]
    is_closed: bool


class WeeklyScheduleResponse(BaseModel):
    """Complete weekly schedule."""
    schedule: List[DaySchedule]
    source: str  # "inferred", "manual", or "mixed"


class WeeklyScheduleUpdate(BaseModel):
    """Update for weekly schedule."""
    schedule: List[DaySchedule]


class ServicePeriodCreate(BaseModel):
    """Create a service period exception."""
    date: date
    open_time: Optional[str] = None  # "HH:MM" or None
    close_time: Optional[str] = None
    is_closed: bool = False
    reason: Optional[str] = None


class ServicePeriodResponse(BaseModel):
    id: UUID
    date: date
    open_time: Optional[str]
    close_time: Optional[str]
    is_closed: bool
    reason: Optional[str]

    model_config = ConfigDict(from_attributes=True)


class ServicePeriodListResponse(BaseModel):
    periods: List[ServicePeriodResponse]
    total: int


# ============ Helper Functions ============

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def get_user_restaurant(db: Session, user: User) -> Restaurant:
    """Get restaurant for current user, raise 404 if not found."""
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == user.id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    return restaurant


def time_to_str(t: Optional[time]) -> Optional[str]:
    """Convert time object to HH:MM string."""
    if t is None:
        return None
    return t.strftime("%H:%M")


def str_to_time(s: Optional[str]) -> Optional[time]:
    """Convert HH:MM string to time object."""
    if s is None:
        return None
    try:
        h, m = map(int, s.split(":"))
        if not (0 <= h <= 23 and 0 <= m <= 59):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid time format: {s}. Hours must be 0-23, minutes 0-59."
            )
        return time(h, m)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid time format: {s}. Expected HH:MM format."
        )


# ============ Endpoints ============

@router.get("/operating-hours", response_model=WeeklyScheduleResponse)
def get_operating_hours(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get weekly operating schedule.

    Returns manual schedule if set, otherwise inferred from transaction history.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Check for manual schedule
    manual_hours = db.query(OperatingHours).filter(
        OperatingHours.restaurant_id == restaurant.id
    ).all()

    if manual_hours:
        # Build schedule from manual data
        manual_by_day = {h.day_of_week: h for h in manual_hours}
        schedule = []
        for i, day_name in enumerate(DAY_NAMES):
            if i in manual_by_day:
                h = manual_by_day[i]
                schedule.append(DaySchedule(
                    day_of_week=i,
                    day_name=day_name,
                    open_time=time_to_str(h.open_time),
                    close_time=time_to_str(h.close_time),
                    is_closed=h.is_closed
                ))
            else:
                schedule.append(DaySchedule(
                    day_of_week=i,
                    day_name=day_name,
                    open_time=None,
                    close_time=None,
                    is_closed=True
                ))

        return WeeklyScheduleResponse(schedule=schedule, source="manual")

    # Fall back to inferred schedule
    service = OperatingHoursService(db)
    inferred = service.calculate_standard_hours(restaurant.id)

    schedule = []
    for i, day_name in enumerate(DAY_NAMES):
        if day_name in inferred and inferred[day_name]:
            schedule.append(DaySchedule(
                day_of_week=i,
                day_name=day_name,
                open_time=inferred[day_name]["open"],
                close_time=inferred[day_name]["close"],
                is_closed=False
            ))
        else:
            schedule.append(DaySchedule(
                day_of_week=i,
                day_name=day_name,
                open_time=None,
                close_time=None,
                is_closed=True
            ))

    return WeeklyScheduleResponse(schedule=schedule, source="inferred")


@router.put("/operating-hours", response_model=WeeklyScheduleResponse)
def update_operating_hours(
    update: WeeklyScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save weekly operating schedule.

    Replaces any existing manual schedule.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Delete existing schedule
    db.query(OperatingHours).filter(
        OperatingHours.restaurant_id == restaurant.id
    ).delete()

    # Insert new schedule
    for day in update.schedule:
        hours = OperatingHours(
            restaurant_id=restaurant.id,
            day_of_week=day.day_of_week,
            open_time=str_to_time(day.open_time),
            close_time=str_to_time(day.close_time),
            is_closed=day.is_closed
        )
        db.add(hours)

    db.commit()

    # Return updated schedule
    return get_operating_hours(db, current_user)


@router.get("/service-periods", response_model=ServicePeriodListResponse)
def list_service_periods(
    start_date: Optional[date] = Query(None, description="Filter from date"),
    end_date: Optional[date] = Query(None, description="Filter to date"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List service period exceptions (holidays, closures).
    """
    restaurant = get_user_restaurant(db, current_user)

    query = select(ServicePeriod).where(
        ServicePeriod.restaurant_id == restaurant.id
    )

    if start_date:
        query = query.where(ServicePeriod.date >= start_date)
    if end_date:
        query = query.where(ServicePeriod.date <= end_date)

    query = query.order_by(ServicePeriod.date.desc())
    periods = db.execute(query).scalars().all()

    return ServicePeriodListResponse(
        periods=[
            ServicePeriodResponse(
                id=p.id,
                date=p.date,
                open_time=time_to_str(p.open_time),
                close_time=time_to_str(p.close_time),
                is_closed=p.is_closed,
                reason=p.reason
            )
            for p in periods
        ],
        total=len(periods)
    )


@router.post("/service-periods", response_model=ServicePeriodResponse, status_code=status.HTTP_201_CREATED)
def create_service_period(
    period: ServicePeriodCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a service period exception.

    Use for holidays, special hours, or closures.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Check for existing entry on this date
    existing = db.query(ServicePeriod).filter(
        ServicePeriod.restaurant_id == restaurant.id,
        ServicePeriod.date == period.date
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Service period already exists for {period.date}"
        )

    db_period = ServicePeriod(
        restaurant_id=restaurant.id,
        date=period.date,
        open_time=str_to_time(period.open_time),
        close_time=str_to_time(period.close_time),
        is_closed=period.is_closed,
        reason=period.reason
    )
    db.add(db_period)
    db.commit()
    db.refresh(db_period)

    return ServicePeriodResponse(
        id=db_period.id,
        date=db_period.date,
        open_time=time_to_str(db_period.open_time),
        close_time=time_to_str(db_period.close_time),
        is_closed=db_period.is_closed,
        reason=db_period.reason
    )


@router.delete("/service-periods/{period_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service_period(
    period_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete a service period exception.
    """
    restaurant = get_user_restaurant(db, current_user)

    period = db.query(ServicePeriod).filter(
        ServicePeriod.id == period_id,
        ServicePeriod.restaurant_id == restaurant.id
    ).first()

    if not period:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Service period not found"
        )

    db.delete(period)
    db.commit()
