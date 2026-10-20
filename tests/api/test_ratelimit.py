"""Sliding-window limits: 60/min per reporter network, 600/min global (spec 03 step 5)."""

from agentfacts.api.ratelimit import RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_per_network_limit_with_retry_after():
    clock = Clock()
    limiter = RateLimiter(per_net=60, global_limit=600, window_s=60, clock=clock)
    for _ in range(60):
        assert limiter.hit("a") is None
        clock.now += 0.5
    assert limiter.hit("a") == 30  # oldest hit (t=1000) leaves the window at t=1060; now 1030
    assert limiter.hit("b") is None


def test_rejected_hits_do_not_extend_the_block():
    clock = Clock()
    limiter = RateLimiter(per_net=2, global_limit=100, window_s=60, clock=clock)
    limiter.hit("a")
    limiter.hit("a")
    for _ in range(10):
        assert limiter.hit("a") is not None
    clock.now += 60
    assert limiter.hit("a") is None


def test_global_limit_across_networks():
    clock = Clock()
    limiter = RateLimiter(per_net=60, global_limit=600, window_s=60, clock=clock)
    for i in range(600):
        assert limiter.hit(f"net-{i % 20}") is None
    assert limiter.hit("fresh") == 60
    clock.now += 60
    assert limiter.hit("fresh") is None


def test_retry_after_is_at_least_one_second():
    clock = Clock()
    limiter = RateLimiter(per_net=1, global_limit=10, window_s=60, clock=clock)
    limiter.hit("a")
    clock.now += 59.9
    assert limiter.hit("a") == 1


def test_idle_networks_are_forgotten():
    clock = Clock()
    limiter = RateLimiter(per_net=5, global_limit=10_000, window_s=60, clock=clock, sweep_at=10)
    for i in range(10):
        limiter.hit(f"n{i}")
    clock.now += 61
    limiter.hit("new")
    assert limiter.tracked_networks() == 1
