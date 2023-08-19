#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2023       Matthias Manhart             smarthome@beathis.ch
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Monitoring of BYD energy storage systems (HVM, HVS).
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

# -----------------------------------------------------------------------
#
# History
#
# V0.0.1 230811 - erster Release
#
# V0.0.2 230812 - Korrektur Berechnung Batteriestrom
#
# V0.0.3 230819 - Code mit pycodestyle kontrolliert/angepasst
#               - Anpassungen durch 'check_plugin'
#
# -----------------------------------------------------------------------
#
# Als Basis fuer die Implementierung wurde die folgende Quelle verwendet:
#
# https://github.com/christianh17/ioBroker.bydhvs
#
# Diverse Notizen
#
# - Datenpaket wird mit CRC16/MODBUS am Ende abgeschlossen (2 Byte, LSB,MSB)
#
# -----------------------------------------------------------------------

from lib.model.smartplugin import *
from lib.item import Items
from .webif import WebInterface
import cherrypy

import socket
import time
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

byd_ip_default = "192.168.16.254"

scheduler_name = 'mmbyd'

BUFFER_SIZE = 4096

byd_sample_basics = 60                           # Abfrage fuer Basisdaten [s]

byd_timeout_1s = 1.0
byd_timeout_2s = 2.0
byd_timeout_8s = 8.0

byd_tours_max = 3
byd_cells_max = 160
byd_temps_max = 64

byd_no_of_col = 8

byd_webif_img = "/webif/static/img/"
byd_path_empty = "x"
byd_fname_volt = "bydvt"
byd_fname_temp = "bydtt"
byd_fname_ext = ".png"

MESSAGE_0   = "010300000066c5e0"
MESSAGE_1   = "01030500001984cc"
MESSAGE_2   = "010300100003040e"

MESSAGE_3_1 = "0110055000020400018100f853"        # Start Messung Turm 1
MESSAGE_3_2 = "01100550000204000281000853"        # Start Messung Turm 2
MESSAGE_3_3 = "01100550000204000381005993"        # Start Messung Turm 3
MESSAGE_4   = "010305510001d517"
MESSAGE_5   = "01030558004104e5"
MESSAGE_6   = "01030558004104e5"
MESSAGE_7   = "01030558004104e5"
MESSAGE_8   = "01030558004104e5"

MESSAGE_9   = "01100100000306444542554700176f"    # switch to second turn for the last few cells (not tested, perhaps only for tower 1 ?)
MESSAGE_10  = "0110055000020400018100f853"        # start measuring remaining cells (like 3a) (not tested, perhaps only for tower 1 ?)
MESSAGE_11  = "010305510001d517"                  # (like 4) (not tested)
MESSAGE_12  = "01030558004104e5"                  # (like 5) (not tested)
MESSAGE_13  = "01030558004104e5"                  # (like 6) (not tested)

byd_errors = [
  "High Temperature Charging (Cells)",
  "Low Temperature Charging (Cells)",
  "Over Current Discharging",
  "Over Current Charging",
  "Main circuit Failure",
  "Short Current Alarm",
  "Cells Imbalance",
  "Current Sensor Failure",
  "Battery Over Voltage",
  "Battery Under Voltage",
  "Cell Over Voltage",
  "Cell Under Voltage",
  "Voltage Sensor Failure",
  "Temperature Sensor Failure",
  "High Temperature Discharging (Cells)",
  "Low Temperature Discharging (Cells)"
]

byd_invs = [
  "Fronius HV",
  "Goodwe HV",
  "Fronius HV",
  "Kostal HV",
  "Goodwe HV",
  "SMA SBS3.7/5.0",
  "Kostal HV",
  "SMA SBS3.7/5.0",
  "Sungrow HV",
  "Sungrow HV",
  "Kaco HV",
  "Kaco HV",
  "Ingeteam HV",
  "Ingeteam HV",
  "SMA SBS 2.5 HV",
  "",
  "SMA SBS 2.5 HV",
  "Fronius HV"
]

