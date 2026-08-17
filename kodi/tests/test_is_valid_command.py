#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests that is_valid_command(read=None) actually checks both the 'read'
and 'write' special-command lists, matching its own docstring ("check for
read (True) or write (False), or both (None)"). The ternary
'read' if read else 'write' treated None the same as False, so a
read=None call only ever consulted the 'write' list.
"""

import unittest
from unittest.mock import MagicMock

from plugins.kodi import kodi


def _make_plugin():
    plugin = object.__new__(kodi)
    plugin.logger = MagicMock()
    plugin._special_commands = {'read': ['info.player'], 'write': ['status.update']}
    return plugin


class TestIsValidCommandReadNone(unittest.TestCase):
    def test_read_none_matches_read_only_special_command(self):
        plugin = _make_plugin()
        self.assertTrue(plugin.is_valid_command('info.player'))

    def test_read_none_matches_write_only_special_command(self):
        plugin = _make_plugin()
        self.assertTrue(plugin.is_valid_command('status.update'))


if __name__ == '__main__':
    unittest.main(verbosity=2)
