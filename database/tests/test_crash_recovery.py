import time
from unittest import mock

from plugins.database.constants import COL_LOG_DURATION, COL_LOG_TIME, COL_LOG_VAL_NUM, QUALITY_NO_DATA
from plugins.database.tests.base import TestDatabaseBase


class TestCloseStartupOrphans(TestDatabaseBase):
    """After an unclean shutdown an item's last log row keeps ``duration IS NULL``. At startup,
    before the first dump, that row is closed at the last time any item was flushed."""

    START_TS = 1000

    def plugin(self, **param_overrides):
        plugin = super().plugin(**param_overrides)
        plugin._plugin_start_ts = self.t(self.START_TS)
        return plugin

    def duration_at(self, plugin, name, second):
        item_id = plugin.id(self.sh.return_item(name), create=False)
        rows = plugin._log_store.find(item_id, self.t(second))
        self.assertEqual(1, len(rows))
        return rows[0][COL_LOG_DURATION]

    def set_last_flush(self, plugin, name, second):
        """Mark *name* as last flushed at *second* (the item table's ``changed``)."""
        item_id = self.create_item(plugin, name)
        plugin.updateItem(item_id, self.t(second), None, 'x', 'str', self.t(second))

    def test_last_row_without_duration_is_closed_at_last_flush(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5)])
        self.set_last_flush(plugin, 'main.str', 500)

        plugin._close_startup_orphans()

        self.assertEqual(self.t(490), self.duration_at(plugin, 'main.num', 10))

    def test_live_row_restored_from_the_item_table_stays_open(self):
        # A restored `database: init` item has last_change() == its open row's time: the value is still active.
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        item_id = self.create_item(plugin, 'main.num')
        live_time = plugin._timestamp(item.last_change())
        plugin.insertLog(item_id, time=live_time, duration=None, val=5, it='num')
        self.set_last_flush(plugin, 'main.str', 500)

        plugin._close_startup_orphans()

        self.assertIsNone(plugin._log_store.find(item_id, live_time)[0][COL_LOG_DURATION])

    def test_flush_older_than_the_row_gives_zero_duration(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5)])
        self.set_last_flush(plugin, 'main.str', 5)

        plugin._close_startup_orphans()

        self.assertEqual(0, self.duration_at(plugin, 'main.num', 10))

    def test_duration_ends_no_later_than_startup(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5)])
        self.set_last_flush(plugin, 'main.str', self.START_TS + 500)

        plugin._close_startup_orphans()

        self.assertEqual(self.t(self.START_TS - 10), self.duration_at(plugin, 'main.num', 10))

    def test_closed_row_is_left_alone(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, 20, 5)])
        self.set_last_flush(plugin, 'main.str', 500)

        self.assertEqual(0, plugin._close_startup_orphans())

        self.assertEqual(self.t(10), self.duration_at(plugin, 'main.num', 10))

    def test_only_the_last_row_is_considered(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5), (20, 30, 6)])
        self.set_last_flush(plugin, 'main.str', 500)

        self.assertEqual(0, plugin._close_startup_orphans())

        self.assertIsNone(self.duration_at(plugin, 'main.num', 10))

    def test_no_data_gap_row_is_left_alone(self):
        plugin = self.plugin()
        item_id = self.create_item(plugin, 'main.num')
        plugin.insertLog(item_id, time=self.t(10), duration=None, val=None, it='num', quality=QUALITY_NO_DATA)
        self.set_last_flush(plugin, 'main.str', 500)

        self.assertEqual(0, plugin._close_startup_orphans())

        self.assertIsNone(self.duration_at(plugin, 'main.num', 10))

    def test_database_failure_is_survived(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5)])

        with mock.patch.object(plugin._db, 'transaction', side_effect=ConnectionError('not connected')):
            self.assertEqual(0, plugin._close_startup_orphans())

    def test_nothing_flushed_yet_closes_nothing(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5)])

        self.assertEqual(0, plugin._close_startup_orphans())

        self.assertIsNone(self.duration_at(plugin, 'main.num', 10))


