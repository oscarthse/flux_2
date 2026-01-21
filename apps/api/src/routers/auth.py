"""
Authentication router with register, login, logout, and refresh endpoints.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    blacklist_token,
    is_token_blacklisted,
)
from src.core.deps import get_current_user
from src.db.session import get_db
from src.models.user import User
from src.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    TokenRefresh,
    UserResponse,
)
from src.models.restaurant import Restaurant
from pydantic import BaseModel


class RestaurantCreate(BaseModel):
    name: str
    timezone: str = "UTC"


class RestaurantResponse(BaseModel):
    id: str
    name: str
    timezone: str

    class Config:
        from_attributes = True

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(user_data: UserRegister, db: Session = Depends(get_db)) -> Token:
    """
    Register a new user account.
    Returns access and refresh tokens on success.
    """
    # Check if email already exists
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create new user
    new_user = User(
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Generate tokens
    access_token = create_access_token(subject=str(new_user.id))
    refresh_token = create_refresh_token(subject=str(new_user.id))

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=Token)
def login(user_data: UserLogin, db: Session = Depends(get_db)) -> Token:
    """
    Authenticate user and return tokens.
    """
    # Find user by email
    user = db.query(User).filter(User.email == user_data.email).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Verify password
    if not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Generate tokens
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=Token)
def refresh(token_data: TokenRefresh, db: Session = Depends(get_db)) -> Token:
    """
    Exchange a refresh token for a new access and refresh token.

    Implements token rotation: old refresh token is blacklisted and a new one is issued.
    This prevents token reuse attacks.
    """
    old_token = token_data.refresh_token
    payload = decode_token(old_token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    # Verify token type
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    # Check if token has been blacklisted (already used)
    if is_token_blacklisted(old_token, db):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has already been used. Please log in again.",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Verify user still exists
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Blacklist the old refresh token (single-use tokens)
    exp_timestamp = payload.get("exp")
    if exp_timestamp:
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
        blacklist_token(old_token, expires_at, db)

    # Generate new tokens
    access_token = create_access_token(subject=str(user.id))
    refresh_token = create_refresh_token(subject=str(user.id))

    return Token(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout", status_code=status.HTTP_200_OK)
def logout(current_user: User = Depends(get_current_user)) -> dict:
    """
    Logout user (stateless - just acknowledges the logout).
    Client should discard tokens.
    """
    return {"message": "Successfully logged out"}


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)) -> User:
    """
    Get the current authenticated user's profile.
    """
    return current_user


@router.post("/restaurant", response_model=RestaurantResponse, status_code=status.HTTP_201_CREATED)
def create_restaurant(
    restaurant_data: RestaurantCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Create a restaurant for the current user.
    Each user can only have one restaurant.
    """
    # Check if user already has a restaurant
    existing = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a restaurant",
        )

    # Create new restaurant
    new_restaurant = Restaurant(
        name=restaurant_data.name,
        timezone=restaurant_data.timezone,
        owner_id=current_user.id,
    )
    db.add(new_restaurant)
    db.commit()
    db.refresh(new_restaurant)

    return RestaurantResponse(
        id=str(new_restaurant.id),
        name=new_restaurant.name,
        timezone=new_restaurant.timezone,
    )


@router.get("/restaurant", response_model=RestaurantResponse)
def get_my_restaurant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Get the current user's restaurant.
    """
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == current_user.id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No restaurant found. Create one first.",
        )

    return RestaurantResponse(
        id=str(restaurant.id),
        name=restaurant.name,
        timezone=restaurant.timezone,
    )
