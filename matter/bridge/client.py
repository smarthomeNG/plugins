#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Client for bridge.js's control WebSocket - this plugin's own protocol,
#  documented at the top of sidecar/bridge.js.
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

from typing import Any

from ..rpc import JsonWsRpcClient, RpcCommandError


class BridgeCommandError(RpcCommandError):
    """bridge.js answered a command with an "error" field."""

    def __init__(self, command: str, message: dict[str, Any]):
        super().__init__(command, str(message.get('error')))


class MatterBridgeClient(JsonWsRpcClient):
    """Connection to this plugin's bridge.js process."""

    ID_FIELD = 'id'
    LABEL = 'bridge'

    def _error_from(self, command: str, message: dict[str, Any]) -> RpcCommandError | None:
        return BridgeCommandError(command, message) if 'error' in message else None

    # -- bridge.js commands --

    async def add_endpoint(self, item_path: str, expose_type: str, name: str) -> int:
        """Add (or return the existing) bridged endpoint for an item; its number is stable per item_path."""
        result = await self.send_command(
            'add_endpoint', {'item_path': item_path, 'expose_type': expose_type, 'name': name}
        )
        return result['endpoint_id']

    async def remove_endpoint(self, endpoint_id: int) -> None:
        await self.send_command('remove_endpoint', {'endpoint_id': endpoint_id})

    async def set_attribute(self, endpoint_id: int, value: Any) -> None:
        await self.send_command('set_attribute', {'endpoint_id': endpoint_id, 'value': value})

    async def get_status(self) -> dict:
        return await self.send_command('get_status', {})

    async def open_commissioning_window(self) -> None:
        await self.send_command('open_commissioning_window', {})

    async def get_fabrics(self) -> list:
        result = await self.send_command('get_fabrics', {})
        return result['fabrics']

    async def remove_fabric(self, fabric_index: int) -> None:
        await self.send_command('remove_fabric', {'fabric_index': fabric_index})
