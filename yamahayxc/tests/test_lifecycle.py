"""Plugin lifecycle: scheduler/listener teardown and per-host bookkeeping on item removal."""

import json
from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin, wait_until

MAIN_ZONE = {'id': 'main', 'func_list': ['power', 'volume'], 'input_list': [], 'range_step': []}


def make_state_plugin():
    device = FakeDevice({'zone': [MAIN_ZONE]})
    device.responses = {'v1/main/getStatus': {'power': 'on', 'volume': 50}}
    network = FakeNetwork({'127.0.0.1': device})
    plugin, sh = make_plugin('items_state.yaml', network)
    return plugin, sh, device, network


def test_removed_items_stop_receiving_pushes():
    plugin, sh, device, network = make_state_plugin()
    volume = sh.return_item('yamaha.dev.main.volume')

    power = sh.return_item('yamaha.dev.main.power')
    power(False, 'test')

    plugin.remove_item(volume)
    plugin._data_received(('127.0.0.1', 41100), json.dumps({'main': {'volume': 42, 'power': 'on'}}))

    assert wait_until(lambda: power() is True)
    assert volume() == 50


def test_readded_host_reports_reachable_on_first_contact():
    plugin, sh, device, network = make_state_plugin()
    plugin.alive = True
    items = list(sh.return_items())
    for item in items:
        plugin.remove_item(item)
    reachable = sh.return_item('yamaha.dev.main.reachable')
    reachable(False, 'test')
    for item in items:
        plugin.parse_item(item)

    with network.active():
        plugin.poll_device()

    assert reachable() is True


def test_deinit_unregisters_all_items():
    plugin, sh, device, network = make_state_plugin()

    plugin.deinit()
    plugin._data_received(('127.0.0.1', 41100), json.dumps({'main': {'volume': 42}}))

    assert plugin.get_item_list() == []
    assert sh.return_item('yamaha.dev.main.volume')() == 50
