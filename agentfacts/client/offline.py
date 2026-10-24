"""`--agentfacts-offline` / `agentfacts check --offline`: answer from a YAML snapshot, no network.

A snapshot has the repository layout (`services/*.yaml`, `facts/<service>/*.yaml`). The packaged one
(`snapshot/` next to this file) is empty in wave 1; release builds fill it. `AGENTFACTS_SNAPSHOT`
points at another directory, e.g. a checkout of the registry. The lookup mirrors the server's
cascade (spec 03, step 3) without the normalized-string hash: `(template, status)`, then
`kind ∈ {rate_limit, availability}`.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from agentfacts.schema.registry import match_host, match_template

PACKAGED = Path(__file__).parent / "snapshot"
SERVICE_WIDE_KINDS = frozenset({"rate_limit", "availability"})


def _load(paths: list[Path]) -> tuple[dict[str, Any], ...]:
    from agentfacts.schema.yamlio import load_yaml, plain

    docs = []
    for path in paths:
        try:
            doc = plain(load_yaml(path))
        except Exception:  # one unreadable file must not hide the rest
            continue
        if isinstance(doc, dict):
            docs.append(doc)
    return tuple(docs)


def _map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _hosts(service: Mapping[str, Any]) -> list[str]:
    """`hosts` and the tenant `auth.instance_hosts` (D-090), lowercased."""
    listed = _list(service.get("hosts")) + _list(_map(service.get("auth")).get("instance_hosts"))
    return [h.lower() for h in listed if isinstance(h, str)]


def _templates(service: Mapping[str, Any]) -> list[tuple[str, str]]:
    http = _map(_map(service.get("surfaces")).get("http"))
    return [
        (t["method"], t["path"])
        for t in _list(http.get("templates"))
        if isinstance(t, Mapping)
        and isinstance(t.get("method"), str)
        and isinstance(t.get("path"), str)
    ]


@dataclass(frozen=True)
class Snapshot:
    services: tuple[dict[str, Any], ...]
    facts: tuple[dict[str, Any], ...]

    @classmethod
    def load(cls, root: Path | None = None) -> "Snapshot":
        root = PACKAGED if root is None else root
        return cls(
            services=_load(sorted(root.glob("services/*.yaml"))),
            facts=_load(sorted(root.glob("facts/*/*.yaml"))),
        )

    @property
    def hosts(self) -> frozenset[str]:
        return frozenset(h for s in self.services for h in _hosts(s))

    def check(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        """Same shape as the server's answer; `observed` is always empty offline."""
        target, error = _map(payload.get("target")), _map(payload.get("error"))
        url, method, status = target.get("url", ""), target.get("method"), error.get("status")
        parts = urlsplit(url) if "://" in url else urlsplit("https://" + url)
        host = (parts.hostname or "").lower()
        service = next(
            (
                s
                for s in self.services
                if match_host(host, _hosts(s))
            ),
            None,
        )
        answer: dict[str, Any] = {
            "facts": [],
            "observed": {},
            "registry": {"version": "snapshot", "license": "CC-BY-4.0"},
        }
        if service is None:
            answer["unknown"] = {"reason": "unregistered_target", "stored_as_observation": False}
            return answer
        answer["service"] = service.get("key")
        template = next(
            (
                (m, p)
                for m, p in _templates(service)
                if (method is None or m == method) and match_template(parts.path or "/", p)
            ),
            None,
        )
        facts = [
            f
            for f in self.facts
            if f.get("service") == service.get("key") and f.get("status") != "retracted"
        ]
        found = []
        if template is not None:
            answer["matched_template"] = {"method": template[0], "path": template[1]}
            found = [
                f
                for f in facts
                if _map(f.get("target")).get("method") == template[0]
                and _map(f.get("target")).get("path_template") == template[1]
                and (status is None or _map(f.get("signal")).get("status") == status)
            ]
        if not found:
            found = [f for f in facts if f.get("kind") in SERVICE_WIDE_KINDS]
        answer["facts"] = [_with_fixes_rendered(f) for f in found]
        if not found:
            reason = "no_fact_for_signal" if template is not None else "unregistered_target"
            answer["unknown"] = {"reason": reason, "stored_as_observation": False}
        return answer


def _with_fixes_rendered(fact: dict[str, Any]) -> dict[str, Any]:
    from agentfacts.fixes.templates import render_fix

    rendered = []
    for fix in _list(fact.get("fixes")):
        try:
            rendered.append(render_fix(fix))
        except Exception:
            continue
    return {**fact, "fixes_rendered": rendered}
