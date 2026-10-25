"""plugin.yaml (item structs) and the plugin's command table agree with each other."""

import pathlib
import re

from ruamel.yaml import YAML

from plugins.yamahayxc.tests.harness import FakeNetwork, make_plugin

PLUGIN_YAML = pathlib.Path(__file__).parent.parent / 'plugin.yaml'
YAML_LOADER = YAML(typ='safe')


def struct_items(node, path=''):
    """Yield (path, item_dict) for every dict in an item struct tree that looks like an item."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, dict):
                yield f'{path}.{key}', value
                yield from struct_items(value, f'{path}.{key}')


def load_struct_items():
    meta = YAML_LOADER.load(PLUGIN_YAML.read_text())
    return list(struct_items(meta['item_structs']))


def test_every_struct_cmd_is_a_known_cmd():
    plugin, sh = make_plugin('test_items.yaml', FakeNetwork({}), initialize=False)

    unknown = {
        path: item['yamahayxc_cmd']
        for path, item in load_struct_items()
        if 'yamahayxc_cmd' in item and item['yamahayxc_cmd'].lower() not in plugin._yamaha_cmds
    }

    assert unknown == {}


def test_every_known_cmd_is_used_by_a_struct():
    plugin, sh = make_plugin('test_items.yaml', FakeNetwork({}), initialize=False)

    used = {item['yamahayxc_cmd'].lower() for _, item in load_struct_items() if 'yamahayxc_cmd' in item}

    assert sorted(set(plugin._yamaha_cmds) - used) == []


def test_available_items_are_wired_to_the_plugin():
    available = [(path, item) for path, item in load_struct_items() if path.endswith('.available')]

    assert available
    assert [
        path for path, item in available if item.get('yamahayxc_cmd') not in ('zone_present', 'dsp_available')
    ] == []


def test_every_widget_catalog_model_is_a_device_struct():
    catalog = (pathlib.Path(__file__).parent.parent / 'sv_widgets' / 'yxc_devices.html').read_text()
    models = re.findall(r"^\s*'([a-z0-9-]+)':\s*'[a-z0-9,]*',?$", catalog, re.MULTILINE)
    structs = YAML_LOADER.load(PLUGIN_YAML.read_text())['item_structs']

    assert models
    assert [model for model in models if model not in structs] == []


def test_deprecated_isx_18_struct_still_exists_as_an_alias_of_isx_18d():
    structs = YAML_LOADER.load(PLUGIN_YAML.read_text())['item_structs']

    assert structs['isx-18']['struct'] == '.isx-18d'
    assert 'Veraltet' in structs['isx-18']['remark']
