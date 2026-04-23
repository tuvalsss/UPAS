"""
rl/reward.py
Reward calculation based on signal outcome vs prediction.
"""
from __future__ import annotations

from typing import Any


def compute_reward(
    signal: dict[str, Any],
    outcome: int,          # 1=correct, 0=wrong, -1=unknown
    asked_user: bool = False,
    confidence: float = 0.5,
) -> float:
    """
    Compute reward for a signal decision.

    Reward schedule:
    - Correct + high confidence:  +1.0
    - Correct + low confidence:   +0.5
    - Correct (asked user):       +0.5 (good caution rewarded)
    - Wrong:                      -1.0
    - Unknown:                     0.0
    - Asked user unnecessarily:   -0.1 (confidence was high, didn't need to ask)
    """
    if outcome == -1 or outcome is None:
        return 0.0

    if outcome == 1:  # Correct
        if asked_user and confidence < 0.6:
            return 0.5  # Correct caution
        if asked_user and confidence >= 0.75:
            return 0.4  # Unnecessary question but still correct
        return 1.0 if confidence >= 0.70 else 0.7

    else:  # Wrong
        return -1.0


def compute_batch_rewards(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Compute rewards for a batch of training records."""
    rewards = []
    for rec in records:
        reward = compute_reward(
            signal={},
            outcome=rec.get("realized_outcome", -1),
            asked_user=rec.get("asked_user", False),
            confidence=rec.get("confidence", 0.5),
        )
        rewards.append({
            "market_id": rec.get("market_id"),
            "strategy": rec.get("decision_path"),
            "reward": reward,
            "outcome": rec.get("realized_outcome"),
        })
    return rewards
