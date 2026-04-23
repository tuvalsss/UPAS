"""
strategies/reverse/whale_exhaustion.py
Detect large trader withdrawal — whale has taken profits or position.
Reverse strategy — direction: "reverse"
"""
from __future__ import annotations

from typing import Any

from config.variables import REV_WHALE_EXHAUSTION
from strategies.base import BaseStrategy, Signal


class WhaleExhaustion(BaseStrategy):
    name = "whale_exhaustion"
    direction = "reverse"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            liquidity = m.get("liquidity", 0.0)
            volume = m.get("volume", 0.0)
            raw = m.get("raw", {})

            # Proxy: large single-trade volume relative to total liquidity
            largest_trade = raw.get("largest_trade_size") or raw.get("maxTradeSize")
            if largest_trade is None:
                # Fallback: if volume >> liquidity by whale threshold, signal exhaustion
                if liquidity > 0 and volume / liquidity > (1 / (1 - REV_WHALE_EXHAUSTION)):
                    score = 55.0
                    signals.append(self._make_signal(
                        m["market_id"], score, 0.50,
                        f"Volume ({volume:.0f}) >> liquidity ({liquidity:.0f}) — possible whale activity.",
                        "WATCH", 0.35,
                    ))
                continue

            largest_trade = float(largest_trade)
            if liquidity == 0:
                continue

            whale_ratio = largest_trade / liquidity
            if whale_ratio < REV_WHALE_EXHAUSTION:
                continue

            score = min(100.0, whale_ratio * 70)
            reasoning = (
                f"Whale exhaustion: largest trade = {largest_trade:.0f} "
                f"({whale_ratio:.0%} of total liquidity {liquidity:.0f}). "
                "Dominant position likely already established — follow-on alpha reduced."
            )
            signals.append(
                self._make_signal(m["market_id"], score, 0.70, reasoning, "AVOID", 0.20)
            )
        return signals


_strategy = WhaleExhaustion()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
