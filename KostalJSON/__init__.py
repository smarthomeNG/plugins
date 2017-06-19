#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Wenger Florian                       <wenger@unifox.at>
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
from lib.model.smartplugin import SmartPlugin
import urllib.request, json
import time

class KostalJSON(SmartPlugin):
    """
    Kostal Solar Electric Inverter with UI-version >6.
    Please use kostal - plugin for inverters with ui version <6.
    Since UI-version 6 the inverter can answere requests with json.
    Unfortunately, I have only a simple inverter. Therefore, I can not test
    the values for other phases or a second DC Line-In.

    Based on the original Kostal Plugin 
    """
    ALLOW_MULTIINSTANCE = True

    PLUGIN_VERSION = "1.2.1"

    _keytable = {
       'operation_status' : 16780032,
       'dctot_w' : 33556736,
       'dc1_v' : 33555202,
       'dc1_a' : 33555201,
       'dc1_w' : 33555203,
       'dc2_v' : 33555458,
       'dc2_a' : 33555457,
       'dc2_w' : 33555459,
       'actot_w' : 67109120,
       'actot_Hz' : 67110400,
       'actot_cos' : 67110656,
       'actot_limitation' : 67110144,
       'ac1_v' : 67109378,
       'ac1_a' : 67109377,
       'ac1_w' : 67109379,
       'ac2_v' : 67109634,
       'ac2_a' : 67109633,
       'ac2_w' : 67109635,
       'ac3_v' : 67109890,
       'ac3_a' : 67109889,
       'ac3_w' : 67109891,
       'yield_day_wh' : 251658754,
       'yield_tot_kwh' : 251658753,
       'operationtime_h' : 251658496
    }

    def __init__(self, sh, ip, cycle=300):

        self._sh = sh
        self.logger = logging.getLogger(__name__)       # get a unique logger for the plugin and provide it internally
        self.logger.info('Init KostalJSON plugin')
        self.ip = ip
        self.cycle = int(cycle)
        self._items = []
        self._values = {}


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("run method KostalJSON called")
        self.alive = True
        
        
        self._sh.scheduler.add('KostalJSON', self._refresh, cycle=self.cycle)


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method KostalJSON called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array

        :param item: The item to process.
        """
        if 'kostal' in item.conf:
            kostal_key = item.conf['kostal']
            if kostal_key in self._keytable:
                self._items.append([item, kostal_key])
                return self.update_item
            else:
                self.logger.warn('invalid key {0} configured', kostal_key)
        return None
        if self.has_iattr(item.conf, 'foo_itemtag'):
            self.logger.debug("parse item: {0}".format(item))

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Kostal':
            pass

    def _refresh(self):
        start = time.time()
        try:
            kostalurl = 'http://' + self.ip + '/api/dxs.json?sessionid=SmartHomeNG'
            for kostal_key in self._keytable:
                value = self._keytable[kostal_key]
                kostalurl +='&dxsEntries=' + str(value)
            with urllib.request.urlopen(kostalurl) as url:
                data = json.loads(url.read().decode())

                for values in data['dxsEntries']:
                    kostal_key = str(list(self._keytable.keys())[list(self._keytable.values()).index(values['dxsId'])])
                    self._values[kostal_key] = str(values['value'])

                    if kostal_key == "operation_status":
                        if str(values['value']) == "0":
                            self._values[kostal_key] = "off"
                        if str(values['value']) == "2":
                            self._values[kostal_key] = "startup"
                        if str(values['value']) == "3":
                            self._values[kostal_key] = "feed in (mpp)"
                        if str(values['value']) == "6":
                            self._values[kostal_key] = "dc voltag low"

                for item_cfg in self._items:
                    if item_cfg[1] in self._values:
                        item_cfg[0](self._values[item_cfg[1]], 'Kostal')
        except Exception as e:
            self.logger.error(
                'could not retrieve data from {0}: {1}'.format(self.ip, e))
            return
        cycletime = time.time() - start
        self.logger.debug("cycle takes {0} seconds".format(cycletime))

"""
If the plugin is run standalone e.g. for test purposes the follwing code will be executed
"""
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    # todo
    # change PluginClassName appropriately
    PluginClassName(None).run()
