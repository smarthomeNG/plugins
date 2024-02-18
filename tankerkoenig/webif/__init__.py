#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-     <AUTHOR>                                   <EMAIL>
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
import json

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
        self.items = Items.get_instance()

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # Setting pagelength (max. number of table entries per page) for web interface
        try:
            pagelength = self.plugin.webif_pagelength
        except Exception:
            pagelength = 100
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           items=self.plugin.item_list,
                           item_count=len(self.plugin.item_list),
                           plugin_shortname=self.plugin.get_shortname(),
                           plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(),
                           maintenance=True if self.plugin.log_level == 10 else False,
                           )

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """

        if dataSet is None:
            # get the new data
            data = dict()
            data['items'] = {}

            for item in self.plugin.item_list:
                data['items'][item.property.path] = {}
                data['items'][item.property.path]['value'] = item.property.value
                data['items'][item.property.path]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data['items'][item.property.path]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            data['maintenance'] = True if self.plugin.log_level == 10 else False
            data['prices'] = self.plugin.station_prices

            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")

    @cherrypy.expose
    def submit(self, button=None, lat=None, lon=None, rad=4, clear=False):
        """
        Submit handler for Ajax
        """

        self.logger.warning(f"submit called with button={button}, lat={lat}, lon={lon}, rad={rad}")
        if button is not None:
            result = self.plugin.get_petrol_stations(lat=lat, lon=lon, rad=rad)
            self.logger.warning(f"result={result}")

        elif clear:
            for addr in self._last_read:
                self._last_read[addr]['val'] = ''
            self._last_read['last'] = {'addr': None, 'val': '', 'cmd': ''}

        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(self._last_read).encode('utf-8')

    @cherrypy.expose
    def recalc_all(self):
        self.logger.debug(f"recalc_all called")
        self.plugin.update_status_data()