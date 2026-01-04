import pytest
from datetime import datetime, date, timedelta
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.inventory import InventorySnapshot
from src.models.menu import MenuItem
from src.models.restaurant import Restaurant
from src.models.user import User
from src.services.data_health import DataHealthService
from src.core.config import get_settings

settings = get_settings()

@pytest.fixture
def db_session():
    """Create a database session for testing."""
    engine = create_engine(settings.DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

@pytest.fixture
def test_restaurant_and_user(db_session):
    """Create a test restaurant and user."""
    user = User(email=f"stockout_test_{uuid4()}@example.com", hashed_password="pw")
    db_session.add(user)
    db_session.flush()

    restaurant = Restaurant(name=f"Stockout Test {uuid4()}", owner_id=user.id)
    db_session.add(restaurant)
    db_session.commit()
    db_session.refresh(restaurant)

    return restaurant, user

@pytest.fixture
def test_item(db_session, test_restaurant_and_user):
    restaurant, _ = test_restaurant_and_user
    item = MenuItem(
        restaurant_id=restaurant.id,
        name=f"Item {uuid4()}",
        price=10.0,
        is_active=True
    )
    db_session.add(item)
    db_session.commit()
    return item

class TestStockoutTracking:

    def test_stockout_health_score_impact(self, db_session, test_restaurant_and_user, test_item):
        """Test that stockout data presence affects accuracy score."""
        restaurant, _ = test_restaurant_and_user
        service = DataHealthService(db_session)

        # Initial score: 0% accuracy (no stockout data)
        # Note: Completeness/Timeliness will be 0 too due to lack of history, but we check accuracy component
        score = service.calculate_score(restaurant.id)
        assert score.accuracy_score == 0

        # Add a snapshot without stockout
        snapshot = InventorySnapshot(
            restaurant_id=restaurant.id,
            menu_item_id=test_item.id,
            date=date.today(),
            available_qty=10,
            stockout_flag='N',
            source='manual'
        )
        db_session.add(snapshot)
        db_session.commit()

        score = service.calculate_score(restaurant.id)
        assert score.accuracy_score == 50  # Partial credit for tracking

        # Add a stockout
        snapshot2 = InventorySnapshot(
            restaurant_id=restaurant.id,
            menu_item_id=test_item.id,
            date=date.today() - timedelta(days=1),
            stockout_flag='Y',
            source='manual'
        )
        db_session.add(snapshot2)
        db_session.commit()

        score = service.calculate_score(restaurant.id)
        assert score.accuracy_score == 100  # Full credit for capturing stockouts

    def test_create_snapshot(self, db_session, test_restaurant_and_user, test_item):
        """Test creating an inventory snapshot manually."""
        restaurant, _ = test_restaurant_and_user

        # Create
        snap = InventorySnapshot(
             restaurant_id=restaurant.id,
             menu_item_id=test_item.id,
             date=date.today(),
             available_qty=20,
             stockout_flag='N'
        )
        db_session.add(snap)
        db_session.commit()

        # Verify
        saved = db_session.query(InventorySnapshot).filter_by(id=snap.id).first()
        assert saved is not None
        assert saved.available_qty == 20
        assert saved.stockout_flag == 'N'

    def test_unique_constraint(self, db_session, test_restaurant_and_user, test_item):
        """Ensure we can't create duplicate snapshots for same item/day."""
        restaurant, _ = test_restaurant_and_user
        today = date.today()

        snap1 = InventorySnapshot(
             restaurant_id=restaurant.id,
             menu_item_id=test_item.id,
             date=today,
             stockout_flag='N'
        )
        db_session.add(snap1)
        db_session.commit()

        snap2 = InventorySnapshot(
             restaurant_id=restaurant.id,
             menu_item_id=test_item.id,
             date=today,
             stockout_flag='Y'
        )
        db_session.add(snap2)

        with pytest.raises(Exception): # IntegrityError
            db_session.commit()
        db_session.rollback()


class TestDetectStockoutsEndpoint:
    """Tests for POST /api/inventory/detect-stockouts endpoint."""

    def test_detect_stockouts_returns_empty_for_new_restaurant(
        self, client, auth_headers_with_restaurant, db, test_user_with_restaurant
    ):
        """Should return empty list for restaurant with no transaction history."""
        response = client.post(
            "/api/inventory/detect-stockouts",
            headers=auth_headers_with_restaurant,
            json={"days_to_analyze": 30, "save_results": False}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["total_detected"] == 0
        assert data["saved_count"] == 0
        assert data["detected_stockouts"] == []
