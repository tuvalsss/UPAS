---
aliases: [Uncertainty Agent]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[modules/uncertainty-engine]], [[modules/assumption-guard]], [[architecture/uncertainty-model]]
---

← [[agents/INDEX]]

# uncertainty-agent

## Role

Runs before every major pipeline action. Flags missing inputs, ambiguous requirements, and unsafe assumptions. Blocks the pipeline when confidence is below threshold.

## Checks

1. Are all required market fields present?
2. Are there conflicting signals that cannot be resolved?
3. Is any assumption being made without explicit data?
4. Is the blast radius of a wrong assumption acceptable?

## Output

```json
{
  "confidence": 0.0,
  "uncertainty": 0.0,
  "gaps": [],
  "conflicts": [],
  "safe_to_proceed": true
}
```

## File

`.claude/agents/uncertainty-agent.md`

## Related

[[modules/uncertainty-engine]] · [[modules/assumption-guard]] · [[modules/question-router]] · [[architecture/uncertainty-model]]
