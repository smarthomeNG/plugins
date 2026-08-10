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

from lib.model.smartplugin import SmartPlugin

from .client import MatterCommandError, MatterServerClient
from .clusters import switch_info
from .discovery import discovery_rows, generate_item_yaml, node_summary
from .mapping import AttributeMapping, CommandMapping, availability_mapping_key, report_mapping_key
from .sidecar import RESTART_BACKOFF_SECONDS, MatterSidecar, SidecarStartError
from .webif import WebInterface


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

        self.sidecar: MatterSidecar | None = None
        self.client: MatterServerClient | None = None

        self.init_webinterface(WebInterface)

    # -- lifecycle --

    def run(self):
        self.alive = True
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

    def _apply_availability(self, node_id: int, available: bool) -> None:
        for item in self.get_items_for_mapping(availability_mapping_key(node_id)):
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

    # -- item handling --

    def parse_item(self, item):
        """
        Three ways an item can be configured, cheapest/most convenient first:

        - `matter_available` (bool, read-only): mirrors matter-server's
          node-level reachability tracking (see `_apply_availability`) -
          needs only `matter_node` (via `_resolve_node_id()`), no
          endpoint/cluster.
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

        `matter_node`/`matter_endpoint`/`matter_cluster` need not be set on
        every item - `_resolve_addressing()` uses `Item.find_attribute()`
        to walk up to the nearest ancestor that sets each one, so
        addressing only needs stating once on a device's "master" item; a
        child only overrides what differs (e.g. matter_cluster, for
        power-measurement children on another cluster).
        """
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
        node_id, endpoint_id, cluster_id = addressing

        config_data: dict = {}
        report_key = None

        if has_attribute:
            attribute_mapping = AttributeMapping(
                node_id=node_id,
                endpoint_id=endpoint_id,
                cluster_id=cluster_id,
                attribute_id=int(self.get_iattr_value(item.conf, 'matter_attribute')),
            )
            config_data['matter_attribute_mapping'] = attribute_mapping
            report_key = attribute_mapping.report_key

        if has_command:
            config_data['matter_command_mapping'] = CommandMapping(
                node_id=node_id,
                endpoint_id=endpoint_id,
                cluster_id=cluster_id,
                command_name=self.get_iattr_value(item.conf, 'matter_command'),
                params=self.get_iattr_value(item.conf, 'matter_command_params', {}) or {},
                command_name_false=self.get_iattr_value(item.conf, 'matter_command_false', None),
            )

        self.add_item(item, config_data_dict=config_data, mapping=report_key, updating=True)
        return self.update_item

    def _parse_availability_item(self, item):
        node_id = self._resolve_node_id(item)
        if node_id is None:
            return None
        self.add_item(item, config_data_dict={}, mapping=availability_mapping_key(node_id), updating=False)
        return None

    def _parse_switch_item(self, item):
        addressing = self._resolve_addressing(item)
        if addressing is None:
            return None
        node_id, endpoint_id, cluster_id = addressing

        switch = switch_info(cluster_id)
        if switch is None:
            self.logger.error(
                f'{item.property.path}: matter_switch is set but no switch mapping is known for cluster '
                f'{cluster_id} - use matter_attribute/matter_command/matter_command_false directly for it '
                f"instead, or add it to clusters.py's SWITCH_CLUSTERS once validated against a real device"
            )
            return None

        attribute_id, command_true, command_false = switch
        attribute_mapping = AttributeMapping(node_id, endpoint_id, cluster_id, attribute_id)
        command_mapping = CommandMapping(
            node_id, endpoint_id, cluster_id, command_true, command_name_false=command_false
        )
        self.add_item(
            item,
            config_data_dict={'matter_attribute_mapping': attribute_mapping, 'matter_command_mapping': command_mapping},
            mapping=attribute_mapping.report_key,
            updating=True,
        )
        return self.update_item

    def _resolve_addressing(self, item) -> tuple[int, int, int] | None:
        """
        (node_id, endpoint_id, cluster_id), each resolved from this item or
        its nearest ancestor (Item.find_attribute() checks the item first,
        so a child can override just one, e.g. a different matter_cluster).
        Only addressing inherits this way - matter_switch/matter_attribute/
        matter_command stay item-local, so an item always opts in
        explicitly.
        """
        node_id = self._resolve_node_id(item)
        if node_id is None:
            return None
        values = {}
        for attr in ('matter_endpoint', 'matter_cluster'):
            raw = item.find_attribute(attr, default=None)
            if raw is None or raw == '':
                self.logger.error(f'{item.property.path}: {attr} not set on this item or any ancestor')
                return None
            values[attr] = int(raw)
        return node_id, values['matter_endpoint'], values['matter_cluster']

    def _resolve_node_id(self, item) -> int | None:
        """matter_node alone, resolved from this item or the nearest ancestor that sets it."""
        raw = item.find_attribute('matter_node', default=None)
        if raw is None or raw == '':
            self.logger.error(f'{item.property.path}: matter_node not set on this item or any ancestor')
            return None
        return int(raw)

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
                self.run_asyncio_coro(
                    self.client.device_command(
                        command_mapping.node_id,
                        command_mapping.endpoint_id,
                        command_mapping.cluster_id,
                        command_mapping.resolve_command_name(value),
                        command_mapping.resolve_params(value),
                    )
                )
            elif attribute_mapping is not None:
                self.run_asyncio_coro(
                    self.client.write_attribute(attribute_mapping.node_id, attribute_mapping.path, item())
                )
        except MatterCommandError as ex:
            self.logger.error(f'writing {item.property.path} to Matter failed: {ex}')

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

        parts = [
            f'node={mark("matter_node", mapping.node_id)}',
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
