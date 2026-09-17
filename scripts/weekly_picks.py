#!/usr/bin/env python3
"""Print games where the model disagrees with the market spread or total, and log picks.

Usage:
    python scripts/weekly_picks.py                  # auto-detect current season/week
    python scripts/weekly_picks.py --season 2026 --week 3
    python scripts/weekly_picks.py --threshold 2.5 --total-threshold 4 --no-log
"""
from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nfl_model import config, context
from nfl_model.backtest import build_current_state
from nfl_model.elo import EloRatings
from nfl_model.epa import TeamEpaTracker, matchup_edges
from nfl_model.model import NFLPredictionModel, NFLTotalsModel

PICKS_CSV = Path(__file__).resolve().parent.parent / "data" / "picks.csv"

# One row per bet. bet_type is "spread" or "total"; pick_side/pick_label and
# market_line/model_value mean different things depending on which.
PICKS_COLUMNS = [
    "logged_at", "season", "week", "game_id", "gameday",
    "home_team", "away_team", "bet_type",
    "market_line", "model_value", "home_win_prob", "edge",
    "pick_side", "pick_label",
    "actual_value", "result",
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
    totals_model: NFLTotalsModel,
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
        epa_diff, scoring_env = matchup_edges(home_off, home_def, away_off, away_def)

        spread_pred = model.predict(elo_diff, epa_diff)
        has_spread = g.spread_line == g.spread_line  # not NaN
        spread_edge = spread_pred.predicted_margin - g.spread_line if has_spread else float("nan")
        spread_side = "home" if spread_edge > 0 else "away" if has_spread else None
        spread_pick = (g.home_team if spread_side == "home" else g.away_team) if has_spread else None

        total_pred = totals_model.predict(scoring_env)
        has_total = g.total_line == g.total_line  # not NaN
        total_edge = total_pred.predicted_total - g.total_line if has_total else float("nan")
        total_side = "over" if total_edge > 0 else "under" if has_total else None
        total_pick = total_side.upper() if has_total else None

        rows.append(
            {
                "season": season,
                "week": week,
                "game_id": g.game_id,
                "gameday": g.gameday,
                "home_team": g.home_team,
                "away_team": g.away_team,
                "market_spread": g.spread_line,
                "predicted_margin": round(spread_pred.predicted_margin, 2),
                "home_win_prob": round(spread_pred.home_win_prob, 3),
                "spread_edge": round(spread_edge, 2) if has_spread else None,
                "spread_pick_side": spread_side,
                "spread_pick_team": spread_pick,
                "market_total": g.total_line,
                "predicted_total": round(total_pred.predicted_total, 2),
                "total_edge": round(total_edge, 2) if has_total else None,
                "total_pick_side": total_side,
                "total_pick_label": total_pick,
                "home_qb_name": g.home_qb_name,
                "away_qb_name": g.away_qb_name,
                "home_rest": g.home_rest,
                "away_rest": g.away_rest,
                "roof": g.roof,
            }
        )
    return pd.DataFrame(rows)


def flagged_bets(predictions: pd.DataFrame, spread_threshold: float, total_threshold: float) -> pd.DataFrame:
    """Long-format bets (one row per bet) that clear their respective edge threshold."""
    spread_flags = predictions[predictions["spread_edge"].abs() >= spread_threshold].copy()
    spread_flags["bet_type"] = "spread"
    spread_flags["market_line"] = spread_flags["market_spread"]
    spread_flags["model_value"] = spread_flags["predicted_margin"]
    spread_flags["edge"] = spread_flags["spread_edge"]
    spread_flags["pick_side"] = spread_flags["spread_pick_side"]
    spread_flags["pick_label"] = spread_flags["spread_pick_team"]

    total_flags = predictions[predictions["total_edge"].abs() >= total_threshold].copy()
    total_flags["bet_type"] = "total"
    total_flags["market_line"] = total_flags["market_total"]
    total_flags["model_value"] = total_flags["predicted_total"]
    total_flags["edge"] = total_flags["total_edge"]
    total_flags["pick_side"] = total_flags["total_pick_side"]
    total_flags["pick_label"] = total_flags["total_pick_label"]
    total_flags["home_win_prob"] = None

    keep = [
        "season", "week", "game_id", "gameday", "home_team", "away_team",
        "bet_type", "market_line", "model_value", "home_win_prob", "edge",
        "pick_side", "pick_label",
        "home_qb_name", "away_qb_name", "home_rest", "away_rest", "roof",
    ]
    combined = pd.concat([spread_flags[keep], total_flags[keep]], ignore_index=True)
    combined["abs_edge"] = combined["edge"].abs()
    return combined.sort_values("abs_edge", ascending=False).drop(columns="abs_edge")


def log_picks(df: pd.DataFrame) -> int:
    """Append newly flagged bets to data/picks.csv, skipping (game_id, bet_type) pairs already logged."""
    if PICKS_CSV.exists() and PICKS_CSV.stat().st_size > 0:
        existing = pd.read_csv(PICKS_CSV)
    else:
        existing = pd.DataFrame(columns=PICKS_COLUMNS)

    if not existing.empty:
        already_logged = set(zip(existing["game_id"], existing["bet_type"]))
        to_log = df[~df.apply(lambda r: (r["game_id"], r["bet_type"]) in already_logged, axis=1)].copy()
    else:
        to_log = df.copy()
    if to_log.empty:
        return 0

    to_log["logged_at"] = datetime.now(timezone.utc).isoformat()
    to_log["actual_value"] = None
    to_log["result"] = ""
    to_log = to_log[PICKS_COLUMNS]

    combined = pd.concat([existing, to_log], ignore_index=True)
    PICKS_CSV.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(PICKS_CSV, index=False)
    return len(to_log)


def main() -> None:
    parser = argparse.ArgumentParser(description="Flag games where the model disagrees with the spread or total.")
    parser.add_argument("--season", type=int, default=None)
    parser.add_argument("--week", type=int, default=None)
    parser.add_argument("--threshold", type=float, default=config.EDGE_THRESHOLD, help="Spread edge threshold")
    parser.add_argument(
        "--total-threshold", type=float, default=config.TOTAL_EDGE_THRESHOLD, help="Total (O/U) edge threshold"
    )
    parser.add_argument("--no-log", action="store_true", help="Print only, don't write to data/picks.csv")
    args = parser.parse_args()

    print("Loading schedules and play-by-play, rebuilding current ratings...")
    elo, epa_tracker, model, totals_model, schedules = build_current_state()

    season = args.season or config.CURRENT_SEASON
    week = args.week if args.week is not None else current_week(schedules, season)
    if week is None:
        print(f"No upcoming games found for the {season} season.")
        return

    predictions = predict_week(elo, epa_tracker, model, totals_model, schedules, season, week)
    if predictions.empty:
        print(f"No scheduled games found for {season} week {week}.")
        return

    print(f"\n{season} season, week {week} -- model vs. market")
    print("-" * 78)
    for row in predictions.itertuples():
        spread_flag = row.spread_edge is not None and abs(row.spread_edge) >= args.threshold
        total_flag = row.total_edge is not None and abs(row.total_edge) >= args.total_threshold
        spread_str = (
            f"spread: market {row.market_spread:+.1f} model {row.predicted_margin:+.1f} "
            f"edge {row.spread_edge:+.1f}{' <--' if spread_flag else ''}"
            if row.spread_edge is not None
            else "spread: no line posted yet"
        )
        total_str = (
            f"total: market {row.market_total:.1f} model {row.predicted_total:.1f} "
            f"edge {row.total_edge:+.1f}{' <--' if total_flag else ''}"
            if row.total_edge is not None
            else "total: no line posted yet"
        )
        print(f"{row.away_team:>3} @ {row.home_team:<3}  {spread_str}  |  {total_str}")

    flagged = flagged_bets(predictions, args.threshold, args.total_threshold)
    if flagged.empty:
        print(f"\nNo bets clear the disagreement thresholds this week "
              f"(spread {args.threshold}, total {args.total_threshold}).")
        return

    print(f"\n{len(flagged)} bet(s) flagged:")
    print(
        "(Context below is informational only -- it does not feed the model's numbers. "
        "Use it as a manual gut-check before betting.)"
    )
    injuries = context.load_injuries(season)
    for row in flagged.itertuples():
        if row.bet_type == "spread":
            headline = f"Take {row.pick_label} ({row.pick_side}) ATS -- edge {row.edge:+.1f}"
        else:
            headline = f"Take the {row.pick_label} {row.market_line:.1f} -- edge {row.edge:+.1f}"
        print(f"\n  {row.away_team} @ {row.home_team}: {headline}")
        print(f"    Projected starters: {row.away_team} {row.away_qb_name} @ {row.home_team} {row.home_qb_name}")

        for team in (row.home_team, row.away_team):
            notes = context.team_injury_notes(injuries, team, week)
            if notes:
                print(f"    {team} injury report: " + "; ".join(notes))

        h2h = context.head_to_head(schedules, row.home_team, row.away_team)
        if h2h:
            print("    Last meetings: " + " | ".join(h2h))

        rest = context.rest_note(row.home_team, row.away_team, row.home_rest, row.away_rest)
        if rest:
            print(f"    Rest edge: {rest}")

        venue = context.venue_note(row.roof)
        if venue:
            print(f"    Venue: {venue}")

    if not args.no_log:
        n_logged = log_picks(flagged)
        print(f"\nLogged {n_logged} new bet(s) to {PICKS_CSV}")


if __name__ == "__main__":
    main()
