#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 - 2015 KNX-User-Forum e.V.    http://knx-user-forum.de/
#  Copyright 2016 - 2022 Bernd Meiners              Bernd.Meiners@mail.de
#  Copyright 2024 -      Sebastian Helms         morg @ knx-user-forum.de
#########################################################################
#
#  DLMS module for SmartMeter plugin for SmartHomeNG
#
#  This file is part of SmartHomeNG.py.
#  Visit:  https://github.com/smarthomeNG/
#          https://knx-user-forum.de/forum/supportforen/smarthome-py
#          https://smarthomeng.de
#
#  SmartHomeNG.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import asyncio
import logging
import time
import serial
try:
    import serial_asyncio
    ASYNC_IMPORTED = True
except ImportError:
    ASYNC_IMPORTED = False
import socket  # not needed, just for code portability

from ruamel.yaml import YAML
from smllib import const as smlConst
from threading import Lock
from typing import (Union, Tuple, Any)

# only for syntax/type checking
try:
    from lib.model.smartplugin import SmartPlugin
except ImportError:
    class SmartPlugin():
        pass

    class SmartPluginWebIf():
        pass


"""
This module implements the query of a smartmeter using the DLMS protocol.
The smartmeter needs to have an infrared interface and an IR-Adapter is needed for USB.

The Character Format for protocol mode A - D is defined as 1 start bit, 7 data bits, 1 parity bit, 1 stop bit and even parity
In protocol mode E it is defined as 1 start bit, 8 data bits, 1 stop bit is allowed, see Annex E of IEC62056-21
For this plugin the protocol mode E is neither implemented nor supported.

Abbreviations
-------------
COSEM
   COmpanion Specification for Energy Metering

OBIS
   OBject Identification System (see iec62056-61{ed1.0}en_obis_protocol.pdf)

"""

#
# protocol constants
#

SOH = 0x01  # start of header
STX = 0x02  # start of text
ETX = 0x03  # end of text
ACK = 0x06  # acknowledge
CR = 0x0D  # carriage return
LF = 0x0A  # linefeed
BCC = 0x00  # Block check Character will contain the checksum immediately following the data packet

OBIS_NAMES = {
    **smlConst.OBIS_NAMES,
    '010000020000': 'Firmware Version, Firmware Prüfsumme CRC, Datum',
    '0100010800ff': 'Bezug Zählerstand Total',
    '0100010801ff': 'Bezug Zählerstand Tarif 1',
    '0100010802ff': 'Bezug Zählerstand Tarif 2',
    '0100011100ff': 'Total-Zählerstand',
    '0100020800ff': 'Einspeisung Zählerstand Total',
    '0100020801ff': 'Einspeisung Zählerstand Tarif 1',
    '0100020802ff': 'Einspeisung Zählerstand Tarif 2',
    '0100600100ff': 'Server-ID',
    '010060320101': 'Hersteller-Identifikation',
    '0100605a0201': 'Prüfsumme',
}

# serial config
S_BITS = serial.SEVENBITS
S_PARITY = serial.PARITY_EVEN
S_STOP = serial.STOPBITS_ONE


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.debug(f"init standalone {__name__}")
else:
    logger = logging.getLogger(__name__)
    logger.debug(f"init plugin component {__name__}")


manufacturer_ids = {}
exportfile = 'manufacturer.yaml'
try:
    with open(exportfile, 'r') as infile:
        y = YAML(typ='safe')
        manufacturer_ids = y.load(infile)
except Exception:
    pass


#
# internal testing
#
TESTING = False
# TESTING = True

if TESTING:
    if __name__ == '__main__':
        from dlms_test import RESULT
    else:
        from .dlms_test import RESULT
    logger.error('DLMS testing mode enabled, no serial communication, no real results!')
else:
    RESULT = ''


#
# start module code
#


def hex_obis(code: str) -> str:
    """ convert obis to hex """

    # form x.x.x.x.x.x from x-x:x.x.x*x
    l1 = code.replace(':', '.').replace('-', '.').replace('*', '.').split('.')
    # fill missing fields
    if len(l1) in (3, 5):
        l1 = l1 + ['255']
    if len(l1) == 4:
        l1 = ['1', '0'] + l1

    # fix for DLMS testing, codes from SmlLib all have pattern '1-0:x.y.z*255'
    l1[1] = '0'

    # convert to string, take care for letters instead of numbers
    return ''.join(['{:02x}'.format(x) for x in [int(y) if y.isnumeric() else ord(y) for y in (l1)]])


