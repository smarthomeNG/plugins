#!/usr/bin/env python3
"""Tests for the val_quality / missing-value feature.

- TestQualityBufferLevel / TestQualityStoreLevel: isolated unit tests of
  buffer.BufferManager / store.LogStore, the modules the live plugin's
  quality tracking is built on.
- TestQualityEndToEnd: exercises the real plugin (Database.update_item(),
  db_mark_invalid()/db_mark_valid(), _dump()) via TestDatabaseBase's
  in-memory-SQLite harness and asserts on actual database rows - not a
  reimplementation of the logic under test.
"""

import unittest
from unittest import mock

from lib.db import NO_CURSOR
from plugins.database.buffer import BufferManager
from plugins.database.constants import BufferEntry, QUALITY_NO_DATA, QUALITY_VALID
from plugins.database.store import ItemStore, LogStore
from plugins.database.tests.base import TestDatabaseBase


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests that only need the buffer + store layer (no SmartHomeNG mock)
# ──────────────────────────────────────────────────────────────────────────────


class TestQualityBufferLevel(unittest.TestCase):
    """Verify gap lifecycle purely at the buffer level."""

    def _item(self):
        class _I:
            pass

        return _I()

    def test_open_gap_creates_no_data_entry(self):
        mgr = BufferManager()
        item = self._item()
        mgr.register(item)
        mgr.push(item, BufferEntry(time=1000, duration=None, value=250.0))
        mgr.push_invalid(item, start_ts=1500)
        entries = mgr.pop_all(item)
        self.assertEqual(len(entries), 2)
        # first entry closed
        self.assertEqual(entries[0].duration, 500)
        self.assertEqual(entries[0].quality, QUALITY_VALID)
        # gap entry
        self.assertEqual(entries[1].quality, QUALITY_NO_DATA)
        self.assertIsNone(entries[1].value)
        self.assertIsNone(entries[1].duration)

    def test_close_gap_sets_duration(self):
        mgr = BufferManager()
        item = self._item()
        mgr.register(item)
        mgr.push_invalid(item, start_ts=2000)
        mgr.close_open(item, end_ts=3000)
        last = mgr.last_entry(item)
        self.assertEqual(last.quality, QUALITY_NO_DATA)
        self.assertEqual(last.duration, 1000)

    def test_valid_entry_default_quality(self):
        mgr = BufferManager()
        item = self._item()
        mgr.register(item)
        mgr.push(item, BufferEntry(time=100, duration=None, value=42.0))
        last = mgr.last_entry(item)
        self.assertEqual(last.quality, QUALITY_VALID)


