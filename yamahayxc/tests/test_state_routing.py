"""Device responses and push notifications reach the items registered for the matching host/zone/cmd."""

import json

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin, wait_until

MAIN_ZONE = {'id': 'main', 'func_list': ['power', 'volume'], 'input_list': [], 'range_step': []}


def make_device():
    device = FakeDevice({'zone': [MAIN_ZONE]})
    device.responses = {
        'v1/main/getStatus': {'power': 'on', 'volume': 50},
        'v1/netusb/getPlayInfo': {'track': 'Song'},
        'v1/tuner/getPlayInfo': {'band': 'fm'},
        'v1/dist/getDistributionInfo': {'group_id': 'ABC'},
    }
    return device


def test_initialize_pushes_each_scope_to_its_items():
    device = make_device()
    plugin, sh = make_plugin('items_state.yaml', FakeNetwork({'127.0.0.1': device}))

    assert sh.return_item('yamaha.dev.main.power')() is True
    assert sh.return_item('yamaha.dev.main.volume')() == 50
    assert sh.return_item('yamaha.dev.main.track')() == 'Song'
    assert sh.return_item('yamaha.dev.main.tuner_band')() == 'fm'
    assert sh.return_item('yamaha.dev.main.link_group_id')() == 'ABC'
    assert sh.return_item('yamaha.dev.main.reachable')() is True
    assert sh.return_item('yamaha.dev.main.available')() is True


def test_push_notification_updates_zone_item():
    device = make_device()
    plugin, sh = make_plugin('items_state.yaml', FakeNetwork({'127.0.0.1': device}))

    plugin._data_received(('127.0.0.1', 41100), json.dumps({'main': {'volume': 42}}))

    assert wait_until(lambda: sh.return_item('yamaha.dev.main.volume')() == 42)


def test_push_from_unknown_host_is_ignored():
    device = make_device()
    plugin, sh = make_plugin('items_state.yaml', FakeNetwork({'127.0.0.1': device}))

    plugin._data_received(('10.9.9.9', 41100), json.dumps({'main': {'volume': 7}}))

    assert sh.return_item('yamaha.dev.main.volume')() == 50
