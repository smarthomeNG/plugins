#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Thomas Hengsberg <thomas@thomash.eu>
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
#  upwards.
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

from lib.model.smartplugin import *

from .inverter import Inverter

class Kostalmodbus(SmartPlugin):
    PLUGIN_VERSION = '1.6.3'
    inverter = 'None'
    _items = []

    def __init__(self, sh, *args, **kwargs):
        self.inverter = Inverter(self.get_parameter_value("inverter_ip"),self.get_parameter_value("modbus_port"))
        self._cycle = int(self.get_parameter_value("update_cycle"))
        return

    def run(self):
        self.logger.debug("Run method called")
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True

    def stop(self):
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        for i in self.inverter.decRow:
            s = 'kostal_' + str(i)
            if self.has_iattr(item.conf, s):
                self._items.append(item)

    def poll_device(self):
        inverter_data = self.inverter.get_data()
        for item in self._items:
            for i in range (0,len(inverter_data)):
                s = 'kostal_' + str(inverter_data[i].adrDec)
                if self.has_iattr(item.conf, s):
                    item(self.inverter.registers[i].value)
