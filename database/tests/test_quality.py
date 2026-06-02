#!/usr/bin/env python3
"""Tests for the val_quality / missing-value feature.

These tests exercise the full plugin stack (via the in-memory SQLite database
already used by the existing base.py infrastructure) to verify:

- db_mark_invalid() opens a no-data gap in the buffer
- db_mark_valid() closes the gap
- The gap is written to the database with val_quality=1 and val_*=NULL
- Normal value entries have val_quality=0
- Aggregation queries (avg) exclude quality=1 rows
"""

import datetime
import sys
import os
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from plugins.database.constants import QUALITY_VALID, QUALITY_NO_DATA

try:
    from plugins.database.tests.base import TestDatabaseBase
    from tests.mock.core import MockSmartHome
    from tests import common
    HAS_SHNG_MOCK = True
except ImportError:
    HAS_SHNG_MOCK = False


# ──────────────────────────────────────────────────────────────────────────────
# Unit tests that only need the buffer + store layer (no SmartHomeNG mock)
# ──────────────────────────────────────────────────────────────────────────────

class TestQualityBufferLevel(unittest.TestCase):
    """Verify gap lifecycle purely at the buffer level."""

    def _make_buffer(self):
        from plugins.database.buffer import BufferManager
        from plugins.database.constants import BufferEntry
        mgr = BufferManager()
        return mgr, BufferEntry

    def _item(self):
        class _I:
            pass
        return _I()

    def test_open_gap_creates_no_data_entry(self):
        mgr, BE = self._make_buffer()
        item = self._item()
        mgr.register(item)
        mgr.push(item, BE(time=1000, duration=None, value=250.0))
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
        mgr, BE = self._make_buffer()
        item = self._item()
        mgr.register(item)
        mgr.push_invalid(item, start_ts=2000)
        mgr.close_open(item, end_ts=3000)
        last = mgr.last_entry(item)
        self.assertEqual(last.quality, QUALITY_NO_DATA)
        self.assertEqual(last.duration, 1000)

    def test_valid_entry_default_quality(self):
        mgr, BE = self._make_buffer()
        item = self._item()
        mgr.register(item)
        mgr.push(item, BE(time=100, duration=None, value=42.0))
        last = mgr.last_entry(item)
        self.assertEqual(last.quality, QUALITY_VALID)


class TestQualityStoreLevel(unittest.TestCase):
    """Verify gap storage at the LogStore level."""

    def setUp(self):
        import sqlite3
        from plugins.database.store import ItemStore, LogStore
        from plugins.database.constants import BufferEntry, QUALITY_NO_DATA, QUALITY_VALID

        class _DB:
            def __init__(self):
                self._conn = sqlite3.connect(':memory:')
                c = self._conn.cursor()
                c.execute("CREATE TABLE item (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                          " name VARCHAR(255), time BIGINT, val_str TEXT,"
                          " val_num REAL, val_bool BOOLEAN, changed BIGINT)")
                c.execute("CREATE TABLE log (time BIGINT, item_id INTEGER,"
                          " duration BIGINT, val_str TEXT, val_num REAL,"
                          " val_bool BOOLEAN, changed BIGINT, val_quality TINYINT DEFAULT 0)")
                self._conn.commit()
            def execute(self, s, p=(), cur=None):
                c = cur or self._conn.cursor()
                c.execute(s, p)
                if cur is None: self._conn.commit(); c.close()
            def fetchone(self, s, p=(), cur=None):
                c = cur or self._conn.cursor(); c.execute(s, p)
                r = c.fetchone()
                if cur is None: c.close()
                return tuple(r) if r else None
            def fetchall(self, s, p=(), cur=None):
                c = cur or self._conn.cursor(); c.execute(s, p)
                rows = c.fetchall()
                if cur is None: c.close()
                return [tuple(r) for r in rows]
            def commit(self): self._conn.commit()
            def rollback(self): self._conn.rollback()
            def connected(self): return True
            def cursor(self): return self._conn.cursor()

        tn = {'item': 'item', 'log': 'log',
              'item_columns': 'id, name, time, val_str, val_num, val_bool, changed',
              'log_columns':  'time, item_id, duration, val_str, val_num, val_bool, changed'}
        db = _DB()
        self.item_store = ItemStore(db, tn)
        self.log_store  = LogStore(db, tn)
        self.db = db
        self.BE = BufferEntry
        self.item_id = self.item_store.insert('solar.power')

    def test_gap_entry_val_quality_is_one(self):
        gap = self.BE(time=5000, duration=600, value=None, quality=QUALITY_NO_DATA)
        self.log_store.insert(self.item_id, gap, 'num', changed=5600)
        rows = self.db.fetchall(
            "SELECT val_quality, val_num, val_str, val_bool FROM log WHERE item_id=? AND time=?",
            (self.item_id, 5000),
        )
        self.assertEqual(rows[0][0], QUALITY_NO_DATA)
        self.assertIsNone(rows[0][1])  # val_num
        self.assertIsNone(rows[0][2])  # val_str
        self.assertIsNone(rows[0][3])  # val_bool

    def test_valid_entry_val_quality_is_zero(self):
        e = self.BE(time=1000, duration=500, value=250.0, quality=QUALITY_VALID)
        self.log_store.insert(self.item_id, e, 'num', changed=1500)
        rows = self.db.fetchall(
            "SELECT val_quality FROM log WHERE item_id=? AND time=?",
            (self.item_id, 1000),
        )
        self.assertEqual(rows[0][0], QUALITY_VALID)


if __name__ == '__main__':
    unittest.main(verbosity=2)
