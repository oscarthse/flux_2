# Flux Algorithm Architecture Proposal

This document defines the core algorithms powering Flux, how they interact, their mathematical foundations, and data requirements.

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        DATA LAYER                                    │
│  Transactions │ Recipes │ Inventory │ Staff │ Costs │ Weather      │
└───────────────────────────┬─────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│   DEMAND      │   │  INVENTORY    │   │   LABOR       │
│  FORECASTING  │──▶│  OPTIMIZATION │   │  SCHEDULING   │
│               │   │               │   │               │
│  Prophet +    │   │  MIP for      │   │  MIP with     │
│  Bayesian     │   │  Promotions   │   │  Constraints  │
└───────┬───────┘   └───────┬───────┘   └───────────────┘
        │                   │
        └─────────┬─────────┘
                  ▼
        ┌───────────────────┐
        │   PROFITABILITY   │
        │     ANALYSIS      │
        └───────────────────┘
```

---

## 1. Demand Forecasting

### Objective
Predict daily/weekly sales volume for each menu item to drive procurement, staffing, and promotions.

### Algorithm: Hierarchical Bayesian Time Series

**Why not just Prophet/ARIMA?**
- Limited data problem: New restaurants have weeks, not years
- Need to share information across similar items and restaurants
- Must quantify uncertainty, not just point estimates

### Mathematical Framework

**Hierarchical structure:**
```
Sales_item,day ~ Poisson(λ_item,day)

log(λ_item,day) = μ_item + β_dow[day] + β_season[week] + β_weather * weather + ε_day
```

Where:
- `μ_item` = baseline popularity (learned per item, with prior from category average)
- `β_dow` = day-of-week effect (shared across items)
- `β_season` = weekly seasonality
- `β_weather` = weather coefficient
- `ε_day` = residual noise

**Handling limited data:**
- Use informative priors from similar restaurants/categories
- Hierarchical pooling: new items borrow strength from category
- Bayesian updating: uncertainty shrinks as data accumulates

### Implementation
```python
# PyMC or NumPyro for Bayesian inference
# Fallback: Prophet with custom seasonality + ensemble
```

### Outputs
| Output | Use |
|--------|-----|
| Point forecast (mean) | Procurement planning |
| Prediction interval (95%) | Safety stock calculation |
| Trend direction | Menu optimization |
| Weather sensitivity | Day-of decisions |

### Data Required
- `transactions`: item_id, quantity, date, time
- `weather`: temp, precipitation, day
- `events`: local events calendar (optional)
- `menu_items`: category, price, active dates

---

## 2. Dynamic Promotions Engine

### Objective
Maximize profit by intelligently discounting items based on inventory position, predicted demand, margins, and price elasticity.

### Algorithm: Constrained Optimization (MIP + Heuristics)

### Mathematical Framework

**Decision variable:**
```
d_i = discount percentage for item i ∈ [0, max_discount_i]
```

**Objective function (maximize expected profit):**
```
max Σ_i [ (p_i - c_i - d_i * p_i) * q_i(d_i) - W_i * waste_i(d_i) ]
```

Where:
- `p_i` = price of item i
- `c_i` = cost of item i
- `q_i(d_i)` = predicted quantity sold given discount (demand response)
- `W_i` = waste cost if item expires
- `waste_i(d_i)` = expected waste quantity

**Demand response model (price elasticity):**
```
q_i(d) = q_i(0) * (1 + ε_i * d)
```

Where `ε_i` is price elasticity (% demand increase per % price decrease).

**Constraints:**
- `d_i ≤ max_discount` (brand protection)
- `Σ promotions ≤ budget` (limit simultaneous promos)
- `margin_i(d_i) ≥ min_margin` (maintain profitability floor)

### Elasticity Estimation

**Challenge:** No A/B testing data initially.

**Solution:** Bayesian estimation with category priors
```
ε_item ~ Normal(ε_category, σ²)

# Restaurant items typically: ε ∈ [1.5, 3.0]
# Commodity items (drinks): ε ≈ 2.5
# Signature dishes: ε ≈ 1.2 (less elastic)
```

Update elasticity estimates as promotions run and we observe response.

### Inventory Urgency Score

```
urgency_i = (current_stock_i - safety_stock_i) / days_to_expiry_i

