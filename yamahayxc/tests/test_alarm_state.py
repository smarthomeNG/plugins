"""Alarm clock polling: only for hosts with alarm items, tolerant of unexpected responses."""

from plugins.yamahayxc.tests.harness import FakeDevice, FakeNetwork, make_plugin

MAIN_ZONE = {'id': 'main', 'func_list': ['volume'], 'input_list': [], 'range_step': []}


def make_devices():
    one = FakeDevice({'zone': [MAIN_ZONE]})
    two = FakeDevice({'zone': [MAIN_ZONE]})
    two.responses = {'v1/main/getStatus': {'volume': 30}}
    return one, two


def test_alarm_items_receive_the_alarm_state():
    one, two = make_devices()
    one.responses = {'v1/clock/getSettings': {'alarm': {'alarm_on': 'true', 'oneday': {'time': '0630', 'beep': False}}}}

    plugin, sh = make_plugin('items_alarm.yaml', FakeNetwork({'127.0.0.1': one, '127.0.0.2': two}))

    assert sh.return_item('yamaha.one.alarm_on')() is True


def test_unexpected_alarm_response_does_not_stop_other_hosts_initializing():
    one, two = make_devices()
    one.responses = {'v1/clock/getSettings': {'alarm': {'alarm_on': False}}}

    plugin, sh = make_plugin('items_alarm.yaml', FakeNetwork({'127.0.0.1': one, '127.0.0.2': two}))

    assert sh.return_item('yamaha.two.volume')() == 30


def test_alarm_is_not_polled_for_hosts_without_alarm_items():
    one, two = make_devices()

    plugin, sh = make_plugin('items_alarm.yaml', FakeNetwork({'127.0.0.1': one, '127.0.0.2': two}))

    assert 'v1/clock/getSettings' in one.paths()
    assert 'v1/clock/getSettings' not in two.paths()
