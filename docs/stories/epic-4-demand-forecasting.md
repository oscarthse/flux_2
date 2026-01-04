# Epic 4: Demand Forecasting Engine

**Status:** Not Started
**Epic Goal**: Implement production-grade ML-powered demand forecasting that predicts weekly sales per menu item with calibrated uncertainty, achieving WAPE ≤25% with 30 days of data and ≤18% with 60 days. This epic delivers the **core value proposition** of Flux: AI-driven demand prediction that enables waste reduction, optimal procurement, and labor scheduling.

**CRITICAL**: This epic implements recommendations from [model_learning_speed_review.md](../model_learning_speed_review.md), prioritizing **sample efficiency** (learn faster with less data) over raw accuracy. Every design choice must optimize for **cold-start performance** since most restaurants have 2-8 weeks of data.

---

## ML Design Principles (Mandatory Reading)

Per [model_learning_speed_review.md:L19-L26](../model_learning_speed_review.md#L19-L26):

> **Highest-Impact Recommendations:**
> - P0: Implement hierarchical Bayesian models with empirical Bayes priors from day one
> - P0: Use Negative Binomial likelihood (not Poisson) for demand
> - P1: Add explicit censoring/stockout modeling to avoid learning from truncated data
> - P1: Implement exploration budget for elasticity learning

**Expected Improvement**: With recommended approach, models should reach target accuracy in **3-4 weeks** instead of **10-12 weeks**.

---

## User Stories

### Story 4.1: ML Pipeline Infrastructure & Training Orchestration

**As a backend developer,**
**I want a scalable ML pipeline for training, validating, and deploying demand forecasting models,**
**so that models automatically retrain as new data arrives and predictions stay accurate.**

#### Architecture Overview

Per [09-backend-architecture.md](../architecture/09-backend-architecture.md), ML pipeline **must be separate from request path**:

```
┌─────────────────────────────────────────────────────────┐
│                    ML TRAINING PIPELINE                  │
│              (Runs async, separate from API)             │
└─────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        ▼                   ▼                   ▼
┌───────────────┐   ┌───────────────┐   ┌───────────────┐
│  DATA PREP    │   │   TRAINING    │   │  VALIDATION   │
│  Lambda/Glue  │──▶│  SageMaker    │──▶│  Backtesting  │
│               │   │  (Prophet +   │   │               │
│ • Feature eng │   │   Bayesian)   │   │ • WAPE        │
│ • Train/test  │   │               │   │ • Coverage    │
│   split       │   │ • Fit model   │   │ • CRPS        │
│ • Prior calc  │   │ • Serialize   │   │               │
└───────────────┘   └───────────────┘   └───────┬───────┘
                                                 │
                                                 ▼
                                        ┌───────────────┐
                                        │  DEPLOYMENT   │
                                        │               │
                                        │ • Upload to S3│
                                        │ • Update      │
                                        │   registry    │
                                        │ • Invalidate  │
                                        │   cache       │
                                        └───────────────┘
```

**Triggering Schedule:**
- **Daily training**: 2am UTC (after transaction data ingestion)
- **On-demand**: When user uploads historical data (CSV)
- **Change detection**: If CUSUM detects model drift

**Technology Stack:**
- **Orchestration**: AWS Step Functions (state machine)
- **Training**: AWS SageMaker (Python 3.12, custom container)
- **Feature Engineering**: AWS Glue ETL or Lambda
- **Model Storage**: S3 + SageMaker Model Registry (versioning)
- **Monitoring**: CloudWatch metrics + custom dashboard

#### Dev Notes
- Use SageMaker Spot Instances for cost savings (50-70% cheaper)
- Model artifacts stored as pickle files (or joblib) in S3
- Inference uses Lambda (loads model from S3, caches in /tmp)
- Track model lineage: data version, hyperparameters, accuracy metrics

#### Acceptance Criteria
1. Step Functions state machine orchestrates: prep → train → validate → deploy
2. Training job triggered daily at 2am UTC
3. On-demand trigger via `POST /api/ml/retrain` endpoint
4. Feature engineering extracts:
   - Day-of-week (Monday=0, Sunday=6)
   - Week-of-year (1-52)
   - Days since item first seen
   - Stockout flag (from Epic 2)
   - Promotion flag (from Epic 2)
   - Weather features (temp, precip) if available
5. Train/test split: last 7 days held out for validation
6. Model artifacts versioned and stored in S3
7. Validation metrics logged to CloudWatch (WAPE, Coverage, CRPS)
8. Deployment conditional: only deploy if WAPE < current production model
9. Rollback capability: revert to previous model version if accuracy degrades

#### Tasks
- [ ] Create Step Functions state machine definition (JSON/YAML)
- [ ] Create SageMaker training script: `train.py` (entry point)
- [ ] Implement feature engineering Lambda: `prepare_features.py`
  - Query transactions from RDS
  - Extract temporal features (DOW, week, days_since_first_seen)
  - Merge stockout flags, promotion flags, weather
  - Split train/validation (80/20 or rolling-origin)
  - Save to S3 as Parquet
- [ ] Create SageMaker Docker container with dependencies:
  - Prophet (Meta's forecasting library)
  - PyMC or NumPyro (Bayesian inference)
  - scikit-learn, pandas, numpy
- [ ] Implement validation script: `validate.py`
  - Load model, test data
  - Generate predictions
  - Calculate WAPE, Coverage, CRPS
  - Return metrics as JSON
- [ ] Create deployment script: `deploy.py`
  - Upload model to S3 versioned bucket
  - Register in SageMaker Model Registry
  - Invalidate Lambda cache (trigger redeployment)
- [ ] Set up EventBridge cron trigger (daily 2am UTC)
- [ ] Create `POST /api/ml/retrain` endpoint (triggers Step Functions)
- [ ] Add CloudWatch dashboard for ML metrics
- [ ] Write integration test: trigger training, verify model deployed

---

### Story 4.2: Hierarchical Bayesian Model Implementation (P0)

**As an ML engineer,**
**I want to implement a hierarchical Bayesian forecasting model with empirical priors,**
**so that new restaurants and menu items achieve accurate forecasts with minimal data.**

#### Mathematical Specification

Per [model_learning_speed_review.md:L449-L493](../model_learning_speed_review.md#L449-L493), implement **three-level hierarchy**:

```python
# GLOBAL LEVEL (all restaurants in Flux system)
μ_global ~ Normal(0, σ_global²)

# CATEGORY LEVEL (e.g., "Entrees > Beef")
μ_category ~ Normal(μ_global, τ_category²)

# ITEM LEVEL (specific menu item at specific restaurant)
μ_item ~ Normal(μ_category, τ_item²)
```

**Shrinkage Mechanism (James-Stein):**
```python
μ̂_item = (1 - B_item) * ȳ_item + B_item * μ̂_category

where B_item = σ²_item / (σ²_item + τ²)
```

**Key Properties:**
- **New items** (0 observations): `B = 1` → use 100% category prior
- **Sparse items** (5-10 obs): `B ≈ 0.7` → 70% prior, 30% data
- **Mature items** (50+ obs): `B ≈ 0.2` → 20% prior, 80% data

**Transition Schedule** (per [model_learning_speed_review.md:L68-L77](../model_learning_speed_review.md#L68-L77)):
```python
prior_weight(t) = max(0.2, 1 - t/90)

Day 0:   100% prior
Day 30:  67% prior, 33% data
Day 60:  33% prior, 67% data
Day 90+: 20% prior, 80% data  # Never fully abandon prior
```

#### Implementation Strategy

**Phase 1: Empirical Bayes (Simpler, MVP)**
1. Estimate global and category-level parameters from all restaurants in system
2. For new restaurant, initialize with category priors
3. Update using weighted average (shrinkage formula)
4. Store sufficient statistics (not full posterior)

**Phase 2: Full Bayes (Advanced, Post-MVP)**
1. Use PyMC or NumPyro for MCMC sampling
2. Jointly estimate all levels of hierarchy
3. Quantify uncertainty via posterior samples
4. Enables prediction intervals from posterior predictive

**Start with Empirical Bayes** (faster, simpler) then migrate to Full Bayes.

#### Dev Notes
- Store category priors in `ForecastPriors` table:
  - `category_path`, `mu_global`, `sigma_global`, `tau_category`, `tau_item`
  - Recalculate weekly using all mature restaurants
- For new item, look up category prior, initialize `mu_item = mu_category`
- Track `n_observations` per item to adjust shrinkage weight
- Use Negative Binomial likelihood (NOT Poisson) per [model_learning_speed_review.md:L315-L338](../model_learning_speed_review.md#L315-L338)

#### Acceptance Criteria
1. Hierarchical model with 3 levels: global → category → item
2. Empirical Bayes shrinkage formula implemented
3. Priors estimated from mature restaurants (60+ days data, 20+ observations per item)
4. New items initialized with category prior
5. Shrinkage weight adjusts based on `n_observations`
6. Uses Negative Binomial likelihood (overdispersion parameter `α`)
7. Achieves WAPE ≤35% with 14 days of data (cold-start benchmark)
8. Achieves WAPE ≤25% with 30 days of data (acceptance criteria)
9. Achieves WAPE ≤18% with 60 days of data (production target)

#### Tasks
- [ ] Create `ForecastPriors` model (category_path, mu, sigma, tau)
- [ ] Implement `EstimatePriors` service:
  - Query all restaurants with 60+ days data
  - Group by category
  - Estimate `mu_category`, `tau_category` (method of moments or MLE)
  - Store in `ForecastPriors` table
- [ ] Implement `HierarchicalForecastModel` class:
  - `fit()`: Estimate item-level parameters with shrinkage
  - `predict()`: Generate point forecast + prediction interval
  - `get_shrinkage_weight()`: Calculate B_item based on n_observations
- [ ] Use Negative Binomial likelihood (statsmodels or scipy):
  ```python
  from scipy.stats import nbinom
  # Fit: estimate μ and α
  # Predict: return nbinom.ppf([0.05, 0.95], ...)
  ```
- [ ] Implement day-of-week shared effects (global DOW pattern)
- [ ] Implement item-level DOW deviations (after 30+ days)
- [ ] Store sufficient statistics per item (n, sum_y, sum_y²)
- [ ] Write unit test: verify shrinkage formula math
- [ ] Write integration test: cold-start simulation (train on 14 days → test WAPE)
- [ ] Benchmark against naive baseline (moving average, Prophet default)

---

### Story 4.3: Negative Binomial Likelihood (P0)

**As an ML engineer,**
**I want to use Negative Binomial distribution instead of Poisson for demand modeling,**
**so that prediction intervals are correctly calibrated for overdispersed restaurant data.**

#### Statistical Justification

Per [model_learning_speed_review.md:L315-L338](../model_learning_speed_review.md#L315-L338):

> **Problem:** Proposal specifies `Poisson(λ)` but restaurant data is overdispersed.
>
> **Evidence:** Literature and domain knowledge confirm variance >> mean due to:
> - Group orders (party of 8 orders 8 steaks)
> - Event spikes (game day)
> - Random closures
>
> **Statistical Analysis:**
> ```
> Poisson:   Var(Y) = E(Y) = λ
> Reality:   Var(Y) = λ(1 + λ/α) > λ   (Negative Binomial)
> ```
>
> **Impact on Learning Speed:**
> - Falsely narrow posterior variance
> - Overconfident early predictions
> - Prediction intervals systematically too tight

**Mathematical Formulation:**
```python
Y_i ~ NegativeBinomial(μ_i, α)

P(Y = k) = Γ(k + α) / [Γ(α) Γ(k+1)] * (α/(α+μ))^α * (μ/(α+μ))^k

E(Y) = μ
Var(Y) = μ + μ²/α   # Overdispersion parameter α controls variance
```

**Expected Improvement** (per [model_learning_speed_review.md:L423-L428](../model_learning_speed_review.md#L423-L428)):
- Time-to-calibration: -30% (from ~60 days to ~40 days)
- Coverage accuracy: +15 percentage points

#### Implementation

**Option 1: statsmodels (Recommended for MVP)**
```python
import statsmodels.api as sm

# Fit Negative Binomial GLM
model = sm.GLM(
    y,
    X,
    family=sm.families.NegativeBinomial(alpha=1.0)  # Estimate alpha
)
result = model.fit()
```

**Option 2: PyMC (Full Bayesian)**
```python
import pymc as pm

with pm.Model() as model:
    α = pm.Exponential("alpha", 1.0)  # Overdispersion
    μ = pm.math.exp(linear_predictor)
    y = pm.NegativeBinomial("sales", mu=μ, alpha=α, observed=sales_data)
    trace = pm.sample()
```

#### Dev Notes
- Start with statsmodels (faster, simpler)
- Estimate `α` from data (MLE or moment matching)
- Store `α` per category (items in same category have similar overdispersion)
- Use overdispersion parameter in prediction interval calculation

#### Acceptance Criteria
1. Model uses Negative Binomial likelihood (not Poisson)
2. Overdispersion parameter `α` estimated from data
3. Prediction intervals calibrated: 90% PI covers 85-95% of actuals
4. CRPS improves by ≥10% compared to Poisson baseline
5. Model handles zero-inflated items (many days with 0 sales)
6. Documented: why Negative Binomial matters, show calibration plots

#### Tasks
- [ ] Replace Poisson with Negative Binomial in forecast model
- [ ] Implement `EstimateOverdispersion` function:
  - Calculate sample mean and variance per item
  - Fit `α` using method of moments: `α = μ² / (var - μ)`
  - Bound: `0.1 ≤ α ≤ 100` (avoid numerical issues)
- [ ] Store `α` in `ForecastPriors` table (category-level)
- [ ] Update `predict()` to use Negative Binomial quantiles:
  ```python
  from scipy.stats import nbinom
  lower = nbinom.ppf(0.05, n=α, p=α/(α+μ))
  upper = nbinom.ppf(0.95, n=α, p=α/(α+μ))
  ```
- [ ] Implement coverage calibration check:
  - For validation set, count % of actuals within [lower, upper]
  - Target: 85-95% for 90% prediction interval
- [ ] Add CRPS calculation (proper scoring rule)
- [ ] Create calibration plots: predicted vs actual intervals
- [ ] Write unit test: verify Negative Binomial math (mean, variance)
- [ ] Benchmark: Poisson vs NegBinom on 10 restaurants

---

### Story 4.4: Stockout Censoring Model (P1)

**As an ML engineer,**
**I want to model stockouts as censored observations,**
**so that demand estimates are unbiased when items sell out before end of day.**

#### Problem Statement

Per [model_learning_speed_review.md:L356-L365](../model_learning_speed_review.md#L356-L365):

> **Problem:** If item sells out, true demand is censored. Learning from `sales = 5` when true demand was 12 biases estimates downward.
>
> **Statistical Model:**
> ```
> Observed:  sales_i = min(demand_i, available_i)
> Likelihood: P(sales | demand) needs to account for truncation
> ```

**Real Impact:**
- Stockouts cause chronic underordering → perpetual stockouts (vicious cycle)
- Underestimates baseline demand by 15-30% for stockout-prone items
- Forecasts learn "Tuesday demand = low" when actually "out of stock on Tuesday"

#### Censoring Likelihood

**Modified Likelihood** (per [model_learning_speed_review.md:L571-L585](../model_learning_speed_review.md#L571-L585)):
```python
If available_i = 1 (item fully stocked):
    L(y_i | θ) = NegBinom(y_i; μ_i, α)

If available_i = 0 (stockout occurred):
    L(y_i | θ) = 1 - CDF(y_i; μ_i, α)  # y_i is lower bound on true demand
```

**Interpretation:**
- Non-stockout days: use observed sales directly
- Stockout days: treat observed sales as **minimum** (true demand ≥ observed)
- Likelihood integrates over all possible true demands above observed

#### Implementation

**Option 1: Tobit Model (Censored Regression)**
```python
from statsmodels.regression.linear_model import OLS
from statsmodels.base.model import GenericLikelihoodModel

class CensoredNegBinom(GenericLikelihoodModel):
    def loglike(self, params):
        # Custom likelihood with censoring
        pass
```

**Option 2: Heuristic Adjustment (Simpler MVP)**
```python
# For stockout days, multiply observed sales by correction factor
correction_factor = 1.3  # Assume 30% unmet demand
adjusted_sales = sales * correction_factor if stockout else sales
```

#### Dev Notes
- Use stockout flags from Epic 2 (`Transaction.stockout_occurred`)
- Start with heuristic (MVP), upgrade to proper censored likelihood (post-MVP)
- Track "stockout-adjusted demand" separately from raw sales
- Flag items with frequent stockouts (>20% of days) for operator attention

#### Acceptance Criteria
1. Model accounts for stockout days using censored likelihood or heuristic
2. Stockout-adjusted demand estimates 15-30% higher than naive for stockout-prone items
3. Forecasts for items with stockout history unbiased (no systematic underestimation)
4. Validation: compare forecast accuracy for items with vs without stockout data
5. Dashboard shows "unmet demand estimate" for stockout days
6. Alerts: "Item X had 5 stockouts last week → estimated lost sales: 23 units"

#### Tasks
- [ ] Extend `HierarchicalForecastModel` to accept stockout flags
- [ ] Implement heuristic adjustment (MVP):
  ```python
  if stockout_flag:
      adjusted_sales = observed_sales * 1.3
  else:
      adjusted_sales = observed_sales
  ```
- [ ] Train model on adjusted sales
- [ ] Implement proper censored likelihood (post-MVP):
  - Use survival function (1 - CDF) for stockout days
  - Combine log-likelihoods: `Σ log(PDF) + Σ log(1 - CDF)`
- [ ] Create `UnmetDemandEstimator` service:
  - For each stockout day, estimate lost sales
  - Return: `{date, item, observed, estimated_true_demand, lost_sales}`
- [ ] Add "Unmet Demand" widget to dashboard
- [ ] Create alert: "Frequent stockouts detected"
- [ ] Write test: simulate stockouts → verify demand unbiased
- [ ] Benchmark: WAPE with vs without censoring model

---

### Story 4.5: Day-of-Week Effects with Pooling (P0)

**As an ML engineer,**
**I want to model day-of-week effects hierarchically,**
**so that new items immediately benefit from shared DOW patterns while allowing customization as data accumulates.**

#### Design Rationale

Per [model_learning_speed_review.md:L481-L492](../model_learning_speed_review.md#L481-L492):

> **Rationale:** Day-of-week patterns are largely consistent (Friday busy, Monday slow). Item deviations are small and can be learned later.
>
> **Structure:**
> ```
> β_dow_item = β_dow_global + δ_dow_item
>
> β_dow_global ~ Normal(0, σ_global²)
> δ_dow_item ~ Normal(0, σ_deviation²)
>
> σ_deviation << σ_global  # Strong pooling initially
> ```

**Example:**
- Global pattern: Friday = +40%, Monday = -20%, Tuesday = -10%, ...
- New item (Salmon): Inherits global pattern immediately (day 1)
- After 30 days: Learn item-specific deviation (Salmon Friday = +50%, not +40%)

#### Implementation

**Shared DOW Component:**
```python
# Estimate from all mature restaurants
dow_effects = {
    0: -0.15,  # Monday: -15%
    1: -0.08,  # Tuesday: -8%
    2: -0.05,  # Wednesday: -5%
    3: +0.02,  # Thursday: +2%
    4: +0.35,  # Friday: +35%
    5: +0.40,  # Saturday: +40%
    6: +0.10,  # Sunday: +10%
}
```

**Item-Level Deviations (After 30+ Days):**
```python
# Allow item to deviate from global pattern
δ_dow_item ~ Normal(0, 0.1²)  # Small deviation (±30% max)
β_dow_item = β_dow_global + δ_dow_item
```

#### Dev Notes
- Store global DOW effects in `ForecastPriors` table
- For new items, use global DOW (no deviation)
- After 30+ observations, estimate item-specific deviation
- Use F-test to determine if item deviation is significant

#### Acceptance Criteria
1. Global DOW pattern estimated from all mature restaurants
2. New items use global DOW pattern (day 1)
3. After 30+ observations, item-specific deviations estimated
4. Deviation magnitude bounded: `|δ| ≤ 0.3` (prevent overfitting)
5. F-test determines when to use item-level deviation vs shared pattern
6. Achieves accurate weekend forecasts (Friday/Saturday WAPE ≤20%)
7. Documentation: show shared vs item-specific DOW plots

#### Tasks
- [ ] Implement `EstimateGlobalDOW` function:
  - Query all restaurants with 60+ days data
  - For each DOW, calculate median log(sales) relative to weekly avg
  - Store in `ForecastPriors` table
- [ ] Update `HierarchicalForecastModel.fit()`:
  - Use global DOW for all items initially
  - If `n_observations >= 30`, estimate item deviation
  - Add regularization: `δ ~ Normal(0, 0.1²)`
- [ ] Implement F-test for heterogeneity:
  - Null: item uses global DOW
  - Alternative: item has custom DOW
  - Accept alternative if p < 0.05 and n >= 30
- [ ] Add DOW visualization in dashboard:
  - Show global pattern (bar chart)
  - Overlay item-specific pattern if available
- [ ] Write test: new item → uses global DOW, mature item → custom DOW
- [ ] Benchmark: weekend forecast accuracy with pooled DOW

---

### Story 4.6: Prediction Interval Calibration (P0)

**As an ML engineer,**
**I want prediction intervals that are correctly calibrated,**
**so that operators can trust uncertainty estimates for safety stock and procurement.**

#### Calibration Definition

**Target:** 90% prediction interval should cover 90% of actual values

**Validation Protocol** (per [model_learning_speed_review.md:L625-L632](../model_learning_speed_review.md#L625-L632)):
```python
Coverage = % of actuals within [lower_90, upper_90]

Acceptance:
- Coverage ∈ [85%, 95%] → Well-calibrated
- Coverage < 80% → Intervals too narrow (overconfident)
- Coverage > 97% → Intervals too wide (underconfident)
```

#### Calibration Methods

**Method 1: Conformal Prediction (Distribution-Free)**
```python
# On validation set, compute residuals
residuals = abs(actual - predicted)

# Find 90th percentile
q_90 = np.quantile(residuals, 0.90)

# Prediction interval:
lower = predicted - q_90
upper = predicted + q_90
```

**Method 2: Quantile Regression**
```python
# Train separate models for 5th, 50th, 95th percentiles
model_05 = QuantileRegressor(quantile=0.05)
model_50 = QuantileRegressor(quantile=0.50)
model_95 = QuantileRegressor(quantile=0.95)
```

**Method 3: Bayesian Posterior Predictive (Full Bayes)**
```python
# Sample from posterior predictive distribution
posterior_samples = pm.sample_posterior_predictive(trace)
lower = np.quantile(posterior_samples, 0.05, axis=0)
upper = np.quantile(posterior_samples, 0.95, axis=0)
```

#### Dev Notes
- Start with conformal prediction (simplest, no distributional assumptions)
- Track coverage per restaurant, per item, per day-of-week
- Recalibrate weekly (recompute quantiles on recent validation data)
- Display coverage metrics in ML monitoring dashboard

#### Acceptance Criteria
1. 90% prediction intervals achieve 85-95% coverage on validation set
2. Coverage tracked and logged per restaurant
3. Intervals recalibrate weekly using recent data
4. Conformal prediction implemented (distribution-free guarantee)
5. Dashboard displays: coverage %, interval width, calibration plot
6. Alerts if coverage <80% or >97% (miscalibration detected)
7. Documentation: explain why calibration matters for procurement

#### Tasks
- [ ] Implement conformal prediction calibration:
  - Compute residuals on validation set
  - Find α-quantile (α = 0.90 for 90% interval)
  - Store quantile in model metadata
- [ ] Update `predict()` to return calibrated intervals:
  ```python
  residual_quantile = model.metadata['residual_q90']
  lower = point_forecast - residual_quantile
  upper = point_forecast + residual_quantile
  ```
- [ ] Implement `CheckCoverage` validation function:
  - For validation set, count actuals within interval
  - Return coverage %
  - Log to CloudWatch
- [ ] Schedule weekly recalibration job (Lambda or Step Functions)
- [ ] Create calibration plot (predicted interval vs actual)
- [ ] Add coverage metric to ML dashboard (gauge chart)
- [ ] Alert if coverage out of range [80%, 97%]
- [ ] Write test: verify coverage on synthetic data (known distribution)

---

### Story 4.7: Forecasting API & Batch Prediction

**As a backend developer,**
**I want API endpoints to generate and retrieve demand forecasts,**
**so that the frontend can display predictions and procurement recommendations.**

#### API Specification

**1. Generate Forecast (Batch)**
```
POST /api/forecasts/generate
Body: {
  restaurant_id: uuid,
  start_date: "2025-01-01",
  end_date: "2025-01-07",  # 7-day forecast
  force_retrain: false
}
Response: {
  job_id: uuid,
  status: "queued" | "running" | "completed" | "failed"
}
```

**2. Get Forecast**
```
GET /api/forecasts?restaurant_id={id}&start_date={date}&end_date={date}
Response: {
  forecasts: [
    {
      date: "2025-01-01",
      item_id: uuid,
      item_name: "Ribeye Steak",
      point_forecast: 23.5,
      lower_90: 18.0,
      upper_90: 30.0,
      confidence: "high" | "medium" | "low",
      factors: {
        dow_effect: +0.35,
        trend: +0.02,
        weather: -0.05,
        stockout_adjusted: false
      }
    }
  ]
}
```

**3. Get Forecast Accuracy**
```
GET /api/forecasts/accuracy?restaurant_id={id}&days=30
Response: {
  wape: 0.22,
  mae: 3.5,
  coverage_90: 0.89,
  by_dow: {
    "Monday": {wape: 0.25, coverage: 0.87},
    "Friday": {wape: 0.18, coverage: 0.91}
  }
}
```

#### Async Processing
- Forecast generation runs async (SageMaker batch transform or Lambda)
- Store results in `demand_forecasts` table
- Polling endpoint: `GET /api/forecasts/jobs/{job_id}` returns status

#### Dev Notes
- Cache forecasts in Redis (TTL = 24 hours)
- Invalidate cache on model retraining
- Serve from cache if forecast exists and <24h old
- Use database for historical forecasts (>7 days old)

#### Acceptance Criteria
1. `POST /api/forecasts/generate` triggers batch prediction job
2. Returns job ID immediately (async processing)
3. `GET /api/forecasts` retrieves saved forecasts from database
4. Response includes point forecast + 90% PI + confidence level
5. Confidence level based on:
   - High: item has 60+ observations, coverage 85-95%
   - Medium: item has 30-60 observations, coverage 80-95%
   - Low: item has <30 observations or coverage <80%
6. Factors breakdown shows contribution of each feature
7. Forecast accuracy endpoint returns WAPE, MAE, coverage by DOW
8. Handles missing forecasts gracefully (return null or generate on-demand)
9. Pagination for large result sets (100+ items)

#### Tasks
- [ ] Create `DemandForecast` model (date, item_id, point, lower, upper, confidence, factors_json)
- [ ] Create `POST /api/forecasts/generate` endpoint:
  - Trigger SageMaker batch transform or Lambda invocation
  - Return job ID
  - Store job in `ForecastJobs` table
- [ ] Create `GET /api/forecasts` endpoint:
  - Query `DemandForecast` table
  - Filter by restaurant, date range
  - Return JSON response
- [ ] Create `GET /api/forecasts/jobs/{id}` polling endpoint
- [ ] Implement batch prediction Lambda:
  - Load model from S3
  - Query feature data for target dates
  - Generate predictions
  - Save to `DemandForecast` table
  - Update job status
- [ ] Add Redis caching layer (cache forecasts for 24h)
- [ ] Create `GET /api/forecasts/accuracy` endpoint:
  - Query actual vs predicted for last N days
  - Calculate WAPE, MAE, coverage
  - Group by DOW
- [ ] Add confidence level calculation logic
- [ ] Write integration test: generate forecast → poll → retrieve results

---

### Story 4.8: Forecast Dashboard UI

**As a restaurant owner,**
**I want to see a visual dashboard of my weekly demand forecasts,**
**so that I can plan procurement, staffing, and promotions.**

#### Dashboard Components

**1. Weekly Calendar View**
- 7-day forecast grid (columns = days, rows = top 20 items)
- Each cell shows: point forecast, confidence band, DOW indicator
- Color coding:
  - Green: high confidence (tight intervals)
  - Yellow: medium confidence
  - Red: low confidence (new item, sparse data)

**2. Forecast Chart (Per Item)**
- Line chart: 30-day history + 7-day forecast
- Shaded area: 90% prediction interval
- Markers: actual sales (past), forecasted (future)
- Annotations: stockouts, promotions, events

**3. Accuracy Metrics**
- WAPE, MAE, coverage % (last 30 days)
- Breakdown by day-of-week (bar chart)
- Trend: accuracy improving or degrading?

**4. Explainability Panel**
- Show factors driving forecast:
  - "Friday +35% (day-of-week)"
  - "Weather: rain forecast -8%"
  - "Trending up +5% (last 2 weeks)"
  - "Stockout-adjusted +20%"

**5. Confidence Indicators**
- Badge: "High Confidence" (green), "Medium Confidence" (yellow), "Low Confidence" (red)
- Tooltip: "Based on 65 days of data, coverage 91%"

#### UX Principles
- **Mobile-first**: Thumb-friendly, swipe to navigate days
- **Actionable**: Click item → drill into details, adjust procurement
- **Trust-building**: Show accuracy metrics prominently (transparency)
- **Progressive disclosure**: Summary view → detail view → full explainability

#### Dev Notes
- Use recharts or Chart.js for visualizations
- Fetch from `GET /api/forecasts` endpoint
- Cache in React Query (5-minute stale time)
- Real-time updates via WebSocket (optional, post-MVP)

#### Acceptance Criteria
1. Weekly calendar view displays 7-day forecast for top 20 items
2. Per-item chart shows history + forecast with prediction intervals
3. Accuracy metrics dashboard (WAPE, coverage, DOW breakdown)
4. Explainability panel shows factor contributions
5. Confidence badges (high/medium/low) displayed per item
6. Responsive design (mobile + desktop)
7. Loading states, error handling (graceful degradation)
8. Export forecast as CSV

#### Tasks
- [ ] Create `ForecastDashboard` React component
- [ ] Build weekly calendar grid (table or custom grid)
- [ ] Create `ForecastChart` component (recharts LineChart with area)
- [ ] Add prediction interval shading (recharts Area)
- [ ] Build accuracy metrics panel (cards + bar chart)
- [ ] Create explainability panel (list of factors with +/- indicators)
- [ ] Add confidence badge component (color-coded, with tooltip)
- [ ] Implement CSV export (download forecast as CSV)
- [ ] Fetch data from `GET /api/forecasts` via React Query
- [ ] Handle loading, error, empty states
- [ ] Write Storybook stories for components
- [ ] E2E test: navigate to dashboard, verify forecast displayed

---

### Story 4.9: Backtesting & Model Validation Harness

**As an ML engineer,**
**I want automated backtesting to validate model accuracy before deployment,**
**so that poor models never reach production.**

#### Backtesting Protocol

Per [model_learning_speed_review.md:L741-L755](../model_learning_speed_review.md#L741-L755):

**Rolling-Origin Backtest:**
```python
for t in [30, 60, 90, 120]:  # days of training data
    train on data[0:t]
    predict data[t:t+7]  # next week
    compute WAPE, Coverage, CRPS
```

**Acceptance Criteria:**
- WAPE ≤ 25% with 30 days of data
- WAPE ≤ 18% with 60 days of data
- 90% PI coverage within [85%, 95%]

**Cold-Start Simulation:**
```python
for restaurant in mature_restaurants:
    for t in [7, 14, 21, 28]:  # first N days only
        train on data[0:t]
        predict holdout week
        compare to model trained on full data
```

**Acceptance Criteria:**
- Error ≤ 1.5x full-data error with 14 days
- Error ≤ 1.2x full-data error with 28 days

#### Implementation

**Backtesting Service:**
```python
class BacktestRunner:
    def run_rolling_origin(self, restaurant_id, horizons=[30, 60, 90]):
        results = []
        for horizon in horizons:
            train_data = data[:horizon]
            test_data = data[horizon:horizon+7]
            model.fit(train_data)
            predictions = model.predict(test_data)
            metrics = evaluate(predictions, test_data)
            results.append(metrics)
        return results

    def run_cold_start_simulation(self, restaurant_ids, init_days=[7, 14, 21, 28]):
        # Similar logic
        pass
```

#### Dev Notes
- Run backtests automatically before deployment (Step Functions validation stage)
- Store backtest results in `ModelValidation` table
- Display results in ML monitoring dashboard
- Fail deployment if acceptance criteria not met

#### Acceptance Criteria
1. Backtesting harness implements rolling-origin validation
2. Cold-start simulation tests 7, 14, 21, 28-day scenarios
3. Computes WAPE, MAE, CRPS, coverage for each test
4. Logs results to `ModelValidation` table
5. Deployment conditional on acceptance criteria:
   - WAPE ≤ 25% with 30 days
   - WAPE ≤ 18% with 60 days
   - Coverage 85-95%
6. Dashboard displays backtest results (table + charts)
7. Alerts if model fails validation

#### Tasks
- [ ] Create `BacktestRunner` service class
- [ ] Implement `run_rolling_origin()` method
- [ ] Implement `run_cold_start_simulation()` method
- [ ] Create `ModelValidation` model (model_version, test_type, metrics_json, passed)
- [ ] Integrate into Step Functions validation stage
- [ ] Add conditional deployment logic (only deploy if passed)
- [ ] Create backtest results dashboard (table + charts)
- [ ] Add alert: "Model failed validation: WAPE 28% > 25% threshold"
- [ ] Write test: run backtest on synthetic data, verify metrics

---

## Epic Acceptance Criteria

**This epic is complete when:**

1. **ML Pipeline Operational**
   - Daily training runs automatically (2am UTC)
   - Models versioned and stored in S3 + SageMaker Model Registry
   - Validation metrics logged to CloudWatch

2. **Forecast Accuracy Targets Met**
   - WAPE ≤ 25% with 30 days of data (cold-start)
   - WAPE ≤ 18% with 60 days of data (production)
   - 90% PI coverage within [85%, 95%]

3. **ML Best Practices Implemented**
   - Hierarchical Bayesian model with empirical priors
   - Negative Binomial likelihood (not Poisson)
   - Stockout censoring model
   - Day-of-week pooling with item-level deviations
   - Calibrated prediction intervals

4. **API & UI Functional**
   - `POST /api/forecasts/generate` triggers batch prediction
   - `GET /api/forecasts` retrieves forecasts with confidence levels
   - Dashboard displays 7-day forecast with explainability
   - Accuracy metrics visible (WAPE, coverage, DOW breakdown)

5. **Validation & Monitoring**
   - Backtesting harness runs before every deployment
   - Cold-start simulation validates early performance
   - Coverage calibration checked weekly
   - Alerts on accuracy degradation

6. **Test Coverage**
   - Unit test: hierarchical model math (shrinkage, priors)
   - Integration test: end-to-end training pipeline
   - Backtest: rolling-origin on 10 restaurants
   - E2E test: user views forecast dashboard, exports CSV

---

## Dev Agent Record

### Agent Model Used
- model: TBD

### Debug Log References
- TBD

### Completion Notes
- Epic not yet started

### Critical Dependencies
- **Epic 2 (Data Ingestion)** MUST complete first:
  - Need 30+ days of transaction history
  - Need stockout flags for censoring model
  - Need promotion flags for elasticity learning
  - Need operating hours for exposure normalization
- **Epic 3 (Recipe Intelligence)** enables procurement:
  - Forecasts must explode into ingredient requirements
  - Cannot generate procurement recommendations without recipes

### ML Model Performance Targets
Per [model_learning_speed_review.md](../model_learning_speed_review.md):

| Metric | 30 Days | 60 Days | 90+ Days |
|--------|---------|---------|----------|
| WAPE | ≤ 25% | ≤ 18% | ≤ 15% |
| Coverage (90% PI) | 85-95% | 85-95% | 85-95% |
| Cold-start regret | 1.5x baseline | 1.2x baseline | 1.0x baseline |

### File List
- `ml/train.py` (SageMaker training script)
- `ml/models/hierarchical_forecast.py` (core model)
- `ml/validation/backtest.py` (validation harness)
- `ml/inference/predict.py` (Lambda inference)
- `apps/api/src/services/forecast_service.py`
- `apps/api/src/models/demand_forecast.py`
- `apps/api/src/models/forecast_priors.py`
- `apps/api/src/routers/forecasts.py`
- `apps/web/src/components/ForecastDashboard.tsx`
- `apps/web/src/components/ForecastChart.tsx`
- `infrastructure/modules/sagemaker/` (Terraform)
- `infrastructure/step-functions/ml-pipeline.json` (state machine)

### Change Log
- 2025-12-23: Epic created with rigorous ML requirements from model_learning_speed_review.md
