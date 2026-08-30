"""
Regression test: input_sources (and other getFeatures-derived capability
lists) must be re-read after a device comes back online, not left stale
from the last successful read (or empty, if the device was down at
plugin startup).
"""

import json
from unittest.mock import patch

from tests import common
from tests.mock.core import MockSmartHome

from plugins.yamahayxc import YamahaYXC


class FakeDevice:
    """Stands in for the real MusicCast HTTP endpoint behind requests.get()."""

    def __init__(self):
        self.input_sources = ['hdmi1', 'hdmi2']
        self.up = True

    def get(self, url, headers=None, timeout=None):
        if not self.up:
            raise ConnectionError('device unreachable')

        class _Response:
            pass

        response = _Response()
        if url.endswith('getFeatures'):
            body = {
                'response_code': 0,
                'zone': [{'id': 'main', 'func_list': [], 'input_list': self.input_sources, 'range_step': []}],
            }
        else:
            body = {'response_code': 0}
        response.text = json.dumps(body)
        return response


def make_plugin(device):
    sh = MockSmartHome()
    sh.with_items_from(common.BASE + '/plugins/yamahayxc/tests/test_items.yaml')

    YamahaYXC._parameters = {'cycle': 30}
    plugin = YamahaYXC.__new__(YamahaYXC)
    plugin._set_sh(sh)
    plugin.__init__(sh)
    for item in sh.return_items():
        plugin.parse_item(item)

    with patch('plugins.yamahayxc.requests.get', side_effect=device.get):
        plugin._initialize()

    return plugin, sh


def test_reconnect_refreshes_input_sources():
    device = FakeDevice()
    plugin, sh = make_plugin(device)

    input_sources_item = sh.return_item('yamaha.dev.main.input_sources')
    reachable_item = sh.return_item('yamaha.dev.reachable')

    assert list(input_sources_item()) == sorted(['hdmi1', 'hdmi2'])
    assert reachable_item() is True

    device.up = False
    with patch('plugins.yamahayxc.requests.get', side_effect=device.get):
        plugin.poll_device()
        plugin.poll_device()  # 2 consecutive failures -> flips to unreachable

    assert reachable_item() is False

    # device comes back online with a changed input list, e.g. a newly
    # detected HDMI source
    device.input_sources = ['hdmi1', 'hdmi2', 'bluetooth']
    device.up = True
    with patch('plugins.yamahayxc.requests.get', side_effect=device.get):
        plugin.poll_device()

    assert reachable_item() is True
    assert list(input_sources_item()) == sorted(['hdmi1', 'hdmi2', 'bluetooth'])
