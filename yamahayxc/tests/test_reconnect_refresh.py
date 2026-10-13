"""
Regression test: input_sources (and other getFeatures-derived capability
lists) must be re-read after a device comes back online, not left stale
from the last successful read (or empty, if the device was down at
plugin startup).
"""

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin


def features(input_sources):
    return {'zone': [{'id': 'main', 'func_list': [], 'input_list': input_sources, 'range_step': []}]}


def test_reconnect_refreshes_input_sources():
    device = FakeDevice(features(['hdmi1', 'hdmi2']))
    network = FakeNetwork({'127.0.0.1': device})
    plugin, sh = make_plugin('test_items.yaml', network)
    plugin.alive = True

    input_sources_item = sh.return_item('yamaha.dev.main.input_sources')
    reachable_item = sh.return_item('yamaha.dev.reachable')

    assert list(input_sources_item()) == sorted(['hdmi1', 'hdmi2'])
    assert reachable_item() is True

    device.up = False
    with network.active():
        plugin.poll_device()
        plugin.poll_device()  # 2 consecutive failures -> flips to unreachable

    assert reachable_item() is False

    # device comes back online with a changed input list, e.g. a newly
    # detected HDMI source
    device.features = features(['hdmi1', 'hdmi2', 'bluetooth'])
    device.up = True
    with network.active():
        plugin.poll_device()

    assert reachable_item() is True
    assert list(input_sources_item()) == sorted(['hdmi1', 'hdmi2', 'bluetooth'])
