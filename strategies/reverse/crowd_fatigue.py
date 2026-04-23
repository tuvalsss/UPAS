"""
strategies/reverse/crowd_fatigue.py
Detect declining trading activity despite approaching event — crowd losing interest.
Reverse strategy — direction: "reverse"
"""
from __future__ import annotations

from typing import Any

from config.variables import REV_CROWD_FATIGUE
from strategies.base import BaseStrategy, Signal


class CrowdFatigue(BaseStrategy):
    name = "crowd_fatigue"
    direction = "reverse"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            volume = m.get("volume", 0.0)
            liquidity = m.get("liquidity", 1.0)
            raw = m.get("raw", {})
            prev_volume = raw.get("previous_volume") or raw.get("prevVolume")

            if prev_volume is None:
                # Proxy: volume/liquidity ratio declining
                ratio = volume / max(liquidity, 1.0)
                if ratio < (1 - REV_CROWD_FATIGUE):
                    score = min(100.0, (1 - REV_CROWD_FATIGUE - ratio) * 200)
                    signals.append(self._make_signal(
                        m["market_id"], score, 0.55,
                        f"Low vol/liq ratio ({ratio:.2f}) suggests crowd fatigue.",
                        "AVOID", 0.30,
                    ))
                continue

            prev_volume = float(prev_volume)
            if prev_volume == 0:
                continue

            decline = (prev_volume - volume) / prev_volume
            if decline < REV_CROWD_FATIGUE:
                continue

            score = min(100.0, decline * 100)
            reasoning = (
                f"Volume declined {decline:.0%}: {prev_volume:.0f} → {volume:.0f}. "
                "Crowd losing interest despite approaching event. Forward signals less reliable."
            )
            signals.append(
                self._make_signal(m["market_id"], score, 0.65, reasoning, "AVOID", 0.25)
            )
        return signals


_strategy = CrowdFatigue()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
