#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-2026  <Michael Buchmann>                        <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Plugin for Fronius solar inverter Symo GEN24 to run with SmartHomeNG
#  version 1.1 and upwards.
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
from datetime import datetime, time

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface


class fronius(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items
    """

    PLUGIN_VERSION = '0.1.0'
    ALLOW_MULTIINSTANCE = False  # set to True if the plugin can run as multiple instances simultaneously

    def __init__(self, sh=None, **kwargs):

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # Unfortunately the GEN24 does not report a correct device type
        self.logger.info('fronius plugin started')
        self._fronius_model = 'Symo GEN24'
        self._p_pv_day = 0
        self._cyclic_update_active = False
        self._cycle = self.get_parameter_value('poll_cycle')
        self._timeout = self.get_parameter_value('timeout')
        self._ip_address = self.get_parameter_value('ip_address')
        self.itemsApi = Items.get_instance()
        self.scheduler_add('midnight', self._midnight, cron='55 23 * *', prio=3)
        self.init_webinterface(WebInterface)

#---------------------- run ---------------------------------------------------
    def run(self):
        self.logger.debug(self.translate("Methode '{method}' aufgerufen", {'method': 'run()'}))

        # setup scheduler for device poll loop
        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True

#---------------------- stop --------------------------------------------------
    def stop(self):
        self.logger.debug(self.translate("Methode '{method}' aufgerufen", {'method': 'stop()'}))
        self.alive = False

        # this stops all schedulers the plugin has started.
        self.scheduler_remove_all()

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
            self.add_item(item, updating=True)
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
            self.logger.debug(
                f"update_item: '{item.property.path}' has been changed outside this plugin "
                #                f"by caller '{self.callerinfo(caller, source)}'"
            )

# --------------------------- poll_device -------------------------------------
# poll the inverter and change the corrosponding items
# -----------------------------------------------------------------------------
    def poll_device(self):

        # check if another cyclic cmd run is still active
        if self._cyclic_update_active:
            self.logger.warning('Triggered cyclic poll_device, but previous cyclic run is still active. Therefore request will be skipped.')
            return
        else:
            self.logger.debug('Triggering cyclic poll_device')

        # set lock
        self._cyclic_update_active = True

        # get the data
        path = f'http://{self._ip_address}/solar_api/v1/GetPowerFlowRealtimeData.fcgi'
        try:
            response = requests.get(path, timeout=self._timeout)
        except Exception:
            self.logger.error(f'Fronius inverter at address {self._ip_address} did not answer')
            self._cyclic_update_active = False
            return
        try:
            response = response.json()
            soc = float(response['Body']['Data']['Inverters']['1']['SOC'])
            p_pv = float(response['Body']['Data']['Site']['P_PV'])
            p_grid = float(response['Body']['Data']['Site']['P_Grid'])
            p_accu = float(response['Body']['Data']['Site']['P_Akku'])
            p_load = float(response['Body']['Data']['Site']['P_Load'])
        except Exception:
            self.logger.error(f'Fronius inverter at address {self._ip_address} returned invalid data')
            self._cyclic_update_active = False
            return

        # Remove noise
        if p_pv < 2:
            p_pv = 0

        # Put the date into the items
        for key, item in self._plg_item_dict.items():
            if self.get_iattr_value(item['item'].conf, 'fronius_data') == 'soc':
                item['item'](soc, self.get_fullname())
            if self.get_iattr_value(item['item'].conf, 'fronius_data') == 'p_grid':
                item['item'](p_grid, self.get_fullname())
            if self.get_iattr_value(item['item'].conf, 'fronius_data') == 'p_accu':
                item['item'](p_accu, self.get_fullname())
            if self.get_iattr_value(item['item'].conf, 'fronius_data') == 'p_load':
                item['item'](p_load, self.get_fullname())
            if self.get_iattr_value(item['item'].conf, 'fronius_data') == 'p_pv':
                item['item'](p_pv, self.get_fullname())

                # Calculate the day engery using db plugin. Check if p_pv item is in database.
                last_midnight = int(datetime.combine(datetime.today(), time.min).timestamp() * 1000)
                try:
                    self._p_pv_day = item['item'].db('integrate',last_midnight) / 3600000
                except Exception:
                    self.logger.error(f'Item {item} is not in database. Please add database: yes to the item file.')
            if self.get_iattr_value(item['item'].conf, 'fronius_data') == 'p_pv_day':
                item['item'](self._p_pv_day, self.get_fullname())

        # release lock
        self._cyclic_update_active = False

# ------------------------------ _midnight --------------------------------
# Called by the scheduler at midnight. Store the daily engergy sum
# into the database item if it exists.
# -----------------------------------------------------------------------------
    def _midnight(self):
        self.logger.debug('Midnight')
        self.logger.debug(self._p_pv_day)
        for key, item in self._plg_item_dict.items():
            if self.get_iattr_value(item['item'].conf, 'fronius_data') == 'p_pv_day_database':
                item['item'](self._p_pv_day, self.get_fullname())

