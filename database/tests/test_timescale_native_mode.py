#!/usr/bin/env python3
"""Tests for timescale_native_aggregation - continuous-aggregate-based
aggregation and (optionally) native chunk-drop retention, replacing
compact_maxage() on PostgreSQL (psycopg2/psycopg) only.
"""

import contextlib
import types
from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class _SpyDB:
    """Records every execute() call's prepared SQL + params, without
    touching a real connection - same pattern as the hypertable/compression
    spies, duplicated locally by existing convention in this test package."""

    def __init__(self, fail_on=None):
        self.executed = []  # list of (stmt, params) tuples
        self._fail_on = fail_on or ()

    def connected(self):
        return True

    def setup(self, queries):
        pass

    @contextlib.contextmanager
    def transaction(self):
        yield object()

    def execute(self, stmt, params=(), cur=None):
        self.executed.append((stmt, params))
        for needle in self._fail_on:
            if needle in stmt:
                raise RuntimeError(f'simulated failure for statement containing {needle!r}')


class TestTimescaleAggregationModeConfig(TestDatabaseBase):
    def test_defaults_to_plugin_mode(self):
        plugin = self.plugin()
        self.assertFalse(plugin._timescale_native_aggregation)

    def test_native_mode_accepted_when_configured(self):
        fake_driver = types.SimpleNamespace(paramstyle='pyformat', __name__='psycopg2')
        with mock.patch('lib.db.importlib.import_module', return_value=fake_driver):
            plugin = self.plugin(driver='psycopg2', timescale_native_aggregation=True)
        self.assertTrue(plugin._timescale_native_aggregation)

    def test_native_mode_falls_back_to_plugin_on_non_psycopg_driver(self):
        # Must actually fall back (not just warn-and-leave-set, like
        # timescale_hypertable/timescale_compress do) - leaving native
        # aggregation set-but-ignored on sqlite3/mysql would silently disable
        # remove_older_than_maxage() (gated off when native aggregation is
        # on) with no native replacement able to run either, losing maxage
        # handling entirely.
        plugin = self.plugin(timescale_native_aggregation=True)  # default driver: sqlite3
        self.assertFalse(plugin._timescale_native_aggregation)

    def test_native_retention_disabled_by_default(self):
        plugin = self.plugin()
        self.assertFalse(plugin._timescale_native_retention)

    def test_native_retention_enabled_when_configured(self):
        plugin = self.plugin(timescale_native_retention=True)
        self.assertTrue(plugin._timescale_native_retention)


class TestSchedulerGatedOffInNativeMode(TestDatabaseBase):
    def test_remove_old_not_registered_in_native_mode(self):
        fake_driver = types.SimpleNamespace(paramstyle='pyformat', __name__='psycopg2')
        with mock.patch('lib.db.importlib.import_module', return_value=fake_driver):
            plugin = self.plugin(driver='psycopg2', timescale_native_aggregation=True, default_maxage=90)
        with mock.patch.object(plugin, 'scheduler_add') as scheduler_add:
            plugin._start_schedulers()
        names = [call.args[0] for call in scheduler_add.call_args_list]
        self.assertNotIn('Remove old', names)

    def test_remove_old_still_registered_in_plugin_mode(self):
        plugin = self.plugin(default_maxage=90)  # native aggregation defaults to False
        with mock.patch.object(plugin, 'scheduler_add') as scheduler_add:
            plugin._start_schedulers()
        names = [call.args[0] for call in scheduler_add.call_args_list]
        self.assertIn('Remove old', names)


