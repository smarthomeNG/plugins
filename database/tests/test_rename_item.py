"""
Tests for Database.rename_item() — re-keys plugin-internal bookkeeping and
migrates SQL log history when an item is renamed in place (same object,
only its path changes — see Items.rename_item() in the core repo and
~/.claude/handoff/shng-rename-item-design.md).

self.plugin() (the test fixture) already calls parse_item() on every item
in test_items.yaml during setup.
"""

from unittest import mock

from plugins.database.constants import BufferEntry
from plugins.database.tests.base import TestDatabaseBase


class TestDatabaseRenameItem(TestDatabaseBase):
    def test_rename_item_rekeys_webdata(self):
        plugin = self.plugin()
        item = self.sh.items.return_item('main.num')

        plugin.rename_item(item, 'main.num', 'main.renamed')

        self.assertNotIn('main.num', plugin._webdata)
        self.assertIn('main.renamed', plugin._webdata)

    def test_rename_item_refreshes_db_and_series_partials(self):
        plugin = self.plugin()
        item = self.sh.items.return_item('main.num')

        plugin.rename_item(item, 'main.num', 'main.renamed')

        self.assertEqual(item.db.keywords['item'], 'main.renamed')
        self.assertEqual(item.series.keywords['item'], 'main.renamed')

    def test_rename_item_returns_false_if_item_not_tracked(self):
        plugin = self.plugin()
        item = self.sh.items.return_item('main.nodb')

        result = plugin.rename_item(item, 'main.nodb', 'main.renamed')

        self.assertFalse(result)

    def test_rename_item_reassigns_orphaned_log_history(self):
        # database.rename_item() relies on item.property.path already
        # being new_path when it runs (Items.rename_item() mutates the
        # path before calling any plugin's hook) — mutate it directly
        # here too, same as test_remove_item.py calls plugin.remove_item()
        # directly rather than through Items.remove_item().
        plugin = self.plugin()
        item = self.sh.items.return_item('main.num')
        old_id = self.create_item(plugin, 'main.num')
        plugin.insertItem('main.renamed')

        item._path = 'main.renamed'
        plugin.rename_item(item, 'main.num', 'main.renamed')

        new_id = plugin.id('main.renamed', create=False)
        self.assertIsNotNone(new_id)
        self.assertNotEqual(old_id, new_id)
        # the orphaned old id's row is gone — merged into new_id, not left behind
        self.assertIsNone(plugin.id('main.num', create=False))

    def test_rename_item_reassigns_actual_log_entries_not_just_an_empty_row(self):
        # Exercises the UPDATE {log} ... LIMIT path inside
        # reassign_orphaned_id() — test_rename_item_reassigns_orphaned_log_history
        # has zero log entries, so that statement's while loop body never
        # actually runs there.
        plugin = self.plugin()
        item = self.sh.items.return_item('main.num')
        self.create_log(plugin, 'main.num', [(0, 1, 1.0), (1, None, 2.0)])
        plugin.insertItem('main.renamed')
        plugin._db.commit()  # reassign_orphaned_id() uses the separate _db_maint
        # connection — its writes would otherwise block on this connection's
        # uncommitted insert (SQLite allows only one writer at a time).

        item._path = 'main.renamed'
        plugin.rename_item(item, 'main.num', 'main.renamed')

        new_id = plugin.id('main.renamed', create=False)
        values = [v[4] for v in plugin.readLogs(new_id)]  # COL_LOG_VAL_NUM
        self.assertEqual(sorted(values), [1.0, 2.0])

    def test_reassign_orphaned_id_converges_across_multiple_chunks(self):
        # The UPDATE inside reassign_orphaned_id()'s while loop must match
        # on (item_id, time) via the existing UNIQUE KEY, not a
        # rowid-subquery ('WHERE rowid IN (SELECT rowid FROM {log} WHERE
        # item_id = :orphanid LIMIT :limit)') - MariaDB rejects LIMIT
        # directly inside IN(subquery), and {log} has no primary key, so
        # MySQL/MariaDB exposes no rowid for it under any name.
        # test_rename_item_reassigns_actual_log_entries_not_just_an_empty_
        # row only has 2 rows (one chunk, default max_reassign_logentries=
        # 20) - this test forces several loop iterations to confirm
        # convergence across chunk boundaries too.
        plugin = self.plugin()
        plugin.max_reassign_logentries = 3
        item = self.sh.items.return_item('main.num')
        self.create_log(plugin, 'main.num', [(i, i + 1, float(i)) for i in range(10)])
        plugin.insertItem('main.renamed')
        plugin._db.commit()

        item._path = 'main.renamed'
        plugin.rename_item(item, 'main.num', 'main.renamed')

        new_id = plugin.id('main.renamed', create=False)
        old_id = plugin.id('main.num', create=False)
        values = sorted(v[4] for v in plugin.readLogs(new_id))
        self.assertEqual(values, [float(i) for i in range(10)], 'all 10 rows across 4 chunks must be reassigned')
        self.assertIsNone(old_id, 'orphaned id must be fully drained and removed, not left with leftover rows')

    def test_rename_right_after_a_stop_run_cycle_still_moves_the_history(self):
        # Items.rename_item() brackets a rename with stop()/run(); a second rename soon after the first must not lose the history
        plugin = self.plugin()
        item = self.sh.items.return_item('main.num')
        self.create_log(plugin, 'main.num', [(0, 1, 1.0), (1, None, 2.0)])
        plugin._db.commit()
        plugin.stop()
        plugin.run()
        plugin.stop()

        item._path = 'main.renamed'
        plugin.rename_item(item, 'main.num', 'main.renamed')

        new_id = plugin.id('main.renamed', create=False)
        self.assertLessEqual({1.0, 2.0}, {v[4] for v in plugin.readLogs(new_id)})

    def test_rename_logs_an_error_when_the_history_cannot_be_moved(self):
        plugin = self.plugin()
        item = self.sh.items.return_item('main.num')
        self.create_item(plugin, 'main.num')
        plugin.insertItem('main.renamed')

        item._path = 'main.renamed'
        with mock.patch.object(plugin, '_ensure_db_maint', return_value=False):
            with self.assertLogs(plugin.logger, level='ERROR') as logs:
                plugin.rename_item(item, 'main.num', 'main.renamed')

        self.assertIn('main.num', logs.output[0])
        self.assertIn('main.renamed', logs.output[0])

    def test_reassign_orphaned_id_uses_transaction(self):
        # Regression: reassign_orphaned_id() used to open a raw cursor via
        # self._db_maint.cursor() with no lock() call anywhere - no
        # serialization at all against this connection's other users.
        plugin = self.plugin()
        item = self.sh.items.return_item('main.num')
        old_id = self.create_item(plugin, 'main.num')
        plugin.insertItem('main.renamed')

        calls = []
        orig_transaction = plugin._db_maint.transaction

        def spy_transaction(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        plugin._db_maint.transaction = spy_transaction
        item._path = 'main.renamed'
        plugin.rename_item(item, 'main.num', 'main.renamed')

        self.assertGreaterEqual(len(calls), 1, 'reassign_orphaned_id() must go through self._db_maint.transaction()')
        self.assertIsNone(plugin.id('main.num', create=False), 'sanity: reassignment must still have happened')
        self.assertNotEqual(old_id, plugin.id('main.renamed', create=False))


class TestRenameKeepsTheDatabaseId(TestDatabaseBase):
    """With no database row under the new name, a rename only changes the name of the item row: id and log rows stay."""

    def _rename(self, plugin, old, new):
        item = self.sh.items.return_item(old)
        item._path = new
        return item, plugin.rename_item(item, old, new)

    def test_the_item_keeps_its_id_under_the_new_name(self):
        plugin = self.plugin()
        old_id = self.create_item(plugin, 'main.num')

        self._rename(plugin, 'main.num', 'main.renamed')

        self.assertEqual(old_id, plugin.id('main.renamed', create=False))
        self.assertEqual('main.renamed', plugin.readItem(old_id)[1])  # COL_ITEM_NAME
        self.assertIsNone(plugin.id('main.num', create=False))

    def test_a_row_already_under_the_new_name_receives_the_history(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(0, 1, 1.0)])
        leftover_id = plugin.insertItem('main.renamed')
        plugin.insertLog(leftover_id, time=self.t(5), duration=None, val=9.0, it='num')
        plugin._db.commit()

        self._rename(plugin, 'main.num', 'main.renamed')

        self.assertEqual(leftover_id, plugin.id('main.renamed', create=False))
        self.assertEqual([1.0, 9.0], sorted(v[4] for v in plugin.readLogs(leftover_id)))
        self.assertEqual(1, [row[1] for row in plugin.readItems()].count('main.renamed'))
        self.assertIsNone(plugin.id('main.num', create=False))

    def test_the_log_history_is_readable_under_the_new_name_without_being_moved(self):
        plugin = self.plugin()
        old_id = self.create_item(plugin, 'main.num')
        self.create_log(plugin, 'main.num', [(i, i + 1, float(i)) for i in range(5)])

        self._rename(plugin, 'main.num', 'main.renamed')

        self.assertEqual(5, plugin.readLogCount(old_id))
        self.assertEqual([float(i) for i in range(5)], sorted(v[4] for v in plugin.readLogs(plugin.id('main.renamed'))))

    def test_entries_buffered_before_the_rename_are_written_under_the_same_id(self):
        plugin = self.plugin()
        old_id = self.create_item(plugin, 'main.num')
        item, _ = self._rename(plugin, 'main.num', 'main.renamed')
        plugin._buffer_mgr.push(item, BufferEntry(time=1000, duration=None, value=5))

        plugin._dump(finalize=True)

        self.assertIn(5, [v[4] for v in plugin.readLogs(old_id)])

    def test_a_failing_name_change_falls_back_to_moving_the_history(self):
        plugin = self.plugin()
        self.create_log(plugin, 'main.num', [(0, 1, 1.0), (1, None, 2.0)])
        plugin._db.commit()

        with mock.patch.object(plugin._item_store, 'rename', side_effect=RuntimeError('db gone')):
            self._rename(plugin, 'main.num', 'main.renamed')

        new_id = plugin.id('main.renamed', create=False)
        self.assertEqual([1.0, 2.0], sorted(v[4] for v in plugin.readLogs(new_id)))
        self.assertIsNone(plugin.id('main.num', create=False))
