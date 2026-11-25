#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Pause item handling of the sonos plugin."""

import unittest

from tests.pause_item_contract import PauseItemContract


class TestSonosPauseItem(PauseItemContract, unittest.TestCase):
    CLASS_PATH = 'plugins.sonos'
    CLASS_NAME = 'Sonos'

    def test_soco_version_is_read(self) -> None:
        self.assertRegex(self.plugin.SoCo_version, r'^\d+\.\d+')


if __name__ == '__main__':
    unittest.main(verbosity=2)
