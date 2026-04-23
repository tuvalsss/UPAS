# UPAS — Universal Prediction Alpha System

Alpha-detection engine for prediction markets (Polymarket + Kalshi), running live on Windows with Chainlink Data Streams integration.

## What it does

Scans 14,000+ binary prediction markets across two exchanges every 60s. Runs 18 statistical strategies (7 core, 8 reverse, 3 meta) + 1 real-time Chainlink edge strategy. Cross-validates every forward signal via a reverse strategy before scoring. AI-ranks surviving signals via Claude. Executes fee-aware live orders on Polymarket (USDC on Polygon, sig_type=1 proxy) and Kalshi (API key).

## Quick start (Windows)

```cmd
cd C:\Users\tuval\GTproducts\UPAS
.venv\Scripts\python.exe -m pip install -r requirements.txt
copy .env.example .env         :: then fill in credentials
START_ALL.bat                  :: opens scheduler + dashboard + CLI; close window -> all stop
```

## Runtime layout

| Window | Process | Purpose |
|---|---|---|
| `UPAS_SCHEDULER` | `core.scheduler` | Runs pipeline every 60s |
| `UPAS_DASHBOARD` | `tools.dashboard` | Live status panels |
| `UPAS_MONITOR` | `core.position_monitor` | Stop-loss (-40%) / take-profit (+80%) every 5 min |
| `UPAS_TRACKER` | `core.outcome_tracker` | Resolves closed positions, updates adaptive weights every 30 min |
| `UPAS MASTER` (foreground) | `tools.cli` | Interactive REPL — `help`, `pnl`, `scorecard`, `orders`, `positions`, etc. |

Closing `UPAS MASTER` kills scheduler + dashboard + monitor + tracker.

## CLI commands

```
status       system health summary
portfolio    balances (poly + kalshi)
positions    active positions
pnl [hours]  portfolio curve + realized + live unrealized P&L
scorecard    per-strategy win rate + PnL + adaptive weights
orders [n]   last N orders
signals [n]  top N signals from last 10 min
track        force one outcome-tracker pass
train        train ML re-ranker (needs ≥100 outcomes)
propose      ask Claude for a new strategy (needs ≥500 outcomes)
pause/resume pause/resume execute stage
ask <q>      free-form question to Claude about system state
```

## Self-improvement pipeline

UPAS learns from its own results:

1. **outcome_tracker** verifies each trade against Polymarket CLOB resolution API and writes PnL to `results` table.
2. **strategy_scorecard** aggregates per-strategy win rate + PnL.
3. **strategy_weights** auto-disables strategies with n≥50 and win_rate<35%, boosts strategies with n≥30 and win_rate>55%.
4. **ml/reranker.py** (scaffold, activates at 100 outcomes) trains XGBoost on signal features → win probability → scales Kelly sizing.
5. **ai/strategy_generator.py** (scaffold, activates at 500 outcomes) asks Claude to propose new strategies based on gap analysis. Output goes to `strategies/proposed/` for human review — never auto-enabled.

## Pipeline stages

```
scan → normalize → dedup → core strategies → reverse strategies → meta strategies
  → reverse validator → uncertainty engine → AI scorer → fee gate → execute → checkpoint
```

Full diagram: [docs/pipeline/flow.md](docs/pipeline/flow.md).

## Safety model

- **Fee gate** ([tools/fees.py](tools/fees.py)): trade rejected unless expected gross edge > 1.5× round-trip fees. Kalshi uses the official `ceil(7 × contracts × p × (1-p))` cents formula.
- **Reverse validation**: every forward signal is counter-checked by its paired reverse strategy. Failing signals are downgraded 50% or discarded.
- **Per-order caps**: `$5` fixed size in validation window, `$500` max position, `$2000` max total exposure.
- **DRY_RUN flag**: `.env` flip disables all live orders.
- **Checkpoint on every stage transition** — resume mid-pipeline after crash.

## Polymarket auth specifics

Polymarket uses Magic.link proxy wallets. Our setup:

- `POLY_PRIVATE_KEY` = EOA signer
- `POLY_FUNDER_ADDRESS` = proxy (discovered via `https://polymarket.com/api/profile/userData`)
- `POLY_SIGNATURE_TYPE=1`
- USDC sits in the **proxy**, not the EOA
- Allowance must be set to three spenders: CTF Exchange, NegRisk Exchange, NegRiskAdapter

Diagnostic: `python -m tools.poly_diagnose`

## Chainlink integration

Real-time Chainlink Data Streams via Polymarket's public WebSocket (`wss://ws-live-data.polymarket.com`, topic `crypto_prices_chainlink`). One thread per symbol (BTC, ETH, SOL, XRP). Feeds [strategies/core/chainlink_edge.py](strategies/core/chainlink_edge.py) — detects directional edge on Polymarket's 5-minute crypto Up/Down markets when ≥25s have elapsed in the window.

## Health check

```cmd
.venv\Scripts\python.exe -m tools.e2e_test      :: 11-step system audit
.venv\Scripts\python.exe -m tools.poly_diagnose :: balance + allowance per chain
```

## Documentation

- [docs/HOME.md](docs/HOME.md) — Obsidian vault index
- [docs/STATUS.md](docs/STATUS.md) — current system state, profitability model, gaps
- [docs/architecture/overview.md](docs/architecture/overview.md) — module map
- [docs/pipeline/flow.md](docs/pipeline/flow.md) — full pipeline diagram
- [docs/strategies/](docs/strategies/) — every strategy with formula + thresholds
