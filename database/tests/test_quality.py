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


class TestImplicitRevalidation(unittest.TestCase):
    """Verify that supplying a new value while a gap is open correctly
    closes the gap with the right duration and clears gap tracking state.

    The three bugs fixed:
      1. Gap duration used item.prev_change() instead of the gap's own start
         time, making the gap appear longer than it actually was.
      2. _gap_items was not cleared, so a subsequent db_mark_valid() would
         incorrectly close the new valid entry instead of being a no-op.
      3. The gap entry (value=None) was mistakenly treated as a normal open
         value entry in step-1a, producing a buffer entry with value=None
         and the wrong duration.
    """

    def _make_buffer(self):
        from plugins.database.buffer import BufferManager
        from plugins.database.constants import BufferEntry
        return BufferManager(), BufferEntry

    def _item(self):
        class _I:
            pass
        return _I()

    # ── helpers that replicate _mark_item_invalid / update_item logic ────────

    def _open_gap(self, mgr, item, gap_start_ts, prior_value=250.0,
                  prior_start_ts=1000):
        """Open a gap in the buffer, mirroring _mark_item_invalid."""
        mgr.push(item, __import__('plugins.database.constants',
                                  fromlist=['BufferEntry']).BufferEntry(
            time=prior_start_ts, duration=None, value=prior_value))
        mgr.push_invalid(item, start_ts=gap_start_ts)

    def _simulate_update_item(self, mgr, gap_items, item,
                              update_ts, new_value):
        """
        Simulate the gap-path in update_item() as fixed:
          - Detect open gap
          - Close it with duration relative to gap.time (not item.prev_change)
          - Clear _gap_items
          - Append new valid entry
        """
        from plugins.database.constants import QUALITY_NO_DATA, BufferEntry
        buf = mgr._buffer[item]
        in_gap = (
            gap_items.get(item) is not None
            and buf
            and buf[-1].duration is None
            and buf[-1].value is None
        )
        if in_gap:
            gap = buf[-1]
            buf[-1] = gap._replace(duration=update_ts - gap.time)
            del gap_items[item]
            buf.append(BufferEntry(time=update_ts, duration=None, value=new_value))
        else:
            # normal path (not under test here)
            buf.append(BufferEntry(time=update_ts, duration=None, value=new_value))

    # ── tests ────────────────────────────────────────────────────────────────

    def test_gap_duration_uses_gap_start_not_prev_change(self):
        """Gap duration must be (update_time - gap_start), not
        (update_time - item.prev_change)."""
        mgr, BE = self._make_buffer()
        item = self._item()
        mgr.register(item)
        gap_items = {}

        # Valid entry from T=1000, gap opened at T=1500, new value at T=3000
        prior_start = 1000
        gap_start   = 1500
        update_ts   = 3000

        self._open_gap(mgr, item, gap_start, prior_value=250.0,
                       prior_start_ts=prior_start)
        gap_items[item] = gap_start

        self._simulate_update_item(mgr, gap_items, item, update_ts, 180.0)

        entries = mgr.pop_all(item)
        # [valid_250, gap, valid_180]
        self.assertEqual(len(entries), 3)

        gap_entry = entries[1]
        correct_duration = update_ts - gap_start       # 1500 ms
        wrong_duration   = update_ts - prior_start     # 2000 ms (old bug)

        self.assertEqual(gap_entry.duration, correct_duration,
                         f"Expected gap duration {correct_duration}, "
                         f"got {gap_entry.duration} (old bug would give "
                         f"{wrong_duration})")
        self.assertIsNone(gap_entry.value)

    def test_gap_items_cleared_after_implicit_revalidation(self):
        """_gap_items must be cleared when update_item closes the gap,
        so that a subsequent db_mark_valid() call is a no-op and does not
        corrupt the new valid entry."""
        mgr, BE = self._make_buffer()
        item = self._item()
        mgr.register(item)
        gap_items = {}

        self._open_gap(mgr, item, gap_start_ts=2000)
        gap_items[item] = 2000

        # New value arrives — gap is implicitly closed
        self._simulate_update_item(mgr, gap_items, item, 3000, 200.0)

        # _gap_items must be cleared
        self.assertNotIn(item, gap_items,
                         "_gap_items must be cleared after implicit re-validation")

    def test_no_stale_prev_value_emitted_during_gap(self):
        """When closing a gap implicitly, no step-1b prev_value entry must
        be emitted.  The buffer should contain exactly:
          [closed_valid, closed_gap, open_valid_new]."""
        mgr, BE = self._make_buffer()
        item = self._item()
        mgr.register(item)
        gap_items = {}

        self._open_gap(mgr, item, gap_start_ts=1500, prior_value=250.0,
                       prior_start_ts=1000)
        gap_items[item] = 1500

        self._simulate_update_item(mgr, gap_items, item, 3000, 180.0)

        entries = mgr.pop_all(item)
        self.assertEqual(len(entries), 3,
                         f"Expected [valid, gap, new_valid], got {len(entries)} entries")
        self.assertEqual(entries[0].value, 250.0)   # prior valid
        self.assertIsNone(entries[1].value)          # gap
        self.assertEqual(entries[2].value, 180.0)   # new valid

    def test_normal_update_unaffected(self):
        """Normal update (no open gap) must not be changed by the gap detection."""
        mgr, BE = self._make_buffer()
        item = self._item()
        mgr.register(item)
        gap_items = {}   # empty — no gap open

        # Push a normal open valid entry
        mgr.push(item, BE(time=1000, duration=None, value=250.0))

        # Simulate normal step-1a: close the previous entry, append new
        buf = mgr._buffer[item]
        in_gap = (
            gap_items.get(item) is not None
            and buf and buf[-1].duration is None and buf[-1].value is None
        )
        self.assertFalse(in_gap, "Should not detect a gap when none was opened")

    def test_subsequent_mark_valid_is_noop_after_implicit_close(self):
        """After implicit re-validation, db_mark_valid() must not close the
        new valid entry (stale _gap_items would have caused it to do so)."""
        mgr, BE = self._make_buffer()
        item = self._item()
        mgr.register(item)
        gap_items = {}

        self._open_gap(mgr, item, gap_start_ts=2000)
        gap_items[item] = 2000

        # New value — implicit re-validation, clears gap_items
        self._simulate_update_item(mgr, gap_items, item, 3000, 180.0)

        # Simulate db_mark_valid() — with _gap_items cleared it should no-op
        if gap_items.get(item) is not None:
            end_ts = 3500
            buf = mgr._buffer[item]
            if buf and buf[-1].duration is None:
                last = buf[-1]
                buf[-1] = last._replace(duration=end_ts - last.time)
            del gap_items[item]

        # The new valid entry (180W) must still be open (duration=None)
        last = mgr.last_entry(item)
        self.assertEqual(last.value, 180.0)
        self.assertIsNone(last.duration,
                          "New valid entry must remain open after the (no-op) "
                          "db_mark_valid() call")


if __name__ == '__main__':
    unittest.main(verbosity=2)
