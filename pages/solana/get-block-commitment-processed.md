# `` method does not support commitment below `confirmed` ``

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 200 `-32602`**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-25 · 57 confirmations from 2 vantages

> getBlock with commitment processed returns JSON-RPC error -32602 Method does not support commitment below \`confirmed\`.

## What to do

1. Set body parameter params\[1\].commitment to confirmed.

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:block-commitment-processed` (declarative, [source](../../probes/solana/block-commitment-processed.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":200,"body_excerpt":"method does not support commitment below `confirmed`"}}'
```

YAML: [facts/solana/get-block-commitment-processed.yaml](../../facts/solana/get-block-commitment-processed.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
