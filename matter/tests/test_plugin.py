#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Tests for the Matter plugin frame (plugins/matter/__init__.py): item
dispatch across roles, disabled-role handling, and per-role supervision.
"""

import asyncio
import unittest

from plugins.matter.role import RoleConfigError, RoleState, RoleStatus
from plugins.matter.server.sidecar import MatterServerSidecar
from plugins.matter.tests.support import PluginHarness, connect_client, wait_for
from plugins.matter.tests.test_bridge_role import BridgePeer
from plugins.matter.tests.test_server_role import MatterServerPeer

PASSTHROUGH = """
plug:
    matter_node: 3
    matter_endpoint: 1
    sw:
        type: bool
        matter_cluster: 6
        matter_switch: true
        matter_expose_type: switch
        matter_expose_name: Plug
"""


class TestPassthroughItem(unittest.TestCase):
    """An item with server and bridge attributes: device reports reach the bridge, controller commands the device."""

    def setUp(self):
        self.harness = PluginHarness(PASSTHROUGH)
        self.addCleanup(self.harness.close)
        self.matter_server = MatterServerPeer().start()
        self.addCleanup(self.matter_server.stop)
        self.bridge_js = BridgePeer().start()
        self.addCleanup(self.bridge_js.stop)
        plugin = self.harness.plugin
        self.harness.start_loop()
        connect_client(self.harness, plugin.server, self.matter_server.url + '/ws')
        connect_client(self.harness, plugin.bridge, self.bridge_js.url)
        self.harness.run(plugin.bridge._on_connected(plugin.bridge.client))
        self.bridge_js.received.clear()
        self.item = self.harness.item('plug.sw')

    def test_registered_once_with_both_roles_mappings(self):
        description = self.harness.plugin.describe_item(self.item)

        self.assertIn('command=on', description)
        self.assertIn('bridge: expose=switch', description)

    def test_device_report_is_pushed_to_the_bridge(self):
        self.matter_server.push({'event': 'attribute_updated', 'data': [3, '1/6/0', True]})

        self.assertTrue(wait_for(lambda: self.bridge_js.commands('set_attribute')))
        self.assertEqual(self.bridge_js.commands('set_attribute')[0]['args']['value'], True)
        self.assertEqual(self.matter_server.commands('device_command'), [])

    def test_controller_command_reaches_the_device(self):
        endpoint_id = self.harness.plugin.bridge.bridged_items()[0]['endpoint_id']

        self.bridge_js.push({'event': 'command_received', 'data': {'endpoint_id': endpoint_id, 'value': True}})

        self.assertTrue(wait_for(lambda: self.matter_server.commands('device_command')))
        self.assertEqual(self.matter_server.commands('device_command')[0]['args']['command_name'], 'on')
        self.assertEqual(self.bridge_js.commands('set_attribute'), [])


class TestDisabledRole(unittest.TestCase):
    def test_items_of_a_disabled_role_are_ignored_with_one_warning(self):
        harness = PluginHarness(PASSTHROUGH, bridge_enabled=False)
        self.addCleanup(harness.close)

        self.assertIsNone(harness.plugin.bridge)
        self.assertNotIn('bridge', harness.plugin.describe_item(harness.item('plug.sw')))
        with self.assertLogs(harness.plugin.logger, 'WARNING') as logs:
            harness.plugin._warn_disabled_role_items()

        self.assertEqual(len(logs.output), 1)
        self.assertIn('disabled bridge role', logs.output[0])
        self.assertIn('plug.sw', logs.output[0])


class _CrashOnceRole:
    """Role double whose first run() raises, later runs stay up - drives the plugin's real supervisor."""

    name = 'crash_once'
    ITEM_ATTRIBUTES = ()

    def __init__(self):
        self.status = RoleStatus(RoleState.STARTING)
        self.runs = 0
        self.cleanups = 0

    async def run(self):
        self.runs += 1
        if self.runs == 1:
            raise RuntimeError('first run fails')
        await asyncio.Event().wait()

    async def cleanup(self):
        self.cleanups += 1


class TestRoleSupervision(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.harness = PluginHarness('', bridge_enabled=False, server_sidecar_entry='does/not/exist.js')
        self.addCleanup(self.harness.close)
        self.plugin = self.harness.plugin

    async def test_config_error_disables_only_that_role(self):
        other = _CrashOnceRole()
        other.runs = 1
        server_task = asyncio.create_task(self.plugin._supervise_role(self.plugin.server))
        other_task = asyncio.create_task(self.plugin._supervise_role(other))

        await asyncio.wait_for(server_task, 5)

        self.assertEqual(self.plugin.server.status.state, RoleState.FAILED)
        self.assertIn('entry file not found', self.plugin.server.status.detail)
        self.assertFalse(other_task.done())
        other_task.cancel()
        await asyncio.gather(other_task, return_exceptions=True)

    async def test_crashed_role_is_cleaned_up_and_restarted(self):
        role = _CrashOnceRole()
        task = asyncio.create_task(self.plugin._supervise_role(role))

        for _ in range(300):
            if role.runs == 2:
                break
            await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

        self.assertEqual(role.runs, 2)
        self.assertEqual(role.cleanups, 1)

    async def test_server_config_error_is_a_role_config_error(self):
        self.assertIsInstance(self.plugin.server.sidecar, MatterServerSidecar)
        with self.assertRaises(RoleConfigError):
            await self.plugin.server.run()


if __name__ == '__main__':
    unittest.main()
