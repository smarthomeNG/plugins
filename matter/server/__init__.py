#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Matter controller ("server") role: commissions and controls real Matter
#  devices via the matter-server Node.js sidecar (sidecar.py) over a
#  WebSocket (client.py), mirroring cluster attributes/commands onto shng
#  items (mapping.py, shared with the bridge role) and managing the
#  matter_alias node_id-indirection layer.
#
#  Extracted from plugins/matter/__init__.py - every function here takes the
#  Matter plugin instance as its first argument (same pattern as
#  lib/item/_internal/*.py's relationship to lib/item/item.py), so state
#  (self.server_sidecar, self.server_client, self._server_aliases, ...)
#  still lives on the one plugin instance rather than a separate object.
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
import functools

from ..clusters import switch_info
from ..mapping import (
    AttributeMapping,
    CommandMapping,
    alias_availability_mapping_key,
    alias_mapping_key,
    availability_mapping_key,
    report_mapping_key,
)
from .client import MatterCommandError, MatterServerClient
from .discovery import discovery_rows, generate_suggested_item, node_summary
from .sidecar import RESTART_BACKOFF_SECONDS, MatterServerSidecar, SidecarStartError

DEFAULT_ALIAS_BASE_REMARK = 'matter alias base item, child items are alias definitions, do not change'

# -- lifecycle --


async def run_forever(plugin):
    plugin.server_sidecar = MatterServerSidecar(
        plugin.node_binary,
        plugin.server_sidecar_entry,
        plugin.server_sidecar_port,
        plugin.storage_path,
        plugin.server_enable_test_net_dcl,
        logger=plugin.logger,
        primary_interface=plugin.primary_interface,
        fabric_vendor_id=plugin.server_fabric_vendor_id,
        fabric_label=plugin.server_fabric_label,
    )
    try:
        await plugin.server_sidecar.start()
    except SidecarStartError as ex:
        plugin.logger.error(str(ex))
        return  # config problem, not something retrying fixes - stay idle rather than loop forever

    plugin.server_sidecar_supervisor_task = asyncio.create_task(
        plugin.server_sidecar.supervise(), name='matter-sidecar-supervisor'
    )
    await connect_client_with_retry(plugin)
    seed_initial_values(plugin, await plugin.server_client.start_listening())

    while plugin.alive:
        await asyncio.sleep(5)
        if not plugin.server_client.connected:
            plugin.logger.warning('lost connection to matter server sidecar, reconnecting...')
            await connect_client_with_retry(plugin)
            seed_initial_values(plugin, await plugin.server_client.start_listening())


async def connect_client_with_retry(plugin) -> None:
    attempt = 0
    while plugin.alive:
        plugin.server_client = MatterServerClient(
            f'ws://localhost:{plugin.server_sidecar_port}/ws',
            on_event=lambda message: on_event(plugin, message),
            on_late_result=lambda command, message: on_late_result(plugin, command, message),
            logger=plugin.logger,
        )
        try:
            await plugin.server_client.connect()
            plugin.logger.info('connected to matter server sidecar')
            return
        except Exception as ex:
            delay = RESTART_BACKOFF_SECONDS[min(attempt, len(RESTART_BACKOFF_SECONDS) - 1)]
            plugin.logger.warning(f'could not connect to matter server sidecar ({ex}), retrying in {delay}s')
            attempt += 1
            await asyncio.sleep(delay)


async def cleanup(plugin):
    # Cancelled first, and awaited, before anything else - closes the race documented
    # on server_sidecar_supervisor_task's own declaration (plugins/matter/__init__.py):
    # supervise() only stops restarting once it observes sidecar._stopping, which
    # sidecar.stop() below is what sets - without cancelling supervise() explicitly
    # first, a sidecar process dying at the wrong moment during shutdown could still
    # get restarted by the *old* supervise() loop before stop() ever runs.
    if plugin.server_sidecar_supervisor_task is not None:
        plugin.server_sidecar_supervisor_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await plugin.server_sidecar_supervisor_task
        plugin.server_sidecar_supervisor_task = None
    if plugin.server_client is not None:
        await plugin.server_client.close()
    if plugin.server_sidecar is not None:
        await plugin.server_sidecar.stop()


