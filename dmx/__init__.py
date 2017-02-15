#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2011-2013 Marcus Popp                         marcus@popp.mx
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
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import threading
import serial

logger = logging.getLogger('')


class DMX():
    # _dim = 10^((n-1)/(253/3)-1) by JNK from KNX UF
    #_dim = [ 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 3, 4, 4, 4, 4, 4, 4, 4, 4, 4, 4, 5, 5, 5, 5, 5, 5, 5, 6, 6, 6, 6, 6, 6, 7, 7, 7, 7, 7, 8, 8, 8, 8, 8, 9, 9, 9, 9, 10, 10, 10, 10, 11, 11, 11, 12, 12, 12, 13, 13, 13, 14, 14, 14, 15, 15, 16, 16, 17, 17, 18, 18, 19, 19, 20, 20, 21, 21, 22, 22, 23, 24, 24, 25, 26, 26, 27, 28, 29, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 46, 47, 48, 50, 51, 52, 54, 55, 57, 58, 60, 62, 63, 65, 67, 69, 71, 73, 75, 77, 79, 81, 83, 86, 88, 90, 93, 95, 98, 101, 104, 106, 109, 112, 115, 119, 122, 125, 129, 132, 136, 140, 144, 148, 152, 156, 160, 165, 169, 174, 179, 184, 189, 194, 199, 205, 211, 216, 222, 228, 235, 241, 248, 255 ]

    def __init__(self, smarthome, tty, interface='nanodmx'):
        self._sh = smarthome
        self._is_connected = False
        self._lock = threading.Lock()

        try:
            self._port = serial.Serial(tty, 38400, timeout=1)
        except:
            logger.error("Could not open {}.".format(tty))
            return
        else:
            self._is_connected = True
        if interface == 'nanodmx':
            self.send = self.send_nanodmx
            if not self._send_nanodmx("C?"):
                logger.warning("Could not communicate with dmx adapter.")
                self._is_connected = False
        elif interface == 'enttec':
            self._enttec_data = bytearray(512)
            self.send = self.send_enttec
        else:
            logger.error("Unknown interface: {0}".format(interface))

    def _send_nanodmx(self, data):
        if not self._is_connected:
            return False
        self._lock.acquire()
        try:
            self._port.write(data.encode())
            ret = self._port.read(1)
        except:
            logger.warning("Problem sending data to dmx adapter.")
            ret = False
        finally:
            self._lock.release()
        if ret == b'G':
            return True
        else:
            return False

    def _send_enttec(self, data):
        if not self._is_connected:
            return False
        self._lock.acquire()
        self._port.write(data)
        self._lock.release()
        return True

    def run(self):
        self.alive = True

    def stop(self):
        self._port.close()
        self.alive = False

    def send_nanodmx(self, channel, value):
        self._send_nanodmx("C{0:03d}L{1:03d}".format(int(channel), int(value)))

    def send_enttec(self, channel, value):
        START_VAL = 0x7E
        END_VAL = 0xE7

        LABELS = {
           'GET_WIDGET_PARAMETERS' :3,  #unused
           'SET_WIDGET_PARAMETERS' :4,  #unused
           'RX_DMX_PACKET'         :5,  #unused
           'TX_DMX_PACKET'         :6,
           'TX_RDM_PACKET_REQUEST' :7,  #unused
           'RX_DMX_ON_CHANGE'      :8,  #unused
        }

        START_DATA = 0x00

        self._enttec_data[channel] = int(value);

        packet = bytearray()
        packet.append(START_VAL)
        packet.append(LABELS['TX_DMX_PACKET'])
        packet.append(len(self._enttec_data) & 0xFF)
        packet.append((len(self._enttec_data) >> 8) & 0xFF)
        packet.append(START_DATA)
        packet.extend(self._enttec_data)
        packet.append(END_VAL)

        self._send_enttec(packet)

    def parse_item(self, item):
        if 'dmx_ch' in item.conf:
            channels = item.conf['dmx_ch']
            if isinstance(channels, str):
                channels = [channels, ]
            channels = list(map(int, channels))
            item.conf['dmx_ch'] = channels
            return self.update_item
        else:
            return None

    def update_item(self, item, caller=None, source=None, dest=None):
        #logger.debug("update dmx channel {0:03d}".format(item.dmx_ch))
        for channel in item.conf['dmx_ch']:
            self.send(channel, int(item()))
