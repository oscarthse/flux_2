"""
Seed script for Flux development database.

Creates test users, restaurants, and sample data uploads for local development.

Usage:
    cd apps/api
    uv run python scripts/seed.py
"""
import os
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import bcrypt

from db.base import Base
from models.user import User
from models.restaurant import Restaurant
from models.data_upload import DataUpload


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


# Database URL from environment or default
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://flux:fluxpassword@localhost:5432/flux_dev"
)


def seed_database():
    """Seed the database with test data."""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    try:
        # Check if data already exists
        existing_users = session.query(User).count()
        if existing_users > 0:
            print("Database already seeded. Skipping...")
            return

        print("Seeding database...")

        # Create test users
        user1 = User(
            email="chef@laboqueria.es",
            hashed_password=hash_password("password123"),
        )
        user2 = User(
            email="owner@eixample.cat",
            hashed_password=hash_password("password123"),
        )
        session.add_all([user1, user2])
        session.flush()  # Get IDs

        print(f"Created users: {user1.email}, {user2.email}")

        # Create restaurants
        restaurant1 = Restaurant(
            name="La Boqueria Bites",
            owner_id=user1.id,
        )
        restaurant2 = Restaurant(
            name="Eixample Elegance",
            owner_id=user2.id,
        )
        session.add_all([restaurant1, restaurant2])
        session.flush()

        print(f"Created restaurants: {restaurant1.name}, {restaurant2.name}")

        # Create sample data uploads
        upload1 = DataUpload(
            restaurant_id=restaurant1.id,
            status="COMPLETED",
            errors=None,
        )
        upload2 = DataUpload(
            restaurant_id=restaurant2.id,
            status="PENDING",
            errors=None,
        )
        session.add_all([upload1, upload2])

        print("Created sample data uploads")

        session.commit()
        print("\n✅ Database seeded successfully!")
        print("\nTest credentials:")
        print("  Email: chef@laboqueria.es | Password: password123")
        print("  Email: owner@eixample.cat | Password: password123")

    except Exception as e:
        session.rollback()
        print(f"❌ Error seeding database: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
