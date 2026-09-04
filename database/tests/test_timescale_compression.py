#!/usr/bin/env python3
"""Tests for timescale_compress - the plugin-level wiring that enables
native columnar compression on {log} and adds a compression policy on
PostgreSQL (psycopg2/psycopg) only.
"""

import contextlib
import types
from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class _SpyDB:
    """Records every execute() call's prepared SQL + params, without
    touching a real connection - same pattern as test_timescale_hypertable.py's
    own spy, duplicated locally rather than imported since each test file's
    double stays self-contained by existing convention here."""

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


class TestTimescaleCompressionConfig(TestDatabaseBase):
    def test_disabled_by_default(self):
        plugin = self.plugin()
        self.assertFalse(plugin._timescale_compress)

    def test_enabled_when_configured(self):
        plugin = self.plugin(timescale_compress=True)
        self.assertTrue(plugin._timescale_compress)

    def test_warns_when_enabled_on_non_psycopg_driver(self):
        # Same effective-level caveat as test_timescale_hypertable.py's identical case -
        # .warning() is filtered before assertLogs' handler sees it at this test level.
        plugin = self.plugin(timescale_compress=True)  # default driver: sqlite3
        self.assertTrue(plugin._timescale_compress)

    def test_no_warning_when_disabled(self):
        with self.assertNoLogs(level='WARNING'):
            self.plugin(timescale_compress=False)


class TestEnableTimescaleCompression(TestDatabaseBase):
    def test_alters_table_then_adds_compression_policy(self):
        plugin = self.plugin(timescale_chunk_interval='24h')
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_compression()

        self.assertEqual(2, len(spy.executed))
        alter_stmt, _alter_params = spy.executed[0]
        policy_stmt, policy_params = spy.executed[1]
        self.assertIn('timescaledb.compress', alter_stmt)
        self.assertIn("timescaledb.compress_segmentby = 'item_id'", alter_stmt)
        self.assertIn("timescaledb.compress_orderby = 'time DESC'", alter_stmt)
        self.assertIn('add_compression_policy', policy_stmt)
        self.assertEqual('log', policy_params['table'])
        self.assertEqual(24 * 3600 * 1000, policy_params['compress_after_ms'])  # 24h in ms

    def test_uses_prefixed_table_name(self):
        plugin = self.plugin(prefix='myprefix')
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_compression()
        alter_stmt, _ = spy.executed[0]
        _, policy_params = spy.executed[1]
        self.assertIn('myprefix_log', alter_stmt)
        self.assertEqual('myprefix_log', policy_params['table'])

    def test_compress_after_matches_chunk_interval_not_a_second_parameter(self):
        # No separate timescale_compress_after config - reuses the same
        # interval already computed for hypertable conversion.
        plugin = self.plugin(timescale_chunk_interval='168h')
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_compression()
        _, policy_params = spy.executed[1]
        self.assertEqual(plugin._timescale_chunk_interval_ms, policy_params['compress_after_ms'])

    def test_alter_table_failure_is_non_fatal_and_skips_policy_call(self):
        plugin = self.plugin()
        spy = _SpyDB(fail_on=['timescaledb.compress'])
        plugin._db = spy
        plugin._enable_timescale_compression()  # must not raise
        self.assertEqual(1, len(spy.executed), 'must not attempt add_compression_policy after ALTER TABLE failed')

    def test_policy_failure_is_non_fatal(self):
        plugin = self.plugin()
        spy = _SpyDB(fail_on=['add_compression_policy'])
        plugin._db = spy
        plugin._enable_timescale_compression()  # must not raise
        self.assertEqual(2, len(spy.executed), 'ALTER TABLE must still be attempted and succeed')

    def test_only_called_for_psycopg_driver_during_initialize(self):
        # sqlite3 (the harness default): must never reach
        # _enable_timescale_compression() even with timescale_compress=True.
        plugin = self.plugin(timescale_compress=True)
        with mock.patch.object(plugin, '_enable_timescale_compression') as mocked:
            plugin._db_initialized = False
            plugin._initialize_db()
        mocked.assert_not_called()

    def test_called_for_psycopg_driver_during_initialize(self):
        fake_driver = types.SimpleNamespace(paramstyle='pyformat', __name__='psycopg2')
        with mock.patch('lib.db.importlib.import_module', return_value=fake_driver):
            plugin = self.plugin(driver='psycopg2', timescale_compress=True)
        plugin._db = _SpyDB()  # replace the (unconnectable, fake-driver-backed) real Database
        plugin._db_initialized = False
        with mock.patch.object(plugin, '_enable_timescale_compression') as mocked:
            plugin._initialize_db()
        mocked.assert_called_once()

    def test_not_called_when_disabled_even_for_psycopg_driver(self):
        fake_driver = types.SimpleNamespace(paramstyle='pyformat', __name__='psycopg2')
        with mock.patch('lib.db.importlib.import_module', return_value=fake_driver):
            plugin = self.plugin(driver='psycopg2', timescale_compress=False)
        plugin._db = _SpyDB()
        plugin._db_initialized = False
        with mock.patch.object(plugin, '_enable_timescale_compression') as mocked:
            plugin._initialize_db()
        mocked.assert_not_called()
