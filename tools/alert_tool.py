"""
tools/alert_tool.py
Alert delivery: console (rich) and Telegram.
All pipeline alerts go through this tool.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests
from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from config.variables import ALERT_CHANNELS, TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)
_console = Console(stderr=True, legacy_windows=False)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _fmt_score(score: float) -> str:
    if score >= 80:
        return f"[bold green]{score:.1f}[/bold green]"
    if score >= 60:
        return f"[bold yellow]{score:.1f}[/bold yellow]"
    return f"[bold red]{score:.1f}[/bold red]"


def send_console_alert(payload: dict[str, Any]) -> None:
    """Rich-formatted console alert for a signal."""
    score_str = _fmt_score(payload.get("score", 0.0))
    direction = payload.get("signal_type", "forward").upper()
    colour = {"FORWARD": "cyan", "REVERSE": "red", "META": "magenta"}.get(direction, "white")

    panel_text = Text.assemble(
        ("Market: ", "bold"), (payload.get("market_title", ""), "white"), "\n",
        ("Source: ", "bold"), (payload.get("source_platform", ""), "dim"), "\n",
        ("Signal: ", "bold"), (direction, colour), "  Score: ", (score_str, ""),  "\n",
        ("Confidence: ", "bold"), (f"{payload.get('confidence', 0):.0%}", ""), "  ",
        ("Uncertainty: ", "bold"), (f"{payload.get('uncertainty_score', 0):.0%}", ""), "\n",
        ("Action: ", "bold"), (payload.get("suggested_action", ""), "bold white"), "\n",
        ("Reason: ", "bold dim"), (payload.get("reasoning_summary", ""), "dim"),
    )
    _console.print(Panel(panel_text, title="⚡ UPAS Signal", border_style=colour))


def send_telegram_alert(payload: dict[str, Any]) -> bool:
    """Send alert via Telegram Bot API. Returns True on success."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.warning("alert_tool.telegram.not_configured")
        return False

    score = payload.get("score", 0.0)
    direction = payload.get("signal_type", "forward").upper()
    emoji = {"FORWARD": "📈", "REVERSE": "📉", "META": "🔮"}.get(direction, "⚡")

    text = (
        f"{emoji} *UPAS Signal*\n"
        f"*Market:* {payload.get('market_title', '')}\n"
        f"*Source:* {payload.get('source_platform', '')}\n"
        f"*Type:* {direction}  *Score:* `{score:.1f}`\n"
        f"*Confidence:* {payload.get('confidence', 0):.0%}  "
        f"*Uncertainty:* {payload.get('uncertainty_score', 0):.0%}\n"
        f"*Action:* `{payload.get('suggested_action', '')}`\n"
        f"*Reason:* _{payload.get('reasoning_summary', '')}_\n"
        f"`{payload.get('timestamp', _now())}`"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            url,
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("alert_tool.telegram.sent")
        return True
    except Exception as e:
        logger.error("alert_tool.telegram.error", extra={"error": str(e)})
        return False


def send_alert(
    market_title: str,
    source_platform: str,
    signal_type: str,
    score: float,
    confidence: float,
    uncertainty_score: float,
    reasoning_summary: str,
    suggested_action: str,
    timestamp: str | None = None,
) -> dict[str, Any]:
    """
    Main entry point. Sends alerts to all configured channels.
    Returns: { sent_channels: List[str], timestamp: str }
    """
    payload = {
        "market_title": market_title,
        "source_platform": source_platform,
        "signal_type": signal_type,
        "score": score,
        "confidence": confidence,
        "uncertainty_score": uncertainty_score,
        "reasoning_summary": reasoning_summary,
        "suggested_action": suggested_action,
        "timestamp": timestamp or _now(),
    }

    sent: list[str] = []

    if "console" in ALERT_CHANNELS:
        send_console_alert(payload)
        sent.append("console")

    if "telegram" in ALERT_CHANNELS:
        if send_telegram_alert(payload):
            sent.append("telegram")

    logger.info("alert_tool.sent", extra={"channels": sent, "score": score})
    return {"sent_channels": sent, "timestamp": payload["timestamp"]}
