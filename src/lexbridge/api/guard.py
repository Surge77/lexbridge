"""Per-client rate limiting and an answer cache: the free model tier is the scarce resource.

Both are in-process. The API runs as one process on one small machine; a shared store
would be infrastructure with nothing to share between.
"""

from __future__ import annotations

import threading
import time
from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable, Hashable
from typing import Generic, TypeVar

K = TypeVar("K", bound=Hashable)
V = TypeVar("V")


class RateLimiter:
    """At most `limit` requests per client in any sliding `window_seconds`."""

    def __init__(self, *, limit: int, window_seconds: float,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self._limit = limit
        self._window = window_seconds
        self._clock = clock
        self._seen: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def wait(self, client: str) -> float:
        """0 when the request may go ahead (and is counted), else seconds until it may."""
        now = self._clock()
        with self._lock:
            seen = self._seen[client]
            while seen and seen[0] <= now - self._window:
                seen.popleft()
            if len(seen) >= self._limit:
                return seen[0] + self._window - now
            seen.append(now)
            return 0


class AnswerCache(Generic[K, V]):
    """Least-recently-used cache: a repeated question costs no model call."""

    def __init__(self, *, capacity: int) -> None:
        self._capacity = capacity
        self._items: OrderedDict[K, V] = OrderedDict()
        self._lock = threading.Lock()

    def get(self, key: K) -> V | None:
        with self._lock:
            if key not in self._items:
                return None
            self._items.move_to_end(key)
            return self._items[key]

    def put(self, key: K, value: V) -> None:
        with self._lock:
            self._items[key] = value
            self._items.move_to_end(key)
            if len(self._items) > self._capacity:
                self._items.popitem(last=False)
