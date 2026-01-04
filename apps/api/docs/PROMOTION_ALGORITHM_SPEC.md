# Promotion Detection & Price Elasticity Algorithm Specification

## 1. Mathematical Foundation

### 1.1 Price Elasticity of Demand

Price elasticity measures the sensitivity of demand to price changes:

```
ε = (ΔQ/Q) / (ΔP/P) = (∂Q/∂P) × (P/Q)
```

Where:
- `ε` = Price elasticity (negative for normal goods)
- `Q` = Quantity demanded
- `P` = Price
- `ΔQ` = Change in quantity
- `ΔP` = Change in price

**Economic Interpretation:**
- |ε| > 1: Elastic (demand very sensitive to price)
- |ε| = 1: Unit elastic
- |ε| < 1: Inelastic (demand not very sensitive to price)
- |ε| = 0: Perfectly inelastic (demand unchanging)

### 1.2 Log-Linear Demand Model

We use a log-linear specification for computational stability:

```
log(Q_t) = β₀ + β₁×log(P_t) + β₂×DOW_t + β₃×Promo_t + ε_t
```

Where:
- `β₁` = constant elasticity (what we want to estimate)
- `β₂` = day-of-week seasonal effects (vector)
- `β₃` = promotion indicator coefficient
- `ε_t` = error term (zero-mean)

**Why log-linear?**
1. Elasticity is constant across price ranges
2. Handles heteroskedasticity better
3. More stable parameter estimates
4. Aligns with economic theory

### 1.3 Identification Strategy

**Problem:** Promotions are endogenous - restaurants run promotions when demand is already low.

**Solution:** Two-stage approach
1. **Exploration promotions** (5% random): Unbiased elasticity estimation
2. **Instrumental variables**: Use lagged prices as instruments for current prices

```
First stage:  P_t = γ₀ + γ₁×P_{t-7} + γ₂×P_{t-28} + controls + u_t
Second stage: log(Q_t) = β₀ + β₁×log(P̂_t) + controls + ε_t
```

## 2. Promotion Detection Algorithm

### 2.1 Direct Detection from CSV

**Input:** Transaction items with prices
**Output:** Promotion flags and discount amounts

```python
def detect_discount_from_csv(row):
    """Detect if transaction item was discounted."""

    # Method 1: Explicit discount column
    if row.discount_amount is not None and row.discount_amount > 0:
        return {
            'is_promo': True,
            'discount_amount': row.discount_amount,
            'discount_type': 'explicit',
            'confidence': 1.0
        }

    # Method 2: Negative price items (comps, voids)
    if row.unit_price < 0 or row.total < 0:
        return {
            'is_promo': True,
            'discount_amount': abs(row.total),
            'discount_type': 'comp_void',
            'confidence': 1.0
        }

    # Method 3: Item name contains discount keywords
    discount_keywords = [
        'discount', 'promo', 'comp', 'void', 'off',
        'coupon', 'special', 'deal', 'happy hour'
    ]
    if any(kw in row.item_name.lower() for kw in discount_keywords):
        return {
            'is_promo': True,
            'discount_amount': None,  # Unknown amount
            'discount_type': 'inferred_keyword',
            'confidence': 0.7
        }

    return {'is_promo': False}
```

### 2.2 Statistical Promotion Inference

**When:** After data ingestion, for items without explicit discount flags

**Algorithm:** Price variance analysis with Bayesian change-point detection

```python
def infer_promotions_from_price_history(item_sales_history):
    """
    Detect implicit promotions using price variance.

    Uses Bayesian change-point detection to find periods where
    prices deviate significantly from baseline.
    """

    # Step 1: Establish baseline price
    baseline_price = calculate_robust_baseline(item_sales_history)
    baseline_std = calculate_price_std(item_sales_history)

    # Step 2: Define discount threshold
    # A sale is flagged if price < baseline - k*std, where k=2 (2-sigma rule)
    discount_threshold = baseline_price - 2 * baseline_std

    # Step 3: Bayesian change-point detection
    change_points = detect_change_points(
        prices=item_sales_history.prices,
        prior_precision=1.0,  # Informative prior
        min_duration=3  # Minimum 3 days to be considered promotion
    )

    # Step 4: Flag promotion periods
    promotions = []
    for cp_start, cp_end in change_points:
        segment_mean = mean(prices[cp_start:cp_end])

        if segment_mean < discount_threshold:
            discount_pct = (baseline_price - segment_mean) / baseline_price

            promotions.append({
                'start_date': dates[cp_start],
                'end_date': dates[cp_end],
                'discount_pct': discount_pct,
                'confidence': calculate_posterior_probability(cp_start, cp_end),
                'method': 'bayesian_changepoint'
            })

    return promotions
```

