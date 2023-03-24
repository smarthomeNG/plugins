#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2023-  Andreas Künz                    onkelandy66@gmail.com
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  lirc plugin for USB remote web interface
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
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           item_count=len(self.plugin.get_item_list('lirc', True)),
                           items=self.plugin.get_item_list('lirc', True))


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
            data = {'response': self.plugin._responseStr, 'items': {}}
            for item in self.plugin.get_item_list('lirc', True):
                data['items'].update({item.id(): {'last_update': item.property.last_update.strftime('%d.%m.%Y %H:%M:%S'), 'last_change': item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')}})
            try:
                return json.dumps(data)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")
        return {}

    @cherrypy.expose
    def submit(self, item=None):
        result = None
        if item is not None:
            item = self.plugin.items.return_item(item)
            self.logger.debug(f"Sending remote signal for {item} via web interface")
            result = self.plugin.update_item(item, caller=None, source='Web Interface', dest=None)

        if result is not None:
            # JSON zurücksenden
            cherrypy.response.headers['Content-Type'] = 'application/json'
            self.logger.debug(f"Result for web interface: {result}")
            return json.dumps(result).encode('utf-8')
