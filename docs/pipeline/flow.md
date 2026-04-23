---
aliases: [Pipeline Flow, Full Pipeline]
tags: [architecture, concept]
type: concept
related: [[HOME]], [[architecture/overview]], [[pipeline/scheduler]], [[agents/ai-uni]], [[tools/checkpoint-tool]], [[modules/uncertainty-engine]]
---

← [[HOME]] → [[architecture/overview]]

# Pipeline Flow

## Full Pipeline Diagram

```mermaid
flowchart TD
    A[CLI trigger\nscan / live] --> B[ai-uni\norchestrator]
    B --> C[uncertainty-agent\ncheck inputs]
    C --> D[tool-discovery-agent\ncheck existing tools]
    D --> E[scanner-agent\nfetch markets]
    E --> F[Polymarket CLOB API]
    E --> G[Kalshi API]
    F & G --> H[Normalize\nstandard market object]
    H --> I[strategy-agent\ncore + meta strategies]
    H --> J[reverse-strategy-agent\nreverse strategies]
    I --> K[signal objects\nforward + meta]
    J --> L[signal objects\nreverse]
    K & L --> M[reverse_validator\ncheck forward vs reverse]
    M --> N{confidence\n≥ threshold?}
    N -- No --> O[question_router\nask user]
    O --> P[wait for answer\ncheckpoint saved]
    P --> N
    N -- Yes --> Q[ai-uni scorer\n0-100 ranking]
    Q --> R[data-agent\nstore to SQLite]
    R --> S[alert-tool\nconsole + Telegram]
    R --> T[checkpoint-tool\nsave state]
    T --> U[ml-agent\nlog training record]
    U --> V[rl-agent\nupdate policy]
    V --> W[ranked signals\noutput]
```

## Stage Descriptions

| Stage | Agent/Tool | Output |
|---|---|---|
| Scan | [[agents/scanner-agent]] | Raw market data |
| Normalize | [[agents/scanner-agent]] | Standard market objects |
| Core Strategy | [[agents/strategy-agent]] | Forward signals |
| Reverse Strategy | [[agents/reverse-strategy-agent]] | Reverse signals |
| Meta Strategy | [[agents/strategy-agent]] | Meta signals |
| Uncertainty Check | [[agents/uncertainty-agent]] | Confidence score |
| AI Score | [[agents/ai-uni]] + [[modules/ai]] | Ranked signal list |
| Store | [[agents/data-agent]] | SQLite rows |
| Alert | [[tools/alert-tool]] | Console / Telegram |
| Checkpoint | [[tools/checkpoint-tool]] | Saved state |

## Related

[[pipeline/scheduler]] · [[architecture/checkpointing]] · [[architecture/uncertainty-model]]
