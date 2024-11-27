#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
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

from lib.model.smartplugin import SmartPlugin
from lib.item import Items

from .webif import WebInterface

import smbus

class piusv(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items
    """
    # Handle
    piusv_handle = smbus.SMBus(1)

    PLUGIN_VERSION = '0.1.0'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object anymore.

        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._item_dict = {}
        self._cyclic_update_active = False
        self.alive = False

        # check if shNG is running on Raspberry Pi
        try:
            self.webif_pagelength = self.get_parameter_value('webif_pagelength')
            self.poll_cycle = self.get_parameter_value('poll_cycle')
            self.i2c_address = self.get_parameter_value('i2c_address')
        except KeyError as e:
            self.logger.critical("Plugin '{}': Inconsistent plugin (invalid metadata definition: {} not defined)".format(self.get_shortname(), e))
            self._init_complete = False
            return

        self.init_webinterface(WebInterface)
        return

####################################################################################
# Die Parameter der Pi USV+ byteweise auslesen
    def get_parameter(self, index):
        parameters = [0,0,0,0,0,0,0,0,0,0]

        try:
            self.piusv_handle.write_byte(self.i2c_address, 0x02)
        except (IOError):
            self.logger.error("get_parameter: error writing to piusv")
            return(0)
        for i in range(10):
            try:
                parameters[i] = self.piusv_handle.read_byte(self.i2c_address)
            except (IOError):
                self.logger.error("get_parameter: error reading to piusv")
                return(0)
        value = 256*parameters[index] + parameters[index+1]
        return value

# Statusbyte auslesen 
    def get_status(self):

        try:
            self.piusv_handle.write_byte(self.i2c_address, 0x00)
        except (IOError):
            self.logger.error("get_status: error writing to piusv")
            return(0)
        try:
            status = self.piusv_handle.read_byte(self.i2c_address)
        except (IOError):
            self.logger.error("get_status: error reading to piusv")
            return(0)
        return status
 
# Firmware auslesen 
    def get_firmware(self):

        version = ''
        try:
            self.piusv_handle.write_byte(self.i2c_address, 0x01)
        except (IOError):
            self.logger.error("get_get_firmware: error writing to piusv")
            return(0)
        for i in range (12):
            try:
                version = version + chr(self.piusv_handle.read_byte(self.i2c_address))
            except (IOError):
                self.logger.error("get_firmware: error reading to piusv")
                return(0)
        return version
###############################################################################
    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('poll_device', self.poll_device, cycle=self.poll_cycle)
        self.alive = True

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
        the item in the future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, 'piusv_func'):
            self.logger.debug(f"parse item: {item}")
            self._item_dict[item] = self.get_iattr_value(item.conf, 'piusv_func')

        elif self.has_iattr(item.conf, 'piusv_sys'):
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped and only, if the item has not been changed by this plugin:
            self.logger.info(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.has_iattr(item.conf, 'piusv_sys'):
                self.logger.debug(f"update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")
                if self.get_iattr_value(item.conf, 'piusv_sys') == 'update' and bool(item()):
                    self.logger.info(f"Update of all items of piusv Plugin requested. ")
                    self.poll_device()
                    item(False)
            pass

    def poll_device(self):
        """
        Polls for updates of the device
        """
        # check if another cyclic cmd run is still active
        if self._cyclic_update_active:
            self.logger.warning('Triggered cyclic poll_device, but previous cyclic run is still active. Therefore request will be skipped.')
            return
        else:
            self.logger.info('Triggering cyclic poll_device')

        # set lock
        self._cyclic_update_active = True

        for item in self._item_dict:
            # self.logger.debug(f"poll_device: handle item {item.id()}")
            value = eval(f"self.{self.get_iattr_value(item.conf, 'piusv_func')}()")
            # self.logger.info(f"poll_device: {value=} for item {item.id()} will be set.")
            item(value, self.get_shortname())

        # release lock
        self._cyclic_update_active = False

        pass

    def v_batt(self):
        return self.get_parameter(0)

    def i_rasp(self):
        return self.get_parameter(2)

    def u_rasp(self):
        return self.get_parameter(4)

    def u_usb(self):
        return self.get_parameter(6)

    def u_ext(self):
        return self.get_parameter(8)

    def piusv_status(self):
        return self.get_status()

    def piusv_firmware(self):
#        return 'hallo'
        return self.get_firmware()

    @property
    def item_list(self):
        return list(self._item_dict.keys())

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()

    @property
    def rpi_sn(self):
        return '1234'

