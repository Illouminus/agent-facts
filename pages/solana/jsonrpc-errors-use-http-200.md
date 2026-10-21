# JSON-RPC errors from the public mainnet endpoint, such as -32601 Method not found, arrive with HTTP status 200; only the error object in the body signals the failure.

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 200**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-21 · 13 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:methods-removed` (declarative, [source](../../probes/solana/methods-removed.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":200}}'
```

YAML: [facts/solana/jsonrpc-errors-use-http-200.yaml](../../facts/solana/jsonrpc-errors-use-http-200.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
