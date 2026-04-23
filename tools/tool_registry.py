"""
tools/tool_registry.py
Central registry of all available tools — tracks reuse/new-code decisions.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from tools.database_tool import log_tool_decision
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_REGISTRY: dict[str, dict[str, Any]] = {
    "polymarket_tool": {
        "file": "tools/polymarket_tool.py",
        "description": "Fetch markets from Polymarket CLOB API",
        "capabilities": ["fetch_markets", "get_market_by_id"],
        "dependencies": ["requests", "config.variables"],
        "status": "active",
    },
    "kalshi_tool": {
        "file": "tools/kalshi_tool.py",
        "description": "Fetch markets from Kalshi API (RSA-PSS auth)",
        "capabilities": ["fetch_markets", "get_market_by_ticker"],
        "dependencies": ["requests", "cryptography", "config.variables"],
        "status": "active",
    },
    "database_tool": {
        "file": "tools/database_tool.py",
        "description": "SQLite CRUD, deduplication, migrations",
        "capabilities": ["upsert_market", "insert_signal", "save_checkpoint", "append_audit_log"],
        "dependencies": ["sqlite3"],
        "status": "active",
    },
    "alert_tool": {
        "file": "tools/alert_tool.py",
        "description": "Console + Telegram alert delivery",
        "capabilities": ["send_alert", "send_console_alert", "send_telegram_alert"],
        "dependencies": ["requests", "rich"],
        "status": "active",
    },
    "strategy_tool": {
        "file": "tools/strategy_tool.py",
        "description": "Strategy registry and dispatcher",
        "capabilities": ["run_strategies", "list_strategies"],
        "dependencies": [],
        "status": "active",
    },
    "mcp_bridge": {
        "file": "tools/mcp_bridge.py",
        "description": "MCP client bridge — all MCP calls go here",
        "capabilities": ["call_tool", "list_tools"],
        "dependencies": ["mcp"],
        "status": "active",
    },
    "npm_bridge": {
        "file": "tools/npm_bridge.py",
        "description": "npm/npx MCP server subprocess wrapper",
        "capabilities": ["run_npx_command", "get_mcp_server_command"],
        "dependencies": ["subprocess"],
        "status": "active",
    },
    "checkpoint_tool": {
        "file": "tools/checkpoint_tool.py",
        "description": "Save/load pipeline state for resumable runs",
        "capabilities": ["save", "load", "status"],
        "dependencies": ["tools.database_tool"],
        "status": "active",
    },
    "uncertainty_tool": {
        "file": "tools/uncertainty_tool.py",
        "description": "Uncertainty engine interface",
        "capabilities": ["assess", "is_safe"],
        "dependencies": ["core.uncertainty_engine"],
        "status": "active",
    },
    "tool_registry": {
        "file": "tools/tool_registry.py",
        "description": "This registry",
        "capabilities": ["list_tools", "get_tool", "log_decision"],
        "dependencies": [],
        "status": "active",
    },
    "tool_discovery": {
        "file": "tools/tool_discovery.py",
        "description": "Search for existing tools before building new ones",
        "capabilities": ["search", "check"],
        "dependencies": [],
        "status": "active",
    },
}


def list_tools() -> list[dict[str, Any]]:
    """Return all registered tools with metadata."""
    return [{"name": k, **v} for k, v in _REGISTRY.items()]


def get_tool(name: str) -> dict[str, Any] | None:
    """Get metadata for a specific tool."""
    return _REGISTRY.get(name)


def log_decision(
    component: str,
    decision: str,
    existing_tool: str | None,
    reason: str,
) -> None:
    """Log a reuse-vs-new-code decision to the database."""
    try:
        log_tool_decision(component, decision, existing_tool, reason)
    except Exception:
        pass  # Don't fail the pipeline if logging fails
    logger.info(
        "tool_registry.decision",
        extra={"component": component, "decision": decision, "existing": existing_tool},
    )


def snapshot() -> dict[str, Any]:
    """Return a full snapshot of the registry state."""
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_count": len(_REGISTRY),
        "tools": list_tools(),
    }
