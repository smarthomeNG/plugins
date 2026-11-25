"""
Device adapters: behaviour of a device beyond plain register reads and writes.

The plugin parameter ``adapter`` selects one adapter per plugin instance; ``''`` (the default)
selects ``NoAdapter``. An adapter gets a ``Bus`` for its own requests over the plugin's
connection.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Protocol

from .devices.pluggit import PluggitAdapter
from .model import RegisterSpec, Table, Value


class Bus(Protocol):
    """Requests over the plugin's connection, for adapters."""

    async def read(self, unit: int, table: Table, address: int, count: int) -> list[int] | list[bool] | None:
        """Registers (or bits) from ``address`` on; None if not connected or the device answers with an error."""
        ...

    async def write(self, unit: int, table: Table, address: int, registers: Sequence[int]) -> bool:
        """Write holding registers from ``address`` on; False if not connected or the write failed (logged)."""
        ...


class DeviceAdapter(Protocol):
    """Device logic around item writes."""

    async def write(self, bus: Bus, spec: RegisterSpec, value: Value) -> bool:
        """
        Prepare or perform the write of an item value.

        :param spec: the written item's register spec
        :param value: the item value, before lookup, factor and encoding
        :returns: True if the adapter wrote ``value`` itself, False to let the plugin write it as usual
        :raises ValueError: ``value`` cannot be written to this device; the plugin logs the message
        """
        ...


class NoAdapter:
    """Plain register access, no device logic."""

    async def write(self, bus: Bus, spec: RegisterSpec, value: Value) -> bool:
        """Never writes itself."""
        return False


ADAPTERS: dict[str, Callable[[], DeviceAdapter]] = {'': NoAdapter, 'pluggit': PluggitAdapter}
"""Adapter name (plugin parameter ``adapter``) -> factory."""


def create(name: str) -> DeviceAdapter:
    """Adapter selected by the plugin parameter ``adapter``; ValueError for unknown names."""
    if name not in ADAPTERS:
        raise ValueError(f'unknown adapter {name!r}, known: {", ".join(sorted(n for n in ADAPTERS if n))}')
    return ADAPTERS[name]()
