"""The web interface serves the plugin's item and device data as JSON."""

import json
from types import SimpleNamespace
from unittest.mock import patch

from plugins.yamahayxc import YamahaYXC
from plugins.yamahayxc.tests.features_samples import ISX_18D
from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin
from plugins.yamahayxc.webif import WebInterface


def start_webif():
    device = FakeDevice(ISX_18D)
    device.responses = {'v1/system/getDeviceInfo': {'model_name': 'ISX-18D'}}
    network = FakeNetwork({'127.0.0.1': device})
    plugin, sh = make_plugin('items_state.yaml', network)
    plugin.metadata = SimpleNamespace(itemstructs={'isx-18d': {}, 'amp': {}})
    webif = WebInterface.__new__(WebInterface)
    webif.plugin = plugin
    return webif, network


def test_data_has_the_bound_items_and_the_devices_with_their_struct_advice():
    webif, network = start_webif()

    data = json.loads(webif.get_data_html())

    assert 'yamaha.dev.main.power' in [item['path'] for item in data['items']]
    device = next(device for device in data['devices'] if device['host'] == '127.0.0.1')
    assert device['advice']['ready_made'] == 'isx-18d'


def test_querying_a_device_returns_json_with_its_advice():
    webif, network = start_webif()
    newdev = FakeDevice(ISX_18D)
    newdev.responses = {'v1/system/getDeviceInfo': {'model_name': 'ISX-18D'}}
    other = FakeNetwork({'newdev': newdev})

    with other.active():
        result = json.loads(webif.query_device('newdev'))

    assert result['advice']['ready_made'] == 'isx-18d'


def test_the_plugin_registers_its_web_interface():
    with patch.object(YamahaYXC, 'init_webinterface') as init_webinterface:
        make_plugin('items_state.yaml', FakeNetwork({'127.0.0.1': FakeDevice(ISX_18D)}), initialize=False)

    init_webinterface.assert_called_once_with(WebInterface)
