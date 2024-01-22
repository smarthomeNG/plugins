#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2024       Matthias Manhart             smarthome@beathis.ch
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
# =======
#
# V0.0.1 230811 - erster Release
#
# V0.0.2 230812 - Korrektur Berechnung Batteriestrom
#
# V0.0.3 230819 - Code mit pycodestyle kontrolliert/angepasst
#               - Anpassungen durch 'check_plugin'
#
# V0.0.4 230904 - Bilder JPG in PNG konvertiert fuer user_doc.rst
#
# V0.0.5 231030 - Diagnose ergaenzt: Bat-Voltag, V-Out, Current
#               - Liste der Wechselrichter aktualisiert
#               - Alle Plot-Dateien beim Plugin-Start loeschen
#               - Anpassungen fuer mathplotlib 3.8.0 mit requirements.txt
#               - webif aktualisiert (Uebersetzungen, Parameter)
#
# V0.0.6 231126 - Diagnose ergaenzt Temperatur max/min
#               - Auslesen und anzeigen der Balancing-Flags im Plot
#               - Plot diverse Fehler korrigiert
#               - Plot-Dateien loeschen ueberarbeitet
#               - Batterietypen HVS, HVM und LVS im Plot getestet
#
# V0.0.7 231209 - item_structs.byd_struct.enable_connection neu
#                 true -> Kommunikation mit BYD aktiv, false -> keine Kommunikation
#               - Temperatur Fehler beim Auslesen korrigiert
#               - Neuer Parameter 'diag_cycle' fuer Abfrage der Diagnosedaten
#
# V0.0.8 240112 - Leere kleine PNG fuer nicht vorhandene Tuerme erzeugen
#               - Zellen mit Balancing werden neu rot umrandet (Heatmap Spannungen)
#               - Turm Diagnose Balancing neue Items 'active' und 'number'
#               - Turm Diagnose neues Item 'volt_diff' fuer Spannungsdifferenz (Max-Min)
#               - Turm neue Items 'soh' und 'state'
#               - Neuer Parameter 'log_data' und 'log_age'
#               - Neue Items 'state.charge_total', 'state.discharge_total' und 'state.eta'
#               - Turm Diagnose neue Items 'charge_total' und 'discharge_total'
#               - Liste der Wechselrichter aktualisiert
#               - Funktion 'send_msg' mit CRC-Check ergaenzt
#               - Berechnung diverser Werte fuer jedes Modul in jedem Turm 'diagnosis/towerX/modules/...'
#               - Abfrage der Logdaten in BMU und BMS implementiert
#               - Logdaten BYD werden in speziellen Logdateien pro Tag gespeichert
#               - Logdaten werden speziell fuer Visualisierung aufbereitet 'visu/...'
#               - Diverse Anpassungen in der Code-Struktur
#
# V0.1.0 240113 - Release
#
# V0.1.1 240115 - Neue Items 'info/last_state','info/last_diag','info/last_log'
#               - Dummy-Plot-Dateien werden in 'imgpath' nicht mehr erstellt
#               - Fehler korrigiert (self.decode_nop(data,x,MESSAGE_9_L))
#               - Balkendiagramm Balancing Farbe geaendert auf gruen
#               - Plot Spannung im Titel Details zu den Daten ergaenzt
#               - Balkendiagramm Legende mit Farbcodes ergaenzt
#
# V0.1.2 240120 - Logdaten Verarbeitung ergaenzt (BMS 9,20)
#
# -----------------------------------------------------------------------
#
# Als Basis fuer die Implementierung wurde u.a. folgende Quelle verwendet:
#
# https://github.com/christianh17/ioBroker.bydhvs
#
# Diverse Notizen
#
# - Max. Anzahl Module: HVS=2-5, HVM=3-8, HVL=3-8, LVS=1-8
# - Beginn Frame (Senden/Empfangen): 0x01 0x03 (Beispiel, es gibt auch andere Startsequenzen)
# - Antwort 3.Byte (direkt nach Header): Anzahl Bytes Nutzdaten (?) (2 Byte CRC werden mitgezaehlt)
#   packetLength = data[2] + 5; (3 header, 2 crc)
#   https://crccalc.com/ (Input=Hex, CRC-16, CRC-16/MODBUS)
# - Datenpaket wird mit CRC16/MODBUS am Ende abgeschlossen (2 Byte,LSB,MSB) (Nutzdaten+Längenbyte)
# - Der Server im BYD akzeptiert nur 1 Verbindung auf Port 8080/TCP !
# - Ein Register (Index) hat 2 Bytes und ist MSB,LSB aufgebaut
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
import matplotlib.patches as patches
from matplotlib.lines import Line2D
import numpy as np
import os
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from decimal import Decimal,ROUND_DOWN

#import random    # only for internal test [TEST]

byd_ip_default = "192.168.16.254"

scheduler_name = 'byd_bat'

byd_sample_basics = 60                             # Abfrage fuer Basisdaten [s]
byd_sample_diag = 300                              # Abfrage fuer Diagnosedaten [s]
byd_sample_log = 300                               # Abfrage fuer Logdaten [s]

byd_timeout_1s = 1.0
byd_timeout_2s = 2.0
byd_timeout_8s = 8.0
byd_timeout_10s = 10.0

byd_towers_max = 3
byd_cells_max = 160
byd_temps_max = 64
byd_module_max = 8

byd_no_of_col_7 = 7
byd_no_of_col_8 = 8
byd_no_of_col_12 = 12

byd_webif_img = "/webif/static/img/"
byd_path_empty = "x"
byd_fname_volt = "bydvt"
byd_fname_volt2 = "bydvbt"
byd_fname_temp = "bydtt"
byd_fname_ext = ".png"

byd_ok = 1
byd_error = 0

byd_module_vmin = 0
byd_module_vmax = 1
byd_module_vava = 2
byd_module_vdif = 3

BUFFER_SIZE = 4096                                 # Groesse Empfangsbuffer

byd_log_max_rows = 40                              # maximale Anzahl Eintraege (html/json)
byd_log_directory = "byd_logs"
byd_log_extension = "log"
byd_log_special = "byd_special"
byd_log_newline = "\n"
byd_log_sep = "\t"

# Log-Daten Indizes in der Liste
byd_log_year = 0                                   # Jahr
byd_log_month = 1                                  # Monat
byd_log_day = 2                                    # Tag
byd_log_hour = 3                                   # Stunde
byd_log_minute = 4                                 # Minute
byd_log_second = 5                                 # Sekunde
byd_log_codex = 6                                  # Code des Log-Eintrages
byd_log_data = 7                                   # Daten zum Log-Eintrag
byd_log_raw = 8                                    # Roh-Daten des Log-Eintrages
byd_log_str = 9                                    # 'byd_log_data' als String
byd_log_str_sep = " | "
byd_log_degree = "*C"

MESSAGE_0    = "010300000066c5e0"
MESSAGE_0_L  = 209
MESSAGE_1    = "01030500001984cc"
MESSAGE_1_L  = 55
MESSAGE_2    = "010300100003040e"
MESSAGE_2_L  = 11

MESSAGE_3_1  = "0110055000020400018100f853"        # Start Messung Turm 1
MESSAGE_3_2  = "01100550000204000281000853"        # Start Messung Turm 2
MESSAGE_3_3  = "01100550000204000381005993"        # Start Messung Turm 3
MESSAGE_3_L  = 8
MESSAGE_4    = "010305510001d517"
MESSAGE_4_L  = 7
MESSAGE_5    = "01030558004104e5"
MESSAGE_5_L  = 135
MESSAGE_6    = "01030558004104e5"
MESSAGE_6_L  = 135
MESSAGE_7    = "01030558004104e5"
MESSAGE_7_L  = 135
MESSAGE_8    = "01030558004104e5"
MESSAGE_8_L  = 135
                                                   # to read the 5th module, the box must first be reconfigured (not tested)
MESSAGE_9    = "01100100000306444542554700176f"    # switch to second turn for the last few cells
MESSAGE_9_L  = 0                                   # UNBEKANNT !!
MESSAGE_10_1 = "0110055000020400018100f853"        # start measuring remaining cells in tower 1 (like 3)
MESSAGE_10_2 = "01100550000204000281000853"        # start measuring remaining cells in tower 2 (like 3)
MESSAGE_10_3 = "01100550000204000381005993"        # start measuring remaining cells in tower 3 (like 3)
MESSAGE_10_L = 8
MESSAGE_11   = "010305510001d517"                  # (like 4)
MESSAGE_11_L = 7
MESSAGE_12   = "01030558004104e5"                  # (like 5)
MESSAGE_12_L = 135
MESSAGE_13   = "01030558004104e5"                  # (like 6)
MESSAGE_13_L = 135
MESSAGE_14   = "01030558004104e5"                  # (like 7)
MESSAGE_14_L = 135
MESSAGE_15   = "01030558004104e5"                  # (like 8)
MESSAGE_15_L = 135

EVT_MSG_0_0 = "011005a000020400008100A6D7"         # BMU
EVT_MSG_0_1 = "011005a000020400018100f717"         # BMS tower 1
EVT_MSG_0_2 = "011005a0000204000281000717"         # BMS tower 2
EVT_MSG_0_3 = "011005a00002040003810056D7"         # BMS tower 3
EVT_MSG_0_L  = 8
EVT_MSG_1   = "010305A8004104D6"                   # request log-data
EVT_MSG_1_L  = 135

byd_errors = [
  "High Temperature Charging (Cells)",             #  0
  "Low Temperature Charging (Cells)",              #  1
  "Over Current Discharging",                      #  2
  "Over Current Charging",                         #  3
  "Main circuit Failure",                          #  4
  "Short Current Alarm",                           #  5
  "Cells Imbalance",                               #  6
  "Current Sensor Failure",                        #  7
  "Battery Over Voltage",                          #  8
  "Battery Under Voltage",                         #  9
  "Cell Over Voltage",                             # 10
  "Cell Under Voltage",                            # 11
  "Voltage Sensor Failure",                        # 12
  "Temperature Sensor Failure",                    # 13
  "High Temperature Discharging (Cells)",          # 14
  "Low Temperature Discharging (Cells)"            # 15
]

# Liste der Wechselrichter (entnommen aus Be_Connect)
byd_inverters = [
  "Fronius HV",                                    #  0
  "Goodwe HV/Viessmann HV",                        #  1
  "KOSTAL HV",                                     #  2
  "SMA SBS3.7/5.0/6.0 HV",                         #  3
  "Sungrow HV",                                    #  4
  "KACO_HV",                                       #  5
  "Ingeteam HV",                                   #  6
  "SMA SBS2.5 HV",                                 #  7
  "Solis HV",                                      #  8
  "SMA STP 5.0-10.0 SE HV",                        #  9
  "GE HV",                                         # 10
  "Deye HV",                                       # 11
  "KACO_NH",                                       # 12
  "Solplanet",                                     # 13
  "Western HV",                                    # 14
  "SOSEN",                                         # 15
  "Hoymiles HV",                                   # 16
  "SAJ HV",                                        # 17
  "Selectronic LV",                                # 18
  "SMA LV",                                        # 19
  "Victron LV",                                    # 20
  "Studer LV",                                     # 21
  "Schneider LV",                                  # 22
  "Solis LV",                                      # 23
  "Deye LV",                                       # 24
  "Raion LV",                                      # 25
  "Hoymiles LV",                                   # 26
  "Goodwe LV/Viessmann LV",                        # 27
  "SolarEdge LV",                                  # 28
  "Sungrow LV Phocos LV",                          # 29
  "Suntech LV"                                     # 30  (nicht im Hauptblock von Be_Connect)
]

# Status eines Turms (2 Byte, 16 Bit)
byd_stat_tower = [
    "Battery Over Voltage",                         # Bit 0
    "Battery Under Voltage",                        # Bit 1
    "Cells OverVoltage",                            # Bit 2
    "Cells UnderVoltage",                           # Bit 3
    "Cells Imbalance",                              # Bit 4
    "Charging High Temperature(Cells)",             # Bit 5
    "Charging Low Temperature(Cells)",              # Bit 6
    "DisCharging High Temperature(Cells)",          # Bit 7
    "DisCharging Low Temperature(Cells)",           # Bit 8
    "Charging OverCurrent(Cells)",                  # Bit 9
    "DisCharging OverCurrent(Cells)",               # Bit 10
    "Charging OverCurrent(Hardware)",               # Bit 11
    "Short Circuit",                                # Bit 12
    "Inversly Connection",                          # Bit 13
    "Interlock switch Abnormal",                    # Bit 14
    "AirSwitch Abnormal"                            # Bit 15
]

byd_log_code = [
    [  0,"Power ON"],                               # [  0]
    [  1,"Power OFF"],                              # [  1]
    [  2,"Events record"],                          # [  2]  Events appear, Events disappear
    [  3,"Timing Record"],                          # [  3]
    [  4,"Start Charging"],                         # [  4]
    [  5,"Stop Charging"],                          # [  5]
    [  6,"Start DisCharging"],                      # [  6]
    [  7,"Stop DisCharging"],                       # [  7]
    [  8,"SOC calibration rough"],                  # [  8]
    [  9,"??"],                                     # [  9]
    [ 10,"SOC calibration Stop"],                   # [ 10]
    [ 11,"CAN Communication failed"],               # [ 11]
    [ 12,"Serial Communication failed"],            # [ 12]
    [ 13,"Receive PreCharge Command"],              # [ 13]
    [ 14,"PreCharge Successful"],                   # [ 14]
    [ 15,"PreCharge Failure"],                      # [ 15]
    [ 16,"Start end SOC calibration"],              # [ 16]
    [ 17,"Start Balancing"],                        # [ 17]
    [ 18,"Stop Balancing"],                         # [ 18]
    [ 19,"Address Registered"],                     # [ 19]
    [ 20,"System Functional Safety Fault"],         # [ 20]
    [ 21,"Events additional info"],                 # [ 21]
    [ 22,"Start Firmware Update"],                  # [ 22]
    [ 23,"Firmware Update finish"],                 # [ 23]
    [ 24,"Firmware Update fails"],                  # [ 24]
    [ 25,"SN Code was Changed"],                    # [ 25]
    [ 26,"Current Calibration"],                    # [ 26]
    [ 27,"Battery Voltage Calibration"],            # [ 27]
    [ 28,"PackVoltage Calibration"],                # [ 28]
    [ 29,"SOC/SOH Calibration"],                    # [ 29]
    [ 30,"??"],                                     # [ 30]
    [ 31,"??"],                                     # [ 31]
    [ 32,"System status changed"],                  # [ 32]
    [ 33,"Erase BMS Firmware"],                     # [ 33]
    [ 34,"BMS update start"],                       # [ 34]
    [ 35,"BMS update done"],                        # [ 35]
    [ 36,"Functional Safety Info"],                 # [ 36]
    [ 37,"No Defined"],                             # [ 37]
    [ 38,"SOP Info"],                               # [ 38]
    [ 39,"??"],                                     # [ 39]
    [ 40,"BMS Firmware list"],                      # [ 40]
    [ 41,"MCU list of BMS"],                        # [ 41]
    
    # BCU Hardware failt
    # Firmware Update failure 
    # Firmware Jumpinto other section 

    [101,"Firmware Start to Update"],               # [101]  BMS: Start Firmware Update
    [102,"Firmware Update Successful"],             # [102]  BMS: Firmware Update finish
                                                    
    [105,"Parameters table Update"],                # [105]
    [106,"SN Code was Changed"],                    # [106]
                                                    
    [111,"DateTime Calibration"],                   # [111]
    [112,"BMS disconnected with BMU"],              # [112]
    [113,"MU F/W Reset"],                           # [113]
    [114,"BMU Watchdog Reset"],                     # [114]
    [115,"PreCharge Failed"],                       # [115]
    [116,"Address registration failed"],            # [116]
    [117,"Parameters table Load Failed"],           # [117]
    [118,"System timing log"]                       # [118]
    
    # Parameters table updating done 
]

# System-Code (Log SOP Info (38), Quelle: Be_Connect 2.0.9, * = aus eigenen Log-Dateien)
byd_log_status = [
    "SYS_STANDBY",                                  # 0 *
    "SYS_INACTIVE",                                 # 1 *
    "SYS_BLACK_START",                              # 2
    "SYS_ACTIVE",                                   # 3 *
    "SYS_FAULT",                                    # 4
    "SYS_UPDATING",                                 # 5
    "SYS_SHUTDOWN",                                 # 6 *
    "SYS_PRECHARGE",                                # 7 *
    "SYS_BATT_CHECK",                               # 8 *
    "SYS_ASSIGN_ADDR",                              # 9 *
    "SYS_LOAD_PARAM",                               # 10 *
    "SYS_INIT",                                     # 11 *
    "SYS_UNKNOWN12"                                 # 12
]

