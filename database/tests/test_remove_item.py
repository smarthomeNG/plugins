"""
Tests for Database.remove_item() — cleans up plugin-internal bookkeeping for
an item before it's deleted/recreated (e.g. by Items.remove_item() or the
admin UI's item-edit feature). Mirrors what parse_item() registers.

self.plugin() (the test fixture) already calls parse_item() on every item in
test_items.yaml during setup — tests below rely on that, not a second
explicit parse_item() call (which would double-register list-based state).
"""

from plugins.database.tests.base import TestDatabaseBase


class TestDatabaseRemoveItem(TestDatabaseBase):
    def test_remove_item_clears_webdata(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.assertIn(item.property.path, plugin._webdata)

        plugin.remove_item(item)

        self.assertNotIn(item.property.path, plugin._webdata)

    def test_remove_item_clears_handled_items(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.assertIn(item, plugin._handled_items)

        plugin.remove_item(item)

        self.assertNotIn(item, plugin._handled_items)

    def test_remove_item_clears_buffer(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        self.assertIn(item, plugin._buffer)

        plugin.remove_item(item)

        self.assertNotIn(item, plugin._buffer)

    def test_remove_item_clears_items_with_maxage(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.maxage')
        self.assertIn(item, plugin._items_with_maxage)

        plugin.remove_item(item)

        self.assertNotIn(item, plugin._items_with_maxage)

    def test_remove_item_returns_false_for_untracked_item(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.nodb')

        self.assertFalse(plugin.remove_item(item))

    def test_remove_item_flushes_pending_buffer_to_db(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.num')
        plugin._buffer_insert(item, [(1000, None, 5)])

        plugin.remove_item(item)

        count = plugin.readLogCount(plugin.id(item, False))
        self.assertGreater(count, 0)
