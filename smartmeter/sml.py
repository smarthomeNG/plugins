#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 - 2015 KNX-User-Forum e.V.    http://knx-user-forum.de/
#  Copyright 2022        Julian Scholle     julian.scholle@googlemail.com
#  Copyright 2024 -      Sebastian Helms         morg @ knx-user-forum.de
#########################################################################
#
#  SML module for SmartMeter plugin for SmartHomeNG
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


__license__ = "GPL"
__version__ = "2.0"
__revision__ = "0.1"
__docformat__ = 'reStructuredText'

import errno
import logging
import serial
import socket
import time
import traceback

from smllib.reader import SmlStreamReader
from smllib import const as smlConst
from threading import Lock
from typing import Union


"""
This module implements the query of a smartmeter using the SML protocol.
The smartmeter needs to have an infrared interface and an IR-Adapter is needed for USB.

Abbreviations
-------------
OBIS
   OBject Identification System (see iec62056-61{ed1.0}en_obis_protocol.pdf)
"""


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
S_BITS = serial.EIGHTBITS
S_PARITY = serial.PARITY_NONE
S_STOP = serial.STOPBITS_ONE


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.debug(f"init standalone {__name__}")
else:
    logger = logging.getLogger(__name__)
    logger.debug(f"init plugin component {__name__}")


#
# internal testing
#
TESTING = False
# TESTING = True

if TESTING:
    if __name__ == '__main__':
        from sml_test import RESULT
    else:
        from .sml_test import RESULT
    logger.error('SML testing mode enabled, no serial communication, no real results!')
else:
    RESULT = b''


#
# start module code
#


def to_hex(data: Union[int, str, bytes, bytearray], space: bool = True) -> str:
    """
    Returns the hex representation of the given data
    """
    if isinstance(data, int):
        return hex(data)

    if isinstance(data, str):
        if space:
            return " ".join([data[i:i + 2] for i in range(0, len(data), 2)])
        else:
            return data

    templ = "%02x"
    if space:
        templ += " "
    return "".join(templ % b for b in data).rstrip()


def format_time(timedelta):
    """
    returns a pretty formatted string according to the size of the timedelta
    :param timediff: time delta given in seconds
    :return: returns a string
    """
    if timedelta > 1000.0:
        return f"{timedelta:.2f} s"
    elif timedelta > 1.0:
        return f"{timedelta:.2f} s"
    elif timedelta > 0.001:
        return f"{timedelta*1000.0:.2f} ms"
    elif timedelta > 0.000001:
        return f"{timedelta*1000000.0:.2f} µs"
    elif timedelta > 0.000000001:
        return f"{timedelta * 1000000000.0:.2f} ns"


def _read(sock, length: int) -> bytes:
    """ isolate the read method from the connection object """
    if isinstance(sock, serial.Serial):
        return sock.read()
    elif isinstance(sock, socket.socket):
        return sock.recv(length)
    else:
        return b''


def read(sock: Union[serial.Serial, socket.socket], length: int = 0) -> bytes:
    """
    This function reads some bytes from serial or network interface
    it returns an array of bytes if a timeout occurs or a given end byte is encountered
    and otherwise b'' if an error occurred
    :returns the read data
    """
    if TESTING:
        return RESULT

    logger.debug("start to read data from serial/network device")
    response = bytes()
    while True:
        try:
            # on serial, length is ignored
            data = _read(sock, length)
            if data:
                response += data
                if len(response) >= length:
                    logger.debug('read end, length reached')
                    break
            else:
                if isinstance(sock, serial.Serial):
                    logger.debug('read end, end of data reached')
                    break
        except socket.error as e:
            if e.args[0] == errno.EAGAIN or e.args[0] == errno.EWOULDBLOCK:
                logger.debug(f'read end, error: {e}')
                break
            else:
                raise
        except Exception as e:
            logger.debug(f"error while reading from serial/network: {e}")
            return b''

    logger.debug(f"finished reading data from serial/network {len(response)} bytes")
    return response


