"""
core/outcome_tracker.py
Closes the learning loop by detecting resolved positions and recording
per-order realized PnL + win/loss into the `results` table.

Detection (Polymarket only for now — Kalshi closer parity later):
  1. Pull current positions via data-api (positions with redeemable=True and
     value=0 are LOSERS; positions that no longer appear for a previously
     held token_id have been REDEEMED as WINNERS).
  2. Cross-reference against orders in the DB that have no matching result yet.
  3. Write (signal_id, market_id, strategy, side, entry_price, final_price,
     size_usd, pnl_usd, won) to `results`.

Runs every OUTCOME_TRACK_INTERVAL_SEC (default 1800 = 30 min).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from logging_config.structured_logger import get_logger
from tools.account_tool import get_polymarket_positions
from tools.database_tool import _conn

logger = get_logger(__name__)

_INTERVAL = int(os.getenv("OUTCOME_TRACK_INTERVAL_SEC", "1800"))
_MIN_AGE_MIN = int(os.getenv("OUTCOME_MIN_AGE_MIN", "10"))  # don't judge orders < 10 min old


def _ensure_schema():
    """Add missing result columns and create strategy_weights table if absent."""
    with _conn() as con:
        # Extend results table (idempotent)
        existing = {r[1] for r in con.execute("PRAGMA table_info(results)").fetchall()}
        for col, typ in [
            ("strategy_name", "TEXT"),
            ("side", "TEXT"),
            ("entry_price", "REAL"),
            ("final_price", "REAL"),
            ("size_usd", "REAL"),
            ("pnl_usd", "REAL"),
            ("won", "INTEGER"),
            ("source", "TEXT"),
            ("token_id", "TEXT"),
            ("paper_trade", "INTEGER"),
        ]:
            if col not in existing:
                con.execute(f"ALTER TABLE results ADD COLUMN {col} {typ}")

        con.execute("""
            CREATE TABLE IF NOT EXISTS strategy_weights (
                strategy TEXT PRIMARY KEY,
                weight REAL NOT NULL DEFAULT 1.0,
                enabled INTEGER NOT NULL DEFAULT 1,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                total_pnl_usd REAL NOT NULL DEFAULT 0,
                total_trades INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT
            )
        """)
        con.commit()


def _resolve_outcome(condition_id: str, side: str) -> str | None:
    """
    Query Polymarket CLOB for market status by condition_id (hex).
    side: 'yes' / 'no' / 'buy' (engine.execute buys YES when sig.direction=forward, NO when=reverse)

    Returns 'win' | 'loss' | None (unresolved / unknown).
    """
    try:
        import requests
        r = requests.get(
            f"https://clob.polymarket.com/markets/{condition_id}",
            timeout=10,
        )
        if r.status_code != 200:
            return None
        data = r.json() or {}
    except Exception:
        return None

    if not data.get("closed", False):
        return None

    tokens = data.get("tokens") or []
    # side 'yes'/'buy' means we bought the YES outcome; 'no' means the NO outcome
    target_outcome = "Yes" if side.lower() in ("yes", "buy", "up", "over", "long") else "No"
    for tk in tokens:
        if str(tk.get("outcome", "")).lower() == target_outcome.lower():
            return "win" if tk.get("winner") else "loss"
    return None


def _unresolved_poly_buys() -> list[dict]:
    """Return Poly BUY orders (real + paper) that don't yet have a result row."""
    with _conn() as con:
        con.row_factory = None  # tuples faster
        rows = con.execute("""
            SELECT o.order_id, o.market_id, o.side, o.price, o.size_usd, o.timestamp,
                   COALESCE(o.paper_trade, 0) AS paper_trade
            FROM orders o
            LEFT JOIN results r ON r.signal_id = o.order_id
            WHERE o.exchange='polymarket'
              AND o.status IN ('filled','paper')
              AND o.dry_run=0
              AND LOWER(o.side) IN ('yes','no','buy')
              AND r.result_id IS NULL
              AND o.timestamp <= datetime('now', '-' || ? || ' minutes')
            ORDER BY o.timestamp ASC
        """, (_MIN_AGE_MIN,)).fetchall()
    return [
        {"order_id": r[0], "token_id": r[1], "side": r[2], "entry_price": r[3],
         "size_usd": r[4], "timestamp": r[5], "paper_trade": r[6]}
        for r in rows
    ]


