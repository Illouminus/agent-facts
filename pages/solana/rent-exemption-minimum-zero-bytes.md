# On 2026-10-20 getMinimumBalanceForRentExemption with dataLength 0 returned 650240 lamports on mainnet.

**Solana JSON-RPC (public mainnet endpoint) · POST /**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-28 · 92 confirmations from 2 vantages

## What to do

1. No client-side fix known (by design).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:rent-exemption-zero-bytes` (declarative, [source](../../probes/solana/rent-exemption-zero-bytes.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"}}'
```

YAML: [facts/solana/rent-exemption-minimum-zero-bytes.yaml](../../facts/solana/rent-exemption-minimum-zero-bytes.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
