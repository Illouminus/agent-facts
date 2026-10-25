"""FastAPI application: `uvicorn apifacts.api.app:app` (spec 03).

Configuration (environment, read at startup): `APIFACTS_REPO` (registry checkout, default `.`),
`APIFACTS_DB` (sqlite file, default `observations.sqlite`), `APIFACTS_TRUSTED_PROXIES`
(comma-separated IPs/CIDRs whose `X-Forwarded-For` is believed, default `127.0.0.1,::1`),
`APIFACTS_REGISTRY_VERSION` (overrides the version derived from the facts), `APIFACTS_RESULTS`
(the probe runner's results.jsonl for `/healthz`, default `<repo>/var/results.jsonl`).

The facts index is read once, at startup: a new registry needs a restart (`ops/deploy.sh` does it).

One process: rate limits live in memory and the store is one sqlite connection.
"""

import hashlib
import json
import os
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from starlette.datastructures import Headers
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from apifacts.api.facts_index import (
    FactsIndex,
    IndexedFact,
    ServiceEntry,
    Template,
    instance_hosts_of,
)
from apifacts.api.health import last_probe_run
from apifacts.api.match import (
    HostTarget,
    Locator,
    Network,
    Target,
    UrlTarget,
    best_template,
    classify_ua,
    client_ip,
    network_of,
    parse_proxies,
    parse_target,
)
from apifacts.api.models import (
    CheckRequest,
    CheckResponse,
    ErrorResponse,
    FactOut,
    FactsResponse,
    Health,
    ServicesResponse,
)
from apifacts.api.normalize import ExtractedSignal, extract_signal, find_urls, looks_like_prompt
from apifacts.api.ratelimit import RateLimiter
from apifacts.api.seed_hosts import metric_host
from apifacts.api.store import Drop, Store, salt_period
from apifacts.schema.registry import on_vendor_domain

LICENSE = "CC-BY-4.0"
MAX_BODY = 8192  # spec 03: max request body
DAILY_CAP = 1000  # spec 05: observations per reporter net per day
TEMPLATE_CAP = 200  # spec 05: distinct error strings per (service, method, template, status) a week
CACHE_CONTROL = "public, max-age=300"
DEFAULT_TRUSTED_PROXIES = ("127.0.0.1", "::1")
CHECK_PATH = "/v0/check"


def _error_body(code: str, message: str, field: str | None = None) -> dict[str, Any]:
    return {"error": {"code": code, "message": message, "field": field}}


def _error(status: int, code: str, message: str, field: str | None = None, **kw) -> JSONResponse:
    return JSONResponse(_error_body(code, message, field), status_code=status, **kw)


def _fail(status: int, code: str, message: str, field: str | None = None) -> HTTPException:
    return HTTPException(status, detail=_error_body(code, message, field)["error"])


# ── state ───────────────────────────────────────────────────────────────────────────────────────


@dataclass
class _State:
    index: FactsIndex
    store: Store
    daily_cap: int
    template_cap: int
    trusted_proxies: tuple[Network, ...]
    utcnow: Callable[[], datetime]
    results: Path


def _state(request: Request) -> _State:
    return request.app.state.apifacts


def _caller_ip(scope_client: Any, headers: Headers, trusted: tuple[Network, ...]) -> str:
    peer = scope_client[0] if scope_client else ""
    return client_ip(peer, headers.get("x-forwarded-for"), trusted)


class _CheckGuard:
    """Before FastAPI reads the body of POST /v0/check: rate limit (429), then size (413), so
    neither a flood nor an oversized body costs a parse."""

    def __init__(self, app: ASGIApp, limiter: RateLimiter, trusted: tuple[Network, ...]):
        self.app, self.limiter, self.trusted = app, limiter, trusted
        self._key = secrets.token_bytes(16)  # limiter keys: never a raw network, even in memory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] != CHECK_PATH or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        net = network_of(_caller_ip(scope.get("client"), headers, self.trusted))
        key = hashlib.blake2b(net.encode(), key=self._key, digest_size=16).hexdigest()
        if (retry := self.limiter.hit(key)) is not None:
            response = _error(
                429, "rate_limited", "too many requests", headers={"Retry-After": str(retry)}
            )
            await response(scope, receive, send)
            return
        length = headers.get("content-length")
        if length is not None and not length.isdigit():
            await _error(400, "invalid_request", "malformed Content-Length")(scope, receive, send)
            return
        if length is not None and int(length) > MAX_BODY:
            await _error(413, "body_too_large", f"body over {MAX_BODY} bytes")(scope, receive, send)
            return
        received = 0

        async def limited() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY:  # chunked body: FastAPI re-raises HTTPException as is
                    raise _fail(413, "body_too_large", f"body over {MAX_BODY} bytes")
            return message

        await self.app(scope, limited, send)


