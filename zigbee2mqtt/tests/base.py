"""
Test harness for the zigbee2mqtt plugin.

The plugin is driven through its MQTT callbacks; results are observed on real items. Only the MQTT
broker connection is replaced, by `FakeMqttModule`, and the database plugin's per-item functions
by `GapRecorder`.
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

from plugins.zigbee2mqtt import Zigbee2Mqtt

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


class Zigbee2MqttTestBase(unittest.TestCase):
    ITEMS_FILE = common.BASE + '/plugins/zigbee2mqtt/tests/test_items.yaml'
    PARAMETERS: dict = {}

    def plugin(self) -> Zigbee2Mqtt:
        """Create a Zigbee2Mqtt plugin instance with all items of `ITEMS_FILE` parsed and recording gaps."""
        self.sh = MockSmartHome()
        self.sh.with_items_from(self.ITEMS_FILE)

        patcher = mock.patch('lib.model.mqttplugin.Modules', FakeModules)
        patcher.start()
        self.addCleanup(patcher.stop)

        plugin = Zigbee2Mqtt.__new__(Zigbee2Mqtt)
        # mirrors the attribute wiring lib.plugin.PluginWrapper does before calling __init__()
        plugin.logger = logging.getLogger('plugins.zigbee2mqtt')
        plugin._set_shortname('zigbee2mqtt')
        plugin._set_classname('Zigbee2Mqtt')
        plugin._set_sh(self.sh)
        plugin._set_plugin_dir(os.path.join(common.BASE, 'plugins', 'zigbee2mqtt'))
        plugin._parameters = {
            'base_topic': 'zigbee2mqtt',
            'poll_period': 300,
            'read_at_init': False,
            'z2m_gui': '',
            'pause_item': '',
            **self.PARAMETERS,
        }
        plugin._init_complete = True
        plugin.__init__(self.sh)
        plugin.alive = True
        self.gaps = {item.property.path: GapRecorder(item) for item in self.sh.return_items()}
        for item in self.sh.return_items():
            plugin.parse_item(item)
        return plugin
