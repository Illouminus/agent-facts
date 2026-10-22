# `invalid limit; max ####`

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 200 `-32602`**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 25 confirmations from 2 vantages

> getSignaturesForAddress with limit above 1000 returns JSON-RPC error -32602 Invalid limit; max 1000 instead of capping the page.

## What to do

1. Paginate by signature via before, ≤ 1000 per page.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:signatures-limit` (declarative, [source](../../probes/solana/signatures-limit.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":200,"body_excerpt":"invalid limit; max ####"}}'
```

YAML: [facts/solana/signatures-for-address-limit-1000.yaml](../../facts/solana/signatures-for-address-limit-1000.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
