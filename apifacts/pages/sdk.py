"""The "In your code" section of a fact page (spec 06): which exception each SDK raises for the
fact's error response (`sdk_errors.yaml`, read from the SDKs' source), and the fact's typed fixes
as code (one template per fix action, spec 02). Nothing here is prose about a fact: every value
comes from the fact, its fixes or the mapping file.
"""

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import yaml

from apifacts.schema import models as m

SDK_ERRORS = Path(__file__).with_name("sdk_errors.yaml")
LANGUAGES = {"pypi": "Python", "npm": "Node"}


@dataclass(frozen=True)
class Raised:
    ecosystem: str
    package: str
    official: bool
    verified: str
    raises: str | None  # None: the SDK hands the error back (`returns`)
    returns: str | None
    checks: tuple[tuple[str, Any], ...]  # (attribute, value) the error object carries


@cache
def load_mapping(path: Path = SDK_ERRORS) -> dict[str, tuple[dict, ...]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(service): tuple(entries) for service, entries in data.items()}


def _as_list(value: Any) -> list:
    return value if isinstance(value, list) else [value]


def _status_matches(spec: Any, status: int) -> bool:
    for item in _as_list(spec):
        if isinstance(item, str) and len(item) == 3 and item.endswith("xx"):
            if status // 100 == int(item[0]):
                return True
        elif item == status:
            return True
    return False


_MESSAGE_TESTS = {
    "message_equals": lambda text, needle: text == needle,
    "message_startswith": lambda text, needle: text.startswith(needle),
    "message_endswith": lambda text, needle: text.endswith(needle),
    "message_contains": lambda text, needle: needle in text,
}


def _rule_outcome(when: dict, fact: m.Fact) -> bool | None:
    """True / False, or None when the rule tests something the fact does not record."""
    signal = fact.signal
    status = signal.status if signal else None
    for key, spec in when.items():
        if key == "status":
            if status is None or not _status_matches(spec, status):
                return False
        elif key == "error_code":
            code = signal.error_code if signal else None
            if code is None or code not in _as_list(spec):
                return False
        elif key == "path_template":
            if fact.target.path_template not in _as_list(spec):
                return False
        elif key in _MESSAGE_TESTS:
            message = signal.error_string if signal else None
            if not message:
                return None
            text = " ".join(message.split()).lower()
            if not any(_MESSAGE_TESTS[key](text, str(n)) for n in _as_list(spec)):
                return False
        else:
            raise ValueError(f"sdk_errors.yaml: unknown condition {key!r}")
    return True


def _value(source: Any, fact: m.Fact) -> Any:
    if source == "error_code":
        return fact.signal.error_code if fact.signal else None
    return source


def raised(fact: m.Fact, mapping: dict[str, tuple[dict, ...]] | None = None) -> list[Raised]:
    """What each mapped SDK of the fact's service raises for its error response (status ≥ 400)."""
    signal = fact.signal
    if signal is None or signal.status is None or signal.status < 400:
        return []
    out = []
    for entry in (mapping if mapping is not None else load_mapping()).get(fact.service, ()):
        sdk = entry["sdk"]
        raises, reads = entry.get("catch"), {}
        for rule in entry.get("rules", ()):
            outcome = _rule_outcome(rule.get("when") or {}, fact)
            if outcome is False:
                continue
            if outcome is True and ("raises" not in rule or rule["raises"] is not None):
                raises = rule.get("raises", raises)
                reads = rule.get("read") or {}
            break
        checks = []
        if entry.get("status"):
            checks.append((entry["status"], signal.status))
        for attribute, source in reads.items():
            if (value := _value(source, fact)) is not None:
                checks.append((str(attribute), value))
        out.append(
            Raised(
                ecosystem=sdk["ecosystem"],
                package=sdk["package"],
                official=bool(sdk.get("official")),
                verified=entry["verified"],
                raises=None if entry.get("returns") else raises,
                returns=entry.get("returns"),
                checks=tuple(checks),
            )
        )
    return out


def check_expr(ecosystem: str, attribute: str, value: Any) -> str:
    literal = json.dumps(value, ensure_ascii=False)
    return f"{attribute} {'===' if ecosystem == 'npm' else '=='} {literal}"


# ── typed fixes as code (Python, httpx-style dicts: headers, params, body) ────────────────────


