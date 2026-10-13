"""
Mqtt2.create_json_items(): child items mirroring an item's JSON value, sharing the item's topic.

Runs with the real item registry, so the items are created, wired to the plugin and persisted by the real
Items.create_item(); only the broker connection is replaced.
"""

import json
import os
import shutil
import tempfile
from collections import OrderedDict
from unittest import mock

import lib.config
import lib.shyaml
import lib.item.item
import lib.item.items
from lib.item.items import Items

from plugins.mqtt.tests.test_select import MqttSelectTestBase
from plugins.mqtt.webif import WebInterface

GENERATED_ITEMS_FILE = 'mqtt_generated_items.yaml'
PAYLOAD = b'{"temp": 5.5, "state": {"on": false}, "sensors": [{"v": 7}, {"v": 8}]}'


def _reset():
    lib.item.items._items_instance = None
    lib.item.item._items_instance = None
    Items._Items__items = []
    Items._Items__item_dict = {}
    Items._children = []


class JsonItemsTestBase(MqttSelectTestBase):
    """Plugin on the test items, with runtime-created items parsed by the plugin and persisted to a temp dir."""

    def setUp(self):
        _reset()
        self.addCleanup(_reset)
        super().setUp()
        self.items_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.items_dir)
        self.sh._items_dir = self.items_dir + os.sep
        self.plugin._parameters['generated_items_file'] = GENERATED_ITEMS_FILE

        class _Plugins:
            @staticmethod
            def return_plugins():
                return [self.plugin]

        patcher = mock.patch('lib.item.item.Plugins.get_instance', return_value=_Plugins)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.source = self.sh.return_item('dev.whole_state')
        self.source({'temp': 21.5, 'state': {'on': True}, 'sensors': [{'v': 1}, {'v': 2}]}, 'test')

    def generated_file(self, name=GENERATED_ITEMS_FILE):
        return os.path.join(self.items_dir, name)


class TestCreateJsonItems(JsonItemsTestBase):
    def test_children_are_created_and_receive_their_part_of_the_payload(self):
        self.plugin.create_json_items(self.source)

        self.publish(PAYLOAD)

        self.assertEqual(self.value('dev.whole_state.temp'), 5.5)
        self.assertIs(self.value('dev.whole_state.state.on'), False)
        self.assertEqual(self.value('dev.whole_state.sensors.item_1.v'), 8)

    def test_returns_the_paths_of_the_created_leaf_items(self):
        paths = self.plugin.create_json_items(self.source)

        self.assertEqual(
            sorted(paths),
            [
                'dev.whole_state.sensors.item_0.v',
                'dev.whole_state.sensors.item_1.v',
                'dev.whole_state.state.on',
                'dev.whole_state.temp',
            ],
        )

    def test_items_are_persisted_to_the_configured_file(self):
        self.plugin.create_json_items(self.source)

        children = lib.config.parse(self.generated_file(), None)['dev']['whole_state']
        self.assertEqual(children['temp']['mqtt_select_in'], 'temp')
        self.assertEqual(children['state']['on']['mqtt_select_in'], 'state.on')
        self.assertEqual(children['sensors']['item_1']['v']['mqtt_select_in'], 'sensors[1].v')
        self.assertEqual(os.listdir(self.items_dir), [GENERATED_ITEMS_FILE])

    def test_file_name_is_taken_from_the_parameter(self):
        self.plugin._parameters['generated_items_file'] = 'custom.yaml'

        self.plugin.create_json_items(self.source)

        self.assertEqual(os.listdir(self.items_dir), ['custom.yaml'])

    def test_parses_json_held_by_a_str_item(self):
        self.source._value = '{"a": 1}'

        paths = self.plugin.create_json_items(self.source)

        self.assertEqual(paths, ['dev.whole_state.a'])

    def test_names_that_collide_with_item_attributes_are_avoided(self):
        self.source({'type': 1, 'path': 2}, 'test')

        paths = self.plugin.create_json_items(self.source)

        self.assertEqual(sorted(paths), ['dev.whole_state.path_', 'dev.whole_state.type_'])

    def test_refuses_if_an_item_already_exists_and_creates_nothing(self):
        self.sh.items.create_item('dev.whole_state.state', {'type': 'dict'}, persist=False)

        with self.assertRaises(ValueError) as raised:
            self.plugin.create_json_items(self.source)

        self.assertIn('dev.whole_state.state', str(raised.exception))
        self.assertIsNone(self.sh.return_item('dev.whole_state.temp'))
        self.assertEqual(os.listdir(self.items_dir), [])

    def test_refuses_item_without_json_value(self):
        with self.assertRaises(ValueError):
            self.plugin.create_json_items(self.sh.return_item('dev.temperature'))
        self.assertEqual(os.listdir(self.items_dir), [])

    def test_refuses_item_without_topic_in(self):
        item = self.sh.return_item('dev.orphan_select')
        item._value = {'a': 1}

        with self.assertRaises(ValueError) as raised:
            self.plugin.create_json_items(item)

        self.assertIn('mqtt_topic_in', str(raised.exception))
        self.assertEqual(os.listdir(self.items_dir), [])


class TestCreateItemsEndpoint(JsonItemsTestBase):
    """The web interface endpoint reports the outcome as JSON."""

    def setUp(self):
        super().setUp()
        self.webif = WebInterface.__new__(WebInterface)
        self.webif.plugin = self.plugin
        self.webif.logger = self.plugin.logger
        self.webif.items = self.sh

    def test_reports_the_number_of_created_items_and_the_file(self):
        result = json.loads(self.webif.create_items('dev.whole_state'))

        self.assertEqual(result, {'ok': True, 'count': 4, 'file': GENERATED_ITEMS_FILE})
        self.assertTrue(os.path.exists(self.generated_file()))

    def test_reports_errors(self):
        for item_path in ('dev.temperature', 'dev.nonexistent', None):
            with self.subTest(item_path=item_path):
                result = json.loads(self.webif.create_items(item_path))
                self.assertFalse(result['ok'])
                self.assertTrue(result['message'])


class TestItemsSurviveRestart(MqttSelectTestBase):
    """The persisted file, merged into the item tree at startup, wires the children to the source item's topic."""

    def setUp(self):
        _reset()
        self.addCleanup(_reset)
        items_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, items_dir)
        super().setUp()
        self.sh._items_dir = items_dir + os.sep
        self.plugin._parameters['generated_items_file'] = GENERATED_ITEMS_FILE
        self.sh.return_item('dev.whole_state')({'temp': 21.5, 'state': {'on': True}}, 'test')
        with mock.patch('lib.item.item.Plugins.get_instance', return_value=self._plugins_serving(self.plugin)):
            self.plugin.create_json_items(self.sh.return_item('dev.whole_state'))

        merged = lib.config.parse(
            os.path.join(items_dir, GENERATED_ITEMS_FILE), lib.config.parse(self.ITEMS_FILE, None)
        )
        self.ITEMS_FILE = os.path.join(items_dir, 'merged.yaml')
        lib.shyaml.yaml_save(self.ITEMS_FILE, OrderedDict(merged))
        _reset()
        super().setUp()

    @staticmethod
    def _plugins_serving(plugin):
        class _Plugins:
            @staticmethod
            def return_plugins():
                return [plugin]

        return _Plugins

    def test_children_get_the_selected_values(self):
        self.publish(PAYLOAD)

        self.assertEqual(self.value('dev.whole_state.temp'), 5.5)
        self.assertIs(self.value('dev.whole_state.state.on'), False)
