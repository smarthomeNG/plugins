#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  This file is part of SmartHomeNG.py.
#  https://www.smarthomeng.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

"""Bookkeeping for knxd group cache reads that need to be repeated until answered"""

import threading
from collections.abc import Iterable, Sequence


class CacheReadTracker:
    """
    Tracks group addresses read from the knxd group cache until a value arrived.

    knxd answers a cache miss with an empty entry after a short timeout while the
    bus read it triggered may still complete afterwards and fill the cache, so
    unanswered group addresses are read again in rounds spaced by ``retry_delays``.

    All methods are safe to call from different threads.

    :param retry_delays: seconds to wait before each retry round; the number of
                         entries is the maximum number of retry rounds
    """

    def __init__(self, retry_delays: Sequence[float]) -> None:
        self._retry_delays = tuple(retry_delays)
        self._lock = threading.Lock()
        self._pending: list[str] = []
        self._rounds_done = 0
        self._replied = False

    @property
    def replied(self) -> bool:
        """True once knxd answered any cache read of the current run, with or without a value"""
        with self._lock:
            return self._replied

    def note_reply(self) -> None:
        """Record that knxd answered a cache read, which proves it has a group cache"""
        with self._lock:
            self._replied = True

    @property
    def pending(self) -> list[str]:
        """Group addresses without a value yet, in the order they were registered"""
        with self._lock:
            return list(self._pending)

    def start(self, gas: Iterable[str]) -> list[str]:
        """
        Begin a new run, discarding the state of any previous one.

        :param gas: group addresses to read, duplicates allowed
        :return: the distinct group addresses in their original order
        """
        with self._lock:
            self._pending = list(dict.fromkeys(gas))
            self._rounds_done = 0
            self._replied = False
            return list(self._pending)

    def answered(self, ga: str) -> bool:
        """
        Mark a group address as having received a value.

        :return: True if the group address was still waiting for its first value
        """
        with self._lock:
            if ga in self._pending:
                self._pending.remove(ga)
                return True
            return False

    def next_retry_delay(self) -> float | None:
        """
        :return: seconds to wait before the next retry round, or None if
                 everything was answered or all retry rounds are used up
        """
        with self._lock:
            if not self._pending or self._rounds_done >= len(self._retry_delays):
                return None
            return self._retry_delays[self._rounds_done]

    def take_retry(self) -> list[str]:
        """
        Consume one retry round.

        :return: the group addresses that are still unanswered and must be read again
        """
        with self._lock:
            self._rounds_done += 1
            return list(self._pending)
