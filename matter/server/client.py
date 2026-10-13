#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Client for the matter-server sidecar's WebSocket API: message_id-
#  correlated commands, an unframed ServerInfoMessage on connect, and
#  unsolicited {"event": ...} pushes.
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
import json
from typing import Any

from ..rpc import JsonWsRpcClient, RpcCommandError

# matter-server budgets up to 255s for one commissioning attempt (ControllerCommissioner.js).
DEFAULT_COMMISSION_TIMEOUT = 300.0


class MatterCommandError(RpcCommandError):
    """matter-server answered a command with an error_code."""

    def __init__(self, command: str, message: dict[str, Any]):
        self.error_code = message.get('error_code')
        self.details = message.get('details')
        super().__init__(command, f'error_code={self.error_code} details={self.details}')


class MatterServerClient(JsonWsRpcClient):
    """Connection to a matter-server sidecar."""

    ID_FIELD = 'message_id'
    LABEL = 'matter-server'

    server_info: dict[str, Any] | None = None

    async def _handshake(self, timeout: float) -> None:
        raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        self.server_info = json.loads(raw)
        self.logger.debug(f'matter-server connected, server_info={self.server_info}')

    def _error_from(self, command: str, message: dict[str, Any]) -> RpcCommandError | None:
        return MatterCommandError(command, message) if 'error_code' in message else None

    # -- matter-server commands --

    async def commission_with_code(
        self, code: str, network_only: bool = False, timeout: float = DEFAULT_COMMISSION_TIMEOUT
    ) -> dict:
        """
        Commission a device from its manual pairing code or QR content.

        network_only=False lets matter-server try BLE in parallel to on-network
        discovery (only if it was started with a Bluetooth adapter) - required
        for a not-yet-networked Thread device, harmless otherwise.
        """
        return await self.send_command(
            'commission_with_code', {'code': code, 'network_only': network_only}, timeout=timeout
        )

    async def set_thread_dataset(self, dataset: str, credential_id: str | None = None) -> dict:
        """
        Register a Thread operational dataset (hex TLV, e.g. `ot-ctl dataset
        active -x`) under credential_id (matter-server's default slot if
        omitted). Persisted by matter-server; commission_with_code() hands it
        to joining Thread devices.
        """
        args = {'dataset': dataset}
        if credential_id is not None:
            args['id'] = credential_id
        result = await self.send_command('set_thread_dataset', args)
        if self.server_info is not None:
            self.server_info['thread_credentials_set'] = True
        return result

    async def remove_thread_dataset(self, credential_id: str | None = None) -> dict:
        """Remove a registered Thread dataset (see set_thread_dataset())."""
        args = {}
        if credential_id is not None:
            args['id'] = credential_id
        result = await self.send_command('remove_thread_dataset', args)
        if self.server_info is not None:
            self.server_info['thread_credentials_set'] = False
        return result

    async def get_nodes(self, only_available: bool = False) -> list:
        """matter-server's cached node list - no live device query."""
        return await self.send_command('get_nodes', {'only_available': only_available})

    async def start_listening(self) -> list:
        """Subscribe to events; returns the same node snapshot as get_nodes()."""
        return await self.send_command('start_listening', {})

    async def read_attribute(self, node_id: int, path: str, fabric_filtered: bool = False) -> Any:
        return await self.send_command(
            'read_attribute', {'node_id': node_id, 'attribute_path': path, 'fabric_filtered': fabric_filtered}
        )

    async def device_command(
        self, node_id: int, endpoint_id: int, cluster_id: int, command_name: str, payload: dict[str, Any] | None = None
    ) -> Any:
        return await self.send_command(
            'device_command',
            {
                'node_id': node_id,
                'endpoint_id': endpoint_id,
                'cluster_id': cluster_id,
                'command_name': command_name,
                'payload': payload or {},
                'response_type': None,
            },
        )

    async def write_attribute(self, node_id: int, path: str, value: Any) -> Any:
        return await self.send_command('write_attribute', {'node_id': node_id, 'attribute_path': path, 'value': value})

    async def remove_node(self, node_id: int) -> Any:
        """
        Decommission a node. A reachable device removes its own fabric
        credentials; for an unreachable one matter-server only forgets it
        locally, leaving the device unaware it was dropped.
        """
        return await self.send_command('remove_node', {'node_id': node_id})

    async def open_commissioning_window(self, node_id: int, timeout: int = 900) -> dict:
        """
        Fresh pairing code for an already-commissioned node, so a second
        controller (Apple Home, ...) can add it to its own fabric. 900s is
        matter.js's own default window. Returns setup_pin_code,
        setup_manual_code and setup_qr_code.
        """
        return await self.send_command('open_commissioning_window', {'node_id': node_id, 'timeout': timeout})

    async def get_matter_fabrics(self, node_id: int) -> list:
        """Every fabric on a node, with vendor_name resolved by matter-server."""
        return await self.send_command('get_matter_fabrics', {'node_id': node_id})

    async def remove_matter_fabric(self, node_id: int, fabric_index: int) -> Any:
        """
        Remove one fabric from a node - a device-side RemoveFabric. Meant for
        other controllers' fabrics; this plugin's own fabric goes through
        remove_node(), which also cleans up matter-server's node record.
        """
        return await self.send_command('remove_matter_fabric', {'node_id': node_id, 'fabric_index': fabric_index})

    async def interview_node(self, node_id: int) -> None:
        """Re-read every attribute of a node, replacing matter-server's cached copy (awaited until done)."""
        await self.send_command('interview_node', {'node_id': node_id})

    async def get_node_ip_addresses(self, node_id: int, prefer_cache: bool = True) -> list[str]:
        """Addresses of the node's operational session, with interface zone suffix (e.g. 'fe80::1%en0')."""
        return await self.send_command(
            'get_node_ip_addresses', {'node_id': node_id, 'prefer_cache': prefer_cache, 'scoped': True}
        )
