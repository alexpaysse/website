"""Constants shared across the NFL prediction model."""
from __future__ import annotations

from datetime import date

_today = date.today()
# NFL seasons are labeled by the year they start (Sep). Jan/Feb games still
# belong to the previous season's label.
CURRENT_SEASON = _today.year if _today.month >= 3 else _today.year - 1

# Last 5 seasons, including whatever is in progress right now.
BACKTEST_SEASONS = list(range(CURRENT_SEASON - 4, CURRENT_SEASON + 1))

# --- Elo ---
INITIAL_ELO = 1500.0
MEAN_ELO = 1500.0
HOME_FIELD_ADV = 55.0       # Elo points added to the home team's rating
K_FACTOR = 20.0
SEASON_REGRESSION = 1 / 3   # fraction regressed toward the mean between seasons

# --- EPA ---
EPA_TRAILING_GAMES = 10     # trailing window (in games) for rolling team EPA/play

# --- Betting ---
EDGE_THRESHOLD = 1.5        # minimum |model spread - market spread| to flag a pick
