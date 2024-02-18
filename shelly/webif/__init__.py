#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-     <AUTHOR>                                   <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Plugin to support Shelly devices
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
from lib.model.mqttplugin import MqttPluginWebIf
#from lib.model.mqttplugin import *

# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy


class WebInterface(MqttPluginWebIf):

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
        self.tplenv = self.init_template_environment()

        self.items = Items.get_instance()

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
                           webif_pagelength=self.plugin.get_parameter_value('webif_pagelength'),
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])) )


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            result_array = []

            # callect data for 'items' tab
            item_list = []
            for item in self.plugin.get_item_list():
                value_dict = {}
                value_dict['path'] = item.property.path
                value_dict['type'] = item.type()
                value_dict['shelly_type'] = self.plugin.get_shelly_device_from_item( item ).get('app', '')
                value_dict['shelly_id']  = self.plugin.get_iattr_value(item.conf, 'shelly_id')
                if value_dict['shelly_type'] == '':
                    value_dict['value'] = ''
                    value_dict['last_update'] = 'Kein passendes Shelly'
                    value_dict['last_change'] = 'Device gefunden'
                else:
                    value_dict['value'] = item()
                    value_dict['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                    value_dict['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')
                item_list.append(value_dict)

            # callect data for 'buses' tab
            device_list = []
            for device in self.plugin.discovered_devices():
                value_dict = {}
                value_dict['shelly_id'] = device
                value_dict['shelly_type'] = self.plugin.shelly_devices[device].get('app', '')
                value_dict['shelly_gen'] = 'Gen' + self.plugin.shelly_devices[device].get('gen', '?')
                value_dict['shelly_online'] = self.ja_nein(self.plugin.shelly_devices[device]['online'])
                value_dict['shelly_mac'] = self.plugin.shelly_devices[device]['mac']
                value_dict['shelly_ip'] = self.plugin.shelly_devices[device]['ip']
                value_dict['shelly_fw'] = self.plugin.shelly_devices[device]['fw_ver']
                value_dict['shelly_newfw'] = self.ja_nein(self.plugin.shelly_devices[device]['new_fw'])
                value_dict['shelly_rssi'] = self.plugin.shelly_devices[device].get('rssi', '')
                value_dict['list_attrs'] = self.ja_nein(self.plugin.shelly_devices[device].get('list_attrs', ''))
                value_dict['items_defined'] = self.ja_nein(self.plugin.shelly_devices[device]['connected_to_item'])
                device_list.append(value_dict)

            # get the new data about broker status
            self.plugin.get_broker_info()
            broker_data = {}
            broker_data['broker_info'] = self.plugin._broker
            broker_data['broker_uptime'] = self.plugin.broker_uptime()
            broker_data['item_values'] = self.plugin._item_values

            result = {'items': item_list, 'devices': device_list, 'broker': broker_data}

            # send result to wen interface
            try:
                data = json.dumps(result)
                if data:
                    return data
                else:
                    return None
            except Exception as e:
                self.logger.error(f"get_data_html exception: {e}")

        return {}

    # @cherrypy.expose
    # def get_data_html(self, dataSet=None):
    #     """
    #     Return data to update the webpage
    #
    #     For the standard update mechanism of the web interface, the dataSet to return the data for is None
    #
    #     :param dataSet: Dataset for which the data should be returned (standard: None)
    #     :return: dict with the data needed to update the web page.
    #     """
    #     if dataSet is None:
    #         # get the new data
    #         self.plugin.get_broker_info()
    #         data = {}
    #         data['broker_info'] = self.plugin._broker
    #         data['broker_uptime'] = self.plugin.broker_uptime()
    #         data['item_values'] = self.plugin._item_values
    #
    #         # return it as json the the web page
    #         try:
    #             return json.dumps(data)
    #         except Exception as e:
    #             self.logger.error("get_data_html exception: {}".format(e))
    #             return {}
    #
    #     return


    def ja_nein(self, value) -> str:
        """
        Bool Wert in Ja/Nein String wandeln

        :param value:
        :return:
        """
        if isinstance(value, bool):
            if value:
                return self.translate('Ja')
            return self.translate('Nein')
        return value
