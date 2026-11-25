"""Sliding-window rate limiting."""

import threading
import time
from collections import deque
from collections.abc import Callable

WINDOW_SECONDS = 60.0


class SlidingWindowLimiter:
    """Counts hits per key within the last minute and refuses hits beyond a limit."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str, limit: int) -> float | None:
        """
        Record a hit for the key unless the limit is reached.

        :param key: the counted subject
        :param limit: allowed hits per minute; 0 or less disables limiting
        :return: None if the hit was recorded, else the seconds until a hit would be allowed
        """
        if limit <= 0:
            return None
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= WINDOW_SECONDS:
                hits.popleft()
            if len(hits) >= limit:
                return hits[0] + WINDOW_SECONDS - now
            hits.append(now)
            return None
