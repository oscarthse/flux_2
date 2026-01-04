"""
Auth-related Pydantic schemas for request/response validation.
"""
from pydantic import BaseModel, EmailStr
from uuid import UUID


class UserRegister(BaseModel):
    """Schema for user registration request."""
    email: EmailStr
    password: str


class UserLogin(BaseModel):
    """Schema for user login request."""
    email: EmailStr
    password: str


class Token(BaseModel):
    """Schema for token response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefresh(BaseModel):
    """Schema for token refresh request."""
    refresh_token: str


class UserResponse(BaseModel):
    """Schema for user response (without password)."""
    id: UUID
    email: str

    class Config:
        from_attributes = True
