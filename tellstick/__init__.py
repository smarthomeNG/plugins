#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2014-2015 Matthieu Gaigniere                matthieu@ip42.eu
#########################################################################
##  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
#  How to use 
#  -----------
#
#  To activate the plugin in `etc/plugin.conf` :
#  
#      [tellstick]
#        class_name = Tellstick
#        class_path = plugins.tellstick
#  
#  
#  To add a tellstick item in items/items.conf :
#  
#      - ts_id : id of tellstick object
#  
#  Example :
#  
#      [kitchen]
#        [[shutter]]
#          type = bool
#          ts_id = 1
#
#########################################################################

import logging
import threading
import struct
import binascii
import os

logger = logging.getLogger('')


class Tellstick:

    def __init__(self, smarthome):
        self._sh = smarthome

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        if 'ts_id' in item.conf:
            id_ = item.conf['ts_id']
            logger.debug("Tellstick: item {0} with ID {1} found".format(item, id_))
            return self.update_item
        return None

    def update_item(self, item, caller=None, source=None, dest=None):
        if 'ts_id' in item.conf:
            new_value = item()
            status = 'on' if new_value else 'off'
            logger.info("Tellstick: update item {0} with status {1}".format(item, status))
            self._exec_cmd("tdtool --{0} {1}".format(status, item.conf['ts_id']))

    def _exec_cmd(self, cmd): 
        logger.debug("Tellstick cmd: {0}".format(cmd))
        os.system(cmd)

    def parse_logic(self, logic):
        logger.debug("Launch telegram, receive : {0}".format(repr(logic)))
        return None
