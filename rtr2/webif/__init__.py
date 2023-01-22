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
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])),
                           item_count=0,
                           rtr=self.plugin._rtr)


    def get_value(self, param):
        try:
            result = param
        except:
            result = None

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
            result = {}

            for r in self.plugin._rtr:
                result[r] = {}
                rtr = self.plugin._rtr[r]
                # data for tab 1 'Raumtemperatur Regler'
                result[r]['temp_actual'] = rtr.temp_actual_item()
                result[r]['temp_set'] = rtr.temp_set_item()
                result[r]['control_output'] = rtr.control_output_item()
                result[r]['mode'] = str(rtr._mode)
                result[r]['lock_status'] = rtr.lock_status_item()
                result[r]['setting_temp_comfort'] = rtr.setting_temp_comfort_item()
                result[r]['setting_temp_standby'] = rtr.setting_temp_standby_item()
                result[r]['setting_temp_night'] = rtr.setting_temp_night_item()
                result[r]['setting_temp_frost'] = rtr.setting_temp_frost_item()

                # data for tab 2 'Erweiterte Einstellungen'
                result[r]['controller_type'] = rtr.controller.controller_type
                result[r]['controller_Kp'] = rtr.controller._Kp
                result[r]['controller_Ki'] = rtr.controller._Ki
                if rtr.controller.controller_type == 'PID':
                    result[r]['controller_Kd'] = self.get_value(rtr.controller._Kd)
                else:
                    result[r]['controller_Kd'] = '-'
                result[r]['valve_protect'] = rtr.valve_protect

                result[r]['setting_standby_reduction'] = rtr.setting_standby_reduction_item()
                result[r]['setting_night_reduction'] = rtr.setting_night_reduction_item()
                result[r]['setting_fixed_reduction'] = rtr.setting_fixed_reduction_item()
                result[r]['setting_min_output'] = rtr.setting_min_output_item()
                result[r]['setting_max_output'] = rtr.setting_max_output_item()

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

