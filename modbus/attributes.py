"""
Item attributes of the modbus plugin and their translation into a ``RegisterSpec``.

The attribute names are shared with modbus_tcp, so items move over by changing only the
plugin instance.
"""

from __future__ import annotations

import ast
from collections.abc import Callable, Mapping
from typing import Any

from .model import Direction, Endian, RegisterKey, RegisterSpec, Table

ADDRESS = 'modBusAddress'
DATATYPE = 'modBusDataType'
FACTOR = 'modBusFactor'
BYTE_ORDER = 'modBusByteOrder'
WORD_ORDER = 'modBusWordOrder'
UNIT = 'modBusUnit'
TABLE = 'modBusObjectType'
DIRECTION = 'modBusDirection'
INVALID = 'modBusInvalid'
INVALID_VALUE = 'modBusInvalidValue'
SUNSPEC = 'modBusSunSpec'
BIT = 'modBusBit'
LOOKUP = 'modBusLookup'
ROUND = 'modBusRound'
POLL = 'modbusPoll'

AttributeGetter = Callable[[str], Any]
"""Returns the value of an item attribute, or None if the item doesn't set it."""


def parse_spec(get: AttributeGetter, default_unit: int, warn: Callable[[str], None]) -> RegisterSpec:
    """
    Register spec from the attributes of one item.

    Invalid table, direction or byte/word order fall back to their defaults with a warning.

    :param get: attribute getter of the item; ``modBusAddress`` must be set
    :param default_unit: unit id when the item sets no ``modBusUnit`` (plugin ``slaveUnit``)
    :param warn: receives one message per fallback
    :raises ValueError: if address, unit, factor, bit or round are not numbers, the lookup is no mapping
        or modBusInvalid no list of numbers
    """
    table = _choice(Table, get(TABLE), Table.HOLDING_REGISTER, TABLE, warn)
    return RegisterSpec(
        key=RegisterKey(parse_unit(get, default_unit), table, int(get(ADDRESS))),
        datatype=str(get(DATATYPE) or 'uint16'),
        byte_order=_endian(get(BYTE_ORDER), BYTE_ORDER, warn),
        word_order=_endian(get(WORD_ORDER), WORD_ORDER, warn),
        factor=1.0 if get(FACTOR) is None else float(get(FACTOR)),
        direction=parse_direction(get, warn),
        invalid=parse_invalid(get(INVALID)),
        invalid_value=get(INVALID_VALUE),
        bit=None if get(BIT) is None else int(get(BIT)),
        lookup=parse_lookup(get(LOOKUP)),
        decimals=None if get(ROUND) is None else int(get(ROUND)),
    )


def parse_invalid(raw: Any) -> frozenset[int | float]:
    """
    Decoded values a ``modBusInvalid`` list declares as "not available".

    :raises ValueError: ``raw`` is no list of numbers
    """
    if raw is None:
        return frozenset()
    if not isinstance(raw, list) or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in raw):
        raise ValueError(f'{INVALID} must be a list of numbers, not {raw!r}')
    return frozenset(raw)


def parse_lookup(raw: Any) -> tuple[tuple[Any, Any], ...]:
    """
    (device value, item value) pairs of a ``modBusLookup`` mapping.

    Items give the mapping as Python literal string (``"{0: 'Standby'}"``), since YAML mappings
    in item definitions are child items.

    :raises ValueError: ``raw`` is neither a mapping nor a string holding one
    """
    if raw is None:
        return ()
    if isinstance(raw, str):
        try:
            raw = ast.literal_eval(raw)
        except (ValueError, SyntaxError):
            raise ValueError(f'{LOOKUP} is no mapping: {raw!r}') from None
    if not isinstance(raw, Mapping):
        raise ValueError(f'{LOOKUP} must be a mapping, not {raw!r}')
    return tuple(raw.items())


def parse_unit(get: AttributeGetter, default_unit: int) -> int:
    """Unit id of an item: ``modBusUnit``, else ``default_unit``; ValueError if not a number."""
    return default_unit if get(UNIT) is None else int(get(UNIT))


def parse_direction(get: AttributeGetter, warn: Callable[[str], None]) -> Direction:
    """Data direction of an item: ``modBusDirection``, read if unset or invalid (with a warning)."""
    return _choice(Direction, get(DIRECTION), Direction.READ, DIRECTION, warn)


def _choice(enum: Any, raw: Any, default: Any, name: str, warn: Callable[[str], None]) -> Any:
    if raw is None:
        return default
    try:
        return enum(raw)
    except ValueError:
        warn(f'invalid {name} {raw!r}, using {default.value}')
        return default


def _endian(raw: Any, name: str, warn: Callable[[str], None]) -> Endian:
    if raw is None:
        return Endian.BIG
    try:
        return Endian.parse(raw)
    except ValueError:
        warn(f'invalid {name} {raw!r}, using big')
        return Endian.BIG
