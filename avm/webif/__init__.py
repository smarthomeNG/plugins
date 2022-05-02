#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2021-      Michael Wenzel              wenzel_michael@web.de
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

import json
from lib.item import Items
from lib.model.smartplugin import SmartPluginWebIf


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
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

        self.call_monitor_items = []
        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None, action=None):
        """
        Build index.html for cherrypy
        Render the template and return the html file to be delivered to the browser
        :return: contents of the template after beeing rendered
        """

        if self.plugin._call_monitor:
            self.call_monitor_items = []
            self.call_monitor_items.extend(self.plugin._monitoring_service.get_items())
            self.call_monitor_items.extend(self.plugin._monitoring_service.get_trigger_items())
            self.call_monitor_items.extend(self.plugin._monitoring_service.get_items_incoming())
            self.call_monitor_items.extend(self.plugin._monitoring_service.get_items_outgoing())

        try:
            pagelength = self.plugin.webif_pagelength
        except Exception:
            pagelength = 100

        tmpl = self.tplenv.get_template('index.html')

        return tmpl.render(plugin_shortname=self.plugin.get_shortname(),
                           plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(),
                           avm_items=sorted(self.plugin.get_fritz_device().get_items(), key=lambda k: str.lower(k['_path'])),
                           avm_item_count=len(self.plugin.get_fritz_device().get_items()),
                           call_monitor_items=sorted(self.call_monitor_items, key=lambda k: str.lower(k['_path'])),
                           call_monitor_item_count=len(self.call_monitor_items),
                           smarthome_items=sorted(self.plugin.get_fritz_device().get_smarthome_items(), key=lambda k: str.lower(k['_path'])),
                           smarthome_item_count=len(self.plugin.get_fritz_device().get_smarthome_items()),
                           p=self.plugin,
                           webif_pagelength=pagelength,
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
            if self.plugin._call_monitor:
                if self.call_monitor_items:
                    data['call_monitor'] = {}
                    for item in self.call_monitor_items:
                        data['call_monitor'][item.id()] = {}
                        data['call_monitor'][item.id()]['value'] = item()
                        data['call_monitor'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                        data['call_monitor'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            if self.plugin.get_fritz_device().get_items():
                data['avm_items'] = {}
                for item in self.plugin.get_fritz_device().get_items():
                    data['avm_items'][item.id()] = {}
                    data['avm_items'][item.id()]['value'] = item()
                    data['avm_items'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                    data['avm_items'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            if self.plugin.get_fritz_device().get_smarthome_items():
                data['avm_smarthome_items'] = {}
                for item in self.plugin.get_fritz_device().get_smarthome_items():
                    data['avm_smarthome_items'][item.id()] = {}
                    data['avm_smarthome_items'][item.id()]['value'] = item()
                    data['avm_smarthome_items'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                    data['avm_smarthome_items'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")
        return {}

    @cherrypy.expose
    def reboot(self):
        self.plugin.reboot()

    @cherrypy.expose
    def reconnect(self):
        self.plugin.reconnect()
