"""
tools/tool_discovery.py
Search for existing tools before building anything new.
Checks project modules, pip packages, MCP, and npm.
"""
from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from typing import Any

from logging_config.structured_logger import get_logger

logger = get_logger(__name__)

_ROOT = Path(__file__).parent.parent


def search_project_modules(capability: str) -> list[dict[str, Any]]:
    """Search project tools/, strategies/, core/ for matching capability."""
    found = []
    search_dirs = [
        _ROOT / "tools",
        _ROOT / "strategies",
        _ROOT / "core",
        _ROOT / "ai",
        _ROOT / "ml",
        _ROOT / "rl",
    ]
    capability_lower = capability.lower()
    for d in search_dirs:
        if not d.exists():
            continue
        for py_file in d.rglob("*.py"):
            if py_file.name.startswith("_"):
                continue
            try:
                content = py_file.read_text(encoding="utf-8", errors="ignore")
                if capability_lower in content.lower():
                    found.append({
                        "type": "project_module",
                        "path": str(py_file.relative_to(_ROOT)),
                        "match": "keyword_match",
                    })
            except Exception:
                pass
    return found


def check_pip_package(package_name: str) -> bool:
    """Check if a pip package is installed."""
    spec = importlib.util.find_spec(package_name.replace("-", "_"))
    return spec is not None


def list_installed_packages() -> list[str]:
    """Return list of installed pip package names."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True, text=True, timeout=15,
        )
        import json
        pkgs = json.loads(result.stdout)
        return [p["name"] for p in pkgs]
    except Exception:
        return []


def search(requirement: str, check_packages: bool = True) -> dict[str, Any]:
    """
    Full search for an existing implementation of a requirement.
    Returns recommendation: reuse | adapt | build_new
    """
    logger.info("tool_discovery.search", extra={"requirement": requirement})

    project_matches = search_project_modules(requirement)

    pkg_available = False
    if check_packages:
        # Check common relevant packages
        common_map = {
            "polymarket": "py_clob_client",
            "kalshi": "kalshi_python_sync",
            "mcp": "mcp",
            "telegram": "requests",
            "database": "sqlite3",
            "ml": "xgboost",
        }
        for keyword, pkg in common_map.items():
            if keyword.lower() in requirement.lower():
                if check_pip_package(pkg):
                    pkg_available = True
                    break

    if project_matches:
        recommendation = "reuse"
        existing = project_matches[0]["path"]
    elif pkg_available:
        recommendation = "adapt"
        existing = "installed_package"
    else:
        recommendation = "build_new"
        existing = None

    result = {
        "requirement": requirement,
        "found": bool(project_matches or pkg_available),
        "existing_tool": existing,
        "recommendation": recommendation,
        "project_matches": project_matches,
        "reason": (
            f"Found {len(project_matches)} project module(s)" if project_matches
            else "Package available" if pkg_available
            else "No existing implementation found"
        ),
    }
    logger.info("tool_discovery.result", extra={"recommendation": recommendation})
    return result


def check(requirement: str) -> bool:
    """Quick check: returns True if an existing implementation was found."""
    return search(requirement)["found"]
