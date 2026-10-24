"""OAuth refresh-token grants for probes (`auth.kind: oauth_refresh_token`), Salesforce style.

The key file is an sfdx auth URL, `force://<client_id>:<client_secret>:<refresh_token>@<host>`
(what `sf org display --verbose` prints; the secret is empty for the CLI's own client). Once per
service per tick the runner trades the refresh token at `https://<host><auth.token_path>` for an
access token and the org's `instance_url`; probe requests then go to that instance as Bearer. Both
hosts must be on the service's `auth.instance_hosts` (tenant domains such as my.salesforce.com,
kept apart from the hosts check() matches exactly), so the refresh token and the access token
never leave the vendor, and the org's own domain never has to be written into the public file.
`secrets_of` lists the secret forms of the file for the Redactor; the access token joins it when
it arrives.
"""

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, quote_plus, urlsplit

import httpx

from agentfacts.probe import USER_AGENT
from agentfacts.probe.google_sa import AuthError
from agentfacts.probe.http import transport_error_name
from agentfacts.schema.models import Service
from agentfacts.schema.registry import on_vendor_domain

MAX_TOKEN_RESPONSE = 64 * 1024
_FIELD = re.compile(r"^[A-Za-z0-9._~!$*+=/-]*$")  # client id / secret / refresh token: no : @ space
_HOST = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)+$")
_OAUTH_ERROR = re.compile(r"^[a-z_]{1,64}$")


@dataclass(frozen=True)
class RefreshGrant:
    client_id: str
    client_secret: str
    refresh_token: str
    host: str


def parse_auth_url(raw: str) -> RefreshGrant:
    raw = raw.strip()
    if not raw.startswith("force://"):
        raise AuthError("bad_key_file", "the key file is not a force:// auth URL")
    creds, sep, host = raw[len("force://"):].rpartition("@")
    parts = creds.split(":")
    if not sep or len(parts) != 3:
        raise AuthError("bad_key_file", "the auth URL is not force://<id>:<secret>:<token>@<host>")
    client_id, client_secret, refresh_token = parts
    if not client_id or not refresh_token or not all(_FIELD.match(p) for p in parts):
        raise AuthError("bad_key_file", "the auth URL has an empty or malformed field")
    if not _HOST.match(host):
        raise AuthError("bad_key_file", "the auth URL host is not a bare host name")
    return RefreshGrant(client_id, client_secret, refresh_token, host)


def secrets_of(raw: str) -> set[str]:
    """The file itself and, when it parses, the refresh token and client secret (as is and
    URL-encoded, the way they travel in the token request's form body)."""
    found = {raw.strip()}
    try:
        grant = parse_auth_url(raw)
    except AuthError:
        return {s for s in found if s}
    for secret in (grant.refresh_token, grant.client_secret):
        if secret:
            found |= {secret, quote(secret, safe=""), quote_plus(secret)}
    return {s for s in found if s}


def token_url(service: Service, grant: RefreshGrant) -> str:
    """Where the refresh token goes: the key's own host, which must be one of the service's
    `auth.instance_hosts` (or a subdomain of one)."""
    url = f"https://{grant.host}{service.auth.token_path}"
    if not on_vendor_domain(url, service.auth.instance_hosts):
        message = f"the auth URL host is not one of {service.key}'s instance_hosts"
        raise AuthError("foreign_host", message)
    return url


def instance_base_url(service: Service, instance_url: Any) -> str:
    """The org instance the token answers with, as a base URL: an https origin on the service's
    hosts, or nothing at all (the access token would follow it)."""
    if isinstance(instance_url, str):
        parts = urlsplit(instance_url)
        if (parts.scheme == "https" and parts.path in ("", "/") and not parts.query
                and not parts.fragment
                and on_vendor_domain(instance_url, service.auth.instance_hosts)):
            return f"https://{parts.hostname}" + (f":{parts.port}" if parts.port else "")
    message = f"instance_url is not an https origin on {service.key}'s instance_hosts"
    raise AuthError("foreign_instance", message)


def refresh_access_token(
    client: httpx.Client, grant: RefreshGrant, url: str
) -> tuple[str, Any]:
    """One token request → (access token, the instance_url as answered, unchecked)."""
    form = {"grant_type": "refresh_token", "client_id": grant.client_id,
            "refresh_token": grant.refresh_token}
    if grant.client_secret:
        form["client_secret"] = grant.client_secret
    headers = {"User-Agent": USER_AGENT, "Accept-Encoding": "identity",
               "Accept": "application/json"}
    try:
        with client.stream("POST", url, data=form, headers=headers) as response:
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
    token = body.get("access_token")
    if status == 200 and isinstance(token, str) and token.strip():
        return token.strip(), body.get("instance_url")
    if status == 200:
        raise AuthError("token_exchange", "200 no access_token")
    error = body.get("error")
    detail = f" {error}" if isinstance(error, str) and _OAUTH_ERROR.match(error) else ""
    raise AuthError("token_exchange", f"{status}{detail}")
