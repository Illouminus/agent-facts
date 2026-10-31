"""The "Example" section of a fact page (spec 06): the request the fact's probe sends and the
response it asserts, both rebuilt from the probe file, the service registration and the fact's
recorded error string. No body is invented: a response field appears only when an assertion
pins it (`equals`), or names a substring of it (`contains`, shown as the recorded error string
when that string holds it, else as `…substring…`). Credentials are never in a probe (the runner
injects them, spec 04); the page shows where they go as `<key>`, and an `auth: invalid` step as
the public fake constant it sends (`apifacts-invalid-key`).
"""

import base64
import json
import re
from dataclasses import dataclass
from urllib.parse import urlencode, urlsplit

from apifacts.probe.http import INVALID_KEY
from apifacts.probe.redact import Redactor
from apifacts.schema import models as m
from apifacts.schema.registry import match_template

_REDACT = Redactor(())
_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
_SEGMENT = re.compile(r"\.([A-Za-z_][A-Za-z0-9_-]*)|\[(\d+)\]")
MAX_FIELDS = 8


def _clean(text: str) -> str:
    """Probe templating shown as placeholders, then the runner's strict redaction."""
    return _REDACT.text_strict(_PLACEHOLDER.sub(lambda mt: f"<{mt.group(1)}>", text))


def _scalar(value: object) -> str:
    return _clean(value) if isinstance(value, str) else json.dumps(value)


@dataclass(frozen=True)
class Example:
    probe_id: str
    env: str
    steps: tuple[tuple[int, str, int | None], ...]  # (step number, request text, asserted status)
    response: str  # the chosen step's response text


def _status_of(probe: m.Probe, step: int) -> int | None:
    return next(
        (a.status for a in probe.assertions if isinstance(a, m.AssertStatus) and a.step == step),
        None,
    )


def chosen_step(fact: m.Fact, probe: m.Probe) -> int | None:
    """The step the fact is about: among the http steps on the fact's endpoint (all http steps if
    none is), the last one asserting the fact's status, else the last one with any assertion."""
    http = [i for i, s in enumerate(probe.steps, 1) if isinstance(s, m.HttpStep)]
    target = fact.target
    on_endpoint = [
        i
        for i in http
        if target.path_template
        and probe.steps[i - 1].method == target.method
        and match_template(probe.steps[i - 1].path, target.path_template)
    ]
    http = on_endpoint or http
    status = fact.signal.status if fact.signal else None
    if status is not None:
        hits = [i for i in http if _status_of(probe, i) == status]
        if hits:
            return hits[-1]
    asserted = {a.step for a in probe.assertions}
    candidates = [i for i in http if i in asserted]
    return candidates[-1] if candidates else None


def _base(service: m.Service, env: str) -> str:
    url = getattr(service.dimensions.env, env, None)
    http = service.surfaces.http
    split = urlsplit(url or (http.base_url if http else f"https://{service.hosts[0]}"))
    return f"{split.scheme}://{split.netloc}"


LIST_HEAD = 3


def _compact(value: object) -> object:
    """A long array shows its first items and how many more were sent (display only)."""
    if isinstance(value, list):
        head = [_compact(v) for v in value[:LIST_HEAD]]
        more = len(value) - LIST_HEAD
        return head + [f"… {more} more"] if more > 1 else [_compact(v) for v in value]
    if isinstance(value, dict):
        return {k: _compact(v) for k, v in value.items()}
    return value


def _credential(step: m.HttpStep, auth: m.Auth | None) -> str | None:
    """What the runner sends as the key: `<key>` for the service's own key (a keyless service
    declaring only its scheme sends nothing), the public fake constant for `auth: invalid`."""
    if auth is None or auth.kind == "none":
        return None
    if step.auth == "invalid":
        return INVALID_KEY
    if step.auth == "service" and auth.key_name is not None:
        return "<key>"
    return None


def request_text(step: m.HttpStep, service: m.Service, env: str) -> str:
    auth = service.auth
    key = _credential(step, auth)
    kind = auth.kind if auth and key else "none"
    base, path = _base(service, env), step.path
    headers: list[tuple[str, str]] = []
    query = dict(step.query or {})
    if kind == "bearer":
        headers.append(("Authorization", f"Bearer {key}"))
    elif kind == "basic":
        pair = f"{key}:{key}" if key == INVALID_KEY else None
        token = base64.b64encode(pair.encode()).decode() if pair else "<credentials>"
        headers.append(("Authorization", f"Basic {token}"))
    elif kind == "header" and auth.header_name:
        headers.append((auth.header_name, key))
    elif kind == "query" and auth.param_name:
        query[auth.param_name] = key
    elif kind == "path_prefix" and auth.path_prefix:
        path = auth.path_prefix.replace("{key}", key) + path
    elif kind in ("google_service_account", "oauth_refresh_token"):
        token = key if key == INVALID_KEY else "<access token>"
        headers.append(("Authorization", f"Bearer {token}"))
        if kind == "oauth_refresh_token" and auth.instance_hosts and key != INVALID_KEY:
            base = f"https://<org>.{auth.instance_hosts[0]}"
    url = base + path
    if query:
        url += "?" + urlencode({k: _scalar(v) for k, v in query.items()}, safe="<>,:")
    headers += [(name, _clean(value)) for name, value in (step.headers or {}).items()]
    body = None
    if step.form:
        headers.append(("Content-Type", "application/x-www-form-urlencoded"))
        body = urlencode({k: _scalar(v) for k, v in step.form.items()}, safe="<>[]")
    elif step.json_body is not None:
        headers.append(("Content-Type", "application/json"))
        body = _clean(json.dumps(_compact(step.json_body), ensure_ascii=False))
    lines = [f"{step.method} {_clean(url)}", *(f"{k}: {v}" for k, v in headers)]
    return "\n".join(lines + ([""] + [body] if body else []))


