"""
Menu item Pydantic schemas for API request/response models.
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MenuItemResponse(BaseModel):
    """Response model for a single menu item."""
    id: UUID
    name: str
    price: Decimal
    category_path: Optional[str] = None
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None
    auto_created: bool = False
    confidence_score: Optional[Decimal] = None
    is_active: bool = True
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MenuItemListResponse(BaseModel):
    """Response model for list of menu items."""
    items: List[MenuItemResponse]
    total: int
    auto_created_count: int
    needs_review_count: int


class MenuItemUpdate(BaseModel):
    """Request model for updating a menu item."""
    name: Optional[str] = None
    category_path: Optional[str] = None
    price: Optional[Decimal] = None
    is_active: Optional[bool] = None
    # Mark as reviewed (sets confidence to 1.0)
    confirmed: Optional[bool] = None


class MenuItemMergeRequest(BaseModel):
    """Request model for merging duplicate menu items."""
    source_id: UUID  # Item to merge FROM (will be deleted)
    target_id: UUID  # Item to merge INTO (will be kept)


class MenuItemMergeResponse(BaseModel):
    """Response model for merge operation."""
    target_item: MenuItemResponse
    transactions_updated: int
    source_deleted: bool
