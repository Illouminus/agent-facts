"""In-memory sliding-window rate limits for POST /v0/check (spec 03 step 5).

A request is allowed when its network has < `per_net` and everyone together < `global_limit`
accepted requests in the last `window_s` seconds; refused requests are not recorded, so a blocked
caller is free again exactly one window after its oldest accepted hit. Memory is bounded: at most
`global_limit` timestamps are live, idle networks are swept once `sweep_at` are tracked. One
process only (state is not shared between uvicorn workers).
"""

import math
import threading
import time
from collections import deque
from collections.abc import Callable


class RateLimiter:
    def __init__(
        self,
        per_net: int = 60,
        global_limit: int = 600,
        window_s: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
        sweep_at: int = 4096,
    ):
        self.per_net, self.global_limit, self.window_s = per_net, global_limit, window_s
        self._clock, self._sweep_at = clock, sweep_at
        self._global: deque[float] = deque()
        self._nets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _evict(self, hits: deque[float], now: float) -> None:
        while hits and hits[0] <= now - self.window_s:
            hits.popleft()

    def _wait(self, hits: deque[float], now: float) -> int:
        return max(1, math.ceil(hits[0] + self.window_s - now))

    def hit(self, net: str) -> int | None:
        """Record one request from `net`: None if allowed, else the Retry-After seconds."""
        with self._lock:
            now = self._clock()
            if len(self._nets) >= self._sweep_at:
                self._sweep(now)
            hits = self._nets.setdefault(net, deque())
            self._evict(hits, now)
            self._evict(self._global, now)
            waits = []
            if len(hits) >= self.per_net:
                waits.append(self._wait(hits, now))
            if len(self._global) >= self.global_limit:
                waits.append(self._wait(self._global, now))
            if waits:
                return max(waits)
            hits.append(now)
            self._global.append(now)
            return None

    def _sweep(self, now: float) -> None:
        horizon = now - self.window_s
        idle = [n for n, hits in self._nets.items() if not hits or hits[-1] <= horizon]
        for net in idle:
            del self._nets[net]

    def tracked_networks(self) -> int:
        with self._lock:
            return len(self._nets)
