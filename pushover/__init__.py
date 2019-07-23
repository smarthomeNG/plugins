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

from lib.model.smartplugin import *
from lib.network import Http

import time
import json


class Pushover(SmartPlugin):

    PLUGIN_VERSION = "1.6.1.0"

    _url = "https://api.pushover.net/1/messages.json"

    def __init__(self, sh, *args, **kwargs):
        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        self._apiKey = self.get_parameter_value('apiKey')
        self._userKey = self.get_parameter_value('userKey')
        self._device = self.get_parameter_value('device')
        self._po = Http()

    def run(self):
        pass

    def stop(self):
        pass

    def __call__(self, title=None, message='', priority=None, retry=None, expire=None, sound=None, url=None, url_title=None, device=None, userKey=None, apiKey=None, attachment=None):
        data = {}

        data['timestamp'] = int(time.time())

        if title:
            data['title'] = title[:250]

        data['message'] = message[:1000]

        if priority:
            if isinstance(priority, int) and priority >= -2 and priority <= 2:
                data['priority'] = priority

                if retry and priority == 2:
                    if isinstance(retry, int) and retry >= 30:
                        data['retry'] = retry
                    else:
                        data['retry'] = 30
                        self.logger.error("Pushover message retry need at least 30 secounds! I set it to 30!")
                elif not retry and priority == 2:
                    self.logger.error("Pushover message priority = 2 need retry to be set, degrade priority to 1!")
                    data['priority'] = 1

                if expire and priority == 2:
                    if isinstance(expire, int) and expire <= 10800:
                        data['expire'] = expire
                    else:
                        data['expire'] = 10800
                        self.logger.error("Pushover message expire need at most 10800 secounds! I set it to 10800.")
                elif not expire and priority == 2:
                    self.logger.error("Pushover message priority = 2 need expire to be set, degrade priority to 1!")
                    data['priority'] = 1

                # delete not used vars
                if data['priority'] < 2:
                    if 'expire' in data:
                        del data['expire']
                    if 'retry' in data:
                        del data['retry']

            else:
                self.logger.error("Pushover message priority need to be a number between -2 and 2!")

        if sound:
            data['sound'] = sound

        if url:
            data['url'] = url[:512]
            if url_title:
                data['url_title'] = url_title[:100]

        if userKey:
            data['user'] = userKey
        elif self._userKey:
            data['user'] = self._userKey
        else:
            self.logger.error("Pushover needs a userKey")
            return

        if apiKey:
            data['token'] = apiKey
        elif self._apiKey:
            data['token'] = self._apiKey
        else:
            self.logger.error("Pushover needs a apiKey")
            return

        if device:
            data['device'] = device
        elif self._device:
            data['device'] = self._device

        if attachment:
            files = {'attachment': open(attachment, 'rb')}
        else:
            files = {}

        try:
            json_data = self._po.post_json(self._url, json=data, files=files)
            (_status_code, _reason) = self._po.response_status()

            # process response
            if (_status_code == 200 and json_data['status'] == 1):
                self.logger.debug("Pushover returns: Notification successful submitted.")
            elif (_status_code == 429):
                self.logger.warning("Pushover returns: Message limits have been reached.")
            else:
                self.logger.warning("Pushover returns: {0} - {1}".format(_status_code, _reason))

        except Exception as e:
            self.logger.warning("Could not send Pushover notification. Error: {}".format(e))
