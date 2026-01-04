"""
Promotions router for managing discount campaigns and elasticity learning.

Provides endpoints for creating, listing, and updating promotions.
Includes exploration candidate detection for unbiased elasticity learning.
"""
import random
from datetime import datetime, date
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from src.core.deps import get_current_user
from src.db.session import get_db
from src.models.promotion import Promotion, PriceElasticity
from src.models.menu import MenuItem
from src.models.restaurant import Restaurant
from src.models.user import User

router = APIRouter(prefix="/promotions", tags=["promotions"])


# Exploration rate for unbiased elasticity learning
EXPLORATION_RATE = 0.05  # 5% random promotions


# ============ Schemas ============

class PromotionCreate(BaseModel):
    menu_item_id: UUID
    name: Optional[str] = None
    discount_type: Literal["percentage", "fixed_amount"] = "percentage"
    discount_value: Decimal
    start_date: datetime
    end_date: datetime
    trigger_reason: Optional[Literal["expiring_stock", "low_demand", "manual"]] = None


class PromotionUpdate(BaseModel):
    name: Optional[str] = None
    status: Optional[Literal["draft", "active", "completed", "cancelled"]] = None
    actual_lift: Optional[Decimal] = None


class PromotionResponse(BaseModel):
    id: UUID
    restaurant_id: UUID
    menu_item_id: Optional[UUID]
    name: Optional[str]
    discount_type: str
    discount_value: Decimal
    start_date: datetime
    end_date: datetime
    status: str
    trigger_reason: Optional[str]
    is_exploration: bool
    expected_lift: Optional[Decimal]
    actual_lift: Optional[Decimal]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PromotionListResponse(BaseModel):
    promotions: List[PromotionResponse]
    total: int
    exploration_count: int


class ExploreCandidateResponse(BaseModel):
    """Menu item that needs elasticity exploration."""
    menu_item_id: UUID
    name: str
    current_price: Decimal
    sample_size: int
    confidence: Optional[Decimal]
    suggested_discount: Decimal  # Recommended discount %


class ExploreCandidatesListResponse(BaseModel):
    candidates: List[ExploreCandidateResponse]
    total: int


class ElasticityEstimateResponse(BaseModel):
    """Price elasticity estimate for a menu item."""
    menu_item_id: UUID
    menu_item_name: str
    elasticity: float
    std_error: float
    ci_lower: float
    ci_upper: float
    sample_size: int
    confidence: float
    method: str
    r_squared: Optional[float] = None
    f_stat: Optional[float] = None
    is_weak_instrument: Optional[bool] = None


class PromotionInferenceResponse(BaseModel):
    """Result of statistical promotion inference."""
    promotions_inferred: int
    message: str


# ============ Helper Functions ============

def get_user_restaurant(db: Session, user: User) -> Restaurant:
    """Get restaurant for current user, raise 404 if not found."""
    restaurant = db.query(Restaurant).filter(Restaurant.owner_id == user.id).first()
    if not restaurant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Restaurant not found"
        )
    return restaurant


# ============ Endpoints ============

