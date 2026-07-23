import time

from plugins.database.constants import COL_LOG_TIME, COL_LOG_DURATION, COL_LOG_VAL_NUM
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

    def test_maxage_action_falls_back_to_plugin_default_when_unset(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_no_action')
        self.assertEqual('delete', plugin._maxage_action_for(item))

        plugin._default_maxage_action = 'avg'
        self.assertEqual('avg', plugin._maxage_action_for(item))

    def test_maxage_action_invalid_for_item_type_falls_back_to_delete(self):
        # main.maxage_invalid_type is type str with database_maxage_action: sum -
        # sum reads val_num, which is always NULL for str items (utils.encode_value).
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage_invalid_type')
        self.assertEqual('delete', plugin._maxage_action_for(item))

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

    # -- remove_older_than_maxage() integration --------------------------------

    def test_remove_older_than_maxage_default_delete_behavior_unchanged(self):
        # regression: an item with database_maxage but no database_maxage_action
        # must still be plain-deleted through the full scheduler entrypoint,
        # exactly like before this feature existed.
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
