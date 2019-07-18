#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
# Copyright 2013 KNX-User-Forum e.V.            http://knx-user-forum.de/
#########################################################################
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
#########################################################################

import ctypes
import os
import string
import time
import logging
import threading
from lib.model.smartplugin import *
from lib.module import Modules
from lib.logic import Logics
from lib.item import Items
import snap7

class snap7logo(SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.5.2"
    def __init__(self, smarthome, host, tsap_server=0x0200, tsap_client=0x0100, version='0BA7', cycle=5 ):
        self.logger = logging.getLogger(__name__)
        self.host = host
        self.tsap_server = int(tsap_server)
        self.tsap_client = int(tsap_client)
        self._version = version
        self._cycle = int(cycle)
        self._lock = threading.Lock()
        self._rw_lock = threading.Lock()
        self.connected = False
        self._sh = smarthome
        self._connection_attempts = 0
        self._connection_errorlog = 2

        self._vmIO = 923  # lesen der I Q M AI AQ AM ab VM-Adresse VM923
        self._vmIO_len = 60  # Anzahl der zu lesenden Bytes 60
        self._vm = 0  # lesen der VM ab VM-Adresse VM0
        self._vm_len = 850  # Anzahl der zu lesenden Bytes VM0-850
        self.tableVM_IO = {  # Address-Tab der I,Q,M,AI,AQ,AM im PLC-VM-Buffer
        'I': {'VMaddr': 923, 'bytes': 3, 'bits': 24},
        'Q': {'VMaddr': 942, 'bytes': 2, 'bits': 16},
        'M': {'VMaddr': 948, 'bytes': 3, 'bits': 27},
        'AI': {'VMaddr': 926, 'words': 8},
        'AQ': {'VMaddr': 944, 'words': 2},
        'AM': {'VMaddr': 952, 'words': 16},
        'VM': {'VMaddr': 0, 'bytes': 850}}
        self.logger.info('LOGO: init {0}:{1} '.format(self.get_instance_name(), self.host))

    # Hardware Version 0BA8
        self._vmIO_0BA8 = 1024  # lesen der I Q M AI AQ AM ab VM-Adresse VM1024
        self._vmIO_len_0BA8 = 445  # Anzahl der zu lesenden Bytes 445
        self.table_VM_IO_0BA8 = {  # Address-Tab der I,Q,M,AI,AQ,AM im PLC-VM-Buffer
        'I': {'VMaddr': 1024, 'bytes': 8, 'bits': 64},
        'Q': {'VMaddr': 1064, 'bytes': 8, 'bits': 64},
        'M': {'VMaddr': 1104, 'bytes': 14, 'bits': 112},
        'AI': {'VMaddr': 1032, 'words': 16},
        'AQ': {'VMaddr': 1072, 'words': 16},
        'AM': {'VMaddr': 1118, 'words': 64},
        'NI': {'VMaddr': 1256, 'bytes': 16, 'bits':128},
        'NAI': {'VMaddr': 1262, 'words': 64},
        'NQ': {'VMaddr': 1390, 'bytes': 16, 'bits': 128},
        'NAQ': {'VMaddr': 1406, 'words': 32},
        'VM': {'VMaddr': 0, 'bytes': 850}}

        if self._version == '0BA8':
            self.logger.info('{0}: LOGO-Version {1}'.format(self.get_instance_name(), self._version))
            self.tableVM_IO = self.table_VM_IO_0BA8
            self._vmIO = self._vmIO_0BA8
            self._vmIO_len = self._vmIO_len_0BA8
    # End Hardware Version 0BA8

        self.reads = {}
        self.writes = {}
        self.stat_writes = {}
        
        #self.Dateipfad = '/lib'  # Dateipfad zur Bibliothek
        self.threadLastRead = 0  # verstrichene Zeit zwischen zwei LeseBefehlen

        smarthome.connections.monitor(self)  # damit connect ausgeführt wird
        
        self.init_webinterface()

    # Öffnen der Verbindung zur LOGO
    def connect(self):
        self._lock.acquire()
        try:
            self.logger.debug('{0}: try to connected to {1}'.format(self.get_instance_name(), self.host))
            self.plc = snap7.logo.Logo()
            self.plc.connect(self.host, self.tsap_client, self.tsap_server)
            #if not self.plc.get_connected():
                #raise LOGO('{0}:connection error'.format(self.get_instance_name()))

        except Exception as e:
            self._connection_attempts -= 1
            if self._connection_attempts <= 0:
                self.logger.error('{0}: could not connect to {1}: {2}'.format(self.get_instance_name(), self.host, e))
                self._connection_attempts = self._connection_errorlog
            self._lock.release()
            return
        else:
            if self.plc.get_connected():
                self.connected = True
                self.logger.info('{0}: connected to {1}'.format(self.get_instance_name(), self.host))
                self._connection_attempts = 0
                self._lock.release()
            else:
                self.logger.error('{0}: could not connect to {1}: {2}'.format(self.get_instance_name(), self.host, e))
    
    # called once at startup after all items are loaded
    def run(self):
        self.scheduler_add('update', self._update_loop, prio=5, cycle=self._cycle, offset=2)
        self.alive = True
        

    # close files and data connections
    def stop(self):
        self.alive = False
        self.close()

    def _update_loop(self):
        if self._rw_lock.locked():
            self.logger.warning('_update_loop locked!!')
            return
                        
        #self.logger.debug('_update_loop acquire')
        self._rw_lock.acquire(timeout=60)
        try:
        
            if len(self.writes) > 0:    # beim Schreiben sofort schreiben
                self._write_cycle()
            
            self._read_cycle()
            
            
        finally:
            self._rw_lock.release()
        
        #self.logger.debug('_update_loop release')
        

    def _write_cycle(self):
        
        if not self.connected:
            return
        #self.logger.debug("{0}: _write_cycle() connected:{1}".format(self.get_instance_name(), self.connected))
        try:
            remove = []    # Liste der bereits geschriebenen Items
            for k, v in self.writes.items():    # zu schreibend Items I1,Q1,M1, AI1, AQ1, AM1, VM850, VM850.2, VMW0
                #self.logger.debug('{0}: write_cycle() {1} : {2} '.format(self.get_instance_name(), k, v))
                addr = k
                typ = v['typ']  # z.B. I Q M AI AQ AM VM VMW
                value = v['value']
                write_res = -1
                if typ in ['I', 'Q', 'M', 'NI', 'NQ']:  # I1 Q1 M1
                    if value is True:
                        #self.logger.debug("{0}: set {1} : {2} : {3} ".format(self.get_instance_name(), k, v, value))
                        write_res = self.set_vm_bit(v['VMaddr'], v['VMbit'])    # Setzen
                    else:
                        #self.logger.debug("{0}: clear {1} : {2} : {3} ".format(self.get_instance_name(), k, v, value))
                        write_res = self.clear_vm_bit(v['VMaddr'], v['VMbit'])  # Löschen

                elif typ in ['AI', 'AQ', 'AM', 'NAI', 'NAQ', 'VMW']:    # AI1 AQ1 AM1 VMW
                    write_res = self.write_vm_word(v['VMaddr'], value)

                elif typ == 'VM':       # VM0 VM10.6
                    if 'VMbit' in v:    # VM10.6
                        if value is True:
                            write_res = self.set_vm_bit(v['VMaddr'], v['VMbit'])
                        else:
                            write_res = self.clear_vm_bit(v['VMaddr'], v['VMbit'])
                    else:               # VM0
                        write_res = self.write_vm_byte(v['VMaddr'], value)
                else:
                    raise LOGO('{0}:invalid typ: {1}'.format(self.get_instance_name(), typ))

                if write_res is not 0:
                    raise LOGO('{0}:LOGO: write failed: {1} {2} '.format(self.get_instance_name(), typ, value))
                    self.close()
                else:
                    self.logger.debug("{0}: write {1} : {2} : {3} ".format(self.get_instance_name(), k, value, v))
                    #if not 'last_write' in self.stat_writes[addr]:
                    
                    if 'write_dt' in self.stat_writes[addr]:
                        self.stat_writes[addr]['last_write_dt'] = self.stat_writes[addr]['write_dt']
                        
                    if 'value' in self.stat_writes[addr]:
                        self.stat_writes[addr]['last_value'] = self.stat_writes[addr]['value']
                    
                    self.stat_writes[addr]['write_dt'] = self.shtime.now()
                    self.stat_writes[addr]['value'] = value
                    
                    remove.append(k)  # nach dem Übertragen aus der Liste write entfernen

        except Exception as e:
            self.logger.error('{0}: write_cycle(){1} write error {2} '.format(self.get_instance_name(), k, e))
            
            return

        for k in remove:    # nach dem Übertragen aus der Liste writes entfernen - damit das Item nur 1x übertragen wird
            del self.writes[k]
         
    def _read_cycle(self):
        if not self.connected:
            return
        
        
        try:
            # lesen der VM
            #self.logger.debug("{0}: _read_cycle() try to read addr:{1} len:{2}".format(self.get_instance_name(), self._vm, self._vm_len))
            resVM = self.plc.db_read(1, self._vm, self._vm_len)
            if not len(resVM) == self._vm_len:
                self.logger.error('{0}: read_cycle() failed ro read VM-Buffer (db_read) len:{1}'.format(self.get_instance_name(), len(resVM)))
                self.close()
                return
                
            # lesen der I Q M AI AQ AM
            #self.logger.debug("{0}: _read_cycle() try to read addr:{1} len:{2}".format(self.get_instance_name(), self._vmIO, self._vmIO_len))
            resVMIO = self.plc.db_read(1, self._vmIO, self._vmIO_len)
            if not len(resVMIO) == self._vmIO_len:
                self.logger.error('{0}: read_cycle() failed ro read VM_IO-Buffer (db_read) len:{1}'.format(self.get_instance_name(), len(resVMIO)))
                self.close()
                return

            # prüfe Buffer auf Änderung
            for k, v in self.reads.items():
                #self.logger.debug('{0}: read_cycle() k:{1} v:{2} '.format(self.get_instance_name(), k, v))
                new_value = 0
                item = v['item']

                if v['DataType'] == 'byte':
                    new_value = resVM[v['VMaddr'] - self._vm]  # VM byte   z.B. VM0
                elif v['DataType'] == 'word':
                    #self.logger.debug('{0}: read_cycle() h{1} : l{2} '.format(self.get_instance_name(), resVM[v['VMaddr']-self._vm], resVM[v['VMaddr']+1-self._vm]))
                    if v['typ'] == 'VMW':                           # VMW word   z.B. VMW0
                        h = resVM[v['VMaddr'] - self._vm]
                        l = resVM[v['VMaddr'] + 1 - self._vm]
                    else:                                           # AI AQ AM word z.B, AM1
                        h = resVMIO[v['VMaddr'] - self._vmIO]
                        l = resVMIO[v['VMaddr'] + 1 - self._vmIO]
                    new_value = l + (h << 8)
                elif v['DataType'] == 'bit':
                    if v['typ'] == 'VM':                            # VM bit z.B.VM10.6
                        new_byte = resVM[v['VMaddr'] - self._vm]
                    else:                                           # I Q M bit z.B. M1
                        new_byte = resVMIO[v['VMaddr'] - self._vmIO]
                    new_value = self.get_bit(new_byte, v['VMbit'])
                else:
                    raise LOGO('{0}:{1} invalid DataType in reads: {2}'.format(self.get_instance_name(), k, v['DataType']))

                if 'old' in v:  # Variable wurde schon einmal gelesen
                    if v['old'] != new_value:   # Variable hat sich geändert
                        self.logger.debug("{0}: read_cycle():{1} newV:{2} oldV:{3} item:{4} ".format(self.get_instance_name(), k, new_value, v['old'], v['item']))
                        item(new_value)   # aktualisiere das Item
                        v.update({'old': new_value})    # speichere den aktuellen Zustand
                        if 'read_dt' in v:
                            v['last_read_dt'] = v['read_dt']
                        
                        if 'value' in v:
                            v['last_value'] = v['value']
                    
                        v['read_dt'] = self.shtime.now()
                        v['value'] = new_value

                    #else:   # Variable hat sich nicht geändert
                        #self.logger.debug("{0}: read:{1} newV:{2} = oldV:{3} item:{4} ".format(self.get_instance_name(), k, new_value, v['old'], v['item']))
                else:   # Variable wurde noch nie gelesen
                    self.logger.debug('{0}: read_cycle() first read:{1} value:{2} item:{3}'.format(self.get_instance_name(), k, new_value, v['item']))
                    item(new_value)   # aktualisiere das Item zum ersten mal
                    v.update({'old': new_value})    # speichere den aktuellen Zustand
                    v['read_dt'] = self.shtime.now()
                    v['value'] = new_value

        except Exception as e:
            self.logger.error('{0}: read_cycle(){1} read error {2} '.format(self.get_instance_name(), k, e))
            return
        
        return

    def close(self):
        self.connected = False
        try:
            self.disconnect()
            self.logger.info('{0}: disconnected {1}'.format(self.get_instance_name(), self.host))
        except:
            pass

    def disconnect(self):
        self.plc.disconnect()
        self.plc.destroy()

    # called for each item during startup, items.yaml contains the "attibute: value" entries
    def parse_item(self, item):
    
        if self.has_iattr(item.conf, 'logo_read'): # if 'logo_read' in item.conf:
            addr = self.get_iattr_value(item.conf, 'logo_read')    #for addr in logo_read:
            self.logger.debug('{0}: parse_item {1} {2}'.format(self.get_instance_name(), item, addr))
            addressInfo = self.getAddressInfo(addr)
            if addressInfo is not False:
                addressInfo.update({'value': item()})   # Wert des Items hinzufügen
                addressInfo.update({'item': item})      # Item hinzufügen
                self.reads.update({addr: addressInfo})  # zu lesende Items
            
            #logo_read = item.conf['logo_read']
            #if isinstance(logo_read, str):
            #    logo_read = [logo_read, ]
            #for addr in self.get_iattr_value(item.conf, 'logo_read')    #for addr in logo_read:
            #    self.logger.debug('{0}: parse_item {1} {2}'.format(self.get_instance_name(), item, addr))
            #    addressInfo = self.getAddressInfo(addr)
            #    if addressInfo is not False:
            #        addressInfo.update({'value': item()})   # Wert des Items hinzufügen
            #        addressInfo.update({'item': item})      # Item hinzufügen
            #        self.reads.update({addr: addressInfo})  # zu lesende Items
            

        if self.has_iattr(item.conf, 'logo_write'):  # if 'logo_write' in item.conf:
            addr = self.get_iattr_value(item.conf, 'logo_write')    #for addr in logo_read:
            self.logger.debug('{0}: parse_item {1} {2}'.format(self.get_instance_name(), item, addr))
            addressInfo = self.getAddressInfo(addr)
            if addressInfo is not False:
                addressInfo.update({'value': item()})   # Wert des Items hinzufügen
                addressInfo.update({'item': item})      # Item hinzufügen
                self.stat_writes.update({addr: addressInfo})  # zu schreibende Items - Statistik
            return self.update_item
        #    if isinstance(item.conf['logo_write'], str):
        #        item.conf['logo_write'] = [item.conf['logo_write'], ]
        

    def parse_logic(self, logic):
        pass
        #if 'xxx' in logic.conf:
            # self.function(logic['name'])

    # called each time an item changes.
    def update_item(self, item, caller=None, source=None, dest=None):
        if self.has_iattr(item.conf, 'logo_write'):  # if 'logo_write' in item.conf:
            if caller != 'snap7logo':
                addr = self.get_iattr_value(item.conf, 'logo_write')    # for addr in item.conf['logo_write']:
                self.logger.debug('{0}: update_item() item:{1} addr:{2}'.format(self.get_instance_name(), item, addr))
                addressInfo = self.getAddressInfo(addr)
                if addressInfo is not False:
                    
                    
            
                    addressInfo.update({'value': item()})  # Wert des Items hinzufügen
                    addressInfo.update({'item': item})
                    self.writes.update({addr: addressInfo})   # zu schreibende Items
                    if self._rw_lock.locked():
                        self.logger.warning('update_item locked!!')
                        return
                    
                    #self.logger.debug('update_item acquire')
                    self._rw_lock.acquire(timeout=60)
                    
                    #self.logger.debug('update_item _write_cycle()')
                    self._write_cycle()
                    self._read_cycle()
            
                    #self.logger.debug('update_item release')
                    self._rw_lock.release()
                    
                    
                
    def getAddressInfo(self, value):    # I1,Q1,M1, AI1, AQ1, AM1, VM850, VM850.2, VMW0
        try:
            indexDigit = 0
            for c in value:  # indexDigit: ermittle Index der ersten Zahl
                if c.isdigit():
                    break
                else:
                    indexDigit += 1
            indexComma = value.find('.')    # ermittle ob ein Komma vorhanden ist (z.B. VM10.6)
            #self.logger.debug('{0}: getAddressInfo() value:{1} iC:{2} iD:{3}'.format(self.get_instance_name(), value, indexComma, indexDigit))
            if (len(value) < 2):
                raise LOGO('{0}:invalid address {1} indexDigit < 1'.format(self.get_instance_name(), value))
            if indexDigit < 1:
                raise LOGO('{0}:invalid address {1} indexDigit < 1'.format(self.get_instance_name(), value))
            typ = value[0:indexDigit]   # I Q M AI AQ AM VM VMW
            if indexComma == -1:        # kein Komma (z.B. M1)
                address = int(value[indexDigit:len(value)])
            else:               # Komma vorhanden (z.B. VM10.6)
                address = int(value[indexDigit:indexComma])
                bitNr = int(value[indexComma + 1:len(value)])
                if (bitNr < 0) or (bitNr > 8):
                    raise LOGO('{0}:invalid address {1} bitNr invalid'.format(self.get_instance_name(), value))

            #self.logger.debug('{0}: getAddressInfo() typ:{1} address:{2}'.format(self.get_instance_name(), typ, address))

            if typ == 'VMW':
                VMaddr = int(self.tableVM_IO['VM']['VMaddr'])   # Startaddresse
            else:
                VMaddr = int(self.tableVM_IO[typ]['VMaddr'])    # Startaddresse

            if typ in ['I', 'Q', 'M', 'NI', 'NQ']:  # I1 Q1 M1
                MaxBits = int(self.tableVM_IO[typ]['bits'])    # Anzahl bits
                if address > MaxBits:
                    raise LOGO('{0}:Address out of range. {1}1-{1}{2}'.format(self.get_instance_name(), typ, MaxBits))
                q, r = divmod(address - 1, 8)
                VMaddr = VMaddr + q
                bitNr = r
                return {'VMaddr': VMaddr, 'VMbit': bitNr, 'typ': typ, 'DataType': 'bit'}

            elif typ in ['AI', 'AQ', 'AM', 'NAI', 'NAQ']:    # AI1 AQ1 AM1
                MaxWords = int(self.tableVM_IO[typ]['words'])  # Anzahl words
                if address > MaxWords:
                    raise LOGO('{0}:Address out of range. {1}1-{1}{2}'.format(self.get_instance_name(), typ, MaxWords))
                VMaddr = VMaddr + ((address - 1) * 2)
                return {'VMaddr': VMaddr, 'typ': typ, 'DataType': 'word'}

            elif typ == 'VMW':    # VMW0
                #typ = 'VM'
                MaxBytes = int(self.tableVM_IO['VM']['bytes'])  # Anzahl words
                if address > MaxBytes:
                    raise LOGO('{0}:Address out of range. {0}0-{1}{2}'.format(self.get_instance_name(), typ, MaxBytes))
                VMaddr = VMaddr + address
                return {'VMaddr': VMaddr, 'typ': typ, 'DataType': 'word'}

            elif (typ == 'VM') and (indexComma == -1):    # VM0
                MaxBytes = int(self.tableVM_IO[typ]['bytes'])  # Anzahl bytes
                if address > MaxBytes:
                    raise LOGO('{0}:Address out of range. {0}0-{1}{2}'.format(self.get_instance_name(), typ, MaxBytes))
                VMaddr = VMaddr + address
                return {'VMaddr': VMaddr, 'typ': typ, 'DataType': 'byte'}

            elif (typ == 'VM') and (indexComma > 2):    # VM10.6
                MaxBytes = int(self.tableVM_IO[typ]['bytes'])  # Anzahl bytes
                if address > MaxBytes:
                    raise LOGO('{0}:Address out of range. {0}0-{1}{2}'.format(self.get_instance_name(), typ, MaxBytes))
                VMaddr = VMaddr + address
                return {'VMaddr': VMaddr, 'VMbit': bitNr, 'typ': typ, 'DataType': 'bit'}
            else:
                raise LOGO('{0}:invalid typ: {1}'.format(self.get_instance_name(), typ))

        except Exception as e:
            self.logger.error('{0}: getAddressInfo() {1} : {2} '.format(self.get_instance_name(), value, e))
            return False

    def get_bit(self, byteval, idx):
        return ((byteval & (1 << idx)) != 0)

    #******************************** WRITE IN BYTE FORMAT ****************************************
    #VM
    def write_vm_byte(self, vm, value):
        writeBuffer = bytearray(struct.pack(">h", value))
        #self.logger.debug('write_vm_byte() vm:{0} value:{1} buffer:{2}'.format(vm, value, writeBuffer))
        return self.plc.db_write(1, vm, writeBuffer)
    #******************************** WRITE IN WORD FORMAT *******************************
    #VM WORD
    def write_vm_word(self, vm, value):
        writeBuffer = bytearray(value.to_bytes(2,byteorder='big'))
        #self.logger.debug('write_vm_word() vm:{0} value:{1} buffer:{2}'.format(vm, value, writeBuffer))
        return self.plc.db_write(1, vm, writeBuffer)

    #******************************** WRITE IN BIT FORMAT *****************************************
    #VM
    def set_vm_bit(self, vm, position):
        vm_address = 'V' + str(vm) + '.' + str(position)
        self.logger.debug('set_vm_bit() vm:{0} position:{1} vm_address:{2}'.format(vm, position, vm_address))
        return self.plc.write(vm_address, 1)

    def clear_vm_bit(self, vm, position):
        vm_address = 'V' + str(vm) + '.' + str(position)
        self.logger.debug('set_vm_bit() vm:{0} position:{1} vm_address:{2}'.format(vm, position, vm_address))
        return self.plc.write(vm_address, 0)

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
                           reads=sorted(self.plugin.reads, key=lambda k: str.lower(k)),
                           writes=sorted(self.plugin.stat_writes, key=lambda k: str.lower(k)),
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
