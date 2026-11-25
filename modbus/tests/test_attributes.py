"""Item attributes -> register spec."""

import pytest

from plugins.modbus import attributes
from plugins.modbus.model import Direction, Endian, RegisterKey, Table


def parse(conf: dict, default_unit: int = 1):
    warnings: list[str] = []
    spec = attributes.parse_spec(conf.get, default_unit, warnings.append)
    return spec, warnings


def test_defaults():
    spec, warnings = parse({'modBusAddress': 40067}, default_unit=3)
    assert spec.key == RegisterKey(3, Table.HOLDING_REGISTER, 40067)
    assert (spec.datatype, spec.byte_order, spec.word_order, spec.factor, spec.direction) == (
        'uint16',
        Endian.BIG,
        Endian.BIG,
        1.0,
        Direction.READ,
    )
    assert not warnings


def test_all_attributes():
    spec, warnings = parse(
        {
            'modBusAddress': '12',
            'modBusUnit': 5,
            'modBusObjectType': 'InputRegister',
            'modBusDataType': 'int32',
            'modBusByteOrder': 'Endian.LITTLE',
            'modBusWordOrder': 'little',
            'modBusFactor': '0.1',
            'modBusDirection': 'read_write',
        }
    )
    assert spec.key == RegisterKey(5, Table.INPUT_REGISTER, 12)
    assert spec.datatype == 'int32'
    assert spec.byte_order is Endian.LITTLE
    assert spec.word_order is Endian.LITTLE
    assert spec.factor == 0.1
    assert spec.direction is Direction.READ_WRITE
    assert not warnings


@pytest.mark.parametrize(
    'name,value', [('modBusObjectType', 'Register'), ('modBusDirection', 'both'), ('modBusByteOrder', 'Endian.MIDDLE')]
)
def test_invalid_choice_falls_back_with_warning(name, value):
    spec, warnings = parse({'modBusAddress': 1, name: value})
    assert spec.key.table is Table.HOLDING_REGISTER
    assert spec.direction is Direction.READ
    assert spec.byte_order is Endian.BIG
    assert len(warnings) == 1 and name in warnings[0]


@pytest.mark.parametrize('conf', [{'modBusAddress': 'x'}, {'modBusAddress': 1, 'modBusFactor': 'ten'}])
def test_non_numbers_are_rejected(conf):
    with pytest.raises(ValueError):
        parse(conf)
