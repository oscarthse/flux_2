# Waste Factor Integration Plan

## Current State Analysis

### What We Have
1. **Ingredient Model**: Has `waste_factor` field (0.00-0.60 representing 0-60% waste)
2. **COGSCalculator**: Applies waste factors when calculating from custom/standard recipes:
   ```python
   waste_adjusted_cost = base_cost * (1 + waste_factor)
   ```
3. **Cached Recipe Estimates**: Store ingredients as JSONB with:
   - name, quantity, unit, estimated_cost, notes
   - **Missing**: waste_factor, perishability, category

### The Problem
- AI-generated recipes currently store only `estimated_cost` (single number)
- No breakdown showing: base_cost vs waste-adjusted cost
- Users can't see or edit waste factors during recipe confirmation
- COGS calculation uses estimated_cost directly without proper waste factor application
- No visibility into which ingredients drive waste costs

## The Value Proposition

**What makes this special:**
Most restaurant systems calculate simple margins (Price - Cost). Flux should show:
- **Base Cost**: Raw ingredient cost
- **Waste Factor**: Realistic % lost to trimming, spoilage, prep errors
- **True COGS**: Base cost + waste cost
- **Hidden Cost Visibility**: Show which items have hidden waste costs

**Example:**
```
Caesar Salad - $11.99
Traditional view:
  Cost: $4.30 → Margin: 64%

Flux view with waste factors:
  Romaine Lettuce: $1.30 base + 15% waste ($0.20) = $1.50
  Parmesan: $1.00 base + 5% waste ($0.05) = $1.05
  Total Base: $4.30
  Total Waste: $0.45 (10.4% hidden cost!)
  True COGS: $4.75
  Real Margin: 60.4% (not 64%)
```

## Solution Design

### Phase 1: Data Model Enhancement

#### 1.1 Update cached_recipe_estimates.ingredients JSONB structure
```json
{
  "name": "Romaine Lettuce",
  "quantity": 150.0,
  "unit": "g",
  "base_cost": 1.30,
  "waste_factor": 0.15,
  "waste_cost": 0.20,
  "total_cost": 1.50,
  "perishability": "high",
  "category": "produce",
  "notes": "High waste due to outer leaves"
}
```

**Migration needed:**
- Add fields to existing ingredient objects
- Backward compatible: default waste_factor=0.0 for existing data

#### 1.2 Update schemas
```python
class EstimatedIngredientResponse(BaseModel):
    name: str
    quantity: Decimal
    unit: str
    base_cost: Decimal  # New: separated from total
    waste_factor: Decimal = Decimal(0)  # New: 0.00-0.60
    waste_cost: Decimal = Decimal(0)  # New: calculated field
    total_cost: Decimal  # New: base_cost + waste_cost
    perishability: Optional[str] = None  # New: "low"/"medium"/"high"
    category: Optional[str] = None  # New: "produce"/"meat"/"dairy"/etc
    notes: Optional[str] = None
```

### Phase 2: AI Estimation Enhancement

#### 2.1 Update RecipeEstimationService prompt
Add waste factor intelligence based on ingredient type:

```python
WASTE_FACTOR_GUIDANCE = {
    "produce": {
        "leafy_greens": 0.15,  # lettuce, spinach, herbs
        "root_vegetables": 0.10,  # potatoes, carrots
        "fruits": 0.12,
    },
    "meat": {
        "beef": 0.20,  # trimming fat, bones
        "chicken": 0.15,
        "fish": 0.25,  # highest waste
    },
    "dairy": {
        "cheese": 0.05,  # low waste
        "milk": 0.02,
    },
    "dry_goods": {
        "pasta": 0.01,  # minimal waste
        "flour": 0.03,
    }
}
```

#### 2.2 Enhanced AI prompt
```
You are estimating ingredient costs for a restaurant recipe.
For each ingredient, provide:
1. Base cost (raw ingredient purchase price)
2. Waste factor (0.00-0.60):
   - Produce (leafy): 15% typical
   - Produce (root): 10% typical
   - Meat/protein: 15-25% depending on cut
   - Dairy: 2-5%
   - Dry goods: 1-3%
3. Perishability: low/medium/high
4. Category: produce/meat/dairy/dry_goods/other

Consider:
- Trimming waste (lettuce outer leaves, meat fat)
- Prep waste (vegetable peels, bone removal)
- Spoilage risk (highly perishable items)
- Portion control errors (typical restaurant waste)
```

