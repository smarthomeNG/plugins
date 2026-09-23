#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for the bridge role (plugins/matter/bridge/role.py) on a real Matter
plugin instance with real Items and loop, against a WsPeer speaking
bridge.js's control protocol.
"""

import itertools
import time
import unittest

from plugins.matter.tests.support import PluginHarness, WsPeer, connect_client, wait_for

ITEMS = """
exposed:
    lamp:
        type: bool
        matter_expose_type: switch
        matter_expose_name: Lamp
    door:
        type: bool
        matter_expose_type: contact
    temp:
        type: num
        matter_expose_type: temperature_sensor
    wrong_type:
        type: str
        matter_expose_type: temperature_sensor
    unknown_kind:
        type: bool
        matter_expose_type: dimmer
    name_too_long:
        type: bool
        matter_expose_type: switch
        matter_expose_name: this name is far too long for matter
"""


class BridgePeer(WsPeer):
    """WsPeer answering bridge.js's control commands, numbering endpoints from 2."""

    def __init__(self):
        super().__init__('id', responder=self.answer)
        self._numbers = itertools.count(2)
        self.fail_status = False

    def answer(self, request):
        command = request['command']
        if command == 'add_endpoint':
            return {'result': {'endpoint_id': next(self._numbers)}}
        if command == 'get_status':
            return (
                {'error': 'boom'} if self.fail_status else {'result': {'commissioned': True, 'qr_pairing_code': 'MT:X'}}
            )
        if command == 'get_fabrics':
            return {'result': {'fabrics': [{'fabric_index': 1}]}}
        return {'result': {}}


class _BridgeRoleTest(unittest.TestCase):
    def setUp(self):
        self.harness = PluginHarness(ITEMS)
        self.addCleanup(self.harness.close)
        self.bridge = self.harness.plugin.bridge
        self.peer = BridgePeer().start()
        self.addCleanup(self.peer.stop)

    def connect_and_seed(self):
        self.harness.start_loop()
        connect_client(self.harness, self.bridge, self.peer.url)
        self.harness.run(self.bridge._on_connected(self.bridge.client))

    def item(self, path):
        return self.harness.item(path)

    def endpoint_of(self, path):
        return next(entry['endpoint_id'] for entry in self.bridge.bridged_items() if entry['item_path'] == path)


class TestParsing(_BridgeRoleTest):
    def test_valid_items_are_exposed_with_their_names(self):
        exposed = {entry['item_path']: entry for entry in self.bridge.bridged_items()}

        self.assertEqual(set(exposed), {'exposed.lamp', 'exposed.door', 'exposed.temp'})
        self.assertEqual(exposed['exposed.lamp']['name'], 'Lamp')
        self.assertEqual(exposed['exposed.door']['name'], 'exposed.door')

    def test_item_type_must_match_the_expose_type(self):
        self.assertNotIn(self.item('exposed.wrong_type'), self.harness.plugin.mapped_items())

    def test_unknown_expose_type_and_long_name_are_rejected(self):
        mapped = self.harness.plugin.mapped_items()

        self.assertNotIn(self.item('exposed.unknown_kind'), mapped)
        self.assertNotIn(self.item('exposed.name_too_long'), mapped)


class TestEndpoints(_BridgeRoleTest):
    def test_connect_adds_every_endpoint_and_pushes_current_values(self):
        self.item('exposed.temp')(21.5, 'test')

        self.connect_and_seed()

        self.assertEqual(len(self.peer.commands('add_endpoint')), 3)
        pushed = {
            command['args']['endpoint_id']: command['args']['value'] for command in self.peer.commands('set_attribute')
        }
        self.assertEqual(pushed[self.endpoint_of('exposed.temp')], 21.5)

    def test_item_write_is_pushed_without_blocking(self):
        self.connect_and_seed()
        self.peer.received.clear()

        started = time.monotonic()
        self.item('exposed.lamp')(True, 'test')

        self.assertLess(time.monotonic() - started, 0.5)
        self.assertTrue(wait_for(lambda: self.peer.commands('set_attribute')))
        self.assertEqual(
            self.peer.commands('set_attribute')[0]['args'],
            {'endpoint_id': self.endpoint_of('exposed.lamp'), 'value': True},
        )

    def test_controller_command_updates_the_item_without_echo(self):
        self.connect_and_seed()
        self.peer.received.clear()

        self.peer.push(
            {'event': 'command_received', 'data': {'endpoint_id': self.endpoint_of('exposed.lamp'), 'value': True}}
        )

        self.assertTrue(wait_for(lambda: self.item('exposed.lamp')() is True))
        time.sleep(0.2)
        self.assertEqual(self.peer.commands('set_attribute'), [])

    def test_removed_item_removes_its_endpoint(self):
        self.connect_and_seed()
        endpoint_id = self.endpoint_of('exposed.door')

        self.harness.sh.items.remove_item(self.item('exposed.door'), persist=False)

        self.assertTrue(wait_for(lambda: self.peer.commands('remove_endpoint')))
        self.assertEqual(self.peer.commands('remove_endpoint')[0]['args'], {'endpoint_id': endpoint_id})
        self.assertNotIn('exposed.door', [entry['item_path'] for entry in self.bridge.bridged_items()])


class TestWebifQueries(_BridgeRoleTest):
    def test_status_unavailable_while_not_connected(self):
        self.assertEqual(self.bridge.bridge_status(), {'available': False})
        self.assertEqual(self.bridge.bridge_fabrics(), [])

    def test_status_and_fabrics_when_connected(self):
        self.connect_and_seed()

        self.assertEqual(self.bridge.bridge_status()['available'], True)
        self.assertEqual(self.bridge.bridge_fabrics(), [{'fabric_index': 1}])

    def test_status_error_degrades_to_unavailable(self):
        self.connect_and_seed()
        self.peer.fail_status = True

        self.assertEqual(self.bridge.bridge_status(), {'available': False})

    def test_actions_without_connection_raise(self):
        with self.assertRaises(ConnectionError):
            self.bridge.open_commissioning_window()


if __name__ == '__main__':
    unittest.main()