class TestRunClosesStartupOrphans(TestDatabaseBase):
    def test_run_closes_orphans_before_the_schedulers_start(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5)])
        item_id = self.create_item(plugin, 'main.str')
        plugin.updateItem(item_id, self.t(500), None, 'x', 'str', self.t(500))
        durations_at_scheduler_start = []

        def record_duration():
            row = plugin._log_store.find(plugin.id(self.sh.return_item('main.num'), create=False), self.t(10))[0]
            durations_at_scheduler_start.append(row[COL_LOG_DURATION])

        with mock.patch.object(plugin, '_start_schedulers', side_effect=record_duration):
            plugin.run()

        self.assertEqual([self.t(490)], durations_at_scheduler_start)


class TestRecoverStaleOrphans(TestDatabaseBase):
    """Rows left open by older crashes sit before a newer row of the same item. They are closed at the newer
    row's time, one bounded slice per call."""

    START_TS = 1000

    def plugin(self, **param_overrides):
        plugin = super().plugin(**param_overrides)
        plugin._plugin_start_ts = self.t(self.START_TS)
        return plugin

    def recover_all(self, plugin):
        for _ in range(100):
            if not plugin._recover_stale_slice():
                return
        self.fail('recovery did not finish')

    def duration_at(self, plugin, name, second):
        item_id = plugin.id(self.sh.return_item(name), create=False)
        rows = plugin._log_store.find(item_id, self.t(second))
        self.assertEqual(1, len(rows))
        return rows[0][COL_LOG_DURATION]

    def test_open_row_before_a_newer_row_is_closed_at_the_newer_rows_time(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5), (25, 30, 6)])

        self.recover_all(plugin)

        self.assertEqual(self.t(15), self.duration_at(plugin, 'main.num', 10))

    def test_time_weighted_average_ignores_the_crash_afterwards(self):
        # The same three rows as an uncrashed run: closed it reads 43.33, left open it read 66.0.
        plugin = self.plugin()
        item_id = self.create_item(plugin, 'main.num')
        plugin.insertLog(item_id, time=self.t(0), duration=self.t(2), val=10, it='num')
        plugin.insertLog(item_id, time=self.t(2), duration=None, val=100, it='num')
        plugin.insertLog(item_id, time=self.t(4), duration=self.t(2), val=20, it='num')

        self.recover_all(plugin)

        self.assertEqual(43.33, plugin._single('avg', start=self.t(0), end=self.t(8), item='main.num'))

    def test_successive_open_rows_are_each_closed_at_their_successor(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5), (20, None, 6), (35, 40, 7)])

        self.recover_all(plugin)

        self.assertEqual(self.t(10), self.duration_at(plugin, 'main.num', 10))
        self.assertEqual(self.t(15), self.duration_at(plugin, 'main.num', 20))

    def test_last_row_is_left_open(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, 20, 5), (30, None, 6)])

        self.recover_all(plugin)

        self.assertIsNone(self.duration_at(plugin, 'main.num', 30))

    def test_rows_from_this_run_are_left_open(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(self.START_TS + 10, None, 5), (self.START_TS + 20, 30, 6)])

        self.recover_all(plugin)

        self.assertIsNone(self.duration_at(plugin, 'main.num', self.START_TS + 10))

    def test_open_row_is_closed_no_later_than_the_last_flush(self):
        # Successor far later than the crash: the value was not necessarily held through the outage.
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 5), (900, 30, 6)])
        item_id = self.create_item(plugin, 'main.str')
        plugin.updateItem(item_id, self.t(100), None, 'x', 'str', self.t(100))
        plugin._close_startup_orphans()

        self.recover_all(plugin)

        self.assertEqual(self.t(90), self.duration_at(plugin, 'main.num', 10))

    def test_a_slice_scans_a_bounded_number_of_rows(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 1), (20, None, 2), (30, None, 3), (40, None, 4), (50, 60, 5)])
        plugin._recovery.window_rows = 2

        self.assertTrue(plugin._recover_stale_slice())

        closed = [s for s in (10, 20, 30, 40) if self.duration_at(plugin, 'main.num', s) is not None]
        self.assertEqual([10, 20], closed)

        self.recover_all(plugin)

        for second in (10, 20, 30, 40):
            self.assertIsNotNone(self.duration_at(plugin, 'main.num', second))

    def test_every_item_is_scanned(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 1), (20, 30, 2)])
        self.create_log(plugin, 'main.maxage', [(40, None, 1), (55, 60, 2)])

        self.recover_all(plugin)

        self.assertEqual(self.t(10), self.duration_at(plugin, 'main.num', 10))
        self.assertEqual(self.t(15), self.duration_at(plugin, 'main.maxage', 40))

    def test_a_database_failure_is_retried_on_the_next_call(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 1), (20, 30, 2)])

        with mock.patch.object(plugin._db_maint, 'transaction', side_effect=ConnectionError('not connected')):
            self.assertTrue(plugin._recover_stale_slice())

        self.recover_all(plugin)

        self.assertEqual(self.t(10), self.duration_at(plugin, 'main.num', 10))

    def test_a_call_works_through_slices_until_its_time_budget_is_spent(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(10, None, 1), (20, None, 2), (30, None, 3), (40, 50, 4)])
        plugin._recovery.window_rows = 1

        self.assertTrue(plugin._recovery.recover_stale(budget_seconds=0))
        self.assertIsNotNone(self.duration_at(plugin, 'main.num', 10))
        self.assertIsNone(self.duration_at(plugin, 'main.num', 20))

        self.assertFalse(plugin._recovery.recover_stale(budget_seconds=60))
        self.assertIsNotNone(self.duration_at(plugin, 'main.num', 30))


