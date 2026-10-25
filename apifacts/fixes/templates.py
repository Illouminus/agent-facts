"""One English sentence per fix action (docs/specs/02-fix-vocabulary.md, column "Rendered as").

Fixes are data; this module is the only place that turns them into prose, so every consumer (the
`check()` API, pages, plugins) says the same thing. One golden test per action in
`tests/fixes/test_templates.py`.
"""

from collections.abc import Callable, Mapping
from typing import Any

from pydantic import TypeAdapter

from apifacts.schema import models as m

_FIX = TypeAdapter(m.Fix)

_UNITS = {"s": "seconds", "ms": "milliseconds"}
_ENCODINGS = {
    "base64": "base64",
    "url": "URL percent-encoding",
    "json_string": "a JSON string",
    "rfc3339": "an RFC 3339 timestamp",
}


def _value(source: str) -> str:
    if source == "new_uuid_per_request":
        return "new UUID per request"
    if source == "new_uuid_per_distinct_request":
        return "new UUID per distinct request"
    kind, _, value = source.partition(":")
    return value if kind == "literal" else f"the account setting {value}"


def _words(enum_value: str) -> str:
    return enum_value.replace("_", " ")


def _set_param(f: m.SetParam) -> str:
    where = f"{f.location} parameter" if f.location else "parameter"
    return f"Set {where} {f.name} to {_value(f.value_source)}"


def _reduce_payload(f: m.ReducePayload) -> str:
    limit = f"{f.max_bytes} bytes" if f.max_bytes is not None else f"{f.max_items} items"
    return f"Keep {f.field} ≤ {limit}"


_RENDERERS: dict[str, Callable[[Any], str]] = {
    "retry_after_header": lambda f: (
        f"Wait the number of {_UNITS[f.unit]} in {f.header}, "
        f"then retry (≤ {f.max_attempts} attempts)"
    ),
    "backoff_exponential": lambda f: (
        f"Retry with exponential backoff from {f.base_ms} ms × {f.factor}, cap {f.max_ms} ms, "
        f"≤ {f.max_attempts} attempts, {'with' if f.jitter else 'without'} jitter"
    ),
    "set_header": lambda f: f"Send header {f.name} = {_value(f.value_source)}",
    "set_param": _set_param,
    "remove_param": lambda f: f"Omit {f.location} parameter {f.name}",
    "use_endpoint": lambda f: f"Call {f.method} {f.path_template} instead",
    "paginate_with": lambda f: (
        f"Paginate by {f.cursor_field} via {f.param_name}, ≤ {f.page_size_max} per page"
    ),
    "pin_sdk_version": lambda f: f"Pin {f.package} ({f.ecosystem}) to {f.constraint}",
    "upgrade_sdk": lambda f: f"Upgrade {f.package} ({f.ecosystem}) to ≥ {f.min_version}",
    "switch_env": lambda f: f"Use the {f.to} environment: {_words(f.reason_kind)}",
    "request_scope": lambda f: f"Request OAuth scope {f.scope}",
    "wait_for_state": lambda f: (
        f"Wait until account state {f.account_state} (typically {f.typical_delay_s} s)"
    ),
    "enable_in_dashboard": lambda f: (
        f"A human must enable {f.setting_key} in the vendor dashboard (see {f.vendor_doc_url})"
    ),
    "reduce_payload": _reduce_payload,
    "encode_as": lambda f: f"Encode {f.field} as {_ENCODINGS[f.encoding]}",
    "none_known": lambda f: f"No client-side fix known ({_words(f.reason_kind)})",
}


def render_fix(fix: m.Fix | Mapping[str, Any]) -> str:
    """Render one fix (a model, or a mapping that validates as one) to its English sentence."""
    model = fix if isinstance(fix, m.FIX_MODELS) else _FIX.validate_python(fix)
    return _RENDERERS[model.action](model)
