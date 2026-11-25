"""
Datatype codecs: conversion between raw registers and item values.

A codec serves one datatype family and parses the size from the datatype name
(``int32`` = 32 bits, ``string16`` = 16 bytes, ``bit17`` = 17 bits). A name without size
means 16 (``uint``, ``int``, ``bit``, ``string``). Factor and invalid-value handling are
applied by the caller, around the codec.
"""

from __future__ import annotations

import ipaddress
import re
import struct
from collections.abc import Sequence
from dataclasses import replace
from datetime import datetime, timezone
from typing import ClassVar, Protocol

from pymodbus.client import AsyncModbusTcpClient

from .devices import pluggit
from .model import Endian, RegisterSpec, Value

_DATATYPE = AsyncModbusTcpClient.DATATYPE


class Codec(Protocol):
    """Conversion between registers and an item value for one datatype family."""

    def handles(self, datatype: str) -> bool:
        """Whether this codec serves ``datatype``."""
        ...

    def register_count(self, datatype: str) -> int:
        """Number of registers one value of ``datatype`` occupies."""
        ...

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """Item value from ``register_count`` registers; raises ValueError on malformed data."""
        ...

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """Registers for ``value``; raises ValueError, TypeError or OverflowError if it does not fit."""
        ...

    def invalid(self, datatype: str) -> frozenset[int | float]:
        """Decoded values the datatype uses for "not available"."""
        ...


def swap_bytes(registers: Sequence[int]) -> list[int]:
    """Registers with high and low byte exchanged."""
    return [((register & 0x00FF) << 8) | ((register & 0xFF00) >> 8) for register in registers]


def shortest_float32(value: float) -> float:
    """The shortest decimal that is stored as the same float32 as ``value``, e.g. 23.4 instead of 23.399999618530273."""
    if value != value or value in (float('inf'), float('-inf')):
        return value
    stored = struct.pack('>f', value)
    for digits in range(1, 10):
        candidate = float(f'{value:.{digits}g}')
        try:
            if struct.pack('>f', candidate) == stored:
                return candidate
        except OverflowError:
            continue
    return value


class _SizedCodec:
    """Base for codecs whose datatype name is ``<family><size>``; subclasses set the class attributes."""

    pattern: ClassVar[re.Pattern[str]]
    sizes: ClassVar[frozenset[int] | None] = None

    def size(self, datatype: str) -> int:
        """Size from the datatype name, 16 when omitted; raises KeyError if the codec doesn't serve it."""
        match = self.pattern.fullmatch(datatype)
        if match is None:
            raise KeyError(datatype)
        size = int(match.group('size')) if match.group('size') else 16
        if size <= 0 or (self.sizes is not None and size not in self.sizes):
            raise KeyError(datatype)
        return size

    def handles(self, datatype: str) -> bool:
        """Whether this codec serves ``datatype``."""
        try:
            self.size(datatype)
        except KeyError:
            return False
        return True

    def invalid(self, datatype: str) -> frozenset[int | float]:
        """No sentinel values."""
        return frozenset()


