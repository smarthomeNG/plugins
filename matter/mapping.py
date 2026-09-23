#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Translation types between shng items and Matter's (node, endpoint,
#  cluster, attribute/command) addressing, plus the reverse lookup index
#  used to route incoming reports to items. No network code and no
#  dependency on the plugin/item framework.
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

import threading
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from lib.item.item import Item

# Placeholder in matter_command_params, replaced by the written item value.
VALUE_PLACEHOLDER = '$value'

# Report name for node-level reachability, used in place of an attribute path in dispatch keys.
AVAILABILITY = 'available'


@dataclass(frozen=True)
class DirectNode:
    """An item addressed by a fixed Matter node_id (matter_node)."""

    node_id: int


@dataclass(frozen=True)
class AliasNode:
    """An item addressed through a named alias (matter_alias), resolved to a node_id at dispatch time."""

    name: str


NodeTarget = Union[DirectNode, AliasNode]


def attribute_path(endpoint_id: int, cluster_id: int, attribute_id: int) -> str:
    """matter-server's decimal 'endpoint/cluster/attribute' path string."""
    return f'{endpoint_id}/{cluster_id}/{attribute_id}'


def dispatch_key(target: NodeTarget, report: str) -> str:
    """Reverse-lookup key for items receiving *report* (an attribute path or AVAILABILITY) from *target*."""
    if isinstance(target, DirectNode):
        return f'node:{target.node_id}:{report}'
    return f'alias:{target.name}:{report}'


@dataclass(frozen=True)
class AttributeMapping:
    """
    A matter_attribute-backed item. Reports for this attribute update the
    item; an item write issues a WriteAttribute. Devices may reject direct
    writes to attributes they expect a command for - that is logged, not raised.
    """

    target: NodeTarget
    endpoint_id: int
    cluster_id: int
    attribute_id: int

    @property
    def path(self) -> str:
        return attribute_path(self.endpoint_id, self.cluster_id, self.attribute_id)


@dataclass(frozen=True)
class CommandMapping:
    """
    A matter_command-backed item: a write invokes a cluster command.

    Without command_name_false the command is value-independent (e.g.
    toggle) and only fires on truthy writes - such items are usually reset
    by autotimer, and that reset must not fire the command a second time.
    With command_name_false, falsy writes invoke that command instead
    (on/off pair), so every write fires.
    """

    target: NodeTarget
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
        """False for a falsy write to a value-independent (no command_name_false) command."""
        return self.command_name_false is not None or bool(value)

    def resolve_params(self, value: Any) -> dict[str, Any]:
        """This mapping's params with every VALUE_PLACEHOLDER replaced by *value*."""
        return {key: (value if val == VALUE_PLACEHOLDER else val) for key, val in self.params.items()}


@dataclass(frozen=True)
class BridgeMapping:
    """A matter_expose_type-backed item, exposed as a bridged accessory to other Matter controllers."""

    item_path: str
    expose_type: str
    name: str


class ItemIndex:
    """
    Thread-safe reverse lookup dispatch_key -> items, for routing reports
    arriving on the asyncio thread while items are (un)parsed on others.
    Remembers each item's keys, so removal needs only the item path.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._items_by_key: dict[str, list[Item]] = {}
        self._keys_by_path: dict[str, set[str]] = {}

    def add(self, key: str, item: Item) -> None:
        with self._lock:
            self._items_by_key.setdefault(key, []).append(item)
            self._keys_by_path.setdefault(item.property.path, set()).add(key)

    def items_for(self, key: str) -> tuple[Item, ...]:
        with self._lock:
            return tuple(self._items_by_key.get(key, ()))

    def remove(self, item_path: str) -> bool:
        """Drop the item from every key it was added under; False if it was never added."""
        with self._lock:
            keys = self._keys_by_path.pop(item_path, None)
            if keys is None:
                return False
            for key in keys:
                remaining = [item for item in self._items_by_key.get(key, []) if item.property.path != item_path]
                if remaining:
                    self._items_by_key[key] = remaining
                else:
                    self._items_by_key.pop(key, None)
            return True
