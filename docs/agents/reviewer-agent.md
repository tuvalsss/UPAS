---
aliases: [Reviewer Agent, Code Reviewer]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[architecture/tool-reuse-policy]], [[tools/tool-registry]]
---

← [[agents/INDEX]]

# reviewer-agent

## Role

Periodically inspects the codebase for code duplication, architecture drift, and dead code. Runs after major pipeline changes.

## Checks

1. Duplicate logic across modules
2. Tools that bypass [[tools/tool-registry]]
3. Hardcoded values that should be in [[config/settings]]
4. Dead code (unused functions, unreachable branches)
5. Missing uncertainty checks before assumptions
6. Agents that duplicate each other's logic

## Output

Structured report logged to `audit_logs` + console alert.

## File

`.claude/agents/reviewer-agent.md`

## Related

[[architecture/tool-reuse-policy]] · [[tools/tool-registry]] · [[tools/tool-discovery]]
