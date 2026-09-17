"""Thin data-loading layer on top of nflreadpy."""
from __future__ import annotations

import pandas as pd
import nflreadpy as nfl

_PBP_COLUMNS = [
    "game_id",
    "season",
    "week",
    "season_type",
    "posteam",
    "defteam",
    "play_type",
    "epa",
]


def load_schedules(seasons: list[int]) -> pd.DataFrame:
    """Games (played and upcoming) with dates, scores, and betting lines."""
    df = nfl.load_schedules(seasons=seasons).to_pandas()
    df["gameday"] = pd.to_datetime(df["gameday"])
    return df.sort_values(["gameday", "game_id"]).reset_index(drop=True)


def load_pbp(seasons: list[int]) -> pd.DataFrame:
    """Play-by-play, trimmed to the columns needed for EPA aggregation."""
    raw = nfl.load_pbp(seasons=seasons)
    cols = [c for c in _PBP_COLUMNS if c in raw.columns]
    df = raw.select(cols).to_pandas()
    df = df[df["play_type"].isin(["run", "pass"])]
    df = df.dropna(subset=["epa", "posteam", "defteam"])
    return df.reset_index(drop=True)
