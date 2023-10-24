#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013 KNX-User-Forum e.V.            http://knx-user-forum.de/
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
import subprocess # we scrape apcaccess output
from lib.model.smartplugin import SmartPlugin

logger = logging.getLogger(__name__)

ITEM_TAG = ['apcups']
class APCUPS(SmartPlugin):

    PLUGIN_VERSION = "1.4.0"

    def __init__(self, sh):
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self._host = self.get_parameter_value('host')
        self._port = self.get_parameter_value('port')
        self._cycle = self.get_parameter_value('cycle')
        self._items = {}
        self._lock = threading.Lock()
        # the command goes here
        self._command = f"/sbin/apcaccess status {self._host}:{ self._port}"
        self._last_readout = ""

    def run(self):
        self.alive = True
        self.scheduler_add(self.get_shortname(), self.update_status, cycle=self._cycle)

    def stop(self):
        self.alive = False
        self.scheduler_remove(self.get_shortname())


    def parse_item(self, item):
        if self.has_iattr(item.conf, ITEM_TAG[0]):
            apcups_key = (self.get_iattr_value(item.conf, ITEM_TAG[0])).lower()
            self._items[apcups_key]=item
            self.logger.debug(f"item {item} added with apcupd_key {apcups_key}")
        # no callback for any item needed as this plugin is readonly
        return None

    def update_item(self, item, caller=None, source=None, dest=None):
        pass

    def update_status(self):
        """
        Start **apcaccess** on a shell, capture the output and parse it.
        The items attribut parameter will be matched against the shell output
        """
        
        if not self._lock.acquire(timeout=1):
            return
        try:
            self._command = f"/sbin/apcaccess status {self._host}:{self._port}"   # the command goes here
            output = subprocess.check_output(self._command.split(), shell=False)
            # decode byte string to string
            output = output.decode()
            # save for webinterface
            self._last_readout = output
            for line in output.split('\n'):
                (key,spl,val) = line.partition(': ')
                key = key.rstrip().lower()
                val = val.strip()

                if key in self._items:
                     self.logger.debug(f"update item {self._items[key]} with {val}")
                     item = self._items[key]
                     self.logger.debug(f"Item type {item.type()}")
                     if item.type() == 'str':
                         item (val, self.get_shortname())
                     else:
                         val = val.split(' ', 1)[0]  # ignore anything after 1st space
                         item (float(val), self.get_shortname())
            return
        except Exception as e:
            self.logger.error(f"Problem {e} reading output from call to {self._command}")
        finally:
            self._lock.release()

