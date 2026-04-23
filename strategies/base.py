"""
strategies/base.py
Abstract base class and Signal dataclass for all UPAS strategies.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Signal:
    """Standard signal object — all strategies return List[Signal]."""
    market_id: str
    strategy_name: str
    direction: str                  # "forward" | "reverse" | "meta"
    score: float                    # 0.0–100.0
    confidence: float               # 0.0–1.0
    uncertainty: float              # 0.0–1.0
    reasoning: str
    suggested_action: str           # e.g. "BUY YES", "WATCH", "AVOID"
    signal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=_now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "signal_id": self.signal_id,
            "market_id": self.market_id,
            "strategy_name": self.strategy_name,
            "direction": self.direction,
            "score": self.score,
            "confidence": self.confidence,
            "uncertainty": self.uncertainty,
            "reasoning": self.reasoning,
            "suggested_action": self.suggested_action,
            "timestamp": self.timestamp,
        }


class BaseStrategy(ABC):
    """Abstract base for all UPAS strategies."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def direction(self) -> str: ...

    @abstractmethod
    def detect(self, markets: list[dict[str, Any]], **kwargs) -> list[Signal]: ...

    def _make_signal(
        self,
        market_id: str,
        score: float,
        confidence: float,
        reasoning: str,
        suggested_action: str = "WATCH",
        uncertainty: float = 0.1,
    ) -> Signal:
        return Signal(
            market_id=market_id,
            strategy_name=self.name,
            direction=self.direction,
            score=min(100.0, max(0.0, score)),
            confidence=min(1.0, max(0.0, confidence)),
            uncertainty=min(1.0, max(0.0, uncertainty)),
            reasoning=reasoning,
            suggested_action=suggested_action,
        )