@router.get("", response_model=PromotionListResponse)
def list_promotions(
    status_filter: Optional[str] = Query(None, description="Filter by status"),
    is_exploration: Optional[bool] = Query(None, description="Filter by exploration flag"),
    menu_item_id: Optional[UUID] = Query(None, description="Filter by menu item"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    List all promotions for the current user's restaurant.

    Supports filtering by status, exploration flag, and menu item.
    """
    restaurant = get_user_restaurant(db, current_user)

    query = select(Promotion).where(Promotion.restaurant_id == restaurant.id)

    if status_filter:
        query = query.where(Promotion.status == status_filter)
    if is_exploration is not None:
        query = query.where(Promotion.is_exploration == is_exploration)
    if menu_item_id:
        query = query.where(Promotion.menu_item_id == menu_item_id)

    query = query.order_by(Promotion.created_at.desc())
    promotions = db.execute(query).scalars().all()

    exploration_count = sum(1 for p in promotions if p.is_exploration)

    return PromotionListResponse(
        promotions=[PromotionResponse.model_validate(p) for p in promotions],
        total=len(promotions),
        exploration_count=exploration_count
    )


@router.post("", response_model=PromotionResponse, status_code=status.HTTP_201_CREATED)
def create_promotion(
    promo: PromotionCreate,
    force_exploration: Optional[bool] = Query(None, description="Force exploration flag"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Create a new promotion campaign.

    Automatically assigns is_exploration=True with 5% probability for
    unbiased elasticity learning. Use force_exploration=true to override.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Verify menu item belongs to restaurant
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == promo.menu_item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()
    if not menu_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Determine exploration flag
    if force_exploration is not None:
        is_exploration = force_exploration
    else:
        # 5% random exploration for unbiased elasticity learning
        is_exploration = random.random() < EXPLORATION_RATE

    db_promo = Promotion(
        restaurant_id=restaurant.id,
        menu_item_id=promo.menu_item_id,
        name=promo.name or f"{menu_item.name} Promo",
        discount_type=promo.discount_type,
        discount_value=promo.discount_value,
        start_date=promo.start_date,
        end_date=promo.end_date,
        status="draft",
        trigger_reason=promo.trigger_reason or "manual",
        is_exploration=is_exploration,
    )

    db.add(db_promo)
    db.commit()
    db.refresh(db_promo)

    return PromotionResponse.model_validate(db_promo)


@router.get("/explore-candidates", response_model=ExploreCandidatesListResponse)
def get_explore_candidates(
    min_sales_days: int = Query(14, description="Minimum days of sales history"),
    max_sample_size: int = Query(3, description="Max existing elasticity samples"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get menu items that need elasticity exploration.

    Returns items with insufficient price elasticity data that would
    benefit from a random exploration discount.

    Per ML review: "With 5 exploration observations per item, can detect
    elasticity with SE ≈ 0.5"
    """
    restaurant = get_user_restaurant(db, current_user)

    # Get menu items with their elasticity data (if any)
    # Use left join and filter in Python for better DB portability
    query = (
        select(
            MenuItem.id,
            MenuItem.name,
            MenuItem.price,
            PriceElasticity.sample_size,
            PriceElasticity.confidence
        )
        .outerjoin(
            PriceElasticity,
            and_(
                PriceElasticity.menu_item_id == MenuItem.id,
                PriceElasticity.restaurant_id == restaurant.id
            )
        )
        .where(
            MenuItem.restaurant_id == restaurant.id,
            MenuItem.is_active == True
        )
    )

    results = db.execute(query).all()

    # Filter in Python for portability (HAVING without aggregation varies by DB)
    candidates = []
    for row in results:
        sample_size = row.sample_size if row.sample_size is not None else 0
        if sample_size >= max_sample_size:
            continue  # Skip items with sufficient elasticity data

        # Suggest discount based on category defaults (5-8%)
        suggested_discount = Decimal("0.05") + Decimal(str(random.random() * 0.03))

        candidates.append(ExploreCandidateResponse(
            menu_item_id=row.id,
            name=row.name,
            current_price=row.price,
            sample_size=sample_size,
            confidence=row.confidence,
            suggested_discount=round(suggested_discount, 2)
        ))

    return ExploreCandidatesListResponse(
        candidates=candidates,
        total=len(candidates)
    )


@router.get("/{promotion_id}", response_model=PromotionResponse)
def get_promotion(
    promotion_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a specific promotion by ID."""
    restaurant = get_user_restaurant(db, current_user)

    promo = db.query(Promotion).filter(
        Promotion.id == promotion_id,
        Promotion.restaurant_id == restaurant.id
    ).first()

    if not promo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )

    return PromotionResponse.model_validate(promo)


@router.patch("/{promotion_id}", response_model=PromotionResponse)
def update_promotion(
    promotion_id: UUID,
    update_data: PromotionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Update a promotion.

    Typically used to:
    - Change status (draft → active → completed)
    - Record actual_lift after promotion completes
    """
    restaurant = get_user_restaurant(db, current_user)

    promo = db.query(Promotion).filter(
        Promotion.id == promotion_id,
        Promotion.restaurant_id == restaurant.id
    ).first()

    if not promo:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Promotion not found"
        )

    update_dict = update_data.model_dump(exclude_unset=True)

    for field, value in update_dict.items():
        setattr(promo, field, value)

    db.commit()
    db.refresh(promo)

    return PromotionResponse.model_validate(promo)


@router.post("/elasticity/estimate/{menu_item_id}", response_model=ElasticityEstimateResponse)
def estimate_price_elasticity(
    menu_item_id: UUID,
    lookback_days: int = Query(180, description="Days of history to use for estimation"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Estimate price elasticity for a menu item using robust hierarchical methods.

    Uses a 6-level fallback hierarchy:
    1. Full 2SLS (n≥60, 3+ prices) → confidence 0.7-0.9
    2. Bayesian + prior (n≥20) → confidence 0.5-0.7
    3. Category pooled (3+ items) → confidence 0.4-0.6
    4. Price tier (5+ similar items) → confidence 0.3-0.5
    5. Restaurant average → confidence 0.2-0.4
    6. Industry default (always works) → confidence 0.1-0.3

    Always returns an estimate, even with 0 days of data.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Verify menu item belongs to restaurant
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == menu_item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()
    if not menu_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Run robust elasticity estimation
    from src.services.robust_elasticity import RobustElasticityEstimator
    estimator = RobustElasticityEstimator(db)

    try:
        estimate = estimator.estimate(
            restaurant_id=restaurant.id,
            menu_item_id=menu_item_id
        )

        return ElasticityEstimateResponse(
            menu_item_id=menu_item_id,
            menu_item_name=menu_item.name,
            elasticity=estimate.elasticity,
            std_error=estimate.std_error,
            ci_lower=estimate.ci_lower,
            ci_upper=estimate.ci_upper,
            sample_size=estimate.sample_size,
            confidence=estimate.confidence,
            method=estimate.method,
            r_squared=estimate.r_squared if hasattr(estimate, 'r_squared') else None,
            f_stat=estimate.f_stat if hasattr(estimate, 'f_stat') else None,
            is_weak_instrument=estimate.is_weak_instrument if hasattr(estimate, 'is_weak_instrument') else None
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Elasticity estimation failed: {str(e)}"
        )


@router.post("/infer-promotions", response_model=PromotionInferenceResponse)
def infer_historical_promotions(
    lookback_days: int = Query(90, description="Days of history to analyze"),
    confidence_threshold: float = Query(0.6, description="Minimum confidence to save (0-1)"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Run statistical promotion inference on historical price data.

    Uses Bayesian change-point detection to identify periods where prices
    deviated significantly from baseline (2-sigma threshold).

    Detects promotions that weren't explicitly marked but are evident
    from price patterns (e.g., happy hour pricing, seasonal discounts).
    """
    restaurant = get_user_restaurant(db, current_user)

    from src.services.promotion_detection import PromotionDetectionService
    promo_service = PromotionDetectionService(db)

    try:
        promotions_inferred = promo_service.detect_and_save_promotions(
            restaurant_id=restaurant.id,
            confidence_threshold=confidence_threshold
        )

        return PromotionInferenceResponse(
            promotions_inferred=promotions_inferred,
            message=f"Successfully inferred {promotions_inferred} historical promotions"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Promotion inference failed: {str(e)}"
        )


@router.get("/elasticity/{menu_item_id}", response_model=ElasticityEstimateResponse)
def get_saved_elasticity(
    menu_item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get saved price elasticity estimate for a menu item.

    Returns the most recently calculated elasticity from the database.
    Use POST /elasticity/estimate/{menu_item_id} to recalculate.
    """
    restaurant = get_user_restaurant(db, current_user)

    # Verify menu item belongs to restaurant
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == menu_item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()
    if not menu_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Menu item not found"
        )

    # Get saved elasticity
    elasticity_record = db.query(PriceElasticity).filter(
        PriceElasticity.restaurant_id == restaurant.id,
        PriceElasticity.menu_item_id == menu_item_id
    ).first()

    if not elasticity_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No elasticity estimate found. Use POST /elasticity/estimate/{menu_item_id} to calculate."
        )

    return ElasticityEstimateResponse(
        menu_item_id=menu_item_id,
        menu_item_name=menu_item.name,
        elasticity=float(elasticity_record.elasticity),
        std_error=0.0,  # Not stored in DB
        ci_lower=0.0,  # Not stored in DB
        ci_upper=0.0,  # Not stored in DB
        sample_size=elasticity_record.sample_size,
        confidence=float(elasticity_record.confidence),
        method="saved"
    )
