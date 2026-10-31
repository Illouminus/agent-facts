# `Keys for idempotent requests can only be used with the same parameters they were first used with.`

**Stripe · POST /v1/payment_intents · SDK `stripe` (pypi) `>=7,<13` · HTTP 400 `idempotency_error`**

Status: ✅ verified:server:prod · first seen 2026-10-22 · last confirmed 2026-10-22 · 1 confirmation from 1 vantage

> Reusing an Idempotency-Key with a different request body returns HTTP 400 idempotency_error for 24 hours after the first request.

## What to do

1. Set parameter Idempotency-Key to new UUID per distinct request.

## Example

What probe [`af:stripe:probe:idempotency-key-reuse`](../../probes/stripe/idempotency-key-reuse.yaml) sends (sandbox) and what it checks in the answer; the real key is elided.

Step 1:

```http
POST https://api.stripe.com/v1/payment_intents
Authorization: Bearer <key>
Idempotency-Key: <run_uuid>
Content-Type: application/x-www-form-urlencoded

amount=100&currency=usd
```

Step 2 → HTTP 400:

```http
POST https://api.stripe.com/v1/payment_intents
Authorization: Bearer <key>
Idempotency-Key: <run_uuid>
Content-Type: application/x-www-form-urlencoded

amount=200&currency=usd
```

Response (only what the probe asserts; other fields omitted):

```http
HTTP 400

{
  "error": {
    "code": "idempotency_error",
    "message": "Keys for idempotent requests can only be used with the same parameters they were first used with."
  }
}
```

## In your code

When an SDK receives this response:

| SDK | Raises | Check |
| --- | --- | --- |
| Python `stripe` | `stripe.IdempotencyError` | `e.http_status == 400` · `e.error.type == "idempotency_error"` |
| Node `stripe` | `Stripe.errors.StripeIdempotencyError` | `err.statusCode === 400` · `err.rawType === "idempotency_error"` |

Read from the SDK source: stripe 16.1.0: stripe/\_api_requestor.py specific_v1_api_error, stripe/\_error.py; stripe 23.1.0: cjs/Error.js generateV1Error, cjs/RequestSender.js.

Fix 1:

```python
import uuid
params["Idempotency-Key"] = str(uuid.uuid4())  # a new value per distinct request; reuse it only to retry
```

## Dimensions

env: prod · plan: any · region: any · account_state: any · also seen: [sandbox/test_mode](idempotency-key-reuse-different-params-sandbox.md) (verified 2026-10-29)

## Evidence

Probe `af:stripe:probe:idempotency-key-reuse` (declarative, [source](../../probes/stripe/idempotency-key-reuse.yaml)) · official doc: <https://docs.stripe.com/api/idempotent_requests>

Observations: none from reporters yet.

## Machine access

Match signature (what `check()` matches): `keys for idempotent requests can only be used with the same parameters they were first used with`

```sh
curl -s https://apifacts.dev/v0/check \
  -H 'content-type: application/json' \
  -d '{"target":{"method":"POST","url":"https://api.stripe.com/v1/payment_intents"},"error":{"status":400,"body_excerpt":"keys for idempotent requests can only be used with the same parameters they were first used with"}}'
```

YAML: [facts/stripe/idempotency-key-reuse-different-params.yaml](../../facts/stripe/idempotency-key-reuse-different-params.yaml)

---

Data: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · apifacts registry · This page is generated; edit the YAML, not the page.
