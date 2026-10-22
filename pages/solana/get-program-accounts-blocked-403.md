# `your ip or provider is blocked from this endpoint`

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 403 `403`**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-22 · 21 confirmations from 2 vantages

> On 2026-10-20 getProgramAccounts on the public mainnet endpoint returned HTTP 403 with error Your IP or provider is blocked from this endpoint to an IP whose other calls were served.

## What to do

1. No client-side fix known (vendor side).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:program-accounts-blocked` (declarative, [source](../../probes/solana/program-accounts-blocked.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":403,"body_excerpt":"your ip or provider is blocked from this endpoint"}}'
```

YAML: [facts/solana/get-program-accounts-blocked-403.yaml](../../facts/solana/get-program-accounts-blocked-403.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
