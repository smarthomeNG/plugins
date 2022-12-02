#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014 Oliver Hinckel                  github@ollisnet.de
#  Copyright 2018-2021                              Bernd.Meiners@mail.de
#########################################################################
#
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import time
import re
import serial
import threading
import struct
import socket
import errno

from lib.module import Modules
from lib.item import Items

from lib.model.smartplugin import *

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.debug("Init standalone {}".format(__name__))
    logging.getLogger().setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)
    # just like print
    formatter = logging.Formatter('%(message)s')
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logging.getLogger().addHandler(ch)
else:
    logger = logging.getLogger()
    logger.debug("Init plugin component {}".format(__name__))

from . import algorithms
from .webif import WebInterface


def to_Hex(data):
    """
    Returns the hex representation of the given data
    """
    # try:
    #    return data.hex()
    # except:
    #    return "".join("%02x " % b for b in data).rstrip()
    # logger.debug("Hextype: {}".format(type(data)))
    if isinstance(data, int):
        return hex(data)

    return "".join("%02x " % b for b in data).rstrip()


def swap16(x):
    return (((x << 8) & 0xFF00) |
            ((x >> 8) & 0x00FF))


def swap32(x):
    return (((x << 24) & 0xFF000000) |
            ((x <<  8) & 0x00FF0000) |
            ((x >>  8) & 0x0000FF00) |
            ((x >> 24) & 0x000000FF))


# start_sequence = bytearray.fromhex('1B 1B 1B 1B 01 01 01 01')
# end_sequence = bytearray.fromhex('1B 1B 1B 1B 1A')
SML_SCHEDULER_NAME = 'Smlx'


