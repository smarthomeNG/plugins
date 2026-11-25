#!/usr/bin/env python3
"""Tests for _reconcile_native_retention_reality() - checks database
reality against config (not the other way round) since a TimescaleDB
retention policy runs as the server's own background job, independent of
shng, and config can drift from what's actually active. 2026-09-04 design
decision: self-correct the two data-safety-critical mismatches rather than
merely warn, since a wrong auto-correction is a recoverable inconvenience
while leaving the unsafe combination running is not.
"""

from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class TestReconcileNativeRetentionReality(TestDatabaseBase):
    def test_active_and_configured_but_plugin_mode_forces_native(self):
        plugin = self.plugin()
        plugin._timescale_native_retention = True
        plugin._timescale_native_aggregation = False
        with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=True):
            with self.assertLogs(level='CRITICAL'):
                plugin._reconcile_native_retention_reality()
        self.assertTrue(plugin._timescale_native_aggregation)

    def test_active_and_configured_and_already_native_does_nothing(self):
        plugin = self.plugin()
        plugin._timescale_native_retention = True
        plugin._timescale_native_aggregation = True
        with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=True):
            with mock.patch.object(plugin, '_disable_native_retention_policy') as disable:
                plugin._reconcile_native_retention_reality()
        disable.assert_not_called()
        self.assertTrue(plugin._timescale_native_aggregation)

    def test_active_but_configured_off_removes_the_policy(self):
        plugin = self.plugin()
        plugin._timescale_native_retention = False
        with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=True):
            with mock.patch.object(plugin, '_disable_native_retention_policy', return_value=True) as disable:
                with self.assertLogs(level='CRITICAL'):
                    plugin._reconcile_native_retention_reality()
        disable.assert_called_once()
        self.assertFalse(plugin._timescale_native_aggregation)  # removal succeeded, no fallback needed

    def test_active_configured_off_removal_fails_falls_back_to_native(self):
        # Fail-safe: the policy is still active either way once removal
        # fails, so the run still needs to be safe under it.
        plugin = self.plugin()
        plugin._timescale_native_retention = False
        plugin._timescale_native_aggregation = False
        with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=True):
            with mock.patch.object(plugin, '_disable_native_retention_policy', return_value=False):
                with self.assertLogs(level='CRITICAL'):
                    plugin._reconcile_native_retention_reality()
        self.assertTrue(plugin._timescale_native_aggregation)

    def test_not_active_but_configured_with_plugin_mode_refuses(self):
        plugin = self.plugin()
        plugin._timescale_native_retention = True
        plugin._timescale_native_aggregation = False
        with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=False):
            with self.assertLogs(level='CRITICAL'):
                plugin._reconcile_native_retention_reality()
        self.assertFalse(plugin._timescale_native_retention)

    def test_not_active_configured_and_already_native_does_nothing(self):
        # The normal, safe, aligned state - no warning, no mutation.
        plugin = self.plugin()
        plugin._timescale_native_retention = True
        plugin._timescale_native_aggregation = True
        with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=False):
            plugin._reconcile_native_retention_reality()
        self.assertTrue(plugin._timescale_native_retention)
        self.assertTrue(plugin._timescale_native_aggregation)

    def test_not_active_and_not_configured_does_nothing(self):
        plugin = self.plugin()
        plugin._timescale_native_retention = False
        with mock.patch.object(plugin, '_native_retention_active_in_db', return_value=False):
            plugin._reconcile_native_retention_reality()
        self.assertFalse(plugin._timescale_native_retention)

    def test_check_failure_is_non_fatal(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_native_retention_active_in_db', side_effect=RuntimeError('boom')):
            plugin._reconcile_native_retention_reality()  # must not raise


class TestNativeRetentionActiveInDb(TestDatabaseBase):
    def test_true_when_job_found(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_fetchall', return_value=[(1,)]) as fetchall:
            self.assertTrue(plugin._native_retention_active_in_db())
        stmt, params = fetchall.call_args.args
        self.assertIn("proc_name = 'policy_retention'", stmt)
        self.assertEqual('log', params['table'])

    def test_false_when_no_job_found(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_fetchall', return_value=[]):
            self.assertFalse(plugin._native_retention_active_in_db())


class TestDisableNativeRetentionPolicy(TestDatabaseBase):
    def test_calls_remove_retention_policy(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_db') as db:
            with self.assertLogs(level='CRITICAL'):
                plugin._disable_native_retention_policy()
        stmt = db.execute.call_args.args[0]
        self.assertIn('remove_retention_policy', stmt)

    def test_failure_still_logs_critical_and_returns_false(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_db') as db:
            db.execute.side_effect = RuntimeError('boom')
            with self.assertLogs(level='CRITICAL') as logs:
                result = plugin._disable_native_retention_policy()  # must not raise
        self.assertFalse(result)
        self.assertTrue(any('could not remove' in m for m in logs.output))

    def test_success_returns_true(self):
        plugin = self.plugin()
        with mock.patch.object(plugin, '_db'):
            with self.assertLogs(level='CRITICAL'):
                result = plugin._disable_native_retention_policy()
        self.assertTrue(result)
