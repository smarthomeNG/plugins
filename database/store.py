#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-     Oliver Hinckel                  github@ollisnet.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  database plugin — SQL CRUD layer
#########################################################################

"""
SQL CRUD layer for the database plugin.

:class:`ItemStore` manages the ``{prefix}item`` table (one row per tracked
item, holding the latest value).

:class:`LogStore` manages the ``{prefix}log`` table (historical time-series,
one row per value-duration pair).

Both classes accept a ``lib.db.Database`` connection and a ``table_names``
dict (``{'log': '...', 'item': '...', ...}``) as constructor arguments and
are otherwise fully independent of the plugin lifecycle.
"""

import logging
from typing import List, Optional

from .constants import (
    BufferEntry,
    COL_ITEM,
    COL_ITEM_ID,
    COL_ITEM_NAME,
    COL_LOG,
    COL_LOG_TIME,
    COL_LOG_ITEM_ID,
    QUALITY_VALID,
)
from .utils import encode_value, apply_table_names, build_where_clause


class ItemStore:
    """CRUD operations for the ``{prefix}item`` table.

    The item table holds one row per tracked item, storing its most
    recently written value.  It is used to initialise items on startup
    (``database: init``) and by the web interface.

    :param db:          A :class:`lib.db.Database` connection (with lock
                        already acquired by the caller when ``cur`` is
                        passed; otherwise the store acquires its own lock).
    :param table_names: Dict mapping ``'item'``, ``'log'``,
                        ``'item_columns'``, ``'log_columns'`` to their
                        fully-qualified names.
    :param logger:      Logger instance.
    """

    def __init__(self, db, table_names: dict, logger=None) -> None:
        self._db = db
        self._tn = table_names
        self.logger = logger or logging.getLogger(__name__)

    def _sql(self, query: str) -> str:
        return apply_table_names(query, self._tn)

    def _execute(self, query, params, cur=None):
        self._db.execute(self._sql(query), params, cur=cur)

    def _fetchone(self, query, params=None, cur=None):
        return self._db.fetchone(self._sql(query), params or {}, cur=cur)

    def _fetchall(self, query, params=None, cur=None):
        result = self._db.fetchall(self._sql(query), params or {}, cur=cur)
        return [] if result is None else list(result)

    # ── write ────────────────────────────────────────────────────────────────

    def insert(self, name: str, cur=None) -> int:
        """Insert a new item row and return its database ID.

        Uses ``INTEGER PRIMARY KEY`` autoincrement behaviour: the INSERT
        omits ``id`` and lets the database assign it.  A subsequent SELECT
        retrieves the assigned id.  This avoids the previous
        ``MAX(id) + 1`` race condition.

        :param name: Full item path (e.g. ``'solar.power'``).
        :param cur:  Optional cursor for transaction batching.
        :returns:    The new integer item ID.
        :rtype:      int
        """
        self._execute('INSERT INTO {item}(name) VALUES(:name);', {'name': name}, cur=cur)
        row = self._fetchone('SELECT id FROM {item} WHERE name = :name;', {'name': name}, cur=cur)
        return int(row[0])

    def update(self, item_id: int, time: int, val, item_type: str, changed: int, cur=None) -> None:
        """Update the latest-value row for *item_id*.

        :param item_id:   Database item ID.
        :param time:      Timestamp of the value (milliseconds).
        :param val:       The new value.
        :param item_type: SmartHomeNG item type (``'num'``, ``'bool'``, etc.).
        :param changed:   Current time (milliseconds) — when the row was written.
        :param cur:       Optional cursor.
        """
        params = {'id': item_id, 'time': time, 'changed': changed}
        params.update(encode_value(item_type, val))
        self._execute(
            'UPDATE {item} SET time=:time, val_str=:val_str, val_num=:val_num,'
            ' val_bool=:val_bool, changed=:changed WHERE id=:id;',
            params,
            cur=cur,
        )

    def delete(self, item_id: int, cur=None) -> None:
        """Delete the item row *and* all its log rows.

        :param item_id: Database item ID.
        :param cur:     Optional cursor.
        """
        LogStore(self._db, self._tn, self.logger).delete_range(item_id, cur=cur)
        self._execute('DELETE FROM {item} WHERE id=:id;', {'id': item_id}, cur=cur)

    # ── read ─────────────────────────────────────────────────────────────────

    def find(self, id_or_name, cur=None):
        """Return the item row for *id_or_name*, or ``None``.

        Accepts either an integer database ID or a string item path.

        :param id_or_name: Integer ID or string path.
        :param cur:        Optional cursor.
        :returns:          Row tuple or ``None``.
        """
        params = {'id': id_or_name}
        if isinstance(id_or_name, str):
            return self._fetchone('SELECT {item_columns} FROM {item} WHERE name=:id;', params, cur=cur)
        return self._fetchone('SELECT {item_columns} FROM {item} WHERE id=:id;', params, cur=cur)

    def find_all(self, cur=None) -> list:
        """Return all item rows.

        :param cur: Optional cursor.
        :rtype:     list
        """
        return self._fetchall('SELECT {item_columns} FROM {item};', cur=cur)

    def count(self, cur=None) -> int:
        """Return the total number of item rows.

        :param cur: Optional cursor.
        :rtype:     int
        """
        if not self._db.connected():
            return 0
        result = self._fetchall('SELECT count(*) FROM {item};', cur=cur)
        return result[0][0] if result else 0


