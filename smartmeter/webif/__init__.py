#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2024-     Michael Wenzel               wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This file implements the web interface for the Sample plugin.
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
import pprint

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

        :return: contents of the template after being rendered
        """
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           item_count=len(self.plugin.get_item_list()),
                        )

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """

        # if dataSets are used, define them here
        if dataSet == 'overview':
            try:
                data = json.dumps(self.plugin.obis_results)
                return data
            except Exception as e:
                self.logger.error(f"get_data_html overview exception: {e}")

        elif dataSet == 'devices_info':
            data = {'items': {}}

            # add item data
            for item in self.plugin.get_item_list():
                item_dict = {'typ': item.property.type,
                    		 'obis_code': self.plugin.get_iattr_value(item.conf, 'obis_code', ''),
                             'obis_index': self.plugin.get_iattr_value(item.conf, 'obis_index', '0'),
                             'obis_property': self.plugin.get_iattr_value(item.conf, 'obis_property', 'value'),
                             'obis_vtype': self.plugin.get_iattr_value(item.conf, 'obis_vtype', '-'),
                             'value': item.property.value,
                             'last_update': item.property.last_update.strftime('%d.%m.%Y %H:%M:%S'),
                             'last_change': item.property.last_change.strftime('%d.%m.%Y %H:%M:%S'),
                             }

                data['items'][item.property.path] = item_dict

            # add obis result
            data['obis_results'] = self.plugin.obis_results

            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error(f"get_data_html devices_info exception: {e}")

        if dataSet is None:
            return

    @cherrypy.expose
    def submit(self, cmd=None):

        self.logger.debug(f"submit:  {cmd=}")
        result = None

        if cmd == "detect":
            result = {'discovery_successful': self.plugin.discover(), 'protocol': self.plugin.protocol}

        elif cmd == 'query':
            result = self.plugin.query(assign_values=False)

        elif cmd == 'create_items':
            result = self.plugin.create_items()

        if result is not None:
            # JSON zurücksenden
            cherrypy.response.headers['Content-Type'] = 'application/json'
            self.logger.debug(f"Result for web interface: {result}")
            return json.dumps(result).encode('utf-8')

