"""Google service-account credentials for probes (`auth.kind: google_service_account`).

The key file holds the JSON key Google issues for a service account. The runner signs a JWT with
its private key (RS256, RFC 7523) and trades it at `GOOGLE_TOKEN_URL` for a short-lived access
token, which the probe sends as Bearer: the JSON key never leaves the runner. The token URL is fixed
here and not read from the key file; a file naming another one is refused. `secrets_of` lists every
secret form of the file for the Redactor; the minted token joins it when it arrives.
"""

import base64
import json
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from agentfacts.probe import USER_AGENT
from agentfacts.probe.http import transport_error_name

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
JWT_BEARER = "urn:ietf:params:oauth:grant-type:jwt-bearer"
TOKEN_LIFETIME_S = 3600
MAX_TOKEN_RESPONSE = 64 * 1024
_EMAIL = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_OAUTH_ERROR = re.compile(r"^[a-z_]{1,64}$")
_PEM_LINE = 16  # base64 lines of a PEM body at least this long are redacted one by one too


class AuthError(Exception):
    """No access token. `message` never carries key material; it is redacted again anyway."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ServiceAccount:
    client_email: str
    private_key: str
    private_key_id: str


def parse_service_account(raw: str) -> ServiceAccount:
    try:
        doc = json.loads(raw)
    except ValueError:
        raise AuthError("bad_key_file", "the key file is not JSON") from None
    if not isinstance(doc, dict) or doc.get("type") != "service_account":
        raise AuthError("bad_key_file", "the key file is not a service-account key")
    fields = {name: doc.get(name) for name in ("client_email", "private_key", "private_key_id")}
    if missing := sorted(name for name, value in fields.items() if not isinstance(value, str)):
        raise AuthError("bad_key_file", f"the key file has no {missing[0]}")
    if not _EMAIL.match(fields["client_email"]):
        raise AuthError("bad_key_file", "client_email is not an e-mail address")
    if not fields["private_key"].lstrip().startswith("-----BEGIN "):
        raise AuthError("bad_key_file", "private_key is not a PEM block")
    if doc.get("token_uri", GOOGLE_TOKEN_URL) != GOOGLE_TOKEN_URL:
        raise AuthError("bad_key_file", f"token_uri is not {GOOGLE_TOKEN_URL}")
    return ServiceAccount(**fields)


def secrets_of(raw: str) -> set[str]:
    """The file itself, and when it parses: the PEM (as is, as escaped inside JSON, line by line)
    and its key id."""
    found = {raw}
    try:
        doc = json.loads(raw)
    except ValueError:
        return found
    if not isinstance(doc, dict):
        return found
    if isinstance(key_id := doc.get("private_key_id"), str):
        found.add(key_id)
    if isinstance(pem := doc.get("private_key"), str):
        found |= {pem, json.dumps(pem)[1:-1]}
        found |= {line for line in pem.splitlines() if len(line.strip()) >= _PEM_LINE}
    return {s for s in found if s.strip()}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64json(value: dict[str, Any]) -> str:
    return _b64(json.dumps(value, separators=(",", ":")).encode())


def signed_assertion(
    sa: ServiceAccount, scopes: Sequence[str], now: datetime, audience: str = GOOGLE_TOKEN_URL
) -> str:
    try:
        key = serialization.load_pem_private_key(sa.private_key.encode(), password=None)
    except (ValueError, TypeError):
        raise AuthError("bad_key_file", "private_key does not load") from None
    if not isinstance(key, rsa.RSAPrivateKey):
        raise AuthError("bad_key_file", "private_key is not an RSA key")
    iat = int(now.timestamp())
    claims = {"iss": sa.client_email, "scope": " ".join(scopes), "aud": audience, "iat": iat,
              "exp": iat + TOKEN_LIFETIME_S}
    signing_input = _b64json({"alg": "RS256", "typ": "JWT", "kid": sa.private_key_id}) + "."
    signing_input += _b64json(claims)
    signature = key.sign(signing_input.encode(), padding.PKCS1v15(), hashes.SHA256())
    return signing_input + "." + _b64(signature)


def mint_access_token(
    client: httpx.Client,
    sa: ServiceAccount,
    scopes: Sequence[str],
    now: datetime,
    token_url: str = GOOGLE_TOKEN_URL,
) -> tuple[str, int]:
    """One token request → (access token, seconds it lives; the JWT's lifetime when Google does
    not say). The audience is the fixed Google token URL even when a test points `token_url` at
    a local server."""
    form = {"grant_type": JWT_BEARER, "assertion": signed_assertion(sa, scopes, now)}
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity"}
    try:
        with client.stream("POST", token_url, data=form, headers=headers) as response:
            raw = bytearray()
            for chunk in response.iter_raw():  # identity asked: raw bytes are the body
                raw.extend(chunk)
                if len(raw) > MAX_TOKEN_RESPONSE:
                    break
            status = response.status_code
    except httpx.HTTPError as exc:
        raise AuthError("token_exchange", transport_error_name(exc)) from None
    try:
        body = json.loads(bytes(raw[:MAX_TOKEN_RESPONSE]))
    except ValueError:
        body = None
    body = body if isinstance(body, dict) else {}
    token, lifetime = body.get("access_token"), body.get("expires_in")
    if status == 200 and isinstance(token, str) and token.strip():
        valid = isinstance(lifetime, int) and not isinstance(lifetime, bool) and lifetime > 0
        return token.strip(), lifetime if valid else TOKEN_LIFETIME_S
    if status == 200:
        raise AuthError("token_exchange", "200 no access_token")
    error = body.get("error")
    detail = f" {error}" if isinstance(error, str) and _OAUTH_ERROR.match(error) else ""
    raise AuthError("token_exchange", f"{status}{detail}")