class TestEnableTimescaleNativeAggregation(TestDatabaseBase):
    def test_registers_integer_now_function_first(self):
        plugin = self.plugin()
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_native_aggregation()

        func_stmt, _ = spy.executed[0]
        set_func_stmt, _ = spy.executed[1]
        self.assertIn('CREATE OR REPLACE FUNCTION log_time_now', func_stmt)
        self.assertIn('set_integer_now_func', set_func_stmt)

    def test_already_set_integer_now_func_is_tolerated_not_fatal(self):
        # set_integer_now_func() is not idempotent - errors on every call
        # after the first, even re-registering the same function (found live
        # against the real testbed, from an earlier prototyping session's
        # leftover registration). Must be treated as success, not a failure
        # that aborts native mode on every restart after the first one.
        class _AlreadySetDB(_SpyDB):
            def execute(self, stmt, params=(), cur=None):
                self.executed.append((stmt, params))
                if 'set_integer_now_func' in stmt:
                    raise RuntimeError('custom time function already set for hypertable "log"')

        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 30
        item.conf['database_maxage_action'] = 'avg'
        item.conf['database_maxage_interval'] = '1h'
        plugin._items_with_maxage = [item]
        spy = _AlreadySetDB()
        plugin._db = spy
        plugin._enable_timescale_native_aggregation()  # must not raise, must still create the cagg

        cagg_stmts = [stmt for stmt, _ in spy.executed if 'CREATE MATERIALIZED VIEW' in stmt]
        self.assertEqual(1, len(cagg_stmts))

    def test_integer_now_function_failure_is_non_fatal_and_creates_no_caggs(self):
        plugin = self.plugin()
        spy = _SpyDB(fail_on=['CREATE OR REPLACE FUNCTION'])
        plugin._db = spy
        plugin._enable_timescale_native_aggregation()  # must not raise
        self.assertEqual(1, len(spy.executed), 'must not attempt set_integer_now_func after the function failed')

    def test_creates_one_cagg_per_distinct_interval(self):
        plugin = self.plugin()
        item_1h = self.sh.return_item('main.num')
        item_1h.conf['database_maxage'] = 30
        item_1h.conf['database_maxage_action'] = 'avg'
        item_1h.conf['database_maxage_interval'] = '1h'
        item_1d = self.sh.return_item('main.bool')
        item_1d.conf['database_maxage'] = 30
        item_1d.conf['database_maxage_action'] = 'duty_cycle'
        item_1d.conf['database_maxage_interval'] = '24h'
        plugin._items_with_maxage = [item_1h, item_1d]
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_native_aggregation()

        cagg_stmts = [stmt for stmt, _ in spy.executed if 'CREATE MATERIALIZED VIEW' in stmt]
        self.assertEqual(2, len(cagg_stmts))
        self.assertTrue(any('log_cagg_3600s' in s for s in cagg_stmts))
        self.assertTrue(any('log_cagg_86400s' in s for s in cagg_stmts))

    def test_items_sharing_an_interval_produce_only_one_cagg(self):
        plugin = self.plugin()
        item_a = self.sh.return_item('main.num')
        item_a.conf['database_maxage'] = 30
        item_a.conf['database_maxage_action'] = 'avg'
        item_a.conf['database_maxage_interval'] = '1h'
        item_b = self.sh.return_item('main.bool')
        item_b.conf['database_maxage'] = 5
        item_b.conf['database_maxage_action'] = 'duty_cycle'
        item_b.conf['database_maxage_interval'] = '1h'
        plugin._items_with_maxage = [item_a, item_b]
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_native_aggregation()

        cagg_stmts = [stmt for stmt, _ in spy.executed if 'CREATE MATERIALIZED VIEW' in stmt]
        self.assertEqual(1, len(cagg_stmts))

    def test_delete_action_items_are_skipped_entirely(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 30
        item.conf['database_maxage_action'] = 'delete'
        item.conf['database_maxage_interval'] = '1h'
        plugin._items_with_maxage = [item]
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_native_aggregation()

        cagg_stmts = [stmt for stmt, _ in spy.executed if 'CREATE MATERIALIZED VIEW' in stmt]
        self.assertEqual(0, len(cagg_stmts))


class TestCreateNativeCagg(TestDatabaseBase):
    def test_creates_cagg_wrapper_view_and_refresh_policy(self):
        plugin = self.plugin()
        spy = _SpyDB()
        plugin._db = spy
        plugin._create_native_cagg('log', 3600000)

        self.assertEqual(3, len(spy.executed))
        cagg_stmt, _ = spy.executed[0]
        view_stmt, _ = spy.executed[1]
        policy_stmt, _ = spy.executed[2]
        self.assertIn('CREATE MATERIALIZED VIEW IF NOT EXISTS log_cagg_3600s', cagg_stmt)
        self.assertIn('WITH NO DATA', cagg_stmt)
        self.assertIn('first(val_str, time)', cagg_stmt)
        self.assertIn('last(val_bool, time)', cagg_stmt)
        self.assertIn('CREATE OR REPLACE VIEW log_cagg_3600s_final', view_stmt)
        self.assertIn('sum_val_duration / NULLIF(sum_duration, 0) AS avg_value', view_stmt)
        self.assertIn('sum_val_bool_duration / NULLIF(sum_duration, 0) AS duty_cycle_value', view_stmt)
        self.assertIn("add_continuous_aggregate_policy('log_cagg_3600s'", policy_stmt)
        self.assertIn('end_offset => 3600000', policy_stmt)

    def test_wrapper_view_creation_failure_is_non_fatal_and_skips_policy(self):
        plugin = self.plugin()
        spy = _SpyDB(fail_on=['CREATE OR REPLACE VIEW'])
        plugin._db = spy
        plugin._create_native_cagg('log', 3600000)  # must not raise
        self.assertEqual(2, len(spy.executed), 'must not attempt add_continuous_aggregate_policy after view failed')


class TestEnableTimescaleNativeRetention(TestDatabaseBase):
    def test_drop_after_uses_longest_maxage_plus_chunk_interval(self):
        plugin = self.plugin(timescale_chunk_interval='168h')  # 604800000ms
        item_short = self.sh.return_item('main.num')
        item_short.conf['database_maxage'] = 5
        item_long = self.sh.return_item('main.bool')
        item_long.conf['database_maxage'] = 90
        plugin._items_with_maxage = [item_short, item_long]
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_native_retention()

        stmt, params = spy.executed[0]
        self.assertIn('add_retention_policy', stmt)
        self.assertEqual(90 * 86400000 + 604800000, params['drop_after_ms'])

    def test_default_maxage_considered_as_a_floor(self):
        plugin = self.plugin(default_maxage=90, timescale_chunk_interval='168h')
        item = self.sh.return_item('main.num')
        item.conf['database_maxage'] = 5
        plugin._items_with_maxage = [item]
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_native_retention()

        _, params = spy.executed[0]
        self.assertEqual(90 * 86400000 + 604800000, params['drop_after_ms'])

    def test_skips_with_warning_when_nothing_configures_a_maxage(self):
        # Not asserting the warning log itself - same effective-level caveat
        # as test_timescale_hypertable.py's identical documented case.
        plugin = self.plugin()
        plugin._items_with_maxage = []  # base test fixture's own maxage items must not count here
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_native_retention()
        self.assertEqual(0, len(spy.executed))