def _segments(path: str) -> list[str | int] | None:
    if path == "$":
        return None
    out: list[str | int] = []
    pos = 1
    while pos < len(path):
        match = _SEGMENT.match(path, pos)
        if match is None:
            return None
        out.append(match.group(1) if match.group(1) is not None else int(match.group(2)))
        pos = match.end()
    return out or None


def _place(doc: object, segments: list[str | int], value: object) -> object | None:
    """`doc` with `value` at `segments`, or None when it cannot be placed without inventing
    elements (an index past the end, a key on a list)."""
    if not segments:
        return value if doc is None else None
    head, rest = segments[0], segments[1:]
    if isinstance(head, int):
        doc = [] if doc is None else doc
        if not isinstance(doc, list) or head > len(doc):
            return None
        child = _place(doc[head] if head < len(doc) else None, rest, value)
        if child is None:
            return None
        return doc[:head] + [child] + doc[head + 1 :]
    doc = {} if doc is None else doc
    if not isinstance(doc, dict):
        return None
    child = _place(doc.get(head), rest, value)
    return None if child is None else {**doc, head: child}


def _shown(assertion: m.AssertJsonPath, error_string: str | None) -> object | None:
    if assertion.equals is not None:
        return _clean(assertion.equals) if isinstance(assertion.equals, str) else assertion.equals
    if assertion.contains is not None:
        if error_string and assertion.contains in error_string:
            return _clean(error_string)
        return f"…{_clean(assertion.contains)}…"
    return "…" if assertion.exists else None


def response_text(fact: m.Fact, probe: m.Probe, step: int) -> str:
    status = _status_of(probe, step)
    lines = [f"HTTP {status}" if status is not None else "HTTP (status not asserted)"]
    for a in probe.assertions:
        if isinstance(a, m.AssertHeader) and a.step == step:
            if a.equals is not None:
                lines.append(f"{a.header}: {_clean(a.equals)}")
            elif a.matches is not None:
                lines.append(f"{a.header}: <matches {_clean(a.matches)}>")
            elif a.present:
                lines.append(f"{a.header}: …")
    error_string = fact.signal.error_string if fact.signal else None
    doc: object = None
    loose: list[str] = []
    fields = [a for a in probe.assertions if isinstance(a, m.AssertJsonPath) and a.step == step]
    # values first; `exists` only where it does not collide with a value (it says less)
    fields.sort(key=lambda a: a.exists is not None)
    placed_paths: set[str] = set()
    for a in fields[:MAX_FIELDS]:
        value = _shown(a, error_string)
        if value is None or a.json_path in placed_paths:  # two `contains` on one field
            continue
        placed_paths.add(a.json_path)
        segments = _segments(a.json_path)
        placed = _place(doc, segments, value) if segments else None
        if placed is not None:
            doc = placed
        elif a.exists is None:
            loose.append(f"{a.json_path} = {json.dumps(value, ensure_ascii=False)}")
    for a in probe.assertions:
        if isinstance(a, m.AssertBodyContains) and a.step == step:
            loose.append(f"body contains {json.dumps(_clean(a.body_contains), ensure_ascii=False)}")
    if doc is not None or loose:
        lines.append("")
    if doc is not None:
        lines.append(json.dumps(doc, ensure_ascii=False, indent=2))
        if loose:
            lines += ["", "also asserted:"]
    lines += loose
    return "\n".join(lines)


def example(fact: m.Fact, service: m.Service, probe: m.Probe | None) -> Example | None:
    """The probe's request(s) up to the step the fact is about, and that step's asserted
    response; None without a probe, for a probe of another service or without an http step."""
    if probe is None or probe.service != fact.service or fact.target.surface is not m.Surface.http:
        return None
    step = chosen_step(fact, probe)
    if step is None:
        return None
    steps = []
    for i, s in enumerate(probe.steps[:step], 1):
        if isinstance(s, m.HttpStep):
            steps.append((i, request_text(s, service, probe.env.value), _status_of(probe, i)))
        else:
            steps.append((i, f"(wait {s.seconds} s)", None))
    return Example(probe.id, probe.env.value, tuple(steps), response_text(fact, probe, step))
