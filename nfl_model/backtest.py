"""Walk-forward simulation of the Elo+EPA model, plus a chronological state builder."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import config
from .data import load_pbp, load_schedules
from .elo import EloRatings
from .epa import TeamEpaTracker, compute_game_team_epa
from .model import NFLPredictionModel


def walk_forward_features(
    played_games: pd.DataFrame, pbp: pd.DataFrame
) -> tuple[pd.DataFrame, EloRatings, TeamEpaTracker]:
    """Replay games in chronological order, recording each game's *pre-game* features.

    Elo and EPA state are only updated with a game's result *after* that
    game's features are recorded, so nothing here can see the future.
    Returns the feature/outcome rows plus the final Elo and EPA state, which
    the weekly script reuses to score not-yet-played games.
    """
    game_epa = compute_game_team_epa(pbp)
    epa_lookup = {
        (row.game_id, row.team): (row.off_epa_play, row.def_epa_play_allowed)
        for row in game_epa.itertuples()
    }

    elo = EloRatings()
    epa_tracker = TeamEpaTracker()
    rows = []
    current_season = None

    for game in played_games.sort_values(["gameday", "game_id"]).itertuples():
        if game.season != current_season:
            elo.start_season(game.season)
            current_season = game.season

        home_elo, away_elo = elo.pre_game_ratings(game.home_team, game.away_team)
        elo_diff = home_elo + config.HOME_FIELD_ADV - away_elo

        home_off, home_def = epa_tracker.pregame(game.home_team)
        away_off, away_def = epa_tracker.pregame(game.away_team)
        epa_diff = (home_off - home_def) - (away_off - away_def)

        rows.append(
            {
                "game_id": game.game_id,
                "season": game.season,
                "week": game.week,
                "gameday": game.gameday,
                "home_team": game.home_team,
                "away_team": game.away_team,
                "elo_diff": elo_diff,
                "epa_diff": epa_diff,
                "actual_margin": game.home_score - game.away_score,
                "market_spread": game.spread_line,
            }
        )

        elo.update(game.home_team, game.away_team, game.home_score, game.away_score)
        h_off, h_def = epa_lookup.get((game.game_id, game.home_team), (float("nan"), float("nan")))
        a_off, a_def = epa_lookup.get((game.game_id, game.away_team), (float("nan"), float("nan")))
        epa_tracker.update(game.home_team, h_off, h_def)
        epa_tracker.update(game.away_team, a_off, a_def)

    return pd.DataFrame(rows), elo, epa_tracker


def _played_reg_games(schedules: pd.DataFrame) -> pd.DataFrame:
    played = schedules.dropna(subset=["home_score", "away_score"])
    return played[played["game_type"] == "REG"].copy()


def _brier(probs: np.ndarray, outcomes: np.ndarray) -> float:
    return float(np.mean((probs - outcomes) ** 2))


def _log_loss(probs: np.ndarray, outcomes: np.ndarray) -> float:
    eps = 1e-9
    p = np.clip(probs, eps, 1 - eps)
    return float(-np.mean(outcomes * np.log(p) + (1 - outcomes) * np.log(1 - p)))


def run_backtest(seasons: list[int] | None = None) -> tuple[pd.DataFrame, dict, NFLPredictionModel]:
    """Fit the model on all but the most recent season, evaluate on that holdout season."""
    seasons = seasons or config.BACKTEST_SEASONS
    schedules = load_schedules(seasons)
    played = _played_reg_games(schedules)
    pbp = load_pbp(seasons)

    df, _elo, _epa_tracker = walk_forward_features(played, pbp)

    holdout_season = max(seasons)
    train = df[df["season"] < holdout_season]
    test = df[df["season"] == holdout_season]
    if train.empty:
        train, test = df, df

    model = NFLPredictionModel()
    model.fit(train["elo_diff"].to_numpy(), train["epa_diff"].to_numpy(), train["actual_margin"].to_numpy())

    preds = df.apply(lambda r: model.predict(r["elo_diff"], r["epa_diff"]), axis=1)
    df["predicted_margin"] = [p.predicted_margin for p in preds]
    df["home_win_prob"] = [p.home_win_prob for p in preds]
    df["home_win"] = (df["actual_margin"] > 0).astype(int)
    df["ats_edge"] = df["predicted_margin"] - df["market_spread"]
    df["picked_home"] = df["ats_edge"] > 0
    df["home_covered"] = df["actual_margin"] > df["market_spread"]
    df["pick_correct"] = np.where(df["picked_home"], df["home_covered"], ~df["home_covered"])

    eval_df = df[df["season"] == holdout_season]
    if eval_df.empty:
        eval_df = df

    metrics = {
        "train_seasons": sorted(train["season"].unique().tolist()),
        "eval_season": holdout_season,
        "n_games": int(len(eval_df)),
        "brier_score": _brier(eval_df["home_win_prob"].to_numpy(), eval_df["home_win"].to_numpy()),
        "log_loss": _log_loss(eval_df["home_win_prob"].to_numpy(), eval_df["home_win"].to_numpy()),
        "straight_up_accuracy": float((eval_df["home_win_prob"].round() == eval_df["home_win"]).mean()),
        "mean_abs_spread_error": float((eval_df["predicted_margin"] - eval_df["market_spread"]).abs().mean()),
        "ats_accuracy_all_games": float(eval_df["pick_correct"].mean()),
        "elo_to_points": model.elo_to_points,
        "epa_coef": model.epa_coef,
        "sigma": model.sigma,
    }
    return df, metrics, model


def build_current_state(
    seasons: list[int] | None = None,
) -> tuple[EloRatings, TeamEpaTracker, NFLPredictionModel, pd.DataFrame]:
    """Replay every played game to date and fit the model on all of it.

    Used by the weekly script: the returned Elo/EPA state reflects every
    completed game, ready to score whatever games haven't been played yet.
    """
    seasons = seasons or config.BACKTEST_SEASONS
    schedules = load_schedules(seasons)
    played = _played_reg_games(schedules)
    pbp = load_pbp(seasons)

    df, elo, epa_tracker = walk_forward_features(played, pbp)

    model = NFLPredictionModel()
    model.fit(df["elo_diff"].to_numpy(), df["epa_diff"].to_numpy(), df["actual_margin"].to_numpy())

    return elo, epa_tracker, model, schedules
