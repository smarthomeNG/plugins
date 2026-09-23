#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2026-  Sebastian Helms                 Morg @ knx-user-forum
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#
#  Contracts between the Matter plugin frame and its roles (server,
#  bridge): the Role protocol each role implements, the RoleHost view of
#  the plugin a role depends on, role status, and the shared retry backoff.
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

import concurrent.futures
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Any, Callable, ClassVar, Coroutine, Iterable, Mapping, Protocol

if TYPE_CHECKING:
    from lib.item.item import Item
    from lib.item.items import Items

RESTART_BACKOFF_SECONDS: tuple[int, ...] = (1, 2, 5, 10, 30, 60)

# A run that lasted at least this long counts as recovered - the next failure starts the schedule over.
STABLE_RUN_SECONDS = RESTART_BACKOFF_SECONDS[-1]


class RoleConfigError(Exception):
    """Permanent misconfiguration of a role - retrying cannot help (missing entry file, bad node binary, ...)."""


class RoleState(Enum):
    STARTING = 'starting'
    CONNECTED = 'connected'
    RECONNECTING = 'reconnecting'
    RESTARTING = 'restarting'
    FAILED = 'failed'


@dataclass(frozen=True)
class RoleStatus:
    """Current lifecycle state of a role, with a human-readable detail for the webif."""

    state: RoleState
    detail: str = ''


@dataclass(frozen=True)
class ItemRegistration:
    """
    A role's claim on an item from parse_item(): the plugin-specific config
    data to store for it (SmartPlugin.add_item()'s config_data_dict) and
    whether shng item writes should reach the plugin's update_item().
    """

    config: Mapping[str, Any] = field(default_factory=dict)
    updating: bool = True


def merge_registrations(registrations: Iterable[ItemRegistration | None]) -> ItemRegistration | None:
    """
    Combine every role's registration for one item into the single one
    SmartPlugin.add_item() accepts - an item carrying both server and bridge
    attributes is registered once, with both roles' config data.
    """
    claimed = [registration for registration in registrations if registration is not None]
    if not claimed:
        return None
    config: dict[str, Any] = {}
    for registration in claimed:
        config.update(registration.config)
    return ItemRegistration(config, updating=any(registration.updating for registration in claimed))


class Backoff:
    """
    Escalating retry delay (RESTART_BACKOFF_SECONDS, capped at its last
    entry). Call started() once an attempt succeeded - if that attempt then
    lasted at least stable_after seconds, the next next_delay() starts the
    schedule over instead of escalating further.
    """

    def __init__(
        self,
        schedule: tuple[int, ...] = RESTART_BACKOFF_SECONDS,
        stable_after: float = STABLE_RUN_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._schedule = schedule
        self._stable_after = stable_after
        self._clock = clock
        self._attempt = 0
        self._started_at: float | None = None

    @property
    def attempt(self) -> int:
        """Number of delays handed out since the last reset."""
        return self._attempt

    def started(self) -> None:
        """Record that an attempt just succeeded."""
        self._started_at = self._clock()

    def reset(self) -> None:
        """Start the schedule over."""
        self._attempt = 0
        self._started_at = None

    def next_delay(self) -> int:
        """Delay before the next attempt, in seconds."""
        if self._started_at is not None and self._clock() - self._started_at >= self._stable_after:
            self._attempt = 0
        self._started_at = None
        delay = self._schedule[min(self._attempt, len(self._schedule) - 1)]
        self._attempt += 1
        return delay


class RoleHost(Protocol):
    """
    The part of the Matter plugin (a SmartPlugin) a role depends on. Matter
    satisfies it structurally; roles never touch plugin internals beyond this.
    """

    logger: logging.Logger
    items: Items
    alive: bool

    def get_fullname(self) -> str: ...

    def get_instance_name(self) -> str: ...

    def has_iattr(self, conf: dict, attr: str) -> bool: ...

    def get_iattr_value(self, conf: dict, attr: str, default: Any = None) -> Any: ...

    def get_item_config(self, item: Item | str) -> dict: ...

    def run_asyncio_coro(self, coro: Coroutine, timeout: float = 60) -> Any: ...

    def submit_asyncio_coro(
        self, coro: Coroutine, on_error: Callable[[BaseException], None] | None = None
    ) -> concurrent.futures.Future | None: ...


class Role(Protocol):
    """
    One independently running part of the Matter plugin. The plugin frame
    dispatches item callbacks to every enabled role, runs each role's run()
    under its own supervision (a crash restarts only that role), and calls
    cleanup() before a restart and on shutdown.
    """

    name: ClassVar[str]
    # Item attributes that make an item this role's - used to warn about items configured for a disabled role.
    ITEM_ATTRIBUTES: ClassVar[tuple[str, ...]]
    status: RoleStatus

    def prepare(self) -> None:
        """Synchronous setup once all items are parsed, before run() is started (plugin.run())."""

    def parse_item(self, item: Item) -> ItemRegistration | None:
        """Claim an item for this role, or None if it isn't one of this role's items."""

    def unparse_item(self, item: Item) -> bool:
        """Drop this role's bookkeeping for an item; True if the item was this role's."""

    def update_item(self, item: Item, caller: str | None, source: str | None, dest: str | None) -> None:
        """React to a shng write of an item this role registered - must not block the calling thread."""

    def describe_item(self, item: Item) -> str | None:
        """One-line description of this role's mapping for an item (webif Items tab), or None if not mapped."""

    async def run(self) -> None:
        """Run until cancelled; raise RoleConfigError for a permanent problem."""

    async def cleanup(self) -> None:
        """Release everything run() started (sidecar process, connection) - safe to call repeatedly."""
