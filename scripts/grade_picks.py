#!/usr/bin/env python3
"""Grade logged picks against final scores and print a running ATS record.

Usage:
    python scripts/grade_picks.py
    python scripts/grade_picks.py --season 2026
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nfl_model.data import load_schedules

PICKS_CSV = Path(__file__).resolve().parent.parent / "data" / "picks.csv"


def grade(df: pd.DataFrame) -> pd.DataFrame:
    seasons = sorted(df["season"].unique().tolist())
    schedules = load_schedules(seasons)
    scores = schedules.set_index("game_id")[["home_score", "away_score"]]

    df = df.merge(scores, left_on="game_id", right_index=True, how="left")
    played = df["home_score"].notna() & df["away_score"].notna()

    df.loc[played, "actual_margin"] = df.loc[played, "home_score"] - df.loc[played, "away_score"]
    home_covered = df["actual_margin"] > df["market_spread"]
    away_covered = df["actual_margin"] < df["market_spread"]
    push = df["actual_margin"] == df["market_spread"]

    picked_home = df["pick_side"] == "home"
    won = played & (
        (picked_home & home_covered) | (~picked_home & away_covered)
    ) & ~push
    lost = played & (
        (picked_home & away_covered) | (~picked_home & home_covered)
    ) & ~push
    pushed = played & push

    df.loc[won, "result"] = "WIN"
    df.loc[lost, "result"] = "LOSS"
    df.loc[pushed, "result"] = "PUSH"

    return df.drop(columns=["home_score", "away_score"])


def summarize(df: pd.DataFrame) -> None:
    graded = df[df["result"].isin(["WIN", "LOSS", "PUSH"])]
    if graded.empty:
        print("No graded picks yet -- games may still be in progress.")
        return

    wins = int((graded["result"] == "WIN").sum())
    losses = int((graded["result"] == "LOSS").sum())
    pushes = int((graded["result"] == "PUSH").sum())
    decided = wins + losses
    win_rate = wins / decided if decided else 0.0
    # Standard -110 juice: win +1 unit, lose 1.1 units.
    units = wins * 1.0 - losses * 1.1

    print(f"Record: {wins}-{losses}-{pushes}  ({win_rate:.1%} on decided picks)")
    print(f"Units (assuming -110 odds): {units:+.2f}")

    print("\nBy week:")
    by_week = (
        graded.groupby(["season", "week"])["result"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["WIN", "LOSS", "PUSH"], fill_value=0)
    )
    print(by_week.to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade logged picks and print the ATS record.")
    parser.add_argument("--season", type=int, default=None, help="Only grade/report this season")
    args = parser.parse_args()

    if not PICKS_CSV.exists() or PICKS_CSV.stat().st_size == 0:
        print(f"No picks logged yet at {PICKS_CSV}. Run scripts/weekly_picks.py first.")
        return

    df = pd.read_csv(PICKS_CSV)
    if df.empty:
        print("Picks log is empty -- nothing to grade.")
        return
    df["result"] = df["result"].astype(object).fillna("")

    df = grade(df)
    df.to_csv(PICKS_CSV, index=False)
    print(f"Updated {PICKS_CSV} with graded results.\n")

    if args.season is not None:
        df = df[df["season"] == args.season]
        print(f"-- {args.season} season --")

    summarize(df)


if __name__ == "__main__":
    main()
