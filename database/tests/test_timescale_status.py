#!/usr/bin/env python3
"""Tests for timescale_status() and its three reality-check helpers -
what's actually active against the real database, independent of what
timescale_hypertable/timescale_native_aggregation/timescale_native_retention
say in plugin.yaml. Used by shngadmin dashboard's database-properties
widget (see modules/admin/api_database.py in the core repo).
"""

from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class TestHypertableActiveInDb(TestDatabaseBase):
    def test_true_when_catalog_has_a_row(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_fetchall', return_value=[(1,)]) as fetchall:
            self.assertTrue(plugin._hypertable_active_in_db())
        query, params = fetchall.call_args[0]
        self.assertIn('timescaledb_information.hypertables', query)
        self.assertEqual('log', params['table'])

    def test_false_when_catalog_has_no_row(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_fetchall', return_value=[]):
            self.assertFalse(plugin._hypertable_active_in_db())

    def test_uses_prefixed_table_name(self):
        plugin = self.plugin(prefix='myprefix')
        with mock.patch.object(plugin, '_fetchall', return_value=[]) as fetchall:
            plugin._hypertable_active_in_db()
        _, params = fetchall.call_args[0]
        self.assertEqual('myprefix_log', params['table'])


class TestNativeCaggActiveInDb(TestDatabaseBase):
    def test_true_when_catalog_has_a_row(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_fetchall', return_value=[(1,)]) as fetchall:
            self.assertTrue(plugin._native_cagg_active_in_db())
        query, params = fetchall.call_args[0]
        self.assertIn('timescaledb_information.continuous_aggregates', query)
        self.assertEqual('log', params['table'])

    def test_false_when_catalog_has_no_row(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_fetchall', return_value=[]):
            self.assertFalse(plugin._native_cagg_active_in_db())


class TestTimescaleStatus(TestDatabaseBase):
    def test_empty_for_non_psycopg_driver(self):
        plugin = self.plugin()  # harness default: sqlite3
        self.assertEqual({}, plugin.timescale_status())

    def test_reports_all_three_reality_checks(self):
        plugin = self.plugin()
        plugin.driver = 'psycopg2'
        with mock.patch.object(plugin, '_hypertable_active_in_db', return_value=True):
            with mock.patch.object(plugin, '_native_cagg_active_in_db', return_value=False):
                with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=True):
                    status = plugin.timescale_status()
        self.assertEqual({'hypertable': True, 'native_cagg': False, 'native_retention': True}, status)

    def test_reports_the_case_the_user_asked_about(self):
        # A hypertable with a native retention policy active in the database,
        # but never configured via timescale_native_aggregation/
        # timescale_native_retention - reality, not configured intent.
        plugin = self.plugin()
        plugin.driver = 'psycopg2'
        self.assertFalse(plugin._timescale_native_aggregation)
        self.assertFalse(plugin._timescale_native_retention)
        with mock.patch.object(plugin, '_hypertable_active_in_db', return_value=True):
            with mock.patch.object(plugin, '_native_cagg_active_in_db', return_value=True):
                with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=True):
                    status = plugin.timescale_status()
        self.assertEqual({'hypertable': True, 'native_cagg': True, 'native_retention': True}, status)

    def test_a_failed_check_reports_none_without_breaking_the_others(self):
        plugin = self.plugin()
        plugin.driver = 'psycopg2'
        with mock.patch.object(plugin, '_hypertable_active_in_db', side_effect=RuntimeError('relation does not exist')):
            with mock.patch.object(plugin, '_native_cagg_active_in_db', return_value=False):
                with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=False):
                    with self.assertLogs(plugin.logger, level='WARNING'):
                        status = plugin.timescale_status()
        self.assertIsNone(status['hypertable'])
        self.assertFalse(status['native_cagg'])
        self.assertFalse(status['native_retention'])

    def test_psycopg_alias_also_recognized(self):
        plugin = self.plugin()
        plugin.driver = 'psycopg'
        with mock.patch.object(plugin, '_hypertable_active_in_db', return_value=False):
            with mock.patch.object(plugin, '_native_cagg_active_in_db', return_value=False):
                with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=False):
                    status = plugin.timescale_status()
        self.assertEqual({'hypertable': False, 'native_cagg': False, 'native_retention': False}, status)


if __name__ == '__main__':
    import unittest

    unittest.main(verbosity=2)
