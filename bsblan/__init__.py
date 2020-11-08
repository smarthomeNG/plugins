#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020 Thomas Hengsberg <thomas@thomash.eu>
#########################################################################
#  This file is part of SmartHomeNG.   
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.7 and
#  upwards.
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
from urllib.request import urlopen
import json
from lib.model.smartplugin import *

class Bsblan(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = '1.0.0'
    url = ''
    _items = []

    def __init__(self, sh, *args, **kwargs):
        self.logger.info('INIT')
        self.SH = sh
        return

    def run(self):
        self.logger.debug("Run method called")
        self.scheduler_add('poll_device', self.poll_device, cycle=60)
        self.alive = True

    def stop(self):
        self.logger.debug("Stop method called")
        self.alive = False

    def parse_item(self, item):
        if 'bsb_lan' in item.conf:
            self._items.append(item)

    def poll_device(self):
        for item in self._items:
            self.url = 'http://'+str(self.get_parameter_value('bsblan_ip'))+'/JQ='+str(item.conf['bsb_lan'])
            try:
                response = urlopen(self.url)
                json_obj = json.loads(response.read().decode('utf-8'))
                item(json_obj[str(item.conf['bsb_lan'])]['value'])
                item.descr.property.value = (json_obj[str(item.conf['bsb_lan'])]['desc'])
            except Exception as exc:
                print("Error getting Data from BSBLAN-Adapter: ", exc)