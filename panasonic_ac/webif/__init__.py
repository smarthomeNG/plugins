#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2023-     <AUTHOR>                                   <EMAIL>
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


    def get_itemsdata(self):

        result = {}

        for item in self.plugin.get_item_list():
            item_config = self.plugin.get_item_config(item)
            value_dict = {}
            value_dict['path'] = item.property.path
            value_dict['type'] = item.type()
            value_dict['value'] = item()
            if value_dict['type'] == 'dict':
                value_dict['value'] = str(item())
            value_dict['index'] = item_config['index']
            value_dict['parameter'] = item_config['parameter']

            value_dict['last_update'] = item.property.last_update.strftime('%d.%m.%y %H:%M:%S')
            value_dict['last_change'] = item.property.last_change.strftime('%d.%m.%y %H:%M:%S')

            result[value_dict['path']] = value_dict
        return result


    def get_device_parameter(self, device_index, parametername, suffix=''):
        result = self.plugin._devices[device_index]['parameters'].get(parametername, '-')
        try:
            result = str(result.value) + ' (' + result.name + ')'   # get name of enum type
        except:
            pass
        if result != '-':
            result = str(result) + suffix
        return result


    def get_devicesdata(self):

        result = {}

        for device_index in self.plugin._devices:
            value_dict = {}
            value_dict['name'] = self.plugin._devices[device_index]['name']
            value_dict['group'] = self.plugin._devices[device_index]['group']
            value_dict['model'] = self.plugin._devices[device_index]['model']
            value_dict['id'] = self.plugin._devices[device_index]['id']
            #
            try:
                value_dict['parameters'] = {}
                value_dict['parameters']['temperatureInside'] = self.get_device_parameter(device_index, 'temperatureInside', '°C')
                value_dict['parameters']['temperatureOutside'] = self.get_device_parameter(device_index, 'temperatureOutside', '°C')
                if value_dict['parameters']['temperatureOutside'] == '126°C':
                    value_dict['parameters']['temperatureOutside'] = '-'
                value_dict['parameters']['temperature'] = self.get_device_parameter(device_index, 'temperature', '°C')
                value_dict['parameters']['power'] = self.get_device_parameter(device_index, 'power')
                value_dict['parameters']['mode'] = self.get_device_parameter(device_index, 'mode')
                value_dict['parameters']['fanSpeed'] = self.get_device_parameter(device_index, 'fanSpeed')
                value_dict['parameters']['airSwingHorizontal'] = self.get_device_parameter(device_index, 'airSwingHorizontal')
                value_dict['parameters']['airSwingVertical'] = self.get_device_parameter(device_index, 'airSwingVertical')
                value_dict['parameters']['eco'] = self.get_device_parameter(device_index, 'eco')
                value_dict['parameters']['nanoe'] = self.get_device_parameter(device_index, 'nanoe')
            except Exception as ex:
                self.logger.warning(f"WebIf get_devicesdata(): Exception {ex}")
                self.logger.warning(f" - Devicedata for index={device_index}: {self.plugin._devices[device_index]}")
                self.logger.warning(f" - Devices: {self.plugin._devices}")
            result[device_index] = value_dict
        return result


    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after being rendered
        """
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])),
                           item_count=0
                           )


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        #        self.plugin.logger.info(f"get_data_html: dataSet={dataSet}")
        item_list = []
        if dataSet is None :
            result_array = []

            # callect data for items
            items = self.get_itemsdata()
            for item in items:
                value_dict = {}
                for key in items[item]:
                    value_dict[key] = items[item][key]

                item_list.append(value_dict)

            # collect data for devices
            devices_data = self.get_devicesdata()

        # if dataSets are used, define them here
        if dataSet == 'overview':
            # get the new data from the plugin variable called _webdata
            data = self.plugin._webdata
            try:
                data = json.dumps(data)
                return data
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")

        result = {'items': item_list, 'devices': devices_data}

        # send result to wen interface
        try:
            data = json.dumps(result)
            if data:
                return data
            else:
                return None
        except Exception as e:
            self.logger.error(f"get_data_html exception: {e}")
            self.logger.error(f"- {result}")

        return {}

