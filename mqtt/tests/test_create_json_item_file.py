"""
Mqtt2.create_json_item_file(): an item file mirroring an item's JSON value, whose children share the item's topic.

Runs with real items; the generated file is loaded back by the real item config parser.
"""

import json
import os
import shutil
import tempfile
from collections import OrderedDict

import lib.config
import lib.shyaml

from tests import common

from plugins.mqtt.webif import WebInterface
from plugins.mqtt.tests.test_select import MqttSelectTestBase, TOPIC

PAYLOAD = {'temp': 21.5, 'state': {'on': True}, 'sensors': [{'v': 1}, {'v': 2}]}


class ItemFileTestBase(MqttSelectTestBase):
    """Plugin on the test items, writing item files to a temporary items directory."""

    def setUp(self):
        super().setUp()
        self.items_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.items_dir)
        self.sh._items_dir = self.items_dir + os.sep
        self.source = self.sh.return_item('dev.whole_state')
        self.source(PAYLOAD, 'test')

    def generated_path(self):
        return os.path.join(self.items_dir, 'dev.whole_state.yaml')


class TestCreateJsonItemFile(ItemFileTestBase):
    def test_writes_file_named_after_the_item(self):
        path = self.plugin.create_json_item_file(self.source)

        self.assertEqual(path, self.generated_path())
        tree = lib.config.parse(path, None)
        children = tree['dev']['whole_state']
        self.assertEqual(children['temp']['mqtt_select_in'], 'temp')
        self.assertEqual(children['state']['on']['mqtt_select_in'], 'state.on')
        self.assertEqual(children['sensors']['item_1']['v']['mqtt_select_in'], 'sensors[1].v')

    def test_parses_json_held_by_a_str_item(self):
        self.source._value = '{"a": 1}'

        path = self.plugin.create_json_item_file(self.source)

        self.assertEqual(lib.config.parse(path, None)['dev']['whole_state']['a']['mqtt_select_in'], 'a')

    def test_refuses_to_overwrite_an_existing_file(self):
        self.plugin.create_json_item_file(self.source)

        with self.assertRaises(ValueError) as raised:
            self.plugin.create_json_item_file(self.source)

        self.assertIn('dev.whole_state.yaml', str(raised.exception))

    def test_refuses_item_without_json_value(self):
        with self.assertRaises(ValueError):
            self.plugin.create_json_item_file(self.sh.return_item('dev.temperature'))
        self.assertEqual(os.listdir(self.items_dir), [])

    def test_refuses_item_without_topic_in(self):
        item = self.sh.return_item('dev.orphan_select')
        item._value = {'a': 1}

        with self.assertRaises(ValueError) as raised:
            self.plugin.create_json_item_file(item)

        self.assertIn('mqtt_topic_in', str(raised.exception))

    def test_names_that_collide_with_item_attributes_are_avoided(self):
        self.source({'type': 1, 'path': 2}, 'test')

        path = self.plugin.create_json_item_file(self.source)

        self.assertEqual(sorted(lib.config.parse(path, None)['dev']['whole_state']), ['path_', 'type_'])


class TestCreateItemFileEndpoint(ItemFileTestBase):
    """The web interface endpoint reports the outcome as JSON."""

    def setUp(self):
        super().setUp()
        self.webif = WebInterface.__new__(WebInterface)
        self.webif.plugin = self.plugin
        self.webif.logger = self.plugin.logger
        self.webif.items = self.sh

    def test_reports_the_written_file(self):
        result = json.loads(self.webif.create_item_file('dev.whole_state'))

        self.assertTrue(result['ok'])
        self.assertIn('dev.whole_state.yaml', result['message'])
        self.assertTrue(os.path.exists(self.generated_path()))

    def test_reports_errors(self):
        for item_path in ('dev.temperature', 'dev.nonexistent', None):
            with self.subTest(item_path=item_path):
                result = json.loads(self.webif.create_item_file(item_path))
                self.assertFalse(result['ok'])
                self.assertTrue(result['message'])


class TestGeneratedItemsReceiveTheirPart(MqttSelectTestBase):
    """The generated file, merged into the item tree, wires the children to the source item's topic."""

    def setUp(self):
        items_dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, items_dir)
        super().setUp()
        self.sh._items_dir = items_dir + os.sep
        source = self.sh.return_item('dev.whole_state')
        source(PAYLOAD, 'test')
        generated = self.plugin.create_json_item_file(source)

        merged = lib.config.parse(generated, lib.config.parse(self.ITEMS_FILE, None))
        self.ITEMS_FILE = os.path.join(items_dir, 'merged.yaml')
        lib.shyaml.yaml_save(self.ITEMS_FILE, OrderedDict(merged))
        super().setUp()

    def test_children_get_the_selected_values(self):
        self.publish(b'{"temp": 5.5, "state": {"on": false}, "sensors": [{"v": 7}, {"v": 8}]}')

        self.assertEqual(self.value('dev.whole_state.temp'), 5.5)
        self.assertIs(self.value('dev.whole_state.state.on'), False)
        self.assertEqual(self.value('dev.whole_state.sensors.item_1.v'), 8)
