"""
Application configuration using Pydantic Settings.
"""
import os
import secrets
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import field_validator


# List of known insecure default secrets that should never be used
INSECURE_DEFAULTS = {
    "your-super-secret-key-change-in-production",
    "secret",
    "changeme",
    "test",
    "dev",
    "development",
    "password",
}


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Flux API"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "postgresql://flux:fluxpassword@localhost:5432/flux_dev"

    # JWT Configuration
    JWT_SECRET_KEY: str = "your-super-secret-key-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Optional API Keys (for LLM categorization in future stories)
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def validate_jwt_secret(cls, v: str) -> str:
        """
        Validate JWT secret key is secure.

        Requirements:
        - At least 32 characters
        - Not a known insecure default
        - In production mode, must be set via environment variable
        """
        # Check for known insecure defaults
        if v.lower() in INSECURE_DEFAULTS:
            raise ValueError(
                f"JWT_SECRET_KEY is set to an insecure default value. "
                f"Please set a strong secret key via environment variable. "
                f"Generate one with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        # Check minimum length
        if len(v) < 32:
            raise ValueError(
                f"JWT_SECRET_KEY must be at least 32 characters long (got {len(v)}). "
                f"Generate a secure key with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
            )

        return v

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
