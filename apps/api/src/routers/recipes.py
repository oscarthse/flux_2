"""
Recipe Intelligence Router for Epic 3.

Provides API endpoints for:
- COGS calculation
- Menu profitability analysis
- Recipe explosion for procurement
"""
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.session import get_db
from src.models.user import User
from src.routers.auth import get_current_user
from src.services.cogs_calculator import COGSCalculator
from src.services.recipe_explosion import RecipeExplosionService
from src.services.menu_ocr import MenuOCRService


router = APIRouter(prefix="/recipes", tags=["recipes"])


# Helper to get restaurant
def get_user_restaurant(db: Session, current_user: User):
    from src.models.restaurant import Restaurant
    from sqlalchemy import select
    restaurant = db.execute(
        select(Restaurant).where(Restaurant.owner_id == current_user.id)
    ).scalar_one_or_none()
    if not restaurant:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return restaurant


# Helper to get waste factors setting
def get_waste_factors_enabled(db: Session, restaurant_id: UUID) -> bool:
    from sqlalchemy import text
    result = db.execute(
        text("""
            SELECT setting_value
            FROM restaurant_settings
            WHERE restaurant_id = :restaurant_id
            AND setting_key = 'waste_factors_enabled'
        """),
        {"restaurant_id": restaurant_id}
    ).fetchone()

    if result:
        return result[0].get('enabled', True)

    # Default: waste factors enabled
    return True


# ============ Profitability Schemas ============

class IngredientCostResponse(BaseModel):
    ingredient_id: UUID
    ingredient_name: str
    quantity: Decimal
    unit: str
    unit_cost: Decimal
    waste_factor: Decimal
    base_cost: Decimal
    waste_adjusted_cost: Decimal


class ProfitabilityResponse(BaseModel):
    menu_item_id: UUID
    menu_item_name: str
    menu_item_price: Decimal
    total_cogs: Decimal
    contribution_margin: Decimal
    margin_percentage: Decimal
    recipe_source: str
    ingredient_breakdown: List[IngredientCostResponse]
    bcg_quadrant: Optional[str] = None


class MenuProfitabilityResponse(BaseModel):
    items: List[ProfitabilityResponse]
    average_margin: Decimal
    low_margin_count: int  # Items with margin < 20%


# ============ Procurement Schemas ============

class ForecastItem(BaseModel):
    menu_item_id: UUID
    quantity: int


class IngredientRequirementResponse(BaseModel):
    ingredient_id: UUID
    ingredient_name: str
    total_quantity: Decimal
    unit: str
    estimated_cost: Decimal
    perishability_days: Optional[int]
    priority_score: Decimal


class ProcurementResponse(BaseModel):
    requirements: List[IngredientRequirementResponse]
    total_cost: Decimal
    items_processed: int
    items_skipped: int
    skipped_item_names: List[str]


# ============ Profitability Endpoints ============