### 2.3 Robust Baseline Price Calculation

```python
def calculate_robust_baseline(sales_history, lookback_days=90):
    """
    Calculate robust baseline price resistant to outliers.

    Uses Huber M-estimator for robustness.
    """
    recent_prices = sales_history.last_n_days(lookback_days).prices

    # Remove promotion periods first
    non_promo_prices = [p for p, promo in zip(recent_prices, is_promo)
                        if not promo]

    if len(non_promo_prices) < 10:
        # Fallback to median if insufficient data
        return median(recent_prices)

    # Huber M-estimator: robust mean
    baseline = huber_mean(
        non_promo_prices,
        k=1.345  # Standard Huber constant (95% efficiency vs OLS)
    )

    return baseline
```

## 3. Price Elasticity Estimation

### 3.1 Two-Stage Least Squares (2SLS) Estimator

```python
def estimate_price_elasticity_2sls(item_id, restaurant_id, db):
    """
    Estimate price elasticity using 2SLS with lagged prices as instruments.

    Returns:
        elasticity: Point estimate
        std_error: Standard error
        confidence_interval: 95% CI
        sample_size: Number of observations
        r_squared: Model fit
    """

    # Get historical data
    data = get_item_sales_and_prices(
        item_id=item_id,
        restaurant_id=restaurant_id,
        min_days=60  # Need minimum 60 days for reliable estimation
    )

    if len(data) < 60:
        return None  # Insufficient data

    # Prepare variables
    log_quantity = np.log(data.quantity + 1)  # +1 to handle zeros
    log_price = np.log(data.price)
    log_price_lag7 = np.log(data.price.shift(7))
    log_price_lag28 = np.log(data.price.shift(28))

    # Control variables
    dow_dummies = pd.get_dummies(data.day_of_week, prefix='dow')
    month_dummies = pd.get_dummies(data.month, prefix='month')
    is_promotion = data.is_promotion.astype(int)
    hours_open = data.hours_open

    # Construct design matrices
    X_exog = pd.concat([dow_dummies, month_dummies, is_promotion, hours_open], axis=1)
    X_endog = log_price  # Endogenous regressor
    Z_instruments = pd.concat([log_price_lag7, log_price_lag28], axis=1)

    # First stage: Regress price on instruments
    first_stage = sm.OLS(
        X_endog,
        sm.add_constant(pd.concat([Z_instruments, X_exog], axis=1))
    ).fit()

    # Get fitted values
    price_hat = first_stage.fittedvalues

    # Second stage: Regress quantity on fitted price
    second_stage = sm.OLS(
        log_quantity,
        sm.add_constant(pd.concat([price_hat, X_exog], axis=1))
    ).fit(cov_type='HC3')  # Robust standard errors

    # Extract elasticity (coefficient on log_price)
    elasticity = second_stage.params['log_price']
    std_error = second_stage.bse['log_price']

    # Calculate confidence interval
    ci_lower = elasticity - 1.96 * std_error
    ci_upper = elasticity + 1.96 * std_error

    # First-stage F-statistic (instrument strength)
    f_stat = calculate_first_stage_f_stat(first_stage, instrument_cols=['log_price_lag7', 'log_price_lag28'])

    # Weak instruments test (rule of thumb: F > 10)
    is_weak_instrument = f_stat < 10

    return {
        'elasticity': float(elasticity),
        'std_error': float(std_error),
        'ci_lower': float(ci_lower),
        'ci_upper': float(ci_upper),
        'sample_size': len(data),
        'r_squared': float(second_stage.rsquared),
        'f_stat': float(f_stat),
        'is_weak_instrument': is_weak_instrument,
        'method': '2SLS'
    }
```

