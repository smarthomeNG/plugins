#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Matter bridge role: exposes shng items to other Matter ecosystems
#  (Apple Home, Google Home, ...) as bridged accessories on this plugin's
#  own @matter/node application (sidecar/bridge.js, supervised/talked to
#  from here via sidecar.py/client.py) - a separate Matter identity from
#  the server role's fabric, not something matter-server is involved in at
#  all. bridge.js itself lives under sidecar/, not bridge/, so it shares
#  one Node.js dependency tree with the server role instead of installing
#  separately - see user_doc.rst. See dev/matter/matter-integration-plan.md
#  in the core (shng) repo for the full design, including the live test
#  against Apple Home the dynamic add_endpoint/remove_endpoint design is
#  built on.
#
#  Same function-takes-plugin-first-arg pattern as server/__init__.py.
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

from __future__ import annotations

import asyncio
import contextlib

from ..mapping import BridgeMapping
from .client import BridgeCommandError, MatterBridgeClient
from .sidecar import RESTART_BACKOFF_SECONDS, BridgeSidecarStartError, MatterBridgeSidecar

# v1 scope only - see matter-integration-plan.md's "Bridge item-attribute
# surface" section for why these three and not more yet (no low-level
# escape hatch, no thermostat - both explicitly deferred until a real use
# case shows up). Must match bridge.js's own EXPOSE_TYPES keys and
# plugin.yaml's matter_expose_type valid_list.
VALID_EXPOSE_TYPES = ('switch', 'contact', 'temperature_sensor')

# What every bridge_client call below can raise: BridgeCommandError (bridge.js
# answered with an "error"), ConnectionError (not connected - can race the
# plugin.bridge_client.connected check callers do before these run),
# TimeoutError (client.py's send_command() gives up after its own 30s
# asyncio.wait_for(), e.g. when the bridge sidecar or the WS connection
# doesn't respond in time). Tolerated everywhere here rather than left to
# surface as a bare traceback through Item.__update()'s generic handler -
# same "hiccups are tolerated, log clearly" approach server/__init__.py's
# update_item() takes for the equivalent matter-server exceptions.
_BRIDGE_ERRORS = (BridgeCommandError, TimeoutError, ConnectionError)


def _describe_bridge_error(ex: Exception) -> str:
    """str(TimeoutError()) is empty - give it a real message; the other two already stringify usefully."""
    if isinstance(ex, TimeoutError):
        return 'timed out - bridge sidecar or the WS connection did not respond in time'
    return str(ex)


# -- lifecycle --


async def run_forever(plugin):
    plugin.bridge_sidecar = MatterBridgeSidecar(
        plugin.node_binary,
        plugin.bridge_sidecar_entry,
        plugin.bridge_matter_port,
        plugin.bridge_control_port,
        plugin.bridge_storage_path,
        plugin.bridge_passcode,
        plugin.bridge_discriminator,
        plugin.bridge_vendor_id,
        logger=plugin.logger,
        primary_interface=plugin.primary_interface,
    )
    try:
        await plugin.bridge_sidecar.start()
    except BridgeSidecarStartError as ex:
        plugin.logger.error(str(ex))
        return  # config problem, not something retrying fixes - stay idle rather than loop forever

    plugin.bridge_sidecar_supervisor_task = asyncio.create_task(
        plugin.bridge_sidecar.supervise(), name='matter-bridge-sidecar-supervisor'
    )
    await connect_client_with_retry(plugin)
    await seed_all_endpoints(plugin)

    while plugin.alive:
        await asyncio.sleep(5)
        if not plugin.bridge_client.connected:
            plugin.logger.warning('lost connection to matter bridge sidecar, reconnecting...')
            await connect_client_with_retry(plugin)
            # A bridge sidecar restart loses every dynamically-added endpoint
            # in memory (not its commissioned identity, which is persisted) -
            # re-add everything currently configured rather than leaving the
            # bridge silently missing accessories until shng restarts too.
            await seed_all_endpoints(plugin)


async def connect_client_with_retry(plugin) -> None:
    attempt = 0
    while plugin.alive:
        plugin.bridge_client = MatterBridgeClient(
            f'ws://127.0.0.1:{plugin.bridge_control_port}',
            on_event=lambda message: on_event(plugin, message),
            logger=plugin.logger,
        )
        try:
            await plugin.bridge_client.connect()
            plugin.logger.info('connected to matter bridge sidecar')
            return
        except Exception as ex:
            delay = RESTART_BACKOFF_SECONDS[min(attempt, len(RESTART_BACKOFF_SECONDS) - 1)]
            plugin.logger.warning(f'could not connect to matter bridge sidecar ({ex}), retrying in {delay}s')
            attempt += 1
            await asyncio.sleep(delay)


async def seed_all_endpoints(plugin) -> None:
    """(Re-)add every configured matter_expose_* item's endpoint and push its current value."""
    for item_path, mapping in plugin._bridge_items.items():
        await add_endpoint_for_item(plugin, item_path, mapping)


