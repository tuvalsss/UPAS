"""
strategies/reverse/event_shadow_drift.py
Detect correlated events drifting apart — one market becoming stale.
Reverse strategy — direction: "reverse"
"""
from __future__ import annotations

from typing import Any

from config.variables import REV_EVENT_SHADOW_DRIFT
from strategies.base import BaseStrategy, Signal


class EventShadowDrift(BaseStrategy):
    name = "event_shadow_drift"
    direction = "reverse"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        """
        Groups markets by event keyword and checks if related markets have drifted.
        For example: 'Fed rate hike' YES prices on Polymarket vs Kalshi should be close.
        """
        signals = []
        # Group by first 30 chars of title
        groups: dict[str, list[dict[str, Any]]] = {}
        for m in markets:
            key = m.get("title", "")[:30].lower()
            groups.setdefault(key, []).append(m)

        for key, group in groups.items():
            if len(group) < 2:
                continue
            prices = [m["yes_price"] for m in group]
            max_drift = max(prices) - min(prices)
            if max_drift <= REV_EVENT_SHADOW_DRIFT:
                continue

            for m in group:
                score = min(100.0, max_drift / REV_EVENT_SHADOW_DRIFT * 50)
                reasoning = (
                    f"Event shadow drift: '{key[:20]}' group has YES price spread={max_drift:.3f} "
                    f"(threshold: {REV_EVENT_SHADOW_DRIFT}). One market may be stale or mispriced."
                )
                signals.append(
                    self._make_signal(m["market_id"], score, 0.60, reasoning, "WATCH", 0.30)
                )
        return signals


_strategy = EventShadowDrift()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
