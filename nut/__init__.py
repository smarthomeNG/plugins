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

import logging
import telnetlib
from lib.model.smartplugin import SmartPlugin

class NUT(SmartPlugin):
  PLUGIN_VERSION = '1.3.0'
  ALLOW_MULTIINSTANCE = True

  def __init__(self, sh, ups, cycle = 60, host = 'localhost', port = 3493, timeout = 5):
    self._sh = sh
    self._cycle = int(cycle)
    self._host = host
    self._port = port
    self._ups = ups
    self._timeout = timeout
    self._conn = None
    self._items = {}
    self.logger = logging.getLogger(__name__)
    self._sh.scheduler.add(__name__, self._read_ups, prio = 5, cycle = self._cycle)
    self.logger.info('Init NUT Plugin')
    
  def run(self):
    self.alive = True

  def stop(self):
    self.alive = False
    self._conn.close()

  def parse_item(self, item):
    if self.has_iattr(item.conf, 'nut_var'):
      var = self.get_iattr_value(item.conf, 'nut_var')
      self.logger.debug('bind item {} with variable {}'.format(item, var))
      self._items[var] = item
      return self.update_item

  def update_item(self, item, caller=None, source=None, dest=None):
    return

  def _read_ups(self):
    self._conn = telnetlib.Telnet(self._host, self._port)
    self._conn.write('LIST VAR {}\n'.format(self._ups).encode('ascii'))
    self._conn.read_until('BEGIN LIST VAR {}\n'.format(self._ups).encode('ascii'), self._timeout)
    result = self._conn.read_until("END LIST VAR {}\n".format(self._ups).encode('ascii'))
    self._conn.close()
    for line in result.decode().splitlines():
      cmd, ups, var, val = line.split(maxsplit = 3)
      if var in self._items:
        self.logger.debug('update {} with {}'.format(var, val.strip('"')))
        self._items[var](val.strip('"'))




