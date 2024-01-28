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

    def __init__(self,webif_dir,plugin):
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
    def index(self,reload=None):
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
    def get_data_html(self,dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        
        # get the new data
        data = {}
        
        data['batttype'] = self.plugin.byd_batt_str
        data['bydip'] = self.plugin.ip
        data['soc'] = f'{self.plugin.byd_soc:.1f}' + " %"
        data['capacity_total'] = f'{self.plugin.byd_capacity_total:.2f}' + " kWh"
        data['power_charge'] = f'{self.plugin.byd_power_charge:.1f}' + " W"
        data['power_discharge'] = f'{self.plugin.byd_power_discharge:.1f}' + " W"
        data['last_homedata'] = self.plugin.last_homedata
        data['last_diagdata'] = self.plugin.last_diagdata
        data['imppath'] = self.plugin.bpath
        
#        self.logger.warning("c=" + str(self.plugin.byd_root.enable_connection()))
        data['connection'] = self.plugin.byd_root.enable_connection()

        for xx in range(1,self.plugin.byd_towers_max+1):
          tx = 't' + str(xx) + '_'
          if xx <= self.plugin.byd_bms_qty:
            # Turm ist vorhanden
            data[tx + 'log_html'] = self.plugin.byd_diag_bms_log_html[xx]
          else:
            # Turm nicht vorhanden
            data[tx + 'log_html'] = ""
                  
        # 1.Register "BYD Home"
        t = '<table id="byd_diag_home1" border="1"><tbody>'
        t = t + '<tr><td class="py-1"><strong>SOC:</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_soc:.1f}' + ' %' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>SOH:</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_soh:.1f}' + ' %' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Leistung") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_power:.1f}' + ' W' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Ladeleistung") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_power_charge:.1f}' + ' W' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Entladeleistung") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_power_discharge:.1f}' + ' W' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Spannung Ausgang") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_volt_out:.1f}' + ' V' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Strom Ausgang") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_current:.1f}' + ' A' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Spannung Batterie") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_volt_bat:.1f}' + ' V' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Spannung Batteriezellen max") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_volt_max:.3f}' + ' V' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Spannung Batteriezellen min") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_volt_min:.3f}' + ' V' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Spannung Batteriezellen Differenz") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_volt_diff * 1000:.1f}' + ' mV' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Temperatur Batterie") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_temp_bat:.1f}' + ' °C' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Temperatur Batterie max") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_temp_max:.1f}' + ' °C' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Temperatur Batterie min") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_temp_min:.1f}' + ' °C' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Laden total") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_charge_total:.1f}' + ' kWh' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Entladen total") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_discharge_total:.1f}' + ' kWh' + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Wirkungsgrad") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + f'{self.plugin.byd_eta:.1f}' + ' %' + '</td>' + '</tr>'
        t = t + '</tbody></table>'
        data['r1_table'] = t
        
        t = '<table id="byd_diag_home2" border="1"><tbody>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Wechselrichter") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_inv_str + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Batterietyp") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_batt_str + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Seriennummer") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_serial + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Türme") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + str(self.plugin.byd_bms_qty) + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Module pro Turm") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + str(self.plugin.byd_modules) + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Parameter") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_application + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + self.translate("Fehler") + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_error_str + " (" + str(self.plugin.byd_error_nr) + ")" + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + 'BMS' + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_bmu + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + 'BMU' + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_bms + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + 'BMU A' + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_bmu_a + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + 'BMU B' + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_bmu_b + '</td>' + '</tr>'
        t = t + '<tr><td class="py-1"><strong>' + 'P/T' + ':</strong></td>' + '<td class="py-1" style="text-align: right">' + self.plugin.byd_param_t + '</td>' + '</tr>'
        t = t + '</tbody></table>'
        data['r2_table'] = t
        
        # 2.Register "BYD Diagnose"
        ds = []
        for xx in range(1,self.plugin.byd_towers_max+1):
          ts = []
          if xx <= self.plugin.byd_bms_qty:
            # Turm ist vorhanden
            ts.append(['SOC',f'{self.plugin.byd_diag_soc[xx]:.1f}' + " %"])
            ts.append(['SOH',f'{self.plugin.byd_diag_soh[xx]:.1f}' + " %"])
            ts.append([self.translate("Batteriespannung"),f'{self.plugin.byd_diag_bat_voltag[xx]:.1f}' + " V"])
            ts.append([self.translate("Spannung Out"),f'{self.plugin.byd_diag_v_out[xx]:.1f}' + " V"])
            ts.append([self.translate("Strom"),f'{self.plugin.byd_diag_current[xx]:.1f}' + " A"])
            ts.append([self.translate("Spannung max (Zelle)"),f'{self.plugin.byd_diag_volt_max[xx]:.3f}' + " V (" + str(self.plugin.byd_diag_volt_max_c[xx]) + ")"])
            ts.append([self.translate("Spannung min (Zelle)"),f'{self.plugin.byd_diag_volt_min[xx]:.3f}' + " V (" + str(self.plugin.byd_diag_volt_min_c[xx]) + ")"])
            ts.append([self.translate("Spannung Differenz"),f'{self.plugin.byd_diag_volt_diff[xx]:.0f}' + " mV"])
            ts.append([self.translate("Temperatur max (Zelle)"),f'{self.plugin.byd_diag_temp_max[xx]:.1f}' + " V (" + str(self.plugin.byd_diag_temp_max_c[xx]) + ")"])
            ts.append([self.translate("Temperatur min (Zelle)"),f'{self.plugin.byd_diag_temp_min[xx]:.1f}' + " V (" + str(self.plugin.byd_diag_temp_min_c[xx]) + ")"])
            ts.append([self.translate("Laden total"),f'{self.plugin.byd_diag_charge_total[xx]:.3f}' + " kWh"])
            ts.append([self.translate("Entladen total"),f'{self.plugin.byd_diag_discharge_total[xx]:.3f}' + " kWh"])
            ts.append([self.translate("Balancing Anzahl Zellen"),f'{self.plugin.byd_diag_balance_number[xx]:.0f}'])
          else:
            for ii in range(0,13):
              ts.append(['',''])
          ds.append(ts)

        t = '<table id="byd_diag_table" border="1">'
        t = t + '<thead><tr><th class="py-1" width=40%></th>'
        t = t + '<th class="py-1" style="text-align: center" width=20%>' + self.translate("Turm") + ' 1</th>'
        if self.plugin.byd_bms_qty > 1:
          t = t + '<th class="py-1" style="text-align: center" width=20%>' + self.translate("Turm") + ' 2</th>'
          if self.plugin.byd_bms_qty > 2:
            t = t + '<th class="py-1" style="text-align: center" width=20%>' + self.translate("Turm") + ' 3</th>'
        t = t + '</tr></thead>'
        t = t + '<tbody>'
        for ii in range(0,13):
          t = t + self.table_diag_row(ds[0][ii][0],ds[0][ii][1],ds[1][ii][1],ds[2][ii][1])
        t = t + '</tbody></table>'
        data['r3_table'] = t
        
        t = '<p><strong>' + self.translate("Turm") + ' 1 BMS</strong></p><p></p>'
        t = t + self.table_diag_details(1)
        t = t + '<p>' + self.translate("Status") + ': ' + self.plugin.byd_diag_state_str[1] + ' (0x' + f'{self.plugin.byd_diag_state[1]:04x}' + ')</p>'
        if self.plugin.byd_bms_qty > 1:
          t = t + '<p></p>'
          t = t + '<p><strong>' + self.translate("Turm") + ' 2 BMS</strong></p>'
          t = t + self.table_diag_details[2]
          t = t + '<p>' + self.translate("Status") + ': ' + self.plugin.byd_diag_state_str[2] + ' (0x' + f'{self.plugin.byd_diag_state[2]:04x}' + ')</p>'
          if self.plugin.byd_bms_qty > 2:
            t = t + '<p></p>'
            t = t + '<p><strong>' + self.translate("Turm") + ' 3 BMS</strong></p>'
            t = t + self.table_diag_details[3]
            t = t + '<p>' + self.translate("Status") + ': ' + self.plugin.byd_diag_state_str[3] + ' (0x' + f'{self.plugin.byd_diag_state[3]:04x}' + ')</p>'
        data['r4_table'] = t

        # 5.Register "BYD Logdaten"
        t = '<p><strong>BMU</strong></p><p></p>'
        t = t + self.plugin.byd_bmu_log_html
        t = t + '<p></p>'
        t = t + '<p><strong>' + self.translate("Turm") + ' 1 BMS</strong></p>'
        t = t + self.plugin.byd_diag_bms_log_html[1]
        if self.plugin.byd_bms_qty > 1:
          t = t + '<p></p>'
          t = t + '<p><strong>' + self.translate("Turm") + ' 2 BMS</strong></p>'
          t = t + self.plugin.byd_diag_bms_log_html[2]
          if self.plugin.byd_bms_qty > 2:
            t = t + '<p></p>'
            t = t + '<p><strong>' + self.translate("Turm") + ' 3 BMS</strong></p>'
            t = t + self.plugin.byd_diag_bms_log_html[3]
        data['r5_table'] = t

