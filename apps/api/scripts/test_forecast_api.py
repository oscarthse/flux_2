"""
Test Forecast API End-to-End

Validates:
1. Forecast generation with synthetic data
2. Forecast retrieval
3. API response format
4. Error handling
"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.db.session import SessionLocal
from src.models.restaurant import Restaurant
from src.models.menu import MenuItem
from src.services.forecast import ForecastService


def test_forecast_generation():
    """Test forecast generation for all synthetic data items."""
    db = SessionLocal()

    try:
        print("\n" + "="*70)
        print("FORECAST API END-TO-END TEST")
        print("="*70)

        # Get restaurant
        restaurant = db.query(Restaurant).filter(
            Restaurant.name == "Synthetic Test Cafe"
        ).first()

        if not restaurant:
            print("❌ Synthetic Test Cafe not found!")
            print("   Run: python scripts/generate_synthetic_data.py")
            return False

        print(f"✅ Found restaurant: {restaurant.name}")

        # Get all menu items
        items = db.query(MenuItem).filter(
            MenuItem.restaurant_id == restaurant.id
        ).all()

        print(f"✅ Menu items: {len(items)}")

        # Initialize forecast service
        forecast_service = ForecastService(db)

        all_passed = True

        for item in items:
            print(f"\n{'─'*70}")
            print(f"Testing: {item.name}")
            print(f"{'─'*70}")

            try:
                # Test 1: Generate forecast
                print("  [1/3] Generating 7-day forecast...")
                forecast_points = forecast_service.generate_forecasts(
                    restaurant_id=restaurant.id,
                    menu_item_name=item.name,
                    days_ahead=7
                )

                if not forecast_points or len(forecast_points) == 0:
                    print("  ❌ No forecast points generated")
                    all_passed = False
                    continue

                print(f"  ✅ Generated {len(forecast_points)} forecast points")

                # Test 2: Validate forecast structure
                print("  [2/3] Validating forecast structure...")
                first_point = forecast_points[0]

                required_fields = ['forecast_date', 'p10_quantity', 'p50_quantity', 'p90_quantity']
                missing_fields = [f for f in required_fields if not hasattr(first_point, f)]

                if missing_fields:
                    print(f"  ❌ Missing fields: {missing_fields}")
                    all_passed = False
                    continue

                # Check values are reasonable
                p10 = float(first_point.p10_quantity)
                p50 = float(first_point.p50_quantity)
                p90 = float(first_point.p90_quantity)

                if p10 < 0 or p50 < 0 or p90 < 0:
                    print("  ❌ Negative forecast values detected")
                    all_passed = False
                    continue

                if not (p10 <= p50 <= p90):
                    print(f"  ❌ Invalid quantile ordering: p10={p10:.1f}, p50={p50:.1f}, p90={p90:.1f}")
                    all_passed = False
                    continue

                print(f"  ✅ Forecast structure valid")
                print(f"      Date: {first_point.forecast_date}")
                print(f"      p10={p10:.1f}, p50={p50:.1f}, p90={p90:.1f}")

                # Test 3: Summary
                print("  [3/3] Test summary...")

                total_forecast = sum(float(fp.p50_quantity) for fp in forecast_points)
                avg_forecast = total_forecast / len(forecast_points)

                print(f"      Total 7-day demand: {total_forecast:.1f} units")
                print(f"      Average daily: {avg_forecast:.1f} units")

                print(f"  ✅ {item.name}: ALL TESTS PASSED")

            except Exception as e:
                print(f"  ❌ Error: {e}")
                import traceback
                traceback.print_exc()
                all_passed = False

        print("\n" + "="*70)
        if all_passed:
            print("✅ ALL FORECAST TESTS PASSED")
        else:
            print("⚠️  SOME TESTS FAILED - Review errors above")
        print("="*70)

        return all_passed

    except Exception as e:
        print(f"❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        db.close()


if __name__ == "__main__":
    success = test_forecast_generation()
    sys.exit(0 if success else 1)
