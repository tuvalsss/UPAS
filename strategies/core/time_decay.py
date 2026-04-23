"""
strategies/core/time_decay.py
Detect accelerating probability changes as expiry approaches.
Forward strategy — direction: "forward"
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from strategies.base import BaseStrategy, Signal


class TimeDecay(BaseStrategy):
    name = "time_decay"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        now = datetime.now(timezone.utc)

        for m in markets:
            expiry_str = m.get("expiry_timestamp", "")
            if not expiry_str:
                continue
            try:
                expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            hours_left = max(0, (expiry - now).total_seconds() / 3600)
            if hours_left > 168 or hours_left < 1:
                continue

            yes = m.get("yes_price", 0.5)
            urgency = max(0.0, (168 - hours_left) / 168)

            if yes >= 0.7:
                score = min(100.0, (1.0 - yes) * 180 + urgency * 40)
                confidence = 0.6 + 0.2 * urgency
                reasoning = (
                    f"High YES ({yes:.2%}) with {hours_left:.1f}h to expiry. "
                    "Time decay favors holders — buying YES near resolution."
                )
                signals.append(
                    self._make_signal(m["market_id"], score, confidence, reasoning, "BUY YES")
                )
            elif yes <= 0.3:
                score = min(100.0, yes * 180 + urgency * 40)
                confidence = 0.6 + 0.2 * urgency
                reasoning = (
                    f"Low YES ({yes:.2%}) with {hours_left:.1f}h to expiry. "
                    "Time decay favors NO — shorting YES near resolution."
                )
                signals.append(
                    self._make_signal(m["market_id"], score, confidence, reasoning, "BUY NO")
                )
        return signals


_strategy = TimeDecay()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
