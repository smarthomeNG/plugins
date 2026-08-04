#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests that on_connect() does not crash when no item is bound to
'general.verbose'. get_items_for_mapping() returns [] (never None) when
unbound, so `[...][0]` raised IndexError on every connection unless a
user happened to configure an item for that specific mapping.
"""

import unittest
from unittest.mock import MagicMock

from plugins.oppo import oppo


def _make_plugin(bound_items=None):
    plugin = object.__new__(oppo)
    plugin.logger = MagicMock()
    plugin.send_command = MagicMock()
    plugin.get_items_for_mapping = MagicMock(return_value=bound_items or [])
    return plugin


class TestOnConnectVerboseGuard(unittest.TestCase):
    def test_no_bound_item_does_not_raise(self):
        plugin = _make_plugin(bound_items=[])
        # must not raise IndexError
        plugin.on_connect()
        plugin.send_command.assert_not_called()

    def test_bound_item_still_activates_verbose(self):
        item = MagicMock()
        item.property.value = 2
        plugin = _make_plugin(bound_items=[item])
        plugin.on_connect()
        plugin.send_command.assert_called_once_with('general.verbose', 2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
