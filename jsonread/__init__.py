#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2019 Torsten Dreyer torsten (at) t3r (dot) de
#  Version 1.0.0
#########################################################################
#
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
import requests
from requests_file import FileAdapter
import pyjq
from lib.model.smartplugin import SmartPlugin


class JSONREAD(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.0.0"

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        @param url: URL of the json data to fetch
        @param cycle: the polling interval in seconds
        """
        self.logger = logging.getLogger(__name__)
        self._url = self.get_parameter_value('url')
        self._cycle = self.get_parameter_value('cycle')
        self._session = requests.Session()
        self._session.mount('file://', FileAdapter())
        self._items = {}

    def run(self):
        self.alive = True
        self.scheduler_add(__name__, self.poll_device, cycle=self._cycle)

    def stop(self):
        self.scheduler_remove(__name__ )
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

        for k in self._items.keys():
            try:
                jqres = pyjq.first(self._items[k], json_obj)

            except Exception as ex:
                self.logger.error("jq filter failed: {}'".format(str(ex)))
                continue

            k(jqres)

