"""
strategies/core/liquidity_shift.py
Detect significant redistribution of liquidity suggesting informed trading.
Forward strategy — direction: "forward"
"""
from __future__ import annotations

from typing import Any

from config.variables import LIQUIDITY_MIN
from strategies.base import BaseStrategy, Signal

_SHIFT_RATIO = 0.3  # 30% of liquidity moved


class LiquidityShift(BaseStrategy):
    name = "liquidity_shift"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            liquidity = m.get("liquidity", 0.0)
            volume = m.get("volume", 0.0)
            raw = m.get("raw", {})

            prev_liq = raw.get("previous_liquidity") or raw.get("prevLiquidity")
            if prev_liq is None:
                # Fallback: very high volume relative to liquidity = active shift
                if liquidity > LIQUIDITY_MIN and volume > liquidity * 2:
                    score = min(100.0, (volume / liquidity) * 20)
                    reasoning = (
                        f"High volume/liquidity ratio: vol={volume:.0f}, liq={liquidity:.0f} "
                        f"(ratio={volume/liquidity:.1f}x). Possible informed flow."
                    )
                    signals.append(
                        self._make_signal(m["market_id"], score, 0.6, reasoning, "WATCH", 0.25)
                    )
                continue

            prev_liq = float(prev_liq)
            if prev_liq == 0:
                continue

            shift = (liquidity - prev_liq) / prev_liq
            if abs(shift) < _SHIFT_RATIO:
                continue

            direction_word = "inflow" if shift > 0 else "outflow"
            action = "BUY YES" if shift > 0 else "WATCH"
            score = min(100.0, abs(shift) * 120)
            reasoning = (
                f"Liquidity {direction_word}: {prev_liq:.0f} → {liquidity:.0f} "
                f"({shift:+.1%}). Possible informed position building."
            )
            signals.append(
                self._make_signal(m["market_id"], score, 0.65, reasoning, action, 0.2)
            )
        return signals


_strategy = LiquidityShift()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
