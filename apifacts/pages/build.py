"""`apifacts pages build`: registry YAML → `{relative path: markdown}` → files under `--out`.

Deterministic by construction: inputs are sorted, no clock or git is read, and every date on a page
comes from the YAML. What is published is decided here; `templates.py` only renders.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from pydantic import BaseModel, ValidationError
from ruamel.yaml.error import YAMLError

from apifacts.pages import PagesError, templates
from apifacts.pages.errors_index import error_groups
from apifacts.schema.models import Fact, Probe, Service, Status
from apifacts.schema.validate import collect_files
from apifacts.schema.yamlio import load_yaml, plain


def _load[M: BaseModel](path: Path, model: type[M]) -> M:
    hint = "run `apifacts validate`"
    try:
        return model.model_validate(plain(load_yaml(path)))
    except (OSError, YAMLError, UnicodeDecodeError) as exc:
        raise PagesError(f"{path}: cannot read: {exc}; {hint}") from None
    except ValidationError as exc:
        first = exc.errors()[0]
        where = ".".join(str(part) for part in first["loc"]) or "document"
        kind = model.__name__.lower()
        raise PagesError(f"{path}: invalid {kind}: {where}: {first['msg']}; {hint}") from None


def _files(directory: Path) -> list[Path]:
    return collect_files([directory]) if directory.is_dir() else []


def load_registry(root: Path) -> tuple[tuple[Service, ...], tuple[Fact, ...]]:
    """Services and facts under `root` (missing directories read as empty), sorted by key / id."""
    services = sorted((_load(p, Service) for p in _files(root / "services")), key=lambda s: s.key)
    facts = sorted((_load(p, Fact) for p in _files(root / "facts")), key=lambda f: f.id)
    keys = [s.key for s in services]
    if len(set(keys)) != len(keys):
        raise PagesError("duplicate service key in services/; run `apifacts validate`")
    ids = [f.id for f in facts]
    if len(set(ids)) != len(ids):
        raise PagesError("duplicate fact id in facts/; run `apifacts validate`")
    return tuple(services), tuple(facts)


def load_probes(root: Path) -> tuple[Probe, ...]:
    """Probes under `root/probes` sorted by id: the Example section of the facts citing them."""
    probes = sorted((_load(p, Probe) for p in _files(root / "probes")), key=lambda p: p.id)
    return tuple(probes)


def registry_pages(root: Path, version: str | None = None) -> dict[str, str]:
    """`build_pages` over the repository at `root`: what the CLI, CI and the bot all run."""
    services, facts = load_registry(root)
    return build_pages(services, facts, load_probes(root), version=version)


# ── what is published ───────────────────────────────────────────────────────────────────────────

REPORTED_EXPIRY = timedelta(days=30)  # 01: "30 days without quorum refresh → removed from pages"


def _dates(fact: Fact) -> Iterable[str]:
    yield templates.utc_date(fact.evidence.first_seen)
    if fact.evidence.last_confirmed:
        yield templates.utc_date(fact.evidence.last_confirmed)
    yield fact.provenance.created
    for entry in fact.provenance.history or ():
        yield entry.date


def registry_version(facts: Iterable[Fact]) -> str | None:
    """The latest date anywhere in the facts (`YYYY-MM-DD`), or None for an empty registry.

    Taken from the data, not git: a squash merge gives main a new commit date, and a code-only
    commit must not make every page stale."""
    return max((d for fact in facts for d in _dates(fact)), default=None)


def _last_refresh(fact: Fact) -> date:
    evidence = fact.evidence
    stamps = [evidence.first_seen] + ([evidence.last_confirmed] if evidence.last_confirmed else [])
    return max(date.fromisoformat(templates.utc_date(s)) for s in stamps)


def published(facts: Iterable[Fact], version: str | None) -> tuple[Fact, ...]:
    """Facts that get a page: all but `reported` ones whose last quorum refresh is more than 30 days
    before the registry version (they stay in git)."""
    if version is None:
        return tuple(facts)
    today = date.fromisoformat(version)
    return tuple(
        f
        for f in facts
        if f.status is not Status.reported or today - _last_refresh(f) <= REPORTED_EXPIRY
    )


def siblings(fact: Fact, facts: Iterable[Fact]) -> tuple[Fact, ...]:
    """Dimension rows of the same fact: same kind, target and signal, other dimensions (01)."""
    return tuple(
        f
        for f in facts
        if f.id != fact.id
        and f.status is not Status.retracted
        and (f.kind, f.target, f.signal) == (fact.kind, fact.target, fact.signal)
        and f.dimensions != fact.dimensions
    )


def _related_key(fact: Fact, other: Fact) -> tuple[int, str] | None:
    """Rank of `other` as a related error of `fact`, or None: same endpoint and same error
    status first, then the same error status, then the same endpoint."""
    a, b = fact.target, other.target
    same_endpoint = a.path_template is not None and (a.method, a.path_template) == (
        b.method,
        b.path_template,
    )
    status = fact.signal.status if fact.signal else None
    other_status = other.signal.status if other.signal else None
    if other_status is None or other_status < 400:
        return None  # related *errors*: a 200 behaviour of the endpoint is not one
    same_status = status == other_status
    if not (same_endpoint or same_status):
        return None
    rank = 0 if same_endpoint and same_status else 1 if same_status else 2
    return rank, templates.slug_of(other)


def related(fact: Fact, facts: Iterable[Fact], exclude: Iterable[Fact] = ()) -> tuple[Fact, ...]:
    """Other published error facts (HTTP ≥ 400) of the same service with the same status or the
    same endpoint (spec 06 "Related errors"), best first, at most `templates.RELATED_MAX`; dimension
    rows (`exclude`, listed under Dimensions) and retracted facts are left out."""
    skip = {fact.id} | {f.id for f in exclude}
    ranked = sorted(
        (key, f)
        for f in facts
        if f.id not in skip
        and f.service == fact.service
        and f.status is not Status.retracted
        and (key := _related_key(fact, f)) is not None
    )
    return tuple(f for _, f in ranked[: templates.RELATED_MAX])


# ── pages ────────────────────────────────────────────────────────────────────────────────────────

ERRORS_DIR = "errors"
INDEX = "index"


def _check_paths(services: Sequence[Service], facts: Sequence[Fact]) -> None:
    for service in services:
        if service.key == ERRORS_DIR:
            raise PagesError(f"service key {ERRORS_DIR!r} collides with pages/{ERRORS_DIR}/")
    for fact in facts:
        if templates.slug_of(fact) == INDEX:
            raise PagesError(f"{fact.id}: slug {INDEX!r} collides with the service index page")


def build_pages(
    services: Iterable[Service],
    facts: Iterable[Fact],
    probes: Iterable[Probe] = (),
    version: str | None = None,
) -> dict[str, str]:
    """`{path relative to pages/: markdown}` for the registry, sorted by path.

    `probes` feed the Example section of the facts that cite them. `version` overrides the
    registry version (default: the latest date in the facts); reported expiry is measured
    against it, so the output depends on nothing but the arguments."""
    probe_by_id = {p.id: p for p in probes}
    services = sorted(services, key=lambda s: s.key)
    facts = sorted(facts, key=lambda f: f.id)
    version = version or registry_version(facts)
    live = published(facts, version)
    _check_paths(services, live)

    by_key = {s.key: s for s in services}
    by_service: dict[str, list[Fact]] = {s.key: [] for s in services}
    for fact in live:
        if fact.service not in by_service:
            raise PagesError(f"{fact.id}: service {fact.service} is not registered in services/")
        by_service[fact.service].append(fact)

    pages = {f"{INDEX}.md": templates.root_index(services, by_service, version)}
    for service in services:
        own = by_service[service.key]
        pages[f"{service.key}/{INDEX}.md"] = templates.service_index(service, own)
        for fact in own:
            rows = siblings(fact, own)
            probe = probe_by_id.get(fact.evidence.probe) if fact.evidence.probe else None
            page = templates.fact_page(fact, service, rows, probe, related(fact, own, rows))
            pages[f"{service.key}/{templates.slug_of(fact)}.md"] = page
    for prefix, (normalized, group) in error_groups(live).items():
        pages[f"{ERRORS_DIR}/{prefix}.md"] = templates.error_stub(normalized, group, by_key)
    return dict(sorted(pages.items()))


# ── output directory ────────────────────────────────────────────────────────────────────────────


@dataclass
class SyncReport:
    changed: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    extra: list[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not (self.changed or self.missing or self.extra)


def _generated(path: Path) -> bool:
    """True if the file ends with our exact footer line (quoting the phrase is not enough)."""
    try:
        return path.read_bytes().endswith(("\n" + templates.FOOTER + "\n").encode("utf-8"))
    except OSError:
        return False


def sync(out: Path, pages: Mapping[str, str], check: bool = False) -> SyncReport:
    """Compare `out` with `pages`; unless `check`, write what differs and delete stale pages.

    Only files ending with the generated-page footer count as ours: a hand-written
    `pages/README.md` (or a doc quoting the footer) is never reported or deleted."""
    try:
        return _sync(out, pages, check)
    except OSError as exc:
        raise PagesError(f"{out}: {exc.strerror or exc}: {exc.filename or out}") from None


def _sync(out: Path, pages: Mapping[str, str], check: bool) -> SyncReport:
    if out.exists() and not out.is_dir():
        raise PagesError(f"{out} is not a directory")
    report = SyncReport()
    for rel, text in pages.items():
        path = out / rel
        data = text.encode("utf-8")
        if not path.is_file():
            report.missing.append(rel)
        elif path.read_bytes() != data:
            report.changed.append(rel)
        else:
            continue
        if not check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
    if out.is_dir():
        for path in sorted(out.rglob("*.md")):
            rel = path.relative_to(out).as_posix()
            if rel not in pages and path.is_file() and _generated(path):
                report.extra.append(rel)
                if not check:
                    path.unlink()
                    _prune_empty(path.parent, out)
    return report


def _prune_empty(directory: Path, out: Path) -> None:
    while directory != out and directory.is_dir() and not any(directory.iterdir()):
        directory.rmdir()
        directory = directory.parent