class LogStore:
    """CRUD operations for the ``{prefix}log`` table.

    The log table is the historical time-series store.  Each row records:

    - the timestamp when a value became active (``time``),
    - how long it was active (``duration``, or NULL if still active),
    - the value itself (one of ``val_str``, ``val_num``, ``val_bool``),
    - a data-quality flag (``val_quality``, schema version 7+).

    :param db:          A :class:`lib.db.Database` connection.
    :param table_names: Table-name mapping dict.
    :param logger:      Logger instance.
    """

    def __init__(self, db, table_names: dict, logger=None) -> None:
        self._db = db
        self._tn = table_names
        self.logger = logger or logging.getLogger(__name__)

    def _sql(self, query: str) -> str:
        return apply_table_names(query, self._tn)

    def _execute(self, query, params, cur=None):
        self._db.execute(self._sql(query), params, cur=cur)

    def _fetchone(self, query, params=None, cur=None):
        return self._db.fetchone(self._sql(query), params or {}, cur=cur)

    def _fetchall(self, query, params=None, cur=None):
        result = self._db.fetchall(self._sql(query), params or {}, cur=cur)
        return [] if result is None else list(result)

    # ── write ────────────────────────────────────────────────────────────────

    def insert(self, item_id: int, entry: BufferEntry, item_type: str, changed: int, cur=None) -> None:
        """Insert a new log row from a :class:`~constants.BufferEntry`.

        For entries with ``quality=QUALITY_NO_DATA`` all value columns are
        stored as ``NULL``; ``val_quality`` is set to ``1`` so analytics
        queries can exclude these rows.

        :param item_id:   Database item ID.
        :param entry:     Buffer entry to persist.
        :param item_type: SmartHomeNG item type string.
        :param changed:   Write timestamp (milliseconds).
        :param cur:       Optional cursor.
        """
        params = {
            'id': item_id,
            'time': entry.time,
            'duration': entry.duration,
            'changed': changed,
            'quality': entry.quality,
        }
        params.update(encode_value(item_type, entry.value))
        self._execute(
            'INSERT INTO {log}(item_id, time, val_str, val_num, val_bool,'
            ' duration, changed, val_quality)'
            ' VALUES(:id, :time, :val_str, :val_num, :val_bool,'
            '        :duration, :changed, :quality);',
            params,
            cur=cur,
        )

    def update(self, item_id: int, entry: BufferEntry, item_type: str, changed: int, cur=None) -> None:
        """Update an existing log row matching ``(item_id, time)``.

        :param item_id:   Database item ID.
        :param entry:     Buffer entry containing the new duration / value.
        :param item_type: SmartHomeNG item type string.
        :param changed:   Write timestamp (milliseconds).
        :param cur:       Optional cursor.
        """
        params = {
            'id': item_id,
            'time': entry.time,
            'duration': entry.duration,
            'changed': changed,
            'quality': entry.quality,
        }
        params.update(encode_value(item_type, entry.value))
        self._execute(
            'UPDATE {log} SET duration=:duration, val_str=:val_str,'
            ' val_num=:val_num, val_bool=:val_bool, changed=:changed,'
            ' val_quality=:quality'
            ' WHERE item_id=:id AND time=:time;',
            params,
            cur=cur,
        )

    def upsert(self, item_id: int, entry: BufferEntry, item_type: str, changed: int, cur=None) -> None:
        """Insert *or* update a log row depending on whether it already exists.

        Replaces the ``if len(readLog(...)): updateLog else insertLog``
        pattern in ``_dump()``.

        :param item_id:   Database item ID.
        :param entry:     Buffer entry.
        :param item_type: SmartHomeNG item type.
        :param changed:   Write timestamp (milliseconds).
        :param cur:       Optional cursor.
        """
        existing = self.find(item_id, entry.time, cur=cur)
        if existing:
            self.update(item_id, entry, item_type, changed, cur=cur)
        else:
            self.insert(item_id, entry, item_type, changed, cur=cur)

    def delete_range(
        self,
        item_id: int,
        *,
        time=None,
        time_start=None,
        time_end=None,
        changed=None,
        changed_start=None,
        changed_end=None,
        cur=None,
        commit=True,
    ) -> None:
        """Delete log rows matching the given criteria.

        All criteria are optional; if none are given, *all* rows for
        *item_id* are deleted.

        :param item_id:       Database item ID.
        :param time:          Exact timestamp to match (optional).
        :param time_start:    Lower bound on ``time`` (exclusive, optional).
        :param time_end:      Upper bound on ``time`` (exclusive, optional).
        :param changed:       Exact ``changed`` match (optional).
        :param changed_start: Lower bound on ``changed`` (optional).
        :param changed_end:   Upper bound on ``changed`` (optional).
        :param cur:           Optional cursor.
        :param commit:        If ``True`` (default) commit after deletion.
        """
        where, params = build_where_clause(
            item_id,
            time=time,
            time_start=time_start,
            time_end=time_end,
            changed=changed,
            changed_start=changed_start,
            changed_end=changed_end,
        )
        try:
            self._execute('DELETE FROM {log} WHERE ' + where + ';', params, cur=cur)
            if commit:
                self._db.commit()
        except Exception as e:
            self.logger.error('LogStore.delete_range: {}'.format(e))
            self._db.rollback()

    # ── read ─────────────────────────────────────────────────────────────────

    def find(self, item_id: int, time: int, cur=None) -> list:
        """Return all log rows for *item_id* at exact timestamp *time*.

        :param item_id: Database item ID.
        :param time:    Exact timestamp (milliseconds).
        :param cur:     Optional cursor.
        :rtype:         list
        """
        return self._fetchall(
            'SELECT {log_columns} FROM {log} WHERE item_id=:id AND time=:time;', {'id': item_id, 'time': time}, cur=cur
        )

    def find_range(
        self,
        item_id: int,
        *,
        time=None,
        time_start=None,
        time_end=None,
        changed=None,
        changed_start=None,
        changed_end=None,
        cur=None,
    ) -> list:
        """Return log rows matching the given criteria.

        :param item_id:       Database item ID.
        :param time:          Exact timestamp (optional).
        :param time_start:    Lower bound on ``time`` (exclusive, optional).
        :param time_end:      Upper bound on ``time`` (exclusive, optional).
        :param changed:       Exact ``changed`` match (optional).
        :param changed_start: Lower bound on ``changed`` (optional).
        :param changed_end:   Upper bound on ``changed`` (optional).
        :param cur:           Optional cursor.
        :rtype:               list
        """
        where, params = build_where_clause(
            item_id,
            time=time,
            time_start=time_start,
            time_end=time_end,
            changed=changed,
            changed_start=changed_start,
            changed_end=changed_end,
        )
        return self._fetchall('SELECT {log_columns} FROM {log} WHERE ' + where + ';', params, cur=cur)

    def count(self, item_id: int, *, time_start=None, time_end=None, cur=None) -> int:
        """Return the number of log rows for *item_id* in the given range.

        :param item_id:    Database item ID.
        :param time_start: Lower bound on ``time`` (exclusive, optional).
        :param time_end:   Upper bound on ``time`` (exclusive, optional).
        :param cur:        Optional cursor.
        :rtype:            int
        """
        where, params = build_where_clause(item_id, time_start=time_start, time_end=time_end)
        result = self._fetchall('SELECT count(*) FROM {log} WHERE ' + where + ';', params, cur=cur)
        if not result:
            return 0
        try:
            return result[0][0] or 0
        except (IndexError, TypeError) as e:
            self.logger.error('LogStore.count: result={} - {}'.format(result, e))
            return 0

    def count_all(self, cur=None) -> int:
        """Return the total number of log rows across all items.

        :param cur: Optional cursor.
        :rtype:     int
        """
        result = self._fetchall('SELECT count(*) FROM {log};', cur=cur)
        return result[0][0] if result else 0

    def oldest_time(self, item_id: int, cur=None) -> 'int | None':
        """Return the earliest ``time`` value for *item_id*, or ``None``.

        :param item_id: Database item ID.
        :param cur:     Optional cursor.
        :rtype:         int | None
        """
        rows = self._fetchall('SELECT min(time) FROM {log} WHERE item_id=:id;', {'id': item_id}, cur=cur)
        return rows[0][0] if rows else None

    def latest_time(self, item_id: int, before: 'int | None' = None, cur=None) -> 'int | None':
        """Return the most recent ``time`` value for *item_id*, or ``None``.

        :param item_id: Database item ID.
        :param before:  If given, only consider rows with ``time <= before``.
        :param cur:     Optional cursor.
        :rtype:         int | None
        """
        if before is None:
            rows = self._fetchall('SELECT max(time) FROM {log} WHERE item_id=:id;', {'id': item_id}, cur=cur)
        else:
            rows = self._fetchall(
                'SELECT max(time) FROM {log} WHERE item_id=:id AND time<=:before;',
                {'id': item_id, 'before': before},
                cur=cur,
            )
        return rows[0][0] if rows else None
