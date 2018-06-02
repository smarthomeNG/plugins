#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016-2018 Raoul Thill                  raoul.thill@gmail.com
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
#########################################################################

import logging
import json
import requests
from lib.model.smartplugin import SmartPlugin


class Slack(SmartPlugin):
    PLUGIN_VERSION = "1.0.0"
    ALLOW_MULTIINSTANCE = False
    SLACK_INCOMING_WEBHOOK = 'https://hooks.slack.com/services/%s'
    html_escape_table = {
        '&': "&amp;",
        '>': "&gt;",
        '<': "&lt;",
        '"': "\"",
        "'": "\'",
    }

    def __init__(self, smarthome, token):
        self.logger = logging.getLogger(__name__)
        self.logger.info("Init Slack notifications")
        self._sh = smarthome
        self.token = token

    def run(self):
        pass

    def stop(self):
        pass

    def html_escape(self, text):
        return "".join(self.html_escape_table.get(c, c) for c in text)

    def _push(self, payload):
        webhook = self.SLACK_INCOMING_WEBHOOK % self.token
        try:
            res = requests.post(webhook,
                                headers={
                                    "User-Agent": "sh.py",
                                    "Content-Type": "application/json",
                                    "Accept": "application/json"},
                                timeout=4,
                                data=payload,
                                )
            self.logger.debug(res)
            response = res.text
            del res
            self.logger.debug(response)
        except BaseException as e:
            self.logger.exception(e)

    def notify(self, channel, text, color='normal'):
        color_choices = ['normal', 'good', 'warning', 'danger']
        if color not in color_choices:
            self.logger.error("Please choose a valid color from {}".format(','.join(color_choices)))
            color = "normal"
        payload = {}
        if color == "normal" and text is not None:
            payload = dict(text=self.html_escape(text))
        elif text is not None:
            payload = dict(attachments=[dict(text=self.html_escape(text), color=color, mrkdwn_in=["text"])])
        if channel is not None:
            if (channel[0] == '#') or (channel[0] == '@'):
                payload['channel'] = channel
            else:
                payload['channel'] = '#' + channel

        payload = json.dumps(payload)
        self.logger.debug("Slack sending notification {}".format(payload))
        self._push(payload)

    def parse_item(self, item):
        pass
