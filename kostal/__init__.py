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

from lib.model.smartplugin import SmartPlugin
import urllib.request
import json
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

    PLUGIN_VERSION = "1.3.3"

    _key2json = {
        'operation_status': 16780032,
        'dctot_w': 33556736,
        'dc1_v': 33555202,
        'dc1_a': 33555201,
        'dc1_w': 33555203,
        'dc2_v': 33555458,
        'dc2_a': 33555457,
        'dc2_w': 33555459,
        'dc3_v': 33555714,
        'dc3_a': 33555713,
        'dc3_w': 33555715,
        'actot_w': 67109120,
        'actot_Hz': 67110400,
        'actot_cos': 67110656,
        'actot_limitation': 67110144,
        'ac1_v': 67109378,
        'ac1_a': 67109377,
        'ac1_w': 67109379,
        'ac2_v': 67109634,
        'ac2_a': 67109633,
        'ac2_w': 67109635,
        'ac3_v': 67109890,
        'ac3_a': 67109889,
        'ac3_w': 67109891,
        'yield_day_kwh': 251658754,
        'yield_tot_kwh': 251658753,
        'operationtime_h': 251658496
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
    _deprecated = {
        'power_current': 'actot_w',
        'power_total': 'yield_tot_kwh',
        'power_day': 'yield_day_kwh',
        'status': 'operation_status',
        'string1_volt': 'dc1_v',
        'string2_volt': 'dc2_v',
        'string3_volt': 'dc3_v',
        'string1_ampere': 'dc1_a',
        'string2_ampere': 'dc2_a',
        'string3_ampere': 'dc3_a',
        'l1_volt': 'ac1_v',
        'l2_volt': 'ac2_v',
        'l3_volt': 'ac3_v',
        'l1_watt': 'ac1_w',
        'l2_watt': 'ac2_w',
        'l3_watt': 'ac3_w'
    }

    def __init__(self, sh, **kwargs):
        self.ip = self.get_parameter_value('ip')
        self.user = self.get_parameter_value('user')
        self.passwd = self.get_parameter_value('passwd')
        self.cycle = self.get_parameter_value('cycle')
        self.datastructure_param = self.get_parameter_value('datastructure')
        self.logger.info('Init Kostal plugin')
        self._items = {}
        if self.datastructure_param == "html":
            self._keytable = self._key2td
            self.datastructure = self._html
        else:
            self._keytable = self._key2json
            self.datastructure = self._json

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("run method Kostal called")
        self.alive = True
        self.scheduler_add('Kostal', self._refresh, cycle=self.cycle)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("stop method Kostal called")
        self.scheduler_remove('Kostal')
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        Selects each item corresponding to its attribute keywords and adds it to an internal array
        :param item: The item to process.
        """
        if self.has_iattr(item.conf, 'kostal'):
            setting = self.get_iattr_value(item.conf, 'kostal')
            if setting in self._deprecated:
                self.logger.warn('Kostal: Using deprecated setting {}, please change to {}'.format(setting, self._deprecated[setting]))
                setting = self._deprecated[setting]
            self._items[setting] = item
            return self.update_item

    def _html(self):
        # HTML-OLD-Coding
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
        # NEW-JSON-Coding
        try:
            # generate url; fetching only needed elements
            kostalurl = 'http://' + self.ip + '/api/dxs.json?sessionid=SmartHomeNG'
            for item in self._items:
                value = self._keytable[item]
                kostalurl += '&dxsEntries=' + str(value)
            with urllib.request.urlopen(kostalurl) as url:
                data = json.loads(url.read().decode())
                for values in data['dxsEntries']:
                    kostal_key = str(list(self._keytable.keys())[list(self._keytable.values()).index(values['dxsId'])])
                    value = values['value']
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
                        value = float(value) / 1000
                    if kostal_key in self._items:
                        self._items[kostal_key](value)
                        self.logger.debug("items[" + str(kostal_key) + "] = " + str(value))
        except Exception as e:
            self.logger.error(
                'could not retrieve data from {0}: {1}'.format(self.ip, e))
            return

    def _refresh(self):
        if not self.alive:
            return
        start = time.time()
        # run the working methods
        self.datastructure()
        cycletime = time.time() - start
        self.logger.debug("cycle takes {0} seconds".format(cycletime))
