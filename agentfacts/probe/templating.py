"""Probe templating: exactly three forms, nothing else is evaluated (spec 04).

- `{{run_uuid}}` — one UUID4 per probe run, the same in every step;
- `{{now_rfc3339}}` — the run's start time, UTC, `YYYY-MM-DDTHH:MM:SSZ`;
- `{{step[N].json.<path>}}` — a value from the JSON body of an earlier step (N is 1-based, as in
  assertions); `<path>` is `.name` and `[index]` segments.

Any other `{{…}}` is a `TemplateError`, so a typo fails the run instead of sending a literal brace.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote

_PLACEHOLDER = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
_STEP_REF = re.compile(r"step\[(\d+)\]\.json((?:\.[^.\[\]]+|\[\d+\])*)")
_SEGMENT = re.compile(r"\.([^.\[\]]+)|\[(\d+)\]")


class TemplateError(ValueError):
    pass


class _NotJson:
    def __repr__(self) -> str:
        return "NOT_JSON"


NOT_JSON = _NotJson()  # a step whose response is not JSON (or a sleep step)


def rfc3339(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass
class RunContext:
    run_uuid: str
    now_rfc3339: str
    responses: dict[int, Any] = field(default_factory=dict)  # step number → parsed JSON | NOT_JSON
    current_step: int = 1

    @classmethod
    def start(cls, current_step: int = 1, now: datetime | None = None) -> "RunContext":
        return cls(
            run_uuid=str(uuid.uuid4()),
            now_rfc3339=rfc3339(now or datetime.now(UTC)),
            current_step=current_step,
        )


def lookup(doc: Any, path: str) -> Any:
    """Follow `.name` / `[index]` segments; LookupError if absent, ValueError on bad syntax."""
    pos, node = 0, doc
    while pos < len(path):
        match = _SEGMENT.match(path, pos)
        if match is None:
            raise ValueError(f"bad path syntax at {path[pos:]!r}")
        name, index = match.groups()
        if name is not None:
            if not isinstance(node, dict) or name not in node:
                raise LookupError(f"no key {name!r}")
            node = node[name]
        else:
            i = int(index)
            if not isinstance(node, list) or i >= len(node):
                raise LookupError(f"no index [{i}]")
            node = node[i]
        pos = match.end()
    return node


def _resolve(expr: str, ctx: RunContext) -> Any:
    if expr == "run_uuid":
        return ctx.run_uuid
    if expr == "now_rfc3339":
        return ctx.now_rfc3339
    tag = "{{" + expr + "}}"
    match = _STEP_REF.fullmatch(expr)
    if match is None:
        raise TemplateError(f"unsupported placeholder {tag}")
    step = int(match.group(1))
    if not 1 <= step < ctx.current_step:
        raise TemplateError(f"{tag}: step {step} has not run before step {ctx.current_step}")
    body = ctx.responses.get(step, NOT_JSON)
    if body is NOT_JSON:
        raise TemplateError(f"{tag}: step {step} response is not JSON")
    try:
        return lookup(body, match.group(2))
    except LookupError as exc:
        raise TemplateError(f"{tag}: {exc.args[0]}") from None


def _text(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, separators=(",", ":"))


def _render_str(value: str, ctx: RunContext, keep_type: bool, encode: bool) -> Any:
    rest = _PLACEHOLDER.sub("", value)
    if "{{" in rest or "}}" in rest:
        raise TemplateError(f"malformed placeholder in {value!r}")
    whole = _PLACEHOLDER.fullmatch(value)
    if keep_type and whole is not None:
        return _resolve(whole.group(1), ctx)

    def substitute(match: re.Match[str]) -> str:
        text = _text(_resolve(match.group(1), ctx))
        if not encode:
            return text
        if text in ("", ".", ".."):
            # quote() leaves dots alone: a dot segment would resolve to another endpoint.
            raise TemplateError(f"{{{{{match.group(1)}}}}} renders a path to {text!r}")
        return quote(text, safe="")

    return _PLACEHOLDER.sub(substitute, value)


def render(value: Any, ctx: RunContext, *, keep_type: bool = False) -> Any:
    """Render strings inside `value` (dict keys stay literal). With `keep_type`, a string that is
    exactly one placeholder becomes the referenced value itself (JSON bodies keep numbers)."""
    if isinstance(value, str):
        return _render_str(value, ctx, keep_type, encode=False)
    if isinstance(value, dict):
        return {k: render(v, ctx, keep_type=keep_type) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [render(v, ctx, keep_type=keep_type) for v in value]
    return value


def render_path(path: str, ctx: RunContext) -> str:
    """Render a URL path; each substituted value is percent-encoded as one segment and may not be
    empty, `.` or `..`, so a value can never reach another (unregistered) path. The caller still
    matches the result against the service's templates."""
    return _render_str(path, ctx, keep_type=False, encode=True)
