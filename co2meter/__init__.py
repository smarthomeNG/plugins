#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Original CO2Meter project Copyright 2017 by Michael Heinemann
#  under MIT License (https://github.com/heinemml/CO2Meter/)
#  Adaptions as SmartHomeNG Plugin Copyright 2017 Marc René Frieß
#########################################################################
#
# This file is part of SmartHomeNG.
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
#
#########################################################################

import logging
import sys
import fcntl
import threading
import weakref
import time

from lib.model.smartplugin import SmartPlugin


class CO2Meter(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.3.0.1"

    CO2METER_CO2 = 0x50
    CO2METER_TEMP = 0x42
    CO2METER_HUM = 0x44
    HIDIOCSFEATURE_9 = 0xC0094806

    _key = [0xc4, 0xc6, 0xc0, 0x92, 0x40, 0x23, 0xdc, 0x96]
    _device = ""
    _values = {}
    _file = ""
    _running = True

    def __init__(self, smarthome, device="/dev/hidraw0", time_sleep=5):
        """
        Initalizes the plugin. The parameters described for this method are pulled from the entry in plugin.conf.

        :param smarthome:  The instance of the smarthome object, save it for later references
        :param device: Path where the raw usb data is retreived from (default: /dev/hidraw0)
        :param time_sleep: The time in seconds to sleep after a multicast was received
        """
        self._sh = smarthome
        self.logger = logging.getLogger(__name__)
        self._items = {}
        self._time_sleep = int(time_sleep)

        self._device = device
        self._file = open(device, "a+b", 0)

        set_report = [0] + self._key
        fcntl.ioctl(self._file, self.HIDIOCSFEATURE_9, bytearray(set_report))

        thread = threading.Thread(target=self._co2_worker, name="CO2Meter_READ", args=(weakref.ref(self),))
        thread.daemon = True
        thread.start()

    def run(self):
        """
        Run method for the plugin
        """
        self.alive = True

        while self.alive:
            data = self.get_data()
            self.logger.debug(data)
            if 'temperature' in self._items:
                self._items['temperature'](data['temperature'])
            if 'co2' in self._items:
                self._items['co2'](data['co2'])
            if 'humidity' in self._items:
                self._items['humidity'](data['humidity'])
            time.sleep(self._time_sleep)

    def stop(self):
        """
        Stop method for the plugin
        """
        self._running = False
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array

        :param item: The item to process.
        """
        if self.has_iattr(item.conf, 'co2meter_data_type'):
            self._items[self.get_iattr_value(item.conf, 'co2meter_data_type')] = item
    
    def _co2_worker(self, weak_self):
        while True:
            self = weak_self()
            if self is None:
                break
            self._read_data()

            if not self._running:
                break
            del self

    def _read_data(self):
        try:
            result = self._file.read(8)
            data = list(result)

            decrypted = self._decrypt(data)
            if decrypted[4] != 0x0d or (sum(decrypted[:3]) & 0xff) != decrypted[3]:
                self.logger.debug(self._hd(data), " => ", self._hd(decrypted), "Checksum error")
            else:
                operation = decrypted[0]
                val = decrypted[1] << 8 | decrypted[2]
                self._values[operation] = val
        except:
            self._running = False


    def _decrypt(self, data):
        cstate = [0x48, 0x74, 0x65, 0x6D, 0x70, 0x39, 0x39, 0x65]
        shuffle = [2, 4, 0, 7, 1, 6, 5, 3]

        phase1 = [0] * 8
        for i, j in enumerate(shuffle):
            phase1[j] = data[i]

        phase2 = [0] * 8
        for i in range(8):
            phase2[i] = phase1[i] ^ self._key[i]

        phase3 = [0] * 8
        for i in range(8):
            phase3[i] = ((phase2[i] >> 3) | (phase2[(i-1+8)%8] << 5)) & 0xff

        ctmp = [0] * 8
        for i in range(8):
            ctmp[i] = ((cstate[i] >> 4) | (cstate[i]<<4)) & 0xff

        out = [0] * 8
        for i in range(8):
            out[i] = (0x100 + phase3[i] - ctmp[i]) & 0xff

        return out

    @staticmethod
    def _hd(data):
        return " ".join("%02X" % e for e in data)


    def get_co2(self):
        if not self._running:
            raise IOError("worker thread couldn't read data")
        result = {}
        if self.CO2METER_CO2 in self._values:
            result = {'co2': self._values[self.CO2METER_CO2]}

        return result


    def get_temperature(self):
        if not self._running:
            raise IOError("worker thread couldn't read data")
        result = {}
        if self.CO2METER_TEMP in self._values:
            result = {'temperature': (self._values[self.CO2METER_TEMP]/16.0-273.15)}

        return result


    def get_humidity(self): # not implemented by all devices
        if not self._running:
            raise IOError("worker thread couldn't read data")
        result = {}
        if self.CO2METER_HUM in self._values:
            result = {'humidity': (self._values[self.CO2METER_HUM]/100.0)}
        return result


    def get_data(self):
        result = {}
        result.update(self.get_co2())
        result.update(self.get_temperature())
        result.update(self.get_humidity())

        return result
