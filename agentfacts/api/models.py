"""Request and response shapes of the v0 API (spec 03), as published in docs/specs/openapi-v0.json.

Requests are closed (`extra="forbid"` → 400 `unknown_field`) and reuse the registry's value
patterns. Response models document the contract for OpenAPI; handlers build plain dicts, so a fact
is returned exactly as its YAML says (absent fields stay absent).
"""

from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, StringConstraints

from agentfacts.schema.models import Ecosystem, Env, Fact, HttpMethod, HttpStatus, Package, Version

UnknownReason = Literal["no_fact_for_signal", "unregistered_target", "signal_not_extractable"]
UaClass = Literal["pytest-plugin", "jest-plugin", "mcp", "sdk", "other"]


def _upper(value: object) -> object:
    return value.upper() if isinstance(value, str) else value


class _Request(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CheckTarget(_Request):
    method: Annotated[HttpMethod, BeforeValidator(_upper)] | None = Field(
        default=None, description="HTTP method; required when `url` is an http(s) URL with a path."
    )
    url: Annotated[str, StringConstraints(min_length=1, max_length=2048)] = Field(
        description="An http(s) URL, a bare host, or a `pypi:<pkg>@<ver>` / `npm:<pkg>@<ver>` "
        "locator. Query and fragment are dropped before matching and never stored."
    )


class CheckError(_Request):
    status: HttpStatus | None = None
    body_excerpt: str | None = Field(
        default=None,
        description="First 2 KB of the error body or exception text (longer input is cut).",
    )


class SdkContext(_Request):
    package: Package
    ecosystem: Ecosystem
    version: Version | None = None


class CheckContext(_Request):
    sdk: SdkContext | None = None
    env_hint: Env | None = None


class CheckRequest(_Request):
    """Request = contribution: if `target` matches a registered template and `error` carries a
    signal, a normalized observation is stored (no body, headers, query or raw IP)."""

    target: CheckTarget
    error: CheckError | None = None
    context: CheckContext | None = None


# ── responses (OpenAPI only) ────────────────────────────────────────────────────────────────────


class MatchedTemplate(BaseModel):
    method: HttpMethod
    path: str


class FactOut(Fact):
    """A fact as stored in `facts/<service>/<slug>.yaml`, plus its fixes in English."""

    fixes_rendered: list[str]


class Observed(BaseModel):
    status_distribution_30d: dict[str, float] = Field(
        description="Share of probe results per HTTP status over 30 days; empty until probes ran."
    )
    p50_latency_ms: int | None
    last_probe: str | None
    rate_limit_headers: list[str]


class Unknown(BaseModel):
    reason: UnknownReason | None = Field(
        description="Why no fact answers the signal; null when facts do."
    )
    stored_as_observation: bool


class RegistryInfo(BaseModel):
    version: str
    facts_for_service: int
    license: Literal["CC-BY-4.0"]


class CheckResponse(BaseModel):
    """Never empty: all six keys are always present."""

    service: str | None
    matched_template: MatchedTemplate | None
    facts: list[FactOut]
    observed: Observed
    unknown: Unknown
    registry: RegistryInfo


class FactsResponse(BaseModel):
    service: str
    facts: list[FactOut]
    registry: RegistryInfo


class ServiceSummary(BaseModel):
    key: str
    name: str
    hosts: list[str]
    templates: int
    facts: int


class RegistryMeta(BaseModel):
    version: str
    license: Literal["CC-BY-4.0"]


class ServicesResponse(BaseModel):
    services: list[ServiceSummary]
    registry: RegistryMeta


class Health(BaseModel):
    ok: bool
    registry_version: str
    probes_last_run: str | None


class ErrorDetail(BaseModel):
    code: str
    message: str
    field: str | None


class ErrorResponse(BaseModel):
    error: ErrorDetail
