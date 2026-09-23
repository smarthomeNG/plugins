#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  JSON-over-WebSocket request/response client, shared by the server
#  role's matter-server connection and the bridge role's bridge.js
#  connection: id-correlated command futures, one background receive
#  loop, unsolicited {"event": ...} messages handed to a callback.
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
import concurrent.futures
import contextlib
import itertools
import json
import logging
from abc import ABC, abstractmethod
from typing import Any, Callable, ClassVar

import websockets

# Explicit submodule import: the websockets package lazy-loads `.exceptions`, bare attribute access fails.
from websockets.exceptions import ConnectionClosed

EventHandler = Callable[[dict[str, Any]], None]

# How long a timed-out request's id is remembered, so a late answer is logged instead of dropped silently.
LATE_RESULT_RETENTION_SECONDS = 600.0

DEFAULT_COMMAND_TIMEOUT = 30.0


class RpcCommandError(Exception):
    """The peer answered a command with an error."""

    def __init__(self, command: str, detail: str):
        self.command = command
        self.detail = detail
        super().__init__(f'{command} failed: {detail}')


# Distinct classes on Python 3.10, aliases of the builtin TimeoutError from 3.11 on.
TIMEOUT_ERRORS: tuple[type[BaseException], ...] = (TimeoutError, asyncio.TimeoutError, concurrent.futures.TimeoutError)
TRANSIENT_ERRORS: tuple[type[BaseException], ...] = (RpcCommandError, ConnectionError, *TIMEOUT_ERRORS)


def describe_error(ex: BaseException) -> str:
    """Log/UI text for an exception - timeouts stringify to '' on their own."""
    if isinstance(ex, TIMEOUT_ERRORS):
        return 'timed out - the sidecar or the device did not respond in time'
    return str(ex) or type(ex).__name__


class JsonWsRpcClient(ABC):
    """
    Persistent WebSocket connection to one sidecar process.

    Runs entirely on the plugin's asyncio loop - code on other threads goes
    through SmartPlugin.run_asyncio_coro()/submit_asyncio_coro(). `closed`
    is set once the connection is gone for any reason; every request still
    waiting for an answer then fails with ConnectionError right away.
    """

    ID_FIELD: ClassVar[str]
    LABEL: ClassVar[str]

    def __init__(self, url: str, on_event: EventHandler, logger: logging.Logger | None = None):
        self.url = url
        self._on_event = on_event
        self.logger = logger or logging.getLogger(__name__)
        self.closed = asyncio.Event()

        self._ws: Any = None
        self._receive_task: asyncio.Task | None = None
        self._pending: dict[str, tuple[asyncio.Future, str]] = {}
        # message id -> (command, timed out at) for answers arriving after send_command() gave up
        self._timed_out: dict[str, tuple[str, float]] = {}
        self._ids = itertools.count(1)

    @property
    def connected(self) -> bool:
        return self._ws is not None and self._ws.close_code is None and not self.closed.is_set()

    @abstractmethod
    def _error_from(self, command: str, message: dict[str, Any]) -> RpcCommandError | None:
        """The error a response message carries, or None for a successful response."""

    async def _handshake(self, timeout: float) -> None:
        """Protocol-specific exchange right after the WebSocket connects, before the receive loop starts."""

    async def connect(self, timeout: float = 10.0) -> None:
        self._ws = await asyncio.wait_for(websockets.connect(self.url), timeout=timeout)
        try:
            await self._handshake(timeout)
        except BaseException:
            await self.close()
            raise
        self._receive_task = asyncio.create_task(self._receive_loop(), name=f'matter-{self.LABEL}-receive')

    async def close(self) -> None:
        if self._receive_task is not None:
            self._receive_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._receive_task
            self._receive_task = None
        if self._ws is not None:
            with contextlib.suppress(Exception):
                await self._ws.close()
            self._ws = None
        self._fail_pending(ConnectionError(f'{self.LABEL} connection closed'))
        self._timed_out.clear()
        self.closed.set()

    async def send_command(self, command: str, args: dict[str, Any], timeout: float = DEFAULT_COMMAND_TIMEOUT) -> Any:
        if not self.connected:
            raise ConnectionError(f'not connected to {self.LABEL}')

        message_id = str(next(self._ids))
        future: asyncio.Future = asyncio.get_running_loop().create_future()
        self._pending[message_id] = (future, command)
        try:
            try:
                await self._ws.send(json.dumps({self.ID_FIELD: message_id, 'command': command, 'args': args}))
            except ConnectionClosed as ex:
                raise ConnectionError(f'{self.LABEL} connection closed') from ex
            try:
                message = await asyncio.wait_for(future, timeout=timeout)
            except asyncio.TimeoutError:
                self._remember_timeout(message_id, command)
                raise
        finally:
            self._pending.pop(message_id, None)

        error = self._error_from(command, message)
        if error is not None:
            raise error
        return message.get('result')

    def _remember_timeout(self, message_id: str, command: str) -> None:
        now = asyncio.get_running_loop().time()
        self._timed_out = {
            mid: entry for mid, entry in self._timed_out.items() if now - entry[1] < LATE_RESULT_RETENTION_SECONDS
        }
        self._timed_out[message_id] = (command, now)

    def _fail_pending(self, ex: BaseException) -> None:
        pending = list(self._pending.values())
        self._pending.clear()
        for future, _command in pending:
            if not future.done():
                future.set_exception(ex)

    async def _receive_loop(self) -> None:
        try:
            async for raw in self._ws:
                self._dispatch(raw)
        except asyncio.CancelledError:
            raise
        except ConnectionClosed as ex:
            self.logger.warning(f'{self.LABEL} connection closed ({ex})')
        except Exception:
            self.logger.exception(f'{self.LABEL} receive loop terminated unexpectedly')
        finally:
            self._fail_pending(ConnectionError(f'{self.LABEL} connection closed'))
            self.closed.set()

    def _dispatch(self, raw: str | bytes) -> None:
        try:
            message = json.loads(raw)
        except json.JSONDecodeError:
            self.logger.warning(f'{self.LABEL} sent non-JSON message: {raw!r}')
            return

        message_id = message.get(self.ID_FIELD)
        if message_id is not None:
            message_id = str(message_id)
            pending = self._pending.pop(message_id, None)
            if pending is not None:
                future, _command = pending
                if not future.done():
                    future.set_result(message)
                return
            late = self._timed_out.pop(message_id, None)
            if late is not None:
                self.logger.warning(f"late answer for '{late[0]}' arrived after its timeout: {message}")
                return

        if 'event' in message:
            try:
                self._on_event(message)
            except Exception:
                self.logger.exception(f'{self.LABEL} event handler raised')
        else:
            self.logger.debug(f'unmatched message from {self.LABEL}: {message}')