def _strategy_for_order(token_id: str, order_ts: str) -> str:
    """Best-effort link: find the signal that caused this order."""
    with _conn() as con:
        r = con.execute("""
            SELECT strategy_name FROM signals
            WHERE market_id=? AND timestamp<=? AND timestamp>=datetime(?, '-30 minutes')
            ORDER BY score DESC, timestamp DESC LIMIT 1
        """, (token_id, order_ts, order_ts)).fetchone()
    return r[0] if r else "unknown"


def _record_result(order: dict, final_price: float, won: bool, strategy: str, source: str = "polymarket"):
    contracts = order["size_usd"] / max(0.01, order["entry_price"])
    pnl = round(contracts * (final_price - order["entry_price"]), 4)
    paper = int(order.get("paper_trade", 0) or 0)
    with _conn() as con:
        con.execute("""
            INSERT INTO results
              (result_id, signal_id, market_id, realized_outcome, outcome_timestamp,
               strategy_name, side, entry_price, final_price, size_usd, pnl_usd, won,
               source, token_id, paper_trade)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            f"res-{order['order_id']}", order["order_id"], order["token_id"],
            1 if won else 0, datetime.now(timezone.utc).isoformat(),
            strategy, order["side"], order["entry_price"], final_price,
            order["size_usd"], pnl, 1 if won else 0, source, order["token_id"],
            paper,
        ))
        con.commit()
    logger.info("outcome_tracker.recorded", extra={
        "order_id": order["order_id"], "strategy": strategy, "paper": paper,
        "side": order["side"], "entry": order["entry_price"], "final": final_price,
        "pnl_usd": pnl, "won": won,
    })


def run_once() -> dict:
    _ensure_schema()
    unresolved = _unresolved_poly_buys()
    if not unresolved:
        # Still refresh weights so boosts/disables from older data apply
        try:
            from core.strategy_weights import update_weights
            wu = update_weights()
        except Exception:
            wu = {"error": "weight_update_failed"}
        return {"checked": 0, "wins": 0, "losses": 0, "open": 0, "weight_update": wu}

    pos_data = get_polymarket_positions()
    positions = pos_data.get("positions", [])
    # Build token_id -> position map
    by_token: dict[str, dict] = {}
    for p in positions:
        tid = p.get("token_id", "")
        if tid:
            by_token[tid] = p

    wins = losses = still_open = 0
    for o in unresolved:
        tid = o["token_id"]
        pos = by_token.get(tid)
        strategy = _strategy_for_order(tid, o["timestamp"])

        # Loss is *confirmed* when Poly returns redeemable=True + value=0.
        # Win detection needs a real resolution check (market closed with YES
        # winning and we bought YES, etc.) — too many ways for a position to
        # disappear from the API for "position missing" alone to imply win.
        # We only record confirmed losses here; wins come from _resolve_and_record.
        if pos is not None and pos.get("redeemable") and float(pos.get("value_usd", 0)) < 0.01:
            _record_result(o, final_price=0.0, won=False, strategy=strategy)
            losses += 1
        elif pos is None:
            # Missing position → consult market resolution API
            outcome = _resolve_outcome(tid, o["side"])
            if outcome is None:
                still_open += 1
            elif outcome == "win":
                _record_result(o, final_price=1.0, won=True, strategy=strategy)
                wins += 1
            else:  # "loss"
                _record_result(o, final_price=0.0, won=False, strategy=strategy)
                losses += 1
        else:
            still_open += 1

    summary = {"checked": len(unresolved), "wins": wins, "losses": losses, "open": still_open}
    logger.info("outcome_tracker.pass_done", extra=summary)

    # Refresh adaptive weights whenever new outcomes arrived
    if wins + losses > 0:
        try:
            from core.strategy_weights import update_weights
            summary["weight_update"] = update_weights()
        except Exception as e:
            logger.error("outcome_tracker.weights_err", extra={"error": str(e)})
    return summary


def run_forever():
    logger.info("outcome_tracker.start", extra={"interval_sec": _INTERVAL})
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error("outcome_tracker.loop_error", extra={"error": str(e)})
        time.sleep(_INTERVAL)


if __name__ == "__main__":
    import sys
    if "--once" in sys.argv:
        print(run_once())
    else:
        run_forever()
