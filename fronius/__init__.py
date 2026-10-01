#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <Michael Buchmann>                        <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Plugin for Fronius solar inverter  to run with SmartHomeNG version 1.8 and
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

import requests
from lib.model.smartplugin import SmartPlugin

from .webif import WebInterface


class fronius(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items
    """

    PLUGIN_VERSION = '0.1.0'

    def __init__(self, sh):

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # Unfortunately the GEN24 does not report a correct device type
        self._fronius_model = 'Symo GEN24'

        self._items = {}
        self.p_pv_day = 0
        self._cyclic_update_active = False
        self.alive = False
        self.suspended = False
        self.webif_pagelength = self.get_parameter_value('webif_pagelength')
        self.poll_cycle = self.get_parameter_value('poll_cycle')
        self.ip_address = self.get_parameter_value('ip_address')
        self._datafile = self.get_parameter_value('data_file')
        self.init_webinterface(WebInterface)
        self.scheduler_add('midnight', self._midnight, cron='0 0 * *', prio=3)

#---------------------- run ---------------------------------------------------
    def run(self):
        self.logger.debug("Fronius Run method called")

        # setup scheduler for device poll loop
        self.scheduler_add('poll_device', self.poll_device, cycle=self.poll_cycle)
        self.alive = True

#---------------------- stop --------------------------------------------------
    def stop(self):
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')
        self.alive = False

#---------------------- parse_item --------------------------------------------
# Default plugin parse_item method. Is called when the plugin is initialized.
# The plugin can, corresponding to its attribute keywords, decide what to do with
# the item in the future, like adding it to an internal array for future reference
# :param item:    The item to process.
# :return:        If the plugin needs to be informed of an items change you should return a call back function
#                 like the function update_item down below. An example when this is needed is the knx plugin
#                 where parse_item returns the update_item function when the attribute knx_send is found.
#                 This means that when the items value is about to be updated, the call back function is called
#                 with the item, caller, source and dest as arguments and in case of the knx plugin the value
#                 can be sent to the knx with a knx write function within the knx plugin.
#------------------------------------------------------------------------------
    def parse_item(self, item):
        if self.has_iattr(item.conf, 'fronius_data'):
            self.logger.debug(f'parse item: {item}')
            self._items[item] = self.get_iattr_value(item.conf, 'fronius_data')
        return self.update_item

# --------------------- update_item -------------------------------------------
#        
#        Item has been updated
#
#        This method is called, if the value of an item has been updated by SmartHomeNG.
#        :param item: item to be updated towards the plugin
#        :param caller: if given it represents the callers name
#        :param source: if given it represents the source
#        :param dest: if given it represents the dest
# -----------------------------------------------------------------------------
    def update_item(self, item, caller=None, source=None, dest=None):

        # execute if the plugin is not stopped and only, if the item has not been changed by this plugin:
        if self.alive and caller != self.get_shortname():
            self.logger.info(f'Update item: {item.property.path}, item has been changed outside this plugin')

            if self.has_iattr(item.conf, 'fronius_data'):
                self.logger.debug(f'update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}')
                if self.get_iattr_value(item.conf, 'fronius_data') == 'update' and bool(item()):
                    self.logger.info('Update of all items of fronius Plugin requested.')
                    self.poll_device()
                    item(False)

# --------------------------- poll_device -------------------------------------
# poll the inverter and change the corrosponding items
# -----------------------------------------------------------------------------
    def poll_device(self):

        # check if another cyclic cmd run is still active
        if self._cyclic_update_active:
            self.logger.warning('Triggered cyclic poll_device, but previous cyclic run is still active. Therefore request will be skipped.')
            return
        elif self.suspended:
            self.logger.warning('Triggered cyclic poll_device, but Plugin in suspended. Therefore request will be skipped.')
            return
        else:
            self.logger.debug('Triggering cyclic poll_device')

        # set lock
        self._cyclic_update_active = True

        # get the data
        try:
            response = requests.get(f'http://{self.ip_address}/solar_api/v1/GetPowerFlowRealtimeData.fcgi') 
        except Exception:
            self.logger.error(f'Error access Fronius inverter at address {self.ip_address}')
            self._cyclic_update_active = False
            return
        response = response.json()
        soc = float(response['Body']['Data']['Inverters']['1']['SOC'])
        p_pv = float(response['Body']['Data']['Site']['P_PV'])
        p_grid = float(response['Body']['Data']['Site']['P_Grid'])
        p_accu = float(response['Body']['Data']['Site']['P_Akku'])
        p_load = response['Body']['Data']['Site']['P_Load']

        # Calculates the sum and store it in a file so that it survives a restart
        try:
            file = open(self._datafile, 'r')
        except FileNotFoundError:
            self.logger.error('Datafile not found')
            file = open(self._datafile, 'w')
            file.write('0.0')
            self.p_pv_day = 0
            file.close()
        file = open(self._datafile, 'r')
        try:            
            self.p_pv_day = float(file.readline())
        except Exception:
            self.logger.error('No data in datafile')
            self.p_pv_day = 0
        file.close()

        self.p_pv_day = self.p_pv_day + (p_pv * self.poll_cycle / 3600.0) 
        with open(self._datafile, 'w') as file:
            file.write(str(self.p_pv_day))

        # Put the date into the items
        for item in self._items:
            if self.get_iattr_value(item.conf, 'fronius_data') == 'soc':
                item(soc, self.get_shortname())
            if self.get_iattr_value(item.conf, 'fronius_data') == 'p_pv':
                item(p_pv, self.get_shortname())
            if self.get_iattr_value(item.conf, 'fronius_data') == 'p_pv_day':
                item(self.p_pv_day, self.get_shortname())
            if self.get_iattr_value(item.conf, 'fronius_data') == 'p_grid':
                item(p_grid, self.get_shortname())
            if self.get_iattr_value(item.conf, 'fronius_data') == 'p_accu':
                item(p_accu, self.get_shortname())
            if self.get_iattr_value(item.conf, 'fronius_data') == 'p_load':
                item(p_load, self.get_shortname())

        # release lock
        self._cyclic_update_active = False

    # ------------------------------ _midnight --------------------------------
    # Called by the scheduler at midnight. It resets the daily engergy sum and
    # stores the value in the database item if it exists. 

    def _midnight(self):
        self.logger.debug('Midnight')
        self.logger.debug(self.p_pv_day)
        for item in self._items:
            if self.get_iattr_value(item.conf, 'fronius_data') == 'p_pv_day_database':
                item(self.p_pv_day, self.get_shortname())
        self.p_pv_day = 0.0
        with open(self._datafile, 'w') as file:
            file.write(str(self.p_pv_day))

    # -------------- properties for the web interface -------------------------
    @property
    def item_list(self):
        return list(self._items.keys())

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()

    @property
    def fronius_model(self):
        return self._fronius_model
