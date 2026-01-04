
import pytest
from datetime import date, time, timedelta
from uuid import uuid4
from decimal import Decimal

from src.models.transaction import Transaction
from src.services.operating_hours import OperatingHoursService

def test_calculate_standard_hours(db, test_user_with_restaurant):
    """Verify inference of standard hours from history."""
    _, test_restaurant = test_user_with_restaurant

    # Create historical data for 3 Mondays
    # Monday 1: 11:00 - 22:00
    # Monday 2: 11:15 - 22:10
    # Monday 3: 10:55 - 21:50
    # Expect median around 11:00 - 22:00

    base_date = date.today()
    # Find a Monday
    while base_date.weekday() != 0:
        base_date -= timedelta(days=1)

    dates_times = [
        (base_date, time(11, 0), time(22, 0)),
        (base_date - timedelta(days=7), time(11, 15), time(22, 10)),
        (base_date - timedelta(days=14), time(10, 55), time(21, 50))
    ]

    for d, start, end in dates_times:
        tx = Transaction(
            restaurant_id=test_restaurant.id,
            transaction_date=d,
            total_amount=Decimal("100.00"),
            first_order_time=start,
            last_order_time=end,
            is_promo=False
        )
        db.add(tx)
    db.commit()

    # Execute service
    service = OperatingHoursService(db)
    hours = service.calculate_standard_hours(test_restaurant.id)

    # Verify Monday
    monday_hours = hours.get("Monday")
    assert monday_hours is not None

    # Median of 11:00 (660), 11:15 (675), 10:55 (655) -> 660 mins -> 11:00
    assert monday_hours["open"] == "11:00"

    # Median of 22:00 (1320), 22:10 (1330), 21:50 (1310) -> 1320 mins -> 22:00
    assert monday_hours["close"] == "22:00"

    # Verify Tuesday (no data)
    assert hours.get("Tuesday") is None


def test_midnight_crossing_closing_times(db, test_user_with_restaurant):
    """
    Verify that closing times around midnight are calculated correctly.

    Example: If a bar closes at 23:50, 00:10, and 00:30 on different days,
    the median should be ~00:10, NOT some midday time like 12:00.
    """
    _, test_restaurant = test_user_with_restaurant

    # Create historical data for 3 Saturdays with midnight-crossing hours
    base_date = date.today()
    # Find a Saturday
    while base_date.weekday() != 5:
        base_date -= timedelta(days=1)

    # Simulating late-night bar:
    # Saturday 1: Opens 20:00, closes 23:50 (1430 min from midnight)
    # Saturday 2: Opens 20:15, closes 00:10 (10 min from midnight)
    # Saturday 3: Opens 19:45, closes 00:30 (30 min from midnight)
    # Expected median close: 00:10 (normalized via 4 AM offset logic)
    dates_times = [
        (base_date, time(20, 0), time(23, 50)),
        (base_date - timedelta(days=7), time(20, 15), time(0, 10)),
        (base_date - timedelta(days=14), time(19, 45), time(0, 30)),
    ]

    for d, start, end in dates_times:
        tx = Transaction(
            restaurant_id=test_restaurant.id,
            transaction_date=d,
            total_amount=Decimal("500.00"),
            first_order_time=start,
            last_order_time=end,
            is_promo=False
        )
        db.add(tx)
    db.commit()

    service = OperatingHoursService(db)
    hours = service.calculate_standard_hours(test_restaurant.id)

    saturday_hours = hours.get("Saturday")
    assert saturday_hours is not None

    # Median of 20:00 (1200 min), 20:15 (1215 min), 19:45 (1185 min) -> 1200 -> 20:00
    assert saturday_hours["open"] == "20:00"

    # For closing times:
    # 23:50 = 1430 min
    # 00:10 = 10 min -> normalized to 10 + 1440 = 1450 min
    # 00:30 = 30 min -> normalized to 30 + 1440 = 1470 min
    # Median of [1430, 1450, 1470] = 1450 min
    # 1450 - 1440 = 10 min = 00:10
    assert saturday_hours["close"] == "00:10", \
        f"Expected 00:10 (midnight crossing), got {saturday_hours['close']}"
