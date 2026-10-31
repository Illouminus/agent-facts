# The public mainnet endpoint allows 100 requests per 10 s per IP, 40 per 10 s per IP for a single RPC method, 40 concurrent connections and 100 MB per 30 s; exceeding them returns HTTP 429 with Retry-After.

**Solana JSON-RPC (public mainnet endpoint) · POST / · HTTP 429**

Status: 🔵 official · first seen 2026-10-20

## What to do

1. Wait the number of seconds in Retry-After, then retry (≤ 5 attempts).

## In your code

Fix 1:

```python
import time

for attempt in range(5):
    response = client.send(request)
    if "Retry-After" not in response.headers:
        break
    time.sleep(float(response.headers["Retry-After"]))
```

## Dimensions

env: prod · plan: any · region: any · account_state: any

## Evidence

official doc: <https://solana.com/docs/references/clusters#mainnet-rate-limits>

Observations: none from reporters yet.

## Related errors

- [`Your IP or provider is blocked from this endpoint`](get-program-accounts-blocked-403.md) · POST / · HTTP 403 `403`
- [On the public RPC endpoints HTTP 403 means the IP address or website has been blocked; high-traffic websites may be blocked without prior notice.](public-endpoint-403-blocked.md) · POST / · HTTP 403

## Machine access

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.mainnet-beta.solana.com/"},"error":{"status":429}}'
```

YAML: [facts/solana/public-mainnet-rate-limits.yaml](../../facts/solana/public-mainnet-rate-limits.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