def on_event(plugin, message: dict) -> None:
    """Called on the plugin's asyncio thread whenever matter-server pushes an unsolicited event."""
    event = message.get('event')
    if event == 'attribute_updated':
        try:
            node_id, path, value = message['data']
        except (KeyError, ValueError):
            plugin.logger.warning(f'malformed attribute_updated event: {message}')
            return
        apply_attribute(plugin, node_id, path, value)
    elif event == 'node_updated':
        # Full node_updated payload matches get_nodes()'s entry shape (matter-server's
        # nodeAvailabilityChanged, see ControllerCommandHandler.ts) - only 'available' used here.
        data = message.get('data') or {}
        node_id = data.get('node_id')
        available = data.get('available')
        if node_id is None or available is None:
            plugin.logger.warning(f'malformed node_updated event: {message}')
            return
        apply_availability(plugin, node_id, available)


def on_late_result(plugin, command: str, message: dict) -> None:
    """
    Called on the plugin's asyncio thread when matter-server answers a
    request after MatterServerClient.send_command()'s own timeout already
    gave up on it (see client.py's _timed_out/_remember_timeout) - the
    original caller (e.g. the webif's commission() call) already got a
    TimeoutError and returned, so this is the only place that answer still
    exists. Only commission_with_code is queued for the webif to pick up
    (get_late_commission_results()/webif's get_data_html poll) - it's the
    one long-running, user-initiated action where a late answer is actually
    actionable; other commands' late answers are still logged (by the
    client itself) but not surfaced further, nothing currently waits on one.
    """
    if command != 'commission_with_code':
        return
    if 'error_code' in message:
        plugin._late_commission_results.append(
            {'success': False, 'detail': message.get('details') or f'error_code={message.get("error_code")}'}
        )
    else:
        result = message.get('result') or {}
        plugin._late_commission_results.append({'success': True, 'detail': f'node_id={result.get("node_id")}'})


def drain_late_commission_results(plugin) -> list:
    """Pop-all: each result is meant to be shown to the webif user exactly once, then discarded."""
    results = list(plugin._late_commission_results)
    plugin._late_commission_results.clear()
    return results


def own_caller(plugin) -> str:
    """
    Caller identity for this role's own item writes - distinct from
    bridge.own_caller()'s, not just plugin.get_fullname() shared by both.

    A passthrough item (both matter_attribute_mapping/matter_command_mapping
    and matter_bridge_mapping - see parse_item()'s own docstring) needs a
    write from one role to reach the other: a device report should still
    push out to the bridge, a bridge command should still reach the real
    device. A single shared sentinel can't tell "my own write, suppress"
    from "the other role's write, propagate" - it looks identical from
    either role's own_item guard. Matches the caller decoration convention
    zigbee2mqtt's plugin already uses for the same class of problem
    (get_fullname() + ':' + <sub-identity>), not invented fresh here.

    get_fullname() (shortname + '_' + instance name), not get_shortname():
    this plugin is multi-instance capable, and get_shortname() alone would
    be identical across every instance, letting one instance's own write
    be wrongly suppressed by (or wrongly propagate through) another
    instance's guard.
    """
    return f'{plugin.get_fullname()}:server'


def apply_attribute(plugin, node_id: int, path: str, value) -> None:
    for item in plugin.get_items_for_mapping(report_mapping_key(node_id, path)):
        item(value, own_caller(plugin))
    for alias in plugin._server_node_to_alias.get(node_id, ()):
        for item in plugin._server_alias_lookup_dict.get(alias_mapping_key(alias, path), ()):
            item(value, own_caller(plugin))


def apply_availability(plugin, node_id: int, available: bool) -> None:
    for item in plugin.get_items_for_mapping(availability_mapping_key(node_id)):
        item(available, own_caller(plugin))
    for alias in plugin._server_node_to_alias.get(node_id, ()):
        for item in plugin._server_alias_lookup_dict.get(alias_availability_mapping_key(alias), ()):
            item(available, own_caller(plugin))


