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


@dataclass
class TotalPrediction:
    predicted_total: float  # combined points, both teams


class NFLTotalsModel:
    """predicted_total = intercept + coef * scoring_env, fit with OLS.

    ``scoring_env`` (see epa.matchup_edges) is how favorable this specific
    matchup looks for scoring -- both offenses' expected edge against the
    defense they're actually facing. Unlike the spread model this needs an
    intercept: a total is centered on the league-average game total (around
    44-46 points), not zero.
    """

    def __init__(self, intercept: float = 45.0, scoring_coef: float = 40.0, sigma: float = 10.0):
        self.intercept = intercept
        self.scoring_coef = scoring_coef
        self.sigma = sigma

    def predict(self, scoring_env: float) -> TotalPrediction:
        return TotalPrediction(predicted_total=self.intercept + self.scoring_coef * scoring_env)

    def fit(self, scoring_envs: np.ndarray, totals: np.ndarray) -> None:
        X = np.column_stack([np.ones_like(scoring_envs), scoring_envs])
        coef, *_ = np.linalg.lstsq(X, totals, rcond=None)
        self.intercept, self.scoring_coef = (float(c) for c in coef)
        residuals = totals - X @ coef
        self.sigma = float(np.std(residuals))
