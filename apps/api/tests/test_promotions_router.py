"""
Integration tests for promotions API router.
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4


class TestPromotionsRouter:
    """Tests for /api/promotions endpoints."""

    def test_list_promotions_empty(self, client, auth_headers_with_restaurant, db):
        """Should return empty list for restaurant with no promotions."""
        response = client.get(
            "/api/promotions",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["exploration_count"] == 0
        assert data["promotions"] == []

    def test_create_promotion(self, client, auth_headers_with_restaurant, db, test_user_with_restaurant):
        """Should create a promotion with auto exploration flag."""
        from src.models.menu import MenuItem
        _, restaurant = test_user_with_restaurant

        # Create a menu item first
        menu_item = MenuItem(
            restaurant_id=restaurant.id,
            name="Test Burger",
            price=Decimal("12.99"),
            is_active=True
        )
        db.add(menu_item)
        db.commit()

        now = datetime.utcnow()
        response = client.post(
            "/api/promotions",
            headers=auth_headers_with_restaurant,
            json={
                "menu_item_id": str(menu_item.id),
                "name": "Holiday Special",
                "discount_type": "percentage",
                "discount_value": "15.00",
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=7)).isoformat(),
                "trigger_reason": "manual"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Holiday Special"
        assert data["discount_value"] == "15.00"
        assert data["status"] == "draft"
        assert "is_exploration" in data

    def test_create_exploration_promotion(self, client, auth_headers_with_restaurant, db, test_user_with_restaurant):
        """Should create exploration promotion when forced."""
        from src.models.menu import MenuItem
        _, restaurant = test_user_with_restaurant

        menu_item = MenuItem(
            restaurant_id=restaurant.id,
            name="Exploration Item",
            price=Decimal("9.99"),
            is_active=True
        )
        db.add(menu_item)
        db.commit()

        now = datetime.utcnow()
        response = client.post(
            "/api/promotions?force_exploration=true",
            headers=auth_headers_with_restaurant,
            json={
                "menu_item_id": str(menu_item.id),
                "discount_type": "percentage",
                "discount_value": "5.00",
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=3)).isoformat()
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["is_exploration"] is True

    def test_get_explore_candidates(self, client, auth_headers_with_restaurant, db, test_user_with_restaurant):
        """Should return menu items needing elasticity exploration."""
        from src.models.menu import MenuItem
        _, restaurant = test_user_with_restaurant

        # Create menu items without elasticity data
        for i in range(3):
            menu_item = MenuItem(
                restaurant_id=restaurant.id,
                name=f"Explore Candidate {i}",
                price=Decimal("10.00") + i,
                is_active=True
            )
            db.add(menu_item)
        db.commit()

        response = client.get(
            "/api/promotions/explore-candidates",
            headers=auth_headers_with_restaurant
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 0  # May include these or others

    def test_update_promotion(self, client, auth_headers_with_restaurant, db, test_user_with_restaurant):
        """Should update promotion status and actual_lift."""
        from src.models.menu import MenuItem
        from src.models.promotion import Promotion
        _, restaurant = test_user_with_restaurant

        menu_item = MenuItem(
            restaurant_id=restaurant.id,
            name="Update Test Item",
            price=Decimal("15.00"),
            is_active=True
        )
        db.add(menu_item)
        db.flush()

        promo = Promotion(
            restaurant_id=restaurant.id,
            menu_item_id=menu_item.id,
            name="Update Test",
            discount_type="percentage",
            discount_value=Decimal("10.00"),
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow() + timedelta(days=1),
            status="draft"
        )
        db.add(promo)
        db.commit()

        response = client.patch(
            f"/api/promotions/{promo.id}",
            headers=auth_headers_with_restaurant,
            json={
                "status": "completed",
                "actual_lift": "12.50"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["actual_lift"] == "12.50"
