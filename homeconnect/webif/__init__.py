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

from datetime import datetime
import time
import os
import cherrypy

from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import csv
from jinja2 import Environment, FileSystemLoader


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
    def index(self, reload=None, state=None, code=None, grant_type=None, error_description=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after being rendered
        """
        token = self.plugin.get_hc().token_load()

        if grant_type == "authorization_code" and code is not None and state is not None:
            os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'
            self.logger.error("Token expired, refreshing!")
            self.plugin.get_hc().get_token(
                cherrypy.url() + "?code=" + code + "&state=" + state + "&grant_type=" + grant_type)
            token = self.plugin.get_hc().token_load()

        token_expiry_date = None
        if token is not None:
            token_expiry_date = datetime.fromtimestamp(token['expires_at'])

        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, item_count=len(self.plugin.get_items()),
                           plugin_info=self.plugin.get_info(), tabcount=3,
                           tab1title="HomeConnect Items (%s)" % len(self.plugin.get_items()), token=token,
                           token_expiry_date=token_expiry_date,
                           p=self.plugin)
