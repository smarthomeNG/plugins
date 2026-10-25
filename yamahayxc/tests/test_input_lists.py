"""yamahayxc_inputs shortens what input.values/input.names offer; writes are still checked against the device's list."""

import logging

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin

INPUTS = ['tuner', 'net_radio', 'hdmi1', 'hdmi2', 'av3', 'spotify', 'bluetooth']
ZONES = [
    {'id': 'main', 'func_list': ['power'], 'input_list': INPUTS, 'range_step': []},
    {'id': 'zone2', 'func_list': ['power'], 'input_list': ['tuner', 'av3', 'aux'], 'range_step': []},
]


def make(initialize=True, items='items_inputs.yaml'):
    network = FakeNetwork({'127.0.0.1': FakeDevice({'zone': ZONES})})
    plugin, sh = make_plugin(items, network, initialize=initialize)
    return plugin, sh, network


def start(items='items_inputs.yaml'):
    plugin, sh, network = make(items=items)
    return plugin, sh, network.devices['127.0.0.1'], network


def value(sh, path):
    return sh.return_item('yamaha.' + path)()


def test_input_values_offer_only_the_configured_inputs_sorted_regardless_of_the_configured_order():
    plugin, sh, device, network = start()

    assert value(sh, 'dev.main.input_values') == ['hdmi1', 'net_radio', 'spotify', 'tuner']


def test_input_names_are_the_capitalized_values_in_the_same_order():
    plugin, sh, device, network = start()

    assert value(sh, 'dev.main.input_names') == ['Hdmi1', 'Net_radio', 'Spotify', 'Tuner']


def test_without_yamahayxc_inputs_all_inputs_are_offered_sorted():
    plugin, sh, device, network = start('items_inputs_plain.yaml')

    assert value(sh, 'dev.main.input_values') == sorted(INPUTS)
    assert value(sh, 'dev.main.input_names') == [name.capitalize() for name in sorted(INPUTS)]


def test_a_zone_can_override_the_inherited_selection():
    plugin, sh, device, network = start()

    assert value(sh, 'dev.zone2.input_values') == ['av3']
    assert value(sh, 'dev.zone2.input_names') == ['Av3']


def test_the_selection_may_be_a_comma_separated_string_in_any_case():
    plugin, sh, device, network = start('items_inputs_csv.yaml')

    assert value(sh, 'dev.main.input_values') == ['hdmi2', 'tuner']


class Collect(logging.Handler):
    """keeps the records it is given"""

    def __init__(self):
        super().__init__()
        self.records = []

    def emit(self, record):
        self.records.append(record)


def test_names_the_device_does_not_offer_are_logged_at_info_level():
    plugin, sh, network = make(initialize=False)
    collected = Collect()
    plugin.logger.addHandler(collected)
    plugin.logger.setLevel(logging.INFO)

    with network.active():
        plugin._initialize()

    messages = [record.getMessage() for record in collected.records if record.levelno == logging.INFO]
    assert any('typo' in message and 'dev.main.input_values' in message for message in messages)


def test_a_selection_without_any_available_input_falls_back_to_all_inputs():
    plugin, sh, device, network = start('items_inputs_typos.yaml')

    assert value(sh, 'dev.main.input_values') == sorted(INPUTS)


def test_an_input_hidden_from_the_list_can_still_be_selected_by_a_write():
    plugin, sh, device, network = start()
    item = sh.return_item('yamaha.dev.main.input')
    item('av3', 'test')
    device.calls.clear()

    with network.active():
        plugin.update_item(item, 'test')

    assert 'v1/main/setInput?input=av3' in device.paths()
