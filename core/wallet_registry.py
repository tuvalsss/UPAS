"""
core/wallet_registry.py
Cross-reference Polymarket whales across multiple time windows (DAY, WEEK,
MONTH, ALL) to filter lucky single-window traders from consistent performers.

A wallet that appears in TOP_N of MONTH is suggestive. A wallet that appears
in TOP_N of both MONTH *and* ALL (and ideally WEEK too) is strong evidence
of durable alpha — not a one-month lottery.

Public, no-auth API:
  https://data-api.polymarket.com/v1/leaderboard

Output: `smart_wallets` table with per-wallet consistency score.
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

from logging_config.structured_logger import get_logger
from tools.database_tool import _conn

logger = get_logger(__name__)

_LB_URL = "https://data-api.polymarket.com/v1/leaderboard"
_WINDOWS = ["DAY", "WEEK", "MONTH", "ALL"]
_LIMIT = int(os.getenv("WALLET_REGISTRY_LIMIT", "100"))
_MIN_PNL = float(os.getenv("WALLET_REGISTRY_MIN_PNL", "10000"))
_MIN_CONSISTENCY = int(os.getenv("WALLET_REGISTRY_MIN_CONSISTENCY", "2"))
_REFRESH_SEC = int(os.getenv("WALLET_REGISTRY_REFRESH_SEC", "21600"))  # 6h


def _ensure_schema():
    with _conn() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS smart_wallets (
                address TEXT PRIMARY KEY,
                name TEXT,
                pnl_day REAL,
                pnl_week REAL,
                pnl_month REAL,
                pnl_all REAL,
                rank_day INTEGER,
                rank_week INTEGER,
                rank_month INTEGER,
                rank_all INTEGER,
                consistency INTEGER NOT NULL DEFAULT 0,
                verified_badge INTEGER NOT NULL DEFAULT 0,
                x_username TEXT,
                last_refreshed TEXT
            )
        """)
        con.commit()


def _fetch_window(window: str) -> list[dict]:
    try:
        r = requests.get(_LB_URL, params={
            "category": "OVERALL", "timePeriod": window, "orderBy": "PNL",
            "limit": _LIMIT,
        }, timeout=15)
        r.raise_for_status()
        return r.json() or []
    except Exception as e:
        logger.warning("wallet_registry.fetch_err",
                       extra={"window": window, "error": str(e)})
        return []


def refresh() -> dict:
    """Pull all 4 windows, compute consistency, upsert smart_wallets."""
    _ensure_schema()
    by_addr: dict[str, dict[str, Any]] = {}
    for w in _WINDOWS:
        entries = _fetch_window(w)
        for i, e in enumerate(entries):
            addr = (e.get("proxyWallet") or "").lower()
            if not addr:
                continue
            pnl = float(e.get("pnl", 0) or 0)
            if pnl < _MIN_PNL:
                continue
            rec = by_addr.setdefault(addr, {
                "address": addr,
                "name": e.get("userName", ""),
                "x_username": e.get("xUsername", ""),
                "verified_badge": 1 if e.get("verifiedBadge") else 0,
                "pnl_day": None, "pnl_week": None,
                "pnl_month": None, "pnl_all": None,
                "rank_day": None, "rank_week": None,
                "rank_month": None, "rank_all": None,
            })
            rec[f"pnl_{w.lower()}"] = pnl
            rec[f"rank_{w.lower()}"] = int(e.get("rank", i + 1))

    now_iso = datetime.now(timezone.utc).isoformat()
    with _conn() as con:
        for rec in by_addr.values():
            windows_hit = sum(1 for w in _WINDOWS if rec.get(f"rank_{w.lower()}") is not None)
            rec["consistency"] = windows_hit
            con.execute("""
                INSERT INTO smart_wallets (
                    address, name, pnl_day, pnl_week, pnl_month, pnl_all,
                    rank_day, rank_week, rank_month, rank_all,
                    consistency, verified_badge, x_username, last_refreshed
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(address) DO UPDATE SET
                    name=excluded.name,
                    pnl_day=excluded.pnl_day, pnl_week=excluded.pnl_week,
                    pnl_month=excluded.pnl_month, pnl_all=excluded.pnl_all,
                    rank_day=excluded.rank_day, rank_week=excluded.rank_week,
                    rank_month=excluded.rank_month, rank_all=excluded.rank_all,
                    consistency=excluded.consistency,
                    verified_badge=excluded.verified_badge,
                    x_username=excluded.x_username,
                    last_refreshed=excluded.last_refreshed
            """, (
                rec["address"], rec["name"],
                rec["pnl_day"], rec["pnl_week"], rec["pnl_month"], rec["pnl_all"],
                rec["rank_day"], rec["rank_week"], rec["rank_month"], rec["rank_all"],
                rec["consistency"], rec["verified_badge"],
                rec["x_username"], now_iso,
            ))
        con.commit()

    summary = {
        "total_wallets": len(by_addr),
        "consistent_wallets": sum(1 for r in by_addr.values()
                                  if r["consistency"] >= _MIN_CONSISTENCY),
        "windows": _WINDOWS,
    }
    logger.info("wallet_registry.refreshed", extra=summary)
    return summary


def get_verified_whales(min_consistency: int | None = None) -> list[dict]:
    """Return wallets present in >= min_consistency windows (default from env)."""
    _ensure_schema()
    min_c = min_consistency if min_consistency is not None else _MIN_CONSISTENCY
    with _conn() as con:
        rows = con.execute("""
            SELECT address, name, x_username, consistency,
                   pnl_day, pnl_week, pnl_month, pnl_all,
                   rank_day, rank_week, rank_month, rank_all,
                   verified_badge, last_refreshed
            FROM smart_wallets WHERE consistency >= ?
            ORDER BY consistency DESC,
                     COALESCE(pnl_all, pnl_month, pnl_week, pnl_day, 0) DESC
        """, (min_c,)).fetchall()
    return [{
        "address": r[0], "name": r[1], "x_username": r[2],
        "consistency": r[3],
        "pnl_day": r[4], "pnl_week": r[5], "pnl_month": r[6], "pnl_all": r[7],
        "rank_day": r[8], "rank_week": r[9], "rank_month": r[10], "rank_all": r[11],
        "verified_badge": bool(r[12]), "last_refreshed": r[13],
    } for r in rows]


def stale(max_age_sec: int = _REFRESH_SEC) -> bool:
    """True if the latest snapshot is older than max_age_sec."""
    _ensure_schema()
    with _conn() as con:
        r = con.execute(
            "SELECT MAX(last_refreshed) FROM smart_wallets"
        ).fetchone()
    ts = r[0] if r else None
    if not ts:
        return True
    try:
        age = (datetime.now(timezone.utc) -
               datetime.fromisoformat(ts)).total_seconds()
        return age > max_age_sec
    except Exception:
        return True


if __name__ == "__main__":
    import json
    print(json.dumps(refresh(), indent=2))
    print()
    whales = get_verified_whales(min_consistency=2)
    print(f"Consistent whales (>=2 windows): {len(whales)}")
    for w in whales[:10]:
        cons = w["consistency"]
        mark = "[" + "*" * cons + "]"
        print(f"  {mark:6s} {w['name'][:25]:25s} cons={cons}/4 "
              f"pnl_all=${w['pnl_all'] or 0:>12,.0f} {w['address']}")
