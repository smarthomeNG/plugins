#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2024       Matthias Manhart             smarthome@beathis.ch
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
                           item_count=len(self.plugin.items))

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
        data['model_desc'] = self.plugin._model_desc
        data['uuid'] = self.plugin._uuid
        data['device_type'] = self.plugin._device_type
        data['connectiontype'] = self.plugin._connectiontype
        data['serial'] = self.plugin._serial
        data['host'] = self.plugin._host
        data['softwareversion'] = self.plugin._softwareversion
        data['hardwareversion'] = self.plugin._hardwareversion
        if self.plugin.connection == True:
          s_conn = self.translate("ein")
        else:
          s_conn = self.translate("aus")
        data['connection'] = s_conn
        data['last_connection'] = self.plugin.last_connection
        data['msg_table'] = self.plugin._html
        
        if self.plugin._firmwareavailable == True:
          s_fup = self.translate("verfügbar")
        else:
          s_fup = self.translate("nein")
        if self.plugin._active == True:
          s_active = self.translate("ein")
        else:
          s_active = self.translate("Standby")

        # Informationen
        t = '<table id="vzug_reg_1" border="1"><tbody>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Gerät") + ':</strong></td>' + '<td class="py-1">' + self.plugin._model_desc + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Typ") + ':</strong></td>' + '<td class="py-1">' + self.plugin._device_type + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Serienummer") + ':</strong></td>' + '<td class="py-1">' + self.plugin._serial + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Verbindung") + ':</strong></td>' + '<td class="py-1">' + self.plugin._connectiontype + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + "IP" + ':</strong></td>' + '<td class="py-1">' + self.plugin._host + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Software") + ':</strong></td>' + '<td class="py-1">' + self.plugin._softwareversion + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Hardware") + ':</strong></td>' + '<td class="py-1">' + self.plugin._hardwareversion + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Firmware Update") + ':</strong></td>' + '<td class="py-1">' + s_fup + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("API Version") + ':</strong></td>' + '<td class="py-1">' + self.plugin._apiver + '</td>' + '</tr>'
        t = t + '</tbody></table>'
        data['r1_table'] = t
            
        # Programm
        t = '<table id="vzug_reg_2" border="1"><tbody>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Eingeschaltet") + ':</strong></td>' + '<td class="py-1">' + s_conn + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Letztes Update") + ':</strong></td>' + '<td class="py-1">' + self.plugin.last_connection + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Aktiv") + ':</strong></td>' + '<td class="py-1">' + s_active + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Information") + ':</strong></td>' + '<td class="py-1">' + self.plugin._info + '</td>' + '</tr>'
        if self.plugin._active == True:
          t = t + '<tr><td class="py-1"><strong>' + self.translate("Programm") + ':</strong></td>' + '<td class="py-1">' + self.plugin._program_name + '</td>' + '</tr>'
          t = t + '<tr><td class="py-1"><strong>' + self.translate("Phase") + ':</strong></td>' + '<td class="py-1">' + self.plugin._status + '</td>' + '</tr>'
          t = t + '<tr><td class="py-1"><strong>' + self.translate("Dauer") + ':</strong></td>' + '<td class="py-1">' + f'{self.plugin._program_duration:.0f}' + " Min" + '</td>' + '</tr>'
          t = t + '<tr><td class="py-1"><strong>' + self.translate("Start") + ':</strong></td>' + '<td class="py-1">' + self.plugin._date_time_start + '</td>' + '</tr>'
          t = t + '<tr><td class="py-1"><strong>' + self.translate("Ende") + ':</strong></td>' + '<td class="py-1">' + self.plugin._date_time_end + '</td>' + '</tr>'
          if self.plugin._f_show_consumption_prog == True:
            t = t + '<tr><td class="py-1"><strong>' + self.translate("Energie") + ':</strong></td>' + '<td class="py-1">' + f'{self.plugin._power_consumption_kwh_last:.1f}' + " kWh" + '</td>' + '</tr>'
            t = t + '<tr><td class="py-1"><strong>' + self.translate("Wasser") + ':</strong></td>' + '<td class="py-1">' + f'{self.plugin._water_consumption_l_last:.1f}' + " l" + '</td>' + '</tr>'
        t = t + '</tbody></table>'
        data['r2_table'] = t
            
        # Verbrauch
        t = '<table id="vzug_reg_3" border="1"><tbody>'
        t = t + '<tr><td class="py-1"></td>' + '<td class="py-1" align=right>' + '<strong>' + self.translate("Energie") + '</strong>' + '</td>' + '<td class="py-1" align=right>' + '<strong>' + self.translate("Wasser") + '</strong>' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Total") + ':</strong></td>' + '<td class="py-1" align=right>' + f'{self.plugin._power_consumption_kwh_total:.1f}' + ' kWh</td>' + '<td class="py-1" align=right>' + f'{self.plugin._water_consumption_l_total:.1f}' + ' l</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Durchschnitt") + ':</strong></td>' + '<td class="py-1" align=right>' + f'{self.plugin._power_consumption_kwh_avg:.1f}' + ' kWh</td>' + '<td class="py-1" align=right>' + f'{self.plugin._water_consumption_l_avg:.1f}' + ' l</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Letztes Programm") + ':</strong></td>' + '<td class="py-1" align=right>' + f'{self.plugin._power_consumption_kwh_last:.1f}' + ' kWh</td>' + '<td class="py-1" align=right>' + f'{self.plugin._water_consumption_l_last:.1f}' + ' l</td>' + '</tr>'
        t = t + '</tbody></table>'
        data['r3_table'] = t
            
        # return it as json the the web page
        try:
            return json.dumps(data)
        except Exception as e:
            self.logger.error("get_data_html exception: {}".format(e))
