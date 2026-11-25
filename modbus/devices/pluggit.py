"""
Pluggit air handlers (AP310 and relatives): datatypes and unit mode logic.

The unit mode register takes commands, not a state: writing a mode's bit switches the mode on,
the bit plus 0x8000 switches it off; demand, manual and week program mode have no off command
(another mode replaces them). Parameters are 32-bit values, low word first.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import TYPE_CHECKING, ClassVar

from ..model import RegisterSpec, Table, Value

if TYPE_CHECKING:
    from ..adapter import Bus

UNIT_MODE = 168
SPEED_LEVEL = 324
MANUAL_MODE = 0x0004
OFF = 0x8000
SWITCHABLE_OFF = frozenset({4, 5, 6, 7, 11})
"""Unit mode bits with an off command: away, night, fireplace, manual bypass, summer."""


class PluggitAdapter:
    """
    ``adapter: pluggit``: unit mode switches and speed level writes.

    - an item with ``modBusBit`` on the unit mode register writes the mode's on or off command
    - writing the speed level switches the unit to manual mode first, as the speed level only
      applies there; the unit needs ``settle`` seconds before it accepts the speed level
    """

    def __init__(self, settle: float = 0.5) -> None:
        self._settle = settle

    async def write(self, bus: Bus, spec: RegisterSpec, value: Value) -> bool:
        """Write unit mode switches; prepare speed level writes."""
        key = spec.key
        if key.table is not Table.HOLDING_REGISTER:
            return False
        if key.address == UNIT_MODE and spec.bit is not None:
            await bus.write(key.unit, key.table, UNIT_MODE, [mode_command(spec.bit, bool(value))])
            return True
        if key.address == SPEED_LEVEL:
            await bus.write(key.unit, key.table, UNIT_MODE, [MANUAL_MODE])
            await asyncio.sleep(self._settle)
        return False


def mode_command(bit: int, on: bool) -> int:
    """Unit mode register command that switches the mode of ``bit`` on or off; ValueError if there is none."""
    if on:
        return 1 << bit
    if bit not in SWITCHABLE_OFF:
        raise ValueError(f'pluggit unit mode bit {bit} cannot be switched off, select another mode instead')
    return OFF | 1 << bit


class _ReadOnlyCodec:
    """Base for pluggit datatypes that are only read."""

    counts: ClassVar[dict[str, int]]

    def handles(self, datatype: str) -> bool:
        """Whether ``datatype`` is one of this codec's names."""
        return datatype in self.counts

    def register_count(self, datatype: str) -> int:
        """Registers of the datatype."""
        return self.counts[datatype]

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """Not supported."""
        raise ValueError(f'{spec.datatype} cannot be written')

    def invalid(self, datatype: str) -> frozenset[int | float]:
        """No sentinel values."""
        return frozenset()


class MacCodec(_ReadOnlyCodec):
    """``pluggit_mac``: MAC address from registers 0, 3 and 2 of four (register 1 unused), high byte first."""

    counts: ClassVar[dict[str, int]] = {'pluggit_mac': 4}

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """``xx:xx:xx:xx:xx:xx`` in lower case."""
        octets = [part for index in (0, 3, 2) for part in (registers[index] >> 8, registers[index] & 0xFF)]
        return ':'.join(f'{octet:02x}' for octet in octets)


class VersionCodec(_ReadOnlyCodec):
    """``pluggit_version``: ``<high byte>.<low byte>``; ``pluggit_version_bcd``: three BCD digits ``d.dd``."""

    counts: ClassVar[dict[str, int]] = {'pluggit_version': 1, 'pluggit_version_bcd': 1}

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """Version string of one register."""
        word = registers[0]
        if spec.datatype == 'pluggit_version_bcd':
            return f'{word >> 12 & 0xF}.{word >> 8 & 0xF}{word >> 4 & 0xF}'
        return f'{word >> 8}.{word & 0xFF}'


CODECS = (MacCodec(), VersionCodec())
