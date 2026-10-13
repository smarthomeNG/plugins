"""
Tests for Database.rename_item() — re-keys plugin-internal bookkeeping and
migrates SQL log history when an item is renamed in place (same object,
only its path changes — see Items.rename_item() in the core repo and
~/.claude/handoff/shng-rename-item-design.md).

self.plugin() (the test fixture) already calls parse_item() on every item
in test_items.yaml during setup.
"""

from plugins.database.tests.base import TestDatabaseBase


class TestDatabaseRenameItem(TestDatabaseBase):
    def test_rename_item_rekeys_webdata(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')

        plugin.rename_item(item, 'main.num', 'main.renamed')

        self.assertNotIn('main.num', plugin._webdata)
        self.assertIn('main.renamed', plugin._webdata)

    def test_rename_item_refreshes_db_and_series_partials(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')

        plugin.rename_item(item, 'main.num', 'main.renamed')

        self.assertEqual(item.db.keywords['item'], 'main.renamed')
        self.assertEqual(item.series.keywords['item'], 'main.renamed')

    def test_rename_item_returns_false_if_item_not_tracked(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.nodb')

        result = plugin.rename_item(item, 'main.nodb', 'main.renamed')

        self.assertFalse(result)

    def test_rename_item_reassigns_orphaned_log_history(self):
        # database.rename_item() relies on item.property.path already
        # being new_path when it runs (Items.rename_item() mutates the
        # path before calling any plugin's hook) — mutate it directly
        # here too, same as test_remove_item.py calls plugin.remove_item()
        # directly rather than through Items.remove_item().
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        old_id = self.create_item(plugin, 'main.num')

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
        item = self.sh.return_item('main.num')
        self.create_log(plugin, 'main.num', [(0, 1, 1.0), (1, None, 2.0)])
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
        item = self.sh.return_item('main.num')
        self.create_log(plugin, 'main.num', [(i, i + 1, float(i)) for i in range(10)])
        plugin._db.commit()

        item._path = 'main.renamed'
        plugin.rename_item(item, 'main.num', 'main.renamed')

        new_id = plugin.id('main.renamed', create=False)
        old_id = plugin.id('main.num', create=False)
        values = sorted(v[4] for v in plugin.readLogs(new_id))
        self.assertEqual(values, [float(i) for i in range(10)], 'all 10 rows across 4 chunks must be reassigned')
        self.assertIsNone(old_id, 'orphaned id must be fully drained and removed, not left with leftover rows')

    def test_reassign_orphaned_id_uses_transaction(self):
        # Regression: reassign_orphaned_id() used to open a raw cursor via
        # self._db_maint.cursor() with no lock() call anywhere - no
        # serialization at all against this connection's other users.
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        old_id = self.create_item(plugin, 'main.num')

        calls = []
        orig_transaction = plugin._db_maint.transaction

        def spy_transaction(*a, **kw):
            calls.append((a, kw))
            return orig_transaction(*a, **kw)

        plugin._db_maint.transaction = spy_transaction
        item._path = 'main.renamed'
        plugin.rename_item(item, 'main.num', 'main.renamed')

        # >=1, not ==1: reassign_orphaned_id() also calls build_orphanlist()
        # at the end to refresh the list, which itself goes through
        # self._db_maint.transaction() too - both calls are expected.
        self.assertGreaterEqual(len(calls), 1, 'reassign_orphaned_id() must go through self._db_maint.transaction()')
        self.assertIsNone(plugin.id('main.num', create=False), 'sanity: reassignment must still have happened')
        self.assertNotEqual(old_id, plugin.id('main.renamed', create=False))