def normalize_unit(value: Union[int, float], unit: str) -> Tuple[Union[int, float], str]:
    """ normalize units, i.e. remove prefixes and recalculate value """
    # in this environment, smaller or larger prefixes don't seem sensible...
    _prefix = {
        'u': 1e-6,   # micro
        'm': 1e-3,   # mili
        'c': 1e-2,   # centi
        'd': 1e-1,   # deci
        'k': 1e3,    # kilo
        'M': 1e6,    # mega
        'G': 1e9,    # giga
    }

    nval = value
    nunit = unit

    for p in _prefix:
        if unit.startswith(p):
            nunit = unit[1:]
            nval = nval * _prefix[p]
            break

    # check if we made a float without necessity...
    if unit != nunit and type(value) is int and type(nval) is float and _prefix[unit[0]] > 1:
        nval = int(nval)

    return nval, nunit


def get_unit_code(value: Any, unit: str, normalize: bool = True) -> Tuple[Any, str, Union[int, None]]:
    """
    try to get unit code for u from sml Units. If normalize is set, first try to
    normalize value/unit.
    As SML only lists base units, prefixes units like kW or MWh don't match
    the value/unit pair for prefixed units and we don't return unit codes that
    need normalizing.
    """
    unit_code = None

    # check if value is numeric
    x = None
    try:
        x = float(value)
    except Exception:
        pass
    try:
        x = int(value)
    except Exception:
        pass

    # only check for numeric values...
    if type(x) in (int, float) and unit:
        if normalize:
            value, unit = normalize_unit(x, unit)
        if unit in smlConst.UNITS.values():
            unit_code = list(smlConst.UNITS.keys())[list(smlConst.UNITS.values()).index(unit)]

    return value, unit, unit_code


def format_time(timedelta: float) -> str:
    """
    returns a pretty formatted string according to the size of the timedelta
    :param timediff: time delta given in seconds
    :return: returns a string
    """
    if timedelta > 1000:
        return f"{timedelta:.2f} s"
    elif timedelta > 1:
        return f"{timedelta:.2f} s"
    elif timedelta > 1 / 10 ** 3:
        return f"{timedelta * 10 ** 3 :.2f} ms"
    elif timedelta > 1 / 10 ** 6:
        return f"{timedelta * 10 ** 6:.2f} µs"
    else:
        return f"{timedelta * 10 ** 9:.2f} ns"


# TODO: asyncio for DLMS disabled until real testing has succeeded
# #
# # asyncio reader
# #
# 
# 
# class AsyncReader():
# 
#     def __init__(self, logger, plugin: SmartPlugin, config: dict):
#         self.buf = bytes()
#         self.logger = logger
#         self.lock = config['lock']
# 
#         if not ASYNC_IMPORTED:
#             raise ImportError('pyserial_asyncio not installed, running asyncio not possible.')
# 
#         if 'serial_port' not in config:
#             raise ValueError(f'configuration {config} is missing serial port config')
# 
#         self.serial_port = config.get('serial_port')
#         self.timeout = config.get('timeout', 2)
#         self.baudrate = config.get('baudrate', 300)
#         if not config['dlms'].get('only_listen', False):
#             self.logger.warning('asyncio operation can only listen, smartmeter will not be triggered!')
# 
#         self.target = '(not set)'
#         self.listening = False
#         self.reader = None
# 
#         self.config = config
#         self.transport = None
#         self.protocol = DlmsProtocol(logger, config)
# 
#         # set from plugin
#         self.plugin = plugin
#         self.data_callback = plugin._update_values
# 
#     async def listen(self):
#         result = self.lock.acquire(blocking=False)
#         if not result:
#             self.logger.error('couldn\'t acquire lock, polling/manual access active?')
#             return
# 
#         self.logger.debug('acquired lock')
#         try:  # LOCK
#             self.reader, _ = await serial_asyncio.open_serial_connection(
#                 url=self.serial_port,
#                 baudrate=self.baudrate,
#                 bytesize=S_BITS,
#                 parity=S_PARITY,
#                 stopbits=S_STOP,
#             )
#             self.target = f'async_serial://{self.serial_port}'
#             self.logger.debug(f'target is {self.target}')
# 
#             if self.reader is None and not TESTING:
#                 self.logger.error('error on setting up async listener, reader is None')
#                 return
# 
#             self.plugin.connected = True
#             self.listening = True
#             self.logger.debug('starting to listen')
# 
#             buf = bytes()
# 
#             while self.listening and self.plugin.alive:
# 
#                 if TESTING:
#                     # make this bytes...
#                     data = RESULT.encode()
#                 else:
#                     data = await self.reader.readuntil(b'!')
# 
#                 # check we got a start byte if buf is empty
#                 if len(buf) == 0:
#                     if b'/' not in data:
#                         self.logger.warning('incomplete data received, no start byte, discarding')
#                         continue
#                     else:
#                         # trim data to start byte
#                         data = data[data.find(b'/'):]
# 
#                 # add data to buffer
#                 buf += data
# 
#                 # check if we have an end byte
#                 if b'!' not in buf:
#                     if len(buf) > 100000:
#                         self.logger.warning(f'got {len(buf)} characters without end byte, discarding data')
#                         buf = bytes()
#                     continue
# 
#                 # get data from start (b'/') to end (b'!') into data
#                 # leave the remainder in buf
#                 data, _, buf = buf.partition(b'!')
# 
#                 # we should have data beginning with b'/' and ending with b'!'
#                 identification_message = str(data, 'utf-8').splitlines()[0]
#                 manid = identification_message[1:4]
#                 manname = manufacturer_ids.get(manid, 'unknown')
#                 self.logger.debug(f"manufacturer for {manid} is {manname} (out of {len(manufacturer_ids)} given manufacturers)")
# 
#                 response = self.protocol(data.decode())
# 
#                 # get data from frameparser and call plugin
#                 if response and self.data_callback:
#                     self.data_callback(response)
# 
#         finally:
#             # cleanup
#             try:
#                 self.reader.feed_eof()
#             except Exception:
#                 pass
#             self.plugin.connected = False
#             self.lock.release()
# 
#     async def stop_on_queue(self):
#         """ wait for STOP in queue and signal reader to terminate """
#         self.logger.debug('task waiting for STOP from queue...')
#         await self.plugin. wait_for_asyncio_termination()
#         self.logger.debug('task received STOP, halting listener')
#         self.listening = False
#
# TODO end