def get_sock(config: dict) -> tuple[Union[serial.Serial, socket.socket, None], str]:
    """ open serial or network socket """
    sock = None
    serial_port = config.get('serial_port')
    host = config.get('host')
    port = config.get('port')
    timeout = config.get('timeout', 2)
    baudrate = config.get('baudrate', 9600)

    if TESTING:
        return None, '(test input)'

    if serial_port:
        #
        # open the serial communication
        #
        try:  # open serial
            sock = serial.Serial(
                serial_port,
                baudrate,
                S_BITS,
                S_PARITY,
                S_STOP,
                timeout=timeout
            )
            if not serial_port == sock.name:
                logger.debug(f"Asked for {serial_port} as serial port, but really using now {sock.name}")
            target = f'serial://{sock.name}'

        except FileNotFoundError:
            logger.error(f"Serial port '{serial_port}' does not exist, please check your port")
            return None, ''
        except serial.SerialException:
            if sock is None:
                logger.error(f"Serial port '{serial_port}' could not be opened")
            else:
                logger.error(f"Serial port '{serial_port}' could be opened but somehow not accessed")
            return None, ''
        except OSError:
            logger.error(f"Serial port '{serial_port}' does not exist, please check the spelling")
            return None, ''
        except Exception as e:
            logger.error(f"unforeseen error occurred: '{e}'")
            return None, ''

        if sock is None:
            # this should not happen...
            logger.error("unforeseen error occurred, serial object was not initialized.")
            return None, ''

        if not sock.is_open:
            logger.error(f"serial port '{serial_port}' could not be opened with given parameters, maybe wrong baudrate?")
            return None, ''

    elif host:
        #
        # open network connection
        #
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        sock.connect((host, port))
        sock.setblocking(False)
        target = f'tcp://{host}:{port}'

    else:
        logger.error('neither serialport nor host/port was given, no action possible.')
        return None, ''

    return sock, target


