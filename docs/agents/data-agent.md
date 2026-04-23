---
aliases: [Data Agent, Storage Agent]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[tools/database-tool]], [[database/schema]], [[database/market-schema]], [[database/signal-schema]]
---

← [[agents/INDEX]]

# data-agent

## Role

Owns all storage operations: normalization, deduplication, schema migrations. No other agent writes directly to the database — they go through data-agent.

## Responsibilities

- Deduplicate markets by `market_id + timestamp + source`
- Apply safe additive migrations (never destructive)
- Log every write to `audit_logs`
- Ensure `audit_logs` and `questions_asked` are append-only

## Tools Used

- [[tools/database-tool]]

## File

`.claude/agents/data-agent.md`

## Related

[[database/schema]] · [[tools/database-tool]] · [[agents/ml-agent]] · [[agents/rl-agent]]
