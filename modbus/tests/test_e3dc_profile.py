"""The shipped E3/DC profile, used as struct, reads a simulated S10 over real Modbus TCP."""

from plugins.modbus import profiles
from plugins.modbus.tests.profile_rig import poll_once, text, words

ITEMS = """
pv:
    s10:
        struct: modbus.e3dc.s10
"""


def test_struct_reads_the_simple_mode_registers(tmp_path, modbus_server):
    server = modbus_server(
        1,
        {
            40000: [0xE3DC],
            40003: text('E3/DC GmbH', 16),
            40067: words('>i', 4321, low_word_first=True),
            40069: words('>i', -1500, low_word_first=True),
            40073: words('>i', -250, low_word_first=True),
            40081: [(87 << 8) | 64],
            40082: [55],
        },
    )

    rig = poll_once(tmp_path, server, ITEMS)

    assert rig.item('pv.s10.info.magic')() == 0xE3DC
    assert rig.item('pv.s10.info.manufacturer')() == 'E3/DC GmbH'
    assert rig.item('pv.s10.power.solar')() == 4321
    assert rig.item('pv.s10.power.battery')() == -1500
    assert rig.item('pv.s10.power.grid')() == -250
    assert rig.item('pv.s10.state.autarky')() == 87
    assert rig.item('pv.s10.state.self_consumption')() == 64
    assert rig.item('pv.s10.state.state_of_charge')() == 55


def test_struct_reads_the_extended_simple_mode_registers(tmp_path, modbus_server):
    server = modbus_server(
        1,
        {
            40083: [1],
            40084: [0b0010101],
            40087: [(1 << 12) | 0b1011],
            40095: [119],
            40098: [250],
            40101: [298],
            40128: [1],
            40136: [2],
            40173: words('>i', -4200, low_word_first=True),
            40185: words('>i', 6000, low_word_first=True),
            41005: words('>i', -1830, low_word_first=True),
            41017: [2370],
            41023: [4998],
            41030: [125],
        },
    )

    rig = poll_once(tmp_path, server, ITEMS)

    def value(path: str):
        return rig.item(f'pv.s10.{path}')()

    assert value('state.emergency_power.text') == 'active'
    assert [
        value(f'state.ems_status.{bit}') for bit in ('charging_locked', 'discharging_locked', 'emergency_possible')
    ] == [True, False, True]
    assert value('state.ems_status.curtailed') is True
    assert value('state.sg_ready') == 2
    assert (value('dc.string_1.voltage'), value('dc.string_1.current'), value('dc.string_1.power')) == (119, 2.5, 298)
    assert (value('meters.meter_6.meter_type.text'), value('meters.meter_6.l1')) == ('root meter', -4200)
    assert [
        value(f'wallbox.wallbox_0.{bit}')
        for bit in ('available', 'solar_mode', 'charging_aborted', 'charging', 'one_phase')
    ] == [True, True, False, True, True]
    assert value('control.feed_in_limit') == 6000
    assert (value('inverter.active_l1'), value('inverter.voltage_l1'), value('inverter.frequency')) == (
        -1830,
        237.0,
        49.98,
    )
    assert value('inverter.dc_current_1') == 1.25


def test_feed_in_limit_is_read_only():
    (s10,) = [profile for profile in profiles.load_all() if profile.id == 'e3dc.s10']

    limit = profiles.to_struct(s10)['control']['feed_in_limit']

    assert limit['modBusDirection@instance'] == 'read'
    assert 'remark' not in limit
