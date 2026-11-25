"""The Kostal profiles cover the kostalmodbus / ksemmodbus registers and read them like those plugins."""

import pytest

from plugins.kostalmodbus.inverter import Inverter
from plugins.ksemmodbus.ksem import Ksem
from plugins.modbus import profiles
from plugins.modbus.tests.profile_rig import poll_once, text, words

KOSTAL_UNIT = 71


def points(profile_id: str) -> dict[int, dict]:
    """Address -> generated item attributes (``@instance`` removed) of all register items."""
    profile = next(p for p in profiles.load_all() if p.id == profile_id)
    found: dict[int, dict] = {}

    def walk(node: dict) -> None:
        attrs = {key.removesuffix('@instance'): value for key, value in node.items() if key.startswith('modBus')}
        if attrs:
            assert attrs['modBusAddress'] not in found
            found[attrs['modBusAddress']] = attrs
        for value in node.values():
            if isinstance(value, dict):
                walk(value)

    walk(profiles.to_struct(profile))
    return found


PLENTICORE_DATATYPES = {
    'Float': ('float32', 'Endian.LITTLE'),
    'U16': ('uint16', None),
    'U16_2': ('uint16', None),
    'U32': ('uint32', 'Endian.LITTLE'),
    'S16': ('int16', None),
    'STR08': ('string16', None),
    'STR16': ('string24', None),
    'STR32': ('string32', None),
}

KSEM_DATATYPES = {
    'Float': ('float32', 'Endian.LITTLE', None),
    'U32': ('uint32', None, 0.1),
    'U64': ('uint64', None, 0.0001),
}


def test_plenticore_profile_covers_every_kostalmodbus_register():
    generated = points('kostal.plenticore')
    table = dict(zip(Inverter.decRow, Inverter._Inverter__typeRow))

    assert sorted(generated) == sorted(table)
    for address, kind in table.items():
        attrs = generated[address]
        assert (attrs['modBusDataType'], attrs.get('modBusWordOrder')) == PLENTICORE_DATATYPES[kind], address
        assert 'modBusFactor' not in attrs


def test_ksem_profile_covers_every_ksemmodbus_register():
    generated = points('kostal.ksem')
    table = dict(zip(Ksem.decRow, Ksem._Ksem__typeRow))

    assert sorted(generated) == sorted(table)
    for address, kind in table.items():
        attrs = generated[address]
        datatype, word_order, factor = KSEM_DATATYPES[kind]
        assert attrs['modBusDataType'] == datatype, address
        assert attrs.get('modBusWordOrder') == word_order, address
        assert attrs.get('modBusFactor') == factor, address


def test_plenticore_struct_reads_the_inverter(tmp_path, modbus_server):
    server = modbus_server(
        KOSTAL_UNIT,
        {
            6: text('10544573', 8),
            100: words('>f', 1234.5, low_word_first=True),
            210: words('>f', 87.0, low_word_first=True),
            512: words('>I', 70000, low_word_first=True),
            575: words('>h', -150),
        },
    )

    rig = poll_once(tmp_path, server, 'pv:\n    kostal:\n        struct: modbus.kostal.plenticore\n')

    assert rig.item('pv.kostal.info.article_number')() == '10544573'
    assert rig.item('pv.kostal.power.dc_total')() == 1234.5
    assert rig.item('pv.kostal.battery.state_of_charge')() == 87.0
    assert rig.item('pv.kostal.battery.gross_capacity')() == 70000
    assert rig.item('pv.kostal.power.generation')() == -150


def test_ksem_struct_reads_the_meter(tmp_path, modbus_server):
    server = modbus_server(
        KOSTAL_UNIT, {0: words('>I', 12345), 24: words('>f', 0.5, low_word_first=True), 512: words('>Q', 987654321)}
    )

    rig = poll_once(tmp_path, server, 'meter:\n    ksem:\n        struct: modbus.kostal.ksem\n')

    assert rig.item('meter.ksem.power.active_plus')() == pytest.approx(1234.5)
    assert rig.item('meter.ksem.power.factor')() == 0.5
    assert rig.item('meter.ksem.energy.active_plus')() == pytest.approx(98765.4321)
