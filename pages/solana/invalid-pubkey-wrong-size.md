# `invalid param: wrongsize`

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 200 `-32602`**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-20 · 1 confirmation from 1 vantage

> getBalance with a string that is not a base-58 public key returns JSON-RPC error -32602 Invalid param: WrongSize.

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:invalid-pubkey` (declarative, [source](../../probes/solana/invalid-pubkey.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":200,"body_excerpt":"invalid param: wrongsize"}}'
```

YAML: [facts/solana/invalid-pubkey-wrong-size.yaml](../../facts/solana/invalid-pubkey-wrong-size.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
