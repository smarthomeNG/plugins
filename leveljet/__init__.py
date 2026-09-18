#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013 KNX-User-Forum e.V.           http://knx-user-forum.de/
#  Copyright 2017-2026 knatter
#########################################################################
#  Leveljet plugin for SmartHome.py.         http://mknx.github.io/smarthome/
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
import time
import serial
from crccheck.crc import Crc16Buypass
from lib.model.smartplugin import SmartPlugin


class LevelJet(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = '1.1.0'

    _ljetdata = ['dist', 'level', 'liter', 'percent', 'outflags']

    def __init__(self, smarthome):
        self._sh = smarthome
        self.enable = False
        self.alive = False
        self._serial = None        
        self._items = []
        self.logger = logging.getLogger(__name__)

        serialport = self.get_parameter_value('serialport')
        baudrate = self.get_parameter_value('baudrate')
        update_cycle = self.get_parameter_value('update_cycle') 
 
        self._update_cycle = update_cycle
        try:
            self._serial = serial.Serial(serialport, baudrate, timeout=2)
            self.enable = True
        except Exception as e:
            self.logger.error(f"leveljet: Serial Port could not be opened. Fehler: {e!r}")
       
    def run(self):
        if self._serial is None:
            self.logger.error("leveljet: run() aborted, serial port not available")
            return
        self.alive = True
        self._sh.scheduler.add('LevelJet', self._update_values, prio=5, cycle=self._update_cycle)        

    def stop(self):
        self.alive = False
        if self._serial is not None:
            self._serial.close()
        # self.logger.debug("Plugin '{}': stop method called".format(self.get_fullname()))
        self._sh.scheduler.remove('LevelJet')

    def _update_values(self):
        start = time.time()
        try:
            self._serial.reset_input_buffer()
            rcv = bytes()
            prev_length = 0
            while self.alive:
                rcv += self._serial.read()
                length = len(rcv)
                # break if timeout or Frame found
                if (length >= 12) and (rcv[-12] == 0x00) and (rcv[-11] == 0x10):
                    break
                if length == prev_length:
                    self.logger.warning('leveljet: read timeout! - rcv={}'.format(rcv))
                    return
                prev_length = length
        except Exception as e:
            self.logger.warning('leveljet:Exception {0}'.format(e))
            return
        self.logger.debug('leveljet: reading took: {:.2f}s'.format(time.time() - start))
        # perform check (checksum match)
        crc = Crc16Buypass.calc(rcv[-12:-2])
        crc_high, crc_low = divmod(crc, 0x100)
        if (rcv[-2] != crc_low) or (rcv[-1] != crc_high):
            self.logger.warning(
                'leveljet: checksum error: RX-Frame={} checksum={}'.format(' '.join(hex(i) for i in rcv), hex(crc))
            )
            return
        self.logger.debug('leveljet: RX-Frame={}'.format(' '.join(hex(i) for i in rcv)))
        for item in self._items:
            ljet_cmd = item.conf['ljet_cmd']
            if ljet_cmd == self._ljetdata[0]:  # dist
                value = (rcv[-9] << 8) + rcv[-10]
            elif ljet_cmd == self._ljetdata[1]:  # level
                value = (rcv[-7] << 8) + rcv[-8]
            elif ljet_cmd == self._ljetdata[2]:  # liter
                value = ((rcv[-5] << 8) + rcv[-6]) * 10
            elif ljet_cmd == self._ljetdata[3]:  # percent
                value = rcv[-4]
            elif ljet_cmd == self._ljetdata[4]:  # outflags:
                value = rcv[-3]
            else:
                self.logger.warning('leveljet: unknown ljetcmd: {}'.format(ljet_cmd))
                continue
            # self.logger.debug("leveljet: {}:{}".format(ljet_cmd, value))
            item(value, 'LevelJet', 'refresh')
        return

    def parse_item(self, item):
        if 'ljet_cmd' in item.conf:
            self._items.append(item)
        return
