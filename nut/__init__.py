#!/usr/bin/env python3
#########################################################################
# Copyright 2017- 4d4mu                              bakowski.a@gmail.com
#########################################################################
#  Network UPS Tools for SmartHomeNG
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

import socket
from lib.model.smartplugin import SmartPlugin


class NUT(SmartPlugin):
    PLUGIN_VERSION = '1.3.5'
    ALLOW_MULTIINSTANCE = True

    def __init__(self, sh):
        """
        Initalizes the plugin.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._sh = sh
        self._cycle = self.get_parameter_value('cycle')
        self._host = self.get_parameter_value('host')
        self._port = self.get_parameter_value('port')
        self._ups = self.get_parameter_value('ups')
        self._timeout = self.get_parameter_value('timeout')

        self._items = {}
        self.logger.info('NUT Plugin initialized')

    def run(self):
        self.scheduler_add('poll_nut_device', self._read_ups, prio=5, cycle=self._cycle)
        self.alive = True

    def stop(self):
        self.alive = False
        self.scheduler_remove('poll_nut_device')

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'nut_var'):
            var = self.get_iattr_value(item.conf, 'nut_var')
            self.logger.debug('bind item {} with variable {}'.format(item, var))
            self._items[var] = item
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        return

    def _read_list(self, sock):
        """
        Read from ``sock`` until the end marker of the ``LIST VAR`` reply (or timeout/EOF).

        :return: bytes between the begin and end marker, empty if the begin marker never arrived
        """
        begin = 'BEGIN LIST VAR {}\n'.format(self._ups).encode('ascii')
        end = 'END LIST VAR {}\n'.format(self._ups).encode('ascii')
        buf = b''
        try:
            while end not in buf:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
        except socket.timeout:
            pass
        start = buf.find(begin)
        if start < 0:
            return b''
        return buf[start + len(begin) :].split(end, 1)[0]

    def _read_ups(self):
        self.logger.debug(f'Trying to connect to {self._host} on port {self._port}')
        try:
            with socket.create_connection((self._host, self._port), self._timeout) as sock:
                sock.sendall('LIST VAR {}\n'.format(self._ups).encode('ascii'))
                result = self._read_list(sock)
        except Exception as e:
            self.logger.info('Exception during sending in openWebsocket(): {0}'.format(e))
            return

        for line in result.decode().splitlines():
            cmd, ups, var, val = line.split(maxsplit=3)
            if var in self._items:
                self.logger.debug('update {} with {}'.format(var, val.strip('"')))
                self._items[var](val.strip('"'))
