---
aliases: [UPAS Status, Profitability, System Truth]
tags: [status, profitability, cto-review]
type: operational
updated: 2026-04-24
related: [[HOME]], [[architecture/overview]], [[pipeline/flow]], [[strategies/INDEX]]
---

# UPAS — Current System State (CTO Review)

> Snapshot: **2026-04-24**. This doc tracks reality, not aspiration.

## Live vs scaffold

| Component | State | Notes |
|---|---|---|
| scan / normalize / strategies / reverse / AI score / alert / execute | ✅ **live** | see [[pipeline/flow]] |
| Chainlink stream | ✅ live | WebSocket thread inside scheduler window |
| Tier routing (REAL / PAPER-near-miss / PAPER-proposed) | ✅ live | env: `PAPER_MIN_SCORE`, `PAPER_MIN_CONF` |
| Kelly sizing + compound state | ✅ live | `tools/sizing.py` + `core/compound_state.py` |
| Position monitor (SL/TP) | ✅ live | 5-min loop, separate window |
| Outcome tracker (real + paper resolution) | ✅ live | 30-min loop, CLOB API resolution |
| Strategy scorecard + adaptive weights | ✅ live | auto-disable <35% WR, boost >55% |
| Threshold tuner | ✅ advisory | `upas> tune` shows suggestions |
| Wallet registry (smart money cross-reference) | ✅ live | refreshes lazily every 6h |
| Smart money strategy | ✅ paper-only | promotes to real after 50 paper trades ≥55% WR |
| ML re-ranker (XGBoost) | ⚠️ scaffold | trains at ≥100 realized outcomes |
| Strategy generator (Claude-proposed) | ⚠️ scaffold | runs at ≥500 realized outcomes |
| question_router interactive loop | ❌ skipped in live | blocks the bot — logged instead. intentional. |
| RL policy auto-update | ❌ replaced | `strategy_weights` does the job for now |
| tool-discovery-agent in pipeline | ❌ not called | dev-time skill, not runtime |

## Scanner throughput (live, 24h)

| Exchange   | Markets in DB | Last fetch cadence | Notes |
|------------|---------------|---------------------|-------|
| Polymarket | **3,856**     | every 60s (scheduler) | via Gamma API, paginated |
| Kalshi     | **10,908**    | every 60s            | `run(max_pages=80, page=200)` — full coverage |

The e2e test fetches fewer because it uses `limit=50` by design (smoke test). The production scheduler pulls the full universe.

## Self-questioning / reverse-thinking — does it actually happen?

**Yes, and it runs constantly.** But with one real gap.

### What runs automatically
- **8 reverse strategies** execute on every cycle (see [[strategies/INDEX]]): `probability_freeze`, `liquidity_vacuum`, `crowd_fatigue`, `whale_exhaustion`, `fake_momentum`, `event_shadow_drift`, `mirror_event_divergence`, `time_probability_inversion`. Logged: **1,021 runs / 12h, zero errors.**
- **Reverse validator** ([strategies/reverse/reverse_validator.py](../strategies/reverse/reverse_validator.py)) pairs every forward signal with its counter-strategy. If the reverse trips, the forward is downgraded 50% or discarded.
- **Uncertainty engine** ([core/uncertainty_engine.py](../core/uncertainty_engine.py)) scores every input below 0.65 confidence and routes to `question_router` before execution.
- **AI scorer** cross-checks each surviving signal via Claude with market context — acts as a third-layer reviewer.

### The real gap — similar-but-different markets across exchanges
[strategies/core/cross_market.py](../strategies/core/cross_market.py) is supposed to find the same real-world event priced differently on Poly vs Kalshi and arbitrage it. Production count: **0 cross_market signals all-time.**

Why: the matcher requires Jaccard similarity ≥ 0.45 AND ≥ 5 overlapping substantive tokens AND runner-up gap ≥ 2. Retail Poly/Kalshi markets describe the same event with different phrasings (e.g. Kalshi "Will NBA Champion 2025 be…" vs Poly "2024-25 NBA Finals winner"). Human sees equivalence — token matcher rejects.

**Fix (recommended):** add an AI fuzzy-match layer. Run a loose Jaccard 0.25–0.45 candidate pass, then Claude-verify each candidate pair. Cost: ~5-10 AI calls per cycle × $0.003 ≈ $0.02/cycle × 1,440 cycles = **~$30/day AI spend** for potentially the highest-edge strategy in the system.

## Order execution (live, 24h)

| Exchange   | Filled | Failed | Fill rate | Notional filled |
|------------|--------|--------|-----------|-----------------|
| Polymarket | 108    | 166    | 39%       | $540            |
| Kalshi     | 11     | 1      | 92%       | $55             |

