#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2022 De Filippis Ivan
# Copyright 2022 Ronny Schulz
# Copyright 2023 Bernd Meiners
#########################################################################
# This file is part of SmartHomeNG.
#
# Modbus_TCP plugin for SmartHomeNG
#
# SmartHomeNG is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# SmartHomeNG is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

from lib.model.smartplugin import SmartPlugin
from datetime import datetime
import threading

from .webif import WebInterface

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder

from pymodbus.client.tcp import ModbusTcpClient

import logging

AttrAddress = 'modBusAddress'
AttrType = 'modBusDataType'
AttrFactor = 'modBusFactor'
AttrByteOrder = 'modBusByteOrder'
AttrWordOrder = 'modBusWordOrder'
AttrSlaveUnit = 'modBusUnit'
AttrObjectType = 'modBusObjectType'
AttrDirection = 'modBusDirection'


class modbus_tcp(SmartPlugin):
    """
    This class provides a Plugin for SmarthomeNG to read and or write to modbus
    devices.
    """

    PLUGIN_VERSION = '1.0.13'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the Modbus TCP plugin.
        The parameters are retrieved from get_parameter_value(parameter_name)
        """

        self.logger.info('Init modbus_tcp plugin')

        # Disable logging from imported modul 'pymodbus'
        if not self.logger.isEnabledFor(logging.DEBUG):
            disable_logger = logging.getLogger('pymodbus')
            if disable_logger is not None:
                self.logger.info(f'change logging level from: {disable_logger} to CRITICAL')
                disable_logger.setLevel(logging.CRITICAL)

        # Call init code of parent class (SmartPlugin)
        super().__init__()

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
        self._slaveUnitRegisterDependend = False

        self._pause_item_path = self.get_parameter_value('pause_item')

        self._sh = sh
        self._regToRead = {}
        self._regToWrite = {}
        self._pollStatus = {}
        self.connected = False

        self._Mclient = ModbusTcpClient(self._host, port=self._port)
        self.lock = threading.Lock()

        self.init_webinterface(WebInterface)

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
        self.alive = False
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method called")
        self.scheduler_remove('poll_device_' + self._host)
        self._Mclient.close()
        self.connected = False
        self.logger.debug(f"Plugin '{self.get_fullname()}': stop method finished")

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference

        :param item:    The item to process.
        """

        # check for pause item
        if item.property.path == self._pause_item_path:
            self.logger.debug(f'pause item {item.property.path} registered')
            self._pause_item = item
            self.add_item(item, updating=True)
            return self.update_item

        if self.has_iattr(item.conf, AttrAddress):
            self.logger.debug(f"parse item: {item}")
            regAddr = int(self.get_iattr_value(item.conf, AttrAddress))

            objectType = 'HoldingRegister'
            value = item()
            dataType = 'uint16'
            factor = 1
            byteOrderStr = 'Endian.BIG'
            wordOrderStr = 'Endian.BIG'
            slaveUnit = self._slaveUnit
            dataDirection = 'read'

            if self.has_iattr(item.conf, AttrType):
                dataType = self.get_iattr_value(item.conf, AttrType)
            if self.has_iattr(item.conf, AttrSlaveUnit):
                slaveUnit = int(self.get_iattr_value(item.conf, AttrSlaveUnit))
                if (slaveUnit) != self._slaveUnit:
                    self._slaveUnitRegisterDependend = True
            if self.has_iattr(item.conf, AttrObjectType):
                objectType = self.get_iattr_value(item.conf, AttrObjectType)

            reg = str(objectType)  # dictionary key: objectType.regAddr.slaveUnit // HoldingRegister.528.1
            reg += '.'
            reg += str(regAddr)
            reg += '.'
            reg += str(slaveUnit)

            if self.has_iattr(item.conf, AttrDirection):
                dataDirection = self.get_iattr_value(item.conf, AttrDirection)
            if self.has_iattr(item.conf, AttrFactor):
                factor = float(self.get_iattr_value(item.conf, AttrFactor))
            if self.has_iattr(item.conf, AttrByteOrder):
                byteOrderStr = self.get_iattr_value(item.conf, AttrByteOrder)
            if self.has_iattr(item.conf, AttrWordOrder):
                wordOrderStr = self.get_iattr_value(item.conf, AttrWordOrder)

            try:    # den letzten Teil des Strings extrahieren, in Großbuchstaben und in Endian-Konstante wandeln
                byteOrder = Endian[(str(byteOrderStr).split('.')[-1]).upper()]
            except Exception as e:
                self.logger.warning(f"Invalid byteOrder -> default(Endian.BIG) is used. Error:{e}")
                byteOrder = Endian.BIG

            try:    # den letzten Teil des Strings extrahieren, in Großbuchstaben und in Endian-Konstante wandeln
                wordOrder = Endian[(str(wordOrderStr).split('.')[-1]).upper()]
            except Exception as e:
                self.logger.warning(f"Invalid byteOrder -> default(Endian.BIG) is used. Error:{e}")
                wordOrder = Endian.BIG

            regPara = {'regAddr': regAddr, 'slaveUnit': slaveUnit, 'dataType': dataType, 'factor': factor,
                       'byteOrder': byteOrder,
                       'wordOrder': wordOrder, 'item': item, 'value': value, 'objectType': objectType,
                       'dataDir': dataDirection}
            if dataDirection == 'read':
                self._regToRead.update({reg: regPara})
                self.logger.info(f"parse item: {item} Attributes {regPara}")
            elif dataDirection == 'read_write':
                self._regToRead.update({reg: regPara})
                self._regToWrite.update({reg: regPara})
                self.logger.info(f"parse item: {item} Attributes {regPara}")
                return self.update_item
            else:
                self.logger.warning("Invalid data direction -> default(read) is used")
                self._regToRead.update({reg: regPara})

    def log_error(self, message):
        """
        Logs an error message based on error count
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.error(message)
        else:
            if self.error_count < 10:
                self.logger.error(message)
            elif self.error_count < 100:
                if self.error_count % 10 == 0:
                    self.logger.error(f"{message} [Logging suppressed every 10th error]")
            else:
                if self.error_count % 100 == 0:
                    self.logger.error(f"{message} [Logging suppressed every 100th error]")

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        if not self.alive:
            return

        with self.lock:
            try:
                if self._Mclient.connect():
                    self.logger.debug(f"connected to {str(self._Mclient)}")
                    self.connected = True
                    self.error_count = 0
                else:
                    self.error_count += 1
                    # Logs an error message based on error count
                    self.log_error(f"could not connect to {self._host}:{self._port}, connection_attempts: {self.error_count}")
                    self.connected = False
                    return

            except Exception as e:
                self.error_count += 1
                # Logs an error message based on error count
                self.log_error(f"connection exception: {str(self._Mclient)} {e}, errors: {self.error_count}")
                self.connected = False
                return

        startTime = datetime.now()
        regCount = 0
        try:
            for reg, regPara in self._regToRead.items():
                with self.lock:
                    value = self.__read_Registers(regPara)
                    # self.logger.debug(f"value read: {value} type: {type(value)}")
                    if value is not None:
                        item = regPara['item']
                        if regPara['factor'] != 1:
                            value = value * regPara['factor']
                            # self.logger.debug(f"value {value} multiply by: {regPara['factor']}")
                        item(value, self.get_fullname())
                        regCount += 1

                        if 'read_dt' in regPara:
                            regPara['last_read_dt'] = regPara['read_dt']

                        if 'value' in regPara:
                            regPara['last_value'] = regPara['value']

                        regPara['read_dt'] = datetime.now()
                        regPara['value'] = value
            endTime = datetime.now()
            duration = endTime - startTime
            if regCount > 0:
                self._pollStatus['last_dt'] = datetime.now()
                self._pollStatus['regCount'] = regCount
            self.logger.debug(f"poll_device: {regCount} register read required {duration} seconds")
        except Exception as e:
            self.logger.error(f"something went wrong in the poll_device function: {e}")

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
        objectType = 'HoldingRegister'
        slaveUnit = self._slaveUnit
        dataDirection = 'read'

        # check for pause item
        if item is self._pause_item:
            if caller != self.get_shortname():
                self.logger.debug(f'pause item changed to {item()}')
                if item() and self.alive:
                    self.stop()
                elif not item() and not self.alive:
                    self.run()
            return

        if caller == self.get_fullname():
            # self.logger.debug(f'item was changed by the plugin itself - caller:{caller} source:{source} dest:{dest}')
            return

        if self.has_iattr(item.conf, AttrDirection):
            dataDirection = self.get_iattr_value(item.conf, AttrDirection)
            if not dataDirection == 'read_write':
                self.logger.debug(f'update_item: {item} Writing is not allowed - selected dataDirection:{dataDirection}')
                return
            # else:
            #    self.logger.debug(f'update_item:{item} dataDirection: {dataDirection}')
            if self.has_iattr(item.conf, AttrAddress):
                regAddr = int(self.get_iattr_value(item.conf, AttrAddress))
            else:
                self.logger.warning(f'update_item:{item} Item has no register address')
                return
            if self.has_iattr(item.conf, AttrSlaveUnit):
                slaveUnit = int(self.get_iattr_value(item.conf, AttrSlaveUnit))
                if (slaveUnit) != self._slaveUnit:
                    self._slaveUnitRegisterDependend = True
            if self.has_iattr(item.conf, AttrObjectType):
                objectType = self.get_iattr_value(item.conf, AttrObjectType)
            # else:
                # self.logger.debug(f'update_item:{item} default modBusObjectTyp: {objectType}')

            reg = str(objectType)  # Dict-key: HoldingRegister.528.1 *** objectType.regAddr.slaveUnit ***
            reg += '.'
            reg += str(regAddr)
            reg += '.'
            reg += str(slaveUnit)
            if reg in self._regToWrite:
                with self.lock:
                    regPara = self._regToWrite[reg]
                    self.logger.debug(f'update_item:{item} value:{item()} regToWrite: {reg}')
                    try:
                        if self._Mclient.connect():
                            self.logger.debug(f"connected to {str(self._Mclient)}")
                            self.connected = True
                            self.error_count = 0
                        else:
                            self.error_count += 1
                            # Logs an error message based on error count
                            self.log_error(f"could not connect to {self._host}:{self._port}, connection_attempts: {self.error_count}")
                            self.connected = False
                            return

                    except Exception as e:
                        self.error_count += 1
                        # Logs an error message based on error count
                        self.log_error(f"connection exception: {str(self._Mclient)} {e}, errors: {self.error_count}")
                        self.connected = False
                        return

                    try:
                        self.__write_Registers(regPara, item())
                    except Exception as e:
                        self.logger.error(f"something went wrong in the __write_Registers function: {e}")

    def __write_Registers(self, regPara, value):
        objectType = regPara['objectType']
        address = regPara['regAddr']
        slaveUnit = regPara['slaveUnit']
        bo = regPara['byteOrder']
        wo = regPara['wordOrder']
        dataTypeStr = regPara['dataType']
        dataType = ''.join(filter(str.isalpha, dataTypeStr))  # vom dataType die Ziffen entfernen z.B. uint16 = uint

        try:
            bits = int(''.join(filter(str.isdigit, dataTypeStr)))  # bit-Zahl aus aus dataType z.B. uint16 = 16
        except:
            bits = 16

        if regPara['factor'] != 1:
            # self.logger.debug(f"value {value} divided by: {regPara['factor']}")
            value = value * (1 / regPara['factor'])

        self.logger.debug(f"write {value} to {objectType}.{address}.{address} (address.slaveUnit) dataType:{dataTypeStr}")
        builder = BinaryPayloadBuilder(byteorder=bo, wordorder=wo)

        if dataType.lower() == 'uint':
            if bits == 16:
                builder.add_16bit_uint(int(value))
            elif bits == 32:
                builder.add_32bit_uint(int(value))
            elif bits == 64:
                builder.add_64bit_uint(int(value))
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
        elif dataType.lower() == 'int':
            if bits == 16:
                builder.add_16bit_int(int(value))
            elif bits == 32:
                builder.add_32bit_int(int(value))
            elif bits == 64:
                builder.add_64bit_int(int(value))
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
        elif dataType.lower() == 'float':
            if bits == 32:
                builder.add_32bit_float(value)
            elif bits == 64:
                builder.add_64bit_float(value)
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
        elif dataType.lower() == 'string':
            builder.add_string(value)
        elif dataType.lower() == 'bit':
            if objectType == 'Coil' or objectType == 'DiscreteInput':
                if not isinstance(value, bool):  # test is boolean
                    self.logger.error(f"Value is not boolean: {value}")
                    return
            else:
                if set(value).issubset({'0', '1'}) and bool(value):  # test is bit-string '00110101'
                    builder.add_bits(value)
                else:
                    self.logger.error(f"Value is not a bitstring: {value}")
        else:
            self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
            return None

        if objectType == 'Coil':
            result = self._Mclient.write_coil(address, value, slave=slaveUnit)
        elif objectType == 'HoldingRegister':
            registers = builder.to_registers()
            result = self._Mclient.write_registers(address, registers, slave=slaveUnit)
        elif objectType == 'DiscreteInput':
            self.logger.warning(f"this object type cannot be written {objectType}:{address} slaveUnit:{slaveUnit}")
            return
        elif objectType == 'InputRegister':
            self.logger.warning(f"this object type cannot be written {objectType}:{address} slaveUnit:{slaveUnit}")
            return
        else:
            return
        if result.isError():
            self.logger.error(f"write error: {result} {objectType}.{address}.{slaveUnit} (address.slaveUnit)")
            return None

        if 'write_dt' in regPara:
            regPara['last_write_dt'] = regPara['write_dt']
            regPara['write_dt'] = datetime.now()
        else:
            regPara.update({'write_dt': datetime.now()})

        if 'write_value' in regPara:
            regPara['last_write_value'] = regPara['write_value']
            regPara['write_value'] = value
        else:
            regPara.update({'write_value': value})

        # regPara['write_dt'] = datetime.now()
        # regPara['write_value'] = value

    def __read_Registers(self, regPara):
        objectType = regPara['objectType']
        dataTypeStr = regPara['dataType']
        dataType = ''.join(filter(str.isalpha, dataTypeStr))
        bo = regPara['byteOrder']
        wo = regPara['wordOrder']
        slaveUnit = regPara['slaveUnit']
        registerCount = 0
        address = regPara['regAddr']
        value = None

        try:
            bits = int(''.join(filter(str.isdigit, dataTypeStr)))
        except:
            bits = 16

        if dataType.lower() == 'string':
            registerCount = int(bits / 2)  # bei string: bits = bytes !! string16 -> 16Byte - 8 registerCount
        else:
            registerCount = int(bits / 16)

        if not self.connected:
            self.logger.error(f"not connected to {self._host}:{self._port}")
            return

        # self.logger.debug(f"read {objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount}")
        if objectType == 'Coil':
            result = self._Mclient.read_coils(address, registerCount, slave=slaveUnit)
        elif objectType == 'DiscreteInput':
            result = self._Mclient.read_discrete_inputs(address, registerCount, slave=slaveUnit)
        elif objectType == 'InputRegister':
            result = self._Mclient.read_input_registers(address, registerCount, slave=slaveUnit)
        elif objectType == 'HoldingRegister':
            result = self._Mclient.read_holding_registers(address, registerCount, slave=slaveUnit)
        else:
            self.logger.error(f"{AttrObjectType} not supported: {objectType}")
            return

        if result.isError():
            self.logger.error(f"read error: {result} {objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount}")
            return

        if objectType == 'Coil':
            value = result.bits[0]
        elif objectType == 'DiscreteInput':
            value = result.bits[0]
        elif objectType == 'InputRegister':
            decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=bo, wordorder=wo)
        else:
            decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=bo, wordorder=wo)

        self.logger.debug(f"read {objectType}.{address}.{slaveUnit} (address.slaveUnit) regCount:{registerCount} result:{result}")

        if dataType.lower() == 'uint':
            if bits == 16:
                return decoder.decode_16bit_uint()
            elif bits == 32:
                return decoder.decode_32bit_uint()
            elif bits == 64:
                return decoder.decode_64bit_uint()
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
        elif dataType.lower() == 'int':
            if bits == 16:
                return decoder.decode_16bit_int()
            elif bits == 32:
                return decoder.decode_32bit_int()
            elif bits == 64:
                return decoder.decode_64bit_int()
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
        elif dataType.lower() == 'float':
            if bits == 32:
                return decoder.decode_32bit_float()
            elif bits == 64:
                return decoder.decode_64bit_float()
            else:
                self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
        elif dataType.lower() == 'string':
            # bei string: bits = bytes !! string16 -> 16Byte
            ret = decoder.decode_string(bits)
            return str(ret, 'ASCII')
        elif dataType.lower() == 'bit':
            if objectType == 'Coil' or objectType == 'DiscreteInput':
                # self.logger.debug(f"read bit value: {value}")
                return value
            else:
                self.logger.debug(f"read bits values: {value.decode_bits()}")
                return decoder.decode_bits()
        else:
            self.logger.error(f"Number of bits or datatype not supported : {dataTypeStr}")
