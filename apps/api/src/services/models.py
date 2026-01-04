
from abc import ABC, abstractmethod
from typing import Dict, Any, List
import pandas as pd
import numpy as np

class ForecastModel(ABC):
    """Abstract base class for forecasting models."""

    @abstractmethod
    def train(self, X: pd.DataFrame, y: pd.Series):
        """Train the model."""
        pass

    @abstractmethod
    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """Generate predictions."""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Return model name."""
        pass


class MovingAverageModel(ForecastModel):
    """
    Baseline model using simple moving average.
    Predicts next day = average of last N days.
    Since we predict multiple days out, this is a naive recursive forecast
    or just carrying forward the last known mean.
    For simplicity: Weighted Average of last 7 days.
    """

    def __init__(self, window: int = 7):
        self.window = window
        self.last_mean = 0.0

    def train(self, X: pd.DataFrame, y: pd.Series):
        """
        'Train' just calculates the mean of the most recent window.
        Assumes data is sorted by date.
        """
        if len(y) > 0:
            # Take last N values
            recent = y.tail(self.window)
            self.last_mean = recent.mean()
        else:
            self.last_mean = 0.0

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """
        Predict constant value (last mean) for all future steps.
        """
        # Return array of shape (n_samples,) with constant value
        return np.full(len(X), self.last_mean)

    def get_name(self) -> str:
        return f"MovingAverage_{self.window}d"
