"""
strategies/proposed/smart_money.py
Copy-the-whale strategy for Polymarket.

STATUS: PROPOSED — NOT WIRED. Move to strategies/core/ only after:
  1. Human review of logic + thresholds.
  2. Paper-trade validation over >=50 candidate signals.
  3. Addition to tools/strategy_tool._CORE_STRATEGIES when satisfied.

Hypothesis: accounts with sustained high ROI know something the market hasn't
priced in. Finding a market where >=N top-ranked wallets hold on the same
side is a concentrated smart-money signal that is orthogonal to our existing
strategies (yes_no_imbalance, liquidity_shift, etc.).

Data sources (free, public, no auth):
  - Leaderboard: https://data-api.polymarket.com/v1/leaderboard
      params: category, timePeriod (DAY|WEEK|MONTH|ALL), orderBy (PNL|VOL), limit
  - Positions:   https://data-api.polymarket.com/positions?user=<proxyWallet>
      returns: list of {conditionId, outcome, size, value_usd, ...}

IMPORTANT:
  - Polymarket users trade via a PROXY wallet (Gnosis Safe), not their EOA.
    Leaderboard returns `proxyWallet` — use that address for positions lookup.
  - A single whale on one side proves nothing. Look for CLUSTERING: >=3 top-50
    wallets independently on the same side of the same market.
"""
from __future__ import annotations

import os
import time
from typing import Any

import requests

from logging_config.structured_logger import get_logger
from strategies.base import BaseStrategy, Signal

logger = get_logger(__name__)

_LB_URL = "https://data-api.polymarket.com/v1/leaderboard"
_POS_URL = "https://data-api.polymarket.com/positions"

_LB_LIMIT = int(os.getenv("SMART_MONEY_LB_LIMIT", "50"))
_LB_WINDOW = os.getenv("SMART_MONEY_WINDOW", "MONTH")  # DAY|WEEK|MONTH|ALL
_LB_REFRESH_SEC = int(os.getenv("SMART_MONEY_REFRESH_SEC", "21600"))  # 6h
_MIN_PNL = float(os.getenv("SMART_MONEY_MIN_PNL", "10000"))   # min $10k lifetime PnL
_MIN_WHALES = int(os.getenv("SMART_MONEY_MIN_WHALES", "3"))
_MIN_WHALE_POS_USD = float(os.getenv("SMART_MONEY_MIN_POS_USD", "500"))
_TIMEOUT = 15

# Cached leaderboard snapshot (module-level — survives multiple detect() calls)
_cache: dict[str, Any] = {"ts": 0.0, "wallets": []}


def _fetch_leaderboard() -> list[dict]:
    """
    Return list of VERIFIED top wallets from wallet_registry (cross-window).
    Only wallets present in >= SMART_MONEY_MIN_CONSISTENCY leaderboard windows
    (DAY/WEEK/MONTH/ALL) qualify — filters out one-week lucky streaks.
    """
    from core import wallet_registry
    if wallet_registry.stale():
        try:
            wallet_registry.refresh()
        except Exception as e:
            logger.warning("smart_money.registry_refresh_err",
                           extra={"error": str(e)})

    min_cons = int(os.getenv("SMART_MONEY_MIN_CONSISTENCY", "2"))
    whales = wallet_registry.get_verified_whales(min_consistency=min_cons)
    wallets = [{
        "address": w["address"], "name": w["name"],
        "pnl": w.get("pnl_all") or w.get("pnl_month") or 0,
        "rank": w.get("rank_month") or w.get("rank_all") or 999,
        "consistency": w["consistency"],
    } for w in whales]
    logger.info("smart_money.leaderboard_loaded",
                extra={"n": len(wallets), "min_consistency": min_cons})
    return wallets


def _fetch_whale_positions(address: str) -> list[dict]:
    """Fetch open positions for a single whale wallet."""
    try:
        r = requests.get(
            _POS_URL,
            params={"user": address, "sizeThreshold": "0"},
            timeout=_TIMEOUT,
        )
        if r.status_code != 200:
            return []
        return r.json() or []
    except Exception:
        return []


