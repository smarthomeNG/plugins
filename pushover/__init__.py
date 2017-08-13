#!/usr/bin/env python
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017 Thomas Creutz                      thomas.creutz@gmx.de
#########################################################################
#  This file is part of SmartHomeNG
#  https://github.com/smarthomeNG/smarthome
#  http://knx-user-forum.de/
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
#  along with SmartHomeNG If not, see <http://www.gnu.org/licenses/>.
#########################################################################

import logging
from lib.model.smartplugin import SmartPlugin

import time
import json
import requests

class Pushover(SmartPlugin):

    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.0.0"

    _url = "https://api.pushover.net/1/messages.json"

    def __init__(self, sh, apiKey=None, userKey=None, device=None):
        self._sh = sh
        self.logger = logging.getLogger(__name__)
        self._apiKey = apiKey
        self._userKey = userKey
        self._device = device

    def run(self):
        pass

    def stop(self):
        pass

    def __call__(self, title=None, message='', priority=None, retry=None, expire=None, sound=None, url=None, url_title=None, device=None, userKey=None, apiKey=None):
        data = {}
        headers = {'User-Agent': "SmartHomeNG", 'Content-Type': "application/x-www-form-urlencoded"}

        data['timestamp'] = int(time.time())

        if title:
            data['title'] = title[:250].encode()

        data['message'] = message[:1000].encode()

        if priority:
            data['priority'] = priority
            if retry:
                data['retry'] = retry
            if expire:
                data['expire'] = expire

        if sound:
            data['sound'] = sound

        if url:
            data['url'] = url[:512]
            if url_title:
                data['url_title'] = url_title[:100]

        if userKey:
            data['user'] = userKey
        else:
            data['user'] = self._userKey

        if apiKey:
            data['token'] = apiKey
        else:
            data['token'] = self._apiKey

        if device:
            data['device'] = device
        elif self._device:
            data['device'] = self._device

        try:
            resp = requests.post(self._url, headers=headers, data=data)

            # read json response on successful status 200 
            if (resp.status_code == 200):
                json_data = resp.json()

            # process response
            if (resp.status_code == 200 and json_data['status'] == 1):
                self.logger.debug("Pushover returns: Notification successful submitted.")
            elif (resp.status_code == 429):
                self.logger.warning("Pushover returns: Message limits have been reached.")
            else:
                self.logger.warning("Pushover returns: {0} - {1}".format(resp.status_code, resp.text))

        except Exception as e:
            self.logger.warning("Could not send Pushover notification: {0}. Error: {1}".format(event, e))
