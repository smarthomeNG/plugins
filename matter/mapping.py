#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Pure translation helpers between shng items and Matter's
#  (node, endpoint, cluster, attribute/command) addressing. No network
#  code and no dependency on the plugin/item framework lives here, so it
#  can be unit-tested directly - see tests/test_mapping.py.
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

from dataclasses import dataclass, field
from typing import Any

# Sentinel used in an item's matter_command_params config: gets replaced with
# the item's current value at write time. Lets one generic command mapping
# cover both fixed commands (Toggle, UpOrOpen with no params) and
# value-carrying ones (MoveToLevel, GoToLiftPercentage) without a templating
# engine.
VALUE_PLACEHOLDER = '$value'


def attribute_path(endpoint_id: int, cluster_id: int, attribute_id: int) -> str:
    """Build matter-server's decimal 'endpoint/cluster/attribute' path string."""
    return f'{endpoint_id}/{cluster_id}/{attribute_id}'


def report_mapping_key(node_id: int, path: str) -> str:
    """Build the reverse-lookup key used with SmartPlugin.add_item(..., mapping=...)."""
    return f'{node_id}:{path}'


def availability_mapping_key(node_id: int) -> str:
    """
    Reverse-lookup key for a matter_available item. Node-level, not tied to
    an endpoint/cluster/attribute - 'available' can never collide with a
    real report_mapping_key, since a path there is always three ints
    joined by '/'.
    """
    return f'{node_id}:available'


@dataclass(frozen=True)
class AttributeMapping:
    """
    A matter_attribute-backed item.

    Read direction: subscription reports for this (node, path) update the item.
    Write direction: an item write issues a WriteAttribute call with the item's
    new value. Not every cluster attribute accepts direct writes on real
    devices (many actuators expect a command instead) - if the device rejects
    it, the plugin logs the failure, it does not crash the update.
    """

    node_id: int
    endpoint_id: int
    cluster_id: int
    attribute_id: int

    @property
    def path(self) -> str:
        return attribute_path(self.endpoint_id, self.cluster_id, self.attribute_id)

    @property
    def report_key(self) -> str:
        return report_mapping_key(self.node_id, self.path)


@dataclass(frozen=True)
class CommandMapping:
    """
    A matter_command-backed item write invokes a command.

    With `command_name_false` unset, this is a value-independent action (e.g.
    Toggle) - `should_fire` only reacts to a truthy write, not any write.
    Matters because such items are typically paired with `autotimer` for a
    momentary-trigger effect: autotimer's reset-to-False write reaches
    update_item too (caller='Autotimer', distinct from the plugin's own
    shortname, so the own-write guard doesn't catch it) and would otherwise
    re-invoke the command a second time - e.g. Toggle firing once on write,
    once on the reset, flipping the device twice for nothing.

    Set `command_name_false` to route falsy writes to a different command
    (command_name='on', command_name_false='off') so a bool item means what
    it looks like; `should_fire` then reacts to every write, since falsy is
    a real "off", not an autotimer artifact.
    """

    node_id: int
    endpoint_id: int
    cluster_id: int
    command_name: str
    params: dict[str, Any] = field(default_factory=dict)
    command_name_false: str | None = None

    def resolve_command_name(self, value: Any) -> str:
        if self.command_name_false is not None and not value:
            return self.command_name_false
        return self.command_name

    def should_fire(self, value: Any) -> bool:
        """False for a falsy write to a value-independent (no command_name_false) command mapping."""
        return self.command_name_false is not None or bool(value)

    def resolve_params(self, value: Any) -> dict[str, Any]:
        """Return this mapping's params with any '$value' placeholder replaced by `value`."""
        return {key: (value if val == VALUE_PLACEHOLDER else val) for key, val in self.params.items()}
