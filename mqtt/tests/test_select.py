"""
mqtt_select_in: items on one topic receive their own part of a dict payload.

The plugin runs with real items and the real mqtt module dispatch; only the broker connection is replaced.
"""

import json
import logging
import os
import unittest
from unittest import mock

import lib.item
import lib.item.item

from tests import common
from tests.mock.core import MockSmartHome
from tests.mqtt_harness import Message, make_mqtt_module

from plugins.mqtt import Mqtt2

if not hasattr(lib.item, 'Item'):
    lib.item.Item = lib.item.item.Item

TOPIC = 'device/state'


def _modules_serving(module):
    """Stand-in for `lib.module.Modules` that serves the given mqtt module."""

    class _Modules:
        @staticmethod
        def get_instance():
            return _Modules()

        def get_module(self, name):
            return module if name == 'mqtt' else None

    return _Modules


def _loaded_items(sh, parents_first=False):
    """
    The items loaded by `sh.with_items_from()` in registration order (the item registry itself outlives a test)

    Items register themselves after their children, so plugins parse children before their ancestors.
    """

    def walk(item):
        if parents_first:
            yield item
        for child in item:
            yield from walk(child)
        if not parents_first:
            yield item

    for top_level_item in sh.children:
        yield from walk(top_level_item)


class MqttSelectTestBase(unittest.TestCase):
    ITEMS_FILE = common.BASE + '/plugins/mqtt/tests/test_items.yaml'
    PARENTS_FIRST = False

    def setUp(self):
        self.sh = MockSmartHome()
        self.sh.with_items_from(self.ITEMS_FILE)
        self.module = make_mqtt_module()

        patcher = mock.patch('lib.model.mqttplugin.Modules', _modules_serving(self.module))
        patcher.start()
        self.addCleanup(patcher.stop)

        plugin = Mqtt2.__new__(Mqtt2)
        # mirrors the attribute wiring lib.plugin.PluginWrapper does before calling __init__()
        plugin.logger = logging.getLogger('plugins.mqtt')
        plugin._set_shortname('mqtt')
        plugin._set_classname('Mqtt2')
        plugin._set_sh(self.sh)
        plugin._set_plugin_dir(os.path.join(common.BASE, 'plugins', 'mqtt'))
        plugin._parameters = {}
        plugin._init_complete = True
        plugin.__init__(self.sh)
        plugin.alive = True
        for item in _loaded_items(self.sh, self.PARENTS_FIRST):
            plugin.parse_item(item)
        plugin.start_subscriptions()
        self.plugin = plugin

    def publish(self, payload, topic=TOPIC):
        self.module._on_mqtt_message(None, None, Message(topic, payload))

    def value(self, path):
        return self.sh.return_item(path)()


class TestMqttSelectIn(MqttSelectTestBase):
    def test_items_receive_the_part_their_expression_selects(self):
        self.publish(b'{"temp": 21.5, "hum": 40, "state": {"on": true}}')

        self.assertEqual(self.value('dev.temperature'), 21.5)
        self.assertEqual(self.value('dev.humidity'), 40)
        self.assertIs(self.value('dev.active'), True)

    def test_item_without_select_still_receives_the_whole_payload(self):
        self.publish(b'{"temp": 21.5, "hum": 40}')

        self.assertEqual(self.value('dev.whole_state'), {'temp': 21.5, 'hum': 40})

    def test_key_missing_from_the_payload_leaves_the_item_unchanged(self):
        self.publish(b'{"temp": 21.5}')

        self.assertEqual(self.value('dev.temperature'), 21.5)
        self.assertEqual(self.value('dev.humidity'), 0)

    def test_select_without_topic_in_logs_a_warning(self):
        item = self.sh.return_item('dev.orphan_select')

        with self.assertLogs('plugins.mqtt', level='WARNING') as logs:
            self.plugin.parse_item(item)

        self.assertIn('mqtt_select_in', logs.output[0])
        self.assertIn('dev.orphan_select', logs.output[0])


class _InheritedTopicTests:
    ITEMS_FILE = common.BASE + '/plugins/mqtt/tests/test_items_inherited_topic.yaml'

    def test_child_without_topic_uses_the_topic_of_its_ancestor(self):
        self.publish(b'{"hppower": 3.5, "heatingpump": true}', topic='ems/boiler')

        self.assertEqual(self.value('boiler.state.power'), 3.5)
        self.assertIs(self.value('boiler.state.pump'), True)

    def test_ancestor_still_holds_the_full_payload(self):
        self.publish(b'{"hppower": 3.5, "heatingpump": true}', topic='ems/boiler')

        self.assertEqual(self.value('boiler.state'), {'hppower': 3.5, 'heatingpump': True})

    def test_child_inherits_the_combined_topic_of_its_ancestor(self):
        self.publish(b'{"hppower": 3.5}', topic='ems/combined')

        self.assertEqual(self.value('boiler.combined.power'), 3.5)


