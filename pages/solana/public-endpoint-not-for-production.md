# The public RPC endpoints are not intended for production applications, and their rate limits are subject to change without prior notice.

**Solana JSON-RPC (public mainnet endpoint) · POST /**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://solana.com/docs/references/clusters#mainnet-rate-limits>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"}}'
```

YAML: [facts/solana/public-endpoint-not-for-production.yaml](../../facts/solana/public-endpoint-not-for-production.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
