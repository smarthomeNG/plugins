#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Asyncio WebSocket client for bridge.js's control protocol - this
#  plugin's own design (see dev/matter/matter-integration-plan.md's
#  "Bridge control protocol" section in the core repo), not an external
#  API to match like server/client.py's matter-server protocol. Mirrors
#  server/client.py's id-correlated command/response + unsolicited-event
#  shape for consistency within the same plugin, not because anything
#  requires it here.
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


class BridgeCommandError(Exception):
    """Raised when bridge.js answers a command with an "error" field."""

    def __init__(self, command: str, message: dict):
        self.command = command
        self.error = message.get('error')
        super().__init__(f'{command} failed: {self.error}')


class MatterBridgeClient:
    """
    Persistent WebSocket connection to this plugin's own bridge.js process.

    Same structure as server/client.py's MatterServerClient (one background
    receive loop, id-correlated command futures, on_event callback for
    unsolicited pushes) - see that class's own docstring for the
    threading/asyncio-loop caveat, which applies here identically.
    """

    def __init__(self, url: str, on_event: Callable[[dict], None], logger: logging.Logger | None = None):
        self.url = url
        self._on_event = on_event
        self.logger = logger or logging.getLogger(__name__)

        self._ws = None
        self._receive_task: asyncio.Task | None = None
        self._pending: dict[int, asyncio.Future] = {}
        self._id_counter = itertools.count(1)

    @property
    def connected(self) -> bool:
        return self._ws is not None and not self._ws.close_code

    async def connect(self, timeout: float = 10.0) -> None:
        self._ws = await asyncio.wait_for(websockets.connect(self.url), timeout=timeout)
        self._receive_task = asyncio.create_task(self._receive_loop(), name='matter-bridge-client-receive')

    async def close(self) -> None:
        if self._receive_task is not None:
            self._receive_task.cancel()
            self._receive_task = None
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()

    async def _receive_loop(self) -> None:
        try:
            async for raw in self._ws:
                try:
                    message = json.loads(raw)
                except json.JSONDecodeError:
                    self.logger.warning(f'bridge sent non-JSON message: {raw!r}')
                    continue

                message_id = message.get('id')
                future = self._pending.pop(message_id, None) if message_id is not None else None
                if future is not None:
                    if not future.done():
                        future.set_result(message)
                elif 'event' in message:
                    try:
                        self._on_event(message)
                    except Exception:
                        self.logger.exception('bridge event handler raised')
                else:
                    self.logger.debug(f'unsolicited/unmatched message from bridge: {message}')
        except asyncio.CancelledError:
            raise
        except ConnectionClosed as ex:
            # Routine, not exceptional: the bridge sidecar process died (killed
            # deliberately, crashed, or is being restarted by supervise() -
            # increasingly a normal occurrence now that both happen routinely)
            # and the WS connection drops right along with it. A full
            # traceback (logger.exception(), the generic branch below) reads
            # as an alarming crash on every single sidecar restart - a clean,
            # short warning is the honest severity for this one specific,
            # expected cause. Everything else stays a real exception() dump.
            self.logger.warning(f'bridge connection closed ({ex}) - reconnecting on the next retry cycle')
        except Exception:
            self.logger.exception('bridge receive loop terminated unexpectedly')

    async def send_command(self, command: str, args: dict[str, Any], timeout: float = 30.0) -> Any:
        if self._ws is None:
            raise ConnectionError('not connected to bridge')

        message_id = next(self._id_counter)
        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[message_id] = future

        await self._ws.send(json.dumps({'id': message_id, 'command': command, 'args': args}))
        try:
            message = await asyncio.wait_for(future, timeout=timeout)
        finally:
            self._pending.pop(message_id, None)

        if 'error' in message:
            raise BridgeCommandError(command, message)
        return message.get('result')

    # -- convenience wrappers matching bridge.js's three commands --

    async def add_endpoint(self, item_path: str, expose_type: str, name: str) -> int:
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
