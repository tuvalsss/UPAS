"""
strategies/core/panic_move.py
Detect sudden large price movements indicating panic buying/selling.
Forward strategy — direction: "forward"
"""
from __future__ import annotations

from typing import Any

from strategies.base import BaseStrategy, Signal

_PANIC_THRESHOLD = 0.10  # 10% move


class PanicMove(BaseStrategy):
    name = "panic_move"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        """
        Requires 'price_history' in market raw field or previous_yes_price field.
        If not available, uses yes/no spread as a panic proxy.
        """
        signals = []
        for m in markets:
            yes = m.get("yes_price", 0.5)
            raw = m.get("raw", {})
            prev_yes = raw.get("previous_yes_price") or raw.get("prevPrice")

            if prev_yes is None:
                # Fallback: extreme price (near 0 or 1) with low liquidity = possible panic
                if (yes < 0.10 or yes > 0.90) and m.get("liquidity", 999) < 2000:
                    move = abs(yes - 0.5)
                    score = min(100.0, move * 150)
                    action = "BUY YES" if yes < 0.10 else "BUY NO"
                    reasoning = (
                        f"Extreme price ({yes:.2%}) with low liquidity ({m.get('liquidity', 0):.0f}) "
                        "suggests panic move. Potential mean-reversion opportunity."
                    )
                    signals.append(self._make_signal(m["market_id"], score, 0.55, reasoning, action, 0.3))
                continue

            prev_yes = float(prev_yes)
            move = abs(yes - prev_yes)
            if move < _PANIC_THRESHOLD:
                continue

            direction_word = "spike" if yes > prev_yes else "crash"
            action = "BUY NO" if yes > prev_yes else "BUY YES"
            score = min(100.0, (move / _PANIC_THRESHOLD) * 55)
            confidence = min(0.80, move * 5)
            reasoning = (
                f"Panic {direction_word}: YES moved from {prev_yes:.2%} to {yes:.2%} "
                f"(Δ={move:.3f}). Possible overreaction."
            )
            signals.append(self._make_signal(m["market_id"], score, confidence, reasoning, action, 0.2))
        return signals


_strategy = PanicMove()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
