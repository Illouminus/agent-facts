"""Pydantic mirrors of `schema/*.schema.json`.

The JSON Schemas are the gate (CI, `agentfacts validate`); these models are what the runner, the
API, the bot and the pages import. `tests/schema/test_models.py` keeps both in step: same enums,
same verdicts on every fixture. Numbers and booleans are strict, as in JSON Schema ("3" is not an
integer).
"""

from enum import StrEnum
from typing import Annotated, Literal

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
VersionConstraint = _pattern(r"^[A-Za-z0-9.,<>=!~^*|+ -]{1,64}$")
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
