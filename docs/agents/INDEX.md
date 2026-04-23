---
aliases: [Agents Index, Agent List]
tags: [index, agent]
type: index
related: [[HOME]], [[agents/ai-uni]], [[agents/scanner-agent]], [[agents/strategy-agent]], [[agents/reverse-strategy-agent]], [[agents/data-agent]], [[agents/ml-agent]], [[agents/rl-agent]], [[agents/reviewer-agent]], [[agents/uncertainty-agent]], [[agents/tool-discovery-agent]]
---

← [[HOME]]

# Agents Index

All agents are defined in `.claude/agents/` as Claude Code subagent markdown files.

| Agent | Role | File |
|---|---|---|
| [[agents/ai-uni]] | Central orchestrator | `.claude/agents/ai-uni.md` |
| [[agents/scanner-agent]] | Fetch + normalize markets | `.claude/agents/scanner-agent.md` |
| [[agents/strategy-agent]] | Core + meta strategies | `.claude/agents/strategy-agent.md` |
| [[agents/reverse-strategy-agent]] | Reverse validation | `.claude/agents/reverse-strategy-agent.md` |
| [[agents/data-agent]] | Storage + dedup | `.claude/agents/data-agent.md` |
| [[agents/ml-agent]] | XGBoost training | `.claude/agents/ml-agent.md` |
| [[agents/rl-agent]] | Reward + policy | `.claude/agents/rl-agent.md` |
| [[agents/reviewer-agent]] | Quality + drift | `.claude/agents/reviewer-agent.md` |
| [[agents/uncertainty-agent]] | Ambiguity detection | `.claude/agents/uncertainty-agent.md` |
| [[agents/tool-discovery-agent]] | Reuse before build | `.claude/agents/tool-discovery-agent.md` |

## Spawn Protocol (ai-uni)

```
input → uncertainty-agent → tool-discovery-agent
  → if clear: route to specialist
  → if ambiguous: question_router → ask user → wait → resume
  → collect output → merge → next stage
```

## Related

[[pipeline/flow]] · [[tools/INDEX]] · [[architecture/overview]]