### 3.2 Bayesian Hierarchical Model (Advanced)

For restaurants with multiple items, use hierarchical prior:

```
elasticity_i ~ Normal(μ_category, σ²_category)
μ_category ~ Normal(-1.5, 0.5²)  # Prior: moderately elastic
σ²_category ~ InverseGamma(3, 2)
```

**Benefits:**
1. Partial pooling: Share information across items
2. Better estimates for items with sparse data
3. Category-level priors improve small-sample estimates

## 4. Promotion Impact Quantification

### 4.1 Lift Calculation

```python
def calculate_promotion_lift(promotion_id, db):
    """
    Calculate actual demand lift from promotion.

    Uses difference-in-differences estimator with synthetic control.
    """
    promo = db.query(Promotion).get(promotion_id)

    # Get treatment period sales
    treatment_sales = get_sales_during_period(
        item_id=promo.menu_item_id,
        start_date=promo.start_date,
        end_date=promo.end_date
    )

    # Get counterfactual: what would sales have been without promo?
    # Method 1: Synthetic control (preferred)
    counterfactual = estimate_synthetic_control(
        item_id=promo.menu_item_id,
        treatment_start=promo.start_date,
        treatment_end=promo.end_date,
        donor_pool='same_category_items'
    )

    # Method 2: Regression-based counterfactual (fallback)
    if counterfactual is None:
        counterfactual = estimate_regression_counterfactual(
            item_id=promo.menu_item_id,
            treatment_period=(promo.start_date, promo.end_date),
            controls=['dow', 'month', 'hours_open']
        )

    # Calculate lift
    actual_qty = treatment_sales.quantity.sum()
    counterfactual_qty = counterfactual.sum()

    lift_pct = (actual_qty - counterfactual_qty) / counterfactual_qty

    # Statistical significance test
    se = calculate_lift_standard_error(treatment_sales, counterfactual)
    p_value = calculate_p_value(lift_pct, se)

    return {
        'lift_pct': float(lift_pct),
        'std_error': float(se),
        'p_value': float(p_value),
        'is_significant': p_value < 0.05,
        'actual_quantity': int(actual_qty),
        'counterfactual_quantity': int(counterfactual_qty),
        'incremental_units': int(actual_qty - counterfactual_qty)
    }
```

### 4.2 Revenue Impact

```python
def calculate_revenue_impact(promotion_id, db):
    """
    Calculate net revenue impact accounting for:
    1. Volume lift
    2. Price discount
    3. Margin erosion
    """
    promo = db.query(Promotion).get(promotion_id)
    lift_data = calculate_promotion_lift(promotion_id, db)

    # Get item cost and baseline price
    item = db.query(MenuItem).get(promo.menu_item_id)
    baseline_price = item.price

    # Calculate discounted price
    if promo.discount_type == 'percentage':
        promo_price = baseline_price * (1 - promo.discount_value / 100)
    else:
        promo_price = baseline_price - promo.discount_value

    # Revenue calculation
    baseline_revenue = lift_data['counterfactual_quantity'] * baseline_price
    promo_revenue = lift_data['actual_quantity'] * promo_price

    # Profit calculation (if cost data available)
    if item.cost_per_unit:
        baseline_profit = lift_data['counterfactual_quantity'] * (baseline_price - item.cost_per_unit)
        promo_profit = lift_data['actual_quantity'] * (promo_price - item.cost_per_unit)

        profit_impact = promo_profit - baseline_profit
    else:
        profit_impact = None

    return {
        'revenue_impact': float(promo_revenue - baseline_revenue),
        'profit_impact': float(profit_impact) if profit_impact else None,
        'baseline_revenue': float(baseline_revenue),
        'promotion_revenue': float(promo_revenue),
        'margin_erosion_pct': float((baseline_price - promo_price) / baseline_price)
    }
```

## 5. Integration with Demand Forecasting

