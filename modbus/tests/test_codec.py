"""Datatype codecs: register layout, round trips, sentinels and unknown datatypes."""

from datetime import date, datetime, time

import pytest

from plugins.modbus.codec import default_registry
from plugins.modbus.model import Endian, RegisterKey, RegisterSpec, Table

KEY = RegisterKey(1, Table.HOLDING_REGISTER, 0)
ORDERS = [
    (Endian.BIG, Endian.BIG),
    (Endian.BIG, Endian.LITTLE),
    (Endian.LITTLE, Endian.BIG),
    (Endian.LITTLE, Endian.LITTLE),
]


def spec(datatype: str, byte_order: Endian = Endian.BIG, word_order: Endian = Endian.BIG) -> RegisterSpec:
    return RegisterSpec(KEY, datatype=datatype, byte_order=byte_order, word_order=word_order)


def encode(datatype, value, byte_order=Endian.BIG, word_order=Endian.BIG):
    s = spec(datatype, byte_order, word_order)
    return default_registry().resolve(s.datatype).encode(value, s)


def decode(datatype, registers, byte_order=Endian.BIG, word_order=Endian.BIG):
    s = spec(datatype, byte_order, word_order)
    return default_registry().resolve(s.datatype).decode(registers, s)


@pytest.mark.parametrize(
    'datatype,value',
    [
        ('uint16', 0x1234),
        ('uint32', 0x12345678),
        ('uint64', 0x123456789ABCDEF0),
        ('int16', -1234),
        ('int32', -123456),
        ('int64', -123456789),
        ('float32', 12.5),
        ('float64', -12.5),
    ],
)
@pytest.mark.parametrize('byte_order,word_order', ORDERS)
def test_round_trip(datatype, value, byte_order, word_order):
    assert decode(datatype, encode(datatype, value, byte_order, word_order), byte_order, word_order) == value


@pytest.mark.parametrize(
    'byte_order,word_order,expected',
    [
        (Endian.BIG, Endian.BIG, [0x1234, 0x5678]),
        (Endian.BIG, Endian.LITTLE, [0x5678, 0x1234]),
        (Endian.LITTLE, Endian.BIG, [0x3412, 0x7856]),
        (Endian.LITTLE, Endian.LITTLE, [0x7856, 0x3412]),
    ],
)
def test_known_wire_order(byte_order, word_order, expected):
    assert encode('uint32', 0x12345678, byte_order, word_order) == expected


def test_strings_and_bit_lists():
    assert encode('string2', 'AB') == [0x4142]
    assert decode('string4', [0x4142, 0]) == 'AB'
    assert encode('bit16', '1000000000000001') == [0x8001]
    assert decode('bit16', [0x8001]) == [True] + [False] * 14 + [True]


@pytest.mark.parametrize(
    'datatype,count',
    [('uint16', 1), ('int32', 2), ('float64', 4), ('string16', 8), ('string5', 3), ('bit16', 1), ('bit17', 2)],
)
def test_register_count(datatype, count):
    assert default_registry().resolve(datatype).register_count(datatype) == count


@pytest.mark.parametrize('datatype,count', [('uint', 1), ('int', 1), ('bit', 1), ('string', 8)])
def test_size_defaults_to_16(datatype, count):
    assert default_registry().resolve(datatype).register_count(datatype) == count


@pytest.mark.parametrize(
    'datatype,value,bad',
    [
        ('int16', -32768, True),
        ('int16', -32767, False),
        ('int16', 32767, False),
        ('int32', -2147483648, True),
        ('int32', -2147483647, False),
        ('uint16', 65535, True),
        ('uint16', 65534, False),
        ('uint32', 4294967295, True),
        ('uint32', 4294967294, False),
        ('uint64', 18446744073709551615, True),
        ('float32', 1.0, False),
    ],
)
def test_invalid_sentinels(datatype, value, bad):
    assert (value in default_registry().resolve(datatype).invalid(datatype)) is bad


@pytest.mark.parametrize('datatype', ['uint8', 'float', 'float16', 'int128', 'foo', ''])
def test_unknown_datatype_is_rejected(datatype):
    with pytest.raises(KeyError):
        default_registry().resolve(datatype)


@pytest.mark.parametrize('datatype,expected', [('uint8_high', 0x5A), ('uint8_low', 0x3C)])
def test_byte_halves_of_one_register(datatype, expected):
    assert default_registry().resolve(datatype).register_count(datatype) == 1
    assert decode(datatype, [0x5A3C]) == expected


