"""
tools/sizing.py
Kelly-fraction position sizing for UPAS.

Replaces hardcoded $5 with a dynamic size based on:
  - Signal score (70..100 -> expected edge 3%..20%)
  - AI confidence (0..1)
  - Available equity in the specific exchange
  - Fractional Kelly (default 0.25 — quarter-Kelly for safety)

Hard safety caps (tightest wins):
  - Exchange floor (Polymarket $5)
  - Per-trade cap (MAX_SINGLE_TRADE_USD, env)
  - Per-trade equity fraction (MAX_TRADE_EQUITY_PCT, default 8%)
  - Total open-exposure cap across exchanges (MAX_TOTAL_EXPOSURE_USD, env)

All outputs rounded to nearest $0.50, floored at exchange minimum.
"""
from __future__ import annotations

import os
from typing import Literal

# Read once at import; env can override
_KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.25"))
_MAX_TRADE_EQUITY_PCT = float(os.getenv("MAX_TRADE_EQUITY_PCT", "0.08"))
_MAX_SINGLE_TRADE_USD_BASE = float(os.getenv("MAX_SINGLE_TRADE_USD", "25"))
_MIN_SIZE_USD_POLY = 5.0   # Polymarket hard floor
_MIN_SIZE_USD_KALSHI = 1.0 # Kalshi accepts 1c minimums


def _expected_edge(score: float, ai_confidence: float) -> float:
    """Map (score, confidence) -> expected edge as fraction of notional.
    score 70..100 -> 3%..20% base; then scaled by confidence (0.5..1.0 range).
    """
    base = max(0.0, min(0.20, (score - 70.0) / 30.0 * 0.17 + 0.03))
    # confidence 0.5 = neutral, <0.5 downweights, >0.5 boosts up to 1.2x
    conf_mult = 0.6 + 0.8 * max(0.0, min(1.0, ai_confidence))  # 0.6..1.4
    return base * conf_mult


def kelly_size_usd(
    *,
    exchange: Literal["polymarket", "kalshi"],
    price: float,
    score: float,
    ai_confidence: float,
    equity_usd: float,
    open_exposure_usd: float = 0.0,
    max_total_exposure_usd: float = 2000.0,
) -> dict:
    """
    Compute position size for one order.

    Kelly formula for binary bets at price p with edge e:
        f* = (e / (1 - p))           if buying at p  (you risk 100%, win 1/p-1)
    We use fractional Kelly (25% default) to control variance.

    Returns { size_usd, reason, inputs } — size_usd=0 if below threshold.
    """
    if not (0.02 <= price <= 0.98):
        return {"size_usd": 0.0, "reason": f"price {price} out of range", "inputs": locals()}
    if equity_usd <= 0:
        return {"size_usd": 0.0, "reason": "no equity", "inputs": locals()}

    edge = _expected_edge(score, ai_confidence)
    if edge <= 0:
        return {"size_usd": 0.0, "reason": "edge<=0", "inputs": locals()}

    # Kelly fraction of equity to deploy
    # Buying YES at p: win pays (1-p)/p, lose pays -1. With edge e over fair price:
    # Kelly f* = edge / (1-p), clamped to [0, 1]
    kelly_full = min(1.0, edge / max(0.01, 1.0 - price))
    kelly_applied = kelly_full * _KELLY_FRACTION

    # Start with Kelly fraction of equity
    size = equity_usd * kelly_applied

    # Caps (tightest wins) — cap_single is compound-adjusted from realized profit
    cap_equity = equity_usd * _MAX_TRADE_EQUITY_PCT
    try:
        from core.compound_state import current_max_single_trade_usd
        cap_single = current_max_single_trade_usd()
    except Exception:
        cap_single = _MAX_SINGLE_TRADE_USD_BASE
    cap_exposure = max(0.0, max_total_exposure_usd - open_exposure_usd)

    size_capped = min(size, cap_equity, cap_single, cap_exposure)

    # Exchange minimum floor
    floor = _MIN_SIZE_USD_POLY if exchange == "polymarket" else _MIN_SIZE_USD_KALSHI
    if size_capped < floor:
        # If the Kelly calc is too small to meet floor, only trade if we'd still
        # cap at <=1.5x floor (very small edge — skip instead of oversizing)
        if size_capped < floor * 0.7:
            return {"size_usd": 0.0, "reason": f"kelly ${size_capped:.2f} < floor ${floor}",
                    "inputs": {"edge": round(edge, 4), "kelly_full": round(kelly_full, 4),
                               "kelly_applied": round(kelly_applied, 4),
                               "cap_equity": round(cap_equity, 2), "cap_single": cap_single}}
        size_capped = floor  # bump to floor — borderline case worth one floor-size shot

    # Round to nearest $0.50 for clean ticket sizes
    size_rounded = round(size_capped * 2) / 2
    size_rounded = max(floor, size_rounded)

    return {
        "size_usd": size_rounded,
        "reason": "ok",
        "inputs": {
            "edge": round(edge, 4),
            "kelly_full": round(kelly_full, 4),
            "kelly_applied": round(kelly_applied, 4),
            "cap_equity": round(cap_equity, 2),
            "cap_single": cap_single,
            "cap_exposure": round(cap_exposure, 2),
            "floor": floor,
        },
    }
