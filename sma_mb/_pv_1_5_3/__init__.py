#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2017-      Klaus Bühl                           kla.b@gmx.de
#  Copyright 2021-      Martin Sinn                         m.sinn@gmx.de
#  Copyright 2022-      Ronny Schulz                      r.schulz@gmx.de
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

from .webif import WebInterface

import time

# pymodbus library from https://github.com/riptideio/pymodbus
from pymodbus.version import version
pymodbus_baseversion = int(version.short().split('.')[0])

if pymodbus_baseversion > 2:
    # for newer versions of pymodbus
    from pymodbus.client.tcp import ModbusTcpClient
else:
    # for older versions of pymodbus
    from pymodbus.client.sync import ModbusTcpClient

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder

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

    PLUGIN_VERSION = '1.5.3'    # (must match the version specified in plugin.yaml), use '1.0.0' for your initial plugin Release

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

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        self._cycle = self.get_parameter_value('cycle')

        # Initialization code goes here

        self._items = {}
        self._datatypes = {}

        self.init_webinterface(WebInterface)
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        self.scheduler_add('poll_SMAModbus', self.poll_device, cycle=self._cycle)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_SMAModbus')
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
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        client = ModbusTcpClient(self._host, self._port)
        if not client.connect():
            self.logger.warning(
                f"poll_device: Unable to establish connection to host {self._host}")
            return

        for read_parameter in self._items:

            if self._datatypes[read_parameter] in ['S32', 'U32']:
                register_count = 2
            elif self._datatypes[read_parameter] in ['S16', 'U16']:
                register_count = 1
            elif self._datatypes[read_parameter] in ['S64', 'U64']:
                register_count = 4
            elif self._datatypes[read_parameter] == 'STR08':
                register_count = 8
            elif self._datatypes[read_parameter] == 'STR12':
                register_count = 12
            elif self._datatypes[read_parameter] == 'STR16':
                register_count = 16
            else:
                register_count = 2
            try:
                if pymodbus_baseversion > 2:
                    result = client.read_holding_registers((int(read_parameter)), register_count, slave=3)
                else:
                    result = client.read_holding_registers((int(read_parameter)), register_count, unit=3)
            except Exception as e:
                self.logger.error(f"poll_device: Item {self._items[read_parameter].property.path} - Error trying to get result, got Exception {e}")
            else:
                decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=Endian.Big)
                if self._datatypes[read_parameter] == 'S16':
                    decoded = {'value': decoder.decode_16bit_int()}
                elif self._datatypes[read_parameter] == 'U16':
                    decoded = {'value': decoder.decode_16bit_uint()}
                elif self._datatypes[read_parameter] == 'S32':
                    sint = decoder.decode_32bit_int()
                    if sint == -2147483648:
                        sint = 0
                    decoded = {'value': sint}
                elif self._datatypes[read_parameter] == 'U32':
                    decoded = {'value': decoder.decode_32bit_uint()}
                elif self._datatypes[read_parameter] == 'S64':
                    decoded = {'value': decoder.decode_64bit_int()}
                elif self._datatypes[read_parameter] == 'U64':
                    decoded = {'value': decoder.decode_64bit_uint()}
                elif self._datatypes[read_parameter] == 'STR08':
                    decoded = {'value': decoder.decode_string(size=16).rstrip(b'\0').decode('utf-8')}
                elif self._datatypes[read_parameter] == 'STR12':
                    decoded = {'value': decoder.decode_string(size=24).rstrip(b'\0').decode('utf-8')}
                elif self._datatypes[read_parameter] == 'STR16':
                    decoded = {'value': decoder.decode_string(size=32).rstrip(b'\0').decode('utf-8')}
                else:
                    decoded = {'value': decoder.decode_32bit_uint()}

                valueend = decoded.get("value")
                self.logger.debug(f"value is {valueend} key is {read_parameter} self._item is {self._items[read_parameter].property.path}")
                if read_parameter in self._items:
                    #  self. logger.debug("update item {0} with {1}".format(self._items[read_parameter], value))
                    item = self._items[read_parameter]
                    item(valueend, self.get_shortname(), source='smamb_register')

        client.close()
        return

