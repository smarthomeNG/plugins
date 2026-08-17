#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
"""
Unit tests for the bridge role's item handling (bridge.parse_item/
unparse_item/update_item) - exercised against Matter.__new__() with the
handful of SmartPlugin/bridge-specific attributes these functions touch,
same approach as tests/test_alias_resolution.py for the server role.
has_iattr/get_iattr_value/add_item/get_item_config/get_shortname are the
real SmartPlugin implementations (inherited, not faked) - only network I/O
(run_asyncio_coro, bridge_client) is faked, since none of it is exercised
here (the resulting coroutines are closed unawaited, matching the level of
rigor "does the right registration/dispatch decision get made" needs
without spinning up a real asyncio loop or bridge sidecar).
"""

import asyncio
import unittest

from plugins.matter import Matter, bridge, server
from plugins.matter.bridge.client import BridgeCommandError
from plugins.matter.mapping import BridgeMapping


class _FakeItem:
    def __init__(self, path, conf=None):
        self._path = path
        self.conf = conf or {}
        self._value = None
        self.write_calls = []  # (value, caller)

    class _Property:
        def __init__(self, path):
            self.path = path

    @property
    def property(self):
        return self._Property(self._path)

    def __call__(self, value=None, caller=None, source=None, dest=None):
        if value is None and caller is None:
            return self._value
        self._value = value
        self.write_calls.append((value, caller))


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


class _FakeBridgeClient:
    def __init__(self, connected):
        self.connected = connected


def _make_plugin(bridge_client=None, alive=True):
    plugin = Matter.__new__(Matter)
    plugin.logger = _FakeLogger()
    plugin._shortname = 'matter'
    plugin.alive = alive
    plugin._plg_item_dict = {}
    plugin._item_lookup_dict = {}
    plugin._bridge_items = {}
    plugin._bridge_item_by_path = {}
    plugin._bridge_endpoint_id = {}
    plugin._bridge_item_by_endpoint = {}
    plugin.bridge_client = bridge_client
    plugin.run_asyncio_coro_calls = []

    def _fake_run_asyncio_coro(coro):
        plugin.run_asyncio_coro_calls.append(coro)
        coro.close()  # never actually run - avoids "coroutine was never awaited"

    plugin.run_asyncio_coro = _fake_run_asyncio_coro
    return plugin


