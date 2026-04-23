---
aliases: [Tools Index, Tool List]
tags: [index, tool]
type: index
related: [[HOME]], [[tools/polymarket-tool]], [[tools/kalshi-tool]], [[tools/database-tool]], [[tools/alert-tool]], [[tools/strategy-tool]], [[tools/mcp-bridge]], [[tools/npm-bridge]], [[tools/checkpoint-tool]], [[tools/uncertainty-tool]], [[tools/tool-registry]], [[tools/tool-discovery]]
---

← [[HOME]]

# Tools Index

All tools live in `tools/`. Every tool exposes a typed interface, returns normalized data, supports JSON-schema output, logs I/O and errors, and declares its dependencies.

| Tool | File | Purpose |
|---|---|---|
| [[tools/polymarket-tool]] | `tools/polymarket_tool.py` | Fetch markets from Polymarket CLOB API |
| [[tools/kalshi-tool]] | `tools/kalshi_tool.py` | Fetch markets from Kalshi API |
| [[tools/database-tool]] | `tools/database_tool.py` | SQLite CRUD, dedup, migrations |
| [[tools/alert-tool]] | `tools/alert_tool.py` | Console + Telegram alerts |
| [[tools/strategy-tool]] | `tools/strategy_tool.py` | Strategy registry + dispatcher |
| [[tools/mcp-bridge]] | `tools/mcp_bridge.py` | MCP client — all MCP calls go here |
| [[tools/npm-bridge]] | `tools/npm_bridge.py` | npm package bridge |
| [[tools/checkpoint-tool]] | `tools/checkpoint_tool.py` | Save/load pipeline state |
| [[tools/uncertainty-tool]] | `tools/uncertainty_tool.py` | Uncertainty engine interface |
| [[tools/tool-registry]] | `tools/tool_registry.py` | Central tool registry |
| [[tools/tool-discovery]] | `tools/tool_discovery.py` | Search for existing tools before building |

## Tool Contract

Every tool must:
1. Expose a typed `run()` or equivalent function
2. Return normalized data matching a defined schema
3. Be reusable by all subagents
4. Log inputs/outputs/errors via structured logger
5. Declare its dependencies and fallbacks

## Related

[[agents/INDEX]] · [[architecture/tool-reuse-policy]] · [[tools/tool-registry]]