### Phase 3: UI Enhancement

#### 3.1 Recipe Confirmation Component Updates

**Add waste factor editing to RecipeConfirmation.tsx:**

```tsx
// Expanded ingredient row
<div className="grid grid-cols-12 gap-2">
  <div className="col-span-3">
    <Input value={ingredient.name} onChange={...} />
  </div>
  <div className="col-span-1">
    <Input type="number" value={ingredient.quantity} />
  </div>
  <div className="col-span-1">
    <Input value={ingredient.unit} />
  </div>
  <div className="col-span-2">
    <label className="text-xs text-muted-foreground">Base Cost</label>
    <Input type="number" value={ingredient.base_cost} step="0.01" />
  </div>
  <div className="col-span-1">
    <label className="text-xs text-muted-foreground">Waste %</label>
    <Input type="number" value={ingredient.waste_factor * 100}
           max="60" step="1"
           onChange={(e) => updateWasteFactor(e.target.value / 100)} />
  </div>
  <div className="col-span-2">
    <label className="text-xs text-muted-foreground">Total Cost</label>
    <div className="font-semibold">
      ${(ingredient.base_cost * (1 + ingredient.waste_factor)).toFixed(2)}
    </div>
  </div>
  <div className="col-span-1">
    <Badge variant={getPerishabilityColor(ingredient.perishability)}>
      {ingredient.perishability}
    </Badge>
  </div>
  <div className="col-span-1">
    <Button onClick={() => removeIngredient(index)}>
      <Trash2 />
    </Button>
  </div>
</div>
```

**Visual indicators:**
- Color-code waste factors: <5% green, 5-15% yellow, >15% red
- Show waste cost breakdown in summary
- Highlight high-waste ingredients

#### 3.2 Summary Section Enhancement

```tsx
<div className="summary-card">
  <div className="cost-breakdown">
    <div>Base Ingredient Cost: ${baseTotal.toFixed(2)}</div>
    <div className="text-amber-600">+ Waste Cost: ${wasteTotal.toFixed(2)}
      <span className="text-sm">({wastePct.toFixed(1)}%)</span>
    </div>
    <div className="border-t font-bold">True COGS: ${totalCost.toFixed(2)}</div>
  </div>

  <div className="margin-comparison">
    <div className="text-muted-foreground">
      Without waste: {((price - baseTotal) / price * 100).toFixed(1)}%
    </div>
    <div className="text-foreground font-semibold">
      Real margin: {((price - totalCost) / price * 100).toFixed(1)}%
    </div>
  </div>
</div>
```

### Phase 4: COGS Calculator Updates

#### 4.1 Update _calculate_from_cached_estimate

```python
def _calculate_from_cached_estimate(self, menu_item: MenuItem) -> Optional[list[IngredientCost]]:
    """Calculate COGS from confirmed cached recipe estimates with proper waste factors."""
    # ... query code ...

    breakdown = []
    for ing_data in ingredients_data:
        base_cost = Decimal(str(ing_data.get('base_cost', ing_data.get('estimated_cost', 0))))
        waste_factor = Decimal(str(ing_data.get('waste_factor', 0)))
        quantity = Decimal(str(ing_data['quantity']))

        # Calculate properly
        waste_adjusted_cost = base_cost * (1 + waste_factor)

        breakdown.append(IngredientCost(
            ingredient_id=UUID_TYPE('00000000-0000-0000-0000-000000000000'),
            ingredient_name=ing_data['name'],
            quantity=quantity,
            unit=ing_data['unit'],
            unit_cost=base_cost / quantity if quantity > 0 else Decimal(0),
            waste_factor=waste_factor,
            base_cost=base_cost,
            waste_adjusted_cost=waste_adjusted_cost
        ))

    return breakdown
```

### Phase 5: Profitability Dashboard Enhancement

#### 5.1 Add waste factor visibility

Update ProfitabilityDashboard to show:
- Total waste cost per item
- Waste % of total COGS
- Flag high-waste items
- Sorting by waste impact

```tsx
<div className="waste-indicator">
  {item.total_waste > 0 && (
    <Badge variant="warning">
      ${item.total_waste.toFixed(2)} waste ({item.waste_pct.toFixed(1)}%)
    </Badge>
  )}
</div>
```

### Phase 6: Confirmed Recipes View Enhancement