def seed_initial_values(plugin, nodes: list) -> None:
    """
    Push each node's cached values/availability into items once per
    (re)connect. start_listening()'s return is the same snapshot as
    get_nodes() (matter-server's #handleStartListening calls
    #handleGetNodes internally) - without this, an item sits at its
    load-time value until a live event happens to arrive, which never
    happens for state that hasn't changed since shng started.
    """
    for node in nodes:
        node_id = node['node_id']
        for path, value in node['attributes'].items():
            apply_attribute(plugin, node_id, path, value)
        apply_availability(plugin, node_id, node.get('available'))


# -- alias base item / definitions --


def ensure_alias_base_item(plugin) -> None:
    """
    Give the base item a default remark if it has none. Never creates
    it - same as pause_item elsewhere in shng, the user is expected to
    have already created the item a plugin.yaml parameter names.
    """
    if not plugin.server_alias_base_item:
        plugin.logger.info('alias_base_item is empty - matter_alias support disabled')
        return
    base_item = plugin.items.return_item(plugin.server_alias_base_item)
    if base_item is None:
        example = '\n'.join(f'{"    " * i}{part}:' for i, part in enumerate(plugin.server_alias_base_item.split('.')))
        plugin.logger.info(
            f"alias base item '{plugin.server_alias_base_item}' not found - matter_alias support stays inactive "
            f'until it exists (the rest of the plugin is unaffected). Create it yourself, e.g.:\n{example}'
        )
        return
    if base_item.property.remark is None:
        config = preserve_core_config(base_item)
        config['remark'] = DEFAULT_ALIAS_BASE_REMARK
        # notify_plugins=False: only remark changes, a core attribute no
        # plugin registers - and the base item is matter's own alias
        # container, unused by anything else
        plugin.items.edit_item(base_item, config, notify_plugins=False)
        plugin.logger.info(f"set default remark on alias base item '{plugin.server_alias_base_item}'")


def preserve_core_config(item) -> dict:
    """
    Config dict for edit_item(). type/remark aren't in item.conf (core
    attributes, applied via setattr in Item._apply_config() rather than
    stored there) - rebuilding from .conf alone would silently drop them.
    """
    config = {key: value for key, value in item.conf.items() if not key.startswith('_')}
    config['type'] = item._type
    if item.property.remark is not None:
        config['remark'] = item.property.remark
    return config


def validate_alias_references(plugin) -> None:
    """Log genuinely unknown matter_alias names, once every item has parsed (see resolve_node_id)."""
    for path, alias in plugin._server_item_alias.items():
        if alias not in plugin._server_aliases:
            plugin.logger.error(
                f"{path}: matter_alias '{alias}' is not a known alias - check it exists "
                f'as an item under {plugin.server_alias_base_item}'
            )


def is_alias_definition(plugin, item) -> bool:
    """True if item is a DIRECT child of the configured alias base item - the sole, structural definition."""
    if not plugin.server_alias_base_item:
        return False
    parent_path, sep, _name = item.property.path.rpartition('.')
    return sep != '' and parent_path == plugin.server_alias_base_item


def parse_alias_definition_item(plugin, item):
    """
    Gate a candidate alias definition and register it. Every gate is
    checked (not just the first failure) so one error message tells
    the user everything wrong at once.
    """
    path = item.property.path
    errors = []
    if item._type != 'num':
        errors.append(f"type is '{item._type}', must be 'num'")
    elif not isinstance(item(), int) or item() <= 0:
        errors.append('no explicit (positive integer) value: set')
    if item._cache:
        errors.append('cache is set - the node_id must live in the item definition (etc/), not var/ cache')
    if 'database' in item.conf:
        errors.append('database is set - not appropriate for an alias definition')
    if item.property.eval:
        errors.append('eval is set - an alias value must be a plain literal, not computed')
    if errors:
        plugin.logger.error(f'{path}: not a valid matter alias definition - {"; ".join(errors)}')
        return None

    _parent, _sep, name = path.rpartition('.')
    set_alias(plugin, name, item())
    plugin.add_item(item, config_data_dict={'matter_alias_name': name}, mapping=None, updating=True)
    return functools.partial(update_alias_item, plugin)


