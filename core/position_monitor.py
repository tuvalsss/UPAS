"""
core/position_monitor.py
Stop-loss + take-profit guardian. Runs as a standalone loop.

For every open Polymarket position:
  - Compute PnL% = unrealized_pnl_usd / entry_cost
  - If PnL% <= STOP_LOSS_PCT (default -40%): SELL (cut losses)
  - If PnL% >= TAKE_PROFIT_PCT (default +80%): SELL (lock gains)

Kalshi close is not implemented yet — only tracked/logged for visibility.

Runs every MONITOR_INTERVAL_SEC (default 300 = 5 min).
"""
from __future__ import annotations

import os
import time
from datetime import datetime, timezone

from logging_config.structured_logger import get_logger
from tools.account_tool import get_polymarket_positions
from tools.execution_tool import place_order
from tools.database_tool import append_audit_log

logger = get_logger(__name__)

_STOP_LOSS_PCT = float(os.getenv("STOP_LOSS_PCT", "-0.40"))   # sell if -40% or worse
_TAKE_PROFIT_PCT = float(os.getenv("TAKE_PROFIT_PCT", "0.80"))  # sell if +80% or better
_INTERVAL = int(os.getenv("MONITOR_INTERVAL_SEC", "300"))
_MIN_POS_VALUE = float(os.getenv("MONITOR_MIN_VALUE_USD", "5.50"))  # Poly min $5 + buffer


def _decide(pos: dict) -> tuple[str | None, float]:
    """Return (decision, pnl_pct). decision in {None, 'stop_loss', 'take_profit'}."""
    avg = float(pos.get("avg_price", 0) or 0)
    size = float(pos.get("size", 0) or 0)
    pnl = float(pos.get("unrealized_pnl_usd", 0) or 0)
    value = float(pos.get("value_usd", 0) or 0)

    if avg <= 0 or size <= 0:
        return None, 0.0
    if pos.get("redeemable"):
        return None, 0.0  # already resolved; can't sell
    # Compute anyway for logging, but skip action if position too small to sell
    if value < _MIN_POS_VALUE:
        return None, 0.0

    entry_cost = avg * size
    if entry_cost <= 0:
        return None, 0.0
    pnl_pct = pnl / entry_cost

    if pnl_pct <= _STOP_LOSS_PCT:
        return "stop_loss", pnl_pct
    if pnl_pct >= _TAKE_PROFIT_PCT:
        return "take_profit", pnl_pct
    return None, pnl_pct


def _close_polymarket(pos: dict, reason: str, pnl_pct: float) -> dict:
    """Issue SELL for the full position at current market price."""
    token_id = pos.get("token_id", "")
    current_price = float(pos.get("current_price", 0) or 0)
    size = float(pos.get("size", 0) or 0)

    if not token_id or current_price <= 0 or size <= 0:
        return {"ok": False, "error": "missing token/price/size"}

    # Sell at 1 tick below market for immediate fill
    sell_price = max(0.01, round(current_price - 0.01, 2))
    size_usd = round(size * sell_price, 2)

    logger.info("position_monitor.close", extra={
        "reason": reason, "token_id": token_id[:20],
        "title": pos.get("title", "")[:60],
        "avg": pos.get("avg_price"), "cur": current_price,
        "size": size, "size_usd": size_usd, "pnl_pct": round(pnl_pct, 3),
    })

    result = place_order(
        exchange="polymarket",
        market_id=token_id,
        side="sell",
        price=sell_price,
        size_usd=size_usd,
        token_id=token_id,
    )
    append_audit_log("position.close_attempt", "position_monitor",
                     f"{reason} pnl={pnl_pct:.1%} {result.get('status')}")
    return result


def run_once() -> dict:
    """Single pass. Returns summary."""
    data = get_polymarket_positions()
    positions = data.get("positions", [])
    closed_sl = closed_tp = skipped = 0

    for pos in positions:
        decision, pnl_pct = _decide(pos)
        if decision is None:
            skipped += 1
            continue
        result = _close_polymarket(pos, decision, pnl_pct)
        if decision == "stop_loss":
            closed_sl += 1
        elif decision == "take_profit":
            closed_tp += 1
        logger.info("position_monitor.result", extra={
            "decision": decision, "pnl_pct": round(pnl_pct, 3),
            "ok": result.get("status") == "filled", "status": result.get("status"),
        })

    summary = {
        "total": len(positions),
        "stop_loss_closed": closed_sl,
        "take_profit_closed": closed_tp,
        "skipped": skipped,
        "ts": datetime.now(timezone.utc).isoformat(),
    }
    logger.info("position_monitor.pass_done", extra=summary)
    return summary


def run_forever():
    logger.info("position_monitor.start", extra={
        "stop_loss_pct": _STOP_LOSS_PCT, "take_profit_pct": _TAKE_PROFIT_PCT,
        "interval_sec": _INTERVAL,
    })
    while True:
        try:
            run_once()
        except Exception as e:
            logger.error("position_monitor.loop_error", extra={"error": str(e)})
        time.sleep(_INTERVAL)


if __name__ == "__main__":
    run_forever()