byd_invs_lvs = [
    "Fronius HV",
    "Goodwe HV",
    "Goodwe HV",
    "Kostal HV",
    "Selectronic LV",
    "SMA SBS3.7/5.0",
    "SMA LV",
    "Victron LV",
    "Suntech LV",
    "Sungrow HV",
    "Kaco HV",
    "Studer LV",
    "Solar Edge LV",
    "Ingeteam HV",
    "Sungrow LV",
    "Schneider LV",
    "SMA SBS2.5 HV",
    "Solar Edge LV",
    "Solar Edge LV",
    "Solar Edge LV"
]


class byd_bat(SmartPlugin):

    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '0.0.3'
    
    def __init__(self,sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        
        if self.get_parameter_value('ip') != '':
          self.ip = self.get_parameter_value('ip')
        else:
          self.log_info("no ip defined => use default '" + byd_ip_default + "'")
          self.ip = byd_ip_default
        
        if self.get_parameter_value('imgpath') != '':
          self.bpath = self.get_parameter_value('imgpath')
          if self.bpath is None:
            self.log_info("path is None")
            self.bpath = byd_path_empty
        else:
          self.log_info("no path defined")
          self.bpath = byd_path_empty
        
        self.log_debug("BYD ip   = " + self.ip)
        self.log_debug("BYD path = " + self.bpath)

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = byd_sample_basics
        
        self.last_diag_hour = 99                  # erzwingt beim ersten Aufruf das Abfragen der Detaildaten
        
        self.byd_root_found = False
        
        self.byd_diag_soc = []
        self.byd_diag_volt_max = []
        self.byd_diag_volt_max_c = []
        self.byd_diag_volt_min = []
        self.byd_diag_volt_min_c = []
        self.byd_diag_temp_max_c = []
        self.byd_diag_temp_min_c = []
        self.byd_volt_cell = []
        self.byd_temp_cell = []
        for x in range(0,byd_tours_max + 1):
          self.byd_diag_soc.append(0)
          self.byd_diag_volt_max.append(0)
          self.byd_diag_volt_max_c.append(0)
          self.byd_diag_volt_min.append(0)
          self.byd_diag_volt_min_c.append(0)
          self.byd_diag_temp_max_c.append(0)
          self.byd_diag_temp_min_c.append(0)
          a = []
          for xx in range(0,byd_cells_max + 1):
            a.append(0)
          self.byd_volt_cell.append(a)
          a = []
          for xx in range(0,byd_temps_max + 1):
            a.append(0)
          self.byd_temp_cell.append(a)
          
        self.last_homedata = self.now_str()
        self.last_diagdata = self.now_str()

        # Initialization code goes here

        self.sh = sh
        
        self.init_webinterface()
        
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.scheduler_add(scheduler_name,self.poll_device,cycle=self._cycle)

        self.alive = True
        
        return

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        # todo
        # if interesting item for sending values:
        #   self._itemlist.append(item)
        #   return self.update_item
        if self.get_iattr_value(item.conf,'byd_root'):
          self.byd_root = item
          self.byd_root_found = True
          self.log_debug("BYD root = " + "{0}".format(self.byd_root))

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        # Wird aufgerufen, wenn ein Item mit dem Attribut 'mmgarden' geaendert wird

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this plugin:
            
            return

    def poll_device(self):
        # Wird alle 'self._cycle' aufgerufen
        
        self.log_debug("BYD Start *********************")
        
        if self.byd_root_found is False:
          self.log_debug("BYD not root found - please define root item with structure 'byd_struct'")
          return
        
        # Verbindung herstellen
        client = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
          client.connect((self.ip,8080))
        except:
          self.log_info("client.connect failed (" + self.ip + ")")
          self.byd_root.info.connection(False)
          client.close()
          return
          
        # 1.Befehl senden
        client.send(bytes.fromhex(MESSAGE_0))
        client.settimeout(byd_timeout_1s)
        
        try:
          data = client.recv(BUFFER_SIZE)
        except:
          self.log_info("client.recv 0 failed")
          self.byd_root.info.connection(False)
          client.close()
          return
        self.decode_0(data)
        
        # 2.Befehl senden
        client.send(bytes.fromhex(MESSAGE_1))
        client.settimeout(byd_timeout_1s)
        
        try:
          data = client.recv(BUFFER_SIZE)
        except:
          self.log_info("client.recv 1 failed")
          self.byd_root.info.connection(False)
          client.close()
          return
        self.decode_1(data)
        
        # 3.Befehl senden
        client.send(bytes.fromhex(MESSAGE_2))
        client.settimeout(byd_timeout_1s)
        
        try:
          data = client.recv(BUFFER_SIZE)
        except:
          self.log_info("client.recv 2 failed")
          self.byd_root.info.connection(False)
          client.close()
          return
        self.decode_2(data)
        
        # Speichere die Basisdaten
        self.basisdata_save(self.byd_root)
        
        # Pruefe, ob die Diagnosedaten abgefragt werden sollen
        tn = self.now()
        if tn.hour == self.last_diag_hour:
          self.byd_root.info.connection(True)
          self.log_debug("BYD Basic Done ****************")
          client.close()
          return
          
        self.last_diag_hour = tn.hour
        
        # Durchlaufe alle Tuerme
        for x in range(1,self.byd_bms_qty + 1):
          self.log_debug("Turm " + str(x))
          
          # 4.Befehl senden
          if x == 1:
            client.send(bytes.fromhex(MESSAGE_3_1))
          elif x == 2:
            client.send(bytes.fromhex(MESSAGE_3_2))
          elif x == 3:
            client.send(bytes.fromhex(MESSAGE_3_3))
          client.settimeout(byd_timeout_2s)
          
          try:
            data = client.recv(BUFFER_SIZE)
          except:
            self.log_info("client.recv 3 failed")
            self.byd_root.info.connection(False)
            client.close()
            return
          self.decode_nop(data,x)
          time.sleep(2)
          
          # 5.Befehl senden
          client.send(bytes.fromhex(MESSAGE_4))
          client.settimeout(byd_timeout_8s)
        
          try:
            data = client.recv(BUFFER_SIZE)
          except:
            self.log_info("client.recv 4 failed")
            self.byd_root.info.connection(False)
            client.close()
            return
          self.decode_nop(data,x)
          
          # 6.Befehl senden
          client.send(bytes.fromhex(MESSAGE_5))
          client.settimeout(byd_timeout_1s)
        
          try:
            data = client.recv(BUFFER_SIZE)
          except:
            self.log_info("client.recv 5 failed")
            self.byd_root.info.connection(False)
            client.close()
            return
          self.decode_5(data,x)
          
          # 7.Befehl senden
          client.send(bytes.fromhex(MESSAGE_6))
          client.settimeout(byd_timeout_1s)
        
          try:
            data = client.recv(BUFFER_SIZE)
          except:
            self.log_info("client.recv 6 failed")
            self.byd_root.info.connection(False)
            client.close()
            return
          self.decode_6(data,x)
          
          # 8.Befehl senden
          client.send(bytes.fromhex(MESSAGE_7))
          client.settimeout(byd_timeout_1s)
        
          try:
            data = client.recv(BUFFER_SIZE)
          except:
            self.log_info("client.recv 7 failed")
            self.byd_root.info.connection(False)
            client.close()
            return
          self.decode_7(data,x)
          
          # 9.Befehl senden
          client.send(bytes.fromhex(MESSAGE_8))
          client.settimeout(byd_timeout_1s)
        
          try:
            data = client.recv(BUFFER_SIZE)
          except:
            self.log_info("client.recv 8 failed")
            self.byd_root.info.connection(False)
            client.close()
            return
          self.decode_8(data,x)
          
        self.diagdata_save(self.byd_root)
        self.byd_root.info.connection(True)

        self.log_debug("BYD Diag Done +++++++++++++++++")
        client.close()

        return
        
    def decode_0(self,data):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_0'.
        
        self.log_debug("decode_0: " + data.hex())
        
        # Serienummer
        self.byd_serial = ""
        for x in range(3,22):
          self.byd_serial = self.byd_serial + chr(data[x])
          
        # Firmware-Versionen
        self.byd_bmu_a = "V" + str(data[27]) + "." + str(data[28])
        self.byd_bmu_b = "V" + str(data[29]) + "." + str(data[30])
        if data[33] == 0:
          self.byd_bmu = self.byd_bmu_a + "-A"
        else:
          self.byd_bmu = self.byd_bmu_b + "-B"
        self.byd_bms = "V" + str(data[31]) + "." + str(data[32]) + "-" + chr(data[34] + 65)

        # Anzahl Tuerme und Anzahl Module pro Turm
        self.byd_bms_qty = data[36] // 0x10
        if (self.byd_bms_qty == 0) or (self.byd_bms_qty > byd_tours_max):
          self.byd_bms_qty = 1
        self.byd_modules = data[36] % 0x10
        self.byd_batt_type_snr = data[5]
        
        # Application
        if data[38] == 1:
          self.byd_application = "OnGrid"
        else:
          self.byd_application = "OffGrid"
          
        self.log_debug("Serial      : " + self.byd_serial)
        self.log_debug("BMU A       : " + self.byd_bmu_a)
        self.log_debug("BMU B       : " + self.byd_bmu_b)
        self.log_debug("BMU         : " + self.byd_bmu)
        self.log_debug("BMS         : " + self.byd_bms)
        self.log_debug("BMS QTY     : " + str(self.byd_bms_qty))
        self.log_debug("Modules     : " + str(self.byd_modules))
        self.log_debug("Application : " + self.byd_application)
        return

    def decode_1(self,data):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_1'.

        self.log_debug("decode_1: " + data.hex())
        
        self.byd_soc = self.buf2int16SI(data,3)
        self.byd_soh = self.buf2int16SI(data,9)
        
        self.byd_volt_bat = self.buf2int16US(data,13) * 1.0 / 100.0
        self.byd_volt_out = self.buf2int16US(data,35) * 1.0 / 100.0
        self.byd_volt_max = self.buf2int16SI(data,5) * 1.0 / 100.0
        self.byd_volt_min = self.buf2int16SI(data,7) * 1.0 / 100.0
        self.byd_volt_diff = self.byd_volt_max - self.byd_volt_min
        self.byd_current = self.buf2int16SI(data,11) * 1.0 / 10.0
        self.byd_power = self.byd_volt_out * self.byd_current
        if self.byd_power >= 0:
          self.byd_power_discharge = self.byd_power
          self.byd_power_charge = 0
        else:
          self.byd_power_discharge = 0
          self.byd_power_charge = -self.byd_power
          
        self.byd_temp_bat = self.buf2int16SI(data,19)
        self.byd_temp_max = self.buf2int16SI(data,15)
        self.byd_temp_min = self.buf2int16SI(data,17)

        self.byd_error_nr = self.buf2int16SI(data,29)
        self.byd_error_str = ""
        for x in range(0,16):
          if (((1 << x) & self.byd_error_nr) != 0):
            if len(self.byd_error_str) > 0:
              self.byd_error_str = self.byd_error_str + ";"
            self.byd_error_str = self.byd_error_str + byd_errors[x]
        if len(self.byd_error_str) == 0:
          self.byd_error_str = "no error"

        self.byd_param_t = str(data[31]) + "." + str(data[32])
        
        self.log_debug("SOC          : " + str(self.byd_soc))
        self.log_debug("SOH          : " + str(self.byd_soh))
        self.log_debug("Volt Battery : " + str(self.byd_volt_bat))
        self.log_debug("Volt Out     : " + str(self.byd_volt_out))
        self.log_debug("Volt max     : " + str(self.byd_volt_max))
        self.log_debug("Volt min     : " + str(self.byd_volt_min))
        self.log_debug("Volt diff    : " + str(self.byd_volt_diff))
        self.log_debug("Current      : " + str(self.byd_current))
        self.log_debug("Power        : " + str(self.byd_power))
        self.log_debug("Temp Battery : " + str(self.byd_temp_bat))
        self.log_debug("Temp max     : " + str(self.byd_temp_max))
        self.log_debug("Temp min     : " + str(self.byd_temp_min))
        self.log_debug("Error        : " + str(self.byd_error_nr) + " " + self.byd_error_str)
        self.log_debug("ParamT       : " + self.byd_param_t)
        return
        
    def decode_2(self,data):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_2'.

        self.log_debug("decode_2: " + data.hex())

        self.byd_batt_type = data[5]
        if self.byd_batt_type == 0:
          # HVL -> unknown specification, so 0 cells and 0 temps
          self.byd_batt_str = "HVL"
          self.byd_capacity_module = 4.0
          self.byd_volt_n = 0
          self.byd_temp_n = 0
          self.byd_cells_n = 0
          self.byd_temps_n = 0
        elif self.byd_batt_type == 1:
          # HVM 16 Cells per module
          self.byd_batt_str = "HVM"
          self.byd_capacity_module = 2.76
          self.byd_volt_n = 16
          self.byd_temp_n = 8
          self.byd_cells_n = self.byd_modules * self.byd_volt_n
          self.byd_temps_n = self.byd_modules * self.byd_temp_n
        elif self.byd_batt_type == 2:
          # HVS 32 cells per module
          self.byd_batt_str = "HVS"
          self.byd_capacity_module = 2.56
          self.byd_volt_n = 32
          self.byd_temp_n = 12
          self.byd_cells_n = self.byd_modules * self.byd_volt_n
          self.byd_temps_n = self.byd_modules * self.byd_temp_n
        else:
          if (self.byd_batt_type_snr == 49) or (self.byd_batt_type_snr == 50):
            self.byd_batt_str = "LVS"
            self.byd_capacity_module = 4.0
            self.byd_volt_n = 7
            self.byd_temp_n = 0
            self.byd_cells_n = self.byd_modules * self.byd_volt_n
            self.byd_temps_n = 0
          else:
            self.byd_batt_str = "???"
            self.byd_capacity_module = 0.0
            self.byd_volt_n = 0
            self.byd_temp_n = 0
            self.byd_cells_n = 0
            self.byd_temps_n = 0
            
        self.byd_capacity_total = self.byd_bms_qty * self.byd_modules * self.byd_capacity_module
        
        self.byd_inv_type = data[3]
        if self.byd_batt_str == "LVS":
          self.byd_inv_str = byd_invs_lvs[self.byd_inv_type]
        else:
          self.byd_inv_str = byd_invs[self.byd_inv_type]
        
        self.log_debug("Inv Type  : " + self.byd_inv_str + " (" + str(self.byd_inv_type) + ")")
        self.log_debug("Batt Type : " + self.byd_batt_str + " (" + str(self.byd_batt_type) + ")")
        self.log_debug("Cells n   : " + str(self.byd_cells_n))
        self.log_debug("Temps n   : " + str(self.byd_temps_n))
        
        if self.byd_cells_n > byd_cells_max:
          self.byd_cells_n = byd_cells_max
        if self.byd_temps_n > byd_temps_max:
          self.byd_temps_n = byd_temps_max
        return
   
    def decode_5(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_5'.

        self.log_debug("decode_5 (" + str(x) + ") : " + data.hex())
        
        self.byd_diag_soc[x] = self.buf2int16SI(data,53) * 1.0 / 10.0
        self.byd_diag_volt_max[x] = self.buf2int16SI(data,5) / 1000.0
        self.byd_diag_volt_max_c[x] = data[9]
        self.byd_diag_volt_min[x] = self.buf2int16SI(data,7) / 1000.0
        self.byd_diag_volt_min_c[x] = data[10]
        self.byd_diag_temp_max_c[x] = data[15]
        self.byd_diag_temp_min_c[x] = data[16]
        
        # starting with byte 101, ending with 131, Cell voltage 1-16
        for xx in range(0,16):
          self.byd_volt_cell[x][xx] = self.buf2int16SI(data,101 + (xx * 2)) / 1000.0

        self.log_debug("SOC      : " + str(self.byd_diag_soc[x]))
        self.log_debug("Volt max : " + str(self.byd_diag_volt_max[x]) + " c=" + str(self.byd_diag_volt_max_c[x]))
        self.log_debug("Volt min : " + str(self.byd_diag_volt_min[x]) + " c=" + str(self.byd_diag_volt_min_c[x]))
        self.log_debug("Temp max : " + " c=" + str(self.byd_diag_temp_max_c[x]))
        self.log_debug("Temp min : " + " c=" + str(self.byd_diag_temp_min_c[x]))
#        for xx in range(0,16):
#          self.log_debug("Turm " + str(x) + " Volt " + str(xx) + " : " + str(self.byd_volt_cell[x][xx]))
        
        return

    def decode_6(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_6'.

        self.log_debug("decode_6 (" + str(x) + ") : " + data.hex())
        
        for xx in range(0,64):
          self.byd_volt_cell[x][16 + xx] = self.buf2int16SI(data,5 + (xx * 2)) / 1000.0
          
#        for xx in range(0,64):
#          self.log_debug("Turm " + str(x) + " Volt " + str(16 + xx) + " : " + str(self.byd_volt_cell[x][16 + xx]))

        return

    def decode_7(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_7'.

        self.log_debug("decode_7 (" + str(x) + ") : " + data.hex())

        # starting with byte 5, ending 101, voltage for cell 81 to 128
        for xx in range(0,48):
          self.byd_volt_cell[x][80 + xx] = self.buf2int16SI(data,5 + (xx * 2)) / 1000.0
        
        # starting with byte 103, ending 132, temp for cell 1 to 30
        for xx in range(0,30):
          self.byd_temp_cell[x][xx] = data[103 + xx]

#        for xx in range(0,48):
#          self.log_debug("Turm " + str(x) + " Volt " + str(80 + xx) + " : " + str(self.byd_volt_cell[x][80 + xx]))
#        for xx in range(0,30):
#          self.log_debug("Turm " + str(x) + " Temp " + str(xx) + " : " + str(self.byd_temp_cell[x][xx]))
        
        return

    def decode_8(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_8'.

        self.log_debug("decode_8 (" + str(x) + ") : " + data.hex())

        for xx in range(0,34):
          self.byd_temp_cell[x][30 + xx] = data[5 + xx]
        
#        for xx in range(0,34):
#          self.log_debug("Turm " + str(x) + " Temp " + str(30 + xx) + " : " + str(self.byd_temp_cell[x][30 + xx]))

        return

    def decode_nop(self,data,x):
#        self.log_debug("decode_nop (" + str(x) + ") : " + data.hex())
        return
        
    def basisdata_save(self,device):
        # Speichert die Basisdaten in der sh-Struktur.

        self.log_debug("basisdata_save")
        
        device.state.current(self.byd_current)
        device.state.power(self.byd_power)
        device.state.power_charge(self.byd_power_charge)
        device.state.power_discharge(self.byd_power_discharge)
        device.state.soc(self.byd_soc)
        device.state.soh(self.byd_soh)
        device.state.tempbatt(self.byd_temp_bat)
        device.state.tempmax(self.byd_temp_max)
        device.state.tempmin(self.byd_temp_min)
        device.state.voltbatt(self.byd_volt_bat)
        device.state.voltdiff(self.byd_volt_diff)
        device.state.voltmax(self.byd_volt_max)
        device.state.voltmin(self.byd_volt_min)
        device.state.voltout(self.byd_volt_out)
        
        device.system.bms(self.byd_bms)
        device.system.bmu(self.byd_bmu)
        device.system.bmubanka(self.byd_bmu_a)
        device.system.bmubankb(self.byd_bmu_b)
        device.system.batttype(self.byd_batt_str)
        device.system.errornum(self.byd_error_nr)
        device.system.errorstr(self.byd_error_str)
        device.system.grid(self.byd_application)
        device.system.invtype(self.byd_inv_str)
        device.system.modules(self.byd_modules)
        device.system.bmsqty(self.byd_bms_qty)
        device.system.capacity_total(self.byd_capacity_total)
        device.system.paramt(self.byd_param_t)
        device.system.serial(self.byd_serial)
        
        self.last_homedata = self.now_str()

        return
        
    def diagdata_save(self,device):
        # Speichert die Diagnosedaten in der sh-Struktur.

        self.log_debug("diagdata_save")
        
        self.diagdata_save_one(device.diagnosis.tower1,1)
        if self.byd_bms_qty > 1:
          self.diagdata_save_one(device.diagnosis.tower2,2)
        if self.byd_bms_qty > 2:
          self.diagdata_save_one(device.diagnosis.tower3,3)
    
        self.last_diagdata = self.now_str()
        
        return

    def diagdata_save_one(self,device,x):
    
        device.soc(self.byd_diag_soc[x])
        device.volt_max.volt(self.byd_diag_volt_max[x])
        device.volt_max.cell(self.byd_diag_volt_max_c[x])
        device.volt_min.volt(self.byd_diag_volt_min[x])
        device.volt_min.cell(self.byd_diag_volt_min_c[x])
        device.temp_max_cell(self.byd_diag_temp_max_c[x])
        device.temp_min_cell(self.byd_diag_temp_min_c[x])
        
        self.diag_plot(x)
        
#        self.log_debug("Turm " + str(x))
#        for xx in range(0,self.byd_cells_n):
#          self.log_debug("Volt " + str(xx+1) + " : " + str(self.byd_volt_cell[x][xx]))
#        for xx in range(0,self.byd_temps_n):
#          self.log_debug("Temp " + str(xx+1) + " : " + str(self.byd_temp_cell[x][xx]))
          
        return
        
    def diag_plot(self,x):
    
        # Heatmap der Spannungen
        i = 0
        j = 1
        rows = self.byd_cells_n // byd_no_of_col
        d = []
        rt = []
        for r in range(0,rows):
          c = []
          for cc in range(0,byd_no_of_col):
            c.append(self.byd_volt_cell[x][i])
            i = i + 1
          d.append(c)
          rt.append("M" + str(j))
          if ((r + 1) % (self.byd_volt_n // self.byd_modules)) == 0:
            j = j + 1
        dd = np.array(d)
                  
        fig,ax = plt.subplots(figsize=(10,4))  # Erzeugt ein Bitmap von 1000x500 Pixel
        
        im = ax.imshow(dd)
        cbar = ax.figure.colorbar(im,ax=ax,shrink=0.5)
        cbar.ax.yaxis.set_tick_params(color='white')
        cbar.outline.set_edgecolor('white')
        plt.setp(plt.getp(cbar.ax.axes,'yticklabels'),color='white')
        
        ax.set_aspect(0.25)
        ax.get_xaxis().set_visible(False)
        ax.set_yticks(np.arange(len(rt)),labels=rt)
        
        ax.spines[:].set_visible(False)
        ax.set_xticks(np.arange(dd.shape[1] + 1) - .5,minor=True)
        ax.set_yticks(np.arange(dd.shape[0] + 1) - .5,minor=True,size=10)
        ax.tick_params(which='minor',bottom=False,left=False)
        ax.tick_params(axis='y',colors='white')
        
        textcolors = ("white","black")
        threshold = im.norm(dd.max()) / 2.
        kw = dict(horizontalalignment="center",verticalalignment="center",size=9)
        valfmt = matplotlib.ticker.StrMethodFormatter("{x:.3f}")
        
        # Loop over data dimensions and create text annotations.
        for i in range(0,rows):
          for j in range(0,byd_no_of_col):
            kw.update(color=textcolors[int(im.norm(dd[i,j]) > threshold)])
            text = ax.text(j,i,valfmt(dd[i,j], None),**kw)
                           
        ax.set_title("Turm " + str(x) + " - Spannungen [V]" + " (" + self.now_str() + ")",size=10,color='white')
        
        fig.tight_layout()
        if len(self.bpath) != byd_path_empty:
          fig.savefig(self.bpath + byd_fname_volt + str(x) + byd_fname_ext,format='png',transparent=True)
          self.log_debug("save " + self.bpath + byd_fname_temp + str(x) + byd_fname_ext)
        fig.savefig(self.get_plugin_dir() + byd_webif_img + byd_fname_volt + str(x) + byd_fname_ext,
                    format='png',transparent=True)
        self.log_debug("save " + self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(x) + byd_fname_ext)
        plt.close('all')
    
        # Heatmap der Temperaturen
        i = 0
        j = 1
        rows = self.byd_temps_n // byd_no_of_col
        d = []
        rt = []
        for r in range(0,rows):
          c = []
          for cc in range(0,byd_no_of_col):
            c.append(self.byd_temp_cell[x][i])
            i = i + 1
          d.append(c)
          rt.append("M" + str(j))
          if ((r + 1) % (self.byd_temp_n // self.byd_modules)) == 0:
            j = j + 1
        dd = np.array(d)
        cmap = matplotlib.colors.LinearSegmentedColormap.from_list('',['#f5f242','#ffaf38','#fc270f'])
        norm = matplotlib.colors.TwoSlopeNorm(vcenter=dd.min() + (dd.max() - dd.min()) / 2,
                                              vmin=dd.min(),vmax=dd.max())
                  
        fig,ax = plt.subplots(figsize=(10,2.5))  # Erzeugt ein Bitmap von 1000x400 Pixel
        
        im = ax.imshow(dd,cmap=cmap,norm=norm)
        cbar = ax.figure.colorbar(im,ax=ax,shrink=0.5)
        cbar.ax.yaxis.set_tick_params(color='white')
        cbar.outline.set_edgecolor('white')
        plt.setp(plt.getp(cbar.ax.axes,'yticklabels'),color='white')
       
        ax.set_aspect(0.28)
        ax.get_xaxis().set_visible(False)
        ax.set_yticks(np.arange(len(rt)),labels=rt)
        
        ax.spines[:].set_visible(False)
        ax.set_xticks(np.arange(dd.shape[1] + 1) - .5,minor=True)
        ax.set_yticks(np.arange(dd.shape[0] + 1) - .5,minor=True,size=10)
        ax.tick_params(which='minor',bottom=False,left=False)
        ax.tick_params(axis='y',colors='white')
        
        textcolors = ("black","white")
        threshold = im.norm(dd.max()) / 2.
        kw = dict(horizontalalignment="center",verticalalignment="center",size=9)
        valfmt = matplotlib.ticker.StrMethodFormatter("{x:.0f}")
        
        # Loop over data dimensions and create text annotations.
        for i in range(0,rows):
          for j in range(0,byd_no_of_col):
            kw.update(color=textcolors[int(im.norm(dd[i,j]) > threshold)])
            text = ax.text(j,i,valfmt(dd[i,j], None),**kw)
                           
        ax.set_title("Turm " + str(x) + " - Temperaturen [°C]" + " (" + self.now_str() + ")",size=10,color='white')

        fig.tight_layout()
        if len(self.bpath) != byd_path_empty:
          fig.savefig(self.bpath + byd_fname_temp + str(x) + byd_fname_ext,format='png',transparent=True)
          self.log_debug("save " + self.bpath + byd_fname_temp + str(x) + byd_fname_ext)
        fig.savefig(self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(x) + byd_fname_ext,
                    format='png',transparent=True)
        self.log_debug("save " + self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(x) + byd_fname_ext)
        plt.close('all')

        return

    def buf2int16SI(self,byteArray,pos):   # signed
        result = byteArray[pos] * 256 + byteArray[pos + 1]
        if (result > 32768):
            result -= 65536
        return result

    def buf2int16US(self,byteArray,pos):   # unsigned
        result = byteArray[pos] * 256 + byteArray[pos + 1]
        return result

    def now_str(self):
        return self.now().strftime("%d.%m.%Y, %H:%M:%S")

    def log_debug(self,s1):
        self.logger.debug(s1)

    def log_info(self,s1):
        self.logger.warning(s1)

    # webinterface init method
    def init_webinterface(self):

        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http is None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
            return False

        # set application configuration for cherrypy
        webif_dir = self.path_join(self.get_plugin_dir(), 'webif')
        config = {
          '/': {
                'tools.staticdir.root': webif_dir,
               },
          '/static': {
                       'tools.staticdir.on': True,
                       'tools.staticdir.dir': 'static'
                     }
                 }

        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir,self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(),
                                     self.get_instance_name(),
                                     description='')

        return True