class TestParseItem(unittest.TestCase):
    def test_no_matter_expose_type_returns_none(self):
        plugin = _make_plugin()
        item = _FakeItem('some.item')

        self.assertIsNone(bridge.parse_item(plugin, item))
        self.assertEqual(plugin._bridge_items, {})

    def test_unknown_expose_type_logs_error_and_returns_none(self):
        plugin = _make_plugin()
        item = _FakeItem('some.item', conf={'matter_expose_type': 'bogus'})

        self.assertIsNone(bridge.parse_item(plugin, item))
        self.assertEqual(plugin._bridge_items, {})
        self.assertEqual(len(plugin.logger.errors), 1)

    def test_name_over_32_chars_logs_error_and_returns_none(self):
        """Regression guard: BridgedDeviceBasicInformation's NodeLabel/ProductName are spec-capped at
        32 chars, and a longer value doesn't truncate, it fails the whole endpoint's construction
        inside bridge.js with a matter.js ConstraintError, dropping the accessory silently from
        Python's point of view (add_endpoint_for_item() only logs a generic 'could not add bridge
        endpoint'). Caught here instead, with a message that actually says why."""
        plugin = _make_plugin()
        item = _FakeItem('some.item', conf={'matter_expose_type': 'switch', 'matter_expose_name': 'x' * 33})

        self.assertIsNone(bridge.parse_item(plugin, item))
        self.assertEqual(plugin._bridge_items, {})
        self.assertEqual(len(plugin.logger.errors), 1)

    def test_name_exactly_32_chars_is_accepted(self):
        plugin = _make_plugin()
        item = _FakeItem('some.item', conf={'matter_expose_type': 'switch', 'matter_expose_name': 'x' * 32})

        self.assertIsNotNone(bridge.parse_item(plugin, item))
        self.assertEqual(plugin.logger.errors, [])

    def test_valid_expose_type_registers_and_returns_update_item(self):
        plugin = _make_plugin()
        item = _FakeItem('some.switch', conf={'matter_expose_type': 'switch'})

        result = bridge.parse_item(plugin, item)

        # Bound methods aren't identical objects per access (a.m is a.m is
        # False) but do compare equal when __self__/__func__ match, which is
        # what item.remove_method_trigger()'s list.remove() actually relies
        # on - see parse_item()'s own comment on why this must be the bound
        # method, not a fresh closure/partial per call.
        self.assertEqual(result, plugin.update_item)
        self.assertIn('some.switch', plugin._bridge_items)
        self.assertIs(plugin._bridge_item_by_path['some.switch'], item)
        self.assertEqual(
            plugin._plg_item_dict['some.switch']['config_data']['matter_bridge_mapping'].expose_type, 'switch'
        )

    def test_name_defaults_to_full_item_path(self):
        """Deliberate default - see matter-integration-plan.md's reasoning
        for why remark/item-name were rejected (collision-prone in a flat
        accessory list, unlike the full path)."""
        plugin = _make_plugin()
        item = _FakeItem('house.living_room.lamp', conf={'matter_expose_type': 'switch'})

        bridge.parse_item(plugin, item)

        self.assertEqual(plugin._bridge_items['house.living_room.lamp'].name, 'house.living_room.lamp')

    def test_explicit_matter_expose_name_overrides_default(self):
        plugin = _make_plugin()
        item = _FakeItem('house.living_room.lamp', conf={'matter_expose_type': 'switch', 'matter_expose_name': 'Lamp'})

        bridge.parse_item(plugin, item)

        self.assertEqual(plugin._bridge_items['house.living_room.lamp'].name, 'Lamp')

    def test_contact_expose_type_registers_and_returns_update_item(self):
        """VALID_EXPOSE_TYPES/parse_item() are type-agnostic - switch isn't special-cased, so this
        (and the temperature_sensor test below) prove contact registers exactly the same way,
        matching bridge.js's own EXPOSE_TYPES coverage for both."""
        plugin = _make_plugin()
        item = _FakeItem('some.contact', conf={'matter_expose_type': 'contact'})

        result = bridge.parse_item(plugin, item)

        self.assertEqual(result, plugin.update_item)
        self.assertEqual(plugin._bridge_items['some.contact'].expose_type, 'contact')

    def test_temperature_sensor_expose_type_registers_and_returns_update_item(self):
        plugin = _make_plugin()
        item = _FakeItem('some.temp', conf={'matter_expose_type': 'temperature_sensor'})

        result = bridge.parse_item(plugin, item)

        self.assertEqual(result, plugin.update_item)
        self.assertEqual(plugin._bridge_items['some.temp'].expose_type, 'temperature_sensor')

    def test_valid_expose_types_is_exactly_switch_contact_temperature_sensor(self):
        """Regression guard, not a design assertion: VALID_EXPOSE_TYPES must stay in lockstep with
        bridge.js's own EXPOSE_TYPES keys (see that module's own comment) - a silent drift here would
        mean parse_item() accepts (or rejects) a type bridge.js doesn't actually agree with."""
        self.assertEqual(set(bridge.VALID_EXPOSE_TYPES), {'switch', 'contact', 'temperature_sensor'})

    def test_no_live_add_when_bridge_not_connected(self):
        plugin = _make_plugin(bridge_client=None)
        item = _FakeItem('some.switch', conf={'matter_expose_type': 'switch'})

        bridge.parse_item(plugin, item)

        self.assertEqual(plugin.run_asyncio_coro_calls, [])

    def test_live_add_triggered_when_bridge_already_connected(self):
        """Covers the edit_item path - an item parsed after the bridge is
        already up, not the initial-load path (that's seed_all_endpoints(),
        called once from run_forever(), not from parse_item())."""
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=True))
        item = _FakeItem('some.switch', conf={'matter_expose_type': 'switch'})

        bridge.parse_item(plugin, item)

        self.assertEqual(len(plugin.run_asyncio_coro_calls), 1)


