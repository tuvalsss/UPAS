"""
strategies/meta/negative_signal_detector.py
Detect absence of expected signals — markets that SHOULD have fired signals but didn't.
Meta strategy — direction: "meta"
"""
from __future__ import annotations

from typing import Any

from strategies.base import BaseStrategy, Signal


class NegativeSignalDetector(BaseStrategy):
    name = "negative_signal_detector"
    direction = "meta"

    def detect(self, markets: list[dict[str, Any]], all_signals: list[dict[str, Any]] | None = None, **kwargs) -> list[Signal]:
        """
        High-liquidity, near-expiry markets that fired NO signals are suspicious.
        The absence of any signal is itself a signal — something may be very stable or being suppressed.
        """
        if not markets:
            return []

        signaled_market_ids = {s.get("market_id") for s in (all_signals or [])}
        signals = []

        for m in markets:
            if m["market_id"] in signaled_market_ids:
                continue  # Normal — has signals

            liquidity = m.get("liquidity", 0.0)
            volume = m.get("volume", 0.0)
            yes = m.get("yes_price", 0.5)

            # Only flag high-activity markets with no signals
            if liquidity < 5000 or volume < 1000:
                continue

            # Markets at extreme probability should have fired something
            if 0.2 < yes < 0.8:
                continue  # Neutral market — silence is normal

            score = 45.0
            confidence = 0.50
            reasoning = (
                f"No signals fired on high-activity market (liq={liquidity:.0f}, "
                f"vol={volume:.0f}, YES={yes:.2%}). "
                "Absence of expected signals may indicate suppression or missed opportunity."
            )
            signals.append(
                self._make_signal(m["market_id"], score, confidence, reasoning, "INVESTIGATE", 0.40)
            )
        return signals


_strategy = NegativeSignalDetector()

def detect(markets: list[dict[str, Any]], all_signals: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets, all_signals=all_signals)]
