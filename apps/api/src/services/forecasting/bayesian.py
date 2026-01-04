"""
Flux Probabilistic Forecasting Engine.
Implements Hierarchical Bayesian Negative Binomial forecasting.

Mathematical Basis:
Poisson-Gamma Conjugate:
Prior: lambda ~ Gamma(alpha, beta)
Likelihood: y ~ Poisson(lambda)
Posterior: lambda | y ~ Gamma(alpha + sum(y), beta + n)
Predictive: y_pred ~ NegBin(n=alpha_post, p=beta_post/(beta_post+1))
"""
from dataclasses import dataclass
from typing import List, Optional, Tuple, Dict
import numpy as np
from scipy import stats
from decimal import Decimal

@dataclass
class ForecastDistribution:
    """Probabilistic forecast for a specific date."""
    date: str
    mean: float
    p10: float  # 10th percentile (Optimistic/Low risk)
    p50: float  # Median
    p90: float  # 90th percentile (Conservative/High risk)
    p99: float  # Tail risk (Stockout prevention)
    confidence_score: float = 0.0 # 0.0 to 1.0 (Based on amount of evidence n)
    logic_trigger: str = "" # Explainability string

@dataclass
class GammaParams:
    """Parameters for Gamma Distribution (alpha=shape, beta=rate)."""
    alpha: float
    beta: float

    @property
    def mean(self) -> float:
        return self.alpha / self.beta

class BayesianForecaster:
    """
    Seasonal Hierarchical Bayesian Forecaster.

    Logic:
    1. Deseasonalize History: y' = y / M_dow
    2. Bayesian Update: Posterior ~ Prior + y'
    3. Reseasonalize Forecast: y_pred = NegBin(Posterior) * M_dow_future
    """

    def __init__(self, global_alpha: float = 2.0, global_beta: float = 0.5):
        """
        Initialize with weak global priors.
        """
        self.global_prior = GammaParams(alpha=global_alpha, beta=global_beta)
        self.category_priors: Dict[str, GammaParams] = {}

    def learn_priors(self, category_data: Dict[str, List[float]]):
        """
        Learn category-level priors from historical data (Aggregated/Normalized).
        """
        for cat, data in category_data.items():
            if not data:
                self.category_priors[cat] = self.global_prior
                continue

            # Update Global -> Category
            # Ideally data here is also de-seasonalized?
            # For simplicity, if we sum over many weeks, seasonality averages out roughly?
            # Better: assume 'data' passed here is already 'base sales' or sum of 28 days.

            n = len(data)
            sum_y = sum(data)

            cat_alpha = self.global_prior.alpha + sum_y
            cat_beta = self.global_prior.beta + n
            self.category_priors[cat] = GammaParams(alpha=cat_alpha, beta=cat_beta)

    def predict_item(
        self,
        item_history: List[float],
        history_dows: List[int], # Day of week for each history point (0=Mon, 6=Sun)
        future_dates: List[str], # Dates to forecast
        future_dows: List[int], # DOWs for forecast
        category: Optional[str] = None,
        seasonal_multipliers: Optional[Dict[int, float]] = None # DOW -> Multiplier
    ) -> List[ForecastDistribution]:
        """
        Generate probabilistic forecast with De-seasonalization.
        """
        # 1. Select Prior (Hierarchy)
        prior = self.global_prior
        prior_source = "Global"

        if category and category in self.category_priors:
            prior = self.category_priors[category]
            prior_source = "Category"

        # 2. De-seasonalize History
        # If no profile provided, assume flat (multiplier=1.0)
        multipliers = seasonal_multipliers or {i: 1.0 for i in range(7)}

        deseasonalized_history = []
        for y, dow in zip(item_history, history_dows):
            # Safe division - handle very small or zero multipliers
            m = multipliers.get(dow, 1.0)
            # Only exclude days that are truly closed (multiplier near 0)
            # Days with low but non-zero demand (0.1-0.3x) are still valid
            if m < 0.01:
                # Skip this day entirely - likely closed
                continue
            y_prime = y / m
            deseasonalized_history.append(y_prime)

        # 3. Bayesian Update (on Base Sales)
        n = len(deseasonalized_history)
        sum_y_prime = sum(deseasonalized_history)

        post_alpha = prior.alpha + sum_y_prime
        post_beta = prior.beta + n

        # Calculate Base Predictive Dist (Negative Binomial)
        # scipy nbinom: n=alpha_post, p=beta_post/(beta_post+1)
        nb_n = post_alpha
        nb_p = post_beta / (post_beta + 1.0)

        # Confidence Score: Sigmoid of 'n' (observations)
        # n=0 -> low, n=30 -> high
        confidence = 1.0 / (1.0 + np.exp(-(n - 5.0) / 5.0))

        forecasts = []

        # Use Monte Carlo sampling for correct reseasonalization
        # This preserves the exact percentile meanings after scaling
        n_samples = 10000
        np.random.seed(42)  # For reproducibility

        for i, (date_str, dow) in enumerate(zip(future_dates, future_dows)):
            # 4. Re-seasonalize using Monte Carlo
            m = multipliers.get(dow, 1.0)

            # CORRECT METHOD: Sample from base distribution, scale, compute quantiles
            # If we simply multiply quantiles by m, we lose percentile meaning
            # Instead: sample -> scale -> empirical quantiles
            base_samples = stats.nbinom.rvs(nb_n, nb_p, size=n_samples)
            scaled_samples = base_samples * m

            # Compute quantiles from scaled distribution
            mean = float(np.mean(scaled_samples))
            p10 = float(np.percentile(scaled_samples, 10))
            p50 = float(np.percentile(scaled_samples, 50))
            p90 = float(np.percentile(scaled_samples, 90))
            p99 = float(np.percentile(scaled_samples, 99))

            explanation = []
            if abs(m - 1.0) > 0.1:
                explanation.append(f"Seasonality {m:.2f}x")

            if n < 5:
                explanation.append(f"Cold Start ({prior_source} Prior)")

            trigger = ", ".join(explanation) if explanation else "Normal"

            forecasts.append(ForecastDistribution(
                date=date_str,
                mean=mean,
                p10=p10,
                p50=p50,
                p90=p90,
                p99=p99,
                confidence_score=float(confidence),
                logic_trigger=trigger
            ))

        return forecasts
