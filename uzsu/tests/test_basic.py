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


class TestUZSUWithoutSun(TestUZSUBase):
    """sh.sun is False when core has no lat/lon or no ephemeris backend: plugin must still load and
    handle everything not related to sunrise/sunset."""

    def test_plugin_loads_and_parses_items(self):
        plugin = self.plugin(with_sun=False)
        self.assertIsNot(getattr(plugin, '_init_complete', True), False)
        self.assertIn(self.sh.return_item('main.temp.uzsu'), plugin._items)

    def test_fixed_time_entry_is_scheduled(self):
        plugin = self.plugin_with_entry('main.temp.uzsu', {'value': 18.0, 'time': '07:00'}, with_sun=False)
        item = self.sh.return_item('main.temp.uzsu')
        nxt, value, _ = plugin._get_time(plugin._items[item]['list'][0], 'next', item, 0, 'test')
        self.assertEqual(nxt.hour, 7)
        self.assertEqual(value, 18.0)

    def test_sun_entry_is_ignored_and_warned_about_once(self):
        plugin = self.plugin_with_entry('main.temp.uzsu', {'value': 18.0, 'time': 'sunset'}, with_sun=False)
        item = self.sh.return_item('main.temp.uzsu')
        entry = plugin._items[item]['list'][0]
        self.assertEqual(plugin._get_time(entry, 'next', item, 0, 'test'), (None, None, None))
        self.assertEqual(plugin._get_time(entry, 'previous', item, 0, 'test'), (None, None, None))
        self.assertEqual(plugin._sun_warned, {(str(item), 'sunset')})

    def test_series_with_sun_boundary_is_ignored(self):
        plugin = self.plugin(with_sun=False)
        mydict = {
            'series': {
                'timeSeriesMin': 'sunrise',
                'timeSeriesMax': '12:00',
                'timeSeriesIntervall': '00:30',
                'timeSeriesCount': '',
            }
        }
        self.assertIsNone(plugin._series_get_time(mydict, 'next'))

    def test_sun_calculations_report_failure_instead_of_raising(self):
        plugin = self.plugin(with_sun=False)
        item = self.sh.return_item('main.temp.uzsu')
        self.assertFalse(plugin._get_sun4week(item))
        self.assertIsNot(plugin._update_sun(item), True)
