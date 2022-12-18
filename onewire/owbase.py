#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014 Marcus Popp                         marcus@popp.mx
#  Copyright 2019-2020 Bernd Meiners                Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

__docformat__ = 'reStructuredText'

import socket
import logging
import time
import threading

class owex(Exception):
    pass

class owexpath(Exception):
    pass


# Message types see at https://owfs.org/index_php_page_owserver-message-types.html
OW_ERROR = 4294967295   # 0xFFFFFFFF or -1
OWMSG_ERROR = 0         # not used
OWMSG_NOP = 1           # No-Op (not used)
OWMSG_READ = 2          # read from 1-wire bus
OWMSG_WRITE = 3         # write to 1-wire bus
OWMSG_DIR = 4           # list 1-wire bus (one dir per message, quite inefficient)
OWMSG_SIZE = 5          # get data size (not used)
OWMSG_PRESENT = 6       # Is the specified component recognized and known?
OWMSG_DIRALL = 7        # list 1-wire bus, in one packet string, comma separated
OWMSG_GET = 8           # dirall or read depending on path
OWMSG_DIRALLSLASH = 9   # dirall but with directory entries getting a trailing '/'
OWMSG_GETSLASH = 10     # dirallslash or read depending on path

# Flags see https://owfs.org/index_php_page_owserver-flag-word.html
OWFLAG_OWNET_REQUEST =          0x00000100  # Ownet request (included for all ownet messages)
OWFLAG_UNCACHED =               0x00000020  # Implicit /uncached
OWFLAG_SAFEMODE =               0x00000010  # Restrict operations to reads and cached, more
OWFLAG_USE_ALIAS =              0x00000008  # Use aliases for known slaves (human readable names)
OWFLAG_PERSISTENCE =            0x00000004  # persistence
OWFLAG_INCLUDE_SPECIAL_DIRS =   0x00000002  # include special directories
# further flags are defined for other measurement units instead of
# Celsius, Millibar, or standard display /10.67C6697351FF

# Directory Messages
# see at https://www.owfs.org/index_php_page_directory-messages.html
DEV_resume =            0b0000000000000001  # supports RESUME command
DEV_alarm =             0b0000000000000010  # can trigger an alarm
DEV_ovdr =              0b0000000000000100  # support OVERDRIVE 
DEV_temp =              0b1000000000000000  # responds to simultaneous temperature convert 0x44
DEV_volt =              0b0100000000000000  # responds to simultaneous voltage convert 0x3C
DEV_chain =             0b0010000000000000  # supports CHAIN command

