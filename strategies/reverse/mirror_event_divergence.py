"""
strategies/reverse/mirror_event_divergence.py
Detect mirror events (YES/NO complements) with inconsistent pricing.
Reverse strategy — direction: "reverse"
"""
from __future__ import annotations

from typing import Any

from config.variables import REV_MIRROR_DIVERGENCE
from strategies.base import BaseStrategy, Signal


class MirrorEventDivergence(BaseStrategy):
    name = "mirror_event_divergence"
    direction = "reverse"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        """
        For any market, YES + NO should sum to ~1.0.
        Large deviations suggest data error or market manipulation.
        """
        signals = []
        for m in markets:
            yes = m.get("yes_price", 0.0)
            no = m.get("no_price", 0.0)

            if yes <= 0 or no <= 0:
                continue

            deviation = abs((yes + no) - 1.0)
            if deviation <= REV_MIRROR_DIVERGENCE:
                continue

            score = min(100.0, deviation / REV_MIRROR_DIVERGENCE * 75)
            reasoning = (
                f"Mirror divergence: YES={yes:.3f} + NO={no:.3f} = {yes+no:.3f} "
                f"(deviation from 1.0: {deviation:.4f}, threshold: {REV_MIRROR_DIVERGENCE}). "
                "Prices do not sum to 1.0 — possible data issue or arbitrage opportunity."
            )
            action = "ARBITRAGE" if deviation > 0.05 else "WATCH"
            signals.append(
                self._make_signal(m["market_id"], score, 0.75, reasoning, action, 0.15)
            )
        return signals


_strategy = MirrorEventDivergence()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
