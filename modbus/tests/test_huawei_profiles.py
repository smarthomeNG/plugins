"""The huawei profiles generate the structs modbus_tcp ships by hand, except for renamed nodes."""

import pathlib

from ruamel.yaml import YAML

from plugins.modbus import attributes, profiles

PLUGINS = pathlib.Path(profiles.__file__).parent.parent
RENAMED = {('meter', 'type'): 'meter_type'}


def normalized(node: dict) -> dict:
    """Children recursively, register attributes as the parsed spec, other attributes as text; no ``remark``."""
    result: dict = {}
    register = {key.removesuffix('@instance'): value for key, value in node.items() if key.startswith('modBus')}
    if register:
        result['spec'] = attributes.parse_spec(register.get, 1, lambda message: None)
    for key, value in node.items():
        if isinstance(value, dict):
            result[key] = normalized(value)
        elif not key.startswith('modBus') and key != 'remark':
            result[key] = str(value)
    return result


def test_generated_huawei_structs_equal_the_modbus_tcp_ones():
    original = YAML(typ='safe').load((PLUGINS / 'modbus_tcp' / 'plugin.yaml').read_text())['item_structs']['huawei']
    huawei = [p for p in profiles.load_all() if p.vendor == 'huawei']
    generated = profiles.vendor_trees(huawei)['huawei']

    for (device, old), new in RENAMED.items():
        original[device][new] = original[device].pop(old)
    assert sorted(generated) == sorted(original)
    for device in original:
        assert normalized(generated[device]) == normalized(original[device]), device