class OwBase(object):

    def __init__(self, host='127.0.0.1', port=4304):
        self.logger = logging.getLogger(__name__)

        self.address = (host, int(port))
        self.connected = False
        self._connection_attempts = 0
        self._connection_errorlog = 60

        self._lock = threading.Lock()
        self._flag = OWFLAG_OWNET_REQUEST + OWFLAG_PERSISTENCE + OWFLAG_INCLUDE_SPECIAL_DIRS
        self.owserver_flags = 0
        self.owserver_size = 0
        self.owserver_offset = 0
        self.version = 0
        self._unknown_sensor_already_warned = []
        self._unsupported_sensor_already_warned = []


    def connect(self):
        is_locked = self._lock.acquire()
        if is_locked:
            try:
                self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._sock.settimeout(2)
                self._sock.connect(self.address)
            except Exception as e:
                self._connection_attempts -= 1
                if self._connection_attempts <= 0:
                    if self.logger.isEnabledFor(logging.ERROR):
                        self.logger.error('1-Wire: could not connect to {0}:{1}: {2}'.format(*self.address, e))
                    self._connection_attempts = self._connection_errorlog
                return
            else:
                self.connected = True
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug('1-Wire: connected to {0}:{1}'.format(*self.address))
                self._connection_attempts = 0
            finally:
                self._lock.release()

    # some short definitions to call request function

    def read(self, path):   
        """
        Reads the value of a sensor at a given path
        """
        return self._request(path, cmd=OWMSG_READ)

    def write(self, path, value):
        """
        Writes the value to a sensor at a given path
        """
        return self._request(path, cmd=OWMSG_WRITE, value=value)

    def dir(self, path='/'):
        """
        Reads the directory starting with given path.
        As default the root path is assumed
        """
        return self._request(path, cmd=OWMSG_DIRALLSLASH).decode().strip('\x00').split(',')

    def tree(self, path='/', max_depth=None, with_values=False):
        """
        Calls itself recursively to create a tree of all mounted sensors, devices, settings, etc.
        Warnung: This can result in a couple of thousand lines and might take a long time
        """
        result = ""
        try:
            items = self.dir(path)
        except Exception as e:
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"dir({path}) raised an exception {e}, giving up")
        else:
            for item in items:
                if item.endswith('/'):
                    result = result + item + "\n"
                    if max_depth is not None and max_depth > 0:
                        subresult = self.tree(item, max_depth=max_depth-1, with_values=with_values)
                        if subresult is not None:
                            result += subresult
                else:
                    vstr = ""
                    if with_values:
                        try:
                            value = self.read(item)
                        except Exception as e:
                            value = ">>> value could not be read <<<"
                        else:
                            if value is not None:
                                vstr = f" --> {value}"
                            else:
                                vstr = "(None)"
                    result = result + item + vstr + "\n"
        return result

    def _request(self, path, cmd=OWMSG_GETSLASH, value=None):
        """
        Sends a request for data to owserver and waits for response
        Protocol described in https://owfs.org/index_php_page_owserver-protocol.html and
        the messages are part of `ow_message.h <https://github.com/owfs/owfs/blob/master/module/owlib/src/include/ow_message.h>`__
        ```
        /* message to owserver */
        struct server_msg {
            int32_t version;
            int32_t payload;
            int32_t type;
            int32_t control_flags;
            int32_t size;
            int32_t offset;
        };

        /* message to client */
        struct client_msg {
            int32_t version;
            int32_t payload;
            int32_t ret;
            int32_t control_flags;
            int32_t size;
            int32_t offset;
        };
        ```
        returns the payload of communication efforts
        """
        #if self.logger.isEnabledFor(logging.DEBUG):
        #    self.logger.debug("request for path='{}' with cmd='{} and value='{}' called".format(path, cmd, value))
        if not self.connected:
            #if self.logger.isEnabledFor(logging.DEBUG):
            #    self.logger.debug("no connection while request() was called. Retrying ...")
            self.connect()
        if not self.connected:
            raise ConnectionError("No connection to owserver.")
        islocked = self._lock.acquire()
        if islocked:
            try:
                if value is not None:
                    payload = path + '\x00' + str(value) + '\x00'
                    data = len(str(value)) + 1
                else:
                    payload = path + '\x00'
                    data = 65536
                header = bytearray(24)
                #header[0:3]                                                # version, currently defined as 0
                header[4:8] = len(payload).to_bytes(4, byteorder='big')     # payload
                header[8:12] = cmd.to_bytes(4, byteorder='big')             # type
                header[12:16] = self._flag.to_bytes(4, byteorder='big')     # control flags
                header[16:20] = data.to_bytes(4, byteorder='big')           # size
                #header[20:23]                                              # offset
                try:
                    data = header + payload.encode()
                    self._sock.sendall(data)
                except Exception as e:
                    self.close()
                    raise owex("error sending request: {0}".format(e))
                    
                while True:
                    header = bytearray()
                    try:
                        header = self._sock.recv(24)
                    except socket.timeout:
                        self.close()
                        raise owex("error receiving header: timeout")
                    except Exception as e:
                        self.close()
                        raise owex("error receiving header: {0}".format(e))
                        
                    if len(header) != 24:
                        self.close()
                        raise owex("error receiving header: no or not enough data {} bytes".format(len(header)))

                    self.version = int.from_bytes(data[0:4], byteorder='big')
                    length = int.from_bytes(header[4:8], byteorder='big')
                    ret = int.from_bytes(header[8:12], byteorder='big')
                    self.owserver_flags = int.from_bytes(data[12:16], byteorder='big')
                    self.owserver_size = int.from_bytes(data[16:20], byteorder='big')
                    self.owserver_offset = int.from_bytes(data[20:24], byteorder='big')
                    if not length == OW_ERROR:
                        break
                        
                if ret == OW_ERROR:  # unknown path
                    raise owexpath("path '{0}' not found.".format(path))
                    
                if length == 0:
                    if cmd != 3:
                        raise owex('no payload for {0}'.format(path))
                    return
                try:
                    payload = self._sock.recv(length)
                except socket.timeout:
                    self.close()
                    raise owex("error receiving payload: timeout")
                except Exception as e:
                    self.close()
                    raise owex("error receiving payload: {0}".format(e))
            finally:
                self._lock.release()
        else:
            raise owex("error acquiring lock")

        #if self.logger.isEnabledFor(logging.DEBUG):
        #    self.logger.debug("request successfully finished, return '{}'".format(payload))
        return payload

    def close(self):
        """
        Closes the tcp connection with owserver
        """
        self.connected = False
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self._sock.close()
        except:
            pass

    def identify_sensor(self, path):
        """
        Reads from owserver a path like '/bus.0/2816971B03000059/  and gets the type of an attached sensor.
        Then returns a dict of possible types and the subpath for evaluating them or 
        None if an error occurred or if there is no way found to read out
        Details for most sensor types can be found at http://owfs.sourceforge.net/family.html
        """
        try:
            typ = self.read(path + 'type').decode()
        except Exception:
            #if self.logger.isEnabledFor(logging.DEBUG):
            #    self.logger.debug("path '{0}' not found.".format(path+'type'))
            return
        addr = path.split("/")[-2]      # sensor device id like 28.16971B03000059 or an alias like MultiTemp
        # return possible types
        if typ == 'DS18B20':            # Temperature
            return {'T': 'temperature', 'T9': 'temperature9', 'T10': 'temperature10', 'T11': 'temperature11', 'T12': 'temperature12'}
        elif typ == 'DS18S20':          # Temperature
            return {'T': 'temperature'}
        elif typ == 'DS2438':           # Multisensor (see at https://www.owfs.org/index_php_page_ds2438.html)
            # sensor subtype needs to be further identified by page3 of its memory
            try:
                page3 = self.read(path + 'pages/page.3')  # .encode('hex').upper()
            except Exception as e:
                if self.logger.isEnabledFor(logging.WARNING):
                    self.logger.warning("1-Wire: sensor {0} problem reading page.3: {1}".format(addr, e))
                return
            # check if a light sensor could be available, if so then path 'vis' is present
            try: 
                vis = float(self.read(path + 'vis').decode())
            except Exception:
                vis = 0
            if vis > 0:
                keys = {'T': 'temperature', 'H': 'HIH4000/humidity', 'L': 'vis'}
            else:
                keys = {'T': 'temperature', 'H': 'HIH4000/humidity'}
            # check if a voltage from 1-wire bus can be measured
            try:
                vdd = float(self.read(path + 'VDD').decode())
            except Exception:
                vdd = None
            if vdd is not None:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug("1-Wire: sensor {0} voltage: {1}".format(addr, vdd))
                keys['VDD'] = 'VDD'
            # certain multisensors have also other infos to pass.
            if page3[0] == 0x19:
                return keys
            elif page3[0] == 0xF2:      # BMS
                return keys
            elif page3[0] == 0xF3:      # AMSv2 TH
                return keys
            elif page3[0] == 0xF4:      # AMSv2 V
                return {'V': 'VAD'}
            elif page3[0] == 0xF7:
                # ToDo: check if this data here is valid
                return keys
                # 
                #if self.logger.isEnabledFor(logging.WARNING) and not addr in self._unsupported_sensor_already_warned:
                #    self.logger.warning("1-Wire: unsupported multisensor {0} {1} page3: {2}".format(addr, typ, page3))
                #    self._unsupported_sensor_already_warned.append(addr)
                #    return
            elif page3 == b'HUMIDIT3':  # DataNab
                keys['H'] = 'humidity'
                return keys
            else:
                if self.logger.isEnabledFor(logging.WARNING):
                    self.logger.warning("1-Wire: unknown sensor {0} {1} page3: {2}".format(addr, typ, page3))
                keys.update({'V': 'VAD', 'VDD': 'VDD'})
                return keys
        elif typ == 'DS2401':           # iButton
            return {'B': 'iButton'}
        elif typ in ['DS2413', 'DS2406']:  # I/O
            return {'IA': 'sensed.A', 'IB': 'sensed.B', 'OA': 'PIO.A', 'OB': 'PIO.B'}
        elif typ == 'DS1420':           # Busmaster
            return {'BM': 'Busmaster'}
        elif typ == 'DS2423':           # Counter
            return {'CA': 'counter.A', 'CB': 'counter.B'}
        elif typ == 'DS2408':           # I/O
            return {'I0': 'sensed.0', 'I1': 'sensed.1', 'I2': 'sensed.2', 'I3': 'sensed.3', 'I4': 'sensed.4', 'I5': 'sensed.5', 'I6': 'sensed.6', 'I7': 'sensed.7', 'O0': 'PIO.0', 'O1': 'PIO.1', 'O2': 'PIO.2', 'O3': 'PIO.3', 'O4': 'PIO.4', 'O5': 'PIO.5', 'O6': 'PIO.6', 'O7': 'PIO.7'}
        elif typ == 'DS2431':          # 1K EEprom
            if self.logger.isEnabledFor(logging.WARNING) and addr not in self._unsupported_sensor_already_warned:
                self._unsupported_sensor_already_warned.append(addr)
                self.logger.warning("1-Wire: unsupported device {0} {1}".format(addr, typ))
            return
        elif typ == 'DS2433':          # 4K EEprom
            if self.logger.isEnabledFor(logging.WARNING) and addr not in self._unsupported_sensor_already_warned:
                self._unsupported_sensor_already_warned.append(addr)
                self.logger.warning("1-Wire: unsupported device {0} {1}".format(addr, typ))
            return
        else:
            # unknown sensor type found, warn but only once
            if self.logger.isEnabledFor(logging.WARNING) and addr not in self._unknown_sensor_already_warned:
                self._unknown_sensor_already_warned.append(addr)
                self.logger.warning("1-Wire: unknown sensor {0} {1}".format(addr, typ))
            return
