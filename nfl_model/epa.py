"""Rolling team efficiency (EPA/play) tracking, offense and defense."""
from __future__ import annotations

import math
from collections import defaultdict, deque

import pandas as pd

from . import config


def compute_game_team_epa(pbp: pd.DataFrame) -> pd.DataFrame:
    """One row per (game, team) with offensive and defensive EPA/play for that game."""
    off = (
        pbp.groupby(["game_id", "posteam"])["epa"]
        .mean()
        .rename("off_epa_play")
        .reset_index()
        .rename(columns={"posteam": "team"})
    )
    deff = (
        pbp.groupby(["game_id", "defteam"])["epa"]
        .mean()
        .rename("def_epa_play_allowed")
        .reset_index()
        .rename(columns={"defteam": "team"})
    )
    return off.merge(deff, on=["game_id", "team"], how="outer")


class TeamEpaTracker:
    """Maintains a trailing window of per-game EPA/play for every team.

    ``pregame`` only ever looks at games already fed in through ``update``, so
    using it inside a chronological walk-forward loop can't leak future data.
    """

    def __init__(self, window: int = config.EPA_TRAILING_GAMES):
        self.window = window
        self._off: dict[str, deque] = defaultdict(lambda: deque(maxlen=self.window))
        self._def: dict[str, deque] = defaultdict(lambda: deque(maxlen=self.window))

    def pregame(self, team: str) -> tuple[float, float]:
        """League-neutral (0.0) EPA/play until a team has built up any history."""
        off_hist = self._off[team]
        def_hist = self._def[team]
        off_epa = sum(off_hist) / len(off_hist) if off_hist else 0.0
        def_epa = sum(def_hist) / len(def_hist) if def_hist else 0.0
        return off_epa, def_epa

    def update(self, team: str, off_epa_play: float, def_epa_play_allowed: float) -> None:
        if off_epa_play is not None and not math.isnan(off_epa_play):
            self._off[team].append(off_epa_play)
        if def_epa_play_allowed is not None and not math.isnan(def_epa_play_allowed):
            self._def[team].append(def_epa_play_allowed)