def update_alias_item(plugin, item, caller=None, source=None, dest=None):
    """Fires on any write to an alias definition item - keeps plugin._server_aliases in sync regardless of write source."""
    config = plugin.get_item_config(item)
    name = config.get('matter_alias_name')
    if name is None:
        return
    set_alias(plugin, name, item())


def set_alias(plugin, name: str, node_id: int) -> None:
    old_node_id = plugin._server_aliases.get(name)
    if old_node_id == node_id:
        return
    if old_node_id is not None:
        plugin._server_node_to_alias.get(old_node_id, set()).discard(name)
        if not plugin._server_node_to_alias.get(old_node_id):
            plugin._server_node_to_alias.pop(old_node_id, None)
    plugin._server_aliases[name] = node_id
    plugin._server_node_to_alias.setdefault(node_id, set()).add(name)
    plugin.logger.info(f"matter alias '{name}' -> node_id {node_id}")


# -- item handling --


def parse_item(plugin, item):
    """
    Checked in order: alias definition (item directly under
    alias_base_item) > matter_available > matter_switch > matter_attribute/
    matter_command. See plugin.yaml for what each attribute does.

    matter_node/matter_alias/matter_endpoint/matter_cluster are resolved via
    Item.find_attribute_with_instance() up the ancestor chain (instance-aware,
    unlike plain find_attribute() - see resolve_addressing()'s own docstring
    for why), so a child only overrides what differs from its "master" item.
    matter_alias wins if an ancestor chain sets both it and matter_node.
    """
    if is_alias_definition(plugin, item):
        return parse_alias_definition_item(plugin, item)

    if plugin.has_iattr(item.conf, 'matter_available'):
        return parse_availability_item(plugin, item)

    if plugin.has_iattr(item.conf, 'matter_switch'):
        return parse_switch_item(plugin, item)

    has_attribute = plugin.has_iattr(item.conf, 'matter_attribute')
    has_command = plugin.has_iattr(item.conf, 'matter_command')
    if not has_attribute and not has_command:
        return None

    addressing = resolve_addressing(plugin, item)
    if addressing is None:
        return None
    node_id, endpoint_id, cluster_id, alias = addressing

    config_data: dict = {}
    path_for_mapping = None

    if has_attribute:
        attribute_mapping = AttributeMapping(
            node_id=node_id,
            endpoint_id=endpoint_id,
            cluster_id=cluster_id,
            attribute_id=int(plugin.get_iattr_value(item.conf, 'matter_attribute')),
            alias=alias,
        )
        config_data['matter_attribute_mapping'] = attribute_mapping
        path_for_mapping = attribute_mapping.path

    if has_command:
        config_data['matter_command_mapping'] = CommandMapping(
            node_id=node_id,
            endpoint_id=endpoint_id,
            cluster_id=cluster_id,
            command_name=plugin.get_iattr_value(item.conf, 'matter_command'),
            params=plugin.get_iattr_value(item.conf, 'matter_command_params', {}) or {},
            command_name_false=plugin.get_iattr_value(item.conf, 'matter_command_false', None),
            alias=alias,
        )

    direct_key = report_mapping_key(node_id, path_for_mapping) if path_for_mapping is not None else None
    alias_key = alias_mapping_key(alias, path_for_mapping) if alias and path_for_mapping is not None else None
    register_item(plugin, item, config_data, alias, direct_key, alias_key)
    # Must be plugin.update_item specifically, not a fresh closure/partial each
    # call: SmartPlugin.remove_item() hardcodes item.remove_method_trigger(self.update_item)
    # for cleanup, matched by object identity - a different callable here would
    # silently fail to unregister (caught by remove_item()'s own bare except).
    return plugin.update_item


