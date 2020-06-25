#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2013-     Oliver Hinckel                  github@ollisnet.de
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
import datetime
import time
import lib.log

from lib.model.smartplugin import SmartPlugin


class MemLog(SmartPlugin):

    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = '1.3.0'

    _log = None
    _items = {}

    def __init__(self, smarthome, name, mapping = ['time', 'thread', 'level', 'message'], items = [], maxlen = 50):
        logger = logging.getLogger(__name__)
        self._sh = smarthome
        self.name = name
        self._log = lib.log.Log(smarthome, name, mapping, maxlen)
        self._items = items

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'memlog') and self.get_iattr_value(item.conf, 'memlog') == self.name:
            return self.update_item
        else:
            return None

    def parse_logic(self, logic):
        if 'memlog' in logic.conf:
            return self.trigger_logic
        else:
            return None

    def __call__(self, param1=None, param2=None):
        if type(param1) == list and type(param2) == type(None):
            self.log(param1)
        elif type(param1) == str and type(param2) == type(None):
            self.log([param1])
        elif type(param1) == str and type(param2) == str:
            self.log([param2], param1)

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'MemLog':
            if self.get_iattr_value(item.conf, 'memlog') == self.name:
                if len(self._items) == 0:
                    logvalues = [item()]
                else:
                    logvalues = []
                    for item in self._items:
                        logvalues.append(self._sh.return_item(item)())

                self.log(logvalues, 'INFO')

    def trigger_logic(self, logic, by=None, source=None, dest=None):
        if self.name == logic.conf['memlog']:
            if 'memlog_message' in logic.conf:
                msg = logic.conf['memlog_message']
            else:
                msg = "Logic {} triggered"
            self.log([msg.format(**{'plugin' : self, 'logic' : logic, 'by' : by, 'source' : source, 'dest' : dest})]) 

    def log(self, logvalues, level = 'INFO'):
        if len(logvalues):
            log = []
            for name in self._log.mapping:
                if name == 'time':
                    log.append(self._sh.now())
                elif name == 'thread':
                    log.append(threading.current_thread().name)
                elif name == 'level':
                    log.append(level)
                else:
                    log.append(logvalues[0])
                    logvalues = logvalues[1:]

            self._log.add(log)

