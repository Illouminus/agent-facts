"""The facts `check()` answers from: built once at startup from `services/` and `facts/` in git.

Only documents that pass `agentfacts validate` are loaded; any other file is skipped and logged,
so one bad file cannot take the API down or put an unvalidated claim in an answer. Lookup follows
spec 03 step 3: exact `(service, template, normalized hash)`, then `(service, template, status)`,
then `(service, kind in {rate_limit, availability})`.
"""

import logging
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from agentfacts.api.match import Locator, version_in
from agentfacts.api.normalize import ExtractedSignal, error_hash, normalize
from agentfacts.fixes.templates import render_fix
from agentfacts.schema.models import Fact, Kind, Service, Status
from agentfacts.schema.registry import ServiceInfo, match_host
from agentfacts.schema.validate import Report, default_paths, validate_paths

log = logging.getLogger("agentfacts.api")

SERVICE_LEVEL_KINDS = frozenset({Kind.rate_limit, Kind.availability})
_RATE_LIMIT_HEADER = re.compile(r"(?i)retry-after|rate-?limit")
_DATE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}")

Template = tuple[str, str]  # (method, path template)


@dataclass(frozen=True)
class IndexedFact:
    fact: Fact
    document: dict[str, Any]  # the YAML as JSON + fixes_rendered: what the API returns
    hashes: frozenset[str]  # error hashes this fact answers

    @property
    def slug(self) -> str:
        return self.fact.id.rsplit(":", 1)[1]

    @property
    def status(self) -> int | None:
        return self.fact.signal.status if self.fact.signal else None

    @property
    def code(self) -> str | None:
        return self.fact.signal.error_code if self.fact.signal else None

    @property
    def template(self) -> Template | None:
        t = self.fact.target
        return (t.method, t.path_template) if t.method and t.path_template else None

    def fits(self, sdk: Locator | None) -> bool:
        """False only when the caller's SDK version is provably outside the fact's range."""
        ref = self.fact.target.sdk
        if sdk is None or ref is None or not self.about(sdk):
            return True
        return sdk.version is None or ref.versions is None or version_in(sdk.version, ref.versions)

    def about(self, sdk: Locator) -> bool:
        ref = self.fact.target.sdk
        return ref is not None and (ref.ecosystem, ref.package) == (sdk.ecosystem, sdk.package)


def _instance_hosts(service: Service) -> tuple[str, ...]:
    return (service.auth.instance_hosts or ()) if service.auth else ()


def fact_hashes(fact: Fact) -> frozenset[str]:
    """A fact answers the hash of its error string and of its own `normalized` (normalized
    again: authors may drop punctuation the rules keep, as the spec 01 example does)."""
    signal = fact.signal
    texts = (signal.error_string, signal.normalized) if signal else ()
    return frozenset(error_hash(n) for t in texts if t and (n := normalize(t)))


def _indexed(fact: Fact, document: dict[str, Any]) -> IndexedFact:
    rendered = [render_fix(f) for f in fact.fixes]
    return IndexedFact(fact, {**document, "fixes_rendered": rendered}, fact_hashes(fact))


@dataclass(frozen=True)
class ServiceEntry:
    service: Service
    info: ServiceInfo
    facts: tuple[IndexedFact, ...]  # non-retracted, by id

    @property
    def key(self) -> str:
        return self.service.key

    @property
    def signal_fields(self) -> tuple[str, ...]:
        http = self.service.surfaces.http
        return tuple(http.signal_fields or ()) if http else ()

    @property
    def rate_limit_headers(self) -> tuple[str, ...]:
        """Whitelisted header names (no dot, no pointer) that carry rate-limit state."""
        return tuple(
            f
            for f in self.signal_fields
            if "." not in f and not f.startswith("/") and _RATE_LIMIT_HEADER.search(f)
        )

    def env_for_host(self, host: str) -> str | None:
        """prod/sandbox when the two environments live on different hosts, else unknown."""
        hosts = {
            env: urlsplit(url).hostname
            for env, url in self.service.dimensions.env.model_dump(exclude_none=True).items()
        }
        if len(set(hosts.values())) < len(hosts):
            return None
        return next((env for env, h in hosts.items() if h == host), None)