def _source_expr(source: str) -> tuple[str, list[str]]:
    """(Python expression, imports) for a spec 02 value_source."""
    if source in ("new_uuid_per_request", "new_uuid_per_distinct_request"):
        return "str(uuid.uuid4())", ["import uuid"]
    kind, _, value = source.partition(":")
    if kind == "literal":
        return json.dumps(value, ensure_ascii=False), []
    return "YOUR_" + "".join(c if c.isalnum() else "_" for c in value).upper(), []


_SOURCE_NOTES = {
    "new_uuid_per_request": "  # a new value on every request",
    "new_uuid_per_distinct_request": "  # a new value per distinct request; reuse it only to retry",
}
_TARGET = {"query": "params", "body": "body", "header": "headers", None: "params"}


_SLOT = re.compile(r"\{[A-Za-z_][A-Za-z0-9_]*\}")


def _path_expr(template: str) -> str:
    """A Python string for a path template: an f-string only when every brace belongs to a
    `{identifier}` slot, so a snippet a reader pastes can never evaluate anything else."""
    literal = json.dumps(template, ensure_ascii=False)
    has_slot = _SLOT.search(template) is not None
    only_slots = not any(c in _SLOT.sub("", template) for c in "{}")
    return "f" + literal if has_slot and only_slots and "\\" not in literal else literal


def _retry_status(fact: m.Fact) -> str:
    status = fact.signal.status if fact.signal else None
    return f"response.status_code != {status}" if status else "response.is_success"


def fix_snippet(fix: m.Fix, fact: m.Fact) -> tuple[str, str] | None:
    """(language, code) for fix actions that map onto code without judgement; None otherwise."""
    if isinstance(fix, m.SetHeader | m.SetParam):
        target = "headers" if isinstance(fix, m.SetHeader) else _TARGET[fix.location]
        expr, imports = _source_expr(fix.value_source)
        line = f"{target}[{json.dumps(fix.name)}] = {expr}{_SOURCE_NOTES.get(fix.value_source, '')}"
        return "python", "\n".join([*imports, line])
    if isinstance(fix, m.RemoveParam):
        return "python", f"{_TARGET[fix.location]}.pop({json.dumps(fix.name)}, None)"
    if isinstance(fix, m.UseEndpoint):
        call = f"client.request({json.dumps(fix.method)}, {_path_expr(fix.path_template)})"
        return "python", f"response = {call}"
    if isinstance(fix, m.RetryAfterHeader):
        scale = " / 1000" if fix.unit == "ms" else ""
        header = json.dumps(fix.header)
        return "python", (
            "import time\n\n"
            f"for attempt in range({fix.max_attempts}):\n"
            "    response = client.send(request)\n"
            f"    if {header} not in response.headers:\n"
            "        break\n"
            f"    time.sleep(float(response.headers[{header}]){scale})"
        )
    if isinstance(fix, m.BackoffExponential):
        pause = "random.uniform(0, delay_ms)" if fix.jitter else "delay_ms"
        imports = "import random\nimport time" if fix.jitter else "import time"
        return "python", (
            f"{imports}\n\n"
            f"delay_ms = {fix.base_ms}\n"
            f"for attempt in range({fix.max_attempts}):\n"
            "    response = client.send(request)\n"
            f"    if {_retry_status(fact)}:\n"
            "        break\n"
            f"    time.sleep({pause} / 1000)\n"
            f"    delay_ms = min(delay_ms * {fix.factor}, {fix.max_ms})"
        )
    if isinstance(fix, m.EncodeAs):
        name = json.dumps(fix.field)
        code = {
            "rfc3339": ("from datetime import UTC, datetime",
                        f"params[{name}] = moment.astimezone(UTC).isoformat()"),
            "base64": ("import base64", f"body[{name}] = base64.b64encode(raw).decode()"),
            "url": ("from urllib.parse import quote", f"params[{name}] = quote(value, safe=\"\")"),
            "json_string": ("import json", f"body[{name}] = json.dumps(value)"),
        }[fix.encoding]
        return "python", "\n".join(code)
    if isinstance(fix, m.PinSdkVersion | m.UpgradeSdk):
        constraint = fix.constraint if isinstance(fix, m.PinSdkVersion) else f">={fix.min_version}"
        if fix.ecosystem == "pypi" and not any(c in constraint for c in "|^"):
            return "sh", f"pip install '{fix.package}{constraint}'"
        if fix.ecosystem == "npm" and not any(c in constraint for c in ",|"):
            return "sh", f"npm install '{fix.package}@{constraint}'"
    return None
