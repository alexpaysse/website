# NFL Prediction Model

A from-scratch NFL win probability and point spread model, built on
[`nflreadpy`](https://github.com/nflverse/nflreadpy) play-by-play and schedule
data. It blends an Elo rating system (with margin-of-victory scaling and
season-to-season regression) with rolling team EPA/play efficiency, backtests
the result against actual closing spreads, and includes a weekly workflow for
generating and grading picks against the market.

## How the model works

1. **Elo ratings** (`nfl_model/elo.py`) — every team starts at 1500. After each
   game, ratings update using a 538-style formula: the shift is scaled by how
   surprising the result was (bigger upsets move ratings more) and by the
   margin of victory (blowouts move ratings more than close wins). Ratings
   partially regress toward the mean between seasons.
2. **Rolling EPA/play** (`nfl_model/epa.py`) — for every game, each team's
   offensive and defensive EPA per play is computed from play-by-play data.
   A trailing window (default: last 10 games) of a team's own history is
   averaged to estimate its current offensive and defensive strength.
3. **Combined model** (`nfl_model/model.py`) — a team's Elo edge (rating diff
   + home-field advantage) and its EPA/play edge (net efficiency diff vs. the
   opponent) are combined into a predicted point margin via a linear
   regression fit on historical games:
   `predicted_margin = a * elo_diff + b * epa_diff`. Win probability comes
   from a normal CDF over that margin, calibrated against the residual
   standard deviation from the fit.
4. **Backtest** (`nfl_model/backtest.py`) — replays every game chronologically
   so Elo and EPA state at prediction time only ever reflects games that had
   already happened (no lookahead). The model is fit on all but the most
   recent season and evaluated out-of-sample on that holdout season, against
   `nflreadpy`'s market closing spread (`spread_line`).

## Setup

```bash
pip install -r requirements.txt
```

The first data load per season takes a bit — `nflreadpy` downloads and caches
play-by-play and schedule files from the nflverse data releases.

## Usage

### Backtest the model

```bash
python scripts/run_backtest.py
python scripts/run_backtest.py --seasons 2021 2022 2023 2024 2025
python scripts/run_backtest.py --save backtest_results.csv
```

Prints the fitted coefficients and out-of-sample metrics (Brier score, log
loss, straight-up accuracy, mean absolute spread error, ATS accuracy).

### Weekly picks

```bash
python scripts/weekly_picks.py                       # auto-detects season/week
python scripts/weekly_picks.py --season 2026 --week 3
python scripts/weekly_picks.py --threshold 2.5        # only flag bigger edges
python scripts/weekly_picks.py --no-log               # print without logging
```

Rebuilds current Elo/EPA ratings from every completed game, predicts every
game in the target week, and flags any game where the model's predicted
margin disagrees with the market spread by more than `--threshold` points
(default: 1.5). Flagged picks are appended to `data/picks.csv`.

### Grade picks

```bash
python scripts/grade_picks.py
python scripts/grade_picks.py --season 2026
```

Looks up final scores for every logged pick, fills in `actual_margin` and
`result` (WIN/LOSS/PUSH) in `data/picks.csv`, and prints a running
against-the-spread record, win rate, unit total (at standard -110 odds), and
a week-by-week breakdown.

## Project layout

```
nfl_model/
  config.py     seasons, Elo/EPA constants, edge threshold
  data.py       nflreadpy loading helpers
  elo.py        Elo rating system
  epa.py        rolling team EPA/play tracker
  model.py      Elo+EPA blend -> spread & win probability
  backtest.py   chronological walk-forward simulation
scripts/
  run_backtest.py   backtest CLI
  weekly_picks.py   weekly picks CLI
  grade_picks.py    grading CLI
data/
  picks.csv     logged picks (created/updated by the scripts)
```

## Notes and caveats

- Regular season games only; the model isn't tuned for playoff variance.
- Early in a season, EPA history is thin and ratings lean more on the prior
  season's regressed Elo, so predictions are noisier in Weeks 1-3.
- This is a personal analysis tool, not a betting system — backtested
  accuracy on historical closing lines does not guarantee future edge, and
  the sample sizes here are small by sports-betting standards.
