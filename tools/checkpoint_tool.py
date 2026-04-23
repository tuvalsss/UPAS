"""
tools/checkpoint_tool.py
Save and load pipeline state for resumable runs.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from tools.database_tool import get_latest_checkpoint, save_checkpoint
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save(stage: str, state: dict[str, Any], run_id: str | None = None) -> str:
    """
    Save a checkpoint for the current pipeline stage.
    Returns checkpoint_id.
    """
    checkpoint_id = str(uuid.uuid4())
    checkpoint = {
        "checkpoint_id": checkpoint_id,
        "run_id": run_id or str(uuid.uuid4()),
        "stage": stage,
        "pipeline_state": state,
        "timestamp": _now(),
    }
    save_checkpoint(checkpoint)
    logger.info("checkpoint_tool.save", extra={"stage": stage, "checkpoint_id": checkpoint_id})
    return checkpoint_id


def load() -> dict[str, Any] | None:
    """Load the most recent checkpoint. Returns None if no checkpoint exists."""
    checkpoint = get_latest_checkpoint()
    if checkpoint:
        logger.info(
            "checkpoint_tool.load",
            extra={"stage": checkpoint.get("stage"), "timestamp": checkpoint.get("timestamp")},
        )
    else:
        logger.info("checkpoint_tool.load.none")
    return checkpoint


def status() -> dict[str, Any]:
    """Return checkpoint status summary."""
    cp = get_latest_checkpoint()
    if cp:
        return {
            "has_checkpoint": True,
            "stage": cp.get("stage"),
            "run_id": cp.get("run_id"),
            "timestamp": cp.get("timestamp"),
            "resumable": True,
        }
    return {"has_checkpoint": False, "resumable": False}
