"""
tools/mcp_bridge.py
MCP client bridge — all MCP calls in UPAS go through this module.
Uses the mcp Python SDK with stdio transport.
"""
from __future__ import annotations

import json
from typing import Any

from config.variables import MCP_ENABLED
from logging_config.structured_logger import get_logger

logger = get_logger(__name__)


class MCPBridge:
    """
    Bridge to MCP servers. Wraps the mcp Python SDK.
    All agents call this — never call MCP directly from strategy code.
    """

    def __init__(self, server_command: list[str] | None = None):
        self._server_command = server_command
        self._session = None
        self._available = False

        if not MCP_ENABLED:
            logger.info("mcp_bridge.disabled")
            return

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
            self._ClientSession = ClientSession
            self._StdioServerParameters = StdioServerParameters
            self._stdio_client = stdio_client
            self._available = True
            logger.info("mcp_bridge.ready")
        except ImportError:
            logger.warning("mcp_bridge.sdk_not_installed", extra={"hint": "pip install mcp"})

    @property
    def available(self) -> bool:
        return self._available and MCP_ENABLED

    async def call_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        server_command: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Call an MCP tool by name. Returns { result, error }.
        Falls back to error dict if MCP unavailable.
        """
        if not self.available:
            logger.warning("mcp_bridge.call_tool.unavailable", extra={"tool": tool_name})
            return {"result": None, "error": "MCP not available"}

        cmd = server_command or self._server_command
        if not cmd:
            return {"result": None, "error": "No MCP server command configured"}

        import time
        t0 = time.time()
        try:
            params = self._StdioServerParameters(command=cmd[0], args=cmd[1:])
            async with self._stdio_client(params) as (read, write):
                async with self._ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    elapsed = round(time.time() - t0, 3)
                    logger.info(
                        "mcp_bridge.call_tool.success",
                        extra={"tool": tool_name, "elapsed_s": elapsed},
                    )
                    return {"result": result, "error": None}
        except Exception as e:
            elapsed = round(time.time() - t0, 3)
            logger.error(
                "mcp_bridge.call_tool.error",
                extra={"tool": tool_name, "error": str(e), "elapsed_s": elapsed},
            )
            return {"result": None, "error": str(e)}

    async def list_tools(self, server_command: list[str] | None = None) -> list[str]:
        """List available tools from an MCP server."""
        if not self.available:
            return []
        cmd = server_command or self._server_command
        if not cmd:
            return []
        try:
            params = self._StdioServerParameters(command=cmd[0], args=cmd[1:])
            async with self._stdio_client(params) as (read, write):
                async with self._ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    return [t.name for t in tools.tools]
        except Exception as e:
            logger.error("mcp_bridge.list_tools.error", extra={"error": str(e)})
            return []


# Singleton instance
_bridge = MCPBridge()


def get_bridge() -> MCPBridge:
    """Return the singleton MCP bridge instance."""
    return _bridge
