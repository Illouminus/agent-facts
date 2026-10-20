"""HTTP steps: render, re-check, authenticate and send one request (spec 04)."""

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True)
class StepResponse:
    status: int | None  # None when the request never got a response
    headers: httpx.Headers
    body: bytes
    json: Any  # parsed body, or templating.NOT_JSON
    latency_ms: int
    error: str | None = None  # normalized transport error ("timeout", "connect_error", …)
