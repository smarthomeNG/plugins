#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
#  Copyright 2021-      Michael Wenzel              wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after being rendered
        """
        self.plugin.get_broker_info()

        tmpl = self.tplenv.get_template('index.html')

        return tmpl.render(p=self.plugin,
                           webif_pagelength=self.plugin.get_parameter_value('webif_pagelength'),
                           item_count=len(self.plugin.get_item_list()),
                           zigbee = True if self.plugin.tasmota_zigbee_devices else False,
                           broker_config = self.plugin.broker_config,
                           full_topic = self.plugin.full_topic,
                           maintenance=True if self.plugin.log_level == 10 else False,
                           )

    @cherrypy.expose
    def get_data_html(self, dataSet=None, params=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        
        self.logger.debug(f"get_data_html: {dataSet=}, {params=}")
        
        data = dict()
        
        if dataSet == "items_info":
            data[dataSet] = {}
            for item in self.plugin.get_item_list():
                item_data = {
                    'value': item.property.value,
                    'type': item.property.type,
                    'topic': self.plugin.get_iattr_value(item.conf, 'tasmota_topic'),
                    'relais': self._get_relay_value(item),
                    'last_update': item.property.last_update.strftime('%d.%m.%Y %H:%M:%S'),
                    'last_change': item.property.last_change.strftime('%d.%m.%Y %H:%M:%S'),
                }
                data['items_info'][item.property.path] = item_data
         
        elif dataSet == "devices_info":
            data[dataSet] = {}
            for device_name, device_data in self.plugin.tasmota_devices.items():
                device_data = device_data.copy()
                device_data.pop('discovery_config', None)
                data[dataSet][device_name] = device_data
                
        elif dataSet == "zigbee_info":
            data[dataSet] = self.plugin.tasmota_zigbee_devices.copy()

        elif dataSet == "broker_info":
            self.plugin.get_broker_info()
            data[dataSet] = self.plugin._broker.copy()
            data[dataSet]['broker_uptime'] = self.plugin.broker_uptime()
            
        elif dataSet == "details_info":
            data['devices_info'] = {}
            for device_name, device_data in self.plugin.tasmota_devices.items():
                device_data = device_data.copy()
                device_data.pop('discovery_config', None)
                data['devices_info'][device_name] = device_data
            data['zigbee_info'] = self.plugin.tasmota_zigbee_devices.copy()

         # return it as json the web page
        try:
            return json.dumps(data, default=str)
        except Exception as e:
            self.logger.error("get_data_html exception: {}".format(e))
            return {}


    @cherrypy.expose
    def submit(self, cmd=None, params=None):

        self.logger.debug(f"submit:  {cmd=}, {params=}")
        result = None

        if cmd == "zbstatus":
            result = self.plugin._poll_zigbee_devices()
            
        elif cmd == "tasmota_status":
            result = self.plugin._interview_device(params)
            
        elif cmd == "zb_ping":
            result = self.plugin._poll_zigbee_device(params)
 
        self.logger.debug(f"submit:  {cmd=}, {params=} --> {result=}")

        if result is not None:
            # JSON zurücksenden
            cherrypy.response.headers['Content-Type'] = 'application/json'
            self.logger.debug(f"Result for web interface: {result}")
            return json.dumps(result).encode('utf-8')
        
    def _get_relay_value(self, item):
        """
        Determines the relay value based on item configuration.

        Args:
            item: The item object containing configuration data.
        Returns:
            The relay value as a string.
        """

        relay = self.plugin.get_iattr_value(item.conf, 'tasmota_relay') 
        if relay in ['1', '2', '3', '4', '5', '6', '7', '8']:
            return relay

        if self.plugin.get_iattr_value(item.conf, 'tasmota_attr') == 'relay':
            return "1"

        return "-"
        