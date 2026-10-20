# Public mainnet responses carry x-ratelimit-\* headers: tier free, a per-method limit (x-ratelimit-method-limit), a per-IP rate limit (x-ratelimit-rps-limit) and x-ratelimit-conn-limit 40.

**Solana JSON-RPC (public mainnet endpoint) · POST /**

Status: ✅ verified:server:prod · first seen 2026-10-20 · last confirmed 2026-10-20 · 2 confirmations from 1 vantage

## What to do

1. Wait the number of seconds in Retry-After, then retry (≤ 3 attempts).

## Dimensions

env: prod · plan: any · region: any · account_state: anonymous

## Evidence

Probe `af:solana:probe:rate-limit-headers` (declarative, [source](../../probes/solana/rate-limit-headers.yaml))

Observations: none from reporters yet.

## Machine access

```sh
curl -s https://facts.baillot.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"}}'
```

YAML: [facts/solana/per-method-rate-limit-headers.yaml](../../facts/solana/per-method-rate-limit-headers.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
