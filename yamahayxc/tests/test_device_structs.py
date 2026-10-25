"""The device structs expand to the items their devices need, with every zone's items under its own child."""

import pytest
from ruamel.yaml import YAML

from plugins.yamahayxc.tests.struct_expansion import PLUGIN_YAML, expanded_structs, item_paths

STRUCTS = expanded_structs()


def paths(device):
    return item_paths(STRUCTS[device])


@pytest.mark.parametrize('device', ['rx-v483', 'rx-s602d'])
def test_a_receiver_has_its_zone2_items_below_zone2(device):
    assert {'zone2.power', 'zone2.volume', 'zone2.mute', 'zone2.input', 'zone2.available'} <= paths(device)


@pytest.mark.parametrize('device', ['rx-v483', 'rx-s602d'])
def test_a_receiver_has_its_dsp_items_below_dsp(device):
    assert {'dsp.sound_program', 'dsp.direct', 'dsp.tone.bass', 'dsp.available'} <= paths(device)


@pytest.mark.parametrize('device', ['wx-010', 'isx-18d', 'isx-18', 'rx-v483', 'rx-s602d'])
def test_the_device_item_itself_stays_on_the_main_zone(device):
    assert STRUCTS[device]['yamahayxc_zone'] == 'main'
    assert 'struct' not in STRUCTS[device]


def test_the_deprecated_isx_18_has_the_items_of_isx_18d():
    assert paths('isx-18') == paths('isx-18d')


def test_the_rx_s602d_has_the_items_of_the_rx_v483():
    assert paths('rx-s602d') == paths('rx-v483')


def test_no_device_struct_is_built_on_another_device_struct():
    raw = YAML(typ='safe').load(PLUGIN_YAML.read_text())['item_structs']
    devices = {'wx-010', 'isx-18d', 'isx-18', 'rx-v483', 'rx-s602d'}

    for device in devices:
        references = raw[device]['struct']
        references = [references] if isinstance(references, str) else references
        assert not {reference.removeprefix('.') for reference in references} & devices
