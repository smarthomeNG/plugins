#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017-2021 Marc René Frieß            rene.friess(a)gmail.com
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.5 and
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

import datetime
import time
import os

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
from jinja2 import Environment, FileSystemLoader
from withings_api import AuthScope, WithingsApi, WithingsAuth
from withings_api.common import Credentials, CredentialsType, get_measure_value, MeasureType

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin):
        """
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        """
        self.logger = plugin.logger
        self.webif_dir = webif_dir
        self.plugin = plugin
        self._creds = None
        self._auth = None

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None, state=None, code=None, error=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        if self._auth is None:
            self._auth = WithingsAuth(
                client_id=self.plugin.get_client_id(),
                consumer_secret=self.plugin.get_consumer_secret(),
                callback_uri=self.plugin.get_callback_url(),
                scope=(AuthScope.USER_ACTIVITY,
                       AuthScope.USER_METRICS,
                       AuthScope.USER_INFO,
                       AuthScope.USER_SLEEP_EVENTS,)
            )

        if not reload and code:
            self.logger.debug("Got code as callback: {}".format(self.plugin.get_fullname(), code))
            credentials = None
            try:
                credentials = self._auth.get_credentials(code)
            except Exception as e:
                self.logger.error(
                    "An error occurred, perhaps code parameter is invalid or too old? Message: {}".format(
                        str(e)))
            if credentials is not None:
                self._creds = credentials
                self.logger.debug(
                    "New credentials are: access_token {}, token_expiry {}, token_type {}, refresh_token {}".
                        format(self.plugin.get_fullname(), self._creds.access_token, self._creds.token_expiry,
                               self._creds.token_type, self._creds.refresh_token))
                self.plugin.get_item('access_token')(self._creds.access_token)
                self.plugin.get_item('token_expiry')(self._creds.token_expiry)
                self.plugin.get_item('token_type')(self._creds.token_type)
                self.plugin.get_item('refresh_token')(self._creds.refresh_token)

                self.plugin._client = None

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, item_count=len(self.plugin.get_items()),
                           plugin_info=self.plugin.get_info(), tabcount=2, callback_url=self.plugin.get_callback_url(),
                           tab1title="Withings Health Items (%s)" % len(self.plugin.get_items()),
                           tab2title="OAuth2 Data", authorize_url=self._auth.get_authorize_url(),
                           p=self.plugin, token_expiry=datetime.datetime.fromtimestamp(self.plugin.get_item(
                'token_expiry')(), tz=self.plugin.shtime.tzinfo()), now=self.plugin.shtime.now(), code=code,
                           state=state, reload=reload, language=self.plugin.get_sh().get_defaultlanguage())