#
# single-shot reader
#


class DlmsReader():
    """
    read data from DLMS meter

    open/handle serial connection and provide read/write methods
    use DlmsProtocol for parsing data
    """
    def __init__(self, logger, config: dict, discover: bool = False):
        self.config = config
        self.sock = None
        self.lock = config['lock']
        self.logger = logger
        self.discover = discover
        self.protocol = DlmsProtocol(logger, config)
        self.target = '(not set)'

        if not ('serial_port' in config or ('host' in config and 'port' in config)):
            raise ValueError(f'configuration {config} is missing source config (serialport or host and port)')

        if not config.get('poll') and not ASYNC_IMPORTED:
            raise ValueError('async configured but pyserial_asyncio not imported. Aborting.')

    def __call__(self) -> dict:
        return self.read()

    def read(self) -> dict:
        #
        # open the serial communication
        #

        starttime = time.time()

        locked = self.lock.acquire(blocking=False)
        if not locked:
            self.logger.error('could not get lock for serial access. Is another scheduled/manual action still active?')
            return {}

        try:  # lock release

            self.get_sock()
            if not self.sock:
                # error already logged, just go
                return {}

            if isinstance(self.sock, socket.socket):
                self.logger.error(f'network reading not yet implemented for DLMS at {self.target}')
                return {}

            self.protocol.set_methods(self.read_data_block_from_serial, self.sock.write, self.target, self.sock)

            runtime = time.time()
            self.logger.debug(f"time to open {self.target}: {format_time(time.time() - runtime)}")

            response = self.protocol()

            try:
                self.sock.close()
            except Exception:
                pass
        except Exception:
            # passthrough, this is only for releasing the lock
            raise
        finally:
            try:
                self.sock.close()
                self.logger.debug(f'{self.target} closed')
            except Exception:
                pass
            self.lock.release()

        self.logger.debug(f"time for reading OBIS data: {format_time(time.time() - runtime)}")
        runtime = time.time()

        # Display performance of the serial communication
        self.logger.debug(f"whole communication with smartmeter took {format_time(time.time() - starttime)}")

        return response

    def read_data_block_from_serial(self, end_byte: bytes = b'\n', start_byte: bytes = b'') -> bytes:
        """
        This function reads some bytes from serial interface
        it returns an array of bytes if a timeout occurs or a given end byte is encountered
        and otherwise None if an error occurred

        If global var TESTING is True, only pre-stored data will be returned to test further processing!

        :param the_serial: interface to read from
        :param end_byte: the indicator for end of data, this will be included in response
        :param start_byte: the indicator for start of data, this will be included in response
        :param max_read_time: maximum time after which to stop reading even if data is still sent
        :returns the read data or None
        """
        if TESTING:
            return RESULT.encode()

        # in discover mode, stop trying after 20 secs
        # reading SML yields bytes, but doesn't trigger returning data
        self.logger.debug(f"start to read data from serial device, start is {start_byte}, end is '{end_byte}, time is 20")
        response = bytes()
        starttime = time.time()
        start_found = False
        end_bytes = 0
        ch = bytes()
        try:
            # try to stop looking if 10 end bytes were found but no start bytes
            while not discover or end_bytes < 10:
                ch = self.sock.read()
                # logger.debug(f"Read {ch}")
                runtime = time.time()
                if len(ch) == 0:
                    break
                if start_byte != b'':
                    if ch == start_byte:
                        self.logger.debug('start byte found')
                        end_bytes = 0
                        response = bytes()
                        start_found = True
                response += ch
                if ch == end_byte:
                    end_bytes += 1
                    self.logger.debug(f'end byte found ({end_bytes})')
                    if start_byte is not None and not start_found:
                        response = bytes()
                        continue
                    else:
                        break
                if (response[-1] == end_byte):
                    self.logger.debug('end byte at end of response found')
                    end_bytes = 0
                    break
                if self.discover:
                    if runtime - starttime > 20:
                        logger.debug('max read time reached')
                        break
        except Exception as e:
            self.logger.debug(f"error occurred while reading data block from serial: {e} ")
            return b''
        self.logger.debug(f"finished reading data from serial device after {len(response)} bytes")
        return response

    def get_sock(self):
        """ open serial or network socket """
        self.sock = None
        self.target = '(not set)'
        serial_port = self.config.get('serial_port')
        host = self.config.get('host')
        port = self.config.get('port')
        timeout = self.config.get('timeout', 2)
        baudrate = self.config.get('DLMS', {'baudate_min': 300}).get('baudrate_min', 300)

        if TESTING:
            self.target = '(test input)'
            return

        if serial_port:
            #
            # open the serial communication
            #
            try:  # open serial
                self.sock = serial.Serial(
                    serial_port,
                    baudrate,
                    S_BITS,
                    S_PARITY,
                    S_STOP,
                    timeout=timeout
                )
                if not serial_port == self.sock.name:
                    logger.debug(f"Asked for {serial_port} as serial port, but really using now {sock.name}")
                self.target = f'serial://{self.sock.name}'

            except FileNotFoundError:
                self.logger.error(f"Serial port '{serial_port}' does not exist, please check your port")
                self.sock = None
                return
            except serial.SerialException:
                if self.sock is None:
                    self.logger.error(f"Serial port '{serial_port}' could not be opened")
                else:
                    self.logger.error(f"Serial port '{serial_port}' could be opened but somehow not accessed")
                    self.sock = None
                return
            except OSError:
                self.logger.error(f"Serial port '{serial_port}' does not exist, please check the spelling")
                self.sock = None
                return
            except Exception as e:
                self.logger.error(f"unforeseen error occurred: '{e}'")
                self.sock = None
                return

            if self.sock is None:
                # this should not happen...
                logger.error("unforeseen error occurred, serial object was not initialized.")
                return

            if not self.sock.is_open:
                logger.error(f"serial port '{serial_port}' could not be opened with given parameters, maybe wrong baudrate?")
                self.sock = None
                return

        elif host:
            #
            # open network connection
            #
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(2)
            self.sock.connect((host, port))
            self.sock.setblocking(False)
            self.target = f'tcp://{host}:{port}'

        else:
            self.logger.error('neither serialport nor host/port was given, no action possible.')
            self.sock = None
            return


