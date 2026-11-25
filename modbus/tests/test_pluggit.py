"""Pluggit air handlers: device datatypes and the ``adapter: pluggit`` unit mode logic, over real Modbus TCP."""

import pytest
from pymodbus.datastore import ModbusSequentialDataBlock

from plugins.modbus.codec import default_registry
from plugins.modbus.model import RegisterKey, RegisterSpec, Table
from plugins.modbus.tests.test_async_io import wait_until
from tests.sdp_harness import load_plugin

UNIT_MODE = 168
SPEED_LEVEL = 324


def decode(datatype, registers):
    spec = RegisterSpec(RegisterKey(1, Table.HOLDING_REGISTER, 0), datatype=datatype)
    return default_registry().resolve(datatype).decode(registers, spec)


@pytest.mark.parametrize(
    'datatype,registers,expected',
    [
        ('pluggit_mac', [0x0011, 0x9999, 0x4455, 0x2233], '00:11:22:33:44:55'),
        ('pluggit_version', [0x0213], '2.19'),
        ('pluggit_version_bcd', [0x1234], '1.23'),
    ],
)
def test_device_datatypes(datatype, registers, expected):
    assert default_registry().resolve(datatype).register_count(datatype) == len(registers)
    assert decode(datatype, registers) == expected


class RecordingBlock(ModbusSequentialDataBlock):
    """Holding registers that remember every write as (0-based address, values)."""

    def __init__(self):
        super().__init__(1, [0] * 1000)
        self.writes = []

    def setValues(self, address, values):  # noqa: N802 - pymodbus API
        self.writes.append((address - 1, list(values)))
        super().setValues(address, values)


ITEMS = """
kwl:
    unit_mode:
        type: num
        modBusAddress: 168
        modBusDataType: uint32
        modBusWordOrder: Endian.LITTLE
        modBusDirection: read_write
        away:
            type: bool
            modBusAddress: 168
            modBusBit: 4
            modBusDirection: read_write
        demand:
            type: bool
            modBusAddress: 168
            modBusBit: 1
            modBusDirection: read_write
    speed:
        type: num
        modBusAddress: 324
        modBusDataType: uint32
        modBusWordOrder: Endian.LITTLE
        modBusDirection: read_write
"""


@pytest.fixture
def pluggit(tmp_path, modbus_server):
    rigs = []

    def start(adapter='pluggit'):
        block = RecordingBlock()
        server = modbus_server(1, {}, block=block)
        params = {'host': server.host, 'port': server.port, 'cycle': 60, 'slaveUnit': 1, 'adapter': adapter}
        rig = load_plugin(str(tmp_path), 'plugins.modbus', 'Modbus', ITEMS, params=params)
        rig.block = block
        rigs.append(rig)
        rig.plugin.run()
        wait_until(lambda: rig.plugin.connected)
        return rig

    yield start
    for rig in rigs:
        rig.plugin.stop()


def test_mode_switches_write_their_on_and_off_commands(pluggit):
    rig = pluggit()

    rig.item('kwl.unit_mode.away')(True, 'test')
    wait_until(lambda: rig.block.writes == [(UNIT_MODE, [0x0010])])
    rig.item('kwl.unit_mode.away')(False, 'test')
    wait_until(lambda: rig.block.writes[-1:] == [(UNIT_MODE, [0x8010])])


def test_modes_without_off_command_are_not_written(pluggit):
    rig = pluggit()

    rig.item('kwl.unit_mode.demand')(True, 'test')
    wait_until(lambda: rig.block.writes == [(UNIT_MODE, [0x0002])])
    rig.item('kwl.unit_mode.demand')(False, 'test')

    wait_until(lambda: any('cannot be switched off' in m for m in rig.logs.messages()))
    assert rig.block.writes == [(UNIT_MODE, [0x0002])]


def test_speed_level_switches_to_manual_mode_first(pluggit):
    rig = pluggit()

    rig.item('kwl.speed')(3, 'test')

    wait_until(lambda: len(rig.block.writes) == 2)
    assert rig.block.writes == [(UNIT_MODE, [0x0004]), (SPEED_LEVEL, [3, 0])]


def test_the_raw_unit_mode_is_written_as_is(pluggit):
    rig = pluggit()

    rig.item('kwl.unit_mode')(0x0008, 'test')

    wait_until(lambda: rig.block.writes == [(UNIT_MODE, [0x0008, 0])])


def test_without_adapter_the_speed_level_is_written_alone(pluggit):
    rig = pluggit(adapter='')

    rig.item('kwl.speed')(2, 'test')

    wait_until(lambda: rig.block.writes == [(SPEED_LEVEL, [2, 0])])


def test_unknown_adapters_are_rejected():
    from plugins.modbus import adapter

    with pytest.raises(ValueError, match="unknown adapter 'nope', known: pluggit"):
        adapter.create('nope')
