#!/usr/bin/env python3
"""Backtest the Elo+EPA model over the last 5 seasons and print evaluation metrics.

Usage:
    python scripts/run_backtest.py
    python scripts/run_backtest.py --seasons 2021 2022 2023 2024 2025
    python scripts/run_backtest.py --save results.csv
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from nfl_model import config
from nfl_model.backtest import run_backtest


def main() -> None:
    parser = argparse.ArgumentParser(description="Backtest the Elo+EPA NFL model.")
    parser.add_argument("--seasons", type=int, nargs="+", default=config.BACKTEST_SEASONS)
    parser.add_argument("--save", type=str, default=None, help="Path to write per-game predictions as CSV")
    args = parser.parse_args()

    print(f"Backtesting seasons {args.seasons} (training on all but the most recent, "
          f"evaluating held out on the last one)...")
    df, metrics, model, totals_model = run_backtest(args.seasons)

    print("\nFitted spread model:")
    print(f"  predicted_margin = {metrics['elo_to_points']:.4f} * elo_diff "
          f"+ {metrics['epa_coef']:.2f} * epa_diff")
    print(f"  residual sigma (for win prob): {metrics['sigma']:.2f} points")
    print(f"  trained on seasons: {metrics['train_seasons']}")

    print("\nFitted totals model:")
    print(f"  predicted_total = {metrics['totals_intercept']:.2f} "
          f"+ {metrics['totals_scoring_coef']:.2f} * scoring_env")
    print(f"  residual sigma: {metrics['totals_sigma']:.2f} points")

    print(f"\nHeld-out evaluation -- {metrics['eval_season']} season ({metrics['n_games']} games):")
    print(f"  Brier score:              {metrics['brier_score']:.4f}  (lower is better, 0.25 = coin flip)")
    print(f"  Log loss:                 {metrics['log_loss']:.4f}")
    print(f"  Straight-up accuracy:     {metrics['straight_up_accuracy']:.1%}")
    print(f"  Mean abs. spread error:   {metrics['mean_abs_spread_error']:.2f} points vs. closing line")
    print(f"  ATS accuracy (all games): {metrics['ats_accuracy_all_games']:.1%}  "
          f"(betting the model's side on every single game, not just flagged edges)")
    print(f"  Mean abs. total error:    {metrics['mean_abs_total_error']:.2f} points vs. closing total "
          f"({metrics['n_games_with_total']} games with a posted total)")
    print(f"  Total (O/U) accuracy:     {metrics['total_accuracy_all_games']:.1%}  "
          f"(betting the model's side on every game's total, not just flagged edges)")

    if args.save:
        df.to_csv(args.save, index=False)
        print(f"\nSaved {len(df)} per-game predictions to {args.save}")


if __name__ == "__main__":
    main()
