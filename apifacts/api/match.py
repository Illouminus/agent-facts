"""What a `check()` request points at, and who sent it (spec 03 steps 1 and 4).

Template matching itself is `apifacts.schema.registry.match_template`, shared with the validator
and the probe runner, so "is this path registered" has one answer across the repository.
"""

import ipaddress
import re
from collections.abc import Iterable
from dataclasses import dataclass
from urllib.parse import urlsplit

from pydantic import TypeAdapter, ValidationError

from apifacts.schema.models import Hostname, Package, Version
from apifacts.schema.registry import match_template

ECOSYSTEMS = ("pypi", "npm")
# The registry's own value types, so a locator or host the validator accepts is accepted here.
_PACKAGE, _VERSION, _HOST = TypeAdapter(Package), TypeAdapter(Version), TypeAdapter(Hostname)


def _valid(adapter: TypeAdapter, value: str) -> bool:
    try:
        adapter.validate_python(value)
    except ValidationError:
        return False
    return True


@dataclass(frozen=True)
class UrlTarget:
    host: str
    path: str  # query and fragment already dropped: never matched, never stored


@dataclass(frozen=True)
class HostTarget:
    host: str


@dataclass(frozen=True)
class Locator:
    ecosystem: str
    package: str
    version: str | None


Target = UrlTarget | HostTarget | Locator


def _locator(ecosystem: str, rest: str) -> Locator | None:
    scoped = rest.startswith("@")
    name, _, version = rest[1:].partition("@") if scoped else rest.partition("@")
    package = f"@{name}" if scoped else name
    if not _valid(_PACKAGE, package) or (version and not _valid(_VERSION, version)):
        return None
    return Locator(ecosystem, package, version or None)


def parse_target(raw: str) -> Target | None:
    """`target.url`: an http(s) URL, a bare host (optionally with a path), or a `pypi:`/`npm:`
    locator. None when it is none of those."""
    raw = raw.strip()
    ecosystem, colon, rest = raw.partition(":")
    if colon and ecosystem in ECOSYSTEMS:
        return _locator(ecosystem, rest)
    if "://" not in raw:
        raw = f"https://{raw}"
    try:
        parts = urlsplit(raw)
        parts.port  # noqa: B018 - raises ValueError on an invalid port
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or parts.username is not None:
        return None
    host = (parts.hostname or "").rstrip(".")
    if not _valid(_HOST, host):
        return None
    if parts.path in ("", "/"):
        return HostTarget(host)
    return UrlTarget(host, parts.path)


def best_template(
    templates: Iterable[tuple[str, str]], method: str, path: str
) -> tuple[str, str] | None:
    """The registered `(method, template)` that `path` instantiates; literal segments beat
    placeholders (`/customers/search` over `/customers/{id}`), then alphabetical."""
    matches = [(m, t) for m, t in templates if m == method and match_template(path, t)]
    if not matches:
        return None
    return min(matches, key=lambda mt: (mt[1].count("{"), mt[1]))


_UA_CLASSES = (
    ("pytest-plugin", re.compile(r"pytest")),
    ("jest-plugin", re.compile(r"jest|vitest")),
    ("mcp", re.compile(r"\bmcp\b|modelcontextprotocol")),
    (
        "sdk",
        re.compile(
            r"apifacts-sdk|python-httpx|python-requests|python-urllib|aiohttp|axios|node-fetch"
            r"|undici|okhttp|go-http-client"
        ),
    ),
)


def classify_ua(user_agent: str | None) -> str:
    """User-Agent → pytest-plugin | jest-plugin | mcp | sdk | other (the only thing kept of it)."""
    ua = (user_agent or "").lower()
    return next((cls for cls, pattern in _UA_CLASSES if pattern.search(ua)), "other")


def network_of(ip: str) -> str:
    """The reporter network: IPv4 /16 (spec 03); IPv6 /32, an ISP-sized block (spec is silent)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "unparsed"
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    prefix = 16 if addr.version == 4 else 32
    return str(ipaddress.ip_network(f"{addr}/{prefix}", strict=False))


Network = ipaddress.IPv4Network | ipaddress.IPv6Network


def parse_proxies(values: Iterable[str]) -> tuple[Network, ...]:
    """Trusted proxy IPs/CIDRs, parsed once at startup; a typo fails loudly (ValueError)."""
    return tuple(ipaddress.ip_network(v.strip(), strict=False) for v in values if v.strip())


def _trusted(ip: str, proxies: tuple[Network, ...]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(addr in proxy for proxy in proxies)


def client_ip(peer: str, forwarded_for: str | None, proxies: tuple[Network, ...]) -> str:
    """The caller's address: the socket peer, unless the peer is a trusted proxy, then the
    rightmost `X-Forwarded-For` hop that is not one (a client can prepend anything)."""
    if not forwarded_for or not _trusted(peer, proxies):
        return peer
    hops = [h.strip() for h in forwarded_for.split(",") if h.strip()]
    for hop in reversed(hops):
        if not _trusted(hop, proxies):
            return hop
    return hops[0] if hops else peer


_CLAUSE = re.compile(r"^(>=|<=|==|!=|>|<)?\s*([0-9]+(?:\.[0-9]+)*)$")
_NUMERIC_PREFIX = re.compile(r"^([0-9]+(?:\.[0-9]+)*)")


def _numbers(version: str) -> tuple[int, ...]:
    return tuple(int(p) for p in version.split("."))


def _cmp(a: tuple[int, ...], b: tuple[int, ...]) -> int:
    width = max(len(a), len(b))
    a, b = a + (0,) * (width - len(a)), b + (0,) * (width - len(b))
    return (a > b) - (a < b)


_OPS = {
    ">=": lambda c: c >= 0,
    "<=": lambda c: c <= 0,
    ">": lambda c: c > 0,
    "<": lambda c: c < 0,
    "==": lambda c: c == 0,
    "!=": lambda c: c != 0,
}


def version_in(version: str, constraint: str) -> bool:
    """True unless `version` is provably outside `constraint` (comma-joined simple comparisons).
    Anything this cannot read (npm `^`/`~`, pre-release-only versions) counts as inside: a fact
    is never hidden because of a parser gap."""
    prefix = _NUMERIC_PREFIX.match(version)
    if prefix is None:
        return True
    current = _numbers(prefix[1])
    for clause in constraint.split(","):
        m = _CLAUSE.match(clause.strip())
        if m is None:
            return True
        if not _OPS[m[1] or "=="](_cmp(current, _numbers(m[2]))):
            return False
    return True
