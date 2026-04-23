---
aliases: [Tool Discovery Agent]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[tools/tool-discovery]], [[tools/tool-registry]], [[architecture/tool-reuse-policy]]
---

← [[agents/INDEX]]

# tool-discovery-agent

## Role

Runs before any new tool or module is implemented. Searches for existing implementations across the project, installed packages, MCP servers, and npm packages.

## Search Order

1. Project `tools/`, `strategies/`, `core/` modules
2. Installed Python packages (`pip list`)
3. Available MCP servers (via [[tools/mcp-bridge]])
4. npm packages (via [[tools/npm-bridge]])
5. Claude Code skills in `.claude/skills/`

## Output

```json
{
  "requirement": "string",
  "found": true,
  "existing_tool": "package_name or file_path",
  "recommendation": "reuse | adapt | build_new",
  "reason": "string"
}
```

## Decision Logged To

`tool_registry_snapshot` table — see [[database/schema]] and [[tools/tool-registry]].

## File

`.claude/agents/tool-discovery-agent.md`

## Related

[[tools/tool-discovery]] · [[tools/tool-registry]] · [[architecture/tool-reuse-policy]] · [[agents/reviewer-agent]]