def parse(data: bytes, config: dict) -> dict:
    """ parse data returned from device read """
    result = {}
    stream = SmlStreamReader()
    stream.add(data)

    while True:
        try:
            frame = stream.get_frame()
            if frame is None:
                break

            obis_values = frame.get_obis()
            for entry in obis_values:
                code = entry.obis.obis_code
                if code not in result:
                    result[code] = []
                content = {
                    'value': entry.get_value(),
                    'name': OBIS_NAMES.get(entry.obis),
                    'valueReal': entry.get_value()
                }
                if entry.scaler:
                    content['scaler'] = entry.scaler
                    content['valueReal'] = round(content['value'] * 10 ** content['scaler'], 1)
                if entry.status:
                    content['status'] = entry.status
                if entry.val_time:
                    content['valTime'] = entry.val_time
                    content['actTime'] = time.ctime(config.get('date_offset', 0) + entry.val_time)
                if entry.value_signature:
                    content['signature'] = entry.value_signature
                if entry.unit:
                    content['unit'] = entry.unit
                    content['unitName'] = smlConst.UNITS.get(content['unit'])

                # Decoding status information if present
                if 'status' in content:
                    # for bitwise operation, true-ish result means bit is set
                    content['statRun'] = bool((content['status'] >> 8) & 1)              # True: meter is counting, False: standstill
                    content['statFraudMagnet'] = bool((content['status'] >> 8) & 2)      # True: magnetic manipulation detected, False: ok
                    content['statFraudCover'] = bool((content['status'] >> 8) & 4)       # True: cover manipulation detected, False: ok
                    content['statEnergyTotal'] = bool((content['status'] >> 8) & 8)      # Current flow total. True: -A, False: +A
                    content['statEnergyL1'] = bool((content['status'] >> 8) & 16)        # Current flow L1. True: -A, False: +A
                    content['statEnergyL2'] = bool((content['status'] >> 8) & 32)        # Current flow L2. True: -A, False: +A
                    content['statEnergyL3'] = bool((content['status'] >> 8) & 64)        # Current flow L3. True: -A, False: +A
                    content['statRotaryField'] = bool((content['status'] >> 8) & 128)    # True: rotary field not L1->L2->L3, False: ok
                    content['statBackstop'] = bool((content['status'] >> 8) & 256)       # True: backstop active, False: backstop not active
                    content['statCalFault'] = bool((content['status'] >> 8) & 512)       # True: calibration relevant fatal fault, False: ok
                    content['statVoltageL1'] = bool((content['status'] >> 8) & 1024)     # True: Voltage L1 present, False: not present
                    content['statVoltageL2'] = bool((content['status'] >> 8) & 2048)     # True: Voltage L2 present, False: not present
                    content['statVoltageL3'] = bool((content['status'] >> 8) & 4096)     # True: Voltage L3 present, False: not present

                # TODO: for backward compatibility - check if really needed
                content['obis'] = code
                # Convert some special OBIS values into nicer format
                # EMH ED300L: add additional OBIS codes
                if content['obis'] == '1-0:0.2.0*0':
                    content['valueReal'] = content['value'].decode()     # Firmware as UTF-8 string
                if content['obis'] == '1-0:96.50.1*1' or content['obis'] == '129-129:199.130.3*255':
                    content['valueReal'] = content['value'].decode()     # Manufacturer code as UTF-8 string
                if content['obis'] == '1-0:96.1.0*255' or content['obis'] == '1-0:0.0.9*255':
                    content['valueReal'] = to_hex(content['value'])
                if content['obis'] == '1-0:96.5.0*255':
                    content['valueReal'] = bin(content['value'] >> 8)    # Status as binary string, so not decoded into status bits as above
                # end TODO

                result[code].append(content)
                logger.debug(f"found {code} with {content}")
        except Exception as e:
            detail = traceback.format_exc()
            logger.warning(f'parsing data failed with error: {e}; details are {detail}')
            # at least return what was decoded up to now
            return result

    return result

    # old frame parser, possibly remove later (needs add'l helper and not-presend "parse" routine)
    # if START_SEQUENCE in data:
    #     prev, _, data = data.partition(START_SEQUENCE)
    #     logger.debug(f'start sequence marker {to_hex(START_SEQUENCE)} found')
    #     if END_SEQUENCE in data:
    #         data, _, remainder = data.partition(END_SEQUENCE)
    #         logger.debug(f'end sequence marker {to_hex(END_SEQUENCE)} found')
    #         logger.debug(f'packet size is {len(data)}')
    #         if len(remainder) > 3:
    #             filler = remainder[0]
    #             logger.debug(f'{filler} fill byte(s) ')
    #             checksum = int.from_bytes(remainder[1:3], byteorder='little')
    #             logger.debug(f'Checksum is {to_hex(checksum)}')
    #             buffer = bytearray()
    #             buffer += START_SEQUENCE + data + END_SEQUENCE + remainder[0:1]
    #             logger.debug(f'Buffer length is {len(buffer)}')
    #             logger.debug(f'buffer is: {to_hex(buffer)}')
    #             crc16 = Crc(width=16, poly=poly, reflect_in=reflect_in, xor_in=xor_in, reflect_out=reflect_out, xor_out=xor_out)
    #             crc_calculated = crc16.table_driven(buffer)
    #             if swap_crc_bytes:
    #                 logger.debug(f'calculated swapped checksum is {to_hex(swap16(crc_calculated))}, given CRC is {to_hex(checksum)}')
    #                 crc_calculated = swap16(crc_calculated)
    #             else:
    #                 logger.debug(f'calculated checksum is {to_hex(crc_calculated)}, given CRC is {to_hex(checksum)}')
    #             data_is_valid = crc_calculated == checksum
    #         else:
    #             logger.debug('not enough bytes read at end to satisfy checksum calculation')
    #     else:
    #         logger.debug('no End sequence marker found in data')
    # else:
    #     logger.debug('no Start sequence marker found in data')