def _index_whale_positions(wallets: list[dict]) -> dict[str, list[dict]]:
    """
    Build {condition_id+outcome: [whale_entry, ...]}
    Each whale_entry = {address, name, rank, pnl, size, value_usd, outcome}
    """
    idx: dict[str, list[dict]] = {}
    for w in wallets:
        positions = _fetch_whale_positions(w["address"])
        for p in positions:
            cid = p.get("conditionId", p.get("condition_id", ""))
            outcome = p.get("outcome", "")
            value_usd = float(p.get("currentValue", p.get("value_usd", 0)) or 0)
            if not cid or not outcome or value_usd < _MIN_WHALE_POS_USD:
                continue
            key = f"{cid}::{outcome}"
            idx.setdefault(key, []).append({
                "address": w["address"], "name": w["name"],
                "rank": w["rank"], "pnl": w["pnl"],
                "size": float(p.get("size", 0) or 0),
                "value_usd": value_usd, "outcome": outcome,
            })
    return idx


class SmartMoney(BaseStrategy):
    name = "smart_money"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        poly = [m for m in markets if m.get("source") == "polymarket"]
        if not poly:
            return []

        wallets = _fetch_leaderboard()
        if len(wallets) < _MIN_WHALES:
            return []

        # Build a lookup from condition_id -> market dict we have
        # (Polymarket market_id in our DB is stored as condition_id hex)
        by_cid = {m.get("market_id", "").lower(): m for m in poly}

        idx = _index_whale_positions(wallets)
        signals: list[Signal] = []

        for key, holders in idx.items():
            if len(holders) < _MIN_WHALES:
                continue
            cid, outcome = key.split("::", 1)
            cid = cid.lower()
            m = by_cid.get(cid)
            if m is None:
                continue  # we don't track this market

            side = "yes" if outcome.lower() in ("yes", "up", "over", "long") else "no"
            yes_price = float(m.get("yes_price", 0) or 0)
            if not (0.03 <= yes_price <= 0.97):
                continue

            total_whale_exposure = sum(h["value_usd"] for h in holders)
            avg_rank = sum(h["rank"] for h in holders) / len(holders)
            top_name = min(holders, key=lambda h: h["rank"])["name"]

            # Score: more whales = higher conviction. Cap at 95 so AI scorer
            # still has headroom to push 95→100 on strongest setups.
            base = 70 + min(20, (len(holders) - _MIN_WHALES) * 5)
            rank_bonus = max(0, 10 - avg_rank / 10)
            score = min(95.0, base + rank_bonus)

            confidence = min(0.90, 0.55 + len(holders) * 0.05 +
                             (1 if total_whale_exposure > 10_000 else 0) * 0.1)

            reasoning = (
                f"SMART-MONEY: {len(holders)} top-{_LB_LIMIT} wallets on {outcome} "
                f"(total exposure ${total_whale_exposure:,.0f}, avg rank {avg_rank:.0f}, "
                f"lead: {top_name}). Market yes_price={yes_price:.3f}."
            )
            signals.append(self._make_signal(
                m["market_id"], score, confidence, reasoning, f"BUY {side.upper()}"
            ))

        logger.info("smart_money.run", extra={
            "wallets_tracked": len(wallets),
            "markets_with_clusters": len(signals),
        })
        return signals


_strategy = SmartMoney()


def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]


if __name__ == "__main__":
    # Diagnostic: show top wallets + any active clusters
    import json
    wl = _fetch_leaderboard()
    print(f"Tracking {len(wl)} whales (pnl >= ${_MIN_PNL})")
    print("Top 5:")
    for w in wl[:5]:
        print(f"  rank={w['rank']:3d} {w['name'][:25]:25s} pnl=${w['pnl']:>12,.0f} {w['address']}")
    print()
    idx = _index_whale_positions(wl[:10])  # limit to 10 whales for diagnostic
    clusters = {k: v for k, v in idx.items() if len(v) >= _MIN_WHALES}
    print(f"Markets with {_MIN_WHALES}+ whales: {len(clusters)}")
    for key, holders in list(clusters.items())[:5]:
        cid, outcome = key.split("::", 1)
        total = sum(h["value_usd"] for h in holders)
        print(f"  {cid[:20]}... {outcome}: {len(holders)} whales, ${total:,.0f} total")
