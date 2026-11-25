"""Polling a Kostal inverter served by a real loopback Modbus server."""

import struct

from tests.sdp_harness import load_plugin

ITEMS = """
kostal:
    dc_power:
        type: num
        kostal_100: ''
    generation_power:
        type: num
        kostal_575: ''
    article_number:
        type: str
        kostal_06: ''
"""


def float_registers(value: float) -> list[int]:
    """Registers of a float32 in Kostal's layout: big-endian bytes, low word first."""
    high, low = struct.unpack('>HH', struct.pack('>f', value))
    return [low, high]


def string_registers(text: str, count: int) -> list[int]:
    """Registers of an ASCII string, NUL padded to ``count`` registers."""
    raw = text.encode().ljust(count * 2, b'\0')
    return list(struct.unpack(f'>{count}H', raw))


def test_poll_device_updates_items(tmp_path, modbus_server):
    server = modbus_server(
        71, {100: float_registers(1234.5), 575: [(-150) & 0xFFFF], 6: string_registers('10544573', 8)}
    )
    rig = load_plugin(
        str(tmp_path),
        'plugins.kostalmodbus',
        'Kostalmodbus',
        ITEMS,
        params={'inverter_ip': server.host, 'modbus_port': server.port, 'update_cycle': 60},
    )

    rig.plugin.poll_device()

    assert rig.item('kostal.dc_power')() == 1234.5
    assert rig.item('kostal.generation_power')() == -150
    assert rig.item('kostal.article_number')() == '10544573'
