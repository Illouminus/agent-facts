# `method not found`

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 200 `-32601`**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-25 · 57 confirmations from 2 vantages

> getRecentBlockhash is removed from mainnet RPC nodes: calling it returns JSON-RPC error -32601 Method not found; its replacement is getLatestBlockhash.

## What to do

1. Set body parameter method to getLatestBlockhash.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:methods-removed` (declarative, [source](../../probes/solana/methods-removed.yaml)) · official doc: <https://solana.com/docs/rpc/deprecated#migration-summary>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":200,"body_excerpt":"method not found"}}'
```

YAML: [facts/solana/get-recent-blockhash-removed.yaml](../../facts/solana/get-recent-blockhash-removed.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
