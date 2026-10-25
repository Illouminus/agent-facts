"""From a test's exception to a `Signal`: method, URL, status, body excerpt, vendor SDK.

Duck-typed, so neither requests nor httpx is imported: `requests.HTTPError` and
`httpx.HTTPStatusError` (`.response`, `.request`), SDK errors with `status_code`/`http_status` and
`request.url` (openai, anthropic, …), aiohttp's `status` + `request_info`. Reading never touches the
network: an unread streaming body is left alone and `str(exc)` stands in for it.
"""

import functools
import importlib.metadata
import re
from collections.abc import Iterator
from typing import Any

from apifacts.client.request import RAW_CHARS, Signal, make_signal

CHAIN_LIMIT = 32
# Modules whose exceptions say nothing about a vendor SDK.
HTTP_LIBRARIES = frozenset(
    {
        "requests",
        "httpx",
        "httpcore",
        "urllib3",
        "aiohttp",
        "urllib",
        "http",
        "builtins",
        "pytest",
        "_pytest",
        "apifacts",
        "apifacts_pytest",
    }
)


def _attr(obj: Any, name: str) -> Any:
    """getattr that never raises (httpx raises RuntimeError for an unset `.request`)."""
    if obj is None:
        return None
    try:
        return getattr(obj, name, None)
    except Exception:
        return None


def _text(value: Any) -> str | None:
    try:
        return value if isinstance(value, str) else (None if value is None else str(value))
    except Exception:
        return None


def iter_chain(exc: BaseException) -> Iterator[BaseException]:
    """The exception, its causes and contexts, and group members; breadth-first, each once."""
    queue: list[Any] = [exc]
    seen: set[int] = set()
    while queue and len(seen) < CHAIN_LIMIT:
        current = queue.pop(0)
        if not isinstance(current, BaseException) or id(current) in seen:
            continue
        seen.add(id(current))
        yield current
        if isinstance(current, BaseExceptionGroup):
            queue.extend(current.exceptions)
        queue.extend((current.__cause__, current.__context__))


def _status(*candidates: Any) -> int | None:
    for value in candidates:
        if isinstance(value, int) and not isinstance(value, bool) and 100 <= value <= 599:
            return value
    return None


def _body(exc: BaseException, response: Any) -> str | None:
    # requests keeps `_content = False` until a streamed body is consumed; reading it would block
    # on the socket. httpx raises ResponseNotRead instead, which _attr turns into None.
    if response is not None and _attr(response, "_content") is not False:
        content = _attr(response, "content")
        if isinstance(content, bytes | bytearray):
            text = bytes(content[: RAW_CHARS * 4]).decode("utf-8", "replace")
        else:
            text = _text(_attr(response, "text"))
        if text and text.strip():
            return text
    http_body = _attr(exc, "http_body")  # stripe-style SDKs
    if isinstance(http_body, bytes | bytearray):
        http_body = bytes(http_body[: RAW_CHARS * 4]).decode("utf-8", "replace")
    if isinstance(http_body, str) and http_body.strip():
        return http_body
    return _text(exc)


def _signal(exc: BaseException) -> Signal | None:
    response = _attr(exc, "response")
    request = _attr(exc, "request") or _attr(response, "request")
    request_info = _attr(exc, "request_info")
    status = _status(
        _attr(response, "status_code"),
        _attr(exc, "status_code"),
        _attr(exc, "http_status"),
        _attr(exc, "status"),
    )
    if status is None:
        return None
    url = next(
        (
            u
            for u in map(
                _text, (_attr(request, "url"), _attr(request_info, "url"), _attr(response, "url"))
            )
            if u
        ),
        None,
    )
    if url is None:
        return None
    method = _text(_attr(request, "method")) or _text(_attr(request_info, "method"))
    return make_signal(
        url, method=method, status=status, body=_body(exc, response), sdk=sdk_context(exc)
    )


@functools.cache
def _distributions() -> dict[str, list[str]]:
    return importlib.metadata.packages_distributions()


def sdk_context(exc: BaseException) -> dict[str, str] | None:
    """`{package, ecosystem, version}` of the installed distribution that defines the exception."""
    module = (_text(type(exc).__module__) or "").split(".")[0]
    if not module or module in HTTP_LIBRARIES or module.startswith("_"):
        return None
    try:
        names = _distributions().get(module) or []
        if len(set(names)) != 1:  # unknown, or a namespace shared by several distributions
            return None
        version = importlib.metadata.version(names[0])
    except Exception:
        return None
    package = re.sub(r"[-_.]+", "-", names[0]).lower()
    return {"package": package, "ecosystem": "pypi", "version": version}


def signal_from_exception(exc: BaseException) -> Signal | None:
    """The first HTTP error in the chain (outermost first), as a filtered `Signal`."""
    for current in iter_chain(exc):
        try:
            signal = _signal(current)
        except Exception:
            signal = None
        if signal is not None:
            return signal
    return None
