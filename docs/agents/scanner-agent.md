---
aliases: [Scanner Agent]
tags: [agent]
type: agent
related: [[agents/INDEX]], [[agents/ai-uni]], [[tools/polymarket-tool]], [[tools/kalshi-tool]], [[database/market-schema]], [[pipeline/flow]]
---

← [[agents/INDEX]]

# scanner-agent

## Role

Fetches markets from Polymarket and Kalshi, normalizes them to the [[database/market-schema]], and deduplicates by `market_id + source`.

## Tools Used

- [[tools/polymarket-tool]] — CLOB API fetch
- [[tools/kalshi-tool]] — Kalshi SDK fetch
- [[tools/database-tool]] — dedup check

## Output

List of standard market objects:
```json
{
  "market_id": "string",
  "title": "string",
  "source": "polymarket | kalshi",
  "yes_price": 0.0,
  "no_price": 0.0,
  "liquidity": 0.0,
  "volume": 0.0,
  "expiry_timestamp": "ISO8601",
  "fetched_at": "ISO8601",
  "raw": {}
}
```

## Filters Applied

From [[config/settings]]:
- `yes_price_min / yes_price_max`
- `liquidity_min`
- `expiry_hours_max`

## File

`.claude/agents/scanner-agent.md`

## Related

[[tools/polymarket-tool]] · [[tools/kalshi-tool]] · [[database/market-schema]] · [[agents/data-agent]]