# High urgency = overstocked + expiring soon
# Feeds into promotion priority ranking
```

### Outputs
| Output | Use |
|--------|-----|
| Recommended discount % per item | Pricing decisions |
| Expected profit impact | ROI justification |
| Urgency ranking | Prioritization |
| Confidence level | Human override triggers |

### Data Required
- `inventory`: item_id, quantity, expiry_date, cost
- `menu_items`: price, category, min_margin
- `historical_promotions`: discount, sales_lift (for elasticity learning)
- `demand_forecast`: from Algorithm 1

---

## 3. Labor Scheduling Optimization

### Objective
Minimize labor cost while meeting predicted demand and honoring all constraints.

### Algorithm: Mixed Integer Programming (MIP)

### Mathematical Framework

**Decision variables:**
```
x_e,s ∈ {0, 1}  = 1 if employee e works shift s
```

**Objective (minimize cost):**
```
min Σ_e Σ_s (wage_e * hours_s * x_e,s) + penalty_understaffing + penalty_preferences
```

**Hard constraints:**

1. **Demand coverage:** For each time slot t:
```
Σ_e (x_e,s * covers(s,t)) ≥ demand_t
```

2. **Availability:** Employee can only work if available:
```
x_e,s ≤ available_e,s    ∀ e, s
```

3. **Max hours per week:**
```
Σ_s (hours_s * x_e,s) ≤ max_hours_e    ∀ e
```

4. **Min hours (guaranteed):**
```
Σ_s (hours_s * x_e,s) ≥ min_hours_e    ∀ e
```

5. **Rest between shifts:**
```
x_e,s1 + x_e,s2 ≤ 1    if gap(s1, s2) < min_rest
```

6. **Skills requirement:** For specialized shifts:
```
x_e,s ≤ has_skill_e,r    if shift s requires skill r
```

**Soft constraints (penalties in objective):**
- Employee preferences (prefer morning vs evening)
- Fairness (distribute weekend shifts evenly)
- Stability (minimize week-to-week variance)

### Demand Curve Generation

From forecast, generate staffing requirements:
```
staff_needed_t = ceiling(predicted_covers_t / covers_per_staff) + buffer
```

Where buffer accounts for forecast uncertainty (higher uncertainty = more buffer).

### Implementation
```python
# Google OR-Tools CP-SAT solver
# Solve time: <30 seconds for typical restaurant (20 employees, 1 week)
```

### Outputs
| Output | Use |
|--------|-----|
| Optimal schedule (assignments) | Staff communication |
| Cost breakdown | Budget tracking |
| Constraint violations | Manual override needed |
| What-if analysis | Planning scenarios |

### Data Required
- `employees`: id, wage, skills, max_hours, min_hours
- `availability`: employee_id, date, available_hours
- `shifts`: id, start_time, end_time, required_skills
- `demand_forecast`: from Algorithm 1 → converted to staffing needs

---

## 4. Profitability Analysis

### Objective
Calculate true profitability per menu item including COGS, labor, and overhead.

### Framework: Activity-Based Costing

### Calculations

**1. Direct costs (COGS):**
```
COGS_item = Σ_i (ingredient_i_qty * ingredient_i_cost)
```
Requires recipe explosion (ingredients per dish).

**2. Labor cost per item:**
```
labor_cost_item = prep_time_item * labor_rate + service_time_item * labor_rate
```

Estimate prep_time from:
- Recipe complexity (number of steps)
- Category defaults (appetizer < entree < dessert)

**3. Overhead allocation:**
```
overhead_item = (sales_volume_item / total_sales_volume) * total_overhead
```

Or activity-based: allocate based on:
- Kitchen time used
- Plating complexity
- Ticket frequency

**4. Contribution margin:**
```
contribution_margin_item = price_item - COGS_item
margin_% = contribution_margin / price * 100
```

**5. True profitability:**
```
profit_item = price - COGS - labor_cost - overhead_allocation
```

### Comparative Analytics
- **Menu matrix:** Plot items by popularity (volume) vs profitability (margin)
  - Stars: High volume, high margin (promote)
  - Puzzles: Low volume, high margin (market more)
  - Plow horses: High volume, low margin (re-engineer)
  - Dogs: Low volume, low margin (remove or fix)

### Data Required
- `recipes`: menu_item_id, ingredient_id, quantity
- `ingredients`: id, unit_cost, supplier
- `menu_items`: price, category
- `transactions`: item sales volume
- `labor_estimates`: prep_time, complexity (or derived from recipe)

---

## Algorithm Interactions

### Flow Diagram

```
            ┌─────────────────────────────────────┐
            │         DAILY OPERATIONS            │
            └─────────────────────────────────────┘
                              │
    ┌─────────────────────────┼─────────────────────────┐
    ▼                         ▼                         ▼
