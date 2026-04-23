"""
rl/policy.py
Epsilon-greedy policy with decay, experiment tracking, and rollback.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.variables import DATABASE_PATH, RL_ENABLED
from rl.reward import compute_batch_rewards
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_POLICY_DIR = DATABASE_PATH.parent / "rl_policies"


class EpsilonGreedyPolicy:
    def __init__(
        self,
        strategy_names: list[str],
        epsilon: float = 0.3,
        epsilon_floor: float = 0.05,
        epsilon_decay: float = 0.01,
        rollback_threshold: float = 0.4,
    ):
        self.strategy_names = strategy_names
        self.epsilon = epsilon
        self.epsilon_floor = epsilon_floor
        self.epsilon_decay = epsilon_decay
        self.rollback_threshold = rollback_threshold
        self.weights: dict[str, float] = {n: 1.0 for n in strategy_names}
        self.episode_count = 0
        self.history: list[dict[str, Any]] = []

    def select(self, available_strategies: list[str]) -> str:
        """Epsilon-greedy strategy selection."""
        import random
        if random.random() < self.epsilon:
            return random.choice(available_strategies)
        # Greedy: pick highest-weighted
        return max(available_strategies, key=lambda s: self.weights.get(s, 1.0))

    def update(self, strategy: str, reward: float) -> None:
        """Update weight for a strategy based on reward."""
        if strategy not in self.weights:
            self.weights[strategy] = 1.0
        self.weights[strategy] = max(0.1, self.weights[strategy] + reward * 0.05)
        self.episode_count += 1

        # Decay epsilon
        if self.episode_count % 100 == 0:
            self.epsilon = max(self.epsilon_floor, self.epsilon - self.epsilon_decay)

        self.history.append({
            "episode": self.episode_count,
            "strategy": strategy,
            "reward": reward,
            "new_weight": self.weights[strategy],
        })

    def check_and_rollback(self) -> bool:
        """Rollback to previous weights if recent performance < rollback_threshold."""
        recent = self.history[-20:] if len(self.history) >= 20 else self.history
        if not recent:
            return False
        avg_reward = sum(h["reward"] for h in recent) / len(recent)
        if avg_reward < self.rollback_threshold:
            # Rollback: reset weights to equal
            self.weights = {n: 1.0 for n in self.strategy_names}
            logger.warning("rl_policy.rollback", extra={"avg_reward": avg_reward})
            return True
        return False

    def save(self) -> Path:
        """Save policy to disk."""
        _POLICY_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = _POLICY_DIR / f"policy_{ts}.json"
        data = {
            "weights": self.weights,
            "epsilon": self.epsilon,
            "episode_count": self.episode_count,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(data, indent=2))
        logger.info("rl_policy.saved", extra={"path": str(path)})
        return path

    def to_dict(self) -> dict[str, Any]:
        return {
            "weights": self.weights,
            "epsilon": self.epsilon,
            "episode_count": self.episode_count,
        }


def update_policy(records: list[dict[str, Any]], policy: EpsilonGreedyPolicy) -> dict[str, Any]:
    """Update policy from batch training records."""
    if not RL_ENABLED:
        return {"updated": False, "reason": "rl_enabled=false"}

    rewards = compute_batch_rewards(records)
    for r in rewards:
        if r["strategy"] and r["reward"] != 0:
            policy.update(r["strategy"], r["reward"])

    rolled_back = policy.check_and_rollback()
    path = policy.save()

    logger.info("rl_policy.updated", extra={"episodes": len(rewards), "rollback": rolled_back})
    return {
        "updated": True,
        "episodes": len(rewards),
        "rolled_back": rolled_back,
        "policy_path": str(path),
        "weights": policy.weights,
    }
