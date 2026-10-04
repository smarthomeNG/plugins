"""Item writes are translated into device requests."""

from unittest.mock import patch

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin


def make_running_plugin():
    device = FakeDevice(
        {'zone': [{'id': 'main', 'func_list': ['power', 'volume', 'mute'], 'input_list': [], 'range_step': []}]}
    )
    network = FakeNetwork({'127.0.0.1': device})
    plugin, sh = make_plugin('items_write.yaml', network)
    plugin.alive = True
    device.calls.clear()
    return plugin, sh, device, network


def write(plugin, sh, network, path, value):
    item = sh.return_item(path)
    item(value, 'test')
    with network.active():
        plugin.update_item(item, 'test')


def test_power_write_sends_set_power():
    plugin, sh, device, network = make_running_plugin()

    write(plugin, sh, network, 'yamaha.dev.main.power', True)

    assert 'v1/main/setPower?power=on' in device.paths()


def test_cmd_is_matched_case_insensitively():
    plugin, sh, device, network = make_running_plugin()

    write(plugin, sh, network, 'yamaha.dev.main.volume_mixed_case', 30)

    assert 'v1/main/setVolume?volume=30' in device.paths()


def test_write_does_not_resolve_hostnames():
    plugin, sh, device, network = make_running_plugin()

    with patch('plugins.yamahayxc.socket.gethostbyname', side_effect=AssertionError('DNS lookup on write')):
        write(plugin, sh, network, 'yamaha.dev.main.power', True)

    assert 'v1/main/setPower?power=on' in device.paths()


def test_write_while_stopped_is_ignored():
    plugin, sh, device, network = make_running_plugin()
    plugin.alive = False

    write(plugin, sh, network, 'yamaha.dev.main.power', True)

    assert device.calls == []


def test_numeric_item_values_work_as_booleans():
    plugin, sh, device, network = make_running_plugin()

    write(plugin, sh, network, 'yamaha.dev.main.power_num', 1)
    write(plugin, sh, network, 'yamaha.dev.main.mute_num', 0)

    assert 'v1/main/setPower?power=on' in device.paths()
    assert 'v1/main/setMute?enable=false' in device.paths()