┌────────┐              ┌──────────┐              ┌─────────┐
│Forecast│──────────────│Inventory │              │ Labor   │
│ Model  │   demand     │ Status   │              │Schedule │
└───┬────┘              └────┬─────┘              └────┬────┘
    │                        │                         │
    │ predicted              │ stock +                 │ labor
    │ sales                  │ expiry                  │ cost
    │                        │                         │
    └────────────┬───────────┘                         │
                 ▼                                     │
         ┌──────────────┐                              │
         │  PROMOTIONS  │◀─────────────────────────────┘
         │   ENGINE     │      staff available?
         └──────┬───────┘
                │
                ▼ recommended promotions
         ┌──────────────┐
         │PROFITABILITY │
         │  ANALYSIS    │
         └──────────────┘
                │
                ▼
         ┌──────────────┐
         │   INSIGHTS   │
         │  DASHBOARD   │
         └──────────────┘
```

### Integration Points

| From | To | Data Passed |
|------|----|----|
| Demand Forecast | Promotions | Expected demand, uncertainty |
| Demand Forecast | Labor Scheduling | Customer covers by hour |
| Inventory | Promotions | Stock levels, expiry dates |
| Labor Schedule | Promotions | Can we handle promotion surge? |
| All | Profitability | Costs and revenues |

---

## Cold Start / Limited Data Strategy

| Scenario | Strategy |
|----------|----------|
| New restaurant (0 data) | Use category/cuisine priors from similar restaurants |
| New menu item | Inherit forecast from similar items in category |
| No elasticity data | Use conservative category defaults (ε = 1.5) |
| Sparse transactions | Bayesian pooling, wider uncertainty intervals |
| No recipe data | Estimate COGS from category averages, prompt user |

**Progressive enhancement:** As data accumulates, models automatically become more confident and personalized.

---

## Data Requirements Summary

### Core Tables

| Table | Key Fields | Source |
|-------|------------|--------|
| `transactions` | item_id, qty, date, time, price | POS / CSV |
| `menu_items` | id, name, price, category | User input |
| `ingredients` | id, name, unit, unit_cost | User input |
| `recipes` | menu_item_id, ingredient_id, qty | User input |
| `inventory` | ingredient_id, qty, expiry_date | User input or integration |
| `employees` | id, name, wage, skills, max_hours | User input |
| `availability` | employee_id, date, hours | User input |
| `shifts` | id, start, end, required_skills | User config |
| `weather` | date, temp, precip | External API |
| `forecasts` | item_id, date, predicted_qty, interval | Generated |
| `promotions` | item_id, discount, start, end, observed_lift | Generated + observed |

---

## Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| Demand Forecasting | Prophet + PyMC | Bayesian, handles seasonality, quantifies uncertainty |
| Promotions | PuLP or OR-Tools | MIP solver, handles constraints |
| Labor Scheduling | OR-Tools CP-SAT | Best-in-class MIP, Google-supported |
| Profitability | Pure Python/SQL | Calculation, not optimization |
| ML Pipeline | SageMaker or local | Training and inference |

---

## Critical Risk Mitigations

Based on production experience and research-level concerns:

### 1. Overdispersion in Demand (Poisson Will Break)

**Problem:** Real restaurant sales have group orders, events, promotions causing overdispersion.

**Solution:** Negative Binomial or Poisson with day-level random effects:
```
Sales ~ NegBinom(μ, α)  where α captures overdispersion

