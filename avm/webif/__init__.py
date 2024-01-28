#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-      Michael Wenzel              wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Part of AVM Plugin
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
import cherrypy
from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf
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

        self.logger.debug(f"Init WebIF of {self.plugin.get_shortname()}")

    @cherrypy.expose
    def index(self, reload=None, action=None):
        """
        Build index.html for cherrypy
        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after being rendered
        """

        if self.plugin.fritz_device:
            tr064_items = self.plugin.get_tr064_items()
            tr064_item_count = len(tr064_items)
        else:
            tr064_items = None
            tr064_item_count = None

        if self.plugin.fritz_home:
            aha_items = self.plugin.get_aha_items()
            aha_item_count = len(aha_items)
            logentries = self.plugin.fritz_home.get_device_log_from_lua_separated()
        else:
            aha_items = None
            aha_item_count = None
            if self.plugin.fritz_device:
                logentries = self.plugin.fritz_device.get_device_log_from_tr064_separated()
            else:
                logentries = None

        if self.plugin.monitoring_service:
            call_monitor_items = self.plugin.get_monitor_items()
            call_monitor_item_count = len(call_monitor_items)
        else:
            call_monitor_items = None
            call_monitor_item_count = None

        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        tmpl = self.tplenv.get_template('index.html')

        return tmpl.render(plugin_shortname=self.plugin.get_shortname(),
                           plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(),
                           tr064_items=tr064_items,
                           tr064_item_count=tr064_item_count,
                           call_monitor_items=call_monitor_items,
                           call_monitor_item_count=call_monitor_item_count,
                           aha_items=aha_items,
                           aha_item_count=aha_item_count,
                           logentries=logentries,
                           p=self.plugin,
                           webif_pagelength=pagelength,
                           maintenance=True if self.plugin.log_level <= 20 else False,
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
            data = dict()
            if self.plugin.monitoring_service:
                data['call_monitor'] = {}
                for item in self.plugin.get_monitor_items():
                    data['call_monitor'][item.id()] = {}
                    data['call_monitor'][item.id()]['value'] = item()
                    data['call_monitor'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                    data['call_monitor'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            if self.plugin.fritz_device:
                data['tr064_items'] = {}
                for item in self.plugin.get_tr064_items():
                    data['tr064_items'][item.id()] = {}
                    data['tr064_items'][item.id()]['value'] = item()
                    data['tr064_items'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                    data['tr064_items'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
                data['tr064_items_blacklistet'] = self.plugin.get_tr064_items_blacklisted()

            if self.plugin.fritz_home:
                data['aha_items'] = {}
                for item in self.plugin.get_aha_items():
                    data['aha_items'][item.id()] = {}
                    data['aha_items'][item.id()]['value'] = item()
                    data['aha_items'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                    data['aha_items'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
                data['aha_last_request'] = self.plugin.fritz_home.last_request

            data['maintenance'] = True if self.plugin.log_level <= 20 else False

            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")

    @cherrypy.expose
    def reboot(self):
        self.plugin.reboot()

    @cherrypy.expose
    def reconnect(self):
        self.plugin.reconnect()

    @cherrypy.expose
    def reset_item_blacklist(self):
        self.plugin.reset_item_blacklist()
