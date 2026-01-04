"""
Tests for velocity-based stockout detection service.
"""
import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
from uuid import uuid4

from src.models.data_upload import DataUpload
from src.models.menu import MenuItem
from src.models.transaction import Transaction, TransactionItem
from src.services.stockout_detection import StockoutDetectionService, StockoutDetectionResult


class TestVelocityCalculation:
    """Test velocity calculation logic."""

    def test_velocity_calculation_basic(self, db, test_user_with_restaurant):
        """Test that velocity is calculated correctly."""
        _, test_restaurant = test_user_with_restaurant

        # Create transactions with known quantities over 14 days
        # 7 sales of 2 units each = 14 units over 14 days = 1.0 velocity
        for i in range(7):
            tx = Transaction(
                restaurant_id=test_restaurant.id,
                transaction_date=date.today() - timedelta(days=i*2),
                total_amount=Decimal("20.00"),
                is_promo=False
            )
            db.add(tx)
            db.flush()

            item = TransactionItem(
                transaction_id=tx.id,
                menu_item_name="Velocity Test Item",
                quantity=2,
                unit_price=Decimal("10.00"),
                total=Decimal("20.00")
            )
            db.add(item)
        db.commit()

        service = StockoutDetectionService(db)
        velocity, active_days = service.calculate_item_velocity(
            test_restaurant.id, "Velocity Test Item", days_lookback=14
        )

        assert velocity == 1.0  # 14 units / 14 days
        assert active_days == 7


class TestStockoutDetection:
    """Test stockout detection logic."""

    def test_high_velocity_zero_day_detected(self, db, test_user_with_restaurant):
        """High velocity item with zero sales should be flagged."""
        _, test_restaurant = test_user_with_restaurant

        # Create high velocity item in the last 14 days for velocity calculation
        # 5 units/day * 10 days = 50 units in 14 days = ~3.5 velocity
        for i in range(10):
            tx = Transaction(
                restaurant_id=test_restaurant.id,
                transaction_date=date.today() - timedelta(days=i+1),
                total_amount=Decimal("50.00"),
                is_promo=False
            )
            db.add(tx)
            db.flush()

            item = TransactionItem(
                transaction_id=tx.id,
                menu_item_name="High Velocity Item",
                quantity=5,
                unit_price=Decimal("10.00"),
                total=Decimal("50.00")
            )
            db.add(item)

        db.commit()

        service = StockoutDetectionService(db)

        # Verify velocity is high enough
        velocity, active_days = service.calculate_item_velocity(
            test_restaurant.id, "High Velocity Item", days_lookback=14
        )
        assert velocity >= 3.0, f"Velocity should be >= 3.0, got {velocity}"

        # Detect stockouts - should find gaps in the last 30 days
        results = service.detect_likely_stockouts(test_restaurant.id, days_to_analyze=30)

        # Should detect stockouts on zero-sale days
        high_velocity_results = [r for r in results if r.item_name == "High Velocity Item"]
        assert len(high_velocity_results) > 0, \
            f"Should detect stockouts for high velocity item, velocity={velocity}"
        assert all(r.confidence >= 0.65 for r in high_velocity_results)

    def test_low_velocity_item_ignored(self, db, test_user_with_restaurant):
        """Low velocity items should not trigger false positives."""
        _, test_restaurant = test_user_with_restaurant

        # Create low velocity item: 1 sale every 3 days = ~0.33/day
        for i in range(5):
            tx = Transaction(
                restaurant_id=test_restaurant.id,
                transaction_date=date.today() - timedelta(days=i*3),
                total_amount=Decimal("30.00"),
                is_promo=False
            )
            db.add(tx)
            db.flush()

            item = TransactionItem(
                transaction_id=tx.id,
                menu_item_name="Low Velocity Specialty",
                quantity=1,
                unit_price=Decimal("30.00"),
                total=Decimal("30.00")
            )
            db.add(item)
        db.commit()

        service = StockoutDetectionService(db)
        results = service.detect_likely_stockouts(test_restaurant.id, days_to_analyze=30)

        # Low velocity item should NOT be flagged
        low_velocity_results = [r for r in results if r.item_name == "Low Velocity Specialty"]
        assert len(low_velocity_results) == 0, \
            f"Low velocity item should not be flagged, got {len(low_velocity_results)} results"


class TestVelocityThresholds:
    """Test that velocity thresholds are correctly applied."""

    def test_threshold_constants(self):
        """Verify threshold constants match audit recommendations."""
        from src.services.stockout_detection import StockoutDetectionService

        # These align with audit recommendations
        assert StockoutDetectionService.HIGH_VELOCITY_THRESHOLD == 3.0
        assert StockoutDetectionService.LOW_VELOCITY_THRESHOLD == 1.0
        assert StockoutDetectionService.GAP_MULTIPLIER == 3.0
