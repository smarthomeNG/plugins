#!/usr/bin/env python3
"""Tests for plugins.database.store — ItemStore and LogStore."""

import unittest
import sqlite3
import time

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..'))

from plugins.database.store import ItemStore, LogStore
from plugins.database.constants import BufferEntry, QUALITY_VALID, QUALITY_NO_DATA
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

    def execute(self, stmt, params=(), cur=None):
        c = cur or self._conn.cursor()
        # sqlite3 accepts both sequences (qmark) and dicts (named params)
        c.execute(stmt, params)
        if cur is None:
            self._conn.commit()
            c.close()

    def fetchone(self, stmt, params=(), cur=None):
        c = cur or self._conn.cursor()
        c.execute(stmt, params)
        row = c.fetchone()
        if cur is None:
            c.close()
        return tuple(row) if row else None

    def fetchall(self, stmt, params=(), cur=None):
        c = cur or self._conn.cursor()
        c.execute(stmt, params)
        rows = c.fetchall()
        if cur is None:
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

    def test_count(self):
        self.store.insert('a')
        self.store.insert('b')
        self.assertEqual(self.store.count(), 2)

    def test_delete_removes_item(self):
        item_id = self.store.insert('gone')
        self.store.delete(item_id)
        self.assertIsNone(self.store.find('gone'))


class TestLogStore(unittest.TestCase):
    def setUp(self):
        self.db = _MockDB()
        self.item_store = ItemStore(self.db, TABLE_NAMES)
        self.log_store = LogStore(self.db, TABLE_NAMES)
        self.item_id = self.item_store.insert('test.item')

    def _entry(self, t, d=None, v=1.0, q=QUALITY_VALID):
        return BufferEntry(time=t, duration=d, value=v, quality=q)

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


if __name__ == '__main__':
    unittest.main(verbosity=2)