class Smlx(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.1.6'

    _units = {  # Blue book @ http://www.dlms.com/documentation/overviewexcerptsofthedlmsuacolouredbooks/index.html
       1 : 'a',    2 : 'mo',    3 : 'wk',  4 : 'd',    5 : 'h',     6 : 'min.',  7 : 's',     8 : '°',     9 : '°C',    10 : 'currency',
      11 : 'm',   12 : 'm/s',  13 : 'm³', 14 : 'm³',  15 : 'm³/h', 16 : 'm³/h', 17 : 'm³/d', 18 : 'm³/d', 19 : 'l',     20 : 'kg',
      21 : 'N',   22 : 'Nm',   23 : 'Pa', 24 : 'bar', 25 : 'J',    26 : 'J/h',  27 : 'W',    28 : 'VA',   29 : 'var',   30 : 'Wh',
      31 : 'WAh', 32 : 'varh', 33 : 'A',  34 : 'C',   35 : 'V',    36 : 'V/m',  37 : 'F',    38 : 'Ω',    39 : 'Ωm²/h', 40 : 'Wb',
      41 : 'T',   42 : 'A/m',  43 : 'H',  44 : 'Hz',  45 : 'Rac',  46 : 'Rre',  47 : 'Rap',  48 : 'V²h',  49 : 'A²h',   50 : 'kg/s',
      51 : 'Smho'
    }
    # Lookup table for smartmeter names to data format
    _devices = {
      'smart-meter-gateway-com-1' : 'hex'
    }

    def __init__(self, sh):
        """
        Initializes the plugin. The parameters described for this method are pulled from the entry in plugin.conf.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.cycle = self.get_parameter_value('cycle')

        self.host = self.get_parameter_value('host')  # None
        self.port = self.get_parameter_value('port')  # 0
        self.serialport = self.get_parameter_value('serialport')    # None
        device = self.get_parameter_value('device')    # raw
        self.timeout = self.get_parameter_value('timeout')    # 5
        self.buffersize = self.get_parameter_value('buffersize')    # 1024
        self.date_offset = self.get_parameter_value('date_offset')    # 0

        # Get base values for CRC calculation
        self.poly = self.get_parameter_value('poly')                        # 0x1021
        self.reflect_in = self.get_parameter_value('reflect_in')            # True
        self.xor_in = self.get_parameter_value('xor_in')                    # 0xffff
        self.reflect_out = self.get_parameter_value('reflect_out')          # True
        self.xor_out = self.get_parameter_value('xor_out')                  # 0xffff
        self.swap_crc_bytes = self.get_parameter_value('swap_crc_bytes')    # False

        self.connected = False
        self.alive = False
        self._serial = None
        self._sock = None
        self._target = None
        self._dataoffset = 0
        self._cyclic_update_active = False
        self._items = {}
        self._item_dict = {}
        self._lock = threading.Lock()
        self.logger = logging.getLogger(__name__)

        if device in self._devices:
            device = self._devices[device]

        if device == "hex":
            self._prepare = self._prepareHex
        elif device == "raw":
            self._prepare = self._prepareRaw
        else:
            self.logger.warning(f"Device type \"{device}\" not supported - defaulting to \"raw\"")
            self._prepare = self._prepareRaw
        self.logger.debug(f"Using CRC params poly={self.poly}, reflect_in={self.reflect_in}, xor_in={self.xor_in}, reflect_out={self.reflect_out}, xor_out={self.xor_out}, swap_crc_bytes={self.swap_crc_bytes}")
        self.init_webinterface(WebInterface)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method called")
        # Setup scheduler for device poll loop
        self.scheduler_add(SML_SCHEDULER_NAME, self.poll_device, cycle=self.cycle)

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")
        self.scheduler_remove(SML_SCHEDULER_NAME)
        self.alive = False
        self.disconnect()

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.

        :param item:    The item to process.
        :return:        returns update_item function if changes are to be watched
        """

        if self.has_iattr(item.conf, 'sml_obis'):
            obis = self.get_iattr_value(item.conf, 'sml_obis')
            prop = self.get_iattr_value(item.conf, 'sml_prop') if self.has_iattr(item.conf, 'sml_prop') else 'valueReal'
            if obis not in self._items:
                self._items[obis] = {}
            if prop not in self._items[obis]:
                self._items[obis][prop] = []
            self._items[obis][prop].append(item)
            self._item_dict[item] = (obis, prop)
            self.logger.debug(f'Attach {item.id()} with {obis=} and {prop=}')
        return None

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if caller != self.get_shortname():
            # Code to execute, only if the item has not been changed by this plugin:
            self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.id()))
            pass

    def connect(self):
        self._lock.acquire()
        self._target = None
        try:
            if self.serialport is not None:
                self._target = f'serial://{self.serialport}'
                self._serial = serial.Serial(self.serialport, 9600, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE, timeout=self.timeout)
            elif self.host is not None:
                self._target = f'tcp://{self.host}:{self.port}'
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(2)
                self._sock.connect((self.host, self.port))
                self._sock.setblocking(False)
        except Exception as e:
            self.logger.error(f'SML: Could not connect to {self._target}: {e}')
            self._lock.release()
            return
        else:
            self.logger.info(f'SML: Connected to {self._target}')
            self.connected = True
            self._lock.release()

    def disconnect(self):
        if self.connected:
            try:
                if self._serial is not None:
                    self._serial.close()
                    self._serial = None
                elif self._sock is not None:
                    self._sock.shutdown(socket.SHUT_RDWR)
                    self._sock = None
            except Exception:
                pass
            self.logger.info('SML: Disconnected!')
            self.connected = False
            self._target = None

    def _read(self, length):
        total = bytes()
        self.logger.debug('Start read')
        if self._serial is not None:
            while True:
                ch = self._serial.read()
                # self.logger.debug(f"Read {ch=}")
                if len(ch) == 0:
                    self.logger.debug('End read')
                    return total
                total += ch
                if len(total) >= length:
                    self.logger.debug('End read')
                    return total
        elif self._sock is not None:
            while True:
                try:
                    data = self._sock.recv(length)
                    if data:
                        total.append(data)
                except socket.error as e:
                    if e.args[0] == errno.EAGAIN or e.args[0] == errno.EWOULDBLOCK:
                        break
                    else:
                        raise e

            self.logger.debug('End read')
            return b''.join(total)

    def poll_device(self):
        """
        Polls for updates of the device, called by the scheduler.
        """

        # check if another cyclic cmd run is still active
        if self._cyclic_update_active:
            self.logger.warning('Triggered cyclic poll_device, but previous cyclic run is still active. Therefore request will be skipped.')
            return

        # set lock
        self._cyclic_update_active = True

        self.logger.debug('Polling Smartmeter now')
        start_sequence = bytearray.fromhex('1B 1B 1B 1B 01 01 01 01')
        end_sequence = bytearray.fromhex('1B 1B 1B 1B 1A')

        self.connect()

        if not self.connected:
            self.logger.error('Not connected, no query possible')
            return
        else:
            self.logger.debug('Connected, try to query')

        start = time.time()
        data_is_valid = False
        try:
            data = self._read(self.buffersize)
            if len(data) == 0:
                self.logger.error('Reading data from device returned 0 bytes!')
                return
            else:
                self.logger.debug(f'Read {len(data)} bytes')

            if start_sequence in data:
                prev, _, data = data.partition(start_sequence)
                self.logger.debug('Start sequence marker {} found'.format(''.join(' {:02x}'.format(x) for x in start_sequence)))
                if end_sequence in data:
                    data, _, rest = data.partition(end_sequence)
                    self.logger.debug('End sequence marker {} found'.format(''.join(' {:02x}'.format(x) for x in end_sequence)))
                    self.logger.debug(f'Packet size is {len(data)}')
                    if len(rest) > 3:
                        filler = rest[0]
                        self.logger.debug(f'{filler} fill byte(s) ')
                        checksum = int.from_bytes(rest[1:3], byteorder='little')
                        self.logger.debug(f'Checksum is {to_Hex(checksum)}')
                        buffer = bytearray()
                        buffer += start_sequence + data + end_sequence + rest[0:1]
                        self.logger.debug(f'Buffer length is {len(buffer)}')
                        self.logger.debug('Buffer: {}'.format(''.join(' {:02x}'.format(x) for x in buffer)))
                        crc16 = algorithms.Crc(width=16, poly=self.poly,
                            reflect_in=self.reflect_in, xor_in=self.xor_in,
                            reflect_out=self.reflect_out, xor_out=self.xor_out)
                        crc_calculated = crc16.table_driven(buffer)
                        if not self.swap_crc_bytes:
                            self.logger.debug(f'Calculated checksum is {to_Hex(crc_calculated)}, given CRC is {to_Hex(checksum)}')
                            data_is_valid = crc_calculated == checksum
                        else:
                            self.logger.debug(f'Calculated and swapped checksum is {to_Hex(swap16(crc_calculated))}, given CRC is {to_Hex(checksum)}')
                            data_is_valid = swap16(crc_calculated) == checksum
                    else:
                        self.logger.debug('Not enough bytes read at end to satisfy checksum calculation')
                        return
                else:
                    self.logger.debug('No End sequence marker found in data')
            else:
                self.logger.debug('No Start sequence marker found in data')
        except Exception as e:
            self.logger.error(f'Reading data from {self._target} failed with exception {e}')
            return

        if data_is_valid:
            self.logger.debug("Checksum was ok, now parse the data_package")
            try:
                values = self._parse(self._prepare(data))
            except Exception as e:
                self.logger.error(f'Preparing and parsing data failed with exception {e}')
            else:
                for obis in values:
                    self.logger.debug(f'Entry {values[obis]}')

                    if obis in self._items:
                        for prop in self._items[obis]:
                            for item in self._items[obis][prop]:
                                try:
                                    value = values[obis][prop]
                                except Exception:
                                    pass
                                else:
                                    item(value, self.get_shortname())
        else:
            self.logger.debug("Checksum was not ok, will not parse the data_package")

        cycletime = time.time() - start

        self.disconnect()
        self.logger.debug(f"Polling Smartmeter done. Poll cycle took {cycletime} seconds.")

        # release lock
        self._cyclic_update_active = False

    def _parse(self, data):
        # Search SML List Entry sequences like:
        # "77 07 81 81 c7 82 03 ff 01 01 01 01 04 xx xx xx xx" - manufacturer
        # "77 07 01 00 00 00 09 ff 01 01 01 01 0b xx xx xx xx xx xx xx xx xx xx 01" - server id
        # "77 07 01 00 01 08 00 ff 63 01 80 01 62 1e 52 ff 56 00 00 00 29 85 01" - active energy consumed
        # Details see http://wiki.volkszaehler.org/software/sml
        self.values = {}
        packetsize = 7
        self.logger.debug('Data:{}'.format(''.join(' {:02x}'.format(x) for x in data)))
        self._dataoffset = 0
        while self._dataoffset < len(data)-packetsize:

            # Find SML_ListEntry starting with 0x77 0x07
            # Attention! The check for != 0xff was necessary because of a possible Client-ID set to 77 07 ff ff ff ff ff ff
            # which would be accidently interpreted as an OBIS value
            if data[self._dataoffset] == 0x77 and data[self._dataoffset+1] == 0x07 and data[self._dataoffset+2] != 0xff:
                packetstart = self._dataoffset
                self._dataoffset += 1
                try:
                    entry = {
                      'objName'   : self._read_entity(data),
                      'status'    : self._read_entity(data),
                      'valTime'   : self._read_entity(data),
                      'unit'      : self._read_entity(data),
                      'scaler'    : self._read_entity(data),
                      'value'     : self._read_entity(data),
                      'signature' : self._read_entity(data)
                    }

                    # Decoding status information if present
                    if entry['status'] is not None:
                        entry['statRun'] = True if ((entry['status'] >> 8) & 1) == 1 else False                 # True: meter is counting, False: standstill
                        entry['statFraudMagnet'] = True if ((entry['status'] >> 8) & 2) == 2 else False         # True: magnetic manipulation detected, False: ok
                        entry['statFraudCover'] = True if ((entry['status'] >> 8) & 4) == 4 else False          # True: cover manipulation detected, False: ok
                        entry['statEnergyTotal'] = True if ((entry['status'] >> 8) & 8) == 8 else False         # Current flow total. True: -A, False: +A
                        entry['statEnergyL1'] = True if ((entry['status'] >> 8) & 16) == 16 else False          # Current flow L1. True: -A, False: +A
                        entry['statEnergyL2'] = True if ((entry['status'] >> 8) & 32) == 32 else False          # Current flow L2. True: -A, False: +A
                        entry['statEnergyL3'] = True if ((entry['status'] >> 8) & 64) == 64 else False          # Current flow L3. True: -A, False: +A
                        entry['statRotaryField'] = True if ((entry['status'] >> 8) & 128) == 128 else False     # True: rotary field not L1->L2->L3, False: ok
                        entry['statBackstop'] = True if ((entry['status'] >> 8) & 256) == 256 else False        # True: backstop active, False: backstop not active
                        entry['statCalFault'] = True if ((entry['status'] >> 8) & 512) == 512 else False        # True: calibration relevant fatal fault, False: ok
                        entry['statVoltageL1'] = True if ((entry['status'] >> 8) & 1024) == 1024 else False     # True: Voltage L1 present, False: not present
                        entry['statVoltageL2'] = True if ((entry['status'] >> 8) & 2048) == 2048 else False     # True: Voltage L2 present, False: not present
                        entry['statVoltageL3'] = True if ((entry['status'] >> 8) & 4096) == 4096 else False     # True: Voltage L3 present, False: not present

                    # Add additional calculated fields
                    entry['obis'] = f"{entry['objName'][0]}-{entry['objName'][1]}:{entry['objName'][2]}.{entry['objName'][3]}.{entry['objName'][4]}*{entry['objName'][5]}"
                    entry['valueReal'] = round(entry['value'] * 10 ** entry['scaler'], 1) if entry['scaler'] is not None else entry['value']
                    entry['unitName'] = self._units[entry['unit']] if entry['unit'] is not None and entry['unit'] in self._units else None
                    entry['actualTime'] = time.ctime(self.date_offset + entry['valTime'][1]) if entry['valTime'] is not None else None  # Decodes valTime into date/time string
                    # For a Holley DTZ541 with faulty Firmware remove the                ^[1] from this line ^.

                    # Convert some special OBIS values into nicer format
                    # EMH ED300L: add additional OBIS codes
                    if entry['obis'] == '1-0:0.2.0*0':
                        entry['valueReal'] = entry['value'].decode()     # Firmware as UTF-8 string
                    if entry['obis'] == '1-0:96.50.1*1' or entry['obis'] == '129-129:199.130.3*255':
                        entry['valueReal'] = entry['value'].decode()     # Manufacturer code as UTF-8 string
                    if entry['obis'] == '1-0:96.1.0*255' or entry['obis'] == '1-0:0.0.9*255':
                        entry['valueReal'] = entry['value'].hex()        # ServerID (Seriel Number) as hex string as found on frontpanel
                    if entry['obis'] == '1-0:96.5.0*255':
                        entry['valueReal'] = bin(entry['value'] >> 8)    # Status as binary string, so not decoded into status bits as above

                    entry['objName'] = entry['obis']                     # Changes objName for DEBUG output to nicer format

                    self.values[entry['obis']] = entry

                except Exception as e:
                    if self._dataoffset < len(data) - 1:
                        self.logger.warning('Cannot parse entity at position {}, byte {}: {}:{}...'.format(self._dataoffset, self._dataoffset - packetstart, e, ''.join(' {:02x}'.format(x) for x in data[packetstart:packetstart+64])))
                        self._dataoffset = packetstart + packetsize - 1
            else:
                self._dataoffset += 1

        return self.values

    def _read_entity(self, data):
        import builtins
        upack = {
            5: {1: '>b', 2: '>h', 4: '>i', 8: '>q'},  # int
            6: {1: '>B', 2: '>H', 4: '>I', 8: '>Q'}   # uint
        }

        result = None

        tlf = data[self._dataoffset]
        type = (tlf & 112) >> 4
        more = tlf & 128
        len = tlf & 15
        self._dataoffset += 1

        if more > 0:
            tlf = data[self._dataoffset]
            len = (len << 4) + (tlf & 15)
            self._dataoffset += 1

        len -= 1

        if len == 0:     # Skip empty optional value
            return result

        if self._dataoffset + len >= builtins.len(data):
            raise Exception(f"Try to read {len} bytes, but only got {builtins.len(data) - self._dataoffset}")

        if type == 0:    # Octet string
            result = data[self._dataoffset:self._dataoffset+len]

        elif type == 5 or type == 6:  # int or uint
            d = data[self._dataoffset:self._dataoffset+len]

            ulen = len
            if ulen not in upack[type]:  # Extend to next greather unpack unit
                while ulen not in upack[type]:
                    d = b'\x00' + d
                    ulen += 1

            result = struct.unpack(upack[type][ulen], d)[0]

        elif type == 7:  # list
            result = []
            self._dataoffset += 1
            for i in range(0, len + 1):
                result.append(self._read_entity(data))
            return result

        else:
            self.logger.warning(f'Skipping unknown field {hex(tlf)}')

        self._dataoffset += len

        return result

    def _prepareRaw(self, data):
        return data

    def _prepareHex(self, data):
        data = data.decode("iso-8859-1").lower();
        data = re.sub("[^a-f0-9]", " ", data)
        data = re.sub("( +[a-f0-9]|[a-f0-9] +)", "", data)
        data = data.encode()
        return bytes(''.join(chr(int(data[i:i+2], 16)) for i in range(0, len(data), 2)), "iso8859-1")

    @property
    def item_list(self):
        return list(self._item_dict.keys())

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()
