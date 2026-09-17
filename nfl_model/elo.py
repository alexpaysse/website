"""NFL Elo rating system with a margin-of-victory adjustment (538-style)."""
from __future__ import annotations

from . import config


def expected_win_prob(rating_diff: float) -> float:
    """Win probability implied by an Elo rating difference (includes any HFA)."""
    return 1.0 / (1.0 + 10 ** (-rating_diff / 400.0))


def mov_multiplier(margin: float, elo_diff: float) -> float:
    """Scales the Elo update by how lopsided the result was."""
    return ((abs(margin) + 3) ** 0.8) / (7.5 + 0.006 * abs(elo_diff))


class EloRatings:
    """Tracks per-team Elo ratings across seasons, with between-season regression."""

    def __init__(self, initial: float = config.INITIAL_ELO):
        self._initial = initial
        self.ratings: dict[str, float] = {}
        self._current_season: int | None = None

    def get(self, team: str) -> float:
        return self.ratings.setdefault(team, self._initial)

    def start_season(self, season: int) -> None:
        """Call once per season, before its first game, to regress ratings toward the mean."""
        if self._current_season is not None and season != self._current_season:
            for team, rating in self.ratings.items():
                self.ratings[team] = (
                    rating * (1 - config.SEASON_REGRESSION)
                    + config.MEAN_ELO * config.SEASON_REGRESSION
                )
        self._current_season = season

    def pre_game_ratings(self, home: str, away: str) -> tuple[float, float]:
        return self.get(home), self.get(away)

    def update(self, home: str, away: str, home_score: float, away_score: float) -> None:
        home_elo = self.get(home)
        away_elo = self.get(away)
        elo_diff = home_elo + config.HOME_FIELD_ADV - away_elo
        expected_home = expected_win_prob(elo_diff)

        margin = home_score - away_score
        actual_home = 1.0 if margin > 0 else (0.5 if margin == 0 else 0.0)

        shift = config.K_FACTOR * mov_multiplier(margin, elo_diff) * (actual_home - expected_home)
        self.ratings[home] = home_elo + shift
        self.ratings[away] = away_elo - shift
