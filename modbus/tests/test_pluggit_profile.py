"""The shipped pluggit profile, used as struct, reads a simulated AP310 over real Modbus TCP."""

from datetime import date, datetime

from plugins.modbus.tests.profile_rig import poll_once, words

ITEMS = """
kwl:
    struct: modbus.pluggit.ap310
"""


def low_word_first(fmt: str, value) -> list[int]:
    return words(fmt, value, low_word_first=True)


def name(text: str, count: int) -> list[int]:
    raw = text.encode().ljust(count * 2, b'\0')
    return [raw[i] | raw[i + 1] << 8 for i in range(0, len(raw), 2)]


def test_struct_reads_the_device(tmp_path, modbus_server):
    server = modbus_server(
        1,
        {
            2: [0x0205],
            4: low_word_first('>Q', 123456789),
            8: name('Wohnung', 16),
            24: [0x0213],
            28: low_word_first('>I', 0xC0A80228),
            40: [0x0011, 0, 0x4455, 0x2233],
            108: low_word_first('>I', 1_700_000_000),
            132: low_word_first('>f', 23.408),
            168: low_word_first('>I', 0x0014),
            198: [32],
            324: low_word_first('>I', 3),
            472: [5],
            516: [3],
        },
    )

    rig = poll_once(tmp_path, server, ITEMS)

    def value(path: str):
        return rig.item(f'kwl.{path}')()

    assert value('SystemComponents') == 0x0205
    assert [value(f'SystemComponents.{f}') for f in ('FP1', 'Week', 'Bypass', 'HAC1')] == [True, False, True, True]
    assert value('SystemSerialNum') == 123456789
    assert value('SystemName') == 'Wohnung'
    assert value('FirmwareVersion') == '2.19'
    assert value('IPAdress') == '192.168.2.40'
    assert value('MACAdress') == '00:11:22:33:44:55'
    assert value('SystemTime') == 1_700_000_000
    assert value('SystemTime.DateTime') == datetime(2023, 11, 14, 22, 13, 20)
    assert rig.item('kwl.SystemTime.DateTime').type() == 'datetime'
    assert value('SystemTime.Date') == date(2023, 11, 14)
    assert value('OutdoorTemperature') == 23.41
    assert value('CurrentUnitMode') == 0x0014
    assert (value('CurrentUnitMode.ManualMode'), value('CurrentUnitMode.AwayMode')) == (True, True)
    assert value('CurrentUnitMode.DemandMode') is False
    assert (value('Bypass'), value('Bypass.Text'), value('Bypass.Open')) == (32, 'Closing', True)
    assert value('FanSpeedLevel') == 3
    assert value('BLState.Text') == 'Away'
    assert value('Alarm.Text') == 'Bypass Alarm'