# ── POST /v0/check ──────────────────────────────────────────────────────────────────────────────


def _resolve(
    index: FactsIndex, target: Target | None, method: str | None
) -> tuple[ServiceEntry | None, Template | None]:
    """Spec 03 step 1: host → services (exact `hosts`, or `auth.instance_hosts` and its
    subdomains, D-090), path → template (`{id}` = one segment)."""
    if isinstance(target, UrlTarget):
        candidates = index.services_for_host(target.host)
        for entry in candidates:
            if (template := best_template(entry.info.templates, method, target.path)) is not None:
                return entry, template
        return (candidates[0] if len(candidates) == 1 else None), None
    if isinstance(target, HostTarget):
        candidates = index.services_for_host(target.host)
    elif isinstance(target, Locator):
        candidates = index.services_for_package(target.ecosystem, target.package)
    else:
        candidates = []
    return (candidates[0] if len(candidates) == 1 else None), None


def _drop_reason(entry: ServiceEntry, signal: ExtractedSignal | None) -> str | None:
    """Spec 05: a string with a URL off the vendor's hosts, or shaped like a prompt."""
    raw = signal.raw_string if signal else None
    if not raw:
        return None
    if any(not on_vendor_domain(url, entry.info.vendor_hosts) for url in find_urls(raw)):
        return "dropped_foreign_url"
    if looks_like_prompt(raw):
        return "dropped_prompt"
    return None


def _ingest(
    state: _State,
    entry: ServiceEntry,
    template: Template,
    signal: ExtractedSignal,
    req: CheckRequest,
    target: UrlTarget,
    ip: str,
    user_agent: str | None,
    now: datetime,
) -> bool:
    """Spec 03 step 4: one normalized row, or nothing (dropped and counted). The reporter salt
    is the week's (Q6): one network keeps one id for the whole quorum window."""
    day = now.date().isoformat()
    if (dropped := _drop_reason(entry, signal)) is not None:
        state.store.bump(dropped, day)
        return False
    salt = state.store.period_salt(salt_period(now.date()).isoformat())
    context = req.context
    sdk = context.sdk if context else None
    row = {
        "received_at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "service": entry.key,
        "method": template[0],
        "path_template": template[1],
        "status": signal.status,
        "error_hash": signal.error_hash,
        "normalized_error": signal.normalized,
        "reporter_net": hashlib.sha256(salt + network_of(ip).encode()).hexdigest(),
        "reporter_ua_class": classify_ua(user_agent),
        "sdk_package": sdk.package if sdk else None,
        "sdk_version": sdk.version if sdk else None,
        "env_guess": (context.env_hint if context else None) or entry.env_for_host(target.host),
        "vantage_country": None,
    }
    stored = state.store.add_observation(
        row, daily_cap=state.daily_cap, template_cap=state.template_cap
    )
    if isinstance(stored, Drop):
        state.store.bump(stored.value, day)
        return False
    state.store.bump("stored", day)
    return True


def _count_unregistered(store: Store, target: Target | None, day: str) -> None:
    """Spec 03 step 1 (Q7): one anonymous daily count, labelled with the host only when it is a
    seed candidate's API host; every other target (package, unparsed, unknown host) is `other`.
    The unlabelled total is kept as well, so a reader can sum one name."""
    host = target.host if isinstance(target, UrlTarget | HostTarget) else None
    store.bump("unregistered_target", day)
    store.bump(f"unregistered_target:{metric_host(host)}", day)


def _observed(entry: ServiceEntry | None) -> dict[str, Any]:
    """What the probes know about the target. Probe results are not wired in yet (W2/W4):
    the structure is always there, with an empty distribution and nulls."""
    return {
        "status_distribution_30d": {},
        "p50_latency_ms": None,
        "last_probe": None,
        "rate_limit_headers": list(entry.rate_limit_headers) if entry else [],
    }


def _registry(index: FactsIndex, entry: ServiceEntry | None) -> dict[str, Any]:
    return {
        "version": index.version,
        "facts_for_service": len(entry.facts) if entry else 0,
        "license": LICENSE,
    }