class TestQualityStoreLevel(unittest.TestCase):
    """Verify gap storage at the LogStore level."""

    def setUp(self):
        import sqlite3

        class _DB:
            # Matches lib.db.Database's real class attribute - ItemStore.insert()
            # reads this to decide between lastrowid and INSERT...RETURNING.
            _psycopg_driver_names = frozenset({'psycopg2', 'psycopg'})

            def __init__(self):
                import types

                self._dbapi = types.SimpleNamespace(__name__='sqlite3')
                self._conn = sqlite3.connect(':memory:')
                c = self._conn.cursor()
                c.execute(
                    'CREATE TABLE item (id INTEGER PRIMARY KEY AUTOINCREMENT,'
                    ' name VARCHAR(255), time BIGINT, val_str TEXT,'
                    ' val_num REAL, val_bool BOOLEAN, changed BIGINT)'
                )
                c.execute(
                    'CREATE TABLE log (time BIGINT, item_id INTEGER,'
                    ' duration BIGINT, val_str TEXT, val_num REAL,'
                    ' val_bool BOOLEAN, changed BIGINT, val_quality TINYINT DEFAULT 0)'
                )
                self._conn.commit()

            def execute(self, s, p=(), cur=NO_CURSOR):
                c = self._conn.cursor() if cur is NO_CURSOR else cur
                c.execute(s, p)
                if cur is NO_CURSOR:
                    self._conn.commit()
                    c.close()
                return c

            def fetchone(self, s, p=(), cur=NO_CURSOR):
                c = self._conn.cursor() if cur is NO_CURSOR else cur
                c.execute(s, p)
                r = c.fetchone()
                if cur is NO_CURSOR:
                    c.close()
                return tuple(r) if r else None

            def fetchall(self, s, p=(), cur=NO_CURSOR):
                c = self._conn.cursor() if cur is NO_CURSOR else cur
                c.execute(s, p)
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

            def transaction(self):
                """Mirrors lib.db.Database.transaction()'s observable
                contract - commit on clean exit, rollback + re-raise on
                any exception."""
                import contextlib

                @contextlib.contextmanager
                def _tx():
                    c = self._conn.cursor()
                    try:
                        yield c
                    except Exception:
                        c.close()
                        self._conn.rollback()
                        raise
                    else:
                        c.close()
                        self._conn.commit()

                return _tx()

        tn = {
            'item': 'item',
            'log': 'log',
            'item_columns': 'id, name, time, val_str, val_num, val_bool, changed',
            'log_columns': 'time, item_id, duration, val_str, val_num, val_bool, changed',
        }
        self.db = _DB()
        self.item_store = ItemStore(self.db, tn)
        self.log_store = LogStore(self.db, tn)
        self.item_id = self.item_store.insert('solar.power')

    def test_gap_entry_val_quality_is_one(self):
        gap = BufferEntry(time=5000, duration=600, value=None, quality=QUALITY_NO_DATA)
        self.log_store.insert(self.item_id, gap, 'num', changed=5600)
        rows = self.db.fetchall(
            'SELECT val_quality, val_num, val_str, val_bool FROM log WHERE item_id=? AND time=?', (self.item_id, 5000)
        )
        self.assertEqual(rows[0][0], QUALITY_NO_DATA)
        self.assertIsNone(rows[0][1])  # val_num
        self.assertIsNone(rows[0][2])  # val_str
        self.assertIsNone(rows[0][3])  # val_bool

    def test_valid_entry_val_quality_is_zero(self):
        e = BufferEntry(time=1000, duration=500, value=250.0, quality=QUALITY_VALID)
        self.log_store.insert(self.item_id, e, 'num', changed=1500)
        rows = self.db.fetchall('SELECT val_quality FROM log WHERE item_id=? AND time=?', (self.item_id, 1000))
        self.assertEqual(rows[0][0], QUALITY_VALID)


# ──────────────────────────────────────────────────────────────────────────────
# End-to-end tests against the real plugin
# ──────────────────────────────────────────────────────────────────────────────


