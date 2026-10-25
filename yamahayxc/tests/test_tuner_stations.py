"""tuner_stations lists the presets of the current band, with names where the device or the DAB cache has them."""

import json

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin

MAIN_ZONE = {'id': 'main', 'func_list': ['power'], 'input_list': [], 'range_step': []}

FM_PLAY_INFO = {'band': 'fm', 'fm': {'preset': 0, 'freq': 87500, 'tuned': True}}
DAB_PLAY_INFO = {
    'band': 'dab',
    'dab': {'preset': 0, 'id': 7, 'service_label': 'Dlf', 'status': 'ready', 'total_station_num': 102},
}


def preset(band, number, text=''):
    return {'band': band, 'number': number, 'hd_program': 0, 'text': text}


UNUSED = preset('unknown', 0)


def start(play_info, presets, preset_type='separate', band=None):
    device = FakeDevice(
        {'zone': [MAIN_ZONE], 'tuner': {'func_list': ['fm', 'dab'], 'preset': {'type': preset_type, 'num': 30}}}
    )
    device.responses = {
        'v1/tuner/getPlayInfo': play_info,
        f'v1/tuner/getPresetInfo?band={band or play_info["band"]}': {'preset_info': presets},
    }
    plugin, sh = make_plugin('items_tuner.yaml', FakeNetwork({'127.0.0.1': device}))
    return plugin, sh, device


def stations(sh):
    return sh.return_item('yamaha.dev.main.tuner_stations')()


def test_fm_presets_are_listed_with_their_frequency_and_slot():
    plugin, sh, device = start(FM_PLAY_INFO, [preset('fm', 88000), UNUSED, preset('fm', 90700)])

    assert stations(sh) == [
        {'slot': 1, 'band': 'fm', 'number': 88000, 'name': ''},
        {'slot': 3, 'band': 'fm', 'number': 90700, 'name': ''},
    ]


def test_dab_preset_name_comes_from_the_device_text_when_it_has_one():
    plugin, sh, device = start(DAB_PLAY_INFO, [preset('dab', 7, 'Dlf  '), UNUSED])

    assert stations(sh) == [{'slot': 1, 'band': 'dab', 'number': 7, 'name': 'Dlf'}]


def test_dab_preset_without_device_text_is_named_from_the_services_seen_on_the_tuner():
    plugin, sh, device = start(DAB_PLAY_INFO, [preset('dab', 7), preset('dab', 8)])

    assert stations(sh) == [
        {'slot': 1, 'band': 'dab', 'number': 7, 'name': 'Dlf'},
        {'slot': 2, 'band': 'dab', 'number': 8, 'name': ''},
    ]


def test_a_band_change_lists_the_presets_of_the_new_band():
    plugin, sh, device = start(FM_PLAY_INFO, [preset('fm', 88000)])
    device.responses['v1/tuner/getPlayInfo'] = DAB_PLAY_INFO
    device.responses['v1/tuner/getPresetInfo?band=dab'] = {'preset_info': [preset('dab', 7, 'Dlf')]}

    with FakeNetwork({'127.0.0.1': device}).active():
        plugin._update_tuner_state('127.0.0.1')

    assert stations(sh) == [{'slot': 1, 'band': 'dab', 'number': 7, 'name': 'Dlf'}]


def test_a_device_with_one_preset_list_for_all_bands_is_asked_for_the_common_list():
    plugin, sh, device = start(
        FM_PLAY_INFO, [preset('fm', 88000), preset('am', 531)], preset_type='common', band='common'
    )

    assert stations(sh) == [
        {'slot': 1, 'band': 'fm', 'number': 88000, 'name': ''},
        {'slot': 2, 'band': 'am', 'number': 531, 'name': ''},
    ]


def test_a_preset_info_push_relists_the_presets():
    plugin, sh, device = start(FM_PLAY_INFO, [preset('fm', 88000)])
    device.responses['v1/tuner/getPresetInfo?band=fm'] = {'preset_info': [preset('fm', 88000), preset('fm', 90700)]}
    network = FakeNetwork({'127.0.0.1': device})

    with network.active():
        plugin._process_notification(('127.0.0.1', 41100), json.dumps({'tuner': {'preset_info_updated': True}}))

    assert [entry['number'] for entry in stations(sh)] == [88000, 90700]
