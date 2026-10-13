#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""Pause item handling of the modbus_tcp plugin."""

import unittest
from unittest.mock import patch

from lib.model.smartplugin import SmartPlugin
from tests.pause_item_contract import PauseItemContract


class TestModbusTcpPauseItem(PauseItemContract, unittest.TestCase):
    CLASS_PATH = 'plugins.modbus_tcp'
    CLASS_NAME = 'modbus_tcp'
    PARAMS = {'host': '127.0.0.1', 'port': 5020}
    MULTI_INSTANCE = True


class TestModbusTcpLegacyCorePauseItem(TestModbusTcpPauseItem):
    """Same instance contract on 1.11 cores without the new helper."""

    def setUp(self):
        super().setUp()
        self._helper_patch = patch.object(SmartPlugin, '_handle_pause_item')
        self._helper_patch.start()
        delattr(SmartPlugin, '_handle_pause_item')
        self.addCleanup(self._helper_patch.stop)


if __name__ == '__main__':
    unittest.main(verbosity=2)
