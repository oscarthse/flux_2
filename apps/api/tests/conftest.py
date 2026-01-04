"""
Test configuration and fixtures.
"""
import os
import pytest
from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from fastapi.testclient import TestClient

# Set test database URL before importing app
os.environ["DATABASE_URL"] = "postgresql://flux:fluxpassword@localhost:5432/flux_dev"

from src.main import app
from src.db.base import Base
from src.db.session import get_db
from src.models.user import User
from src.models.restaurant import Restaurant
from src.core.security import hash_password


# Test database setup - use same database but clean up after each test
TEST_DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(TEST_DATABASE_URL)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db() -> Generator[Session, None, None]:
    """Create a database session for the test."""
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def client(db: Session) -> Generator[TestClient, None, None]:
    """Create test client with database session override."""
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture
def test_user(db: Session) -> User:
    """Create a test user, cleaning up after."""
    # Clean up any existing test user first
    db.execute(text("DELETE FROM users WHERE email = 'testuser@example.com'"))
    db.commit()

    user = User(
        email="testuser@example.com",
        hashed_password=hash_password("testpassword123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    yield user

    # Cleanup
    db.execute(text("DELETE FROM users WHERE email = 'testuser@example.com'"))
    db.commit()


@pytest.fixture
def test_user_with_restaurant(db: Session) -> tuple[User, Restaurant]:
    """Create a test user with a restaurant, cleaning up after."""
    # Clean up first - must delete child records before parent to respect FK constraints
    # Get restaurant IDs for cleanup
    db.execute(text("""
        DELETE FROM demand_forecasts WHERE restaurant_id IN (
            SELECT id FROM restaurants WHERE name = 'Test Restaurant'
        )
    """))
    db.execute(text("""
        DELETE FROM transactions WHERE restaurant_id IN (
            SELECT id FROM restaurants WHERE name = 'Test Restaurant'
        )
    """))
    db.execute(text("""
        DELETE FROM inventory WHERE restaurant_id IN (
            SELECT id FROM restaurants WHERE name = 'Test Restaurant'
        )
    """))
    db.execute(text("""
        DELETE FROM data_uploads WHERE restaurant_id IN (
            SELECT id FROM restaurants WHERE name = 'Test Restaurant'
        )
    """))
    db.execute(text("DELETE FROM restaurants WHERE name = 'Test Restaurant'"))
    db.execute(text("DELETE FROM users WHERE email = 'restaurant_owner@example.com'"))
    db.commit()

    user = User(
        email="restaurant_owner@example.com",
        hashed_password=hash_password("testpassword123"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    restaurant = Restaurant(
        name="Test Restaurant",
        owner_id=user.id,
    )
    db.add(restaurant)
    db.commit()
    db.refresh(restaurant)

    yield user, restaurant

    # Cleanup - delete child records first to avoid foreign key violations
    db.execute(text("DELETE FROM demand_forecasts WHERE restaurant_id = :rid"), {"rid": restaurant.id})
    db.execute(text("DELETE FROM transactions WHERE restaurant_id = :rid"), {"rid": restaurant.id})
    db.execute(text("DELETE FROM inventory WHERE restaurant_id = :rid"), {"rid": restaurant.id})
    db.execute(text("DELETE FROM data_uploads WHERE restaurant_id = :rid"), {"rid": restaurant.id})
    db.execute(text("DELETE FROM restaurants WHERE id = :rid"), {"rid": restaurant.id})
    db.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user.id})
    db.commit()


@pytest.fixture
def auth_headers(client: TestClient, test_user: User) -> dict:
    """Get auth headers for test user."""
    response = client.post(
        "/api/auth/login",
        json={"email": "testuser@example.com", "password": "testpassword123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def auth_headers_with_restaurant(client: TestClient, test_user_with_restaurant: tuple[User, Restaurant]) -> dict:
    """Get auth headers for user with restaurant."""
    user, _ = test_user_with_restaurant
    response = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "testpassword123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
