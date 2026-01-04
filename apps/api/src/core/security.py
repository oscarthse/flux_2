"""
Security utilities for password hashing and JWT token handling.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import hashlib

import bcrypt
from jose import jwt, JWTError
from sqlalchemy.orm import Session

from src.core.config import get_settings

settings = get_settings()


def hash_token(token: str) -> str:
    """
    Hash a JWT token for storage in blacklist.

    We hash tokens before storing them so that if the database is compromised,
    the attacker can't use the blacklisted tokens.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    """Hash a password using bcrypt."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Create a JWT access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "access"
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Create a JWT refresh token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "type": "refresh"
    }
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token. Returns payload or None if invalid."""
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        return None


def is_token_blacklisted(token: str, db: Session) -> bool:
    """
    Check if a token has been blacklisted (revoked).

    Args:
        token: The JWT token string
        db: Database session

    Returns:
        True if token is blacklisted, False otherwise
    """
    from src.models.token_blacklist import TokenBlacklist

    token_hash_value = hash_token(token)
    blacklisted = db.query(TokenBlacklist).filter(
        TokenBlacklist.token_hash == token_hash_value
    ).first()

    return blacklisted is not None


def blacklist_token(token: str, expires_at: datetime, db: Session) -> None:
    """
    Add a token to the blacklist.

    Args:
        token: The JWT token string to blacklist
        expires_at: When the token expires (for cleanup)
        db: Database session
    """
    from src.models.token_blacklist import TokenBlacklist

    token_hash_value = hash_token(token)

    # Check if already blacklisted
    existing = db.query(TokenBlacklist).filter(
        TokenBlacklist.token_hash == token_hash_value
    ).first()

    if not existing:
        blacklist_entry = TokenBlacklist(
            token_hash=token_hash_value,
            expires_at=expires_at
        )
        db.add(blacklist_entry)
        db.commit()


def cleanup_expired_tokens(db: Session) -> int:
    """
    Remove expired tokens from the blacklist.

    This should be run periodically (e.g., daily cron job) to keep the table small.

    Args:
        db: Database session

    Returns:
        Number of tokens removed
    """
    from src.models.token_blacklist import TokenBlacklist

    now = datetime.now(timezone.utc)
    result = db.query(TokenBlacklist).filter(
        TokenBlacklist.expires_at < now
    ).delete()

    db.commit()
    return result
