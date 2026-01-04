"""
Test stockout detection on synthetic data.

Validates that the velocity-based stockout detection correctly identifies
the ground truth stockouts we planted in the synthetic data.
"""
import sys
from pathlib import Path
from datetime import date

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from sqlalchemy import select, func
from src.db.session import SessionLocal
from src.models.restaurant import Restaurant
from src.models.inventory import InventorySnapshot
from src.models.menu import MenuItem
from src.services.stockout_detection import StockoutDetectionService


def test_stockout_detection():
    """Test velocity-based stockout detection against ground truth."""
    db = SessionLocal()

    try:
        # Find the test restaurant
        restaurant = db.query(Restaurant).filter(
            Restaurant.name == "Test Stockout Restaurant"
        ).first()

        if not restaurant:
            print("❌ Test restaurant not found. Run generate_synthetic_stockout_data.py first.")
            return

        print(f"📊 Testing stockout detection on: {restaurant.name}")
        print(f"   Restaurant ID: {restaurant.id}\n")

        # Get ground truth stockouts from Transaction.stockout_occurred flag
        # (synthetic data sets this flag on days with stockouts)
        from src.models.transaction import Transaction, TransactionItem
        ground_truth_stmt = (
            select(Transaction.transaction_date)
            .where(
                Transaction.restaurant_id == restaurant.id,
                Transaction.stockout_occurred == True
            )
            .order_by(Transaction.transaction_date)
        )

        ground_truth_tx_dates = set(db.execute(ground_truth_stmt).scalars().all())

        # For Burger specifically, find days with zero sales (these should be stockouts)
        # Get all transaction dates
        all_tx_dates_stmt = (
            select(func.distinct(Transaction.transaction_date))
            .where(
                Transaction.restaurant_id == restaurant.id
            )
        )
        all_tx_dates = set(db.execute(all_tx_dates_stmt).scalars().all())

        # Get dates where Burger had sales
        burger_sales_stmt = (
            select(func.distinct(Transaction.transaction_date))
            .join(TransactionItem, TransactionItem.transaction_id == Transaction.id)
            .where(
                Transaction.restaurant_id == restaurant.id,
                TransactionItem.menu_item_name == 'Burger'
            )
        )
        burger_sale_dates = set(db.execute(burger_sales_stmt).scalars().all())

        # Days where there were transactions but Burger had zero sales = stockout days
        burger_zero_days = all_tx_dates - burger_sale_dates

        # Ground truth is intersection of stockout_occurred days and burger zero days
        ground_truth_dates = {('Burger', d) for d in burger_zero_days if d in ground_truth_tx_dates}

        print(f"📍 Ground Truth Stockouts: {len(ground_truth_dates)}")
        for item_name, stockout_date in sorted(ground_truth_dates):
            print(f"   - {item_name} on {stockout_date}")

        # Run stockout detection
        print(f"\n🔍 Running velocity-based stockout detection...")
        detection_service = StockoutDetectionService(db)

        detected_stockouts = detection_service.detect_likely_stockouts(
            restaurant_id=restaurant.id,
            days_to_analyze=90
        )

        print(f"   Detected: {len(detected_stockouts)} potential stockouts\n")

        # Analyze results
        detected_dates = {(s.item_name, s.detected_date) for s in detected_stockouts}

        # True Positives: In both ground truth and detected
        true_positives = ground_truth_dates & detected_dates

        # False Negatives: In ground truth but not detected
        false_negatives = ground_truth_dates - detected_dates

        # False Positives: Detected but not in ground truth
        false_positives = detected_dates - ground_truth_dates

        # Calculate metrics
        precision = len(true_positives) / len(detected_dates) if detected_dates else 0
        recall = len(true_positives) / len(ground_truth_dates) if ground_truth_dates else 0
        f1_score = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

        print("📈 Detection Performance:")
        print(f"   True Positives: {len(true_positives)}")
        print(f"   False Positives: {len(false_positives)}")
        print(f"   False Negatives: {len(false_negatives)}")
        print(f"\n   Precision: {precision:.2%}")
        print(f"   Recall: {recall:.2%}")
        print(f"   F1 Score: {f1_score:.2%}")

        # Show details
        if true_positives:
            print(f"\n✅ Correctly Detected ({len(true_positives)}):")
            for item_name, stockout_date in sorted(true_positives):
                matching = [s for s in detected_stockouts if s.item_name == item_name and s.detected_date == stockout_date]
                if matching:
                    print(f"   - {item_name} on {stockout_date} (confidence: {matching[0].confidence:.2f})")

        if false_negatives:
            print(f"\n❌ Missed Stockouts ({len(false_negatives)}):")
            for item_name, stockout_date in sorted(false_negatives):
                print(f"   - {item_name} on {stockout_date}")

        if false_positives:
            print(f"\n⚠️  False Alarms ({len(false_positives)}):")
            for item_name, stockout_date in sorted(false_positives):
                matching = [s for s in detected_stockouts if s.item_name == item_name and s.detected_date == stockout_date]
                if matching:
                    print(f"   - {item_name} on {stockout_date} (confidence: {matching[0].confidence:.2f}, reason: {matching[0].reason})")

        # Test velocity calculation for each item
        print(f"\n📊 Velocity Analysis:")
        menu_items = db.query(MenuItem).filter(MenuItem.restaurant_id == restaurant.id).all()

        for menu_item in menu_items:
            velocity, active_days = detection_service.calculate_item_velocity(
                restaurant_id=restaurant.id,
                item_name=menu_item.name,
                days_lookback=14
            )
            print(f"   {menu_item.name}:")
            print(f"     - Velocity: {velocity:.2f} units/day")
            print(f"     - Active days: {active_days}/14")
            print(f"     - Classification: {'HIGH' if velocity >= 3.0 else 'MEDIUM' if velocity >= 1.0 else 'LOW'}")

        # Overall assessment
        print(f"\n🎯 Overall Assessment:")
        if recall >= 0.8 and precision >= 0.6:
            print(f"   ✅ PASS - Stockout detection is working well!")
            print(f"      High recall ({recall:.0%}) means we catch most real stockouts.")
            print(f"      Good precision ({precision:.0%}) means low false alarm rate.")
        elif recall >= 0.6:
            print(f"   ⚠️  ACCEPTABLE - Detection works but could be improved.")
            print(f"      Recall: {recall:.0%}, Precision: {precision:.0%}")
        else:
            print(f"   ❌ FAIL - Detection needs improvement.")
            print(f"      Too many missed stockouts (recall: {recall:.0%})")

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()

    finally:
        db.close()


if __name__ == "__main__":
    test_stockout_detection()
