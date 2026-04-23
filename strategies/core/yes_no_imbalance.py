"""
strategies/core/yes_no_imbalance.py
Detect significant yes/no price imbalances exceeding imbalance_threshold.
Forward strategy — direction: "forward"
"""
from __future__ import annotations

from typing import Any

from config.variables import IMBALANCE_THRESHOLD
from strategies.base import BaseStrategy, Signal


class YesNoImbalance(BaseStrategy):
    name = "yes_no_imbalance"
    direction = "forward"

    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]:
        signals = []
        for m in markets:
            yes = m.get("yes_price", 0.0)
            no = m.get("no_price", 0.0)
            imbalance = abs(yes - no)

            if imbalance < IMBALANCE_THRESHOLD:
                continue
            if yes <= 0 or no <= 0:
                continue

            # Skip structural long-tail markets (championship futures etc.):
            # if the "underpriced" side is still below 0.10 or above 0.90,
            # the imbalance reflects true low-probability pricing, not alpha.
            # Binary markets always have yes+no ≈ 1.0, so |yes-no| reflects probability,
            # not alpha. Only act when the underpriced side is plausibly mispriced
            # (in the 0.30–0.70 band — i.e. genuine toss-ups skewed by sentiment).
            underpriced = min(yes, no)
            if underpriced < 0.30 or underpriced > 0.70:
                continue
            # Require yes+no ≈ 1.0 (filter out stale/illiquid quotes where the two
            # sides don't sum to a coherent book).
            if abs((yes + no) - 1.0) > 0.05:
                continue

            # The underpriced side is the potential alpha
            if yes < no:
                side, action = "YES", "BUY YES"
            else:
                side, action = "NO", "BUY NO"

            score = min(100.0, (imbalance / IMBALANCE_THRESHOLD) * 50)
            confidence = min(0.9, imbalance * 3)
            reasoning = (
                f"YES={yes:.2%} vs NO={no:.2%} — imbalance={imbalance:.3f} "
                f"exceeds threshold {IMBALANCE_THRESHOLD}. {side} side appears underpriced."
            )
            signals.append(
                self._make_signal(m["market_id"], score, confidence, reasoning, action, uncertainty=0.1)
            )
        return signals


# Module-level entry point used by strategy_tool
_strategy = YesNoImbalance()

def detect(markets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets)]