class TestQualityEndToEnd(TestDatabaseBase):
    """Drives the real Database plugin - update_item(), db_mark_invalid(),
    db_mark_valid(), _dump() - and asserts on actual database rows."""

    def test_db_mark_invalid_opens_gap_in_buffer(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.create_item(plugin, 'main.num')

        plugin._buffer_mgr.push(item, BufferEntry(time=self.t(1000), duration=None, value=250.0))
        item.db_mark_invalid()

        entries = plugin._buffer_mgr.pop_all(item)
        self.assertEqual(2, len(entries))
        self.assertEqual(QUALITY_VALID, entries[0].quality)
        self.assertEqual(self.t(1000), entries[0].time)
        self.assertIsNotNone(entries[0].duration)  # closed by push_invalid
        self.assertEqual(QUALITY_NO_DATA, entries[1].quality)
        self.assertIsNone(entries[1].value)
        self.assertIsNone(entries[1].duration)  # still open

    def test_db_mark_invalid_then_dump_persists_quality_flag(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        id = self.create_item(plugin, 'main.num')

        plugin._buffer_mgr.push(item, BufferEntry(time=self.t(1000), duration=None, value=250.0))
        item.db_mark_invalid()
        plugin._buffer_mgr.close_open(item, self.t(2000))  # close the open gap so _dump() writes it

        plugin._dump(items=[item])

        rows = plugin.readLogs(id)
        gap_rows = [r for r in rows if r[7] == QUALITY_NO_DATA]
        valid_rows = [r for r in rows if r[7] == QUALITY_VALID]
        self.assertEqual(1, len(gap_rows), f'expected exactly one gap row, got: {rows}')
        self.assertIsNone(gap_rows[0][4])  # val_num NULL for the gap
        self.assertEqual(1, len(valid_rows))
        self.assertEqual(250.0, valid_rows[0][4])

    def test_db_mark_valid_closes_open_gap(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.create_item(plugin, 'main.num')

        plugin._buffer_mgr.push_invalid(item, self.t(2000))
        with mock.patch.object(plugin.shtime, 'now', return_value=plugin._datetime(self.t(3000))):
            item.db_mark_valid()

        last = plugin._buffer_mgr.last_entry(item)
        self.assertEqual(QUALITY_NO_DATA, last.quality)
        self.assertEqual(self.t(1000), last.duration)

    def test_db_mark_valid_is_a_noop_without_an_open_gap(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.create_item(plugin, 'main.num')

        plugin._buffer_mgr.push(item, BufferEntry(time=self.t(1000), duration=None, value=250.0))
        item.db_mark_valid()  # no gap open - must not touch the valid entry

        last = plugin._buffer_mgr.last_entry(item)
        self.assertEqual(QUALITY_VALID, last.quality)
        self.assertIsNone(last.duration)  # still open, untouched

    def test_implicit_revalidation_uses_gap_start_not_prev_change(self):
        """A new value arriving while a gap is open must close the gap using
        the gap's own start time, not item.prev_change() - which points
        back to the item's last real Python-level value change and would
        overstate the gap's duration if connectivity was lost some time
        after that change, not at the exact same instant."""
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.create_item(plugin, 'main.num')

        # Item became 250.0 at t=1000 (already an open buffer entry).
        plugin._buffer_mgr.push(item, BufferEntry(time=self.t(1000), duration=None, value=250.0))

        # Connectivity lost later, at t=2000 - a full 1000s after the value
        # last actually changed at the Python level.
        with mock.patch.object(plugin.shtime, 'now', return_value=plugin._datetime(self.t(2000))):
            item.db_mark_invalid()

        # New value arrives at t=5000. item.prev_change() still reflects the
        # last real change (t=1000) since db_mark_invalid() never touches
        # the item's own Python-level value/history.
        item.set(180.0, 'test', prev_change=plugin._datetime(self.t(1000)), last_change=plugin._datetime(self.t(5000)))
        plugin.update_item(item)

        entries = plugin._buffer_mgr.pop_all(item)
        gap_entries = [e for e in entries if e.quality == QUALITY_NO_DATA]
        self.assertEqual(1, len(gap_entries), f'expected exactly one gap entry, got: {entries}')
        gap = gap_entries[0]
        self.assertEqual(self.t(2000), gap.time)
        correct_duration = self.t(5000) - self.t(2000)
        wrong_duration = self.t(5000) - self.t(1000)  # old bug: end - item.prev_change()
        self.assertEqual(
            correct_duration,
            gap.duration,
            f'gap duration must be relative to its own start ({correct_duration}), '
            f'not item.prev_change() ({wrong_duration})',
        )

        # No stale prev_value entry should have been emitted for the gap period:
        # [valid_250 (closed), gap (closed), new_valid_180 (open)] - not 4 entries.
        self.assertEqual(3, len(entries), f'expected [valid_250, gap, new_valid], got {len(entries)} entries')
        self.assertEqual(180.0, entries[2].value)
        self.assertIsNone(entries[2].duration)  # still open

    def test_subsequent_mark_valid_is_noop_after_implicit_close(self):
        """After a new value implicitly closes the gap, a later
        db_mark_valid() call must be a no-op - not close the new valid
        entry using a stale notion of "still in a gap"."""
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.create_item(plugin, 'main.num')

        plugin._buffer_mgr.push(item, BufferEntry(time=self.t(1000), duration=None, value=250.0))
        with mock.patch.object(plugin.shtime, 'now', return_value=plugin._datetime(self.t(2000))):
            item.db_mark_invalid()

        item.set(180.0, 'test', prev_change=plugin._datetime(self.t(1000)), last_change=plugin._datetime(self.t(3000)))
        plugin.update_item(item)

        with mock.patch.object(plugin.shtime, 'now', return_value=plugin._datetime(self.t(3500))):
            item.db_mark_valid()  # must be a no-op: gap already closed implicitly

        last = plugin._buffer_mgr.last_entry(item)
        self.assertEqual(180.0, last.value)
        self.assertIsNone(last.duration, 'new valid entry must remain open after the (no-op) db_mark_valid() call')

    def test_normal_update_unaffected_by_gap_detection(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.create_item(plugin, 'main.num')

        item.set(250.0, 'test', prev_change=plugin._datetime(self.t(0)), last_change=plugin._datetime(self.t(1000)))
        plugin.update_item(item)
        item.set(260.0, 'test', prev_change=plugin._datetime(self.t(1000)), last_change=plugin._datetime(self.t(2000)))
        plugin.update_item(item)

        entries = plugin._buffer_mgr.pop_all(item)
        self.assertTrue(all(e.quality == QUALITY_VALID for e in entries), f'no gap should appear: {entries}')


if __name__ == '__main__':
    unittest.main(verbosity=2)