byd_module_type = [
    "HVL",
    "HVM",
    "HVS",
    "Not defined"
]

# Warnungen fuer Events record (2) (16 Bit)
byd_log_bmu_warnings = [
    "??",                                           # 0
    "??",                                           # 1
    "Cells OverVoltage",                            # 2
    "Cells UnderVoltage",                           # 3
    "V-sensor failure",                             # 4
    "??",                                           # 5
    "??",                                           # 6
    "Cell discharge Temp-Low",                      # 7
    "??",                                           # 8
    "Cell charge Temp-Low",                         # 9
    "??",                                           # 10
    "??",                                           # 11
    "??",                                           # 12
    "??",                                           # 13
    "Cells imbalance",                              # 14
    "??"                                            # 15
]

# Fehlermeldungen fuer Events record (2) (Enum)
byd_log_bmu_errors = [
    "Total Voltage too High",                       # 0
    "Total Voltage too Low",                        # 1
    "Cell Voltage too High",                        # 2
    "Cell Voltage too Low",                         # 3
    "Voltage Sensor Fault",                         # 4
    "Temperature Sersor Fault",                     # 5
    "Cell Discharging Temp. too High",              # 6
    "Cell Discharging Temp. too Low",               # 7
    "Cell Charging Temp. too High",                 # 8
    "Cell Charging Temp. too Low",                  # 9
    "Discharging Over Current",                     # 10
    "Charging Over Current",                        # 11
    "Major loop Fault",                             # 12
    "Short Circuit warning",                        # 13
    "Battery Imbalance",                            # 14
    "Current Sensor Fault",                         # 15
    "??",                                           # 16
    "??",                                           # 17
    "??",                                           # 18
    "??",                                           # 19
    "??",                                           # 20
    "??",                                           # 21
    "??",                                           # 22
    ""                                              # 23 (Wert, wenn keine Meldung)
]

# Warnungen fuer BMS (16 Bit)
byd_log_bms_warnings = [
    "Battery Over Voltage",                         # 0
    "Battery Under Voltage",                        # 1
    "Cells OverVoltage",                            # 2 *
    "Cells UnderVoltage",                           # 3 *
    "Cells Imbalance",                              # 4 *
    "Charging High Temperature(Cells)",             # 5
    "Charging Low Temperature(Cells)",              # 6
    "DisCharging High Temperature(Cells)",          # 7
    "DisCharging Low Temperature(Cells)",           # 8
    "Charging OverCurrent(Cells)",                  # 9
    "DisCharging OverCurrent(Cells)",               # 10
    "Charging OverCurrent(Hardware)",               # 11
    "Short Circuit",                                # 12
    "Inversly Connection",                          # 13
    "Interlock switch Abnormal",                    # 14
    "AirSwitch Abnormal"                            # 15
]

# Fehler fuer BMS (16 Bit)
byd_log_bms_failures = [
    "Cells Voltage Sensor Failure",                 # 0 *
    "Temperature Sensor Failure",                   # 1
    "BIC Communication Failure",                    # 2
    "Pack Voltage Sensor Failure",                  # 3
    "Current Sensor Failure",                       # 4
    "Charging Mos Failure",                         # 5
    "DisCharging Mos Failure",                      # 6
    "PreCharging Mos Failure",                      # 7
    "Main Relay Failure",                           # 8
    "PreCharging Failed",                           # 9
    "Heating Device Failure",                       # 10
    "Radiator Failure",                             # 11
    "BIC Balance Failure",                          # 12
    "Cells Failure",                                # 13
    "PCB Temperature Sensor Failure",               # 14
    "Functional Safety Failure"                     # 15
]

# Switch Status fuer BMS (8 Bit)
byd_log_bms_switch_status_on = [
    "Charge Mos_Switch is on",                      # 0
    "DisCharge Mos_Switch is on",                   # 1
    "PreCharge Mos_Switch is on",                   # 2
    "Relay is on",                                  # 3 *
    "Air Switch is on",                             # 4 *
    "PreCharge_2 Mos_Switch is on",                 # 5
    "??",                                           # 6
    "??"                                            # 7
]

byd_log_bms_switch_status_off = [
    "Charge Mos_Switch is off",                     # 0
    "DisCharge Mos_Switch is off",                  # 1
    "PreCharge Mos_Switch is off",                  # 2
    "Relay is off",                                 # 3 *  -> nur diesen Wert in einem Log gesehen
    "Air Switch is off",                            # 4 *
    "PreCharge_2 Mos_Switch is off",                # 5
    "??",                                           # 6
    "??"                                            # 7
]

# Power-Off fuer BMS (Enum 1 Byte)
byd_log_bms_poweroff = [
    ""                                                             # 0
    "Press BMS LED button to Switch off",                          # 1
    "BMU requires to switch off",                                  # 2 *
    "BMU Power off And communication between BMU and BMS failed",  # 3 *
    "Power off while communication failed(after 30 minutes)",      # 4
    "Premium LV BMU requires to Power off",                        # 5
    "Press BMS LED to Power off",                                  # 6
    "Power off due to communication failed with BMU",              # 7
    "BMS off due to battery UnderVoltage",                         # 8
    "??",                                                          # 9
]

# -----------------------------------------------------------------------
# Plugin-Code
# -----------------------------------------------------------------------

class byd_bat(SmartPlugin):

    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '0.1.2'
    ALLOW_MULTIINSTANCE = False
    
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
        
        if self.get_parameter_value('diag_cycle') != '':
          self.diag_cycle = self.get_parameter_value('diag_cycle')
          if self.diag_cycle is None:
            self.diag_cycle = byd_sample_diag
        else:
          self.log_info("no diag_cycle defined => use default '" + str(byd_sample_diag) + "s'")
          self.diag_cycle = byd_sample_diag
        if self.diag_cycle < byd_sample_basics:
          self.diag_cycle = byd_sample_basics

        if self.get_parameter_value('log_data') != '':
          self.log_data = self.get_parameter_value('log_data')
          if self.log_data is None:
            self.log_data = False
        else:
          self.log_info("log_data not defined => log_data=false")
          self.log_data = False
        
        if self.get_parameter_value('log_age') != '':
          self.log_age = self.get_parameter_value('log_age')
          if self.log_age is None:
            self.log_age = 365
        else:
          self.log_info("no log_age defined => use default '" + str(365) + "s'")
          self.log_age = 365
        if self.log_age < 0:
          self.log_age = 0

        self.log_debug("BYD ip               = " + self.ip)
        self.log_debug("BYD path             = " + self.bpath)
        self.log_debug("BYD diagnostic cycle = " + f"{self.diag_cycle:.0f}" + "s")
        self.log_debug("BYD log data         = " + str(self.log_data))
        self.log_debug("BYD log age          = " + str(self.log_age) + " days")

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = byd_sample_basics
        
        self.last_diag_secs = 9999                  # erzwingt beim ersten Aufruf das Abfragen der Detaildaten
        self.last_log_secs = 9999                   # erzwingt beim ersten Aufruf das Abfragen der Log-Daten
        
        self.byd_root_found = False
        
        self.byd_towers_max = byd_towers_max
        self.byd_module_vmin = byd_module_vmin
        self.byd_module_vmax = byd_module_vmax
        self.byd_module_vava = byd_module_vava
        self.byd_module_vdif = byd_module_vdif

        # State
        self.byd_current = 0
        self.byd_power = 0
        self.byd_power_charge = 0
        self.byd_power_discharge = 0
        self.byd_soc = 0
        self.byd_soh = 0
        self.byd_temp_bat = 0
        self.byd_temp_max = 0
        self.byd_temp_min = 0
        self.byd_volt_bat = 0
        self.byd_volt_diff = 0
        self.byd_volt_max = 0
        self.byd_volt_min = 0
        self.byd_volt_out = 0
        self.byd_charge_total = 0
        self.byd_discharge_total = 0
        self.byd_eta = 0
        
        # System
        self.byd_bms = ""
        self.byd_bmu = ""
        self.byd_bmu_a = ""
        self.byd_bmu_b = ""
        self.byd_batt_str = ""
        self.byd_error_nr = 0
        self.byd_error_str = ""
        self.byd_application = ""
        self.byd_inv_str = ""
        self.byd_modules = 0
        self.byd_bms_qty = 0
        self.byd_capacity_total = 0
        self.byd_param_t = ""
        self.byd_serial = ""
        
        self.last_homedata = self.now_str()
        self.last_diagdata = self.now_str()
        
        self.byd_diag_soc = []
        self.byd_diag_soh = []
        self.byd_diag_state = []
        self.byd_diag_state_str = []
        self.byd_diag_bat_voltag = []
        self.byd_diag_v_out = []
        self.byd_diag_current = []
        self.byd_diag_volt_diff = []
        self.byd_diag_volt_max = []
        self.byd_diag_volt_max_c = []
        self.byd_diag_volt_min = []
        self.byd_diag_volt_min_c = []
        self.byd_diag_temp_max = []
        self.byd_diag_temp_max_c = []
        self.byd_diag_temp_min = []
        self.byd_diag_temp_min_c = []
        self.byd_diag_charge_total = []
        self.byd_diag_discharge_total = []
        self.byd_diag_balance_active = []
        self.byd_diag_balance_number = []
        self.byd_diag_bms_log = []                            # Liste der Log-Eintraege pro Turm
        self.byd_diag_bms_log_html = []                       # HTML-Tabelle der Log-Eintrage pro Turm
        self.byd_diag_module = []                             # Liste der Daten zu den Modulen pro Turm
        self.byd_volt_cell = []
        self.byd_balance_cell = []
        self.byd_temp_cell = []
        self.byd_bmu_log = []
        self.byd_bmu_log_html = ""
        for x in range(0,byd_towers_max + 1):   # 0..3
          self.byd_diag_soc.append(0)
          self.byd_diag_soh.append(0)
          self.byd_diag_state.append(0)
          self.byd_diag_state_str.append(0)
          self.byd_diag_bat_voltag.append(0)
          self.byd_diag_v_out.append(0)
          self.byd_diag_current.append(0)
          self.byd_diag_volt_diff.append(0)
          self.byd_diag_volt_max.append(0)
          self.byd_diag_volt_max_c.append(0)
          self.byd_diag_volt_min.append(0)
          self.byd_diag_volt_min_c.append(0)
          self.byd_diag_temp_max.append(0)
          self.byd_diag_temp_max_c.append(0)
          self.byd_diag_temp_min.append(0)
          self.byd_diag_temp_min_c.append(0)
          self.byd_diag_charge_total.append(0)
          self.byd_diag_discharge_total.append(0)
          self.byd_diag_balance_active.append(0)
          self.byd_diag_balance_number.append(0)
          self.byd_diag_bms_log.append([])
          self.byd_diag_bms_log_html.append("")
          self.byd_diag_module.append([])
          a = []
          for xx in range(0,byd_cells_max + 1):   # 0..160
            a.append(0)
          self.byd_volt_cell.append(a)
          a = []
          for xx in range(0,byd_cells_max + 1):   # 0..160
            a.append(0)
          self.byd_balance_cell.append(a)
          a = []
          for xx in range(0,byd_temps_max + 1):   # 0..64
            a.append(0)
          self.byd_temp_cell.append(a)
          
        self.plt_file_del()
        
        # Log-Verzeichnis erstellen
        if self.log_data == True:
          self.log_dir = self.create_logdirectory(self.get_sh().get_basedir(),byd_log_directory)
          self.log_debug("log_dir=" + self.log_dir)
          
#        self.simulate_data()  # for internal tests only [TEST]

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

        if self.get_iattr_value(item.conf,'byd_root'):
          self.byd_root = item
          self.byd_root_found = True
          self.log_debug("BYD root = " + "{0}".format(self.byd_root))

        if self.has_iattr(item.conf,'byd_para'):
            self._itemlist.append(item)
            return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        # Wird aufgerufen, wenn ein Item mit dem Attribut 'mmgarden' geaendert wird

        self.log_debug("update_auto_item path=" + item.property.path + " name=" + item.property.name + " v=" + str(item()))
        
        if self.alive and caller != self.get_shortname():
          # code to execute if the plugin is not stopped
          # and only, if the item has not been changed by this plugin:
            
          s1 = item.property.path
          if s1.find("enable_connection") != -1:
            self.byd_root.info.connection(item())
            if item() == True:
              self.log_info("communication disabled => enabled !")
            else:
              self.log_info("communication enabled => disabled !")
            
        return

    def poll_device(self):
        # Wird alle 'self._cycle' aufgerufen
        
        if self.byd_root_found is False:
          self.log_debug("BYD not root found - please define root item with structure 'byd_struct'")
          return
        
        if self.byd_root.enable_connection() is False:
          self.log_debug("communication disabled !")
          return
        
        self.log_debug("BYD Start *********************")
        
        # Verbindung herstellen
        client = socket.socket(socket.AF_INET,socket.SOCK_STREAM)
        try:
          client.connect((self.ip,8080))
        except:
          self.log_info("client.connect failed (" + self.ip + ")")
          self.byd_root.info.connection(False)
          client.close()
          return
          
        # 0.Befehl senden
        res,data = self.send_msg(client,MESSAGE_0,byd_timeout_1s)
        if res != byd_ok:
          self.log_info("client.recv 0 failed")
          self.byd_root.info.connection(False)
          client.close()
          return
        if self.decode_0(data) == byd_error:
          return
        
        # 1.Befehl senden
        res,data = self.send_msg(client,MESSAGE_1,byd_timeout_1s)
        if res != byd_ok:
          self.log_info("client.recv 1 failed")
          self.byd_root.info.connection(False)
          client.close()
          return
        if self.decode_1(data) == byd_error:
          return
        
        # 2.Befehl senden
        res,data = self.send_msg(client,MESSAGE_2,byd_timeout_1s)
        if res != byd_ok:
          self.log_info("client.recv 1 failed")
          self.byd_root.info.connection(False)
          client.close()
          return
        if self.decode_2(data) == byd_error:
          return
        if self.byd_cells_n == 0:
          # Batterietyp wird nicht unterstuetzt !
          self.log_info("battery type " + self.byd_batt_str + " not supported !")
          self.byd_root.info.connection(False)
          client.close()
          return
        
        # Speichere die Basisdaten
        self.basisdata_save(self.byd_root)
        
        # Pruefe, ob die Diagnosedaten abgefragt werden sollen
        self.last_diag_secs = self.last_diag_secs + self._cycle
        if self.last_diag_secs >= self.diag_cycle:
          self.last_diag_secs = 0
          
          # Durchlaufe alle Tuerme
          for x in range(1,self.byd_bms_qty + 1):    # 1 ... self.byd_bms_qty
            self.log_debug("Diagnose Turm " + str(x))
            
            # 3.Befehl senden
            if x == 1:
              m = MESSAGE_3_1
            elif x == 2:
              m = MESSAGE_3_2
            elif x == 3:
              m = MESSAGE_3_3
            res,data = self.send_msg(client,m,byd_timeout_2s)
            if res != byd_ok:
              self.log_info("client.recv 3 failed")
              self.byd_root.info.connection(False)
              client.close()
              return
            if self.decode_nop(data,x,MESSAGE_3_L) == byd_error:
              return
            time.sleep(2)
            
            # 4.Befehl senden
            res,data = self.send_msg(client,MESSAGE_4,byd_timeout_10s)
            if res != byd_ok:
              self.log_info("client.recv 4 failed")
              self.byd_root.info.connection(False)
              client.close()
              return
            if self.decode_nop(data,x,MESSAGE_4_L) == byd_error:
              return
            
            # 5.Befehl senden
            res,data = self.send_msg(client,MESSAGE_5,byd_timeout_1s)
            if res != byd_ok:
              self.log_info("client.recv 5 failed")
              self.byd_root.info.connection(False)
              client.close()
              return
            if self.decode_5(data,x) == byd_error:
              return
            
            # 6.Befehl senden
            res,data = self.send_msg(client,MESSAGE_6,byd_timeout_1s)
            if res != byd_ok:
              self.log_info("client.recv 6 failed")
              self.byd_root.info.connection(False)
              client.close()
              return
            if self.decode_6(data,x) == byd_error:
              return
            
            # 7.Befehl senden
            res,data = self.send_msg(client,MESSAGE_7,byd_timeout_1s)
            if res != byd_ok:
              self.log_info("client.recv 7 failed")
              self.byd_root.info.connection(False)
              client.close()
              return
            if self.decode_7(data,x) == byd_error:
              return
            
            # 8.Befehl senden
            res,data = self.send_msg(client,MESSAGE_8,byd_timeout_1s)
            if res != byd_ok:
              self.log_info("client.recv 8 failed")
              self.byd_root.info.connection(False)
              client.close()
              return
            if self.decode_8(data,x) == byd_error:
              return
            
            if self.byd_cells_n > 128:
              # Switch to second turn for the last module - 9.Befehl senden
              res,data = self.send_msg(client,MESSAGE_9,byd_timeout_1s)
              if res != byd_ok:
                self.log_info("client.recv 9 failed")
                self.byd_root.info.connection(False)
                client.close()
                return
              self.decode_nop(data,x,MESSAGE_9_L)  # Laenge von MESSAGE_9 ist nicht bekannt - daher kein Abbruch hier
              time.sleep(2)
  
              # 10.Befehl senden (wie Befehl 3)
              if x == 1:
                m = MESSAGE_10_1
              elif x == 2:
                m = MESSAGE_10_2
              elif x == 3:
                m = MESSAGE_10_3
              res,data = self.send_msg(client,m,byd_timeout_2s)
              if res != byd_ok:
                self.log_info("client.recv 10 failed")
                self.byd_root.info.connection(False)
                client.close()
                return
              if self.decode_nop(data,x,MESSAGE_10_L) == byd_error:
                return
              time.sleep(2)
            
              # 11.Befehl senden (wie Befehl 4)
              res,data = self.send_msg(client,MESSAGE_11,byd_timeout_10s)
              if res != byd_ok:
                self.log_info("client.recv 11 failed")
                self.byd_root.info.connection(False)
                client.close()
                return
              if self.decode_nop(data,x,MESSAGE_11_L) == byd_error:
                return
              
              # 12.Befehl senden (wie Befehl 5)
              res,data = self.send_msg(client,MESSAGE_12,byd_timeout_1s)
              if res != byd_ok:
                self.log_info("client.recv 12 failed")
                self.byd_root.info.connection(False)
                client.close()
                return
              if self.decode_12(data,x) == byd_error:
                return
              
              # 13.Befehl senden (wie Befehl 6)
              res,data = self.send_msg(client,MESSAGE_13,byd_timeout_1s)
              if res != byd_ok:
                self.log_info("client.recv 13 failed")
                self.byd_root.info.connection(False)
                client.close()
                return
              if self.decode_13(data,x) == byd_error:
                return
              
              # 14.Befehl senden (wie Befehl 7)
              res,data = self.send_msg(client,MESSAGE_14,byd_timeout_1s)
              if res != byd_ok:
                self.log_info("client.recv 14 failed")
                self.byd_root.info.connection(False)
                client.close()
                return
              if self.decode_14(data,x) == byd_error:
                return
              
              # 15.Befehl senden (wie Befehl 8)
              res,data = self.send_msg(client,MESSAGE_15,byd_timeout_1s)
              if res != byd_ok:
                self.log_info("client.recv 15 failed")
                self.byd_root.info.connection(False)
                client.close()
                return
              if self.decode_15(data,x) == byd_error:
                return
                
            self.module_update(x)    # Bestimme gewisse Werte zu jedem Modul im Turm
  
          self.diagdata_save(self.byd_root)
          self.byd_root.info.connection(True)

          self.log_debug("BYD Diag Done +++++++++++++++++")
          
        # Pruefe, ob die Logdaten ausgelesen werden sollen
        if self.log_data == True:
          self.last_log_secs = self.last_log_secs + self._cycle
          if self.last_log_secs >= byd_sample_log:
            self.last_log_secs = 0
            if self.read_log_data(client) == byd_error:
              # Etwas ist schief gelaufen
              self.log_info("read_log_data failed")
              self.byd_root.info.connection(False)
              client.close()
              return
            else:
              self.byd_root.info.last_log(self.now_str())
                  
        client.close()

        return

