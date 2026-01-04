"""Quick test for data health endpoint"""
import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.db.session import SessionLocal
from src.models.restaurant import Restaurant
from src.services.data_health import DataHealthService

db = SessionLocal()

try:
    # Get restaurant
    restaurant = db.query(Restaurant).filter(
        Restaurant.name == "Synthetic Test Cafe"
    ).first()

    if not restaurant:
        print("❌ Restaurant not found!")
        sys.exit(1)

    print(f"✅ Found restaurant: {restaurant.name}")

    # Test data health calculation
    health_service = DataHealthService(db)

    print(f"\n📊 Calculating data health score...")

    health_score = health_service.calculate_score(restaurant.id)

    print(f"\n✅ Data Health Score: {health_score.overall_score:.1f}/100")
    print(f"\nComponent Scores:")
    print(f"  - Completeness: {health_score.completeness_score:.1f}/100")
    print(f"  - Consistency: {health_score.consistency_score:.1f}/100")
    print(f"  - Timeliness: {health_score.timeliness_score:.1f}/100")
    print(f"  - Accuracy: {health_score.accuracy_score:.1f}/100")

    print(f"\nRecommendations ({len(health_score.recommendations)}):")
    for i, rec in enumerate(health_score.recommendations[:3], 1):
        priority = rec.get('priority', 'medium') if isinstance(rec, dict) else rec.priority
        title = rec.get('title', '') if isinstance(rec, dict) else rec.title
        description = rec.get('description', '') if isinstance(rec, dict) else rec.description
        print(f"  {i}. [{priority.upper()}] {title}")
        print(f"     {description}")

    if len(health_score.recommendations) > 3:
        print(f"  ... and {len(health_score.recommendations) - 3} more")

    print("\n✅ Data health endpoint is working!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
