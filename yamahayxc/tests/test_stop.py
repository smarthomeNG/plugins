"""Stopping the plugin tears down what run() started."""

from unittest.mock import patch

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin

MAIN_ZONE = {'id': 'main', 'func_list': ['power', 'volume'], 'input_list': [], 'range_step': []}


class FakeUdpServer:
    """Stands in for lib.network.Udp_server (no real socket)."""

    def __init__(self, port):
        self.closed = False

    def set_callbacks(self, data_received=None):
        pass

    def start(self):
        pass

    def listening(self):
        return True

    def close(self):
        self.closed = True


def make_state_plugin():
    device = FakeDevice({'zone': [MAIN_ZONE]})
    device.responses = {'v1/main/getStatus': {'power': 'on', 'volume': 50}}
    network = FakeNetwork({'127.0.0.1': device})
    plugin, sh = make_plugin('items_state.yaml', network)
    return plugin, sh, device, network


def test_stop_removes_poll_schedule():
    plugin, sh, device, network = make_state_plugin()

    with patch('plugins.yamahayxc.Udp_server', FakeUdpServer):
        plugin.run()
        assert sh.scheduler.jobs
        plugin.stop()

    assert not sh.scheduler.jobs


def test_poll_after_stop_does_not_touch_device():
    plugin, sh, device, network = make_state_plugin()
    device.calls.clear()
    plugin.alive = False

    with network.active():
        plugin.poll_device()

    assert device.calls == []
