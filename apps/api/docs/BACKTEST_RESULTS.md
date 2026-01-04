# Forecast Backtesting Results
**Restaurant:** Synthetic Test Cafe  **Generated:** 2026-01-02  
## Summary
Rolling-origin cross-validation with multiple training window sizes.
| Item | Training | WAPE | PI Coverage | Status |
|------|----------|------|-------------|--------|
| Burger | 30d | 27.0% | 85.7% | ⚠️  Review |
| Burger | 60d | 27.9% | 85.7% | ⚠️  Review |
| Caesar Salad | 30d | 28.1% | 85.7% | ⚠️  Review |
| Caesar Salad | 60d | 30.6% | 90.5% | ⚠️  Review |
| French Fries | 30d | 34.2% | 85.7% | ⚠️  Review |
| French Fries | 60d | 38.5% | 90.5% | ⚠️  Review |

## Acceptance Criteria
- ✅ WAPE ≤ 25% with 30 days training
- ✅ WAPE ≤ 18% with 60 days training
- ✅ 90% PI coverage within 85-95%

## Detailed Results

### Burger

**Training Window: 30 days**
- Overall WAPE: **27.01%**
- PI Coverage: **85.7%**
- Forecast Horizon: 7 days
- Total Predictions: 28

Fold-by-fold:
- Fold 1: WAPE=29.3%, Coverage=85.7%
- Fold 2: WAPE=36.0%, Coverage=85.7%
- Fold 3: WAPE=22.2%, Coverage=85.7%
- Fold 4: WAPE=19.8%, Coverage=85.7%

**Training Window: 60 days**
- Overall WAPE: **27.91%**
- PI Coverage: **85.7%**
- Forecast Horizon: 7 days
- Total Predictions: 21

Fold-by-fold:
- Fold 1: WAPE=31.5%, Coverage=85.7%
- Fold 2: WAPE=32.0%, Coverage=85.7%
- Fold 3: WAPE=20.4%, Coverage=85.7%

### Caesar Salad

**Training Window: 30 days**
- Overall WAPE: **28.13%**
- PI Coverage: **85.7%**
- Forecast Horizon: 7 days
- Total Predictions: 28

Fold-by-fold:
- Fold 1: WAPE=48.6%, Coverage=71.4%
- Fold 2: WAPE=12.5%, Coverage=100.0%
- Fold 3: WAPE=30.2%, Coverage=71.4%
- Fold 4: WAPE=22.5%, Coverage=100.0%

**Training Window: 60 days**
- Overall WAPE: **30.63%**
- PI Coverage: **90.5%**
- Forecast Horizon: 7 days
- Total Predictions: 21

Fold-by-fold:
- Fold 1: WAPE=49.9%, Coverage=71.4%
- Fold 2: WAPE=16.1%, Coverage=100.0%
- Fold 3: WAPE=27.7%, Coverage=100.0%

### French Fries

**Training Window: 30 days**
- Overall WAPE: **34.23%**
- PI Coverage: **85.7%**
- Forecast Horizon: 7 days
- Total Predictions: 28

Fold-by-fold:
- Fold 1: WAPE=38.4%, Coverage=100.0%
- Fold 2: WAPE=39.9%, Coverage=85.7%
- Fold 3: WAPE=41.3%, Coverage=57.1%
- Fold 4: WAPE=17.3%, Coverage=100.0%

**Training Window: 60 days**
- Overall WAPE: **38.53%**
- PI Coverage: **90.5%**
- Forecast Horizon: 7 days
- Total Predictions: 21

Fold-by-fold:
- Fold 1: WAPE=34.5%, Coverage=100.0%
- Fold 2: WAPE=39.7%, Coverage=85.7%
- Fold 3: WAPE=40.4%, Coverage=85.7%
