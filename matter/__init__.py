#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Matter controller plugin. Spawns and supervises a matter-server
#  Node.js sidecar (see sidecar.py), talks to it over a WebSocket
#  (see client.py), and mirrors Matter cluster attributes/commands onto
#  shng items (see mapping.py). Design and Phase 0 spike findings this
#  plugin is built on: dev/matter/matter-integration-plan.md in the
#  core (shng) repo.
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
import os

from lib.item import Items
from lib.model.smartplugin import SmartPlugin

from .client import MatterCommandError, MatterServerClient
from .clusters import switch_info
from .discovery import discovery_rows, generate_item_yaml, node_summary
from .mapping import (
    AttributeMapping,
    CommandMapping,
    alias_availability_mapping_key,
    alias_mapping_key,
    availability_mapping_key,
    report_mapping_key,
)
from .sidecar import RESTART_BACKOFF_SECONDS, MatterSidecar, SidecarStartError
from .webif import WebInterface

# All alias item definitions persist to this one dedicated file
# (etc/items/matter_aliases.yaml), kept separate from the user's own item
# config so the alias table is easy to find/back up/inspect on its own.
ALIAS_ITEMS_FILENAME = 'matter_aliases'

DEFAULT_ALIAS_BASE_REMARK = 'matter alias base item, child items are alias definitions, do not change'