class TestUnparseItem(unittest.TestCase):
    def test_untracked_item_returns_false(self):
        plugin = _make_plugin()
        item = _FakeItem('not.tracked')

        self.assertFalse(bridge.unparse_item(plugin, item))

    def test_tracked_item_without_endpoint_id_cleans_up_without_remove_call(self):
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=True))
        item = _FakeItem('some.switch', conf={'matter_expose_type': 'switch'})
        bridge.parse_item(plugin, item)
        plugin.run_asyncio_coro_calls.clear()  # parse_item's own live-add call, not what this test checks

        self.assertTrue(bridge.unparse_item(plugin, item))
        self.assertNotIn('some.switch', plugin._bridge_items)
        self.assertNotIn('some.switch', plugin._bridge_item_by_path)
        self.assertEqual(plugin.run_asyncio_coro_calls, [])

    def test_tracked_item_with_endpoint_id_and_connected_client_removes_endpoint(self):
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=True))
        item = _FakeItem('some.switch', conf={'matter_expose_type': 'switch'})
        bridge.parse_item(plugin, item)
        plugin._bridge_endpoint_id['some.switch'] = 7
        plugin._bridge_item_by_endpoint[7] = item
        plugin.run_asyncio_coro_calls.clear()

        self.assertTrue(bridge.unparse_item(plugin, item))
        self.assertNotIn('some.switch', plugin._bridge_endpoint_id)
        self.assertNotIn(7, plugin._bridge_item_by_endpoint)
        self.assertEqual(len(plugin.run_asyncio_coro_calls), 1)


class TestUpdateItem(unittest.TestCase):
    def test_own_write_is_ignored(self):
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=True))
        item = _FakeItem('some.switch')
        plugin._bridge_endpoint_id['some.switch'] = 1

        bridge.update_item(plugin, item, caller=bridge.own_caller(plugin))

        self.assertEqual(plugin.run_asyncio_coro_calls, [])

    def test_server_own_write_on_a_passthrough_item_is_NOT_ignored(self):
        """Regression guard: a passthrough item (both server- and
        bridge-configured, see bridge.parse_item()'s own docstring) must
        still push a device-report-driven write out to the bridge. A
        shared own-write sentinel between the two roles used to swallow
        this - server.own_caller(plugin) is a different string from
        bridge.own_caller(plugin) specifically so this doesn't match the
        guard above."""
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=True))
        item = _FakeItem('some.switch')
        plugin._bridge_endpoint_id['some.switch'] = 1

        bridge.update_item(plugin, item, caller=server.own_caller(plugin))

        self.assertEqual(len(plugin.run_asyncio_coro_calls), 1)

    def test_bridge_own_write_on_a_passthrough_item_is_NOT_ignored_by_server(self):
        """Mirror of the test above, other direction: a command arriving via
        the bridge (Apple Home, ...) on a passthrough item must still reach
        server.update_item to command the real device. Only checks that
        server.update_item() gets *past* its own-write guard (proceeds to
        its next check, the server_client connectivity warning) - not the
        full command-sending path, which needs a real command_mapping
        fixture test_alias_resolution.py already doesn't build either."""
        plugin = Matter.__new__(Matter)
        plugin.logger = _FakeLogger()
        plugin._shortname = 'matter'
        plugin.alive = True
        plugin.server_client = None
        item = _FakeItem('some.switch')

        server.update_item(plugin, item, caller=bridge.own_caller(plugin))

        self.assertEqual(len(plugin.logger.warnings), 1)

    def test_not_alive_is_ignored(self):
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=True), alive=False)
        item = _FakeItem('some.switch')
        plugin._bridge_endpoint_id['some.switch'] = 1

        bridge.update_item(plugin, item, caller='some_other_plugin')

        self.assertEqual(plugin.run_asyncio_coro_calls, [])

    def test_unknown_endpoint_is_dropped_silently(self):
        """No endpoint yet - bridge not connected when the item first parsed,
        or add_endpoint failed. Not an error case worth logging on every
        write; seed_all_endpoints()/parse_item()'s own live-add already log
        the actual add failure once."""
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=True))
        item = _FakeItem('some.switch')

        bridge.update_item(plugin, item, caller='some_other_plugin')

        self.assertEqual(plugin.run_asyncio_coro_calls, [])
        self.assertEqual(plugin.logger.warnings, [])

    def test_known_endpoint_with_connected_client_pushes_value(self):
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=True))
        item = _FakeItem('some.switch')
        plugin._bridge_endpoint_id['some.switch'] = 1

        bridge.update_item(plugin, item, caller='some_other_plugin')

        self.assertEqual(len(plugin.run_asyncio_coro_calls), 1)

    def test_known_endpoint_without_connection_warns_and_does_not_push(self):
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=False))
        item = _FakeItem('some.switch')
        plugin._bridge_endpoint_id['some.switch'] = 1

        bridge.update_item(plugin, item, caller='some_other_plugin')

        self.assertEqual(plugin.run_asyncio_coro_calls, [])
        self.assertEqual(len(plugin.logger.warnings), 1)


