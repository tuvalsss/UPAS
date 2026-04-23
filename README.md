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
| `UPAS MASTER` (foreground) | `tools.cli` | Interactive REPL — `help`, `status`, `ask`, `orders`, `positions`, etc. |

Closing `UPAS MASTER` kills scheduler + dashboard.

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
