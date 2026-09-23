#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  sidecar/bridge.js as the bridge role's child process, and the bridge's
#  per-instance Matter identity.
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

import hashlib
import logging
from dataclasses import dataclass

from ..sidecar import NodeSidecar

# Matter Core Spec, Basic Information cluster: UniqueID and SerialNumber are strings of at most 32 chars.
MAX_BASIC_INFORMATION_STRING = 32

# Identity of the default (unnamed) instance - kept as is so existing pairings stay valid.
DEFAULT_BRIDGE_UNIQUE_ID = 'shng-matter-bridge-0001'


def bridge_unique_id(instance: str) -> str:
    """
    UniqueID/SerialNumber of the bridge for a plugin instance: the default
    instance keeps DEFAULT_BRIDGE_UNIQUE_ID, a named one gets
    'shng-bridge-<instance>'. An instance name too long for the 32-char limit
    is cut and suffixed with a short hash of the full name, so two long names
    sharing a prefix still differ.
    """
    if not instance:
        return DEFAULT_BRIDGE_UNIQUE_ID
    unique_id = f'shng-bridge-{instance}'
    if len(unique_id) <= MAX_BASIC_INFORMATION_STRING:
        return unique_id
    digest = hashlib.sha256(instance.encode('utf-8')).hexdigest()[:6]
    return f'{unique_id[: MAX_BASIC_INFORMATION_STRING - len(digest) - 1]}-{digest}'


@dataclass(frozen=True)
class BridgeSidecarSettings:
    """bridge.js command line settings (see plugin.yaml's bridge_* parameters)."""

    matter_port: int
    control_port: int
    passcode: int
    discriminator: int
    vendor_id: int
    unique_id: str = DEFAULT_BRIDGE_UNIQUE_ID
    primary_interface: str | None = None


class MatterBridgeSidecar(NodeSidecar):
    """Owns the bridge.js child process."""

    LABEL = 'matter bridge sidecar'
    LOG_PREFIX = '[bridge]'
    READY_MARKER = '[bridge] Matter node started'
    PIDFILE_NAME = 'bridge.pid'
    MISSING_ENTRY_HINT = 'Check the plugin installation.'

    def __init__(
        self,
        node_binary: str,
        entry_path: str,
        storage_path: str,
        settings: BridgeSidecarSettings,
        logger: logging.Logger | None = None,
    ):
        super().__init__(node_binary, entry_path, storage_path, logger)
        self.settings = settings

    def _build_args(self) -> list[str]:
        settings = self.settings
        args = [
            self.entry_path,
            '--matter-port',
            str(settings.matter_port),
            '--control-port',
            str(settings.control_port),
            # matter.js maps only the --key=value form to its storage.path config.
            f'--storage-path={self.storage_path}',
            '--passcode',
            str(settings.passcode),
            '--discriminator',
            str(settings.discriminator),
            '--vendor-id',
            str(settings.vendor_id),
            '--unique-id',
            settings.unique_id,
        ]
        if settings.primary_interface:
            args += ['--primary-interface', settings.primary_interface]
        return args
