from unittest import mock

from plugins.database.tests.base import TestDatabaseBase


class TestDatabaseOrphans(TestDatabaseBase):
    def test_remove_orphan_items_with_zero_orphans_finishes_cleanly(self):
        # cleanup() arms remove_orphan unconditionally; the scheduler then
        # calls remove_orphan_items() every cycle. With no orphans in the
        # database the worklist stays empty - that must end the cleanup,
        # not crash it (a crash here leaves remove_orphan armed and kills
        # every subsequent maxage cycle).
        plugin = self.plugin()
        plugin.cleanup()

        plugin.remove_orphan_items()

        self.assertFalse(plugin.remove_orphan)

    def test_remove_orphan_items_deletes_orphan_and_finishes(self):
        # One orphan row (no matching item in the tree) - a cleanup pass
        # over it must delete it and disarm remove_orphan once the list is
        # drained.
        plugin = self.plugin()
        plugin.insertItem('no.such.item')
        plugin.build_orphanlist()
        self.assertEqual(['no.such.item'], plugin.orphanlist)
        plugin.cleanup()

        plugin.remove_orphan_items()

        self.assertIsNone(plugin.readItem('no.such.item'))
        self.assertFalse(plugin.remove_orphan)

    def test_build_orphanlist_reports_failure_when_db_maint_unavailable(self):
        # build_orphanlist() must report a failed attempt (e.g. DB not
        # connected), not just return None and leave self.orphanlist == []
        # indistinguishable from a successful check that genuinely found no
        # orphans - callers (run(), _dump(), remove_orphan_items()) must be
        # able to tell the difference.
        plugin = self.plugin()
        plugin.insertItem('no.such.item')  # a real orphan the failed attempt must not report

        with mock.patch.object(plugin._db_maint, 'transaction', side_effect=ConnectionError('not connected')):
            result = plugin.build_orphanlist()

        self.assertFalse(result)
        self.assertFalse(plugin._orphanlist_built)
        self.assertEqual([], plugin.orphanlist)

    def test_build_orphanlist_clears_stale_built_flag_on_repeat_failure(self):
        # A rebuild attempt wipes self.orphanlist unconditionally before
        # trying - if that attempt then fails, _orphanlist_built must not
        # be left True from an earlier successful build, or callers would
        # trust this attempt's now-empty list as "confirmed no orphans".
        plugin = self.plugin()
        plugin.insertItem('no.such.item')
        self.assertTrue(plugin.build_orphanlist())
        self.assertTrue(plugin._orphanlist_built)

        with mock.patch.object(plugin._db_maint, 'transaction', side_effect=ConnectionError('not connected')):
            result = plugin.build_orphanlist()

        self.assertFalse(result)
        self.assertFalse(plugin._orphanlist_built)

    def test_remove_orphan_items_does_not_disarm_when_list_build_fails(self):
        # remove_orphan_items() must not trust an empty self.orphanlist
        # unconditionally - if build_orphanlist() just failed (DB not
        # connected), that empty list must not be misread as "confirmed no
        # orphans", disarming remove_orphan and abandoning the cleanup
        # instead of retrying on the next cycle.
        plugin = self.plugin()
        plugin.insertItem('no.such.item')  # a real orphan the failed attempt must not report
        plugin.cleanup()

        with mock.patch.object(plugin._db_maint, 'transaction', side_effect=ConnectionError('not connected')):
            plugin.remove_orphan_items()

        self.assertTrue(plugin.remove_orphan, 'a failed check must not disarm cleanup - retry next cycle')
        self.assertFalse(plugin._orphanlist_built)

    def test_dump_retries_orphanlist_build_until_it_succeeds(self):
        # run()'s one-shot build_orphanlist() call has no retry of its own
        # if the DB isn't connected yet at startup - _dump() (already on
        # its own scheduled cycle) picks it up instead of a bespoke retry
        # loop, and stops once it succeeds.
        plugin = self.plugin()
        plugin._orphanlist_built = False

        with mock.patch.object(plugin, 'build_orphanlist', wraps=plugin.build_orphanlist) as spy:
            plugin._dump()
            self.assertEqual(1, spy.call_count, '_dump() must retry the list build while unbuilt')
            self.assertTrue(plugin._orphanlist_built)

            plugin._dump()
            self.assertEqual(1, spy.call_count, '_dump() must stop retrying once the build has succeeded')

    def test_run_logs_warning_but_still_starts_when_db_unavailable(self):
        # run() must not discard _initialize_db()'s return value and
        # proceed silently either way - a DB outage at startup must produce
        # a clear signal distinct from a normal clean start, without
        # crashing/exiting, matching every other self-healing entry point
        # in this plugin (id()/_dump()/_query() all tolerate this the same
        # way).
        plugin = self.plugin()

        with mock.patch.object(plugin, '_initialize_db', return_value=False):
            with self.assertLogs(plugin.logger, level='WARNING') as logs:
                plugin.run()

        self.assertTrue(any('not connected at startup' in m for m in logs.output))
        self.assertTrue(plugin.alive, 'a DB outage at startup must not prevent the plugin from starting')

    def test_reassign_orphaned_id_commits_each_chunk_separately(self):
        # The LIMIT-batched UPDATE loop exists to keep individual
        # transactions bounded - running every batch inside one wrapping
        # transaction() defeats that (one giant transaction anyway).
        # Each chunk must commit on its own; the orphan item row is only
        # deleted after all its log rows have moved.
        plugin = self.plugin()
        orphan_id = plugin.insertItem('old.path')
        new_id = self.create_item(plugin, 'main.num')
        rows = 45  # max_reassign_logentries is 20 -> 3 chunks
        for i in range(rows):
            plugin.insertLog(orphan_id, time=i * 1000, duration=1000, val=float(i), it='num')

        calls = []
        orig_transaction = plugin._db_maint.transaction

        def spy_transaction(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        with mock.patch.object(plugin._db_maint, 'transaction', side_effect=spy_transaction):
            with mock.patch.object(plugin, 'build_orphanlist'):
                plugin.reassign_orphaned_id(orphan_id, new_id)

        self.assertEqual(rows, plugin.readLogCount(new_id))
        self.assertEqual(0, plugin.readLogCount(orphan_id))
        self.assertIsNone(plugin.readItem(orphan_id))
        self.assertGreaterEqual(
            len(calls), 4, 'each UPDATE chunk and the final item delete must run as separate transactions'
        )
