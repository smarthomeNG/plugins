#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 - 2015 KNX-User-Forum e.V.    http://knx-user-forum.de/
#  Copyright 2016 - 2022 Bernd Meiners              Bernd.Meiners@mail.de
#  Copyright 2024 -      Sebastian Helms         morg @ knx-user-forum.de
#########################################################################
#
#  SML plugin for SmartHomeNG
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

import logging
from ruamel.yaml import YAML

if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    logger.debug(f"init standalone {__name__}")
else:
    logger = logging.getLogger(__name__)
    logger.debug(f"init plugin component {__name__}")

import time
import serial
import re
from threading import Lock


def discover(config: dict) -> bool:
    """ try to autodiscover SML protocol """
    return False


def query(config: dict) -> dict:
    """ query smartmeter and return result """
    return {}


#
#manufacturer_ids = {}
#
#exportfile = 'manufacturer.yaml'
#try:
#    with open(exportfile, 'r') as infile:
#        y = YAML(typ='safe')
#        manufacturer_ids = y.load(infile)
#except:
#    pass
#"""
#This module implements the query of a smartmeter using the SML protocol.
#The smartmeter needs to have an infrared interface and an IR-Adapter is needed for USB.
#
#The Character Format for protocol mode A - D is defined as 1 start bit, 7 data bits, 1 parity bit, 1 stop bit and even parity 
#In protocol mode E it is defined as 1 start bit, 8 data bits, 1 stop bit is allowed, see Annex E of IEC62056-21
#For this plugin the protocol mode E is neither implemented nor supported.
#
#Abbreviations
#-------------
#COSEM
#   COmpanion Specification for Energy Metering
#
#OBIS
#   OBject Identification System (see iec62056-61{ed1.0}en_obis_protocol.pdf)
#
#"""
#
#SOH = 0x01  # start of header
#STX = 0x02  # start of text        
#ETX = 0x03  # end of text
#ACK = 0x06  # acknowledge
#CR  = 0x0D  # carriage return
#LF  = 0x0A  # linefeed
#BCC = 0x00  # Block check Character will contain the checksum immediately following the data packet
#
#
#def format_time( timedelta ):
#    """
#    returns a pretty formatted string according to the size of the timedelta
#    :param timediff: time delta given in seconds
#    :return: returns a string
#    """
#    if timedelta > 1000.0:
#        return f"{timedelta:.2f} s"
#    elif timedelta > 1.0:
#        return f"{timedelta:.2f} s"
#    elif timedelta > 0.001:
#        return f"{timedelta*1000.0:.2f} ms"
#    elif timedelta > 0.000001:
#        return f"{timedelta*1000000.0:.2f} µs"
#    elif timedelta > 0.000000001:
#        return f"{timedelta * 1000000000.0:.2f} ns"
#
#        
#def read_data_block_from_serial(the_serial, end_byte=0x0a, start_byte=None, max_read_time=None):
#    """
#    This function reads some bytes from serial interface
#    it returns an array of bytes if a timeout occurs or a given end byte is encountered
#    and otherwise None if an error occurred
#    :param the_serial: interface to read from
#    :param end_byte: the indicator for end of data, this will be included in response
#    :param start_byte: the indicator for start of data, this will be included in response
#    :param max_read_time: 
#    :returns the read data or None
#    """
#    logger.debug("start to read data from serial device")
#    response = bytes()
#    starttime = time.time()
#    start_found = False
#    try:
#        while True:
#            ch = the_serial.read()
#            #logger.debug(f"Read {ch}")
#            runtime = time.time()
#            if len(ch) == 0:
#                break
#            if start_byte is not None:
#                if ch == start_byte:
#                    response = bytes()
#                    start_found = True
#            response += ch
#            if ch == end_byte:
#                if start_byte is not None and not start_found:
#                    response = bytes()
#                    continue
#                else:
#                    break
#            if (response[-1] == end_byte):
#                break
#            if max_read_time is not None:
#                if runtime-starttime > max_read_time:
#                    break
#    except Exception as e:
#        logger.debug(f"Exception {e} occurred in read data block from serial")
#        return None
#    logger.debug(f"finished reading data from serial device after {len(response)} bytes")
#    return response
#
##
##
## moved from ehz.py
## adjust/implement
##
##
#
#        # TODO: make this config dict
#        self._serial = None
#        self._sock = None
#        self._target = None
#        self._dataoffset = 0
#
#    # Lookup table for smartmeter names to data format
#    _sml_devices = {
#        'smart-meter-gateway-com-1': 'hex'
#    }
#
#OBIS_TYPES = ('objName', 'status', 'valTime', 'unit', 'scaler', 'value', 'signature', 'obis', 'valueReal', 'unitName', 'actualTime')
#
#SML_START_SEQUENCE = bytearray.fromhex('1B 1B 1B 1B 01 01 01 01')
#SML_END_SEQUENCE = bytearray.fromhex('1B 1B 1B 1B 1A')
#
#UNITS = {  # Blue book @ http://www.dlms.com/documentation/overviewexcerptsofthedlmsuacolouredbooks/index.html
#    1: 'a', 2: 'mo', 3: 'wk', 4: 'd', 5: 'h', 6: 'min.', 7: 's', 8: '°', 9: '°C', 10: 'currency',
#    11: 'm', 12: 'm/s', 13: 'm³', 14: 'm³', 15: 'm³/h', 16: 'm³/h', 17: 'm³/d', 18: 'm³/d', 19: 'l', 20: 'kg',
#    21: 'N', 22: 'Nm', 23: 'Pa', 24: 'bar', 25: 'J', 26: 'J/h', 27: 'W', 28: 'VA', 29: 'var', 30: 'Wh',
#    31: 'WAh', 32: 'varh', 33: 'A', 34: 'C', 35: 'V', 36: 'V/m', 37: 'F', 38: 'Ω', 39: 'Ωm²/h', 40: 'Wb',
#    41: 'T', 42: 'A/m', 43: 'H', 44: 'Hz', 45: 'Rac', 46: 'Rre', 47: 'Rap', 48: 'V²h', 49: 'A²h', 50: 'kg/s',
#    51: 'Smho'
#}
#
#def init(self):
#    # TODO: move this to the SML module
#    # set function pointers
#    if device == "hex":
#        self._sml_prepare = self._sml_prepareHex
#    elif device == "raw":
#        self._sml_prepare = self._sml_prepareRaw
#    else:
#        self.logger.warning(f"Device type \"{device}\" not supported - defaulting to \"raw\"")
#        self._sml_prepare = self._prepareRaw
#
#    self.logger.debug(f"Using SML CRC params poly={self.poly}, reflect_in={self.reflect_in}, xor_in={self.xor_in}, reflect_out={self.reflect_out}, xor_out={self.xor_out}, swap_crc_bytes={self.swap_crc_bytes}")
#
#def connect(self):
#    if not self.alive:
#        self.logger.info('connect called but plugin not running.')
#        return
#
#    self._target = None
#    with self._lock:
#        try:
#            if self.serialport is not None:
#                self._target = f'serial://{self.serialport}'
#                self._serial = serial.Serial(self.serialport, 9600, serial.EIGHTBITS, serial.PARITY_NONE, serial.STOPBITS_ONE, timeout=self.timeout)
#            elif self.host is not None:
#                self._target = f'tcp://{self.host}:{self.port}'
#                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#                self._sock.settimeout(2)
#                self._sock.connect((self.host, self.port))
#                self._sock.setblocking(False)
#        except Exception as e:
#            self.logger.error(f'Could not connect to {self._target}: {e}')
#            return
#        else:
#            self.logger.info(f'Connected to {self._target}')
#            self.connected = True
#
#def disconnect(self):
#    if self.connected:
#        with self._lock:
#            try:
#                self._serial.close()
#            except Exception:
#                pass
#            self._serial = None
#            try:
#                self._sock.shutdown(socket.SHUT_RDWR)
#            except Exception:
#                pass
#            self._sock = None
#
#            self.logger.info('SML: Disconnected!')
#            self.connected = False
#            self._target = None
#
#
#    def _read(self, length):
#        total = bytes()
#        self.logger.debug('Start read')
#        if self._serial is not None:
#            while True:
#                ch = self._serial.read()
#                # self.logger.debug(f"Read {ch=}")
#                if len(ch) == 0:
#                    self.logger.debug('End read')
#                    return total
#                total += ch
#                if len(total) >= length:
#                    self.logger.debug('End read')
#                    return total
#        elif self._sock is not None:
#            while True:
#                try:
#                    data = self._sock.recv(length)
#                    if data:
#                        total.append(data)
#                except socket.error as e:
#                    if e.args[0] == errno.EAGAIN or e.args[0] == errno.EWOULDBLOCK:
#                        break
#                    else:
#                        raise e
#
#            self.logger.debug('End read')
#            return b''.join(total)
#
#    def poll_device(self):
#        """
#        Polls for updates of the device, called by the scheduler.
#        """
#
#        # check if another cyclic cmd run is still active
#        if self._parse_lock.acquire(timeout=1):
#            try:
#                self.logger.debug('Polling Smartmeter now')
#
#                self.connect()
#                if not self.connected:
#                    self.logger.error('Not connected, no query possible')
#                    return
#                else:
#                    self.logger.debug('Connected, try to query')
#
#                start = time.time()
#                data_is_valid = False
#                try:
#                    data = self._read(self.buffersize)
#                    if len(data) == 0:
#                        self.logger.error('Reading data from device returned 0 bytes!')
#                        return
#                    else:
#                        self.logger.debug(f'Read {len(data)} bytes')
#
#                    if START_SEQUENCE in data:
#                        prev, _, data = data.partition(START_SEQUENCE)
#                        self.logger.debug('Start sequence marker {} found'.format(''.join(' {:02x}'.format(x) for x in START_SEQUENCE)))
#                        if END_SEQUENCE in data:
#                            data, _, rest = data.partition(END_SEQUENCE)
#                            self.logger.debug('End sequence marker {} found'.format(''.join(' {:02x}'.format(x) for x in END_SEQUENCE)))
#                            self.logger.debug(f'Packet size is {len(data)}')
#                            if len(rest) > 3:
#                                filler = rest[0]
#                                self.logger.debug(f'{filler} fill byte(s) ')
#                                checksum = int.from_bytes(rest[1:3], byteorder='little')
#                                self.logger.debug(f'Checksum is {to_Hex(checksum)}')
#                                buffer = bytearray()
#                                buffer += START_SEQUENCE + data + END_SEQUENCE + rest[0:1]
#                                self.logger.debug(f'Buffer length is {len(buffer)}')
#                                self.logger.debug('Buffer: {}'.format(''.join(' {:02x}'.format(x) for x in buffer)))
#                                crc16 = algorithms.Crc(width=16, poly=self.poly, reflect_in=self.reflect_in, xor_in=self.xor_in, reflect_out=self.reflect_out, xor_out=self.xor_out)
#                                crc_calculated = crc16.table_driven(buffer)
#                                if not self.swap_crc_bytes:
#                                    self.logger.debug(f'Calculated checksum is {to_Hex(crc_calculated)}, given CRC is {to_Hex(checksum)}')
#                                    data_is_valid = crc_calculated == checksum
#                                else:
#                                    self.logger.debug(f'Calculated and swapped checksum is {to_Hex(swap16(crc_calculated))}, given CRC is {to_Hex(checksum)}')
#                                    data_is_valid = swap16(crc_calculated) == checksum
#                            else:
#                                self.logger.debug('Not enough bytes read at end to satisfy checksum calculation')
#                                return
#                        else:
#                            self.logger.debug('No End sequence marker found in data')
#                    else:
#                        self.logger.debug('No Start sequence marker found in data')
#                except Exception as e:
#                    self.logger.error(f'Reading data from {self._target} failed with exception {e}')
#                    return
#
#                if data_is_valid:
#                    self.logger.debug("Checksum was ok, now parse the data_package")
#                    try:
#                        values = self._parse(self._sml_prepare(data))
#                    except Exception as e:
#                        self.logger.error(f'Preparing and parsing data failed with exception {e}')
#                    else:
#                        for obis in values:
#                            self.logger.debug(f'Entry {values[obis]}')
#
#                            if obis in self._items:
#                                for prop in self._items[obis]:
#                                    for item in self._items[obis][prop]:
#                                        try:
#                                            value = values[obis][prop]
#                                        except Exception:
#                                            pass
#                                        else:
#                                            item(value, self.get_shortname())
#                else:
#                    self.logger.debug("Checksum was not ok, will not parse the data_package")
#
#                cycletime = time.time() - start
#
#                self.logger.debug(f"Polling Smartmeter done. Poll cycle took {cycletime} seconds.")
#            finally:
#                self.disconnect()
#                self._parse_lock.release()
#        else:
#            self.logger.warning('Triggered poll_device, but could not acquire lock. Request will be skipped.')
#
#    def _parse(self, data):
#        # Search SML List Entry sequences like:
#        # "77 07 81 81 c7 82 03 ff 01 01 01 01 04 xx xx xx xx" - manufacturer
#        # "77 07 01 00 00 00 09 ff 01 01 01 01 0b xx xx xx xx xx xx xx xx xx xx 01" - server id
#        # "77 07 01 00 01 08 00 ff 63 01 80 01 62 1e 52 ff 56 00 00 00 29 85 01" - active energy consumed
#        # Details see http://wiki.volkszaehler.org/software/sml
#        self.values = {}
#        packetsize = 7
#        self.logger.debug('Data:{}'.format(''.join(' {:02x}'.format(x) for x in data)))
#        self._dataoffset = 0
#        while self._dataoffset < len(data)-packetsize:
#
#            # Find SML_ListEntry starting with 0x77 0x07
#            # Attention! The check for != 0xff was necessary because of a possible Client-ID set to 77 07 ff ff ff ff ff ff
#            # which would be accidently interpreted as an OBIS value
#            if data[self._dataoffset] == 0x77 and data[self._dataoffset+1] == 0x07 and data[self._dataoffset+2] != 0xff:
#                packetstart = self._dataoffset
#                self._dataoffset += 1
#                try:
#                    entry = {
#                      'objName'   : self._read_entity(data),
#                      'status'    : self._read_entity(data),
#                      'valTime'   : self._read_entity(data),
#                      'unit'      : self._read_entity(data),
#                      'scaler'    : self._read_entity(data),
#                      'value'     : self._read_entity(data),
#                      'signature' : self._read_entity(data)
#                    }
#
#                    # Decoding status information if present
#                    if entry['status'] is not None:
#                        entry['statRun'] = True if ((entry['status'] >> 8) & 1) == 1 else False                 # True: meter is counting, False: standstill
#                        entry['statFraudMagnet'] = True if ((entry['status'] >> 8) & 2) == 2 else False         # True: magnetic manipulation detected, False: ok
#                        entry['statFraudCover'] = True if ((entry['status'] >> 8) & 4) == 4 else False          # True: cover manipulation detected, False: ok
#                        entry['statEnergyTotal'] = True if ((entry['status'] >> 8) & 8) == 8 else False         # Current flow total. True: -A, False: +A
#                        entry['statEnergyL1'] = True if ((entry['status'] >> 8) & 16) == 16 else False          # Current flow L1. True: -A, False: +A
#                        entry['statEnergyL2'] = True if ((entry['status'] >> 8) & 32) == 32 else False          # Current flow L2. True: -A, False: +A
#                        entry['statEnergyL3'] = True if ((entry['status'] >> 8) & 64) == 64 else False          # Current flow L3. True: -A, False: +A
#                        entry['statRotaryField'] = True if ((entry['status'] >> 8) & 128) == 128 else False     # True: rotary field not L1->L2->L3, False: ok
#                        entry['statBackstop'] = True if ((entry['status'] >> 8) & 256) == 256 else False        # True: backstop active, False: backstop not active
#                        entry['statCalFault'] = True if ((entry['status'] >> 8) & 512) == 512 else False        # True: calibration relevant fatal fault, False: ok
#                        entry['statVoltageL1'] = True if ((entry['status'] >> 8) & 1024) == 1024 else False     # True: Voltage L1 present, False: not present
#                        entry['statVoltageL2'] = True if ((entry['status'] >> 8) & 2048) == 2048 else False     # True: Voltage L2 present, False: not present
#                        entry['statVoltageL3'] = True if ((entry['status'] >> 8) & 4096) == 4096 else False     # True: Voltage L3 present, False: not present
#
#                    # Add additional calculated fields
#                    entry['obis'] = f"{entry['objName'][0]}-{entry['objName'][1]}:{entry['objName'][2]}.{entry['objName'][3]}.{entry['objName'][4]}*{entry['objName'][5]}"
#                    entry['valueReal'] = round(entry['value'] * 10 ** entry['scaler'], 1) if entry['scaler'] is not None else entry['value']
#                    entry['unitName'] = UNITS[entry['unit']] if entry['unit'] is not None and entry['unit'] in UNITS else None
#                    entry['actualTime'] = time.ctime(self.date_offset + entry['valTime'][1]) if entry['valTime'] is not None else None  # Decodes valTime into date/time string
#                    # For a Holley DTZ541 with faulty Firmware remove the                ^[1] from this line ^.
#
#                    # Convert some special OBIS values into nicer format
#                    # EMH ED300L: add additional OBIS codes
#                    if entry['obis'] == '1-0:0.2.0*0':
#                        entry['valueReal'] = entry['value'].decode()     # Firmware as UTF-8 string
#                    if entry['obis'] == '1-0:96.50.1*1' or entry['obis'] == '129-129:199.130.3*255':
#                        entry['valueReal'] = entry['value'].decode()     # Manufacturer code as UTF-8 string
#                    if entry['obis'] == '1-0:96.1.0*255' or entry['obis'] == '1-0:0.0.9*255':
#                        entry['valueReal'] = entry['value'].hex()        # ServerID (Seriel Number) as hex string as found on frontpanel
#                    if entry['obis'] == '1-0:96.5.0*255':
#                        entry['valueReal'] = bin(entry['value'] >> 8)    # Status as binary string, so not decoded into status bits as above
#
#                    entry['objName'] = entry['obis']                     # Changes objName for DEBUG output to nicer format
#
#                    self.values[entry['obis']] = entry
#
#                except Exception as e:
#                    if self._dataoffset < len(data) - 1:
#                        self.logger.warning('Cannot parse entity at position {}, byte {}: {}:{}...'.format(self._dataoffset, self._dataoffset - packetstart, e, ''.join(' {:02x}'.format(x) for x in data[packetstart:packetstart+64])))
#                        self._dataoffset = packetstart + packetsize - 1
#            else:
#                self._dataoffset += 1
#
#        return self.values
#
#    def _read_entity(self, data):
#        import builtins
#        upack = {
#            5: {1: '>b', 2: '>h', 4: '>i', 8: '>q'},  # int
#            6: {1: '>B', 2: '>H', 4: '>I', 8: '>Q'}   # uint
#        }
#
#        result = None
#
#        tlf = data[self._dataoffset]
#        type = (tlf & 112) >> 4
#        more = tlf & 128
#        len = tlf & 15
#        self._dataoffset += 1
#
#        if more > 0:
#            tlf = data[self._dataoffset]
#            len = (len << 4) + (tlf & 15)
#            self._dataoffset += 1
#
#        len -= 1
#
#        if len == 0:     # Skip empty optional value
#            return result
#
#        if self._dataoffset + len >= builtins.len(data):
#            raise Exception(f"Try to read {len} bytes, but only got {builtins.len(data) - self._dataoffset}")
#
#        if type == 0:    # Octet string
#            result = data[self._dataoffset:self._dataoffset+len]
#
#        elif type == 5 or type == 6:  # int or uint
#            d = data[self._dataoffset:self._dataoffset+len]
#
#            ulen = len
#            if ulen not in upack[type]:  # Extend to next greather unpack unit
#                while ulen not in upack[type]:
#                    d = b'\x00' + d
#                    ulen += 1
#
#            result = struct.unpack(upack[type][ulen], d)[0]
#
#        elif type == 7:  # list
#            result = []
#            self._dataoffset += 1
#            for i in range(0, len + 1):
#                result.append(self._read_entity(data))
#            return result
#
#        else:
#            self.logger.warning(f'Skipping unknown field {hex(tlf)}')
#
#        self._dataoffset += len
#
#        return result
#
#    def _prepareRaw(self, data):
#        return data
#
#    def _prepareHex(self, data):
#        data = data.decode("iso-8859-1").lower()
#        data = re.sub("[^a-f0-9]", " ", data)
#        data = re.sub("( +[a-f0-9]|[a-f0-9] +)", "", data)
#        data = data.encode()
#        return bytes(''.join(chr(int(data[i:i+2], 16)) for i in range(0, len(data), 2)), "iso8859-1")
#
#
###########################################################
##   Helper Functions
###########################################################
#
#
#def to_Hex(data):
#    """
#    Returns the hex representation of the given data
#    """
#    # try:
#    #    return data.hex()
#    # except:
#    #    return "".join("%02x " % b for b in data).rstrip()
#    # logger.debug("Hextype: {}".format(type(data)))
#    if isinstance(data, int):
#        return hex(data)
#
#    return "".join("%02x " % b for b in data).rstrip()
#
#
#def swap16(x):
#    return (((x << 8) & 0xFF00) |
#            ((x >> 8) & 0x00FF))
#
#
#def swap32(x):
#    return (((x << 24) & 0xFF000000) |
#            ((x <<  8) & 0x00FF0000) |
#            ((x >>  8) & 0x0000FF00) |
#            ((x >> 24) & 0x000000FF))
#
##
##
##
##
##
##
#
#
#def query( config ):
#    """
#    This function will
#    1. open a serial communication line to the smartmeter
#    2. sends a request for info
#    3. parses the devices first (and maybe second) answer for capabilities of the device
#    4. adjusts the speed of the communication accordingly
#    5. reads out the block of OBIS information
#    6. closes the serial communication
#
#    config contains a dict with entries for
#    'serialport', 'device', 'querycode', 'baudrate', 'baudrate_fix', 'timeout', 'onlylisten', 'use_checksum'
#    
#    return: a textblock with the data response from smartmeter
#    """
#    # for the performance of the serial read we need to save the actual time
#    starttime = time.time()
#    runtime = starttime
#    result = None
#    
#
#    SerialPort = config.get('serialport')
#    Device = config.get('device','')
#    InitialBaudrate = config.get('baudrate', 300)
#    QueryCode = config.get('querycode', '?')
#    use_checksum = config.get('use_checksum', True)
#    baudrate_fix = config.get('baudrate_fix', False)
#    timeout = config.get('timeout', 3)
#    OnlyListen = config.get('onlylisten', False)    # just for the case that smartmeter transmits data without a query first
#    logger.debug(f"Config='{config}'")
#    StartChar = b'/'[0]
#
#    Request_Message = b"/"+QueryCode.encode('ascii')+Device.encode('ascii')+b"!\r\n"
#
#    
#    # open the serial communication
#    # about timeout: time tr between sending a request and an answer needs to be
#    # 200ms < tr < 1500ms for protocol mode A or B
#    # inter character time must be smaller than 1500 ms
#    # The time between the reception of a message and the transmission of an answer is:
#    # (20 ms) 200 ms = tr = 1 500 ms (see item 12) of 6.3.14).
#    # If a response has not been received, the waiting time of the transmitting equipment after
#    # transmission of the identification message, before it continues with the transmission, is:
#    # 1 500 ms < tt = 2 200 ms
#    # The time between two characters in a character sequence is:
#    # ta < 1 500 ms
#    wait_before_acknowledge = 0.4   # wait for 400 ms before sending the request to change baudrate
#    wait_after_acknowledge = 0.4    # wait for 400 ms after sending acknowledge
#    sml_serial = None
#
#    try:
#        sml_serial = serial.Serial(SerialPort,
#                                    InitialBaudrate,
#                                    bytesize=serial.SEVENBITS,
#                                    parity=serial.PARITY_EVEN,
#                                    stopbits=serial.STOPBITS_ONE,
#                                    timeout=timeout)
#        if not SerialPort == sml_serial.name:
#            logger.debug(f"Asked for {SerialPort} as serial port, but really using now {sml_serial.name}")
#            
#    except FileNotFoundError as e:
#        logger.error(f"Serial port '{SerialPort}' does not exist, please check your port")
#        return
#    except OSError as e:
#        logger.error(f"Serial port '{SerialPort}' does not exist, please check the spelling")
#        return
#    except serial.SerialException as e:
#        if sml_serial is None:
#            logger.error(f"Serial port '{SerialPort}' could not be opened")
#        else:
#            logger.error(f"Serial port '{SerialPort}' could be opened but somehow not accessed")
#    except Exception as e:
#        logger.error(f"Another unknown error occurred: '{e}'")
#        return
#
#    if not sml_serial.isOpen():
#        logger.error(f"Serial port '{SerialPort}' could not be opened with given parameters, maybe wrong baudrate?")
#        return
#
#    logger.debug(f"Time to open serial port {SerialPort}: {format_time(time.time()- runtime)}")
#    runtime = time.time()
#
#    Acknowledge = b''   # preset empty answer
#
#    if not OnlyListen:
#        # start a dialog with smartmeter
#        try:
#            #logger.debug(f"Reset input buffer from serial port '{SerialPort}'")
#            #sml_serial.reset_input_buffer()    # replaced sml_serial.flushInput()
#            logger.debug(f"Writing request message {Request_Message} to serial port '{SerialPort}'")
#            sml_serial.write(Request_Message)
#            #logger.debug(f"Flushing buffer from serial port '{SerialPort}'")
#            #sml_serial.flush()                 # replaced sml_serial.drainOutput()
#        except Exception as e:
#            logger.warning(f"Error {e}")
#            return
#
#        logger.debug(f"Time to send first request to smartmeter: {format_time(time.time()- runtime)}")
#
#        # now get first response
#        response = read_data_block_from_serial(sml_serial)
#        if response is None:
#            logger.debug("No response received upon first request")
#            return
#
#        logger.debug(f"Time to receive an answer: {format_time(time.time()- runtime)}")
#        runtime = time.time()
#
#        # We need to examine the read response here for an echo of the _Request_Message
#        # some meters answer with an echo of the request Message
#        if response == Request_Message:
#            logger.debug("Request Message was echoed, need to read the identification message")
#            # read Identification message if Request was echoed
#            # now read the capabilities and type/brand line from Smartmeter
#            # e.g. b'/LGZ5\\2ZMD3104407.B32\r\n'
#            response = read_data_block_from_serial(sml_serial)
#        else:
#            logger.debug("Request Message was not equal to response, treating as identification message")
#
#        logger.debug(f"Time to get first identification message from smartmeter: {format_time(time.time() - runtime)}")
#        runtime = time.time()
#
#        Identification_Message = response
#        logger.debug(f"Identification Message is {Identification_Message}")
#
#        # need at least 7 bytes:
#        # 1 byte "/"
#        # 3 bytes short Identification
#        # 1 byte speed indication
#        # 2 bytes CR LF
#        if (len(Identification_Message) < 7):
#            logger.warning(f"malformed identification message: '{Identification_Message}', abort query")
#            return
#
#        if (Identification_Message[0] != StartChar):
#            logger.warning(f"identification message '{Identification_Message}' does not start with '/', abort query")
#            return
#
#        manid = str(Identification_Message[1:4],'utf-8')
#        manname = manufacturer_ids.get(manid,'unknown')
#        logger.debug(f"The manufacturer for {manid} is {manname} (out of {len(manufacturer_ids)} given manufacturers)")
#        
#        """
#        Different smartmeters allow for different protocol modes. 
#        The protocol mode decides whether the communication is fixed to a certain baudrate or might be speed up.
#        Some meters do initiate a protocol by themselves with a fixed speed of 2400 baud e.g. Mode D
#        However some meters specify a speed of 9600 Baud although they use protocol mode D (readonly)
#        """
#        Protocol_Mode = 'A'
#
#        """
#        The communication of the plugin always stays at the same speed, 
#        Protocol indicator can be anything except for A-I, 0-9, /, ?
#        """
#        Baudrates_Protocol_Mode_A = 300
#        Baudrates_Protocol_Mode_B = { 'A': 600, 'B': 1200, 'C': 2400, 'D': 4800, 'E': 9600, 'F': 19200,
#                                    'G': "reserved", 'H': "reserved", 'I': "reserved" }
#        Baudrates_Protocol_Mode_C = { '0': 300, '1': 600, '2': 1200, '3': 2400, '4': 4800, '5': 9600, '6': 19200,
#                                    '7': "reserved", '8': "reserved", '9': "reserved"}
#
#        # always '3' but it is always initiated by the metering device so it can't be encountered here
#        Baudrates_Protocol_Mode_D = { '3' : 2400}
#        Baudrates_Protocol_Mode_E = Baudrates_Protocol_Mode_C
#
#        Baudrate_identification = chr(Identification_Message[4])
#        if Baudrate_identification in Baudrates_Protocol_Mode_B:
#            NewBaudrate = Baudrates_Protocol_Mode_B[Baudrate_identification]
#            Protocol_Mode = 'B'
#        elif Baudrate_identification in Baudrates_Protocol_Mode_C:
#            NewBaudrate = Baudrates_Protocol_Mode_C[Baudrate_identification]
#            Protocol_Mode = 'C' # could also be 'E' but it doesn't make any difference here
#        else:
#            NewBaudrate = Baudrates_Protocol_Mode_A
#            Protocol_Mode = 'A'
#
#        logger.debug(f"Baudrate id is '{Baudrate_identification}' thus Protocol Mode is {Protocol_Mode} and suggested Baudrate is {NewBaudrate} Bd")
#
#        if chr(Identification_Message[5]) == '\\':
#            if chr(Identification_Message[6]) == '2':
#                logger.debug("HDLC protocol could be used if it was implemented")
#            else:
#                logger.debug("Another protocol could probably be used if it was implemented")
#
#        # for protocol C or E we now send an acknowledge and include the new baudrate parameter
#        # maybe todo
#        # we could implement here a baudrate that is fixed to somewhat lower speed if we need to
#        # read out a smartmeter with broken communication
#        Action = b'0' # Data readout, possible are also b'1' for programming mode or some manufacturer specific
#        Acknowledge = b'\x060'+ Baudrate_identification.encode() + Action + b'\r\n'
#
#        if Protocol_Mode == 'C':
#            # the speed change in communication is initiated from the reading device
#            time.sleep(wait_before_acknowledge)
#            logger.debug(f"Using protocol mode C, send acknowledge {Acknowledge} and tell smartmeter to switch to {NewBaudrate} Baud")
#            try:
#                sml_serial.write( Acknowledge )
#            except Exception as e:
#                logger.warning(f"Warning {e}")
#                return
#            time.sleep(wait_after_acknowledge)
#            #sml_serial.flush()
#            #sml_serial.reset_input_buffer()
#            if (NewBaudrate != InitialBaudrate):
#                # change request to set higher baudrate
#                sml_serial.baudrate = NewBaudrate
#
#        elif Protocol_Mode == 'B':
#            # the speed change in communication is initiated from the smartmeter device
#            time.sleep(wait_before_acknowledge)
#            logger.debug(f"Using protocol mode B, smartmeter and reader will switch to {NewBaudrate} Baud")
#            time.sleep(wait_after_acknowledge)
#            #sml_serial.flush()
#            #sml_serial.reset_input_buffer()
#            if (NewBaudrate != InitialBaudrate):
#                # change request to set higher baudrate
#                sml_serial.baudrate = NewBaudrate
#        else:
#            logger.debug(f"No change of readout baudrate, "
#                            "smartmeter and reader will stay at {NewBaudrate} Baud")
#
#        # now read the huge data block with all the OBIS codes
#        logger.debug("Reading OBIS data from smartmeter")
#        response = read_data_block_from_serial(sml_serial, None)
#    else:
#        # only listen mode, starts with / and last char is !
#        # data will be in between those two
#        response = read_data_block_from_serial(sml_serial, b'!', b'/')
#
#        Identification_Message = str(response,'utf-8').splitlines()[0]
#
#        manid = Identification_Message[1:4]
#        manname = manufacturer_ids.get(manid,'unknown')
#        logger.debug(f"The manufacturer for {manid} is {manname} (out of {len(manufacturer_ids)} given manufacturers)")
#
#
#    sml_serial.close()
#    logger.debug(f"Time for reading OBIS data: {format_time(time.time()- runtime)}")
#    runtime = time.time()
#
#    # Display performance of the serial communication
#    logger.debug(f"Whole communication with smartmeter took {format_time(time.time() - starttime)}")
#
#    if response.startswith(Acknowledge):
#        if not OnlyListen:
#            logger.debug("Acknowledge echoed from smartmeter")
#            response = response[len(Acknowledge):]
#
#    if use_checksum:
#        # data block in response may be capsuled within STX and ETX to provide error checking
#        # thus the response will contain a sequence of
#        # STX Datablock ! CR LF ETX BCC
#        # which means we need at least 6 characters in response where Datablock is empty
#        logger.debug("trying now to calculate a checksum")
#
#        if response[0] == STX:
#            logger.debug("STX found")
#        else:
#            logger.warning(f"STX not found in response='{' '.join(hex(i) for i in response[:10])}...'")
#
#        if response[-2] == ETX:
#            logger.debug("ETX found")
#        else:
#            logger.warning(f"ETX not found in response='...{' '.join(hex(i) for i in response[-11])}'")
#
#        if (len(response) > 5) and (response[0] == STX) and (response[-2] == ETX):
#            # perform checks (start with char after STX, end with ETX including, checksum matches last byte (BCC))
#            BCC = response[-1]
#            logger.debug(f"block check character BCC is {BCC}")
#            checksum = 0
#            for i in response[1:-1]:
#                checksum ^= i
#            if checksum != BCC:
#                logger.warning(f"checksum/protocol error: response={' '.join(hex(i) for i in response[1:-1])} "
#                                    "checksum={checksum}")
#                return
#            else:
#                logger.debug("checksum over data response was ok, data is valid")
#        else:
#            logger.warning("STX - ETX not found")
#    else:
#        logger.debug("checksum calculation skipped")
#
#    if not OnlyListen:
#        if len(response) > 5:
#            result = str(response[1:-4], 'ascii')
#            logger.debug(f"parsing OBIS codes took {format_time(time.time()- runtime)}")
#        else:
#            logger.debug("Sorry response did not contain enough data for OBIS decode")
#    else:
#        result = str(response, 'ascii')
#
#    suggested_cycle = (time.time() - starttime) + 10.0
#    config['suggested_cycle'] = suggested_cycle
#    logger.debug(f"the whole query took {format_time(time.time()- starttime)}, suggested cycle thus is at least {format_time(suggested_cycle)}")
#    return result
#
#if __name__ == '__main__':
#    import sys
#    import argparse
#    
#    parser = argparse.ArgumentParser(description='Query a smartmeter at a given port for SML output',
#                                     usage='use "%(prog)s --help" for more information',
#                                     formatter_class=argparse.RawTextHelpFormatter)
#    parser.add_argument('port', help='specify the port to use for the smartmeter query, e.g. /dev/ttyUSB0 or /dev/sml0')    
#    parser.add_argument('-v', '--verbose', help='print verbose information', action='store_true')
#    parser.add_argument('-t', '--timeout', help='maximum time to wait for a message from the smartmeter', type=float, default=3.0 )
#    parser.add_argument('-b', '--baudrate', help='initial baudrate to start the communication with the smartmeter', type=int, default=300 )
#    parser.add_argument('-d', '--device', help='give a device address to include in the query', default='' )
#    parser.add_argument('-q', '--querycode', help='define alternative query code\ndefault query code is ?\nsome smartmeters provide additional information when sending\nan alternative query code, e.g. 2 instead of ?', default='?' )
#    parser.add_argument('-l', '--onlylisten', help='Only listen to serial, no active query', action='store_true' )
#    parser.add_argument('-f', '--baudrate_fix', help='Keep baudrate speed fixed', action='store_false' )
#    parser.add_argument('-c', '--nochecksum', help='use a checksum', action='store_false' )
#    
#    args = parser.parse_args()
#        
#    config = {}
#
#    config['serialport'] = args.port
#    config['device'] = args.device
#    config['querycode'] = args.querycode
#    config['baudrate'] = args.baudrate
#    config['baudrate_fix'] = args.baudrate_fix
#    config['timeout'] = args.timeout
#    config['onlylisten'] = args.onlylisten
#    config['use_checksum'] = args.nochecksum
#    
#    if args.verbose:
#        logging.getLogger().setLevel( logging.DEBUG )
#        ch = logging.StreamHandler()
#        ch.setLevel(logging.DEBUG)
#        # create formatter and add it to the handlers
#        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s  @ %(lineno)d')
#        #formatter = logging.Formatter('%(message)s')
#        ch.setFormatter(formatter)
#        # add the handlers to the logger
#        logging.getLogger().addHandler(ch)
#    else:
#        logging.getLogger().setLevel( logging.DEBUG )
#        ch = logging.StreamHandler()
#        ch.setLevel(logging.DEBUG)
#        # just like print
#        formatter = logging.Formatter('%(message)s')
#        ch.setFormatter(formatter)
#        # add the handlers to the logger
#        logging.getLogger().addHandler(ch)
#
#
#    logger.info("This is SML Plugin running in standalone mode")
#    logger.info("==============================================")
#
#    result = query(config)
#    
#    if result is None:
#        logger.info(f"No results from query, maybe a problem with the serial port '{config['serialport']}' given ")
#        logger.info("==============================================")
#    elif len(result) > 0:
#        logger.info("These are the results of the query")
#        logger.info("==============================================")
#        logger.info(result)
#        logger.info("==============================================")
#    else:
#        logger.info("The query did not get any results!")
#        logger.info("Maybe the serial was occupied or there was an error")
#
#