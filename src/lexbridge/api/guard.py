"""Rate limits and an answer cache: the free model tier is the scarce resource.

Both are in-process. The API runs as one process on one small machine; a shared store
would be infrastructure with nothing to share between.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable, Hashable
from dataclasses import dataclass
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")
# Enough for every real visitor of a small demo; past it, new clients wait rather than
# grow memory without bound under a flood of spoofed or rotating addresses.
MAX_CLIENTS = 10_000


class RateLimiter:
    """At most `limit` requests per client in any sliding `window_seconds`."""

    def __init__(self, *, limit: int, window_seconds: float, max_clients: int = MAX_CLIENTS,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._window = window_seconds
        self._max_clients = max_clients
        self._clock = clock
        self._seen: dict[str, deque[float]] = {}
        self._swept = clock()
        self._lock = threading.Lock()

    @property
    def tracked(self) -> int:
        return len(self._seen)

    def _forget_idle(self, now: float) -> None:
        idle = [c for c, seen in self._seen.items() if not seen or seen[-1] <= now - self._window]
        for client in idle:
            del self._seen[client]

    def wait(self, client: str) -> float:
        """0 when the request may go ahead (and is counted), else seconds until it may."""
        now = self._clock()
        with self._lock:
            # Clients whose window has emptied are dropped once a window, so memory follows
            # current traffic, not every address ever seen.
            if now - self._swept >= self._window:
                self._forget_idle(now)
                self._swept = now
            if client not in self._seen and len(self._seen) >= self._max_clients:
                return self._window
            seen = self._seen.setdefault(client, deque())
            while seen and seen[0] <= now - self._window:
                seen.popleft()
            if len(seen) >= self._limit:
                return seen[0] + self._window - now
            seen.append(now)
            return 0


@dataclass(frozen=True)
class Limits:
    per_minute: RateLimiter  # per client, every request
    per_day: RateLimiter  # per client, questions
    # One shared key: questions that need the model, across all clients. The free tier's
    # daily token budget is shared too, so no one client may spend it for everyone.
    model_calls: RateLimiter


class AnswerCache(Generic[K, V]):
    """Least-recently-used cache with expiry: a repeated question costs no model call."""

    def __init__(self, *, capacity: int, ttl_seconds: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._capacity = capacity
        self._ttl = ttl_seconds
        self._clock = clock
        self._items: OrderedDict[K, tuple[float, V]] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            if item[0] <= self._clock():
                del self._items[key]
                return None
            self._items.move_to_end(key)
            return item[1]

    def put(self, key: K, value: V) -> None:
        with self._lock:
            self._items[key] = (self._clock() + self._ttl, value)
            self._items.move_to_end(key)
            if len(self._items) > self._capacity:
                self._items.popitem(last=False)