### 5.1 Promotion-Adjusted Forecasts

When generating forecasts during promotion periods:

```python
def forecast_with_promotion(item_id, promo_discount_pct, forecast_horizon=7):
    """
    Generate demand forecast accounting for promotion effect.
    """
    # Get baseline forecast (without promotion)
    baseline_forecast = generate_baseline_forecast(item_id, forecast_horizon)

    # Get item's price elasticity
    elasticity_data = get_price_elasticity(item_id)

    if elasticity_data is None:
        # Use category average if item-level not available
        elasticity = get_category_elasticity(item_id)
    else:
        elasticity = elasticity_data['elasticity']

    # Calculate expected lift from elasticity
    # ε = (ΔQ/Q) / (ΔP/P)
    # Therefore: ΔQ/Q = ε × (ΔP/P)
    price_change_pct = -promo_discount_pct / 100  # Negative because price decreases
    expected_lift_pct = elasticity * price_change_pct

    # Adjust baseline forecast
    promo_forecast = baseline_forecast * (1 + expected_lift_pct)

    # Widen uncertainty bands during promotion (higher variance)
    promo_forecast['p10'] = baseline_forecast['p10'] * (1 + expected_lift_pct * 0.7)
    promo_forecast['p50'] = baseline_forecast['p50'] * (1 + expected_lift_pct)
    promo_forecast['p90'] = baseline_forecast['p90'] * (1 + expected_lift_pct * 1.3)

    return promo_forecast
```

## 6. Data Quality Requirements

### 6.1 Minimum Data Requirements

For reliable elasticity estimation:
- **Minimum observations:** 60 days with sales
- **Price variation:** At least 3 distinct price points
- **Minimum promotions:** 5 exploration promotions for unbiased estimates
- **Control group:** Items in same category without concurrent promotions

### 6.2 Confidence Scoring

```python
def calculate_elasticity_confidence(estimation_results):
    """
    Score confidence in elasticity estimate (0-1 scale).
    """
    score = 1.0

    # Penalty 1: Small sample size
    if estimation_results['sample_size'] < 90:
        score *= 0.7
    elif estimation_results['sample_size'] < 60:
        score *= 0.4

    # Penalty 2: Weak instruments
    if estimation_results['is_weak_instrument']:
        score *= 0.5

    # Penalty 3: Wide confidence interval
    ci_width = estimation_results['ci_upper'] - estimation_results['ci_lower']
    if ci_width > 2.0:
        score *= 0.6

    # Penalty 4: Low R-squared
    if estimation_results['r_squared'] < 0.3:
        score *= 0.7

    # Penalty 5: Implausible elasticity
    elasticity = estimation_results['elasticity']
    if elasticity > 0:  # Wrong sign (should be negative)
        score *= 0.2
    elif abs(elasticity) > 5:  # Too elastic (unrealistic)
        score *= 0.5
    elif abs(elasticity) < 0.1:  # Too inelastic (suspicious)
        score *= 0.6

    return max(0.0, min(1.0, score))
```

## 7. Implementation Priorities

### Phase 1: Foundation (Day 2)
1. ✅ CSV discount detection
2. ✅ Promotion inference from price variance
3. ✅ Basic promotion tracking

### Phase 2: Elasticity (Week 2)
1. 2SLS elasticity estimation
2. Exploration promotion system
3. Confidence scoring

### Phase 3: Advanced (Week 3)
1. Bayesian hierarchical models
2. Synthetic control for lift calculation
3. Real-time promotion optimization

## 8. Expected Performance

### Elasticity Estimation Accuracy
- With 60 days data: SE ≈ 0.3-0.5
- With 90 days + 5 explorations: SE ≈ 0.2-0.3
- With hierarchical prior: 15-20% improvement in RMSE

### Promotion Detection
- Direct detection: 100% precision (explicit flags)
- Keyword inference: ~85% precision, ~70% recall
- Statistical inference: ~75% precision, ~60% recall

### Revenue Impact
- Expected lift prediction error: ±15-20% with good elasticity estimates
- Improves to ±10-15% after 3+ promotions on same item
