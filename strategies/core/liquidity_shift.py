"""
strategies/core/liquidity_shift.py
Detect directional volume pressure suggesting informed trading.

The OLD version fired on ANY high-volume market and always bought YES — no edge.

New logic: use YES price level as direction proxy when volume is anomalously high.
  YES > 0.65 with high volume → buyers pushing YES up → BUY YES
  YES < 0.35 with high volume → sellers driving YES down → BUY NO
  YES 0.35-0.65 → skip (price too close to 50/50, direction uncertain)

Hypothesis: when volume >> liquidity, someone informed is moving the market.
The direction they're moving it is revealed by where the price has settled.
"""
from __future__ import annotations

from typing import Any

from config.variables import LIQUIDITY_MIN
from strategies.base import BaseStrategy, Signal

_VOL_LIQ_RATIO = 3.0      # volume must be ≥3× liquidity (strict — filters noise)
_DIRECTIONAL_BAND = 0.15  # only act if price is outside 0.5±0.15 (i.e. <0.35 or >0.65)
_MIN_LIQUIDITY = 1000.0   # enough liquidity to enter/exit cleanly


class LiquidityShift(BaseStrategy):
    name = "liquidity_shift"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            liquidity = m.get("liquidity", 0.0)
            volume = m.get("volume", 0.0)
            yes = m.get("yes_price", 0.0)

            if liquidity < max(LIQUIDITY_MIN, _MIN_LIQUIDITY):
                continue
            if volume < liquidity * _VOL_LIQ_RATIO:
                continue

            # Only act when price clearly favours one side
            if abs(yes - 0.5) < _DIRECTIONAL_BAND:
                continue

            ratio = volume / liquidity
            if yes > 0.5:
                action = "BUY YES"
                confidence = min(0.85, 0.55 + (yes - 0.65) * 0.6 + min(ratio, 10) * 0.01)
            else:
                action = "BUY NO"
                confidence = min(0.85, 0.55 + (0.35 - yes) * 0.6 + min(ratio, 10) * 0.01)

            score = min(95.0, 55.0 + min(ratio, 15.0) * 2.0 + abs(yes - 0.5) * 40.0)
            side = "YES" if yes > 0.5 else "NO"
            reasoning = (
                f"Volume surge: {volume:.0f}/{liquidity:.0f} = {ratio:.1f}× liq — "
                f"price {yes:.1%} signals {side} pressure → {action}."
            )
            signals.append(
                self._make_signal(m["market_id"], score, confidence, reasoning, action,
                                  uncertainty=0.20)
            )
        return signals


_strategy = LiquidityShift()


def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
