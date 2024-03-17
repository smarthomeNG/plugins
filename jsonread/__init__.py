#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Torsten Dreyer                torsten (at) t3r (dot) de
#  Copyright 2021 Bernd Meiners                     Bernd.Meiners@mail.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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
import json
import requests
from requests_file import FileAdapter
import pyjq
from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from .webif import WebInterface


class JSONREAD(SmartPlugin):
    PLUGIN_VERSION = "1.0.4"

    def __init__(self, sh):
        """
        Initializes the plugin
        @param url: URL of the json data to fetch
        @param cycle: the polling interval in seconds
        """
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self._url = self.get_parameter_value('url')
        self._cycle = self.get_parameter_value('cycle')
        self._session = requests.Session()
        self._session.mount('file://', FileAdapter())
        self._items = {}
        self._lastresult = {}
        self._lastresultstr = ""
        self._lastresultjq = ""

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        self.scheduler_add(self.get_fullname(), self.poll_device, cycle=self._cycle)

    def stop(self):
        self.logger.debug("Stop method called")
        self.scheduler_remove(self.get_fullname() )
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'jsonread_filter'):
            self._items[item] = self.get_iattr_value(item.conf, 'jsonread_filter')

    def poll_device(self):
        try:
            response = self._session.get(self._url)

        except Exception as ex:
            self.logger.error("Exception when sending GET request for {}: {}".format(self._url,str(ex)))
            return

        if response.status_code != 200:
            self.logger.error("Bad response code from GET '{}': {}".format(self._url, response.status_code))
            return

        try:
            json_obj = response.json()
        except Exception as ex:
            self.logger.error("Response from '{}' doesn't look like json '{}'".format(self._url, str(response.content)[:30]))
            return

        try:
            self._lastresult = json_obj
            self._lastresultstr = json.dumps(self._lastresult, indent=4, sort_keys=True)
            self._lastresultjq = '\n'.join(str(x) for x in pathes(self._lastresult))
        except Exception as ex:
            self.logger.error("Could not change '{}' into pretty json string'{}'".format(self._lastresult,self._lastresultstr))
            self._lastresultstr = "<empty due to failure>"

        for k in self._items.keys():
            try:
                jqres = pyjq.first(self._items[k], json_obj)

            except Exception as ex:
                self.logger.error("jq filter failed: {}'".format(str(ex)))
                continue

            k(jqres)

# just a helper function

def pathes( d, stem=""):
    #print("Stem:",stem)
    if isinstance(d, dict):
        for key, value in d.items():
            if isinstance(value, dict):
                for d in pathes(value, "{}.{}".format(stem,key)):
                    yield d
            elif isinstance(value, list) or isinstance(value, tuple):
                for v in value:
                    for d in pathes(v, "{}.{}".format(stem,key)):
                        yield d
            else:
                yield "{}.{} => {}".format(stem,key,value)
    elif isinstance(d, list) or isinstance(d, tuple):
        for value in d:
            if isinstance(value, dict):
                for d in pathes(value, "{}.{}".format(stem,key)):
                    yield d
            elif isinstance(value, list) or isinstance(value, tuple):
                for v in value:
                    for d in pathes(v, "{}.{}".format(stem,key)):
                        yield d
            else:
                yield "{}.{} => {}".format(stem,key,value)
    else:
        yield "{}.{}".format(stem,d)
