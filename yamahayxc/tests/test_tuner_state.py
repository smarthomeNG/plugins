"""Tuner getPlayInfo responses reach the tuner items for each band."""

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin

MAIN_ZONE = {'id': 'main', 'func_list': ['power'], 'input_list': [], 'range_step': []}

FM_PLAY_INFO = {'band': 'fm', 'fm': {'preset': 0, 'freq': 87500, 'tuned': True}, 'rds': {'program_service': 'SWR3'}}

DAB_PLAY_INFO = {
    'band': 'dab',
    'fm': {'preset': 0, 'freq': 87500, 'tuned': False},
    'dab': {
        'preset': 5,
        'id': 10,
        'status': 'initial_scan',
        'service_label': 'Dlf             ',
        'ensemble_label': 'DR Deutschland  ',
        'dls': 'Nachrichten',
        'initial_scan_progress': 40,
        'total_station_num': 12,
    },
}


TUNER_FEATURES = {'func_list': ['fm', 'dab'], 'preset': {'type': 'separate', 'num': 30}}


def start(play_info, tuner_features=None):
    device = FakeDevice({'zone': [MAIN_ZONE], **({'tuner': tuner_features} if tuner_features else {})})
    device.responses = {'v1/tuner/getPlayInfo': play_info}
    plugin, sh = make_plugin('items_tuner.yaml', FakeNetwork({'127.0.0.1': device}))
    return plugin, sh, device


def item(sh, name):
    return sh.return_item('yamaha.dev.main.' + name)()


def test_station_on_fm_is_the_rds_program_service():
    plugin, sh, device = start(FM_PLAY_INFO)

    assert item(sh, 'tuner_station') == 'SWR3'


def test_station_on_dab_is_the_trimmed_service_label():
    plugin, sh, device = start(DAB_PLAY_INFO)

    assert item(sh, 'tuner_station') == 'Dlf'


def test_dab_ensemble_and_dls_are_pushed_trimmed():
    plugin, sh, device = start(DAB_PLAY_INFO)

    assert item(sh, 'tuner_ensemble') == 'DR Deutschland'
    assert item(sh, 'tuner_dls') == 'Nachrichten'


def test_dab_ensemble_and_dls_are_empty_on_fm():
    plugin, sh, device = start(FM_PLAY_INFO)

    assert item(sh, 'tuner_ensemble') == ''
    assert item(sh, 'tuner_dls') == ''


def test_current_preset_is_read_back_for_the_active_band():
    plugin, sh, device = start(DAB_PLAY_INFO)

    assert item(sh, 'tuner_preset') == 5


def test_preset_read_back_does_not_recall_the_preset():
    plugin, sh, device = start(DAB_PLAY_INFO)

    assert not [path for path in device.paths() if 'recallPreset' in path]


def test_preset_max_is_the_preset_count_the_device_reports():
    plugin, sh, device = start(DAB_PLAY_INFO, TUNER_FEATURES)

    assert item(sh, 'tuner_preset_max') == 30


def test_dab_scan_status_progress_and_station_count_are_pushed():
    plugin, sh, device = start(DAB_PLAY_INFO)

    assert item(sh, 'tuner_dab_status') == 'initial_scan'
    assert item(sh, 'tuner_dab_scan_progress') == 40
    assert item(sh, 'tuner_dab_station_count') == 12


def test_dab_scan_items_are_empty_on_fm():
    plugin, sh, device = start(FM_PLAY_INFO)

    assert item(sh, 'tuner_dab_status') == ''
    assert item(sh, 'tuner_dab_scan_progress') == 0
    assert item(sh, 'tuner_dab_station_count') == 0
