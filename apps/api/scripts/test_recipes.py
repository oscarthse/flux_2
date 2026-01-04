"""Test recipe endpoints and check recipe data"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.db.session import SessionLocal
from src.models.restaurant import Restaurant
from src.models.recipe import StandardRecipe
from src.services.recipe_matching import RecipeMatchingService

db = SessionLocal()

try:
    # Get restaurant
    restaurant = db.query(Restaurant).filter(
        Restaurant.name == "Synthetic Test Cafe"
    ).first()

    if not restaurant:
        print("❌ Restaurant not found!")
        sys.exit(1)

    print(f"✅ Found restaurant: {restaurant.name} (ID: {restaurant.id})\n")

    # Check for standard recipes
    recipe_count = db.query(StandardRecipe).count()
    print(f"📖 Standard recipes in database: {recipe_count}")

    if recipe_count == 0:
        print("\n⚠️  WARNING: No standard recipes found!")
        print("   The recipes page needs standard recipes to match against menu items.")
        print("   You'll need to seed the database with standard recipes.\n")
    else:
        # Show some examples
        recipes = db.query(StandardRecipe).limit(5).all()
        print("\nSample recipes:")
        for r in recipes:
            print(f"  - {r.name} ({r.cuisine_type}, {r.category})")

    # Test recipe matching service
    print(f"\n🔍 Testing recipe matching for restaurant...")
    service = RecipeMatchingService(db)

    try:
        results = service.match_all_unconfirmed(restaurant.id)
        print(f"✅ Found {len(results)} unconfirmed menu items")

        for result in results:
            print(f"\n  Menu item: {result.menu_item_name}")
            print(f"  Matches: {len(result.matches)}")
            print(f"  Auto-confirmed: {result.auto_confirmed}")
            print(f"  Needs review: {result.needs_review}")

            if result.matches:
                top_match = result.matches[0]
                print(f"  Top match: {top_match.recipe_name} (confidence: {top_match.confidence_score:.2f})")
    except Exception as e:
        print(f"❌ Error during matching: {e}")
        import traceback
        traceback.print_exc()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
finally:
    db.close()
