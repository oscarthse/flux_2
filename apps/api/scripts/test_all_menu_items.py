"""Test forecast generation for all menu items"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.db.session import SessionLocal
from src.models.restaurant import Restaurant
from src.models.menu import MenuItem
from src.services.forecast import ForecastService

db = SessionLocal()

try:
    # Get restaurant
    restaurant = db.query(Restaurant).filter(
        Restaurant.name == "Synthetic Test Cafe"
    ).first()

    if not restaurant:
        print("❌ Restaurant not found!")
        sys.exit(1)

    print(f"✅ Found restaurant: {restaurant.name}\n")

    # Get all menu items
    items = db.query(MenuItem).filter(
        MenuItem.restaurant_id == restaurant.id
    ).all()

    print(f"Testing forecast generation for {len(items)} menu items:\n")
    print("=" * 70)

    forecast_service = ForecastService(db)
    all_passed = True

    for item in items:
        print(f"\n🔮 Testing: {item.name}")
        print("-" * 70)

        try:
            # Generate forecasts
            forecast_points = forecast_service.generate_forecasts(
                restaurant_id=restaurant.id,
                menu_item_name=item.name,
                days_ahead=7
            )

            if not forecast_points or len(forecast_points) == 0:
                print(f"❌ FAILED: No forecast points generated for {item.name}")
                all_passed = False
                continue

            if len(forecast_points) != 7:
                print(f"⚠️  WARNING: Expected 7 points, got {len(forecast_points)}")

            # Validate forecast structure
            print(f"✅ Generated {len(forecast_points)} forecast points")

            # Show first and last forecast
            first = forecast_points[0]
            last = forecast_points[-1]

            print(f"\nFirst day ({first.forecast_date}):")
            print(f"  p10={first.p10_quantity:.1f}, p50={first.p50_quantity:.1f}, p90={first.p90_quantity:.1f}")

            print(f"\nLast day ({last.forecast_date}):")
            print(f"  p10={last.p10_quantity:.1f}, p50={last.p50_quantity:.1f}, p90={last.p90_quantity:.1f}")

            # Calculate total 7-day forecast
            total_p50 = sum(fp.p50_quantity for fp in forecast_points)
            avg_daily = total_p50 / len(forecast_points)

            print(f"\n7-Day Summary:")
            print(f"  Total (p50): {total_p50:.1f} units")
            print(f"  Avg daily: {avg_daily:.1f} units/day")

            # Validate quantile ordering
            has_errors = False
            for fp in forecast_points:
                if not (fp.p10_quantity <= fp.p50_quantity <= fp.p90_quantity):
                    print(f"❌ ERROR: Invalid quantile ordering on {fp.forecast_date}")
                    has_errors = True
                    all_passed = False

            if not has_errors:
                print(f"\n✅ {item.name}: PASSED")
            else:
                print(f"\n❌ {item.name}: FAILED (quantile ordering errors)")

        except Exception as e:
            print(f"❌ FAILED: {e}")
            import traceback
            traceback.print_exc()
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("\n✅ ALL TESTS PASSED! All menu items generate valid forecasts.")
    else:
        print("\n❌ SOME TESTS FAILED! Check errors above.")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
