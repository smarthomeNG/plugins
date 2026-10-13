"""play_time is reported as percent of the same device's total_time."""

import json

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin, wait_until


def make_two_devices():
    one = FakeDevice()
    two = FakeDevice()
    one.responses = {'v1/netusb/getPlayInfo': {'play_time': 100, 'total_time': 200}}
    two.responses = {'v1/netusb/getPlayInfo': {'play_time': 75, 'total_time': 300}}
    return FakeNetwork({'127.0.0.1': one, '127.0.0.2': two})


def test_play_time_is_percent_of_total_time_from_the_same_response():
    plugin, sh = make_plugin('items_playtime.yaml', make_two_devices())

    assert sh.return_item('yamaha.one.play_time')() == 50
    assert sh.return_item('yamaha.two.play_time')() == 25


def test_pushed_play_time_uses_the_total_time_of_its_own_host():
    plugin, sh = make_plugin('items_playtime.yaml', make_two_devices())

    plugin._data_received(('127.0.0.1', 41100), json.dumps({'netusb': {'play_time': 150}}))

    assert wait_until(lambda: sh.return_item('yamaha.one.play_time')() == 75)
