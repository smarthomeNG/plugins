#!/usr/bin/env python3
"""Tests for database_invalid_after (opt-in per-item staleness -> gap detection).

Covers registration/validation (_register_invalid_after), the reactive check
in update_item() (zero-loss for gaps that already resolved), and the periodic
scan _check_invalid_items() (for items still silent with no resolution yet).
"""

from unittest import mock

from plugins.database.constants import BufferEntry, QUALITY_NO_DATA, QUALITY_VALID
from plugins.database.tests.base import TestDatabaseBase


class TestInvalidAfterRegistration(TestDatabaseBase):
    def test_registers_item_with_valid_config(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_num')
        self.assertIn(item, plugin._items_with_invalid_after)
        self.assertEqual(300, plugin._items_with_invalid_after[item])

    def test_rejects_ro_acl(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_ro')
        self.assertNotIn(item, plugin._items_with_invalid_after)

    def test_rejects_unparseable_value(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_bad_value')
        self.assertNotIn(item, plugin._items_with_invalid_after)

    def test_still_registers_without_enforce_updates(self):
        # Missing enforce_updates degrades the reactive check for same-value
        # recoveries only (see _register_invalid_after's warning) - it must
        # not block registration outright.
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_no_enforce')
        self.assertIn(item, plugin._items_with_invalid_after)


class TestInvalidAfterScheduler(TestDatabaseBase):
    def test_registers_scheduler_when_configured(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, 'scheduler_add') as scheduler_add:
            plugin._start_schedulers()
        names = [call.args[0] for call in scheduler_add.call_args_list]
        self.assertIn('Check invalid items', names)

    def test_skips_scheduler_when_none_configured(self):
        plugin = self.plugin()
        plugin._items_with_invalid_after = {}
        with mock.patch.object(plugin, 'scheduler_add') as scheduler_add:
            plugin._start_schedulers()
        names = [call.args[0] for call in scheduler_add.call_args_list]
        self.assertNotIn('Check invalid items', names)


class TestInvalidAfterReactive(TestDatabaseBase):
    """update_item()'s reactive check - fires the instant a next update
    proves a gap is over, regardless of scan timing.

    _seed() establishes item.last_change()/last_update() at a controlled
    synthetic time and seeds a matching open buffer entry directly, without
    going through update_item() - mirrors test_quality.py's own established
    pattern. Going through update_item() for this step instead would hit its
    Step 1b "record the previous value" path against the item's real
    construction-time default, polluting the buffer with an unrelated entry.
    """

    def _seed(self, plugin, item, value, at_seconds):
        item.set(
            value,
            'test',
            prev_change=plugin._datetime(self.t(at_seconds)),
            last_change=plugin._datetime(self.t(at_seconds)),
        )
        plugin._buffer_mgr.push(item, BufferEntry(time=self.t(at_seconds), duration=None, value=value))

    def test_detects_gap_on_recovery_with_different_value_and_provable_boundary(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_num')
        self.create_item(plugin, 'main.invalid_after_num')
        self._seed(plugin, item, 10.0, 0)

        # Silent for 400s (threshold is 5m = 300s) before a different value arrives.
        item.set(20.0, 'test', last_change=plugin._datetime(self.t(400)))
        plugin.update_item(item)

        entries = plugin._buffer_mgr.pop_all(item)
        self.assertEqual(3, len(entries), f'expected [valid_10, gap, valid_20], got: {entries}')
        self.assertEqual(QUALITY_VALID, entries[0].quality)
        self.assertEqual(
            self.t(300),
            entries[0].duration,
            'previous value must be credited only its allowed threshold, not the full silence',
        )
        self.assertEqual(QUALITY_NO_DATA, entries[1].quality)
        self.assertEqual(self.t(300), entries[1].time, 'gap boundary must be prev_update+threshold, not "now"')
        self.assertEqual(self.t(100), entries[1].duration)
        self.assertEqual(20.0, entries[2].value)
        self.assertIsNone(entries[2].duration)

    def test_no_gap_within_threshold(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_num')
        self.create_item(plugin, 'main.invalid_after_num')
        self._seed(plugin, item, 10.0, 0)

        item.set(20.0, 'test', last_change=plugin._datetime(self.t(100)))  # well within 300s threshold
        plugin.update_item(item)

        entries = plugin._buffer_mgr.pop_all(item)
        gap_entries = [e for e in entries if e.quality == QUALITY_NO_DATA]
        self.assertEqual(0, len(gap_entries))

    def test_does_not_double_open_gap_when_already_open(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_num')
        self.create_item(plugin, 'main.invalid_after_num')
        self._seed(plugin, item, 10.0, 0)
        # Simulates an earlier scan tick having already marked it invalid.
        plugin._buffer_mgr.push_invalid(item, self.t(300))

        item.set(20.0, 'test', last_change=plugin._datetime(self.t(1000)))
        plugin.update_item(item)

        entries = plugin._buffer_mgr.pop_all(item)
        gap_entries = [e for e in entries if e.quality == QUALITY_NO_DATA]
        self.assertEqual(1, len(gap_entries), 'must not open a second gap on top of an existing one')

    def test_ignored_for_items_without_database_invalid_after(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.create_item(plugin, 'main.num')
        self._seed(plugin, item, 10.0, 0)

        item.set(20.0, 'test', last_change=plugin._datetime(self.t(100000)))  # way silent, but not opted in
        plugin.update_item(item)

        entries = plugin._buffer_mgr.pop_all(item)
        gap_entries = [e for e in entries if e.quality == QUALITY_NO_DATA]
        self.assertEqual(0, len(gap_entries))


class TestInvalidAfterScan(TestDatabaseBase):
    """The periodic scan - only path that can catch an item still silent
    right now, with no resolving update yet."""

    def _seed(self, plugin, item, value, at_seconds):
        item.set(
            value,
            'test',
            prev_change=plugin._datetime(self.t(at_seconds)),
            last_change=plugin._datetime(self.t(at_seconds)),
        )
        plugin._buffer_mgr.push(item, BufferEntry(time=self.t(at_seconds), duration=None, value=value))

    def test_marks_silent_item_invalid_with_provable_boundary(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_num')
        self.create_item(plugin, 'main.invalid_after_num')
        plugin._plugin_start_ts = self.t(0)
        self._seed(plugin, item, 10.0, 0)

        # Well past threshold (300s) + grace_time (60s) since both plugin start and last_update.
        with mock.patch.object(plugin.shtime, 'now', return_value=plugin._datetime(self.t(1000))):
            plugin._check_invalid_items()

        last = plugin._buffer_mgr.last_entry(item)
        self.assertEqual(QUALITY_NO_DATA, last.quality)
        self.assertIsNone(last.duration)
        self.assertEqual(self.t(300), last.time, 'gap boundary must be last_update+threshold, not scan time')

    def test_respects_startup_grace_period(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_num')
        self.create_item(plugin, 'main.invalid_after_num')
        plugin._plugin_start_ts = self.t(0)
        self._seed(plugin, item, 10.0, 0)

        # last_update age (350s) already exceeds threshold (300s), but the
        # plugin itself only started 350s ago too - still within
        # threshold(300s) + grace_time(60s) = 360s since startup.
        with mock.patch.object(plugin.shtime, 'now', return_value=plugin._datetime(self.t(350))):
            plugin._check_invalid_items()

        last = plugin._buffer_mgr.last_entry(item)
        self.assertEqual(QUALITY_VALID, last.quality)
        self.assertIsNone(last.duration)

    def test_skips_item_within_threshold(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_num')
        self.create_item(plugin, 'main.invalid_after_num')
        plugin._plugin_start_ts = self.t(0) - 1000 * 1000  # long past startup, grace irrelevant
        self._seed(plugin, item, 10.0, 0)

        with mock.patch.object(plugin.shtime, 'now', return_value=plugin._datetime(self.t(100))):
            plugin._check_invalid_items()

        last = plugin._buffer_mgr.last_entry(item)
        self.assertEqual(QUALITY_VALID, last.quality)

    def test_skips_item_already_in_gap(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.invalid_after_num')
        self.create_item(plugin, 'main.invalid_after_num')
        plugin._plugin_start_ts = self.t(0) - 1000 * 1000
        self._seed(plugin, item, 10.0, 0)
        plugin._buffer_mgr.push_invalid(item, self.t(50))

        with mock.patch.object(plugin.shtime, 'now', return_value=plugin._datetime(self.t(1000))):
            plugin._check_invalid_items()

        entries = plugin._buffer_mgr.pop_all(item)
        gap_entries = [e for e in entries if e.quality == QUALITY_NO_DATA]
        self.assertEqual(1, len(gap_entries), 'must not open a second gap on top of an existing one')

    def test_noop_before_run_has_set_plugin_start_ts(self):
        plugin = self.plugin()
        self.create_item(plugin, 'main.invalid_after_num')
        # plugin.plugin() never calls run(), so _plugin_start_ts is still None.
        plugin._check_invalid_items()  # must not raise
