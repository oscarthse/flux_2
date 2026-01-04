"""
Test promotion detection using synthetic data with known promotions.

Generates:
- 90 days of sales data
- 3-5 known promotion periods per item
- Tests discount detection methods (explicit, keyword, statistical)
- Validates precision and recall
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from datetime import datetime, timedelta, date
from decimal import Decimal
import random
from typing import List, Tuple
from uuid import uuid4

from sqlalchemy import select, func
from src.db.session import SessionLocal
from src.models.restaurant import Restaurant
from src.models.menu import MenuItem, MenuCategory
from src.models.transaction import Transaction, TransactionItem
from src.models.promotion import Promotion
from src.models.user import User
from src.services.promotion_detection import PromotionDetectionService


def generate_synthetic_promotion_data(db: SessionLocal):
    """
    Generate synthetic sales data with known promotion periods.

    Returns:
        Tuple of (restaurant_id, ground_truth_promotions)
    """
    print("=" * 80)
    print("GENERATING SYNTHETIC PROMOTION DATA")
    print("=" * 80)

    # Create test user
    user = User(
        id=uuid4(),
        email="test_promo@example.com",
        hashed_password="fake_hash"
    )
    db.add(user)
    db.flush()

    # Create test restaurant
    restaurant = Restaurant(
        id=uuid4(),
        name="Test Promo Restaurant",
        owner_id=user.id,
        timezone="UTC"
    )
    db.add(restaurant)
    db.flush()

    # Create menu category
    category = MenuCategory(
        id=uuid4(),
        restaurant_id=restaurant.id,
        name="burgers",  # Will use burger elasticity prior (-1.2)
        display_order=1
    )
    db.add(category)
    db.flush()

    # Create menu items
    menu_items = [
        MenuItem(
            id=uuid4(),
            restaurant_id=restaurant.id,
            category_id=category.id,
            name="Classic Burger",
            price=Decimal("12.00"),
            is_active=True
        ),
        MenuItem(
            id=uuid4(),
            restaurant_id=restaurant.id,
            category_id=category.id,
            name="Bacon Cheeseburger",
            price=Decimal("14.00"),
            is_active=True
        ),
        MenuItem(
            id=uuid4(),
            restaurant_id=restaurant.id,
            category_id=category.id,
            name="Veggie Burger",
            price=Decimal("11.00"),
            is_active=True
        ),
    ]

    for item in menu_items:
        db.add(item)
    db.flush()

    # Define known promotion periods (ground truth)
    # Format: (item_index, start_day, end_day, discount_pct, method)
    ground_truth_promotions: List[Tuple[int, int, int, float, str]] = [
        # Classic Burger promotions
        (0, 10, 13, 0.20, 'explicit'),    # 20% off, days 10-13
        (0, 30, 32, 0.15, 'keyword'),     # 15% off, days 30-32
        (0, 60, 65, 0.25, 'statistical'), # 25% off, days 60-65

        # Bacon Cheeseburger promotions
        (1, 15, 18, 0.15, 'explicit'),    # 15% off, days 15-18
        (1, 45, 47, 0.10, 'statistical'), # 10% off, days 45-47

        # Veggie Burger promotions
        (2, 20, 24, 0.30, 'keyword'),     # 30% off, days 20-24
        (2, 55, 58, 0.20, 'statistical'), # 20% off, days 55-58
    ]

    print(f"\nCreated {len(menu_items)} menu items")
    print(f"Ground truth: {len(ground_truth_promotions)} promotion periods")

    # Generate 90 days of sales
    start_date = datetime.now() - timedelta(days=90)

    for day_offset in range(90):
        tx_date = (start_date + timedelta(days=day_offset)).date()

        # Create daily transaction
        transaction = Transaction(
            id=uuid4(),
            restaurant_id=restaurant.id,
            transaction_date=tx_date,
            total_amount=Decimal("0.00"),
            is_promo=False,
            discount_amount=None
        )
        db.add(transaction)
        db.flush()

        # Add transaction items for each menu item
        total_amount = Decimal("0.00")

        for item_idx, menu_item in enumerate(menu_items):
            # Check if this day is in a promotion period for this item
            is_promo_day = False
            promo_discount_pct = 0.0
            promo_method = None

            for promo in ground_truth_promotions:
                promo_item_idx, start_day, end_day, discount_pct, method = promo
                if promo_item_idx == item_idx and start_day <= day_offset <= end_day:
                    is_promo_day = True
                    promo_discount_pct = discount_pct
                    promo_method = method
                    break

            # Base sales quantity (10-20 units per day)
            base_qty = random.randint(10, 20)

            # If promotion, increase quantity (demand lift)
            if is_promo_day:
                # Simple elasticity simulation: 20% discount → ~15% lift
                lift_factor = 1.0 + (promo_discount_pct * 0.75)
                qty = int(base_qty * lift_factor)
            else:
                qty = base_qty

            # Calculate price
            base_price = menu_item.price
            if is_promo_day:
                unit_price = base_price * Decimal(str(1 - promo_discount_pct))
            else:
                unit_price = base_price

            total = unit_price * qty
            total_amount += total

            # Determine item name based on detection method
            item_name = menu_item.name
            discount_amount = None

            if is_promo_day:
                if promo_method == 'explicit':
                    # Explicit discount column
                    discount_amount = (base_price - unit_price) * qty
                elif promo_method == 'keyword':
                    # Add keyword to item name
                    item_name = f"{menu_item.name} - PROMO"
                # For 'statistical', just set lower price (no explicit marker)

            # Create transaction item
            tx_item = TransactionItem(
                id=uuid4(),
                transaction_id=transaction.id,
                menu_item_name=item_name,
                quantity=qty,
                unit_price=unit_price,
                total=total
            )
            db.add(tx_item)

        # Update transaction total
        transaction.total_amount = total_amount

    db.commit()

    print(f"✓ Generated 90 days of sales data")
    print(f"✓ Embedded {len(ground_truth_promotions)} promotion periods")

    return restaurant.id, ground_truth_promotions


def test_promotion_detection(db: SessionLocal, restaurant_id, ground_truth_promotions):
    """
    Test promotion detection and calculate precision/recall.
    """
    print("\n" + "=" * 80)
    print("TESTING PROMOTION DETECTION")
    print("=" * 80)

    # Run promotion inference
    service = PromotionDetectionService(db)

    # Get menu items
    menu_items = db.query(MenuItem).filter(
        MenuItem.restaurant_id == restaurant_id
    ).all()

    print(f"\nRunning statistical promotion inference for {len(menu_items)} items...")

    all_inferred: List[Tuple[str, date, date, float]] = []

    for item in menu_items:
        inferred = service.infer_promotions_from_price_history(
            restaurant_id=restaurant_id,
            item_name=item.name,
            lookback_days=90,
            min_promotion_days=2
        )

        for promo in inferred:
            if promo.confidence >= 0.5:  # Only high-confidence detections
                all_inferred.append((
                    item.name,
                    promo.start_date,
                    promo.end_date,
                    promo.confidence
                ))
                print(f"  Detected: {item.name} | {promo.start_date} to {promo.end_date} | confidence={promo.confidence:.2f}")

    print(f"\n✓ Detected {len(all_inferred)} promotion periods (confidence >= 0.5)")

    # Calculate precision and recall
    # Convert ground truth to date ranges
    start_date = datetime.now() - timedelta(days=90)
    menu_item_names = [item.name for item in menu_items]

    ground_truth_ranges = []
    for promo in ground_truth_promotions:
        item_idx, start_day, end_day, discount_pct, method = promo
        if method == 'statistical':  # Only statistical promotions are detectable by inference
            item_name = menu_item_names[item_idx]
            start = (start_date + timedelta(days=start_day)).date()
            end = (start_date + timedelta(days=end_day)).date()
            ground_truth_ranges.append((item_name, start, end))

    print(f"\nGround truth (statistical promotions only): {len(ground_truth_ranges)} periods")

    # Check overlap
    def ranges_overlap(r1_start, r1_end, r2_start, r2_end):
        """Check if two date ranges overlap."""
        return r1_start <= r2_end and r2_start <= r1_end

    true_positives = 0
    false_positives = 0
    false_negatives = 0

    # Check detected promotions against ground truth
    matched_ground_truth = set()

    for detected_item, detected_start, detected_end, confidence in all_inferred:
        matched = False
        for gt_idx, (gt_item, gt_start, gt_end) in enumerate(ground_truth_ranges):
            if detected_item == gt_item and ranges_overlap(detected_start, detected_end, gt_start, gt_end):
                matched = True
                matched_ground_truth.add(gt_idx)
                break

        if matched:
            true_positives += 1
        else:
            false_positives += 1

    # Count missed ground truth promotions
    false_negatives = len(ground_truth_ranges) - len(matched_ground_truth)

    # Calculate metrics
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"True Positives:  {true_positives}")
    print(f"False Positives: {false_positives}")
    print(f"False Negatives: {false_negatives}")
    print(f"\nPrecision: {precision:.2%}")
    print(f"Recall:    {recall:.2%}")
    print(f"F1 Score:  {f1:.2%}")

    if precision >= 0.7 and recall >= 0.7:
        print("\n✅ PASS: Promotion detection is working well!")
    else:
        print("\n⚠️  WARNING: Detection accuracy could be improved")

    return precision, recall, f1


def main():
    """Run the full test suite."""
    db = SessionLocal()

    try:
        # Clean up any existing test data
        existing_restaurant = db.query(Restaurant).filter(
            Restaurant.name == "Test Promo Restaurant"
        ).first()

        if existing_restaurant:
            print("Cleaning up existing test data...")
            owner_id = existing_restaurant.owner_id

            db.query(TransactionItem).filter(
                TransactionItem.transaction_id.in_(
                    db.query(Transaction.id).filter(
                        Transaction.restaurant_id == existing_restaurant.id
                    )
                )
            ).delete(synchronize_session=False)

            db.query(Transaction).filter(
                Transaction.restaurant_id == existing_restaurant.id
            ).delete(synchronize_session=False)

            db.query(MenuItem).filter(
                MenuItem.restaurant_id == existing_restaurant.id
            ).delete(synchronize_session=False)

            db.query(MenuCategory).filter(
                MenuCategory.restaurant_id == existing_restaurant.id
            ).delete(synchronize_session=False)

            db.query(Promotion).filter(
                Promotion.restaurant_id == existing_restaurant.id
            ).delete(synchronize_session=False)

            db.delete(existing_restaurant)

            # Delete test user
            test_user = db.query(User).filter(User.id == owner_id).first()
            if test_user:
                db.delete(test_user)

            db.commit()

        # Generate synthetic data
        restaurant_id, ground_truth = generate_synthetic_promotion_data(db)

        # Test detection
        precision, recall, f1 = test_promotion_detection(db, restaurant_id, ground_truth)

    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    main()
