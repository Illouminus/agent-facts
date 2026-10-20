"""HTTP steps: render, re-check, authenticate and send one request (spec 04).

`prepare` renders a step and re-checks the *rendered* request before anything is sent — the
validator saw only the template: the path must instantiate a registered template for the method,
a prod probe stays read-only (`http_step_violations`), and a step that uses the service key must run
in the env that key reaches. `send` adds credentials and the runner's User-Agent last, never follows
redirects (a key never follows a `Location`), ignores proxy/netrc environment, asks for an identity
encoding and decodes gzip/deflate itself under the body cap (no decompression bomb), and stops a
body that drips past the timeout as a whole.
"""

import base64
import json
import time
import zlib
from dataclasses import dataclass
from typing import Any

import httpx

from agentfacts.probe import USER_AGENT
from agentfacts.probe.templating import NOT_JSON, RunContext, TemplateError, render, render_path
from agentfacts.schema.models import HttpStep, Service, http_step_violations
from agentfacts.schema.registry import match_template, on_vendor_domain

TIMEOUT_S = 20.0
MAX_BODY_BYTES = 1024 * 1024
MAX_RAW_BYTES = 4 * MAX_BODY_BYTES  # what we read off the wire, compressed or not


class Refused(Exception):
    """The runner will not send this request; `code` is a validator-style problem code."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class StepResponse:
    status: int | None  # None when the request never got a response
    headers: httpx.Headers
    body: bytes
    json: Any  # parsed body, or templating.NOT_JSON
    latency_ms: int
    error: str | None = None  # normalized transport error ("timeout", "connect_error", …)


@dataclass(frozen=True)
class PreparedRequest:
    method: str
    path: str  # rendered, percent-encoded
    template: str  # the registered template it instantiates
    query: dict[str, str]
    form: dict[str, str] | None
    json_body: Any
    headers: dict[str, str]
    uses_key: bool


def _scalar_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return value if isinstance(value, str) else json.dumps(value)


def _uses_key(step: HttpStep, service: Service) -> bool:
    return step.auth == "service" and service.auth is not None and service.auth.kind != "none"


def matching_template(service: Service, method: str, path: str) -> str | None:
    http = service.surfaces.http
    for template in http.templates if http else ():
        if template.method == method and match_template(path, template.path):
            return template.path
    return None


def prepare(step: HttpStep, ctx: RunContext, service: Service, env: str) -> PreparedRequest:
    try:
        path = render_path(step.path, ctx)
        query = {k: _scalar_text(render(v, ctx)) for k, v in (step.query or {}).items()}
        form = (
            {k: _scalar_text(render(v, ctx)) for k, v in step.form.items()}
            if step.form is not None
            else None
        )
        json_body = render(step.json_body, ctx, keep_type=True)
        headers = {k: str(render(v, ctx)) for k, v in (step.headers or {}).items()}
    except TemplateError as exc:
        raise Refused("template_error", str(exc)) from None

    template = matching_template(service, step.method, path)
    if template is None:
        raise Refused(
            "unregistered_template", f"{step.method} {path} matches no template of {service.key}"
        )
    rendered = {"method": step.method, "headers": headers, "query": query, "form": form,
                "json": json_body}
    if violations := http_step_violations(rendered, env):
        _, code, message = violations[0]
        raise Refused(code, message)
    uses_key = _uses_key(step, service)
    if uses_key and service.auth.env != env:
        raise Refused(
            "auth_env_mismatch", f"probe env {env} but the {service.key} key reaches "
            f"{service.auth.env}"
        )
    return PreparedRequest(step.method, path, template, query, form, json_body, headers, uses_key)


def base_url_for(service: Service, env: str) -> str:
    url = getattr(service.dimensions.env, env, None)
    if url is None:
        raise Refused("env_not_offered", f"{service.key} offers no {env} environment")
    if not on_vendor_domain(url, service.hosts):
        raise Refused("foreign_host", f"{url} is not on {service.key}'s hosts")
    return url


def auth_for(service: Service, key: str | None) -> tuple[dict[str, str], dict[str, str]]:
    """(headers, query parameters) that carry the service key."""
    auth = service.auth
    if auth is None or auth.kind == "none" or key is None:
        return {}, {}
    if auth.kind == "bearer":
        return {"Authorization": f"Bearer {key}"}, {}
    if auth.kind == "basic":
        user_pass = key if ":" in key else key + ":"  # a bare key is the user, empty password
        return {"Authorization": "Basic " + base64.b64encode(user_pass.encode()).decode()}, {}
    if auth.kind == "header":
        return {auth.header_name: key}, {}
    return {}, {auth.param_name: key}


def make_client(timeout: float = TIMEOUT_S) -> httpx.Client:
    return httpx.Client(timeout=timeout, follow_redirects=False, trust_env=False)


def _error_name(exc: httpx.HTTPError) -> str:
    if isinstance(exc, httpx.TimeoutException):
        return "timeout"
    if isinstance(exc, httpx.ConnectError):
        return "connect_error"
    return "http_error:" + type(exc).__name__


class _Decoder:
    """Bounded decoder: `feed` returns at most `limit` decoded bytes; `done` turns true at the end
    of a compressed stream or on corrupt data, after which nothing more is read. Unknown encodings
    (br, zstd) stay raw — the body is then simply not JSON."""

    def __init__(self, content_encoding: str | None):
        encoding = (content_encoding or "identity").strip().lower()
        self.compressed = encoding in ("gzip", "x-gzip", "deflate")
        self.done = False
        # deflate is zlib-wrapped or (some servers) raw: decided on the first chunk.
        self._z = zlib.decompressobj(16 + zlib.MAX_WBITS) if encoding != "deflate" else None

    def feed(self, chunk: bytes, limit: int) -> bytes:
        if not self.compressed:
            return chunk[:limit]
        if self._z is None:
            wrapped = bool(chunk) and (chunk[0] & 0x0F) == 8
            self._z = zlib.decompressobj(zlib.MAX_WBITS if wrapped else -zlib.MAX_WBITS)
        try:
            data = self._z.decompress(chunk, limit)
        except zlib.error:
            self.done = True
            return b""
        self.done = self._z.eof
        return data


def _parse(body: bytes) -> Any:
    if not body:
        return NOT_JSON
    try:
        return json.loads(body)
    except ValueError:
        return NOT_JSON


def send(
    client: httpx.Client,
    base_url: str,
    request: PreparedRequest,
    auth_headers: dict[str, str],
    auth_query: dict[str, str],
) -> StepResponse:
    headers = httpx.Headers(request.headers)
    for name, value in auth_headers.items():
        headers[name] = value
    headers["User-Agent"] = USER_AGENT
    headers["Accept-Encoding"] = "identity"
    url = base_url.rstrip("/") + request.path
    params = {**request.query, **auth_query}
    total = client.timeout.read or TIMEOUT_S
    started = time.perf_counter()

    def failed(error: str) -> StepResponse:
        latency = int((time.perf_counter() - started) * 1000)
        return StepResponse(None, httpx.Headers(), b"", NOT_JSON, latency, error)

    try:
        with client.stream(
            request.method,
            url,
            params=params or None,
            data=request.form,
            json=request.json_body,
            headers=headers,
        ) as response:
            decoder = _Decoder(response.headers.get("content-encoding"))
            body, raw = bytearray(), 0
            for chunk in response.iter_raw():
                if time.perf_counter() - started > total:
                    return failed("timeout")
                raw += len(chunk)
                body.extend(decoder.feed(chunk, MAX_BODY_BYTES - len(body)))
                if decoder.done or len(body) >= MAX_BODY_BYTES or raw >= MAX_RAW_BYTES:
                    break
            status, response_headers = response.status_code, response.headers
    except httpx.HTTPError as exc:
        return failed(_error_name(exc))
    latency = int((time.perf_counter() - started) * 1000)
    return StepResponse(status, response_headers, bytes(body), _parse(bytes(body)), latency)
