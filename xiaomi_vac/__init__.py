#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#
####################################################################################
######################################################################################
#
#  Copyright 2018 Version-1    Manuel Holländer
#  Copyright 2019 Version-2    Manuel Holländer
####################################################################################
#
#  This Plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  smarthomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHome.py. If not, see <http://www.gnu.org/licenses/>.
#
#
import logging
import threading
import struct
import binascii
import re
import time
from datetime import datetime, timedelta

try:
    from miio.vacuum import Vacuum, VacuumException, Consumable
except Exception:
    from miio.integrations.vacuum.roborock import RoborockVacuum, VacuumException
    from miio.integrations.vacuum.roborock.vacuum import Consumable
try:
    from miio.vacuumcontainers import (VacuumStatus, ConsumableStatus, DNDStatus, CleaningDetails, CleaningSummary, Timer)
except Exception:
    from miio.integrations.vacuum.roborock.vacuumcontainers import (VacuumStatus, ConsumableStatus, DNDStatus, CleaningDetails, CleaningSummary, Timer)

from miio.discovery import Discovery

from lib.model.smartplugin import *
from lib.module import Modules
from lib.item import Items
from bin.smarthome import VERSION


class Robvac(SmartPlugin):
    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = "1.2.0"

    def __init__(self, smarthome):
        self._ip = self.get_parameter_value("ip")
        self._token = self.get_parameter_value("token")
        self._cycle = self.get_parameter_value("read_cycle")
        self._discovererror = 0
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.messages = {}
        self.found = False
        self._lock = threading.Lock()
        self.retry_count_max = 3
        self.retry_count = 1
        self._connected = False
        self._data = {}
        self._data['state'] = 'disconnected'
        if not self.init_webinterface():
            self._init_complete = False

        if self._token == '':
            self.logger.error("Xiaomi_Robvac: No Key for Communication given, Plugin would not start!")
            pass
        else:
            self.logger.debug("Xiaomi_Robvac: Plugin Start!")
            if self._cycle > 10:
                self.scheduler_add('Xiaomi_Robvac Read cycle', self._read, prio=5, cycle=self._cycle)
            else:
                self.logger.warning("Xiaomi_Robvac: Read Cycle is too fast! < 10s, not starting!")

    # --------------------------------------------------------------------------
    # Verbinden zum Roboter
    # --------------------------------------------------------------------------
    def _connect(self):
        if self._connected is False:
            for i in range(0, self.retry_count_max-self.retry_count):
                try:
                    try:
                        self.vakuum = Vacuum(self._ip, self._token, 0, 0)
                    except Exception:
                        self.vakuum = RoborockVacuum(self._ip, self._token, 0, 0)
                    self.retry_count = 1
                    self._connected = True
                    return True
                except Exception as e:
                    self.logger.error("Xiaomi_Robvac: Error {0}, "
                                      "Cycle {1} ".format(e, self.retry_count))
                    self.retry_count += 1
                    self._connected = False
                    self._data['state'] = 'disconnected'
                    return False

    # --------------------------------------------------------------------------
    # Daten Lesen, über SHNG bei item_Change
    # --------------------------------------------------------------------------
    def groupread(self, ga, dpt):
        pass

    # --------------------------------------------------------------------------
    # Daten Lesen, zyklisch
    # --------------------------------------------------------------------------
    def _read(self):
        self._connect()
        try:
            clean_history = self.vakuum.clean_history()
            self._data['clean_total_count'] = int(clean_history.count)
            self._data['clean_total_area'] = round(clean_history.total_area, 2)
            self._data['clean_total_duration'] = (
                clean_history.total_duration.total_seconds() / 60)
            self._data['clean_ids'] = clean_history.ids
            self.logger.debug("Xiaomi_Robvac: Statistics count {0}, area {1}², "
                              "duration {2}, clean ids {3}".format(
                                    self._data['clean_total_count'],
                                    self._data['clean_total_area'],
                                    self._data['clean_total_duration'],
                                    self._data['clean_ids']))

            # letzte reinigung
            # funktioniert nur mit übergebener id
            if self._data.get('clean_ids') is not None:
                # self._data['clean_ids'] = self._data['clean_ids'].sort(reverse=True)
                try:
                    self._data['clean_details_last0'] = (
                        self.vakuum.clean_details(self._data['clean_ids'][0], return_list=False))
                except Exception:
                    self._data['clean_details_last0'] = (
                        self.vakuum.clean_details(self._data['clean_ids'][0]))
                self._data['last0_area'] = (
                    round(self._data['clean_details_last0'].area, 2))
                self._data['last0_complete'] = self._data['clean_details_last0'].complete
                self._data['last0_duration'] = (
                    round(self._data['clean_details_last0'].duration.total_seconds() / 60, 2))
                self._data['last0_start_date'] = (
                    self._data['clean_details_last0'].start.strftime("%d.%m.%Y"))
                self._data['last0_start_time'] = (
                    self._data['clean_details_last0'].start.strftime("%H:%M"))
                self._data['last0_end_date'] = (
                    self._data['clean_details_last0'].start.strftime("%d.%m.%Y"))
                self._data['last0_end_time'] = (
                    (self._data['clean_details_last0'].start
                     + self._data['clean_details_last0'].duration).strftime("%H:%M"))

                try:
                    self._data['clean_details_last1'] = (
                        self.vakuum.clean_details(self._data['clean_ids'][1], return_list=False))
                except Exception:
                    self._data['clean_details_last1'] = (
                        self.vakuum.clean_details(self._data['clean_ids'][1]))
                self._data['last1_area'] = (
                    round(self._data['clean_details_last1'].area, 2))
                self._data['last1_complete'] = self._data['clean_details_last1'].complete
                self._data['last1_duration'] = (
                    round(self._data['clean_details_last1'].duration.total_seconds() / 60, 2))
                self._data['last1_start_date'] = (
                    self._data['clean_details_last1'].start.strftime("%d.%m.%Y"))
                self._data['last1_start_time'] = (
                    self._data['clean_details_last1'].start.strftime("%H:%M"))
                self._data['last1_end_date'] = (
                    self._data['clean_details_last1'].start.strftime("%d.%m.%Y"))
                self._data['last1_end_time'] = (
                    (self._data['clean_details_last1'].start
                     + self._data['clean_details_last1'].duration).strftime("%H:%M"))

                try:
                    self._data['clean_details_last2'] = (
                        self.vakuum.clean_details(self._data['clean_ids'][2], return_list=False))
                except Exception:
                    self._data['clean_details_last2'] = (
                        self.vakuum.clean_details(self._data['clean_ids'][2]))
                self._data['last2_area'] = (
                    round(self._data['clean_details_last2'].area, 2))
                self._data['last2_complete'] = self._data['clean_details_last2'].complete
                self._data['last2_duration'] = (
                    round(self._data['clean_details_last2'].duration.total_seconds() / 60, 2))
                self._data['last2_start_date'] = (
                    self._data['clean_details_last2'].start.strftime("%d.%m.%Y"))
                self._data['last2_start_time'] = (
                    self._data['clean_details_last2'].start.strftime("%H:%M"))
                self._data['last2_end_date'] = (
                    self._data['clean_details_last2'].start.strftime("%d.%m.%Y"))
                self._data['last2_end_time'] = (
                     (self._data['clean_details_last2'].start
                      + self._data['clean_details_last2'].duration).strftime("%H:%M"))

                try:
                    self._data['clean_details_last3'] = (
                        self.vakuum.clean_details(self._data['clean_ids'][3], return_list=False))
                except Exception:
                    self._data['clean_details_last3'] = (
                        self.vakuum.clean_details(self._data['clean_ids'][3]))
                self._data['last3_area'] = (
                    round(self._data['clean_details_last3'].area, 2))
                self._data['last3_complete'] = self._data['clean_details_last3'].complete
                self._data['last3_duration'] = (
                    round(self._data['clean_details_last3'].duration.total_seconds() / 60, 2))
                self._data['last3_start_date'] = (
                    self._data['clean_details_last3'].start.strftime("%d.%m.%Y"))
                self._data['last3_start_time'] = (
                    self._data['clean_details_last3'].start.strftime("%H:%M"))
                self._data['last3_end_date'] = (
                    self._data['clean_details_last3'].start.strftime("%d.%m.%Y"))
                self._data['last3_end_time'] = (
                    (self._data['clean_details_last3'].start
                     + self._data['clean_details_last3'].duration).strftime("%H:%M"))

                self.logger.debug("Xiaomi_Robvac: historic id1 {}, "
                                  "id2{}, id3 {}".format(
                                        self._data['clean_details_last0'],
                                        self._data['clean_details_last1'],
                                        self._data['clean_details_last2']))

                self.logger.debug("Xiaomi_Robvac: Clean Run complete id1 {}, "
                                  "id2{}, id3 {}".format(
                                       self._data['last1_complete'],
                                       self._data['last2_complete'],
                                       self._data['last3_complete'],))
            carpet_mode = self.vakuum.carpet_mode()
            self._data['carpetmode_high'] = carpet_mode.current_high
            self._data['carpetmode_integral'] = carpet_mode.current_integral
            self._data['carpetmode_low'] = carpet_mode.current_low
            self._data['carpetmode_enabled'] = carpet_mode.enabled
            self._data['carpetmode_stall_time'] = carpet_mode.stall_time
            self.logger.debug("Xiaomi_Robvac: Carpet Mode high: {}, integral: {}, low: {}, "
                              "enabled: {}, stall_time: {}".format(
                                   self._data['carpetmode_high'],
                                   self._data['carpetmode_integral'],
                                   self._data['carpetmode_low'],
                                   self._data['carpetmode_enabled'],
                                   self._data['carpetmode_stall_time']))

            # status
            self._data['serial'] = self.vakuum.serial_number()
            self._data['volume'] = self.vakuum.sound_volume()
            self._data['dnd_status'] = self.vakuum.dnd_status().enabled
            self._data['dnd_start'] = self.vakuum.dnd_status().start
            self._data['dnd_end'] = self.vakuum.dnd_status().end
            self.logger.debug("Xiaomi_Robvac: Serial{}, vol {}, dnd status {}, "
                              "dnd start {},dnd end {},".format(
                                    self._data['serial'],
                                    self._data['volume'],
                                    self._data['dnd_status'],
                                    self._data['dnd_start'],
                                    self._data['dnd_end']))

            self._data['device_group'] = self.vakuum.get_device_group()
            self._data['segment_status'] = self.vakuum.get_segment_status()
            self._data['fanspeed'] = self.vakuum.status().fanspeed
            self._data['batt'] = self.vakuum.status().battery
            self._data['battery'] = self.vakuum.status().battery
            self._data['area'] = round(self.vakuum.status().clean_area, 2)
            self._data['clean_time'] = self.vakuum.status().clean_time.total_seconds() / 60
            self._data['active'] = self.vakuum.status().is_on  # reinigt?
            self._data['zone_cleaning'] = self.vakuum.status().in_zone_cleaning  # reinigt?
            self._data['is_error'] = self.vakuum.status().got_error
            self.logger.debug("Xiaomi_Robvac: segment_status {}, fanspeed {}, "
                              "battery {}, area {}, clean_time {}, active {}, "
                              "zone_clean {}, device group {}".format(
                                    self._data['segment_status'],
                                    self._data['fanspeed'],
                                    self._data['battery'],
                                    self._data['area'],
                                    self._data['clean_time'],
                                    self._data['active'],
                                    self._data['zone_cleaning'],
                                    self._data['device_group']))
            self._data['error'] = self.vakuum.status().error_code
            self._data['pause'] = self.vakuum.status().is_paused  # reinigt?
            self._data['state'] = self.vakuum.status().state  # status charging
            self._data['timer'] = self.vakuum.timer()
            self._data['timezone'] = self.vakuum.timezone()

            # bekannet States: Charging, Pause, Charging Disconnected
            if self._data['state'] == 'Charging':
                self._data['charging'] = True
            else:
                self._data['charging'] = False

            self.logger.debug("Xiaomi_Robvac: error {}, pause {}, "
                "status {} , timer {}, timezone {}".format(
                    self._data['error'],
                    self._data['pause'],
                    self._data['state'],
                    self._data['timer'],
                    self._data['timezone']))
            self._data['sensor_dirty'] = (
                self.vakuum.consumable_status().sensor_dirty.total_seconds() // 3600)
            self._data['sensor_dirty_left'] = (
                self.vakuum.consumable_status().sensor_dirty_left.total_seconds() // 3600)
            self._data['side_brush'] = (
                self.vakuum.consumable_status().side_brush.total_seconds() // 3600)
            self._data['side_brush_left'] = (
                self.vakuum.consumable_status().side_brush_left.total_seconds() // 3600)
            self._data['main_brush'] = (
                self.vakuum.consumable_status().main_brush.total_seconds() // 3600)
            self._data['main_brush_left'] = (
                self.vakuum.consumable_status().main_brush_left.total_seconds() // 3600)
            self._data['filter'] = (
                self.vakuum.consumable_status().filter.total_seconds() // 3600)
            self._data['filter_left'] = (
                self.vakuum.consumable_status().filter_left.total_seconds() // 3600)
            self.logger.debug("Xiaomi_Robvac: Brush Side {0}/{1}, "
                              "Brush Main {2}/{3}, Filter{4}/{5}, "
                              "Sensor{6}/{7}".format(
                                    self._data['side_brush'],
                                    self._data['side_brush_left'],
                                    self._data['main_brush'],
                                    self._data['main_brush_left'],
                                    self._data['filter'],
                                    self._data['filter_left'],
                                    self._data['sensor_dirty'],
                                    self._data['sensor_dirty_left']))

            self._discovererror = 0
        except Exception as e:
            if str(e).startswith("Unable to discover"):
                self._discovererror += 1
                self.logger.error("Xiaomi_Robvac: Error {} for {} time(s) in a row.".format(e, self._discovererror))
            else:
                self.logger.error("Xiaomi_Robvac: Error {}".format(e))
            self._connected = False
            self._data['state'] = 'disconnected'

        for x in self._data:
            if x in self.messages:
                self.logger.debug("Xiaomi_Robvac: Update item {1} with key {0} = value {2}".format(x, self.messages[x], self._data[x]))
                item = self.messages[x]
                item(self._data[x], 'Xiaomi Robovac')

    # -------------------------------------------------------------------------
    # Befehl senden, wird aufgerufen wenn sich item  mit robvac ändert!
    # --------------------------------------------------------------------------

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'Robvac' and self.alive:
            # if 'robvac' in item.conf:
            #    message = item.conf['robvac']
            if not self._connected:
                message = self.get_iattr_value(item.conf, 'robvac')
                self.logger.error("Xiaomi_Robvac: Keyword {0}, item {1}"
                    " not changed - no connection! Resetting item to {2}".format(
                        message, item, item.property.last_value))
                item(item.property.last_value, 'Robvac', 'NoConnection')
            elif self.has_iattr(item.conf, 'robvac'):
                # bei boolischem item Item zurücksetzen, damit enforce_updates nicht nötig!
                message = self.get_iattr_value(item.conf, 'robvac')
                self.logger.debug("Xiaomi_Robvac: Keyword {0}, item {1} "
                    "changed to {2}".format(message, item, item.property.value))
                if message == 'fanspeed':
                    self.vakuum.set_fan_speed(item.property.value)
                elif message == 'volume':
                    if item() > 100:
                        vol = 100
                    else:
                        vol = item()
                    self.vakuum.set_sound_volume(vol)
                elif message == 'set_start':
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    self.vakuum.start()
                elif message == 'set_stop':
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    self.vakuum.pause()
                elif message == "set_home":
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    self.vakuum.home()
                elif message == "set_pause":
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    self.vakuum.pause()
                elif message == "set_spot":
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    self.vakuum.spot()
                elif message == "set_find":
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    self.vakuum.find()
                elif message == "reset_filtertimer":
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    self.vakuum.reset_consumable()
                elif message == "disable_dnd":
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    self.vakuum.disable_dnd()
                elif message == "set_dnd":
                    if item() is True:
                        item(False, 'Robvac', 'AutoResetBool')
                    # start_hr, start_min, end_hr, end_min
                    self.vakuum.set_dnd(item()[0], item()[1], item()[2], item()[3])
                elif message == "clean_zone":
                    self.vakuum.zoned_clean(item()[0], item()[1], item()[2], item()[3], item()[4])
                elif message == "segment_clean":
                    self.vakuum.segment_clean(item())
                elif message == "go_to":
                    self.vakuum.goto(item()[0], item()[1])
                elif message == "create_nogo_zones":
                    self.vakuum.create_nogo_zone(item()[0], item()[1])
                elif message == "reset":
                    if item().lower() in ["sensor_dirty", "sensor_reinigen"]:
                        self.vakuum.consumable_reset(Consumable.SensorDirty)
                        self.logger.debug("Xiaomi_Robvac: sensor_dirty reset")
                    elif item().lower() in ["main_brush", "buerste_haupt"]:
                        self.vakuum.consumable_reset(Consumable.MainBrush)
                        self.logger.debug("Xiaomi_Robvac: main_brush reset")
                    elif item().lower() in ["side_brush", "buerste_seite"]:
                        self.vakuum.consumable_reset(Consumable.SideBrush)
                        self.logger.debug("Xiaomi_Robvac: side_brush reset")
                    elif item().lower() == "filter":
                        self.vakuum.consumable_reset(Consumable.Filter)
                        self.logger.debug("Xiaomi_Robvac: filter reset")
                    else:
                        self.logger.warning("Consumable {} does not exit. Please use only sensor_dirty/sensor_reinigen, main_brush/buerste_haupt, side_brush/buerste_seite, filter.".format(item.property.value))

    def run(self):
        self.alive = True
        self.logger.debug("Xiaomi_Robvac: Run method. Found items {}".format(self.messages))

    def stop(self):
        self.logger.debug("Xiaomi_Robvac: Stop method.")
        self.scheduler_remove('Xiaomi_Robvac Read cycle')
        self.alive = False

    def parse_item(self, item):
        if self.has_iattr(item.conf, 'robvac'):
            message = self.get_iattr_value(item.conf, 'robvac')
            self.logger.debug("Xiaomi_Robvac: {0} keyword {1}".format(item, message))
            if message not in self.messages:
                self.messages[message] = item
            return self.update_item

    def update_item_read(self, item, caller=None, source=None, dest=None):
        if self.has_iattr(item.conf, 'robvac'):
            for message in item.get_iattr_value(item.conf, 'robvac'):
                self.logger.debug("Xiaomi_Robvac: update_item_read {0}".format(message))
# ------------------------------------------
#    Webinterface Methoden
# ------------------------------------------

    def get_connection_info(self):
        info = {}
        info['ip'] = self._ip
        info['token'] = self._token
        info['cycle'] = self._cycle
        info['connected'] = self._connected
        return info

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')
        except Exception:
            self.mod_http = None
        if self.mod_http is None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
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

        self.logger.debug("Plugin '{0}': {1}, {2}, {3}, {4}, {5}".format(
            self.get_shortname(), webif_dir, self.get_shortname(),
            config, self.get_classname(), self.get_instance_name()))
        # Register the web interface as a cherrypy app
        self.mod_http.register_webif(WebInterface(webif_dir, self),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

import cherrypy
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
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()
        self.logger.debug("Plugin : Init Webif")
        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy
        Render the template and return the html file to be delivered to the browser
        :return: contents of the template after beeing rendered
        """
        plgitems = []
        for item in self.items.return_items():
            if ('robvac' in item.conf):
                plgitems.append(item)
        self.logger.debug("Plugin : Render index Webif")
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(),
                           plugin_version=self.plugin.get_version(),
                           plugin_info=self.plugin.get_info(),
                           p=self.plugin,
                           connection=self.plugin.get_connection_info(),
                           webif_dir=self.webif_dir,
                           items=sorted(plgitems, key=lambda k: str.lower(k['_path'])))
