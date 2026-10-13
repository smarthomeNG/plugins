#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Pause item handling of the russound plugin."""

import unittest

from tests.pause_item_contract import PauseItemContract


class TestRussoundPauseItem(PauseItemContract, unittest.TestCase):
    CLASS_PATH = 'plugins.russound'
    CLASS_NAME = 'Russound'


if __name__ == '__main__':
    unittest.main(verbosity=2)
