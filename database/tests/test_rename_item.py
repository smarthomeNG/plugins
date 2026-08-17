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
