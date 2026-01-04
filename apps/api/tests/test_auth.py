"""
Tests for authentication endpoints.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.models.user import User


class TestRegister:
    """Tests for POST /api/auth/register."""

    def test_register_success(self, client: TestClient, db: Session):
        """Test successful user registration."""
        # Clean up any existing user first
        from sqlalchemy import text
        db.execute(text("DELETE FROM users WHERE email = 'newuser@example.com'"))
        db.commit()

        response = client.post(
            "/api/auth/register",
            json={"email": "newuser@example.com", "password": "securepassword123"}
        )

        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

        # Verify user was created in database
        db.expire_all()  # Force refresh from DB
        user = db.query(User).filter(User.email == "newuser@example.com").first()
        assert user is not None

        # Cleanup
        db.execute(text("DELETE FROM users WHERE email = 'newuser@example.com'"))
        db.commit()

    def test_register_duplicate_email(self, client: TestClient, test_user: User):
        """Test registration with existing email fails."""
        response = client.post(
            "/api/auth/register",
            json={"email": test_user.email, "password": "somepassword123"}
        )

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client: TestClient):
        """Test registration with invalid email fails."""
        response = client.post(
            "/api/auth/register",
            json={"email": "not-an-email", "password": "securepassword123"}
        )

        assert response.status_code == 422


class TestLogin:
    """Tests for POST /api/auth/login."""

    def test_login_success(self, client: TestClient, test_user: User):
        """Test successful login."""
        response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "testpassword123"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_login_wrong_password(self, client: TestClient, test_user: User):
        """Test login with wrong password fails."""
        response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "wrongpassword"}
        )

        assert response.status_code == 401
        assert "invalid" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client: TestClient):
        """Test login with nonexistent user fails."""
        response = client.post(
            "/api/auth/login",
            json={"email": "nobody@example.com", "password": "somepassword"}
        )

        assert response.status_code == 401


class TestRefresh:
    """Tests for POST /api/auth/refresh."""

    def test_refresh_success(self, client: TestClient, test_user: User):
        """Test successful token refresh."""
        # First login to get tokens
        login_response = client.post(
            "/api/auth/login",
            json={"email": "testuser@example.com", "password": "testpassword123"}
        )
        refresh_token = login_response.json()["refresh_token"]

        # Refresh the token
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token}
        )

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data

    def test_refresh_invalid_token(self, client: TestClient):
        """Test refresh with invalid token fails."""
        response = client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid.token.here"}
        )

        assert response.status_code == 401


class TestMe:
    """Tests for GET /api/auth/me."""

    def test_me_authenticated(self, client: TestClient, auth_headers: dict, test_user: User):
        """Test getting current user info."""
        response = client.get("/api/auth/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user.email
        assert "id" in data

    def test_me_unauthenticated(self, client: TestClient):
        """Test accessing /me without auth fails."""
        response = client.get("/api/auth/me")

        assert response.status_code == 401

    def test_me_invalid_token(self, client: TestClient):
        """Test accessing /me with invalid token fails."""
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer invalid.token.here"}
        )

        assert response.status_code == 401


class TestLogout:
    """Tests for POST /api/auth/logout."""

    def test_logout_success(self, client: TestClient, auth_headers: dict):
        """Test successful logout."""
        response = client.post("/api/auth/logout", headers=auth_headers)

        assert response.status_code == 200
        assert "logged out" in response.json()["message"].lower()
