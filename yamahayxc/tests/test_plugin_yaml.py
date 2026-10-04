"""plugin.yaml (item structs) and the plugin's command table agree with each other."""

import pathlib

import yaml

from plugins.yamahayxc.tests.harness import FakeNetwork, make_plugin

PLUGIN_YAML = pathlib.Path(__file__).parent.parent / 'plugin.yaml'


def struct_items(node, path=''):
    """Yield (path, item_dict) for every dict in an item struct tree that looks like an item."""
    if isinstance(node, dict):
        for key, value in node.items():
            if isinstance(value, dict):
                yield f'{path}.{key}', value
                yield from struct_items(value, f'{path}.{key}')


def load_struct_items():
    meta = yaml.safe_load(PLUGIN_YAML.read_text())
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