async def add_endpoint_for_item(plugin, item_path: str, mapping: BridgeMapping) -> None:
    item = plugin._bridge_item_by_path.get(item_path)
    if item is None:
        return
    try:
        endpoint_id = await plugin.bridge_client.add_endpoint(mapping.item_path, mapping.expose_type, mapping.name)
    except _BRIDGE_ERRORS as ex:
        plugin.logger.error(f'{item_path}: could not add bridge endpoint ({_describe_bridge_error(ex)})')
        return
    plugin._bridge_endpoint_id[item_path] = endpoint_id
    plugin._bridge_item_by_endpoint[endpoint_id] = item
    try:
        await plugin.bridge_client.set_attribute(endpoint_id, item())
    except _BRIDGE_ERRORS as ex:
        plugin.logger.warning(
            f'{item_path}: added bridge endpoint but could not seed its initial value ({_describe_bridge_error(ex)})'
        )


async def cleanup(plugin):
    # Cancelled first, and awaited, before anything else - same race as
    # server.cleanup()'s equivalent guard, see server_sidecar_supervisor_task's own
    # declaration (plugins/matter/__init__.py) for the full reasoning: without this,
    # a bridge sidecar dying at the wrong moment during shutdown could still get
    # restarted by the *old* supervise() loop before stop() below ever runs (observed:
    # a fresh pid showed up mid-shutdown in a real log).
    if plugin.bridge_sidecar_supervisor_task is not None:
        plugin.bridge_sidecar_supervisor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await plugin.bridge_sidecar_supervisor_task
        plugin.bridge_sidecar_supervisor_task = None
    if plugin.bridge_client is not None:
        await plugin.bridge_client.close()
    if plugin.bridge_sidecar is not None:
        await plugin.bridge_sidecar.stop()


def own_caller(plugin) -> str:
    """
    Caller identity for this role's own item writes - see
    server.own_caller()'s docstring for why this must differ from that
    one (not share a sentinel with bridge), and why get_fullname() rather
    than get_shortname() (this plugin is multi-instance capable).
    """
    return f'{plugin.get_fullname()}:bridge'


def on_event(plugin, message: dict) -> None:
    """Called on the plugin's asyncio thread whenever bridge.js pushes an unsolicited event."""
    if message.get('event') != 'command_received':
        return
    data = message.get('data') or {}
    endpoint_id = data.get('endpoint_id')
    value = data.get('value')
    item = plugin._bridge_item_by_endpoint.get(endpoint_id)
    if item is None:
        plugin.logger.warning(f'command_received for unknown bridge endpoint {endpoint_id}: {message}')
        return
    item(value, own_caller(plugin))


# -- item handling --


def parse_item(plugin, item):
    if not plugin.has_iattr(item.conf, 'matter_expose_type'):
        return None

    expose_type = plugin.get_iattr_value(item.conf, 'matter_expose_type')
    if expose_type not in VALID_EXPOSE_TYPES:
        plugin.logger.error(
            f"{item.property.path}: matter_expose_type '{expose_type}' is not one of {VALID_EXPOSE_TYPES}"
        )
        return None

    # Full item path, not remark/item name: the only structurally-unique
    # default available without requiring the user to set anything - see
    # matter-integration-plan.md's "matter_expose_name" reasoning (a flat
    # accessory list has no item-tree context to disambiguate identically-
    # worded remarks or names the way shng's own item tree does).
    name = plugin.get_iattr_value(item.conf, 'matter_expose_name', item.property.path) or item.property.path

    # bridge.js writes *name* into BridgedDeviceBasicInformation's NodeLabel/
    # ProductName, both spec-capped at 32 chars (Matter Core Spec, Basic
    # Information cluster) - a longer value doesn't get silently truncated,
    # it fails the whole endpoint's construction with a matter.js
    # ConstraintError, dropping the accessory entirely. Caught here, not in
    # bridge.js, for the same reason
    # the unknown-expose_type check above is: a clear, early, item-path-
    # attributed log line beats a cryptic JS stack trace three layers removed
    # from the actual misconfiguration.
    if len(name) > 32:
        plugin.logger.error(
            f'{item.property.path}: matter_expose_name (or the item path, if unset) is {len(name)} chars, '
            f"over the 32-char limit Matter imposes on a bridged accessory's display name - set a shorter "
            f'matter_expose_name'
        )
        return None

    item_path = item.property.path
    mapping = BridgeMapping(item_path=item_path, expose_type=expose_type, name=name)
    plugin._bridge_items[item_path] = mapping
    plugin._bridge_item_by_path[item_path] = item
    plugin.add_item(item, config_data_dict={'matter_bridge_mapping': mapping}, mapping=None)

    if plugin.bridge_client is not None and plugin.bridge_client.connected:
        # Live add: an item parsed after the bridge is already up (edit_item,
        # not initial load) - run_forever()'s own seed_all_endpoints() covers
        # every item that existed at startup/reconnect already.
        plugin.run_asyncio_coro(add_endpoint_for_item(plugin, item_path, mapping))

    # Must be plugin.update_item specifically, not a fresh closure/partial each
    # call: SmartPlugin.remove_item() hardcodes item.remove_method_trigger(self.update_item)
    # for cleanup, matched by object identity - a different callable here would
    # silently fail to unregister (caught by remove_item()'s own bare except).
    return plugin.update_item


