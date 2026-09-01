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

from lib.db import NO_CURSOR
from .constants import BufferEntry, QUALITY_VALID
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

    def _execute(self, query, params, cur=NO_CURSOR):
        self._db.execute(self._sql(query), params, cur=cur)

    def _fetchone(self, query, params=None, cur=NO_CURSOR):
        return self._db.fetchone(self._sql(query), params or {}, cur=cur)

    def _fetchall(self, query, params=None, cur=NO_CURSOR):
        result = self._db.fetchall(self._sql(query), params or {}, cur=cur)
        return [] if result is None else list(result)

    # ── write ────────────────────────────────────────────────────────────────

    def insert(self, name: str, cur=NO_CURSOR) -> int:
        """Insert a new item row and return its database ID.

        Uses ``INTEGER PRIMARY KEY`` autoincrement behaviour: the INSERT
        omits ``id`` and lets the database assign it.  The cursor's own
        ``lastrowid`` is read right after the INSERT rather than a
        follow-up ``SELECT id WHERE name=`` - the database connection can
        be shared across threads, and a concurrent caller could interleave
        between the two statements and cause the lookup to miss, leaving
        the item permanently id-less. ``lastrowid`` is scoped to this
        cursor and immune to that race.

        :param name: Full item path (e.g. ``'solar.power'``).
        :param cur:  Optional cursor for transaction batching.
        :returns:    The new integer item ID.
        :rtype:      int
        """
        if cur is not NO_CURSOR:
            self._execute('INSERT INTO {item}(name) VALUES(:name);', {'name': name}, cur=cur)
            return int(cur.lastrowid)
        # No cur passed: acquires its own lock and commits via
        # transaction() - the class docstring above promises exactly this
        # ("otherwise the store acquires its own lock"), so this path
        # must actually do it, not just read from the table.
        with self._db.transaction() as tcur:
            self._execute('INSERT INTO {item}(name) VALUES(:name);', {'name': name}, cur=tcur)
            return int(tcur.lastrowid)

    def update(self, item_id: int, time: int, val, item_type: str, changed: int, cur=NO_CURSOR) -> None:
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
        stmt = (
            'UPDATE {item} SET time=:time, val_str=:val_str, val_num=:val_num,'
            ' val_bool=:val_bool, changed=:changed WHERE id=:id;'
        )
        if cur is not NO_CURSOR:
            self._execute(stmt, params, cur=cur)
            return
        with self._db.transaction() as tcur:
            self._execute(stmt, params, cur=tcur)

    def delete(self, item_id: int, cur=NO_CURSOR) -> None:
        """Delete the item row *and* all its log rows, as one atomic unit.

        With ``cur`` omitted this acquires its own lock and commits both
        deletes via ``self._db.transaction()`` - a crash between them
        can never leave one done and the other not.

        :param item_id: Database item ID.
        :param cur:     Optional cursor for transaction batching.
        """
        log_store = LogStore(self._db, self._tn, self.logger)
        if cur is not NO_CURSOR:
            log_store.delete_range(item_id, cur=cur)
            self._execute('DELETE FROM {item} WHERE id=:id;', {'id': item_id}, cur=cur)
            return
        with self._db.transaction() as tcur:
            log_store.delete_range(item_id, cur=tcur)
            self._execute('DELETE FROM {item} WHERE id=:id;', {'id': item_id}, cur=tcur)

    # ── read ─────────────────────────────────────────────────────────────────

    def find(self, id_or_name, cur=NO_CURSOR):
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

    def find_all(self, cur=NO_CURSOR) -> list:
        """Return all item rows.

        :param cur: Optional cursor.
        :rtype:     list
        """
        return self._fetchall('SELECT {item_columns} FROM {item};', cur=cur)

    def count(self, cur=NO_CURSOR) -> int:
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

    def _execute(self, query, params, cur=NO_CURSOR):
        self._db.execute(self._sql(query), params, cur=cur)

    def _fetchone(self, query, params=None, cur=NO_CURSOR):
        return self._db.fetchone(self._sql(query), params or {}, cur=cur)

    def _fetchall(self, query, params=None, cur=NO_CURSOR):
        result = self._db.fetchall(self._sql(query), params or {}, cur=cur)
        return [] if result is None else list(result)

    # ── write ────────────────────────────────────────────────────────────────

    def insert(self, item_id: int, entry: BufferEntry, item_type: str, changed: int, cur=NO_CURSOR) -> None:
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
        stmt = (
            'INSERT INTO {log}(item_id, time, val_str, val_num, val_bool,'
            ' duration, changed, val_quality)'
            ' VALUES(:id, :time, :val_str, :val_num, :val_bool,'
            '        :duration, :changed, :quality);'
        )
        if cur is not NO_CURSOR:
            self._execute(stmt, params, cur=cur)
            return
        with self._db.transaction() as tcur:
            self._execute(stmt, params, cur=tcur)

    def update(self, item_id: int, entry: BufferEntry, item_type: str, changed: int, cur=NO_CURSOR) -> None:
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
        stmt = (
            'UPDATE {log} SET duration=:duration, val_str=:val_str,'
            ' val_num=:val_num, val_bool=:val_bool, changed=:changed,'
            ' val_quality=:quality'
            ' WHERE item_id=:id AND time=:time;'
        )
        if cur is not NO_CURSOR:
            self._execute(stmt, params, cur=cur)
            return
        with self._db.transaction() as tcur:
            self._execute(stmt, params, cur=tcur)

    def upsert(self, item_id: int, entry: BufferEntry, item_type: str, changed: int, cur=NO_CURSOR) -> None:
        """Insert *or* update a log row depending on whether it already exists.

        Replaces the ``if len(readLog(...)): updateLog else insertLog``
        pattern in ``_dump()``.

        :param item_id:   Database item ID.
        :param entry:     Buffer entry.
        :param item_type: SmartHomeNG item type.
        :param changed:   Write timestamp (milliseconds).
        :param cur:       Optional cursor.
        """
        if cur is not NO_CURSOR:
            existing = self.find(item_id, entry.time, cur=cur)
            if existing:
                self.update(item_id, entry, item_type, changed, cur=cur)
            else:
                self.insert(item_id, entry, item_type, changed, cur=cur)
            return
        # check-then-act: find and the write must share one transaction,
        # not run as two independently-committing calls.
        with self._db.transaction() as tcur:
            existing = self.find(item_id, entry.time, cur=tcur)
            if existing:
                self.update(item_id, entry, item_type, changed, cur=tcur)
            else:
                self.insert(item_id, entry, item_type, changed, cur=tcur)

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
        cur=NO_CURSOR,
    ) -> None:
        """Delete log rows matching the given criteria.

        All criteria are optional; if none are given, *all* rows for
        *item_id* are deleted.

        No ``commit`` parameter: with ``cur`` omitted this acquires its own
        lock and commits via ``self._db.transaction()`` (matching
        :meth:`ItemStore.insert`) - with an explicit ``cur``, the caller
        already holds the lock and owns the commit/rollback decision, so
        this never touches it. A caller-controlled independent commit flag
        used to let a passed-in ``cur`` be committed unilaterally mid- the
        caller's own transaction, or a call with ``cur`` omitted be left
        uncommitted with nothing else guaranteed to flush it.

        :param item_id:       Database item ID.
        :param time:          Exact timestamp to match (optional).
        :param time_start:    Lower bound on ``time`` (exclusive, optional).
        :param time_end:      Upper bound on ``time`` (exclusive, optional).
        :param changed:       Exact ``changed`` match (optional).
        :param changed_start: Lower bound on ``changed`` (optional).
        :param changed_end:   Upper bound on ``changed`` (optional).
        :param cur:           Optional cursor for transaction batching.
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
        stmt = 'DELETE FROM {log} WHERE ' + where + ';'
        if cur is not NO_CURSOR:
            self._execute(stmt, params, cur=cur)
            return
        with self._db.transaction() as tcur:
            self._execute(stmt, params, cur=tcur)

    def set_quality(
        self,
        item_id: int,
        quality: int,
        *,
        time=None,
        time_start=None,
        time_end=None,
        changed=None,
        changed_start=None,
        changed_end=None,
        cur=NO_CURSOR,
        commit=True,
    ) -> None:
        """Set ``val_quality`` on matching log rows without touching their values.

        Used for reversible invalidate/restore (e.g. the webif's "delete"
        action), as opposed to :meth:`delete_range` which permanently
        removes rows. ``duration``/``val_str``/``val_num``/``val_bool`` are
        left untouched.

        :param item_id:       Database item ID.
        :param quality:       New ``val_quality`` value.
        :param time:          Exact timestamp to match (optional).
        :param time_start:    Lower bound on ``time`` (exclusive, optional).
        :param time_end:      Upper bound on ``time`` (exclusive, optional).
        :param changed:       Exact ``changed`` match (optional).
        :param changed_start: Lower bound on ``changed`` (optional).
        :param changed_end:   Upper bound on ``changed`` (optional).
        :param cur:           Optional cursor.
        :param commit:        If ``True`` (default) commit after the update.
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
        params['quality'] = quality
        try:
            self._execute('UPDATE {log} SET val_quality=:quality WHERE ' + where + ';', params, cur=cur)
            if commit:
                self._db.commit()
        except Exception as e:
            self.logger.error('LogStore.set_quality: {}'.format(e))
            self._db.rollback()

    # ── read ─────────────────────────────────────────────────────────────────

    def find(self, item_id: int, time: int, cur=NO_CURSOR) -> list:
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
        cur=NO_CURSOR,
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

    def count(self, item_id: int, *, time_start=None, time_end=None, exclude_gaps=False, cur=NO_CURSOR) -> int:
        """Return the number of log rows for *item_id* in the given range.

        :param item_id:    Database item ID.
        :param time_start: Lower bound on ``time`` (exclusive, optional).
        :param time_end:   Upper bound on ``time`` (exclusive, optional).
        :param exclude_gaps: If True, count only valid-quality rows (see
                           build_where_clause).
        :param cur:        Optional cursor.
        :rtype:            int
        """
        where, params = build_where_clause(item_id, time_start=time_start, time_end=time_end, exclude_gaps=exclude_gaps)
        result = self._fetchall('SELECT count(*) FROM {log} WHERE ' + where + ';', params, cur=cur)
        if not result:
            return 0
        try:
            return result[0][0] or 0
        except (IndexError, TypeError) as e:
            self.logger.error('LogStore.count: result={} - {}'.format(result, e))
            return 0

    def count_all(self, cur=NO_CURSOR) -> int:
        """Return the total number of log rows across all items.

        :param cur: Optional cursor.
        :rtype:     int
        """
        result = self._fetchall('SELECT count(*) FROM {log};', cur=cur)
        return result[0][0] if result else 0

    def oldest_time(self, item_id: int, cur=NO_CURSOR) -> 'int | None':
        """Return the earliest ``time`` value for *item_id*, or ``None``.

        :param item_id: Database item ID.
        :param cur:     Optional cursor.
        :rtype:         int | None
        """
        rows = self._fetchall('SELECT min(time) FROM {log} WHERE item_id=:id;', {'id': item_id}, cur=cur)
        return rows[0][0] if rows else None

    def latest_time(self, item_id: int, before: 'int | None' = None, cur=NO_CURSOR) -> 'int | None':
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

    def find_open(self, item_id: int, cur=NO_CURSOR) -> 'int | None':
        """Return the ``time`` of the still-open (``duration IS NULL``,
        valid-quality) row for *item_id*, or ``None`` if there is none.

        At most one such row can exist per item by construction - it is
        the currently active value, not yet closed by a later change. A
        no-data gap row (``val_quality != 0``) is also duration-NULL but
        is not "open" in this sense, so it is excluded.

        :param item_id: Database item ID.
        :param cur:     Optional cursor.
        :rtype:         int | None
        """
        rows = self._fetchall(
            'SELECT time FROM {log} WHERE item_id=:id AND duration IS NULL AND val_quality=:quality;',
            {'id': item_id, 'quality': QUALITY_VALID},
            cur=cur,
        )
        return rows[0][0] if rows else None

    def reanchor_open(self, item_id: int, old_time: int, new_time: int, cur=NO_CURSOR) -> None:
        """Move the still-open row's ``time`` forward to *new_time*.

        Used by maxage compaction to carry a long-open row past an
        interval it has just been partially aggregated into, without
        deleting it - the row keeps its value/quality, only its "open
        since" marker advances. Guarded by ``duration IS NULL`` so this
        can never touch a closed row even under a stale *old_time*.

        :param item_id:  Database item ID.
        :param old_time: The row's current ``time``.
        :param new_time: The ``time`` to move it to.
        :param cur:      Optional cursor.
        """
        stmt = 'UPDATE {log} SET time=:new_time WHERE item_id=:id AND time=:old_time AND duration IS NULL;'
        params = {'id': item_id, 'old_time': old_time, 'new_time': new_time}
        if cur is not NO_CURSOR:
            self._execute(stmt, params, cur=cur)
            return
        with self._db.transaction() as tcur:
            self._execute(stmt, params, cur=tcur)

    def edge_value(self, item_id: int, order: str, *, time_start=None, time_end=None, cur=NO_CURSOR):
        """Return the raw ``(val_str, val_num, val_bool)`` tuple of the
        first or last row (by ``time``) for *item_id* in the given range.

        Unlike :meth:`aggregate`, this reads the actual stored value rather
        than computing a scalar over ``val_num``/``val_bool`` - the only way
        to get a meaningful compacted value for ``str``-typed items (and the
        correct choice for ``num``/``bool`` items too, when the desired
        value is literally "the value at the start/end of the interval"
        rather than a statistic over it).

        :param item_id: Database item ID.
        :param order:   ``'ASC'`` for the first (oldest) row, ``'DESC'`` for
                        the last (newest) row in the range.
        :param time_start: Exclusive lower bound on ``time`` (optional).
        :param time_end:   Exclusive upper bound on ``time`` (optional).
        :param cur:        Optional cursor.
        :returns:          ``(val_str, val_num, val_bool)`` tuple, or ``None``
                           if the range is empty (or contains only no-data
                           gap rows - see build_where_clause's exclude_gaps).
        """
        where, params = build_where_clause(item_id, time_start=time_start, time_end=time_end, exclude_gaps=True)
        result = self._fetchall(
            'SELECT val_str, val_num, val_bool FROM {log} WHERE ' + where + f' ORDER BY time {order} LIMIT 1;',
            params,
            cur=cur,
        )
        return result[0] if result else None

    def aggregate(self, item_id: int, expr: str, *, time_start=None, time_end=None, cur=NO_CURSOR):
        """Return one aggregate value for *item_id* in the given range.

        *expr* must be a caller-controlled SQL aggregate expression (e.g.
        ``'SUM(val_num)'``) - it is interpolated directly into the query, so
        it must never come from user/item-config input, only from a fixed,
        code-defined set of fragments.

        :param item_id:    Database item ID.
        :param expr:       SQL aggregate expression over ``val_num``/``val_bool``/``duration``.
        :param time_start: Exclusive lower bound on ``time`` (optional).
        :param time_end:   Exclusive upper bound on ``time`` (optional).
        :param cur:        Optional cursor.
        :returns:          The aggregate result, or ``None`` if the range is empty
                           (or the aggregate itself evaluates to NULL).
        """
        where, params = build_where_clause(item_id, time_start=time_start, time_end=time_end, exclude_gaps=True)
        result = self._fetchall(f'SELECT {expr} FROM {{log}} WHERE ' + where + ';', params, cur=cur)
        if not result:
            return None
        return result[0][0]
