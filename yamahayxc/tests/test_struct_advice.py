"""recommend(): which yamahayxc structs fit a device, derived from its getFeatures."""

from plugins.yamahayxc.structadvice import ready_made, recommend, render_config
from plugins.yamahayxc.tests.features_samples import ISX_18D, RX_S602D, RX_V483, WX_010


def test_a_streaming_speaker_gets_amp_link_and_netusb():
    advice = recommend(WX_010)

    assert advice.structs == ('amp', 'link', 'netusb')
    assert advice.widget_features == ('netusb', 'link')


def test_a_device_with_a_tuner_and_an_alarm_clock_gets_tuner_and_alarm():
    advice = recommend(ISX_18D)

    assert advice.structs == ('amp', 'link', 'netusb', 'tuner', 'alarm')
    assert advice.widget_features == ('netusb', 'link', 'tuner')


def test_a_receiver_gets_dsp_and_its_extra_zones():
    advice = recommend(RX_V483)

    assert advice.structs == ('amp', 'link', 'netusb', 'tuner', 'dsp', 'zone2')
    assert advice.widget_features == ('dsp', 'netusb', 'link', 'tuner', 'zone2')


def test_receivers_with_the_same_building_blocks_get_the_same_advice():
    assert recommend(RX_S602D) == recommend(RX_V483)


def test_a_model_with_a_ready_made_struct_is_matched_by_its_lowercased_name():
    known = {'isx-18d', 'rx-v483', 'wx-010'}

    assert ready_made('ISX-18D', known) == 'isx-18d'
    assert ready_made('RX-S602', known) is None
    assert ready_made('', known) is None


def test_the_item_config_uses_the_ready_made_struct_when_there_is_one():
    config = render_config('192.168.2.5', recommend(ISX_18D), 'isx-18d')

    assert config == 'device:\n    yamahayxc_host: 192.168.2.5\n    struct: yamahayxc.isx-18d\n'


def test_the_item_config_lists_the_recommended_structs_otherwise():
    config = render_config('rx-av', recommend(RX_V483), None)

    assert config == (
        'device:\n'
        '    yamahayxc_host: rx-av\n'
        '    struct: [yamahayxc.amp, yamahayxc.link, yamahayxc.netusb, yamahayxc.tuner, yamahayxc.dsp]\n'
        '    zone2:\n'
        '        struct: yamahayxc.zone2\n'
    )
