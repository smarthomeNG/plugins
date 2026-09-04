#!/usr/bin/env python3
"""Tests for friendly driver aliases (e.g. 'mysql', 'timescaledb') resolved
to a real, importable DB-API2 module name before self.driver is used
anywhere - see Database._resolve_driver_alias()/_resolve_postgres_driver_alias().
"""

from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class TestDriverAliases(TestDatabaseBase):
    def test_real_module_names_pass_through_unchanged(self):
        plugin = self.plugin(driver='sqlite3')
        self.assertEqual('sqlite3', plugin.driver)

    def test_mysql_alias_resolves_to_pymysql(self):
        plugin = self.plugin(driver='mysql', connect={'host': 'h', 'user': 'u', 'passwd': 'p', 'db': 'd'})
        self.assertEqual('pymysql', plugin.driver)

    def test_mariadb_alias_resolves_to_pymysql(self):
        plugin = self.plugin(driver='mariadb', connect={'host': 'h', 'user': 'u', 'passwd': 'p', 'db': 'd'})
        self.assertEqual('pymysql', plugin.driver)

    def test_alias_is_case_insensitive(self):
        plugin = self.plugin(driver='MySQL', connect={'host': 'h', 'user': 'u', 'passwd': 'p', 'db': 'd'})
        self.assertEqual('pymysql', plugin.driver)

    def test_postgres_alias_prefers_installed_psycopg2(self):
        # This venv has psycopg2 but not psycopg (v3) - a real, unmocked
        # probe, not just asserting the preference order in isolation.
        plugin = self.plugin(driver='postgres', connect={'host': 'h', 'user': 'u', 'password': 'p', 'database': 'd'})
        self.assertEqual('psycopg2', plugin.driver)

    def test_timescaledb_alias_resolves_like_postgres(self):
        plugin = self.plugin(driver='timescaledb', connect={'host': 'h', 'user': 'u', 'password': 'p', 'database': 'd'})
        self.assertEqual('psycopg2', plugin.driver)

    def test_postgres_alias_falls_back_to_psycopg_when_psycopg2_missing(self):
        # Calls the resolution method directly rather than going through
        # full plugin construction - a global importlib.import_module mock
        # would also intercept lib.db.Database's own (separate) import of
        # the already-resolved driver name, breaking construction itself.
        plugin = self.plugin()  # normal sqlite3 plugin, just to get an instance

        def fake_import(name):
            if name == 'psycopg2':
                raise ImportError('simulated: psycopg2 not installed')
            return mock.DEFAULT

        with mock.patch('plugins.database.importlib.import_module', side_effect=fake_import):
            resolved = plugin._resolve_postgres_driver_alias('postgresql')
        self.assertEqual('psycopg', resolved)

    def test_postgres_alias_falls_back_to_psycopg2_when_neither_installed(self):
        # Not asserting the warning log itself - this logger's effective
        # test level (31) sits above stdlib WARNING (30), so .warning()
        # calls are filtered before assertLogs ever sees them; see
        # test_timescale_hypertable.py's identical, already-documented case.
        plugin = self.plugin()
        with mock.patch('plugins.database.importlib.import_module', side_effect=ImportError('simulated')):
            resolved = plugin._resolve_postgres_driver_alias('timescale')
        self.assertEqual('psycopg2', resolved)