class NumberCodec(_SizedCodec):
    """Integers (``uint``/``int`` 16, 32, 64) and floats (``float`` 32, 64)."""

    pattern = re.compile(r'(?P<family>uint|int|float)(?P<size>\d+)?')

    _TYPES: ClassVar[dict[tuple[str, int], object]] = {
        ('uint', 16): _DATATYPE.UINT16,
        ('uint', 32): _DATATYPE.UINT32,
        ('uint', 64): _DATATYPE.UINT64,
        ('int', 16): _DATATYPE.INT16,
        ('int', 32): _DATATYPE.INT32,
        ('int', 64): _DATATYPE.INT64,
        ('float', 32): _DATATYPE.FLOAT32,
        ('float', 64): _DATATYPE.FLOAT64,
    }

    _SENTINELS: ClassVar[dict[tuple[str, int], frozenset[int | float]]] = {
        ('int', 16): frozenset({-0x8000}),
        ('int', 32): frozenset({-0x80000000}),
        ('uint', 16): frozenset({0xFFFF}),
        ('uint', 32): frozenset({0xFFFFFFFF}),
        ('uint', 64): frozenset({0xFFFFFFFFFFFFFFFF}),
    }

    def _parse(self, datatype: str) -> tuple[str, int]:
        match = self.pattern.fullmatch(datatype)
        if match is None:
            raise KeyError(datatype)
        family = match.group('family')
        size = int(match.group('size')) if match.group('size') else 16
        if (family, size) not in self._TYPES:
            raise KeyError(datatype)
        return family, size

    def size(self, datatype: str) -> int:
        """Size in bits; raises KeyError for unsupported family/size combinations."""
        return self._parse(datatype)[1]

    def register_count(self, datatype: str) -> int:
        """One register per 16 bits."""
        return self.size(datatype) // 16

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """Number from registers in the spec's byte and word order."""
        family, size = self._parse(spec.datatype)
        if spec.byte_order is Endian.LITTLE:
            registers = swap_bytes(registers)
        value = AsyncModbusTcpClient.convert_from_registers(
            list(registers), self._TYPES[(family, size)], word_order=spec.word_order.value
        )
        if not isinstance(value, (int, float)):
            raise ValueError(f'{spec.datatype}: unexpected decoded value {value!r}')
        return shortest_float32(value) if (family, size) == ('float', 32) else value

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """Registers for a number in the spec's byte and word order."""
        family, size = self._parse(spec.datatype)
        if isinstance(value, (list, str)):
            raise TypeError(f'{spec.datatype}: not a number: {value!r}')
        number: int | float = float(value) if family == 'float' else round(value)
        registers = AsyncModbusTcpClient.convert_to_registers(
            number, self._TYPES[(family, size)], word_order=spec.word_order.value
        )
        return swap_bytes(registers) if spec.byte_order is Endian.LITTLE else list(registers)

    def invalid(self, datatype: str) -> frozenset[int | float]:
        """The minimum of signed and the maximum of unsigned integers (16 to 64 bit)."""
        return self._SENTINELS.get(self._parse(datatype), frozenset())


class StringCodec(_SizedCodec):
    """ASCII strings of ``size`` bytes, two characters per register in the spec's byte order; word order doesn't apply."""

    pattern = re.compile(r'string(?P<size>\d+)?')

    def register_count(self, datatype: str) -> int:
        """One register per two bytes, odd lengths rounded up."""
        return (self.size(datatype) + 1) // 2

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """The string up to ``size`` bytes or the first NUL."""
        if spec.byte_order is Endian.LITTLE:
            registers = swap_bytes(registers)
        raw = b''.join(register.to_bytes(2, 'big') for register in registers)[: self.size(spec.datatype)]
        return raw.split(b'\x00')[0].decode('ascii')

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """Registers holding ``str(value)``, NUL padded to ``size`` bytes."""
        raw = str(value).encode('ascii')
        size = self.size(spec.datatype)
        if len(raw) > size:
            raise ValueError(f'{spec.datatype}: {value!r} is longer than {size} bytes')
        raw = raw.ljust(self.register_count(spec.datatype) * 2, b'\x00')
        registers = [int.from_bytes(raw[i : i + 2], 'big') for i in range(0, len(raw), 2)]
        return swap_bytes(registers) if spec.byte_order is Endian.LITTLE else registers