class TestOnEvent(unittest.TestCase):
    def test_command_received_writes_the_mapped_item(self):
        plugin = _make_plugin()
        item = _FakeItem('some.switch')
        plugin._bridge_item_by_endpoint[5] = item

        bridge.on_event(plugin, {'event': 'command_received', 'data': {'endpoint_id': 5, 'value': True}})

        self.assertEqual(item.write_calls, [(True, bridge.own_caller(plugin))])

    def test_command_received_for_unknown_endpoint_logs_warning(self):
        plugin = _make_plugin()

        bridge.on_event(plugin, {'event': 'command_received', 'data': {'endpoint_id': 999, 'value': True}})

        self.assertEqual(len(plugin.logger.warnings), 1)

    def test_other_events_are_ignored(self):
        plugin = _make_plugin()

        bridge.on_event(plugin, {'event': 'something_else', 'data': {}})
        # no exception, nothing to assert - just must not touch item lookups


class _RaisingBridgeClient:
    """set_attribute()/remove_endpoint() raise the given exception - for
    testing that bridge.py's async helpers actually catch it, not just that
    run_asyncio_coro() was called (the fake in _make_plugin() closes every
    coroutine unawaited, so it never exercises what's inside them)."""

    def __init__(self, exception):
        self.connected = True
        self._exception = exception

    async def set_attribute(self, endpoint_id, value):
        raise self._exception

    async def remove_endpoint(self, endpoint_id):
        raise self._exception

    async def get_status(self):
        raise self._exception

    async def get_fabrics(self):
        raise self._exception

    async def open_commissioning_window(self):
        raise self._exception

    async def remove_fabric(self, fabric_index):
        raise self._exception


class _FakeStatusBridgeClient:
    """get_status()/get_fabrics() return fixed real-shaped data - for testing the success path."""

    def __init__(self, status, fabrics):
        self.connected = True
        self._status = status
        self._fabrics = fabrics

    async def get_status(self):
        return self._status

    async def get_fabrics(self):
        return self._fabrics


class TestBridgeErrorHandling(unittest.TestCase):
    """Regression tests: a TimeoutError from bridge.js/the WS connection used
    to surface as a bare uncaught traceback through Item.__update() instead
    of being logged clearly - same bug class as the server role's
    update_item(), fixed the same way here."""

    def test_set_attribute_timeout_is_caught_and_logged_clearly(self):
        plugin = _make_plugin()
        plugin.bridge_client = _RaisingBridgeClient(TimeoutError())

        asyncio.run(bridge._set_attribute_quietly(plugin, 'some.switch', 1, True))

        self.assertEqual(len(plugin.logger.warnings), 1)
        self.assertIn('timed out', plugin.logger.warnings[0])

    def test_set_attribute_connection_error_is_caught_and_logged(self):
        plugin = _make_plugin()
        plugin.bridge_client = _RaisingBridgeClient(ConnectionError('not connected'))

        asyncio.run(bridge._set_attribute_quietly(plugin, 'some.switch', 1, True))

        self.assertEqual(len(plugin.logger.warnings), 1)
        self.assertIn('not connected', plugin.logger.warnings[0])

    def test_set_attribute_bridge_command_error_is_caught_and_logged(self):
        plugin = _make_plugin()
        plugin.bridge_client = _RaisingBridgeClient(BridgeCommandError('set_attribute', {'error': 'no endpoint 1'}))

        asyncio.run(bridge._set_attribute_quietly(plugin, 'some.switch', 1, True))

        self.assertEqual(len(plugin.logger.warnings), 1)

    def test_remove_endpoint_timeout_is_caught_and_logged_clearly(self):
        plugin = _make_plugin()
        plugin.bridge_client = _RaisingBridgeClient(TimeoutError())

        asyncio.run(bridge._remove_endpoint_quietly(plugin, 'some.switch', 1))

        self.assertEqual(len(plugin.logger.warnings), 1)
        self.assertIn('timed out', plugin.logger.warnings[0])


