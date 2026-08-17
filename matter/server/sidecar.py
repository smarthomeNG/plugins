#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Supervises the matter-server Node.js sidecar process: spawns it,
#  forwards its log output into the plugin's logger, and restarts it
#  with backoff if it dies unexpectedly while the plugin is alive.
#
#  matter-server has no CLI bin/entry point (see plugin.yaml's sidecar_entry parameter doc) -
#  it is invoked by running its main JS file directly with node. CLI flags below were confirmed
#  against the actually-installed matter-server 1.3.3's dist/esm/cli.js.
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

# Backoff schedule for unexpected sidecar exits while the plugin is alive.
# Caps out rather than growing forever, so a persistently broken sidecar
# still gets retried occasionally instead of being abandoned.
RESTART_BACKOFF_SECONDS = (1, 2, 5, 10, 30, 60)

# A process that stayed up at least this long gets treated as a fresh
# failure, not a continuation of a crash loop - see supervise()'s own
# comment on the bug this constant fixes (same fix as bridge/sidecar.py's
# supervise()). Reuses the top of the backoff schedule itself rather than
# introducing a second, unrelated magic number.
STABLE_RUN_SECONDS = RESTART_BACKOFF_SECONDS[-1]

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


class MatterServerSidecar:
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
        fabric_vendor_id: int = 65521,
        fabric_label: str = 'SmartHomeNG',
    ):
        self.node_binary = node_binary
        self.entry_path = entry_path
        self.port = port
        self.storage_path = storage_path
        self.enable_test_net_dcl = enable_test_net_dcl
        self.logger = logger or logging.getLogger(__name__)
        self.fabric_vendor_id = fabric_vendor_id
        self.fabric_label = fabric_label
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
            # matter-server's own unpinned default is "HomeAssistant" (ConfigStorage.ts) - every
            # other controller listing this fabric would otherwise see it mislabeled.
            '--default-fabric-label',
            self.fabric_label,
            # Only takes effect the first time a fabric is created (matter.js persists vendorId into
            # the fabric's NOC at that point, read from storage on every later run regardless of this
            # flag) - changing it on an already-commissioned install needs a storage wipe + re-pairing
            # every device to have any effect. Default 65521 (0xFFF1) is the Matter spec's own
            # test-vendor range, matter-server's own default - real vendor IDs are CSA-assigned.
            '--vendorid',
            str(self.fabric_vendor_id),
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
                self.node_binary,
                *self._build_args(),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                # Without this, the child inherits the parent's (POSIX) process group - a terminal
                # Ctrl-C's SIGINT reaches it directly, racing shng's own graceful, sequential
                # per-plugin shutdown. Observed live with multiple plugin instances: shng shut
                # them down ~10s apart, and the still-running instance's sidecar died from the
                # direct SIGINT immediately, got auto-respawned by supervise() (its own _stopping
                # still False, cleanup() not yet run), only settling once shng's shutdown reached
                # it. start_new_session detaches the child into its own session/process group -
                # only our own terminate()/kill() below (pid-targeted, not group-targeted) can stop it.
                start_new_session=True,
            )
        except FileNotFoundError as ex:
            raise SidecarStartError(
                f"Node binary {self.node_binary!r} not found. Check the plugin's node_binary parameter "
                'and that a supported Node.js version is installed - see user_doc.rst.'
            ) from ex

        self.logger.info(f'matter server sidecar started (pid={self._process.pid}, port={self.port})')
        try:
            await asyncio.wait_for(self._wait_until_ready(), timeout=READY_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            self.logger.warning(
                f'matter server sidecar did not log readiness within {READY_TIMEOUT_SECONDS}s, '
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
                self.logger.warning('matter server sidecar did not exit in time, killing it')
                self._process.kill()
                await self._process.wait()
        self.logger.info('matter server sidecar stopped')
        self._process = None

    async def supervise(self) -> None:
        """
        Run forever (until stop() is called): restart the sidecar with
        backoff whenever it exits unexpectedly. Call as a background task
        alongside the plugin's main connection loop, not awaited directly.

        Backoff only actually escalates for a genuine crash loop, not any
        restart - attempt is reset to 0 only once a process has stayed up at
        least STABLE_RUN_SECONDS, not unconditionally on every start(). A
        prior version reset it right after every start() regardless of how
        long that process then stayed up, which meant a sidecar dying
        immediately, repeatedly, always hit the shortest (1s) delay - never
        actually backing off despite RESTART_BACKOFF_SECONDS climbing to 60s
        (the same bug was independently present in bridge/sidecar.py's copy
        of this method).
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

            self.logger.warning(f'matter server sidecar exited unexpectedly (code={returncode})')
            self._process = None
            delay = RESTART_BACKOFF_SECONDS[min(attempt, len(RESTART_BACKOFF_SECONDS) - 1)]
            attempt += 1
            self.logger.info(f'restarting matter server sidecar in {delay}s (attempt {attempt})')
            await asyncio.sleep(delay)
