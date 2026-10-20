"""Registry of services and probes, and the matching rules other packages reuse.

`check()` (W3) and the probe runner (W2) need the same answers the validator does: is this path an
instance of a registered template, is this URL on the vendor's domain.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
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


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: Any) -> tuple[str, ...]:
    if isinstance(value, Mapping):
        value = list(value)
    if not isinstance(value, list):
        return ()
    return tuple(v for v in value if isinstance(v, str))


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
