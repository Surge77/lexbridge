from __future__ import annotations

from lexbridge.api.guard import AnswerCache, RateLimiter


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_a_client_is_refused_past_its_limit_and_told_when_to_return() -> None:
    clock = Clock()
    limiter = RateLimiter(limit=2, window_seconds=60, clock=clock)

    assert limiter.wait("1.2.3.4") == 0
    clock.now += 10
    assert limiter.wait("1.2.3.4") == 0
    assert limiter.wait("1.2.3.4") == 50  # the first request leaves the window at 1060


def test_requests_leave_the_window_as_it_slides() -> None:
    clock = Clock()
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.wait("a")

    clock.now += 60

    assert limiter.wait("a") == 0


def test_a_refused_request_does_not_use_up_the_allowance() -> None:
    clock = Clock()
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    limiter.wait("a")
    limiter.wait("a")  # refused

    clock.now += 60

    assert limiter.wait("a") == 0


def test_clients_are_limited_separately() -> None:
    limiter = RateLimiter(limit=1, window_seconds=60, clock=Clock())
    limiter.wait("a")

    assert limiter.wait("b") == 0


def test_a_client_whose_window_has_emptied_is_forgotten() -> None:
    clock = Clock()
    limiter = RateLimiter(limit=1, window_seconds=60, clock=clock)
    for n in range(100):
        limiter.wait(f"10.0.0.{n}")

    clock.now += 60
    limiter.wait("fresh")

    assert limiter.tracked == 1


def test_when_too_many_clients_are_tracked_new_ones_are_refused() -> None:
    limiter = RateLimiter(limit=5, window_seconds=60, max_clients=2, clock=Clock())
    limiter.wait("a")
    limiter.wait("b")

    assert limiter.wait("c") > 0
    assert limiter.wait("a") == 0


def test_a_cached_answer_expires() -> None:
    clock = Clock()
    cache: AnswerCache[str, int] = AnswerCache(capacity=2, ttl_seconds=10, clock=clock)
    cache.put("a", 1)

    clock.now += 10

    assert cache.get("a") is None


def test_the_cache_forgets_the_least_recently_used_answer_first() -> None:
    cache: AnswerCache[str, int] = AnswerCache(capacity=2, ttl_seconds=60)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1  # a is now the most recent

    cache.put("c", 3)

    assert (cache.get("a"), cache.get("b"), cache.get("c")) == (1, None, 3)
