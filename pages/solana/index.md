# Solana JSON-RPC (public mainnet endpoint)

Hosts: `api.mainnet-beta.solana.com`, `api.mainnet.solana.com` · 14 facts

## Error meanings

- ✅ verified:server:prod · [`` method does not support commitment below `confirmed` ``](get-block-commitment-processed.md) · POST / · env prod
- ✅ verified:server:prod · [`invalid param: wrongsize`](invalid-pubkey-wrong-size.md) · POST / · env prod
- ✅ verified:server:prod · [`too many inputs provided; max ###`](multiple-accounts-max-100.md) · POST / · env prod
- ✅ verified:server:prod · [`invalid limit; max ####`](signatures-for-address-limit-1000.md) · POST / · env prod

## Rate limits

- ✅ verified:server:prod · [Public mainnet responses carry x-ratelimit-\* headers: tier free, a per-method limit (x-ratelimit-method-limit), a per-IP rate limit (x-ratelimit-rps-limit) and x-ratelimit-conn-limit 40.](per-method-rate-limit-headers.md) · POST / · env prod
- 🔵 official · [The public mainnet endpoint allows 100 requests per 10 s per IP, 40 per 10 s per IP for a single RPC method, 40 concurrent connections and 100 MB per 30 s; exceeding them returns HTTP 429 with Retry-After.](public-mainnet-rate-limits.md) · POST / · env prod

## Silent behavior

- ✅ verified:server:prod · [JSON-RPC errors from the public mainnet endpoint, such as -32601 Method not found, arrive with HTTP status 200; only the error object in the body signals the failure.](jsonrpc-errors-use-http-200.md) · POST / · env prod
- ✅ verified:server:prod · [On 2026-10-20 getMinimumBalanceForRentExemption with dataLength 0 returned 650240 lamports on mainnet.](rent-exemption-minimum-zero-bytes.md) · POST / · env prod

## Deprecations

- ✅ verified:server:prod · [`method not found`](get-confirmed-block-removed.md) · POST / · env prod
- ✅ verified:server:prod · [`method not found`](get-confirmed-transaction-removed.md) · POST / · env prod
- ✅ verified:server:prod · [`method not found`](get-recent-blockhash-removed.md) · POST / · env prod

## Availability

- ✅ verified:server:prod · [`your ip or provider is blocked from this endpoint`](get-program-accounts-blocked-403.md) · POST / · env prod
- 🔵 official · [On the public RPC endpoints HTTP 403 means the IP address or website has been blocked; high-traffic websites may be blocked without prior notice.](public-endpoint-403-blocked.md) · POST / · env prod
- 🔵 official · [The public RPC endpoints are not intended for production applications, and their rate limits are subject to change without prior notice.](public-endpoint-not-for-production.md) · POST / · env prod

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · agent-facts registry · This page is generated; edit the YAML, not the page.
