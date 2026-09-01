#!/usr/bin/env python3
"""Tests for sqlite_wal_mode - the plugin-level wiring around lib.db.Database's
wal_mode (see tests/test_db.py::TestDbWalMode in the core repo for the
underlying journal-mode-switching behaviour itself, which isn't retested here).
"""

import os
import sqlite3

from plugins.database.tests.base import TestDatabaseBase


class TestWalModeWiring(TestDatabaseBase):
    def test_disabled_by_default(self):
        plugin = self.plugin()
        self.assertFalse(plugin._db._wal_mode)
        self.assertFalse(plugin._db_maint._wal_mode)

    def test_passed_to_both_connections_when_enabled(self):
        plugin = self.plugin(sqlite_wal_mode=True)
        self.assertTrue(plugin._db._wal_mode)
        self.assertTrue(plugin._db_maint._wal_mode)

    def test_actually_activates_wal_on_the_file(self):
        plugin = self.plugin(sqlite_wal_mode=True)
        plugin._db.connect()
        (mode,) = plugin._db.fetchone('PRAGMA journal_mode;')
        self.assertEqual('wal', str(mode).lower())

    def test_construction_survives_non_sqlite3_driver(self):
        # Not asserting the warning log itself here - this test environment's
        # effective logger level sits above stdlib WARNING, so .warning()
        # calls are filtered before assertLogs ever sees them (same
        # environment property noted in test_maxage_action.py). The
        # non-sqlite3 case must still not crash construction, and the flag
        # itself isn't forced off - _apply_wal_mode_locked() already makes
        # it a no-op per-connection regardless. Uses pymysql (a real,
        # importable driver) rather than a bogus name - a driver that fails
        # to import at all leaves the plugin instance partially constructed
        # (a separate, pre-existing characteristic unrelated to WAL), which
        # isn't what this test is after.
        plugin = self.plugin(sqlite_wal_mode=True, driver='pymysql')
        self.assertTrue(plugin._sqlite_wal_mode)


class TestExtractConnectValue(TestDatabaseBase):
    """Regression coverage for copy_databasefile()'s database_name lookup -
    it used to assume connect was a list of 'key:value' strings only,
    silently resolving to '' (and then failing) whenever connect was
    configured as a dict instead - a form lib.db.Database itself accepts."""

    def test_dict_connect(self):
        plugin = self.plugin()
        self.assertEqual('/path/to/db', plugin._extract_connect_value({'database': '/path/to/db'}, 'database'))

    def test_list_of_strings_connect(self):
        plugin = self.plugin()
        self.assertEqual(
            '/path/to/db', plugin._extract_connect_value(['database:/path/to/db', 'timeout:5'], 'database')
        )

    def test_list_of_dict_connect(self):
        plugin = self.plugin()
        self.assertEqual(
            '/path/to/db', plugin._extract_connect_value([{'database': '/path/to/db'}, {'timeout': 5}], 'database')
        )

    def test_missing_key_returns_empty_string(self):
        plugin = self.plugin()
        self.assertEqual('', plugin._extract_connect_value({'host': 'localhost'}, 'database'))
        self.assertEqual('', plugin._extract_connect_value([], 'database'))


class TestCopyDatabasefileWalSafety(TestDatabaseBase):
    def test_checkpoints_wal_data_before_copying(self):
        # Test harness's default connect is dict-style ({'database': path}) -
        # exercises the fix directly, no workaround needed.
        plugin = self.plugin(sqlite_wal_mode=True)
        plugin._db.connect()
        # Write directly via a second raw connection, bypassing the plugin's
        # own buffer/dump cycle - simulates data that reached the WAL file
        # but was never explicitly checkpointed before copy_databasefile() runs.
        raw = sqlite3.connect(self._db_file.name)
        raw.execute('CREATE TABLE IF NOT EXISTS wal_probe (v INT);')
        raw.execute('INSERT INTO wal_probe VALUES (42);')
        raw.commit()
        raw.close()

        dest = self.create_tmpfile()
        self.addCleanup(os.unlink, dest)
        plugin._copy_database_name = dest
        plugin.copy_databasefile()

        copied = sqlite3.connect(dest)
        (value,) = copied.execute('SELECT v FROM wal_probe;').fetchone()
        copied.close()
        self.assertEqual(
            42, value, 'copy must include data only checkpointed just before the copy, not yet in the main file'
        )

    def test_noop_and_no_crash_for_non_wal_file(self):
        plugin = self.plugin()  # sqlite_wal_mode default False
        plugin._db.connect()

        dest = self.create_tmpfile()
        self.addCleanup(os.unlink, dest)
        plugin._copy_database_name = dest
        plugin.copy_databasefile()  # must not raise
