"""
tools/strategy_tool.py
Strategy registry and dispatcher. All strategy execution goes through here.
"""
from __future__ import annotations

import importlib
import time
from pathlib import Path
from typing import Any

from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_STRATEGY_DIRS = {
    "core": "strategies.core",
    "reverse": "strategies.reverse",
    "meta": "strategies.meta",
}

_CORE_STRATEGIES = [
    "yes_no_imbalance", "cross_market", "cross_market_ai", "time_decay",
    "panic_move", "high_prob_bond", "liquidity_shift",
    "chainlink_edge",
    # Paper-trade strategies (see _PAPER_STRATEGIES below) — still listed so
    # strategy_tool picks them up.
    "smart_money",
]

# Paper-trade list: these strategies RUN (signals are logged and "virtually
# executed") but never place a real order. Used to collect performance data
# for unproven strategies before promoting them to real trading.
_PAPER_STRATEGIES = {"smart_money", "yes_no_imbalance", "chainlink_edge"}


def is_paper_strategy(name: str) -> bool:
    """engine.py consults this to decide whether to place a real order."""
    return name in _PAPER_STRATEGIES
_REVERSE_STRATEGIES = [
    "probability_freeze", "liquidity_vacuum", "crowd_fatigue",
    "whale_exhaustion", "fake_momentum", "event_shadow_drift",
    "mirror_event_divergence", "time_probability_inversion",
]
_META_STRATEGIES = [
    "opportunity_cluster", "signal_memory", "negative_signal_detector",
]


def _load_strategy(pkg: str, name: str):
    """Dynamically import a strategy module."""
    module = importlib.import_module(f"{pkg}.{name}")
    return module


def run_strategies(
    markets: list[dict[str, Any]],
    strategy_type: str = "core",
    all_signals: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Run all strategies of the given type against market data.
    strategy_type: "core" | "reverse" | "meta"
    all_signals: for meta strategies, pass existing signals list
    Returns list of signal objects.
    """
    pkg = _STRATEGY_DIRS.get(strategy_type)
    if not pkg:
        raise ValueError(f"Unknown strategy_type: {strategy_type}")

    names = {
        "core": _CORE_STRATEGIES,
        "reverse": _REVERSE_STRATEGIES,
        "meta": _META_STRATEGIES,
    }[strategy_type]

    signals: list[dict[str, Any]] = []

    # Adaptive layer: skip strategies that have been auto-disabled by the
    # outcome tracker (poor win rate on realized trades). Never blocks a new
    # strategy with no history.
    try:
        from core.strategy_weights import is_enabled, get_weight
    except Exception:
        is_enabled = lambda _n: True  # noqa: E731
        get_weight = lambda _n: 1.0   # noqa: E731

    for name in names:
        if not is_enabled(name):
            logger.info("strategy_tool.skip_disabled", extra={"strategy": name})
            continue
        t0 = time.time()
        try:
            mod = _load_strategy(pkg, name)
            if strategy_type == "meta":
                result = mod.detect(markets, all_signals or [])
            else:
                result = mod.detect(markets)
            # Apply weight: multiply each signal's score (capped at 100)
            w = get_weight(name)
            is_paper = name in _PAPER_STRATEGIES
            for sig in result:
                try:
                    if w != 1.0:
                        sig["score"] = min(100.0, float(sig.get("score", 0)) * w)
                    if is_paper:
                        sig["paper_trade"] = True
                except Exception:
                    pass
            elapsed = round(time.time() - t0, 3)
            logger.info(
                "strategy_tool.run",
                extra={
                    "strategy": name,
                    "type": strategy_type,
                    "signals": len(result),
                    "weight": w,
                    "elapsed_s": elapsed,
                },
            )
            signals.extend(result)
        except Exception as e:
            elapsed = round(time.time() - t0, 3)
            logger.error(
                "strategy_tool.error",
                extra={"strategy": name, "error": str(e), "elapsed_s": elapsed},
            )
            # Gracefully skip — log and continue

    return signals


def list_strategies() -> dict[str, list[str]]:
    """Return all registered strategy names by type."""
    return {
        "core": _CORE_STRATEGIES,
        "reverse": _REVERSE_STRATEGIES,
        "meta": _META_STRATEGIES,
    }