def unparse_item(plugin, item) -> bool:
    item_path = item.property.path
    if item_path not in plugin._bridge_items:
        return False

    del plugin._bridge_items[item_path]
    plugin._bridge_item_by_path.pop(item_path, None)
    endpoint_id = plugin._bridge_endpoint_id.pop(item_path, None)
    if endpoint_id is not None:
        plugin._bridge_item_by_endpoint.pop(endpoint_id, None)
        if plugin.bridge_client is not None and plugin.bridge_client.connected:
            plugin.run_asyncio_coro(_remove_endpoint_quietly(plugin, item_path, endpoint_id))
    return True


async def _remove_endpoint_quietly(plugin, item_path: str, endpoint_id: int) -> None:
    """Item edits/removals are usually a manual admin action - tolerate a hiccup rather than raise into it."""
    try:
        await plugin.bridge_client.remove_endpoint(endpoint_id)
    except _BRIDGE_ERRORS as ex:
        plugin.logger.warning(
            f'{item_path}: could not remove bridge endpoint {endpoint_id} ({_describe_bridge_error(ex)})'
        )


def update_item(plugin, item, caller=None, source=None, dest=None):
    if not plugin.alive or caller == own_caller(plugin):
        return
    item_path = item.property.path
    endpoint_id = plugin._bridge_endpoint_id.get(item_path)
    if endpoint_id is None:
        return  # endpoint not added yet (bridge not connected, or add_endpoint failed) - drop the write
    if plugin.bridge_client is None or not plugin.bridge_client.connected:
        plugin.logger.warning(f'cannot push {item_path} to bridge: not connected to matter bridge sidecar')
        return
    plugin.run_asyncio_coro(_set_attribute_quietly(plugin, item_path, endpoint_id, item()))


async def _set_attribute_quietly(plugin, item_path: str, endpoint_id: int, value) -> None:
    try:
        await plugin.bridge_client.set_attribute(endpoint_id, value)
    except _BRIDGE_ERRORS as ex:
        plugin.logger.warning(
            f'{item_path}: could not push value to bridge endpoint {endpoint_id} ({_describe_bridge_error(ex)})'
        )


# -- webif: bridge view --


def get_bridge_status(plugin) -> dict:
    """
    Read-only, always rendered (not flash-gated) - degrades to
    {'available': False} on any error rather than raising, same reasoning
    as get_node_summaries() on the server side: a status card showing
    "unavailable" is better than the whole page failing to render because
    the bridge sidecar happened to hiccup on one poll.
    """
    if plugin.bridge_client is None or not plugin.bridge_client.connected:
        return {'available': False}
    try:
        status = plugin.run_asyncio_coro(plugin.bridge_client.get_status())
    except _BRIDGE_ERRORS as ex:
        plugin.logger.warning(f'could not read bridge status ({_describe_bridge_error(ex)})')
        return {'available': False}
    return {**status, 'available': True}


def get_bridge_fabrics(plugin) -> list:
    """Same degrade-gracefully reasoning as get_bridge_status() - an empty table beats a failed page render."""
    if plugin.bridge_client is None or not plugin.bridge_client.connected:
        return []
    try:
        return plugin.run_asyncio_coro(plugin.bridge_client.get_fabrics())
    except _BRIDGE_ERRORS as ex:
        plugin.logger.warning(f'could not read bridge fabrics ({_describe_bridge_error(ex)})')
        return []


def get_bridge_items(plugin) -> list:
    """No bridge.js round-trip - already-live plugin state, same source add_endpoint_for_item() reads from."""
    return [
        {
            'item_path': item_path,
            'expose_type': mapping.expose_type,
            'name': mapping.name,
            'endpoint_id': plugin._bridge_endpoint_id.get(item_path),
        }
        for item_path, mapping in plugin._bridge_items.items()
    ]


def open_bridge_commissioning_window(plugin) -> None:
    """
    An explicit user action (webif button), not best-effort background work -
    exceptions propagate, same as server.commission()/server.remove_matter_fabric():
    the webif's own try/except turns them into a flash error, not a swallowed log line.
    """
    plugin.run_asyncio_coro(plugin.bridge_client.open_commissioning_window())


def remove_bridge_fabric(plugin, fabric_index: int) -> None:
    """Same as open_bridge_commissioning_window() - an explicit action, exceptions propagate to the webif."""
    plugin.run_asyncio_coro(plugin.bridge_client.remove_fabric(fabric_index))
