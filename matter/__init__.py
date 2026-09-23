#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Matter plugin. A thin SmartPlugin frame around independent roles (see
#  role.py): server/ commissions and controls real Matter devices, bridge/
#  exposes shng items to other Matter ecosystems. Each enabled role gets
#  every item callback and runs under its own supervision on the plugin's
#  asyncio loop; one role failing leaves the other running.
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
from typing import TYPE_CHECKING

from lib.item import Items
from lib.model.smartplugin import SmartPlugin

from .bridge import BridgeRole, BridgeSidecarSettings, MatterBridgeSidecar, bridge_unique_id
from .role import Backoff, Role, RoleConfigError, RoleState, RoleStatus, merge_registrations
from .server import MatterServerSidecar, ServerRole, ServerSettings, ServerSidecarSettings
from .webif import WebInterface

if TYPE_CHECKING:
    from lib.item.item import Item

ROLE_TYPES: tuple[type[ServerRole] | type[BridgeRole], ...] = (ServerRole, BridgeRole)


class Matter(SmartPlugin):
    """Matter plugin frame - see the module header."""

    PLUGIN_VERSION = '0.3.0'
    ALLOW_MULTIINSTANCE = True
    STOP_ON_ITEM_CHANGE = False

    def __init__(self, sh=None, **kwargs):
        super().__init__()
        self.items = Items.get_instance()
        self.primary_interface: str | None = self.get_parameter_value('primary_interface') or None

        self.server: ServerRole | None = self._build_server() if self.get_parameter_value('server_enabled') else None
        self.bridge: BridgeRole | None = self._build_bridge() if self.get_parameter_value('bridge_enabled') else None
        self.roles: list[Role] = [role for role in (self.server, self.bridge) if role is not None]
        # role name -> paths of items configured for that role while it is disabled
        self._disabled_role_items: dict[str, list[str]] = {}

        self.init_webinterface(WebInterface)

    def _plugin_path(self, parameter: str) -> str:
        return self.path_join(self.get_plugin_dir(), self.get_parameter_value(parameter))

    def _build_server(self) -> ServerRole:
        port = self.get_parameter_value('server_sidecar_port')
        sidecar = MatterServerSidecar(
            self.get_parameter_value('node_binary'),
            self._plugin_path('server_sidecar_entry'),
            os.path.abspath(self.get_parameter_value('storage_path')),
            ServerSidecarSettings(
                port=port,
                enable_test_net_dcl=self.get_parameter_value('server_enable_test_net_dcl'),
                primary_interface=self.primary_interface,
                fabric_vendor_id=self.get_parameter_value('server_fabric_vendor_id'),
                fabric_label=self.get_parameter_value('server_fabric_label'),
                bluetooth_adapter=self.get_parameter_value('server_bluetooth_adapter') or None,
            ),
            logger=self.logger,
        )
        settings = ServerSettings(
            alias_base_item=self.get_parameter_value('server_alias_base_item'),
            generated_items_file=self.get_parameter_value('server_generated_items_file'),
            generated_items_base=self.get_parameter_value('server_generated_items_base'),
            commission_timeout=self.get_parameter_value('server_commission_timeout'),
            otbr_rest_url=self.get_parameter_value('server_otbr_rest_url') or '',
        )
        return ServerRole(self, sidecar, settings, url=f'ws://localhost:{port}/ws')

    def _build_bridge(self) -> BridgeRole:
        control_port = self.get_parameter_value('bridge_control_port')
        sidecar = MatterBridgeSidecar(
            self.get_parameter_value('node_binary'),
            self._plugin_path('bridge_sidecar_entry'),
            os.path.abspath(self.get_parameter_value('bridge_storage_path')),
            BridgeSidecarSettings(
                matter_port=self.get_parameter_value('bridge_matter_port'),
                control_port=control_port,
                passcode=self.get_parameter_value('bridge_passcode'),
                discriminator=self.get_parameter_value('bridge_discriminator'),
                vendor_id=self.get_parameter_value('bridge_vendor_id'),
                unique_id=bridge_unique_id(self.get_instance_name()),
                primary_interface=self.primary_interface,
            ),
            logger=self.logger,
        )
        return BridgeRole(self, sidecar, url=f'ws://127.0.0.1:{control_port}')

    # -- lifecycle --

    def run(self):
        self.alive = True
        for role in self.roles:
            role.prepare()
        self._warn_disabled_role_items()
        self.start_asyncio(self._plugin_coro())

    def stop(self):
        self.alive = False
        self.stop_asyncio()

    async def _plugin_coro(self):
        tasks = [asyncio.create_task(self._supervise_role(role), name=f'matter-{role.name}') for role in self.roles]
        try:
            await self.wait_for_asyncio_termination()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            for role in self.roles:
                await self._cleanup_role(role)

    async def _supervise_role(self, role: Role) -> None:
        """
        Run one role until the plugin stops. A RoleConfigError disables the
        role; any other exception restarts it (after cleanup) with backoff.
        The other role is unaffected either way.
        """
        backoff = Backoff()
        while True:
            backoff.started()
            try:
                await role.run()
            except asyncio.CancelledError:
                raise
            except RoleConfigError as ex:
                role.status = RoleStatus(RoleState.FAILED, str(ex))
                self.logger.error(f'matter {role.name} role disabled: {ex}')
                await self._cleanup_role(role)
                return
            except Exception as ex:
                self.logger.exception(f'matter {role.name} role crashed: {ex!r}')
            else:
                self.logger.error(f'matter {role.name} role stopped unexpectedly')
            await self._cleanup_role(role)
            delay = backoff.next_delay()
            role.status = RoleStatus(RoleState.RESTARTING, f'restarting in {delay}s')
            await asyncio.sleep(delay)

    async def _cleanup_role(self, role: Role) -> None:
        try:
            await role.cleanup()
        except Exception as ex:
            self.logger.exception(f'matter {role.name} role cleanup failed: {ex!r}')

    # -- item handling --

    def parse_item(self, item: Item):
        """
        Every enabled role sees every item - one item may carry both server
        and bridge attributes - and the item is registered once with all
        roles' config data.
        """
        self._note_disabled_role_item(item)
        registration = merge_registrations([role.parse_item(item) for role in self.roles])
        if registration is None:
            return None
        self.add_item(item, config_data_dict=dict(registration.config), updating=registration.updating)
        return self.update_item if registration.updating else None

    def update_item(self, item: Item, caller=None, source=None, dest=None):
        for role in self.roles:
            role.update_item(item, caller, source, dest)

    def unparse_item(self, item: Item) -> bool:
        return any([role.unparse_item(item) for role in self.roles])

    def _note_disabled_role_item(self, item: Item) -> None:
        enabled = {role.name for role in self.roles}
        for role_type in ROLE_TYPES:
            if role_type.name in enabled:
                continue
            if any(self.has_iattr(item.conf, attr) for attr in role_type.ITEM_ATTRIBUTES):
                self._disabled_role_items.setdefault(role_type.name, []).append(item.property.path)

    def _warn_disabled_role_items(self) -> None:
        for role_name, paths in self._disabled_role_items.items():
            self.logger.warning(
                f'{len(paths)} item(s) configured for the disabled {role_name} role are ignored '
                f'(enable {role_name}_enabled to use them): {", ".join(paths[:10])}{" ..." if len(paths) > 10 else ""}'
            )

    # -- webif helpers --

    def mapped_items(self) -> list[Item]:
        """Items this plugin registered, sorted by path."""
        return sorted(self.get_item_list(), key=lambda item: item.property.path.lower())

    def describe_item(self, item: Item) -> str:
        """Every role's mapping description for an item, joined."""
        descriptions = [role.describe_item(item) for role in self.roles]
        return '; '.join(description for description in descriptions if description)