def query(config) -> dict:
    """
    This function will
    1. open a serial communication line to the smartmeter
    2. reads out the block of OBIS information
    3. closes the serial communication
    4. extract obis data and format return dict

    config contains a dict with entries for
    'serial_port', 'device' and a sub-dict 'sml' with entries for
    'device', 'buffersize', 'date_offset' and additional entries for
    calculating crc ('poly', 'reflect_in', 'xor_in', 'reflect_out', 'xor_out', 'swap_crc_bytes')

    return: a dict with the response data formatted as follows:
        {
            'readout': <full readout lines>,
            '<obis1>': [{'value': <val0>, (optional) 'unit': '<unit0>'}, {'value': <val1>', 'unit': '<unit1>'}, ...],
            '<obis2>': [...],
            ...
        }
    """

    #
    # initialize module
    #

    # for the performance of the serial read we need to save the current time
    starttime = time.time()
    runtime = starttime
    result = {}
    lock = Lock()
    sock = None

    if not ('serial_port' in config or ('host' in config and 'port' in config)):
        logger.warning(f'configuration {config} is missing source config (serialport or host and port)')
        return {}

    buffersize = config.get('sml', {'buffersize': 1024}).get('buffersize', 1024)

    logger.debug(f"config='{config}'")

    #
    # open the serial communication
    #

    locked = lock.acquire(blocking=False)
    if not locked:
        logger.error('could not get lock for serial/network access. Is another scheduled/manual action still active?')
        return result

    try:  # lock release

        sock, target = get_sock(config)
        if not sock:
            # error already logged, just go
            return result
        runtime = time.time()
        logger.debug(f"time to open {target}: {format_time(time.time() - runtime)}")

        #
        # read data from device
        #

        response = bytes()
        try:
            response = read(sock, buffersize)
            if len(response) == 0:
                logger.error('reading data from device returned 0 bytes!')
                return result
            else:
                logger.debug(f'read {len(response)} bytes')

        except Exception as e:
            logger.error(f'reading data from {target} failed with error: {e}')

    except Exception:
        # passthrough, this is only for releasing the lock
        raise
    finally:
        #
        # clean up connection
        #
        try:
            sock.close()
        except Exception:
            pass
        sock = None
        lock.release()

    logger.debug(f"time for reading OBIS data: {format_time(time.time() - runtime)}")
    runtime = time.time()

    # Display performance of the serial communication
    logger.debug(f"whole communication with smartmeter took {format_time(time.time() - starttime)}")

    #
    # parse data
    #

    return parse(response, config)


def discover(config: dict) -> bool:
    """ try to autodiscover SML protocol """

    # as of now, this simply tries to listen to the meter
    # called from within the plugin, the parameters are either manually set by
    # the user, or preset by the plugin.yaml defaults.
    # If really necessary, the query could be called multiple times with
    # reduced baud rates or changed parameters, but there would need to be
    # the need for this.
    # For now, let's see how well this works...
    result = query(config)

    return bool(result)


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Query a smartmeter at a given port for SML output',
                                     usage='use "%(prog)s --help" for more information',
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument('port', help='specify the port to use for the smartmeter query, e.g. /dev/ttyUSB0 or /dev/sml0')
    parser.add_argument('-v', '--verbose', help='print verbose information', action='store_true')
    parser.add_argument('-t', '--timeout', help='maximum time to wait for a message from the smartmeter', type=float, default=3.0)
    parser.add_argument('-b', '--buffersize', help='maximum size of message buffer for the reply', type=int, default=1024)

    args = parser.parse_args()

    # complete default dict
    config = {
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
            'onlylisten': False
        },
        'sml': {
            'buffersize': 1024
        }
    }

    config['serial_port'] = args.port
    config['timeout'] = args.timeout
    config['sml']['buffersize'] = args.buffersize

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

    logger.info("This is Smartmeter Plugin, SML module, running in standalone mode")
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