def test_byte_halves_follow_byte_order():
    assert decode('uint8_high', [0x5A3C], byte_order=Endian.LITTLE) == 0x3C


def test_byte_halves_cannot_be_written():
    with pytest.raises(ValueError):
        encode('uint8_high', 1)


@pytest.mark.parametrize('datatype,value,expected', [('uint16', 0.7 / 0.1, [7]), ('int16', -0.7 / 0.1, [0xFFF9])])
def test_integers_are_rounded_not_truncated(datatype, value, expected):
    assert encode(datatype, value) == expected


def test_strings_end_at_the_first_nul():
    assert decode('string6', [0x4142, 0x0043, 0x4400]) == 'AB'


def test_strings_are_padded_to_their_size():
    assert encode('string6', 'AB') == [0x4142, 0, 0]


def test_strings_longer_than_their_size_are_rejected():
    with pytest.raises(ValueError, match='string4'):
        encode('string4', 'ABCDE')


def test_strings_follow_byte_order():
    assert decode('string4', [0x4241, 0x0043], byte_order=Endian.LITTLE) == 'ABC'
    assert encode('string4', 'ABC', byte_order=Endian.LITTLE) == [0x4241, 0x0043]


@pytest.mark.parametrize('value', [23.4, -0.1, 327.67, 1e-7, 3.4028235e38])
def test_float32_decodes_to_the_shortest_decimal_of_the_stored_value(value):
    assert decode('float32', encode('float32', value)) == value


def test_ipv4_addresses_follow_word_order():
    assert decode('ipv4', [0xC0A8, 0x0217]) == '192.168.2.23'
    assert decode('ipv4', [0x0217, 0xC0A8], word_order=Endian.LITTLE) == '192.168.2.23'
    assert encode('ipv4', '192.168.2.23', word_order=Endian.LITTLE) == [0x0217, 0xC0A8]


def test_ipv4_rejects_what_is_not_an_address():
    with pytest.raises(ValueError):
        encode('ipv4', '192.168.2')


SECONDS = 1_700_000_000  # 2023-11-14 22:13:20


@pytest.mark.parametrize(
    'datatype,expected',
    [('datetime32', datetime(2023, 11, 14, 22, 13, 20)), ('date32', date(2023, 11, 14)), ('time32', time(22, 13, 20))],
)
def test_timestamps_are_the_device_clock_without_time_zone(datatype, expected):
    assert decode(datatype, [SECONDS & 0xFFFF, SECONDS >> 16], word_order=Endian.LITTLE) == expected


def test_datetimes_can_be_written():
    assert encode('datetime32', datetime(2023, 11, 14, 22, 13, 20)) == [SECONDS >> 16, SECONDS & 0xFFFF]


@pytest.mark.parametrize('datatype,value', [('date32', date(2023, 11, 14)), ('datetime32', 'yesterday')])
def test_dates_times_and_non_datetimes_cannot_be_written(datatype, value):
    with pytest.raises((TypeError, ValueError)):
        encode(datatype, value)


@pytest.mark.parametrize(
    'datatype,register,text',
    [
        ('hhmm', 1530, '15:30'),
        ('hhmm', 905, '09:05'),
        ('hhmm', 0, '00:00'),
        ('ddmm', 1503, '15.03.'),
        ('ddmm', 101, '01.01.'),
    ],
)
def test_decimal_digit_times_and_dates_round_trip(datatype, register, text):
    assert decode(datatype, [register]) == text
    assert encode(datatype, text) == [register]


@pytest.mark.parametrize('text,register', [('7:45', 745), ('31.12', 3112)])
def test_decimal_digit_formats_accept_short_input(text, register):
    assert encode('hhmm' if ':' in text else 'ddmm', text) == [register]


@pytest.mark.parametrize(
    'datatype,value',
    [('hhmm', '24:00'), ('hhmm', '12:60'), ('hhmm', 'noon'), ('ddmm', '32.01.'), ('ddmm', '01.13.'), ('ddmm', 1503)],
)
def test_decimal_digit_formats_reject_invalid_writes(datatype, value):
    with pytest.raises(ValueError):
        encode(datatype, value)


@pytest.mark.parametrize('datatype,register', [('hhmm', 2460), ('hhmm', 32767), ('ddmm', 1513), ('ddmm', 0)])
def test_decimal_digit_formats_reject_registers_out_of_range(datatype, register):
    with pytest.raises(ValueError):
        decode(datatype, [register])
