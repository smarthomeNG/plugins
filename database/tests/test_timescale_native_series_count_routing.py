#!/usr/bin/env python3
"""Tests for _series()'s and readLogCount()'s native-mode cagg routing -
step 4's remaining pieces after _single(). Same narrow discipline: only
covers the portion of a range that predates the raw floor, never attempts
to stitch a single precise answer across the raw/cagg-only boundary.
"""

from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class TestItemForId(TestDatabaseBase):
    def test_resolves_and_caches(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        item_id = plugin.id(item, create=True)
        with mock.patch.object(plugin, '_fetchall', wraps=plugin._fetchall) as fetchall:
            resolved_1 = plugin._item_for_id(item_id)
            resolved_2 = plugin._item_for_id(item_id)
        self.assertIs(item, resolved_1)
        self.assertIs(item, resolved_2)
        fetchall.assert_called_once()  # second call must hit the cache, not the DB again

    def test_returns_none_for_unknown_id(self):
        plugin = self.plugin()
        self.assertIsNone(plugin._item_for_id(999999))


class TestNativeCaggSeries(TestDatabaseBase):
    def _native_plugin(self, action='avg', interval='1h'):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 30
        item.conf['database_maxage_action'] = action
        item.conf['database_maxage_interval'] = interval
        plugin._items_with_maxage = [item]
        plugin.id(item, create=True)  # _native_cagg_series() needs a real item_id, not None
        return plugin, item

    def test_not_applicable_for_a_func_with_no_cagg_column(self):
        plugin, item = self._native_plugin()
        self.assertIsNone(plugin._native_cagg_series('diff', 0, 1000, 100, item))
        self.assertIsNone(plugin._native_cagg_series('raw', 0, 1000, 100, item))

    def test_not_applicable_without_a_step(self):
        plugin, item = self._native_plugin()
        self.assertIsNone(plugin._native_cagg_series('avg', 0, 1000, None, item))
        self.assertIsNone(plugin._native_cagg_series('avg', 0, 1000, 0, item))

    def test_not_applicable_when_item_not_cagg_covered(self):
        plugin = self.plugin()  # mode 'plugin'
        item = self.sh.return_item('main.num')
        self.assertIsNone(plugin._native_cagg_series('avg', 0, 1000, 100, item))

    def test_not_applicable_when_nothing_predates_raw_floor(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=0):
            self.assertIsNone(plugin._native_cagg_series('avg', 0, 1000, 100, item))

    def test_queries_cagg_for_the_portion_predating_raw_floor(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=500):
            with mock.patch.object(plugin, '_fetchall', return_value=[(0, 1.0), (200, 2.0)]) as fetchall:
                result = plugin._native_cagg_series('avg', 0, 1000, 200, item)
        self.assertEqual([(0, 1.0), (200, 2.0)], result)
        stmt, params = fetchall.call_args.args
        self.assertIn('log_cagg_3600s', stmt)
        self.assertIn('(bucket - (bucket % :step)) AS out_bucket', stmt)
        self.assertIn('GROUP BY out_bucket', stmt)
        self.assertIn('SUM(sum_val_duration) / SUM(sum_duration)', stmt)
        self.assertEqual(0, params['time_start'])
        self.assertEqual(500, params['time_end'])  # clipped to oldest, not the full requested iend
        self.assertEqual(200, params['step'])

    def test_returns_none_when_cagg_query_finds_no_rows(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=500):
            with mock.patch.object(plugin, '_fetchall', return_value=[]):
                result = plugin._native_cagg_series('avg', 0, 1000, 200, item)
        self.assertIsNone(result)

    def test_step_finer_than_cagg_interval_still_returns_real_rows_no_synthesis(self):
        # No special case needed - GROUP BY never fabricates empty buckets,
        # confirmed against plain sqlite semantics (see the conversation
        # this implements). A 1-minute step against hourly cagg rows just
        # returns the real rows, each in its own sub-bucket.
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=10_000_000):
            with mock.patch.object(plugin, '_fetchall', return_value=[(0, 1.0), (3600000, 2.0)]) as fetchall:
                result = plugin._native_cagg_series('avg', 0, 7200000, 60000, item)
        self.assertEqual([(0, 1.0), (3600000, 2.0)], result)
        _, params = fetchall.call_args.args
        self.assertEqual(60000, params['step'])


