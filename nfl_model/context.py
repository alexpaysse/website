"""Extra, non-modeled context for a game: injuries, head-to-head, rest, venue.

None of this feeds the point-spread math in model.py -- it's surfaced next to
each pick so you can apply judgment before betting, the way you'd skim an
injury report before placing a real one. Baking hand-picked point penalties
for "starting QB out" etc. straight into the spread isn't done here because
there isn't enough historical injury data wired up yet to fit and backtest
those adjustments properly -- guessing at the numbers would just add
unvalidated noise to a model that's otherwise backtested.
"""
from __future__ import annotations

import pandas as pd
import nflreadpy as nfl

_SEVERITY = {"Out": 0, "Doubtful": 1, "Questionable": 2}


def load_injuries(season: int) -> pd.DataFrame:
    df = nfl.load_injuries(seasons=[season]).to_pandas()
    return df[df["report_status"].notna()].copy()


def team_injury_notes(injuries: pd.DataFrame, team: str, week: int, limit: int = 6) -> list[str]:
    """Most severe injury designations for a team, as of the latest report at or before `week`."""
    team_rows = injuries[(injuries["team"] == team) & (injuries["week"] <= week)]
    if team_rows.empty:
        return []
    latest_week = team_rows["week"].max()
    team_rows = team_rows[team_rows["week"] == latest_week].copy()
    team_rows["severity"] = team_rows["report_status"].map(_SEVERITY).fillna(3)
    team_rows = team_rows.sort_values("severity").head(limit)

    notes = []
    for r in team_rows.itertuples():
        note = f"{r.position} {r.full_name} - {r.report_status}"
        if isinstance(r.report_primary_injury, str) and r.report_primary_injury:
            note += f" ({r.report_primary_injury})"
        notes.append(note)
    return notes


def head_to_head(schedules: pd.DataFrame, team_a: str, team_b: str, n: int = 3) -> list[str]:
    """Last n meetings between the two teams (any location), most recent first."""
    played = schedules.dropna(subset=["home_score", "away_score"])
    matchups = played[
        ((played["home_team"] == team_a) & (played["away_team"] == team_b))
        | ((played["home_team"] == team_b) & (played["away_team"] == team_a))
    ].sort_values("gameday", ascending=False).head(n)

    notes = []
    for g in matchups.itertuples():
        cover = ""
        if g.spread_line == g.spread_line:  # not NaN
            margin = g.home_score - g.away_score
            if margin > g.spread_line:
                cover = f", {g.home_team} covered"
            elif margin < g.spread_line:
                cover = f", {g.away_team} covered"
            else:
                cover = ", push"
        notes.append(
            f"{g.season} wk{g.week}: {g.away_team} {int(g.away_score)} @ "
            f"{g.home_team} {int(g.home_score)}{cover}"
        )
    return notes


def rest_note(home_team: str, away_team: str, home_rest: float, away_rest: float) -> str | None:
    if home_rest != home_rest or away_rest != away_rest:  # NaN
        return None
    diff = home_rest - away_rest
    if abs(diff) < 3:
        return None
    if diff > 0:
        return f"{home_team} has {int(home_rest)} days rest vs {away_team}'s {int(away_rest)}"
    return f"{away_team} has {int(away_rest)} days rest vs {home_team}'s {int(home_rest)}"


def venue_note(roof: str) -> str | None:
    if not isinstance(roof, str):
        return None
    if roof in ("outdoors", "open"):
        return "Outdoors -- check the forecast closer to kickoff (wind/cold can swing passing games and totals)"
    return None
