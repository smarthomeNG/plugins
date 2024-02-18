#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  rtr2 plugin to run with SmartHomeNG version 1.8 and upwards.
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
import os
import json

from lib.model.smartplugin import *
from lib.item import Items
from lib.shtime import Shtime

from .webif import WebInterface


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class Rtr2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '2.2.0'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

    _rtr = {}  # dict containing data of the rtrs. Key is the attribute rtr2_id


    def __init__(self, sh):
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
        self.default_Kp = self.get_parameter_value('default_Kp')
        self.default_Ki = self.get_parameter_value('default_Ki')
        self.default_Kd = self.get_parameter_value('default_Kd')

        self.default_comfort_temp = self.get_parameter_value('comfort_temp')
        self.default_standby_reduction = self.get_parameter_value('standby_reduction')
        self.default_night_reduction = self.get_parameter_value('night_reduction')
        self.default_fixed_reduction = self.get_parameter_value('fixed_reduction')
        self.default_frost_temp = self.get_parameter_value('frost_temp')
        self.default_hvac_mode = self.get_parameter_value('hvac_mode')
        self.default_valve_protect = self.get_parameter_value('valve_protect')
        self.default_min_output = self.get_parameter_value('min_output')
        self.default_max_output = self.get_parameter_value('max_output')

        self.cache_read_tried = False # Only write cache on shutdown, if a cache read has been tried on start

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = 10

        # Initialization code goes here

        # On initialization error use:
        #   self._init_complete = False
        #   return

        # set path to cache directory for plugins
        self.cache_path = os.path.join(self.get_sh().get_basedir(), 'var', 'plugins_cache')
        if not os.path.isdir(self.cache_path):
            # create plugins_cache dir if it does not already exist
            self.logger.warning(f"Createing cache directory {self.cache_path}")
            os.mkdir(self.cache_path)
        self.logger.info(f"Using cache directory {self.cache_path}")


        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)
        # if plugin should not start without web interface
        # if not self.init_webinterface():
        #     self._init_complete = False

        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # read rtr values from cache
        self.read_cacheinfo()

        # set items to initial rtr state
        for r in self._rtr:
            # validate
            pass
        self.update_all_rtrs()

        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('update_all_rtrs', self.update_all_rtrs, cycle=self._cycle)
        self.scheduler_add('valve_protection', self.valve_protection, prio=5, cron='30 2 * 0')


        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('valve_protection')
        self.scheduler_remove('update_all_rtrs')
        self.alive = False
        self.write_cacheinfo()

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
        if self.has_iattr(item.conf, 'rtr2_id'):
            self.logger.debug(f"parse item: {item}")
            rtr_id = self.get_iattr_value(item.conf, 'rtr2_id')
            if self._rtr.get(rtr_id, None) is None:
                # Create a new rtr
                parent_item = item.return_parent()
                temp_settings = []
                controller_settings = []
                if self.has_iattr(parent_item.conf, 'rtr2_settings'):
                    temp_settings = self.get_iattr_value(parent_item.conf, 'rtr2_settings')
                if self.has_iattr(parent_item.conf, 'rtr2_controller_settings'):
                    controller_settings = self.get_iattr_value(parent_item.conf, 'rtr2_controller_settings')
                self._rtr[rtr_id] = Rtr_object(self, temp_settings, controller_settings)
                self._rtr[rtr_id].id = rtr_id
                self._rtr[rtr_id].valve_protect = self.default_valve_protect

            rtr_func = self.get_iattr_value(item.conf, 'rtr2_function')
            if rtr_func is not None:
                rtr_func = rtr_func.lower()
                if rtr_func == 'comfort_mode':
                    self._rtr[rtr_id].comfort_item = item
                elif rtr_func == 'standby_mode':
                    self._rtr[rtr_id].standby_item = item
                elif rtr_func == 'night_mode':
                    self._rtr[rtr_id].night_item = item
                elif rtr_func == 'frost_mode':
                    self._rtr[rtr_id].frost_item = item
                elif rtr_func == 'hvac_mode':
                    self._rtr[rtr_id].hvac_item = item
                elif rtr_func == 'heating_status':
                    self._rtr[rtr_id].heating_status_item = item
                elif rtr_func == 'lock_status':
                    self._rtr[rtr_id].lock_status_item = item
                elif rtr_func == 'temp_set':
                    self._rtr[rtr_id].temp_set_item = item

                elif rtr_func == 'temp_actual':
                    self._rtr[rtr_id].temp_actual_item = item
                elif rtr_func == 'control_output':
                    self._rtr[rtr_id].control_output_item = item

                elif rtr_func == 'setting_temp_comfort':
                    self._rtr[rtr_id].setting_temp_comfort_item = item
                elif rtr_func == 'setting_temp_standby':
                    self._rtr[rtr_id].setting_temp_standby_item = item
                elif rtr_func == 'setting_temp_night':
                    self._rtr[rtr_id].setting_temp_night_item = item
                elif rtr_func == 'setting_night_reduction':
                    self._rtr[rtr_id].setting_night_reduction_item = item
                elif rtr_func == 'setting_standby_reduction':
                    self._rtr[rtr_id].setting_standby_reduction_item = item
                elif rtr_func == 'setting_fixed_reduction':
                    self._rtr[rtr_id].setting_fixed_reduction_item = item
                elif rtr_func == 'setting_temp_frost':
                    self._rtr[rtr_id].setting_temp_frost_item = item
                elif rtr_func == 'setting_min_output':
                    self._rtr[rtr_id].setting_min_output_item = item
                    if item() == 0:
                        item(self.default_min_output)
                elif rtr_func == 'setting_max_output':
                    self._rtr[rtr_id].setting_max_output_item = item
                    if item() == 0:
                        item(self.default_max_output)
                else:
                    return

                self._rtr[rtr_id].update_rtr_items('Init')
                return self.update_item


    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            #self.logger.warning(f"update_item: item={item.property.path} - value={item()}")
            rtr_id = self.get_iattr_value(item.conf, 'rtr2_id')
            rtr_func = self.get_iattr_value(item.conf, 'rtr2_function')
            self._rtr[rtr_id].set_mode(rtr_func, item())
            # update PI controller
            # self._rtr[rtr_id].update()
        return

    def update_all_rtrs(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        for r in self._rtr:
            # validate
            pass
            # set initial state
            # update PI controller
            self._rtr[r].update()


    def valve_protection(self):
        """
        Open and close valves of all RTRs periodically to protect them
        """
        self.logger.info(f"Starting valve protection for all RTRs")
        for r in self._rtr:
            if self._rtr[r].valve_protect:
                self.logger.info(f"- rtr {r}: Valve protection is opening valve")
                self._rtr[r].valve_protect_active = True
            else:
                self.logger.info(f"- rtr {r}: Valve protection is disabled")

        shtime = Shtime.get_instance()
        close_time = shtime.now() + datetime.timedelta(minutes=5)
        # add scheduler to turn protection off after 5 minutes
        self.scheduler_add('valve_protection_close', self.valve_protection_close, next=close_time)

        self.update_all_rtrs()
        return


    def valve_protection_close(self):
        """

        :return:
        """
        self.logger.info(f"Ending valve protection for all RTRs")
        for r in self._rtr:
            if self._rtr[r].valve_protect_active:
                self.logger.info(f"- rtr {r}: Valve protection is closing valve (returning to regular state)")
                self._rtr[r].valve_protect_active = False
        self.update_all_rtrs()
        return


    def write_cacheinfo(self):
        self.logger.info("write_cacheinfo() called")
        # get parameters from all rtrs to be written to cache file (e.g. to survive a restart)
        # Info to be written:
        #  - temp info (analog to setup parameters)
        #  - rtr mode
        #
        if not self.cache_read_tried:
            # Do not write cache, if no cache read has been tried on startup
            # (-> an error has happend in the initialization of SmartHomeNG)
            # This is done to prevent writing the default values to cache if initialization of shng aborts
            return

        info_dict = {}
        for r in self._rtr:
            info_dict[r] = {}
            info_dict[r]['hvac'] = self._rtr[r]._mode.hvac
            info_dict[r]['mode_before_frost'] = self._rtr[r]._mode._mode_before_frost
            info_dict[r]['comfort_temp'] = round(self._rtr[r]._temp._temp_comfort, 2)
            info_dict[r]['standby_reduction'] = round(self._rtr[r]._temp.standby_reduction, 2)
            info_dict[r]['night_reduction'] = round(self._rtr[r]._temp.night_reduction, 2)
            info_dict[r]['fixed_reduction'] = self._rtr[r]._temp.fixed_reduction
            info_dict[r]['frost_temp'] = round(self._rtr[r]._temp._temp_frost, 2)
            if (self._rtr[r].lock_status_item is not None):
                info_dict[r]['locked'] = self._rtr[r].lock_status_item()
            if (self._rtr[r].setting_max_output_item is not None):
                info_dict[r]['max_output'] = self._rtr[r].setting_max_output_item()
            if (self._rtr[r].setting_min_output_item is not None):
                info_dict[r]['min_output'] = self._rtr[r].setting_min_output_item()
            if self.default_Kp != self._rtr[r].controller._Kp:
                info_dict[r]['Kp'] = self._rtr[r].controller._Kp
            if self.default_Ki != self._rtr[r].controller._Ki:
                info_dict[r]['Ki'] = self._rtr[r].controller._Ki
            try:
                if self.default_Kd != self._rtr[r].controller._Kd:
                    info_dict[r]['Kd'] = self._rtr[r].controller._Kd
            except: pass
        self.logger.info(f"write_cacheinfo: info_dict = {info_dict}")

        filename = os.path.join(self.cache_path,'rtr2.json')
        # write thread list to ../var/run
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(info_dict, f, ensure_ascii=False, indent=4)

        return

    def read_cacheinfo(self):
        self.cache_read_tried = True

        self.logger.info("read_cacheinfo() called")
        filename = os.path.join(self.cache_path,'rtr2.json')
        try:
            with open(filename) as f:
                info_dict = json.load(f)
        except:
            return

        self.logger.info(f"read_cacheinfo: info_dict = {info_dict}")
        for r in info_dict:
            self.logger.info(f"rtr {r} = {info_dict[r]}")
            if self._rtr.get(r, None) is not None:
                try:
                    # set Kp, Ki, Kd only, if saved to cache before
                    self._rtr[r].controller._Kp = float(info_dict[r]['Kp'])
                    self._rtr[r].controller._Ki = float(info_dict[r]['Ki'])
                    self._rtr[r].controller._Kd = float(info_dict[r]['Kd'])
                except: pass

                self._rtr[r]._mode._mode_before_frost = info_dict[r].get('mode_before_frost', 0)
                self._rtr[r]._mode.hvac = info_dict[r]['hvac']
                self._rtr[r]._temp._temp_comfort = info_dict[r]['comfort_temp']
                self._rtr[r]._temp.standby_reduction = info_dict[r]['standby_reduction']
                self._rtr[r]._temp.night_reduction = info_dict[r]['night_reduction']
                self._rtr[r]._temp.fixed_reduction = info_dict[r]['fixed_reduction']
                self._rtr[r]._temp._temp_frost = info_dict[r]['frost_temp']

                if (self._rtr[r].lock_status_item is not None):
                    value = info_dict[r].get('locked', None)
                    if value is not None:
                        self._rtr[r].lock_status_item(value)
                if (self._rtr[r].setting_max_output_item is not None):
                    value = info_dict[r].get('max_output', None)
                    if value is not None:
                        self._rtr[r].setting_max_output_item(value)
                if (self._rtr[r].setting_min_output_item is not None):
                    value = info_dict[r].get('min_output', None)
                    if value is not None:
                        self._rtr[r].setting_min_output_item(value)

                self._rtr[r].update_rtr_items('Cache')
            else:
                self.logger.warning(f"Cannot restore cached values for rtr '{r}' (rtr not defined in items)")
        return

# ==================================================================================================


from .mode import *
from .temperature import *
from .pi_controller import *

class Rtr_object():

    def __init__(self, plugin, temp_settings=None, controller_settings=None):
        self.plugin = plugin
        self.logger = self.plugin.logger
        self.valve_protect = False
        self.valve_protect_active = False

        if temp_settings is not None and isinstance(temp_settings, list):
            if len(temp_settings) < 1:
                temp_settings.append(self.plugin.default_comfort_temp)      # comfort temp
            if len(temp_settings) < 2:
                temp_settings.append(self.plugin.default_night_reduction)   # night reduction
            if len(temp_settings) < 3:
                temp_settings.append(self.plugin.default_standby_reduction) # standby_reduction
            if len(temp_settings) < 4:
                temp_settings.append(self.plugin.default_fixed_reduction)   # fixed_reduction
            if len(temp_settings) < 5:
                temp_settings.append(self.plugin.default_hvac_mode)         # hvac mode
            if len(temp_settings) < 6:
                temp_settings.append(self.plugin.default_frost_temp)        # frost prevention temp

        self.logger.info(f"New Rtr_object: Initial temp_settings = {temp_settings}")

        Kp = self.plugin.default_Kp
        Ki = self.plugin.default_Ki
        Kd = self.plugin.default_Kd
        if controller_settings is not None and isinstance(controller_settings, list):
            # use inividual controller settings for Kp, Ki (and Kd)
            if len(controller_settings) > 0:
                Kp = controller_settings[0]
            if len(controller_settings) > 1:
                Ki = controller_settings[1]
            if len(controller_settings) > 2:
                Kd = controller_settings[2]

        self._mode = Mode()

        #                        mode,       comfort_temp,   night_reduction=None, standby_reduction=None,
        #                         fixed_reduction=True, hvac_mode=True, frost_temp=None):
        self._temp = Temperature(self._mode, temp_settings[0], temp_settings[1], temp_settings[2],
                                 temp_settings[3], temp_settings[4], temp_settings[5])
        self.controller = Pi_controller(self._temp, Kp, Ki)
        # self.controller = Pi_controller(self._temp, 3, 120)

        self.id = 'unknown_rtr'
        self.comfort_item = None
        self.standby_item = None
        self.night_item = None
        self.frost_item = None
        self.hvac_item = None
        self.heating_status_item = None
        self.lock_status_item = None
        self.lock_items = [None, None, None]
        self.temp_set_item = None

        self.temp_actual_item = None
        self.control_output_item = None

        self.setting_temp_comfort_item = None
        self.setting_temp_standby_item = None
        self.setting_temp_night_item = None
        self.setting_night_reduction_item = None
        self.setting_standby_reduction_item = None
        self.setting_fixed_reduction_item = None
        self.setting_temp_frost_item = None
        self.setting_min_output_item = None
        self.setting_max_output_item = None


    def update(self):
        self.logger.info(f"rtr {self.id}: update called")
        if self.temp_actual_item is not None:
            # If valve protection is active, overrule lock and controler values
            if self.valve_protect_active:
                dummy = self.controller.update(self.temp_actual_item())
                output = 100
                if (self.setting_max_output_item is not None) and (output > self.setting_max_output_item()):
                    output = self.setting_max_output_item()
                self._update_item(self.control_output_item, output)
                self._update_item(self.heating_status_item, self.heating)
            # test if RTR is locked
            elif (self.lock_status_item is not None) and self.lock_status_item:
                # if RTR is locked, set output to 0
                dummy = self.controller.update(self.temp_actual_item())
                self._update_item(self.control_output_item, 0)
                self._update_item(self.heating_status_item, False)
            else:
                # regular opertion: Set output to conroller result
                output = self.controller.update(self.temp_actual_item())
                # test if controller has been fully initialized
                if output is not None:
                    # test if a min- od max output is set
                    if (self.setting_max_output_item is not None) and (output > self.setting_max_output_item()):
                        output = self.setting_max_output_item()
                    if (self.setting_min_output_item is not None) and (output < self.setting_min_output_item()):
                        output = self.setting_min_output_item()
                    # set output value
                    self._update_item(self.control_output_item, output)
                    self._update_item(self.heating_status_item, self.heating)
        self.logger.info(f"rtr {self.id}: update finished")
        return


    # ----------------------------------------------------------------------
    # Methods to update status
    #
    def set_mode(self, mode, state):

        if mode == 'comfort_mode':
            self._mode.comfort = state
            self.update_rtr_items(mode)
        if mode == 'standby_mode':
            self._mode.standby = state
            self.update_rtr_items(mode)
        if mode == 'night_mode':
            self._mode.night = state
            self.update_rtr_items(mode)
        if mode == 'frost_mode':
            self._mode.frost = state
            self.update_rtr_items(mode)
        if mode == 'hvac_mode':
            self._mode.hvac = state
            self.update_rtr_items(mode)
        if mode == 'temp_set':
            self._temp.set_temp = state
            self.update_rtr_items(mode)

        if mode == 'lock_status':
            if (self.lock_items[0] is None) and (self.lock_items[1] is None) and (self.lock_items[2] is None):
                self.update()
            else:
                # self.lock_status_item aus den Werten von self.lock_items[0..2] berechnen und setzen
                # (das macht self.lock_status_item r/o)
                pass

        if mode == 'temp_actual':
            self._temp.temp_actual = state
            self.update_rtr_items(mode)
        if mode == 'control_output':
            self._temp.control_output = state
            self.update_rtr_items(mode)

        if mode == 'setting_temp_comfort':
            self._temp.comfort = state
            self.update_rtr_items(mode)
        if mode == 'setting_temp_standby':
            self._temp.standby = state
            self.update_rtr_items(mode)
        if mode == 'setting_temp_night':
            self._temp.night = state
            self.update_rtr_items(mode)
        if mode == 'setting_night_reduction':
            self._temp.night_reduction = state
            self.update_rtr_items(mode)
        if mode == 'setting_standby_reduction':
            self._temp.standby_reduction = state
            self.update_rtr_items(mode)
        if mode == 'setting_fixed_reduction':
            self._temp.fixed_reduction = state
            self.update_rtr_items(mode)
        if mode == 'setting_temp_frost':
            self._temp.frost = state
            self.update_rtr_items(mode)
        return


    def update_rtr_items(self, ignore_function=None):

        if ignore_function != 'comfort_mode':
            self._update_item(self.comfort_item, self._mode.comfort, src=ignore_function)
        if ignore_function != 'standby_mode':
            self._update_item(self.standby_item, self._mode.standby, src=ignore_function)
        if ignore_function != 'night_mode':
            self._update_item(self.night_item, self._mode.night, src=ignore_function)
        if ignore_function != 'frost_mode':
            self._update_item(self.frost_item, self._mode.frost, src=ignore_function)
        if ignore_function != 'hvac_mode':
            self._update_item(self.hvac_item, self._mode.hvac, src=ignore_function)
        if ignore_function != 'temp_set':
            self._update_item(self.temp_set_item, round(float(self._temp.set_temp), 2), src=ignore_function)

        # self.temp_actual_item = None

        if ignore_function != 'setting_temp_comfort':
            self._update_item(self.setting_temp_comfort_item, round(self._temp.comfort, 2), src=ignore_function)
        if ignore_function != 'setting_temp_standby':
            self._update_item(self.setting_temp_standby_item, round(self._temp.standby, 2), src=ignore_function)
        if ignore_function != 'setting_temp_night':
            self._update_item(self.setting_temp_night_item, round(self._temp.night, 2), src=ignore_function)
        if ignore_function != 'setting_night_reduction':
            self._update_item(self.setting_night_reduction_item, self._temp.night_reduction, src=ignore_function)
        if ignore_function != 'setting_standby_reduction':
            self._update_item(self.setting_standby_reduction_item, self._temp.standby_reduction, src=ignore_function)
        if ignore_function != 'setting_fixed_reduction':
            self._update_item(self.setting_fixed_reduction_item, self._temp.fixed_reduction, src=ignore_function)
        if ignore_function != 'setting_temp_frost':
            self._update_item(self.setting_temp_frost_item, round(self._temp.frost, 2), src=ignore_function)

        self._update_item(self.heating_status_item, self.heating, src=ignore_function)


    def _update_item(self, item, value, src=None):
        if item is not None:
            item(value, self.plugin.get_shortname(), src)


    @property
    def heating(self):
        """
        Property: heating state

        :return: actual heating state
        :rtype: bool
        """
        #self.logger.warning(f"rtr.heating={(self.controller.output >= 1.0)}, controller.putput={self.controller.output}")
        return (self.controller.output >= 1.0)


    def __repr__(self):
        #return f"Mode object:\n{self._mode}\n\nTemperature object:\n{self._temp}\n\nPI-controller object:\n{self.controller}"
        #return f"PI-controller object:\n{self.controller}, valve protect: {self.valve_protect}"
        return f"valve protect: {self.valve_protect}"
