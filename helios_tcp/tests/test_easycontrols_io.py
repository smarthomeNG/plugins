"""Reading and writing Helios EasyControls variables over a real loopback Modbus server."""

from pymodbus.datastore import ModbusSequentialDataBlock

from tests.sdp_harness import load_plugin

from plugins.helios_tcp import HeliosTCP

ITEMS = """
helios:
    outside_temp:
        type: num
        helios_tcp: outside_temp
    fan_level:
        type: num
        helios_tcp: fan_level
"""


def to_text(registers: list[int]) -> str:
    """ASCII text held in ``registers``, two characters per register, up to the first NUL."""
    raw = b''.join(reg.to_bytes(2, 'big') for reg in registers)
    return raw.split(b'\0', 1)[0].decode('ascii')


def to_registers(text: str, count: int) -> list[int]:
    """``text`` as ``count`` registers, two ASCII characters each, NUL padded."""
    raw = text.encode('ascii').ljust(count * 2, b'\0')
    return [int.from_bytes(raw[i : i + 2], 'big') for i in range(0, count * 2, 2)]


class EasyControls(ModbusSequentialDataBlock):
    """
    Holding registers of an EasyControls device.

    Writing ``vNNNNN`` from register 1 selects a variable, whose ``vNNNNN=value`` is read back
    from register 1. Writing ``vNNNNN=value`` sets the variable.
    """

    def __init__(self, variables: dict[str, str]):
        super().__init__(0, [0] * 64)
        self.variables = variables
        self.written: list[str] = []

    def setValues(self, address, values):
        text = to_text(list(values))
        self.written.append(text)
        name, _, value = text.partition('=')
        if value:
            self.variables[name] = value
        super().setValues(address, to_registers(f'{name}={self.variables.get(name, "")}', 20))


def test_update_values_reads_variables(tmp_path, modbus_server, monkeypatch):
    device = EasyControls({'v00104': '12.3', 'v00102': '2'})
    server = modbus_server(HeliosTCP.MODBUS_SLAVE, {}, block=device)
    monkeypatch.setattr(HeliosTCP, 'PORT', server.port)
    rig = load_plugin(str(tmp_path), 'plugins.helios_tcp', 'HeliosTCP', ITEMS, params={'helios_ip': server.host})

    rig.plugin.run()
    try:
        rig.plugin._update_values()
    finally:
        rig.plugin.stop()

    assert rig.item('helios.outside_temp')() == 12.3
    assert rig.item('helios.fan_level')() == 2


def test_writing_item_sets_variable(tmp_path, modbus_server, monkeypatch):
    device = EasyControls({'v00102': '1'})
    server = modbus_server(HeliosTCP.MODBUS_SLAVE, {}, block=device)
    monkeypatch.setattr(HeliosTCP, 'PORT', server.port)
    rig = load_plugin(str(tmp_path), 'plugins.helios_tcp', 'HeliosTCP', ITEMS, params={'helios_ip': server.host})

    rig.plugin.run()
    try:
        rig.item('helios.fan_level')(3, 'test')
    finally:
        rig.plugin.stop()

    assert 'v00102=3' in device.written
    assert device.variables['v00102'] == '3'
