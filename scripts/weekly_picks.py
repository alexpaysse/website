#!/usr/bin/env python3
"""Print games where the model disagrees with the market spread, and log picks.

Usage:
    python scripts/weekly_picks.py                  # auto-detect current season/week
    python scripts/weekly_picks.py --season 2026 --week 3
    python scripts/weekly_picks.py --threshold 2.5 --no-log
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nfl_model import config
from nfl_model.backtest import build_current_state
from nfl_model.elo import EloRatings
from nfl_model.epa import TeamEpaTracker
from nfl_model.model import NFLPredictionModel

PICKS_CSV = Path(__file__).resolve().parent.parent / "data" / "picks.csv"

PICKS_COLUMNS = [
    "logged_at", "season", "week", "game_id", "gameday",
    "home_team", "away_team", "market_spread", "predicted_margin",
    "home_win_prob", "edge", "pick_side", "pick_team",
    "actual_margin", "result",
]


def current_week(schedules: pd.DataFrame, season: int) -> int | None:
    season_games = schedules[(schedules["season"] == season) & (schedules["game_type"] == "REG")]
    upcoming = season_games[season_games["home_score"].isna()]
    if upcoming.empty:
        return None
    return int(upcoming["week"].min())


def predict_week(
    elo: EloRatings,
    epa_tracker: TeamEpaTracker,
    model: NFLPredictionModel,
    schedules: pd.DataFrame,
    season: int,
    week: int,
) -> pd.DataFrame:
    games = schedules[
        (schedules["season"] == season)
        & (schedules["week"] == week)
        & (schedules["game_type"] == "REG")
    ]

    rows = []
    for g in games.itertuples():
        home_elo, away_elo = elo.pre_game_ratings(g.home_team, g.away_team)
        elo_diff = home_elo + config.HOME_FIELD_ADV - away_elo

        home_off, home_def = epa_tracker.pregame(g.home_team)
        away_off, away_def = epa_tracker.pregame(g.away_team)
        epa_diff = (home_off - home_def) - (away_off - away_def)

        pred = model.predict(elo_diff, epa_diff)
        has_line = g.spread_line == g.spread_line  # not NaN
        edge = pred.predicted_margin - g.spread_line if has_line else float("nan")
        pick_side = "home" if edge > 0 else "away" if has_line else None
        pick_team = (g.home_team if pick_side == "home" else g.away_team) if has_line else None

        rows.append(
            {
                "season": season,
                "week": week,
                "game_id": g.game_id,
                "gameday": g.gameday,
                "home_team": g.home_team,
                "away_team": g.away_team,
                "market_spread": g.spread_line,
                "predicted_margin": round(pred.predicted_margin, 2),
                "home_win_prob": round(pred.home_win_prob, 3),
                "edge": round(edge, 2) if has_line else None,
                "pick_side": pick_side,
                "pick_team": pick_team,
            }
        )
    return pd.DataFrame(rows)


def log_picks(df: pd.DataFrame) -> int:
    """Append newly flagged picks to data/picks.csv, skipping game_ids already logged."""
    if PICKS_CSV.exists() and PICKS_CSV.stat().st_size > 0:
        existing = pd.read_csv(PICKS_CSV)
    else:
        existing = pd.DataFrame(columns=PICKS_COLUMNS)

    already_logged = set(existing["game_id"]) if not existing.empty else set()
    to_log = df[~df["game_id"].isin(already_logged)].copy()
    if to_log.empty:
        return 0

    to_log["logged_at"] = datetime.now(timezone.utc).isoformat()
    to_log["actual_margin"] = None
    to_log["result"] = ""
    to_log = to_log[PICKS_COLUMNS]

    combined = pd.concat([existing, to_log], ignore_index=True)
    PICKS_CSV.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(PICKS_CSV, index=False)
    return len(to_log)


def main() -> None:
    parser = argparse.ArgumentParser(description="Flag games where the model disagrees with the spread.")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=config.EDGE_THRESHOLD)
    parser.add_argument("--no-log", action="store_true", help="Print only, don't write to data/picks.csv")
    args = parser.parse_args()

    print("Loading schedules and play-by-play, rebuilding current ratings...")
    elo, epa_tracker, model, schedules = build_current_state()

    season = args.season or config.CURRENT_SEASON
    week = args.week if args.week is not None else current_week(schedules, season)
    if week is None:
        print(f"No upcoming games found for the {season} season.")
        return

    predictions = predict_week(elo, epa_tracker, model, schedules, season, week)
    if predictions.empty:
        print(f"No scheduled games found for {season} week {week}.")
        return

    abs_edge = predictions["edge"].abs()
    flagged = predictions[abs_edge >= args.threshold].copy()
    flagged["abs_edge"] = flagged["edge"].abs()
    flagged = flagged.sort_values("abs_edge", ascending=False).drop(columns="abs_edge")

    print(f"\n{season} season, week {week} -- model vs. market spread")
    print("-" * 60)
    for row in predictions.itertuples():
        if row.edge is None or row.edge != row.edge:
            print(f"{row.away_team:>3} @ {row.home_team:<3}  market: no line posted yet")
            continue
        flag = "  <-- DISAGREE" if abs(row.edge) >= args.threshold else ""
        print(
            f"{row.away_team:>3} @ {row.home_team:<3}  "
            f"market {row.market_spread:+.1f}  model {row.predicted_margin:+.1f}  "
            f"P(home win)={row.home_win_prob:.0%}  edge={row.edge:+.1f}{flag}"
        )

    if flagged.empty:
        print(f"\nNo games clear the disagreement threshold ({args.threshold} pts) this week.")
        return

    print(f"\n{len(flagged)} pick(s) flagged (|edge| >= {args.threshold}):")
    for row in flagged.itertuples():
        print(f"  Take {row.pick_team} ({row.pick_side}) -- edge {row.edge:+.1f}")

    if not args.no_log:
        n_logged = log_picks(flagged)
        print(f"\nLogged {n_logged} new pick(s) to {PICKS_CSV}")


if __name__ == "__main__":
    main()
