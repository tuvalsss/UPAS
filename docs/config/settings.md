---
aliases: [Config Settings, Settings Reference]
tags: [config, reference]
type: reference
related: [[HOME]], [[config/variables]], [[architecture/overview]]
---

← [[HOME]]

# Settings Reference

All settings live in `config/settings.yaml`. Imported via `config/variables.py`.

| Key | Default | Description |
|---|---|---|
| `capital` | 1000.0 | Total capital available |
| `risk_per_trade` | 0.02 | Max risk per signal (2%) |
| `scan_interval_seconds` | 60 | Interval between live scans |
| `yes_price_min` | 0.05 | Filter: minimum YES price |
| `yes_price_max` | 0.95 | Filter: maximum YES price |
| `liquidity_min` | 500 | Filter: minimum USD liquidity |
| `expiry_hours_max` | 168 | Filter: max hours to expiry (7 days) |
| `imbalance_threshold` | 0.15 | Threshold for yes/no imbalance signal |
| `ai_enabled` | true | Enable AI scoring module |
| `ml_enabled` | true | Enable ML training module |
| `rl_enabled` | true | Enable RL policy module |
| `mcp_enabled` | true | Enable MCP bridge |
| `claude_auth_mode` | user | `user` = CLI session, `api` = API key |
| `anthropic_model_standard` | claude-sonnet-4-5 | Model for standard tasks |
| `anthropic_model_complex` | claude-opus-4-5 | Model for complex reasoning |
| `checkpoint_interval` | 300 | Auto-checkpoint interval (seconds) |
| `log_level` | INFO | Logging verbosity |
| `ask_before_assuming` | true | Block on any unverified inference |
| `uncertainty_threshold` | 0.65 | Escalate to user above this |
| `reverse_mode_enabled` | true | Run reverse validation |
| `fallback_to_user_question` | true | Ask user if stuck |

## Reverse Thresholds

| Key | Default | Strategy |
|---|---|---|
| `reverse_thresholds.probability_freeze` | 0.03 | [[strategies/reverse/probability-freeze]] |
| `reverse_thresholds.liquidity_vacuum` | 200 | [[strategies/reverse/liquidity-vacuum]] |
| `reverse_thresholds.crowd_fatigue` | 0.6 | [[strategies/reverse/crowd-fatigue]] |
| `reverse_thresholds.whale_exhaustion` | 0.8 | [[strategies/reverse/whale-exhaustion]] |
| `reverse_thresholds.fake_momentum` | 0.4 | [[strategies/reverse/fake-momentum]] |
| `reverse_thresholds.event_shadow_drift` | 0.05 | [[strategies/reverse/event-shadow-drift]] |
| `reverse_thresholds.mirror_event_divergence` | 0.1 | [[strategies/reverse/mirror-event-divergence]] |
| `reverse_thresholds.time_probability_inversion` | 0.07 | [[strategies/reverse/time-probability-inversion]] |

## Related

[[config/variables]] · [[architecture/overview]]
