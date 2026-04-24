"""
strategies/core/high_prob_bond.py
Buy high-probability markets like bonds — collect the spread as the market
converges to 1.0 at resolution.

Alpha: markets at YES=82-99% are very likely to resolve YES. Buying at 0.92
and collecting 1.00 is an 8.7% return over the remaining time. Annualised on
a 24h market that's 3170%. Risk: the tail (market resolves NO).

Only signals when annualised yield > 20% (short-dated + high prob = best).
Direction always BUY YES (we only look when YES is already high).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from strategies.base import BaseStrategy, Signal

_HIGH_PROB_MIN = 0.82          # minimum YES price
_MIN_ANNUALISED_YIELD = 0.20   # at least 20% annualised return
_MAX_HOURS = 240               # max 10 days — beyond that yield is too thin
_MIN_HOURS = 1.0               # need ≥1h or we can't fill in time


class HighProbBond(BaseStrategy):
    name = "high_prob_bond"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        now = datetime.now(timezone.utc)

        for m in markets:
            yes = m.get("yes_price", 0.0)
            if yes < _HIGH_PROB_MIN:
                continue

            expiry_str = m.get("expiry_timestamp", "")
            if not expiry_str:
                continue
            try:
                expiry = datetime.fromisoformat(expiry_str.replace("Z", "+00:00"))
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                hours_left = (expiry - now).total_seconds() / 3600
            except Exception:
                continue

            if not (_MIN_HOURS <= hours_left <= _MAX_HOURS):
                continue

            raw_yield = (1.0 - yes) / yes                    # profit per dollar staked
            annualised = raw_yield * (8760 / hours_left)

            if annualised < _MIN_ANNUALISED_YIELD:
                continue

            # Score: high yes_price + short time to collect = high score
            score = min(99.0, yes * 60 + min(annualised, 10.0) * 4)
            confidence = min(0.95, yes)
            reasoning = (
                f"Bond: YES={yes:.1%}, {hours_left:.1f}h left, "
                f"yield={raw_yield:.1%} ({annualised:.0%} ann.). "
                f"Buying YES, collecting {(1-yes)*100:.1f}¢ on the dollar."
            )
            signals.append(
                self._make_signal(
                    m["market_id"], score, confidence, reasoning, "BUY YES",
                    uncertainty=round(1.0 - yes, 3),
                )
            )
        return signals


_strategy = HighProbBond()


def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
