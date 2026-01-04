"""
Integration tests for operating hours API router.
"""
import pytest
from datetime import date, timedelta
from decimal import Decimal


class TestOperatingHoursRouter:
    """Tests for /api/operating-hours endpoints."""

    def test_get_operating_hours_empty(self, client, auth_headers_with_restaurant, db):
        """Should return inferred schedule (empty if no transactions)."""
        response = client.get(
            "/api/operating-hours",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 200
        data = response.json()
        assert "schedule" in data
        assert len(data["schedule"]) == 7  # One per day
        assert data["source"] in ["inferred", "manual"]

    def test_update_operating_hours(self, client, auth_headers_with_restaurant, db):
        """Should save and return updated weekly schedule."""
        schedule = [
            {"day_of_week": 0, "day_name": "Monday", "open_time": "11:00", "close_time": "22:00", "is_closed": False},
            {"day_of_week": 1, "day_name": "Tuesday", "open_time": "11:00", "close_time": "22:00", "is_closed": False},
            {"day_of_week": 2, "day_name": "Wednesday", "open_time": "11:00", "close_time": "22:00", "is_closed": False},
            {"day_of_week": 3, "day_name": "Thursday", "open_time": "11:00", "close_time": "22:00", "is_closed": False},
            {"day_of_week": 4, "day_name": "Friday", "open_time": "11:00", "close_time": "23:00", "is_closed": False},
            {"day_of_week": 5, "day_name": "Saturday", "open_time": "10:00", "close_time": "23:00", "is_closed": False},
            {"day_of_week": 6, "day_name": "Sunday", "open_time": None, "close_time": None, "is_closed": True},
        ]

        response = client.put(
            "/api/operating-hours",
            headers=auth_headers_with_restaurant,
            json={"schedule": schedule}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["source"] == "manual"
        assert len(data["schedule"]) == 7

        # Verify Sunday is closed
        sunday = next(d for d in data["schedule"] if d["day_name"] == "Sunday")
        assert sunday["is_closed"] is True

        # Verify Friday extended hours
        friday = next(d for d in data["schedule"] if d["day_name"] == "Friday")
        assert friday["close_time"] == "23:00"


class TestServicePeriodsRouter:
    """Tests for /api/service-periods endpoints."""

    def test_list_service_periods_empty(self, client, auth_headers_with_restaurant, db):
        """Should return empty list for restaurant with no exceptions."""
        response = client.get(
            "/api/service-periods",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["periods"] == []

    def test_create_service_period_holiday(self, client, auth_headers_with_restaurant, db):
        """Should create a holiday closure."""
        christmas = date.today().replace(month=12, day=25)
        if christmas < date.today():
            christmas = christmas.replace(year=christmas.year + 1)

        response = client.post(
            "/api/service-periods",
            headers=auth_headers_with_restaurant,
            json={
                "date": christmas.isoformat(),
                "is_closed": True,
                "reason": "Christmas Day"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_closed"] is True
        assert data["reason"] == "Christmas Day"

    def test_create_service_period_special_hours(self, client, auth_headers_with_restaurant, db):
        """Should create a day with special hours."""
        new_years_eve = date.today().replace(month=12, day=31)
        if new_years_eve < date.today():
            new_years_eve = new_years_eve.replace(year=new_years_eve.year + 1)

        response = client.post(
            "/api/service-periods",
            headers=auth_headers_with_restaurant,
            json={
                "date": new_years_eve.isoformat(),
                "open_time": "18:00",
                "close_time": "02:00",
                "is_closed": False,
                "reason": "New Year's Eve"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_closed"] is False
        assert data["open_time"] == "18:00"
        assert data["close_time"] == "02:00"

    def test_delete_service_period(self, client, auth_headers_with_restaurant, db, test_user_with_restaurant):
        """Should delete a service period."""
        from src.models.operating_hours import ServicePeriod
        _, restaurant = test_user_with_restaurant

        # Create a period directly
        period = ServicePeriod(
            restaurant_id=restaurant.id,
            date=date.today() + timedelta(days=30),
            is_closed=True,
            reason="Test"
        )
        db.add(period)
        db.commit()

        response = client.delete(
            f"/api/service-periods/{period.id}",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 204

        # Verify deleted
        deleted = db.query(ServicePeriod).filter(ServicePeriod.id == period.id).first()
        assert deleted is None

    def test_create_duplicate_date_fails(self, client, auth_headers_with_restaurant, db, test_user_with_restaurant):
        """Should reject duplicate date."""
        from src.models.operating_hours import ServicePeriod
        _, restaurant = test_user_with_restaurant

        target_date = date.today() + timedelta(days=60)

        # Create first period
        period = ServicePeriod(
            restaurant_id=restaurant.id,
            date=target_date,
            is_closed=True,
            reason="Already exists"
        )
        db.add(period)
        db.commit()

        # Try to create duplicate
        response = client.post(
            "/api/service-periods",
            headers=auth_headers_with_restaurant,
            json={
                "date": target_date.isoformat(),
                "is_closed": True,
                "reason": "Duplicate"
            }
        )

        assert response.status_code == 409  # Conflict
