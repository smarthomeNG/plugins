"""Outgoing request handling: GET for string payloads, POST for [url, data] payloads, nothing for garbage."""

import json

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin


def make_running_plugin():
    device = FakeDevice()
    network = FakeNetwork({'127.0.0.1': device})
    plugin, sh = make_plugin('items_payload.yaml', network)
    plugin.alive = True
    device.calls.clear()
    return plugin, sh, device, network


def write(plugin, sh, network, path, value):
    item = sh.return_item(path)
    item(value, 'test')
    with network.active():
        plugin.update_item(item, 'test')


def test_string_passthru_is_sent_as_get():
    plugin, sh, device, network = make_running_plugin()

    write(plugin, sh, network, 'yamaha.dev.main.passthru', 'v1/main/setVolume?volume=10')

    assert ('GET', 'v1/main/setVolume?volume=10', None) in device.calls


def test_list_payload_is_sent_as_post():
    plugin, sh, device, network = make_running_plugin()

    write(plugin, sh, network, 'yamaha.dev.main.alarm_on', True)

    method, path, data = next(call for call in device.calls if call[1] == 'v1/clock/setAlarmSettings')
    assert method == 'POST'
    assert json.loads(data) == {'alarm_on': 'true'}


def test_non_string_passthru_value_is_ignored():
    plugin, sh, device, network = make_running_plugin()

    write(plugin, sh, network, 'yamaha.dev.main.passthru_num', 5)

    assert '5' not in device.paths()
