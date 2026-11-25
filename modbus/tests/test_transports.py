"""The plugin reads over each transport: TCP, RTU over TCP, and RTU on a serial port."""

import pytest

from tests.sdp_harness import PluginNotLoaded, load_plugin

from plugins.modbus.tests.test_async_io import wait_until

ITEMS = """
dev:
    value:
        type: num
        modBusAddress: 10
        modBusDataType: int32
"""


def read_once(tmp_path, params: dict):
    rig = load_plugin(str(tmp_path), 'plugins.modbus', 'Modbus', ITEMS, params={'cycle': 60, 'slaveUnit': 3, **params})
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        rig.job(plugin._scheduler_name()).fire()
        wait_until(lambda: rig.item('dev.value')() == -70000)
    finally:
        plugin.stop()
    return rig


@pytest.mark.parametrize(
    'rtu,params',
    [
        (False, lambda port: {'host': '127.0.0.1', 'port': port}),
        (False, lambda port: {'transport': 'tcp', 'host': '127.0.0.1', 'port': port}),
        (True, lambda port: {'transport': 'rtu_over_tcp', 'host': '127.0.0.1', 'port': port}),
        (True, lambda port: {'transport': 'rtu', 'serialport': f'socket://127.0.0.1:{port}', 'baudrate': 9600}),
    ],
    ids=['default', 'tcp', 'rtu_over_tcp', 'rtu_serial'],
)
def test_reads_over_transport(tmp_path, modbus_server, rtu, params):
    server = modbus_server(3, {10: [0xFFFE, 0xEE90]}, rtu=rtu)

    read_once(tmp_path, params(server.port))


@pytest.mark.parametrize(
    'params,message',
    [
        ({'transport': 'tcp'}, 'host'),
        ({'transport': 'rtu_over_tcp', 'port': 502}, 'host'),
        ({'transport': 'rtu'}, 'serialport'),
    ],
)
def test_missing_connection_parameters_stop_the_plugin_from_loading(tmp_path, params, message):
    with pytest.raises(PluginNotLoaded) as failure:
        load_plugin(str(tmp_path), 'plugins.modbus', 'Modbus', ITEMS, params={'cycle': 60, **params})

    assert any(message in x for x in failure.value.logs.messages())
