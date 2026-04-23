"""
strategies/meta/opportunity_cluster.py
Detect clusters of correlated signals across strategies — convergence = strong alpha.
Meta strategy — direction: "meta"
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from strategies.base import BaseStrategy, Signal


class OpportunityCluster(BaseStrategy):
    name = "opportunity_cluster"
    direction = "meta"

    def detect(self, markets: list[dict[str, Any]], all_signals: list[dict[str, Any]] | None = None, **kwargs) -> list[Signal]:
        if not all_signals:
            return []

        # Count how many strategies fired per market
        market_signal_count: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for sig in all_signals:
            if sig.get("direction") in ("forward", "reverse"):
                market_signal_count[sig["market_id"]].append(sig)

        signals = []
        for market_id, sigs in market_signal_count.items():
            if len(sigs) < 3:
                continue  # Need at least 3 signals for a cluster

            forward_sigs = [s for s in sigs if s.get("direction") == "forward"]
            reverse_sigs = [s for s in sigs if s.get("direction") == "reverse"]

            # Only cluster if forward outweighs reverse
            if len(forward_sigs) <= len(reverse_sigs):
                continue

            avg_score = sum(s.get("score", 0) for s in forward_sigs) / len(forward_sigs)
            cluster_score = min(100.0, avg_score * (1 + len(forward_sigs) * 0.1))
            confidence = min(0.90, 0.5 + len(forward_sigs) * 0.08)

            reasoning = (
                f"Opportunity cluster: {len(forward_sigs)} forward signals + "
                f"{len(reverse_sigs)} reverse signals on this market. "
                f"Strategies: {', '.join(s['strategy_name'] for s in forward_sigs[:4])}. "
                f"Avg forward score: {avg_score:.1f}."
            )
            signals.append(
                self._make_signal(market_id, cluster_score, confidence, reasoning, "BUY YES", 0.10)
            )
        return signals


_strategy = OpportunityCluster()

def detect(markets: list[dict[str, Any]], all_signals: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets, all_signals=all_signals)]
