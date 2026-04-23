"""
strategies/reverse/fake_momentum.py
Detect price movement without supporting volume — potentially manipulated.
Reverse strategy — direction: "reverse"
"""
from __future__ import annotations

from typing import Any

from config.variables import REV_FAKE_MOMENTUM
from strategies.base import BaseStrategy, Signal


class FakeMomentum(BaseStrategy):
    name = "fake_momentum"
    direction = "reverse"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            yes = m.get("yes_price", 0.5)
            volume = m.get("volume", 0.0)
            liquidity = m.get("liquidity", 1.0)
            raw = m.get("raw", {})

            prev_yes = raw.get("previous_yes_price") or raw.get("prevPrice")
            if prev_yes is None:
                continue

            prev_yes = float(prev_yes)
            price_move = abs(yes - prev_yes)

            if price_move < 0.03:  # Not enough price movement to analyse
                continue

            # Volume should support price movement; if not → fake momentum
            expected_vol = price_move * liquidity * 10  # heuristic
            if volume >= expected_vol * REV_FAKE_MOMENTUM:
                continue  # Volume is adequate

            score = min(100.0, (1 - volume / max(expected_vol, 1)) * 80)
            reasoning = (
                f"Fake momentum: price moved {price_move:.3f} but volume={volume:.0f} "
                f"is only {volume/max(expected_vol,1):.0%} of expected. "
                "Price movement not supported by trading activity."
            )
            signals.append(
                self._make_signal(m["market_id"], score, 0.70, reasoning, "AVOID", 0.20)
            )
        return signals


_strategy = FakeMomentum()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
