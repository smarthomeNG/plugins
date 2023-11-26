#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2023       Matthias Manhart             smarthome@beathis.ch
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  This file implements the web interface for the byd_bat plugin.
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
        pagelength = self.plugin.get_parameter_value('webif_pagelength')
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           webif_pagelength=pagelength,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])),
                           item_count=0)

    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        # get the new data
        data = {}
        data['bydip'] = self.plugin.ip
        data['imppath'] = self.plugin.bpath
        data['last_homedata'] = self.plugin.last_homedata
        data['last_diagdata'] = self.plugin.last_diagdata

        data['current'] = f'{self.plugin.byd_current:.1f}' + " A"
        data['power'] = f'{self.plugin.byd_power:.1f}' + " W"
        data['power_charge'] = f'{self.plugin.byd_power_charge:.1f}' + " W"
        data['power_discharge'] = f'{self.plugin.byd_power_discharge:.1f}' + " W"
        data['soc'] = f'{self.plugin.byd_soc:.1f}' + " %"
        data['soh'] = f'{self.plugin.byd_soh:.1f}' + " %"
        data['tempbatt'] = f'{self.plugin.byd_temp_bat:.1f}' + " °C"
        data['tempmax'] = f'{self.plugin.byd_temp_max:.1f}' + " °C"
        data['tempmin'] = f'{self.plugin.byd_temp_min:.1f}' + " °C"
        data['voltbatt'] = f'{self.plugin.byd_volt_bat:.1f}' + " V"
        data['voltdiff'] = f'{self.plugin.byd_volt_diff:.3f}' + " V"
        data['voltmax'] = f'{self.plugin.byd_volt_max:.3f}' + " V"
        data['voltmin'] = f'{self.plugin.byd_volt_min:.3f}' + " V"
        data['voltout'] = f'{self.plugin.byd_volt_out:.1f}' + " V"
        
        data['bms'] = self.plugin.byd_bms
        data['bmu'] = self.plugin.byd_bmu
        data['bmubanka'] = self.plugin.byd_bmu_a
        data['bmubankb'] = self.plugin.byd_bmu_b
        data['batttype'] = self.plugin.byd_batt_str
        data['errorstr'] = self.plugin.byd_error_str + " (" + str(self.plugin.byd_error_nr) + ")"
        data['grid'] = self.plugin.byd_application
        data['invtype'] = self.plugin.byd_inv_str
        data['modules'] = str(self.plugin.byd_modules)
        data['bmsqty'] = str(self.plugin.byd_bms_qty)
        data['capacity_total'] = f'{self.plugin.byd_capacity_total:.2f}' + " kWh"
        data['paramt'] = self.plugin.byd_param_t
        data['serial'] = self.plugin.byd_serial
        
        data['t1_soc'] = f'{self.plugin.byd_diag_soc[1]:.1f}' + " %"
        data['t1_bat_voltag'] = f'{self.plugin.byd_diag_bat_voltag[1]:.1f}' + " V"
        data['t1_v_out'] = f'{self.plugin.byd_diag_v_out[1]:.1f}' + " V"
        data['t1_current'] = f'{self.plugin.byd_diag_current[1]:.1f}' + " A"
        data['t1_volt_max'] = f'{self.plugin.byd_diag_volt_max[1]:.3f}' + " V (" + str(self.plugin.byd_diag_volt_max_c[1]) + ")"
        data['t1_volt_min'] = f'{self.plugin.byd_diag_volt_min[1]:.3f}' + " V (" + str(self.plugin.byd_diag_volt_min_c[1]) + ")"
        data['t1_temp_max_cell'] = str(self.plugin.byd_diag_temp_max_c[1])
        data['t1_temp_min_cell'] = str(self.plugin.byd_diag_temp_min_c[1])
        if self.plugin.byd_bms_qty > 1:
          data['t2_soc'] = f'{self.plugin.byd_diag_soc[2]:.1f}' + " %"
          data['t2_bat_voltag'] = f'{self.plugin.byd_diag_bat_voltag[2]:.1f}' + " V"
          data['t2_v_out'] = f'{self.plugin.byd_diag_v_out[2]:.1f}' + " V"
          data['t2_current'] = f'{self.plugin.byd_diag_current[2]:.1f}' + " A"
          data['t2_volt_max'] = f'{self.plugin.byd_diag_volt_max[2]:.3f}' + " V (" + str(self.plugin.byd_diag_volt_max_c[2]) + ")"
          data['t2_volt_min'] = f'{self.plugin.byd_diag_volt_min[2]:.3f}' + " V (" + str(self.plugin.byd_diag_volt_min_c[2]) + ")"
          data['t2_temp_max_cell'] = str(self.plugin.byd_diag_temp_max_c[2])
          data['t2_temp_min_cell'] = str(self.plugin.byd_diag_temp_min_c[2])
        else:
          data['t2_soc'] = "-"
          data['t2_bat_voltag'] = "-"
          data['t2_v_out'] = "-"
          data['t2_current'] = "-"
          data['t2_volt_max'] = "-"
          data['t2_volt_min'] = "-"
          data['t2_temp_max_cell'] = "-"
          data['t2_temp_min_cell'] = "-"
        if self.plugin.byd_bms_qty > 2:
          data['t3_soc'] = f'{self.plugin.byd_diag_soc[3]:.1f}' + " %"
          data['t3_bat_voltag'] = f'{self.plugin.byd_diag_bat_voltag[3]:.1f}' + " V"
          data['t3_v_out'] = f'{self.plugin.byd_diag_v_out[3]:.1f}' + " V"
          data['t3_current'] = f'{self.plugin.byd_diag_current[3]:.1f}' + " A"
          data['t3_volt_max'] = f'{self.plugin.byd_diag_volt_max[3]:.3f}' + " V (" + str(self.plugin.byd_diag_volt_max_c[3]) + ")"
          data['t3_volt_min'] = f'{self.plugin.byd_diag_volt_min[3]:.3f}' + " V (" + str(self.plugin.byd_diag_volt_min_c[3]) + ")"
          data['t3_temp_max_cell'] = str(self.plugin.byd_diag_temp_max_c[3])
          data['t3_temp_min_cell'] = str(self.plugin.byd_diag_temp_min_c[3])
        else:
          data['t3_soc'] = "-"
          data['t3_bat_voltag'] = "-"
          data['t3_v_out'] = "-"
          data['t3_current'] = "-"
          data['t3_volt_max'] = "-"
          data['t3_volt_min'] = "-"
          data['t3_temp_max_cell'] = "-"
          data['t3_temp_min_cell'] = "-"

        # return it as json the the web page
        try:
          return json.dumps(data)
        except Exception as e:
          self.logger.error("get_data_html exception: {}".format(e))
