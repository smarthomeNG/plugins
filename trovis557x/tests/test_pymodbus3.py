import unittest
from types import SimpleNamespace

from pymodbus.client import ModbusSerialClient

from plugins.trovis557x import trovis557x


class _Client:
    """Modbus client with the keyword-only signatures of pymodbus 3.9."""

    def __init__(self):
        self.calls = []

    def read_holding_registers(self, address, *, count=1, slave=1):
        self.calls.append(('register', address, count, slave))
        return SimpleNamespace(registers=list(range(count)))

    def read_coils(self, address, *, count=1, slave=1):
        self.calls.append(('coil', address, count, slave))
        return SimpleNamespace(bits=[True] * 8)


def make_plugin(**attributes):
    plugin = trovis557x.__new__(trovis557x)
    plugin.logger = SimpleNamespace(debug=lambda *a: None, info=lambda *a: None)
    plugin.getKeyFromID = lambda id, typ: 'x'
    plugin.__dict__.update(attributes)
    return plugin


class TestPymodbus3(unittest.TestCase):
    def test_registers_are_read_with_keyword_arguments(self):
        client = _Client()
        plugin = make_plugin(_modbus=client, _modbus_trovis_address=247)

        values = plugin.leseTrovis([100, 102], 'register')

        self.assertEqual([('register', 100, 3, 247)], client.calls)
        self.assertEqual([[100, 0], [101, 1], [102, 2]], values)

    def test_coils_are_read_with_keyword_arguments(self):
        client = _Client()
        plugin = make_plugin(_modbus=client, _modbus_trovis_address=247)

        values = plugin.leseTrovis([10, 11], 'coil')

        self.assertEqual([('coil', 10, 2, 247)], client.calls)
        self.assertEqual([[10, 1], [11, 1]], values)

    def test_serial_client_is_created(self):
        plugin = make_plugin(
            _modbus_mode='rtu', _modbus_port='/dev/shng-test-missing', _modbus_timeout=1, _modbus_speed=19200
        )

        self.assertIsInstance(plugin.connect_trovis(), ModbusSerialClient)
