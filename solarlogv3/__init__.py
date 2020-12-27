#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2017 klab
#  Copyright 2020  Christian Michels
#  Version 1.3.2
#########################################################################
#  Free for non-commercial use
#  
#  Plugin for the software SmartHome.py (NG), which allows to read
#  devices such as the Solarlog with Firmware 3.xx
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHome.py is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py (NG). If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import logging
from datetime import datetime, timedelta
import json
import http.client
from lib.model.smartplugin import SmartPlugin


class SolarlogFw3(SmartPlugin):
     ALLOW_MULTIINSTANCE = False
     PLUGIN_VERSION = '1.3.2'

     def __init__(self, sh, *args, **kwargs):
          self.logger = logging.getLogger(__name__)
          self.logger.debug("SolarlogFw3 starting")
          self._sh = sh

          # get the parameters for the plugin (as defined in metadata plugin.yaml):
          self._host = self.get_parameter_value('host')
          self._cycle = self.get_parameter_value('cycle')

          self._items = {}

     def run(self):
          self.alive = True
          self._sh.scheduler.add('SolarlogFw3', self.update_status, cycle=self._cycle)

     def stop(self):
          self.alive = False

     def parse_item(self, item):
          if 'solarfw3' in item.conf:
               solarfw3_key = item.conf['solarfw3']
               self._items[solarfw3_key]=item
               return self.update_item
          else:
               return None

     def parse_logic(self, logic):
          pass

     def update_item(self, item, caller=None, source=None, dest=None):
                          if caller != 'plugin':
                              self.logger.info("update item: {0}".format(item.id()))

     def update_status(self):
          for parameter in self._items:
               params = '{"801":{"170":null}}'
               paramsbytes = params.encode('utf-8')
               headers = {"Content-Type": "application/json",
                          "Accept": "text/plain"}
               conn = http.client.HTTPConnection(self._host)
               conn.request("POST", "/getjp", params, headers)
               response = conn.getresponse()
               data=response.read()
               jsondata = json.loads(data.decode('utf-8'))
               value = jsondata['801']['170'][str(parameter)]
               if parameter in self._items:
                    item = self._items[parameter]
                    item (value, 'solarfw3')
          return
