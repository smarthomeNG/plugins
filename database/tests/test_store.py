#!/usr/bin/env python3
"""Tests for plugins.database.store — ItemStore and LogStore."""

import contextlib
import unittest
import sqlite3
import time

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from lib.db import NO_CURSOR
from plugins.database.store import ItemStore, LogStore
from plugins.database.constants import BufferEntry, QUALITY_VALID, QUALITY_NO_DATA, QUALITY_INVALID
from plugins.database.utils import to_timestamp


# ──────────────────────────────────────────────────────────────────────────────
# Minimal in-memory SQLite wrapper that satisfies the lib.db.Database interface
# used by ItemStore / LogStore
# ──────────────────────────────────────────────────────────────────────────────


class _MockDB:
    """Thin SQLite in-memory wrapper for store tests (no SmartHomeNG needed)."""

    def __init__(self):
        self._conn = sqlite3.connect(':memory:')
        self._conn.row_factory = sqlite3.Row
        self._setup()

    def _setup(self):
        c = self._conn.cursor()
        c.execute(
            'CREATE TABLE item (id INTEGER PRIMARY KEY AUTOINCREMENT,'
            ' name VARCHAR(255), time BIGINT, val_str TEXT,'
            ' val_num REAL, val_bool BOOLEAN, changed BIGINT)'
        )
        c.execute(
            'CREATE TABLE log (time BIGINT, item_id INTEGER, duration BIGINT,'
            ' val_str TEXT, val_num REAL, val_bool BOOLEAN, changed BIGINT,'
            ' val_quality TINYINT DEFAULT 0)'
        )
        self._conn.commit()
        c.close()

    def execute(self, stmt, params=(), cur=NO_CURSOR):
        c = self._conn.cursor() if cur is NO_CURSOR else cur
        # sqlite3 accepts both sequences (qmark) and dicts (named params)
        c.execute(stmt, params)
        if cur is NO_CURSOR:
            self._conn.commit()
            c.close()

    def fetchone(self, stmt, params=(), cur=NO_CURSOR):
        c = self._conn.cursor() if cur is NO_CURSOR else cur
        c.execute(stmt, params)
        row = c.fetchone()
        if cur is NO_CURSOR:
            c.close()
        return tuple(row) if row else None

    def fetchall(self, stmt, params=(), cur=NO_CURSOR):
        c = self._conn.cursor() if cur is NO_CURSOR else cur
        c.execute(stmt, params)
        rows = c.fetchall()
        if cur is NO_CURSOR:
            c.close()
        return [tuple(r) for r in rows]

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def connected(self):
        return True

    def cursor(self):
        return self._conn.cursor()

    @contextlib.contextmanager
    def transaction(self):
        """Mirrors lib.db.Database.transaction()'s observable contract -
        commit on clean exit, rollback + re-raise on any exception - so
        store.py's transaction()-using write paths stay testable against
        this lightweight mock without needing the full sqlite3-backed
        plugin harness in base.py."""
        cur = self._conn.cursor()
        try:
            yield cur
        except Exception:
            cur.close()
            self._conn.rollback()
            raise
        else:
            cur.close()
            self._conn.commit()


TABLE_NAMES = {
    'item': 'item',
    'log': 'log',
    'item_columns': 'id, name, time, val_str, val_num, val_bool, changed',
    'log_columns': 'time, item_id, duration, val_str, val_num, val_bool, changed',
}


