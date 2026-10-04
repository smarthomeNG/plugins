"""Push notifications are processed off the UDP listener thread, one worker per host."""

import json
import threading
import time

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin, wait_until

MAIN_ZONE = {'id': 'main', 'func_list': ['volume'], 'input_list': [], 'range_step': []}


def make_two_host_setup():
    one = FakeDevice({'zone': [MAIN_ZONE]})
    two = FakeDevice({'zone': [MAIN_ZONE]})
    one.responses = {'v1/main/getStatus': {'volume': 11}}
    two.responses = {'v1/main/getStatus': {'volume': 22}}
    network = FakeNetwork({'127.0.0.1': one, '127.0.0.2': two})
    plugin, sh = make_plugin('items_two_hosts.yaml', network)
    return plugin, sh, one, two, network


def test_stalled_device_does_not_delay_other_devices():
    plugin, sh, one, two, network = make_two_host_setup()
    one.gate = threading.Event()

    with network.active():
        started = time.monotonic()
        plugin._data_received(('127.0.0.1', 41100), json.dumps({'main': {'status_updated': True}}))
        plugin._data_received(('127.0.0.2', 41100), json.dumps({'main': {'volume': 7}}))
        returned_after = time.monotonic() - started

        try:
            assert returned_after < 1
            assert wait_until(lambda: sh.return_item('yamaha.two.volume')() == 7)
        finally:
            one.gate.set()


def test_notifications_of_one_host_are_applied_in_order():
    plugin, sh, one, two, network = make_two_host_setup()

    with network.active():
        for volume in (10, 20, 30):
            plugin._data_received(('127.0.0.1', 41100), json.dumps({'main': {'volume': volume}}))

        assert wait_until(lambda: sh.return_item('yamaha.one.volume')() == 30)


def test_notifications_after_stop_are_dropped():
    plugin, sh, one, two, network = make_two_host_setup()

    plugin.stop()
    plugin._data_received(('127.0.0.1', 41100), json.dumps({'main': {'volume': 99}}))

    assert not wait_until(lambda: sh.return_item('yamaha.one.volume')() == 99, timeout=0.2)
