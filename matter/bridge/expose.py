#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  The item kinds the bridge role can expose as bridged Matter
#  accessories. Keys must match sidecar/bridge.js's EXPOSE_TYPES and
#  plugin.yaml's matter_expose_type valid_list (tests/test_consistency.py).
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

from dataclasses import dataclass

# Matter Core Spec, Bridged Device Basic Information: NodeLabel/ProductName hold at most 32 chars.
MAX_EXPOSE_NAME_LENGTH = 32


@dataclass(frozen=True)
class ExposeTypeSpec:
    """One matter_expose_type: which shng item type it reads, and whether controllers can command it."""

    name: str
    item_type: str
    commandable: bool


EXPOSE_TYPES: dict[str, ExposeTypeSpec] = {
    spec.name: spec
    for spec in (
        ExposeTypeSpec('switch', 'bool', commandable=True),
        ExposeTypeSpec('contact', 'bool', commandable=False),
        ExposeTypeSpec('temperature_sensor', 'num', commandable=False),
    )
}
