#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2013 Marcus Popp                         marcus@popp.mx
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
#########################################################################

import logging
import urllib.parse
import http.client
from lib.model.smartplugin import SmartPlugin


class Prowl(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.3.0"

    _host = 'api.prowlapp.com'
    _api = '/publicapi/add'

    def __init__(self, smarthome, apikey=None):
        self.logger = logging.getLogger(__name__)
        self._apikey = apikey
        self._sh = smarthome

    def run(self):
        pass

    def stop(self):
        pass

    def notify(self, event='', description='', priority=None, url=None, apikey=None, application='SmartHomeNG'):
        self.__call__(self, event, description, priority, url, apikey, application)

    def __call__(self, event='', description='', priority=None, url=None, apikey=None, application='SmartHomeNG'):
        data = {}
        origin = application
        if self.get_instance_name() != '':
        	origin += ' (' + self.get_instance_name() + ')'
        headers = {'User-Agent': application, 'Content-Type': "application/x-www-form-urlencoded"}
        data['event'] = event[:1024].encode()
        data['description'] = description[:10000].encode()
        data['application'] = origin[:256].encode()
        if apikey:
            data['apikey'] = apikey
        else:
            data['apikey'] = self._apikey.encode()
        if priority:
            data['priority'] = priority
        if url:
            data['url'] = url[:512]
        try:
            conn = http.client.HTTPSConnection(self._host, timeout=4)
            conn.request("POST", self._api, urllib.parse.urlencode(data), headers)
            resp = conn.getresponse()
            conn.close()
            if resp.status != 200:
                raise Exception("{} {}".format(resp.status, resp.reason))
        except Exception as e:
            self.logger.warning("Could not send prowl notification: {0}. Error: {1}".format(event, e))
