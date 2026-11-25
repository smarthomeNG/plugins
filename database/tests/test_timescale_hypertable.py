#!/usr/bin/env python3
"""Tests for timescale_hypertable - the plugin-level wiring that activates
the TimescaleDB extension and converts {log} into a hypertable on
PostgreSQL (psycopg2/psycopg) only.
"""

import contextlib
import types
from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class _SpyDB:
    """Records every execute() call's prepared SQL + params, without
    touching a real connection - _enable_timescale_hypertable() is
    exercised directly here, not through full plugin construction (which
    would need a real, connectable driver to get past _db.setup() first)."""

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


class TestTimescaleHypertableConfig(TestDatabaseBase):
    def test_disabled_by_default(self):
        plugin = self.plugin()
        self.assertFalse(plugin._timescale_hypertable)

    def test_enabled_when_configured(self):
        plugin = self.plugin(timescale_hypertable=True)
        self.assertTrue(plugin._timescale_hypertable)

    def test_no_warning_when_enabled_on_non_psycopg_driver(self):
        # No warning here (unlike sqlite_wal_mode/timescale_compress) - the
        # parameter now defaults to True, so being True on a non-psycopg
        # driver is everyone's normal resting state, not a misconfiguration.
        with self.assertNoLogs(level='WARNING'):
            plugin = self.plugin(timescale_hypertable=True)  # default driver: sqlite3
        self.assertTrue(plugin._timescale_hypertable)

    def test_no_warning_when_disabled(self):
        with self.assertNoLogs(level='WARNING'):
            self.plugin(timescale_hypertable=False)

    def test_default_chunk_interval_is_168h_in_milliseconds(self):
        plugin = self.plugin()
        self.assertEqual(168 * 3600 * 1000, plugin._timescale_chunk_interval_ms)

    def test_custom_chunk_interval_parsed(self):
        plugin = self.plugin(timescale_chunk_interval='24h')
        self.assertEqual(24 * 3600 * 1000, plugin._timescale_chunk_interval_ms)

    def test_invalid_chunk_interval_falls_back_to_168h(self):
        # Same effective-level caveat as test_warns_when_enabled_on_non_psycopg_driver.
        plugin = self.plugin(timescale_chunk_interval='not-a-duration')
        self.assertEqual(168 * 3600 * 1000, plugin._timescale_chunk_interval_ms)

    def test_chunk_interval_has_no_days_suffix_support(self):
        # shtime.to_seconds() doesn't accept 'd' - same constraint
        # database_maxage_interval already documents. '7d' must fail
        # parsing and fall back, not silently misinterpret the number.
        plugin = self.plugin(timescale_chunk_interval='7d')
        self.assertEqual(168 * 3600 * 1000, plugin._timescale_chunk_interval_ms)


class TestEnableTimescaleHypertable(TestDatabaseBase):
    def test_creates_extension_then_hypertable(self):
        plugin = self.plugin(timescale_chunk_interval='24h')
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_hypertable()

        self.assertEqual(2, len(spy.executed))
        ext_stmt, ext_params = spy.executed[0]
        ht_stmt, ht_params = spy.executed[1]
        self.assertIn('CREATE EXTENSION IF NOT EXISTS timescaledb', ext_stmt)
        self.assertIn('create_hypertable', ht_stmt)
        self.assertIn('migrate_data => TRUE', ht_stmt)
        self.assertEqual('log', ht_params['table'])
        self.assertEqual(24 * 3600 * 1000, ht_params['chunk_ms'])  # 24h in ms

    def test_uses_prefixed_table_name(self):
        plugin = self.plugin(prefix='myprefix')
        spy = _SpyDB()
        plugin._db = spy
        plugin._enable_timescale_hypertable()
        _, ht_params = spy.executed[1]
        self.assertEqual('myprefix_log', ht_params['table'])

    def test_extension_failure_is_non_fatal_and_skips_hypertable_call(self):
        plugin = self.plugin()
        spy = _SpyDB(fail_on=['CREATE EXTENSION'])
        plugin._db = spy
        plugin._enable_timescale_hypertable()  # must not raise
        self.assertEqual(1, len(spy.executed), 'must not attempt create_hypertable after extension activation failed')

    def test_hypertable_failure_is_non_fatal(self):
        plugin = self.plugin()
        spy = _SpyDB(fail_on=['create_hypertable'])
        plugin._db = spy
        plugin._enable_timescale_hypertable()  # must not raise
        self.assertEqual(2, len(spy.executed), 'extension activation must still be attempted and succeed')

    def test_only_called_for_psycopg_driver_during_initialize(self):
        # sqlite3 (the harness default): must never reach
        # _enable_timescale_hypertable() even with timescale_hypertable=True -
        # test_warns_when_enabled_on_non_psycopg_driver already covers the
        # warning; this proves the SQL-issuing method itself is skipped.
        plugin = self.plugin(timescale_hypertable=True)
        with mock.patch.object(plugin, '_enable_timescale_hypertable') as mocked:
            plugin._db_initialized = False
            plugin._initialize_db()
        mocked.assert_not_called()

    def test_called_for_psycopg_driver_during_initialize(self):
        fake_driver = types.SimpleNamespace(paramstyle='pyformat', __name__='psycopg2')
        with mock.patch('lib.db.importlib.import_module', return_value=fake_driver):
            plugin = self.plugin(driver='psycopg2', timescale_hypertable=True)
        plugin._db = _SpyDB()  # replace the (unconnectable, fake-driver-backed) real Database
        plugin._db_initialized = False
        with mock.patch.object(plugin, '_enable_timescale_hypertable') as mocked:
            plugin._initialize_db()
        mocked.assert_called_once()
