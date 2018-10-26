#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2011 KNX-User-Forum e.V.           http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHome.py.    http://mknx.github.io/smarthome/
#
#  SmartHome.py is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
from plugins.roomba_980.roomba import Roomba
from lib.model.smartplugin import SmartPlugin
from lib.item import Items

class ROOMBA_980(SmartPlugin):

    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.0.0"

    logger = logging.getLogger(__name__)

    myroomba = None

    def __init__(self, sh, adress=None, blid=None, roombaPassword=None, cycle=900):
        self._sh = sh
        self._address = adress
        self._blid = blid
        self._roombaPassword = roombaPassword
        self._cycle = cycle

        self._status_batterie = None
        self._status_items = {}

        self.myroomba = Roomba(self._address, self._blid, self._roombaPassword)
        self.myroomba.connect()

    def parse_logic(self, logic):
        pass

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'roomba_980'):
            item_type = self.get_iattr_value(item.conf, 'roomba_980')
            if item_type == "start" or item_type == "stop" or item_type == "dock":
                return self.update_item

            self._status_items[item_type] = item

            self.logger.debug('{} item gefunden {}'.format(item_type, item))

    def run(self):
        self.scheduler_add(__name__, self.get_status, prio=5, cycle=self._cycle, offset=2)
        self.alive = True

    def stop(self):
        self.scheduler.remove(__name__)
        self.myroomba.disconnect()
        self.alive = False

    def __call__(self):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != __name__ and self.has_iattr(item.conf, 'roomba_980'):
            self.logger.debug('item_update {} '.format(item))
            if self.get_iattr_value(item.conf, 'roomba_980') == "start":
               if item() == True:
                   self.send_command("start")
            if self.get_iattr_value(item.conf, 'roomba_980') == "stop":
               if item() == True:
                   self.send_command("stop")
            if self.get_iattr_value(item.conf, 'roomba_980') == "dock":
               if item() == True:
                   self.send_command("dock")

    def get_status(self):
        status = self.myroomba.master_state

        for status_item in self._status_items:
          if status_item == "status_batterie":
             self._status_items[status_item](status['state']['reported']['batPct'],__name__)
          if status_item == "status_bin_full":
             self._status_items[status_item](status['state']['reported']['bin']['full'],__name__)
          if status_item == "status_cleanMissionStatus_phase":
             self._status_items[status_item](status['state']['reported']['cleanMissionStatus']['phase'],__name__)
          if status_item == "status_cleanMissionStatus_error":
             self._status_items[status_item](status['state']['reported']['cleanMissionStatus']['error'],__name__)

        self.logger.debug('Roomba_980: Status update')

    def send_command(self, command):
        if self.myroomba != None:
             self.myroomba.send_command(command)
             self.logger.debug('send command: {} to Roomba'.format(command))


