#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin — in-memory write buffer
#########################################################################

"""
Write-buffer for the database plugin.

The database plugin does not write every item change immediately to the
database.  Instead it batches pending writes in an in-memory buffer and
flushes them periodically (default every 60 seconds) via the scheduler.
This reduces I/O load significantly on busy systems.

The buffer stores :class:`~constants.BufferEntry` named tuples, one list
per item.  Each entry represents one *log row*:

- The ``duration`` field is ``None`` while the value is still active
  (its duration is not yet known).
- When the item changes, the duration of the *previous* entry is
  back-filled: ``duration = new_timestamp - entry.time``.
- On ``_dump()``, the full list is removed from the buffer and written to
  the database.  If the write fails, the entries are restored.
"""

import threading
import logging
from typing import Dict, List

from .constants import BufferEntry, QUALITY_VALID, QUALITY_NO_DATA

logger = logging.getLogger(__name__)


class BufferManager:
    """Thread-safe in-memory buffer for pending database writes.

    One :class:`BufferManager` instance is shared between the plugin's
    ``update_item()`` callback (which pushes entries) and the scheduler-
    driven ``_dump()`` method (which pops and writes them).

    All public methods acquire the internal lock themselves; callers do
    not need to hold any lock.

    :Example usage::

        mgr = BufferManager()
        mgr.register(item)

        # on item change:
        mgr.close_open(item, new_ts)
        mgr.push(item, BufferEntry(new_ts, None, new_value))

        # on dump:
        entries = mgr.pop_all(item)
        # ... write to DB ...
        # on failure:
        mgr.restore(item, entries)
    """

    def __init__(self) -> None:
        self._buffer: Dict[object, List[BufferEntry]] = {}
        self._lock = threading.Lock()

    # ── registration ──────────────────────────────────────────────────────────

    def register(self, item) -> None:
        """Allocate an empty buffer list for a newly registered item.

        Must be called once per item in ``parse_item()`` before any
        ``push()`` calls.

        :param item: SmartHomeNG item object.
        """
        with self._lock:
            if item not in self._buffer:
                self._buffer[item] = []

    # ── writing ───────────────────────────────────────────────────────────────

    def push(self, item, entry: BufferEntry) -> None:
        """Append *entry* to the item's pending-write list.

        :param item:  SmartHomeNG item object (must have been registered).
        :param entry: :class:`~constants.BufferEntry` to append.
        :raises KeyError: if *item* was not registered first.
        """
        with self._lock:
            self._buffer[item].append(entry)

    def close_open(self, item, end_ts: int) -> None:
        """Set the duration on the last open entry (duration=None) for *item*.

        When an item's value changes, the *previous* value's duration
        becomes known.  This method back-fills it before pushing the new
        entry.

        Does nothing if the buffer is empty or if the last entry already
        has a duration set (i.e. is already closed).

        :param item:   SmartHomeNG item.
        :param end_ts: Timestamp at which the previous value ended
                       (milliseconds since epoch).
        """
        with self._lock:
            buf = self._buffer.get(item)
            if buf and buf[-1].duration is None:
                last = buf[-1]
                buf[-1] = last._replace(duration=end_ts - last.time)

    def push_invalid(self, item, start_ts: int) -> None:
        """Open a *no-data* gap entry for *item*.

        Call this when a data source signals that it has lost connectivity.
        The gap entry is stored with ``quality=QUALITY_NO_DATA`` and all
        value fields ``None``.  Its duration remains open (``None``) until
        :meth:`close_open` is called when connectivity is restored.

        :param item:     SmartHomeNG item.
        :param start_ts: Timestamp when the gap started (milliseconds).
        """
        # Close any currently-open valid entry first.
        self.close_open(item, start_ts)
        self.push(item, BufferEntry(time=start_ts, duration=None,
                                    value=None, quality=QUALITY_NO_DATA))

    # ── reading / introspection ────────────────────────────────────────────────

    def has_open_entry(self, item) -> bool:
        """Return ``True`` if the last entry for *item* is still open.

        An "open" entry has ``duration=None``, meaning the value is still
        active and its duration is not yet known.

        :param item: SmartHomeNG item.
        :rtype:      bool
        """
        with self._lock:
            buf = self._buffer.get(item, [])
            return bool(buf) and buf[-1].duration is None

    def last_entry(self, item) -> 'BufferEntry | None':
        """Return the last buffered entry for *item*, or ``None``.

        :param item: SmartHomeNG item.
        :rtype:      BufferEntry | None
        """
        with self._lock:
            buf = self._buffer.get(item, [])
            return buf[-1] if buf else None

    def items(self) -> list:
        """Return a snapshot list of all registered items.

        :rtype: list
        """
        with self._lock:
            return list(self._buffer.keys())

    def pending_count(self, item) -> int:
        """Return the number of pending entries for *item*.

        :param item: SmartHomeNG item.
        :rtype:      int
        """
        with self._lock:
            return len(self._buffer.get(item, []))

    # ── dump support ──────────────────────────────────────────────────────────

    def pop_all(self, item) -> List[BufferEntry]:
        """Remove and return all pending entries for *item*.

        The returned entries are removed from the buffer atomically.
        If the subsequent database write fails, call :meth:`restore` to
        put them back.

        :param item: SmartHomeNG item.
        :returns:    List of :class:`~constants.BufferEntry` objects.
        :rtype:      list[BufferEntry]
        """
        with self._lock:
            entries = list(self._buffer.get(item, []))
            if item in self._buffer:
                del self._buffer[item][:len(entries)]
            return entries

    def restore(self, item, entries: List[BufferEntry]) -> None:
        """Prepend *entries* back into the buffer after a failed dump.

        The restored entries are placed before any new entries that may
        have arrived while the dump was running.

        :param item:    SmartHomeNG item.
        :param entries: Entries to restore (previously returned by
                        :meth:`pop_all`).
        """
        with self._lock:
            if item in self._buffer:
                self._buffer[item] = entries + self._buffer[item]
            else:
                self._buffer[item] = list(entries)
