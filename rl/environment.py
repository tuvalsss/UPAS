"""
rl/environment.py
Prediction market RL environment — states, actions, transitions.
"""
from __future__ import annotations

from typing import Any


class PredictionMarketEnv:
    """
    Simple RL environment for prediction market signal decisions.

    State: market features + signal history
    Action: which strategy weight combination to apply
    Reward: see rl/reward.py
    """

    def __init__(self, strategy_names: list[str]):
        self.strategy_names = strategy_names
        self.current_state: dict[str, Any] = {}
        self.step_count = 0

    def reset(self, market: dict[str, Any]) -> dict[str, Any]:
        """Reset environment to a new market state."""
        self.current_state = {
            "market_id": market.get("market_id"),
            "yes_price": market.get("yes_price", 0.5),
            "no_price": market.get("no_price", 0.5),
            "liquidity": market.get("liquidity", 0.0),
            "volume": market.get("volume", 0.0),
            "signals_fired": [],
            "step": 0,
        }
        self.step_count = 0
        return self.current_state

    def step(self, action: str, reward: float) -> dict[str, Any]:
        """Apply action and reward, return new state."""
        self.step_count += 1
        self.current_state["signals_fired"].append(action)
        self.current_state["last_reward"] = reward
        self.current_state["step"] = self.step_count
        return self.current_state

    def observation(self) -> list[float]:
        """Return flat observation vector for RL policy."""
        return [
            self.current_state.get("yes_price", 0.5),
            self.current_state.get("no_price", 0.5),
            self.current_state.get("liquidity", 0.0) / 10000,
            self.current_state.get("volume", 0.0) / 10000,
            float(len(self.current_state.get("signals_fired", []))),
        ]