class TestSeriesUsesNativeCaggSupplement(TestDatabaseBase):
    def test_native_tuples_prepended_to_raw_tuples(self):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item_obj = self.sh.return_item('main.num')
        item_obj.conf['database_maxage'] = 30
        item_obj.conf['database_maxage_action'] = 'avg'
        item_obj.conf['database_maxage_interval'] = '1h'
        plugin._items_with_maxage = [item_obj]
        fake_logs = {'tuples': [(500, 9.0)], 'item': item_obj, 'istart': 0, 'iend': 1000, 'step': 100, 'count': 100}
        with mock.patch.object(plugin, '_fetch_log', return_value=fake_logs):
            with mock.patch.object(plugin, '_native_cagg_series', return_value=[(0, 1.0)]) as native:
                result = plugin._series('avg', 0, 1000, item='main.num')
        native.assert_called_once_with('avg', 0, 1000, 100, item_obj)
        # (1000, 9.0) is _series()'s own pre-existing end-boundary append
        # (end != 'now' extends the last value forward to iend) - unrelated
        # to native routing, confirms prepending composes correctly with it.
        self.assertEqual([(0, 1.0), (500, 9.0), (1000, 9.0)], result['series'])

    def test_no_native_tuples_leaves_raw_series_unchanged(self):
        plugin = self.plugin()  # mode 'plugin' - native path never applicable
        item_obj = self.sh.return_item('main.num')
        fake_logs = {'tuples': [(500, 9.0)], 'item': item_obj, 'istart': 0, 'iend': 1000, 'step': 100, 'count': 100}
        with mock.patch.object(plugin, '_fetch_log', return_value=fake_logs):
            result = plugin._series('avg', 0, 1000, item='main.num')
        self.assertEqual([(500, 9.0), (1000, 9.0)], result['series'])


class TestNativeCaggCount(TestDatabaseBase):
    def _native_plugin(self):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 30
        item.conf['database_maxage_action'] = 'avg'
        item.conf['database_maxage_interval'] = '1h'
        plugin._items_with_maxage = [item]
        return plugin, item

    def test_not_applicable_when_item_not_cagg_covered(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.assertIsNone(plugin._native_cagg_count(item, 1, None, None))

    def test_not_applicable_when_whole_range_already_raw_covered(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=100):
            self.assertIsNone(plugin._native_cagg_count(item, 1, 200, None))

    def test_sums_countall_for_open_ended_start(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=500):
            with mock.patch.object(plugin, '_fetchall', return_value=[(42,)]) as fetchall:
                result = plugin._native_cagg_count(item, 1, None, None)
        self.assertEqual(42, result)
        stmt, params = fetchall.call_args.args
        self.assertIn('SUM(countall_value)', stmt)
        self.assertNotIn('time_start', params)  # no lower bound in the query at all
        self.assertEqual(500, params['time_end'])

    def test_clips_cagg_end_to_requested_time_end_when_narrower(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=500):
            with mock.patch.object(plugin, '_fetchall', return_value=[(10,)]) as fetchall:
                plugin._native_cagg_count(item, 1, 0, 200)
        _, params = fetchall.call_args.args
        self.assertEqual(200, params['time_end'])  # requested end is narrower than oldest

    def test_returns_zero_not_none_when_cagg_has_no_rows_in_range(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=500):
            with mock.patch.object(plugin, '_fetchall', return_value=[(None,)]):
                result = plugin._native_cagg_count(item, 1, None, None)
        self.assertEqual(0, result)


class TestReadLogCountUsesNativeCaggSupplement(TestDatabaseBase):
    def test_adds_cagg_count_to_raw_count_in_native_mode(self):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item = self.sh.return_item('main.num')
        item_id = plugin.id(item, create=True)
        # _item_for_id() mocked directly, not via _fetchall - _fetchall is
        # also what _item_for_id() itself would use for its own name
        # lookup, so mocking it globally would make that lookup return the
        # same (unrelated) raw-count row instead of a real item name.
        with mock.patch.object(plugin, '_fetchall', return_value=[(3,)]):
            with mock.patch.object(plugin, '_item_for_id', return_value=item):
                with mock.patch.object(plugin, '_native_cagg_count', return_value=7) as native:
                    result = plugin.readLogCount(item_id)
        native.assert_called_once()
        self.assertEqual(10, result)

    def test_plugin_mode_never_calls_native_cagg_count(self):
        plugin = self.plugin()  # mode 'plugin'
        item = self.sh.return_item('main.num')
        item_id = plugin.id(item, create=True)
        with mock.patch.object(plugin, '_fetchall', return_value=[(3,)]):
            with mock.patch.object(plugin, '_native_cagg_count') as native:
                result = plugin.readLogCount(item_id)
        native.assert_not_called()
        self.assertEqual(3, result)

    def test_native_mode_falls_back_to_raw_count_when_supplement_not_applicable(self):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item = self.sh.return_item('main.num')
        item_id = plugin.id(item, create=True)
        with mock.patch.object(plugin, '_fetchall', return_value=[(3,)]):
            with mock.patch.object(plugin, '_native_cagg_count', return_value=None):
                result = plugin.readLogCount(item_id)
        self.assertEqual(3, result)
