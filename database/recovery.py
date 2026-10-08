#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin — repair of log rows left open by an unclean shutdown
#########################################################################

"""
Repair of log rows left open by an unclean shutdown.

A regular shutdown closes every item's last log row (``duration`` set). After a crash that row keeps
``duration IS NULL`` although the value is no longer active. Reads treat such a row as running up to the
end of the queried range, and compaction cannot aggregate an interval consisting only of such rows.

Two parts, sharing one rule for where an open row ends (:meth:`CrashRecovery._closing_time`):

- :meth:`CrashRecovery.close_startup_orphans` closes each registered item's last row at startup.
- :meth:`CrashRecovery.recover_stale_slice` works through the rows older crashes left behind earlier in the
  history, in bounded slices.
"""

import time

from .constants import COL_ITEM_ID, QUALITY_VALID


class CrashRecovery:
    """Closes log rows that a previous run left open.

    Takes a back-reference to the Database plugin instance (*plugin*) rather than individual parameters -
    see maintenance.py's MaintenanceManager for the same pattern.
    """

    window_rows = 100000  # log rows of one item examined per slice

    def __init__(self, plugin):
        self._plugin = plugin
        self._last_flush = None  # newest item-table `changed` at startup, before this run's first dump
        self._worklist = None  # database item ids still to scan; None until built
        self._after = -1  # `time` of the last row handled for the item at the head of the worklist

    def _log_failure(self, error: Exception, what: str, db) -> None:
        """Log a failed database step: a lock timeout at info, anything else by its cause (see
        Database._log_db_exception())."""
        plugin = self._plugin
        if isinstance(error, TimeoutError):
            plugin.logger.info(f'Database: {what} could not acquire the lock{db.lock_holder_description()}')
        else:
            plugin._log_db_exception(error, f'Database: {what} failed: {error}', db=db, exc_info=True)

    @staticmethod
    def _closing_time(open_time: int, *bounds) -> int:
        """Return the time at which an open row ends: the earliest of the given bounds (``None`` is ignored),
        but not before the row's own start."""
        return max(open_time, min(bound for bound in bounds if bound is not None))

    def close_startup_orphans(self) -> int:
        """Close the open last log row of every registered item at the last time any item was flushed.

        Must run before the first dump of this process: the flush timestamp it relies on is the item table's
        newest ``changed``, which every dump advances. The end is clamped to ``[row.time, start of this run]``.

        A row whose ``time`` equals the item's ``last_change()`` is the active value restored by
        ``database: init`` and stays open.

        :return: number of rows closed
        """
        plugin = self._plugin
        if plugin._db.verify(2) == 0:
            return 0
        closed = 0
        try:
            with plugin._db.transaction(timeout=300) as cur:
                last_flush = plugin._item_store.max_changed(cur=cur)
                if last_flush is None:
                    return 0
                self._last_flush = last_flush
                for item in plugin._buffer_mgr.items():
                    item_id = plugin.id(item, create=False, cur=cur)
                    if item_id is None:
                        continue
                    head = plugin._log_store.last_row(item_id, cur=cur)
                    if head is None or head.duration is not None or head.quality != QUALITY_VALID:
                        continue
                    if head.time == plugin._timestamp(item.last_change()):
                        continue  # still active: restored by `database: init`
                    end = self._closing_time(head.time, last_flush, plugin._plugin_start_ts)
                    plugin._log_store.close_open(item_id, head.time, end - head.time, cur=cur)
                    closed += 1
        except Exception as e:
            self._log_failure(e, 'repairing open log rows', plugin._db)
            return 0
        if closed:
            plugin.logger.info(f'Database: closed {closed} log rows left open by an unclean shutdown')
        return closed

    def recover_stale_slice(self) -> bool:
        """Examine the next ``window_rows`` log rows of one item and close the stale open rows among them, each at
        the time of the item's next row (but not after the last flush before this run, when known).

        Rows of earlier runs only: nothing at or after the start of this run is touched. The item list is
        built on the first call; an item stays at the head of it until its history is covered. A window is
        bounded by row count, not time span, so one statement never reads more than that many rows of the
        item. A failed call changes no state, so the next call repeats it.

        :return: True while items remain to be scanned
        """
        plugin = self._plugin
        if not plugin._ensure_db_maint():
            return True
        store = plugin._log_store
        try:
            with plugin._db_maint.transaction() as cur:
                if self._worklist is None:
                    self._worklist = [row[COL_ITEM_ID] for row in plugin._item_store.find_all(cur=cur)]
                if not self._worklist:
                    return False
                item_id = self._worklist[0]
                upto = store.window_end(item_id, self._after, self.window_rows, cur=cur)
                for open_time in store.open_row_times(item_id, self._after, upto, plugin._plugin_start_ts, cur=cur):
                    next_time = store.next_time(item_id, open_time, cur=cur)
                    if next_time is None:
                        continue
                    end = self._closing_time(open_time, next_time, self._last_flush)
                    store.close_open(item_id, open_time, end - open_time, cur=cur)
        except Exception as e:
            self._log_failure(e, 'recovering stale open log rows', plugin._db_maint)
            return True
        if upto is None:
            self._worklist.pop(0)
            self._after = -1
        else:
            self._after = upto
        return bool(self._worklist)

    def recover_stale(self, budget_seconds: float = 2.0) -> bool:
        """Run :meth:`recover_stale_slice` repeatedly until the work is done or *budget_seconds* are spent.

        At least one slice runs per call. The database lock is released between slices.

        :param budget_seconds: time after which no further slice is started
        :return: True while items remain to be scanned
        """
        deadline = time.monotonic() + budget_seconds
        while self.recover_stale_slice():
            if time.monotonic() >= deadline:
                return True
        return False
