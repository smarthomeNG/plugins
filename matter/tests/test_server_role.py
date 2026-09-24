#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for the server role (plugins/matter/server/role.py) on a real
Matter plugin instance: real Items (writes reach update_item through the
item's own method trigger), the plugin's real asyncio loop, and a WsPeer
standing in for matter-server.
"""

import asyncio
import http.server
import os
import sys
import textwrap
import threading
import time
import unittest

import psutil

from plugins.matter.role import RoleState
from plugins.matter.server import CommissionState, MatterServerSidecar, ServerSidecarSettings
from plugins.matter.tests.support import PluginHarness, WsPeer, connect_client, wait_for

ITEMS = """
matter:
    aliases:
        kitchen:
            type: num
            value: 3

dev:
    matter_node: 3
    matter_endpoint: 1
    sw:
        type: bool
        matter_cluster: 6
        matter_switch: true
    power:
        type: num
        matter_cluster: 144
        matter_attribute: 8
    toggle:
        type: bool
        matter_cluster: 6
        matter_command: toggle
    available:
        type: bool
        matter_available: true

aliased:
    matter_alias: kitchen
    matter_endpoint: 1
    sw:
        type: bool
        matter_cluster: 6
        matter_switch: true

ghost:
    matter_alias: ghost
    matter_endpoint: 1
    sw:
        type: bool
        matter_cluster: 6
        matter_switch: true

broken:
    matter_node: 3
    sw:
        type: bool
        matter_cluster: 6
        matter_switch: true
"""

NODE_3 = {
    'node_id': 3,
    'available': True,
    'attributes': {
        '0/40/1': 'Shelly',
        '0/40/3': 'Plug',
        '0/29/0': [{'0': 22, '1': 1}],
        '1/29/0': [{'0': 266, '1': 1}],
        '1/6/0': True,
        '1/144/8': 1500,
    },
}


class MatterServerPeer(WsPeer):
    """WsPeer answering the matter-server commands the server role uses."""

    def __init__(self):
        super().__init__('message_id', responder=self.answer, greeting={'thread_credentials_set': False})
        self.nodes = [NODE_3]
        self.delay = 0.0
        self.error_for: set[str] = set()
        self.silent_for: set[str] = set()

    async def answer(self, request):
        command = request['command']
        if self.delay:
            await asyncio.sleep(self.delay)
        if command in self.silent_for:
            return None
        if command in self.error_for:
            return {'error_code': 1, 'details': f'{command} rejected'}
        if command in ('get_nodes', 'start_listening'):
            return {'result': self.nodes}
        if command == 'commission_with_code':
            return {'result': {'node_id': 9}}
        return {'result': None}


class _ServerRoleTest(unittest.TestCase):
    def setUp(self):
        self.harness = PluginHarness(ITEMS)
        self.addCleanup(self.harness.close)
        self.server = self.harness.plugin.server
        self.peer = MatterServerPeer().start()
        self.addCleanup(self.peer.stop)

    def connect(self):
        self.harness.start_loop()
        connect_client(self.harness, self.server, self.peer.url + '/ws')

    def item(self, path):
        return self.harness.item(path)


class TestParsing(_ServerRoleTest):
    def test_inherited_addressing_is_resolved_and_marked(self):
        self.assertEqual(
            self.harness.plugin.describe_item(self.item('dev.power')), 'node=3*, endpoint=1*, cluster=144, attribute=8'
        )

    def test_alias_item_resolves_through_the_alias(self):
        self.assertEqual(
            self.harness.plugin.describe_item(self.item('aliased.sw')),
            'alias=kitchen*, node=3, endpoint=1*, cluster=6, attribute=0, command=on, command_false=off',
        )

    def test_item_missing_endpoint_is_not_mapped(self):
        self.assertNotIn(self.item('broken.sw'), self.harness.plugin.mapped_items())

    def test_prepare_reports_unknown_alias_references(self):
        with self.assertLogs(self.harness.plugin.logger, 'ERROR') as logs:
            self.server.prepare()

        self.assertTrue(any("matter_alias 'ghost'" in line for line in logs.output))


class TestReports(_ServerRoleTest):
    def test_connect_seeds_cached_values_into_direct_and_alias_items(self):
        self.connect()
        self.harness.run(self.server._on_connected(self.server.client))

        self.assertIs(self.item('dev.sw')(), True)
        self.assertIs(self.item('aliased.sw')(), True)
        self.assertEqual(self.item('dev.power')(), 1500)
        self.assertIs(self.item('dev.available')(), True)

    def test_pushed_attribute_update_reaches_items(self):
        self.connect()

        self.peer.push({'event': 'attribute_updated', 'data': [3, '1/144/8', 42]})

        self.assertTrue(wait_for(lambda: self.item('dev.power')() == 42))

    def test_pushed_availability_reaches_items(self):
        self.connect()
        self.item('dev.available')(True, 'test')

        self.peer.push({'event': 'node_updated', 'data': {'node_id': 3, 'available': False}})

        self.assertTrue(wait_for(lambda: self.item('dev.available')() is False))


class TestWrites(_ServerRoleTest):
    def test_switch_write_sends_on_and_off(self):
        self.connect()

        self.item('dev.sw')(True, 'test')
        self.assertTrue(wait_for(lambda: len(self.peer.commands('device_command')) == 1))
        self.item('dev.sw')(False, 'test')
        self.assertTrue(wait_for(lambda: len(self.peer.commands('device_command')) == 2))

        first, second = (command['args'] for command in self.peer.commands('device_command'))
        self.assertEqual((first['node_id'], first['endpoint_id'], first['cluster_id']), (3, 1, 6))
        self.assertEqual((first['command_name'], second['command_name']), ('on', 'off'))

    def test_attribute_write_sends_write_attribute(self):
        self.connect()

        self.item('dev.power')(7, 'test')

        self.assertTrue(wait_for(lambda: self.peer.commands('write_attribute')))
        self.assertEqual(
            self.peer.commands('write_attribute')[0]['args'], {'node_id': 3, 'attribute_path': '1/144/8', 'value': 7}
        )

    def test_falsy_write_to_value_independent_command_does_not_fire(self):
        self.connect()

        self.item('dev.toggle')(True, 'test')
        self.item('dev.toggle')(False, 'test')

        self.assertTrue(wait_for(lambda: self.peer.commands('device_command')))
        time.sleep(0.2)
        self.assertEqual(len(self.peer.commands('device_command')), 1)

    def test_write_does_not_block_the_writing_thread(self):
        self.connect()
        self.peer.delay = 1.0

        started = time.monotonic()
        self.item('dev.sw')(True, 'test')
        elapsed = time.monotonic() - started

        self.assertLess(elapsed, 0.5)
        self.assertTrue(wait_for(lambda: self.peer.commands('device_command')))

    def test_rejected_write_is_logged_with_the_item_path(self):
        self.connect()
        self.peer.error_for.add('device_command')

        with self.assertLogs(self.harness.plugin.logger, 'ERROR') as logs:
            self.item('dev.sw')(True, 'test')
            wait_for(lambda: any('dev.sw' in line for line in logs.output))

        self.assertTrue(any('writing dev.sw to Matter failed' in line for line in logs.output))

    def test_own_report_is_not_written_back(self):
        self.connect()

        self.peer.push({'event': 'attribute_updated', 'data': [3, '1/6/0', False]})
        self.assertTrue(wait_for(lambda: self.item('dev.sw')() is False))
        time.sleep(0.2)

        self.assertEqual(self.peer.commands('device_command'), [])

    def test_write_via_undefined_alias_is_dropped_not_sent_to_a_placeholder_node(self):
        self.connect()

        with self.assertLogs(self.harness.plugin.logger, 'ERROR') as logs:
            self.item('ghost.sw')(True, 'test')

        time.sleep(0.2)
        self.assertEqual(self.peer.commands('device_command'), [])
        self.assertTrue(any("'ghost' is not defined" in line for line in logs.output))


class TestAliases(_ServerRoleTest):
    def test_repoint_redirects_writes_and_reports_immediately_and_persists(self):
        self.connect()

        self.server.repoint_alias('kitchen', 4)
        self.item('aliased.sw')(True, 'test')
        self.assertTrue(wait_for(lambda: self.peer.commands('device_command')))
        self.peer.push({'event': 'attribute_updated', 'data': [4, '1/6/0', False]})

        self.assertEqual(self.peer.commands('device_command')[0]['args']['node_id'], 4)
        self.assertTrue(wait_for(lambda: self.item('aliased.sw')() is False))
        self.assertEqual(self.server.aliases.snapshot()['kitchen'], 4)
        with open(os.path.join(self.harness.sh._items_dir, 'test_items.yaml')) as f:
            self.assertIn('value: 4', f.read())

    def test_create_and_remove_alias_go_through_real_items(self):
        self.server.create_alias('ghost', 5)

        self.assertEqual(self.server.aliases.snapshot()['ghost'], 5)
        self.assertEqual(self.harness.plugin.describe_item(self.item('matter.aliases.ghost')), 'alias definition ghost')

        self.server.remove_alias('ghost')

        self.assertNotIn('ghost', self.server.aliases.snapshot())

    def test_alias_item_write_repoints(self):
        self.item('matter.aliases.kitchen')(6, 'test')

        self.assertEqual(self.server.aliases.snapshot()['kitchen'], 6)

    def test_invalid_alias_item_write_keeps_the_old_target(self):
        with self.assertLogs(self.harness.plugin.logger, 'ERROR'):
            self.item('matter.aliases.kitchen')(-1, 'test')

        self.assertEqual(self.server.aliases.snapshot()['kitchen'], 3)


class TestCommissioning(_ServerRoleTest):
    def test_commission_returns_at_once_and_completes_in_the_background(self):
        self.connect()
        self.peer.delay = 0.5

        started = time.monotonic()
        job = self.server.start_commission('MT:ABC')

        self.assertLess(time.monotonic() - started, 0.3)
        self.assertEqual(job.state, CommissionState.PENDING)
        self.assertTrue(wait_for(lambda: job.state is CommissionState.SUCCEEDED))
        self.assertEqual(job.detail, 'node_id=9')
        self.assertEqual(self.server.commission_jobs()[-1]['state'], 'succeeded')

    def test_commission_waits_for_the_configured_timeout_not_a_fixed_one(self):
        self.connect()
        self.peer.silent_for.add('commission_with_code')
        self.server.settings = type(self.server.settings)(commission_timeout=0.3)

        job = self.server.start_commission('MT:ABC')

        self.assertTrue(wait_for(lambda: job.state is CommissionState.FAILED))
        self.assertIn('timed out', job.detail)

    def test_commission_without_connection_raises(self):
        with self.assertRaises(ConnectionError):
            self.server.start_commission('MT:ABC')


class TestWebifQueries(_ServerRoleTest):
    def test_nodes_snapshot_degrades_to_an_error_when_not_connected(self):
        snapshot = self.server.nodes_snapshot()

        self.assertEqual(snapshot.nodes, ())
        self.assertIn('not connected', snapshot.error)

    def test_nodes_snapshot_skips_malformed_nodes(self):
        self.connect()
        self.peer.nodes = [NODE_3, {'node_id': 'x'}]

        snapshot = self.server.nodes_snapshot()

        self.assertEqual([node['node_id'] for node in snapshot.nodes], [3])

    def test_create_suggested_items_creates_working_items(self):
        self.connect()

        paths = self.server.create_suggested_items(3)

        self.assertEqual(paths, ['matter_devices.matter_node_3'])
        created = self.item('matter_devices.matter_node_3')
        self.assertIn(created, self.harness.plugin.mapped_items())
        self.assertIn('node=3', self.harness.plugin.describe_item(created))
        with self.assertRaises(ValueError):
            self.server.create_suggested_items(3)

    def test_created_items_start_with_the_cached_device_values(self):
        self.connect()

        self.server.create_suggested_items(3)

        self.assertIs(self.item('matter_devices.matter_node_3')(), True)
        self.assertEqual(self.item('matter_devices.matter_node_3.power.power_mw')(), 1500)


class _OtbrHandler(http.server.BaseHTTPRequestHandler):
    body = b''

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(self.body)

    def log_message(self, *args):
        pass


class TestThreadDataset(_ServerRoleTest):
    def start_otbr(self, body: bytes) -> str:
        handler = type('Handler', (_OtbrHandler,), {'body': body})
        httpd = http.server.HTTPServer(('127.0.0.1', 0), handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        self.addCleanup(httpd.server_close)
        self.addCleanup(httpd.shutdown)
        return f'http://127.0.0.1:{httpd.server_address[1]}'

    def with_otbr_url(self, url: str) -> None:
        settings = self.server.settings
        self.server.settings = type(settings)(**{**settings.__dict__, 'otbr_rest_url': url})

    def test_fetch_registers_the_dataset_with_matter_server(self):
        self.connect()
        self.with_otbr_url(self.start_otbr(b'0e0800\n'))

        self.assertEqual(self.server.fetch_thread_dataset_from_otbr(), '0e0800')

        self.assertEqual(self.peer.commands('set_thread_dataset')[0]['args'], {'dataset': '0e0800'})
        self.assertTrue(self.server.thread_dataset_is_set())

    def test_empty_dataset_is_an_error(self):
        self.connect()
        self.with_otbr_url(self.start_otbr(b''))

        with self.assertRaises(ValueError):
            self.server.fetch_thread_dataset_from_otbr()

    def test_unreachable_border_router_is_an_error(self):
        self.with_otbr_url('http://127.0.0.1:1')

        with self.assertRaises(ValueError):
            self.server.fetch_thread_dataset_from_otbr()

    def test_unconfigured_url_is_an_error(self):
        self.with_otbr_url('')

        with self.assertRaises(ValueError):
            self.server.fetch_thread_dataset_from_otbr()


INSTANCE_ITEMS = """
matter:
    aliases:
        kitchen:
            type: num
            value: 3

mine:
    matter_node@two: 3
    matter_endpoint@two: 1
    sw:
        type: bool
        matter_cluster@two: 6
        matter_switch@two: true

other_instance:
    matter_node: 3
    matter_endpoint: 1
    sw:
        type: bool
        matter_cluster: 6
        matter_switch: true
"""


class TestInstanceAddressing(unittest.TestCase):
    def test_named_instance_maps_only_its_own_attributes(self):
        harness = PluginHarness(INSTANCE_ITEMS, instance='two')
        self.addCleanup(harness.close)
        mapped = harness.plugin.mapped_items()

        self.assertIn(harness.item('mine.sw'), mapped)
        self.assertNotIn(harness.item('other_instance.sw'), mapped)
        self.assertEqual(harness.plugin.server.own_caller(), 'matter_two:server')


class TestAliasBaseItem(unittest.TestCase):
    def test_missing_remark_is_set_once(self):
        harness = PluginHarness(ITEMS)
        self.addCleanup(harness.close)
        base = harness.item('matter.aliases')

        harness.plugin.server.prepare()

        self.assertEqual(
            base.property.remark, 'matter alias base item, child items are alias definitions, do not change'
        )
        self.assertEqual(harness.plugin.server.aliases.snapshot(), {'kitchen': 3})


FAKE_MATTER_SERVER = textwrap.dedent(
    """
    import time
    print('Webserver listening on test', flush=True)
    time.sleep(120)
    """
)


class TestLifecycle(unittest.TestCase):
    """run() with a real child process standing in for matter-server and a WsPeer as its API."""

    def test_run_connects_reconnects_and_cleanup_stops_everything(self):
        harness = PluginHarness(ITEMS)
        self.addCleanup(harness.close)
        peer = MatterServerPeer().start()
        self.addCleanup(peer.stop)
        entry = os.path.join(harness.tmp_dir, 'fake_matter_server.py')
        with open(entry, 'w') as f:
            f.write(FAKE_MATTER_SERVER)
        server = harness.plugin.server
        server.sidecar = MatterServerSidecar(
            sys.executable, entry, os.path.join(harness.tmp_dir, 'storage'), ServerSidecarSettings(port=0)
        )
        server.url = peer.url + '/ws'
        harness.start_loop()

        run = asyncio.run_coroutine_threadsafe(server.run(), harness.plugin._asyncio_loop)
        self.assertTrue(wait_for(lambda: server.status.state is RoleState.CONNECTED))
        self.assertIs(harness.item('dev.sw')(), True)
        pid = server.sidecar._process.pid

        # Widens the RECONNECTING window past the 10ms poll below - a local loopback reconnect can otherwise be faster.
        peer.delay = 0.1
        peer.drop_connections()
        self.assertTrue(wait_for(lambda: server.status.state is RoleState.RECONNECTING, timeout=2))
        peer.delay = 0.0
        self.assertTrue(wait_for(lambda: server.status.state is RoleState.CONNECTED, timeout=5))

        run.cancel()
        harness.run(server.cleanup())

        self.assertFalse(server.sidecar.running)
        self.assertFalse(server.connected)
        self.assertTrue(
            wait_for(lambda: not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE)
        )


if __name__ == '__main__':
    unittest.main()
