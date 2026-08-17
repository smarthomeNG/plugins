#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Asyncio WebSocket client for the matter-server sidecar. The wire
#  protocol (message_id-correlated commands, unframed ServerInfoMessage on
#  connect, unsolicited {"event": ...} pushes) was validated end-to-end
#  against a real matter-server instance and a software Matter device in
#  the Phase 0 spike - see dev/matter/matter-integration-plan.md and
#  dev/matter/spike/spike_client.py in the core repo.
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
import itertools
import json
import logging
from typing import Any, Callable

import websockets

# Bare `import websockets` alone does NOT expose `.exceptions` (this version's
# top-level package lazy-loads submodules via its own __getattr__ -
# `websockets.exceptions.ConnectionClosed` raises AttributeError without this
# explicit import, despite `websockets.connect` below working fine either way).
from websockets.exceptions import ConnectionClosed


class MatterCommandError(Exception):
    """Raised when the sidecar answers a command with an error_code."""

    def __init__(self, command: str, message: dict):
        self.command = command
        self.error_code = message.get('error_code')
        self.details = message.get('details')
        super().__init__(f'{command} failed: error_code={self.error_code} details={self.details}')


class MatterServerClient:
    """
    Persistent WebSocket connection to a matter-server sidecar.

    One background task reads every incoming message and either resolves a
    pending command future (matched by message_id) or, for unsolicited
    {"event": ...} pushes (subscription reports), calls `on_event`.

    `on_event` runs on this client's own asyncio loop - callers on another
    thread (e.g. the plugin's update_item, on shng's item-update thread)
    must go through SmartPlugin.run_asyncio_coro, never touch this client
    directly.
    """

    def __init__(
        self,
        url: str,
        on_event: Callable[[dict], None],
        on_late_result: Callable[[str, dict], None] | None = None,
        logger: logging.Logger | None = None,
    ):
        self.url = url
        self._on_event = on_event
        self._on_late_result = on_late_result
        self.logger = logger or logging.getLogger(__name__)

        self._ws = None
        self._receive_task: asyncio.Task | None = None
        self._pending: dict[str, tuple[asyncio.Future, str]] = {}
        # message_id -> (command, timed_out_at) for a request send_command() gave up
        # waiting on - matter-server can still answer it later (a real commission_with_code
        # call was observed taking ~3 minutes end to end; see commission_with_code's own
        # docstring). Without this, that answer arrives with no pending future to resolve
        # and used to be silently dropped as "unsolicited". Pruned by age, not by count -
        # this is expected to stay near-empty in normal operation.
        self._timed_out: dict[str, tuple[str, float]] = {}
        self._msg_id_counter = itertools.count(1)
        self.server_info: dict | None = None

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.close_code

    async def connect(self, timeout: float = 10.0) -> None:
        self._ws = await asyncio.wait_for(websockets.connect(self.url), timeout=timeout)
        # matter-server pushes an unframed ServerInfoMessage right after connect,
        # before any command has been sent.
        raw = await asyncio.wait_for(self._ws.recv(), timeout=timeout)
        self.server_info = json.loads(raw)
        self.logger.debug(f'matter-server connected, server_info={self.server_info}')
        self._receive_task = asyncio.create_task(self._receive_loop(), name='matter-client-receive')

    async def close(self) -> None:
        if self._receive_task is not None:
            self._receive_task.cancel()
            self._receive_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        for future, _command in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
        self._timed_out.clear()

    def _remember_timeout(self, message_id: str, command: str) -> None:
        now = asyncio.get_event_loop().time()
        self._timed_out = {mid: v for mid, v in self._timed_out.items() if now - v[1] < 600}
        self._timed_out[message_id] = (command, now)

    async def _receive_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    self.logger.warning(f'matter-server sent non-JSON message: {raw!r}')
                    continue

                message_id = message.get('message_id')
                pending = self._pending.pop(message_id, None) if message_id is not None else None
                if pending is not None:
                    future, _command = pending
                    if not future.done():
                        future.set_result(message)
                    continue

                late = self._timed_out.pop(message_id, None) if message_id is not None else None
                if late is not None:
                    command, _timed_out_at = late
                    self.logger.warning(
                        f"late response for '{command}' arrived after this client's own timeout: {message}"
                    )
                    if self._on_late_result is not None:
                        try:
                            self._on_late_result(command, message)
                        except Exception:
                            self.logger.exception('matter-server late-result handler raised')
                elif 'event' in message:
                    try:
                        self._on_event(message)
                    except Exception:
                        self.logger.exception('matter-server event handler raised')
                else:
                    self.logger.debug(f'unsolicited/unmatched message from matter-server: {message}')
        except asyncio.CancelledError:
            raise
        except ConnectionClosed as ex:
            self.logger.warning(f'matter-server connection closed ({ex}) - reconnecting on the next retry cycle')
        except Exception:
            self.logger.exception('matter-server receive loop terminated unexpectedly')

    async def send_command(self, command: str, args: dict[str, Any], timeout: float = 30.0) -> Any:
        if self._ws is None:
            raise ConnectionError('not connected to matter-server')

        message_id = str(next(self._msg_id_counter))
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[message_id] = (future, command)

        await self._ws.send(json.dumps({'message_id': message_id, 'command': command, 'args': args}))
        try:
            message = await asyncio.wait_for(future, timeout=timeout)
        except asyncio.TimeoutError:
            self._remember_timeout(message_id, command)
            raise
        finally:
            self._pending.pop(message_id, None)

        if 'error_code' in message:
            raise MatterCommandError(command, message)
        return message.get('result')

    # -- convenience wrappers for the commands exercised in Phase 0 --

    async def commission_with_code(self, code: str, network_only: bool = True, timeout: float = 300.0) -> dict:
        """
        300s, not send_command()'s 30s default: matter-server's own commissioner
        tries every discovered candidate address with a 30s timeout each
        (ControllerCommissioner.js, Seconds(30)) and a later phase explicitly
        budgets up to 255s ("two ~2-minute server-side retry windows", same
        source) before giving up - a real commission attempt was observed
        taking ~3 minutes end to end before matter-server's own final answer
        arrived, well past the old 30s default. 300s is a safety margin above
        that documented ceiling, not a value derived from interface/candidate
        count - more candidates change how many attempts happen, not the
        per-attempt or overall ceiling, which matter-server controls either
        way. Even if this timeout is still hit, the answer isn't lost - see
        _remember_timeout()/on_late_result.
        """
        return await self.send_command(
            'commission_with_code', {'code': code, 'network_only': network_only}, timeout=timeout
        )

    async def get_nodes(self, only_available: bool = False) -> list:
        return await self.send_command('get_nodes', {'only_available': only_available})

    async def start_listening(self) -> list:
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
        """
        Verified against real hardware (Shelly Plug M Gen3,
        BasicInformation.NodeLabel - see the plan doc's "write_attribute
        verified on real hardware" section). Not yet verified against an
        attribute a device actively rejects (e.g. one expecting a command
        instead of a direct write).
        """
        return await self.send_command('write_attribute', {'node_id': node_id, 'attribute_path': path, 'value': value})

    async def remove_node(self, node_id: int) -> Any:
        """
        Decommissions a node from the fabric (node_id is the WS command's
        only argument). Traced through the real implementation
        (@project-chip/matter.js's CommissioningController.removeNode, via
        @matter-server/ws-controller's decommissionNode), not assumed from
        the WS command's existence alone:

        - Reachable device: real decommission - the device removes its own
          fabric credentials, clean mutual unpair, freshly re-commissionable.
        - Unreachable device: falls back to a local-only forget (with a
          warning) - the device is left not knowing it was dropped, same
          "orphaned" state as manually deleting local storage.

        NOT YET exercised against a live sidecar or real hardware -
        destructive, unlike this plugin's other client methods, so not
        casually tested. Verify carefully before relying on it.
        """
        return await self.send_command('remove_node', {'node_id': node_id})

    async def open_commissioning_window(self, node_id: int, timeout: int = 900) -> dict:
        """
        Generates a fresh pairing code for an already-commissioned node, so
        a second controller (Apple Home, Google Home, ...) can commission
        it onto its own separate fabric without disturbing this one - Matter
        is designed for multiple simultaneous admins per device. 900s (15
        min) default matches matter.js's own default
        (PairedNode.openEnhancedCommissioningWindow), not invented.

        Returns {'setup_pin_code': int, 'setup_manual_code': str,
        'setup_qr_code': str} (WebSocketControllerHandler.ts's
        #handleOpenCommissioningWindow). Only the manual code and QR content
        string are surfaced in the webif - no QR image rendering, since
        every major commissioning app (incl. Apple Home) accepts manual
        entry as a first-class alternative to scanning.
        """
        return await self.send_command('open_commissioning_window', {'node_id': node_id, 'timeout': timeout})

    async def get_matter_fabrics(self, node_id: int) -> list:
        """
        Every fabric currently on a node - node_id, vendor_id, fabric_index,
        fabric_label, and a resolved vendor_name (matter-server maps
        vendor_id through its own VendorIds table, so an Apple Home fabric
        shows up with vendor_name='Apple' directly, not just a numeric id).
        """
        return await self.send_command('get_matter_fabrics', {'node_id': node_id})

    async def remove_matter_fabric(self, node_id: int, fabric_index: int) -> Any:
        """
        Removes one specific fabric from a node (by fabric_index from
        get_matter_fabrics). A real, spec-compliant device-side command
        (ControllerCommandHandler.removeFabric ->
        OperationalCredentialsClient.removeFabric({fabricIndex})), not a
        local-only forget - the device itself is cleanly notified, same
        class of operation as remove_node's decommission path. Removing
        this plugin's own fabric this way still isn't recommended: it
        skips matter-server's own node-removal bookkeeping that
        remove_node performs, so its local record of the node goes stale
        instead of being cleaned up. Use remove_node for this plugin's own
        pairing; this method is for removing *other* controllers' fabrics.
        """
        return await self.send_command('remove_matter_fabric', {'node_id': node_id, 'fabric_index': fabric_index})

    async def interview_node(self, node_id: int) -> None:
        """
        Forces a fresh full read of every attribute on a node, replacing
        matter-server's cached copy (#handleInterviewNode, awaited - by the
        time this returns, the cache is already updated, no race with an
        immediately following get_nodes()). Requested after the Discovery
        tab's "cached, no live query" data went stale with no way to force
        a refresh short of restarting the sidecar.
        """
        await self.send_command('interview_node', {'node_id': node_id})

    async def get_node_ip_addresses(self, node_id: int, prefer_cache: bool = True) -> list[str]:
        """
        The address(es) currently in use (or last known, if prefer_cache) for
        this node's operational session, each still carrying its network
        interface as an IPv6 zone suffix (e.g. "fe80::...%en0") - always
        scoped=True on the WS call, since the interface name is the entire
        point of exposing this (diagnosing which of several host interfaces
        actually got used, not just the bare address WebSocketControllerHandler.ts's
        own scoped=False default would strip). #handleGetNodeIpAddresses.
        """
        return await self.send_command(
            'get_node_ip_addresses', {'node_id': node_id, 'prefer_cache': prefer_cache, 'scoped': True}
        )
