---
aliases: [Market Schema, Market Object]
tags: [reference]
type: reference
related: [[database/schema]], [[agents/scanner-agent]], [[tools/polymarket-tool]], [[tools/kalshi-tool]]
---

← [[database/schema]]

# Market Schema — Standard Market Object

All markets from Polymarket and Kalshi are normalized to this schema before any strategy runs.

## JSON Schema

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

## Field Definitions

| Field | Type | Description |
|---|---|---|
| `market_id` | string | Platform-native market identifier |
| `title` | string | Human-readable market question |
| `source` | enum | `polymarket` or `kalshi` |
| `yes_price` | float 0–1 | Current YES outcome price |
| `no_price` | float 0–1 | Current NO outcome price (often 1 - yes_price) |
| `liquidity` | float USD | Total available liquidity |
| `volume` | float USD | Total trading volume |
| `expiry_timestamp` | ISO8601 | When the market resolves |
| `fetched_at` | ISO8601 | When we retrieved this snapshot |
| `raw` | dict | Unmodified API response — preserved for debugging |

## Deduplication Key

`(market_id, source, fetched_at)` — see [[database/schema]]

## Related

[[database/schema]] · [[agents/scanner-agent]] · [[tools/polymarket-tool]] · [[tools/kalshi-tool]]
