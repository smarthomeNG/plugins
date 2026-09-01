#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Supervises the bridge role's own Node.js process (bridge.js, this
#  plugin's own @matter/node application - not matter-server, which plays
#  no part in the bridge role). Mirrors server/sidecar.py's supervision
#  pattern (spawn, log forwarding, restart with backoff) against a
#  different process with a different, self-defined readiness marker.
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
import logging
import os
import time

# Same backoff schedule as server/sidecar.py, same reasoning: caps out
# rather than growing forever, so a persistently broken bridge sidecar
# still gets retried occasionally instead of being abandoned.
RESTART_BACKOFF_SECONDS = (1, 2, 5, 10, 30, 60)

# A process that stayed up at least this long gets treated as a fresh
# failure, not a continuation of a crash loop - see supervise()'s own
# comment on the bug this constant fixes. Reuses the top of the backoff
# schedule itself rather than introducing a second, unrelated magic number.
STABLE_RUN_SECONDS = RESTART_BACKOFF_SECONDS[-1]

# Logged by bridge.js itself right after `await server.start()` returns -
# confirmed against this plugin's own script, not a third-party dependency
# to trace through (unlike server/sidecar.py's READY_LOG_MARKER).
READY_LOG_MARKER = '[bridge] Matter node started'
READY_TIMEOUT_SECONDS = 30.0


class BridgeSidecarStartError(Exception):
    """Raised when the bridge.js entry file cannot be found or fails to start."""


class MatterBridgeSidecar:
    """Owns the lifecycle of one bridge.js child process."""

    def __init__(
        self,
        node_binary: str,
        entry_path: str,
        matter_port: int,
        control_port: int,
        storage_path: str,
        passcode: int,
        discriminator: int,
        vendor_id: int,
        logger: logging.Logger | None = None,
        primary_interface: str | None = None,
    ):
        self.node_binary = node_binary
        self.entry_path = entry_path
        self.matter_port = matter_port
        self.control_port = control_port
        self.storage_path = storage_path
        self.passcode = passcode
        self.discriminator = discriminator
        self.vendor_id = vendor_id
        self.logger = logger or logging.getLogger(__name__)
        # Same multi-interface gotcha server/sidecar.py's own primary_interface
        # exists for (a host with multiple interfaces on one subnet can end up
        # advertising/dialing addresses the peer isn't actually reachable
        # through) - observed: a commission against this exact bridge took
        # ~45s cycling through unreachable candidates before
        # reaching the one that worked, long enough to trip the webif's own
        # client-side command timeout and report a false failure even though
        # the commission itself succeeded moments later.
        self.primary_interface = primary_interface

        self._process: asyncio.subprocess.Process | None = None
        self._log_task: asyncio.Task | None = None
        self._stopping = False

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def _build_args(self) -> list[str]:
        return [
            self.entry_path,
            '--matter-port',
            str(self.matter_port),
            '--control-port',
            str(self.control_port),
            # Not read by bridge.js itself - matter.js's own Node environment
            # maps this to its storage.path config automatically, but only
            # in --key=value form (VariableService.ts's parseArgvStyle only
            # splits on "=", a bare "--storage-path" with the value as a
            # separate argv token is silently parsed as storage-path=true
            # and the actual path dropped).
            # matter-server's own --storage-path is unrelated - a
            # different program with its own CLI parser, not this mechanism.
            f'--storage-path={self.storage_path}',
            '--passcode',
            str(self.passcode),
            '--discriminator',
            str(self.discriminator),
            '--vendor-id',
            str(self.vendor_id),
        ] + (['--primary-interface', self.primary_interface] if self.primary_interface else [])

    async def start(self) -> None:
        if not os.path.isfile(self.entry_path):
            raise BridgeSidecarStartError(f'bridge.js not found at {self.entry_path!r}. Check the plugin installation.')
        os.makedirs(self.storage_path, exist_ok=True)

        self._stopping = False
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.node_binary,
                *self._build_args(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                # See server/sidecar.py's identical start_new_session - same requirement:
                # a terminal Ctrl-C's SIGINT must not reach this child directly via
                # inherited process group, racing shng's own graceful per-instance
                # shutdown.
                start_new_session=True,
            )
        except FileNotFoundError as ex:
            raise BridgeSidecarStartError(
                f"Node binary {self.node_binary!r} not found. Check the plugin's node_binary parameter "
                'and that a supported Node.js version is installed - see user_doc.rst.'
            ) from ex

        self.logger.info(f'matter bridge sidecar started (pid={self._process.pid}, control_port={self.control_port})')
        try:
            await asyncio.wait_for(self._wait_until_ready(), timeout=READY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            self.logger.warning(
                f'matter bridge sidecar did not log readiness within {READY_TIMEOUT_SECONDS}s, '
                'proceeding anyway - the connect retry loop will catch up if it is just slow'
            )

        self._log_task = asyncio.create_task(self._pump_logs(), name='matter-bridge-sidecar-logs')

    async def _wait_until_ready(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        async for raw in self._process.stdout:
            line = raw.decode(errors='replace').rstrip()
            if line:
                self.logger.debug(f'[bridge] {line}')
            if READY_LOG_MARKER in line:
                return

    async def _pump_logs(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        async for raw in self._process.stdout:
            line = raw.decode(errors='replace').rstrip()
            if line:
                self.logger.debug(f'[bridge] {line}')

    async def stop(self, timeout: float = 10.0) -> None:
        self._stopping = True
        if self._log_task is not None:
            self._log_task.cancel()
            self._log_task = None
        if self._process is None:
            return
        if self._process.returncode is None:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                self.logger.warning('matter bridge sidecar did not exit in time, killing it')
                self._process.kill()
                await self._process.wait()
        self.logger.info('matter bridge sidecar stopped')
        self._process = None

    async def supervise(self) -> None:
        """
        Run forever (until stop() is called): restart the bridge sidecar
        with backoff whenever it exits unexpectedly. Call as a background
        task alongside the plugin's main connection loop, not awaited
        directly - same pattern as server/sidecar.py's supervise().

        A restart loses every dynamically-added endpoint in memory, but not
        the bridge's own commissioned identity (persisted to storage_path) -
        bridge/__init__.py re-adds every currently-configured
        matter_expose_* item's endpoint once reconnected, the same "coarse
        recovery, not a silent gap" approach server/__init__.py already
        takes for its own reconnect path.

        Backoff only actually escalates for a genuine crash loop, not any
        restart - attempt is reset to 0 only once a process has stayed up at
        least STABLE_RUN_SECONDS, not unconditionally on every start(). A
        prior version reset it right after every start() regardless of how
        long that process then stayed up, which meant a sidecar dying
        immediately, repeatedly, always hit the shortest (1s) delay - never
        actually backing off despite RESTART_BACKOFF_SECONDS climbing to 60s
        (a killed sidecar produced no visible restart activity - the same
        bug also existed in server/sidecar.py's copy of this method).
        """
        attempt = 0
        while not self._stopping:
            if self._process is None:
                await self.start()

            started_at = time.monotonic()
            returncode = await self._process.wait()
            if self._stopping:
                return

            if time.monotonic() - started_at >= STABLE_RUN_SECONDS:
                attempt = 0

            self.logger.warning(f'matter bridge sidecar exited unexpectedly (code={returncode})')
            self._process = None
            delay = RESTART_BACKOFF_SECONDS[min(attempt, len(RESTART_BACKOFF_SECONDS) - 1)]
            attempt += 1
            self.logger.info(f'restarting matter bridge sidecar in {delay}s (attempt {attempt})')
            await asyncio.sleep(delay)