Add waste breakdown to ConfirmedRecipes component:

```tsx
{/* Waste Analysis Section */}
<div className="waste-analysis bg-amber-50 dark:bg-amber-950/20 p-4 rounded-lg">
  <h4 className="font-semibold text-sm mb-2">Waste Impact</h4>
  <div className="grid grid-cols-2 gap-4 text-sm">
    <div>
      <div className="text-muted-foreground">Base Cost</div>
      <div className="font-semibold">${baseCost.toFixed(2)}</div>
    </div>
    <div>
      <div className="text-muted-foreground">Waste Cost</div>
      <div className="font-semibold text-amber-600">${wasteCost.toFixed(2)}</div>
    </div>
  </div>

  {/* High waste ingredients */}
  {highWasteIngredients.length > 0 && (
    <div className="mt-2">
      <div className="text-xs text-muted-foreground">High waste items:</div>
      <div className="text-xs">
        {highWasteIngredients.map(ing =>
          `${ing.name} (${(ing.waste_factor * 100).toFixed(0)}%)`
        ).join(', ')}
      </div>
    </div>
  )}
</div>
```

## Implementation Order

### Sprint 1: Backend Foundation (Days 1-2)
1. ✅ Create migration to update ingredient JSONB structure (backward compatible)
2. ✅ Update RecipeEstimationService with waste factor intelligence
3. ✅ Update API schemas (EstimatedIngredientResponse)
4. ✅ Test AI generates proper waste factors

### Sprint 2: COGS Integration (Day 3)
1. ✅ Update _calculate_from_cached_estimate to use base_cost + waste_factor
2. ✅ Update MenuProfitabilityResponse to include waste breakdown
3. ✅ Add waste_cost and waste_pct fields to responses
4. ✅ Test profitability API returns waste data

### Sprint 3: UI - Recipe Confirmation (Days 4-5)
1. ✅ Add waste factor input fields to RecipeConfirmation
2. ✅ Add real-time calculation of waste costs
3. ✅ Add visual indicators (colors, badges)
4. ✅ Add summary showing base vs total cost
5. ✅ Update save endpoint to store all waste data

### Sprint 4: UI - Visualization (Day 6)
1. ✅ Update ConfirmedRecipes to show waste analysis
2. ✅ Update ProfitabilityDashboard with waste indicators
3. ✅ Add waste factor tooltips/help text
4. ✅ Create waste impact sorting/filtering

### Sprint 5: Polish & Documentation (Day 7)
1. ✅ Add inline help explaining waste factors
2. ✅ Create sample data with realistic waste factors
3. ✅ Update user documentation
4. ✅ End-to-end testing

## Success Metrics

After implementation, users should be able to:
1. ✅ See AI-estimated waste factors for each ingredient
2. ✅ Edit waste factors during recipe confirmation
3. ✅ See cost breakdown: base cost vs waste cost
4. ✅ Identify high-waste items impacting profitability
5. ✅ Compare "simple margin" vs "true margin with waste"

## Data Migration Strategy

For existing cached recipes without waste factors:
```sql
-- Set default waste factors based on ingredient name patterns
UPDATE cached_recipe_estimates
SET ingredients = (
  SELECT jsonb_agg(
    CASE
      -- Add default waste_factor based on keywords
      WHEN ing->>'name' ILIKE '%lettuce%' THEN ing || '{"waste_factor": 0.15}'::jsonb
      WHEN ing->>'name' ILIKE '%meat%' OR ing->>'name' ILIKE '%beef%' THEN ing || '{"waste_factor": 0.20}'::jsonb
      WHEN ing->>'name' ILIKE '%cheese%' THEN ing || '{"waste_factor": 0.05}'::jsonb
      ELSE ing || '{"waste_factor": 0.10}'::jsonb  -- default 10%
    END
  )
  FROM jsonb_array_elements(ingredients) AS ing
)
WHERE NOT ingredients @> '[{"waste_factor": 0}]'::jsonb;
```

## Long-term Enhancements

1. **Machine Learning**: Learn actual waste factors from inventory data
2. **Seasonal Adjustments**: Higher waste in summer for produce
3. **Supplier Integration**: Different waste factors per supplier
4. **Historical Tracking**: Track how waste factors change over time
5. **Prep Method Impact**: Different waste for different prep methods
6. **Staff Training**: Identify prep waste vs spoilage waste
