#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2012- Oliver Hinckel github@ollisnet.de
# Copyright 2017 Wenger Florian  wenger@unifox.at
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
from lib.utils import Utils
import urllib.request, json
import time
import re

class Kostal(SmartPlugin):
    """
    Since UI-version 6 the inverter can answere requests with json.
    Unfortunately, I have only a simple inverter. Therefore, I can not test
    the values for other phases or a second DC Line-In.
    See README.md for more details
    """
    ALLOW_MULTIINSTANCE = True

    PLUGIN_VERSION = "1.3.1.2"

    _key2json = {
       'operation_status' : 16780032,
       'dctot_w' : 33556736,
       'dc1_v' : 33555202,
       'dc1_a' : 33555201,
       'dc1_w' : 33555203,
       'dc2_v' : 33555458,
       'dc2_a' : 33555457,
       'dc2_w' : 33555459,
       'dc3_v' : 33555714,
       'dc3_a' : 33555713,
       'dc3_w' : 33555715,
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
       'yield_day_kwh' : 251658754,
       'yield_tot_kwh' : 251658753,
       'operationtime_h' : 251658496
    }
    _key2td = {
        'actot_w': 9,
        'yield_tot_kwh': 12,
        'yield_day_kwh': 21,
        'operation_status': 27,
        'dc1_v': 45,
        'dc2_v': 69,
        'dc3_v': 93,
        'dc1_a': 54,
        'dc2_a': 78,
        'dc3_a': 102,
        'ac1_v': 48,
        'ac2_v': 72,
        'ac3_v': 96,
        'ac1_w': 57,
        'ac2_w': 81,
        'ac3_w': 105
    }

    def __init__(self, sh, ip, user="pvserver", passwd="pvwr",cycle=300, datastructure="html"):
        self._sh = sh
        self.logger = logging.getLogger(__name__)
        self.logger.info('Init Kostal plugin')
        self.user = user
        self.passwd = passwd
        self.cycle = int(cycle)
        self._items = {}
        if Utils.is_ip(ip):
            self.ip = ip
        else:
            self.logger.error(str(ip) + " is not a valid IP")
        if datastructure == "html":
            self._keytable = self._key2td
            #self.datastructure = "html"
            self.datastructure = self._html
        else:
            self._keytable = self._key2json
            #self.datastructure = "json"
            self.datastructure = self._json

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("run method Kostal called")
        self.alive = True
        self._sh.scheduler.add('Kostal', self._refresh, cycle=self.cycle)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method Kostal called")
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array
        :param item: The item to process.
        """
        if self.has_iattr(item.conf, 'kostal'):
            self._items[self.get_iattr_value(item.conf, 'kostal')] = item
            self.logger.debug("parse item: {0}".format(item))
            return self.update_item

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Write items values
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        pass

    def _html(self):
        #HTML-OLD-Coding
        try:
            data = self._sh.tools.fetch_url(
                'http://' + self.ip + '/', self.user, self.passwd, timeout=2).decode()
            # remove all attributes for easy findall()
            data = re.sub(r'<([a-zA-Z0-9]+)(\s+[^>]*)>', r'<\1>', data)
            # search all TD elements
            table = re.findall(r'<td>([^<>]*)</td>', data, re.M | re.I | re.S)
            for kostal_key in self._keytable:
                value = table[self._keytable[kostal_key]].strip()
                if 'x x x' not in value:
                    self.logger.debug('set {0} = {1}'.format(kostal_key, value))
                    if kostal_key in self._items:
                        self._items[kostal_key](value)
        except Exception as e:
            self.logger.error(
                'could not retrieve data from {0}: {1}'.format(self.ip, e))
            return

    def _json(self):
        #NEW-JSON-Coding
        try:
            # generate url; fetching only needed elements
            kostalurl = 'http://' + self.ip + '/api/dxs.json?sessionid=SmartHomeNG'
            for item in self._items:
                value = self._keytable[item]
                kostalurl +='&dxsEntries=' + str(value)
            with urllib.request.urlopen(kostalurl) as url:
                data = json.loads(url.read().decode())
                for values in data['dxsEntries']:
                    kostal_key = str(list(self._keytable.keys())[list(self._keytable.values()).index(values['dxsId'])])
                    value=values['value']
                    if kostal_key == "operation_status":
                        self.logger.debug("operation_status" + str(value))
                        if str(value) == "0":
                            value = "off"
                        elif str(value) == "2":
                            value = "startup"
                        elif str(value) == "3":
                            value = "feed in (mpp)"
                        elif str(value) == "6":
                            value = "dc voltage low"
                        else:
                            value = "unknown"
                    if kostal_key == "yield_day_kwh":
                            value = value / 1000
                    if kostal_key in self._items:
                        self._items[kostal_key](value)
                        self.logger.debug("items[" + str(kostal_key) +"] = " +str(value))
        except Exception as e:
            self.logger.error(
                'could not retrieve data from {0}: {1}'.format(self.ip, e))
            return

    def _refresh(self):
        start = time.time()
        # run the working methods
        self.datastructure()
        cycletime = time.time() - start
        self.logger.debug("cycle takes {0} seconds".format(cycletime))
