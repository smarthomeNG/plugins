"""A getFeatures answer without usable zone data (rejection, empty body) never replaces known capabilities."""

import pytest

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin

HOST = '127.0.0.1'
GOOD = {'zone': [{'id': 'main', 'func_list': ['volume'], 'input_list': ['hdmi1', 'hdmi2'], 'range_step': []}]}
UNUSABLE = [
    pytest.param({'response_code': 5}, id='guarded'),
    pytest.param({'response_code': 1}, id='initializing'),
    pytest.param({'response_code': 0}, id='no-zone-list'),
    pytest.param({'response_code': 0, 'zone': []}, id='empty-zone-list'),
]


def setup(first_features):
    device = FakeDevice(first_features)
    network = FakeNetwork({HOST: device})
    plugin, sh = make_plugin('test_items.yaml', network)
    return device, network, plugin, sh


@pytest.mark.parametrize('answer', UNUSABLE)
def test_unusable_answer_keeps_the_known_capabilities(answer):
    device, network, plugin, sh = setup(GOOD)
    input_sources = sh.return_item('yamaha.dev.main.input_sources')
    device.features = answer

    with network.active():
        plugin._update_features(HOST)

    assert list(input_sources()) == ['hdmi1', 'hdmi2']
    assert not plugin._zone_input_allowed(HOST, 'main', 'bogus')
    assert plugin._yamaha_features[HOST]['main']['input_list'] == {'hdmi1', 'hdmi2'}


@pytest.mark.parametrize('answer', UNUSABLE)
def test_unusable_first_answer_leaves_capabilities_unknown(answer):
    device, network, plugin, sh = setup(answer)

    assert HOST not in plugin._yamaha_features


def test_usable_answer_replaces_the_known_capabilities():
    device, network, plugin, sh = setup(GOOD)
    device.features = {'zone': [{'id': 'main', 'func_list': [], 'input_list': ['bluetooth'], 'range_step': []}]}

    with network.active():
        plugin._update_features(HOST)

    assert list(sh.return_item('yamaha.dev.main.input_sources')()) == ['bluetooth']


def get_features_calls(device):
    return [path for path in device.paths() if path.endswith('getFeatures')]


def test_poll_fetches_capabilities_missing_after_a_failed_startup():
    device, network, plugin, sh = setup({'response_code': 5})
    input_sources = sh.return_item('yamaha.dev.main.input_sources')
    assert HOST not in plugin._yamaha_features
    device.features = GOOD

    with network.active():
        plugin.poll_device()

    assert list(input_sources()) == ['hdmi1', 'hdmi2']
    assert HOST in plugin._yamaha_features


def test_poll_keeps_asking_until_the_device_answers_usably():
    device, network, plugin, sh = setup({'response_code': 5})

    with network.active():
        plugin.poll_device()
        assert HOST not in plugin._yamaha_features
        device.features = GOOD
        plugin.poll_device()

    assert HOST in plugin._yamaha_features


def test_poll_does_not_refetch_known_capabilities():
    device, network, plugin, sh = setup(GOOD)
    device.calls.clear()

    with network.active():
        plugin.poll_device()

    assert get_features_calls(device) == []


def test_poll_fetches_missing_capabilities_of_hosts_without_reachable_item():
    device = FakeDevice({'response_code': 5})
    network = FakeNetwork({'127.0.0.1': device, '127.0.0.2': FakeDevice(GOOD)})
    plugin, sh = make_plugin('items_two_hosts.yaml', network)
    device.features = GOOD

    with network.active():
        plugin.poll_device()

    assert HOST in plugin._yamaha_features


def test_poll_does_not_ask_a_host_flagged_unreachable():
    device, network, plugin, sh = setup({'response_code': 5})
    device.up = False

    with network.active():
        plugin.poll_device()
        plugin.poll_device()  # second failure flags the host unreachable
        device.calls.clear()
        plugin.poll_device()

    assert get_features_calls(device) == []
