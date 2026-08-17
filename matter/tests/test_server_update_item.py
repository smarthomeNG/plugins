#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Regression tests for server.update_item()'s exception handling: a
TimeoutError from matter-server/the device not responding used to surface as
a bare uncaught traceback through Item.__update() instead of being logged
clearly. Exercises the real update_item() with a fake server_client whose
device_command() actually raises, driven through a real asyncio.run() (not
a closed-unawaited coroutine) so the try/except inside update_item() is
genuinely exercised, not just checked for having been called.
"""

import asyncio
import unittest

from plugins.matter import Matter, server
from plugins.matter.mapping import CommandMapping
from plugins.matter.server.client import MatterCommandError


class _FakeItem:
    def __init__(self, path, value=True):
        self._path = path
        self._value = value

    class _Property:
        def __init__(self, path):
            self.path = path

    @property
    def property(self):
        return self._Property(self._path)

    def __call__(self):
        return self._value


class _FakeLogger:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def error(self, msg):
        self.errors.append(msg)

    def warning(self, msg):
        self.warnings.append(msg)

    def debug(self, msg):
        pass


class _RaisingServerClient:
    """device_command()/write_attribute() raise the given exception."""

    def __init__(self, exception):
        self.connected = True
        self._exception = exception

    async def device_command(self, node_id, endpoint_id, cluster_id, command_name, params):
        raise self._exception

    async def write_attribute(self, node_id, path, value):
        raise self._exception


def _make_plugin(server_client):
    plugin = Matter.__new__(Matter)
    plugin.logger = _FakeLogger()
    plugin._shortname = 'matter'
    plugin.alive = True
    plugin.server_client = server_client
    plugin._server_aliases = {}
    plugin._plg_item_dict = {}
    plugin._item_lookup_dict = {}
    plugin.run_asyncio_coro = lambda coro: asyncio.run(coro)
    return plugin


def _register_command_item(plugin, item):
    mapping = CommandMapping(node_id=1, endpoint_id=2, cluster_id=6, command_name='toggle')
    plugin._plg_item_dict[item.property.path] = {
        'item': item,
        'is_updating': True,
        'mapping': None,
        'config_data': {'matter_command_mapping': mapping},
    }


class TestUpdateItemErrorHandling(unittest.TestCase):
    def test_timeout_error_is_caught_and_logged_clearly(self):
        plugin = _make_plugin(_RaisingServerClient(TimeoutError()))
        item = _FakeItem('some.switch')
        _register_command_item(plugin, item)

        server.update_item(plugin, item, caller='some_other_plugin')

        self.assertEqual(len(plugin.logger.errors), 1)
        self.assertIn('timed out', plugin.logger.errors[0])

    def test_connection_error_is_caught_and_logged(self):
        plugin = _make_plugin(_RaisingServerClient(ConnectionError('not connected to matter-server')))
        item = _FakeItem('some.switch')
        _register_command_item(plugin, item)

        server.update_item(plugin, item, caller='some_other_plugin')

        self.assertEqual(len(plugin.logger.errors), 1)
        self.assertIn('not connected', plugin.logger.errors[0])

    def test_matter_command_error_is_caught_and_logged(self):
        plugin = _make_plugin(_RaisingServerClient(MatterCommandError('device_command', {'error_code': 1})))
        item = _FakeItem('some.switch')
        _register_command_item(plugin, item)

        server.update_item(plugin, item, caller='some_other_plugin')

        self.assertEqual(len(plugin.logger.errors), 1)


if __name__ == '__main__':
    unittest.main()
