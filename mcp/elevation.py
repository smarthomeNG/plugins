"""Temporary elevation of a client's access ceiling."""

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from .types import Access

MAX_ELEVATE_MINUTES = 24 * 60
DEFAULT_ELEVATE_MINUTES = 30


@dataclass(frozen=True)
class Elevation:
    """What an administrator may temporarily grant a client: the ceiling it gets and for how many minutes."""

    max_access: Access
    minutes: int


class ElevationTimer:
    """Remembers until when each client is elevated; held in memory only, so a restart ends every elevation."""

    def __init__(self, clock: Callable[[], float] = time.monotonic):
        self._clock = clock
        self._until: dict[str, float] = {}
        self._lock = threading.Lock()

    def start(self, client: str, minutes: int) -> None:
        """Elevate the client for ``minutes`` from now, replacing a running elevation."""
        with self._lock:
            self._until[client] = self._clock() + minutes * 60

    def stop(self, client: str) -> None:
        """End the client's elevation; does nothing if it has none."""
        with self._lock:
            self._until.pop(client, None)

    def remaining(self, client: str) -> float | None:
        """Return the seconds left of the client's elevation, None if it is not elevated."""
        with self._lock:
            until = self._until.get(client)
            if until is None:
                return None
            left = until - self._clock()
            if left <= 0:
                del self._until[client]
                return None
            return left
