"""Combines Elo rating diff and EPA/play diff into a spread + win probability."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy.stats import norm


@dataclass
class Prediction:
    predicted_margin: float  # points, positive favors the home team
    home_win_prob: float


class NFLPredictionModel:
    """predicted_margin = a * elo_diff + b * epa_diff, win prob via a normal CDF.

    ``elo_diff`` is the home team's Elo edge (rating diff plus home-field
    advantage, in Elo points). ``epa_diff`` is the home team's net EPA/play
    edge (its own offense-minus-defense rating minus the away team's).
    Coefficients ``a``, ``b`` and the residual spread ``sigma`` are fit with
    OLS in ``fit`` rather than guessed, so the blend and the points-per-Elo
    conversion reflect the actual data instead of an arbitrary heuristic.
    """

    def __init__(self, elo_to_points: float = 1 / 25, epa_coef: float = 50.0, sigma: float = 13.5):
        self.elo_to_points = elo_to_points
        self.epa_coef = epa_coef
        self.sigma = sigma

    def predict(self, elo_diff: float, epa_diff: float) -> Prediction:
        predicted_margin = self.elo_to_points * elo_diff + self.epa_coef * epa_diff
        home_win_prob = float(norm.cdf(predicted_margin / self.sigma))
        return Prediction(predicted_margin=predicted_margin, home_win_prob=home_win_prob)

    def fit(self, elo_diffs: np.ndarray, epa_diffs: np.ndarray, margins: np.ndarray) -> None:
        """OLS-fit the blend weights and calibrate sigma from the residuals.

        No intercept: home-field advantage is already baked into elo_diff.
        """
        X = np.column_stack([elo_diffs, epa_diffs])
        coef, *_ = np.linalg.lstsq(X, margins, rcond=None)
        self.elo_to_points, self.epa_coef = (float(c) for c in coef)
        residuals = margins - X @ coef
        self.sigma = float(np.std(residuals))
