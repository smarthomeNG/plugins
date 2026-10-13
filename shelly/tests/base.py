"""
Test harness for the shelly plugin.

The plugin is driven exclusively through its MQTT callbacks (announce, gen1 message); results
are observed on real items. Only the MQTT broker connection is replaced, by `FakeMqttModule`, and the
database plugin's per-item functions by `GapRecorder`.
"""

import logging
import os
import unittest
from unittest import mock

import lib.item
import lib.item.item

from tests import common
from tests.gap_recorder import GapRecorder
from tests.mock.core import MockSmartHome

from plugins.shelly import Shelly

if not hasattr(lib.item, 'Item'):
    lib.item.Item = lib.item.item.Item


class FakeMqttModule:
    """Stands in for the core 'mqtt' module so the plugin can initialize without a broker."""

    def get_broker_config(self) -> dict:
        return {}

    def __getattr__(self, name):
        return mock.MagicMock()


class FakeModules:
    """Stands in for `lib.module.Modules`, serving only the fake mqtt module."""

    @staticmethod
    def get_instance() -> 'FakeModules':
        return FakeModules()

    def get_module(self, name: str):
        return FakeMqttModule() if name == 'mqtt' else None


class ShellyTestBase(unittest.TestCase):
    ITEMS_FILE = common.BASE + '/plugins/shelly/tests/test_items.yaml'
    PARAMETERS: dict = {}

    def plugin(self) -> Shelly:
        """Create a Shelly plugin instance with all items of `ITEMS_FILE` parsed."""
        self.sh = MockSmartHome()
        self.sh.with_items_from(self.ITEMS_FILE)

        patcher = mock.patch('lib.model.mqttplugin.Modules', FakeModules)
        patcher.start()
        self.addCleanup(patcher.stop)

        plugin = Shelly.__new__(Shelly)
        # mirrors the attribute wiring lib.plugin.PluginWrapper does before calling __init__()
        plugin.logger = logging.getLogger('plugins.shelly')
        plugin._set_shortname('shelly')
        plugin._set_classname('Shelly')
        plugin._set_sh(self.sh)
        plugin._set_plugin_dir(os.path.join(common.BASE, 'plugins', 'shelly'))
        plugin._parameters = {'gen1debug': False, 'debuggen1devices': [], **self.PARAMETERS}
        plugin._init_complete = True
        plugin.__init__(self.sh)
        plugin.alive = True
        self.gaps = {item.property.path: GapRecorder(item) for item in self.sh.return_items()}
        for item in self.sh.return_items():
            plugin.parse_item(item)
        return plugin
