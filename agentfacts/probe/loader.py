"""Load the registry for a tick: the W1 validator is the gate, the pydantic models are the payload.

A file with any validator problem is skipped and its problems reported, so the runner never acts on
something CI would reject; everything else keeps running (one broken probe does not stop the tick).
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from agentfacts.schema.models import Fact, Probe, Service
from agentfacts.schema.validate import (
    Problem,
    collect_files,
    default_paths,
    validate_paths,
)
from agentfacts.schema.yamlio import load_yaml, plain


@dataclass(frozen=True)
class LoadedProbe:
    path: Path
    probe: Probe


@dataclass(frozen=True)
class LoadedFact:
    path: Path
    fact: Fact


@dataclass
class Repo:
    services: dict[str, Service] = field(default_factory=dict)
    probes: list[LoadedProbe] = field(default_factory=list)
    facts: list[LoadedFact] = field(default_factory=list)
    problems: list[Problem] = field(default_factory=list)

    def facts_citing(self, probe_id: str) -> list[LoadedFact]:
        return [f for f in self.facts if f.fact.evidence.probe == probe_id]


def _model(path: Path, model: type[BaseModel], problems: list[Problem]) -> Any:
    try:
        return model.model_validate(plain(load_yaml(path)))
    except ValidationError as exc:  # the JSON Schema accepted it, the mirror did not
        first = exc.errors()[0]
        where = ".".join(str(p) for p in first["loc"]) or "document"
        problems.append(Problem(path, 1, "model_invalid", f"{where}: {first['msg']}"[:200]))
        return None


def load_repo(root: Path) -> Repo:
    repo = Repo()
    paths = default_paths(root)
    if not paths:
        return repo
    report = validate_paths(paths, root=root)
    repo.problems.extend(report.problems)
    rejected = {p.file.resolve() for p in report.problems}

    def clean(directory: str) -> list[Path]:
        base = root / directory
        files = collect_files([base]) if base.is_dir() else []
        return [p for p in files if p.resolve() not in rejected]

    loaders: list[tuple[str, type[BaseModel], Callable[[Path, Any], None]]] = [
        ("services", Service, lambda path, m: repo.services.setdefault(m.key, m)),
        ("probes", Probe, lambda path, m: repo.probes.append(LoadedProbe(path, m))),
        ("facts", Fact, lambda path, m: repo.facts.append(LoadedFact(path, m))),
    ]
    for directory, model, keep in loaders:
        for path in clean(directory):
            if (loaded := _model(path, model, repo.problems)) is not None:
                keep(path, loaded)

    known = []
    for item in repo.probes:
        if item.probe.service in repo.services:
            known.append(item)
        else:
            message = f"{item.probe.service} is not loaded; probe skipped"
            repo.problems.append(Problem(item.path, 1, "unknown_service", message))
    repo.probes = known
    repo.problems.sort()
    return repo
