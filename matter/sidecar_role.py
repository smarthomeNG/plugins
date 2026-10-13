#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Common run loop of a role backed by a Node.js sidecar and a WebSocket
#  connection to it: start and supervise the sidecar, connect with
#  backoff, run the role's on-connect work, reconnect when the
#  connection drops, and clean everything up.
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
from abc import ABC, abstractmethod
from typing import Any, ClassVar, Coroutine, Generic, TypeVar

from .role import Backoff, RoleHost, RoleState, RoleStatus
from .rpc import DEFAULT_COMMAND_TIMEOUT, TRANSIENT_ERRORS, JsonWsRpcClient, describe_error
from .sidecar import NodeSidecar

ClientT = TypeVar('ClientT', bound=JsonWsRpcClient)

# A blocking webif call outlasts the command's own timeout, so the command's clearer timeout error wins.
CALL_TIMEOUT_MARGIN = 5.0


class SidecarRole(ABC, Generic[ClientT]):
    """
    Base for a role that talks to its own sidecar process. Subclasses
    provide the client and what to do once connected; everything about
    process and connection lifecycle lives here.
    """

    name: ClassVar[str]

    def __init__(self, host: RoleHost, sidecar: NodeSidecar):
        self.host = host
        self.sidecar = sidecar
        self.client: ClientT | None = None
        self.status = RoleStatus(RoleState.STARTING)
        self._supervisor_task: asyncio.Task | None = None

    @abstractmethod
    def _make_client(self) -> ClientT:
        """A fresh, unconnected client for this role's sidecar."""

    @abstractmethod
    async def _on_connected(self, client: ClientT) -> None:
        """Work after every (re)connect, e.g. pushing current state - may raise one of TRANSIENT_ERRORS."""

    @property
    def connected(self) -> bool:
        return self.client is not None and self.client.connected

    async def run(self) -> None:
        self.status = RoleStatus(RoleState.STARTING)
        await self.sidecar.start()
        self._supervisor_task = asyncio.create_task(self.sidecar.supervise(), name=f'matter-{self.name}-supervisor')
        self._supervisor_task.add_done_callback(self._log_supervisor_exit)

        backoff = Backoff()
        while True:
            client = await self._connect(backoff)
            try:
                await self._on_connected(client)
            except TRANSIENT_ERRORS as ex:
                delay = backoff.next_delay()
                self.host.logger.warning(
                    f'{self.name}: setup after connecting failed ({describe_error(ex)}), reconnecting in {delay}s'
                )
                await client.close()
                await asyncio.sleep(delay)
                continue
            self.status = RoleStatus(RoleState.CONNECTED)
            backoff.started()
            await client.closed.wait()
            self.status = RoleStatus(RoleState.RECONNECTING, 'connection lost')
            self.host.logger.warning(f'{self.name}: lost connection to {self.sidecar.LABEL}, reconnecting')

    async def _connect(self, backoff: Backoff) -> ClientT:
        while True:
            if self.client is not None:
                await self.client.close()
            client = self._make_client()
            self.client = client
            try:
                await client.connect()
            except Exception as ex:
                delay = backoff.next_delay()
                self.host.logger.warning(
                    f'{self.name}: could not connect to {self.sidecar.LABEL} ({describe_error(ex)}), retrying in {delay}s'
                )
                await asyncio.sleep(delay)
                continue
            self.host.logger.info(f'{self.name}: connected to {self.sidecar.LABEL}')
            return client

    async def cleanup(self) -> None:
        try:
            if self._supervisor_task is not None:
                self._supervisor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._supervisor_task
                self._supervisor_task = None
            if self.client is not None:
                await self.client.close()
        finally:
            await self.sidecar.stop()

    def _log_supervisor_exit(self, task: asyncio.Task) -> None:
        if not task.cancelled() and task.exception() is not None:
            self.host.logger.error(f'{self.name}: sidecar supervision ended: {task.exception()!r}')

    # -- helpers for subclasses --

    def _require_client(self) -> ClientT:
        client = self.client
        if client is None or not client.connected:
            raise ConnectionError(f'not connected to {self.sidecar.LABEL}')
        return client

    def _call(self, coro: Coroutine[Any, Any, Any], timeout: float = DEFAULT_COMMAND_TIMEOUT) -> Any:
        """Run a client coroutine from a non-asyncio thread (webif) and wait for its result."""
        return self.host.run_asyncio_coro(coro, timeout=timeout + CALL_TIMEOUT_MARGIN)
