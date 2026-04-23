---
aliases: [ai-uni, Central Orchestrator, Orchestrator]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/scanner-agent]], [[agents/strategy-agent]], [[agents/reverse-strategy-agent]], [[agents/uncertainty-agent]], [[agents/tool-discovery-agent]], [[modules/question-router]], [[pipeline/flow]]
---

← [[agents/INDEX]]

# ai-uni — Central Orchestrator

## Role

Routes all tasks through the UPAS pipeline, maintains pipeline state, and escalates to the user when confidence is below threshold. ai-uni **never executes strategies directly** — it delegates to specialist subagents.

## Spawn Protocol

```
input
  └→ uncertainty-agent.check(input)
  └→ tool-discovery-agent.check(requirement)
      ├─ if clear → route to specialist subagent
      ├─ if ambiguous → question_router.ask(user) → wait → resume
      └─ collect output → merge → pass to next stage
```

## Responsibilities

- Maintain run_id and pipeline state
- Route signals to the correct specialist agent
- Merge outputs from multiple agents
- Trigger checkpoints between stages
- Escalate unresolvable uncertainty to user
- Never duplicate logic owned by specialist agents

## File

`.claude/agents/ai-uni.md`

## Related

[[pipeline/flow]] · [[agents/uncertainty-agent]] · [[agents/tool-discovery-agent]] · [[modules/question-router]] · [[tools/checkpoint-tool]]
