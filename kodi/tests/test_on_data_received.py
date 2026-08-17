#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests that on_data_received() actually stops (as its own log message
claims) when data is not a dict, instead of falling through into
'error' in data.
"""

import unittest
from unittest.mock import MagicMock

from plugins.kodi import kodi


def _make_plugin():
    plugin = object.__new__(kodi)
    plugin.logger = MagicMock()
    plugin.suspended = False
    plugin._dispatch_callback = MagicMock()
    plugin._activeplayers = []
    plugin._playerid = 0
    plugin._connection = MagicMock()
    return plugin


class TestOnDataReceivedNonDictGuard(unittest.TestCase):
    def test_none_data_does_not_raise(self):
        plugin = _make_plugin()
        # must not raise TypeError from `'error' in None`
        plugin.on_data_received('test', None, 'some.command')

    def test_int_data_does_not_raise(self):
        plugin = _make_plugin()
        plugin.on_data_received('test', 42, 'some.command')


class TestCapitalizeGuard(unittest.TestCase):
    def test_get_active_players_missing_type_does_not_raise(self):
        plugin = _make_plugin()
        data = {'id': 1, 'result': [{'playerid': 1}]}  # no 'type' key
        # must not raise AttributeError from None.capitalize()
        plugin.on_data_received('test', data, 'Player.GetActivePlayers')

    def test_get_item_missing_type_does_not_raise(self):
        plugin = _make_plugin()
        data = {'id': 1, 'result': {'item': {'title': 'Some Title'}}}  # no 'type' key
        plugin.on_data_received('test', data, 'Player.GetItem')


class TestTitleArtistConcatGuard(unittest.TestCase):
    def test_missing_title_and_label_with_artist_does_not_raise(self):
        plugin = _make_plugin()
        data = {
            'id': 1,
            'result': {'item': {'type': 'audio', 'artist': ['Some Artist']}},  # no title, no label
        }
        # must not raise TypeError from None + ' - ' + str
        plugin.on_data_received('test', data, 'Player.GetItem')


if __name__ == '__main__':
    unittest.main(verbosity=2)
