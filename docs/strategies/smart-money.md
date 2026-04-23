# Smart Money (Copy-Trade Whales) — Polymarket Only

Strategy at [strategies/core/smart_money.py](../../strategies/core/smart_money.py) (origin at [strategies/proposed/smart_money.py](../../strategies/proposed/smart_money.py)).

**Currently running in PAPER-TRADE mode.** Signals are generated, logged, and resolved by `outcome_tracker` — but `engine.py` skips real order placement because `smart_money` is listed in `tools/strategy_tool._PAPER_STRATEGIES`. Real capital is untouched.

Paper results appear in `scorecard` under "Paper Trades (no real money)". Promote to real trading by removing `smart_money` from `_PAPER_STRATEGIES` once win rate ≥55% over ≥50 paper trades.

## Hypothesis

Accounts with sustained high ROI know something the market hasn't priced in. When **≥3 top-50-ranked wallets independently hold the same side of the same market**, that's a concentrated smart-money signal orthogonal to anything our other strategies detect.

## Data sources (all free, public, no auth)

### 1. Polymarket official leaderboard — primary
```
GET https://data-api.polymarket.com/v1/leaderboard
  ?category=OVERALL          # or POLITICS, SPORTS, CRYPTO, CULTURE, WEATHER, ECONOMICS, TECH, FINANCE, MENTIONS
  &timePeriod=MONTH          # or DAY, WEEK, ALL
  &orderBy=PNL               # or VOL
  &limit=50                  # max 50
```
Returns: `[{rank, proxyWallet, userName, xUsername, pnl, vol, verifiedBadge, profileImage}]`

**Critical**: `proxyWallet` is the trading address (Gnosis Safe). The user's EOA/MetaMask address shows **zero trades** — always use `proxyWallet`.

Test it live:
```bash
curl "https://data-api.polymarket.com/v1/leaderboard?category=OVERALL&timePeriod=MONTH&orderBy=PNL&limit=10"
```

### 2. Polymarket positions — per wallet
```
GET https://data-api.polymarket.com/positions?user=<proxyWallet>&sizeThreshold=0
```
Returns list of `{conditionId, outcome, size, currentValue, avgPrice, ...}` for that wallet's open positions. Already used by UPAS via `tools/account_tool.py`.

### 3. Kalshi — **no public whale data**
Kalshi does not expose per-user trades. There is no leaderboard, no wallet addresses (not on-chain). Smart-money strategy is Polymarket-only.

## Other free tools worth knowing

| Tool | URL | Purpose | Free tier |
|---|---|---|---|
| **Polywhaler** | polywhaler.com | Real-time $10k+ trade feed, AI predictions, market sentiment | ✅ free tier, upgrade for alerts |
| **PolymarketScan** | polymarketscan.org | Full REST API: leaderboard, whale_trades, market_whales, wallet_profile, deposits, etc. | ✅ free forever, 30 req/min |
| **Polytrackerbot** | Twitter/X bot | Passive feed of big trades | ✅ fully free |
| **Unusual Predictions** | unusualwhales.com/predictions | Prediction market section of Unusual Whales | ⚠️ freemium |
| **Whale Tracker Livid** | - | Free tier with 1-hour delay | ✅ free tier |
| **pm.wiki** | pm.wiki/learn/best-polymarket-whale-trackers | Comparison of all 7 trackers | ℹ️ reference only |
| **laikalabs.ai** | laikalabs.ai/prediction-markets/how-to-track-polymarket-wallets | How-to guide for wallet tracking | ℹ️ reference |
| **GitHub: al1enjesus/polymarket-whales** | github.com/al1enjesus/polymarket-whales | Open-source real-time whale tracker with Telegram alerts | ✅ MIT, self-host |

### PolymarketScan API highlights
Free alternate data source — useful as backup or for richer endpoints:
- `?endpoint=leaderboard&limit=25`
- `?endpoint=whale_trades&limit=10`
- `?endpoint=market_whales&market_slug=<slug>&min_size=5000&limit=20`
- `?endpoint=wallet_profile&wallet=<addr>`
- `?endpoint=wallet_pnl&wallet=<addr>`

Base URL: `https://gzydspfquuaudqeztorw.supabase.co/functions/v1/public-api`
Auth: `api_key` query param or `x-api-key` header. Request a key at polymarketscan.org.

## Wallet cross-reference (`core/wallet_registry.py`)

Before a wallet qualifies as "smart money", it is cross-referenced across **all four Polymarket leaderboard windows** (DAY, WEEK, MONTH, ALL). Only wallets that appear in the top-100 of at least 2 windows count. This filters one-week luck from durable alpha.

`smart_wallets` table columns: `address, name, x_username, pnl_{day,week,month,all}, rank_{day,week,month,all}, consistency (1-4), verified_badge, last_refreshed`.

Refreshed every 6 hours by `smart_money.detect()`. Override via `WALLET_REGISTRY_REFRESH_SEC`, `WALLET_REGISTRY_MIN_PNL`, `WALLET_REGISTRY_MIN_CONSISTENCY`.

Inspect live:
```bash
python -m core.wallet_registry
```
Example output from a recent run: 127 raw whales → 51 verified (≥2 windows) → 3 hall-of-fame (all 4 windows): RN1 ($7.4M), 0x2a2C53 ($3.1M), gatorr ($2.1M).

## UPAS strategy logic

Cached leaderboard (refresh every 6h), per-market clustering detection, score = 70 + 5*(whales_over_min) + rank_bonus. Environment tunables:

```
SMART_MONEY_LB_LIMIT=50        # how deep into leaderboard to look
SMART_MONEY_WINDOW=MONTH       # DAY|WEEK|MONTH|ALL
SMART_MONEY_REFRESH_SEC=21600  # 6h leaderboard cache
SMART_MONEY_MIN_PNL=10000      # min wallet PnL to count as "whale"
SMART_MONEY_MIN_WHALES=3       # clustering threshold
SMART_MONEY_MIN_POS_USD=500    # ignore whale dust
```

## Paper → Real promotion checklist

1. ✅ Wallet registry populated (≥50 consistent whales across windows).
2. ✅ Wired in `_CORE_STRATEGIES` under `_PAPER_STRATEGIES` — signals generated, orders virtualised.
3. ⏳ Wait for ≥50 paper signals to resolve in `results` table (where `paper_trade=1`).
4. ⏳ Check `scorecard` paper row: win rate ≥55%, avg PnL positive.
5. ⏳ Remove `"smart_money"` from `_PAPER_STRATEGIES` (keep in `_CORE_STRATEGIES`).
6. ⏳ Move this file to `docs/strategies/core/smart-money.md`.

## Risks

- **Leaderboard is latency-lagged** — whales may have already sold by the time we see their position.
- **Wash trading** — some leaderboard "whales" self-trade to inflate PnL. The `_MIN_PNL=10000` threshold filters only trivially, not against sophisticated wash. Sharpe ratio over time would be a better filter (future upgrade).
- **Overcrowding** — if >5 whales pile on one side, we may be the LAST one in. Consider adding a reverse rule: "if ≥7 whales on one side, reverse the signal (take the other side)".
- **Market manipulation** — large bettors can move prices against us even when "correct" in the long run. Always use Kelly sizing, never all-in.
