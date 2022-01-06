#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Marc René Frieß                   rene.friess@gmail.com
#  The Plugin uses parts of the source code of the garminconnect pypi
#  package, without directly using the package. Thanks therefore go to
#  Ron Klinkien, the developer!
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
#
#########################################################################

import logging
import json
import re
from garminconnect import (
    Garmin,
    GarminConnectConnectionError,
    GarminConnectTooManyRequestsError,
    GarminConnectAuthenticationError,
)
from enum import Enum, auto
from lib.model.smartplugin import *

class GarminConnect(SmartPlugin):
    """
    Retrieves Garmin Connect Stats and Heart Rates.
    """
    PLUGIN_VERSION = "1.2.0"

    def __init__(self, sh, *args, **kwargs):
        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()

        self._shtime = Shtime.get_instance()
        self._username = self.get_parameter_value("email")
        self._password = self.get_parameter_value("password")
        self._is_cn = self.get_parameter_value("is_cn")
        self._api = None


        self.init_webinterface()

    def run(self):
        self.alive = True


    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False

    def parse_item(self, item):
        pass

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        pass

    def login(self):
        try:
            self._api = Garmin(self._username, self._password, is_cn=self._is_cn)
            self._api.login()
            self.logger.info(self._api.get_full_name())
            self.logger.info(self._api.get_unit_system())
        except (
                GarminConnectConnectionError,
                GarminConnectAuthenticationError,
                GarminConnectTooManyRequestsError,
        ) as err:
            self._api = Garmin(self._username, self._password, is_cn=self._is_cn)
            self._api.login()
            self.logger.error("Error occurred during Garmin Connect communication: %s", err)

    def get_stats(self, date_str=None):
        date = self._get_date(date_str)
        self.login()
        stats = self._api.get_stats(date.strftime('%Y-%m-%d'))
        return stats

    def get_heart_rates(self, date_str=None):
        date = self._get_date(date_str)
        self.login()
        heart_rates = self._api.get_heart_rates(date.strftime('%Y-%m-%d'))
        return heart_rates

    def _get_date(self, date_str):
        if date_str is not None:
            date = self._shtime.datetime_transform(date_str)
        else:
            date = self._shtime.now()
        return date

    def init_webinterface(self):
        """
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
            '/': {
                'tools.staticdir.root': webif_dir,
            },
            '/static': {
                'tools.staticdir.on': True,
                'tools.staticdir.dir': 'static'
            }
        }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
import json
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
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None, day=None, month=None, year=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, plugin_info=self.plugin.get_info(), tabcount=3, now=self.plugin.shtime.now(),
                           day=day, month=month, year=year, p=self.plugin)
