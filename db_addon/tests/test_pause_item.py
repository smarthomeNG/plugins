#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Pause item handling of the db_addon plugin."""

import unittest

from tests.pause_item_contract import PauseItemContract


class TestDbAddonPauseItem(PauseItemContract, unittest.TestCase):
    CLASS_PATH = 'plugins.db_addon'
    CLASS_NAME = 'DatabaseAddOn'


if __name__ == '__main__':
    unittest.main(verbosity=2)
