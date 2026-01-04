"""
Unit tests for security utilities.
"""
import pytest
from datetime import timedelta

from src.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_hash_password(self):
        """Test that password hashing produces a hash."""
        password = "mysecretpassword"
        hashed = hash_password(password)

        assert hashed != password
        assert len(hashed) > 20  # bcrypt hashes are long

    def test_hash_password_different_each_time(self):
        """Test that hashing same password produces different hashes."""
        password = "mysecretpassword"
        hash1 = hash_password(password)
        hash2 = hash_password(password)

        assert hash1 != hash2  # Different salts

    def test_verify_password_correct(self):
        """Test verifying correct password."""
        password = "mysecretpassword"
        hashed = hash_password(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test verifying incorrect password."""
        password = "mysecretpassword"
        hashed = hash_password(password)

        assert verify_password("wrongpassword", hashed) is False


class TestJWTTokens:
    """Tests for JWT token functions."""

    def test_create_access_token(self):
        """Test creating an access token."""
        token = create_access_token(subject="user-123")

        assert token is not None
        assert len(token) > 50

    def test_create_refresh_token(self):
        """Test creating a refresh token."""
        token = create_refresh_token(subject="user-123")

        assert token is not None
        assert len(token) > 50

    def test_decode_access_token(self):
        """Test decoding an access token."""
        subject = "user-123"
        token = create_access_token(subject=subject)

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == subject
        assert payload["type"] == "access"

    def test_decode_refresh_token(self):
        """Test decoding a refresh token."""
        subject = "user-456"
        token = create_refresh_token(subject=subject)

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == subject
        assert payload["type"] == "refresh"

    def test_decode_invalid_token(self):
        """Test decoding an invalid token returns None."""
        payload = decode_token("invalid.token.here")

        assert payload is None

    def test_access_token_with_custom_expiry(self):
        """Test access token with custom expiry."""
        token = create_access_token(
            subject="user-789",
            expires_delta=timedelta(minutes=5)
        )

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user-789"
