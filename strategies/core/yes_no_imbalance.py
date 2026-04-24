"""
strategies/core/yes_no_imbalance.py
Detects order-book bid/ask volume imbalance — buying pressure on one side.

The OLD version (broken): bought the "cheaper" side of YES vs NO price.
  Flaw: YES+NO≈1.0 always, so this just bought lower-probability outcomes → 19% WR.

This version: looks at actual bid/ask SIZE imbalance from the raw market data.
  Alpha: when buy orders for YES significantly outweigh sell orders (ask side),
  it implies accumulation before a price move. Valid for Polymarket only.

PAPER-ONLY until ≥50 paper trades show WR>50%.
"""
from __future__ import annotations

from typing import Any

from strategies.base import BaseStrategy, Signal

_MIN_VOLUME_USD = 500.0       # skip low-volume markets (no real order book)
_IMBALANCE_RATIO = 2.5        # bid_size must be >= 2.5× ask_size to signal YES
_PRICE_BAND = (0.25, 0.75)    # only act on markets in 25-75¢ range (real uncertainty)


class YesNoImbalance(BaseStrategy):
    name = "yes_no_imbalance"
    direction = "forward"
    paper_only = True          # disabled for real money until WR proven ≥50%

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            yes = m.get("yes_price", 0.0)
            if not (_PRICE_BAND[0] <= yes <= _PRICE_BAND[1]):
                continue
            if m.get("volume", 0.0) < _MIN_VOLUME_USD:
                continue

            raw = m.get("raw") or {}
            bid_sz = float(raw.get("yes_bid_size_fp") or raw.get("yes_bid_size") or 0.0)
            ask_sz = float(raw.get("yes_ask_size_fp") or raw.get("yes_ask_size") or 0.0)

            if bid_sz <= 0 or ask_sz <= 0:
                continue

            ratio = bid_sz / ask_sz

            if ratio >= _IMBALANCE_RATIO:
                side, action = "YES", "BUY YES"
            elif ratio <= (1.0 / _IMBALANCE_RATIO):
                side, action = "NO", "BUY NO"
            else:
                continue

            score = min(92.0, 55.0 + min(ratio, 10.0) * 4.0)
            confidence = min(0.85, 0.50 + min(ratio, 5.0) * 0.07)
            reasoning = (
                f"Order book imbalance on {side}: bid_sz={bid_sz:.0f} ask_sz={ask_sz:.0f} "
                f"ratio={ratio:.1f}x  YES={yes:.2%}  vol=${m.get('volume',0):.0f}"
            )
            signals.append(
                self._make_signal(m["market_id"], score, confidence, reasoning, action,
                                  uncertainty=0.25)
            )
        return signals


_strategy = YesNoImbalance()


def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