def parse_availability_item(plugin, item):
    resolved = resolve_node_id(plugin, item)
    if resolved is None:
        return None
    node_id, alias = resolved
    direct_key = availability_mapping_key(node_id)
    alias_key = alias_availability_mapping_key(alias) if alias else None
    register_item(plugin, item, {}, alias, direct_key, alias_key, updating=False)
    return None


def parse_switch_item(plugin, item):
    addressing = resolve_addressing(plugin, item)
    if addressing is None:
        return None
    node_id, endpoint_id, cluster_id, alias = addressing

    switch = switch_info(cluster_id)
    if switch is None:
        plugin.logger.error(
            f'{item.property.path}: matter_switch is set but no switch mapping is known for cluster '
            f'{cluster_id} - use matter_attribute/matter_command/matter_command_false directly for it '
            f"instead, or add it to clusters.py's SWITCH_CLUSTERS once validated against a real device"
        )
        return None

    attribute_id, command_true, command_false = switch
    attribute_mapping = AttributeMapping(node_id, endpoint_id, cluster_id, attribute_id, alias=alias)
    command_mapping = CommandMapping(
        node_id, endpoint_id, cluster_id, command_true, command_name_false=command_false, alias=alias
    )
    direct_key = attribute_mapping.report_key
    alias_key = alias_mapping_key(alias, attribute_mapping.path) if alias else None
    register_item(
        plugin,
        item,
        {'matter_attribute_mapping': attribute_mapping, 'matter_command_mapping': command_mapping},
        alias,
        direct_key,
        alias_key,
    )
    # Must be plugin.update_item specifically, not a fresh closure/partial each
    # call: SmartPlugin.remove_item() hardcodes item.remove_method_trigger(self.update_item)
    # for cleanup, matched by object identity - a different callable here would
    # silently fail to unregister (caught by remove_item()'s own bare except).
    return plugin.update_item


def register_item(
    plugin,
    item,
    config_data: dict,
    alias: str | None,
    direct_key: str | None,
    alias_key: str | None,
    updating: bool = True,
) -> None:
    """
    Direct matter_node items go through the base class's node_id-keyed
    mapping; alias-based items go through _server_alias_lookup_dict instead,
    so a repoint only ever touches plugin._server_aliases/_server_node_to_alias.
    *_key is None for a command-only item with no read-side dispatch.
    """
    if alias is None:
        plugin.add_item(item, config_data_dict=config_data, mapping=direct_key, updating=updating)
        return

    plugin.add_item(item, config_data_dict=config_data, mapping=None, updating=updating)
    plugin._server_item_alias[item.property.path] = alias
    if alias_key is not None:
        plugin._server_alias_lookup_dict.setdefault(alias_key, []).append(item)


def resolve_addressing(plugin, item) -> tuple[int, int, int, str | None] | None:
    """
    (node_id, endpoint_id, cluster_id, alias_name_or_None), each resolved via
    Item.find_attribute_with_instance() - the instance-aware sibling of plain
    find_attribute(), added to shng core specifically for this: neither plain
    find_attribute() (ancestor-aware, not instance-aware) nor
    has_iattr()/get_iattr_value() (instance-aware, not ancestor-aware) alone
    covers matter_node/matter_alias/matter_endpoint/matter_cluster's need for
    both - set once on a device's "master" item with every child inheriting
    it (user_doc.rst), and correctly scoped once more than one plugin
    instance is configured.
    """
    resolved = resolve_node_id(plugin, item)
    if resolved is None:
        return None
    node_id, alias = resolved
    values = {}
    for attr in ('matter_endpoint', 'matter_cluster'):
        raw = item.find_attribute_with_instance(attr, default=None, plugin=plugin)
        if raw is None or raw == '':
            plugin.logger.error(f'{item.property.path}: {attr} not set on this item or any ancestor')
            return None
        values[attr] = int(raw)
    return node_id, values['matter_endpoint'], values['matter_cluster'], alias


