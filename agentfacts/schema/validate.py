"""`agentfacts validate`: JSON Schema per document, then cross-document rules.

Every problem prints as `file:line: code message`. Schema codes come from the schemas'
`x-error-codes` annotations (keyword → code), else from where the error sits (`fix_invalid` inside
`fixes[]`), else `schema_<keyword>`. Cross-document codes: duplicate_id, id_mismatch,
unknown_service, unknown_probe, unknown_step, unregistered_template, foreign_url,
unknown_account_state, env_not_offered, auth_env_mismatch, forbidden_header,
prod_probe_not_readonly. Cross-document rules run only on documents that passed their schema, so
one mistake gives one problem.
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from jsonschema.exceptions import ValidationError as SchemaError
from ruamel.yaml.error import MarkedYAMLError, YAMLError

from agentfacts.schema import validator_for
from agentfacts.schema.models import http_step_violations
from agentfacts.schema.registry import Registry, ServiceInfo, on_vendor_domain
from agentfacts.schema.yamlio import line_of, load_yaml, plain

DocType = Literal["service", "fact", "probe"]
YAML_SUFFIXES = (".yaml", ".yml")
DEFAULT_DIRS = ("services", "facts", "probes")
CONTEXT_DIRS = ("services", "probes")
_MESSAGE_MAX = 200


@dataclass(frozen=True, order=True)
class Problem:
    file: Path
    line: int
    code: str
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.code} {self.message}"


@dataclass
class Report:
    files: int = 0
    problems: list[Problem] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.problems


@dataclass
class _Doc:
    path: Path
    type: DocType
    raw: Any  # ruamel tree, for line numbers
    data: dict[str, Any]
    schema_ok: bool = False

    @property
    def ident(self) -> str | None:
        value = self.data.get("key" if self.type == "service" else "id")
        return value if isinstance(value, str) else None

    def problem(self, path: Sequence[str | int], code: str, message: str) -> Problem:
        return Problem(self.path, line_of(self.raw, path), code, _clip(message))


def collect_files(paths: Iterable[Path]) -> list[Path]:
    """YAML files under each path (a file is taken as is); FileNotFoundError on a missing path."""
    files: list[Path] = []
    for path in paths:
        if path.is_dir():
            files.extend(
                sorted(p for p in path.rglob("*") if p.suffix in YAML_SUFFIXES and p.is_file())
            )
        elif path.is_file():
            files.append(path)
        else:
            raise FileNotFoundError(path)
    return files


def default_paths(root: Path) -> list[Path]:
    return [root / d for d in DEFAULT_DIRS if (root / d).is_dir()]


def validate_paths(paths: Sequence[Path], root: Path = Path(".")) -> Report:
    """Validate the YAML files under `paths`; `root/services` and `root/probes` are loaded as
    context (their own problems are not reported; inputs shadow them)."""
    inputs = collect_files(paths)
    seen = {p.resolve() for p in inputs}
    report = Report(files=len(inputs))

    docs: list[_Doc] = []
    for path in inputs:
        doc = _load(path, report.problems)
        if doc is not None:
            report.problems.extend(_schema_problems(doc))
            docs.append(doc)
            report.counts[doc.type] = report.counts.get(doc.type, 0) + 1

    context: list[_Doc] = []
    for directory in CONTEXT_DIRS:
        if (root / directory).is_dir():
            for path in collect_files([root / directory]):
                if path.resolve() not in seen and (doc := _load(path, [])) is not None:
                    if not list(_schema_problems(doc)):
                        context.append(doc)

    report.problems.extend(_duplicates(docs))
    registry = _registry(docs, context)
    for doc in docs:
        if doc.schema_ok:
            report.problems.extend(_CROSS_CHECKS[doc.type](doc, registry))
    report.problems.sort()
    return report


# ── loading and schema pass ─────────────────────────────────────────────────────────────────────


def _load(path: Path, problems: list[Problem]) -> _Doc | None:
    try:
        raw = load_yaml(path)
    except OSError as exc:
        problems.append(Problem(path, 1, "read_error", _clip(f"cannot read file: {exc.strerror}")))
        return None
    except (YAMLError, UnicodeDecodeError) as exc:
        mark = exc.problem_mark if isinstance(exc, MarkedYAMLError) else None
        line = mark.line + 1 if mark is not None else 1
        detail = exc.problem if isinstance(exc, MarkedYAMLError) and exc.problem else str(exc)
        problems.append(Problem(path, line, "yaml_error", _clip(" ".join(str(detail).split()))))
        return None
    if not isinstance(raw, Mapping):
        what = "empty document" if raw is None else f"top level is a {type(raw).__name__}"
        problems.append(Problem(path, 1, "not_a_mapping", f"{what}; expected a mapping"))
        return None
    doc_type = _classify(raw)
    if doc_type is None:
        problems.append(
            Problem(path, 1, "unknown_document", "neither a service (key), probe (steps) nor fact")
        )
        return None
    return _Doc(path=path, type=doc_type, raw=raw, data=plain(raw))


def _classify(doc: Mapping[str, Any]) -> DocType | None:
    if "key" in doc:
        return "service"
    if "steps" in doc:
        return "probe"
    if "claim" in doc or "kind" in doc:
        return "fact"
    return None


def _schema_problems(doc: _Doc) -> list[Problem]:
    errors = list(validator_for(doc.type).iter_errors(doc.data))
    doc.schema_ok = not errors
    return [doc.problem(list(e.absolute_path), _code(e), _schema_message(e)) for e in errors]


def _annotated_code(error: SchemaError) -> str | None:
    """The code a schema assigns to the failing keyword via `x-error-codes`, if any."""
    if not isinstance(error.schema, Mapping):
        return None
    return error.schema.get("x-error-codes", {}).get(error.validator)


def _code(error: SchemaError) -> str:
    if code := _annotated_code(error):
        return code
    path = list(error.absolute_path)
    if len(path) >= 2 and path[0] == "fixes":
        return "fix_invalid"
    return f"schema_{error.validator}"


def _schema_message(error: SchemaError) -> str:
    where = _dotted(error.absolute_path) or "document"
    if error.validator == "maxLength" and isinstance(error.instance, str):
        return f"{where}: {len(error.instance)} chars, max {error.validator_value}"
    if error.validator == "not":
        return f"{where}: not allowed here"
    return f"{where}: {error.message}"


def _dotted(path: Iterable[str | int]) -> str:
    out = ""
    for part in path:
        out += f"[{part}]" if isinstance(part, int) else (f".{part}" if out else str(part))
    return out


def _clip(message: str) -> str:
    return message if len(message) <= _MESSAGE_MAX else message[: _MESSAGE_MAX - 1] + "…"


# ── cross-document pass ─────────────────────────────────────────────────────────────────────────


def _duplicates(docs: list[_Doc]) -> list[Problem]:
    first: dict[tuple[str, str], Path] = {}
    problems = []
    for doc in docs:
        if doc.ident is None:
            continue
        key = (doc.type, doc.ident)
        if key in first:
            path = ["key" if doc.type == "service" else "id"]
            problems.append(doc.problem(path, "duplicate_id", f"{doc.ident} also in {first[key]}"))
        else:
            first[key] = doc.path
    return problems


def _registry(docs: list[_Doc], context: list[_Doc]) -> Registry:
    def pick(doc_type: DocType) -> list[dict[str, Any]]:
        by_id = {d.ident: d.data for d in context if d.type == doc_type and d.ident}
        # Inputs shadow context. A schema-invalid service still registers, so its facts don't
        # cascade into unknown_service.
        by_id.update({d.ident: d.data for d in docs if d.type == doc_type and d.ident})
        return list(by_id.values())

    return Registry.from_documents(pick("service"), pick("probe"))


def _location_mismatch(doc: _Doc, folder: str, service: str, slug: str) -> str | None:
    """If the file sits in its canonical folder, the folder and file name must match the id."""
    path = doc.path
    if folder != "services" and path.parent.name == folder:
        return f"{folder}/{path.name} must live in {folder}/<service>/<slug>.yaml"
    if folder == "services" and path.parent.name == "services" and path.stem != slug:
        return f"services/{path.name} holds service {slug}"
    if path.parent.parent.name == folder and (path.parent.name, path.stem) != (service, slug):
        return f"{folder}/{path.parent.name}/{path.name} holds {doc.ident}"
    return None


def _service_checks(doc: _Doc, registry: Registry) -> list[Problem]:
    key = doc.data["key"]
    mismatch = _location_mismatch(doc, "services", key, key)
    return [doc.problem(["key"], "id_mismatch", mismatch)] if mismatch else []


def _service_of(doc: _Doc, registry: Registry) -> tuple[ServiceInfo | None, list[Problem]]:
    service = registry.services.get(doc.data["service"])
    if service is None:
        problem = doc.problem(
            ["service"], "unknown_service", f"{doc.data['service']} is not registered"
        )
        return None, [problem]
    return service, []


def _fact_checks(doc: _Doc, registry: Registry) -> list[Problem]:
    data = doc.data
    problems: list[Problem] = []
    service_key = data["service"]
    prefix, slug = f"af:{service_key}:", data["id"].split(":", 2)[2]
    if not data["id"].startswith(prefix):
        problems.append(doc.problem(["id"], "id_mismatch", f"{data['id']} does not start {prefix}"))
    elif mismatch := _location_mismatch(doc, "facts", service_key, slug):
        problems.append(doc.problem(["id"], "id_mismatch", mismatch))

    probe = data["evidence"].get("probe")
    if probe is not None and probe not in registry.probes:
        problems.append(doc.problem(["evidence", "probe"], "unknown_probe", f"{probe} not found"))

    service, missing = _service_of(doc, registry)
    if service is None:
        return problems + missing

    target = data["target"]
    if target["surface"] == "http" and not service.has_template(
        target["method"], target["path_template"]
    ):
        problems.append(
            doc.problem(
                ["target", "path_template"],
                "unregistered_template",
                f"{target['method']} {target['path_template']} is not a template of {service.key}",
            )
        )
    state = data["dimensions"].get("account_state", "any")
    if not service.knows_account_state(state):
        problems.append(_unknown_state(doc, ["dimensions", "account_state"], state, service))

    for i, fix in enumerate(data["fixes"]):
        problems.extend(_fix_checks(doc, ["fixes", i], fix, service))
    return problems


def _fix_checks(
    doc: _Doc, path: list[str | int], fix: Mapping[str, Any], service: ServiceInfo
) -> list[Problem]:
    problems = []
    if fix["action"] == "use_endpoint" and not service.has_template(
        fix["method"], fix["path_template"]
    ):
        problems.append(
            doc.problem(
                [*path, "path_template"],
                "unregistered_template",
                f"{fix['method']} {fix['path_template']} is not a template of {service.key}",
            )
        )
    if fix["action"] == "wait_for_state" and not service.knows_account_state(fix["account_state"]):
        problems.append(
            _unknown_state(doc, [*path, "account_state"], fix["account_state"], service)
        )
    for name, value in fix.items():
        if (
            isinstance(value, str)
            and "://" in value
            and not on_vendor_domain(value, service.vendor_hosts)
        ):
            problems.append(
                doc.problem(
                    [*path, name], "foreign_url", f"{value} is not on {service.key}'s domain"
                )
            )
    return problems


def _unknown_state(doc: _Doc, path: list[str | int], state: str, service: ServiceInfo) -> Problem:
    known = ", ".join(sorted(service.account_states)) or "none"
    message = f"{state} is not an account_state of {service.key} (any, {known})"
    return doc.problem(path, "unknown_account_state", message)


def _probe_checks(doc: _Doc, registry: Registry) -> list[Problem]:
    data = doc.data
    problems: list[Problem] = []
    service_key = data["service"]
    prefix, slug = f"af:{service_key}:probe:", data["id"].split(":", 3)[3]
    if not data["id"].startswith(prefix):
        problems.append(doc.problem(["id"], "id_mismatch", f"{data['id']} does not start {prefix}"))
    elif mismatch := _location_mismatch(doc, "probes", service_key, slug):
        problems.append(doc.problem(["id"], "id_mismatch", mismatch))

    steps = data["steps"]
    for i, a in enumerate(data["assert"]):
        if a["step"] > len(steps):
            message = f"step {a['step']} does not exist ({len(steps)} steps)"
            problems.append(doc.problem(["assert", i, "step"], "unknown_step", message))

    for i, step in enumerate(steps):
        if step["do"] == "http":
            for name, code, message in http_step_violations(step, data["env"]):
                problems.append(doc.problem(["steps", i, name], code, message))

    service, missing = _service_of(doc, registry)
    if service is None:
        return problems + missing

    env = data["env"]
    if env not in service.envs:
        message = f"{service.key} offers no {env} environment ({', '.join(sorted(service.envs))})"
        problems.append(doc.problem(["env"], "env_not_offered", message))
    state = data.get("account_state", "any")
    if not service.knows_account_state(state):
        problems.append(_unknown_state(doc, ["account_state"], state, service))

    keyed = service.auth_kind != "none"
    for i, step in enumerate(steps):
        if step["do"] != "http":
            continue
        if not service.matches_template(step["method"], step["path"]):
            message = f"{step['method']} {step['path']} matches no template of {service.key}"
            problems.append(doc.problem(["steps", i, "path"], "unregistered_template", message))
        if keyed and step.get("auth", "service") == "service" and service.auth_env != env:
            # The key decides which environment is reached: a sandbox-labelled probe with a prod
            # key would write to production.
            message = f"probe env {env} but the {service.key} key reaches {service.auth_env}"
            problems.append(doc.problem(["steps", i], "auth_env_mismatch", message))
    return problems


_CROSS_CHECKS = {"service": _service_checks, "fact": _fact_checks, "probe": _probe_checks}


def fix_problems(fix: Any, label: Path = Path("<fix>")) -> list[Problem]:
    """Schema problems of one standalone fix (no service context), for `agentfacts render-fix`."""
    problems = []
    for error in validator_for("fix").iter_errors(fix):
        code = _annotated_code(error) or "fix_invalid"
        problems.append(Problem(label, 1, code, _clip(_schema_message(error))))
    return sorted(problems)