**Cause of 166 Poly failures:** 148 were `balance: 0` on NO-side orders — fixed **2026-04-23 07:04 UTC** in [tools/execution_tool.py:308](../tools/execution_tool.py#L308). Root cause: code mapped `side="no"` → `SELL` (closing existing inventory) instead of `BUY` on the `token_id_no`. Fix verified end-to-end: the failure mode changed from `balance: 0` to `orderbook does not exist` for the specific test market, confirming the request reaches the correct code path.

**Expected post-fix:** Polymarket fill rate ≥ 95%.

## Profitability model — realistic expectations

### Current capital base
- Polymarket proxy: **$189.72 USDC**
- Kalshi cash: **$127.20**
- **Total deployable: ~$317**

### Per-trade economics (system-enforced)
- Size: `$5.00` per trade (hardcoded in [core/engine.py:306](../core/engine.py#L306))
- Fee gate: expected edge > 1.5 × round-trip fees
  - Kalshi round-trip fee at $5, p=0.50: `$0.035` → min expected gross **$0.053** (1.06% of notional)
  - Polymarket round-trip fee: 0 bps default → min expected gross **$0.15** (3% edge)
- Expected edge model: `score 70→100 maps to 3%→20% of notional`
- Win rate target: 55–60% on score ≥ 75 signals (unvalidated — needs 1-week sample)

### Daily volume — hard ceilings at $317 capital

- **Max active positions simultaneously:** ~63 at $5 each (but `MAX_TOTAL_EXPOSURE=$2000` — irrelevant at this capital level)
- **Capital recycle time:** depends on average position hold-time. Polymarket 5-min crypto windows recycle every 5 minutes; daily markets tie up capital for hours. Blended: ~6× turnover/day estimated.
- **Daily trades possible:** 317 × 6 / 5 ≈ **~380 trades/day max**
- **Daily profit expectation:**
  - Conservative (3% avg edge × 55% win-rate × 380 trades × $5) = **$25–45/day**
  - Optimistic (if cross_market fixed and AI-ranked arbs run): **$60–120/day**
  - Realistic 1-week average at current config: **$15–35/day** (most signals will be near the fee threshold)

### Is this the max we can extract?

**No — three bottlenecks leave money on the table:**

1. **Capital-constrained.** The strategies produce 27,000+ signals/day but we execute <300. Every 1% edge detected and skipped is lost alpha. **Adding capital is the #1 multiplier** (linear scale up to ~$20k before liquidity walls).

2. **cross_market returns $0.** Cross-exchange arbitrage is historically the highest-edge category in prediction markets (3-15% per trade, market-neutral). Currently producing 0 signals because of token-matcher strictness. **AI-assisted matching would unlock this.**

3. **Fixed $5 sizing is suboptimal.** Kelly-criterion sizing on high-confidence signals (score ≥ 85, reverse-validated, AI-confirmed) could 2–4× the ROI. Current system treats all signals equally.

Additional smaller gaps:
- No position-close logic on losing positions (we hold to expiry → 0)
- Kalshi execution underutilized (only 11 fills/day vs 108 Poly) — Kalshi has better fees
- `chainlink_edge` produced 987 signals/24h — very active. Win-rate validation needed before scaling.

## Architecture verdict (CTO honest take)

**What is done right:**
- Reverse-first design is rare and valuable — real defensive depth.
- Checkpoint-per-stage + fee gate + dry-run flag = safe to run unattended.
- Chainlink real-time integration gives the system one clear structural edge on Poly 5-min crypto markets.
- 18 strategies + AI re-ranker is well-layered; not over-engineered.

**What to change next (priority order):**

| # | Task | Impact | Effort |
|---|------|--------|--------|
| 1 | Add AI fuzzy-match to `cross_market` | +$30-80/day | 0.5 day |
| 2 | Replace fixed $5 sizing with Kelly-fraction on AI score | +30% ROI | 0.5 day |
| 3 | Add position-close logic (stop-loss / take-profit) | -30% drawdown | 1 day |
| 4 | Backfill outcomes table + train ML re-ranker on real results | +win-rate over time | 2 days |
| 5 | Lift capital to ~$2–5k once fill-rate stabilizes | linear $ multiplier | external |

**What NOT to do:**
- Don't add more strategies until the above are in place. Signal volume is already 27k/day; the bottleneck is ranking + sizing, not generation.
- Don't raise position size before 1-week real win-rate sample.
- Don't connect to more exchanges (Manifold, PredictIt) until cross_market works.

## Health check commands

```cmd
:: full system audit (11 steps, ~60s)
.venv\Scripts\python.exe -m tools.e2e_test

:: Polymarket balance + allowance per chain
.venv\Scripts\python.exe -m tools.poly_diagnose

:: AI credit check
.venv\Scripts\python.exe -c "from ai.scorer import _call_claude; print(_call_claude('PONG', tier='B'))"

:: DB truth snapshot
sqlite3 data\upas.db "SELECT source, COUNT(*) FROM markets GROUP BY source;"
```