class BitCodec(_SizedCodec):
    """Bit lists of ``size`` bits packed into registers, most significant bit first."""

    pattern = re.compile(r'bit(?P<size>\d+)?')

    def register_count(self, datatype: str) -> int:
        """One register per 16 bits, rounded up."""
        return (self.size(datatype) + 15) // 16

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """``size`` bits in the spec's byte order."""
        if spec.byte_order is Endian.LITTLE:
            registers = swap_bytes(registers)
        bits = [bool(register & (1 << bit)) for register in registers for bit in range(15, -1, -1)]
        return bits[: self.size(spec.datatype)]

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """Registers for a ``'0'``/``'1'`` string or a list of truth values."""
        if isinstance(value, str):
            if not value or not set(value) <= {'0', '1'}:
                raise ValueError(f'not a bit string: {value!r}')
            bits = [char == '1' for char in value]
        elif isinstance(value, list):
            bits = [bool(bit) for bit in value]
        else:
            raise ValueError(f'not a bit string or bit list: {value!r}')
        count = max(1, (max(self.size(spec.datatype), len(bits)) + 15) // 16)
        bits += [False] * (count * 16 - len(bits))
        registers = [
            sum(1 << (15 - index) for index, bit in enumerate(bits[offset : offset + 16]) if bit)
            for offset in range(0, len(bits), 16)
        ]
        return swap_bytes(registers) if spec.byte_order is Endian.LITTLE else registers


class ByteCodec:
    """``uint8_high``/``uint8_low``: one byte of a register, e.g. two percentages packed into one register."""

    _HALVES: ClassVar[dict[str, int]] = {'uint8_high': 8, 'uint8_low': 0}

    def handles(self, datatype: str) -> bool:
        """Whether ``datatype`` names a register half."""
        return datatype in self._HALVES

    def register_count(self, datatype: str) -> int:
        """Always one register."""
        return 1

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """The byte as unsigned integer, after the spec's byte order is applied."""
        register = swap_bytes(registers[:1])[0] if spec.byte_order is Endian.LITTLE else registers[0]
        return (register >> self._HALVES[spec.datatype]) & 0xFF

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """Not supported: writing one byte would overwrite the other half of the register."""
        raise ValueError(f'{spec.datatype} cannot be written')

    def invalid(self, datatype: str) -> frozenset[int | float]:
        """No sentinel values."""
        return frozenset()


class _Uint32Codec:
    """Base for datatypes stored as one unsigned 32-bit number in the spec's byte and word order."""

    names: ClassVar[frozenset[str]]
    _number: ClassVar[NumberCodec] = NumberCodec()

    def handles(self, datatype: str) -> bool:
        """Whether ``datatype`` is one of ``names``."""
        return datatype in self.names

    def register_count(self, datatype: str) -> int:
        """Always two registers."""
        return 2

    def invalid(self, datatype: str) -> frozenset[int | float]:
        """No sentinel values."""
        return frozenset()

    def _number_spec(self, spec: RegisterSpec) -> RegisterSpec:
        return replace(spec, datatype='uint32')

    def _decode_number(self, registers: Sequence[int], spec: RegisterSpec) -> int:
        return int(self._number.decode(registers, self._number_spec(spec)))

    def _encode_number(self, number: int, spec: RegisterSpec) -> list[int]:
        return self._number.encode(number, self._number_spec(spec))


class Ipv4Codec(_Uint32Codec):
    """``ipv4``: an IPv4 address as dotted quad, most significant byte first."""

    names = frozenset({'ipv4'})

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """Dotted quad of the stored number."""
        return str(ipaddress.IPv4Address(self._decode_number(registers, spec)))

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """Registers of a dotted quad; ValueError if ``value`` is no IPv4 address."""
        return self._encode_number(int(ipaddress.IPv4Address(str(value))), spec)


class TimestampCodec(_Uint32Codec):
    """
    ``datetime32``, ``date32``, ``time32``: seconds since 1970-01-01 as the device's clock.

    Values are naive: no time zone conversion, the device decides what its clock means.
    Only ``datetime32`` can be written.
    """

    names = frozenset({'datetime32', 'date32', 'time32'})

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """Naive datetime, date or time of the stored seconds."""
        moment = datetime.fromtimestamp(self._decode_number(registers, spec), timezone.utc).replace(tzinfo=None)
        if spec.datatype == 'date32':
            return moment.date()
        if spec.datatype == 'time32':
            return moment.time()
        return moment

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """Registers of a naive datetime; TypeError for anything else, ValueError for date32/time32."""
        if spec.datatype != 'datetime32':
            raise ValueError(f'{spec.datatype} cannot be written')
        if not isinstance(value, datetime):
            raise TypeError(f'{spec.datatype}: not a datetime: {value!r}')
        return self._encode_number(int(value.replace(tzinfo=timezone.utc).timestamp()), spec)


class DigitCodec:
    """
    ``hhmm``, ``ddmm``: a time or a day of the year packed as decimal digits into one register.

    ``hhmm``: 1530 is ``'15:30'``; ``ddmm``: 1503 is ``'15.03.'`` (no year). Writes take the same
    text, leading zeros and the trailing dot optional (``'7:45'``, ``'31.12'``).
    """

    _FORMATS: ClassVar[dict[str, tuple[re.Pattern[str], str, range, range]]] = {
        'hhmm': (re.compile(r'(\d{1,2}):(\d{2})'), '{:02d}:{:02d}', range(24), range(60)),
        'ddmm': (re.compile(r'(\d{1,2})\.(\d{1,2})\.?'), '{:02d}.{:02d}.', range(1, 32), range(1, 13)),
    }

    def handles(self, datatype: str) -> bool:
        """Whether ``datatype`` is ``hhmm`` or ``ddmm``."""
        return datatype in self._FORMATS

    def register_count(self, datatype: str) -> int:
        """Always one register."""
        return 1

    def decode(self, registers: Sequence[int], spec: RegisterSpec) -> Value:
        """Text of the register; ValueError if its digits are no valid time or day."""
        _, layout, high, low = self._FORMATS[spec.datatype]
        first, second = divmod(registers[0], 100)
        if first not in high or second not in low:
            raise ValueError(f'{spec.datatype}: {registers[0]} is out of range')
        return layout.format(first, second)

    def encode(self, value: Value, spec: RegisterSpec) -> list[int]:
        """The register of a text in the datatype's format; ValueError for anything else."""
        pattern, _, high, low = self._FORMATS[spec.datatype]
        match = pattern.fullmatch(value) if isinstance(value, str) else None
        if match is None:
            raise ValueError(f'{spec.datatype}: not a valid value: {value!r}')
        first, second = int(match.group(1)), int(match.group(2))
        if first not in high or second not in low:
            raise ValueError(f'{spec.datatype}: {value!r} is out of range')
        return [first * 100 + second]

    def invalid(self, datatype: str) -> frozenset[int | float]:
        """No sentinel values."""
        return frozenset()


class CodecRegistry:
    """Datatype name -> codec; the first registered codec serving a name wins."""

    def __init__(self, codecs: Sequence[Codec] = ()) -> None:
        self._codecs: list[Codec] = list(codecs)

    def register(self, codec: Codec) -> None:
        """Add ``codec`` after the ones registered so far."""
        self._codecs.append(codec)

    def resolve(self, datatype: str) -> Codec:
        """Codec serving ``datatype``; raises KeyError for unknown datatypes."""
        for codec in self._codecs:
            if codec.handles(datatype):
                return codec
        raise KeyError(f'unknown datatype: {datatype!r}')


def default_registry() -> CodecRegistry:
    """Registry with the built-in and the device codecs."""
    return CodecRegistry(
        [
            NumberCodec(),
            StringCodec(),
            BitCodec(),
            ByteCodec(),
            Ipv4Codec(),
            TimestampCodec(),
            DigitCodec(),
            *pluggit.CODECS,
        ]
    )


def decode_available(codecs: CodecRegistry, spec: RegisterSpec, registers: Sequence[int]) -> Value | None:
    """
    Value of a point's registers; None if the device reports "not available" (codec sentinels, ``spec.invalid``).

    :raises KeyError: unknown datatype
    :raises ValueError: registers that don't decode as the datatype (also TypeError, pymodbus exceptions)
    """
    codec = codecs.resolve(spec.datatype)
    value = codec.decode(registers, spec)
    if value in codec.invalid(spec.datatype) or value in spec.invalid:
        return None
    return value


def scale(value: int | float, exponent: int) -> int | float:
    """``value * 10**exponent``, dividing for negative exponents so 1234 * 10**-1 gives 123.4."""
    return value * 10**exponent if exponent >= 0 else value / 10**-exponent


def lookup_read(spec: RegisterSpec, value: Value) -> Value:
    """Item value of a device value through ``spec.lookup``; values not listed pass unchanged."""
    for device_value, item_value in spec.lookup:
        if device_value == value:
            return item_value
    return value


def lookup_write(spec: RegisterSpec, value: Value) -> Value:
    """
    Device value of an item value through ``spec.lookup``.

    Without lookup and for listed device values, ``value`` passes unchanged.

    :raises ValueError: ``value`` is neither a listed item value nor a listed device value
    """
    if not spec.lookup:
        return value
    for device_value, item_value in spec.lookup:
        if item_value == value:
            return device_value
    if any(device_value == value for device_value, _ in spec.lookup):
        return value
    raise ValueError(f'{value!r} is not in the lookup of {spec.key}')


def word_ordered(codecs: CodecRegistry, datatype: str) -> bool:
    """Whether word order applies to ``datatype``: a number stored in more than one register."""
    codec = codecs.resolve(datatype)
    if isinstance(codec, _Uint32Codec):
        return True
    return isinstance(codec, NumberCodec) and codec.register_count(datatype) > 1