def resolve_node_id(plugin, item) -> tuple[int, str | None] | None:
    """(node_id, alias_name_or_None), resolved from this item or its nearest ancestor."""
    alias = item.find_attribute_with_instance('matter_alias', default=None, plugin=plugin)
    if alias:
        # 0 is a deliberate placeholder, not a bug: item tree load order doesn't
        # guarantee the alias definition parses first, and mapping.node_id is never
        # read for an alias mapping (dispatch always re-resolves via plugin._server_aliases -
        # see resolve_current_node_id/apply_attribute). A genuinely unknown alias is
        # caught tree-wide by validate_alias_references() once every item has parsed.
        return plugin._server_aliases.get(alias, 0), alias
    raw = item.find_attribute_with_instance('matter_node', default=None, plugin=plugin)
    if raw is None or raw == '':
        plugin.logger.error(f'{item.property.path}: matter_node or matter_alias not set on this item or any ancestor')
        return None
    return int(raw), None


def resolve_current_node_id(plugin, mapping) -> int:
    """mapping.node_id directly, or the current alias target read fresh from plugin._server_aliases."""
    if mapping.alias is None:
        return mapping.node_id
    node_id = plugin._server_aliases.get(mapping.alias)
    if node_id is None:
        plugin.logger.error(
            f"matter_alias '{mapping.alias}' is no longer known - was it deleted? Using last-known node_id."
        )
        return mapping.node_id
    return node_id


def unparse_item(plugin, item) -> bool:
    path = item.property.path
    alias = plugin._server_item_alias.pop(path, None)
    if alias is not None:
        # Scanning by prefix instead of storing this item's own resolved key.
        prefix = f'{alias}:'
        for key in list(plugin._server_alias_lookup_dict.keys()):
            if not key.startswith(prefix):
                continue
            items = plugin._server_alias_lookup_dict[key]
            if item in items:
                items.remove(item)
                if not items:
                    del plugin._server_alias_lookup_dict[key]
        return True

    parent_path, sep, name = path.rpartition('.')
    if sep and parent_path == plugin.server_alias_base_item:
        node_id = plugin._server_aliases.pop(name, None)
        if node_id is not None:
            plugin._server_node_to_alias.get(node_id, set()).discard(name)
            if not plugin._server_node_to_alias.get(node_id):
                plugin._server_node_to_alias.pop(node_id, None)
        dependents = [dep_path for dep_path, dep_alias in plugin._server_item_alias.items() if dep_alias == name]
        if dependents:
            plugin.logger.warning(
                f"matter alias '{name}' removed while still referenced by: {', '.join(dependents)} - "
                'those items keep their last-known node_id until repointed or removed themselves'
            )
        return True

    return False


def update_item(plugin, item, caller=None, source=None, dest=None):
    if not plugin.alive or caller == own_caller(plugin):
        return
    if plugin.server_client is None or not plugin.server_client.connected:
        plugin.logger.warning(f'cannot write {item.property.path}: not connected to matter server sidecar')
        return

    config = plugin.get_item_config(item)
    command_mapping = config.get('matter_command_mapping')
    attribute_mapping = config.get('matter_attribute_mapping')
    try:
        if command_mapping is not None:
            value = item()
            if not command_mapping.should_fire(value):
                # falsy write to a value-independent command (e.g.
                # toggle) - autotimer's own reset, not a real trigger;
                # see should_fire's docstring in mapping.py
                return
            node_id = resolve_current_node_id(plugin, command_mapping)
            plugin.run_asyncio_coro(
                plugin.server_client.device_command(
                    node_id,
                    command_mapping.endpoint_id,
                    command_mapping.cluster_id,
                    command_mapping.resolve_command_name(value),
                    command_mapping.resolve_params(value),
                )
            )
        elif attribute_mapping is not None:
            node_id = resolve_current_node_id(plugin, attribute_mapping)
            plugin.run_asyncio_coro(plugin.server_client.write_attribute(node_id, attribute_mapping.path, item()))
    except MatterCommandError as ex:
        plugin.logger.error(f'writing {item.property.path} to Matter failed: {ex}')
    except TimeoutError:
        # str(TimeoutError()) is empty - client.py's send_command() raises a bare
        # one from asyncio.wait_for() with no message, so this needs its own
        # branch to say anything useful at all. E.g. matter-server itself
        # was up and the WS connection looked fine, but the device didn't
        # respond within send_command()'s 30s window - a real device-side
        # stall, not a code bug, but letting the bare traceback surface
        # through Item.__update()'s generic handler was still bad UX.
        plugin.logger.error(
            f'writing {item.property.path} to Matter timed out - matter-server or the device did not respond in time'
        )
    except ConnectionError as ex:
        # The plugin.server_client.connected check above can race a connection
        # drop between that check and the actual send - same "tolerate a
        # hiccup, log clearly" approach as the other two branches.
        plugin.logger.error(f'writing {item.property.path} to Matter failed: {ex}')


