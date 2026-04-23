"""
strategies/meta/signal_memory.py
Track signal history and detect recurring patterns that historically resolve correctly.
Meta strategy — direction: "meta"
"""
from __future__ import annotations

from collections import defaultdict
from typing import Any

from strategies.base import BaseStrategy, Signal


class SignalMemory(BaseStrategy):
    name = "signal_memory"
    direction = "meta"

    def detect(self, markets: list[dict[str, Any]], all_signals: list[dict[str, Any]] | None = None, **kwargs) -> list[Signal]:
        """
        Looks for markets that have fired the same strategy signal multiple times.
        Historical repetition of a signal increases confidence.
        Requires historical_signals kwarg (from DB) for full power;
        falls back to current-run signals.
        """
        historical = kwargs.get("historical_signals", all_signals or [])
        if not historical:
            return []

        # Count signal firings per (market_id, strategy_name)
        firing_counts: dict[tuple, int] = defaultdict(int)
        for sig in historical:
            key = (sig.get("market_id", ""), sig.get("strategy_name", ""))
            firing_counts[key] += 1

        market_ids = {m["market_id"] for m in markets}
        signals = []

        for (market_id, strategy_name), count in firing_counts.items():
            if market_id not in market_ids:
                continue
            if count < 3:
                continue  # Need at least 3 occurrences for memory effect

            score = min(100.0, 40 + count * 8)
            confidence = min(0.85, 0.5 + count * 0.06)
            reasoning = (
                f"Signal memory: '{strategy_name}' has fired {count}x on this market. "
                "Recurring pattern detected — historical reliability boost applied."
            )
            signals.append(
                self._make_signal(market_id, score, confidence, reasoning, "WATCH", 0.15)
            )
        return signals


_strategy = SignalMemory()

def detect(markets: list[dict[str, Any]], all_signals: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    return [s.to_dict() for s in _strategy.detect(markets, all_signals=all_signals)]
