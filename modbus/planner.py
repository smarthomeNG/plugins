"""
Read planning: which requests one poll sends.

Points of the same unit and table whose registers touch or overlap are read with one request,
up to the protocol limits. Gaps are never bridged, so a block only covers registers some
item reads.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .codec import CodecRegistry
from .model import Point, Table

MAX_REGISTERS = 125
MAX_BITS = 2000


@dataclass(frozen=True)
class ReadBlock:
    """One read request and the points it serves; ``start``/``count`` in registers or bits."""

    unit: int
    table: Table
    start: int
    count: int
    points: tuple[Point, ...]


def span(point: Point, codecs: CodecRegistry) -> int:
    """Registers (or bits, for coils and discrete inputs) one point occupies."""
    spec = point.spec
    return 1 if spec.key.table.bit_sized else codecs.resolve(spec.datatype).register_count(spec.datatype)


def plan(
    points: Iterable[Point], codecs: CodecRegistry, max_registers: int = MAX_REGISTERS, max_bits: int = MAX_BITS
) -> list[ReadBlock]:
    """Requests reading ``points``, grouped by unit and table, in address order."""
    groups: dict[tuple[int, Table], list[Point]] = {}
    for point in points:
        groups.setdefault((point.spec.key.unit, point.spec.key.table), []).append(point)

    blocks: list[ReadBlock] = []
    for (unit, table), members in groups.items():
        limit = max_bits if table.bit_sized else max_registers
        members.sort(key=lambda p: p.spec.key.address)
        start = end = None
        current: list[Point] = []
        for point in members:
            address = point.spec.key.address
            stop = address + span(point, codecs)
            if current and address <= end and max(end, stop) - start <= limit:
                end = max(end, stop)
                current.append(point)
                continue
            if current:
                blocks.append(ReadBlock(unit, table, start, end - start, tuple(current)))
            start, end, current = address, stop, [point]
        if current:
            blocks.append(ReadBlock(unit, table, start, end - start, tuple(current)))
    return blocks
