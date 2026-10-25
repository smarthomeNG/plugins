"""The DAB walk/tune items run jobs against a device and publish their outcome."""

import threading

from plugins.yamahayxc.dabstations import Settle
from plugins.yamahayxc.tests.dab_fake import FakeDabTuner
from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin, wait_until

SERVICES = [(7, 'Dlf'), (3, 'RADIO BOB!'), (9, 'WDR 2')]
MAIN_ZONE = {'id': 'main', 'func_list': ['power', 'mute'], 'input_list': [], 'range_step': []}
FAST = Settle(poll_interval=0.0, timeout=0.5)


def start(services=SERVICES, position=0, preset_numbers=()):
    tuner = FakeDabTuner(services, position)
    tuner.preset_numbers = list(preset_numbers)
    device = FakeDevice(
        {'zone': [MAIN_ZONE], 'tuner': {'func_list': ['dab'], 'preset': {'type': 'separate', 'num': 30}}}
    )
    device.handlers.append(tuner.handle)
    network = FakeNetwork({'127.0.0.1': device})
    plugin, sh = make_plugin('items_dab.yaml', network, initialize=False)
    plugin._dab_settle = FAST
    with network.active():
        plugin._initialize()
    plugin.alive = True
    return plugin, sh, device, network, tuner


def item(sh, name):
    return sh.return_item('yamaha.dev.main.' + name)


def write(plugin, sh, name, value):
    target = item(sh, name)
    target(value, 'test')
    plugin.update_item(target, 'test')


def test_walk_item_runs_a_walk_and_publishes_the_ordered_services():
    plugin, sh, device, network, tuner = start()

    with network.active():
        write(plugin, sh, 'tuner_dab_walk', True)
        assert wait_until(lambda: item(sh, 'tuner_dab_walk_state')() == 'done')

    assert item(sh, 'tuner_dab_services')() == [
        {'index': 0, 'id': 7, 'name': 'Dlf'},
        {'index': 1, 'id': 3, 'name': 'RADIO BOB!'},
        {'index': 2, 'id': 9, 'name': 'WDR 2'},
    ]
    assert item(sh, 'tuner_dab_walk')() is False
    assert item(sh, 'tuner_dab_walk_progress')() == 100


def walked(plugin, sh, network):
    write(plugin, sh, 'tuner_dab_walk', True)
    assert wait_until(lambda: item(sh, 'tuner_dab_walk_state')() == 'done')


def test_tune_item_steps_to_the_listed_service_and_resets_to_idle():
    plugin, sh, device, network, tuner = start()

    with network.active():
        walked(plugin, sh, network)
        write(plugin, sh, 'tuner_dab_tune', 2)
        assert wait_until(lambda: len(tuner.mute_history) == 4)
        assert wait_until(lambda: item(sh, 'tuner_dab_walk_state')() == 'done')

    assert tuner.position == 2
    assert tuner.muted is False


def test_writing_false_to_the_walk_item_aborts_the_walk_and_keeps_no_list():
    plugin, sh, device, network, tuner = start()
    tuner.gate = threading.Event()

    with network.active():
        write(plugin, sh, 'tuner_dab_walk', True)
        assert wait_until(lambda: tuner.mute_history == [True])
        write(plugin, sh, 'tuner_dab_walk', False)
        tuner.gate.set()
        assert wait_until(lambda: item(sh, 'tuner_dab_walk_state')() == 'aborted')

    assert item(sh, 'tuner_dab_services')() == []
    assert tuner.muted is False


def test_tune_without_a_walked_list_does_nothing():
    plugin, sh, device, network, tuner = start()

    with network.active():
        write(plugin, sh, 'tuner_dab_tune', 1)

    assert item(sh, 'tuner_dab_tune')() == -1
    assert not [path for path in device.paths() if 'setDabService' in path]


def test_walk_off_dab_ends_in_error_and_resets_the_item():
    plugin, sh, device, network, tuner = start()
    tuner.band = 'fm'

    with network.active():
        write(plugin, sh, 'tuner_dab_walk', True)
        assert wait_until(lambda: item(sh, 'tuner_dab_walk_state')() == 'error')

    assert item(sh, 'tuner_dab_walk')() is False


def test_a_changed_station_count_empties_the_published_service_list():
    plugin, sh, device, network, tuner = start()

    with network.active():
        walked(plugin, sh, network)
        tuner.services = tuner.services + [(11, 'NDR 2')]
        plugin._update_tuner_state('127.0.0.1')

    assert item(sh, 'tuner_dab_services')() == []


def test_a_finished_walk_names_the_presets_in_the_station_list():
    plugin, sh, device, network, tuner = start(preset_numbers=[3, 9])

    with network.active():
        assert [entry['name'] for entry in item(sh, 'tuner_stations')()] == ['', '']
        walked(plugin, sh, network)
        assert wait_until(lambda: [entry['name'] for entry in item(sh, 'tuner_stations')()] == ['RADIO BOB!', 'WDR 2'])
