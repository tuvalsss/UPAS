"""
tools/npm_bridge.py
NPM package bridge — discovers and uses npm-based MCP servers via subprocess.
Windows-safe: uses pathlib and subprocess with list args.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


def _npx_available() -> bool:
    return shutil.which("npx") is not None


def run_npx_command(
    package: str,
    args: list[str],
    cwd: Path | None = None,
    timeout: int = 30,
) -> dict[str, Any]:
    """
    Run an npx command safely on Windows.
    Returns: { stdout, stderr, returncode, error }
    """
    if not _npx_available():
        return {"stdout": "", "stderr": "", "returncode": -1, "error": "npx not found in PATH"}

    cmd = ["npx", "--yes", package] + args
    logger.info("npm_bridge.run", extra={"package": package, "args": args})

    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
            "error": None if result.returncode == 0 else result.stderr,
        }
    except subprocess.TimeoutExpired:
        logger.error("npm_bridge.timeout", extra={"package": package})
        return {"stdout": "", "stderr": "", "returncode": -1, "error": "timeout"}
    except Exception as e:
        logger.error("npm_bridge.error", extra={"error": str(e)})
        return {"stdout": "", "stderr": "", "returncode": -1, "error": str(e)}


def get_mcp_server_command(package: str, args: list[str] | None = None) -> list[str]:
    """Return the command list to start an npm-based MCP server via npx."""
    return ["npx", "--yes", package] + (args or [])


def check_npm_package_exists(package: str) -> bool:
    """Check if an npm package exists (via npm view)."""
    if not shutil.which("npm"):
        return False
    try:
        result = subprocess.run(
            ["npm", "view", package, "name"],
            capture_output=True, text=True, timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False
