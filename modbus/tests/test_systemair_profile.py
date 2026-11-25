"""The systemair profile covers systemair.yaml and works over serial RTU."""

import pathlib

from ruamel.yaml import YAML

from plugins.modbus import profiles
from plugins.modbus.tests.profile_rig import expand_structs, words
from plugins.modbus.tests.test_async_io import wait_until
from tests.sdp_harness import load_plugin

SYSTEMAIR_YAML = pathlib.Path(profiles.__file__).parent.parent / 'systemair' / 'systemair.yaml'


def generated() -> dict:
    profile = next(p for p in profiles.load_all() if p.id == 'systemair.residential')
    return profiles.to_struct(profile)


def test_profile_matches_systemair_yaml():
    original = YAML(typ='safe').load(SYSTEMAIR_YAML.read_text())['kwl']
    struct = generated()

    assert sorted(struct) == sorted(original)
    for name, conf in original.items():
        item = {key.removesuffix('@instance'): value for key, value in struct[name].items()}
        if 'systemair_regaddr' in conf:
            register = int(conf['systemair_regaddr'])
            assert item['modBusAddress'] == register - 1, name
            assert 'modBusObjectType' not in item, name
            if 208 <= register <= 218:
                assert (item['modBusDataType'], item['modBusFactor']) == ('int16', 0.1), name
            else:
                assert (item['modBusDataType'], item.get('modBusFactor')) == ('uint16', None), name
        else:
            assert item['modBusAddress'] == int(conf['systemair_coiladdr']) - 1, name
            assert item['modBusObjectType'] == 'DiscreteInput', name
        writable = str(conf.get('mod_write', 'false')).lower() == 'true'
        assert item['modBusDirection'] == ('read_write' if writable else 'read'), name
        assert item.get('eval') == conf.get('eval'), name


def test_struct_reads_and_writes_over_serial_rtu(tmp_path, modbus_server):
    server = modbus_server(1, {100: [2], 207: words('>h', -55)}, rtu=True)
    rig = load_plugin(
        str(tmp_path),
        'plugins.modbus',
        'Modbus',
        expand_structs('kwl:\n    struct: modbus.systemair.residential\n', tmp_path),
        params={'transport': 'rtu', 'serialport': f'socket://127.0.0.1:{server.port}', 'cycle': 60},
    )
    plugin = rig.plugin
    try:
        plugin.run()
        wait_until(lambda: plugin.connected)
        rig.job(plugin._scheduler_name()).fire()
        wait_until(lambda: plugin._scheduled_read_task is not None and plugin._scheduled_read_task.done(), timeout=30)

        assert rig.item('kwl.Lueftergeschwindigkeit')() == 2
        assert rig.item('kwl.Isttemperatur_Heizregister')() == -5.5

        rig.item('kwl.Lueftergeschwindigkeit')(3, 'test')
        wait_until(lambda: server.holding(100) == [3])
    finally:
        plugin.stop()
