---
aliases: [Database Schema, Tables]
tags: [reference, config]
type: reference
related: [[HOME]], [[database/market-schema]], [[database/signal-schema]], [[database/training-schema]], [[tools/database-tool]]
---

← [[HOME]]

# Database Schema

Engine: **SQLite** · File: `data/upas.db`

## Tables

### markets
Normalized market snapshots from Polymarket and Kalshi.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | auto-increment |
| market_id | TEXT | platform market ID |
| title | TEXT | market question |
| source | TEXT | `polymarket` or `kalshi` |
| yes_price | REAL | 0.0–1.0 |
| no_price | REAL | 0.0–1.0 |
| liquidity | REAL | USD |
| volume | REAL | USD |
| expiry_timestamp | TEXT | ISO8601 |
| fetched_at | TEXT | ISO8601 |
| raw | TEXT | JSON blob of raw API response |
| UNIQUE | — | `(market_id, source, fetched_at)` |

### signals
Generated strategy signals.

| Column | Type | Notes |
|---|---|---|
| signal_id | TEXT PK | UUID |
| market_id | TEXT | FK → markets |
| strategy_name | TEXT | |
| direction | TEXT | `forward`, `reverse`, `meta` |
| score | REAL | 0.0–100.0 |
| confidence | REAL | 0.0–1.0 |
| uncertainty | REAL | 0.0–1.0 |
| reasoning | TEXT | human-readable |
| suggested_action | TEXT | |
| timestamp | TEXT | ISO8601 |

### reverse_signals
Signals from reverse strategies — same schema as `signals` but `direction = "reverse"`.

### scores
AI scoring results per signal.

| Column | Type |
|---|---|
| score_id | TEXT PK |
| signal_id | TEXT FK |
| ai_score | REAL |
| combined_score | REAL |
| confidence | REAL |
| model_used | TEXT |
| timestamp | TEXT |

### results
Realized outcomes for ML training.

| Column | Type |
|---|---|
| result_id | TEXT PK |
| signal_id | TEXT FK |
| market_id | TEXT |
| realized_outcome | INTEGER | `1=correct, 0=wrong, -1=unknown` |
| outcome_timestamp | TEXT |

### checkpoints
Pipeline state snapshots.

| Column | Type |
|---|---|
| checkpoint_id | TEXT PK |
| run_id | TEXT |
| stage | TEXT |
| pipeline_state | TEXT | JSON blob |
| timestamp | TEXT |

### model_artifacts
Saved ML/RL models.

| Column | Type |
|---|---|
| artifact_id | TEXT PK |
| model_type | TEXT | `xgboost`, `rl_policy` |
| artifact_path | TEXT |
| metrics | TEXT | JSON |
| created_at | TEXT |

### audit_logs
**Append-only.** Every write action logged here.

| Column | Type |
|---|---|
| log_id | INTEGER PK |
| timestamp | TEXT |
| action | TEXT |
| actor | TEXT | agent name |
| details | TEXT | JSON |

### questions_asked
**Append-only.** Every question asked to user.

| Column | Type |
|---|---|
| question_id | TEXT PK |
| question_text | TEXT |
| context | TEXT | JSON |
| asked_at | TEXT |
| answered_at | TEXT |
| answer | TEXT |

### clarifications
User answers to pipeline questions.

### uncertainty_events
Every event where confidence fell below threshold.

### tool_registry_snapshot
Reuse-vs-new-code decisions.

| Column | Type |
|---|---|
| entry_id | INTEGER PK |
| timestamp | TEXT |
| component | TEXT |
| decision | TEXT | `reuse` or `new` |
| existing_tool | TEXT |
| reason | TEXT |

## Migration Rules

- Only additive migrations (ADD COLUMN, CREATE TABLE)
- Never DROP or RENAME without explicit user approval
- Schema version tracked in `audit_logs`

## Related

[[database/market-schema]] · [[database/signal-schema]] · [[database/training-schema]] · [[tools/database-tool]]
