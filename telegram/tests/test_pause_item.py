#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Pause item handling of the telegram plugin."""

import unittest

from tests.pause_item_contract import PauseItemContract


class TestTelegramPauseItem(PauseItemContract, unittest.TestCase):
    CLASS_PATH = 'plugins.telegram'
    CLASS_NAME = 'Telegram'
    PARAMS = {'token': '123:abc'}
    MULTI_INSTANCE = True


if __name__ == '__main__':
    unittest.main(verbosity=2)
