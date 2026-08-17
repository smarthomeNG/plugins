#!/usr/bin/env python3
"""
End-to-end test for jsonread: parse_item() registers an item with a
jsonread_filter attribute, poll_device() fetches the configured URL (here
a file:// URL onto a fixture, exercising the plugin's real FileAdapter
wiring) and writes the resolved value onto the item itself.

This is the layer the bug fixed in this branch actually broke: jq engine
unit tests in isolation wouldn't have caught a wiring problem between
parse_item/poll_device and the item, and the engine tests alone don't
prove the plugin ever calls item(value) with the right value for a real
item.conf attribute.
"""

import os
import unittest

import tests.common as common
from tests.mock.core import MockSmartHome

from .base import JsonreadTestBase

common.register_shng_log_levels()

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), 'fixtures')


class TestPluginEndToEnd(JsonreadTestBase, unittest.TestCase):
    def setUp(self):
        self.sh = MockSmartHome()
        self.sh.with_items_from(os.path.join(FIXTURES_DIR, 'test_items.yaml'))
        from plugins.jsonread import JSONREAD

        JSONREAD._parameters = {'url': f'file://{FIXTURES_DIR}/fronius.json', 'cycle': 30}
        self.plg = JSONREAD(self.sh)
        for item in self.sh.return_items():
            self.plg.parse_item(item)

    def test_poll_device_fills_simple_numeric_item(self):
        self.plg.poll_device()

        item = self.sh.return_item('fronius_smartmeter.current_phase_1')
        self.assertEqual(item(), 0.455)

    def test_poll_device_fills_nested_string_item(self):
        self.plg.poll_device()

        item = self.sh.return_item('fronius_smartmeter.manufacturer')
        self.assertEqual(item(), 'Fronius')

    def test_poll_device_fills_second_array_element(self):
        self.plg.poll_device()

        item = self.sh.return_item('fronius_smartmeter.second_reading_current')
        self.assertEqual(item(), 0.073)

    def test_poll_device_leaves_unmatched_filter_at_default(self):
        self.plg.poll_device()

        item = self.sh.return_item('fronius_smartmeter.unmatched')
        # str-type default is '' — item(None) on a str item casts via
        # cast_str, confirming "no match" doesn't raise and doesn't
        # silently leave stale data from a previous poll either.
        self.assertEqual(item(), '')


if __name__ == '__main__':
    unittest.main(verbosity=2)
