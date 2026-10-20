"""Registry of services and probes, and the matching rules other packages reuse.

`check()` (W3) and the probe runner (W2) need the same answers the validator does: is this path an
instance of a registered template, is this URL on the vendor's domain.
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit


def match_template(path: str, template: str) -> bool:
    """True if `path` instantiates `template`; a `{name}` segment matches one non-empty segment."""
    parts, slots = path.split("/"), template.split("/")
    if len(parts) != len(slots):
        return False
    for part, slot in zip(parts, slots, strict=True):
        if slot.startswith("{") and slot.endswith("}") and len(slot) > 2:
            if not part:
                return False
        elif part != slot:
            return False
    return True


def vendor_domains(hosts: Iterable[str]) -> frozenset[str]:
    """Each registered host plus its parent domain when it has a subdomain (api.stripe.com →
    stripe.com), so vendor docs on docs.stripe.com count as the vendor's."""
    domains = set()
    for host in hosts:
        domains.add(host)
        labels = host.split(".")
        if len(labels) >= 3:
            domains.add(".".join(labels[1:]))
    return frozenset(domains)


def on_vendor_domain(url: str, hosts: Iterable[str]) -> bool:
    try:
        parts = urlsplit(url)
    except ValueError:
        return False
    if parts.username is not None or parts.password is not None or not parts.hostname:
        return False
    host = parts.hostname.lower()
    return any(host == d or host.endswith("." + d) for d in vendor_domains(hosts))


@dataclass(frozen=True)
class ServiceInfo:
    key: str
    hosts: tuple[str, ...]
    templates: frozenset[tuple[str, str]]
    account_states: frozenset[str]
    envs: frozenset[str]
    auth_kind: str
    auth_env: str | None

    @classmethod
    def from_document(cls, doc: Mapping[str, Any]) -> "ServiceInfo":
        http = (doc.get("surfaces") or {}).get("http") or {}
        dimensions = doc.get("dimensions") or {}
        auth = doc.get("auth") or {}
        return cls(
            key=doc["key"],
            hosts=tuple(doc.get("hosts") or ()),
            templates=frozenset(
                (t.get("method"), t.get("path"))
                for t in http.get("templates") or ()
                if isinstance(t, Mapping)
            ),
            account_states=frozenset(dimensions.get("account_state") or ()),
            envs=frozenset(dimensions.get("env") or ()),
            auth_kind=auth.get("kind", "none"),
            auth_env=auth.get("env"),
        )

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