class TestRecoverySchedulerJob(TestDatabaseBase):
    def test_the_job_is_registered_with_the_schedulers(self):
        plugin = self.plugin()

        with mock.patch.object(plugin, 'scheduler_add') as scheduler_add:
            plugin._start_schedulers()

        self.assertIn('Recover open rows', [call.args[0] for call in scheduler_add.call_args_list])

    def test_the_job_removes_itself_once_everything_is_scanned(self):
        plugin = self.plugin()

        with mock.patch.object(plugin, 'scheduler_remove') as scheduler_remove:
            plugin._recover_stale_orphans()

        scheduler_remove.assert_called_once_with('Recover open rows')

    def test_the_job_stays_registered_while_work_remains(self):
        plugin = self.plugin()

        with mock.patch.object(plugin._recovery, 'recover_stale', return_value=True):
            with mock.patch.object(plugin, 'scheduler_remove') as scheduler_remove:
                plugin._recover_stale_orphans()

        scheduler_remove.assert_not_called()


class TestCompactionAfterRecovery(TestDatabaseBase):
    """An interval holding only a crash-orphaned row cannot be aggregated by a duration-weighted action."""

    HOUR_MS = 3600 * 1000

    def build(self):
        plugin = self.plugin()
        plugin._plugin_start_ts = int(time.time() * 1000)
        item = self.sh.return_item('main.maxage_avg')
        item_id = self.create_item(plugin, 'main.maxage_avg')
        old_hour = ((int(time.time() * 1000) - 3 * 86400 * 1000) // self.HOUR_MS) * self.HOUR_MS
        plugin.insertLog(item_id, time=old_hour, duration=None, val=10.0, it='num')
        plugin.insertLog(item_id, time=old_hour + self.HOUR_MS + 1000, duration=1000, val=30.0, it='num')
        plugin._db.commit()
        return plugin, item, item_id, old_hour

    def compact(self, plugin, item, item_id):
        plugin._compact_maxage(item, item_id, 'main.maxage_avg', plugin.get_maxage_ts(item), 'avg')

    def test_compaction_stalls_on_the_open_row_without_recovery(self):
        plugin, item, item_id, old_hour = self.build()

        self.compact(plugin, item, item_id)

        self.assertEqual(2, len(plugin.readLogs(item_id)))

    def test_compaction_aggregates_the_interval_after_recovery(self):
        plugin, item, item_id, old_hour = self.build()
        while plugin._recover_stale_slice():
            pass

        self.compact(plugin, item, item_id)

        first = plugin.readLogs(item_id)[0]
        self.assertEqual(old_hour, first[COL_LOG_TIME])
        self.assertEqual(self.HOUR_MS, first[COL_LOG_DURATION])
        self.assertAlmostEqual(10.0, first[COL_LOG_VAL_NUM], places=3)
