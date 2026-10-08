#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Pause item handling of the modbus_tcp plugin."""

import unittest

from tests.pause_item_contract import PauseItemContract


class TestModbusTcpPauseItem(PauseItemContract, unittest.TestCase):
    CLASS_PATH = 'plugins.modbus_tcp'
    CLASS_NAME = 'modbus_tcp'
    PARAMS = {'host': '127.0.0.1', 'port': 5020}
    MULTI_INSTANCE = True


if __name__ == '__main__':
    unittest.main(verbosity=2)
