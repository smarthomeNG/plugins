#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019 Marc René Frieß                   rene.friess@gmail.com
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

import datetime
import logging
import ferien
from lib.shtime import Shtime
from lib.model.smartplugin import *


class Vacations(SmartPlugin):
    """
    Retrieves the German school vacations.
    """
    PLUGIN_VERSION = "1.0.3"
    ALLOWED_PROVINCES = ['BW', 'BY', 'BE', 'BB', 'HB', 'HH', 'HE', 'MV', 'NI', 'NW', 'RP', 'SL', 'SN', 'ST', 'SH', 'TH']

    def __init__(self, sh, *args, **kwargs):
        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()

        self._cycle = self.get_parameter_value('cycle')
        self.shtime = Shtime.get_instance()
        self._province_codes = self.ALLOWED_PROVINCES
        self._vacation_list = {}
        self._update_vacations()
        self.init_webinterface()

    def run(self):
        self.alive = True
        self.scheduler_add(__name__, self._update_vacations, prio=5, cycle=self._cycle, offset=2)

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

    def _update_vacations(self):
        new_vactions = None
        try:
            new_vacations = ferien.all_vacations()
        except Exception as e:
            self.logger.error("An exception occurred when calling \"all_vacations()\" in ferien_api library: %s" % e)
            return
        if new_vacations is not None:
            for province_code in self._province_codes:
                self._vacation_list[province_code] = []
            for v in new_vacations:
                self._vacation_list[v.state_code].append(v)
        return

    def get_vacation_list(self):
        return self._vacation_list

    def get_province_codes(self):
        return self._province_codes

    def get_vacation(self, date_str=None, province=None):
        if province is None:
            if self.shtime.config.get('location', None).get('country').lower() not in ['de', 'germany']:
                self.logger.error('The SmartHomeNG country "%s" not supported by vacations plugin' % self.shtime.config.get('location', None).get('country'))
                return
            else:
                province = self.shtime.config.get('location', None).get('province')
                if province is None:
                    self.logger.error(
                        'No province configured in etc/holidays.yaml. Please set country to DE and province value to one of '
                        'those supported by this plugin: BW, BY, BE, BB, HB, HH, HE, MV, NI, NW, RP, SL, SN, ST, SH, TH ')
                    return
                elif province not in self._province_codes:
                    self.logger.error(
                        'Province %s is not available in this plugin. Please ensure you are using one of the following provinces: '
                        'BW, BY, BE, BB, HB, HH, HE, MV, NI, NW, RP, SL, SN, ST, SH, TH. Not specifying the parameter will use '
                        'the province configuration of your SmartHomeNG instance in etc/holidays.yaml.')
                    return

        if date_str is not None:
            date = self.shtime.datetime_transform(date_str)
        else:
            date = self.shtime.now()

        vacation_list = self.get_vacation_list()
        if vacation_list is None:
            self._update_vacations()
            vacation_list = self.get_vacation_list()

        if vacation_list is not None:
            if province in vacation_list:
                for v in vacation_list[province]:
                    if v.start <= date <= v.end:
                        return v
        return None

    def is_vacation(self, date_str=None, province=None):
        v = self.get_vacation(date_str, province)
        if v is not None:
            return True
        else:
            return False

    def get_vacation_name(self, date_str=None, province=None):
        v = self.get_vacation(date_str, province)
        if v is not None:
            return v.name.capitalize()
        else:
            return ""

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
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(),
                           interface=None, plugin_info=self.plugin.get_info(), tabcount=2,
                           p=self.plugin)