class TestInheritedTopicAncestorParsedAfterChild(_InheritedTopicTests, MqttSelectTestBase):
    PARENTS_FIRST = False


class TestInheritedTopicAncestorParsedBeforeChild(_InheritedTopicTests, MqttSelectTestBase):
    PARENTS_FIRST = True


class _PrefixedAncestorTests:
    ITEMS_FILE = common.BASE + '/plugins/mqtt/tests/test_items_prefixed_ancestor.yaml'

    def test_child_subscribes_to_the_prefixed_topic_of_its_ancestor(self):
        self.publish(b'{"hppower": 3.5}', topic='home/ems/boiler')

        self.assertEqual(self.value('prefixed.state.power'), 3.5)


class TestPrefixedAncestorParsedAfterChild(_PrefixedAncestorTests, MqttSelectTestBase):
    PARENTS_FIRST = False


class TestPrefixedAncestorParsedBeforeChild(_PrefixedAncestorTests, MqttSelectTestBase):
    PARENTS_FIRST = True


BOILER_PAYLOAD = {
    'hppower': 2.5,
    'heatingpump': 'on',
    'heatingpumpmod': 40,
    'heatingactive': 'on',
    'tapwateractive': 'off',
    'hpcompspd': 55,
    'outdoortemp': 4.5,
    'curflowtemp': 31.2,
    'rettemp': 28.4,
    'nrgconstotal': 1234,
    'nrgconscomptotal': 1100,
    'auxelecheatnrgconstotal': 12,
    'nrgtotal': 4800,
    'auxheaterstatus': 'off',
    'auxelecheatnrgconsheating': 8,
    'elheatstep1': 'off',
    'elheatstep2': 'off',
    'elheatstep3': 'off',
}

BOILER_ITEM_VALUES = {
    'Power': 2500.0,
    'Heatingpump': 'on',
    'Heatingpump_Modulation': 40,
    'Heating_Active': 'on',
    'Tapwater_Active': 'off',
    'Compressor_Speed': 55,
    'Aussentemperatur': 4.5,
    'Aktuelle_Vorlauftemperatur': 31.2,
    'Ruecklauftemperatur': 28.4,
    'Energieverbrauch_gesamt': 1234,
    'Energieverbrauch_Verdichter_gesamt': 1100,
    'Energieverbrauch_Zuheizer': 12,
    'Energieerzeugung_gesamt': 4800,
    'Zuheizer_Status': 'off',
    'Energieverbrauch_Zuheizer_Heizung': 8,
    'Zuheizer_Stufe_1': 'off',
    'Zuheizer_Stufe_2': 'off',
    'Zuheizer_Stufe_3': 'off',
}


class TestBoilerShapedConfig(MqttSelectTestBase):
    """A dict item with many select-only children, one of them scaled by an eval, as in a heat pump gateway setup"""

    ITEMS_FILE = common.BASE + '/plugins/mqtt/tests/test_items_buderus.yaml'
    TOPIC_IN = 'ems-esp/boiler_data'

    def setUp(self):
        super().setUp()
        # runs item evals inline instead of handing them to the scheduler
        self.sh.trigger = lambda name, obj=None, value=None, **kwargs: obj(**value)

    def boiler_values(self):
        return {name: self.value(f'Buderus.Boiler_Data.{name}') for name in BOILER_ITEM_VALUES}

    def publish_boiler(self, payload):
        self.publish(json.dumps(payload).encode(), topic=self.TOPIC_IN)

    def test_every_child_receives_its_key_in_its_own_type(self):
        self.publish_boiler(BOILER_PAYLOAD)

        self.assertEqual(self.boiler_values(), BOILER_ITEM_VALUES)

    def test_ancestor_holds_the_full_payload(self):
        self.publish_boiler(BOILER_PAYLOAD)

        self.assertEqual(self.value('Buderus.Boiler_Data'), BOILER_PAYLOAD)

    def test_keys_missing_from_a_later_payload_leave_their_items_unchanged(self):
        self.publish_boiler(BOILER_PAYLOAD)

        self.publish_boiler({'outdoortemp': 5.5})

        self.assertEqual(self.boiler_values(), {**BOILER_ITEM_VALUES, 'Aussentemperatur': 5.5})


if __name__ == '__main__':
    unittest.main(verbosity=2)
