"""``modBusBit`` reads one bit of a register, ``modBusLookup`` maps device values to item values and back."""

import pytest

from plugins.modbus.tests.test_async_io import Simulator, rig_for, wait_until


@pytest.fixture
def simulator():
    server = Simulator()
    try:
        yield server
    finally:
        server.close()


@pytest.fixture
def running(tmp_path, simulator):
    rigs = []

    def start(items: str):
        rig = rig_for(tmp_path, simulator, items=items)
        rigs.append(rig)
        rig.plugin.run()
        wait_until(lambda: rig.plugin.connected)
        return rig

    yield start
    for rig in rigs:
        rig.plugin.stop()


def poll(plugin) -> None:
    plugin._trigger_async_read()
    wait_until(lambda: plugin._scheduled_read_task is not None and plugin._scheduled_read_task.done())


def test_bits_of_one_register_become_bool_items(simulator, running):
    simulator.registers[20] = 0b1000_0000_0001_0010
    rig = running(
        """
dev:
    flags:
        type: num
        modBusAddress: 20
        b1:
            type: bool
            modBusAddress: 20
            modBusBit: 1
        b2:
            type: bool
            initial_value: true
            modBusAddress: 20
            modBusBit: 2
        b15:
            type: bool
            modBusAddress: 20
            modBusBit: 15
"""
    )
    poll(rig.plugin)

    assert rig.item('dev.flags')() == 0b1000_0000_0001_0010
    assert rig.item('dev.flags.b1')() is True
    assert rig.item('dev.flags.b2')() is False
    assert rig.item('dev.flags.b15')() is True


def test_bit_out_of_range_is_ignored_with_a_warning(running):
    rig = running(
        """
dev:
    bad:
        type: bool
        modBusAddress: 20
        modBusBit: 16
"""
    )

    assert any('dev.bad' in m and 'modBusBit' in m for m in rig.logs.messages())
    assert 'dev.bad' not in {str(item) for item in rig.plugin._regToRead}


LOOKUP_ITEMS = """
dev:
    state:
        type: str
        modBusAddress: 30
        modBusDirection: read_write
        modBusLookup: "{0: 'Standby', 1: 'Manual', 3: 'Week program'}"
"""


def test_lookup_maps_device_values_to_item_values(simulator, running):
    simulator.registers[30] = 3
    rig = running(LOOKUP_ITEMS)
    poll(rig.plugin)
    assert rig.item('dev.state')() == 'Week program'

    simulator.registers[30] = 7
    poll(rig.plugin)
    assert rig.item('dev.state')() == '7'


def test_lookup_writes_the_device_value_of_an_item_value(simulator, running):
    rig = running(LOOKUP_ITEMS)

    rig.item('dev.state')('Manual', 'test')
    wait_until(lambda: simulator.registers.get(30) == 1)

    rig.item('dev.state')('Unknown', 'test')
    wait_until(lambda: any('Unknown' in m for m in rig.logs.messages()))
    assert simulator.registers.get(30) == 1


def test_malformed_lookup_is_ignored_with_a_warning(running):
    rig = running(
        """
dev:
    bad:
        type: str
        modBusAddress: 30
        modBusLookup: "0: Standby"
"""
    )

    assert any('dev.bad' in m and 'modBusLookup' in m for m in rig.logs.messages())
    assert 'dev.bad' not in {str(item) for item in rig.plugin._regToRead}


def test_single_bits_are_not_written_without_an_adapter(simulator, running):
    simulator.registers[20] = 0
    rig = running(
        """
dev:
    b1:
        type: bool
        modBusAddress: 20
        modBusBit: 1
        modBusDirection: read_write
"""
    )

    rig.item('dev.b1')(True, 'test')

    wait_until(lambda: any('single bits' in m for m in rig.logs.messages()))
    assert simulator.registers[20] == 0


def test_round_keeps_the_given_decimals(simulator, running):
    simulator.registers.update({40: 0x41BB, 41: 0x4396, 42: 0x449A, 43: 0x5225})  # 23.40800, 1234.567
    rig = running(
        """
dev:
    temp:
        type: num
        modBusAddress: 40
        modBusDataType: float32
        modBusRound: 1
    rpm:
        type: num
        modBusAddress: 42
        modBusDataType: float32
        modBusRound: 0
"""
    )
    poll(rig.plugin)

    assert rig.item('dev.temp')() == 23.4
    assert rig.item('dev.rpm')() == 1235


def test_round_on_a_str_item_gives_exactly_the_given_decimals(simulator, running):
    simulator.registers.update({50: 210, 51: 3})
    rig = running(
        """
dev:
    firmware:
        type: str
        modBusAddress: 50
        modBusFactor: 0.01
        modBusRound: 2
    hardware:
        type: str
        modBusAddress: 51
        modBusRound: 2
"""
    )
    poll(rig.plugin)

    assert rig.item('dev.firmware')() == '2.10'
    assert rig.item('dev.hardware')() == '3.00'


def test_lookup_applies_to_coils(simulator, running):
    simulator.coils.update({5: True})
    rig = running(
        """
dev:
    mode:
        type: str
        modBusObjectType: Coil
        modBusAddress: 5
        modBusLookup: "{False: 'ferngesteuert', True: 'autark'}"
"""
    )
    poll(rig.plugin)

    assert rig.item('dev.mode')() == 'autark'
