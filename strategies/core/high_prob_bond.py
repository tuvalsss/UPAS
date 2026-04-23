"""
strategies/core/high_prob_bond.py
Identify high-probability markets offering bond-like returns.
Forward strategy — direction: "forward"
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from strategies.base import BaseStrategy, Signal

_HIGH_PROB_MIN = 0.80
_MAX_HOURS = 720          # Max 30 days to expiry


class HighProbBond(BaseStrategy):
    name = "high_prob_bond"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        now = datetime.now(timezone.utc)

        for m in markets:
            yes = m.get("yes_price", 0.0)
            if yes < _HIGH_PROB_MIN:
                continue

            expiry_str = m.get("expiry_timestamp", "")
            if expiry_str:
                try:
                    expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                    if expiry.tzinfo is None:
                        expiry = expiry.replace(tzinfo=timezone.utc)
                    hours_left = (expiry - now).total_seconds() / 3600
                    if hours_left > _MAX_HOURS or hours_left < 1:
                        continue
                    # Annualized yield proxy
                    yield_pct = (1.0 - yes) / yes
                    annualized = yield_pct * (8760 / hours_left)
                except Exception:
                    continue
            else:
                continue

            if annualized < 0.05:  # Less than 5% annualized — not worth it
                continue

            score = min(100.0, yes * 80 + annualized * 10)
            confidence = yes  # Confidence = probability itself
            reasoning = (
                f"Bond-like opportunity: YES={yes:.2%}, "
                f"{hours_left:.0f}h to expiry, "
                f"annualized yield≈{annualized:.0%}."
            )
            signals.append(
                self._make_signal(m["market_id"], score, confidence, reasoning, "BUY YES", 0.08)
            )
        return signals


_strategy = HighProbBond()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
