"""
strategies/reverse/probability_freeze.py
Detect suspiciously stable probabilities — may indicate manipulation or stale data.
Reverse strategy — direction: "reverse"
"""
from __future__ import annotations

from typing import Any

from config.variables import REV_PROBABILITY_FREEZE
from strategies.base import BaseStrategy, Signal


class ProbabilityFreeze(BaseStrategy):
    name = "probability_freeze"
    direction = "reverse"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            raw = m.get("raw", {})
            price_history = raw.get("price_history", [])
            if len(price_history) < 3:
                # No history: use volume/liquidity as proxy
                if m.get("volume", 0) < 100 and m.get("liquidity", 0) > 1000:
                    signals.append(self._make_signal(
                        m["market_id"], 60.0, 0.55,
                        "Low volume despite high liquidity — possible price freeze.",
                        "AVOID", 0.35,
                    ))
                continue

            prices = [float(p) for p in price_history[-10:]]
            max_move = max(abs(prices[i] - prices[i-1]) for i in range(1, len(prices)))

            if max_move > REV_PROBABILITY_FREEZE:
                continue  # Normal movement — not frozen

            score = min(100.0, (REV_PROBABILITY_FREEZE - max_move) / REV_PROBABILITY_FREEZE * 80)
            reasoning = (
                f"Price frozen: max move over last {len(prices)} snapshots = {max_move:.4f} "
                f"(threshold: {REV_PROBABILITY_FREEZE}). Possible manipulation or data staleness."
            )
            signals.append(self._make_signal(m["market_id"], score, 0.65, reasoning, "AVOID", 0.3))
        return signals


_strategy = ProbabilityFreeze()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
