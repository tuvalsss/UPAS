---
aliases: [Tool Reuse Policy, Reuse Before Build]
tags: [architecture, concept]
type: concept
related: [[HOME]], [[architecture/reverse-thinking]], [[tools/tool-discovery]], [[tools/tool-registry]], [[agents/tool-discovery-agent]]
---

← [[HOME]] → [[architecture/overview]]

# Tool Reuse Policy

## Rule

> **Never write new code if an existing tool, package, MCP server, or module already does the job.**

## Enforcement

[[agents/tool-discovery-agent]] runs before any new tool is implemented. It checks:

1. Project modules in `tools/`, `strategies/`, `core/`
2. Installed Python packages (`pip list`)
3. Available MCP servers (via [[tools/mcp-bridge]])
4. npm packages (via [[tools/npm-bridge]])
5. Claude Code skills in `.claude/skills/`

## Decision Log

Every decision — reuse or new code — is logged to `tool_registry_snapshot` table (see [[database/schema]]).

Format:
```json
{
  "timestamp": "ISO8601",
  "component": "string",
  "decision": "reuse | new",
  "existing_tool": "string or null",
  "reason": "string"
}
```

## Config

From [[config/settings]]: `use_existing_tools_first: true`

Set to `false` only in testing environments where you want to force fresh implementations.

## Related

[[tools/tool-registry]] · [[tools/tool-discovery]] · [[agents/tool-discovery-agent]] · [[agents/reviewer-agent]]
