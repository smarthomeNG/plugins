"""The plugin keeps what each device reported and presents it, with a struct recommendation, for the web interface."""

from plugins.yamahayxc.tests.features_samples import ISX_18D, RX_V483
from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin

DEVICE_INFO = {'model_name': 'ISX-18D', 'system_version': 2.16, 'api_version': 2.08}


def start():
    device = FakeDevice(ISX_18D)
    device.responses = {'v1/system/getDeviceInfo': DEVICE_INFO}
    plugin, sh = make_plugin('items_state.yaml', FakeNetwork({'127.0.0.1': device}))
    return plugin, device


def test_the_overview_lists_each_host_with_its_reported_device_info_and_features():
    plugin, device = start()

    entry = next(entry for entry in plugin.devices_overview({'isx-18d'}) if entry['host'] == '127.0.0.1')

    assert entry['host'] == '127.0.0.1'
    assert entry['reachable'] is True
    assert entry['device_info']['model_name'] == 'ISX-18D'
    assert entry['features']['tuner']['func_list'][0] == 'fm'


def overview_entry(plugin):
    return next(entry for entry in plugin.devices_overview({'isx-18d'}) if entry['host'] == '127.0.0.1')


def test_the_overview_recommends_the_ready_made_struct_for_a_known_model():
    plugin, device = start()

    advice = overview_entry(plugin)['advice']

    assert advice['ready_made'] == 'isx-18d'
    assert advice['structs'] == ['amp', 'link', 'netusb', 'tuner', 'alarm']
    assert 'struct: yamahayxc.isx-18d' in advice['config']


def test_a_device_that_did_not_answer_has_empty_info_and_features():
    device = FakeDevice(ISX_18D)
    device.up = False
    plugin, sh = make_plugin('items_state.yaml', FakeNetwork({'127.0.0.1': device}))

    entry = overview_entry(plugin)

    assert entry['device_info'] == {}
    assert entry['features'] == {}
    assert entry['reachable'] is False


def query(host, devices=None, known=frozenset({'rx-v483'})):
    network = FakeNetwork(devices or {})
    plugin, sh = make_plugin('items_state.yaml', FakeNetwork({'127.0.0.1': FakeDevice(ISX_18D)}))
    with network.active():
        return plugin.query_device(host, known), network


def new_device():
    device = FakeDevice(RX_V483)
    device.responses = {'v1/system/getDeviceInfo': {'model_name': 'RX-V483'}}
    return device


def test_a_new_device_can_be_queried_for_its_struct_advice():
    result, network = query('newdev', {'newdev': new_device()})

    assert result['device_info']['model_name'] == 'RX-V483'
    assert result['advice']['ready_made'] == 'rx-v483'
    assert result['advice']['structs'] == ['amp', 'link', 'netusb', 'tuner', 'dsp', 'zone2']


def test_querying_a_new_device_does_not_subscribe_it_to_notifications():
    result, network = query('newdev', {'newdev': new_device()})

    assert network.requests
    assert all('X-AppName' not in (headers or {}) for _, headers in network.requests)


def test_only_a_plain_host_name_is_queried():
    for host in ('', 'dev:80', 'dev/../x', 'dev x', 'http://dev'):
        result, network = query(host, {})

        assert result == {'error': 'invalid host'}
        assert network.requests == []


def test_a_device_that_does_not_answer_is_reported():
    offline = new_device()
    offline.up = False

    result, network = query('newdev', {'newdev': offline})

    assert result == {'error': 'no answer from newdev'}


def test_bound_items_list_path_command_host_zone_and_value():
    plugin, device = start()

    entries = {entry['path']: entry for entry in plugin.bound_items()}

    entry = entries['yamaha.dev.main.power']
    assert entry['cmd'] == 'power'
    assert entry['host'] == '127.0.0.1'
    assert entry['zone'] == 'main'
    assert 'value' in entry and 'last_update' in entry
