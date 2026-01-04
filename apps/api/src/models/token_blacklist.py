"""
Token blacklist model for handling token revocation.

When refresh tokens are used, the old token is blacklisted to prevent reuse.
This implements single-use refresh tokens as a security best practice.
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Index
from sqlalchemy.sql import func

from src.db.base import Base


class TokenBlacklist(Base):
    """
    Store revoked/blacklisted JWT tokens.

    Tokens are added here when:
    - A refresh token is used (old token blacklisted, new one issued)
    - User explicitly logs out
    - Admin revokes user's tokens
    """
    __tablename__ = "token_blacklist"

    # JWT token string (we hash it for security/space efficiency)
    token_hash = Column(String(64), primary_key=True)

    # When the token was blacklisted
    blacklisted_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # When the token expires (for cleanup - we can delete expired blacklisted tokens)
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Index for cleanup queries
    __table_args__ = (
        Index('idx_token_blacklist_expires', 'expires_at'),
    )
