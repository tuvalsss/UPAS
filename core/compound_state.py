"""
core/compound_state.py
Auto-compound adjustment for position sizing.

Logic:
  base_max = MAX_SINGLE_TRADE_USD (env, default $25)
  realized_profit = sum of PnL from filled sell orders minus filled buy orders (net)
  bump_unit = COMPOUND_BUMP_USD (default $5)
  bump_trigger = COMPOUND_BUMP_PER_USD (default $50)
  adjusted_max = base_max + floor(realized_profit / bump_trigger) * bump_unit
  capped at COMPOUND_MAX_ADJUSTED (default $60)

Called from tools/sizing.py to get the current per-trade cap.
"""
from __future__ import annotations

import os
from functools import lru_cache
import time

_BASE = float(os.getenv("MAX_SINGLE_TRADE_USD", "25"))
_BUMP = float(os.getenv("COMPOUND_BUMP_USD", "5"))
_TRIGGER = float(os.getenv("COMPOUND_BUMP_PER_USD", "50"))
_CAP = float(os.getenv("COMPOUND_MAX_ADJUSTED", "60"))
_TTL_SEC = 60  # recompute at most once/minute


def _realized_profit_usd() -> float:
    """Sum of (filled SELL size) minus (filled BUY size), best-effort over last 30 days."""
    try:
        from tools.database_tool import _conn
        with _conn() as con:
            r = con.execute("""
                SELECT
                  COALESCE(SUM(CASE WHEN LOWER(side) IN ('sell','close') THEN size_usd ELSE 0 END), 0) -
                  COALESCE(SUM(CASE WHEN LOWER(side) IN ('yes','no','buy') THEN size_usd ELSE 0 END), 0)
                FROM orders
                WHERE dry_run=0 AND status='filled'
                  AND timestamp>=datetime('now','-30 day')
            """).fetchone()
        return float(r[0] or 0)
    except Exception:
        return 0.0


_last = {"ts": 0.0, "value": _BASE}


def current_max_single_trade_usd() -> float:
    """Return compounded per-trade cap. Caches for 60s to avoid hitting DB per signal."""
    now = time.time()
    if now - _last["ts"] < _TTL_SEC:
        return _last["value"]
    try:
        realized = _realized_profit_usd()
        bumps = max(0, int(realized // _TRIGGER))
        adjusted = min(_CAP, _BASE + bumps * _BUMP)
    except Exception:
        adjusted = _BASE
    _last["ts"] = now
    _last["value"] = adjusted
    return adjusted


if __name__ == "__main__":
    print(f"base=${_BASE} bump=${_BUMP}/${_TRIGGER} cap=${_CAP}")
    print(f"realized_profit=${_realized_profit_usd():.2f}")
    print(f"current_max_single_trade=${current_max_single_trade_usd():.2f}")
