"""
strategies/reverse/time_probability_inversion.py
Detect probability moving against expected time decay — anomalous behaviour.
Reverse strategy — direction: "reverse"
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from config.variables import REV_TIME_PROB_INVERSION
from strategies.base import BaseStrategy, Signal


class TimeProbabilityInversion(BaseStrategy):
    name = "time_probability_inversion"
    direction = "reverse"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        """
        Near expiry, high-probability (>0.9) markets SHOULD stay high.
        If they're declining, something anomalous is happening.
        Low-probability (<0.1) markets near expiry should stay low — rising = anomaly.
        """
        signals = []
        now = datetime.now(timezone.utc)

        for m in markets:
            yes = m.get("yes_price", 0.5)
            raw = m.get("raw", {})
            prev_yes = raw.get("previous_yes_price") or raw.get("prevPrice")

            expiry_str = m.get("expiry_timestamp", "")
            if not expiry_str or not prev_yes:
                continue

            try:
                expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                hours_left = (expiry - now).total_seconds() / 3600
            except Exception:
                continue

            if hours_left > 72 or hours_left < 1:
                continue

            prev_yes = float(prev_yes)
            change = yes - prev_yes

            # High prob declining near expiry = inversion
            inversion = False
            if yes > 0.85 and change < -REV_TIME_PROB_INVERSION:
                inversion = True
                direction_word = "declining despite high probability"
            # Low prob rising near expiry = inversion
            elif yes < 0.15 and change > REV_TIME_PROB_INVERSION:
                inversion = True
                direction_word = "rising despite low probability"

            if not inversion:
                continue

            score = min(100.0, abs(change) / REV_TIME_PROB_INVERSION * 60)
            reasoning = (
                f"Time-probability inversion: YES={yes:.2%} is {direction_word} "
                f"(Δ={change:+.4f}) with {hours_left:.0f}h to expiry. "
                "Unusual — investigate before trading."
            )
            signals.append(
                self._make_signal(m["market_id"], score, 0.70, reasoning, "AVOID", 0.25)
            )
        return signals


_strategy = TimeProbabilityInversion()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
