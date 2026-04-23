"""
logging_config/structured_logger.py
Structured JSON logging for UPAS.
Every log entry matches the standard UPAS log schema.
"""
from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config.variables import LOG_LEVEL

_ROOT = Path(__file__).parent.parent
_LOG_DIR = _ROOT / "logs"
_LOG_DIR.mkdir(parents=True, exist_ok=True)


class StructuredFormatter(logging.Formatter):
    """Formats log records as JSON matching UPAS log schema."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "source": record.name,
            "step": getattr(record, "step", None),
            "signal_type": getattr(record, "signal_type", None),
            "confidence": getattr(record, "confidence", None),
            "uncertainty": getattr(record, "uncertainty", None),
            "tool_reused": getattr(record, "tool_reused", None),
            "new_code_created": getattr(record, "new_code_created", False),
            "uncertainty_event": getattr(record, "uncertainty_event", False),
            "question_asked": getattr(record, "question_asked", False),
            "retry_attempt": getattr(record, "retry_attempt", 0),
            "error": None,
            "stack_trace": None,
        }

        # Message
        msg = record.getMessage()
        log_obj["message"] = msg

        # Extra fields from logger.info(..., extra={...}).
        # Overwrite pre-set None placeholders (error, stack_trace) when caller supplies them.
        _OVERRIDABLE = {"error", "stack_trace"}
        for key in vars(record):
            if key in logging.LogRecord.__dict__ or key.startswith("_"):
                continue
            if key in log_obj and key not in _OVERRIDABLE and log_obj[key] is not None:
                continue
            v = getattr(record, key)
            if key in _OVERRIDABLE and log_obj.get(key) is None and v is not None:
                log_obj[key] = v
            elif key not in log_obj:
                log_obj[key] = v

        # Exception info
        if record.exc_info:
            log_obj["error"] = str(record.exc_info[1])
            log_obj["stack_trace"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(log_obj, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-readable console formatter with colours."""

    COLOURS = {
        "DEBUG": "\033[36m",
        "INFO": "\033[32m",
        "WARNING": "\033[33m",
        "ERROR": "\033[31m",
        "CRITICAL": "\033[35m",
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        col = self.COLOURS.get(record.levelname, "")
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        base = f"{col}[{ts}] {record.levelname:<8} {record.name}: {record.getMessage()}"
        # For WARNING/ERROR: include extra fields (error reason, context) inline.
        if record.levelno >= logging.WARNING:
            extras = {
                k: v for k, v in vars(record).items()
                if k not in logging.LogRecord.__dict__
                and not k.startswith("_")
                and k not in ("message", "asctime", "levelname", "name", "msg", "args", "exc_info", "exc_text", "stack_info")
                and v is not None and v is not False and v != 0
            }
            if extras:
                base += " | " + " ".join(f"{k}={v}" for k, v in extras.items())
        return base + self.RESET


def get_logger(name: str) -> logging.Logger:
    """Return a configured UPAS logger for the given module name."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # ── Console handler — stderr keeps stdout clean for --json mode ──
    ch = logging.StreamHandler(sys.stderr)
    ch.setFormatter(ConsoleFormatter())
    ch.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.addHandler(ch)

    # ── File handler (JSON) ──────────────────────────────────
    log_file = _LOG_DIR / "upas.jsonl"
    fh = logging.FileHandler(str(log_file), encoding="utf-8")
    fh.setFormatter(StructuredFormatter())
    fh.setLevel(logging.DEBUG)
    logger.addHandler(fh)

    logger.propagate = False
    return logger