class DlmsProtocol():
    """ read and parse DLMS readout, if necessary, trigger meter to send data """

    def __init__(self, logger, config):
        self.logger = logger
        self._read = self.__read
        self._write = self.__write
        self.sock = None
        self.target = ''

        try:
            self.device = config['dlms']['device']
            self.initial_baudrate = config['dlms']['baudrate_min']
            self.query_code = config['dlms']['querycode']
            self.use_checksum = config['dlms']['use_checksum']
            self.only_listen = config['dlms'].get('only_listen', False)    # just for the case that smartmeter transmits data without a query first
            self.normalize = config['dlms'].get('normalize', True)
        except (KeyError, AttributeError) as e:
            self.logger.warning(f'configuration {config} is missing elements: {e}')

    def __read(self, end_byte: bytes = b'\n', start_byte: bytes = b'') -> bytes:
        """ dummy stub to prevent errors """
        self.logger.warning('self._read called without setting method - please check!')
        return b''

    def __write(self, data):
        """ dummy stub to prevent errors """
        self.logger.warning('self._write called without setting method - please check!')

    def set_methods(self, read, write, target: str = '', sock=None):
        self.logger.debug(f'setting methods {read} / {write} with sock {sock} for {target}')
        self._read = read
        self._write = write
        self.target = target
        self.sock = sock

    def __call__(self, data: str = '') -> dict:
        if not data:
            r_bytes = self.read_data()
            if not r_bytes:
                return {}
            data = self.check_protocol(r_bytes)
            if not data:
                return {}
        r_dict = self.parse(data)
        return r_dict

    def read_data(self) -> bytes:
        #
        # read data from device
        #

        runtime = time.time()

        # about timeout: time tr between sending a request and an answer needs to be
        # 200ms < tr < 1500ms for protocol mode A or B
        # inter character time must be smaller than 1500 ms
        # The time between the reception of a message and the transmission of an answer is:
        # (20 ms) 200 ms = tr = 1 500 ms (see item 12) of 6.3.14).
        # If a response has not been received, the waiting time of the transmitting equipment after
        # transmission of the identification message, before it continues with the transmission, is:
        # 1 500 ms < tt = 2 200 ms
        # The time between two characters in a character sequence is:
        # ta < 1 500 ms
        wait_before_acknowledge = 0.4   # wait for 400 ms before sending the request to change baudrate
        wait_after_acknowledge = 0.4    # wait for 400 ms after sending acknowledge
        start_char = b'/'
        request_message = b"/" + self.query_code.encode('ascii') + self.device.encode('ascii') + b"!\r\n"

        if not self.only_listen:
            response = b''

            # start a dialog with smartmeter
            try:
                self.logger.debug(f"writing request message {request_message} to serial port '{self.target}'")
                self._write(request_message)
            except Exception as e:
                self.logger.warning(f"error on serial write: {e}")
                return b''

            logger.debug(f"time to send first request to smartmeter: {format_time(time.time() - runtime)}")

            # now get first response
            response = self._read()
            if not response:
                self.logger.debug("no response received upon first request")
                return b''

            self.logger.debug(f"time to receive an answer: {format_time(time.time() - runtime)}")
            runtime = time.time()

            # We need to examine the read response here for an echo of the _Request_Message
            # some meters answer with an echo of the request Message
            if response == request_message:
                self.logger.debug("request message was echoed, need to read the identification message")
                # now read the capabilities and type/brand line from Smartmeter
                # e.g. b'/LGZ5\\2ZMD3104407.B32\r\n'
                response = self._read()
            else:
                self.logger.debug("request message was not equal to response, treating as identification message")

            self.logger.debug(f"time to get first identification message from smartmeter: {format_time(time.time() - runtime)}")
            runtime = time.time()

            identification_message = response
            self.logger.debug(f"identification message is {identification_message}")

            # need at least 7 bytes:
            # 1 byte "/"
            # 3 bytes short Identification
            # 1 byte speed indication
            # 2 bytes CR LF
            if len(identification_message) < 7:
                self.logger.warning(f"malformed identification message: '{identification_message}', abort query")
                return b''

            if (identification_message[0] != start_char):
                self.logger.warning(f"identification message '{identification_message}' does not start with '/', abort query")
                return b''

            manid = str(identification_message[1:4], 'utf-8')
            manname = manufacturer_ids.get(manid, 'unknown')
            self.logger.debug(f"manufacturer for {manid} is {manname} ({len(manufacturer_ids)} manufacturers known)")

            # Different smartmeters allow for different protocol modes.
            # The protocol mode decides whether the communication is fixed to a certain baudrate or might be speed up.
            # Some meters do initiate a protocol by themselves with a fixed speed of 2400 baud e.g. Mode D
            # However some meters specify a speed of 9600 Baud although they use protocol mode D (readonly)
            #
            # protocol_mode = 'A'
            #
            # The communication of the plugin always stays at the same speed,
            # Protocol indicator can be anything except for A-I, 0-9, /, ?
            #
            baudrates = {
                # mode A
                '': (300, 'A'),
                # mode B
                'A': (600, 'B'),
                'B': (1200, 'B'),
                'C': (2400, 'B'),
                'D': (4800, 'B'),
                'E': (9600, 'B'),
                'F': (19200, 'B'),
                # mode C & E
                '0': (300, 'C'),
                '1': (600, 'C'),
                '2': (1200, 'C'),
                '3': (2400, 'C'),
                '4': (4800, 'C'),
                '5': (9600, 'C'),
                '6': (19200, 'C'),
            }

            baudrate_id = chr(identification_message[4])
            if baudrate_id not in baudrates:
                baudrate_id = ''
            new_baudrate, protocol_mode = baudrates[baudrate_id]

            logger.debug(f"baudrate id is '{baudrate_id}' thus protocol mode is {protocol_mode} and suggested Baudrate is {new_baudrate} Bd")

            if chr(identification_message[5]) == '\\':
                if chr(identification_message[6]) == '2':
                    self.logger.debug("HDLC protocol could be used if it was implemented")
                else:
                    self.logger.debug(f"another protocol could probably be used if it was implemented, id is {identification_message[6]}")

            # for protocol C or E we now send an acknowledge and include the new baudrate parameter
            # maybe todo
            # we could implement here a baudrate that is fixed to somewhat lower speed if we need to
            # read out a smartmeter with broken communication
            action = b'0'  # Data readout, possible are also b'1' for programming mode or some manufacturer specific
            acknowledge = b'\x060' + baudrate_id.encode() + action + b'\r\n'

            if protocol_mode == 'C':
                # the speed change in communication is initiated from the reading device
                time.sleep(wait_before_acknowledge)
                self.logger.debug(f"using protocol mode C, send acknowledge {acknowledge} and tell smartmeter to switch to {new_baudrate} baud")
                try:
                    self._write(acknowledge)
                except Exception as e:
                    self.logger.warning(f"error on sending baudrate change: {e}")
                    return b''
                time.sleep(wait_after_acknowledge)
                # dlms_serial.flush()
                # dlms_serial.reset_input_buffer()
                if (new_baudrate != self.initial_baudrate):
                    # change request to set higher baudrate
                    self.sock.baudrate = new_baudrate

            elif protocol_mode == 'B':
                # the speed change in communication is initiated from the smartmeter device
                time.sleep(wait_before_acknowledge)
                self.logger.debug(f"using protocol mode B, smartmeter and reader will switch to {new_baudrate} baud")
                time.sleep(wait_after_acknowledge)
                # dlms_serial.flush()
                # dlms_serial.reset_input_buffer()
                if (new_baudrate != self.initial_baudrate):
                    # change request to set higher baudrate
                    self.sock.baudrate = new_baudrate
            else:
                self.logger.debug(f"no change of readout baudrate, smartmeter and reader will stay at {new_baudrate} baud")

            # now read the huge data block with all the OBIS codes
            self.logger.debug("Reading OBIS data from smartmeter")
            response = self._read()
        else:
            # only listen mode, starts with / and last char is !
            # data will be in between those two
            response = self._read(b'!', b'/')

            try:
                identification_message = str(response, 'utf-8').splitlines()[0]
                manid = identification_message[1:4]
                manname = manufacturer_ids.get(manid, 'unknown')
                self.logger.debug(f"manufacturer for {manid} is {manname} (out of {len(manufacturer_ids)} given manufacturers)")
            except Exception as e:
                self.logger.info(f'error while extracting manufacturer: {e}')

        return response

    def split_header(self, readout: str, break_at_eod: bool = True) -> list:
        """if there is an empty line at second position within readout then seperate this"""
        has_header = False
        obis = []
        endofdata_count = 0
        for linecount, line in enumerate(readout.splitlines()):
            if linecount == 0 and line.startswith("/"):
                has_header = True
                continue

            # an empty line separates the header from the codes, it must be suppressed here
            if len(line) == 0 and linecount == 1 and has_header:
                continue

            # if there is an empty line other than directly after the header
            # it is very likely that there is a faulty obis readout.
            # It might be that checksum is disabled an thus no error could be catched
            if len(line) == 0:
                self.logger.error("incorrect format: empty line was encountered unexpectedly, aborting!")
                break

            # '!' as single OBIS code line means 'end of data'
            if line.startswith("!"):
                self.logger.debug("end of data reached")
                if endofdata_count:
                    self.logger.debug(f"found {endofdata_count} end of data marker '!' in readout")
                    if break_at_eod:    # omit the rest of data here
                        break
                endofdata_count += 1
            else:
                obis.append(line)
        return obis

    def check_protocol(self, data: bytes) -> Union[str, None]:
        """ check for proper protocol handling """
        acknowledge = b''   # preset empty answer

        if data.startswith(acknowledge):
            if not self.only_listen:
                self.logger.debug("acknowledge echoed from smartmeter")
                data = data[len(acknowledge):]

        if self.use_checksum:
            # data block in response may be capsuled within STX and ETX to provide error checking
            # thus the response will contain a sequence of
            # STX Datablock ! CR LF ETX BCC
            # which means we need at least 6 characters in response where Datablock is empty
            self.logger.debug("trying now to calculate a checksum")

            if data[0] == STX:
                self.logger.debug("STX found")
            else:
                self.logger.warning(f"STX not found in response='{' '.join(hex(i) for i in data[:10])}...'")

            if data[-2] == ETX:
                self.logger.debug("ETX found")
            else:
                self.logger.warning(f"ETX not found in response='...{' '.join(hex(i) for i in data[-11:])}'")

            if (len(data) > 5) and (data[0] == STX) and (data[-2] == ETX):
                # perform checks (start with char after STX, end with ETX including, checksum matches last byte (BCC))
                BCC = data[-1]
                self.logger.debug(f"block check character BCC is {BCC}")
                checksum = 0
                for i in data[1:-1]:
                    checksum ^= i
                if checksum != BCC:
                    self.logger.warning(f"checksum/protocol error: response={' '.join(hex(i) for i in data[1:-1])}, checksum={checksum}")
                    return
                else:
                    self.logger.debug("checksum over data response was ok, data is valid")
            else:
                self.logger.warning("STX - ETX not found")
        else:
            self.logger.debug("checksum calculation skipped")

        if not self.only_listen:
            if len(data) > 5:
                res = str(data[1:-4], 'ascii')
            else:
                self.logger.debug("response did not contain enough data for OBIS decode")
                return
        else:
            res = str(data, 'ascii')

        return res

    def parse(self, data: str) -> dict:
        """ parse data returned from device read """

        runtime = time.time()
        result = {}
        obis = self.split_header(data)

        try:
            for line in obis:
                # Now check if we can split between values and OBIS code
                arguments = line.split('(')
                if len(arguments) == 1:
                    # no values found at all; that seems to be a wrong OBIS code line then
                    arguments = arguments[0]
                    values = ""
                    self.logger.warning(f"OBIS code line without data item: {line}")
                else:
                    # ok, found some values to the right, lets isolate them
                    values = arguments[1:]
                    code = arguments[0]
                    name = OBIS_NAMES.get(hex_obis(code))
                    content = []
                    for s in values:
                        s = s.replace(')', '')
                        if len(s) > 0:
                            # we now should have a list with values that may contain a number
                            # separated from a unit by a '*' or a date
                            # so see, if there is an '*' within
                            vu = s.split('*')
                            if len(vu) > 2:
                                self.logger.error(f"too many '*' found in '{s}' of '{line}'")
                            elif len(vu) == 2:
                                # just a value and a unit
                                v = vu[0]
                                u = vu[1]

                                # normalize SI units if possible to return values analogue to SML (e.g. Wh instead of kWh)
                                v, u, uc = get_unit_code(v, u, self.normalize)

                                values = {
                                    'value': v,
                                    'valueRaw': v,
                                    'obis': code,
                                    'unit': u
                                }
                                if uc:
                                    values['unitCode'] = uc
                                if name:
                                    values['name'] = name
                                content.append(values)
                            else:
                                # just a value, no unit
                                v = vu[0]
                                values = {
                                    'value': v,
                                    'valueRaw': v,
                                    'obis': code
                                }
                                if name:
                                    values['name'] = name
                                content.append(values)
                    # uncomment the following line to check the generation of the values dictionary
                    # logger.dbghigh(f"{line:40} ---> {content}")
                    result[code] = content
                    self.logger.debug(f"found {code} with {content}")
            self.logger.debug("finished processing lines")
        except Exception as e:
            self.logger.debug(f"error while extracting data: '{e}'")

        self.logger.debug(f"parsing OBIS codes took {format_time(time.time() - runtime)}")
        return result


