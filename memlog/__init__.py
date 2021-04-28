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

    PLUGIN_VERSION = '1.6.0'

    def __init__(self, sh, *args, **kwargs):

        self.name = self.get_parameter_value('name')
        self.mappings = self.get_parameter_value('mappings')
        self.items = self.get_parameter_value('items')
        self.maxlen = self.get_parameter_value('maxlen')

        self._log = lib.log.Log(self.get_sh(), self.name, self.mappings, self.maxlen)

    def run(self):
        self.alive = True

    def stop(self):
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, "memlog"):
            if self.get_iattr_value(item.conf, 'memlog') == self.name:
                return self.update_item
        return None

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        This will be called after a registered item was changed.
        If no items were given within definition in ``etc/plugin.yaml``
        the value of this updated item will be logged.
        Otherwise the values of all defined items in ``etc/plugin.yaml``.
        If items are defined, then four items should be named,
        each with the following purpose:

        * Item A - the value of this item is entered as the timestamp
        * Item B - the value of this item is entered as the thread info
        * Item C - the value of this item is entered as the level of log message
        * Item D - the value of this item is entered as the message

        Using Items this way it is possible to set the values of those items first
        and then trigger the item which has the ``memlog`` attribute.
        """
        if self.alive and caller != self.get_shortname():
            if self.get_iattr_value(item.conf, 'memlog') == self.name:
                if len(self.items) == 0:
                    logvalues = [item()]
                else:
                    logvalues = []
                    for item in self.items:
                        logvalues.append(self.get_sh().return_item(item)())

                self.log(logvalues, 'INFO')

    def parse_logic(self, logic):
        """
        If a logic contains the attribute ``memlog`` then a trigger of this logic will
        lead to a call
        """
        if 'memlog' in logic.conf:
            return self.trigger_logic
        else:
            return None

    def trigger_logic(self, logic, by=None, source=None, dest=None):
        """
        This function is called when memlog attribute is given for a logic.
        If attribute value is equal to this memlogs name then a log entry
        will be generated.
        The attribute ``memlog_message`` may contain the following placeholders for format instruction:

        - plugin
        - logic
        - by
        - source
        - dest

        If no attribute ``memlog_message`` is given, a default log entry ``Logic {} triggered`` will be generated.
        """
        if self.name == logic.conf['memlog']:
            if 'memlog_message' in logic.conf:
                msg = logic.conf['memlog_message']
            else:
                msg = "Logic {logic.name} triggered"
            self.log([msg.format(**{'plugin' : self, 'logic' : logic, 'by' : by, 'source' : source, 'dest' : dest})])

    def __call__(self, param1=None, param2=None):
        if type(param1) == list and type(param2) == type(None):
            self.log(param1)
        elif type(param1) == str and type(param2) == type(None):
            self.log([param1])
        elif type(param1) == str and type(param2) == str:
            self.log([param2], param1)

    def log(self, logvalues, level = 'INFO'):
        """

        """
        if len(logvalues):
            log = []
            for name in self._log.mapping:
                if name == 'time':
                    log.append(self.get_sh().now())
                elif name == 'thread':
                    log.append(threading.current_thread().name)
                elif name == 'level':
                    log.append(level)
                else:
                    log.append(logvalues[0])
                    logvalues = logvalues[1:]

            self._log.add(log)

