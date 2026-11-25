"""Polling a Kostal Smart Energy Meter served by a real loopback Modbus server."""

import struct

from tests.sdp_harness import load_plugin

ITEMS = """
ksem:
    active_power_plus:
        type: num
        ksem_0: ''
    power_factor:
        type: num
        ksem_24: ''
    active_energy_plus:
        type: num
        ksem_512: ''
"""


def float_registers(value: float) -> list[int]:
    """Registers of a float32: big-endian bytes, low word first."""
    high, low = struct.unpack('>HH', struct.pack('>f', value))
    return [low, high]


def uint_registers(value: int, count: int) -> list[int]:
    """Registers of an unsigned integer, high word first."""
    return list(struct.unpack(f'>{count}H', value.to_bytes(count * 2, 'big')))


def test_poll_device_updates_items(tmp_path, modbus_server):
    server = modbus_server(
        71, {0: uint_registers(12345, 2), 24: float_registers(0.5), 512: uint_registers(987654321, 4)}
    )
    rig = load_plugin(
        str(tmp_path),
        'plugins.ksemmodbus',
        'Ksemmodbus',
        ITEMS,
        params={'ksem_ip': server.host, 'modbus_port': server.port, 'update_cycle': 60},
    )

    rig.plugin.poll_device()

    assert rig.item('ksem.active_power_plus')() == 1234.5
    assert rig.item('ksem.power_factor')() == 0.5
    assert rig.item('ksem.active_energy_plus')() == 98765.43