def _check(state: _State, req: CheckRequest, ip: str, user_agent: str | None) -> dict[str, Any]:
    index, now = state.index, state.utcnow()
    target = parse_target(req.target.url)
    method = req.target.method
    if isinstance(target, UrlTarget) and method is None:
        raise _fail(
            400, "invalid_request", "target.method is required for a URL with a path",
            "target.method",
        )
    sdk_ctx = req.context.sdk if req.context else None
    sdk = Locator(sdk_ctx.ecosystem, sdk_ctx.package, sdk_ctx.version) if sdk_ctx else None
    entry, template = _resolve(index, target, method)

    facts: list[IndexedFact]
    stored = False
    if isinstance(target, UrlTarget) and entry is not None and template is not None:
        signal = None
        if req.error is not None:
            signal = extract_signal(req.error.status, req.error.body_excerpt, entry.signal_fields)
        if signal is None:
            facts = index.for_template(entry, template, sdk)
            reason = None if facts else "no_fact_for_signal"
        elif signal.empty:
            facts, reason = index.service_level(entry, sdk), "signal_not_extractable"
        else:
            facts, answered = index.for_signal(entry, template, signal, sdk)
            reason = None if answered else "no_fact_for_signal"
        if signal is not None and not signal.empty:  # pre-flight and empty errors: never (Q5)
            stored = _ingest(state, entry, template, signal, req, target, ip, user_agent, now)
    elif entry is not None and isinstance(target, HostTarget):
        facts = index.for_service(entry, sdk)
        reason = None if facts else "no_fact_for_signal"
    elif entry is not None and isinstance(target, Locator):
        facts = index.for_package(entry, target)
        reason = None if facts else "no_fact_for_signal"
    else:  # default-deny: answer with what the host's service knows, store nothing
        facts = index.service_level(entry, sdk) if entry is not None else []
        entry = entry if isinstance(target, UrlTarget) else None
        reason = "unregistered_target"
        _count_unregistered(state.store, target, now.date().isoformat())

    return {
        "service": entry.key if entry else None,
        "matched_template": {"method": template[0], "path": template[1]} if template else None,
        "facts": [f.document for f in facts],
        "observed": _observed(entry),
        "unknown": {"reason": reason, "stored_as_observation": stored},
        "registry": _registry(index, entry),
    }


# ── read endpoints ──────────────────────────────────────────────────────────────────────────────


def _cached(request: Request, payload: Any) -> Response:
    """JSON with a strong ETag and `Cache-Control: public, max-age=300` (spec 03)."""
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
    headers = {"ETag": etag, "Cache-Control": CACHE_CONTROL}
    wanted = request.headers.get("if-none-match", "")
    tags = {t.strip().removeprefix("W/") for t in wanted.split(",")}
    if etag in tags or "*" in tags:
        return Response(status_code=304, headers=headers)
    return Response(body, media_type="application/json", headers=headers)


# ── errors ──────────────────────────────────────────────────────────────────────────────────────


def _field(loc: tuple[Any, ...]) -> str | None:
    parts = [str(p) for p in loc[1:]] if loc and loc[0] == "body" else [str(p) for p in loc]
    return ".".join(parts) or None


async def _on_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    extra = next((e for e in errors if e.get("type") == "extra_forbidden"), None)
    if extra is not None:
        field = _field(tuple(extra["loc"]))
        return _error(400, "unknown_field", f"unknown field {field}", field)
    first = errors[0] if errors else {}
    message = first.get("msg", "invalid request")  # pydantic messages never echo the input
    return _error(400, "invalid_request", message, _field(tuple(first.get("loc", ()))))


_DEFAULT_CODES = {404: "not_found", 405: "method_not_allowed", 413: "body_too_large"}


async def _on_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "code" in exc.detail:
        body = {"error": exc.detail}
    else:
        code = _DEFAULT_CODES.get(exc.status_code, "error")
        body = _error_body(code, str(exc.detail))
    return JSONResponse(body, status_code=exc.status_code, headers=exc.headers)


def _without_422(default: Callable[[], dict[str, Any]]) -> Callable[[], dict[str, Any]]:
    """Validation errors are answered 400 with the error envelope, never FastAPI's 422."""

    def openapi() -> dict[str, Any]:
        schema = default()
        for operations in schema.get("paths", {}).values():
            for operation in operations.values():
                operation.get("responses", {}).pop("422", None)
        for name in ("HTTPValidationError", "ValidationError"):
            schema.get("components", {}).get("schemas", {}).pop(name, None)
        return schema

    return openapi


