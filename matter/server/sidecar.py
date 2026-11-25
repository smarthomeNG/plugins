#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  The vendored matter-server as the server role's child process.
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

import logging
from dataclasses import dataclass

from ..sidecar import NodeSidecar


@dataclass(frozen=True)
class ServerSidecarSettings:
    """matter-server command line settings (see plugin.yaml's server_* parameters)."""

    port: int
    enable_test_net_dcl: bool = False
    # Interface for mDNS/operational traffic on multi-interface hosts, e.g. 'eth0'.
    primary_interface: str | None = None
    # Only applied when the fabric is first created - persisted in its NOC afterwards.
    fabric_vendor_id: int = 65521
    fabric_label: str = 'SmartHomeNG'
    # HCI id (e.g. '0' for hci0), needed for BLE commissioning of not-yet-networked Thread devices.
    bluetooth_adapter: str | None = None


class MatterServerSidecar(NodeSidecar):
    """Owns the matter-server child process."""

    LABEL = 'matter server sidecar'
    LOG_PREFIX = '[matter-server]'
    READY_MARKER = 'Webserver listening on'  # matter-server/src/server/WebServer.ts
    PIDFILE_NAME = 'matter-server.pid'
    MISSING_ENTRY_HINT = "Run 'npm install' in the plugin's sidecar/ directory first - see user_doc.rst."

    def __init__(
        self,
        node_binary: str,
        entry_path: str,
        storage_path: str,
        settings: ServerSidecarSettings,
        logger: logging.Logger | None = None,
    ):
        super().__init__(node_binary, entry_path, storage_path, logger)
        self.settings = settings

    def _build_args(self) -> list[str]:
        settings = self.settings
        args = [
            self.entry_path,
            '--port',
            str(settings.port),
            '--storage-path',
            self.storage_path,
            '--log-level',
            'info',
            '--default-fabric-label',
            settings.fabric_label,
            '--vendorid',
            str(settings.fabric_vendor_id),
        ]
        if settings.enable_test_net_dcl:
            args.append('--enable-test-net-dcl')
        if settings.primary_interface:
            args += ['--primary-interface', settings.primary_interface]
        if settings.bluetooth_adapter:
            args += ['--bluetooth-adapter', settings.bluetooth_adapter]
        return args