# -- alias CRUD, called from the webif --


def get_aliases(plugin) -> dict:
    """Current alias name -> node_id table, for the webif."""
    return dict(plugin._server_aliases)


def create_alias(plugin, name: str, node_id: int, remark: str = '') -> None:
    if not plugin.server_alias_base_item:
        raise ValueError('alias_base_item is not configured')
    base_item = plugin.items.return_item(plugin.server_alias_base_item)
    if base_item is None:
        raise ValueError(f"alias base item '{plugin.server_alias_base_item}' does not exist - create it first")
    path = f'{plugin.server_alias_base_item}.{name}'
    if plugin.items.return_item(path) is not None:
        raise ValueError(f"'{name}' already exists")
    config = {'type': 'num', 'value': node_id}
    if remark:
        config['remark'] = remark
    plugin.items.create_item(path, config, parent=base_item, filename=base_item.property.defined_in)


def repoint_alias(plugin, name: str, node_id: int) -> None:
    path = f'{plugin.server_alias_base_item}.{name}'
    alias_item = plugin.items.return_item(path)
    if alias_item is None:
        raise ValueError(f"alias '{name}' does not exist")
    config = preserve_core_config(alias_item)
    config['value'] = node_id
    # notify_plugins=False: alias items are matter's own node_id lookup
    # table, unused by any other plugin
    plugin.items.edit_item(alias_item, config, notify_plugins=False)


def remove_alias(plugin, name: str) -> None:
    path = f'{plugin.server_alias_base_item}.{name}'
    alias_item = plugin.items.return_item(path)
    if alias_item is None:
        raise ValueError(f"alias '{name}' does not exist")
    plugin.items.remove_item(alias_item)


# -- called from the webif (its own cherrypy thread) --


def commission(plugin, code: str) -> dict:
    return plugin.run_asyncio_coro(
        plugin.server_client.commission_with_code(code, timeout=plugin.server_commission_timeout)
    )


def describe_mapping(plugin, item) -> str:
    """
    Reads the mapping objects parse_item stored, not item.conf directly -
    a child relying on ancestor inheritance wouldn't have those in its own conf.
    """
    if item.property.path not in plugin._plg_item_dict:
        return '(not mapped - see log for the parse_item error)'

    config = plugin.get_item_config(item)
    attribute_mapping = config.get('matter_attribute_mapping')
    command_mapping = config.get('matter_command_mapping')
    mapping = attribute_mapping or command_mapping
    if mapping is None:
        return ''

    def mark(attr_name: str, value) -> str:
        # '*' = resolved via ancestor walk, not declared on this item itself.
        suffix = '' if attr_name in item.conf else '*'
        return f'{value}{suffix}'

    if mapping.alias is not None:
        parts = [f'alias={mark("matter_alias", mapping.alias)}', f'node={resolve_current_node_id(plugin, mapping)}']
    else:
        parts = [f'node={mark("matter_node", mapping.node_id)}']
    parts += [
        f'endpoint={mark("matter_endpoint", mapping.endpoint_id)}',
        f'cluster={mark("matter_cluster", mapping.cluster_id)}',
    ]
    if attribute_mapping is not None:
        parts.append(f'attribute={attribute_mapping.attribute_id}')
    if command_mapping is not None:
        parts.append(f'command={command_mapping.command_name}')
        if command_mapping.command_name_false is not None:
            parts.append(f'command_false={command_mapping.command_name_false}')
    return ', '.join(parts)


