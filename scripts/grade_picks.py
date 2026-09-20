#!/usr/bin/env python3
"""Grade logged bets (spread and total) against final scores, print a running record.

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
    """Fill in actual_value and result for every graded bet.

    Spread bets (pick_side "home"/"away") and total bets (pick_side
    "over"/"under") share the same win condition once you notice "home" and
    "over" both mean "wins if actual_value > market_line": a home-side pick
    wins if the margin (home - away) beats the line, an over pick wins if
    the total beats the line.
    """
    seasons = sorted(df["season"].unique().tolist())
    schedules = load_schedules(seasons)
    scores = schedules.set_index("game_id")[["home_score", "away_score"]]

    df = df.merge(scores, left_on="game_id", right_index=True, how="left")
    played = df["home_score"].notna() & df["away_score"].notna()
    is_spread = df["bet_type"] == "spread"

    margin = df["home_score"] - df["away_score"]
    total = df["home_score"] + df["away_score"]
    df.loc[played & is_spread, "actual_value"] = margin[played & is_spread]
    df.loc[played & ~is_spread, "actual_value"] = total[played & ~is_spread]

    higher_side = df["pick_side"].isin(["home", "over"])
    covers_high = df["actual_value"] > df["market_line"]
    covers_low = df["actual_value"] < df["market_line"]
    push = df["actual_value"] == df["market_line"]

    won = played & ~push & ((higher_side & covers_high) | (~higher_side & covers_low))
    lost = played & ~push & ((higher_side & covers_low) | (~higher_side & covers_high))
    pushed = played & push

    df.loc[won, "result"] = "WIN"
    df.loc[lost, "result"] = "LOSS"
    df.loc[pushed, "result"] = "PUSH"

    return df.drop(columns=["home_score", "away_score"])


def _record_line(graded: pd.DataFrame) -> str:
    wins = int((graded["result"] == "WIN").sum())
    losses = int((graded["result"] == "LOSS").sum())
    pushes = int((graded["result"] == "PUSH").sum())
    decided = wins + losses
    win_rate = wins / decided if decided else 0.0
    units = wins * 1.0 - losses * 1.1  # standard -110 juice
    return f"{wins}-{losses}-{pushes}  ({win_rate:.1%} on decided picks)  units: {units:+.2f}"


def _dollar_pnl(graded: pd.DataFrame) -> float:
    """Actual $ P/L for real-money bets at standard -110 odds, using each row's stake."""
    stake = graded["stake"].fillna(0)
    win_profit = stake * (100 / 110)
    pnl = pd.Series(0.0, index=graded.index)
    pnl[graded["result"] == "WIN"] = win_profit[graded["result"] == "WIN"]
    pnl[graded["result"] == "LOSS"] = -stake[graded["result"] == "LOSS"]
    return float(pnl.sum())


def summarize(df: pd.DataFrame) -> None:
    graded = df[df["result"].isin(["WIN", "LOSS", "PUSH"])]
    if graded.empty:
        print("No graded picks yet -- games may still be in progress.")
        return

    for mode in ("paper", "real"):
        subset = graded[graded.get("mode", "paper").fillna("paper") == mode]
        if subset.empty:
            continue
        label = "PAPER (no money)" if mode == "paper" else "REAL MONEY"
        print(f"\n[{label}] {_record_line(subset)}")
        if mode == "real":
            print(f"  Actual $ P/L (at -110): {_dollar_pnl(subset):+.2f}")
        for bet_type in ("spread", "total"):
            bt_subset = subset[subset["bet_type"] == bet_type]
            if not bt_subset.empty:
                print(f"    {bet_type:>6}: {_record_line(bt_subset)}")

    print("\nBy week:")
    by_week = (
        graded.groupby(["season", "week", "bet_type", "mode"])["result"]
        .value_counts()
        .unstack(fill_value=0)
        .reindex(columns=["WIN", "LOSS", "PUSH"], fill_value=0)
    )
    print(by_week.to_string())


def main() -> None:
    parser = argparse.ArgumentParser(description="Grade logged bets and print the record.")
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