@dataclass
class FactsIndex:
    services: dict[str, ServiceEntry]
    version: str
    skipped: tuple[Path, ...] = ()
    _all: dict[tuple[str, str], IndexedFact] = field(default_factory=dict)
    _by_template: dict[tuple[str, Template], list[IndexedFact]] = field(default_factory=dict)

    @classmethod
    def load(cls, repo: Path, version: str | None = None) -> "FactsIndex":
        paths = default_paths(repo)
        report = validate_paths(paths, root=repo) if paths else Report()
        skipped = sorted({p.file for p in report.problems})
        for path in skipped:
            mine = [p for p in report.problems if p.file == path]
            log.warning("skipped %s (%d problems), first: %s", path, len(mine), mine[0])
        bad = set(skipped)
        documents = {p: d for p, d in report.documents.items() if p not in bad}

        services: dict[str, Service] = {}
        for path, document in _under(documents, repo / "services"):
            if (svc := _parse(Service, path, document, skipped)) is not None:
                services[svc.key] = svc
        facts: list[tuple[Fact, dict[str, Any]]] = []
        for path, document in _under(documents, repo / "facts"):
            if (fact := _parse(Fact, path, document, skipped)) is None:
                continue
            if fact.service not in services:
                log.warning("skipped %s: service %s is not loaded", path, fact.service)
                skipped.append(path)
                continue
            facts.append((fact, document))

        indexed = sorted((_indexed(f, d) for f, d in facts), key=lambda f: f.fact.id)
        index = cls(
            services={
                key: ServiceEntry(
                    svc,
                    ServiceInfo.from_document(svc.model_dump(mode="json", exclude_none=True)),
                    tuple(
                        f
                        for f in indexed
                        if f.fact.service == key and f.fact.status is not Status.retracted
                    ),
                )
                for key, svc in sorted(services.items())
            },
            version=version or _newest_date(f for f, _ in facts),
            skipped=tuple(sorted(set(skipped))),
        )
        for f in indexed:
            index._all[(f.fact.service, f.slug)] = f
            if f.fact.status is not Status.retracted and f.template is not None:
                index._by_template.setdefault((f.fact.service, f.template), []).append(f)
        return index

    # ── resolution ──────────────────────────────────────────────────────────────────────────────

    def fact(self, service: str, slug: str) -> IndexedFact | None:
        """One fact by slug, retracted ones included (a link never breaks; the status says)."""
        return self._all.get((service, slug))

    def services_for_host(self, host: str) -> list[ServiceEntry]:
        """Exact `hosts` match, or a tenant host on `auth.instance_hosts` (it or a subdomain:
        `<org>.my.salesforce.com`, D-090); no other subdomains (default-deny). By key;
        Google-style shared hosts give several services."""
        return [
            s
            for s in self.services.values()
            if host in s.service.hosts or match_host(host, _instance_hosts(s.service)) is not None
        ]

    def services_for_package(self, ecosystem: str, package: str) -> list[ServiceEntry]:
        return [
            s
            for s in self.services.values()
            if any(
                (p.ecosystem, p.package) == (ecosystem, package)
                for p in s.service.surfaces.sdk or ()
            )
        ]

    # ── lookup (spec 03 step 3) ─────────────────────────────────────────────────────────────────

    def _candidates(
        self, entry: ServiceEntry, template: Template, sdk: Locator | None
    ) -> list[IndexedFact]:
        return [f for f in self._by_template.get((entry.key, template), ()) if f.fits(sdk)]

    def service_level(self, entry: ServiceEntry, sdk: Locator | None) -> list[IndexedFact]:
        return [f for f in entry.facts if f.fact.kind in SERVICE_LEVEL_KINDS and f.fits(sdk)]

    def for_signal(
        self,
        entry: ServiceEntry,
        template: Template,
        signal: ExtractedSignal,
        sdk: Locator | None,
    ) -> tuple[list[IndexedFact], bool]:
        """Facts for an observed error, and whether they answer the signal itself (tiers 1–2)
        or are only the service-level fallback (tier 3)."""
        candidates = self._candidates(entry, template, sdk)
        exact = [f for f in candidates if signal.error_hash in f.hashes]
        if not exact and signal.error_code:
            exact = [
                f
                for f in candidates
                if f.code == signal.error_code
                and (signal.status is None or f.status in (None, signal.status))
            ]
        if exact:
            return exact, True
        if signal.status is not None:
            by_status = [
                f
                for f in candidates
                if f.status == signal.status
                and not (signal.error_code and f.code and f.code != signal.error_code)
            ]
            if by_status:
                return by_status, True
        return self.service_level(entry, sdk), False

    def for_template(
        self, entry: ServiceEntry, template: Template, sdk: Locator | None
    ) -> list[IndexedFact]:
        """Pre-flight on an endpoint: its facts, then the service's rate limits/availability."""
        return _unique(self._candidates(entry, template, sdk) + self.service_level(entry, sdk))

    def for_service(self, entry: ServiceEntry, sdk: Locator | None) -> list[IndexedFact]:
        return [f for f in entry.facts if f.fits(sdk)]

    def for_package(self, entry: ServiceEntry, sdk: Locator) -> list[IndexedFact]:
        return [f for f in entry.facts if f.about(sdk) and f.fits(sdk)]


def _under(
    documents: dict[Path, dict[str, Any]], directory: Path
) -> list[tuple[Path, dict[str, Any]]]:
    return [(p, d) for p, d in documents.items() if p.is_relative_to(directory)]


def _parse(model, path: Path, document: dict[str, Any], skipped: list[Path]):
    try:
        return model.model_validate(document)
    except ValidationError as exc:  # schema and models disagree: trust neither
        log.warning("skipped %s: %s", path, exc.errors()[0]["msg"])
        skipped.append(path)
        return None


def _newest_date(facts: Iterable[Fact]) -> str:
    dates: list[str] = []
    for fact in facts:
        dates.append(fact.provenance.created)
        dates.extend(h.date for h in fact.provenance.history or ())
        dates.extend(
            d[:10] for d in (fact.evidence.first_seen, fact.evidence.last_confirmed) if d
        )
    return max((d for d in dates if _DATE.match(d)), default="none")


def _unique(facts: Sequence[IndexedFact]) -> list[IndexedFact]:
    seen: set[str] = set()
    return [f for f in facts if not (f.fact.id in seen or seen.add(f.fact.id))]
