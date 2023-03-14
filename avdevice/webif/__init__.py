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
    def index(self, action=None, item_id=None, item_path=None, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        config_reloaded = False
        keep_cleared = False
        command_cleared = False
        query_cleared = False
        send_cleared = False
        if action is not None:
            if action == "reload":
                self.plugin._initialize()
                config_reloaded = True
            if action == "connect":
                self.plugin.connect('webif')
            if action == "clear_query_history":
                self.plugin._clear_history('query')
                query_cleared = True
            if action == "clear_send":
                self.plugin._clear_history('send')
                send_cleared = True
            if action == "clear_command_history":
                self.plugin._clear_history('command')
                command_cleared = True
            if action == "clear_keep_commands":
                self.plugin._clear_history('keep')
                keep_cleared = True

        tmpl = self.tplenv.get_template('index.html')
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           config_reloaded=config_reloaded, query_cleared=query_cleared,
                           command_cleared=command_cleared, keep_cleared=keep_cleared, send_cleared=send_cleared,
                           language=self.plugin._sh.get_defaultlanguage(),
                           webif_pagelength=pagelength,
                           now=self.plugin.shtime.now())

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
            data = {'sendcommands': '', 'sendingcommand': '', 'item_values': {}, 'query': {}, 'command': {}}

            data['sendcommands'] = self.plugin._send_commands
            data['sendingcommand'] = self.plugin._sendingcommand
            data['item_values'] = self.plugin._item_values
            data['query'] = self.plugin._send_history['query']
            data['command'] = self.plugin._send_history['command']

            try:
                return json.dumps(data)
            except Exception as e:
                self.logger.error("get_data_html exception: {}".format(e))
        return {}
