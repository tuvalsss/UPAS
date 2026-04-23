"""
core/strategy_weights.py
Adaptive per-strategy weight + enable/disable layer.

Refreshed by update_weights() (called by outcome_tracker after each pass).

Rules (env-tunable):
  n >= AUTO_DISABLE_MIN_N (50) and win_rate < AUTO_DISABLE_WR (0.35):
      -> enabled=0 (strategy stops firing)
  n >= BOOST_MIN_N (30) and win_rate > BOOST_WR (0.55):
      -> weight = BOOST_WEIGHT (1.3)
  otherwise:
      -> enabled=1, weight=1.0

strategy_tool reads is_enabled() before running; engine reads get_weight() to
multiply signal scores (higher weight = bigger bet via Kelly edge scaling).

The strategy_weights table is created/extended by outcome_tracker._ensure_schema.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from functools import lru_cache

from logging_config.structured_logger import get_logger
from tools.database_tool import _conn

logger = get_logger(__name__)

_AUTO_DISABLE_MIN_N = int(os.getenv("AUTO_DISABLE_MIN_N", "50"))
_AUTO_DISABLE_WR = float(os.getenv("AUTO_DISABLE_WR", "0.35"))
_BOOST_MIN_N = int(os.getenv("BOOST_MIN_N", "30"))
_BOOST_WR = float(os.getenv("BOOST_WR", "0.55"))
_BOOST_WEIGHT = float(os.getenv("BOOST_WEIGHT", "1.3"))
_CACHE_TTL = 60  # seconds

_cache = {"ts": 0.0, "weights": {}, "enabled": {}}


def _load_from_db() -> tuple[dict, dict]:
    with _conn() as con:
        rows = con.execute(
            "SELECT strategy, weight, enabled FROM strategy_weights"
        ).fetchall()
    weights = {r[0]: float(r[1] or 1.0) for r in rows}
    enabled = {r[0]: bool(r[2]) for r in rows}
    return weights, enabled


def _refresh_cache():
    now = time.time()
    if now - _cache["ts"] < _CACHE_TTL:
        return
    try:
        w, e = _load_from_db()
        _cache["weights"], _cache["enabled"] = w, e
        _cache["ts"] = now
    except Exception:
        # leave stale cache
        pass


def get_weight(strategy: str) -> float:
    _refresh_cache()
    return _cache["weights"].get(strategy, 1.0)


def is_enabled(strategy: str) -> bool:
    _refresh_cache()
    # Default True if unknown (don't block new strategies)
    return _cache["enabled"].get(strategy, True)


def update_weights() -> dict:
    """
    Recompute all strategy weights from `results`. Writes to strategy_weights table.
    Returns summary.
    """
    from core.strategy_scorecard import scorecard
    cards = scorecard()
    disabled_now, boosted_now, neutral_now = [], [], []
    now_iso = datetime.now(timezone.utc).isoformat()

    with _conn() as con:
        for c in cards:
            strategy = c["strategy"]
            n = c["n"]
            wr = c["win_rate"]
            wins = c["wins"]
            losses = c["losses"]
            total_pnl = c["total_pnl_usd"]

            if n >= _AUTO_DISABLE_MIN_N and wr < _AUTO_DISABLE_WR:
                weight, enabled = 1.0, 0
                disabled_now.append(strategy)
            elif n >= _BOOST_MIN_N and wr > _BOOST_WR:
                weight, enabled = _BOOST_WEIGHT, 1
                boosted_now.append(strategy)
            else:
                weight, enabled = 1.0, 1
                neutral_now.append(strategy)

            con.execute("""
                INSERT INTO strategy_weights
                  (strategy, weight, enabled, wins, losses, total_pnl_usd, total_trades, updated_at)
                VALUES (?,?,?,?,?,?,?,?)
                ON CONFLICT(strategy) DO UPDATE SET
                  weight=excluded.weight,
                  enabled=excluded.enabled,
                  wins=excluded.wins,
                  losses=excluded.losses,
                  total_pnl_usd=excluded.total_pnl_usd,
                  total_trades=excluded.total_trades,
                  updated_at=excluded.updated_at
            """, (strategy, weight, enabled, wins, losses, total_pnl, n, now_iso))
        con.commit()

    # Invalidate cache
    _cache["ts"] = 0.0
    summary = {
        "disabled": disabled_now,
        "boosted": boosted_now,
        "neutral": neutral_now,
        "total_strategies": len(cards),
    }
    logger.info("strategy_weights.updated", extra=summary)
    return summary


def list_all() -> list[dict]:
    """For CLI display."""
    with _conn() as con:
        rows = con.execute("""
            SELECT strategy, weight, enabled, wins, losses, total_pnl_usd, total_trades, updated_at
            FROM strategy_weights ORDER BY total_pnl_usd DESC
        """).fetchall()
    return [{
        "strategy": r[0], "weight": r[1], "enabled": bool(r[2]),
        "wins": r[3], "losses": r[4], "total_pnl_usd": r[5],
        "total_trades": r[6], "updated_at": r[7],
    } for r in rows]


if __name__ == "__main__":
    import json
    print(json.dumps(update_weights(), indent=2))
    print()
    for w in list_all():
        mark = "DISABLED" if not w["enabled"] else (f"BOOST×{w['weight']}" if w["weight"] > 1.0 else "normal")
        print(f"  {w['strategy']:30s} {mark:12s} n={w['total_trades']:4d} "
              f"W={w['wins']}/L={w['losses']} pnl={w['total_pnl_usd']:+.2f}")