def list_nodes(plugin) -> list:
    if plugin.server_client is None or not plugin.server_client.connected:
        return []
    return plugin.run_asyncio_coro(plugin.server_client.get_nodes())


def get_discovery_rows(plugin) -> list:
    """Flat discovery-table rows (Node/Endpoint/Cluster/Attribute/Value) across all known nodes."""
    rows = []
    for node in list_nodes(plugin):
        rows.extend(discovery_rows(node))
    return rows


def _device_label(summary: dict) -> str:
    """
    Human-readable device identity for the item generator's remark/tree label - vendor + product,
    with node_label appended in parens if the user has set one and it differs from product. A
    separate rule from node_summary()'s own 'label' field (node_label > product > "Node N", a
    single best-guess display name for the Devices table) - here vendor and product both matter,
    since disambiguating "which physical device" is the whole point.
    """
    base = f'{summary["vendor"]} {summary["product"]}'.strip() or f'Node {summary["node_id"]}'
    if summary['node_label'] and summary['node_label'] != summary['product']:
        return f'{base} ({summary["node_label"]})'
    return base


def get_suggested_item_yaml(plugin, node_id: int) -> str | None:
    """
    Suggested item config for one specific device, as copy-paste YAML (discovery.py's
    generate_suggested_item()) - the webif's per-row "Vorschlag" button on the Devices tab. None
    means no CLUSTER_STRUCTS-covered cluster was found for this node - the caller shows a clear
    "nothing to suggest" message for that case, see discovery.py's own docstring for why (not a
    bug, an intentional gap covered by the Discovery tab instead).
    """
    node = next((n for n in list_nodes(plugin) if n['node_id'] == node_id), None)
    if node is None:
        return None
    return generate_suggested_item(node, device_label=_device_label(node_summary(node)))


def get_node_summaries(plugin) -> list:
    """Devices-tab rows: name/vendor/product/device type per known node."""
    return [node_summary(node) for node in list_nodes(plugin)]


def get_matter_items(plugin) -> list:
    """Items tab rows: only items this plugin actually mapped (its own _plg_item_dict), not every shng item."""
    return sorted(
        (data['item'] for data in plugin._plg_item_dict.values()), key=lambda item: item.property.path.lower()
    )


def remove_node(plugin, node_id: int) -> None:
    """Decommission a node from the fabric - see client.py's remove_node for the destructive/unverified caveat."""
    plugin.run_asyncio_coro(plugin.server_client.remove_node(node_id))


def open_commissioning_window(plugin, node_id: int) -> dict:
    """Fresh pairing code for a second controller (Apple Home, ...) - see client.py for the mechanism."""
    return plugin.run_asyncio_coro(plugin.server_client.open_commissioning_window(node_id))


def get_matter_fabrics(plugin, node_id: int) -> list:
    """Every fabric currently on a node, for the webif's per-device fabric list."""
    return plugin.run_asyncio_coro(plugin.server_client.get_matter_fabrics(node_id))


def remove_matter_fabric(plugin, node_id: int, fabric_index: int) -> None:
    """Remove one fabric from a node, leaving others (incl. this plugin's own) untouched."""
    plugin.run_asyncio_coro(plugin.server_client.remove_matter_fabric(node_id, fabric_index))


def interview_node(plugin, node_id: int) -> None:
    """Force a fresh full attribute read for one node - see client.py for why this exists."""
    plugin.run_asyncio_coro(plugin.server_client.interview_node(node_id))


def get_node_ip_addresses(plugin, node_id: int) -> list[str]:
    """Currently-connected (or last-known) addresses for a node, each still
    carrying its network interface (e.g. "fe80::...%en0") - see client.py."""
    return plugin.run_asyncio_coro(plugin.server_client.get_node_ip_addresses(node_id))
