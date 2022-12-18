#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
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
# import csv
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
        self.plugin.get_broker_info()

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           webif_pagelength=self.plugin.webif_pagelength,
                           items=sorted(self.plugin.tasmota_items, key=lambda k: str.lower(k['_path'])),
                           item_count=len(self.plugin.tasmota_items))

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
            self.plugin.get_broker_info()
            data = dict()
            data['broker_info'] = self.plugin._broker
            data['broker_uptime'] = self.plugin.broker_uptime()

            data['item_values'] = {}
            for item in self.plugin.tasmota_items:
                data['item_values'][item.id()] = {}
                data['item_values'][item.id()]['value'] = item.property.value
                data['item_values'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data['item_values'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            data['device_values'] = {}
            for device in self.plugin.tasmota_devices:
                data['device_values'][device] = {}
                data['device_values'][device]['online'] = self.plugin.tasmota_devices[device].get('online', None)
                data['device_values'][device]['uptime'] = self.plugin.tasmota_devices[device].get('uptime', None)
                data['device_values'][device]['fw_ver'] = self.plugin.tasmota_devices[device].get('fw_ver', None)
                data['device_values'][device]['wifi_signal'] = self.plugin.tasmota_devices[device].get('wifi_signal', None)
                data['device_values'][device]['sensors'] = self.plugin.tasmota_devices[device].get('sensors', None)
                data['device_values'][device]['lights'] = self.plugin.tasmota_devices[device].get('lights', None)
                data['device_values'][device]['rf'] = self.plugin.tasmota_devices[device].get('rf', None)

            data['tasmota_zigbee_devices'] = self.plugin.tasmota_zigbee_devices

            data['tasmota_meta'] = self.plugin.tasmota_meta

            # return it as json the the web page
            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error("get_data_html exception: {}".format(e))
                return {}
        return