# Alternative: hierarchical random effect
log(λ_day) = μ + β*X + ε_day   where ε_day ~ Normal(0, σ²_day)
```

**Impact if ignored:** Falsely narrow uncertainty bands → wrong safety stock and labor buffers.

---

### 2. Weather as Noise, Not Driver

**Problem:** Weather effects are nonlinear, cuisine-dependent, prone to sign flips and Simpson's paradox.

**Solution:**
- Start with weather as **optional additive noise** (small prior variance)
- Allow model to learn restaurant-specific weather sensitivity
- Cap weather effect magnitude: `|β_weather| ≤ 0.2`
- Only promote to "strong driver" after 90+ days of data with clear signal

---

### 3. Elasticity: Nonlinearity and Endogeneity

**Problem 1: Nonlinear elasticity**
- Discounts saturate
- Can backfire (cheap = low quality)
- Linear model will hallucinate free profit

**Solution:**
```
q(d) = q(0) * (1 + ε * d * (1 - saturation_rate * d))

# Caps:
lift_max = 1.5  # Can't more than 2.5x baseline
lift_min = 0.8  # Allow negative lift (promo hurts brand)
```

**Problem 2: Endogeneity** (Critical)
- Promotions chosen because of low demand/expiry
- Observed elasticity biased downward
- Bayesian updates converge to wrong values

**Solution:**
- **Exploration budget:** 5% of promotions are random micro-discounts (3-5%)
- Track "promoted" vs "organic" sales separately
- Require minimum 3 exploration observations before trusting elasticity
- Flag elasticity estimates with low confidence visibly in UI

---

### 4. Cross-Elasticity (Cannibalization)

**Problem:** Discounting Ribeye may steal sales from higher-margin Filet Mignon.

**Solution:**
- Track category-level demand shifts during promotions
- Add cannibalization penalty to objective:
```
max Σ [(margin_i * q_i(d_i)) - λ_cannibal * Σ_j∈substitutes (lost_margin_j)]
```
- Start with category-level heuristic: assume 20% cannibalization within category
- Learn cross-elasticity matrix over time

---

### 5. Manager-in-the-Loop (Scheduling)

**Problem:** Algorithms fail on human factors (staff conflicts, undocumented preferences).

**Solution:**
- **Manual overrides table:** Store all manager changes with reason
- **MIP respects overrides:** Hard constraints from previous edits
- **"Why was I scheduled?" UI:** Show factors contributing to each assignment
- **Conflict flags:** Allow marking employee pairs that shouldn't work together
- **Fairness dashboard:** Visualize weekend/holiday distribution per employee

---

### 6. Recipe Data Entry (AI Assistant)

**Problem:** Chefs don't maintain gram-perfect digital recipes.

**Solution:**
- **Photo upload:** Parse handwritten prep sheets via OCR + LLM
- **PDF parsing:** Extract from supplier invoices, menu docs
- **Smart defaults:** Estimate ingredient quantities from category + dish name
- **Validation prompts:** "This pasta dish has no carbs listed. Add pasta?"
- **Flag low-confidence recipes:** Don't include in profitability without confirmation

---

### 7. Prep Time Estimation

**Problem:** Category-based prep time is noisy; batching/multitasking ignored.

**Solution:**
- Communicate as **directional**, not absolute
- Show confidence bands on labor cost estimates
- Allow override per dish
- Learn from actual ticket times (if POS provides)

---

### 8. Feedback Loop Control

**Key questions:**
- How fast do priors decay?
- When do restaurant-specific beats global?
- How to prevent overfitting early wins?

**Solution:**
```
# Bayesian weighting schedule
prior_weight = max(0.2, 1 - (days_of_data / 90))

# After 90 days: 80% restaurant-specific, 20% prior
# Before 30 days: heavy prior weight
```

- Track prediction accuracy weekly
- Alert if accuracy drops significantly (model drift)
- Require re-validation before major model updates

---

### 9. Global Objective Alignment

**Problem:** Sub-objectives conflict:
- Forecasting optimizes accuracy
- Promotions optimize profit
- Labor optimizes cost

**Solution:**
- Define global objective: **Maximize long-term gross profit subject to operational stability**
- Add guardrails:
  - Promotion profit must exceed cannibalization cost
  - Scheduling cost savings cannot increase turnover
  - Forecast errors penalized by downstream impact (not just RMSE)
- Quarterly "system health" review comparing all metrics

---

## Next Steps

1. **Design complete database schema** supporting all algorithms
2. **Implement demand forecasting** (start simple with Prophet, add Bayesian later)
3. **Build profitability calculator** (needs recipe data first)
4. **Implement labor scheduling MIP** (most constrained, clear wins)
5. **Build promotions engine** (requires all others as inputs)
