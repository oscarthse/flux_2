# Epic 3: Recipe Intelligence & Ingredient Management

**Status:** Not Started
**Epic Goal**: Build the "Recipe Explosion" system that breaks down menu items into component ingredients with quantities, leveraging a proprietary database of 10,000+ standard recipes, providing smart defaults for operator confirmation via swipe-based UI, and calculating true COGS (Cost of Goods Sold) per menu item. This epic unlocks procurement optimization and profitability analysis.

**Critical Business Value**: Recipe data is the foundation for:
1. **Procurement**: Translate demand forecasts (Epic 4) into ingredient orders
2. **Profitability**: Calculate true COGS including waste/trim factors
3. **Waste Reduction**: Track expiring ingredients and suggest promotions (Epic 5)

---

## User Stories

### Story 3.1: Recipe Database Schema & Seeding

**As a backend developer,**
**I want a normalized database schema for recipes, ingredients, and their relationships,**
**so that I can store and query recipe data efficiently.**

#### Business Context
The recipe database is Flux's **competitive moat**. Unlike generic restaurant software, Flux ships with:
- 10,000+ standard recipes (French, Italian, American, Asian, Mexican cuisines)
- Ingredient taxonomy (proteins, produce, dairy, dry goods, etc.)
- Waste/trim factors (whole chicken → usable meat = 65% yield)
- Allergen tags, dietary flags (vegan, gluten-free, dairy-free)

#### Database Design

**Core Tables:**

1. **`ingredients`**
   - `id`, `name`, `category`, `unit` (kg, L, each), `avg_cost_per_unit`
   - `perishability` (1-7 day shelf life), `allergens` (JSON array)
   - `waste_factor` (0.0-1.0, e.g., 0.35 = 35% waste after trim)

