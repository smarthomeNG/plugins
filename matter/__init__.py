#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Matter plugin. Thin SmartPlugin frame dispatching to two internal
#  roles: server/ (commissions and controls real Matter devices, mirroring
#  cluster attributes/commands onto shng items - see server/__init__.py)
#  and bridge/ (exposes shng items to other Matter ecosystems as bridged
#  accessories - see bridge/__init__.py). Both share plugin.yaml,
#  mapping.py, and clusters.py; each owns its own sidecar/client pair -
#  server's talks to the vendored matter-server, bridge's talks to this
#  plugin's own @matter/node application (sidecar/bridge.js - lives next to
#  matter-server, not under bridge/, so both share one Node.js dependency
#  tree instead of installing separately).
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
import collections
import os

from lib.item import Items
from lib.model.smartplugin import SmartPlugin

from . import bridge, server
from .bridge.client import MatterBridgeClient
from .bridge.sidecar import MatterBridgeSidecar
from .mapping import BridgeMapping
from .server.client import MatterServerClient
from .server.sidecar import MatterServerSidecar
from .webif import WebInterface


class Matter(SmartPlugin):
    """
    Matter plugin. See module docstring above.
    """

    PLUGIN_VERSION = '0.2.0'  # must match the version in plugin.yaml
    # Each instance needs its own ports/storage paths (and, for the bridge role,
    # its own commissioning identity) - see plugin.yaml's per-parameter notes on
    # which ones. Item attributes are already instance-scoped for free via
    # shng's own attr@instance/attr@* convention (SmartPlugin.__get_iattr_conf) -
    # nothing extra needed in this plugin's own parse_item() for that part.
    ALLOW_MULTIINSTANCE = True
    STOP_ON_ITEM_CHANGE = False

    def __init__(self, sh=None, **kwargs):
        super().__init__()

        # -- global (shared by every role) --
        self.node_binary = self.get_parameter_value('node_binary')
        self.storage_path = os.path.abspath(self.get_parameter_value('storage_path'))
        self.primary_interface = self.get_parameter_value('primary_interface') or None

        # -- server role config --
        self.server_sidecar_entry = self.path_join(
            self.get_plugin_dir(), self.get_parameter_value('server_sidecar_entry')
        )
        self.server_sidecar_port = self.get_parameter_value('server_sidecar_port')
        self.server_enable_test_net_dcl = self.get_parameter_value('server_enable_test_net_dcl')
        self.server_alias_base_item = self.get_parameter_value('server_alias_base_item')
        self.server_fabric_vendor_id = self.get_parameter_value('server_fabric_vendor_id')
        self.server_fabric_label = self.get_parameter_value('server_fabric_label')
        self.server_commission_timeout = self.get_parameter_value('server_commission_timeout')

        self.items = Items.get_instance()

        # -- server role state --
        self.server_sidecar: MatterServerSidecar | None = None
        self.server_client: MatterServerClient | None = None
        # The sidecar's own crash-recovery loop, run as a free-standing task (not part of the
        # {stop_task, server_task, bridge_task} set _plugin_coro() awaits) - stored so cleanup()
        # can cancel it before calling sidecar.stop(). Without this, a sidecar dying at the wrong
        # moment during shutdown could get restarted by supervise() before cleanup() sets
        # sidecar._stopping.
        self.server_sidecar_supervisor_task: asyncio.Task | None = None
        # Alias bookkeeping, kept separate from SmartPlugin's own _plg_item_dict/_item_lookup_dict.
        self._server_aliases: dict[str, int] = {}  # alias name -> current node_id
        self._server_node_to_alias: dict[int, set[str]] = {}  # node_id -> alias names currently pointing at it
        self._server_alias_lookup_dict: dict[str, list] = {}  # alias_mapping_key()/..._availability_...() -> items
        self._server_item_alias: dict[str, str] = {}  # device item path -> alias name it depends on
        # commission_with_code results that arrived after MatterServerClient's own timeout
        # already gave up on them (see server/client.py's _timed_out) - drained once by the
        # webif's periodic poll (get_late_commission_results()), not persisted beyond that.
        # deque, not a list: bounded so a webif that's never polling can't grow this forever.
        self._late_commission_results: collections.deque = collections.deque(maxlen=10)

        # -- bridge role config --
        self.bridge_sidecar_entry = self.path_join(
            self.get_plugin_dir(), self.get_parameter_value('bridge_sidecar_entry')
        )
        self.bridge_matter_port = self.get_parameter_value('bridge_matter_port')
        self.bridge_control_port = self.get_parameter_value('bridge_control_port')
        self.bridge_storage_path = os.path.abspath(self.get_parameter_value('bridge_storage_path'))
        self.bridge_passcode = self.get_parameter_value('bridge_passcode')
        self.bridge_discriminator = self.get_parameter_value('bridge_discriminator')
        self.bridge_vendor_id = self.get_parameter_value('bridge_vendor_id')

        # -- bridge role state --
        self.bridge_sidecar: MatterBridgeSidecar | None = None
        self.bridge_client: MatterBridgeClient | None = None
        # Same reasoning as server_sidecar_supervisor_task above - same race, same fix,
        # mirrored for the bridge role's own sidecar.
        self.bridge_sidecar_supervisor_task: asyncio.Task | None = None
        self._bridge_items: dict[str, BridgeMapping] = {}  # item path -> mapping (expose_type, name)
        self._bridge_item_by_path: dict[str, object] = {}  # item path -> item, for re-adds on reconnect
        self._bridge_endpoint_id: dict[str, int] = {}  # item path -> bridge-assigned endpoint_id
        self._bridge_item_by_endpoint: dict[int, object] = {}  # endpoint_id -> item, for command_received routing

        self.init_webinterface(WebInterface)

    # -- lifecycle --

    def run(self):
        self.alive = True
        server.ensure_alias_base_item(self)
        server.validate_alias_references(self)
        self.start_asyncio(self._plugin_coro())

    def stop(self):
        self.alive = False
        self.stop_asyncio()

    async def _plugin_coro(self):
        stop_task = asyncio.create_task(self.wait_for_asyncio_termination(), name='matter-stop-watcher')
        server_task = asyncio.create_task(server.run_forever(self), name='matter-server-role-work')
        bridge_task = asyncio.create_task(bridge.run_forever(self), name='matter-bridge-work')
        try:
            await asyncio.wait({stop_task, server_task, bridge_task}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            for task in (stop_task, server_task, bridge_task):
                if not task.done():
                    task.cancel()
            await server.cleanup(self)
            await bridge.cleanup(self)

    # -- item handling: dispatches to server/bridge based on which attributes an item carries --

    def parse_item(self, item):
        """
        Calls both roles unconditionally (not server.parse_item(item) or
        bridge.parse_item(item)) - an item may carry both a server and a
        bridge attribute at once (a passthrough item), and short-circuiting
        on the first truthy result would silently skip the other role's
        registration.
        """
        server_registered = server.parse_item(self, item)
        bridge_registered = bridge.parse_item(self, item)
        return self.update_item if (server_registered or bridge_registered) else None

    def update_item(self, item, caller=None, source=None, dest=None):
        """Dispatches to whichever role(s) actually registered this item, not just server."""
        config = self.get_item_config(item)
        if 'matter_attribute_mapping' in config or 'matter_command_mapping' in config:
            server.update_item(self, item, caller, source, dest)
        if 'matter_bridge_mapping' in config:
            bridge.update_item(self, item, caller, source, dest)

    def unparse_item(self, item) -> bool:
        """
        No super() call: SmartPlugin.unparse_item()'s default is a genuine
        no-op by design. Both roles are always tried (not server.unparse_item(item)
        or bridge.unparse_item(item)) for the same reason as parse_item().
        """
        server_handled = server.unparse_item(self, item)
        bridge_handled = bridge.unparse_item(self, item)
        return server_handled or bridge_handled

    # -- alias CRUD, called from the webif --

    def get_aliases(self) -> dict:
        return server.get_aliases(self)

    def create_alias(self, name: str, node_id: int, remark: str = '') -> None:
        server.create_alias(self, name, node_id, remark)

    def repoint_alias(self, name: str, node_id: int) -> None:
        server.repoint_alias(self, name, node_id)

    def remove_alias(self, name: str) -> None:
        server.remove_alias(self, name)

    # -- called from the webif (its own cherrypy thread) --

    def commission(self, code: str) -> dict:
        return server.commission(self, code)

    def describe_mapping(self, item) -> str:
        return server.describe_mapping(self, item)

    def list_nodes(self) -> list:
        return server.list_nodes(self)

    def get_discovery_rows(self) -> list:
        return server.get_discovery_rows(self)

    def get_suggested_item_yaml(self, node_id: int) -> str | None:
        return server.get_suggested_item_yaml(self, node_id)

    def get_node_summaries(self) -> list:
        return server.get_node_summaries(self)

    def get_matter_items(self) -> list:
        return server.get_matter_items(self)

    def remove_node(self, node_id: int) -> None:
        server.remove_node(self, node_id)

    def open_commissioning_window(self, node_id: int) -> dict:
        return server.open_commissioning_window(self, node_id)

    def get_matter_fabrics(self, node_id: int) -> list:
        return server.get_matter_fabrics(self, node_id)

    def remove_matter_fabric(self, node_id: int, fabric_index: int) -> None:
        server.remove_matter_fabric(self, node_id, fabric_index)

    def interview_node(self, node_id: int) -> None:
        server.interview_node(self, node_id)

    def get_node_ip_addresses(self, node_id: int) -> list:
        return server.get_node_ip_addresses(self, node_id)

    def get_late_commission_results(self) -> list:
        return server.drain_late_commission_results(self)

    # -- bridge view, called from the webif --

    def get_bridge_status(self) -> dict:
        return bridge.get_bridge_status(self)

    def get_bridge_fabrics(self) -> list:
        return bridge.get_bridge_fabrics(self)

    def get_bridge_items(self) -> list:
        return bridge.get_bridge_items(self)

    def open_bridge_commissioning_window(self) -> None:
        bridge.open_bridge_commissioning_window(self)

    def remove_bridge_fabric(self, fabric_index: int) -> None:
        bridge.remove_bridge_fabric(self, fabric_index)
