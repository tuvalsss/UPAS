# Smart Money (Copy-Trade Whales) — Polymarket Only

Proposed strategy at [strategies/proposed/smart_money.py](../../strategies/proposed/smart_money.py). **Not yet wired** to the core pipeline. Needs human review + paper-trade validation before promotion to `strategies/core/`.

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

## Promotion checklist

Do NOT move to `strategies/core/` until:

1. ✅ Run `python -m strategies.proposed.smart_money` and verify ≥1 live cluster.
2. ⏳ Wire temporarily in DRY_RUN mode, collect 50+ signals.
3. ⏳ After those 50 signals resolve, check win rate in scorecard ≥55%.
4. ⏳ Add `"smart_money"` to `tools/strategy_tool._CORE_STRATEGIES`.
5. ⏳ Update this doc → move to `docs/strategies/core/smart-money.md`.

## Risks

- **Leaderboard is latency-lagged** — whales may have already sold by the time we see their position.
- **Wash trading** — some leaderboard "whales" self-trade to inflate PnL. The `_MIN_PNL=10000` threshold filters only trivially, not against sophisticated wash. Sharpe ratio over time would be a better filter (future upgrade).
- **Overcrowding** — if >5 whales pile on one side, we may be the LAST one in. Consider adding a reverse rule: "if ≥7 whales on one side, reverse the signal (take the other side)".
- **Market manipulation** — large bettors can move prices against us even when "correct" in the long run. Always use Kelly sizing, never all-in.
