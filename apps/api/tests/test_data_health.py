import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.menu import MenuItem
from src.models.inventory import InventorySnapshot
from src.models.restaurant import Restaurant
from src.models.transaction import Transaction
from src.models.data_upload import DataUpload
from src.schemas.data import UploadStatus
from src.models.user import User
from src.models.data_health import DataHealthScore
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
def test_restaurant(db_session):
    """Create a test restaurant."""
    user = User(email=f"health_test_{uuid4()}@example.com", hashed_password="pw")
    db_session.add(user)
    db_session.flush()

    restaurant = Restaurant(name=f"Health Test {uuid4()}", owner_id=user.id)
    db_session.add(restaurant)
    db_session.commit()
    db_session.refresh(restaurant)

    yield restaurant

    # Cleanup
    db_session.query(DataHealthScore).filter(DataHealthScore.restaurant_id == restaurant.id).delete()
    db_session.query(Transaction).filter(Transaction.restaurant_id == restaurant.id).delete()
    db_session.query(DataUpload).filter(DataUpload.restaurant_id == restaurant.id).delete()
    db_session.query(MenuItem).filter(MenuItem.restaurant_id == restaurant.id).delete()
    db_session.query(Restaurant).filter(Restaurant.id == restaurant.id).delete()
    db_session.query(User).filter(User.id == restaurant.owner_id).delete()
    db_session.commit()

class TestDataHealthScoring:

    def test_new_account_low_completeness(self, db_session, test_restaurant):
        """Brand new account with 1 day of data should have low scores."""
        service = DataHealthService(db_session)

        # Create upload
        upload = DataUpload(restaurant_id=test_restaurant.id, status=UploadStatus.COMPLETED.value)
        db_session.add(upload)
        db_session.flush()

        # Add 1 day of transactions
        tx = Transaction(
            restaurant_id=test_restaurant.id,
            transaction_date=datetime.now().date(),
            total_amount=Decimal("100.00"),
            upload_id=upload.id
        )
        db_session.add(tx)

        # Add 1 item
        item = MenuItem(
            restaurant_id=test_restaurant.id,
            name="Burger",
            price=Decimal("10.00"),
            category_path="Entrees > Beef",
            is_active=True
        )
        db_session.add(item)
        db_session.commit()

        score = service.calculate_score(test_restaurant.id)

        # With 0 days range (single day), history score is 0
        # Completeness = (0 * 0.7) + (100 * 0.3) = 30 (item is categorized)
        # But overall is high due to timeliness (100) and accuracy (100)
        # Let's just verify completeness is low and we get the right recommendation
        assert score.completeness_score < 50

        # Check recommendations include completeness
        recs = score.recommendations
        assert any(r['type'] == 'completeness' for r in recs)

    def test_stale_data_low_timeliness(self, db_session, test_restaurant):
        """Old data (last upload > 30 days ago) should have low timeliness."""
        service = DataHealthService(db_session)

        # Create upload
        upload = DataUpload(restaurant_id=test_restaurant.id, status=UploadStatus.COMPLETED.value)
        db_session.add(upload)
        db_session.flush()

        # Add transaction 40 days ago
        old_date = datetime.now().date() - timedelta(days=40)
        tx = Transaction(
            restaurant_id=test_restaurant.id,
            transaction_date=old_date,
            total_amount=Decimal("100.00"),
            upload_id=upload.id
        )
        db_session.add(tx)
        db_session.commit()

        score = service.calculate_score(test_restaurant.id)

        # Timeliness should be 0 for >30 days lag
        assert score.timeliness_score == 0

        recs = score.recommendations
        stale_rec = next((r for r in recs if r['type'] == 'timeliness'), None)
        assert stale_rec is not None
        assert "Data is Stale" in stale_rec['title']

    def test_uncategorized_items_impact(self, db_session, test_restaurant):
        """Uncategorized items should lower completeness score."""
        service = DataHealthService(db_session)

        # Create upload
        upload = DataUpload(restaurant_id=test_restaurant.id, status=UploadStatus.COMPLETED.value)
        db_session.add(upload)
        db_session.flush()

        # Add 90 days history for max history score
        base_date = datetime.now()
        tx1 = Transaction(restaurant_id=test_restaurant.id, transaction_date=(base_date - timedelta(days=90)).date(), total_amount=Decimal("100"), upload_id=upload.id)
        tx2 = Transaction(restaurant_id=test_restaurant.id, transaction_date=base_date.date(), total_amount=Decimal("100"), upload_id=upload.id)
        db_session.add_all([tx1, tx2])

        # Add 10 uncategorized items
        for i in range(10):
            db_session.add(MenuItem(
                restaurant_id=test_restaurant.id,
                name=f"Item {i}",
                price=Decimal("10.00"),
                category_path=None, # UN-CATEGORIZED
                is_active=True
            ))
        db_session.commit()

        score = service.calculate_score(test_restaurant.id)

        # History score is 100, but Categorization score is 0
        # Weighted: 100 * 0.7 + 0 * 0.3 = 70
        assert score.completeness_score == 70

        recs = score.recommendations
        assert any(r['action'] == 'review_items' for r in recs)

    def test_perfect_data(self, db_session, test_restaurant):
        """Perfect data should yield 100% score."""
        service = DataHealthService(db_session)

        # Create upload
        upload = DataUpload(restaurant_id=test_restaurant.id, status=UploadStatus.COMPLETED.value)
        db_session.add(upload)
        db_session.flush()

        # 1. 90 days history
        base_date = datetime.now()

        # Insert 91 transactions (days 0-90) to get exactly 90-day range
        transactions = []
        for i in range(91):  # 0 to 90 inclusive = 91 transactions
             transactions.append(Transaction(
                restaurant_id=test_restaurant.id,
                transaction_date=(base_date - timedelta(days=i)).date(),
                total_amount=Decimal("100"),
                upload_id=upload.id
            ))
        db_session.add_all(transactions)

        # Add categorized item
        db_session.add(MenuItem(
            restaurant_id=test_restaurant.id,
            name="Categorized Item",
            price=Decimal("10.00"),
            category_path="Entrees",
            is_active=True
        ))

        # Add stockout data for accuracy score
        db_session.add(InventorySnapshot(
            restaurant_id=test_restaurant.id,
            menu_item_id=test_restaurant.menu_items[0].id if test_restaurant.menu_items else uuid4(),
            date=base_date.date(),
            stockout_flag='Y',
            source='manual'
        ))

        db_session.commit()

        score = service.calculate_score(test_restaurant.id)

        # With 90-day range (91 distinct dates), all scores should be 100
        assert score.completeness_score == 100
        assert score.timeliness_score == 100
        assert score.accuracy_score == 100
        # Consistency: 91 active days / 90 day range = ratio > 1 = 100%
        assert score.consistency_score == 100
        assert score.overall_score == 100