def query(config, discover: bool = False) -> Union[dict, None]:
    """
    This function will
    1. open a serial communication line to the smartmeter
    2. sends a request for info
    3. parses the devices first (and maybe second) answer for capabilities of the device
    4. adjusts the speed of the communication accordingly
    5. reads out the block of OBIS information
    6. closes the serial communication
    7. strip header lines from returned data
    8. extract obis data and format return dict

    config contains a dict with entries for
    'serial_port', 'device' and a sub-dict 'dlms' with entries for
    'querycode', 'baudrate', 'baudrate_fix', 'timeout', 'only_listen', 'use_checksum'

    return: a dict with the response data formatted as follows:
        {
            'readout': <full readout lines>,
            '<obis1>': [{'value': <val0>, (optional) 'unit': '<unit0>'}, {'value': <val1>', 'unit': '<unit1>'}, ...],
            '<obis2>': [...],
            ...
        }

    The obis lines contain at least one value (index 0), possibly with a unit, and possibly more values in analogous format
    """

    # for the performance of the serial read we need to save the current time
    starttime = time.time()

    reader = DlmsReader(logger, config, discover)
    response = reader()

    if not response:
        return

    suggested_cycle = (time.time() - starttime) + 10.0
    config['suggested_cycle'] = suggested_cycle
    logger.debug(f"the whole query took {format_time(time.time() - starttime)}, suggested cycle thus is at least {format_time(suggested_cycle)}")

    return response


