#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Alias registry for the server role: alias name -> node_id, the
#  reverse node_id -> alias names mapping used to route reports, and
#  which items depend on which alias.
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

from .mapping import AliasNode, DirectNode, NodeTarget


class AliasRegistry:
    """
    Thread-safe alias table. Written from item parsing, item writes and the
    webif; read from the asyncio thread on every incoming report.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._node_by_alias: dict[str, int] = {}
        self._aliases_by_node: dict[int, set[str]] = {}
        self._alias_by_item: dict[str, str] = {}

    def set(self, name: str, node_id: int) -> bool:
        """Point alias *name* at *node_id*; False if it already pointed there."""
        with self._lock:
            old_node_id = self._node_by_alias.get(name)
            if old_node_id == node_id:
                return False
            if old_node_id is not None:
                self._forget_reverse(name, old_node_id)
            self._node_by_alias[name] = node_id
            self._aliases_by_node.setdefault(node_id, set()).add(name)
            return True

    def remove(self, name: str) -> int | None:
        """Remove alias *name*; returns the node_id it pointed at, or None if unknown."""
        with self._lock:
            node_id = self._node_by_alias.pop(name, None)
            if node_id is not None:
                self._forget_reverse(name, node_id)
            return node_id

    def resolve(self, target: NodeTarget) -> int | None:
        """Current node_id for *target*, or None for an alias that isn't defined."""
        if isinstance(target, DirectNode):
            return target.node_id
        with self._lock:
            return self._node_by_alias.get(target.name)

    def targets_for(self, node_id: int) -> tuple[NodeTarget, ...]:
        """Every target a report from *node_id* is addressed to: the node itself, then each alias pointing at it."""
        with self._lock:
            names = sorted(self._aliases_by_node.get(node_id, ()))
        return (DirectNode(node_id), *(AliasNode(name) for name in names))

    def snapshot(self) -> dict[str, int]:
        """Copy of the alias name -> node_id table."""
        with self._lock:
            return dict(self._node_by_alias)

    def bind_item(self, item_path: str, alias: str) -> None:
        """Record that the item at *item_path* is addressed through *alias*."""
        with self._lock:
            self._alias_by_item[item_path] = alias

    def unbind_item(self, item_path: str) -> str | None:
        """Forget an item's alias dependency; returns the alias it used, or None."""
        with self._lock:
            return self._alias_by_item.pop(item_path, None)

    def dependents(self, alias: str) -> list[str]:
        """Sorted paths of the items addressed through *alias*."""
        with self._lock:
            return sorted(path for path, name in self._alias_by_item.items() if name == alias)

    def unknown_references(self) -> list[tuple[str, str]]:
        """Sorted (item_path, alias) pairs whose alias is not defined."""
        with self._lock:
            return sorted((path, name) for path, name in self._alias_by_item.items() if name not in self._node_by_alias)

    def _forget_reverse(self, name: str, node_id: int) -> None:
        names = self._aliases_by_node.get(node_id)
        if names is None:
            return
        names.discard(name)
        if not names:
            del self._aliases_by_node[node_id]