2. **`recipes`**
   - `id`, `name`, `cuisine_type`, `category`, `servings`
   - `prep_time_minutes`, `skill_level` (1-5)
   - `is_standard` (true for Flux's 10K database, false for custom)

3. **`recipe_ingredients`** (join table)
   - `recipe_id`, `ingredient_id`, `quantity`, `unit`
   - `preparation` (e.g., "diced", "julienned", "whole")
   - `is_optional` (for garnishes, sides)

4. **`menu_item_recipes`** (maps restaurant's menu to recipes)
   - `menu_item_id` (FK to restaurant's actual menu)
   - `recipe_id` (FK to standard or custom recipe)
   - `yield_multiplier` (1.0 = standard serving, 1.5 = XL portion)
   - `confirmed_by_user` (boolean, starts false for auto-suggestions)
   - `confidence_score` (0.0-1.0 for AI-suggested matches)

#### Dev Notes
- Seed database with 10,000 recipes sourced from:
  - Open recipe databases (RecipeDB, Spoonacular API historical data)
  - Culinary textbooks (Le Cordon Bleu, CIA Culinary Institute)
  - Standardized recipes from restaurant supply companies
- Normalize ingredient names (e.g., "Tomato", "Roma Tomato", "Cherry Tomato" → parent "Tomato" with variants)
- Use JSONB for allergen/dietary tags for fast querying

#### Acceptance Criteria
1. Database schema supports standard recipes, custom recipes, and menu item mappings
2. 10,000 standard recipes seeded (target: 60% American, 15% Italian, 10% Asian, 10% Mexican, 5% French)
3. 2,000+ unique ingredients seeded with categories and waste factors
4. Ingredients table includes top 500 most common restaurant ingredients with avg costs
5. Recipe search by name, cuisine, ingredients works (full-text search indexed)
6. Allergen filtering works (e.g., "show all dairy-free recipes")
7. Waste factor validation (0.0 ≤ waste_factor ≤ 0.6, reject if outside range)

#### Tasks
- [ ] Create `ingredients` model with category taxonomy and waste factors
- [ ] Create `recipes` model with cuisine/category classification
- [ ] Create `recipe_ingredients` join table with preparation notes
- [ ] Create `menu_item_recipes` mapping table with confirmation tracking
- [ ] Design ingredient taxonomy (3-level hierarchy: Category > Subcategory > Item)
- [ ] Source and clean 10,000 recipe dataset (CSV import)
- [ ] Seed ingredients table with 2,000+ entries + avg costs (use USDA pricing data)
- [ ] Add full-text search index on recipes.name, ingredients.name (PostgreSQL `tsvector`)
- [ ] Create database views for common queries (recipe_with_ingredients, menu_item_cogs)
- [ ] Write data validation tests (waste factors, units, cost ranges)

---

### Story 3.2: AI-Powered Recipe Matching

**As a restaurant owner,**
**I want Flux to automatically suggest which standard recipe matches each of my menu items,**
**so that I don't have to manually enter ingredients for every dish.**

#### ML Approach: Semantic Similarity + Fuzzy Matching

**Algorithm Pipeline:**
1. **Exact name match** (case-insensitive): "Caesar Salad" → recipe "Caesar Salad"
2. **Fuzzy string match** (Levenshtein distance): "Ceasar Salad" → recipe "Caesar Salad" (typo tolerance)
3. **Semantic embedding match** (sentence transformers):
   - Encode menu item name: `"Grilled Salmon with Lemon Butter"`
   - Find closest recipe embedding in vector space
   - Use `all-MiniLM-L6-v2` model (fast, 384-dim embeddings)
4. **Category filtering**: If menu item category known (from Epic 2), filter recipes by cuisine/category
5. **Confidence scoring**:
   ```python
   confidence = 0.5 * name_similarity + 0.3 * ingredient_overlap + 0.2 * category_match
   ```

#### Dev Notes
- Use `sentence-transformers` library for semantic search
- Precompute embeddings for all 10K recipes (store in `recipes.embedding` JSONB column)
- Use PostgreSQL `pgvector` extension for fast similarity search
- Return top 3 matches with confidence scores
- Auto-accept if confidence >0.9, suggest if 0.7-0.9, manual if <0.7

#### Acceptance Criteria
1. Matches menu items to recipes with >85% top-1 accuracy on test set (100 menu items)
2. Returns top 3 recipe suggestions with confidence scores
3. Auto-accepts match if confidence >0.9 and creates `menu_item_recipes` entry
4. Flags low-confidence matches (<0.7) for manual review
5. Handles common variations ("Burger" → "Hamburger", "Fries" → "French Fries")
6. Supports multi-language menu items (English, Spanish) via translation before matching
7. Completes matching for 100 menu items in <10 seconds

#### Tasks
- [ ] Install `sentence-transformers` and `pgvector` PostgreSQL extension
- [ ] Precompute embeddings for all 10,000 recipes (batch job)
- [ ] Store embeddings in `recipes.embedding` column (VECTOR type)
- [ ] Implement `RecipeMatchingService` with 4-stage pipeline
- [ ] Add fuzzy string matching using `fuzzywuzzy` or `rapidfuzz`
- [ ] Create `POST /api/recipes/match-menu-items` endpoint
- [ ] Return top 3 matches with confidence breakdown (name, ingredient, category scores)
- [ ] Auto-create `menu_item_recipes` for high-confidence matches
- [ ] Build test dataset of 100 real menu items with ground truth recipes
- [ ] Achieve >85% top-1 accuracy, >95% top-3 accuracy on test set
- [ ] Add fallback: if no good match, suggest "create custom recipe"

---

### Story 3.3: Swipe-Based Recipe Confirmation UI

**As a restaurant owner,**
**I want a fast, intuitive way to confirm or reject AI-suggested recipes,**
**so that I can validate my menu setup in minutes, not hours.**

#### UX Inspiration: Tinder for Recipes
- Show menu item card with suggested recipe
- **Swipe right** → Accept (creates confirmed `menu_item_recipes` entry)
- **Swipe left** → Reject (show next suggestion or "create custom")
- **Swipe up** → Skip for now (mark for later review)
- **Tap card** → View full recipe details (ingredients, prep steps)

#### Design Specifications
- Mobile-first (restaurant owners use phones/tablets)
- Large, thumb-friendly swipe targets
- Show recipe preview: name, cuisine, top 5 ingredients, photo (if available)
- Display confidence score visually (3-star rating: ⭐⭐⭐ = 90%+, ⭐⭐ = 70-90%, ⭐ = 50-70%)
- Progress indicator: "12 of 45 items confirmed"
- Bulk actions: "Accept all high-confidence matches" button

#### Dev Notes
- Use React gesture library (`react-swipeable` or `framer-motion`)
- Fetch unconfirmed menu items from `GET /api/menu-items/unconfirmed`
- For each item, fetch top 3 recipe suggestions
- On swipe right: `POST /api/menu-items/{id}/confirm-recipe` with `recipe_id`
- On swipe left: skip to next suggestion or show "custom recipe" prompt
- Store swipe history for analytics (track rejection reasons)

#### Acceptance Criteria
1. Mobile-responsive swipe interface works on iOS and Android browsers
2. Displays menu item name, photo (if available), and suggested recipe preview
3. Swipe right confirms recipe (updates `menu_item_recipes.confirmed_by_user = true`)
4. Swipe left shows next suggestion or "create custom recipe" option
5. Swipe up skips item (marks for later review)
6. Tap card shows full recipe details (ingredients, allergens, prep time)
7. Progress indicator shows X/Y items confirmed
8. "Accept all high-confidence" bulk action (confidence >0.9)
9. Works offline (caches suggestions, syncs on reconnect)

#### Tasks
- [ ] Create `RecipeSwipeCard` React component with gesture handling
- [ ] Implement swipe detection (left, right, up) using `react-swipeable`
- [ ] Build recipe preview card layout (name, cuisine, ingredients list, photo placeholder)
- [ ] Create `GET /api/menu-items/unconfirmed` endpoint (returns items needing confirmation)
- [ ] Create `POST /api/menu-items/{id}/confirm-recipe` endpoint
- [ ] Create `POST /api/menu-items/{id}/reject-recipe` endpoint (logs rejection reason)
- [ ] Add progress indicator component (X of Y confirmed, % complete)
- [ ] Implement "Accept all high-confidence" bulk action
- [ ] Add keyboard shortcuts (Arrow Left = reject, Arrow Right = accept, Arrow Up = skip)
- [ ] Write E2E test: swipe through 10 items, verify confirmations saved
- [ ] Add analytics event tracking (swipe_accept, swipe_reject, swipe_skip)

---

### Story 3.4: Custom Recipe Builder

**As a restaurant owner,**
**I want to create custom recipes for my signature dishes,**
**so that Flux can calculate accurate COGS and procurement needs.**

#### User Flow
1. User navigates to "Create Custom Recipe" (from swipe UI or menu)
2. Enters recipe name, cuisine, category
3. Adds ingredients one-by-one:
   - Search ingredient database (autocomplete)
   - Enter quantity + unit (e.g., "500 g", "2 each")
   - Optionally add preparation note ("diced", "julienned")
4. Reviews ingredient list, total estimated cost
5. Saves recipe → auto-links to menu item

#### Smart Defaults & Assistance
- **AI ingredient suggestions**:
  - Analyze recipe name: "Chicken Parmesan" → suggest "Chicken Breast", "Mozzarella", "Marinara Sauce", "Breadcrumbs"
  - Use LLM (GPT-4) to generate ingredient list from name
- **Photo upload + OCR**:
  - User uploads photo of handwritten recipe
  - Extract ingredients using OCR (Tesseract) + LLM parsing
  - Present extracted list for validation
- **Cost estimation**:
  - Pull avg ingredient costs from database
  - Calculate total recipe cost, display per-serving cost
  - Show breakdown: "Protein: €4.50, Produce: €1.20, Dairy: €0.80, Dry Goods: €0.50 = €7.00/serving"

#### Dev Notes
- Use typeahead autocomplete for ingredient search (fast, indexed)
- Support bulk ingredient add via paste (comma-separated list)
- Validate quantities: unit must match ingredient's base unit (convert if needed)
- Store custom recipes with `is_standard = false`

#### Acceptance Criteria
1. User can create custom recipe with name, cuisine, category
2. Ingredient search autocomplete returns results in <200ms
3. Supports adding ingredients with quantity, unit, preparation note
4. Validates quantity + unit compatibility (e.g., can't use "kg" for "Eggs")
5. AI suggests 5-10 likely ingredients based on recipe name
6. Photo upload + OCR extracts ingredients with 70%+ accuracy
7. Displays total recipe cost and per-serving cost
8. Saves recipe and auto-links to menu item
9. Allows editing existing custom recipes

#### Tasks
- [ ] Create `CustomRecipeForm` React component with multi-step wizard
- [ ] Implement ingredient autocomplete using `GET /api/ingredients/search?q={query}`
- [ ] Add quantity + unit input with validation (unit converter)
- [ ] Create `POST /api/recipes/custom` endpoint
- [ ] Integrate LLM for AI ingredient suggestions (OpenAI or Anthropic API)
  - Prompt: "List 8-12 ingredients for this recipe: {name}. Return JSON array."
- [ ] Implement photo OCR pipeline:
  - Upload to S3
  - Trigger Lambda with Tesseract OCR
  - Parse text with LLM to extract structured ingredients
- [ ] Build cost calculator component (sum ingredient costs, show breakdown)
- [ ] Add recipe preview before saving (ingredient list, total cost, servings)
- [ ] Create `PUT /api/recipes/{id}` endpoint for editing
- [ ] Write E2E test: create custom recipe, verify saved correctly

---

### Story 3.5: Ingredient Cost Management

**As a restaurant owner,**
**I want to update ingredient costs based on my actual supplier prices,**
**so that COGS calculations reflect reality, not generic averages.**

#### Business Problem
Flux ships with avg ingredient costs (e.g., "Chicken Breast = €8/kg") but:
- Prices vary by region (NYC vs rural Montana)
- Bulk purchasing changes unit cost
- Seasonal pricing (tomatoes expensive in winter)
- Supplier relationships (negotiated pricing)

**Solution**: Allow users to override costs with actual invoiced prices

#### User Flow
1. Navigate to "Ingredient Costs" page (table view)
2. See all ingredients used in restaurant's recipes
3. Edit cost per unit (inline edit or modal)
4. Optionally upload supplier invoice (PDF/photo)
   - OCR extracts item names + prices
   - Auto-matches to ingredient database
   - Suggests cost updates
5. View cost history (track price changes over time)

#### Invoice OCR Pipeline
- User uploads PDF invoice or photo
- Extract text with OCR (Tesseract or AWS Textract)
- Parse structured data with LLM:
  ```
  Prompt: "Extract ingredient names and prices from this invoice. Return JSON array: [{item, quantity, unit, price_per_unit}]"
  ```
- Fuzzy match extracted items to ingredient database
- Present suggested cost updates for user confirmation

#### Dev Notes
- Store cost history in `ingredient_cost_history` table (ingredient_id, cost, effective_date, source)
- Use most recent cost for COGS calculations
- Flag ingredients with stale costs (>90 days old, no update)

#### Acceptance Criteria
1. User can view all ingredients used in their recipes (table with search/filter)
2. Inline edit ingredient cost (validates >0, <€10,000/unit)
3. Cost history tracked in `ingredient_cost_history` table
4. Invoice upload supports PDF, JPG, PNG formats
5. OCR extracts 80%+ of items with prices from standard invoices
6. Fuzzy matching links extracted items to ingredients with 75%+ accuracy
7. User confirms cost updates before applying
8. COGS calculations use latest cost (fallback to avg if no custom cost)
9. Data health score rewards cost accuracy (accuracy sub-score)

#### Tasks
- [ ] Create `ingredient_cost_history` model (ingredient_id, cost, effective_date, source)
- [ ] Create `IngredientCostTable` React component (table with inline edit)
- [ ] Implement `PUT /api/ingredients/{id}/cost` endpoint
- [ ] Add invoice upload UI (drag-and-drop or file picker)
- [ ] Implement OCR pipeline:
  - Upload to S3
  - Trigger Lambda with AWS Textract or Tesseract
  - Parse extracted text with LLM (OpenAI/Anthropic)
  - Return structured JSON: [{item, quantity, unit, price}]
- [ ] Build invoice parser: fuzzy match items to ingredients
- [ ] Create `POST /api/ingredients/bulk-update-costs` endpoint
- [ ] Display cost history chart (line graph, 90-day history per ingredient)
- [ ] Flag stale costs in UI (warning icon, "Cost last updated 120 days ago")
- [ ] Write integration test: upload sample invoice, verify cost updates

---

### Story 3.6: COGS Calculation & Menu Profitability

**As a restaurant owner,**
**I want to see the true cost and profitability of each menu item,**
**so that I can make data-driven pricing and menu optimization decisions.**

#### Profitability Formula
Per [13-algorithm-architecture.md:L264-L299](../architecture/13-algorithm-architecture.md#L264-L299):

```python
# 1. Direct costs (COGS)
COGS_item = Σ (ingredient_qty * ingredient_cost * (1 + waste_factor))

# 2. Labor cost per item (estimated)
labor_cost_item = prep_time_minutes * (labor_rate / 60)

# 3. Overhead allocation (simplified)
overhead_item = (sales_volume_item / total_sales_volume) * total_overhead

# 4. Contribution margin
contribution_margin = price - COGS_item

# 5. True profitability
profit_item = price - COGS - labor_cost - overhead_allocation
margin_pct = (profit_item / price) * 100
```

#### Menu Matrix Analysis
Categorize items using BCG matrix (see [13-algorithm-architecture.md:L301-L306](../architecture/13-algorithm-architecture.md#L301-L306)):

| Quadrant | Volume | Margin | Action |
|----------|--------|--------|--------|
| **Stars** | High | High | Promote heavily, never remove |
| **Puzzles** | Low | High | Market more, increase visibility |
| **Plow Horses** | High | Low | Re-engineer recipe, raise price |
| **Dogs** | Low | Low | Remove or fix immediately |

#### Dev Notes
- Calculate COGS in real-time when viewing menu item (no pre-computation)
- Labor cost estimation:
  - Use category defaults: Appetizer=10min, Entree=15min, Dessert=8min
  - Allow manual override per item
- Overhead allocation simplified: proportional to sales volume
- Display margin % with color coding (red <20%, yellow 20-35%, green >35%)

#### Acceptance Criteria
1. Displays COGS per menu item including waste factors
2. Shows contribution margin (price - COGS)
3. Estimates labor cost per item (category default or custom)
4. Calculates true profit margin %
5. Categorizes items into BCG matrix quadrants (Stars, Puzzles, Plow Horses, Dogs)
6. Sortable table: by margin %, by volume, by profit $
7. Highlights low-margin items (<20%) in red
8. Suggests actions for each quadrant (promote, re-engineer, remove)
9. Exports profitability report as CSV

#### Tasks
- [ ] Create `CalculateCOGS` service function
  - Query recipe ingredients for menu item
  - Sum ingredient costs with waste factors
  - Return breakdown: [{ingredient, qty, cost, waste_adjusted_cost}]
- [ ] Create `CalculateProfitability` service function
  - Call `CalculateCOGS`
  - Add labor cost estimate (category default or custom)
  - Add overhead allocation
  - Return profit, margin %, quadrant
- [ ] Create `GET /api/menu-items/{id}/profitability` endpoint
- [ ] Create `MenuProfitabilityTable` React component
  - Sortable columns (margin %, volume, profit $)
  - Color-coded margins (red/yellow/green)
  - BCG quadrant badges
- [ ] Implement BCG matrix categorization logic
  - High/low volume threshold = median volume
  - High/low margin threshold = 25%
- [ ] Add action suggestions per quadrant
- [ ] Create CSV export functionality
- [ ] Write unit tests for COGS calculation edge cases (missing ingredients, zero costs)
- [ ] Add profitability page to main navigation

---

### Story 3.7: Recipe Explosion for Procurement

**As a backend developer,**
**I want to "explode" demand forecasts into ingredient requirements,**
**so that procurement recommendations show exactly what to order.**

#### Mathematical Model
Given:
- Demand forecast for menu item `i`: `forecast_i` (units expected to sell)
- Recipe for item `i`: `recipe_i = {(ingredient_j, qty_j, waste_factor_j)}`

Calculate:
```python
ingredient_demand_j = Σ_i (forecast_i * qty_ij * (1 + waste_factor_j))
```

Where `qty_ij` = quantity of ingredient `j` in recipe `i`

**Example:**
- Forecast: 50 Chicken Parmesan dishes
- Recipe: 200g chicken breast per dish, waste factor = 0.10 (10% trim loss)
- Ingredient demand: 50 * 200g * 1.10 = 11,000g = 11kg chicken breast

#### Aggregation Across Items
Multiple menu items use same ingredient:
- Chicken Parmesan → 11kg chicken
- Chicken Caesar Salad → 3kg chicken
- **Total chicken demand = 14kg**

#### Dev Notes
- Query all menu items with forecasts for target date range (e.g., next 7 days)
- For each item, fetch recipe ingredients
- Aggregate by ingredient across all items
- Apply waste factors
- Return prioritized list (sort by $ value, perishability)

#### Acceptance Criteria
1. Given forecast for N menu items, calculates ingredient requirements
2. Aggregates same ingredient across multiple recipes
3. Applies waste/trim factors to quantities
4. Returns ingredient list with:
   - Name, total quantity needed, unit
   - Estimated cost (qty * latest unit cost)
   - Perishability (days until spoilage)
   - Current inventory level (if tracked)
5. Sorts by priority: perishable + high-value items first
6. Handles missing recipes gracefully (exclude item from explosion, log warning)
7. Completes explosion for 100 menu items in <2 seconds

#### Tasks
- [ ] Create `ExplodeRecipes` service function
  - Input: list of (menu_item_id, forecasted_qty)
  - Query recipes for each item
  - Aggregate ingredients across all recipes
  - Apply waste factors
  - Return: [{ingredient_id, total_qty, unit, cost, perishability}]
- [ ] Handle unit conversions (kg → g, L → mL)
- [ ] Create `POST /api/procurement/calculate-requirements` endpoint
- [ ] Add inventory integration (subtract current stock from requirements)
- [ ] Prioritize by perishability and $ value
- [ ] Write unit tests for aggregation logic
- [ ] Write integration test: forecast 3 items → verify ingredient explosion correct
- [ ] Optimize query performance (join recipes, ingredients in single query)

---

### Story 3.8: Ingredient Substitutions & Alternatives

**As a restaurant owner,**
**I want to define ingredient substitutions,**
**so that Flux can adjust recipes when I'm out of stock or prices spike.**

#### Use Cases
1. **Out of stock**: Chicken breast unavailable → suggest thighs (adjust cost, prep time)
2. **Price spike**: Salmon price 2x normal → suggest cod or mahi-mahi
3. **Seasonal**: Tomatoes expensive in winter → suggest canned tomatoes
4. **Dietary**: Customer requests gluten-free → substitute regular flour with GF blend

#### Data Model
Create `ingredient_substitutions` table:
- `ingredient_id` (original)
- `substitute_id` (replacement)
- `conversion_ratio` (1.0 = 1:1, 1.2 = use 20% more substitute)
- `cost_delta` (% change in cost)
- `quality_impact` (1-5 scale, 5 = identical, 1 = poor substitute)
- `substitution_type` (exact, approximate, dietary)

#### Dev Notes
- Seed with common substitutions (e.g., butter ↔ margarine, chicken ↔ turkey)
- Allow user to add custom substitutions
- When calculating COGS, check if original ingredient unavailable → use substitute cost
- Flag dishes using substitutes in UI (badge: "Made with substitute ingredient")

#### Acceptance Criteria
1. Database supports ingredient substitutions with conversion ratios
2. Seeded with 200+ common substitutions
3. User can add custom substitutions via UI
4. COGS calculation checks availability → uses substitute if original unavailable
5. Procurement recommendations suggest substitutes if original out of stock
6. UI displays "substitute used" badge on affected menu items
7. Quality impact visible (warn if substitute is low-quality)

#### Tasks
- [ ] Create `ingredient_substitutions` model
- [ ] Seed with 200+ common substitutions (research culinary equivalents)
- [ ] Create `POST /api/ingredients/{id}/substitutions` endpoint
- [ ] Modify `CalculateCOGS` to check substitutions
- [ ] Modify `ExplodeRecipes` to suggest substitutes if ingredient unavailable
- [ ] Build substitution management UI (table, add/edit/delete)
- [ ] Add "substitute used" badge to menu item cards
- [ ] Write test: ingredient unavailable → COGS uses substitute cost

---

## Epic Acceptance Criteria

**This epic is complete when:**

1. **Recipe Database Operational**
   - 10,000 standard recipes seeded and searchable
   - 2,000+ ingredients with costs, waste factors, allergens
   - Full-text search works (name, cuisine, ingredients)

2. **AI Recipe Matching Works**
   - Matches menu items to recipes with >85% top-1 accuracy
   - Swipe UI allows confirming 100 items in <10 minutes
   - Custom recipe builder supports photo OCR + AI suggestions

3. **COGS Calculation Accurate**
   - Displays true cost per menu item (ingredients + waste)
   - Menu profitability table categorizes items (Stars, Puzzles, Plow Horses, Dogs)
   - Cost history tracked, invoice OCR updates costs

4. **Recipe Explosion Functional**
   - Converts demand forecasts → ingredient requirements
   - Aggregates across menu items, applies waste factors
   - Prioritizes by perishability and $ value

5. **Test Coverage**
   - Unit test: COGS calculation for 20+ recipes with edge cases
   - Integration test: Recipe explosion for 50 menu items
   - E2E test: User swipes through 10 recipes, creates 1 custom, views profitability

---

## Dev Agent Record

### Agent Model Used
- model: TBD

### Debug Log References
- TBD

### Completion Notes
- Epic not yet started

### Dependencies
- **Epic 2 (Data Ingestion)** must complete first:
  - Need menu items extracted from transactions
  - Need item categorization for recipe matching
- **Epic 4 (Forecasting)** depends on this:
  - Forecasts must explode into ingredient requirements
  - Cannot generate procurement recommendations without recipes

### File List
- `apps/api/src/models/ingredient.py`
- `apps/api/src/models/recipe.py`
- `apps/api/src/models/recipe_ingredient.py`
- `apps/api/src/models/menu_item_recipe.py`
- `apps/api/src/models/ingredient_substitution.py`
- `apps/api/src/services/recipe_matching.py`
- `apps/api/src/services/cogs_calculator.py`
- `apps/api/src/services/recipe_explosion.py`
- `apps/api/src/routers/recipes.py`
- `apps/api/src/routers/ingredients.py`
- `apps/web/src/components/RecipeSwipeCard.tsx`
- `apps/web/src/components/CustomRecipeForm.tsx`
- `apps/web/src/components/MenuProfitabilityTable.tsx`
- `apps/web/src/components/IngredientCostTable.tsx`
- `data/seeds/standard_recipes.json` (10K recipes)
- `data/seeds/ingredients.json` (2K ingredients)

### Change Log
- 2025-12-23: Epic created with recipe explosion requirements for procurement
