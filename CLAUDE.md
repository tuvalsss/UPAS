# CLAUDE.md — UPAS Continuation Directives

**Purpose**: instructions for any future Claude session working on UPAS.
The north star is simple: **realized P&L must grow**. Every change in this
repo is measured against that outcome.

---

## 1. The Self-Improvement Pipeline (current state)

Five stages, each building on the previous. Always check the current state
before starting work — never rebuild a stage that already exists.

| Stage | Module | State | Gate |
|---|---|---|---|
| 1. Outcome tracker | `core/outcome_tracker.py` | ✅ built | n/a |
| 2. Strategy scorecard | `core/strategy_scorecard.py` | ✅ built | n/a |
| 3. Adaptive weights | `core/strategy_weights.py` | ✅ built, live | n/a |
| 3b. Near-miss paper routing | `core/engine.py` (tier logic) | ✅ built, live | `PAPER_MIN_SCORE`, `PAPER_MIN_CONF` |
| 3c. Threshold tuner | `core/threshold_tuner.py` | ✅ built (advisory) | n/a |
| 4. ML re-ranker (XGBoost) | `ml/reranker.py` | ⚠️ scaffold, needs ≥100 outcomes to train | `RERANKER_MIN_SAMPLES` |
| 5. AI strategy generator | `ai/strategy_generator.py` | ⚠️ scaffold, needs ≥500 outcomes | `STRATEGY_GEN_MIN_OUTCOMES` |

### Signal tier routing
Every signal is classified at engine.execute time:
- **REAL**   — score ≥ `MIN_SIGNAL_SCORE` AND conf ≥ `MIN_CONFIDENCE_EXEC` → real order.
- **PAPER (near-miss)** — score in [`PAPER_MIN_SCORE`, real-threshold) AND conf ≥ `PAPER_MIN_CONF` → virtual order, logged + resolved but no exchange contact.
- **PAPER (proposed-strategy)** — any strategy in `tools/strategy_tool._PAPER_STRATEGIES` (e.g. `smart_money`) → always paper regardless of score.
- **DISCARDED** — everything else.

Paper orders write to `orders` with `paper_trade=1, status='paper'`. Outcome tracker resolves them the same way as real orders. Scorecard reports them in a separate panel. `threshold_tuner` mines score-bucket performance across both tiers to suggest MIN_SIGNAL_SCORE changes.

The tracker daemon is `UPAS_TRACKER` window (launched by `START_ALL.bat`).
It runs every 30 min, writes to `results` table, then calls
`strategy_weights.update_weights()` which feeds back into
`strategy_tool.run_strategies()` (disabled check + score multiplier).

## 2. Continuation Loop — How To Work On This Project

Before doing anything, run:

```bash
python -m core.strategy_scorecard       # realized P&L by strategy
python -m core.strategy_weights         # current disabled/boost state
python -m ml.reranker                   # training-data readiness
```

### If `grand_total.total_pnl_usd` is declining
Stop. Find the root cause before adding features. Check:
1. Which strategies are losing? Tighten their filters or let the auto-disable kick in.
2. Are markets being traded that shouldn't be? Look at `engine.py` filters (`EXPIRY_HOURS_MIN`, `LIQUIDITY_MIN`).
3. Spread/fee bleed? See `tools/fees.py` gate in engine.

### If enough outcomes have accumulated
- ≥100 outcomes → train the ML re-ranker:
  `python -m ml.reranker --train`
  Check the reported `positive_rate` — must be >0.50 for the model to add value.
- ≥500 outcomes → generate one proposed new strategy:
  `python -m ai.strategy_generator`
  Review `strategies/proposed/<name>.py`. **Never auto-enable.** Move to
  `strategies/core/` only after human review + paper-trade validation.

### Default work mode
Small, measurable changes with a clear hypothesis about P&L impact. One
commit per logical fix. Push to `github.com/tuvalsss/UPAS` after local
verification. CI runs `ruff` + import sanity + gitleaks on every push.

## 3. Non-Negotiables

- **Never commit secrets.** `.env`, `config/*.pem`, `license_private.pem`,
  `license.jwt` are gitignored. Verify before every push.
- **Never disable reverse-validation.** Every forward signal must pass
  `reverse_strategies/reverse_validator.py`. If it's blocking good signals,
  tune the rules — do not skip.
- **Never hardcode trade size.** Use `tools.sizing.kelly_size_usd()`. If it
  returns `size_usd=0`, respect it — that signal is not worth trading.
- **Never trade sub-2h markets on Polymarket.** `EXPIRY_HOURS_MIN=2` is the
  root-cause fix for the 91% loss rate we measured on `chainlink_edge`
  crypto 5-min windows. Don't revert it.

## 4. Measurement Discipline

After any substantive change, log the counterfactual in the commit message:

> Expected impact on win_rate / avg_pnl / trades_per_day, and why.

When the user asks "did this help?", answer with scorecard numbers before
and after, not feelings.

## 5. Upgrade Roadmap (in order)

The system improves incrementally. Do NOT jump stages.

0. **Also available**: `strategies/proposed/smart_money.py` — copy-trade whales
   via Polymarket public leaderboard API
   (`https://data-api.polymarket.com/v1/leaderboard`). NOT wired. Needs dry-run
   validation over ≥50 clusters before promotion. See
   [docs/strategies/smart-money.md](docs/strategies/smart-money.md) for full plan.
1. **Current**: Stages 1-3 live, stages 4-5 scaffolded.
2. **Next once ≥100 realized outcomes (~3-5 days of trading)**:
   - Train reranker. Verify `positive_rate` + `logloss` improvement over
     equal-weighted baseline.
   - Add reranker prob to `tools/sizing.py` edge calculation (already wired).
3. **Next once ≥300 realized outcomes**:
   - Sharpe-ratio-based weight adjustment, not just win rate.
   - Per-exchange weights (a strategy might work on Kalshi but not Poly).
4. **Next once ≥500 outcomes**:
   - Run strategy_generator weekly.
   - Sandbox proposed strategies in dry-run for 100 trades before promoting.
5. **Next once ≥1000 outcomes**:
   - Retrain reranker with tuned hyperparameters (grid over max_depth, eta).
   - Consider a second model: expected-PnL regression instead of binary win.

## 6. Where To Find Things Fast

- Orders placed live: `sqlite> SELECT * FROM orders WHERE dry_run=0 AND timestamp>=datetime('now','-1 day');`
- Live signals: `sqlite> SELECT * FROM signals WHERE timestamp>=datetime('now','-1 hour') ORDER BY score DESC LIMIT 20;`
- Realized outcomes: `sqlite> SELECT * FROM results WHERE won IS NOT NULL ORDER BY outcome_timestamp DESC LIMIT 20;`
- Adaptive state: `sqlite> SELECT * FROM strategy_weights;`
- Structured logs: `logs/upas.jsonl` (JSON per line).

## 7. Communication Style

- Speak in Hebrew unless the user switches to English.
- Be concrete: numbers, file:line references, scorecard outputs.
- When reporting "done", show the before/after metric that proves it.
- Never claim profitability without data to back it.
