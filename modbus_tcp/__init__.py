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

import threading

from lib.model.smartplugin import *
from lib.item import Items
from datetime import datetime

from pymodbus.constants import Endian
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.client.sync import ModbusTcpClient

AttrAddress = 'modBusAddress'
AttrType = 'modBusDataType'
AttrFactor = 'modBusFactor'
AttrByteOrder = 'modBusByteOrder'
AttrWordOrder = 'modBusWordOrder'

class modbus_tcp(SmartPlugin):
    PLUGIN_VERSION = '1.0.1'

    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        :param sh:  The instance of the smarthome object, save it for later references
        """
        
        self._host = self.get_parameter_value('host')
        self._port = int(self.get_parameter_value('port'))
        self._cycle = int(self.get_parameter_value('cycle'))
        self._slaveUnit = int(self.get_parameter_value('slaveUnit'))
        
        self._sh = sh
        self.logger = logging.getLogger(__name__)
        self._lock = threading.Lock()
        self.connected = False
        self._regToRead = {}
        self._pollStatus = {}
        
        self._sh.connections.monitor(self)  # damit connect ausgeführt wird
        self.init_webinterface()
        
        return

    def connect(self):
        """
        method to connecto to the ModbusTcpClient
        """
        if self.connected:
            return True
        self._lock.acquire()
        try:
            self._Mclient = ModbusTcpClient(self._host, port=self._port)
            if self._Mclient.connect():
                self.connected = True
                self.logger.info("connected to {0}".format(str(self._Mclient)))
            else:
                self.connected = False
                self.logger.debug("could not connect to {0}:{1}".format(self._host, self._port))
        except Exception as e:
            self.connected = False
            self.logger.error("connection expection: {0} {1}".format(str(self._Mclient), e))
            return
        finally:
            self._lock.release()

    def disconnect(self):
        """
        method to disconnect the ModbusTcpClient
        """
        if self.connected:
            try:
                self._Mclient.close()
                self.logger.debug("connection closed {0}".format(str(self._Mclient)))
                self.connected = False
            except:
                pass
    
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
        self.scheduler_remove('modbusTCP_poll_device')
        self.disconnect()
        
    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference

        :param item:    The item to process.
        """
        if self.has_iattr(item.conf, AttrAddress):
            regAddr = int(self.get_iattr_value(item.conf, AttrAddress))
            value = item()
            dataType = 'uint16'
            factor = 1
            byteOrder = 'Endian.Big'
            wordOrder = 'Endian.Big'
            self.logger.debug("parse read item: {0}".format(item))
            if self.has_iattr(item.conf, AttrType):
                dataType = self.get_iattr_value(item.conf, AttrType)
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
                
            regPara = {'dataType': dataType, 'factor': factor, 'byteOrder': byteOrder, 'wordOrder': wordOrder, 'item': item, 'value': value }
            self._regToRead.update({regAddr: regPara})
            
    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        startTime = datetime.now()
        regCount = 0
        try:
            self.connect()
            for regAddr, regPara in self._regToRead.items():
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
        # finally:
            # self.disconnect()
        
    def __read_Registers(self, address, regParameters):
        dataTypeStr = regParameters['dataType']
        
        bo = regParameters['byteOrder']         
        wo = regParameters['wordOrder']
        dataType = ''.join(filter(str.isalpha, dataTypeStr))
        try:
            bits = int(''.join(filter(str.isdigit, dataTypeStr)))   
        except:
            bits = 16
            
        if dataType.lower() == 'string':    
            words = int(bits/2)  # bei string: bits = bytes !! string16 -> 16Byte - 8 words
        else:
            words = int(bits/16)
        #self.logger.debug("read register:{0} words:{1} slaveUnit:{2}".format(address, words, self._slaveUnit))
        result = self._Mclient.read_holding_registers(address, words, unit=self._slaveUnit)
        #self.logger.debug("read result: {0} ".format(result))
        value = BinaryPayloadDecoder.fromRegisters(result.registers, byteorder=bo,wordorder=wo)
        
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
        else:
            self.logger.error("Number of bits or datatype not supportet : {0}".format(typeStr))
        return None
        
    def init_webinterface(self):
        """
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')   # try/except to handle running in a core version that does not support modules
        except:
             self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False
        
        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Plugin '{}': Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface".format(self.get_shortname()))
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
        
        self.items = Items.get_instance()

    @cherrypy.expose
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        return tmpl.render(plugin_shortname=self.plugin.get_shortname(), plugin_version=self.plugin.get_version(), plugin_info=self.plugin.get_info(),
                           interface=None,
                           p=self.plugin,
                           _regToRead=sorted(self.plugin._regToRead, key=lambda k: int(k)),
                           )

    @cherrypy.expose
    def triggerAction(self, path, value):
        if path is None:
            self.plugin.logger.error(
                "Plugin '{}': Path parameter is missing when setting action item value!".format(self.get_shortname()))
            return
        if value is None:
            self.plugin.logger.error(
                "Plugin '{}': Value parameter is missing when setting action item value!".format(self.get_shortname()))
            return
        item = self.plugin.items.return_item(path)
        item(int(value), caller=self.plugin.get_shortname(), source='triggerAction()')
        return


        