def discover(config: dict) -> bool:
    """ try to autodiscover DLMS protocol """

    # as of now, this simply tries to query the meter
    # called from within the plugin, the parameters are either manually set by
    # the user, or preset by the plugin.yaml defaults.
    # If really necessary, the query could be called multiple times with
    # reduced baud rates or changed parameters, but there would need to be
    # the need for this.
    # For now, let's see how well this works...
    result = query(config, discover=True)

    # result should have one key 'readout' with the full answer and a separate
    # key for every read OBIS code. If no OBIS codes are read/converted, we can
    # not be sure this is really DLMS, so we check for at least one OBIS code.
    if result:
        return len(result) > 1
    else:
        return False


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Query a smartmeter at a given port for DLMS output',
                                     usage='use "%(prog)s --help" for more information',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('port', help='specify the port to use for the smartmeter query, e.g. /dev/ttyUSB0 or /dev/dlms0')
    parser.add_argument('-v', '--verbose', help='print verbose information', action='store_true')
    parser.add_argument('-t', '--timeout', help='maximum time to wait for a message from the smartmeter', type=float, default=3.0)
    parser.add_argument('-b', '--baudrate', help='initial baudrate to start the communication with the smartmeter', type=int, default=300)
    parser.add_argument('-d', '--device', help='give a device address to include in the query', default='')
    parser.add_argument('-q', '--querycode', help='define alternative query code\ndefault query code is ?\nsome smartmeters provide additional information when sending\nan alternative query code, e.g. 2 instead of ?', default='?')
    parser.add_argument('-l', '--onlylisten', help='only listen to serial, no active query', action='store_true')
    parser.add_argument('-f', '--baudrate_fix', help='keep baudrate speed fixed', action='store_false')
    parser.add_argument('-c', '--nochecksum', help='don\'t use a checksum', action='store_false')
    parser.add_argument('-n', '--normalize', help='convert units to base units and recalculate value', action='store_true')

    args = parser.parse_args()

    # complete default dict
    config = {
        'lock': Lock(),
        'serial_port': '',
        'host': '',
        'port': 0,
        'connection': '',
        'timeout': 2,
        'baudrate': 9600,
        'dlms': {
            'device': '',
            'querycode': '?',
            'baudrate_min': 300,
            'use_checksum': True,
            'onlylisten': False,
            'normalize': True
        },
        'sml': {
            'buffersize': 1024
        }
    }

    config['serial_port'] = args.port
    config['timeout'] = args.timeout
    config['dlms']['querycode'] = args.querycode
    config['dlms']['baudrate_min'] = args.baudrate
    config['dlms']['baudrate_fix'] = args.baudrate_fix
    config['dlms']['only_listen'] = args.onlylisten
    config['dlms']['use_checksum'] = args.nochecksum
    config['dlms']['device'] = args.device
    config['dlms']['normalize'] = args.normalize

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        # create formatter and add it to the handlers
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s  @ %(lineno)d')
        # formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logging.getLogger().addHandler(ch)
    else:
        logging.getLogger().setLevel(logging.INFO)
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        # just like print
        formatter = logging.Formatter('%(message)s')
        ch.setFormatter(formatter)
        # add the handlers to the logger
        logging.getLogger().addHandler(ch)

    logger.info("This is Smartmeter Plugin, DLMS module, running in standalone mode")
    logger.info("==================================================================")

    result = query(config)

    if not result:
        logger.info(f"No results from query, maybe a problem with the serial port '{config['serial_port']}' given.")
    elif len(result) > 1:
        logger.info("These are the processed results of the query:")
        try:
            del result['readout']
        except KeyError:
            pass
        try:
            import pprint
        except ImportError:
            txt = str(result)
        else:
            txt = pprint.pformat(result, indent=4)
        logger.info(txt)
    elif len(result) == 1:
        logger.info("The results of the query could not be processed; raw result is:")
        logger.info(result)
    else:
        logger.info("The query did not get any results. Maybe the serial port was occupied or there was an error.")
