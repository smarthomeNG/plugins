#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022 De Filippis Ivan
#  Copyright 2022 Ronny Schulz
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
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

from lib.model.smartplugin import *
from lib.item import Items
from datetime import datetime
import threading

from .webif import WebInterface

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.payload import BinaryPayloadBuilder

# pymodbus library from https://github.com/riptideio/pymodbus
from pymodbus.version import version
pymodbus_baseversion = int(version.short().split('.')[0])

if pymodbus_baseversion > 2:
    # for newer versions of pymodbus
    from pymodbus.client.tcp import ModbusTcpClient
else:
    # for older versions of pymodbus
    from pymodbus.client.sync import ModbusTcpClient

AttrAddress = 'modBusAddress'
AttrType = 'modBusDataType'
AttrFactor = 'modBusFactor'
AttrByteOrder = 'modBusByteOrder'
AttrWordOrder = 'modBusWordOrder'
AttrSlaveUnit = 'modBusUnit'
AttrObjectType = 'modBusObjectType'
AttrDirection = 'modBusDirection'

class modbus_tcp(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = '1.0.8'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        :param sh:  The instance of the smarthome object, save it for later references
        """

        self.logger.info('Init modbus_tcp plugin')

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self._host = self.get_parameter_value('host')
        self._port = int(self.get_parameter_value('port'))
        self._cycle = int(self.get_parameter_value('cycle'))
        self._slaveUnit = int(self.get_parameter_value('slaveUnit'))
        self._slaveUnitRegisterDependend = False

        self._sh = sh
        self._regToRead = {}
        self._regToWrite = {}
        self._pollStatus = {}
        self.connected = False

        self._Mclient = ModbusTcpClient(self._host, port=self._port)
        self.lock = threading.Lock()

        self.init_webinterface(WebInterface)


        return

    def run(self):
        """
        Run method for the plugin
        """
        self._sh.scheduler.add('modbusTCP_poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.logger.debug("stop modbus_tcp plugin")
        self.scheduler_remove('modbusTCP_poll_device')
        self._Mclient.close()
        self.connected = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference

        :param item:    The item to process.
        """
        if self.has_iattr(item.conf, AttrAddress):
            self.logger.debug("parse item: {0}".format(item))
            regAddr = int(self.get_iattr_value(item.conf, AttrAddress))

            objectType = 'HoldingRegister'
            value = item()
            dataType = 'uint16'
            factor = 1
            byteOrder = 'Endian.Big'
            wordOrder = 'Endian.Big'
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

            reg = str(objectType)   # dictionary key: objectType.regAddr.slaveUnit // HoldingRegister.528.1
            reg += '.'
            reg += str(regAddr)
            reg += '.'
            reg += str(slaveUnit)

            if self.has_iattr(item.conf, AttrDirection):
                dataDirection = self.get_iattr_value(item.conf, AttrDirection)
            if self.has_iattr(item.conf, AttrFactor):
                factor = float(self.get_iattr_value(item.conf, AttrFactor))
            if self.has_iattr(item.conf, AttrByteOrder):
                byteOrder = self.get_iattr_value(item.conf, AttrByteOrder)
            if self.has_iattr(item.conf, AttrWordOrder):
                wordOrder = self.get_iattr_value(item.conf, AttrWordOrder)
            if byteOrder == 'Endian.Big':   # Von String in Endian-Konstante "umwandeln"
                byteOrder = Endian.Big
            elif byteOrder == 'Endian.Little':
                byteOrder = Endian.Little
            else:
                byteOrder = Endian.Big
                self.logger.warning("Invalid byte order -> default(Endian.Big) is used")
            if wordOrder == 'Endian.Big':   # Von String in Endian-Konstante "umwandeln"
                wordOrder = Endian.Big
            elif wordOrder == 'Endian.Little':
                wordOrder = Endian.Little
            else:
                wordOrder = Endian.Big
                self.logger.warning("Invalid byte order -> default(Endian.Big) is used")

            regPara = {'regAddr': regAddr, 'slaveUnit': slaveUnit, 'dataType': dataType, 'factor': factor, 'byteOrder': byteOrder,
                       'wordOrder': wordOrder, 'item': item, 'value': value, 'objectType': objectType, 'dataDir': dataDirection }
            if dataDirection == 'read':
                self._regToRead.update({reg: regPara})
                self.logger.info("parse item: {0} Attributes {1}".format(item, regPara))
            elif dataDirection == 'read_write':
                self._regToRead.update({reg: regPara})
                self._regToWrite.update({reg: regPara})
                self.logger.info("parse item: {0} Attributes {1}".format(item, regPara))
                return self.update_item
            else:
                 self.logger.warning("Invalid data direction -> default(read) is used")
                 self._regToRead.update({reg: regPara})

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """

        with self.lock:
            try:
                if self._Mclient.connect():
                    self.logger.info("connected to {0}".format(str(self._Mclient)))
                    self.connected = True
                else:
                    self.logger.error("could not connect to {0}:{1}".format(self._host, self._port))
                    self.connected = False
                    return

            except Exception as e:
                self.logger.error("connection expection: {0} {1}".format(str(self._Mclient), e))
                self.connected = False
                return


        startTime = datetime.now()
        regCount = 0
        try:
            for reg, regPara in self._regToRead.items():
                with self.lock:
                    regAddr = regPara['regAddr']
                    value = self.__read_Registers(regPara)
                    #self.logger.debug("value readed: {0} type: {1}".format(value, type(value)))
                    if value is not None:
                        item = regPara['item']
                        if regPara['factor'] != 1:
                            value = value * regPara['factor']
                            #self.logger.debug("value {0} multiply by: {1}".format(value, regPara['factor']))
                        item(value, self.get_fullname())
                        regCount+=1

                        if 'read_dt' in regPara:
                            regPara['last_read_dt'] = regPara['read_dt']

                        if 'value' in regPara:
                            regPara['last_value'] = regPara['value']

                        regPara['read_dt'] = datetime.now()
                        regPara['value'] = value
            endTime = datetime.now()
            duration = endTime - startTime
            if regCount > 0:
                self._pollStatus['last_dt']=datetime.now()
                self._pollStatus['regCount']=regCount
            self.logger.debug("poll_device: {0} register readed requed-time: {1}".format(regCount, duration))
        except Exception as e:
            self.logger.error("something went wrong in the poll_device function: {0}".format(e))

     # called each time an item changes.
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


        if caller == self.get_fullname():
            #self.logger.debug('item was changed by the plugin itself - caller:{0} source:{1} dest:{2} '.format(caller, source, dest))
            return

        if self.has_iattr(item.conf, AttrDirection):
            dataDirection = self.get_iattr_value(item.conf, AttrDirection)
            if not dataDirection == 'read_write':
                self.logger.debug('update_item:{0} Writing is not allowed - selected dataDirection:{1}'.format(item, dataDirection))
                return
            #else:
            #    self.logger.debug('update_item:{0} dataDirection:{1}'.format(item, dataDirection))
            if self.has_iattr(item.conf, AttrAddress):
                regAddr = int(self.get_iattr_value(item.conf, AttrAddress))
            else:
                self.logger.warning('update_item:{0} Item has no register address'.format(item))
                return
            if self.has_iattr(item.conf, AttrSlaveUnit):
                slaveUnit = int(self.get_iattr_value(item.conf, AttrSlaveUnit))
                if (slaveUnit) != self._slaveUnit:
                    self._slaveUnitRegisterDependend = True
            if self.has_iattr(item.conf, AttrObjectType):
                objectType = self.get_iattr_value(item.conf, AttrObjectType)
            else:
                return

            reg = str(objectType)   # Dict-key: HoldingRegister.528.1 *** objectType.regAddr.slaveUnit ***
            reg += '.'
            reg += str(regAddr)
            reg += '.'
            reg += str(slaveUnit)
            if reg in self._regToWrite:
                with self.lock:
                    regPara = self._regToWrite[reg]
                    self.logger.debug('update_item:{0} value:{1} regToWrite:{2}'.format(item, item(), reg))
                    try:
                        if self._Mclient.connect():
                            self.logger.info("connected to {0}".format(str(self._Mclient)))
                            self.connected = True
                        else:
                            self.logger.error("could not connect to {0}:{1}".format(self._host, self._port))
                            self.connected = False
                            return

                    except Exception as e:
                        self.logger.error("connection expection: {0} {1}".format(str(self._Mclient), e))
                        self.connected = False
                        return

                    startTime = datetime.now()
                    regCount = 0
                    try:
                        self.__write_Registers(regPara, item())
                    except Exception as e:
                        self.logger.error("something went wrong in the __write_Registers function: {0}".format(e))

    def __write_Registers(self, regPara, value):
        objectType = regPara['objectType']
        address = regPara['regAddr']
        slaveUnit = regPara['slaveUnit']
        bo = regPara['byteOrder']
        wo = regPara['wordOrder']
        dataTypeStr = regPara['dataType']
        dataType = ''.join(filter(str.isalpha, dataTypeStr))    # vom dataType die Ziffen entfernen z.B. uint16 = uint
        registerCount = 0   # Anzahl der zu schreibenden Register (Words)

        try:
            bits = int(''.join(filter(str.isdigit, dataTypeStr)))  # bit-Zahl aus aus dataType z.B. uint16 = 16
        except:
            bits = 16

        if dataType.lower() == 'string':
            registerCount = int(bits/2)  # bei string: bits = bytes !! string16 -> 16Byte - 8 registerCount
        else:
            registerCount = int(bits/16)

        if regPara['factor'] != 1:
            #self.logger.debug("value {0} divided by: {1}".format(value, regPara['factor']))
            value = value * (1/regPara['factor'])

        self.logger.debug("write {0} to {1}.{2}.{3} (address.slaveUnit) dataType:{4}".format(value, objectType, address, slaveUnit, dataTypeStr))
        builder = BinaryPayloadBuilder(byteorder=bo, wordorder=wo)

        if dataType.lower() == 'uint':
            if bits == 16:
                builder.add_16bit_uint(int(value))
            elif bits == 32:
                builder.add_32bit_uint(int(value))
            elif bits == 64:
                builder.add_64bit_uint(int(value))
            else:
                self.logger.error("Number of bits or datatype not supported : {0}".format(dataTypeStr))
        elif dataType.lower() == 'int':
            if bits == 16:
                builder.add_16bit_int(int(value))
            elif bits == 32:
                builder.add_32bit_int(int(value))
            elif bits == 64:
                builder.add_64bit_int(int(value))
            else:
                self.logger.error("Number of bits or datatype not supported : {0}".format(dataTypeStr))
        elif dataType.lower() == 'float':
            if bits == 32:
                 builder.add_32bit_float(value)
            if bits == 64:
                 builder.add_64bit_float(value)
            else:
                self.logger.error("Number of bits or datatype not supported : {0}".format(dataTypeStr))
        elif dataType.lower() == 'string':
            builder.add_string(value)
        elif dataType.lower() == 'bit':
            if objectType == 'Coil' or objectType == 'DiscreteInput':
                if not type(value) == type(True):   # test is boolean
                    self.logger.error("Value is not boolean: {0}".format(value))
                    return
            else:
                if set(value).issubset({'0', '1'}) and bool(value):   # test is bit-string '00110101'
                    builder.add_bits(value)
                else:
                    self.logger.error("Value is not a bitstring: {0}".format(value))
        else:
            self.logger.error("Number of bits or datatype not supported : {0}".format(dataTypeStr))
            return None

        if objectType == 'Coil':
            result = self._Mclient.write_coil(address, value, unit=slaveUnit)
        elif objectType == 'HoldingRegister':
            registers = builder.to_registers()
            result = self._Mclient.write_registers(address, registers, unit=slaveUnit)
        elif objectType == 'DiscreteInput':
            self.logger.warning("this object type cannot be written {0}:{1} slaveUnit:{2}".format(objectType, address, slaveUnit))
            return
        elif objectType == 'InputRegister':
            self.logger.warning("this object type cannot be written {0}:{1} slaveUnit:{2}".format(objectType, address, slaveUnit))
            return
        else:
            return
        if result.isError():
            self.logger.error("write error: {0} {1}.{2}.{3} (address.slaveUnit)".format(result, objectType, address, slaveUnit))
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

        #regPara['write_dt'] = datetime.now()
        #regPara['write_value'] = value


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
            registerCount = int(bits/2)  # bei string: bits = bytes !! string16 -> 16Byte - 8 registerCount
        else:
            registerCount = int(bits/16)

        if self.connected == False:
            self.logger.error(" not connect {0}:{1}".format(self._host, self._port))
            return None

        #self.logger.debug("read {0}.{1}.{2} (address.slaveUnit) regCount:{3}".format(objectType, address, slaveUnit, registerCount))
        if objectType == 'Coil':
            if pymodbus_baseversion > 2:
                result = self._Mclient.read_coils(address, registerCount, slave=slaveUnit)
            else:
                result = self._Mclient.read_coils(address, registerCount, unit=slaveUnit)
        elif objectType == 'DiscreteInput':
            if pymodbus_baseversion > 2:
                result = self._Mclient.read_discrete_inputs(address, registerCount, slave=slaveUnit)
            else:
                result = self._Mclient.read_discrete_inputs(address, registerCount, unit=slaveUnit)
        elif objectType == 'InputRegister':
            if pymodbus_baseversion > 2:
                result = self._Mclient.read_input_registers(address, registerCount, slave=slaveUnit)
            else:
                result = self._Mclient.read_input_registers(address, registerCount, unit=slaveUnit)
        elif objectType == 'HoldingRegister':
            if pymodbus_baseversion > 2:
                result = self._Mclient.read_holding_registers(address, registerCount, slave=slaveUnit)
            else:
                result = self._Mclient.read_holding_registers(address, registerCount, unit=slaveUnit)
        else:
            self.logger.error("{0} not supported: {1}".format(AttrObjectType, objectType))
            return None

        if result.isError():
            self.logger.error("read error: {0} {1}.{2}.{3} (address.slaveUnit) regCount:{4}".format(result, objectType, address, slaveUnit, registerCount))
            return None

        if objectType == 'Coil':
            value = result.bits[0]
        elif objectType == 'DiscreteInput':
            value = result.bits[0]
        elif objectType == 'InputRegister':
            decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=bo,wordorder=wo)
        else:
            decoder = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=bo,wordorder=wo)

        self.logger.debug("read {0}.{1}.{2} (address.slaveUnit) regCount:{3} result:{4}".format(objectType, address, slaveUnit, registerCount, result))

        if dataType.lower() == 'uint':
            if bits == 16:
                return decoder.decode_16bit_uint()
            elif bits == 32:
                return decoder.decode_32bit_uint()
            elif bits == 64:
                return decoder.decode_64bit_uint()
            else:
                self.logger.error("Number of bits or datatype not supported : {0}".format(dataTypeStr))
        elif dataType.lower() == 'int':
            if bits == 16:
                return decoder.decode_16bit_int()
            elif bits == 32:
                return decoder.decode_32bit_int()
            elif bits == 64:
                return decoder.decode_64bit_int()
            else:
                self.logger.error("Number of bits or datatype not supported : {0}".format(dataTypeStr))
        elif dataType.lower() == 'float':
            if bits == 32:
                return decoder.decode_32bit_float()
            if bits == 64:
                return decoder.decode_64bit_float()
            else:
                self.logger.error("Number of bits or datatype not supported : {0}".format(dataTypeStr))
        elif dataType.lower() == 'string':
            # bei string: bits = bytes !! string16 -> 16Byte
            ret = decoder.decode_string(bits)
            return str( ret, 'ASCII')
        elif dataType.lower() == 'bit':
            if objectType == 'Coil' or objectType == 'DiscreteInput':
                #self.logger.debug("readed bit value: {0}".format(value))
                return value
            else:
                self.logger.debug("readed bits values: {0}".format(value.decode_bits()))
                return decoder.decode_bits()
        else:
            self.logger.error("Number of bits or datatype not supported : {0}".format(dataTypeStr))
        return None
