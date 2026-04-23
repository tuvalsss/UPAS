"""
strategies/reverse/liquidity_vacuum.py
Detect abnormally low liquidity — forward signals may be unreliable.
Reverse strategy — direction: "reverse"
"""
from __future__ import annotations

from typing import Any

from config.variables import REV_LIQUIDITY_VACUUM
from strategies.base import BaseStrategy, Signal


class LiquidityVacuum(BaseStrategy):
    name = "liquidity_vacuum"
    direction = "reverse"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            liquidity = m.get("liquidity", 0.0)
            if liquidity >= REV_LIQUIDITY_VACUUM:
                continue

            score = min(100.0, (REV_LIQUIDITY_VACUUM - liquidity) / REV_LIQUIDITY_VACUUM * 90)
            reasoning = (
                f"Liquidity vacuum: only ${liquidity:.0f} available "
                f"(threshold: ${REV_LIQUIDITY_VACUUM}). "
                "Forward signals for this market should be discounted heavily."
            )
            signals.append(
                self._make_signal(m["market_id"], score, 0.80, reasoning, "AVOID", 0.15)
            )
        return signals


_strategy = LiquidityVacuum()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