# -----------------------------------------------------------------------
# Decodieren der Daten vom BYD-System (ohne Log-Daten)
# -----------------------------------------------------------------------
        
    def decode_0(self,data):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_0'.
        
        self.log_debug("decode_0: " + data.hex())
        
        if len(data) != MESSAGE_0_L:
          self.log_info("MESSAGE_0 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_0_L) + ")")
          return byd_error
        
        # Serienummer
        self.byd_serial = ""
        for x in range(3,22):  # 3..21
          self.byd_serial = self.byd_serial + chr(data[x])                                     # Byte 3 .. 21
        # self.byd_serial = "xxxxxxxxxxxxxxxxxxx"  # fuer Screenshots
          
        # Firmware-Versionen
        self.byd_bmu_a = "V" + str(data[27]) + "." + str(data[28])                             # Byte 27+28 (Register 12)
        self.byd_bmu_b = "V" + str(data[29]) + "." + str(data[30])                             # Byte 29+30 (Register 13)
        self.byd_bms   = "V" + str(data[31]) + "." + str(data[32]) + "-" + chr(data[34] + 65)  # Byte 31+32+34
        if data[33] == 0:                                                                      # Byte 33
          self.byd_bmu = self.byd_bmu_a + "-A"
        else:
          self.byd_bmu = self.byd_bmu_b + "-B"

        # Anzahl Tuerme und Anzahl Module pro Turm
        self.byd_bms_qty = data[36] // 0x10                                                    # Byte 36 Bit 4-7 (Anzahl Tuerme)
        if (self.byd_bms_qty == 0) or (self.byd_bms_qty > byd_towers_max):
          self.byd_bms_qty = 1
        self.byd_modules = data[36] % 0x10                                                     # Byte 36 Bit 0-3  (Anzahl Module)
        self.byd_batt_type_snr = data[5]                                                       # Byte 5 (LVS Batterietyp Unterscheidung)
        
        # Application
        if data[38] == 0:                                                                      # Byte 38
          self.byd_application = "OffGrid"
        elif data[38] == 1:
          self.byd_application = "OnGrid"
        elif data[38] == 2:
          self.byd_application = "Backup"
        else:
          self.byd_application = "unknown"
          
        self.log_debug("Serial      : " + self.byd_serial)
        self.log_debug("BMU A       : " + self.byd_bmu_a)
        self.log_debug("BMU B       : " + self.byd_bmu_b)
        self.log_debug("BMU         : " + self.byd_bmu)
        self.log_debug("BMS         : " + self.byd_bms)
        self.log_debug("BMS QTY     : " + str(self.byd_bms_qty))
        self.log_debug("Modules     : " + str(self.byd_modules))
        self.log_debug("Application : " + self.byd_application)
        
        return byd_ok

    def decode_1(self,data):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_1'.

        self.log_debug("decode_1: " + data.hex())
        
        if len(data) != MESSAGE_1_L:
          self.log_info("MESSAGE_1 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_1_L) + ")")
          return byd_error
        
        self.byd_soc = self.buf2int16SI(data,3)                       # Byte 3+4   (Register  0)
        self.byd_volt_max = self.buf2int16SI(data,5) * 1.0 / 100.0    # Byte 5+6   (Register  1)
        self.byd_volt_min = self.buf2int16SI(data,7) * 1.0 / 100.0    # Byte 7+8   (Register  2)
        self.byd_soh = self.buf2int16SI(data,9)                       # Byte 9+10  (Register  3)
        self.byd_current = self.buf2int16SI(data,11) * 1.0 / 10.0     # Byte 11+12 (Register  4)
        self.byd_volt_bat = self.buf2int16US(data,13) * 1.0 / 100.0   # Byte 13+14 (Register  5)
        self.byd_temp_max = self.buf2int16SI(data,15)                 # Byte 15+16 (Register  6)
        self.byd_temp_min = self.buf2int16SI(data,17)                 # Byte 17+18 (Register  7)
        self.byd_temp_bat = self.buf2int16SI(data,19)                 # Byte 19+20 (Register  8)
        
        self.byd_error_nr = self.buf2int16SI(data,29)                 # Byte 29+30 (Register 13)
        self.byd_error_str = ""
        for x in range(0,16):
          if (((1 << x) & self.byd_error_nr) != 0):
            if len(self.byd_error_str) > 0:
              self.byd_error_str = self.byd_error_str + ";"
            self.byd_error_str = self.byd_error_str + byd_errors[x]
        if len(self.byd_error_str) == 0:
          self.byd_error_str = "no error"

        self.byd_param_t = str(data[31]) + "." + str(data[32])        # Byte 31+32 (Register 14)
        
        self.byd_volt_out = self.buf2int16US(data,35) * 1.0 / 100.0   # Byte 35+36 (Register 16)
        self.byd_volt_diff = self.byd_volt_max - self.byd_volt_min
        self.byd_power = self.byd_volt_out * self.byd_current
        if self.byd_power >= 0:
          self.byd_power_discharge = self.byd_power
          self.byd_power_charge = 0
        else:
          self.byd_power_discharge = 0
          self.byd_power_charge = -self.byd_power
          
        self.byd_charge_total = self.buf2int32US(data,37) / 10.0      # Byte 37-40 (Register 17+18) (in 100Wh in data)
        self.byd_discharge_total = self.buf2int32US(data,41) / 10.0   # Byte 41-44 (Register 19+20) (in 100Wh in data)
        self.byd_eta = (self.byd_discharge_total / self.byd_charge_total) * 100.0

        self.log_debug("SOC             : " + f"{self.byd_soc:.1f}")
        self.log_debug("SOH             : " + f"{self.byd_soh:.1f}")
        self.log_debug("Volt Battery    : " + f"{self.byd_volt_bat:.1f}")
        self.log_debug("Volt Out        : " + f"{self.byd_volt_out:.1f}")
        self.log_debug("Volt max        : " + f"{self.byd_volt_max:.1f}")
        self.log_debug("Volt min        : " + f"{self.byd_volt_min:.1f}")
        self.log_debug("Volt diff       : " + f"{self.byd_volt_diff:.1f}")
        self.log_debug("Current         : " + f"{self.byd_current:.1f}")
        self.log_debug("Power           : " + f"{self.byd_power:.1f}")
        self.log_debug("Temp Battery    : " + f"{self.byd_temp_bat:.1f}")
        self.log_debug("Temp max        : " + f"{self.byd_temp_max:.1f}")
        self.log_debug("Temp min        : " + f"{self.byd_temp_min:.1f}")
        self.log_debug("Error           : " + f"{self.byd_error_nr:.0f}" + " " + self.byd_error_str)
        self.log_debug("ParamT          : " + self.byd_param_t)
        self.log_debug("Charge total    : " + f"{self.byd_charge_total:.1f}")
        self.log_debug("Discharge total : " + f"{self.byd_discharge_total:.1f}")
        self.log_debug("ETA             : " + f"{self.byd_eta:.1f}")
        
        return byd_ok
        
    def decode_2(self,data):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_2'.

        self.log_debug("decode_2: " + data.hex())

        if len(data) != MESSAGE_2_L:
          self.log_info("MESSAGE_2 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_2_L) + ")")
          return byd_error
        
        self.byd_batt_type = data[5]
        if self.byd_batt_type == 0:
          # HVL -> Lithium Iron Phosphate (LFP), 3-8 Module (12kWh-32kWh), unknown specification, so 0 cells and 0 temps
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
        self.byd_inv_str = self.get_inverter_name(self.byd_batt_str,self.byd_inv_type)
        
        self.log_debug("Inv Type  : " + self.byd_inv_str + " (" + str(self.byd_inv_type) + ")")
        self.log_debug("Batt Type : " + self.byd_batt_str + " (" + str(self.byd_batt_type) + ")")
        self.log_debug("Cells n   : " + f"{self.byd_cells_n:.0f}")
        self.log_debug("Temps n   : " + f"{self.byd_temps_n:.0f}")
        
        if self.byd_cells_n > byd_cells_max:
          self.byd_cells_n = byd_cells_max
        if self.byd_temps_n > byd_temps_max:
          self.byd_temps_n = byd_temps_max
          
        return byd_ok
   
    def decode_5(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_5'.

        self.log_debug("decode_5 (" + str(x) + ") : " + data.hex())
        
        if len(data) != MESSAGE_5_L:
          self.log_info("MESSAGE_5 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_5_L) + ")")
          return byd_error
        
        self.byd_diag_volt_max[x] = self.buf2int16SI(data,5) / 1000.0          # Byte 5+6   (Index 1)
        self.byd_diag_volt_min[x] = self.buf2int16SI(data,7) / 1000.0          # Byte 7+8   (Index 2)
        self.byd_diag_volt_max_c[x] = data[9]                                  # Byte 9     (Index 3)
        self.byd_diag_volt_min_c[x] = data[10]                                 # Byte 10
        self.byd_diag_temp_max[x] = self.buf2int16SI(data,11)                  # Byte 11+12 (Index 4)
        self.byd_diag_temp_min[x] = self.buf2int16SI(data,13)                  # Byte 13+14 (Index 5)
        self.byd_diag_temp_max_c[x] = data[15]                                 # Byte 15    (Index 6)
        self.byd_diag_temp_min_c[x] = data[16]                                 # Byte 16
        
        self.byd_diag_volt_diff[x] = (self.byd_diag_volt_max[x] - self.byd_diag_volt_min[x]) * 1000.0
        
        # Balancing-Flags. Es folgen 8x 16-bit-Worte (MSB,LSB!) = 16 Byte => 0..127 Bits
        i = 0      # Zaehlt die Bits
        nnn = 0    # Zaehlt die Anzahl der Zellen mit Balancing-Modus
        for xx in range(17,33):  # 17..32  (16 Byte) Index 7..14
          if (xx % 2) == 1:
            a = data[xx+1]  # LSB, Bit 0-7
          else:
            a = data[xx-1]  # MSB, Bit 8-15
#          self.log_debug("Balancing i=" + f"{i:.0f}" + " d=" + f"{a:.0f}")
          for yy in range(0,8):  # 0..7
            if (int(a) & 1) == 1:
              self.byd_balance_cell[x][i] = 1
              nnn = nnn + 1
            else:
              self.byd_balance_cell[x][i] = 0
            a = a / 2
            i = i + 1
        self.byd_diag_balance_number[x] = nnn

        self.byd_diag_charge_total[x] = self.buf2int32US(data,33) / 1000.0     # Byte 33-36 (Register 15+16) (in 1Wh in data)
        self.byd_diag_discharge_total[x] = self.buf2int32US(data,37) / 1000.0  # Byte 37-41 (Register 17+18) (in 1Wh in data)
        
        self.byd_diag_bat_voltag[x] = self.buf2int16SI(data,45) * 1.0 / 10.0   # Byte 45+46 (Index 21)
        
        self.byd_diag_v_out[x] = self.buf2int16SI(data,51) * 1.0 / 10.0        # Byte 51+52 (Index 24)
        self.byd_diag_soc[x] = self.buf2int16SI(data,53) * 1.0 / 10.0          # Byte 53+54 (Index 25)
        self.byd_diag_soh[x] = self.buf2int16SI(data,55) * 1.0                 # Byte 55+56 (Index 26)
        self.byd_diag_current[x] = self.buf2int16SI(data,57) * 1.0 / 10.0      # Byte 57+58 (Index 27)
        self.byd_diag_state[x] = data[59] * 0x100 + data[60]                   # Byte 59+60 (Index 28)
        
        # starting with byte 101, ending with 131, Cell voltage 0-15
        for xx in range(0,16):  # 0..15
          self.byd_volt_cell[x][xx] = self.buf2int16SI(data,101 + (xx * 2)) / 1000.0

        self.log_debug("SOC             : " + f"{self.byd_diag_soc[x]:.1f}")
        self.log_debug("SOH             : " + f"{self.byd_diag_soh[x]:.1f}")
        self.log_debug("Bat Voltag      : " + f"{self.byd_diag_bat_voltag[x]:.2f}")
        self.log_debug("V-Out           : " + f"{self.byd_diag_v_out[x]:.2f}")
        self.log_debug("Current         : " + f"{self.byd_diag_current[x]:.2f}")
        self.log_debug("Volt max        : " + f"{self.byd_diag_volt_max[x]:.3f}" + " c=" + f"{self.byd_diag_volt_max_c[x]:.0f}")
        self.log_debug("Volt min        : " + f"{self.byd_diag_volt_min[x]:.3f}" + " c=" + f"{self.byd_diag_volt_min_c[x]:.0f}")
        self.log_debug("Volt diff       : " + f"{self.byd_diag_volt_diff[x]:.1f}")
        self.log_debug("Temp max        : " + f"{self.byd_diag_temp_max[x]:.1f}" + " c=" + f"{self.byd_diag_temp_max_c[x]:.0f}")
        self.log_debug("Temp min        : " + f"{self.byd_diag_temp_min[x]:.1f}" + " c=" + f"{self.byd_diag_temp_min_c[x]:.0f}")
        self.log_debug("Charge total    : " + f"{self.byd_diag_charge_total[x]:.3f}")
        self.log_debug("Discharge total : " + f"{self.byd_diag_discharge_total[x]:.3f}")
        self.log_debug("Status          : " + "0x" + f"{self.byd_diag_state[x]:04x}")
        self.log_debug("Balancing       : " + f"{nnn:.0f}")
#        for xx in range(0,16):
#          self.log_debug("Turm " + str(x) + " Volt " + str(xx) + " : " + str(self.byd_volt_cell[x][xx]))
        
        return byd_ok

    def decode_6(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_6'.

        self.log_debug("decode_6 (" + str(x) + ") : " + data.hex())
        
        if len(data) != MESSAGE_6_L:
          self.log_info("MESSAGE_6 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_6_L) + ")")
          return byd_error
        
        for xx in range(0,64):  # 0..63, Cell voltage 16-79
          self.byd_volt_cell[x][16 + xx] = self.buf2int16SI(data,5 + (xx * 2)) / 1000.0
          
#        for xx in range(0,64):
#          self.log_debug("Turm " + str(x) + " Volt " + str(16 + xx) + " : " + str(self.byd_volt_cell[x][16 + xx]))

        return byd_ok

    def decode_7(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_7'.

        self.log_debug("decode_7 (" + str(x) + ") : " + data.hex())

        if len(data) != MESSAGE_7_L:
          self.log_info("MESSAGE_7 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_7_L) + ")")
          return byd_error
        
        # starting with byte 5, ending 101, voltage for cell 81 to 128
        for xx in range(0,48):  # 0..47, Cell voltage 80-127
          self.byd_volt_cell[x][80 + xx] = self.buf2int16SI(data,5 + (xx * 2)) / 1000.0
        
        # starting with byte 103, ending 132, temp for cell 1 to 30
        for xx in range(0,30):  # 0..29
          self.byd_temp_cell[x][xx] = data[103 + xx]

#        for xx in range(0,48):
#          self.log_debug("Turm " + str(x) + " Volt " + str(80 + xx) + " : " + str(self.byd_volt_cell[x][80 + xx]))
#        for xx in range(0,30):
#          self.log_debug("Turm " + str(x) + " Temp " + str(xx) + " : " + str(self.byd_temp_cell[x][xx]))
        
        return byd_ok

    def decode_8(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_8'.

        self.log_debug("decode_8 (" + str(x) + ") : " + data.hex())

        if len(data) != MESSAGE_8_L:
          self.log_info("MESSAGE_8 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_8_L) + ")")
          return byd_error
        
        for xx in range(0,34):  # 0..33
          self.byd_temp_cell[x][30 + xx] = data[5 + xx]
        
#        for xx in range(0,34):
#          self.log_debug("Turm " + str(x) + " Temp " + str(30 + xx) + " : " + str(self.byd_temp_cell[x][30 + xx]))

        return byd_ok

    def decode_12(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_12' fuer den Turm 'x'.

        self.log_debug("decode_12 (" + str(x) + ") : " + data.hex())

        if len(data) != MESSAGE_12_L:
          self.log_info("MESSAGE_12 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_12_L) + ")")
          return byd_error
        
        # Balancing-Flags. Es folgen 8x 16-bit-Worte (MSB,LSB!) = 16 Byte => 0..127 Bits
        i = 127
        nnn = self.byd_diag_balance_number[x]
        for xx in range(17,33):  # 17..32
          if (xx % 2) == 1:
            a = data[xx+1]  # LSB, Bit 0-7
          else:
            a = data[xx-1]  # MSB, Bit 8-15
#          self.log_debug("Balancing i=" + str(i) + " d=" + str(a))
          for yy in range(0,8):  # 0..7
            if i <= byd_cells_max:
              if (int(a) & 1) == 1:
                self.byd_balance_cell[x][i] = 1
                nnn = nnn + 1
              else:
                self.byd_balance_cell[x][i] = 0
            a = a / 2
            i = i + 1
        self.byd_diag_balance_number[x] = nnn
        
        # starting with byte 101, ending with 116, Cell voltage 129-144
        for xx in range(0,16):  # 0..15, Cell voltage 128-143
          self.byd_volt_cell[x][128 + xx] = self.buf2int16SI(data,101 + (xx * 2)) / 1000.0

        return byd_ok

    def decode_13(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_13'.

        self.log_debug("decode_13 (" + str(x) + ") : " + data.hex())
        
        if len(data) != MESSAGE_13_L:
          self.log_info("MESSAGE_13 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_13_L) + ")")
          return byd_error
        
        # The first round measured up to 128 cells, request[12] then get another 16
        # With 5 HVS Modules (max for HVS), only 16 cells are remaining

        # starting with byte 5, ending with 21, Cell voltage 145-161
        for xx in range(0,16):  # 0..15, Cell voltage 144-160
          self.byd_volt_cell[x][144 + xx] = self.buf2int16SI(data,5 + (xx * 2)) / 1000.0

        return byd_ok

    def decode_14(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_14'.

        self.log_debug("decode_14 (" + str(x) + ") : " + data.hex())

        if len(data) != MESSAGE_14_L:
          self.log_info("MESSAGE_14 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_14_L) + ")")
          return byd_error
        
        return byd_ok

    def decode_15(self,data,x):
        # Decodieren der Nachricht auf Befehl 'MESSAGE_15'.

        self.log_debug("decode_15 (" + str(x) + ") : " + data.hex())

        if len(data) != MESSAGE_15_L:
          self.log_info("MESSAGE_15 answer length wrong ! (" + str(len(data)) + "/" + str(MESSAGE_15_L) + ")")
          return byd_error
        
        return byd_ok
        
    def decode_nop(self,data,x,lenx):
#        self.log_debug("decode_nop (" + str(x) + ") : " + data.hex())

        if len(data) != lenx:
          self.log_info("MESSAGE nop answer length wrong ! (" + str(len(data)) + "/" + str(lenx) + ")")
          return byd_error
        
        return byd_ok
        
    def module_update(self,xx):
        # Aktualisiert die Daten zu den Modulen im Turm 'xx'.

        self.byd_diag_module[xx].clear()
        
        for i in range(0,self.byd_modules):  # 0.. byd_modules-1
          f = True
          vx = 0
          for j in range(i * self.byd_volt_n,(i + 1) * self.byd_volt_n):  # Durchlaufe die Spannungswerte von Modul 'i'
            vv = self.byd_volt_cell[xx][j]
            if f == True:
              vmin = vv
              vmax = vv
              f = False
            if vv < vmin:
              vmin = vv
            if vv > vmax:
              vmax = vv
            vx = vx + vv
          vava = vx / self.byd_volt_n
          vdif = (vmax - vmin) * 1000.0
          ll = []
          ll.append(vmin)
          ll.append(vmax)
          ll.append(vava)
          ll.append(vdif)
          self.byd_diag_module[xx].append(ll)
          
        if self.byd_modules < byd_module_max:
          for i in range(self.byd_modules,byd_module_max):
            ll = []
            ll.append(0)
            ll.append(0)
            ll.append(0)
            ll.append(0)
            self.byd_diag_module[xx].append(ll)
            
#        for i in range(0,self.byd_modules):  # 0.. byd_modules-1
#          vmin = self.byd_diag_module[xx][i][byd_module_vmin]
#          vmax = self.byd_diag_module[xx][i][byd_module_vmax]
#          vava = self.byd_diag_module[xx][i][byd_module_vava]
#          vdif = self.byd_diag_module[xx][i][byd_module_vdif]
#          self.log_debug("M" + str(i+1) + ": vmin=" + f"{vmin:.3f}" + ": vmax=" + f"{vmax:.3f}" + ": vava=" + f"{vava:.3f}" + ": vdif=" + f"{vdif:.3f}")
        
        return
        
# -----------------------------------------------------------------------
# Decodieren der Log-Daten vom BYD-System
# -----------------------------------------------------------------------

    def read_log_data(self,client):
        # Einlesen/aktualisieren der BMS-Log-Eintraege von allen Tuermen
        
        # Log-Daten aus dem BMU (0) und jedem Turm (1-3) auslesen
        for x in range(0,self.byd_bms_qty + 1):    # 0 ... self.byd_bms_qty
          if x == 0:
            self.log_debug("read_log_data BMU")
          else:
            self.log_debug("read_log_data BMS tower " + str(x))
          
          # Trigger zum Auslesen senden
          bmu = False
          if x == 0:
            m = EVT_MSG_0_0
            bmu = True
          if x == 1:
            m = EVT_MSG_0_1
          elif x == 2:
            m = EVT_MSG_0_2
          elif x == 3:
            m = EVT_MSG_0_3
          res,data = self.send_msg(client,m,byd_timeout_1s)
          if res == byd_error:
            self.log_info("read_log_data message " + m + " failed")
            return byd_error
          if self.decode_log_0(data,x) == byd_error:
            return
          time.sleep(2)
          
          # Register 0x05A1 auslesen -> Log-Daten verfuerbar ?
          res,r = self.read_reg(client,0x05A1,0x01)
          if res == byd_error:
            self.log_info("read_log_data read_reg 0x05A1 failed")
            return byd_error
          if (r % 0x100) == 0:
            self.log_debug("read_log_data no data (" + str(x) + ")")
            continue
            
          # 1.Paket auslesen
          res,data1 = self.send_msg(client,EVT_MSG_1,byd_timeout_1s)
          if res == byd_error:
            self.log_info("read_log_data message " + m + " failed")
            return byd_error
            
          # 2.Paket auslesen
          res,data2 = self.send_msg(client,EVT_MSG_1,byd_timeout_1s)
          if res == byd_error:
            self.log_info("read_log_data message " + m + " failed")
            return byd_error
            
          # 3.Paket auslesen
          res,data3 = self.send_msg(client,EVT_MSG_1,byd_timeout_1s)
          if res == byd_error:
            self.log_info("read_log_data message " + m + " failed")
            return byd_error
            
          # 4.Paket auslesen
          res,data4 = self.send_msg(client,EVT_MSG_1,byd_timeout_1s)
          if res == byd_error:
            self.log_info("read_log_data message " + m + " failed")
            return byd_error
            
          # 5.Paket auslesen
          res,data5 = self.send_msg(client,EVT_MSG_1,byd_timeout_1s)
          if res == byd_error:
            self.log_info("read_log_data message " + m + " failed")
            return byd_error
            
          # Daten extrahieren und speichern
          if self.decode_log_1(bmu,data1,data2,data3,data4,data5,x) == byd_error:
            return
            
        if self.byd_bms_qty == 1:
          self.byd_root.visu.tower2_log.log_html("")
          self.byd_root.visu.tower2_log.log_jsonlist([])
          self.byd_root.visu.tower3_log.log_html("")
          self.byd_root.visu.tower3_log.log_jsonlist([])
        elif self.byd_bms_qty == 2:
          self.byd_root.visu.tower3_log.log_html("")
          self.byd_root.visu.tower3_log.log_jsonlist([])
        
        return byd_ok
        
    def decode_log_0(self,data,x):
        # Decodieren der Nachricht auf Befehl 'EVT_MSG_0_1'.

        self.log_debug("decode_log_0 (" + str(x) + ") : " + data.hex())

        if len(data) != EVT_MSG_0_L:
          self.log_info("EVT_MSG_0_x answer length wrong ! (" + str(len(data)) + "/" + str(EVT_MSG_0_L) + ")")
          return byd_error
        
        return byd_ok

    def decode_log_1(self,bmu,d1,d2,d3,d4,d5,xx):
        # Decodieren Log-Daten.

        self.log_debug("decode_log_1 (" + str(xx) + ")")
        self.log_debug("1) " + d1.hex())
        self.log_debug("2) " + d2.hex())
        self.log_debug("3) " + d3.hex())
        self.log_debug("4) " + d4.hex())
        self.log_debug("5) " + d5.hex())

        if (len(d1) != EVT_MSG_1_L) or (len(d2) != EVT_MSG_1_L) or (len(d3) != EVT_MSG_1_L) or (len(d4) != EVT_MSG_1_L) or (len(d5) != EVT_MSG_1_L):
          self.log_info("EVT_MSG_1 answer length wrong ! (" + str(len(data)) + "/" + str(EVT_MSG_1_L) + ")")
          return byd_error
        
        # Erzeuge eine Liste mit allen Datenbytes - 20 Log-Eintraege befinden sich in dieser Liste
        d = []
        for x in range(1,6):  # 1..5
          for y in range(5,133):  # 5..132
            if x == 1:
              d.append(d1[y])
            elif x == 2:
              d.append(d2[y])
            elif x == 3:
              d.append(d3[y])
            elif x == 4:
              d.append(d4[y])
            elif x == 5:
              d.append(d5[y])

        self.log_debug("=> " + bytearray(d).hex())
        
        # https://smarthomeng.github.io/smarthome/plugins/database/README.html
        
        # Log-Eintraege extrahieren
        for x in range(0,20):  # 0..19
          # Alle Bytes fuer diesen Log-Eintrag
          raw = []
          for y in range(0,30):  # 0..29
            raw.append(d[(x*30)+y])
          # Extrahiere Code, Datum und Uhrzeit
          code = d[(x*30)+0]
          year = d[(x*30)+1]                 # im Log ist Datum/Zeit = UTC
          month = d[(x*30)+2]
          day = d[(x*30)+3]
          hour = d[(x*30)+4]
          minute = d[(x*30)+5]
          second = d[(x*30)+6]
          # Extrahiere die Daten zu diesem Log-Eintrag
          data = []
          for y in range(7,30):  # 7..29
            data.append(d[(x*30)+y])
          # Erzeuge nun den Listeneintrag
          ld = []
          ld.append(year)
          ld.append(month)
          ld.append(day)
          ld.append(hour)
          ld.append(minute)
          ld.append(second)
          ld.append(code)
          ld.append(data)
          ld.append(bytearray(raw).hex())
          ld.append(self.logdata2str(bmu,ld,xx))
          
          self.log_update_list(bmu,ld,xx)
        
        self.log_create_html_json(bmu,xx)
        self.logging_update(bmu,xx)
        
#        self.log_debug_list(bmu,xx)
        
        return byd_ok
        
    def log_update_list(self,bmu,ldx,x):
        # Fuegt den Log-Datensatz 'ldx' in die Log-Liste ein. Der neuste Eintrag steht vorne (Index 0).
        ldd = datetime(2000+ldx[byd_log_year],ldx[byd_log_month],ldx[byd_log_day],ldx[byd_log_hour],ldx[byd_log_minute],ldx[byd_log_second],0)
        if bmu == True:
          ld = self.byd_bmu_log
        else:
          ld = self.byd_diag_bms_log[x]
        if len(ld) == 0:
          ld.append(ldx)
          return
        for i in range(len(ld)):
          dd = ld[i]
          dt = datetime(2000+dd[byd_log_year],dd[byd_log_month],dd[byd_log_day],dd[byd_log_hour],dd[byd_log_minute],dd[byd_log_second],0)
          if (ldd == dt) and (ldx[byd_log_codex] == dd[byd_log_codex]) and (set(dd[byd_log_data]) == set(ldx[byd_log_data])):
            # Eintrag ist schon vorhanden
#            self.log_debug("i=" + str(i) + " -> schon vorhanden " + ldd.strftime("%d.%m.%Y, %H:%M:%S") + " - " + dt.strftime("%d.%m.%Y, %H:%M:%S"))
            return
          elif dt < ldd:
            # Index 'i' zeigt auf das Element vor dem wir das neue Element einfuegen.
            ld.insert(i,ldx)
#            self.log_debug("i=" + str(i) + " -> insert " + ldd.strftime("%d.%m.%Y, %H:%M:%S") + " - " + dt.strftime("%d.%m.%Y, %H:%M:%S"))
            return
        # Das Element 'ldx' ist aelter als alle bisherigen Elemente.
        ld.append(ldx)
        return
          
    def logcode2str(self,code):
        # Gibt den Text zum Logcode 'code' zurueck.
        for i in range(len(byd_log_code)):
          if code == byd_log_code[i][0]:
            return byd_log_code[i][1]
        return "??"
        
    def logdata2str(self,bmu,ld,xx):
        # Erzeugt aus 'data' in 'ld' einen lesbaren Text (aehnlich Be_Connect).
        
        data = ld[byd_log_data]
        s1 = ""
        unknown = False
        if ld[byd_log_codex] == 0:                                                                 # Power ON (0)
          if bmu == True:
            if data[0] == 0:
              s1 = s1 + "Bootloader" + byd_log_str_sep
            else:
              s1 = s1 + "??" + byd_log_str_sep
            if data[1] == 0:
              s1 = s1 + "Running section: A" + byd_log_str_sep
            elif data[1] == 1:
              s1 = s1 + "Running section: B" + byd_log_str_sep
            else:
              s1 = s1 + "??" + byd_log_str_sep
            s2 = f"{data[2]:d}" + "." + f"{data[3]:d}"
            s1 = s1 + "Current Version:V" + s2 + byd_log_str_sep
          else:
            if data[0] == 0:
              s1 = s1 + "Bootloader" + byd_log_str_sep
            else:
              s1 = s1 + "??" + byd_log_str_sep
            if data[2] == 0:
              s1 = s1 + "Running section: A" + byd_log_str_sep
            elif data[2] == 1:
              s1 = s1 + "Running section: B" + byd_log_str_sep
            else:
              s1 = s1 + "??" + byd_log_str_sep
            s2 = f"{data[3]:d}" + "." + f"{data[4]:d}"
            s1 = s1 + "FW version:V" + s2 + byd_log_str_sep
          
        elif ld[byd_log_codex] == 1:                                                                 # Power OFF (1)
          if bmu == True:
            if data[0] == 0:
              s1 = s1 + "??" + byd_log_str_sep
            elif data[0] == 1:
              s1 = s1 + "Switch off by pressing LED button." + byd_log_str_sep
            else:
              s1 = s1 + "??" + byd_log_str_sep
          else:
            if data[1] < len(byd_log_bms_poweroff):
              s1 = s1 + byd_log_bms_poweroff[data[1]] + byd_log_str_sep
            else:
              s1 = s1 + byd_log_bms_poweroff[len(byd_log_bms_poweroff)-1] + byd_log_str_sep
            if data[2] == 0:
              s1 = s1 + "Running section: A" + byd_log_str_sep
            elif data[2] == 1:
              s1 = s1 + "Running section: B" + byd_log_str_sep
            else:
              s1 = s1 + "??" + byd_log_str_sep
            s2 = f"{data[3]:d}" + "." + f"{data[4]:d}"
            s1 = s1 + "FW version:V" + s2 + byd_log_str_sep
          
        elif ld[byd_log_codex] == 2:                                                               # Events record (2)
          if bmu == True:
            if data[0] == 0:
              s1 = s1 + "disappear" + byd_log_str_sep
            else:
              s1 = s1 + "appear" + byd_log_str_sep
            if data[1] < len(byd_log_bmu_errors):
              s2 = byd_log_bmu_errors[data[1]]
              if len(s2) > 0:
                s1 = s1 + s2 + byd_log_str_sep
            else:
              s1 = s1 + byd_log_bmu_errors[len(byd_log_bmu_errors)-1] + byd_log_str_sep
            x = int(data[2] * 0x100 + data[3])
            if x == 0:
              s1 = s1 + "No warning" + byd_log_str_sep
            else:
              s2 = ""
              for i in range(0,16):  # 0..15
                if (int(x) % 2) == 1:
                  if len(s2) > 0:
                    s2 = s2 + ";"
                  s2 = s2 + byd_log_bmu_warnings[i]
                x = int(x / 2)
              s1 = s1 + s2 + byd_log_str_sep
            x = self.buf2int16US(data,4)
            s1 = s1 + "Cell_Max._V:" + f"{x:d}" + "mV" + byd_log_str_sep
            x = self.buf2int16US(data,6)
            s1 = s1 + "Cell_Min._V:" + f"{x:d}" + "mV" + byd_log_str_sep
            x = data[8]
            s1 = s1 + "Battery_Temp_Max:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            x = data[9]
            s1 = s1 + "Battery_Temp_Min:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            x = self.buf2int16US(data,10)  / 10.0
            s1 = s1 + "Battery Total Voltage:" + f"{x:.1f}" + "V" + byd_log_str_sep
            x = data[12]
            s1 = s1 + "SOC:" + f"{x:d}" + "%" + byd_log_str_sep
            x = data[13]
            s1 = s1 + "SOH:" + f"{x:d}" + "%" + byd_log_str_sep
          else:
            s1 = self.logdatabms2str(ld,False) 

        elif ld[byd_log_codex] == 3:                                                               # Timing Record (3)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False)
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 4:                                                               # Start Charging(4)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 5:                                                               # Stop Charging(5)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 6:                                                               # Start DisCharging (6)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 7:                                                               # Stop DisCharging (7)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 8:                                                               # SOC calibration rough (8)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 9:                                                               # SOC calibration fine (8)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 10:                                                              # SOC calibration Stop (10)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 13:                                                              # Receive PreCharge Command (13)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 14:                                                              # PreCharge Successful (14)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 16:                                                              # Start end SOC calibration (16)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 17:                                                              # Start Balancing (17)
          if bmu == False:
            s2 = ""
            nn = 0
            ci = 0
            for i in range(0,20):  # 0..19
              x = int(data[i])
              for ii in range(0,8):  # 0..7
                if (int(x) % 2) == 1:
                  if len(s2) > 0:
                    s2 = s2 + ";"
                  s2 = s2 + str(ci)
                  nn = nn + 1
                x = int(x / 2)
                ci = ci + 1
            if len(s2) > 0:
              s1 = s1 + "Balancing Cells:#=" + str(nn) + "[" + s2 + "]" + byd_log_str_sep
            x = self.buf2int16USx(data,21)
            s1 = s1 + "Cell_Min_V:" + f"{x:d}" + "mV" + byd_log_str_sep
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 18:                                                              # Stop Balancing (18)
          if bmu == False:
            x = self.buf2int16USx(data,21)
            s1 = s1 + "Cell_Min_V:" + f"{x:d}" + "mV" + byd_log_str_sep
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 19:                                                              # Address Registered (19)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 20:                                                              # System Functional Safety Fault (20)
          if bmu == False:
            s1 = self.logdatabms2str(ld,False) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 21:                                                              # Events additional info (21)
          if bmu == False:
            s1 = self.logdatabms2str(ld,True) 
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
        
        elif ld[byd_log_codex] == 32:                                                              # System status changed (32)
          if bmu == True:
            if data[1] < len(byd_log_status):
              s1 = s1 + byd_log_status[data[1]] + " => "
            else:
              s1 = s1 + byd_log_status[len(byd_log_status)-1] + " => "
            if data[0] < len(byd_log_status):
              s1 = s1 + byd_log_status[data[0]]
            else:
              s1 = s1 + byd_log_status[len(byd_log_status)-1]
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True

        elif ld[byd_log_codex] == 34:                                                              # BMS update start (34)
          if bmu == True:
            s1 = s1 + "FW Version:V" + f"{data[1]:d}" + "." + f"{data[2]:d}" + byd_log_str_sep
            s1 = s1 + "MCU Type:" + f"{data[4]:d}" + byd_log_str_sep
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True

        elif ld[byd_log_codex] == 35:                                                              # BMS update start (35)
          if bmu == True:
            s1 = s1 + "FW Version:V" + f"{data[1]:d}" + "." + f"{data[2]:d}" + byd_log_str_sep
            s1 = s1 + "MCU Type:" + f"{data[4]:d}" + byd_log_str_sep
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True

        elif ld[byd_log_codex] == 36:                                                              # Functional Safety Info (36)
          if bmu == True:
            x = data[0] * 0x01000000 + data[1] * 0x00010000 + data[2] * 0x00000100 + data[3]
            s1 = s1 + "Running Time:" + f"{x:d}" + "s" + byd_log_str_sep
            x = data[4]
            s1 = s1 + "BMU detected Cells Qty:" + f"{x:d}" + byd_log_str_sep
            x = data[5]
            s1 = s1 + "BMU detected Temp. Qty:" + f"{x:d}" + byd_log_str_sep
            x = self.buf2int16US(data,6)
            s1 = s1 + "BMU detected Cell_V_Max:" + f"{x:d}" + "mV" + byd_log_str_sep
            x = self.buf2int16US(data,8)
            s1 = s1 + "BMU detected Cell_V_Min:" + f"{x:d}" + "mV" + byd_log_str_sep
            x = data[10]
            s1 = s1 + "BMU detected Temp_Max:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            x = data[11]
            s1 = s1 + "BMU detected Temp_Min:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            x = self.buf2int16US(data,12)  / 10.0
            s1 = s1 + "BMU detected Current:" + f"{x:.1f}" + "A" + byd_log_str_sep
            x = self.buf2int16US(data,14)  / 10.0
            s1 = s1 + "BMU detected Output_V:" + f"{x:.1f}" + "V" + byd_log_str_sep
            x = self.buf2int16US(data,16)  / 10.0
            s1 = s1 + "BMU detected All Cells Accum_V:" + f"{x:.1f}" + "V" + byd_log_str_sep
            x = data[18]
            s1 = s1 + "BMS Address:" + f"{x:d}" + byd_log_str_sep
            if data[19] < len(byd_module_type):
              s1 = s1 + "Module type:" + byd_module_type[data[19]] + byd_log_str_sep
            else:
              s1 = s1 + "Module type:" + byd_module_type[len(byd_module_type)-1] + byd_log_str_sep
            x = data[20]
            s1 = s1 + "Module Number:" + f"{x:d}" + byd_log_str_sep
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
          
        elif ld[byd_log_codex] == 37:                                                              # No Defined (37)
          if bmu == True:
            s1 = s1 + "not defined - " + bytearray(ld[byd_log_data]).hex()
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
          
        elif ld[byd_log_codex] == 38:                                                              # SOP Info
          if bmu == True:
            x = self.buf2int16US(data,0)  / 10.0
            s1 = s1 + "Charge Max. Current:" + f"{x:.1f}" + "A" + byd_log_str_sep
            x = self.buf2int16US(data,2)  / 10.0
            s1 = s1 + "Discharge Max. Current:" + f"{x:.1f}" + "A" + byd_log_str_sep
            x = self.buf2int16US(data,4)  / 10.0
            s1 = s1 + "Charge Max. Voltage:" + f"{x:.1f}" + "V" + byd_log_str_sep
            x = self.buf2int16US(data,6)  / 10.0
            s1 = s1 + "Discharge Min. Voltage:" + f"{x:.1f}" + "V" + byd_log_str_sep
            if data[8] < len(byd_log_status):
              s1 = s1 + byd_log_status[data[8]] + byd_log_str_sep
            else:
              s1 = s1 + byd_log_status[len(byd_log_status)-1] + byd_log_str_sep
            x = data[9]
            s1 = s1 + "Battery Temperature:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            s1 = s1 + self.get_inverter_name(self.byd_batt_str,data[10])  + byd_log_str_sep
            x = data[11]
            s1 = s1 + "BMS Qty:" + f"{x:d}" + byd_log_str_sep
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True

        elif ld[byd_log_codex] == 40:                                                              # BMS Firmware list (40)
          if bmu == True:
            x = data[0]
            s1 = s1 + "Firmware Num:" + f"{x:d}" + byd_log_str_sep
            s1 = s1 + "FW Version:V" + f"{data[1]:d}" + "." + f"{data[2]:d}" + byd_log_str_sep
            x = data[3]
            s1 = s1 + "Firmware Num:" + f"{x:d}" + byd_log_str_sep
            s1 = s1 + "FW Version:V" + f"{data[4]:d}" + "." + f"{data[5]:d}" + byd_log_str_sep
            x = data[6]
            if x != 0xFF:
              s1 = s1 + "Firmware Num:" + f"{x:d}" + byd_log_str_sep
              s1 = s1 + "FW Version:V" + f"{data[7]:d}" + "." + f"{data[8]:d}" + byd_log_str_sep
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
          
        elif ld[byd_log_codex] == 41:                                                              # No Defined (41)
          if bmu == True:
            s1 = s1 + "not defined - " + bytearray(ld[byd_log_data]).hex()
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True

        elif ld[byd_log_codex] == 101:                                                             # Firmware Start to Update (101)
          if bmu == True:
            x = data[0]
            if x == 0:
              s1 = s1 + "BMS A Updating" + byd_log_str_sep
            else:
              s1 = s1 + "BMS B Updating" + byd_log_str_sep
            s1 = s1 + "Version:V" + f"{data[1]:d}" + "." + f"{data[2]:d}" + byd_log_str_sep
          else:
            x = data[0]
            if x == 0:
              s1 = s1 + "Target Area:A" + byd_log_str_sep
            else:
              s1 = s1 + "Target Area:B" + byd_log_str_sep
            s1 = s1 + "Before Update:V" + f"{data[2]:d}" + "." + f"{data[1]:d}" + byd_log_str_sep
            s1 = s1 + "After Update:V" + f"{data[4]:d}" + "." + f"{data[3]:d}" + byd_log_str_sep

        elif ld[byd_log_codex] == 102:                                                             # Firmware Update Successful (102)
          if bmu == True:
            x = data[0]
            if x == 0:
              s1 = s1 + "BMS A Update Finish" + byd_log_str_sep
            else:
              s1 = s1 + "BMS B Update Finish" + byd_log_str_sep
            s1 = s1 + "Version:V" + f"{data[1]:d}" + "." + f"{data[2]:d}" + byd_log_str_sep
          else:
            x = data[0]
            if x == 0:
              s1 = s1 + "Target Area:A" + byd_log_str_sep
            else:
              s1 = s1 + "Target Area:B" + byd_log_str_sep
            s1 = s1 + "Before Update:V" + f"{data[2]:d}" + "." + f"{data[1]:d}" + byd_log_str_sep
            s1 = s1 + "After Update:V" + f"{data[4]:d}" + "." + f"{data[3]:d}" + byd_log_str_sep

        elif ld[byd_log_codex] == 105:                                                             # Parameters table Update (105)
          if bmu == True:
            if (data[0] == 0) or (data[0] == 1) or (data[0] == 2):
              s1 = s1 + "BMU Parameters table Update" + byd_log_str_sep
            else:
              s1 = s1 + "??" + byd_log_str_sep
            s2 = f"{data[1]:d}" + "." + f"{data[2]:d}"
            s1 = s1 + "Parameters table：V" + s2 + byd_log_str_sep
          else:
            x = self.buf2int16USx(data,0)
            y = self.buf2int16USx(data,2)
            s1 = s1 + "Threshold table version:V" + f"{x:d}" + "." + f"{y:d}" + byd_log_str_sep
          
        elif ld[byd_log_codex] == 106:                                                             # SN Code was Changed (106)
          if bmu == True:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
          else:
            s1 = s1 + "serial number was changed" + byd_log_str_sep
          
        elif ld[byd_log_codex] == 111:                                                             # DateTime Calibration (111)
          if bmu == True:
            if data[0] == 0:
              s1 = s1 + "Calibrated by Upper computer" + byd_log_str_sep
            elif data[0] == 1:
              s1 = s1 + "Calibrated by Inverter" + byd_log_str_sep
            elif data[0] == 2:
              s1 = s1 + "Calibrated by Internet" + byd_log_str_sep
            else:
              s1 = s1 + "??" + byd_log_str_sep
          else:
            dtl = self.log_datetime_2_local(ld[byd_log_year],ld[byd_log_month],ld[byd_log_day],ld[byd_log_hour],ld[byd_log_minute],ld[byd_log_second],0)
            dtc = self.log_datetime_2_local(data[0],data[1],data[2],data[3],data[4],data[5],0)
            dtx = dtl - dtc
            x = dtx.total_seconds()
#            self.log_debug("x=" + f"{x:.3f}" + " seconds=" + f"{dtx.seconds:.3f}" + " us=" + f"{dtx.microseconds:.1f}" + " - " + dtl.strftime("%d.%m.%Y %H:%M:%S") + " - " + dtc.strftime("%d.%m.%Y %H:%M:%S"))
            s1 = s1 + "New Time:" + dtc.strftime("%d.%m.%Y %H:%M:%S") + " Delta:" + f"{x:.1f}" + "s" + byd_log_str_sep

        elif ld[byd_log_codex] == 118:                                                             # System timing log (118)
          if bmu == True:
            if data[0] < len(byd_log_status):
              s1 = s1 + "System Status:" + byd_log_status[data[0]] + byd_log_str_sep
            else:
              s1 = s1 + "System Status:" + byd_log_status[len(byd_log_status)-1] + byd_log_str_sep
            x = data[1]
            s1 = s1 + "Environment_Temp_Min:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            x = data[2]
            s1 = s1 + "Environment_Temp_Max:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            x = data[3]
            s1 = s1 + "SOC:" + f"{x:.0f}" + "%" + byd_log_str_sep
            x = data[4]
            s1 = s1 + "SOH:" + f"{x:.0f}" + "%" + byd_log_str_sep
            x = self.buf2int16US(data,6)  / 10.0
            s1 = s1 + "Battery Total Voltage:" + f"{x:.1f}" + "V" + byd_log_str_sep
            x = self.buf2int16US(data,8)
            s1 = s1 + "Cell_HV:" + f"{x:d}" + "mV" + byd_log_str_sep
            x = self.buf2int16US(data,10)
            s1 = s1 + "Cell_LV:" + f"{x:d}" + "mV" + byd_log_str_sep
            x = data[5]
            s1 = s1 + "Battery Current_Temp:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            x = data[13]
            s1 = s1 + "Battery_Temp_Max:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
            x = data[15]
            s1 = s1 + "Battery_Temp_Min:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
          else:
            s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
            unknown = True
          
        else:
          s1 = "not implemented yet (" + bytearray(ld[byd_log_data]).hex() + ")"
          unknown = True
          
        if unknown == True:
          # Wir haben einen Log-Eintrag gefunden, den wir noch nicht decodieren
          s1x = "logdata2str "
          if bmu == True:
            s1x = s1x + "BMU "
          else:
            s1x = s1x + "BMS Tower " + str(xx)
          s1x = s1x + " : code " + str(ld[byd_log_codex]) + " (" + self.logcode2str(ld[byd_log_codex]) + ") not implemented yet"
          s1x = s1x + " (" + f"{ld[byd_log_day]:02d}" + "." + f"{ld[byd_log_month]:02d}" + "." + f"{2000+ld[byd_log_year]:4d}"
          s1x = s1x + " " + f"{ld[byd_log_hour]:2d}" + ":" + f"{ld[byd_log_minute]:02d}" + ":" + f"{ld[byd_log_second]:02d}" + ")"
          s2 = "Raw Data: " + ld[byd_log_raw]
          s3 = "Data: " + bytearray(ld[byd_log_data]).hex()
          self.logging_special(s1x,s2,s3)
    
        return s1
        
    def logdatabms2str(self,ld,cnr):
        # Erzeugt den String fuer den Standard-BMS-Log-Eintrag.
        # ld = Log-Eintrag
        # cnr = True  -> Byte 17-21 Zellennummern
        #       False -> Byte 17-22 normale Bedeutung
        co = ld[byd_log_codex]
        data = ld[byd_log_data]
        s1 = ""
        # Warnungen (3x16Bit)
        y1 = int(data[1] * 0x100 + data[0])
        y2 = int(data[3] * 0x100 + data[2])
        y3 = int(data[5] * 0x100 + data[4])
        y = y1 | y2 | y3                      # Bitweise Oder
        if y > 0:
          s2 = "Warning:"
          for i in range(0,16):  # 0..15
            if (int(y) % 2) == 1:
              if len(s2) > 0:
                s2 = s2 + ";"
              s2 = s2 + byd_log_bms_warnings[i]
            y = int(y / 2)
          s1 = s1 + s2 + byd_log_str_sep
        else:
          s1 = s1 + "No Warning" + byd_log_str_sep
        # Fehler
        y = int(data[7] * 0x100 + data[6])
        if y > 0:
          s2 = "Fault:"
          for i in range(0,16):  # 0..15
            if (int(y) % 2) == 1:
              if len(s2) > 0:
                s2 = s2 + ";"
              s2 = s2 + byd_log_bms_failures[i]
            y = int(y / 2)
          s1 = s1 + s2 + byd_log_str_sep
        # Status
        y = int(data[8])
        if y > 0:
          s2 = ""
          for i in range(0,8):  # 0..7
            if (int(y) % 2) == 1:
              if len(s2) > 0:
                s2 = s2 + ";"
              s2 = s2 + byd_log_bms_switch_status_on[i]
            else:
              if i == 3:
                if len(s2) > 0:
                  s2 = s2 + ";"
                s2 = s2 + byd_log_bms_switch_status_off[i]
            y = int(y / 2)
          s1 = s1 + s2 + byd_log_str_sep
        x = data[9]
        if co == 9:
          # Battery Idling
          s1 = s1 + "Battery Idling:" + f"{x:d}" + "%" + byd_log_str_sep
        elif co == 20:
          # BMU serial port
          s1 = s1 + "BMU serial port:V" + f"{x:d}" + byd_log_str_sep
        else:
          # SOC
          s1 = s1 + "SOC:" + f"{x:d}" + "%" + byd_log_str_sep
        x = data[10]
        if co == 9:
          # SOC
          s1 = s1 + "Target SOC:" + f"{x:d}" + "%" + byd_log_str_sep
        elif co == 20:
          # BMS serial port
          s1 = s1 + "BMS serial port:V" + f"{x:d}" + byd_log_str_sep
        else:
          # SOH
          s1 = s1 + "SOH:" + f"{x:d}" + "%" + byd_log_str_sep
        # Spannung Batterie
        x = self.buf2int16USx(data,11)  / 10.0
        s1 = s1 + "Bat_V:" + f"{x:.1f}" + "V" + byd_log_str_sep
        # Spannung Ausgang
        x = self.buf2int16USx(data,13)  / 10.0
        s1 = s1 + "Output_V:" + f"{x:.1f}" + "V" + byd_log_str_sep
        # Strom
        x = self.buf2int16SIx(data,15)  / 10.0
        s1 = s1 + "Current:" + f"{x:.1f}" + "A" + byd_log_str_sep
        # Zellenspannung max
        if cnr == False:
          x = self.buf2int16USx(data,17)
          s1 = s1 + "Cell_Max_V:" + f"{x:d}" + "mV" + byd_log_str_sep
        else:
          x = data[17]
          s1 = s1 + "Cell_Max_V:No" + f"{x:d}" + byd_log_str_sep
        # Zellenspannung min
        if cnr == False:
          x = self.buf2int16USx(data,19)
          s1 = s1 + "Cell_Min_V:" + f"{x:d}" + "mV" + byd_log_str_sep
        else:
          x = data[18]
          s1 = s1 + "Cell_Min_V:No" + f"{x:d}" + byd_log_str_sep
        # Temperatur max
        if cnr == False:
          x = data[21]
          s1 = s1 + "Cell_Max_T:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
        else:
          x = data[19]
          s1 = s1 + "Cell_Max_T:No" + f"{x:d}" + byd_log_str_sep
        # Temperatur min
        if cnr == False:
          x = data[22]
          s1 = s1 + "Cell_Min_T:" + f"{x:d}" + byd_log_degree + byd_log_str_sep
        else:
          x = data[20]
          s1 = s1 + "Cell_Min_T:No" + f"{x:d}" + byd_log_str_sep
        
        return s1
        
    def log_create_html_json(self,bmu,x):
        # Erstellt fuer eine Einheit die HTML-Tabelle fuer die Anzeige in smartVISU.
        
        # Beispiel einer JSON-Message fuer '' in smartVISU:
        # myNewMessage = {"id":6498501,"title":"Geben Sie 4 g Chlor hinzu","message":"Ich empfehle Ihnen, Chlor zuzusetzen, um eine gute Desinfektion Ihres Wassers zu gew\u00e4hrleisten.","created_at":"2022-01-23T14:30:57+0000","updated_at":"2022-01-23T14:30:57+0000","status":"waiting","deadline":"2 022-01-29T00:00:00+0000"}

        if bmu == True:
          ld = self.byd_bmu_log
        else:
          ld = self.byd_diag_bms_log[x]
        line_string = ""
        json_list = []
        for i in range(len(ld)):  # 0..len(ld)-1
          dd = ld[i]
          dt = self.log_datetime_2_local(dd[byd_log_year],dd[byd_log_month],dd[byd_log_day],dd[byd_log_hour],dd[byd_log_minute],dd[byd_log_second],0)
          # HTML
          line_string = line_string + '<tr>'
          line_string = line_string + '<td align=right valign=top>' + dt.strftime("%d.%m.%Y") + '</td>'
          line_string = line_string + '<td align=right valign=top>' + dt.strftime("%H:%M:%S") + '</td>'
          line_string = line_string + '<td valign=top>' + self.logcode2str(dd[byd_log_codex]) + ' (' + f"{dd[byd_log_codex]:d}" + ')' + '</td>'
          line_string = line_string + '<td valign=top>' + dd[byd_log_str] + '</td>'
          line_string = line_string + '</tr>'
          # JSON
          jd = {"id":str(i),"title":self.logcode2str(dd[byd_log_codex]) + " (" + f"{dd[byd_log_codex]:d}" + ")",
                "content":dd[byd_log_str],"level":"info","date":dt.strftime("%d.%m.%Y %H:%M:%S")}
          json_list.append(jd)
          if i == byd_log_max_rows:
            break
        html_string = '<table cellpadding="2" border="1" style="border-collapse:collapse">' + line_string + '</table>'
        
        if bmu == True:
          old = self.byd_root.visu.bmu_log.log_html()
          if html_string != old:
            self.byd_root.visu.bmu_log.log_html(html_string)
          self.byd_bmu_log_html = html_string
          old = self.byd_root.visu.bmu_log.log_jsonlist()
          if json_list != old:
            self.byd_root.visu.bmu_log.log_jsonlist(json_list)
        else:
          self.byd_diag_bms_log_html[x] = html_string
          if x == 1:
            old = self.byd_root.visu.tower1_log.log_html()
            if html_string != old:
              self.byd_root.visu.tower1_log.log_html(html_string)
            old = self.byd_root.visu.tower1_log.log_jsonlist()
            if json_list != old:
              self.byd_root.visu.tower1_log.log_jsonlist(json_list)
          elif x == 2:
            old = self.byd_root.visu.tower2_log.log_html()
            if html_string != old:
              self.byd_root.visu.tower2_log.log_html(html_string)
            old = self.byd_root.visu.tower2_log.log_jsonlist()
            if json_list != old:
              self.byd_root.visu.tower2_log.log_jsonlist(json_list)
          elif x == 3:
            old = self.byd_root.visu.tower3_log.log_html()
            if html_string != old:
              self.byd_root.visu.tower3_log.log_html(html_string)
            old = self.byd_root.visu.tower3_log.log_jsonlist()
            if json_list != old:
              self.byd_root.visu.tower3_log.log_jsonlist(json_list)
        return
               
    def log_debug_list(self,bmu,x):
        # Ausgabe der aktuellen Log-Daten im Debug-Modus.
        if bmu == True:
          ld = self.byd_bmu_log
        else:
          ld = self.byd_diag_bms_log[x]
        for i in range(len(ld)):
          dd = ld[i]
          s1 = "+ " + f"{i:2d}" 
          s1 = s1 + " " + f"{dd[byd_log_year]:2d}" + "." + f"{dd[byd_log_month]:02d}" + "." + f"{dd[byd_log_day]:02d}"
          s1 = s1 + " " + f"{dd[byd_log_hour]:2d}" + ":" + f"{dd[byd_log_minute]:02d}" + ":" + f"{dd[byd_log_second]:02d}"
          s1 = s1 + " d=" + bytearray(dd[byd_log_data]).hex()
          s1 = s1 + " c=" + f"{dd[byd_log_codex]:3d}" + " - " + self.logcode2str(dd[byd_log_codex])
          self.log_debug(s1)

    def log_datetime_2_local(self,y,m,d,h,mi,s,ms):
        dt = datetime(2000+y,m,d,h,mi,s,ms)
        dtx = dt.replace(tzinfo=ZoneInfo('UTC'))      # make aware
        dtxx = dtx.astimezone(ZoneInfo('localtime'))  # convert
        return dtxx
        
# -----------------------------------------------------------------------
# Speichern der Daten in den Items
# -----------------------------------------------------------------------

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
        device.state.charge_total(self.byd_charge_total)
        device.state.discharge_total(self.byd_discharge_total)
        device.state.eta(self.byd_eta)
        
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
        
        self.last_homedata = self.now_str()  # Speichert Zeitpunkt als String
        device.info.last_state(self.last_homedata)

        return
        
    def diagdata_save(self,device):
        # Speichert die Diagnosedaten in der sh-Struktur und erzeugt die Heatmaps.

        self.log_debug("diagdata_save")
        
        self.diagdata_save_one(device.diagnosis.tower1,1)
        if self.byd_bms_qty > 1:
          self.diagdata_save_one(device.diagnosis.tower2,2)
        if self.byd_bms_qty > 2:
          self.diagdata_save_one(device.diagnosis.tower3,3)
    
        self.last_diagdata = self.now_str()  # Speichert Zeitpunkt als String
        device.info.last_diag(self.last_diagdata)
        
        return

    def diagdata_save_one(self,device,x):
        # Speichert alle Daten fuer einen Turm und erzeugt die Heatmaps.
        
        device.soc(self.byd_diag_soc[x])
        device.soh(self.byd_diag_soh[x])
        device.bat_voltag(self.byd_diag_bat_voltag[x])
        device.v_out(self.byd_diag_v_out[x])
        device.current(self.byd_diag_current[x])
        device.volt_diff(self.byd_diag_volt_diff[x])
        device.volt_max.volt(self.byd_diag_volt_max[x])
        device.volt_max.cell(self.byd_diag_volt_max_c[x])
        device.volt_min.volt(self.byd_diag_volt_min[x])
        device.volt_min.cell(self.byd_diag_volt_min_c[x])
        device.temp_max.temp(self.byd_diag_temp_max[x])
        device.temp_max.cell(self.byd_diag_temp_max_c[x])
        device.temp_min.temp(self.byd_diag_temp_min[x])
        device.temp_min.cell(self.byd_diag_temp_min_c[x])
        device.charge_total(self.byd_diag_charge_total[x])
        device.discharge_total(self.byd_diag_discharge_total[x])
        
        self.byd_diag_balance_active[x] = False
        if self.byd_diag_balance_number[x] > 0:
          self.byd_diag_balance_active[x] = True

        device.balancing.active(self.byd_diag_balance_active[x])
        device.balancing.number(self.byd_diag_balance_number[x])
        
        self.save_module_data(x,device.modules)
        
        # Status des Turms = Hex-Wert 'byd_diag_state' (2 Byte)
        device.state.raw(self.byd_diag_state[x])
        if self.byd_diag_state[x] == 0:
          s = "normal"
        else:
          # Fuege alle Bit-Texte in einem String zusammen
          s = ""
          xx = int()
          xx = self.byd_diag_state[x]
          for yy in range(0,16):  # 0..15
            if (int(xx) & 1) == 1:
              if len(s) != 0:
                s = s + ","
              s = s + byd_stat_tower[yy]  # Enum mit den Bit-Texten
              xx = xx / 2
        self.byd_diag_state_str[x] = s
        device.state.str(s)
#        self.log_debug("Status: " + s)
        
        self.diag_plot(x)
        
#        self.log_debug("Turm " + str(x))
#        for xx in range(0,self.byd_cells_n):
#          self.log_debug("Volt " + str(xx+1) + " : " + str(self.byd_volt_cell[x][xx]))
#        for xx in range(0,self.byd_temps_n):
#          self.log_debug("Temp " + str(xx+1) + " : " + str(self.byd_temp_cell[x][xx]))
          
        return
        
    def save_module_data(self,xx,m):
        # Speichert die Daten fuer die Module im Turm 'x' in 'm' ab.
        
        m.m1.v_min(self.byd_diag_module[xx][0][byd_module_vmin])
        m.m1.v_max(self.byd_diag_module[xx][0][byd_module_vmax])
        m.m1.v_av(self.byd_diag_module[xx][0][byd_module_vava])
        m.m1.v_diff(self.byd_diag_module[xx][0][byd_module_vdif])
        
        m.m2.v_min(self.byd_diag_module[xx][1][byd_module_vmin])
        m.m2.v_max(self.byd_diag_module[xx][1][byd_module_vmax])
        m.m2.v_av(self.byd_diag_module[xx][1][byd_module_vava])
        m.m2.v_diff(self.byd_diag_module[xx][1][byd_module_vdif])
        
        m.m3.v_min(self.byd_diag_module[xx][2][byd_module_vmin])
        m.m3.v_max(self.byd_diag_module[xx][2][byd_module_vmax])
        m.m3.v_av(self.byd_diag_module[xx][2][byd_module_vava])
        m.m3.v_diff(self.byd_diag_module[xx][2][byd_module_vdif])
        
        m.m4.v_min(self.byd_diag_module[xx][3][byd_module_vmin])
        m.m4.v_max(self.byd_diag_module[xx][3][byd_module_vmax])
        m.m4.v_av(self.byd_diag_module[xx][3][byd_module_vava])
        m.m4.v_diff(self.byd_diag_module[xx][3][byd_module_vdif])
        
        m.m5.v_min(self.byd_diag_module[xx][4][byd_module_vmin])
        m.m5.v_max(self.byd_diag_module[xx][4][byd_module_vmax])
        m.m5.v_av(self.byd_diag_module[xx][4][byd_module_vava])
        m.m5.v_diff(self.byd_diag_module[xx][4][byd_module_vdif])
        
        m.m6.v_min(self.byd_diag_module[xx][5][byd_module_vmin])
        m.m6.v_max(self.byd_diag_module[xx][5][byd_module_vmax])
        m.m6.v_av(self.byd_diag_module[xx][5][byd_module_vava])
        m.m6.v_diff(self.byd_diag_module[xx][5][byd_module_vdif])
        
        m.m7.v_min(self.byd_diag_module[xx][6][byd_module_vmin])
        m.m7.v_max(self.byd_diag_module[xx][6][byd_module_vmax])
        m.m7.v_av(self.byd_diag_module[xx][6][byd_module_vava])
        m.m7.v_diff(self.byd_diag_module[xx][6][byd_module_vdif])
        
        m.m8.v_min(self.byd_diag_module[xx][7][byd_module_vmin])
        m.m8.v_max(self.byd_diag_module[xx][7][byd_module_vmax])
        m.m8.v_av(self.byd_diag_module[xx][7][byd_module_vava])
        m.m8.v_diff(self.byd_diag_module[xx][7][byd_module_vdif])
        
        return
        
# -----------------------------------------------------------------------
# Generieren der Bilder
# -----------------------------------------------------------------------
        
    def diag_plot(self,x):
        # Erstellt die Plots fuer Turm 'x'.
        
        # Saeulen-Grafik ----------------------------------------------------------------

#        # Simulationsdaten fuer Pruefung des Plots !!!!!!!!!!!!!!!
#        # - Max. Anzahl Module: HVS=2-5, HVM=3-8, HVL=3-8, LVS=1-8
#        old_n = self.byd_volt_n
#        old_m = self.byd_modules
#        old_x = self.byd_cells_n
#        old_v = self.byd_volt_cell
#        old_b = self.byd_balance_cell
#        twr = 1
#        self.byd_volt_n = 8
#        self.byd_modules = 7
#        self.byd_cells_n = self.byd_volt_n * self.byd_modules
#        for xx in range(0,self.byd_cells_n):
#          self.byd_volt_cell[twr][xx] = round(random.uniform(3.08,3.27),2)
#          self.byd_balance_cell[twr][xx] = random.randint(0,1)
        
        # Daten zusammenstellen
        xx = np.arange(self.byd_modules)     # X-Achse -> alle Module
        yy = []
        for ii in range(0,self.byd_volt_n):  # alle Zellen eines Moduls
          zz = []
          for jj in range(0,self.byd_modules):
            v = self.byd_volt_cell[x][(jj*self.byd_volt_n)+ii]
            zz.append(v)
          yy.append(zz)
        # Min/Max bestimmen
        yminl = []
        ymaxl = []
        f = True
        for jj in range(0,self.byd_modules):
          f1 = True
          for ii in range(0,self.byd_volt_n):
            v = self.byd_volt_cell[x][(jj*self.byd_volt_n)+ii]
            if f == True:
              ymin = v
              ymax = v
              f = False
            else:
              if v < ymin:
                ymin = v
              elif v > ymax:
                ymax = v
            if f1 == True:
              ymin1 = v
              ymax1 = v
              ymini = ii
              ymaxi = ii
              f1 = False
            else:
              if v < ymin1:
                ymin1 = v
                ymini = ii
              elif v > ymax1:
                ymax1 = v
                ymaxi = ii
          yminl.append(ymini)
          ymaxl.append(ymaxi)
        # Balancing-Daten extrahieren
        ba = []
        balance_n = 0
        for ii in range(0,self.byd_volt_n):  # alle Zellen eines Moduls
          zz = []
          for jj in range(0,self.byd_modules):
            b = self.byd_balance_cell[x][(jj*self.byd_volt_n)+ii] * ymin * 0.999
            if b > 0:
              balance_n = balance_n + 1
            zz.append(b)
          ba.append(zz)
        nn = []
        # Modulnamen fuer X-Achse
        for jj in range(0,self.byd_modules):
          nn.append("M"+str(jj+1))
        # Daten fuer Titel zusammensetzen
        delta = (ymax - ymin) * 1000.0 
        title_data = " (SOC=" + f"{self.byd_diag_soc[x]:.1f}" + "% min=" + f"{ymin:.3f}" + "V max=" + f"{ymax:.3f}" + "V delta=" + f"{delta:.0f}" + "mV)"
          
        # Berechne bestimmte Parameter fuer die optimale Darstellung
        width = 1.0 / (self.byd_volt_n + 1)
        ddd = width
        y1 = self.round_decimal(ymax,Decimal('0.05'))
        if y1 < ymax:
          y1 = y1 + 0.05
        y0 = self.round_decimal(ymin,Decimal('0.05'))
        if (y1 - y0) < 0.1:
          yyy = (y0 + y1) / 2
          y0 = yyy - 0.05
          y1 = yyy + 0.05
        
        fig,ax = plt.subplots(figsize=(10,4))  # Erzeugt ein Bitmap von 1000x400 Pixel
        
        x1 = -((self.byd_volt_n / 2) * ddd)
        for ii in range(0,self.byd_volt_n):  # alle Zellen eines Moduls
          if (ii % 2) == 0:
            col = '#ff0000'         # 'rot'
          else:
            col = '#ff8c00'         # 'orange'
          b = plt.bar(xx+x1,yy[ii],width,color=col,zorder=3)
          for jj in range(0,self.byd_modules):
            if ii == yminl[jj]:
              b[jj].set_color('#05b4ff')       # 'blau'
            elif ii == ymaxl[jj]:
              b[jj].set_color('#c505ff')       # 'violett'
          if balance_n > 0:
            plt.bar(xx+x1,ba[ii],width,color='#1cfc03',zorder=4)  # 'giftgruen'
          x1 = x1 + ddd
          
        plt.ylim(y0,y1)
        plt.xticks(xx,nn)
        plt.ylabel("Volt [V]")
        plt.grid(axis='y',color='#999999',linestyle='dashed',zorder=0)
        ax.tick_params(axis='x',colors='white')
        ax.tick_params(axis='y',colors='white')
        ax.yaxis.label.set_color('white')
        ax.spines['bottom'].set_color('white')
        ax.spines['top'].set_color('white')
        ax.spines['right'].set_color('white')
        ax.spines['left'].set_color('white')
        ax.set_title("Turm " + str(x) + " - Spannungen [V]" + " (" + self.now_str() + ")" + title_data,size=10,color='white')
        if balance_n > 0:
          n_col = 3
          custom_lines = [Line2D([0], [0],color='#05b4ff',lw=4),
                          Line2D([0], [0],color='#c505ff',lw=4),
                          Line2D([0], [0],color='#1cfc03',lw=4)]
          legend_text = ['Min','Max','Balancing']
        else:
          n_col = 2
          custom_lines = [Line2D([0], [0],color='#05b4ff',lw=4),
                          Line2D([0], [0],color='#c505ff',lw=4)]
          legend_text = ['Min','Max']
        ax.legend(custom_lines,legend_text,fancybox=True,framealpha=0.0,labelcolor='white',fontsize=9,ncol=n_col)
        
        fig.tight_layout()
        if len(self.bpath) != byd_path_empty:
          fig.savefig(self.bpath + byd_fname_volt2 + str(x) + byd_fname_ext,format='png',transparent=True)
          self.log_debug("save " + self.bpath + byd_fname_volt2 + str(x) + byd_fname_ext)
        fig.savefig(self.get_plugin_dir() + byd_webif_img + byd_fname_volt2 + str(x) + byd_fname_ext,format='png',transparent=True)
        self.log_debug("save " + self.get_plugin_dir() + byd_webif_img + byd_fname_volt2 + str(x) + byd_fname_ext)
        plt.close('all')

#        # Simulationsdaten fuer Pruefung des Plots !!!!!!!!!!!!!!!
#        self.byd_volt_n = old_n
#        self.byd_modules = old_m
#        self.byd_cells_n = old_x
#        self.byd_volt_cell = old_v
#        self.byd_balance_cell = old_b
    
        # Heatmap der Spannungen --------------------------------------------------------
        if self.byd_volt_n == byd_no_of_col_7:
          no_of_col = byd_no_of_col_7
        else:
          no_of_col = byd_no_of_col_8
        i = int()
        j = int()
        i = 0
        j = 1
        rows = self.byd_cells_n // no_of_col  # Anzahl Zeilen bestimmen
        d = []
        rt = []
        for r in range(0,rows):  # 0..rows-1
          c = []
          for cc in range(0,no_of_col):  # 0..no_of_col-1
            c.append(self.byd_volt_cell[x][i])
            i = i + 1
          d.append(c)
          rt.append("M" + str(j))
          if ((r + 1) % (self.byd_volt_n // no_of_col)) == 0:
            j = j + 1
        dd = np.array(d)
                  
        fig,ax = plt.subplots(figsize=(10,4))  # Erzeugt ein Bitmap von 1000x400 Pixel
        
        im = ax.imshow(dd)                     # Befehl fuer Heatmap
        cbar = ax.figure.colorbar(im,ax=ax,shrink=0.5)
        cbar.ax.yaxis.set_tick_params(color='white')
        cbar.outline.set_edgecolor('white')
        plt.setp(plt.getp(cbar.ax.axes,'yticklabels'),color='white')
        
        ax.set_aspect(0.25)
        ax.get_xaxis().set_visible(False)
        ax.set_yticks(np.arange(len(rt)),labels=rt)
        
        ax.spines[:].set_visible(False)
        ax.set_xticks(np.arange(dd.shape[1] + 1) - 0.5,minor=True)
        ax.set_yticks(np.arange(dd.shape[0] + 1) - 0.5,minor=True)
        ax.tick_params(which='minor',bottom=False,left=False)
        ax.tick_params(axis='y',colors='white',labelsize=10)
        
        textcolors = ("white","black")
        threshold = im.norm(dd.max()) / 2.0
        kw = dict(horizontalalignment="center",verticalalignment="center",size=9)
        valfmt = matplotlib.ticker.StrMethodFormatter("{x:.3f}")

        # Loop over data dimensions and create text annotations including colored frame around balancing cells.
        k = 0
        for i in range(0,rows):  # 0..rows-1 (Zeilen)
          for j in range(0,no_of_col):  # 0..no_of_col-1 (Spalten)
            kw.update(color=textcolors[int(im.norm(dd[i,j]) > threshold)])
            text = ax.text(j,i,valfmt(dd[i,j],None),**kw)
            if self.byd_balance_cell[x][k] > 0:
              ax.add_patch(patches.Rectangle((-0.5+j,-0.5+i),1,1,edgecolor='red',fill=False,lw=2))
            k = k + 1

        ax.set_title("Turm " + str(x) + " - Spannungen [V]" + " (" + self.now_str() + ")" + title_data,size=10,color='white')
        
        fig.tight_layout()
        if len(self.bpath) != byd_path_empty:
          fig.savefig(self.bpath + byd_fname_volt + str(x) + byd_fname_ext,format='png',transparent=True)
#          self.log_debug("save " + self.bpath + byd_fname_temp + str(x) + byd_fname_ext)
        fig.savefig(self.get_plugin_dir() + byd_webif_img + byd_fname_volt + str(x) + byd_fname_ext,format='png',transparent=True)
#        self.log_debug("save " + self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(x) + byd_fname_ext)
        plt.close('all')
        
        # Heatmap der Temperaturen ------------------------------------------------------
        if self.byd_temps_n == 0:
          return
        if self.byd_temp_n == byd_no_of_col_8:
          no_of_col = byd_no_of_col_8
        else:
          no_of_col = byd_no_of_col_12
        rows = self.byd_temps_n // no_of_col
        i = 0
        j = 1
        d = []
        rt = []
        for r in range(0,rows):
          c = []
          for cc in range(0,no_of_col):
            c.append(self.byd_temp_cell[x][i])
            i = i + 1
          d.append(c)
          rt.append("M" + str(j))
          if ((r + 1) % (self.byd_temp_n // no_of_col)) == 0:
            j = j + 1
        dd = np.array(d)
        cmap = matplotlib.colors.LinearSegmentedColormap.from_list('',['#f5f242','#ffaf38','#fc270f'])
        norm = matplotlib.colors.TwoSlopeNorm(vcenter=dd.min() + (dd.max() - dd.min()) / 2,vmin=dd.min(),vmax=dd.max())
                  
        fig,ax = plt.subplots(figsize=(10,2.5))  # Erzeugt ein Bitmap von 1000x250 Pixel
        
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
        ax.set_yticks(np.arange(dd.shape[0] + 1) - .5,minor=True)
        ax.tick_params(which='minor',bottom=False,left=False)
        ax.tick_params(axis='y',colors='white',labelsize=10)
        
        textcolors = ("black","white")
        threshold = im.norm(dd.max()) / 2.
        kw = dict(horizontalalignment="center",verticalalignment="center",size=9)
        valfmt = matplotlib.ticker.StrMethodFormatter("{x:.0f}")
        
        # Loop over data dimensions and create text annotations.
        for i in range(0,rows):
          for j in range(0,no_of_col):
            kw.update(color=textcolors[int(im.norm(dd[i,j]) > threshold)])
            text = ax.text(j,i,valfmt(dd[i,j], None),**kw)
                           
        ax.set_title("Turm " + str(x) + " - Temperaturen [°C]" + " (" + self.now_str() + ")",size=10,color='white')

        fig.tight_layout()
        if len(self.bpath) != byd_path_empty:
          fig.savefig(self.bpath + byd_fname_temp + str(x) + byd_fname_ext,format='png',transparent=True)
#          self.log_debug("save " + self.bpath + byd_fname_temp + str(x) + byd_fname_ext)
        fig.savefig(self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(x) + byd_fname_ext,
                    format='png',transparent=True)
#        self.log_debug("save " + self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(x) + byd_fname_ext)
        plt.close('all')

        return
        
    def plt_file_del_single(self,fn,dummy):
        # Loescht eine vorhandene Datei 'fn' und erstellt eine leere Datei.
        if os.path.exists(fn) == True:
          os.remove(fn)
        if dummy == True:
          self.create_dummy_png(fn)
        return
        
    def plt_file_del(self):
        # Loescht alle Plot-Dateien
        
        # Spannungs-Plots
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_volt + str(1) + byd_fname_ext,True)
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_volt + str(2) + byd_fname_ext,True)
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_volt + str(3) + byd_fname_ext,True)

        if len(self.bpath) != byd_path_empty:
          self.plt_file_del_single(self.bpath + byd_fname_volt + str(1) + byd_fname_ext,False)
          self.plt_file_del_single(self.bpath + byd_fname_volt + str(2) + byd_fname_ext,False)
          self.plt_file_del_single(self.bpath + byd_fname_volt + str(3) + byd_fname_ext,False)
    
        # Spannungs-Plots
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_volt2 + str(1) + byd_fname_ext,True)
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_volt2 + str(2) + byd_fname_ext,True)
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_volt2 + str(3) + byd_fname_ext,True)

        if len(self.bpath) != byd_path_empty:
          self.plt_file_del_single(self.bpath + byd_fname_volt2 + str(1) + byd_fname_ext,False)
          self.plt_file_del_single(self.bpath + byd_fname_volt2 + str(2) + byd_fname_ext,False)
          self.plt_file_del_single(self.bpath + byd_fname_volt2 + str(3) + byd_fname_ext,False)
    
        # Temperatur-Plots
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(1) + byd_fname_ext,True)
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(2) + byd_fname_ext,True)
        self.plt_file_del_single(self.get_plugin_dir() + byd_webif_img + byd_fname_temp + str(3) + byd_fname_ext,True)

        if len(self.bpath) != byd_path_empty:
          self.plt_file_del_single(self.bpath + byd_fname_temp + str(1) + byd_fname_ext,False)
          self.plt_file_del_single(self.bpath + byd_fname_temp + str(2) + byd_fname_ext,False)
          self.plt_file_del_single(self.bpath + byd_fname_temp + str(3) + byd_fname_ext,False)
    
        return

    def create_dummy_png(self,fn):
        fig,ax = plt.subplots(figsize=(10,0.1))  # Erzeugt ein Bitmap von 1000x10 Pixel
        fig.savefig(fn,format='png',transparent=True)
        plt.close('all')
        return

# -----------------------------------------------------------------------
# Routinen fuer das Logging der Daten
# -----------------------------------------------------------------------

    def create_logdirectory(self,base,log_directory):
        # Erstellt das Verzeichnis 'log_directory' im Log-Verzeichnis von smarthomeNG.
        if log_directory[0] != "/":
          if base[-1] != "/":
            base += "/"
          log_directory = base + "var/log/" + log_directory
        if not os.path.exists(log_directory):
          os.makedirs(log_directory)
        return log_directory
        
    def logging_update(self,bmu,x):
        # Aktualisiert die aktuelle Logdatei.
        # Fuer jeden Tag wird eine neue Log-Datei erstellt.
        
        # Dateiname erstellen und zugehoerige Log-Liste holen
        tn = self.now()
        fn = f"{tn.year-2000:2d}" + f"{tn.month:02d}" + f"{tn.day:02d}" + "_BYD_"
        if bmu == True:
          fn = fn + "BMU"
          ld = self.byd_bmu_log
        else:
          fn = fn + "BMS_Tower_" + str(x)
          ld = self.byd_diag_bms_log[x]
        fn = self.log_dir + "/" + fn + "." + byd_log_extension
#        self.log_debug("logging_update fn=" + fn)
        
         # Wir suchen den aeltesten Eintrag in der Liste 'ld' vom heutigen Tag
        mii = -1
        for mi in range(len(ld)-1,-1,-1):  # len(ld)-1 .. 0
          dd = ld[mi]
          if (2000+dd[byd_log_year] == tn.year) and (dd[byd_log_month] == tn.month) and (dd[byd_log_day] == tn.day):
            mii = mi
            break
        if mii == -1:
          # In der aktuellen Liste gibt es noch keinen Eintrag vom heutigen Datum - wir warten !
          return
        
        if not os.path.exists(fn):
          # Datei existiert noch nicht - erstellen mit Headerzeile
          self.log_debug("logging_update file not exist yet => create (" + fn + ")")
          f = open(fn,"wt",encoding='utf-8')
          s1 = "Date/Time (local)" + byd_log_sep + "Code" + byd_log_sep + "Code Description" + byd_log_sep + "Data" + byd_log_sep + "Data Raw" + byd_log_newline
          sx = []
          sx.append(s1)
          f.writelines(sx)
          f.close()
          if bmu == True:
            self.logging_del_old_files()

        # Datei oeffnen und alle Zeilen einlesen
        fl = []
        with open(fn,"rt",encoding='utf-8') as f:
          fl = f.readlines()
        f.close()
        
        # Wir suchen diesen aeltesten Eintrag 'mii' in der Liste 'ld' in der Logdatei.
        wl = []
        wl.append(fl[0])  # Titelzeile direkt uebernehmen
        s1 = self.logging_create_str(ld[mii])
        if len(fl) > 1:
          for fi in range(1,len(fl)):   # 1..len(fl)-1 - ohne Titelzeile
            # Durchlaufe alle Zeilen, beginnend mit der aeltesten Zeile (oben in der Datei)
            if fl[fi] == s1:
              # Wir haben den Eintrag im Log gefunden - hier brechen wir ab
              break
            else:
              wl.append(fl[fi])
            
        # Nun fuegen wir alle Eintraege aus 'ld' an die Datei hinzu
        nn = 0
        for mi in range(mii,-1,-1):  # mii .. 0
          # Durchlaufe die Eintrage im Speicher, beginnend mit der aeltesten Zeile (am Ende der Liste)
          s1 = self.logging_create_str(ld[mi])
          wl.append(s1)
          nn = nn + 1
          
        if len(fl)-1 == nn:
          # Anzahl Zeilen in der aktuellen Log unveraendert.
          self.log_debug("logging_update rows not changed ! " + str(len(fl)-1) + "/" + str(nn))
          return
            
        # Schreibe die Log-Datei mit den neuen Daten
        f = open(fn,"wt",encoding='utf-8')
        f.writelines(wl)
        f.close()
        
    def logging_create_str(self,dd):
        dt = self.log_datetime_2_local(dd[byd_log_year],dd[byd_log_month],dd[byd_log_day],dd[byd_log_hour],dd[byd_log_minute],dd[byd_log_second],0)
        s1 = dt.strftime("%d.%m.%Y %H:%M:%S") + byd_log_sep + f"{dd[byd_log_codex]:d}" + byd_log_sep + self.logcode2str(dd[byd_log_codex]) + byd_log_sep
        s1 = s1 + dd[byd_log_str] + byd_log_sep + bytearray(dd[byd_log_data]).hex() + byd_log_newline
        return s1
        
    def logging_del_old_files(self):
        # Alte Log-Dateien loeschen.
        if self.log_age == 0:
          return
        tn = self.now()
        files = os.listdir(self.log_dir)
        ts = tn.replace(hour=0,minute=1,second=0)
        tx = ts - timedelta(days=self.log_age)
        tx = tx.replace(tzinfo=None)
#        self.log_debug("ts=" + ts.strftime("%d.%m.%Y %H:%M:%S") + " tx=" + tx.strftime("%d.%m.%Y %H:%M:%S"))
        for i in range(0,len(files)):
          yy = int(files[i][0:2])
          mm = int(files[i][2:4])
          da = int(files[i][4:6])
          dt = datetime(2000+yy,mm,da,0,1,0,0)  # Datum dieser Datei als 'datetime'
          dx = tx - dt
#          self.log_debug("i:" + str(i) + " -> " + files[i] + " / " + " y=" + str(yy) + " m=" + str(mm) + " d=" + str(da) + " - " + dt.strftime("%d.%m.%Y %H:%M:%S") + " dx=" + str(dx.total_seconds()) + " dx=" + str(dx.days))
          if dx.days > 0:
            # Positiv = Datei zu alt, wird geloescht !
            os.remove(self.log_dir + "/" + files[i])
            self.log_info("Log file " + files[i] + " too old -> deleted")

    def logging_special(self,s1,s2,s3):
        # Schreibt die Texte in die Spezial-Log-Datei.
        fn = self.log_dir + "/" + byd_log_special + "." + byd_log_extension
        if not os.path.exists(fn):
          f = open(fn,"wt",encoding='utf-8')
          sx = []
          sx.append("BYD_BAT Plugin - special notes" + byd_log_newline)
          sx.append(byd_log_newline)
          f.writelines(sx)
          f.close()
          
        # Datei oeffnen und alle Zeilen einlesen.
        fl = []
        with open(fn,"rt",encoding='utf-8') as f:
          fl = f.readlines()
        f.close()
        
        # Pruefe, ob dieser neue Eintrag schon im Log vorhanden ist.
        s1 = s1  + byd_log_newline
        s2 = s2  + byd_log_newline
        s3 = s3  + byd_log_newline
        if len(fl) >= 6:
          for i in range(2,len(fl),5):
            if (i+3) > len(fl)-1:
              break
            s1x = fl[i+1]
            s2x = fl[i+2]
            s3x = fl[i+3]
            if (s1 == s1x) and (s2 == s2x) and (s3 == s3x):
              # Eintrag ist schon vorhanden
              self.log_debug("logging_special record exists ! " + s1)
              return
            
        # Neuer Eintrag - an die Datei anfuegen.
        s = []
        tn = self.now()
        s.append(tn.strftime("%d.%m.%Y %H:%M:%S") + byd_log_newline)
        s.append(s1)
        s.append(s2)
        s.append(s3)
        s.append(byd_log_newline)
        f = open(fn,"at",encoding='utf-8')
        f.writelines(s)
        f.close()
        return

    def log_debug(self,s1):
        self.logger.debug(s1)

    def log_info(self,s1):
        self.logger.warning(s1)
        
# -----------------------------------------------------------------------
# Kommunikations-Routinen
# -----------------------------------------------------------------------
        
    def read_reg(self,client,reg,xx):
        # Liest ein Register (MODBUS/RTU) ein.
        msg = "0103" + f"{reg:04x}" + "00" + f"{xx:02x}"
#        self.log_debug("read_reg msg=" + msg)
        msgb = bytes.fromhex(msg)
        crc = self.modbus_crc(msgb)
        ba = crc.to_bytes(2,byteorder='little')
        msg = msg + f"{ba[0]:02x}" + f"{ba[1]:02x}"
#        self.log_debug("read_reg msg=" + msg)

        client.send(bytes.fromhex(msg))
        client.settimeout(byd_timeout_1s)
        
        try:
          data = client.recv(BUFFER_SIZE)
        except:
          self.log_info("read_reg 0x" + f"{reg:04x}" + " failed !")
          return byd_error,0

        v = data[3] * 0x100 + data[4]
#        self.log_debug("read_reg : v=" + f"{v:04x}" + " - " + data.hex())
        return byd_ok,v
        
    def send_msg(self,client,msg,tout):
        # Sendet die Nachricht 'msg' und holt die Antwort.
        # Eingabe : client = Client fuer Senden/Empfangen
        #           msg    = Nachricht zum Senden (String)
        #           tout   = Timeout Warten auf Antwort [s]
        # Ausgabe : ()     = result (byd_ok,byd_error) und data
        client.send(bytes.fromhex(msg))
        client.settimeout(tout)
        try:
          data = client.recv(BUFFER_SIZE)
        except:
          return byd_error,0
        d = []
        for n in range(len(data)-2):  # ohne CRC
          d.append(data[n])
        crc = self.modbus_crc(d)
        crcx = data[len(data)-1] * 0x100 + data[len(data)-2]
        if crc != crcx:
          self.log_info("send_msg recv crc not ok (" + f"{crc:04x}" + "/" + f"{crcx:04x}" + ")")
          return byd_error,0
#        self.log_debug("send_msg crc=" + f"{crc:04x}" + " / " + f"{crcx:04x}" + " len=" + str(len(data)))
        return byd_ok,data
        
    def modbus_crc(self,msg:str) -> int:
        # Bestimmt den CRC-Wert der Nachricht 'msg'.
        crc = 0xFFFF
        for n in range(len(msg)):
          crc ^= msg[n]
          for i in range(8):
            if crc & 1:
              crc >>= 1
              crc ^= 0xA001
            else:
              crc >>= 1
        return crc

# -----------------------------------------------------------------------
# Hilfsroutinen
# -----------------------------------------------------------------------

    def buf2int16SI(self,byteArray,pos):   # signed
        try:
          result = byteArray[pos] * 256 + byteArray[pos + 1]
        except:
          return 0
        if (result > 32768):
            result -= 65536
        return result

    def buf2int16US(self,byteArray,pos):   # unsigned
        try:
          result = byteArray[pos] * 256 + byteArray[pos + 1]
        except:
          return 0
        return result

    def buf2int16SIx(self,byteArray,pos):   # signed
        try:
          result = byteArray[pos+1] * 256 + byteArray[pos]
        except:
          return 0
        if (result > 32768):
            result -= 65536
        return result

    def buf2int16USx(self,byteArray,pos):   # unsigned
        try:
          result = byteArray[pos+1] * 256 + byteArray[pos]
        except:
          return 0
        return result

    def buf2int32SI(self,byteArray,pos):   # signed
#        self.log_debug("buf2int32US 0=" + f"{byteArray[pos]:02x}" + " 1=" + f"{byteArray[pos+1]:02x}" + " 2=" + f"{byteArray[pos+2]:02x}" + " 3=" + f"{byteArray[pos+3]:02x}")
        try:
          result = byteArray[pos+2] * 0x01000000 + byteArray[pos+3] * 0x00010000 + byteArray[pos] * 0x00000100 + byteArray[pos+1]
        except:
          return 0
        if (result > 0x7FFFFFFF):
            result -= 0x100000000
#        self.log_debug("buf2int32US r=" + str(result))
        return result

    def buf2int32US(self,byteArray,pos):   # unsigned
#        self.log_debug("buf2int32US 0=" + f"{byteArray[pos]:02x}" + " 1=" + f"{byteArray[pos+1]:02x}" + " 2=" + f"{byteArray[pos+2]:02x}" + " 3=" + f"{byteArray[pos+3]:02x}")
        try:
          result = byteArray[pos+2] * 0x01000000 + byteArray[pos+3] * 0x00010000 + byteArray[pos] * 0x00000100 + byteArray[pos+1]
        except:
          return 0
#        self.log_debug("buf2int32US r=" + str(result))
        return result

    def now_str(self):
        return self.now().strftime("%d.%m.%Y, %H:%M:%S")
        
    def get_inverter_name(self,batt,type):
        # Bestimmt den Namen des Wechselrichters.
        # Das Mapping wurde Be_Connect (Hauptseite Setup) entnommen.
        if batt == "LVS":                                        # LVS
          if type == 0:
            return byd_inverters[0]                              # Fronius HV
          elif (type == 1) or (type == 2):
            return byd_inverters[1]                              # Goodwe HV/Viessmann HV
          elif type == 3:
            return byd_inverters[2]                              # KOSTAL HV
          elif type == 4:
            return byd_inverters[18]                             # Selectronic LV
          elif type == 5:
            return byd_inverters[3]                              # SMA SBS3.7/5.0/6.0 HV
          elif type == 6:
            return byd_inverters[19]                             # SMA LV
          elif type == 7:
            return byd_inverters[20]                             # Victron LV
          elif type == 8:
            return byd_inverters[30]                             # Suntech LV
          elif type == 9:
            return byd_inverters[4]                              # Sungrow HV
          elif type == 10:
            return byd_inverters[5]                              # KACO_HV
          elif type == 11:
            return byd_inverters[21]                             # Studer LV
          elif type == 12:
            return byd_inverters[28]                             # SolarEdge LV
          elif type == 13:
            return byd_inverters[6]                              # Ingeteam HV
        elif batt == "HVL":                                      # HVL
          if type == 0:
            return byd_inverters[1]
          elif type == 1:
            return byd_inverters[3]
          elif type == 2:
            return byd_inverters[8]
          elif type == 3:
            return byd_inverters[10]
          elif type == 4:
            return byd_inverters[17]
        else:                                                    # HVM, HVS
          if (type >= 0) and (type <= 16):
            return byd_inverters[type]
        return "unknown"

    def round_decimal(self,decimal_number,base,rounding=ROUND_DOWN):
        """
        Round decimal number to the nearest base
        : param decimal_number: decimal number to round to the nearest base
        : type decimal_number: Decimal
        : param base: rounding base, e.g. 5, Decimal('0.05')
        : type base: int or Decimal
        : param rounding: Decimal rounding type
        : rtype: Decimal
        """
#        return base * Decimal(decimal_number / base).quantize(1,rounding=rounding)
        return float(base * (Decimal(decimal_number) / base).quantize(1,rounding=rounding))
        
# -----------------------------------------------------------------------
# Webinterface
# -----------------------------------------------------------------------

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

# -----------------------------------------------------------------------
# Simulations-Routinen
# -----------------------------------------------------------------------

    def simulate_data(self):
        # For internal tests only
        
#        simul = 1  # HVM
        simul = 2  # HVS
#        simul = 3  # LVS

        twr = 3
        
        if simul == 1:
          self.byd_batt_str = "HVM"
          self.byd_modules = 7
          self.byd_capacity_module = 2.76
          self.byd_volt_n = 16
          self.byd_temp_n = 8
        elif simul == 2:
          self.byd_batt_str = "HVS"
          self.byd_modules = 5
          self.byd_capacity_module = 2.56
          self.byd_volt_n = 32
          self.byd_temp_n = 12
        elif simul == 3:
          self.byd_batt_str = "LVS"
          self.byd_modules = 3
          self.byd_capacity_module = 4.0
          self.byd_volt_n = 7
          self.byd_temp_n = 0
          
        self.byd_cells_n = self.byd_modules * self.byd_volt_n
        self.byd_temps_n = self.byd_modules * self.byd_temp_n
        
        for xx in range(0,self.byd_cells_n):
          self.byd_volt_cell[twr][xx] = round(random.uniform(2.1,2.9),2)
          self.byd_balance_cell[twr][xx] = random.randint(0,1)
#          self.log_info("xx=" + str(xx) + " v=" + str(self.byd_volt_cell[1][xx]))
        for xx in range(0,self.byd_temps_n):
          self.byd_temp_cell[twr][xx] = round(random.uniform(20.0,28.0),2)
#          self.log_info("xx=" + str(xx) + " v=" + str(self.byd_temp_cell[1][xx]))

        self.diag_plot(twr)

# -----------------------------------------------------------------------
# ENDE
# -----------------------------------------------------------------------
        