class Matter(SmartPlugin):
    """
    Matter controller plugin. See module docstring above.
    """

    PLUGIN_VERSION = '0.1.0'  # must match the version in plugin.yaml
    ALLOW_MULTIINSTANCE = False

    def __init__(self, sh=None, **kwargs):
        super().__init__()

        self.node_binary = self.get_parameter_value('node_binary')
        self.sidecar_entry = self.path_join(self.get_plugin_dir(), self.get_parameter_value('sidecar_entry'))
        self.sidecar_port = self.get_parameter_value('sidecar_port')
        self.storage_path = os.path.abspath(self.get_parameter_value('storage_path'))
        self.enable_test_net_dcl = self.get_parameter_value('enable_test_net_dcl')
        self.primary_interface = self.get_parameter_value('primary_interface') or None
        self.alias_base_item = self.get_parameter_value('alias_base_item')

        self.sidecar: MatterSidecar | None = None
        self.client: MatterServerClient | None = None
        self.items = Items.get_instance()

        # Alias bookkeeping - entirely plugin-internal, deliberately never
        # touching SmartPlugin's own _plg_item_dict/_item_lookup_dict for
        # alias-based items (see the plan doc's alias design notes for why:
        # a repoint only ever needs to update these dicts, never the item
        # objects themselves or their base-class registration).
        self._aliases: dict[str, int] = {}  # alias name -> current node_id
        self._node_to_alias: dict[int, set[str]] = {}  # node_id -> alias names currently pointing at it
        self._alias_lookup_dict: dict[str, list] = {}  # alias_mapping_key()/alias_availability_mapping_key() -> items
        self._item_alias: dict[str, str] = {}  # device item path -> alias name it depends on, for unparse_item cleanup

        self.init_webinterface(WebInterface)

    # -- lifecycle --

    def run(self):
        self.alive = True
        self._ensure_alias_base_item()
        self.start_asyncio(self._plugin_coro())

    def stop(self):
        self.alive = False
        self.stop_asyncio()

    async def _plugin_coro(self):
        stop_task = asyncio.create_task(self.wait_for_asyncio_termination(), name='matter-stop-watcher')
        work_task = asyncio.create_task(self._run_forever(), name='matter-work')
        try:
            await asyncio.wait({stop_task, work_task}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (stop_task, work_task):
                if not task.done():
                    task.cancel()
            await self._cleanup()

    async def _run_forever(self):
        self.sidecar = MatterSidecar(
            self.node_binary,
            self.sidecar_entry,
            self.sidecar_port,
            self.storage_path,
            self.enable_test_net_dcl,
            logger=self.logger,
            primary_interface=self.primary_interface,
        )
        try:
            await self.sidecar.start()
        except SidecarStartError as ex:
            self.logger.error(str(ex))
            return  # config problem, not something retrying fixes - stay idle rather than loop forever

        asyncio.create_task(self.sidecar.supervise(), name='matter-sidecar-supervisor')
        await self._connect_client_with_retry()
        self._seed_initial_values(await self.client.start_listening())

        while self.alive:
            await asyncio.sleep(5)
            if not self.client.connected:
                self.logger.warning('lost connection to matter-server sidecar, reconnecting...')
                await self._connect_client_with_retry()
                self._seed_initial_values(await self.client.start_listening())

    async def _connect_client_with_retry(self) -> None:
        attempt = 0
        while self.alive:
            self.client = MatterServerClient(
                f'ws://localhost:{self.sidecar_port}/ws', on_event=self._on_event, logger=self.logger
            )
            try:
                await self.client.connect()
                self.logger.info('connected to matter-server sidecar')
                return
            except Exception as ex:
                delay = RESTART_BACKOFF_SECONDS[min(attempt, len(RESTART_BACKOFF_SECONDS) - 1)]
                self.logger.warning(f'could not connect to matter-server sidecar ({ex}), retrying in {delay}s')
                attempt += 1
                await asyncio.sleep(delay)

    async def _cleanup(self):
        if self.client is not None:
            await self.client.close()
        if self.sidecar is not None:
            await self.sidecar.stop()

    def _on_event(self, message: dict) -> None:
        """Called on the plugin's asyncio thread whenever matter-server pushes an unsolicited event."""
        event = message.get('event')
        if event == 'attribute_updated':
            try:
                node_id, path, value = message['data']
            except (KeyError, ValueError):
                self.logger.warning(f'malformed attribute_updated event: {message}')
                return
            self._apply_attribute(node_id, path, value)
        elif event == 'node_updated':
            # Full node details (same shape as a get_nodes() entry), pushed
            # when matter-server's nodeAvailabilityChanged fires
            # (ControllerCommandHandler.ts/WebSocketControllerHandler.ts) -
            # only the availability flag is used here.
            data = message.get('data') or {}
            node_id = data.get('node_id')
            available = data.get('available')
            if node_id is None or available is None:
                self.logger.warning(f'malformed node_updated event: {message}')
                return
            self._apply_availability(node_id, available)

    def _apply_attribute(self, node_id: int, path: str, value) -> None:
        for item in self.get_items_for_mapping(report_mapping_key(node_id, path)):
            item(value, self.get_shortname())
        for alias in self._node_to_alias.get(node_id, ()):
            for item in self._alias_lookup_dict.get(alias_mapping_key(alias, path), ()):
                item(value, self.get_shortname())

    def _apply_availability(self, node_id: int, available: bool) -> None:
        for item in self.get_items_for_mapping(availability_mapping_key(node_id)):
            item(available, self.get_shortname())
        for alias in self._node_to_alias.get(node_id, ()):
            for item in self._alias_lookup_dict.get(alias_availability_mapping_key(alias), ()):
                item(available, self.get_shortname())

    def _seed_initial_values(self, nodes: list) -> None:
        """
        Push each node's cached attribute values and availability into
        matching items once, right after (re)connecting. start_listening()'s
        return value is the same snapshot as get_nodes() (#handleStartListening
        just calls #handleGetNodes internally, see WebSocketControllerHandler.ts)
        - without this, items sit at whatever shng gave them at load until a
        live event happens to arrive for that exact node/path: never, for
        unchanging state (a socket left on) or a node available all along
        (no fresh node_updated).
        """
        for node in nodes:
            node_id = node['node_id']
            for path, value in node['attributes'].items():
                self._apply_attribute(node_id, path, value)
            self._apply_availability(node_id, node.get('available'))

    # -- alias base item / definitions --

    def _ensure_alias_base_item(self) -> None:
        """
        Validate the configured alias base item once at startup and give it
        a default remark if it doesn't have one - but never create it: the
        base item is the user's own structure to own, matching how e.g.
        pause_item works elsewhere in shng (a plugin.yaml parameter naming
        an item the user is expected to have already created).
        """
        if not self.alias_base_item:
            self.logger.info('alias_base_item is empty - matter_alias support disabled')
            return
        base_item = self.items.return_item(self.alias_base_item)
        if base_item is None:
            example = '\n'.join(f'{"    " * i}{part}:' for i, part in enumerate(self.alias_base_item.split('.')))
            self.logger.info(
                f"alias base item '{self.alias_base_item}' not found - matter_alias support stays inactive "
                f'until it exists (the rest of the plugin is unaffected). Create it yourself, e.g.:\n{example}'
            )
            return
        if 'remark' not in base_item.conf:
            config = {key: value for key, value in base_item.conf.items() if not key.startswith('_')}
            config['remark'] = DEFAULT_ALIAS_BASE_REMARK
            self.items.edit_item(base_item, config)
            self.logger.info(f"set default remark on alias base item '{self.alias_base_item}'")

    def _is_alias_definition(self, item) -> bool:
        """True if item is a DIRECT child of the configured alias base item - the sole, structural definition."""
        if not self.alias_base_item:
            return False
        parent_path, sep, _name = item.property.path.rpartition('.')
        return sep != '' and parent_path == self.alias_base_item

    def _parse_alias_definition_item(self, item):
        """
        Gate a candidate alias definition and register it. Every gate is
        checked (not just the first failure) so one error message tells
        the user everything wrong at once.
        """
        path = item.property.path
        errors = []
        if item._type != 'num':
            errors.append(f"type is '{item._type}', must be 'num'")
        if 'value' not in item.conf:
            errors.append('no explicit value: set')
        if 'cache' in item.conf:
            errors.append('cache is set - the node_id must live in the item definition (etc/), not var/ cache')
        if 'database' in item.conf:
            errors.append('database is set - not appropriate for an alias definition')
        if 'eval' in item.conf:
            errors.append('eval is set - an alias value must be a plain literal, not computed')
        if errors:
            self.logger.error(f'{path}: not a valid matter alias definition - {"; ".join(errors)}')
            return None

        _parent, _sep, name = path.rpartition('.')
        self._set_alias(name, item())
        self.add_item(item, config_data_dict={'matter_alias_name': name}, mapping=None, updating=True)
        return self._update_alias_item

    def _update_alias_item(self, item, caller=None, source=None, dest=None):
        """Fires on any write to an alias definition item - keeps self._aliases in sync regardless of write source."""
        config = self.get_item_config(item)
        name = config.get('matter_alias_name')
        if name is None:
            return
        self._set_alias(name, item())

    def _set_alias(self, name: str, node_id: int) -> None:
        old_node_id = self._aliases.get(name)
        if old_node_id == node_id:
            return
        if old_node_id is not None:
            self._node_to_alias.get(old_node_id, set()).discard(name)
            if not self._node_to_alias.get(old_node_id):
                self._node_to_alias.pop(old_node_id, None)
        self._aliases[name] = node_id
        self._node_to_alias.setdefault(node_id, set()).add(name)
        self.logger.info(f"matter alias '{name}' -> node_id {node_id}")

    # -- item handling --

    def parse_item(self, item):
        """
        Item config, cheapest/most convenient first:

        - An item directly under `alias_base_item` is an alias definition
          (see `_parse_alias_definition_item`) - structural location is the
          declaration, no marker attribute needed.
        - `matter_available` (bool, read-only): mirrors matter-server's
          node-level reachability tracking (see `_apply_availability`) -
          needs only `matter_node`/`matter_alias` (via `_resolve_node_id()`),
          no endpoint/cluster.
        - `matter_switch` (bool): shorthand for a bool on/off switch -
          attribute and both commands are derived from clusters.py's
          SWITCH_CLUSTERS table, keyed by matter_cluster. Logs a clear
          error, not a silent no-op, if the cluster isn't registered - use
          the low-level attributes directly until it is.
        - `matter_attribute` + `matter_command`(_false): the general
          mechanism underneath matter_switch, for anything not
          boolean-on/off-shaped (LevelControl, WindowCovering percentages,
          ...) or not yet in SWITCH_CLUSTERS. Both may be set on the same
          item - mirrors state via subscription, drives it via command on
          write; writes always go through the command mapping when both
          are set (OnOff's state attribute is spec-read-only on real
          devices, actuation needs a command anyway).

        `matter_node`/`matter_alias`/`matter_endpoint`/`matter_cluster` need
        not be set on every item - `_resolve_addressing()` uses
        `Item.find_attribute()` to walk up to the nearest ancestor that sets
        each one, so addressing only needs stating once on a device's
        "master" item; a child only overrides what differs (e.g.
        matter_cluster, for power-measurement children on another cluster).
        `matter_alias` takes priority over `matter_node` if an item's
        ancestor chain somehow sets both.
        """
        if self._is_alias_definition(item):
            return self._parse_alias_definition_item(item)

        if self.has_iattr(item.conf, 'matter_available'):
            return self._parse_availability_item(item)

        if self.has_iattr(item.conf, 'matter_switch'):
            return self._parse_switch_item(item)

        has_attribute = self.has_iattr(item.conf, 'matter_attribute')
        has_command = self.has_iattr(item.conf, 'matter_command')
        if not has_attribute and not has_command:
            return None

        addressing = self._resolve_addressing(item)
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
                attribute_id=int(self.get_iattr_value(item.conf, 'matter_attribute')),
                alias=alias,
            )
            config_data['matter_attribute_mapping'] = attribute_mapping
            path_for_mapping = attribute_mapping.path

        if has_command:
            config_data['matter_command_mapping'] = CommandMapping(
                node_id=node_id,
                endpoint_id=endpoint_id,
                cluster_id=cluster_id,
                command_name=self.get_iattr_value(item.conf, 'matter_command'),
                params=self.get_iattr_value(item.conf, 'matter_command_params', {}) or {},
                command_name_false=self.get_iattr_value(item.conf, 'matter_command_false', None),
                alias=alias,
            )

        direct_key = report_mapping_key(node_id, path_for_mapping) if path_for_mapping is not None else None
        alias_key = alias_mapping_key(alias, path_for_mapping) if alias and path_for_mapping is not None else None
        self._register_item(item, config_data, alias, direct_key, alias_key)
        return self.update_item

    def _parse_availability_item(self, item):
        resolved = self._resolve_node_id(item)
        if resolved is None:
            return None
        node_id, alias = resolved
        direct_key = availability_mapping_key(node_id)
        alias_key = alias_availability_mapping_key(alias) if alias else None
        self._register_item(item, {}, alias, direct_key, alias_key, updating=False)
        return None

    def _parse_switch_item(self, item):
        addressing = self._resolve_addressing(item)
        if addressing is None:
            return None
        node_id, endpoint_id, cluster_id, alias = addressing

        switch = switch_info(cluster_id)
        if switch is None:
            self.logger.error(
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
        self._register_item(
            item,
            {'matter_attribute_mapping': attribute_mapping, 'matter_command_mapping': command_mapping},
            alias,
            direct_key,
            alias_key,
        )
        return self.update_item

    def _register_item(
        self,
        item,
        config_data: dict,
        alias: str | None,
        direct_key: str | None,
        alias_key: str | None,
        updating: bool = True,
    ) -> None:
        """
        Register a parsed item, either through the base class's own
        node_id-keyed mapping (direct matter_node items - _item_lookup_dict
        stays exactly what it always was, untouched by any of this) or
        through this plugin's own alias-keyed lookup dict (alias-based
        items - _item_lookup_dict is deliberately never used for these, so
        a repoint never needs to reach into it, only self._aliases/
        self._node_to_alias change). *_key is None when this item has no
        read-side dispatch at all (a command-only item, e.g. toggle).
        """
        if alias is None:
            self.add_item(item, config_data_dict=config_data, mapping=direct_key, updating=updating)
            return

        self.add_item(item, config_data_dict=config_data, mapping=None, updating=updating)
        self._item_alias[item.property.path] = alias
        if alias_key is not None:
            self._alias_lookup_dict.setdefault(alias_key, []).append(item)

    def _resolve_addressing(self, item) -> tuple[int, int, int, str | None] | None:
        """
        (node_id, endpoint_id, cluster_id, alias_name_or_None), each
        resolved from this item or its nearest ancestor (Item.find_attribute()
        checks the item first, so a child can override just one, e.g. a
        different matter_cluster). Only addressing inherits this way -
        matter_switch/matter_attribute/matter_command stay item-local, so
        an item always opts in explicitly.
        """
        resolved = self._resolve_node_id(item)
        if resolved is None:
            return None
        node_id, alias = resolved
        values = {}
        for attr in ('matter_endpoint', 'matter_cluster'):
            raw = item.find_attribute(attr, default=None)
            if raw is None or raw == '':
                self.logger.error(f'{item.property.path}: {attr} not set on this item or any ancestor')
                return None
            values[attr] = int(raw)
        return node_id, values['matter_endpoint'], values['matter_cluster'], alias

    def _resolve_node_id(self, item) -> tuple[int, str | None] | None:
        """
        (node_id, alias_name_or_None), resolved from this item or its
        nearest ancestor. matter_alias is checked first - if an ancestor
        chain somehow sets both, alias wins rather than being silently
        ignored. alias_name is carried through into the mapping objects so
        update_item/_apply_attribute can re-resolve the CURRENT node_id
        from self._aliases at call time instead of trusting a value baked
        in once here - the entire point of aliasing.
        """
        alias = item.find_attribute('matter_alias', default=None)
        if alias:
            node_id = self._aliases.get(alias)
            if node_id is None:
                self.logger.error(
                    f"{item.property.path}: matter_alias '{alias}' is not a known alias - check it exists "
                    f'as an item under {self.alias_base_item} and was recognized at startup (see the log)'
                )
                return None
            return node_id, alias
        raw = item.find_attribute('matter_node', default=None)
        if raw is None or raw == '':
            self.logger.error(f'{item.property.path}: matter_node or matter_alias not set on this item or any ancestor')
            return None
        return int(raw), None

    def _resolve_current_node_id(self, mapping) -> int:
        """
        mapping.node_id for a direct matter_node item; the CURRENT alias
        target for an aliased one, read fresh from self._aliases rather
        than the possibly-stale value baked into the mapping at parse time.
        Falls back to the parse-time value (with a warning) if the alias
        was since removed, rather than failing the write outright.
        """
        if mapping.alias is None:
            return mapping.node_id
        node_id = self._aliases.get(mapping.alias)
        if node_id is None:
            self.logger.error(
                f"matter_alias '{mapping.alias}' is no longer known - was it deleted? Using last-known node_id."
            )
            return mapping.node_id
        return node_id

    def unparse_item(self, item) -> bool:
        """
        Custom cleanup for this plugin's own alias bookkeeping - the base
        class's generic _plg_item_dict/_item_lookup_dict cleanup already
        happened in remove_item() before this is called, unconditionally.
        No super() call: SmartPlugin.unparse_item()'s own default is now a
        genuine no-op by design (the trigger-removal it used to do moved
        into remove_item() itself), so there's nothing to preserve.
        """
        path = item.property.path
        alias = self._item_alias.pop(path, None)
        if alias is not None:
            # A device item that depended on an alias - drop it from every
            # alias_lookup_dict entry under that alias (there's normally
            # just one, for its own path, but scanning by prefix is cheap
            # and doesn't need this item's own resolved path stored too).
            prefix = f'{alias}:'
            for key in list(self._alias_lookup_dict.keys()):
                if not key.startswith(prefix):
                    continue
                items = self._alias_lookup_dict[key]
                if item in items:
                    items.remove(item)
                    if not items:
                        del self._alias_lookup_dict[key]
            return True

        parent_path, sep, name = path.rpartition('.')
        if sep and parent_path == self.alias_base_item:
            # The alias definition item itself was removed.
            node_id = self._aliases.pop(name, None)
            if node_id is not None:
                self._node_to_alias.get(node_id, set()).discard(name)
                if not self._node_to_alias.get(node_id):
                    self._node_to_alias.pop(node_id, None)
            dependents = [dep_path for dep_path, dep_alias in self._item_alias.items() if dep_alias == name]
            if dependents:
                self.logger.warning(
                    f"matter alias '{name}' removed while still referenced by: {', '.join(dependents)} - "
                    'those items keep their last-known node_id until repointed or removed themselves'
                )
            return True

        return False

    def update_item(self, item, caller=None, source=None, dest=None):
        if not self.alive or caller == self.get_shortname():
            return
        if self.client is None or not self.client.connected:
            self.logger.warning(f'cannot write {item.property.path}: not connected to matter-server sidecar')
            return

        config = self.get_item_config(item)
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
                node_id = self._resolve_current_node_id(command_mapping)
                self.run_asyncio_coro(
                    self.client.device_command(
                        node_id,
                        command_mapping.endpoint_id,
                        command_mapping.cluster_id,
                        command_mapping.resolve_command_name(value),
                        command_mapping.resolve_params(value),
                    )
                )
            elif attribute_mapping is not None:
                node_id = self._resolve_current_node_id(attribute_mapping)
                self.run_asyncio_coro(self.client.write_attribute(node_id, attribute_mapping.path, item()))
        except MatterCommandError as ex:
            self.logger.error(f'writing {item.property.path} to Matter failed: {ex}')

    # -- alias CRUD, called from the webif --

    def get_aliases(self) -> dict:
        """Current alias name -> node_id table, for the webif."""
        return dict(self._aliases)

    def create_alias(self, name: str, node_id: int, remark: str = '') -> None:
        if not self.alias_base_item:
            raise ValueError('alias_base_item is not configured')
        base_item = self.items.return_item(self.alias_base_item)
        if base_item is None:
            raise ValueError(f"alias base item '{self.alias_base_item}' does not exist - create it first")
        path = f'{self.alias_base_item}.{name}'
        if self.items.return_item(path) is not None:
            raise ValueError(f"'{name}' already exists")
        config = {'type': 'num', 'value': node_id}
        if remark:
            config['remark'] = remark
        self.items.create_item(path, config, parent=base_item, filename=ALIAS_ITEMS_FILENAME)

    def repoint_alias(self, name: str, node_id: int) -> None:
        path = f'{self.alias_base_item}.{name}'
        alias_item = self.items.return_item(path)
        if alias_item is None:
            raise ValueError(f"alias '{name}' does not exist")
        config = {key: value for key, value in alias_item.conf.items() if not key.startswith('_')}
        config['value'] = node_id
        self.items.edit_item(alias_item, config)

    def remove_alias(self, name: str) -> None:
        path = f'{self.alias_base_item}.{name}'
        alias_item = self.items.return_item(path)
        if alias_item is None:
            raise ValueError(f"alias '{name}' does not exist")
        self.items.remove_item(alias_item)

    # -- called from the webif (its own cherrypy thread) --

    def commission(self, code: str) -> dict:
        return self.run_asyncio_coro(self.client.commission_with_code(code))

    def describe_mapping(self, item) -> str:
        """
        Human-readable summary of an item's resolved Matter mapping, for the
        webif's Items tab. Reads the mapping objects parse_item already
        stored (fully resolved through ancestor inheritance) rather than
        item.conf directly - a child relying on inheritance wouldn't have
        those three in its own conf, so re-deriving from conf would show
        blank.
        """
        if item.property.path not in self._plg_item_dict:
            return '(not mapped - see log for the parse_item error)'

        config = self.get_item_config(item)
        attribute_mapping = config.get('matter_attribute_mapping')
        command_mapping = config.get('matter_command_mapping')
        mapping = attribute_mapping or command_mapping
        if mapping is None:
            return ''

        def mark(attr_name: str, value) -> str:
            # not in this item's own conf -> resolved via ancestor walk, not
            # declared locally; '*' flags that so it isn't a guessing game.
            suffix = '' if attr_name in item.conf else '*'
            return f'{value}{suffix}'

        if mapping.alias is not None:
            parts = [f'alias={mark("matter_alias", mapping.alias)}', f'node={self._resolve_current_node_id(mapping)}']
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

    def list_nodes(self) -> list:
        if self.client is None or not self.client.connected:
            return []
        return self.run_asyncio_coro(self.client.get_nodes())

    def get_discovery_rows(self) -> list:
        """Flat discovery-table rows (Node/Endpoint/Cluster/Attribute/Value) across all known nodes."""
        rows = []
        for node in self.list_nodes():
            rows.extend(discovery_rows(node))
        return rows

    def get_item_generator_yaml(self) -> str:
        """Suggested item YAML (copy-paste, unifi's Item-Generator pattern) for every known node."""
        chunks = [generate_item_yaml(node) for node in self.list_nodes()]
        return '\n'.join(chunks) if chunks else '# no commissioned nodes yet\n'

    def get_node_summaries(self) -> list:
        """Devices-tab rows: name/vendor/product/device type per known node."""
        return [node_summary(node) for node in self.list_nodes()]

    def get_matter_items(self) -> list:
        """Items tab rows: only items this plugin actually mapped (its own _plg_item_dict), not every shng item."""
        return sorted(
            (data['item'] for data in self._plg_item_dict.values()), key=lambda item: item.property.path.lower()
        )

    def remove_node(self, node_id: int) -> None:
        """Decommission a node from the fabric - see client.py's remove_node for the destructive/unverified caveat."""
        self.run_asyncio_coro(self.client.remove_node(node_id))

    def open_commissioning_window(self, node_id: int) -> dict:
        """Fresh pairing code for a second controller (Apple Home, ...) - see client.py for the mechanism."""
        return self.run_asyncio_coro(self.client.open_commissioning_window(node_id))

    def get_matter_fabrics(self, node_id: int) -> list:
        """Every fabric currently on a node, for the webif's per-device fabric list."""
        return self.run_asyncio_coro(self.client.get_matter_fabrics(node_id))

    def remove_matter_fabric(self, node_id: int, fabric_index: int) -> None:
        """Remove one fabric from a node, leaving others (incl. this plugin's own) untouched."""
        self.run_asyncio_coro(self.client.remove_matter_fabric(node_id, fabric_index))

    def interview_node(self, node_id: int) -> None:
        """Force a fresh full attribute read for one node - see client.py for why this exists."""
        self.run_asyncio_coro(self.client.interview_node(node_id))
