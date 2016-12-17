#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 Marc René Frieß                   rene.friess@gmail.com
#########################################################################
#  This file is part of SmartHomeNG.   
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
from miflora.miflora_poller import MiFloraPoller, \
    MI_CONDUCTIVITY, MI_MOISTURE, MI_LIGHT, MI_TEMPERATURE, MI_BATTERY
from lib.model.smartplugin import SmartPlugin

class Xiaomi(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.3.0.1"

    def __init__(self, smarthome, bt_addr, cycle=300):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param smarthome:  The instance of the smarthome object, save it for later references
        :param bt_addr: The Bluetooth address of the device bound to the plugin instance
        :param cycle: Cycle interval in seconds
        """         
        self._sh = smarthome
        self.logger = logging.getLogger(__name__) 	# get a unique logger for the plugin and provide it internally
        self._bt_addr = bt_addr
        self._cycle = int(cycle)
        self._items = []
                

    def run(self):
        """
        Run method for the plugin
        """        
        self.logger.debug("run method called")
        self._sh.scheduler.add(__name__, self._update_loop, prio=7, cycle=self._cycle)
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array

        :param item: The item to process.
        """
        if self.has_iattr(item.conf, 'xiaomi_data_type'):
            self.logger.debug("parse item: {0}".format(item))
            self._items.append(item)

    def _update_loop(self):
        try:
            poller = MiFloraPoller(self._bt_addr)

            for item in self._items:
                if self.get_iattr_value(item.conf, 'xiaomi_data_type') == 'temperature':
                    item(poller.parameter_value('temperature'))
                elif self.get_iattr_value(item.conf, 'xiaomi_data_type') == 'light':
                    item(poller.parameter_value(MI_LIGHT))
                elif self.get_iattr_value(item.conf, 'xiaomi_data_type') == 'moisture':
                    item(poller.parameter_value(MI_MOISTURE))
                elif self.get_iattr_value(item.conf, 'xiaomi_data_type') == 'conductivity':
                    item(poller.parameter_value(MI_CONDUCTIVITY))
                elif self.get_iattr_value(item.conf, 'xiaomi_data_type') == 'battery':
                    item(poller.parameter_value(MI_BATTERY))
                elif self.get_iattr_value(item.conf, 'xiaomi_data_type') == 'name':
                    item(poller.name())
                elif self.get_iattr_value(item.conf, 'xiaomi_data_type') == 'firmware':
                    item(poller.firmware_version())
        except Exception as e:
            self.logger.error(str(e))