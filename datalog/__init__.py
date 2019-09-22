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
import time
import threading

from lib.model.smartplugin import SmartPlugin


class DataLog(SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = '1.5.0'

    filepatterns = {}
    logpatterns = {}
    cycle = 0
    _items = {}
    _buffer = {}
    _buffer_lock = None

    def __init__(self, smarthome, *args, **kwargs):
        self._sh = smarthome
        self.path = self.get_parameter_value('path')
        self.logger = logging.getLogger(__name__)

        filepatterns = self.get_parameter_value('filepatterns')
        logpatterns = self.get_parameter_value('logpatterns')
        cycle = self.get_parameter_value('cycle')

        newfilepatterns = {}
        if isinstance(filepatterns, str):
            filepatterns = [filepatterns]
        if isinstance(filepatterns, list):
            for pattern in filepatterns:
                key, value = pattern.split(':')
                newfilepatterns[key] = value
        elif isinstance(filepatterns, dict):
            newfilepatterns = filepatterns
        else:
            raise Exception("Type of argument filepatterns unknown: {}".format(type(filepatterns)))

        newlogpatterns = {}
        if isinstance(logpatterns, str):
            logpatterns = [logpatterns]
        if isinstance(logpatterns, list):
            for pattern in logpatterns:
                key, value = pattern.split(':')
                newlogpatterns[key] = value
        elif isinstance(logpatterns, dict):
            newlogpatterns = logpatterns
        else:
            raise Exception("Type of argument logpatterns unknown: {}".format(type(logpatterns)))

        for log in newfilepatterns:
            ext = newfilepatterns[log].split('.')[-1]
            if ext in newlogpatterns:
                self.filepatterns[log] = newfilepatterns[log]
                self.logpatterns[log] = newlogpatterns[ext]
            else:
                self.logger.warn('DataLog: Ignoring log "{}", log pattern missing!'.format(log))

        self.cycle = int(cycle)
        self._items = {}
        self._buffer = {}
        self._buffer_lock = threading.Lock()

        self.logger.info('DataLog: Initialized, logging to "{}"'.format(self.path))
        for log in self.filepatterns:
            self.logger.info('DataLog: Registered log "{}", file="{}", format="{}"'.format(log, self.filepatterns[log], self.logpatterns[log]))

    def run(self):
        self.alive = True
        self._sh.scheduler.add('DataLog', self._dump, cycle=self.cycle)

    def stop(self):
        self.alive = False
        self._dump()

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'datalog'):
            datalog = self.get_iattr_value(item.conf, 'datalog')
            if type(datalog) is list:
                logs = datalog
            else:
                logs = [datalog]

            found = False
            for log in logs:
                if log not in self.filepatterns:
                    self.logger.debug('Unknown log "{}" for item {}'.format(log, item.id()))
                    return None

                if log not in self._buffer:
                    self._buffer[log] = []

                if item.id() not in self._items:
                    self._items[item.id()] = []

                if log not in self._items[item.id()]:
                   self._items[item.id()].append(log)
                   found = True

            if found:
                return self.update_item

        return None

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'DataLog':
            pass

        if item.id() in self._items:
            for log in self._items[item.id()]:
                self._buffer[log].append({ 'time' : self._sh.now(), 'item' : item.id(), 'value' : item() })

    def _dump(self):
        data = {}
        now = self._sh.now()
        handles = {}

        for log in self._buffer:
            self._buffer_lock.acquire()
            self.logger.debug('Dumping log "{}" with {} entries ...'.format(log, len(self._buffer[log])))
            entries = self._buffer[log]
            self._buffer[log] = []
            self._buffer_lock.release()

            if len(entries):
                logpattern = self.logpatterns[log]

                try:
                    for entry in entries:
                        filename = self.filepatterns[log].format(**{ 'log' : log, 'year' : entry['time'].year, 'month' : entry['time'].month, 'day' : entry['time'].day })

                        if filename not in handles:
                            handles[filename] = open(self.path + '/' + filename, 'a')

                        data = entry
                        data['stamp'] = data['time'].timestamp();
                        handles[filename].write(logpattern.format(**data))

                except Exception as e:
                    self.logger.error('Error while writing to {}: {}'.format(filename, e))

        for filename in handles:
            handles[filename].close()

            self.logger.debug('Dump done!')
