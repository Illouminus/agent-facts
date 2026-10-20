"""Builds a throwaway registry repo: the W1 valid fixtures plus one fact per lookup tier."""

import textwrap
from pathlib import Path

VALID = Path(__file__).parents[1] / "fixtures" / "valid"
PEER = ("203.0.113.7", 50000)

STRIPE_PI = "https://api.stripe.com/v1/payment_intents"
IDEMPOTENCY_BODY = (
    '{"error": {"message": "Keys for idempotent requests can only be used with the same '
    'parameters they were first used with.", "type": "idempotency_error"}}'
)
IDEMPOTENCY_ID = "af:stripe:idempotency-key-reuse-different-params"


def _fact(slug: str, body: str) -> str:
    head = f"id: af:stripe:{slug}\nservice: stripe\n"
    tail = """
        dimensions: {env: prod}
        evidence: {first_seen: 2026-10-01T08:00:00Z}
        provenance: {source: manual, author: human:edouard, created: 2026-10-01}
        """
    return head + textwrap.dedent(body).strip() + "\n" + textwrap.dedent(tail).strip() + "\n"


FACTS = {
    "payment-intents-429": _fact(
        "payment-intents-429",
        """
        kind: rate_limit
        target: {surface: http, method: POST, path_template: /v1/payment_intents}
        signal: {status: 429}
        claim: POST /v1/payment_intents returns HTTP 429 above the per-account rate.
        fixes:
          - {action: retry_after_header, unit: s, max_attempts: 3}
        status: reported
        """,
    ),
    "customer-not-found": _fact(
        "customer-not-found",
        """
        kind: error_meaning
        target: {surface: http, method: GET, path_template: "/v1/customers/{id}"}
        signal:
          status: 404
          error_code: resource_missing
          error_string: "No such customer: 'cus_123'"
        claim: GET /v1/customers/{id} returns HTTP 404 resource_missing for a deleted customer.
        fixes:
          - {action: none_known, reason_kind: by_design}
        status: reported
        """,
    ),
    "old-sdk-bad-request": _fact(
        "old-sdk-bad-request",
        """
        kind: breaking_change
        target:
          surface: sdk
          method: POST
          path_template: /v1/payment_intents
          sdk: {package: stripe, ecosystem: pypi, versions: "<12"}
        signal: {status: 400}
        claim: stripe-python before 12 sends a parameter the API now rejects with HTTP 400.
        fixes:
          - {action: upgrade_sdk, package: stripe, ecosystem: pypi, min_version: "12.0.0"}
        status: reported
        """,
    ),
    "withdrawn": _fact(
        "withdrawn",
        """
        kind: availability
        target: {surface: http, method: POST, path_template: /v1/payment_intents}
        signal: {status: 503}
        claim: POST /v1/payment_intents was said to return HTTP 503 during maintenance.
        fixes:
          - {action: none_known, reason_kind: vendor_side}
        status: retracted
        """,
    ),
}

PYPI_SERVICE = """
key: pypi
name: PyPI
hosts: [pypi.org]
surfaces:
  http:
    base_url: https://pypi.org
    templates:
      - {method: GET, path: "/pypi/{project}/json"}
    signal_fields: [status, message]
dimensions:
  env: {prod: https://pypi.org}
tos:
  automated_access: allowed
  publish_measurements: allowed
  source: https://pypi.org/policy/terms-of-use/
"""


def write_repo(root: Path) -> Path:
    files = {
        "services/stripe.yaml": (VALID / "service-stripe.yaml").read_text(encoding="utf-8"),
        "services/pypi.yaml": PYPI_SERVICE,
        "probes/stripe/idempotency-key-reuse.yaml": (
            VALID / "probe-idempotency-key-reuse.yaml"
        ).read_text(encoding="utf-8"),
        "facts/stripe/idempotency-key-reuse-different-params.yaml": (
            VALID / "fact-idempotency-key-reuse-different-params.yaml"
        ).read_text(encoding="utf-8"),
        "facts/stripe/broken.yaml": "id: af:stripe:broken\nservice: stripe\nkind: nonsense\n",
        **{f"facts/stripe/{slug}.yaml": text for slug, text in FACTS.items()},
    }
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return root
