#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Supervises the matter-server Node.js sidecar process: spawns it,
#  forwards its log output into the plugin's logger, and restarts it
#  with backoff if it dies unexpectedly while the plugin is alive.
#
#  matter-server has no CLI bin/entry point (see plugin.yaml's
#  sidecar_entry parameter doc and dev/matter/matter-integration-plan.md's
#  Phase 0 findings in the core repo) - it is invoked by running its main
#  JS file directly with node. CLI flags below were confirmed against the
#  actually-installed matter-server 1.3.3's dist/esm/cli.js.
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

# Backoff schedule for unexpected sidecar exits while the plugin is alive.
# Caps out rather than growing forever, so a persistently broken sidecar
# still gets retried occasionally instead of being abandoned.
RESTART_BACKOFF_SECONDS = (1, 2, 5, 10, 30, 60)

# Logged by matter-server itself (matter-server/src/server/WebServer.ts)
# once its WS/HTTP port is bound - confirmed against the installed
# package's source, not guessed. start() waits for this line before
# returning, so the first connection attempt doesn't race the sidecar's
# own multi-second Node.js startup and get an immediate ECONNREFUSED -
# not a timeout, the OS refuses outright when nothing's listening yet.
READY_LOG_MARKER = 'Webserver listening on'
READY_TIMEOUT_SECONDS = 30.0


class SidecarStartError(Exception):
    """Raised when the sidecar process/entry file cannot be found or fails to start."""


class MatterSidecar:
    """Owns the lifecycle of one matter-server child process."""

    def __init__(
        self,
        node_binary: str,
        entry_path: str,
        port: int,
        storage_path: str,
        enable_test_net_dcl: bool,
        logger: logging.Logger | None = None,
        primary_interface: str | None = None,
    ):
        self.node_binary = node_binary
        self.entry_path = entry_path
        self.port = port
        self.storage_path = storage_path
        self.enable_test_net_dcl = enable_test_net_dcl
        self.logger = logger or logging.getLogger(__name__)
        # On a multi-interface host, matter-server can pick an interface whose
        # link-local/IPv6 addresses aren't actually reachable for the target
        # device, causing PASE to time out against "unreachable" addresses
        # even though the device is on the same LAN - found via a real device,
        # not something the loopback-only software example ever exercised.
        self.primary_interface = primary_interface

        self._process: asyncio.subprocess.Process | None = None
        self._log_task: asyncio.Task | None = None
        self._stopping = False

    @property
    def running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    def _build_args(self) -> list[str]:
        args = [
            self.entry_path,
            '--port',
            str(self.port),
            '--storage-path',
            self.storage_path,
            '--log-level',
            'info',
            # matter-server is Home Assistant's own project - its unpinned default
            # fabric label is literally "HomeAssistant" (ConfigStorage.ts), which
            # every other controller/app sees when listing a device's fabrics
            # (e.g. this plugin's own Fabrics webif tab, or Apple Home). Pinning
            # this - confirmed via MatterServer.ts to apply before the controller
            # is even constructed, not just cosmetic - avoids shng's own fabric
            # being mislabeled as a different project entirely.
            '--default-fabric-label',
            'SmartHomeNG',
        ]
        if self.enable_test_net_dcl:
            args.append('--enable-test-net-dcl')
        if self.primary_interface:
            args += ['--primary-interface', self.primary_interface]
        return args

    async def start(self) -> None:
        if not os.path.isfile(self.entry_path):
            raise SidecarStartError(
                f'matter-server entry file not found at {self.entry_path!r}. '
                "Run 'npm install' in the plugin's sidecar/ directory first - see user_doc.rst."
            )
        os.makedirs(self.storage_path, exist_ok=True)

        self._stopping = False
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.node_binary, *self._build_args(), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
            )
        except FileNotFoundError as ex:
            raise SidecarStartError(
                f"Node binary {self.node_binary!r} not found. Check the plugin's node_binary parameter "
                'and that a supported Node.js version is installed - see user_doc.rst.'
            ) from ex

        self.logger.info(f'matter-server sidecar started (pid={self._process.pid}, port={self.port})')
        try:
            await asyncio.wait_for(self._wait_until_ready(), timeout=READY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            self.logger.warning(
                f'matter-server sidecar did not log readiness within {READY_TIMEOUT_SECONDS}s, '
                'proceeding anyway - the connect retry loop will catch up if it is just slow'
            )

        self._log_task = asyncio.create_task(self._pump_logs(), name='matter-sidecar-logs')

    async def _wait_until_ready(self) -> None:
        """Consume stdout until READY_LOG_MARKER appears, logging each line the same way _pump_logs does."""
        assert self._process is not None and self._process.stdout is not None
        async for raw in self._process.stdout:
            line = raw.decode(errors='replace').rstrip()
            if line:
                self.logger.debug(f'[matter-server] {line}')
            if READY_LOG_MARKER in line:
                return

    async def _pump_logs(self) -> None:
        assert self._process is not None and self._process.stdout is not None
        async for raw in self._process.stdout:
            line = raw.decode(errors='replace').rstrip()
            if line:
                self.logger.debug(f'[matter-server] {line}')

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
                self.logger.warning('matter-server sidecar did not exit in time, killing it')
                self._process.kill()
                await self._process.wait()
        self.logger.info('matter-server sidecar stopped')
        self._process = None

    async def supervise(self) -> None:
        """
        Run forever (until stop() is called): restart the sidecar with
        backoff whenever it exits unexpectedly. Call as a background task
        alongside the plugin's main connection loop, not awaited directly.
        """
        attempt = 0
        while not self._stopping:
            if self._process is None:
                await self.start()
                attempt = 0

            returncode = await self._process.wait()
            if self._stopping:
                return

            self.logger.warning(f'matter-server sidecar exited unexpectedly (code={returncode})')
            self._process = None
            delay = RESTART_BACKOFF_SECONDS[min(attempt, len(RESTART_BACKOFF_SECONDS) - 1)]
            attempt += 1
            self.logger.info(f'restarting matter-server sidecar in {delay}s (attempt {attempt})')
            await asyncio.sleep(delay)