class TestItemStore(unittest.TestCase):
    def setUp(self):
        self.db = _MockDB()
        self.store = ItemStore(self.db, TABLE_NAMES)

    def test_insert_returns_sequential_ids(self):
        id1 = self.store.insert('item.one')
        id2 = self.store.insert('item.two')
        self.assertEqual(id1, 1)
        self.assertEqual(id2, 2)

    def test_insert_uses_lastrowid_not_a_followup_lookup(self):
        # Must mirror plugins.database.__init__.py's insertItem(), which
        # documents fixing exactly this: a follow-up "SELECT id WHERE
        # name=" after the INSERT lets a concurrent caller on the shared
        # connection interleave between the two statements and miss,
        # leaving the item permanently id-less. Using the cursor's own
        # lastrowid right after the INSERT avoids the second statement
        # (and the race) entirely.
        calls = {'execute': 0, 'fetchone': 0}
        orig_execute = self.db.execute
        orig_fetchone = self.db.fetchone

        def spy_execute(*a, **kw):
            calls['execute'] += 1
            return orig_execute(*a, **kw)

        def spy_fetchone(*a, **kw):
            calls['fetchone'] += 1
            return orig_fetchone(*a, **kw)

        self.db.execute = spy_execute
        self.db.fetchone = spy_fetchone

        new_id = self.store.insert('item.one')

        self.assertEqual(1, new_id)
        self.assertEqual(1, calls['execute'], 'expected exactly one INSERT statement')
        self.assertEqual(0, calls['fetchone'], 'insert() must not issue a follow-up lookup query')

    def test_insert_own_cur_path_uses_transaction(self):
        # Regression: insert() used to open a raw cursor via self._db.cursor()
        # directly when called without cur=, bypassing transaction()/lock()
        # entirely despite the class docstring promising otherwise. Confirm
        # it now genuinely goes through transaction() - a spy proves this
        # more robustly than just checking the row exists (which a lost/
        # uncommitted write wouldn't necessarily reveal against :memory:).
        calls = []
        orig_transaction = self.db.transaction

        def spy_transaction(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        self.db.transaction = spy_transaction
        self.store.insert('item.one')
        self.assertEqual(1, len(calls), 'insert() without cur= must go through self._db.transaction()')

    def test_insert_own_cur_path_rolls_back_on_failure(self):
        # A failing statement inside the own-cur transaction() block must
        # not leave a partial row behind.
        with self.assertRaises(Exception):
            with self.db.transaction() as cur:
                cur.execute('INSERT INTO item(name) VALUES (?)', ('probe',))
                raise RuntimeError('simulated failure mid-transaction')
        rows = self.store.find_all()
        self.assertEqual([], rows, 'a rolled-back insert must not be visible afterward')

    def test_find_by_name(self):
        self.store.insert('my.item')
        row = self.store.find('my.item')
        self.assertIsNotNone(row)
        self.assertEqual(row[1], 'my.item')

    def test_find_by_id(self):
        item_id = self.store.insert('my.item')
        row = self.store.find(item_id)
        self.assertIsNotNone(row)
        self.assertEqual(row[0], item_id)

    def test_find_unknown_returns_none(self):
        self.assertIsNone(self.store.find('nobody.there'))
        self.assertIsNone(self.store.find(999))

    def test_update_stores_value(self):
        item_id = self.store.insert('my.item')
        self.store.update(item_id, time=1000, val=42.0, item_type='num', changed=1000)
        row = self.store.find(item_id)
        self.assertAlmostEqual(row[4], 42.0)  # val_num
        self.assertEqual(row[2], 1000)  # time

    def test_update_own_cur_path_uses_transaction(self):
        # cur omitted means "own lock + commit via transaction()" (see the
        # class docstring); update() must follow the same two-branch shape
        # as insert()/delete() - a raw explicit-None execute leaves the UPDATE
        # in an open transaction nothing is guaranteed to ever commit.
        item_id = self.store.insert('my.item')
        calls = []
        orig_transaction = self.db.transaction

        def spy_transaction(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        self.db.transaction = spy_transaction
        self.store.update(item_id, time=1000, val=1.0, item_type='num', changed=1000)
        self.assertEqual(1, len(calls), 'update() without cur= must go through self._db.transaction()')

    def test_count(self):
        self.store.insert('a')
        self.store.insert('b')
        self.assertEqual(self.store.count(), 2)

    def test_delete_removes_item(self):
        item_id = self.store.insert('gone')
        self.store.delete(item_id)
        self.assertIsNone(self.store.find('gone'))

    def test_delete_removes_item_and_its_logs_atomically(self):
        item_id = self.store.insert('gone')
        log_store = LogStore(self.db, TABLE_NAMES)
        log_store.insert(item_id, BufferEntry(time=0, duration=None, value=1.0, quality=QUALITY_VALID), 'num', 0)

        self.store.delete(item_id)

        self.assertIsNone(self.store.find('gone'))
        self.assertEqual(0, log_store.count(item_id), 'delete() must remove the log rows too, not just the item row')

    def test_delete_own_cur_path_uses_transaction(self):
        # Regression: delete() used to call self._db.commit() directly
        # via LogStore.delete_range()'s own default commit=True, even
        # when called without cur= - relying on this ad hoc call instead
        # of the same transaction() primitive insert() already uses.
        item_id = self.store.insert('gone')
        calls = []
        orig_transaction = self.db.transaction

        def spy_transaction(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        self.db.transaction = spy_transaction
        self.store.delete(item_id)
        self.assertEqual(1, len(calls), 'delete() without cur= must go through self._db.transaction() exactly once')

    def test_delete_with_explicit_cur_never_calls_commit_directly(self):
        # Regression: delete()/delete_range() used to call self._db.commit()
        # unconditionally (default commit=True), even when called with an
        # explicit cur from inside the caller's own open transaction() -
        # that would commit the caller's transaction early, before the
        # caller's own block finished. A caller-supplied cur must mean the
        # caller alone decides when to commit.
        item_id = self.store.insert('gone')
        commit_calls = []
        orig_commit = self.db.commit
        self.db.commit = lambda: (commit_calls.append(1), orig_commit())[-1]

        with self.db.transaction() as tcur:
            self.store.delete(item_id, cur=tcur)
            self.assertEqual(0, len(commit_calls), 'delete() with an explicit cur must never call commit() itself')

        # the mock's own transaction() commits via self._conn directly, not
        # via self.db.commit() - so commit_calls staying at 0 here is
        # correct; what matters is the delete is actually persisted once
        # the caller's own block exits.
        self.assertIsNone(self.store.find('gone'))


class TestLogStore(unittest.TestCase):
    def setUp(self):
        self.db = _MockDB()
        self.item_store = ItemStore(self.db, TABLE_NAMES)
        self.log_store = LogStore(self.db, TABLE_NAMES)
        self.item_id = self.item_store.insert('test.item')

    def _entry(self, t, d=None, v=1.0, q=QUALITY_VALID):
        return BufferEntry(time=t, duration=d, value=v, quality=q)

    def _spy_transaction(self):
        calls = []
        orig_transaction = self.db.transaction

        def spy(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        self.db.transaction = spy
        return calls

    def test_insert_own_cur_path_uses_transaction(self):
        # Same cur-omitted contract as ItemStore: own lock + commit via
        # transaction(). A raw explicit-None execute leaves the INSERT pending
        # in an open transaction until some unrelated later call happens
        # to commit the shared connection - or a rollback discards it.
        calls = self._spy_transaction()
        self.log_store.insert(self.item_id, self._entry(1000), 'num', 1000)
        self.assertEqual(1, len(calls), 'insert() without cur= must go through self._db.transaction()')

    def test_update_own_cur_path_uses_transaction(self):
        self.log_store.insert(self.item_id, self._entry(1000), 'num', 1000)
        calls = self._spy_transaction()
        self.log_store.update(self.item_id, self._entry(1000, d=5, v=2.0), 'num', 2000)
        self.assertEqual(1, len(calls), 'update() without cur= must go through self._db.transaction()')

    def test_upsert_own_cur_path_uses_exactly_one_transaction(self):
        # upsert() is a check-then-act (find, then insert or update); with
        # cur omitted, both steps must share one transaction - two separate
        # self-committing calls would reopen the id()-style race the
        # explicit-cur path avoids.
        calls = self._spy_transaction()
        self.log_store.upsert(self.item_id, self._entry(1000), 'num', 1000)
        self.assertEqual(1, len(calls), 'upsert() without cur= must wrap find+write in one transaction()')

    def test_insert_and_find(self):
        e = self._entry(1000, 500, 3.14)
        self.log_store.insert(self.item_id, e, 'num', changed=1500)
        rows = self.log_store.find(self.item_id, 1000)
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0][4], 3.14)  # val_num

    def test_upsert_insert(self):
        e = self._entry(1000, 500, 7.0)
        self.log_store.upsert(self.item_id, e, 'num', changed=1500)
        self.assertEqual(self.log_store.count(self.item_id), 1)

    def test_upsert_update(self):
        e1 = self._entry(1000, None, 7.0)
        e2 = self._entry(1000, 500, 7.0)
        self.log_store.insert(self.item_id, e1, 'num', changed=1000)
        self.log_store.upsert(self.item_id, e2, 'num', changed=1500)
        # must still be one row, with duration filled in
        rows = self.log_store.find(self.item_id, 1000)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][2], 500)  # duration

    def test_count_exclude_gaps(self):
        self.log_store.insert(self.item_id, self._entry(1000, d=10), 'num', 0)
        self.log_store.insert(self.item_id, self._entry(2000, d=10, v=None, q=QUALITY_NO_DATA), 'num', 0)

        self.assertEqual(2, self.log_store.count(self.item_id))
        self.assertEqual(1, self.log_store.count(self.item_id, exclude_gaps=True))

    def test_count_range(self):
        for t in (100, 200, 300, 400):
            self.log_store.insert(self.item_id, self._entry(t, 50, float(t)), 'num', t)
        self.assertEqual(self.log_store.count(self.item_id), 4)
        self.assertEqual(self.log_store.count(self.item_id, time_start=150, time_end=350), 2)

    def test_oldest_and_latest_time(self):
        for t in (300, 100, 200):
            self.log_store.insert(self.item_id, self._entry(t, 50, 1.0), 'num', t)
        self.assertEqual(self.log_store.oldest_time(self.item_id), 100)
        self.assertEqual(self.log_store.latest_time(self.item_id), 300)

    def test_delete_range_all(self):
        for t in (100, 200, 300):
            self.log_store.insert(self.item_id, self._entry(t, 50, 1.0), 'num', t)
        self.log_store.delete_range(self.item_id)
        self.assertEqual(self.log_store.count(self.item_id), 0)

    def test_delete_range_partial(self):
        for t in (100, 200, 300, 400):
            self.log_store.insert(self.item_id, self._entry(t, 50, 1.0), 'num', t)
        self.log_store.delete_range(self.item_id, time_end=250)
        self.assertEqual(self.log_store.count(self.item_id), 2)

    def test_delete_range_own_cur_path_uses_transaction(self):
        self.log_store.insert(self.item_id, self._entry(100, 50, 1.0), 'num', 100)
        calls = []
        orig_transaction = self.db.transaction

        def spy_transaction(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        self.db.transaction = spy_transaction
        self.log_store.delete_range(self.item_id)
        self.assertEqual(
            1, len(calls), 'delete_range() without cur= must go through self._db.transaction() exactly once'
        )

    def test_delete_range_with_explicit_cur_never_calls_commit_directly(self):
        # Regression: delete_range() used to call self._db.commit()
        # unconditionally, bypassing the lock, even with an explicit cur
        # from inside the caller's own open transaction() - see
        # test_delete_with_explicit_cur_never_calls_commit_directly above
        # for the ItemStore twin of this bug.
        self.log_store.insert(self.item_id, self._entry(100, 50, 1.0), 'num', 100)
        commit_calls = []
        orig_commit = self.db.commit
        self.db.commit = lambda: (commit_calls.append(1), orig_commit())[-1]

        with self.db.transaction() as tcur:
            self.log_store.delete_range(self.item_id, cur=tcur)
            self.assertEqual(
                0, len(commit_calls), 'delete_range() with an explicit cur must never call commit() itself'
            )

        # the mock's own transaction() commits via self._conn directly, not
        # via self.db.commit() - so commit_calls staying at 0 here is
        # correct; what matters is the delete is actually persisted once
        # the caller's own block exits.
        self.assertEqual(0, self.log_store.count(self.item_id))

    # Quality tests

    def test_no_data_entry_stores_nulls(self):
        """A QUALITY_NO_DATA entry must have all val_* columns as NULL."""
        gap = self._entry(2000, 500, None, QUALITY_NO_DATA)
        self.log_store.insert(self.item_id, gap, 'num', changed=2500)
        rows = self.log_store.find(self.item_id, 2000)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIsNone(row[3])  # val_str
        self.assertIsNone(row[4])  # val_num
        self.assertIsNone(row[5])  # val_bool

    def test_valid_entry_quality_zero(self):
        e = self._entry(1000, 500, 42.0, QUALITY_VALID)
        self.log_store.insert(self.item_id, e, 'num', changed=1500)
        # Fetch raw row to check val_quality column (index 7)
        rows = self.db.fetchall('SELECT val_quality FROM log WHERE item_id=? AND time=?', (self.item_id, 1000))
        self.assertEqual(rows[0][0], QUALITY_VALID)

    def test_no_data_entry_quality_one(self):
        gap = self._entry(3000, 600, None, QUALITY_NO_DATA)
        self.log_store.insert(self.item_id, gap, 'num', changed=3600)
        rows = self.db.fetchall('SELECT val_quality FROM log WHERE item_id=? AND time=?', (self.item_id, 3000))
        self.assertEqual(rows[0][0], QUALITY_NO_DATA)

    def test_edge_value_skips_gap_rows(self):
        # Regression: edge_value()'s ORDER BY time LIMIT 1 could return an
        # all-NULL gap row - a non-empty tuple of Nones is truthy in
        # Python, so a caller decoding it (e.g. _compact_maxage()) would
        # get value=None back and skip writing an aggregate, while the
        # matching delete_range() call (which does NOT exclude gaps - it's
        # a real row to clean up too) had already removed every row in the
        # interval, including any real ones - silent data loss.
        self.log_store.insert(self.item_id, self._entry(50, 50, 99.0, QUALITY_VALID), 'num', 50)
        self.log_store.insert(self.item_id, self._entry(100, None, None, QUALITY_NO_DATA), 'num', 100)

        first = self.log_store.edge_value(self.item_id, 'ASC')
        last = self.log_store.edge_value(self.item_id, 'DESC')

        self.assertIsNotNone(first, 'must skip the gap row and find the real value')
        self.assertAlmostEqual(first[1], 99.0)  # val_num
        self.assertEqual(last, first, 'the only non-gap row must be both edges')

    def test_edge_value_none_when_only_gap_rows_present(self):
        self.log_store.insert(self.item_id, self._entry(100, None, None, QUALITY_NO_DATA), 'num', 100)
        self.assertIsNone(self.log_store.edge_value(self.item_id, 'ASC'))

    def test_aggregate_excludes_gap_rows(self):
        # Regression: aggregate()'s SUM/AVG/etc used to run over gap rows
        # too - harmless for SUM/AVG (NULL propagates out), but COUNT(*)
        # would count a gap as a real data point, inflating readings.
        self.log_store.insert(self.item_id, self._entry(50, 50, 10.0, QUALITY_VALID), 'num', 50)
        self.log_store.insert(self.item_id, self._entry(150, 50, 20.0, QUALITY_VALID), 'num', 150)
        self.log_store.insert(self.item_id, self._entry(250, None, None, QUALITY_NO_DATA), 'num', 250)

        self.assertEqual(2, self.log_store.aggregate(self.item_id, 'COUNT(*)'))
        self.assertAlmostEqual(30.0, self.log_store.aggregate(self.item_id, 'SUM(val_num)'))

    def test_set_quality_flips_quality_without_touching_value(self):
        """set_quality() must be a reversible flag flip: duration/val_* stay put."""
        e = self._entry(4000, 500, 42.0, QUALITY_VALID)
        self.log_store.insert(self.item_id, e, 'num', changed=4500)

        self.log_store.set_quality(self.item_id, QUALITY_INVALID, time=4000, changed=4500)

        rows = self.db.fetchall(
            'SELECT val_quality, val_num, duration FROM log WHERE item_id=? AND time=?', (self.item_id, 4000)
        )
        self.assertEqual(rows[0][0], QUALITY_INVALID)
        self.assertAlmostEqual(rows[0][1], 42.0)  # val_num preserved
        self.assertEqual(rows[0][2], 500)  # duration preserved

    def test_set_quality_is_reversible(self):
        e = self._entry(5000, 500, 7.5, QUALITY_VALID)
        self.log_store.insert(self.item_id, e, 'num', changed=5500)

        self.log_store.set_quality(self.item_id, QUALITY_INVALID, time=5000, changed=5500)
        self.log_store.set_quality(self.item_id, QUALITY_VALID, time=5000, changed=5500)

        rows = self.db.fetchall('SELECT val_quality, val_num FROM log WHERE item_id=? AND time=?', (self.item_id, 5000))
        self.assertEqual(rows[0][0], QUALITY_VALID)
        self.assertAlmostEqual(rows[0][1], 7.5)

    def test_set_quality_only_matches_given_criteria(self):
        """Same time+changed matching as delete_range - other rows untouched."""
        for t in (100, 200, 300):
            self.log_store.insert(self.item_id, self._entry(t, 50, float(t), QUALITY_VALID), 'num', changed=t)

        self.log_store.set_quality(self.item_id, QUALITY_INVALID, time=200, changed=200)

        rows = self.db.fetchall('SELECT time, val_quality FROM log WHERE item_id=? ORDER BY time', (self.item_id,))
        self.assertEqual(
            [(r[0], r[1]) for r in rows], [(100, QUALITY_VALID), (200, QUALITY_INVALID), (300, QUALITY_VALID)]
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
