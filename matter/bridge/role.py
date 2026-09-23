#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Matter bridge role: exposes shng items to other Matter ecosystems
#  (Apple Home, Google Home, ...) as bridged accessories of this plugin's
#  own @matter/node application (sidecar/bridge.js) - a Matter identity of
#  its own, independent of the server role's fabric.
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

import functools
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, ClassVar

from ..mapping import BridgeMapping
from ..role import ItemRegistration, RoleHost
from ..rpc import TIMEOUT_ERRORS, TRANSIENT_ERRORS, RpcCommandError, describe_error
from ..sidecar_role import SidecarRole
from .client import MatterBridgeClient
from .expose import EXPOSE_TYPES, MAX_EXPOSE_NAME_LENGTH
from .sidecar import MatterBridgeSidecar

if TYPE_CHECKING:
    from lib.item.item import Item

BRIDGE_MAPPING_KEY = 'matter_bridge_mapping'


@dataclass
class BridgedItem:
    """An exposed item; endpoint_id is known once bridge.js added its endpoint."""

    item: Item
    mapping: BridgeMapping
    endpoint_id: int | None = None


class BridgeRole(SidecarRole[MatterBridgeClient]):
    """Exposes every item carrying matter_expose_type as one bridged endpoint."""

    name: ClassVar[str] = 'bridge'
    ITEM_ATTRIBUTES: ClassVar[tuple[str, ...]] = ('matter_expose_type',)

    def __init__(self, host: RoleHost, sidecar: MatterBridgeSidecar, url: str):
        super().__init__(host, sidecar)
        self.url = url
        self._lock = threading.Lock()
        self._bridged: dict[str, BridgedItem] = {}
        self._by_endpoint: dict[int, BridgedItem] = {}

    def own_caller(self) -> str:
        """Caller of this role's own item writes - see ServerRole.own_caller()."""
        return f'{self.host.get_fullname()}:bridge'

    # -- lifecycle --

    def prepare(self) -> None:
        pass

    def _make_client(self) -> MatterBridgeClient:
        return MatterBridgeClient(self.url, on_event=self._on_event, logger=self.host.logger)

    async def _on_connected(self, client: MatterBridgeClient) -> None:
        """(Re-)add every exposed item - a restarted bridge.js starts without endpoints."""
        with self._lock:
            entries = list(self._bridged.values())
        for entry in entries:
            await self._add_endpoint(client, entry)

    async def _add_endpoint(self, client: MatterBridgeClient, entry: BridgedItem) -> None:
        """Add one item's endpoint and push its current value; a lost connection propagates to the reconnect loop."""
        path = entry.mapping.item_path
        try:
            endpoint_id = await client.add_endpoint(path, entry.mapping.expose_type, entry.mapping.name)
        except (RpcCommandError, *TIMEOUT_ERRORS) as ex:
            self.host.logger.error(f'{path}: could not add bridge endpoint ({describe_error(ex)})')
            return
        with self._lock:
            if self._bridged.get(path) is not entry:
                return
            entry.endpoint_id = endpoint_id
            self._by_endpoint[endpoint_id] = entry
        try:
            await client.set_attribute(endpoint_id, entry.item())
        except (RpcCommandError, *TIMEOUT_ERRORS) as ex:
            self.host.logger.warning(
                f'{path}: added bridge endpoint but could not push its value ({describe_error(ex)})'
            )

    def _on_event(self, message: dict[str, Any]) -> None:
        if message.get('event') != 'command_received':
            return
        data = message.get('data') or {}
        endpoint_id = data.get('endpoint_id')
        with self._lock:
            entry = self._by_endpoint.get(endpoint_id)
        if entry is None:
            self.host.logger.warning(f'command_received for unknown bridge endpoint {endpoint_id}: {message}')
            return
        entry.item(data.get('value'), self.own_caller())

    # -- item handling --

    def parse_item(self, item: Item) -> ItemRegistration | None:
        if not self.host.has_iattr(item.conf, 'matter_expose_type'):
            return None
        path = item.property.path
        expose_type = self.host.get_iattr_value(item.conf, 'matter_expose_type')
        spec = EXPOSE_TYPES.get(expose_type)
        if spec is None:
            self.host.logger.error(f"{path}: matter_expose_type '{expose_type}' is not one of {sorted(EXPOSE_TYPES)}")
            return None
        if item._type != spec.item_type:
            self.host.logger.error(
                f"{path}: matter_expose_type '{expose_type}' needs an item of type '{spec.item_type}', not '{item._type}'"
            )
            return None
        # The item path is the only structurally unique default name without further configuration.
        name = self.host.get_iattr_value(item.conf, 'matter_expose_name', path) or path
        if len(name) > MAX_EXPOSE_NAME_LENGTH:
            self.host.logger.error(
                f'{path}: matter_expose_name (or the item path, if unset) is {len(name)} chars, over the '
                f"{MAX_EXPOSE_NAME_LENGTH}-char limit of a bridged accessory's name - set a shorter matter_expose_name"
            )
            return None

        mapping = BridgeMapping(item_path=path, expose_type=expose_type, name=name)
        entry = BridgedItem(item, mapping)
        with self._lock:
            self._bridged[path] = entry
        client = self.client
        if client is not None and client.connected:
            self.host.submit_asyncio_coro(self._add_endpoint(client, entry), on_error=self._log_error(path, 'add'))
        return ItemRegistration({BRIDGE_MAPPING_KEY: mapping})

    def unparse_item(self, item: Item) -> bool:
        path = item.property.path
        with self._lock:
            entry = self._bridged.pop(path, None)
            if entry is None:
                return False
            if entry.endpoint_id is not None:
                self._by_endpoint.pop(entry.endpoint_id, None)
        client = self.client
        if entry.endpoint_id is not None and client is not None and client.connected:
            self.host.submit_asyncio_coro(
                client.remove_endpoint(entry.endpoint_id), on_error=self._log_error(path, 'remove')
            )
        return True

    def update_item(self, item: Item, caller: str | None, source: str | None, dest: str | None) -> None:
        if not self.host.alive or caller == self.own_caller():
            return
        path = item.property.path
        with self._lock:
            entry = self._bridged.get(path)
        if entry is None or entry.endpoint_id is None:
            return
        client = self.client
        if client is None or not client.connected:
            self.host.logger.warning(f'cannot push {path} to bridge: not connected to matter bridge sidecar')
            return
        self.host.submit_asyncio_coro(
            client.set_attribute(entry.endpoint_id, item()), on_error=self._log_error(path, 'push value to')
        )

    def _log_error(self, path: str, action: str):
        return functools.partial(self._log_endpoint_error, path, action)

    def _log_endpoint_error(self, path: str, action: str, ex: BaseException) -> None:
        if isinstance(ex, TRANSIENT_ERRORS):
            self.host.logger.warning(f'{path}: could not {action} bridge endpoint ({describe_error(ex)})')
        else:
            self.host.logger.error(f'{path}: could not {action} bridge endpoint ({ex!r})', exc_info=ex)

    def describe_item(self, item: Item) -> str | None:
        with self._lock:
            entry = self._bridged.get(item.property.path)
        if entry is None:
            return None
        endpoint = entry.endpoint_id if entry.endpoint_id is not None else '-'
        return f'bridge: expose={entry.mapping.expose_type}, name={entry.mapping.name}, endpoint={endpoint}'

    # -- webif --

    def bridge_status(self) -> dict[str, Any]:
        """bridge.js status plus 'available'; {'available': False} instead of an error, so the page still renders."""
        client = self.client
        if client is None or not client.connected:
            return {'available': False}
        try:
            status = self._call(client.get_status())
        except TRANSIENT_ERRORS as ex:
            self.host.logger.warning(f'could not read bridge status ({describe_error(ex)})')
            return {'available': False}
        return {**status, 'available': True}

    def bridge_fabrics(self) -> list:
        """Controllers paired with the bridge; empty instead of an error."""
        client = self.client
        if client is None or not client.connected:
            return []
        try:
            return self._call(client.get_fabrics())
        except TRANSIENT_ERRORS as ex:
            self.host.logger.warning(f'could not read bridge fabrics ({describe_error(ex)})')
            return []

    def bridged_items(self) -> list[dict[str, Any]]:
        with self._lock:
            entries = list(self._bridged.values())
        return [
            {
                'item_path': entry.mapping.item_path,
                'expose_type': entry.mapping.expose_type,
                'name': entry.mapping.name,
                'endpoint_id': entry.endpoint_id,
            }
            for entry in entries
        ]

    def open_commissioning_window(self) -> None:
        client = self._require_client()
        self._call(client.open_commissioning_window())

    def remove_fabric(self, fabric_index: int) -> None:
        client = self._require_client()
        self._call(client.remove_fabric(fabric_index))