# ── factory ─────────────────────────────────────────────────────────────────────────────────────

_ERRORS = {status: {"model": ErrorResponse} for status in (400, 413, 429)}
_NOT_FOUND = {404: {"model": ErrorResponse}}


def create_app(
    repo: str | Path | None = None,
    db_path: str | Path | None = None,
    *,
    results_path: str | Path | None = None,
    per_net: int = 60,
    global_limit: int = 600,
    daily_cap: int = DAILY_CAP,
    template_cap: int = TEMPLATE_CAP,
    trusted_proxies: tuple[str, ...] | None = None,
    clock: Callable[[], float] | None = None,
    utcnow: Callable[[], datetime] | None = None,
) -> FastAPI:
    """Arguments override the environment (tests); the index and the store open at startup."""
    env_proxies = os.environ.get("APIFACTS_TRUSTED_PROXIES", ",".join(DEFAULT_TRUSTED_PROXIES))
    trusted = parse_proxies(trusted_proxies or env_proxies.split(","))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        root = Path(repo if repo is not None else os.environ.get("APIFACTS_REPO", "."))
        store = Store(db_path or os.environ.get("APIFACTS_DB", "observations.sqlite"))
        app.state.apifacts = _State(
            index=FactsIndex.load(root, os.environ.get("APIFACTS_REGISTRY_VERSION") or None),
            store=store,
            daily_cap=daily_cap,
            template_cap=template_cap,
            trusted_proxies=trusted,
            utcnow=utcnow or (lambda: datetime.now(UTC)),
            results=Path(
                results_path
                or os.environ.get("APIFACTS_RESULTS")
                or root / "var" / "results.jsonl"
            ),
        )
        try:
            yield
        finally:
            store.close()

    app = FastAPI(
        title="apifacts",
        version="v0",
        summary="Verified facts about machine interfaces for AI agents (data CC BY 4.0).",
        lifespan=lifespan,
    )
    limiter_kwargs = {"clock": clock} if clock else {}
    app.add_middleware(
        _CheckGuard,
        limiter=RateLimiter(per_net=per_net, global_limit=global_limit, **limiter_kwargs),
        trusted=trusted,
    )
    app.add_exception_handler(RequestValidationError, _on_validation)
    app.add_exception_handler(StarletteHTTPException, _on_http)
    app.openapi = _without_422(app.openapi)

    @app.post(CHECK_PATH, response_model=CheckResponse, responses=_ERRORS)
    def check(req: CheckRequest, request: Request) -> Response:
        """Facts and typed fixes for a target and (optionally) an observed error. Never empty.
        A target outside the registered templates is answered but not stored."""
        state = _state(request)
        ip = _caller_ip(request.scope.get("client"), request.headers, state.trusted_proxies)
        return JSONResponse(_check(state, req, ip, request.headers.get("user-agent")))

    @app.get("/v0/services", response_model=ServicesResponse)
    def services(request: Request) -> Response:
        index = _state(request).index
        payload = {
            "services": [
                {
                    "key": e.key,
                    "name": e.service.name,
                    "hosts": list(e.service.hosts),
                    "instance_hosts": list(instance_hosts_of(e.service)),
                    "templates": len(e.info.templates),
                    "facts": len(e.facts),
                }
                for e in index.services.values()
            ],
            "registry": {"version": index.version, "license": LICENSE},
        }
        return _cached(request, payload)

    @app.get("/v0/facts/{service}", response_model=FactsResponse, responses=_NOT_FOUND)
    def facts(service: str, request: Request) -> Response:
        index = _state(request).index
        entry = index.services.get(service)
        if entry is None:
            raise _fail(404, "unknown_service", f"no service {service}")
        payload = {
            "service": entry.key,
            "facts": [f.document for f in entry.facts],
            "registry": _registry(index, entry),
        }
        return _cached(request, payload)

    @app.get("/v0/facts/{service}/{slug}", response_model=FactOut, responses=_NOT_FOUND)
    def fact(service: str, slug: str, request: Request) -> Response:
        found = _state(request).index.fact(service, slug)
        if found is None:
            raise _fail(404, "unknown_fact", f"no fact af:{service}:{slug}")
        return _cached(request, found.document)

    @app.get("/healthz", response_model=Health)
    def healthz(request: Request) -> dict[str, Any]:
        state = _state(request)
        return {
            "ok": True,
            "registry_version": state.index.version,
            "probes_last_run": last_probe_run(state.results),
        }

    return app


app = create_app()
