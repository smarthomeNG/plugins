#!/usr/bin/env python3
"""Tests for plugins.database.buffer.BufferManager."""

import unittest

from plugins.database.buffer import BufferManager
from plugins.database.constants import BufferEntry, QUALITY_VALID, QUALITY_NO_DATA


class _Item:
    """Minimal item stand-in (only needs to be hashable)."""

    def __init__(self, name):
        self.name = name

    def __repr__(self):
        return f'Item({self.name})'


class TestBufferManagerRegistration(unittest.TestCase):
    def setUp(self):
        self.mgr = BufferManager()
        self.item = _Item('test.item')

    def test_register_creates_empty_list(self):
        self.mgr.register(self.item)
        self.assertEqual(self.mgr.pending_count(self.item), 0)

    def test_double_register_is_idempotent(self):
        self.mgr.register(self.item)
        self.mgr.register(self.item)  # must not raise or reset
        self.assertEqual(self.mgr.pending_count(self.item), 0)

    def test_items_returns_registered(self):
        self.mgr.register(self.item)
        self.assertIn(self.item, self.mgr.items())


class TestBufferManagerPushPop(unittest.TestCase):
    def setUp(self):
        self.mgr = BufferManager()
        self.item = _Item('test.item')
        self.mgr.register(self.item)

    def _entry(self, t, d=None, v=1.0):
        return BufferEntry(time=t, duration=d, value=v)

    def test_push_and_count(self):
        self.mgr.push(self.item, self._entry(100))
        self.assertEqual(self.mgr.pending_count(self.item), 1)

    def test_pop_all_removes_entries(self):
        self.mgr.push(self.item, self._entry(100))
        self.mgr.push(self.item, self._entry(200))
        entries = self.mgr.pop_all(self.item)
        self.assertEqual(len(entries), 2)
        self.assertEqual(self.mgr.pending_count(self.item), 0)

    def test_pop_all_empty_returns_empty(self):
        entries = self.mgr.pop_all(self.item)
        self.assertEqual(entries, [])

    def test_restore_puts_entries_back(self):
        self.mgr.push(self.item, self._entry(100))
        original = self.mgr.pop_all(self.item)
        self.mgr.restore(self.item, original)
        self.assertEqual(self.mgr.pending_count(self.item), 1)

    def test_restore_prepends_before_new_entries(self):
        self.mgr.push(self.item, self._entry(100))
        original = self.mgr.pop_all(self.item)
        # new entry arrived while dump was running
        self.mgr.push(self.item, self._entry(200))
        self.mgr.restore(self.item, original)
        entries = self.mgr.pop_all(self.item)
        self.assertEqual(entries[0].time, 100)
        self.assertEqual(entries[1].time, 200)


class TestBufferManagerCloseOpen(unittest.TestCase):
    def setUp(self):
        self.mgr = BufferManager()
        self.item = _Item('test.item')
        self.mgr.register(self.item)

    def test_close_open_sets_duration(self):
        self.mgr.push(self.item, BufferEntry(time=1000, duration=None, value=5.0))
        self.mgr.close_open(self.item, end_ts=1500)
        last = self.mgr.last_entry(self.item)
        self.assertEqual(last.duration, 500)
        self.assertEqual(last.time, 1000)
        self.assertEqual(last.value, 5.0)

    def test_close_open_does_nothing_if_already_closed(self):
        self.mgr.push(self.item, BufferEntry(time=1000, duration=200, value=5.0))
        self.mgr.close_open(self.item, end_ts=1500)
        last = self.mgr.last_entry(self.item)
        self.assertEqual(last.duration, 200)  # unchanged

    def test_close_open_does_nothing_on_empty_buffer(self):
        self.mgr.close_open(self.item, end_ts=1500)  # must not raise

    def test_has_open_entry_true_when_open(self):
        self.mgr.push(self.item, BufferEntry(time=1000, duration=None, value=3.0))
        self.assertTrue(self.mgr.has_open_entry(self.item))

    def test_has_open_entry_false_when_closed(self):
        self.mgr.push(self.item, BufferEntry(time=1000, duration=100, value=3.0))
        self.assertFalse(self.mgr.has_open_entry(self.item))

    def test_has_open_entry_false_when_empty(self):
        self.assertFalse(self.mgr.has_open_entry(self.item))


class TestBufferManagerQuality(unittest.TestCase):
    def setUp(self):
        self.mgr = BufferManager()
        self.item = _Item('solar.power')
        self.mgr.register(self.item)

    def test_push_invalid_creates_no_data_entry(self):
        self.mgr.push(self.item, BufferEntry(time=1000, duration=None, value=250.0))
        self.mgr.push_invalid(self.item, start_ts=1500)
        entries = self.mgr.pop_all(self.item)
        # first entry closed
        self.assertEqual(entries[0].duration, 500)
        self.assertEqual(entries[0].quality, QUALITY_VALID)
        # second entry is the gap
        self.assertEqual(entries[1].quality, QUALITY_NO_DATA)
        self.assertIsNone(entries[1].value)
        self.assertIsNone(entries[1].duration)  # still open

    def test_push_invalid_then_close_gap(self):
        self.mgr.push_invalid(self.item, start_ts=2000)
        self.mgr.close_open(self.item, end_ts=3000)
        last = self.mgr.last_entry(self.item)
        self.assertEqual(last.quality, QUALITY_NO_DATA)
        self.assertEqual(last.duration, 1000)

    def test_default_entry_quality_is_valid(self):
        self.mgr.push(self.item, BufferEntry(time=100, duration=None, value=42.0))
        last = self.mgr.last_entry(self.item)
        self.assertEqual(last.quality, QUALITY_VALID)


if __name__ == '__main__':
    unittest.main(verbosity=2)
