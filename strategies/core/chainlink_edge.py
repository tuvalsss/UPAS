"""
strategies/core/chainlink_edge.py
High-conviction edge detection for Polymarket 5-minute crypto markets
(resolved against Chainlink Data Streams).

Logic: the market resolves YES iff final_price > start_price at the window close.
We hold a live Chainlink feed, so for an in-flight window we can already see
the current price vs. the anchor and price the outcome much more accurately
than the mid-market.

Requires tools.chainlink_stream.start() to be running.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone, timedelta
from typing import Any

from strategies.base import BaseStrategy, Signal
from tools.chainlink_stream import (
    get_anchor, get_latest, resolve_symbol_from_title, status as stream_status,
)

# ── Tunables ─────────────────────────────────────────────────
_MOVE_THRESHOLD = 0.0005   # 0.05% price move = meaningful directional signal
_TARGET_YES_PROB = 0.88    # if trend holds we price YES ~88% (buffer for reversal)
_MIN_EDGE = 0.08           # require ≥8pp edge vs market price
_MIN_SECS_ELAPSED = 25     # anchor must have settled (≥25s past window start)
_MIN_SECS_REMAINING = 25   # need time to fill (≥25s until resolution)

# Title pattern: "Bitcoin Up or Down - April 22, 2:25PM-2:30PM ET"
_TITLE_RE = re.compile(
    r"(\w+)\s+Up or Down\s*-\s*(\w+ \d+),\s*(\d+:\d+[AP]M)\s*-\s*(\d+:\d+[AP]M)\s*ET",
    re.IGNORECASE,
)

# US Eastern Time — Polymarket quotes ET. EDT=-4, EST=-5. Use -4 (summer).
_ET_OFFSET_HOURS = -4


def _parse_window(title: str) -> tuple[datetime, datetime] | None:
    m = _TITLE_RE.search(title or "")
    if not m:
        return None
    _, date_str, t_start, t_end = m.groups()
    now = datetime.now(timezone.utc)
    year = now.year
    try:
        start_local = datetime.strptime(f"{date_str} {year} {t_start}", "%B %d %Y %I:%M%p")
        end_local = datetime.strptime(f"{date_str} {year} {t_end}", "%B %d %Y %I:%M%p")
    except ValueError:
        return None
    # Convert ET → UTC
    et = timezone(timedelta(hours=_ET_OFFSET_HOURS))
    start_utc = start_local.replace(tzinfo=et).astimezone(timezone.utc)
    end_utc = end_local.replace(tzinfo=et).astimezone(timezone.utc)
    # Handle end-of-day rollover if end < start (rare)
    if end_utc <= start_utc:
        end_utc += timedelta(days=1)
    return start_utc, end_utc


class ChainlinkEdge(BaseStrategy):
    name = "chainlink_edge"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals: list[Signal] = []
        if not stream_status().get("running"):
            return signals

        now = datetime.now(timezone.utc)
        for m in markets:
            if m.get("source") != "polymarket":
                continue
            title = m.get("title", "")
            if "up or down" not in title.lower():
                continue
            sym = resolve_symbol_from_title(title)
            if not sym:
                continue
            window = _parse_window(title)
            if not window:
                continue
            w_start, w_end = window
            secs_elapsed = (now - w_start).total_seconds()
            secs_remaining = (w_end - now).total_seconds()
            if secs_elapsed < _MIN_SECS_ELAPSED or secs_remaining < _MIN_SECS_REMAINING:
                continue

            anchor = get_anchor(sym, int(w_start.timestamp()))
            latest = get_latest(sym)
            if anchor is None or not latest:
                continue

            move_pct = (latest["price"] - anchor) / anchor
            if abs(move_pct) < _MOVE_THRESHOLD:
                continue

            yes_mkt = float(m.get("yes_price") or 0)
            if not (0.05 <= yes_mkt <= 0.95):
                continue

            # Direction: up → YES wins; down → NO wins
            going_yes = move_pct > 0
            # Fair probability estimate given trend: _TARGET_YES_PROB for the winner
            fair_yes = _TARGET_YES_PROB if going_yes else (1.0 - _TARGET_YES_PROB)
            edge = fair_yes - yes_mkt if going_yes else (yes_mkt - fair_yes)
            if edge < _MIN_EDGE:
                continue

            action = "BUY YES" if going_yes else "BUY NO"
            # Score: 70..100 scaled by edge magnitude (capped at 25pp)
            score = min(100.0, 70.0 + (edge * 100) * 1.2)
            # Confidence: scales with elapsed portion of window (more elapsed = more certain)
            total = (w_end - w_start).total_seconds() or 300
            confidence = min(0.92, 0.55 + (secs_elapsed / total) * 0.35)

            reasoning = (
                f"Chainlink {sym} moved {move_pct*100:+.3f}% vs window-start anchor "
                f"(${anchor:,.4f}→${latest['price']:,.4f}); "
                f"{int(secs_remaining)}s left in window. "
                f"Market YES={yes_mkt:.2f}, fair≈{fair_yes:.2f}, edge={edge:.3f} → {action}."
            )
            signals.append(self._make_signal(
                m["market_id"], score, confidence, reasoning, action,
            ))
        return signals


_strategy = ChainlinkEdge()


def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