#        self.logger.warning("done done")
        
        # return it as json to the web page
        try:
          return json.dumps(data)
        except Exception as e:
          self.logger.error("get_data_html exception: {}".format(e))

    def table_diag_row(self,title,s1,s2,s3):
        s = '<tr>'
        s = s + '<td class="py-1"><strong>' + title + ':</strong></td>'
        s = s + '<td class="py-1" style="text-align: center">' + s1 + '</td>'
        if self.plugin.byd_bms_qty > 1:
          s = s + '<td class="py-1" style="text-align: center">' + s2 + '</td>'
          if self.plugin.byd_bms_qty > 2:
            s = s + '<td class="py-1" style="text-align: center">' + s3 + '</td>'
        s = s + '</tr>'
        return s
        
    def table_diag_details(self,xx):
        t = '<table id="byd_diag_table2" border="1">'
        t = t + '<tr>''<td>' + '' + '</td>'
        for i in range(0,self.plugin.byd_modules):
          t = t + '<td class="py-1" style="text-align: center"><strong>' + 'M' + str(i+1) + '</strong></td>'
        t = t + '</tr>'
        t = t + self.table_diag_details_row(self.translate("Spannung minimal") + ' [V]',xx,self.plugin.byd_module_vmin,3)
        t = t + self.table_diag_details_row(self.translate("Spannung maximal") + ' [V]',xx,self.plugin.byd_module_vmax,3)
        t = t + self.table_diag_details_row(self.translate("Spannung Durchschnitt") + ' [V]',xx,self.plugin.byd_module_vava,3)
        t = t + self.table_diag_details_row(self.translate("Spannung Differenz") + ' [mV]',xx,self.plugin.byd_module_vdif,0)
        t = t + '</tbody></table>'
        return t
        
    def table_diag_details_row(self,txt,xx,vi,nn):
        t = '<tr>'
        t = t + '<td class="py-1">' + txt + '</td>'
        for i in range(0,self.plugin.byd_modules):
          if nn == 1:
            t = t + '<td class="py-1" style="text-align: center">' + f'{self.plugin.byd_diag_module[xx][i][vi]:.1f}' + '</td>'
          elif nn == 2:
            t = t + '<td class="py-1" style="text-align: center">' + f'{self.plugin.byd_diag_module[xx][i][vi]:.2f}' + '</td>'
          elif nn == 3:
            t = t + '<td class="py-1" style="text-align: center">' + f'{self.plugin.byd_diag_module[xx][i][vi]:.3f}' + '</td>'
          else:
            t = t + '<td class="py-1" style="text-align: center">' + f'{self.plugin.byd_diag_module[xx][i][vi]:.0f}' + '</td>'
        t = t + '</tr>'
        return t

    @cherrypy.expose
    def byd_connection_true(self):
        self.logger.warning("byd_connection_true")
        self.plugin.byd_root.enable_connection(True)
        return
        
    @cherrypy.expose
    def byd_connection_false(self):
        self.logger.warning("byd_connection_false")
        self.plugin.byd_root.enable_connection(False)
        return
        
        