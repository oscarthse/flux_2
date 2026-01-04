"""
Integration tests for menu items API router.

Tests the list, review, update, and merge endpoints.
"""
import pytest
from decimal import Decimal
from sqlalchemy import text

from src.models.menu import MenuItem


@pytest.fixture
def sample_menu_items(db, test_user_with_restaurant):
    """Create sample menu items for testing."""
    _, restaurant = test_user_with_restaurant

    # Clean up any existing menu items first
    db.execute(text("DELETE FROM menu_items WHERE restaurant_id = :rid"), {"rid": restaurant.id})
    db.commit()

    items = [
        MenuItem(
            restaurant_id=restaurant.id,
            name="Caesar Salad",
            price=Decimal("12.00"),
            category_path="Appetizers > Salads > Classic",
            auto_created=True,
            confidence_score=Decimal("0.95"),
            is_active=True
        ),
        MenuItem(
            restaurant_id=restaurant.id,
            name="Mystery Dish",
            price=Decimal("15.00"),
            auto_created=True,
            confidence_score=Decimal("0.45"),  # Low confidence
            is_active=True
        ),
        MenuItem(
            restaurant_id=restaurant.id,
            name="Ribeye Steak",
            price=Decimal("35.00"),
            category_path="Entrees > Beef > Grilled",
            auto_created=False,
            confidence_score=None,
            is_active=True
        ),
    ]

    for item in items:
        db.add(item)
    db.commit()

    for item in items:
        db.refresh(item)

    yield items

    # Cleanup
    db.execute(text("DELETE FROM menu_items WHERE restaurant_id = :rid"), {"rid": restaurant.id})
    db.commit()


class TestListMenuItems:
    """Tests for GET /api/menu-items."""

    def test_list_all_items(self, client, auth_headers_with_restaurant, sample_menu_items):
        """Should list all menu items for restaurant."""
        response = client.get("/api/menu-items", headers=auth_headers_with_restaurant)

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert data["auto_created_count"] == 2
        assert len(data["items"]) == 3

    def test_list_auto_created_only(self, client, auth_headers_with_restaurant, sample_menu_items):
        """Should filter to only auto-created items."""
        response = client.get(
            "/api/menu-items",
            headers=auth_headers_with_restaurant,
            params={"auto_created_only": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert all(item["auto_created"] for item in data["items"])


class TestReviewItems:
    """Tests for GET /api/menu-items/review."""

    def test_get_items_needing_review(self, client, auth_headers_with_restaurant, sample_menu_items):
        """Should return low-confidence auto-created items."""
        response = client.get("/api/menu-items/review", headers=auth_headers_with_restaurant)

        assert response.status_code == 200
        data = response.json()
        # Only "Mystery Dish" has confidence < 0.7
        assert data["total"] == 1
        assert data["items"][0]["name"] == "Mystery Dish"

    def test_custom_confidence_threshold(self, client, auth_headers_with_restaurant, sample_menu_items):
        """Should respect custom confidence threshold."""
        response = client.get(
            "/api/menu-items/review",
            headers=auth_headers_with_restaurant,
            params={"confidence_threshold": 0.99}
        )

        assert response.status_code == 200
        data = response.json()
        # Both auto-created items have confidence < 0.99
        assert data["total"] == 2


class TestUpdateMenuItem:
    """Tests for PATCH /api/menu-items/{id}."""

    def test_update_category_path(self, client, auth_headers_with_restaurant, sample_menu_items):
        """Should update item's category path."""
        item = sample_menu_items[1]  # Mystery Dish

        response = client.patch(
            f"/api/menu-items/{item.id}",
            headers=auth_headers_with_restaurant,
            json={"category_path": "Entrees > Seafood > Fish"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["category_path"] == "Entrees > Seafood > Fish"

    def test_confirm_item(self, client, auth_headers_with_restaurant, sample_menu_items):
        """Should set confidence to 1.0 when confirmed."""
        item = sample_menu_items[1]  # Mystery Dish

        response = client.patch(
            f"/api/menu-items/{item.id}",
            headers=auth_headers_with_restaurant,
            json={"confirmed": True}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["confidence_score"] == "1.00"

    def test_reject_invalid_category_path(self, client, auth_headers_with_restaurant, sample_menu_items):
        """Should reject invalid category paths."""
        item = sample_menu_items[0]

        response = client.patch(
            f"/api/menu-items/{item.id}",
            headers=auth_headers_with_restaurant,
            json={"category_path": "Invalid > Category"}  # Only 2 levels
        )

        assert response.status_code == 400
        assert "Invalid category path" in response.json()["detail"]


class TestMergeMenuItems:
    """Tests for POST /api/menu-items/merge."""

    def test_merge_items(self, client, db, auth_headers_with_restaurant, sample_menu_items):
        """Should merge source item into target."""
        source = sample_menu_items[1]  # Mystery Dish
        target = sample_menu_items[0]  # Caesar Salad

        response = client.post(
            "/api/menu-items/merge",
            headers=auth_headers_with_restaurant,
            json={
                "source_id": str(source.id),
                "target_id": str(target.id)
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["source_deleted"] is True
        assert data["target_item"]["id"] == str(target.id)

        # Verify source is deleted
        db.expire_all()
        deleted = db.query(MenuItem).filter(MenuItem.id == source.id).first()
        assert deleted is None

    def test_merge_same_item(self, client, auth_headers_with_restaurant, sample_menu_items):
        """Should reject merging item with itself."""
        item = sample_menu_items[0]

        response = client.post(
            "/api/menu-items/merge",
            headers=auth_headers_with_restaurant,
            json={
                "source_id": str(item.id),
                "target_id": str(item.id)
            }
        )

        assert response.status_code == 400
        assert "must be different" in response.json()["detail"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
