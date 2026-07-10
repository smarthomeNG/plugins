from plugins.uzsu.tests.base import TestUZSUBase


class TestUZSUBasic(TestUZSUBase):
    def test_plugin_constructs_and_parses_items(self):
        plugin = self.plugin()
        self.assertIn(self.sh.return_item('main.temp.uzsu'), plugin._items)
        self.assertIn(self.sh.return_item('main.lamp.uzsu'), plugin._items)

    def test_parsed_item_has_default_structure(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.temp.uzsu')
        self.assertEqual(plugin._items[item]['active'], False)
        self.assertEqual(plugin._items[item]['list'], [])

    def test_activate_sets_active_flag(self):
        plugin = self.plugin()
        item = self.sh.return_item('main.temp.uzsu')
        plugin._items[item]['list'] = [{'value': 21.5, 'active': True, 'time': '07:00', 'rrule': 'FREQ=DAILY'}]
        self.assertTrue(plugin.activate(True, item))
        self.assertTrue(plugin._items[item]['active'])
        self.assertFalse(plugin.activate(False, item))
        self.assertFalse(plugin._items[item]['active'])

    def test_get_type_returns_target_item_type(self):
        plugin = self.plugin()
        num_item = self.sh.return_item('main.temp.uzsu')
        bool_item = self.sh.return_item('main.lamp.uzsu')
        self.assertEqual(plugin._get_type(num_item), 'num')
        self.assertEqual(plugin._get_type(bool_item), 'bool')
