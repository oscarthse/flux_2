"""Quick test to generate forecasts for synthetic data"""
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

    print(f"✅ Found restaurant: {restaurant.name} (ID: {restaurant.id})")

    # Get menu items
    items = db.query(MenuItem).filter(
        MenuItem.restaurant_id == restaurant.id
    ).all()

    print(f"✅ Found {len(items)} menu items: {[item.name for item in items]}")

    # Test forecast generation for first item
    forecast_service = ForecastService(db)
    test_item = items[0]

    print(f"\n🔮 Generating forecast for '{test_item.name}'...")

    forecast_points = forecast_service.generate_forecasts(
        restaurant_id=restaurant.id,
        menu_item_name=test_item.name,
        days_ahead=7
    )

    if forecast_points and len(forecast_points) > 0:
        print(f"✅ Successfully generated {len(forecast_points)} forecast points!")
        print(f"\nFirst forecast point:")
        fp = forecast_points[0]
        print(f"  Date: {fp.forecast_date}")
        print(f"  p10={fp.p10_quantity:.1f}, p50={fp.p50_quantity:.1f}, p90={fp.p90_quantity:.1f}")
        print("\n✅ Forecast generation is working!")
    else:
        print("❌ No forecast points generated!")
        sys.exit(1)

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
