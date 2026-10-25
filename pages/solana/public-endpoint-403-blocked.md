# On the public RPC endpoints HTTP 403 means the IP address or website has been blocked; high-traffic websites may be blocked without prior notice.

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 403**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. No client-side fix known (vendor side).

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://solana.com/docs/references/clusters#common-http-error-codes>

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":403}}'
```

YAML: [facts/solana/public-endpoint-403-blocked.yaml](../../facts/solana/public-endpoint-403-blocked.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
