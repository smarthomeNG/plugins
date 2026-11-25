"""
Value and addressing types of the modbus plugin.

A ``RegisterSpec`` describes one data point as configured on an item; codecs, the read path
and the write path work on specs, never on raw item attributes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time
from enum import Enum
from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from lib.item.item import Item

Value = int | float | str | bool | list[bool] | datetime | date | time
"""A decoded item value; ``list[bool]`` for bit lists, ``datetime``/``date``/``time`` for timestamps."""


class Table(Enum):
    """Modbus data table; the value is the ``modBusObjectType`` attribute value."""

    COIL = 'Coil'
    DISCRETE_INPUT = 'DiscreteInput'
    INPUT_REGISTER = 'InputRegister'
    HOLDING_REGISTER = 'HoldingRegister'

    @property
    def writable(self) -> bool:
        """Whether Modbus defines write functions for this table."""
        return self in (Table.COIL, Table.HOLDING_REGISTER)

    @property
    def bit_sized(self) -> bool:
        """Whether one address holds one bit instead of one 16-bit register."""
        return self in (Table.COIL, Table.DISCRETE_INPUT)


class Endian(Enum):
    """Byte order within a register, or word order across registers."""

    BIG = 'big'
    LITTLE = 'little'

    @classmethod
    def parse(cls, text: str) -> Endian:
        """
        Endian from an attribute value.

        Accepts ``big``/``little`` in any case and the legacy ``Endian.BIG``/``Endian.LITTLE``
        form; raises ValueError otherwise.
        """
        name = str(text).split('.')[-1].strip().lower()
        try:
            return cls(name)
        except ValueError:
            raise ValueError(f'invalid byte/word order: {text!r}') from None


class Direction(Enum):
    """Data flow between item and device; the value is the ``modBusDirection`` attribute value."""

    READ = 'read'
    WRITE = 'write'
    READ_WRITE = 'read_write'

    @property
    def reads(self) -> bool:
        """Whether the item is updated from the device."""
        return self in (Direction.READ, Direction.READ_WRITE)

    @property
    def writes(self) -> bool:
        """Whether item changes are written to the device."""
        return self in (Direction.WRITE, Direction.READ_WRITE)


class RegisterKey(NamedTuple):
    """Identity of a data point on the bus."""

    unit: int
    table: Table
    address: int

    def __str__(self) -> str:
        """``<table>.<address>.<unit>``, e.g. ``HoldingRegister.528.1``."""
        return f'{self.table.value}.{self.address}.{self.unit}'


@dataclass(frozen=True)
class RegisterSpec:
    """
    One data point as configured on an item.

    :param key: where the point lives on the bus
    :param datatype: codec datatype name, e.g. ``uint16``, ``int32``, ``float32``, ``string16``
    :param byte_order: byte order within each register
    :param word_order: register order of multi-register values
    :param factor: decoded value * factor = item value; writes divide by it
    :param direction: data flow between item and device
    :param invalid: decoded values meaning "not available", in addition to the codec defaults
    :param invalid_value: item value for "not available"; None leaves the item unchanged
    :param scale_ref: register holding a power-of-ten exponent the value is scaled by (SunSpec scale factor)
    :param bit: the item value is this bit of the decoded number (0 = least significant), factor not applied
    :param lookup: (device value, item value) pairs; reads map device to item values, writes back
    :param decimals: read values are rounded to this many decimals (0 gives an int, str items get text
        with exactly this many decimals); None keeps them
    """

    key: RegisterKey
    datatype: str = 'uint16'
    byte_order: Endian = Endian.BIG
    word_order: Endian = Endian.BIG
    factor: float = 1.0
    direction: Direction = Direction.READ
    invalid: frozenset[int | float] = field(default_factory=frozenset)
    invalid_value: Value | None = None
    scale_ref: RegisterKey | None = None
    bit: int | None = None
    lookup: tuple[tuple[Value, Value], ...] = ()
    decimals: int | None = None


@dataclass(eq=False)
class Point:
    """
    A configured item bound to its register spec, with the last transfers shown in the web interface.

    :param spec: what the item reads or writes
    :param item: the bound item
    :param value: last value read from (or initially held by) the item
    """

    spec: RegisterSpec
    item: Item
    value: Value | None = None
    read_dt: datetime | None = None
    last_read_dt: datetime | None = None
    last_value: Value | None = None
    write_value: Value | None = None
    write_dt: datetime | None = None
    last_write_dt: datetime | None = None
    last_write_value: Value | None = None

    def record_read(self, value: Value, when: datetime) -> None:
        """Remember a value read from the device, keeping the previous one."""
        self.last_read_dt, self.last_value = self.read_dt, self.value
        self.read_dt, self.value = when, value

    def record_write(self, value: Value, when: datetime) -> None:
        """Remember a value written to the device, keeping the previous one."""
        self.last_write_dt, self.last_write_value = self.write_dt, self.write_value
        self.write_dt, self.write_value = when, value


ILLEGAL_DATA_ADDRESS = 2
"""Modbus exception code of a request for registers (or bits) the device doesn't have."""


@dataclass(frozen=True)
class Answer:
    """
    Outcome of one read request.

    :param values: the registers (or bits) read; None if the request failed
    :param exception_code: Modbus exception code of an error response; None for other failures
    """

    values: list[int] | list[bool] | None
    exception_code: int | None = None

    @property
    def rejected(self) -> bool:
        """Whether the device answered that it doesn't have the requested addresses."""
        return self.exception_code == ILLEGAL_DATA_ADDRESS
