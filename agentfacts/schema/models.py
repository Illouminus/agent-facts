"""Pydantic mirrors of `schema/*.schema.json`.

The JSON Schemas are the gate (CI, `agentfacts validate`); these models are what the runner, the
API, the bot and the pages import. `tests/schema/test_models.py` keeps both in step: same enums,
same verdicts on every fixture. Numbers and booleans are strict, as in JSON Schema ("3" is not an
integer).
"""

from collections.abc import Mapping
from enum import StrEnum
from typing import Annotated, Any, ClassVar, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    StrictFloat,
    StrictInt,
    StringConstraints,
    model_validator,
)


class _Closed(BaseModel):
    """Every record is closed: unknown fields are errors (`additionalProperties: false`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)


def _pattern(regex: str, max_length: int | None = None) -> type[str]:
    return Annotated[str, StringConstraints(pattern=regex, max_length=max_length)]


# ── shared value types (same patterns as fix.schema.json $defs) ──────────────────────────────────

HeaderName = _pattern(r"^[A-Za-z0-9-]{1,128}$")
Identifier = _pattern(r"^[A-Za-z0-9_.\[\]*$/-]{1,128}$")
ValueSource = _pattern(
    r"^(new_uuid_per_request|new_uuid_per_distinct_request"
    r"|literal:[A-Za-z0-9._/+=,-]{1,128}|account_setting:[A-Za-z0-9_.-]{1,64})$"
)
PathTemplate = _pattern(r"^/[^\s?#]{0,255}$")
Package = _pattern(r"^(@[a-z0-9][a-z0-9._-]*/)?[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
VersionConstraint = _pattern(r"^[A-Za-z0-9.,<>=!~^*|+-]{1,64}$")
Version = _pattern(r"^[A-Za-z0-9.+-]{1,64}$")
HttpsUrl = _pattern(r"^https://[A-Za-z0-9.-]+(:[0-9]{1,5})?(/[^\s]*)?$", max_length=512)

HttpMethod = Literal["GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
Location = Literal["query", "body", "header"]
Ecosystem = Literal["pypi", "npm"]
Attempts = Annotated[StrictInt, Field(ge=1, le=20)]
Number = StrictInt | StrictFloat


class Env(StrEnum):
    prod = "prod"
    sandbox = "sandbox"


# ── fixes (docs/specs/02-fix-vocabulary.md) ──────────────────────────────────────────────────────


class RetryAfterHeader(_Closed):
    action: Literal["retry_after_header"]
    header: HeaderName = "Retry-After"
    unit: Literal["s", "ms"]
    max_attempts: Attempts


class BackoffExponential(_Closed):
    action: Literal["backoff_exponential"]
    base_ms: Annotated[StrictInt, Field(ge=1, le=600_000)]
    factor: Annotated[Number, Field(gt=1, le=10)]
    max_ms: Annotated[StrictInt, Field(ge=1, le=3_600_000)]
    max_attempts: Attempts
    jitter: StrictBool


class SetHeader(_Closed):
    action: Literal["set_header"]
    name: HeaderName
    value_source: ValueSource


class SetParam(_Closed):
    action: Literal["set_param"]
    name: Identifier
    value_source: ValueSource
    location: Location | None = None


class RemoveParam(_Closed):
    action: Literal["remove_param"]
    name: Identifier
    location: Location


class UseEndpoint(_Closed):
    action: Literal["use_endpoint"]
    method: HttpMethod
    path_template: PathTemplate


class PaginateWith(_Closed):
    action: Literal["paginate_with"]
    cursor_field: Identifier
    param_name: Identifier
    page_size_max: Annotated[StrictInt, Field(ge=1, le=100_000)]


class PinSdkVersion(_Closed):
    action: Literal["pin_sdk_version"]
    package: Package
    ecosystem: Ecosystem
    constraint: VersionConstraint


class UpgradeSdk(_Closed):
    action: Literal["upgrade_sdk"]
    package: Package
    ecosystem: Ecosystem
    min_version: Version


class SwitchEnv(_Closed):
    action: Literal["switch_env"]
    to: Env
    reason_kind: Literal["feature_missing", "state_unreachable"]


class RequestScope(_Closed):
    action: Literal["request_scope"]
    scope: _pattern(r"^[A-Za-z0-9._:/-]{1,128}$")


class WaitForState(_Closed):
    action: Literal["wait_for_state"]
    account_state: _pattern(r"^[a-z0-9_-]{1,64}$")
    typical_delay_s: Annotated[StrictInt, Field(ge=0, le=2_592_000)]


class EnableInDashboard(_Closed):
    action: Literal["enable_in_dashboard"]
    setting_key: Identifier
    vendor_doc_url: HttpsUrl


class ReducePayload(_Closed):
    action: Literal["reduce_payload"]
    field: Identifier
    max_bytes: Annotated[StrictInt, Field(ge=1)] | None = None
    max_items: Annotated[StrictInt, Field(ge=1)] | None = None

    @model_validator(mode="after")
    def _exactly_one_limit(self) -> "ReducePayload":
        if (self.max_bytes is None) == (self.max_items is None):
            raise ValueError("exactly one of max_bytes or max_items is required")
        return self


class EncodeAs(_Closed):
    action: Literal["encode_as"]
    field: Identifier
    encoding: Literal["base64", "url", "json_string", "rfc3339"]


class NoneKnown(_Closed):
    action: Literal["none_known"]
    reason_kind: Literal["vendor_side", "investigating", "by_design"]


FIX_MODELS = (
    RetryAfterHeader,
    BackoffExponential,
    SetHeader,
    SetParam,
    RemoveParam,
    UseEndpoint,
    PaginateWith,
    PinSdkVersion,
    UpgradeSdk,
    SwitchEnv,
    RequestScope,
    WaitForState,
    EnableInDashboard,
    ReducePayload,
    EncodeAs,
    NoneKnown,
)
FIX_ACTIONS: tuple[str, ...] = tuple(
    m.model_fields["action"].annotation.__args__[0] for m in FIX_MODELS
)

Fix = Annotated[
    RetryAfterHeader
    | BackoffExponential
    | SetHeader
    | SetParam
    | RemoveParam
    | UseEndpoint
    | PaginateWith
    | PinSdkVersion
    | UpgradeSdk
    | SwitchEnv
    | RequestScope
    | WaitForState
    | EnableInDashboard
    | ReducePayload
    | EncodeAs
    | NoneKnown,
    Field(discriminator="action"),
]


# ── documents (docs/specs/01-fact-schema.md) ─────────────────────────────────────────────────────

Slug = _pattern(r"^[a-z0-9][a-z0-9-]{0,63}$")
FactId = _pattern(r"^af:[a-z0-9][a-z0-9-]{0,63}:[a-z0-9][a-z0-9-]{0,127}$")
ProbeId = _pattern(r"^af:[a-z0-9][a-z0-9-]{0,63}:probe:[a-z0-9][a-z0-9-]{0,127}$")
DimensionValue = _pattern(r"^[A-Za-z0-9_.-]{1,64}$")
Date = _pattern(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")
DateTime = _pattern(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})$"
)
Author = _pattern(r"^(bot|producer:[a-z0-9][a-z0-9-]{0,63}|human:[A-Za-z0-9][A-Za-z0-9-]{0,38})$")
Hostname = _pattern(r"^([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", max_length=253)
Sha256 = _pattern(r"^[0-9a-f]{64}$")
HttpStatus = Annotated[StrictInt, Field(ge=100, le=599)]
NonNegative = Annotated[StrictInt, Field(ge=0)]


class Kind(StrEnum):
    error_meaning = "error_meaning"
    rate_limit = "rate_limit"
    breaking_change = "breaking_change"
    silent_behavior = "silent_behavior"
    auth_quirk = "auth_quirk"
    pagination = "pagination"
    sandbox_divergence = "sandbox_divergence"
    deprecation = "deprecation"
    availability = "availability"
    schema_drift = "schema_drift"
    latency_profile = "latency_profile"


class Status(StrEnum):
    verified_server_prod = "verified:server:prod"
    verified_server_sandbox = "verified:server:sandbox"
    verified_client = "verified:client"
    reported = "reported"
    official = "official"
    stale = "stale"
    retracted = "retracted"


VERIFIED_STATUSES = frozenset(
    {Status.verified_server_prod, Status.verified_server_sandbox, Status.verified_client}
)


class Surface(StrEnum):
    http = "http"
    sdk = "sdk"
    cli = "cli"


class Source(StrEnum):
    probe = "probe"
    observation_quorum = "observation_quorum"
    producer = "producer"
    manual = "manual"


class SdkRef(_Closed):
    package: Package
    ecosystem: Ecosystem
    versions: VersionConstraint | None = None


class Target(_Closed):
    surface: Surface
    method: HttpMethod | None = None
    path_template: PathTemplate | None = None
    sdk: SdkRef | None = None

    @model_validator(mode="after")
    def _surface_fields(self) -> "Target":
        if self.surface is Surface.http and (self.method is None or self.path_template is None):
            raise ValueError("surface http requires method and path_template")
        if self.surface is Surface.sdk and self.sdk is None:
            raise ValueError("surface sdk requires sdk")
        return self


class Signal(_Closed):
    status: HttpStatus | None = None
    error_code: _pattern(r"^[A-Za-z0-9_.:-]{1,128}$") | None = None
    error_string: Annotated[str, StringConstraints(min_length=1, max_length=512)] | None = None
    normalized: Annotated[str, StringConstraints(min_length=1, max_length=512)] | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "Signal":
        if not self.model_fields_set:
            raise ValueError("signal needs at least one field")
        return self


class Dimensions(_Closed):
    env: Env
    plan: DimensionValue = "any"
    region: DimensionValue = "any"
    account_state: DimensionValue = "any"


class Evidence(_Closed):
    probe: ProbeId | None = None
    first_seen: DateTime
    last_confirmed: DateTime | None = None
    confirmations: NonNegative | None = None
    stale_counter: NonNegative | None = None
    vantages: tuple[Slug, ...] | None = None
    official_url: HttpsUrl | None = None
    observations: NonNegative | None = None


class HistoryEntry(_Closed):
    date: Date
    change: _pattern(r"^[a-z][a-z0-9_:.-]{0,63}$")
    by: Author
    previous_status: Status | None = None


class Provenance(_Closed):
    source: Source
    author: Author
    created: Date
    history: tuple[HistoryEntry, ...] | None = None


class Fact(_Closed):
    id: FactId
    service: Slug
    kind: Kind
    target: Target
    signal: Signal | None = None
    claim: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    dimensions: Dimensions
    fixes: Annotated[tuple[Fix, ...], Field(min_length=1, max_length=3)]
    status: Status
    evidence: Evidence
    provenance: Provenance

    @model_validator(mode="after")
    def _status_rules(self) -> "Fact":
        env_of = {
            Status.verified_server_prod: Env.prod,
            Status.verified_server_sandbox: Env.sandbox,
        }
        if self.status in env_of and self.dimensions.env is not env_of[self.status]:
            raise ValueError(f"status {self.status} needs dimensions.env {env_of[self.status]}")
        if self.status in VERIFIED_STATUSES and self.evidence.probe is None:
            raise ValueError(f"status {self.status} needs evidence.probe")
        if self.status is Status.official and self.evidence.official_url is None:
            raise ValueError("status official needs evidence.official_url")
        return self


class Template(_Closed):
    method: HttpMethod
    path: PathTemplate


class HttpSurface(_Closed):
    base_url: HttpsUrl
    templates: Annotated[tuple[Template, ...], Field(min_length=1)]
    signal_fields: tuple[_pattern(r"^[A-Za-z0-9_./-]{1,64}$"), ...] | None = None


class SdkPackage(_Closed):
    ecosystem: Ecosystem
    package: Package


class Surfaces(_Closed):
    http: HttpSurface | None = None
    sdk: Annotated[tuple[SdkPackage, ...], Field(min_length=1)] | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "Surfaces":
        if not self.model_fields_set:
            raise ValueError("surfaces needs at least one surface")
        return self


class EnvUrls(_Closed):
    prod: HttpsUrl | None = None
    sandbox: HttpsUrl | None = None

    @model_validator(mode="after")
    def _not_empty(self) -> "EnvUrls":
        if not self.model_fields_set:
            raise ValueError("dimensions.env needs at least one environment")
        return self


class ServiceDimensions(_Closed):
    env: EnvUrls
    account_state: tuple[DimensionValue, ...] | None = None


class Auth(_Closed):
    kind: Literal["none", "bearer", "basic", "header", "query"]
    key_name: _pattern(r"^[a-z0-9][a-z0-9_-]{0,63}$") | None = None
    env: Env | None = None
    header_name: HeaderName | None = None
    param_name: Identifier | None = None

    @model_validator(mode="after")
    def _kind_fields(self) -> "Auth":
        if self.kind != "none" and (self.key_name is None or self.env is None):
            raise ValueError(f"auth kind {self.kind} requires key_name and env")
        if self.kind == "header" and self.header_name is None:
            raise ValueError("auth kind header requires header_name")
        if self.kind == "query" and self.param_name is None:
            raise ValueError("auth kind query requires param_name")
        return self


class Tos(_Closed):
    automated_access: Literal["allowed"]
    publish_measurements: Literal["allowed"]
    source: HttpsUrl


class ProbeBudget(_Closed):
    per_template_seconds: Annotated[StrictInt, Field(ge=300)] = 300


class Service(_Closed):
    key: Slug
    name: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    hosts: Annotated[tuple[Hostname, ...], Field(min_length=1)]
    doc_hosts: tuple[Hostname, ...] | None = None
    surfaces: Surfaces
    dimensions: ServiceDimensions
    auth: Auth | None = None
    tos: Tos
    probe_budget: ProbeBudget = ProbeBudget()


Scalar = Annotated[str, StringConstraints(max_length=1024)] | StrictInt | StrictFloat | StrictBool


class HttpStep(_Closed):
    do: Literal["http"]
    method: HttpMethod
    path: PathTemplate
    query: dict[Identifier, Scalar] | None = None
    form: dict[Identifier, Scalar] | None = None
    json_body: dict | list | None = Field(default=None, alias="json")
    headers: dict[HeaderName, Annotated[str, StringConstraints(max_length=1024)]] | None = None
    auth: Literal["service", "none"] = "service"
    expect_rate_limit: StrictBool | None = None


class SleepStep(_Closed):
    do: Literal["sleep"]
    seconds: Annotated[Number, Field(gt=0, le=300)]


# The runner injects credentials; a probe never carries them or redirects the request elsewhere.
FORBIDDEN_PROBE_HEADERS = frozenset({"authorization", "proxy-authorization", "cookie", "host"})
# A prod probe is read-only: no body and no way to turn a GET into a write.
METHOD_OVERRIDE_HEADERS = frozenset(
    {"x-http-method-override", "x-http-method", "x-method-override"}
)
METHOD_OVERRIDE_PARAMS = frozenset({"_method"})
READ_ONLY_METHODS = frozenset({"GET", "HEAD"})


def http_step_violations(step: Mapping[str, Any], env: str) -> list[tuple[str, str, str]]:
    """Rules on one http step that JSON Schema cannot state case-insensitively.

    Returns `(field, code, message)` triples; shared by `Probe` and `agentfacts validate`.
    """
    found: list[tuple[str, str, str]] = []
    headers = {str(name).lower() for name in (step.get("headers") or {})}
    for name in sorted(headers & FORBIDDEN_PROBE_HEADERS):
        found.append(("headers", "forbidden_header", f"probes may not set {name}; the runner does"))
    if env == Env.prod:
        if step.get("method") not in READ_ONLY_METHODS:
            found.append(("method", "prod_probe_not_readonly", "prod probes may only GET or HEAD"))
        for body in ("form", "json"):
            if step.get(body) is not None:
                found.append((body, "prod_probe_not_readonly", f"prod probes may not send {body}"))
        for name in sorted(headers & METHOD_OVERRIDE_HEADERS):
            found.append(("headers", "prod_probe_not_readonly", f"method override header {name}"))
        params = {str(name).lower() for name in (step.get("query") or {})}
        for name in sorted(params & METHOD_OVERRIDE_PARAMS):
            found.append(("query", "prod_probe_not_readonly", f"method override parameter {name}"))
    return found


Step = Annotated[HttpStep | SleepStep, Field(discriminator="do")]
StepRef = Annotated[StrictInt, Field(ge=1)]


class AssertStatus(_Closed):
    step: StepRef
    status: HttpStatus


class _OneOperator(_Closed):
    operators: ClassVar[tuple[str, ...]] = ()

    @model_validator(mode="after")
    def _exactly_one_operator(self):
        given = [op for op in self.operators if op in self.model_fields_set]
        if len(given) != 1:
            raise ValueError(f"exactly one of {', '.join(self.operators)} is required")
        return self


class AssertHeader(_OneOperator):
    operators = ("present", "equals", "matches")
    step: StepRef
    header: HeaderName
    present: StrictBool | None = None
    equals: Annotated[str, StringConstraints(max_length=1024)] | None = None
    matches: Annotated[str, StringConstraints(max_length=256)] | None = None


class AssertJsonPath(_OneOperator):
    operators = ("equals", "contains", "exists")
    step: StepRef
    json_path: _pattern(r"^\$[^\s]{0,255}$")
    equals: Scalar | None = None
    contains: Annotated[str, StringConstraints(min_length=1, max_length=1024)] | None = None
    exists: StrictBool | None = None


class AssertBodyContains(_Closed):
    step: StepRef
    body_contains: Annotated[str, StringConstraints(min_length=1, max_length=1024)]


class LatencyBound(_Closed):
    lt: Annotated[StrictInt, Field(ge=1, le=60_000)]


class AssertLatency(_Closed):
    step: StepRef
    latency_ms: LatencyBound


class AssertSchemaFingerprint(_Closed):
    step: StepRef
    schema_fingerprint: Sha256


Assertion = (
    AssertStatus
    | AssertHeader
    | AssertJsonPath
    | AssertBodyContains
    | AssertLatency
    | AssertSchemaFingerprint
)


class Probe(_Closed):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    id: ProbeId
    service: Slug
    env: Env
    account_state: DimensionValue | None = None
    steps: Annotated[tuple[Step, ...], Field(min_length=1, max_length=10)]
    assertions: Annotated[tuple[Assertion, ...], Field(min_length=1, max_length=20)] = Field(
        alias="assert"
    )

    @model_validator(mode="after")
    def _step_rules(self) -> "Probe":
        for i, step in enumerate(self.steps, 1):
            if isinstance(step, HttpStep):
                data = step.model_dump(by_alias=True, exclude_none=True)
                for field, code, message in http_step_violations(data, self.env):
                    raise ValueError(f"steps[{i}].{field}: {code}: {message}")
        for a in self.assertions:
            if a.step > len(self.steps):
                raise ValueError(f"assertion references step {a.step} of {len(self.steps)}")
        return self


class Observation(_Closed):
    id: Annotated[StrictInt, Field(ge=1)]
    received_at: DateTime
    service: Slug
    method: HttpMethod
    path_template: PathTemplate
    status: HttpStatus | None = None
    error_hash: Sha256 | None = None
    normalized_error: Annotated[str, StringConstraints(max_length=512)] | None = None
    reporter_net: Sha256
    reporter_ua_class: Literal["pytest-plugin", "jest-plugin", "mcp", "sdk", "other"]
    sdk_package: Package | None = None
    sdk_version: Version | None = None
    env_guess: Env | None = None
    vantage_country: _pattern(r"^[A-Z]{2}$") | None = None