class TestBridgeWebifFunctions(unittest.TestCase):
    """
    get_bridge_status()/get_bridge_fabrics() are read-only and always
    rendered (not flash-gated) - must degrade to a clear empty/unavailable
    shape rather than raising, same reasoning as get_node_summaries() on the
    server side. open_bridge_commissioning_window()/remove_bridge_fabric()
    are explicit user actions - the opposite: errors must propagate so the
    webif's own try/except can turn them into a flash message, not be
    silently swallowed here.
    """

    def test_get_bridge_status_no_client_returns_unavailable(self):
        plugin = _make_plugin(bridge_client=None)
        self.assertEqual(bridge.get_bridge_status(plugin), {'available': False})

    def test_get_bridge_status_not_connected_returns_unavailable(self):
        plugin = _make_plugin(bridge_client=_FakeBridgeClient(connected=False))
        self.assertEqual(bridge.get_bridge_status(plugin), {'available': False})

    def test_get_bridge_status_error_degrades_to_unavailable_and_logs(self):
        plugin = _make_plugin()
        plugin.bridge_client = _RaisingBridgeClient(TimeoutError())
        plugin.run_asyncio_coro = lambda coro: asyncio.run(coro)

        self.assertEqual(bridge.get_bridge_status(plugin), {'available': False})
        self.assertEqual(len(plugin.logger.warnings), 1)

    def test_get_bridge_status_success_marks_available_and_passes_data_through(self):
        plugin = _make_plugin()
        status = {
            'passcode': 20202021,
            'discriminator': 3840,
            'manual_pairing_code': '34970112332',
            'qr_pairing_code': 'MT:...',
            'commissioned': True,
            'fabric_count': 1,
        }
        plugin.bridge_client = _FakeStatusBridgeClient(status, fabrics=[])
        plugin.run_asyncio_coro = lambda coro: asyncio.run(coro)

        result = bridge.get_bridge_status(plugin)

        self.assertEqual(result, {**status, 'available': True})

    def test_get_bridge_fabrics_no_client_returns_empty(self):
        plugin = _make_plugin(bridge_client=None)
        self.assertEqual(bridge.get_bridge_fabrics(plugin), [])

    def test_get_bridge_fabrics_error_degrades_to_empty_and_logs(self):
        plugin = _make_plugin()
        plugin.bridge_client = _RaisingBridgeClient(ConnectionError('not connected'))
        plugin.run_asyncio_coro = lambda coro: asyncio.run(coro)

        self.assertEqual(bridge.get_bridge_fabrics(plugin), [])
        self.assertEqual(len(plugin.logger.warnings), 1)

    def test_get_bridge_fabrics_success_returns_the_list(self):
        plugin = _make_plugin()
        fabrics = [{'fabric_index': 1, 'vendor_id': 65521, 'fabric_label': 'Apple Home', 'fabric_id': '123'}]
        plugin.bridge_client = _FakeStatusBridgeClient(status={}, fabrics=fabrics)
        plugin.run_asyncio_coro = lambda coro: asyncio.run(coro)

        self.assertEqual(bridge.get_bridge_fabrics(plugin), fabrics)

    def test_get_bridge_items_reads_live_state_no_client_needed(self):
        """No bridge.js round-trip - plugin._bridge_items/_bridge_endpoint_id are already live state."""
        plugin = _make_plugin()
        item = _FakeItem('some.switch', conf={'matter_expose_type': 'switch', 'matter_expose_name': 'Lamp'})
        bridge.parse_item(plugin, item)
        plugin._bridge_endpoint_id['some.switch'] = 5

        self.assertEqual(
            bridge.get_bridge_items(plugin),
            [{'item_path': 'some.switch', 'expose_type': 'switch', 'name': 'Lamp', 'endpoint_id': 5}],
        )

    def test_get_bridge_items_endpoint_id_none_when_not_yet_added(self):
        plugin = _make_plugin()
        item = _FakeItem('some.switch', conf={'matter_expose_type': 'switch'})
        bridge.parse_item(plugin, item)

        self.assertIsNone(bridge.get_bridge_items(plugin)[0]['endpoint_id'])

    def test_open_bridge_commissioning_window_propagates_error(self):
        plugin = _make_plugin()
        plugin.bridge_client = _RaisingBridgeClient(BridgeCommandError('open_commissioning_window', {'error': 'x'}))
        plugin.run_asyncio_coro = lambda coro: asyncio.run(coro)

        with self.assertRaises(BridgeCommandError):
            bridge.open_bridge_commissioning_window(plugin)

    def test_remove_bridge_fabric_propagates_error(self):
        plugin = _make_plugin()
        plugin.bridge_client = _RaisingBridgeClient(BridgeCommandError('remove_fabric', {'error': 'x'}))
        plugin.run_asyncio_coro = lambda coro: asyncio.run(coro)

        with self.assertRaises(BridgeCommandError):
            bridge.remove_bridge_fabric(plugin, 3)


if __name__ == '__main__':
    unittest.main()
