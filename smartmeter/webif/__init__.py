#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2024-     Michael Wenzel               wenzel_michael@web.de
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

import json
import cherrypy

from lib.model.smartplugin import SmartPluginWebIf


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------


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

        self.tplenv = self.init_template_environment()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after being rendered
        """
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           items=self.plugin.get_item_list(),
                           item_count=len(self.plugin.get_item_list()))

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        # if dataSets are used, define them here
        if dataSet == 'overview':
            # get the new data from the plugin variable called _webdata

            data = {}
            for obis, value in self.plugin.obis_results.items():
                if isinstance(value, list):
                    value = value[0]
                data[obis] = value

            try:
                data = json.dumps(data)
                return data
            except Exception as e:
                self.logger.error(f"get_data_html overview exception: {e}")

        elif dataSet == 'devices_info':
            data = {'items': {}}

            # add item data
            for item in self.plugin.get_item_list():
                item_dict = {'value': item.property.value,
                             'last_update': item.property.last_update.strftime('%d.%m.%Y %H:%M:%S'),
                             'last_change': item.property.last_change.strftime('%d.%m.%Y %H:%M:%S')}

                data['items'][item.property.path] = item_dict

            # add obis result
            data['obis_results'] = self.plugin.obis_results

            try:
                return json.dumps(data, default=str)
            except Exception as e:
                self.logger.error(f"get_data_html devices_info exception: {e}")

        if dataSet is None:
            return

    @cherrypy.expose
    def read_data(self):
        self.plugin.query(assign_values=False)
