#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2017-      Klaus Bühl                           kla.b@gmx.de
# Copyright 2021-      Martin Sinn                         m.sinn@gmx.de
# Copyright 2022-      Ronny Schulz                      r.schulz@gmx.de
# Copyright 2025       Bernd Meiners
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Plugin for the software SmartHomeNG, which allows to read
#  devices such as the SMA Inverter
#
#  Free for non-commercial use
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
import threading

from .webif import WebInterface

import time

from pymodbus.client.tcp import ModbusTcpClient
from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.exceptions import ModbusException

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory

class SMAModbus(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items

    HINT: Please have a look at the SmartPlugin class to see which
    class properties and methods (class variables and class functions)
    are already available!
    """

    PLUGIN_VERSION = '1.6.0'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

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
        self._host = self.get_parameter_value('host')
        self._port = self.get_parameter_value('port')

        self._cycle = self.get_parameter_value('cycle')      # the frequency in seconds how often the device should be accessed
        if self._cycle == 0:
            self._cycle = None
        self._crontab = self.get_parameter_value('crontab')  # the more complex way to specify the device query frequency
        if self._crontab == '':
            self._crontab = None
        if not (self._cycle or self._crontab):
            self.logger.error(f"{self.get_fullname()}: no update cycle or crontab set. Modbus will not be queried automatically")

        self._slaveUnit = self.get_parameter_value('slaveUnit')


        # Initialization code goes here
        self.lock = threading.Lock()
        self._items = {}
        self._datatypes = {}

        self.init_webinterface(WebInterface)
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method called")
        if self.alive: 
            return

        self.alive = True

        if self._cycle or self._crontab:
            self.error_count = 0  # Initialize error count
            self.scheduler_add('poll_device_' + self._host, self.poll_device, cycle=self._cycle, cron=self._crontab, prio=5)
        self.logger.debug(f"Plugin '{self.get_fullname()}': run method finished ")
        
    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")
        self.alive = False
        self.scheduler_remove('poll_device_' + self._host)

        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method finished")


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
        if self.has_iattr(item.conf, 'smamb_register'):
            self.logger.debug(f"parse item: {item.property.path}")
            modbus_register = self.get_iattr_value(item.conf, 'smamb_register')
            modbus_datatype = self.get_iattr_value(item.conf, 'smamb_datatype')
            if modbus_datatype is None:
                modbus_datatype = 'U32'
                
            self._items[modbus_register]=item
            self._datatypes[modbus_register]=modbus_datatype
            self.logger.debug(f"item: {item.property.path} added with modbus_register '{modbus_register}', datatype '{modbus_datatype}'")
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
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info(f"Update item: {item}, item has been changed outside this plugin - writing to the device is not implemented")

            # if self.has_iattr(item.conf, 'foo_itemtag'):
            #     self.logger.debug(f"update_item was called with item {item} from caller {caller}, source {source} and dest {dest}")
            # pass

    def poll_device(self):
        """
        Polls for updates from the SMA modbus device

        This method is called by the scheduler which is set within run() method.
        """
        if self.lock.locked():
            self.logger.error(f"poll_device already called and not ready for next poll - please adjust cycle or crontab")
            return

        with self.lock:

            client = ModbusTcpClient(self._host, port=self._port) 

            MODBUS_EXCEPTIONS = {
                1: "Illegal Function",
                2: "Illegal Data Address",
                3: "Illegal Data Value",
                4: "Slave Device Failure",
                5: "Acknowledge",
                6: "Slave Device Busy",
                10: "Gateway Path Unavailable",
                11: "Gateway Target Device Failed to Respond"
            }
            
            if not client.connect():
                self.logger.warning(f"poll_device: Unable to establish connection to host {self._host}")
                return

            for modbus_address in self._items: 
                # shorten the datatype read parameter 
                dtype = self._datatypes[modbus_address]
                # get the size in bytes to read to register_count
                size_map = {
                    'S16': 1, 'U16': 1,
                    'S32': 2, 'U32': 2,
                    'S64': 4, 'U64': 4,
                    'STR08': 8, 'STR12': 12, 'STR16': 16 }
                register_count = size_map.get(dtype, 2)
                    
                try:
                    result = client.read_holding_registers((int(modbus_address)), count=register_count, slave=self._slaveUnit)

                    if result is None:
                        self.logger.warning(f"poll_device: result=None for register {modbus_address}")
                        continue
                    
                    if result.isError():
                        code = result.exception_code
                        msg = MODBUS_EXCEPTIONS.get(code, "Unknown error")
                        self.logger.error(f"Error code {code}: {msg} for register {modbus_address}")
                        continue
                    
                except ModbusException as e:
                    self.logger.error(f"ModbusException in poll_device(): Item {self._items[modbus_address].property.path} - Error trying to get result, got Exception {e}")

                except Exception as e:
                    self.logger.error(f"poll_device: Item {self._items[modbus_address].property.path} - Error trying to get result, got Exception {e}")
                else:
                    if dtype == 'S16':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.INT16)
                    elif dtype == 'U16':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.UINT16)
                    elif dtype == 'S32':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.INT32)
                        if value == -2147483648:
                            value = 0
                    elif dtype == 'U32':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.UINT32)
                    elif dtype == 'S64':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.INT64)
                    elif dtype == 'U64':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.UINT64)
                    elif dtype == 'STR08':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.STRING)
                    elif dtype == 'STR12':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.STRING)
                    elif dtype == 'STR16':
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.STRING)
                    else:
                        value = client.convert_from_registers(result.registers, data_type=client.DATATYPE.UINT32)

                    self.logger.debug(f"value is {value} key is {modbus_address} self._item is {self._items[modbus_address].property.path}")
                    if modbus_address in self._items:
                        #  self. logger.debug("update item {0} with {1}".format(self._items[modbus_address], value))
                        item = self._items[modbus_address]
                        item(value, self.get_shortname(), source='smamb_register')

            client.close()
            return

