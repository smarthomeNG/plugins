#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2021 Thomas Hengsberg <thomas@thomash.eu>
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
import requests

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

        if self.has_iattr(item.conf, 'bsb_lan'):
            return self.update_item

    def poll_device(self):
        for item in self._items:
            self.url = 'http://' + str(self.get_parameter_value('bsblan_ip')) + '/JQ=' + str(item.conf['bsb_lan'])
            try:
                response = urlopen(self.url)
                json_obj = json.loads(response.read().decode('utf-8'))
                if json_obj[str(item.conf['bsb_lan'])]['value'] != "---":
                    item(json_obj[str(item.conf['bsb_lan'])]['value'])
                    item.descr.property.value = (json_obj[str(item.conf['bsb_lan'])]['desc'])
            except Exception as exc:
                self.logger.error("Error getting Data from BSBLAN-Adapter: ", exc)

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        r = requests.post('http://httpbin.org/post', json={"key": "value"})

        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            # self.logger.info("Update item: {}, item has been changed outside this plugin".format(item.property.path))



            if self.has_iattr(item.conf, 'bsb_lan') and str(caller) != "Logic":
                self.logger.debug(
                    "update_item was called with item '{}' from caller '{}', source '{}' and dest '{}'".format(item,
                                                                                                               caller,
                                                                                                               source,
                                                                                                               dest))
                url = 'http://' + self.get_parameter_value('bsblan_ip') + '/JS'
                payload = {"Parameter": str(item.conf['bsb_lan']), "Value": item.property.value, "Type": "1"}
                headers = {'content-type': 'application/json'}
                r = requests.post(url, data=json.dumps(payload), headers=headers)
                response = json.loads(r.text)

                # Status 0 = Fehler, 1 = OK, 2 = Parameter read-only
                if(response["%s" % str(item.conf['bsb_lan'])]["status"] == 0):
                    self.logger.error("Cannot set parameter value "+str(item.conf['bsb_lan']))
                if(response["%s" % str(item.conf['bsb_lan'])]["status"] == 2):
                    self.logger.warning("Cannot set parameter value "+str(item.conf['bsb_lan'])+". Parameter is read only.")

            pass
