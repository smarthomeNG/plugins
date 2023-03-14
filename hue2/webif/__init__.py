#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This file implements the web interface for the hue2 plugin.
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
    def index(self, scan=None, connect=None, disconnect=None, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """

        if scan == 'on':
            self.plugin.discovered_bridges = self.plugin.discover_bridges()

        if connect is not None:
            self.logger.info("Connect: connect={}".format(connect))
            for db in self.plugin.discovered_bridges:
                if db['serialNumber'] == connect:
                    user = self.plugin.create_new_username(db['ip'], db['port'])
                    if user != '':
                        self.plugin.bridge= db
                        self.plugin.bridge['username'] = user
                        self.plugin.bridgeinfo = self.plugin.get_bridgeinfo()
                        self.plugin.update_plugin_config()

        if disconnect is not None:
            self.logger.info("Disconnect: disconnect={}".format(disconnect))
            self.plugin.remove_username(self.plugin.bridge['ip'], self.plugin.bridge['port'], self.plugin.bridge['username'])
            self.plugin.bridge = {}
            self.plugin.bridgeinfo = {}
            self.plugin.update_plugin_config()

        try:
            tmpl = self.tplenv.get_template('index.html')
        except:
            self.logger.error("Template file 'index.html' not found")
        else:
            # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
            return tmpl.render(p=self.plugin,
                               #items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])),
                               items=self.plugin.plugin_items,
                               item_count=len(self.plugin.plugin_items),
                               bridge=self.plugin.bridge,
                               bridge_count=len(self.plugin.bridge),
                               discovered_bridges=self.plugin.discovered_bridges,
                               bridge_lights=self.plugin.bridge_lights,
                               bridge_groups=self.plugin.bridge_groups,
                               bridge_config=self.plugin.bridge_config,
                               bridge_scenes=self.plugin.bridge_scenes,
                               bridge_sensors=self.plugin.bridge_sensors,
                               br_object=self.plugin.br)


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
            data = {}

            # data['item'] = {}
            # for i in self.plugin.items:
            #     data['item'][i]['value'] = self.plugin.getitemvalue(i)
            #
            # return it as json the the web page
            # try:
            #     return json.dumps(data)
            # except Exception as e:
            #     self.logger.error("get_data_html exception: {}".format(e))
        return {}

