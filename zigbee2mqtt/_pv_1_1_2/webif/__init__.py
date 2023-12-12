#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-           Michael Wenzel            zel_michael@web.de
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

        :return: contents of the template after beeing rendered
        """

        self.plugin.get_broker_info()

        tmpl = self.tplenv.get_template('index.html')

        try:
            pagelength = self.plugin.webif_pagelength
        except Exception:
            pagelength = 100

        return tmpl.render(plugin_shortname=self.plugin.get_shortname(),
                           plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(),
                           items=sorted(self.plugin.zigbee2mqtt_items, key=lambda k: str.lower(k['_path'])),
                           item_count=len(self.plugin.zigbee2mqtt_items),
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
            self.plugin.get_broker_info()
            data = dict()
            data['broker_info'] = self.plugin._broker
            data['broker_uptime'] = self.plugin.broker_uptime()

            data['item_values'] = {}
            for item in self.plugin.zigbee2mqtt_items:
                data['item_values'][item.id()] = {}
                data['item_values'][item.id()]['value'] = item.property.value
                data['item_values'][item.id()]['last_update'] = item.property.last_update.strftime('%d.%m.%Y %H:%M:%S')
                data['item_values'][item.id()]['last_change'] = item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')

            data['device_values'] = {}
            for device in self.plugin.zigbee2mqtt_devices:
                data['device_values'][device] = {}
                if 'data' in self.plugin.zigbee2mqtt_devices[device]:
                    data['device_values'][device]['lqi'] = str(self.plugin.zigbee2mqtt_devices[device]['data'].get('linkquality', '-'))
                    data['device_values'][device]['data'] = ", ".join(list(self.plugin.zigbee2mqtt_devices[device]['data'].keys()))
                else:
                    data['device_values'][device]['lqi'] = '-'
                    data['device_values'][device]['data'] = '-'
                if 'meta' in self.plugin.zigbee2mqtt_devices[device]:
                    last_seen = self.plugin.zigbee2mqtt_devices[device]['meta'].get('lastSeen', None)
                    if last_seen:
                        data['device_values'][device]['last_seen'] = last_seen.strftime('%d.%m.%Y %H:%M:%S')
                    else:
                        data['device_values'][device]['last_seen'] = '-'
                else:
                    data['device_values'][device]['last_seen'] = '-'

            # return it as json the web page
            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error("get_data_html exception: {}".format(e))
                return {}