@router.get("/menu-items/{menu_item_id}/profitability", response_model=ProfitabilityResponse)
def get_menu_item_profitability(
    menu_item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get COGS and profitability analysis for a single menu item.

    Returns:
    - Total COGS with ingredient breakdown
    - Contribution margin (price - COGS)
    - Margin percentage
    - Recipe source (custom, standard, override, none)
    """
    restaurant = get_user_restaurant(db, current_user)
    waste_factors_enabled = get_waste_factors_enabled(db, restaurant.id)
    calculator = COGSCalculator(db, waste_factors_enabled)

    result = calculator.calculate_cogs(menu_item_id)
    if not result:
        raise HTTPException(status_code=404, detail="Menu item not found")

    return ProfitabilityResponse(
        menu_item_id=result.menu_item_id,
        menu_item_name=result.menu_item_name,
        menu_item_price=result.menu_item_price,
        total_cogs=result.total_cogs,
        contribution_margin=result.contribution_margin,
        margin_percentage=result.margin_percentage,
        recipe_source=result.recipe_source,
        ingredient_breakdown=[
            IngredientCostResponse(
                ingredient_id=ic.ingredient_id,
                ingredient_name=ic.ingredient_name,
                quantity=ic.quantity,
                unit=ic.unit,
                unit_cost=ic.unit_cost,
                waste_factor=ic.waste_factor,
                base_cost=ic.base_cost,
                waste_adjusted_cost=ic.waste_adjusted_cost
            )
            for ic in result.ingredient_breakdown
        ]
    )


@router.get("/profitability", response_model=MenuProfitabilityResponse)
def get_menu_profitability(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get profitability analysis for all menu items.

    Returns items sorted by margin (lowest first to highlight problems).
    Includes BCG quadrant categorization.
    """
    restaurant = get_user_restaurant(db, current_user)
    waste_factors_enabled = get_waste_factors_enabled(db, restaurant.id)
    calculator = COGSCalculator(db, waste_factors_enabled)

    results = calculator.calculate_menu_profitability(restaurant.id)

    if not results:
        return MenuProfitabilityResponse(
            items=[],
            average_margin=Decimal(0),
            low_margin_count=0
        )

    # Calculate median margin for BCG categorization
    margins = [r.margin_percentage for r in results]
    median_margin = sorted(margins)[len(margins) // 2] if margins else Decimal(25)

    # Convert to response format with BCG quadrant
    items = []
    low_margin_count = 0

    for result in results:
        if result.margin_percentage < 20:
            low_margin_count += 1

        # TODO: Get actual volume data for proper BCG categorization
        # For now, assume all items are "medium" volume
        bcg = calculator.categorize_bcg(result, median_margin, is_high_volume=False)

        items.append(ProfitabilityResponse(
            menu_item_id=result.menu_item_id,
            menu_item_name=result.menu_item_name,
            menu_item_price=result.menu_item_price,
            total_cogs=result.total_cogs,
            contribution_margin=result.contribution_margin,
            margin_percentage=result.margin_percentage,
            recipe_source=result.recipe_source,
            bcg_quadrant=bcg,
            ingredient_breakdown=[
                IngredientCostResponse(
                    ingredient_id=ic.ingredient_id,
                    ingredient_name=ic.ingredient_name,
                    quantity=ic.quantity,
                    unit=ic.unit,
                    unit_cost=ic.unit_cost,
                    waste_factor=ic.waste_factor,
                    base_cost=ic.base_cost,
                    waste_adjusted_cost=ic.waste_adjusted_cost
                )
                for ic in result.ingredient_breakdown
            ]
        ))

    avg_margin = sum(margins) / len(margins) if margins else Decimal(0)

    return MenuProfitabilityResponse(
        items=items,
        average_margin=avg_margin,
        low_margin_count=low_margin_count
    )


# ============ Procurement Endpoints ============

@router.post("/explosion/calculate-requirements", response_model=ProcurementResponse)
def calculate_procurement_requirements(
    forecasts: List[ForecastItem],
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Convert demand forecasts into ingredient requirements for procurement.

    Aggregates ingredients across all forecasted menu items,
    applies waste factors, and prioritizes by perishability + cost.

    Body:
    - forecasts: List of {menu_item_id, quantity} objects

    Returns:
    - requirements: Aggregated ingredient list sorted by priority
    - total_cost: Estimated total procurement cost
    - items_processed/skipped: Counts of items with/without recipes
    """
    restaurant = get_user_restaurant(db, current_user)
    service = RecipeExplosionService(db)

    forecast_tuples = [(f.menu_item_id, f.quantity) for f in forecasts]
    result = service.explode_forecasts(forecast_tuples)

    return ProcurementResponse(
        requirements=[
            IngredientRequirementResponse(
                ingredient_id=r.ingredient_id,
                ingredient_name=r.ingredient_name,
                total_quantity=r.total_quantity,
                unit=r.unit,
                estimated_cost=r.estimated_cost,
                perishability_days=r.perishability_days,
                priority_score=r.priority_score
            )
            for r in result.requirements
        ],
        total_cost=result.total_cost,
        items_processed=result.items_processed,
        items_skipped=result.items_skipped,
        skipped_item_names=result.skipped_item_names
    )


# ============ Recipe Matching Schemas ============

class RecipeMatchResponse(BaseModel):
    recipe_id: UUID
    recipe_name: str
    cuisine_type: Optional[str]
    category: Optional[str]
    prep_time_minutes: Optional[int]
    confidence_score: Decimal
    match_method: str


class MatchResultResponse(BaseModel):
    menu_item_id: UUID
    menu_item_name: str
    matches: List[RecipeMatchResponse]
    auto_confirmed: bool
    needs_review: bool


class UnconfirmedItemsResponse(BaseModel):
    items: List[MatchResultResponse]
    total: int
    high_confidence_count: int
    needs_review_count: int


class ConfirmRecipeRequest(BaseModel):
    recipe_id: UUID


# ============ AI Recipe Estimation Schemas ============

class EstimatedIngredientResponse(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    base_cost: Decimal  # Cost before waste factor
    waste_factor: Decimal = Decimal("0")  # 0.00-0.60 (0-60% waste)
    estimated_cost: Decimal  # Calculated: base_cost * (1 + waste_factor)
    category: Optional[str] = None  # "produce", "meat", "dairy", "dry_goods", "prepared"
    perishability: Optional[str] = None  # "low", "medium", "high"
    notes: Optional[str] = None


class MenuItemWithEstimateResponse(BaseModel):
    menu_item_id: UUID
    menu_item_name: str
    menu_item_price: Optional[Decimal]
    ingredients: List[EstimatedIngredientResponse]
    total_estimated_cost: Decimal
    confidence: str
    estimation_notes: Optional[str] = None


class EstimatedRecipesResponse(BaseModel):
    items: List[MenuItemWithEstimateResponse]
    total: int


class SaveRecipeRequest(BaseModel):
    ingredients: List[EstimatedIngredientResponse]


# ============ Recipe Matching Endpoints ============

@router.get("/menu-items/unconfirmed", response_model=UnconfirmedItemsResponse)
def get_unconfirmed_menu_items(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get menu items that need recipe confirmation.

    Returns unconfirmed items with top 3 recipe suggestions each.
    """
    from src.services.recipe_matching import RecipeMatchingService

    restaurant = get_user_restaurant(db, current_user)
    service = RecipeMatchingService(db)

    results = service.match_all_unconfirmed(restaurant.id)

    high_confidence = sum(1 for r in results if r.auto_confirmed)
    needs_review = sum(1 for r in results if r.needs_review)

    items = [
        MatchResultResponse(
            menu_item_id=r.menu_item_id,
            menu_item_name=r.menu_item_name,
            matches=[
                RecipeMatchResponse(
                    recipe_id=m.recipe_id,
                    recipe_name=m.recipe_name,
                    cuisine_type=m.cuisine_type,
                    category=m.category,
                    prep_time_minutes=m.prep_time_minutes,
                    confidence_score=m.confidence_score,
                    match_method=m.match_method
                )
                for m in r.matches
            ],
            auto_confirmed=r.auto_confirmed,
            needs_review=r.needs_review
        )
        for r in results
    ]

    return UnconfirmedItemsResponse(
        items=items,
        total=len(items),
        high_confidence_count=high_confidence,
        needs_review_count=needs_review
    )


@router.post("/menu-items/{menu_item_id}/confirm-recipe", status_code=status.HTTP_200_OK)
def confirm_menu_item_recipe(
    menu_item_id: UUID,
    request: ConfirmRecipeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Confirm a recipe match for a menu item.

    Called when user swipes right or explicitly confirms a suggestion.
    """
    from src.services.recipe_matching import RecipeMatchingService

    restaurant = get_user_restaurant(db, current_user)
    service = RecipeMatchingService(db)

    mapping = service.confirm_match(menu_item_id, request.recipe_id)

    return {
        "status": "confirmed",
        "menu_item_id": str(menu_item_id),
        "recipe_id": str(request.recipe_id)
    }


@router.post("/menu-items/auto-confirm", status_code=status.HTTP_200_OK)
def auto_confirm_high_confidence_matches(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Auto-confirm all recipe matches with confidence > 90%.

    Bulk action to quickly accept obvious matches.
    """
    from src.services.recipe_matching import RecipeMatchingService

    restaurant = get_user_restaurant(db, current_user)
    service = RecipeMatchingService(db)

    confirmed_count = service.auto_confirm_high_confidence(restaurant.id)

    return {
        "status": "completed",
        "confirmed_count": confirmed_count
    }


# ============ AI Recipe Estimation Endpoints ============

@router.get("/menu-items/estimates", response_model=EstimatedRecipesResponse)
def get_recipe_estimates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    force_regenerate: bool = False
):
    """
    Get AI-generated recipe ingredient estimates for all menu items.

    Uses cached estimates when available to avoid slow OpenAI calls.
    Set force_regenerate=true to regenerate all estimates.

    Returns estimated ingredients, quantities, and costs for menu items
    that don't have confirmed recipes yet. Restaurant owners can review
    and adjust these estimates.
    """
    from src.models.menu import MenuItem
    from src.services.recipe_estimation import RecipeEstimationService
    from sqlalchemy import text

    restaurant = get_user_restaurant(db, current_user)

    # Get all menu items for this restaurant
    menu_items = db.query(MenuItem).filter(
        MenuItem.restaurant_id == restaurant.id
    ).all()

    if not menu_items:
        return EstimatedRecipesResponse(items=[], total=0)

    # Get confirmed menu item IDs to exclude them completely
    confirmed_ids = set()
    confirmed_query = text("""
        SELECT menu_item_id
        FROM cached_recipe_estimates
        WHERE is_confirmed = true
    """)
    confirmed_result = db.execute(confirmed_query)
    for row in confirmed_result:
        confirmed_ids.add(str(row.menu_item_id))

    # Check cache first (exclude confirmed recipes)
    cached_estimates = {}
    if not force_regenerate:
        # Get all cached estimates that haven't been confirmed yet
        cache_query = text("""
            SELECT menu_item_id, ingredients, total_estimated_cost, confidence, estimation_notes
            FROM cached_recipe_estimates
            WHERE is_confirmed = false OR is_confirmed IS NULL
        """)

        result = db.execute(cache_query)

        for row in result:
            cached_estimates[str(row.menu_item_id)] = {
                'ingredients': row.ingredients,
                'total_estimated_cost': row.total_estimated_cost,
                'confidence': row.confidence,
                'estimation_notes': row.estimation_notes
            }

    # Generate estimates for items not in cache
    estimation_service = RecipeEstimationService()
    estimates = []

    for item in menu_items:
        item_id_str = str(item.id)

        # Skip confirmed recipes
        if item_id_str in confirmed_ids:
            continue

        # Use cache if available
        if item_id_str in cached_estimates and not force_regenerate:
            cached = cached_estimates[item_id_str]
            estimates.append(MenuItemWithEstimateResponse(
                menu_item_id=item.id,
                menu_item_name=item.name,
                menu_item_price=item.price,
                ingredients=[
                    EstimatedIngredientResponse(**ing)
                    for ing in cached['ingredients']
                ],
                total_estimated_cost=cached['total_estimated_cost'],
                confidence=cached['confidence'],
                estimation_notes=cached['estimation_notes']
            ))
        else:
            # Generate new estimate
            try:
                estimate = estimation_service.estimate_recipe(
                    menu_item_name=item.name,
                    menu_item_price=item.price,
                    cuisine_type=item.category_path
                )

                # Save to cache
                import json
                ingredients_json = [
                    {
                        'name': ing.name,
                        'quantity': float(ing.quantity),
                        'unit': ing.unit,
                        'base_cost': float(ing.base_cost),
                        'waste_factor': float(ing.waste_factor),
                        'estimated_cost': float(ing.estimated_cost),
                        'category': ing.category,
                        'perishability': ing.perishability,
                        'notes': ing.notes
                    }
                    for ing in estimate.ingredients
                ]

                insert_query = text("""
                    INSERT INTO cached_recipe_estimates
                    (id, menu_item_id, ingredients, total_estimated_cost, confidence, estimation_notes)
                    VALUES (gen_random_uuid(), :menu_item_id, CAST(:ingredients AS jsonb), :total_cost, :confidence, :notes)
                    ON CONFLICT (menu_item_id)
                    DO UPDATE SET
                        ingredients = EXCLUDED.ingredients,
                        total_estimated_cost = EXCLUDED.total_estimated_cost,
                        confidence = EXCLUDED.confidence,
                        estimation_notes = EXCLUDED.estimation_notes,
                        updated_at = now()
                """)

                db.execute(insert_query, {
                    "menu_item_id": str(item.id),
                    "ingredients": json.dumps(ingredients_json),
                    "total_cost": float(estimate.total_estimated_cost),
                    "confidence": estimate.confidence,
                    "notes": estimate.notes
                })
                db.commit()

                estimates.append(MenuItemWithEstimateResponse(
                    menu_item_id=item.id,
                    menu_item_name=item.name,
                    menu_item_price=item.price,
                    ingredients=[
                        EstimatedIngredientResponse(
                            name=ing.name,
                            quantity=ing.quantity,
                            unit=ing.unit,
                            base_cost=ing.base_cost,
                            waste_factor=ing.waste_factor,
                            estimated_cost=ing.estimated_cost,
                            category=ing.category,
                            perishability=ing.perishability,
                            notes=ing.notes
                        )
                        for ing in estimate.ingredients
                    ],
                    total_estimated_cost=estimate.total_estimated_cost,
                    confidence=estimate.confidence,
                    estimation_notes=estimate.notes
                ))
            except Exception as e:
                print(f"Failed to estimate recipe for {item.name}: {e}")
                import traceback
                traceback.print_exc()
                continue

    return EstimatedRecipesResponse(
        items=estimates,
        total=len(estimates)
    )


@router.post("/menu-items/{menu_item_id}/save-recipe", status_code=status.HTTP_200_OK)
def save_recipe(
    menu_item_id: UUID,
    request: SaveRecipeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Save edited recipe ingredients for a menu item.

    Updates the cached recipe estimate with user-edited values.
    """
    from sqlalchemy import text
    import json

    restaurant = get_user_restaurant(db, current_user)

    # Verify menu item belongs to this restaurant
    from src.models.menu import MenuItem
    menu_item = db.query(MenuItem).filter(
        MenuItem.id == menu_item_id,
        MenuItem.restaurant_id == restaurant.id
    ).first()

    if not menu_item:
        raise HTTPException(status_code=404, detail="Menu item not found")

    # Calculate total cost
    total_cost = sum(float(ing.estimated_cost) for ing in request.ingredients)

    # Convert ingredients to JSON
    ingredients_json = [
        {
            'name': ing.name,
            'quantity': float(ing.quantity),
            'unit': ing.unit,
            'base_cost': float(ing.base_cost),
            'waste_factor': float(ing.waste_factor),
            'estimated_cost': float(ing.estimated_cost),
            'category': ing.category,
            'perishability': ing.perishability,
            'notes': ing.notes
        }
        for ing in request.ingredients
    ]

    # Update cache and mark as confirmed
    update_query = text("""
        INSERT INTO cached_recipe_estimates
        (id, menu_item_id, ingredients, total_estimated_cost, confidence, estimation_notes, is_confirmed, confirmed_at)
        VALUES (gen_random_uuid(), :menu_item_id, CAST(:ingredients AS jsonb), :total_cost, 'user_edited', 'User edited recipe', true, now())
        ON CONFLICT (menu_item_id)
        DO UPDATE SET
            ingredients = EXCLUDED.ingredients,
            total_estimated_cost = EXCLUDED.total_estimated_cost,
            confidence = 'user_edited',
            estimation_notes = 'User edited recipe',
            is_confirmed = true,
            confirmed_at = now(),
            updated_at = now()
    """)

    db.execute(update_query, {
        "menu_item_id": str(menu_item_id),
        "ingredients": json.dumps(ingredients_json),
        "total_cost": total_cost
    })
    db.commit()

    return {
        "status": "success",
        "message": "Recipe saved successfully",
        "menu_item_id": str(menu_item_id),
        "total_cost": total_cost
    }


@router.get("/menu-items/confirmed", response_model=EstimatedRecipesResponse)
def get_confirmed_recipes(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Get all confirmed recipes for the current user's restaurant.

    Returns menu items that have had their recipes confirmed/saved.
    """
    from sqlalchemy import text
    from src.models.menu import MenuItem

    restaurant = get_user_restaurant(db, current_user)

    # Get all menu items for this restaurant
    menu_items = db.query(MenuItem).filter(
        MenuItem.restaurant_id == restaurant.id
    ).all()

    if not menu_items:
        return EstimatedRecipesResponse(items=[], total=0)

    # Get confirmed recipes from cache
    confirmed_query = text("""
        SELECT menu_item_id, ingredients, total_estimated_cost, confidence, estimation_notes, confirmed_at
        FROM cached_recipe_estimates
        WHERE is_confirmed = true
    """)

    result = db.execute(confirmed_query)

    confirmed_recipes = {}
    for row in result:
        confirmed_recipes[str(row.menu_item_id)] = {
            'ingredients': row.ingredients,
            'total_estimated_cost': row.total_estimated_cost,
            'confidence': row.confidence,
            'estimation_notes': row.estimation_notes,
            'confirmed_at': row.confirmed_at
        }

    # Build response with confirmed recipes only
    estimates = []
    for item in menu_items:
        item_id_str = str(item.id)

        if item_id_str in confirmed_recipes:
            confirmed = confirmed_recipes[item_id_str]
            estimates.append(MenuItemWithEstimateResponse(
                menu_item_id=item.id,
                menu_item_name=item.name,
                menu_item_price=item.price,
                ingredients=[
                    EstimatedIngredientResponse(**ing)
                    for ing in confirmed['ingredients']
                ],
                total_estimated_cost=confirmed['total_estimated_cost'],
                confidence=confirmed['confidence'],
                estimation_notes=confirmed['estimation_notes']
            ))

    return EstimatedRecipesResponse(items=estimates, total=len(estimates))


# ============ Menu Photo Upload & OCR ============

class ExtractedMenuItem(BaseModel):
    name: str
    category: Optional[str]
    description: Optional[str]
    price: Optional[float]
    confidence: float


class MenuExtractionResponse(BaseModel):
    items: List[ExtractedMenuItem]
    total_items: int
    message: str


@router.post("/menu/upload-photo", response_model=MenuExtractionResponse)
async def upload_menu_photo(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Upload a menu photo and extract menu items using OCR.

    Accepts image files (JPEG, PNG) and uses GPT-4o Vision to extract:
    - Menu item names
    - Categories (if visible)
    - Descriptions (if visible)
    - Prices (if visible)

    Returns a list of extracted items that can then be used to generate
    ingredient estimates.
    """
    # Validate file type
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="File must be an image (JPEG, PNG, etc.)"
        )

    # Validate file size (max 10MB)
    MAX_SIZE = 10 * 1024 * 1024  # 10MB
    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=400,
            detail="File size must be less than 10MB"
        )

    # Get restaurant for context
    restaurant = get_user_restaurant(db, current_user)

    # Extract menu items using OCR service
    ocr_service = MenuOCRService()
    result = ocr_service.extract_menu_items(contents)

    if result.total_items == 0:
        return MenuExtractionResponse(
            items=[],
            total_items=0,
            message="No menu items could be extracted. Please try a clearer photo or enter items manually."
        )

    # Create menu items in database
    from src.models.menu import MenuItem
    from sqlalchemy import select

    created_count = 0
    for item in result.items:
        # Check if menu item already exists (by name)
        existing = db.execute(
            select(MenuItem).where(
                MenuItem.restaurant_id == restaurant.id,
                MenuItem.name == item.name
            )
        ).scalar_one_or_none()

        if not existing:
            # Create new menu item
            menu_item = MenuItem(
                restaurant_id=restaurant.id,
                name=item.name,
                category=item.category or "Uncategorized",
                price=Decimal(str(item.price)) if item.price else Decimal("0"),
                is_active=True
            )
            db.add(menu_item)
            created_count += 1

    db.commit()

    # Convert to response format
    items = [
        ExtractedMenuItem(
            name=item.name,
            category=item.category,
            description=item.description,
            price=item.price,
            confidence=item.confidence
        )
        for item in result.items
    ]

    message = f"Successfully extracted {result.total_items} menu items"
    if created_count > 0:
        message += f" and created {created_count} new items in your menu"

    return MenuExtractionResponse(
        items=items,
        total_items=result.total_items,
        message=message
    )
