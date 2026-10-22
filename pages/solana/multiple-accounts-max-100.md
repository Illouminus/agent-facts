# `too many inputs provided; max ###`

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 200 `-32602`**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 27 confirmations from 2 vantages

> getMultipleAccounts with more than 100 public keys returns JSON-RPC error -32602 Too many inputs provided; max 100.

## What to do

1. Keep params\[0\] ≤ 100 items.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:multiple-accounts-limit` (declarative, [source](../../probes/solana/multiple-accounts-limit.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":200,"body_excerpt":"too many inputs provided; max ###"}}'
```

YAML: [facts/solana/multiple-accounts-max-100.yaml](../../facts/solana/multiple-accounts-max-100.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
