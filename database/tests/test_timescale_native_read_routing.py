#!/usr/bin/env python3
"""Tests for _single()'s native-mode cagg read-path routing - deliberately
narrow: only handles a query range that predates the raw floor entirely
(see _native_cagg_single()'s own docstring for why straddling ranges,
_series(), and readLogCount() are out of scope for this pass).
"""

import types
from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class TestNativeCaggView(TestDatabaseBase):
    def test_none_when_mode_is_plugin(self):
        plugin = self.plugin()  # mode defaults to 'plugin'
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 30
        plugin._items_with_maxage = [item]
        self.assertIsNone(plugin._native_cagg_view(item))

    def test_none_when_item_not_relevant(self):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item = self.sh.return_item('main.num')
        plugin._items_with_maxage = []  # item not covered at all
        self.assertIsNone(plugin._native_cagg_view(item))

    def test_none_when_action_is_delete(self):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 30
        item.conf['database_maxage_action'] = 'delete'
        plugin._items_with_maxage = [item]
        self.assertIsNone(plugin._native_cagg_view(item))

    def test_resolves_cagg_name_from_interval(self):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 30
        item.conf['database_maxage_action'] = 'avg'
        item.conf['database_maxage_interval'] = '1h'
        plugin._items_with_maxage = [item]
        self.assertEqual('log_cagg_3600s', plugin._native_cagg_view(item))


class TestNativeCaggSingle(TestDatabaseBase):
    def _native_plugin(self, action='avg', interval='1h'):
        # _native_cagg_single()/_single() take a string path (matching
        # _single()'s real calling convention) - self.items.return_item()
        # only resolves paths, not item objects, so tests must pass 'main.num'
        # here, not the item object itself (plugin._items_with_maxage/the
        # relevance check still needs the real item object).
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 30
        item.conf['database_maxage_action'] = action
        item.conf['database_maxage_interval'] = interval
        plugin._items_with_maxage = [item]
        plugin.id(item, create=True)  # _native_cagg_single() needs a real item_id, not None
        return plugin, 'main.num'

    def test_not_applicable_for_a_func_with_no_cagg_column(self):
        plugin, item = self._native_plugin()
        # 'diff'/'raw'/threshold-'count' have no cagg equivalent at all -
        # see _NATIVE_CAGG_SINGLE_EXPR's own docstring.
        self.assertIsNone(plugin._native_cagg_single('diff', 0, 'now', item))
        self.assertIsNone(plugin._native_cagg_single('raw', 0, 'now', item))

    def test_not_applicable_when_item_not_cagg_covered(self):
        plugin = self.plugin()  # mode 'plugin' - no cagg exists at all
        item = self.sh.return_item('main.num')
        self.assertIsNone(plugin._native_cagg_single('avg', 0, 'now', item))

    def test_not_applicable_when_no_raw_data_ever_existed(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=None):
            self.assertIsNone(plugin._native_cagg_single('avg', 0, 'now', item))

    def test_not_applicable_when_range_touches_raw_territory(self):
        plugin, item = self._native_plugin()
        # oldest raw row is at t=5000; querying up to 'now' (far later) means
        # part of the range is still raw-covered - must use the precise raw
        # path, not a coarser cagg stitch (see the method's own docstring).
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=5000):
            self.assertIsNone(plugin._native_cagg_single('avg', 0, 'now', item))

    def test_queries_cagg_when_entire_range_predates_raw_floor(self):
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=10_000_000):
            with mock.patch.object(plugin, '_fetchall', return_value=[(4.5,)]) as fetchall:
                result = plugin._native_cagg_single('avg', 0, 1000, item)
        self.assertEqual((4.5,), result)
        stmt, params = fetchall.call_args.args
        self.assertIn('log_cagg_3600s', stmt)
        self.assertIn('SUM(sum_val_duration) / SUM(sum_duration)', stmt)
        self.assertEqual(0, params['time_start'])
        self.assertEqual(1000, params['time_end'])

    def test_returns_none_wrapped_in_tuple_when_cagg_has_no_matching_rows(self):
        # Distinguishes "cagg path taken, genuinely no data" (a 1-tuple
        # wrapping None) from "cagg path not applicable at all" (bare None) -
        # _single() must fall through to the raw path only in the latter case.
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=10_000_000):
            with mock.patch.object(plugin, '_fetchall', return_value=[]):
                result = plugin._native_cagg_single('avg', 0, 1000, item)
        self.assertEqual((None,), result)

    def test_each_action_maps_to_its_own_cagg_expression(self):
        plugin, item = self._native_plugin()
        expected = {
            'avg': 'SUM(sum_val_duration) / SUM(sum_duration)',
            'integrate': 'SUM(sum_val_duration)',
            'sum': 'SUM(sum_value)',
            'min': 'MIN(min_value)',
            'max': 'MAX(max_value)',
            'countall': 'SUM(countall_value)',
            'on': 'SUM(sum_val_bool_duration) / SUM(sum_duration)',
            'duty_cycle': 'SUM(sum_val_bool_duration) / SUM(sum_duration)',
        }
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=10_000_000):
            for func, expr in expected.items():
                with mock.patch.object(plugin, '_fetchall', return_value=[(1,)]) as fetchall:
                    plugin._native_cagg_single(func, 0, 1000, item)
                stmt, _ = fetchall.call_args.args
                self.assertIn(expr, stmt)

    def test_min_max_countall_integrate_sum_not_precision_rounded(self):
        # Only avg/on/duty_cycle go through _precision_query() (ROUND(...)) -
        # matches _single()'s own raw-path 'queries' dict exactly.
        plugin, item = self._native_plugin()
        with mock.patch.object(plugin._log_store, 'oldest_time', return_value=10_000_000):
            with mock.patch.object(plugin, '_fetchall', return_value=[(1,)]) as fetchall:
                plugin._native_cagg_single('sum', 0, 1000, item)
        stmt, _ = fetchall.call_args.args
        self.assertNotIn('ROUND', stmt)


class TestSingleUsesNativeCaggWhenApplicable(TestDatabaseBase):
    def test_single_returns_cagg_value_directly_when_applicable(self):
        plugin = self.plugin()
        plugin._timescale_native_aggregation = True
        item_obj = self.sh.return_item('main.num')
        item_obj.conf['database_maxage'] = 30
        item_obj.conf['database_maxage_action'] = 'avg'
        item_obj.conf['database_maxage_interval'] = '1h'
        plugin._items_with_maxage = [item_obj]
        with mock.patch.object(plugin, '_native_cagg_single', return_value=(7.5,)) as native:
            result = plugin._single('avg', 0, 1000, item='main.num')
        native.assert_called_once()
        self.assertEqual(7.5, result)

    def test_single_falls_through_to_raw_path_when_not_applicable(self):
        plugin = self.plugin()  # mode 'plugin' - native path never applicable
        with mock.patch.object(plugin, '_native_cagg_single', return_value=None) as native:
            plugin._single('avg', 0, 'now', item='main.num')
        native.assert_called_once()
