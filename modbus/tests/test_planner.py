"""Read planning: adjacent points of one unit and table share a request."""

from plugins.modbus.codec import default_registry
from plugins.modbus.model import Point, RegisterKey, RegisterSpec, Table
from plugins.modbus.planner import plan

CODECS = default_registry()


def point(address: int, datatype: str = 'uint16', table: Table = Table.HOLDING_REGISTER, unit: int = 1) -> Point:
    return Point(RegisterSpec(RegisterKey(unit, table, address), datatype=datatype), item=None)


def spans(points: list[Point], **limits) -> list[tuple]:
    return [(b.unit, b.table, b.start, b.count, len(b.points)) for b in plan(points, CODECS, **limits)]


def test_adjacent_registers_share_a_request():
    assert spans([point(10), point(11, 'int32'), point(13)]) == [(1, Table.HOLDING_REGISTER, 10, 4, 3)]


def test_gaps_are_not_bridged():
    assert spans([point(10), point(12)]) == [
        (1, Table.HOLDING_REGISTER, 10, 1, 1),
        (1, Table.HOLDING_REGISTER, 12, 1, 1),
    ]


def test_points_on_the_same_register_share_it():
    assert spans([point(40081, 'uint8_high'), point(40081, 'uint8_low'), point(40082)]) == [
        (1, Table.HOLDING_REGISTER, 40081, 2, 3)
    ]


def test_units_and_tables_are_separate():
    blocks = spans([point(1), point(2, unit=2), point(3, table=Table.INPUT_REGISTER), point(4, table=Table.COIL)])
    assert sorted(blocks, key=lambda b: (b[0], b[1].value)) == [
        (1, Table.COIL, 4, 1, 1),
        (1, Table.HOLDING_REGISTER, 1, 1, 1),
        (1, Table.INPUT_REGISTER, 3, 1, 1),
        (2, Table.HOLDING_REGISTER, 2, 1, 1),
    ]


def test_order_of_configuration_does_not_matter():
    assert spans([point(13), point(10), point(11, 'int32')]) == [(1, Table.HOLDING_REGISTER, 10, 4, 3)]


def test_blocks_respect_the_request_size_limit():
    points = [point(address) for address in range(0, 130)]
    assert [(b[2], b[3]) for b in spans(points)] == [(0, 125), (125, 5)]
    assert [(b[2], b[3]) for b in spans(points, max_registers=50)] == [(0, 50), (50, 50), (100, 30)]


def test_bit_tables_use_the_bit_limit():
    points = [point(address, table=Table.DISCRETE_INPUT) for address in range(0, 2001)]
    assert [(b[2], b[3]) for b in spans(points)] == [(0, 2000), (2000, 1)]


def test_a_value_never_straddles_two_blocks():
    points = [point(address) for address in range(0, 124)] + [point(124, 'int32')]
    assert [(b[2], b[3]) for b in spans(points)] == [(0, 124), (124, 2)]
