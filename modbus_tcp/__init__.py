#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2021 De Filippis Ivan
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

from .webif import WebInterface

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.client.sync import ModbusTcpClient

AttrAddress = 'modBusAddress'
AttrType = 'modBusDataType'
AttrFactor = 'modBusFactor'
AttrByteOrder = 'modBusByteOrder'
AttrWordOrder = 'modBusWordOrder'
AttrSlaveUnit = 'modBusUnit'
AttrObjectType = 'modBusObjectType'

class modbus_tcp(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = '1.0.5'

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
        self._pollStatus = {}
        self.connected = False
        
        self._Mclient = ModbusTcpClient(self._host, port=self._port)
        
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
        #self.logger.debug("parse_item method called")
        if self.has_iattr(item.conf, AttrAddress):
            self.logger.debug("parse read item: {0}".format(item))
            objectType = 'HoldingRegister'
            regAddr = int(self.get_iattr_value(item.conf, AttrAddress))
            
            value = item()
            dataType = 'uint16'
            factor = 1
            byteOrder = 'Endian.Big'
            wordOrder = 'Endian.Big'
            slaveUnit = self._slaveUnit
            
            if self.has_iattr(item.conf, AttrType):
                dataType = self.get_iattr_value(item.conf, AttrType)
            if self.has_iattr(item.conf, AttrSlaveUnit):
                slaveUnit = int(self.get_iattr_value(item.conf, AttrSlaveUnit))
                if (slaveUnit) != self._slaveUnit:
                    self._slaveUnitRegisterDependend = True
            if self.has_iattr(item.conf, AttrObjectType):
                objectType = self.get_iattr_value(item.conf, AttrObjectType)
                
            reg = str(objectType)
            reg += '.'
            reg += str(regAddr)
            reg += '.'
            reg += str(slaveUnit)
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
                self.logger.error("Invalid byte order -> default(Endian.Big) is used : {0}".format(regParameters['byteOrder']))
            if wordOrder == 'Endian.Big':   # Von String in Endian-Konstante "umwandeln"
                wordOrder = Endian.Big
            elif wordOrder == 'Endian.Little':
                wordOrder = Endian.Little
            else:
                wordOrder = Endian.Big
                self.logger.error("Invalid byte order -> default(Endian.Big) is used : {0}".format(regParameters['wordOrder']))    
                
            
            
            regPara = {'regAddr': regAddr, 'slaveUnit': slaveUnit, 'dataType': dataType, 'factor': factor, 'byteOrder': byteOrder, 
                       'wordOrder': wordOrder, 'item': item, 'value': value, 'objectType': objectType }
                        
            self._regToRead.update({reg: regPara})
            
    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
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
                regAddr = regPara['regAddr']
                value = self.__read_Registers(regAddr, regPara)
                #self.logger.debug("value readed: {0} type: {1}".format(value, type(value)))
                if value is not None:
                    item = regPara['item']
                    if regPara['factor'] != 1:
                        value = value * regPara['factor']
                        #self.logger.debug("value {0} multiply by: {1}".format(value, regPara['factor']))
                    item(value)
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
        finally:
            self._Mclient.close()
            #self.connected = False
        
    def __read_Registers(self, address, regParameters):
        objectType = regParameters['objectType']
        dataTypeStr = regParameters['dataType']
        bo = regParameters['byteOrder']         
        wo = regParameters['wordOrder']
        dataType = ''.join(filter(str.isalpha, dataTypeStr))
        slaveUnit = regParameters['slaveUnit']
        registerCount = 0
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
            
        self.logger.debug("read {0}:{1} registerCount:{2} slaveUnit:{3}".format(objectType, address, registerCount, slaveUnit))
        if objectType == 'Coil':
            result = self._Mclient.read_coils(address, registerCount, unit=slaveUnit)
        elif objectType == 'DiscreteInput':
            result = self._Mclient.read_discrete_inputs(address, registerCount, unit=slaveUnit)
        elif objectType == 'InputRegister':
            result = self._Mclient.read_input_registers(address, registerCount, unit=slaveUnit)
        elif objectType == 'HoldingRegister':
            result = self._Mclient.read_holding_registers(address, registerCount, unit=slaveUnit)
        else:
            self.logger.error("{0} not supported: {1}".format(AttrObjectType, objectType))
            return None
        
        if result.isError():
            self.logger.error("read error: {0} register:{1} registerCount:{2} slaveUnit:{3}".format(result, address, registerCount, slaveUnit))
            return None
            
        if objectType == 'Coil':
            value = result.bits[0]
        elif objectType == 'DiscreteInput':
            value = result.bits[0]
        elif objectType == 'InputRegister':
            value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=bo,wordorder=wo)
        else:
            value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=bo,wordorder=wo)
            
        self.logger.debug("read result: {0}".format(result))
        
        if dataType.lower() == 'uint':
            if bits == 16:
                return value.decode_16bit_uint()
            elif bits == 32:
                return value.decode_32bit_uint()
            elif bits == 64:
                return value.decode_64bit_uint()
            else:
                self.logger.error("Number of bits or datatype not supportet : {0}".format(typeStr))
        elif dataType.lower() == 'int':
            if bits == 16:
                return value.decode_16bit_int()
            elif bits == 32:
                return value.decode_32bit_int()
            elif bits == 64:
                return value.decode_64bit_int()
            else:
                self.logger.error("Number of bits or datatype not supportet : {0}".format(typeStr))
        elif dataType.lower() == 'float':
            if bits == 32:
                return value.decode_32bit_float()
            if bits == 64:
                return value.decode_64bit_float()
            else:
                self.logger.error("Number of bits or datatype not supportet : {0}".format(typeStr))
        elif dataType.lower() == 'string':
            # bei string: bits = bytes !! string16 -> 16Byte
            ret = value.decode_string(bits)
            return str( ret, 'ASCII')
        elif dataType.lower() == 'bit':
            self.logger.debug("readed bit value: {0}".format(value))
            return value
        else:
            self.logger.error("Number of bits or datatype not supportet : {0}".format(typeStr))
        return None