import time
from unittest import mock

from plugins.database.constants import COL_LOG_TIME, COL_LOG_DURATION, COL_LOG_VAL_NUM, COL_LOG_VAL_STR, QUALITY_NO_DATA
from plugins.database.tests.base import TestDatabaseBase


class TestMaxageAction(TestDatabaseBase):
    """
    Regression tests for database_maxage_action (compact-instead-of-delete).

    Timestamps here use real epoch-ms (not the self.t() synthetic-seconds
    helper other tests use), since remove_older_than_maxage()/_compact_maxage()
    bucket purely on epoch-ms via floor division - no timezone/calendar
    dependency to worry about, just "old enough to be past the day-1 maxage
    cutoff, and within the same interval_ms-sized bucket".
    """

    def _old_bucket_start(self, interval_ms, days_ago=3):
        base_ms = int(time.time() * 1000) - days_ago * 86400 * 1000
        return (base_ms // interval_ms) * interval_ms

    # -- _maxage_action_for -------------------------------------------------

    def test_maxage_action_resolves_item_attribute(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        self.assertEqual('sum', plugin._maxage_action_for(item))

    def test_maxage_action_duty_cycle_resolves_for_bool_item(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_duty_cycle')
        self.assertEqual('duty_cycle', plugin._maxage_action_for(item))

    def test_maxage_action_falls_back_to_plugin_default_when_unset(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_no_action')
        self.assertEqual('delete', plugin._maxage_action_for(item))

        plugin._default_maxage_action = 'avg'
        self.assertEqual('avg', plugin._maxage_action_for(item))

    def test_maxage_action_duty_cycle_invalid_for_str_falls_back_to_delete(self):
        # 'duty_cycle' computes a time-weighted on-fraction (a float) - for a
        # str item that float would be stored back as the item's string
        # value ('0.37'), replacing real string history with stringified
        # numbers. str items use first/last instead.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_first_str')  # type str
        with mock.patch.object(plugin, 'get_iattr_value', return_value='duty_cycle'):
            with mock.patch.object(plugin, 'has_iattr', return_value=True):
                self.assertEqual('delete', plugin._maxage_action_for(item))

    def test_maxage_action_on_is_legacy_alias_for_duty_cycle(self):
        # 'on' predates 'duty_cycle' (renamed: unquoted 'on' is parsed as
        # YAML bool True, breaking the config) - still accepted and must
        # resolve identically, including the same type check.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_first_str')  # type str
        with mock.patch.object(plugin, 'get_iattr_value', return_value='on'):
            with mock.patch.object(plugin, 'has_iattr', return_value=True):
                self.assertEqual('delete', plugin._maxage_action_for(item))

    def test_maxage_action_invalid_for_item_type_falls_back_to_delete(self):
        # main.maxage_invalid_type is type str with database_maxage_action: sum -
        # sum reads val_num, which is always NULL for str items (utils.encode_value).
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_invalid_type')
        self.assertEqual('delete', plugin._maxage_action_for(item))

    # -- malformed database_maxage --

    def test_parse_item_survives_empty_database_maxage(self):
        # main.maxage_empty has database_maxage: '' - e.g. produced by a
        # struct copy-directive ('..:.') against a parent that doesn't set
        # database_maxage itself. parse_item() must not reach float(maxage)
        # unguarded on this (ValueError: could not convert string to
        # float: '').
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_empty')
        self.assertIsNotNone(item, 'item creation must not have crashed')
        self.assertNotIn(item, plugin._items_with_maxage)

    def test_get_maxage_ts_returns_none_for_empty_maxage(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_empty')
        self.assertIsNone(plugin.get_maxage_ts(item))

    # -- scheduler registration -----------------------------------------------

    def test_start_schedulers_registers_remove_old_for_default_maxage_alone(self):
        # 'Remove old' scheduler registration must not be gated only on
        # len(_items_with_maxage) > 0 (items with their own database_maxage
        # attribute) - a plugin-level default_maxage with zero such items
        # must still get the scheduler registered, since
        # remove_older_than_maxage()'s worklist-fill already falls back to
        # _handled_items for exactly this case (see its len(worklist) == 0
        # branch).
        plugin = self.plugin()
        plugin._items_with_maxage = []
        plugin._default_maxage = 30.0

        with mock.patch.object(plugin, 'scheduler_add') as scheduler_add:
            plugin._start_schedulers()

        names = [call.args[0] for call in scheduler_add.call_args_list]
        self.assertIn('Remove old', names)

    def test_start_schedulers_skips_remove_old_when_neither_configured(self):
        plugin = self.plugin()
        plugin._items_with_maxage = []
        plugin._default_maxage = 0.0

        with mock.patch.object(plugin, 'scheduler_add') as scheduler_add:
            plugin._start_schedulers()

        names = [call.args[0] for call in scheduler_add.call_args_list]
        self.assertNotIn('Remove old', names)

    def test_remove_older_than_maxage_skips_item_with_no_usable_maxage(self):
        # with default_maxage=0 (test default), main.maxage_empty would
        # never reach the worklist in practice - but if it somehow does
        # (e.g. default_maxage > 0, or a future caller), remove_older_than_maxage
        # must not crash trying to use a None time_end.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_empty')
        plugin._maxage_worklist = [item]
        plugin.remove_older_than_maxage()  # must not raise

    def test_remove_older_than_maxage_empty_worklist_does_not_crash(self):
        # Regression: filling the worklist from _handled_items/
        # _items_with_maxage can legitimately produce zero items (e.g. no
        # item routed to this instance yet) - the unconditional pop(0)
        # right after used to raise IndexError in that case.
        plugin = self.plugin()
        plugin._maxage_worklist = []
        plugin._handled_items = []
        plugin._items_with_maxage = []
        plugin.remove_older_than_maxage()  # must not raise

    # -- _maxage_interval_seconds_for ----------------------------------------

    def test_maxage_interval_seconds_for_parses_hours(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        self.assertEqual(3600, plugin._maxage_interval_seconds_for(item))

    def test_maxage_interval_seconds_for_falls_back_on_invalid_string(self):
        # Note: not asserting the warning log itself here - the test
        # logging setup's effective level for this logger (31) sits above
        # stdlib WARNING (30), so .warning() calls are filtered before any
        # handler (including assertLogs') ever sees them; that's a test
        # environment property, not something specific to this code path.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        item.conf['database_maxage_interval'] = 'not-a-duration'
        seconds = plugin._maxage_interval_seconds_for(item)
        self.assertEqual(86400, seconds)

    # -- _compact_maxage ------------------------------------------------------

    def test_compact_maxage_sum_replaces_raw_rows_with_one_aggregate(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        item_id = self.create_item(plugin, 'main.maxage_sum')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        values = [10.0, 20.0, 30.0]
        for i, v in enumerate(values):
            plugin.insertLog(item_id, time=bucket_start + i * 1000, duration=1000, val=v, it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows))
        self.assertEqual(bucket_start, rows[0][COL_LOG_TIME])
        self.assertEqual(interval_ms, rows[0][COL_LOG_DURATION])
        self.assertAlmostEqual(sum(values), rows[0][COL_LOG_VAL_NUM], places=3)

    def test_compact_maxage_avg_computes_duration_weighted_average(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_avg')
        item_id = self.create_item(plugin, 'main.maxage_avg')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        # two equal-duration samples -> plain average of 10 and 30 is 20
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val=10.0, it='num')
        plugin.insertLog(item_id, time=bucket_start + 1000, duration=1000, val=30.0, it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_avg', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows))
        self.assertAlmostEqual(20.0, rows[0][COL_LOG_VAL_NUM], places=3)

    def test_compact_maxage_advances_past_already_compacted_intervals_in_one_call(self):
        # Regression, found live 2026-09-04: oldest_time() can't tell a
        # just-compacted row from raw data (both are plain (time, duration,
        # value) rows) - without excluding rows whose duration already
        # matches interval_ms, the loop re-selects the same first interval
        # on every iteration and never reaches the later ones, even within
        # a single call (max_aggregate_intervals gets burned entirely on
        # interval #1). Four hours of raw data, all past cutoff, must
        # become four distinct aggregate rows in one call, not one.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        item_id = self.create_item(plugin, 'main.maxage_sum')

        interval_ms = 3600 * 1000
        first_bucket = self._old_bucket_start(interval_ms)
        for hour in range(4):
            plugin.insertLog(item_id, time=first_bucket + hour * interval_ms, duration=60000, val=float(hour), it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(4, len(rows), 'all four hourly intervals must compact in one call, not just the first')
        self.assertEqual([first_bucket + h * interval_ms for h in range(4)], [r[COL_LOG_TIME] for r in rows])

    def test_compact_maxage_second_call_does_not_retouch_already_compacted_row(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        item_id = self.create_item(plugin, 'main.maxage_sum')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val=10.0, it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, action)

        with mock.patch.object(plugin._log_store, 'delete_range', wraps=plugin._log_store.delete_range) as spy:
            plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, action)
        spy.assert_not_called()

    def test_maxage_action_first_last_valid_for_str_type(self):
        # the motivating case: avg/sum/min/max/integrate can't work on str
        # (val_num is always NULL there); first/last read back whatever was
        # actually stored, so they're the only meaningful compaction option
        # for str-typed items.
        plugin = self.plugin()
        first_item = self.sh.return_item('main.maxage_first_str')
        last_item = self.sh.return_item('main.maxage_last_str')
        self.assertEqual('first', plugin._maxage_action_for(first_item))
        self.assertEqual('last', plugin._maxage_action_for(last_item))

    def test_compact_maxage_first_keeps_oldest_raw_value(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_first_str')
        item_id = self.create_item(plugin, 'main.maxage_first_str')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val='idle', it='str')
        plugin.insertLog(item_id, time=bucket_start + 1000, duration=1000, val='heating', it='str')
        plugin.insertLog(item_id, time=bucket_start + 2000, duration=1000, val='error', it='str')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_first_str', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows))
        self.assertEqual(bucket_start, rows[0][COL_LOG_TIME])
        self.assertEqual(interval_ms, rows[0][COL_LOG_DURATION])
        self.assertEqual('idle', rows[0][COL_LOG_VAL_STR])

    def test_compact_maxage_last_keeps_newest_raw_value(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_last_str')
        item_id = self.create_item(plugin, 'main.maxage_last_str')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val='idle', it='str')
        plugin.insertLog(item_id, time=bucket_start + 1000, duration=1000, val='heating', it='str')
        plugin.insertLog(item_id, time=bucket_start + 2000, duration=1000, val='error', it='str')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_last_str', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows))
        self.assertEqual('error', rows[0][COL_LOG_VAL_STR])

    def test_compact_maxage_first_does_not_lose_real_data_behind_a_gap_row(self):
        # edge_value()'s ORDER BY time ASC LIMIT 1 must not return an
        # all-NULL no-data gap row as the "oldest" value for the interval -
        # a non-empty tuple of Nones is truthy in Python, so the decoded
        # value would come back None, skipping the aggregate insert, while
        # delete_range() (which never excludes gaps, a gap is a real row to
        # clean up too) still removes every row in the interval: gap AND
        # the real value sitting right after it, silently losing data. Put
        # the gap first (so it's picked as "first") and a real value right
        # after it, in the same interval.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_first_str')
        item_id = self.create_item(plugin, 'main.maxage_first_str')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val=None, it='str', quality=QUALITY_NO_DATA)
        plugin.insertLog(item_id, time=bucket_start + 1000, duration=1000, val='heating', it='str')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_first_str', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows), 'the real value must survive compaction, not be silently destroyed')
        self.assertEqual('heating', rows[0][COL_LOG_VAL_STR])

    def test_compact_maxage_leaves_interval_raw_when_aggregate_yields_no_value(self):
        # An interval whose valid rows all have duration NULL (crash-orphaned
        # open rows that never got their duration back-filled): a duration-
        # weighted aggregate like avg evaluates to NULL over them. value None
        # must mean "leave the interval untouched" here - deleting the raw
        # rows while inserting nothing would silently destroy real values.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_avg')
        item_id = self.create_item(plugin, 'main.maxage_avg')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=None, val=10.0, it='num')
        plugin.insertLog(item_id, time=bucket_start + 1000, duration=None, val=30.0, it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_avg', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(2, len(rows), 'rows the aggregate could not represent must survive compaction')

    def test_compact_maxage_avg_carries_live_open_row_past_interval_instead_of_stalling(self):
        # A value that hasn't changed in longer than database_maxage: its
        # one still-open row (duration=NULL) is confirmed live (matches
        # item.last_change()), so it must be clipped into this interval's
        # aggregate instead of stalling, and survive re-anchored to
        # interval_end - not deleted, not left behind at its old time.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_avg')
        item_id = self.create_item(plugin, 'main.maxage_avg')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=None, val=42.0, it='num')
        plugin._db.commit()
        item.set(42.0, 'test', last_change=plugin._datetime(bucket_start))

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_avg', time_end, action)

        rows = sorted(plugin.readLogs(item_id), key=lambda r: r[COL_LOG_TIME])
        self.assertEqual(2, len(rows), 'stalled instead of compacting the closed portion')
        self.assertEqual(bucket_start, rows[0][COL_LOG_TIME])
        self.assertEqual(interval_ms, rows[0][COL_LOG_DURATION])
        self.assertAlmostEqual(42.0, rows[0][COL_LOG_VAL_NUM], places=3)
        self.assertEqual(
            bucket_start + interval_ms, rows[1][COL_LOG_TIME], 're-anchored open row must move to interval_end'
        )
        self.assertIsNone(rows[1][COL_LOG_DURATION], 'carried-forward row must still be open')
        self.assertAlmostEqual(42.0, rows[1][COL_LOG_VAL_NUM], places=3)

    def test_compact_maxage_avg_folds_live_open_row_sharing_interval_with_closed_data(self):
        # Mixed interval: one closed row plus the live open row that
        # followed it. delete_range() has no idea about "open" rows, so the
        # still-live row must be re-anchored past the interval before
        # compaction, not silently deleted along with the closed one - even
        # though its value never contributed to the computed aggregate.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_avg')
        item_id = self.create_item(plugin, 'main.maxage_avg')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val=10.0, it='num')
        open_time = bucket_start + 1000
        plugin.insertLog(item_id, time=open_time, duration=None, val=30.0, it='num')
        plugin._db.commit()
        item.set(30.0, 'test', last_change=plugin._datetime(open_time))

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_avg', time_end, action)

        rows = sorted(plugin.readLogs(item_id), key=lambda r: r[COL_LOG_TIME])
        self.assertEqual(2, len(rows))
        # weighted avg over (10.0, 1000ms) and (30.0, clipped ~3599000ms) - dominated by 30.0
        expected = (10.0 * 1000 + 30.0 * (interval_ms - 1000)) / interval_ms
        self.assertAlmostEqual(expected, rows[0][COL_LOG_VAL_NUM], places=2)
        self.assertEqual(bucket_start + interval_ms, rows[1][COL_LOG_TIME])
        self.assertIsNone(rows[1][COL_LOG_DURATION])
        self.assertAlmostEqual(30.0, rows[1][COL_LOG_VAL_NUM], places=3)

    def test_compact_maxage_does_not_carry_forward_a_crash_orphaned_open_row(self):
        # Same shape as the live-open-row case, but item.last_change()
        # does NOT match the open row's time (simulating a crash orphan -
        # indistinguishable from a live row in storage alone). Must fall
        # through to the existing stall-and-warn behavior, not fabricate
        # a duration for a row nothing confirms is still current.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_avg')
        item_id = self.create_item(plugin, 'main.maxage_avg')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=None, val=42.0, it='num')
        plugin._db.commit()
        # last_change deliberately left at the item's default (does not match bucket_start)

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_avg', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows), 'orphaned row must survive untouched, not be carried forward or deleted')
        self.assertEqual(bucket_start, rows[0][COL_LOG_TIME])
        self.assertIsNone(rows[0][COL_LOG_DURATION])

    def test_compact_maxage_still_removes_gap_only_interval(self):
        # Companion to the test above: an interval containing ONLY no-data
        # gap rows has nothing to preserve - value None with zero valid rows
        # must still delete the gap rows (they are real rows to clean up).
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_avg')
        item_id = self.create_item(plugin, 'main.maxage_avg')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val=None, it='num', quality=QUALITY_NO_DATA)
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_avg', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(0, len(rows), 'a gap-only interval must still be cleaned up')

    def test_compact_maxage_first_works_for_num_type_too(self):
        # first/last aren't str-only - they're valid for any type, and for
        # num/bool items they mean "the value at the start/end of the
        # interval" rather than a statistic over it.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')  # type num
        item_id = self.create_item(plugin, 'main.maxage_sum')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val=7.0, it='num')
        plugin.insertLog(item_id, time=bucket_start + 1000, duration=1000, val=99.0, it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, 'first')

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows))
        self.assertEqual(7.0, rows[0][COL_LOG_VAL_NUM])

    def test_compact_maxage_never_touches_data_inside_raw_window(self):
        # a row from "now" must survive untouched - only data older than the
        # maxage cutoff may be compacted.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        item_id = self.create_item(plugin, 'main.maxage_sum')

        now_ms = int(time.time() * 1000)
        plugin.insertLog(item_id, time=now_ms, duration=1000, val=42.0, it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)
        plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, action)

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows))
        self.assertEqual(now_ms, rows[0][COL_LOG_TIME])
        self.assertEqual(42.0, rows[0][COL_LOG_VAL_NUM])

    def test_compact_maxage_is_self_healing_across_bounded_calls(self):
        # max_aggregate_intervals=1 forces two separate calls to fully
        # process two old buckets - there is no persisted cursor, so the
        # second call must pick up exactly where the first left off (via
        # oldest_time()) without duplicating or losing data.
        plugin = self.plugin()
        plugin.max_aggregate_intervals = 1
        item = self.sh.return_item('main.maxage_sum')
        item_id = self.create_item(plugin, 'main.maxage_sum')

        interval_ms = 3600 * 1000
        bucket1 = self._old_bucket_start(interval_ms, days_ago=5)
        bucket2 = self._old_bucket_start(interval_ms, days_ago=3)
        plugin.insertLog(item_id, time=bucket1, duration=1000, val=5.0, it='num')
        plugin.insertLog(item_id, time=bucket2, duration=1000, val=7.0, it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)

        plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, action)
        rows = sorted(plugin.readLogs(item_id), key=lambda r: r[COL_LOG_TIME])
        # bucket1 compacted (duration == interval_ms); bucket2 untouched raw
        # row still present (duration == 1000, its original value) - the
        # bound only limits how much work happens per call, not visibility.
        self.assertEqual(2, len(rows), 'bucket1 compacted, bucket2 still raw and present')
        self.assertEqual(interval_ms, rows[0][COL_LOG_DURATION], 'bucket1 must already be an aggregate row')
        self.assertEqual(5.0, rows[0][COL_LOG_VAL_NUM])
        self.assertEqual(1000, rows[1][COL_LOG_DURATION], 'bucket2 must still be the original raw row')
        self.assertEqual(7.0, rows[1][COL_LOG_VAL_NUM])
        self.assertIn(item, plugin._maxage_worklist, 'item must be requeued - a second old bucket remains')

        plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, action)
        rows = sorted(plugin.readLogs(item_id), key=lambda r: r[COL_LOG_TIME])
        self.assertEqual(2, len(rows))
        self.assertEqual(bucket1, rows[0][COL_LOG_TIME])
        self.assertEqual(5.0, rows[0][COL_LOG_VAL_NUM])
        self.assertEqual(bucket2, rows[1][COL_LOG_TIME])
        self.assertEqual(7.0, rows[1][COL_LOG_VAL_NUM])

    def test_compact_maxage_failure_rolls_back_and_leaves_connection_usable(self):
        # A mid-transaction failure here must roll back and leave the
        # connection in a clean, usable state for the next caller -
        # without that, a broken connection stays broken indefinitely.
        # _compact_maxage() must catch this itself, mirroring _dump()'s
        # per-item isolation: one item's failure must not crash the whole
        # scheduled cycle.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        item_id = self.create_item(plugin, 'main.maxage_sum')

        interval_ms = 3600 * 1000
        bucket1 = self._old_bucket_start(interval_ms, days_ago=5)
        plugin.insertLog(item_id, time=bucket1, duration=1000, val=5.0, it='num')
        plugin._db.commit()

        time_end = plugin.get_maxage_ts(item)
        action = plugin._maxage_action_for(item)

        with mock.patch.object(
            plugin._log_store, 'insert', side_effect=RuntimeError('simulated failure mid-transaction')
        ):
            plugin._compact_maxage(item, item_id, 'main.maxage_sum', time_end, action)

        self.assertTrue(plugin._db.lock(0), '_fdb_lock left held after _compact_maxage() caught its own exception')
        plugin._db.release()

        # connection must still be genuinely usable afterward, not left
        # in a corrupted-but-marked-connected state
        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows), 'the failed compaction must have rolled back, not left a partial delete')
        self.assertEqual(5.0, rows[0][COL_LOG_VAL_NUM])

    # -- remove_older_than_maxage() integration --------------------------------

    def test_remove_older_than_maxage_default_delete_behavior_unchanged(self):
        # an item with database_maxage but no database_maxage_action must
        # still be plain-deleted through the full scheduler entrypoint.
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage')
        item_id = self.create_item(plugin, 'main.maxage')

        now_ms = int(time.time() * 1000)
        old_ms = now_ms - 40 * 86400 * 1000  # well past the 30-day maxage
        plugin.insertLog(item_id, time=old_ms, duration=1000, val=99.0, it='num')
        # a recent row too: main.maxage is `database: init`, and the existing
        # delete path deliberately keeps the single latest value alive if
        # deleting would otherwise leave the item with no data at all to
        # init from - a recent row already satisfies that, so the old row
        # gets deleted normally instead of exercising that unrelated guard.
        plugin.insertLog(item_id, time=now_ms, duration=1000, val=100.0, it='num')
        plugin._db.commit()

        plugin._maxage_worklist = [item]
        plugin.remove_older_than_maxage()

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows), 'default action must delete the old row, not leave an aggregate behind')
        self.assertEqual(100.0, rows[0][COL_LOG_VAL_NUM])

    def test_remove_older_than_maxage_bulk_delete_uses_transaction(self):
        # The "strategy b" bulk-delete branch (row count over
        # max_delete_logentries) must lock()/commit() its own DELETE via
        # transaction(), not rely on some unrelated later commit() on
        # self._db (e.g. the next _dump() cycle) to actually persist it. A
        # spy on transaction() proves the delete genuinely locks + commits
        # itself.
        plugin = self.plugin()
        plugin.max_delete_logentries = 1
        item = self.sh.return_item('main.maxage')
        item_id = self.create_item(plugin, 'main.maxage')

        now_ms = int(time.time() * 1000)
        old_ms = now_ms - 40 * 86400 * 1000
        plugin.insertLog(item_id, time=old_ms, duration=1000, val=98.0, it='num')
        plugin.insertLog(item_id, time=old_ms + 1000, duration=1000, val=99.0, it='num')
        plugin._db.commit()

        calls = []
        orig_transaction = plugin._db.transaction

        def spy_transaction(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        plugin._db.transaction = spy_transaction
        plugin._maxage_worklist = [item]
        plugin.remove_older_than_maxage()

        self.assertTrue(calls, 'bulk-delete branch must go through self._db.transaction()')

    def test_remove_older_than_maxage_bulk_delete_removes_oldest_rows_first(self):
        # The bulk-delete DELETE statement must use a rowid-subquery (same
        # pattern as reassign_orphaned_id()'s UPDATE a few dozen lines above
        # this method), not 'DELETE FROM {log} WHERE item_id = :id ORDER BY
        # time ASC LIMIT :maxrecords' - the latter is not valid SQLite
        # syntax without the non-default SQLITE_ENABLE_UPDATE_DELETE_LIMIT
        # compile flag. This test exercises the real SQL - not a mock - and
        # specifically checks that the OLDEST rows (by time) are the ones
        # removed, since a naive rowid-order rewrite could easily get this
        # backwards.
        plugin = self.plugin()
        plugin.max_delete_logentries = 2
        item_id = self.create_item(plugin, 'main.maxage')

        now_ms = int(time.time() * 1000)
        old_ms = now_ms - 40 * 86400 * 1000
        # 4 old rows, distinct times/values, deliberately inserted out of
        # time order so a rowid-based (insertion-order) mistake would be
        # caught rather than accidentally matching time order.
        plugin.insertLog(item_id, time=old_ms + 3000, duration=1000, val=40.0, it='num')
        plugin.insertLog(item_id, time=old_ms + 1000, duration=1000, val=20.0, it='num')
        plugin.insertLog(item_id, time=old_ms, duration=1000, val=10.0, it='num')
        plugin.insertLog(item_id, time=old_ms + 2000, duration=1000, val=30.0, it='num')
        plugin._db.commit()

        plugin._maxage_worklist = [self.sh.return_item('main.maxage')]
        plugin.remove_older_than_maxage()

        remaining = sorted(row[COL_LOG_VAL_NUM] for row in plugin.readLogs(item_id))
        self.assertEqual(
            [30.0, 40.0],
            remaining,
            'must delete exactly the 2 oldest rows (by time, not insertion order) and keep the 2 newest',
        )

    def test_remove_older_than_maxage_dispatches_to_compaction(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_sum')
        item_id = self.create_item(plugin, 'main.maxage_sum')

        interval_ms = 3600 * 1000
        bucket_start = self._old_bucket_start(interval_ms)
        plugin.insertLog(item_id, time=bucket_start, duration=1000, val=11.0, it='num')
        plugin.insertLog(item_id, time=bucket_start + 1000, duration=1000, val=22.0, it='num')
        plugin._db.commit()

        plugin._maxage_worklist = [item]
        plugin.remove_older_than_maxage()

        rows = plugin.readLogs(item_id)
        self.assertEqual(1, len(rows))
        self.assertAlmostEqual(33.0, rows[0][COL_LOG_VAL_NUM], places=3)
