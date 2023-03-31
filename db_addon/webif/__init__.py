#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-         Michael Wenzel           wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This plugin provides additional functionality to mysql database
#  connected via database plugin
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

        :return: contents of the template after being rendered
        """

        tmpl = self.tplenv.get_template('index.html')

        return tmpl.render(p=self.plugin,
                           webif_pagelength=self.plugin.get_parameter_value('webif_pagelength'),
                           suspended='true' if self.plugin.suspended else 'false',
                           items=self.plugin.get_item_list('db_addon', 'function'),
                           item_count=len(self.plugin.get_item_list('db_addon', 'function')),
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

            for item in self.plugin.get_item_list('db_addon', 'function'):
                data['items'][item.id()] = {}
                data['items'][item.id()]['value'] = item.property.value
                data['items'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data['items'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            data['plugin_suspended'] = self.plugin.suspended
            data['maintenance'] = True if self.plugin.log_level == 10 else False
            data['queue_length'] = self.plugin.queue_backlog()
            data['active_queue_item'] = self.plugin.active_queue_item

            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")

    @cherrypy.expose
    def recalc_all(self):
        self.logger.debug(f"recalc_all called")
        self.plugin.execute_all_items()

    @cherrypy.expose
    def clean_cache_dicts(self):
        self.logger.debug(f"_clean_cache_dicts called")
        self.plugin._clean_cache_dicts()

    @cherrypy.expose
    def clear_queue(self):
        self.logger.debug(f"_clear_queue called")
        self.plugin._clear_queue()

    @cherrypy.expose
    def activate(self):
        self.logger.debug(f"active called")
        self.plugin.suspend(False)

    @cherrypy.expose
    def suspend(self):
        self.logger.debug(f"suspend called")
        self.plugin.suspend(True)
