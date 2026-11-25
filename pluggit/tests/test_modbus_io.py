"""Reading and writing a Pluggit AP310 served by a real loopback Modbus server."""

import struct

from tests.sdp_harness import load_plugin

ITEMS = """
pluggit:
    outdoor_temperature:
        type: num
        pluggit_read: prmRamIdxT1
    humidity:
        type: num
        pluggit_read: prmRamIdxRh3Corrected
    speed_level:
        type: num
        pluggit_read: prmRomIdxSpeedLevel
        pluggit_write: prmRomIdxSpeedLevel
"""


def float_registers(value: float) -> list[int]:
    """Registers of a float32 in Pluggit's layout: big-endian bytes, low word first."""
    high, low = struct.unpack('>HH', struct.pack('>f', value))
    return [low, high]


def load(tmp_path, server):
    return load_plugin(
        str(tmp_path),
        'plugins.pluggit',
        'Pluggit',
        ITEMS,
        params={'host': server.host, 'port': server.port, 'cycle': 60},
    )


def test_refresh_updates_items(tmp_path, modbus_server):
    server = modbus_server(1, {132: float_registers(12.34), 196: [55], 324: [2]})
    rig = load(tmp_path, server)

    rig.plugin._refresh()

    assert rig.item('pluggit.outdoor_temperature')() == 12.34
    assert rig.item('pluggit.humidity')() == 55
    assert rig.item('pluggit.speed_level')() == 2


def test_writing_speed_level_switches_to_manual_mode(tmp_path, modbus_server):
    server = modbus_server(1, {})
    rig = load(tmp_path, server)

    rig.item('pluggit.speed_level')(3, 'test')

    assert server.holding(168) == [0x0004]
    assert server.holding(324) == [3]
