"""
Connections to a Modbus device: which transport, and the pymodbus client for it.

The plugin parameter ``transport`` selects one of the configurations below; ``new_client``
builds the matching pymodbus async client with auto-reconnect disabled (the plugin runs its
own reconnect loop).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

import inspect

from pymodbus import FramerType
from pymodbus.client import AsyncModbusSerialClient, AsyncModbusTcpClient

# pymodbus >= 3.10 renamed the 'slave' keyword argument to 'device_id'
try:
    UNIT_KWARG = (
        'slave' if 'slave' in inspect.signature(AsyncModbusTcpClient.read_holding_registers).parameters else 'device_id'
    )
except Exception:
    UNIT_KWARG = 'slave'


@dataclass(frozen=True)
class TcpTransport:
    """Modbus TCP."""

    host: str
    port: int = 502

    def __str__(self) -> str:
        """``host:port``."""
        return f'{self.host}:{self.port}'


@dataclass(frozen=True)
class RtuOverTcpTransport:
    """Modbus RTU frames (with CRC) through a TCP connection, as serial gateways offer."""

    host: str
    port: int = 502

    def __str__(self) -> str:
        """``host:port (rtu)``."""
        return f'{self.host}:{self.port} (rtu)'


@dataclass(frozen=True)
class RtuSerialTransport:
    """Modbus RTU on a serial port; ``port`` may be a pyserial URL such as ``socket://host:port``."""

    port: str
    baudrate: int = 19200
    parity: Literal['N', 'E', 'O'] = 'N'
    stopbits: int = 1
    bytesize: int = 8

    def __str__(self) -> str:
        """``port baudrate/bytesize parity stopbits``, e.g. ``/dev/ttyUSB0 19200/8N1``."""
        return f'{self.port} {self.baudrate}/{self.bytesize}{self.parity}{self.stopbits}'


TransportConfig = TcpTransport | RtuOverTcpTransport | RtuSerialTransport

ModbusClient = AsyncModbusTcpClient | AsyncModbusSerialClient


def from_parameters(get: Callable[[str], Any]) -> TransportConfig:
    """
    Transport from the plugin parameters.

    :param get: plugin parameter getter (``get_parameter_value``)
    :raises ValueError: if the parameters the transport needs are missing
    """
    kind = get('transport') or 'tcp'
    if kind == 'rtu':
        if not get('serialport'):
            raise ValueError('transport rtu needs the parameter serialport')
        return RtuSerialTransport(
            port=str(get('serialport')),
            baudrate=int(get('baudrate')),
            parity=get('parity'),
            stopbits=int(get('stopbits')),
            bytesize=int(get('bytesize')),
        )
    if not get('host'):
        raise ValueError(f'transport {kind} needs the parameter host')
    cls = RtuOverTcpTransport if kind == 'rtu_over_tcp' else TcpTransport
    return cls(host=str(get('host')), port=int(get('port')))


def new_client(config: TransportConfig) -> ModbusClient:
    """pymodbus async client for ``config``, without built-in reconnect."""
    if isinstance(config, RtuSerialTransport):
        return AsyncModbusSerialClient(
            config.port,
            framer=FramerType.RTU,
            baudrate=config.baudrate,
            parity=config.parity,
            stopbits=config.stopbits,
            bytesize=config.bytesize,
            reconnect_delay=0,
        )
    framer = FramerType.RTU if isinstance(config, RtuOverTcpTransport) else FramerType.SOCKET
    return AsyncModbusTcpClient(config.host, port=config.port, framer=framer, reconnect_delay=0)
