"""
Menu items router for managing auto-created and manually added menu items.

Provides endpoints for listing, reviewing, updating, and merging menu items.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from src.core.deps import get_current_user
from src.db.session import get_db
from src.models.menu import MenuItem
from src.models.restaurant import Restaurant
from src.models.transaction import TransactionItem
from src.models.user import User
from src.schemas.menu import (
    MenuItemListResponse,
    MenuItemMergeRequest,
    MenuItemMergeResponse,
    MenuItemResponse,
    MenuItemUpdate,
)
from src.services.menu_categorization import MenuCategorizationService

router = APIRouter(prefix="/menu-items", tags=["menu-items"])


def get_user_restaurant(db: Session, user: User) -> Restaurant:
    """Get restaurant for current user, raise 404 if not found."""
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == user.id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    return restaurant


@router.get("", response_model=MenuItemListResponse)
def list_menu_items(
    active_only: bool = Query(True, description="Only return active items"),
    auto_created_only: bool = Query(False, description="Only return auto-created items"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all menu items for the current user's restaurant.

    Returns items with counts of auto-created and needs-review items.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Build query
    query = select(MenuItem).where(MenuItem.restaurant_id == restaurant.id)

    if active_only:
        query = query.filter(MenuItem.is_active == True)

    if auto_created_only:
        query = query.filter(MenuItem.auto_created == True)

    query = query.order_by(MenuItem.name.asc())

    items = db.execute(query).scalars().all()

    # Calculate counts
    auto_created_count = sum(1 for item in items if item.auto_created)
    needs_review_count = sum(
        1 for item in items
        if item.auto_created and (item.confidence_score is None or item.confidence_score < 0.7)
    )

    return MenuItemListResponse(
        items=[MenuItemResponse.model_validate(item) for item in items],
        total=len(items),
        auto_created_count=auto_created_count,
        needs_review_count=needs_review_count
    )


@router.get("/review", response_model=MenuItemListResponse)
def get_items_needing_review(
    confidence_threshold: float = Query(0.7, ge=0, le=1, description="Confidence threshold"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get auto-created menu items with low confidence scores that need manual review.

    Items with confidence below the threshold are returned for user verification.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Query low-confidence auto-created items
    query = (
        select(MenuItem)
        .where(
            MenuItem.restaurant_id == restaurant.id,
            MenuItem.auto_created == True,
            MenuItem.is_active == True,
        )
        .where(
            (MenuItem.confidence_score == None) |
            (MenuItem.confidence_score < confidence_threshold)
        )
        .order_by(MenuItem.confidence_score.asc().nullsfirst())
    )

    items = db.execute(query).scalars().all()

    return MenuItemListResponse(
        items=[MenuItemResponse.model_validate(item) for item in items],
        total=len(items),
        auto_created_count=len(items),
        needs_review_count=len(items)
    )


@router.patch("/{item_id}", response_model=MenuItemResponse)
def update_menu_item(
    item_id: UUID,
    update_data: MenuItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a menu item's properties.

    Can update name, category_path, price, is_active.
    Setting `confirmed=true` marks the item as reviewed (confidence=1.0).
    """
    restaurant = get_user_restaurant(db, current_user)

    # Find the item
    item = db.query(MenuItem).filter(
        MenuItem.id == item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()

    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)

    # Handle confirmation
    if update_dict.pop("confirmed", None):
        item.confidence_score = 1.0

    # Validate category path if provided
    if "category_path" in update_dict and update_dict["category_path"]:
        categorization_service = MenuCategorizationService(api_key=None)
        if not categorization_service.validate_category_path(update_dict["category_path"]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid category path format. Expected 'Level1 > Level2 > Level3'"
            )

    for field, value in update_dict.items():
        setattr(item, field, value)

    db.commit()
    db.refresh(item)

    return MenuItemResponse.model_validate(item)


@router.post("/merge", response_model=MenuItemMergeResponse)
def merge_menu_items(
    merge_request: MenuItemMergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Merge duplicate menu items.

    Updates all transaction items referencing the source item to reference
    the target item instead, then deletes the source item.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Find both items
    source_item = db.query(MenuItem).filter(
        MenuItem.id == merge_request.source_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()

    target_item = db.query(MenuItem).filter(
        MenuItem.id == merge_request.target_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()

    if not source_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Source menu item not found"
        )

    if not target_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target menu item not found"
        )

    if source_item.id == target_item.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Source and target items must be different"
        )

    # Update transaction items to reference target
    # Note: TransactionItem uses menu_item_name string, not FK
    # So we update items with matching name
    update_stmt = (
        update(TransactionItem)
        .where(TransactionItem.menu_item_name == source_item.name)
        .values(menu_item_name=target_item.name)
    )
    result = db.execute(update_stmt)
    transactions_updated = result.rowcount

    # Update target's first_seen if source is older
    if source_item.first_seen and target_item.first_seen:
        if source_item.first_seen < target_item.first_seen:
            target_item.first_seen = source_item.first_seen

    # Update target's last_seen if source is newer
    if source_item.last_seen and target_item.last_seen:
        if source_item.last_seen > target_item.last_seen:
            target_item.last_seen = source_item.last_seen

    # Delete source item
    db.delete(source_item)
    db.commit()
    db.refresh(target_item)

    return MenuItemMergeResponse(
        target_item=MenuItemResponse.model_validate(target_item),
        transactions_updated=transactions_updated,
        source_deleted=True
    )
