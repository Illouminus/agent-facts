"""Registry of services and probes, and the matching rules other packages reuse.

`check()` (W3) and the probe runner (W2) need the same answers the validator does: is this path an
instance of a registered template, is this URL on the vendor's domain.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

# A placeholder fills exactly one segment: never a dot segment or an encoded separator, which a
# server could resolve into another (unregistered) path.
_UNSAFE_SEGMENT_PARTS = ("%2e", "%2f", "%5c", "\\")


def _safe_segment(part: str) -> bool:
    lowered = part.lower()
    return part not in ("", ".", "..") and not any(u in lowered for u in _UNSAFE_SEGMENT_PARTS)


def match_template(path: str, template: str) -> bool:
    """True if `path` instantiates `template`; a `{name}` slot matches one ordinary segment."""
    parts, slots = path.split("/"), template.split("/")
    if len(parts) != len(slots):
        return False
    for part, slot in zip(parts, slots, strict=True):
        if slot.startswith("{") and slot.endswith("}") and len(slot) > 2:
            if not _safe_segment(part):
                return False
        elif part != slot:
            return False
    return True


def match_host(host: str, hosts: Iterable[str]) -> str | None:
    """The entry of `hosts` that `host` is, or is a subdomain of (most specific wins)."""
    return max((h for h in hosts if host == h or host.endswith("." + h)), key=len, default=None)


def on_vendor_domain(url: str, hosts: Iterable[str]) -> bool:
    """True if `url` is on one of `hosts` or a subdomain of one. The allowlist is explicit (the
    service's `hosts` + `doc_hosts`): no parent-domain guessing, which public suffixes break."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.username is not None or parts.password is not None or not parts.hostname:
        return False
    return match_host(parts.hostname.lower(), hosts) is not None


@dataclass(frozen=True)
class KeyFamily:
    hosts: frozenset[str]  # exact API hosts a service using a family key may list
    scopes: frozenset[str]  # OAuth scopes a family service account may ask for
    # A host the family shares with other APIs: the path prefixes a family key may reach on it.
    paths: Mapping[str, tuple[str, ...]] = field(default_factory=dict)


# Vendor keys that several services of one vendor share (a Google Cloud API key or service
# account serves Sheets, Calendar, Firestore). Exact hosts, not the vendor domain:
# storage.googleapis.com serves user buckets. Scopes are read-only where the API has one
# (Firestore has none: the service account's IAM role decides). www.googleapis.com serves Drive,
# YouTube and others besides Calendar, so on it the key reaches /calendar/ only. Changed only
# here, in a reviewed code PR.
KEY_FAMILIES: Mapping[str, KeyFamily] = {
    "google": KeyFamily(
        hosts=frozenset({
            "sheets.googleapis.com",
            "www.googleapis.com",
            "firestore.googleapis.com",
            "generativelanguage.googleapis.com",
        }),
        scopes=frozenset({
            "https://www.googleapis.com/auth/spreadsheets.readonly",
            "https://www.googleapis.com/auth/calendar.readonly",
            "https://www.googleapis.com/auth/calendar.events.readonly",
            "https://www.googleapis.com/auth/datastore",
        }),
        paths={"www.googleapis.com": ("/calendar/",)},
    ),
}


def _family_of(key_name: str) -> tuple[str, KeyFamily] | None:
    for family, rules in KEY_FAMILIES.items():
        if key_name == family or key_name.startswith((f"{family}-", f"{family}_")):
            return family, rules
    return None


def family_key_reaches(key_name: str, url: str) -> bool:
    """False if `key_name` is a family key and `url` is on a host the family shares with other
    APIs but off the family's paths there. True for any other key, host or path. A dot segment or
    an encoded separator in the path counts as off the paths: a server could resolve it into
    another API."""
    found = _family_of(key_name)
    if found is None:
        return True
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    prefixes = found[1].paths.get((parts.hostname or "").lower())
    if prefixes is None:
        return True
    path = parts.path
    segments = path.split("/")[1:]
    if segments and segments[-1] == "":
        segments.pop()  # a trailing slash
    return path.startswith(prefixes) and all(_safe_segment(s) for s in segments)


def service_urls(bases: Iterable[str], paths: Iterable[str]) -> tuple[str, ...]:
    """Every URL a service's key can be sent to: each base URL joined with each template path."""
    paths = tuple(paths)
    return tuple(base.rstrip("/") + path for base in bases for path in paths)


def key_bound_to_service(
    key_name: str,
    service_key: str,
    hosts: Iterable[str] = (),
    scopes: Iterable[str] = (),
    urls: Iterable[str] = (),
) -> bool:
    """A probe key belongs to one service by name: `stripe`, `stripe-test`, `stripe_live` for
    `stripe`. Without it any new service could name another's key file and send it to its hosts.
    A family key (`google-…`) is decided by the family alone, whatever the name match: it serves
    the family's services (`google`, `google-<x>`) only when every one of their hosts is one of
    the family's API hosts, every OAuth scope they ask for is one of the family's scopes and, on a
    host the family shares with other APIs, every URL (`service_urls`) is on the family's paths
    there. A service on such a host with no URL given is not bound: nothing shows where the key
    goes."""
    if (found := _family_of(key_name)) is not None:
        family, rules = found
        hosts, urls = tuple(h.lower() for h in hosts), tuple(urls)
        in_family = service_key == family or service_key.startswith(f"{family}-")
        shared = any(h in rules.paths for h in hosts)
        return (in_family and bool(hosts) and all(h in rules.hosts for h in hosts)
                and all(scope in rules.scopes for scope in scopes)
                and (not shared or bool(urls))
                and all(family_key_reaches(key_name, u) for u in urls))
    return key_name == service_key or key_name.startswith((f"{service_key}-", f"{service_key}_"))


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        value = list(value)
    if not isinstance(value, list):
        return ()
    return tuple(v for v in value if isinstance(v, str))


@dataclass(frozen=True)
class JsonRpcRead:
    """A service's JSON-RPC endpoint template and the methods on it that only read state."""

    path: str
    methods: frozenset[str]


def _jsonrpc(value: Any) -> JsonRpcRead | None:
    endpoint = _mapping(value)
    path = endpoint.get("path")
    if not isinstance(path, str):
        return None
    return JsonRpcRead(path, frozenset(_strings(endpoint.get("read_methods"))))


@dataclass(frozen=True)
class ServiceInfo:
    key: str
    hosts: tuple[str, ...]
    doc_hosts: tuple[str, ...]
    templates: frozenset[tuple[str, str]]
    account_states: frozenset[str]
    envs: frozenset[str]
    auth_kind: str
    auth_env: str | None
    jsonrpc: JsonRpcRead | None = None

    @classmethod
    def from_document(cls, doc: Mapping[str, Any]) -> "ServiceInfo":
        """Tolerates schema-invalid documents (wrong shapes read as empty), so one broken
        service is reported once instead of crashing the run."""
        http = _mapping(_mapping(doc.get("surfaces")).get("http"))
        templates = http.get("templates")
        dimensions = _mapping(doc.get("dimensions"))
        auth = _mapping(doc.get("auth"))
        return cls(
            key=doc["key"],
            hosts=_strings(doc.get("hosts")),
            doc_hosts=_strings(doc.get("doc_hosts")),
            templates=frozenset(
                (t.get("method"), t.get("path"))
                for t in (templates if isinstance(templates, list) else ())
                if isinstance(t, Mapping)
            ),
            account_states=frozenset(_strings(dimensions.get("account_state"))),
            envs=frozenset(_strings(dimensions.get("env"))),
            auth_kind=auth.get("kind", "none"),
            auth_env=auth.get("env"),
            jsonrpc=_jsonrpc(http.get("jsonrpc")),
        )

    @property
    def vendor_hosts(self) -> tuple[str, ...]:
        return self.hosts + self.doc_hosts

    def has_template(self, method: str, path_template: str) -> bool:
        return (method, path_template) in self.templates

    def matches_template(self, method: str, path: str) -> bool:
        return any(m == method and match_template(path, t) for m, t in self.templates)

    def knows_account_state(self, state: str) -> bool:
        return state == "any" or state in self.account_states


@dataclass(frozen=True)
class Registry:
    services: Mapping[str, ServiceInfo]
    probes: frozenset[str]

    @classmethod
    def from_documents(
        cls, services: Iterable[Mapping[str, Any]], probes: Iterable[Mapping[str, Any]]
    ) -> "Registry":
        return cls(
            services={s["key"]: ServiceInfo.from_document(s) for s in services},
            probes=frozenset(p["id"] for p in probes),
        )
