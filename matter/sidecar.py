#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Lifecycle of one Node.js child process (matter-server or bridge.js):
#  start and wait for readiness, forward its output to the plugin log,
#  restart it with backoff when it dies, stop it, and clean up a copy
#  left over by a previous shng process that could not stop it.
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
import logging
import os
from abc import ABC, abstractmethod
from typing import ClassVar

import psutil

from .role import Backoff, RoleConfigError

READY_TIMEOUT_SECONDS = 30.0
STOP_TIMEOUT_SECONDS = 10.0


class SidecarStartError(RoleConfigError):
    """The sidecar's entry file or the node binary cannot be found or executed."""


class NodeSidecar(ABC):
    """
    Owns one Node.js child process.

    The child runs in its own session (start_new_session), so a terminal
    Ctrl-C reaches only shng, which then stops the child in order. Its pid is
    recorded in a pidfile under storage_path; a still-running process from
    that pidfile whose command line contains this entry file is terminated
    before a new one starts (it would hold the sidecar's ports otherwise).
    """

    LABEL: ClassVar[str]
    LOG_PREFIX: ClassVar[str]
    # Line the process prints once it accepts connections - start() waits for it.
    READY_MARKER: ClassVar[str]
    PIDFILE_NAME: ClassVar[str]
    MISSING_ENTRY_HINT: ClassVar[str]

    def __init__(self, node_binary: str, entry_path: str, storage_path: str, logger: logging.Logger | None = None):
        self.node_binary = node_binary
        self.entry_path = entry_path
        self.storage_path = storage_path
        self.logger = logger or logging.getLogger(__name__)

        self._process: asyncio.subprocess.Process | None = None
        self._log_task: asyncio.Task | None = None
        self._stopping = False

    @abstractmethod
    def _build_args(self) -> list[str]:
        """Command line arguments after the node binary, starting with the entry file."""

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    @property
    def pidfile_path(self) -> str:
        return os.path.join(self.storage_path, self.PIDFILE_NAME)

    async def start(self) -> None:
        if not os.path.isfile(self.entry_path):
            raise SidecarStartError(
                f'{self.LABEL} entry file not found at {self.entry_path!r}. {self.MISSING_ENTRY_HINT}'
            )
        os.makedirs(self.storage_path, exist_ok=True)
        await self._terminate_stale_process()

        self._stopping = False
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.node_binary,
                *self._build_args(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
        except OSError as ex:
            raise SidecarStartError(
                f"cannot run node binary {self.node_binary!r} ({ex}). Check the plugin's node_binary parameter "
                'and that a supported Node.js version is installed - see user_doc.rst.'
            ) from ex
        self._write_pidfile(self._process.pid)

        self.logger.info(f'{self.LABEL} started (pid={self._process.pid})')
        try:
            await asyncio.wait_for(self._wait_until_ready(), timeout=READY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            self.logger.warning(
                f'{self.LABEL} did not log readiness within {READY_TIMEOUT_SECONDS}s, proceeding - '
                'the connect retry loop catches up if it is just slow'
            )
        self._log_task = asyncio.create_task(self._pump_logs(), name=f'matter-{self.PIDFILE_NAME}-logs')

    async def stop(self, timeout: float = STOP_TIMEOUT_SECONDS) -> None:
        self._stopping = True
        if self._log_task is not None:
            self._log_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._log_task
            self._log_task = None
        process, self._process = self._process, None
        if process is None:
            return
        if process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                self.logger.warning(f'{self.LABEL} did not exit in time, killing it')
                process.kill()
                await process.wait()
        self._remove_pidfile()
        self.logger.info(f'{self.LABEL} stopped')

    async def supervise(self, backoff: Backoff | None = None) -> None:
        """
        Restart the process with backoff whenever it exits, until stop() is
        called. Run as a background task next to the connection handling. A
        failing restart (node binary gone, ...) is logged and retried, it
        never ends supervision.
        """
        backoff = backoff or Backoff()
        while not self._stopping:
            if self._process is None:
                try:
                    await self.start()
                except SidecarStartError as ex:
                    delay = backoff.next_delay()
                    self.logger.error(f'restarting {self.LABEL} failed ({ex}), retrying in {delay}s')
                    await asyncio.sleep(delay)
                    continue

            backoff.started()
            returncode = await self._process.wait()
            if self._stopping:
                return
            self._process = None
            delay = backoff.next_delay()
            self.logger.warning(
                f'{self.LABEL} exited unexpectedly (code={returncode}), restarting in {delay}s (attempt {backoff.attempt})'
            )
            await asyncio.sleep(delay)

    async def _wait_until_ready(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        async for raw in self._process.stdout:
            line = self._log_line(raw)
            if self.READY_MARKER in line:
                return

    async def _pump_logs(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        async for raw in self._process.stdout:
            self._log_line(raw)

    def _log_line(self, raw: bytes) -> str:
        line = raw.decode(errors='replace').rstrip()
        if line:
            self.logger.debug(f'{self.LOG_PREFIX} {line}')
        return line

    async def _terminate_stale_process(self) -> None:
        pid = self._read_pidfile()
        if pid is None:
            return
        try:
            process = psutil.Process(pid)
            is_stale_sidecar = self.entry_path in process.cmdline()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            is_stale_sidecar = False
        if is_stale_sidecar:
            self.logger.warning(f'terminating leftover {self.LABEL} from a previous run (pid={pid})')
            await asyncio.to_thread(self._terminate_process, process)
        self._remove_pidfile()

    @staticmethod
    def _terminate_process(process: psutil.Process) -> None:
        with contextlib.suppress(psutil.NoSuchProcess):
            process.terminate()
            try:
                process.wait(timeout=STOP_TIMEOUT_SECONDS)
            except psutil.TimeoutExpired:
                process.kill()
                process.wait(timeout=STOP_TIMEOUT_SECONDS)

    def _read_pidfile(self) -> int | None:
        try:
            with open(self.pidfile_path) as f:
                return int(f.read().strip())
        except (OSError, ValueError):
            return None

    def _write_pidfile(self, pid: int) -> None:
        try:
            with open(self.pidfile_path, 'w') as f:
                f.write(str(pid))
        except OSError as ex:
            self.logger.warning(f'could not write {self.pidfile_path} ({ex}) - a leftover process cannot be detected')

    def _remove_pidfile(self) -> None:
        with contextlib.suppress(FileNotFoundError):
            os.remove(self.pidfile_path)
