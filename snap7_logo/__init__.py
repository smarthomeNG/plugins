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
import snap7
from lib.model.smartplugin import *
from lib.module import Modules
from lib.logic import Logics
from lib.item import Items
from .webif import WebInterface

class snap7_logo(SmartPlugin):

    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.6.0"
 
    def __init__(self, sh, *args, **kwargs):
        """
        Initializes the plugin
        The params are documented in ``plugin.yaml`` and values will be obtained through get_parameter_value(parameter_name)
        """
        # Call init code of parent class (SmartPlugin)
        super().__init__()
        
        self.host = self.get_parameter_value('host')
        self.tsap_server = self.get_parameter_value('tsap_server')
        self.tsap_client = self.get_parameter_value('tsap_client')
        self._version = self.get_parameter_value('version')
        self._cycle = self.get_parameter_value('cycle')
        
        self.connected = False
        self._sh = sh
    
        # Hardware Version 0BA7
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
        # End Hardware Version 0BA8

        if self._version == '0BA8':
            self.logger.info('LOGO init Version:{0} Host:{1} '.format(self._version, self.host))
            self.tableVM_IO = self.table_VM_IO_0BA8
            self._vmIO = self._vmIO_0BA8
            self._vmIO_len = self._vmIO_len_0BA8
        elif self._version == '0BA7':
            self.logger.info('LOGO init Version:{0} Host:{1} '.format(self._version, self.host))
        else:
            self.logger.error('LOGO-Version: {0} not supportet: {1}'.format(self._version, self.host))
            return
    
        self.reads = {}     # zu lesende Items
        self.writes = {}    # zu schreibende Items
        self.stat_writes = {}   # Zeit und Wert der gelesenen Items (Webinterface)
        
        self.threadLastRead = 0  # verstrichene Zeit zwischen zwei LeseBefehlen
        self.plc = snap7.logo.Logo() # plc - Objekt anlegen
        
        self.init_webinterface(WebInterface)

    # called once at startup after all items are loaded
    def run(self):
        """
        Run method for the plugin
        """
        #self.logger.debug("Run method called")
        self.scheduler_add('poll_snap7_logo', self._update_loop, cycle=int(self._cycle))
        self.alive = True

    # close files and data connections
    def stop(self):
        """
        Stop method for the plugin
        """
        #self.logger.debug("Stop method called")
        self.scheduler_remove('poll_snap7_logo')
        self.plc.disconnect()
        self.connected = False
        self.plc.destroy()
        self.alive = False
        
    def _connect_to_plc(self):
        if self.plc.get_connected():
            self.connected = True
            return
        else:
            self.connected = False
            try:
                self.logger.debug('try to connected to {0}'.format(self.host))
                self.plc.connect(self.host, int(self.tsap_client), int(self.tsap_server))
            except Exception as e:
                self.logger.error('connection-Expection {0}: {1}'.format(self.host, e))
                self.connected = False
                return
            else:
                if self.plc.get_connected():
                    self.logger.info('connected to {0}'.format(self.host))
                    self.connected = True
                else:
                    self.logger.error('could not connect to {0}: {1}'.format(self.host, e))
                    self.connected = False
                    return

    def _update_loop(self):
        if len(self.writes) > 0:    # beim Schreiben sofort schreiben
            self._write_cycle()
        self._read_cycle()

    def _write_cycle(self):
        self._connect_to_plc()
        if not self.connected:
            return
        try:
            remove = []    # Liste der bereits geschriebenen Items
            for k, v in self.writes.items():    # zu schreibend Items I1,Q1,M1, AI1, AQ1, AM1, VM850, VM850.2, VMW0
                #self.logger.debug('write_cycle() {0} : {1} '.format(k, v))
                addr = k
                typ = v['typ']  # z.B. I Q M AI AQ AM VM VMW
                value = v['value']
                write_res = -1
                if typ in ['I', 'Q', 'M', 'NI', 'NQ']:  # I1 Q1 M1
                    if value is True:
                        #self.logger.debug("set {0} : {1} : {2} ".format(k, v, value))
                        write_res = self.set_vm_bit(v['VMaddr'], v['VMbit'])    # Setzen
                    else:
                        #self.logger.debug("clear {0} : {1} : {2} ".format(k, v, value))
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
                    raise LOGO('invalid typ: {0}'.format(typ))

                if write_res is not 0:
                    raise LOGO('LOGO: write failed: {0} {1} '.format(typ, value))
                    self.close()
                else:
                    self.logger.debug("write {0} : {1} : {2} ".format(k, value, v))
                    #if not 'last_write' in self.stat_writes[addr]:
                    
                    if 'write_dt' in self.stat_writes[addr]:
                        self.stat_writes[addr]['last_write_dt'] = self.stat_writes[addr]['write_dt']
                        
                    if 'value' in self.stat_writes[addr]:
                        self.stat_writes[addr]['last_value'] = self.stat_writes[addr]['value']
                    
                    self.stat_writes[addr]['write_dt'] = self.shtime.now()
                    self.stat_writes[addr]['value'] = value
                    
                    remove.append(k)  # nach dem Übertragen aus der Liste write entfernen

        except Exception as e:
            self.logger.error('write_cycle(){0} write error {1} '.format(k, e))
            self.plc.disconnect()
            self.connected = False
            return

        for k in remove:    # nach dem Übertragen aus der Liste writes entfernen - damit das Item nur 1x übertragen wird
            del self.writes[k]
        #self.plc.disconnect()
        
    def _read_cycle(self):
        self._connect_to_plc()
        if not self.connected:
            return
            
        try:
            # lesen der VM
            self.logger.debug("read_cycle() connected:{0} read addr:{1} len:{2}".format(self.plc.get_connected(), self._vm, self._vm_len))
            k = self._vm    # für except - Fehlermeldung
            
            resVM = self.plc.db_read(1, self._vm, self._vm_len)
            if not len(resVM) == self._vm_len:
                self.logger.error('read_cycle() failed ro read VM-Buffer (db_read) len:{0}'.format(len(resVM)))
                self.close()
                return
                
            # lesen der I Q M AI AQ AM
            #self.logger.debug("_read_cycle() try to read addr:{0} len:{1}".format(self._vmIO, self._vmIO_len))
            resVMIO = self.plc.db_read(1, self._vmIO, self._vmIO_len)
            if not len(resVMIO) == self._vmIO_len:
                self.logger.error('read_cycle() failed ro read VM_IO-Buffer (db_read) len:{0}'.format(len(resVMIO)))
                self.close()
                return
                
            # prüfe Buffer auf Änderung
            for k, v in self.reads.items():
                #self.logger.debug('read_cycle() k:{0} v:{1} '.format(k, v))
                new_value = 0
                item = v['item']

                if v['DataType'] == 'byte':
                    new_value = resVM[v['VMaddr'] - self._vm]  # VM byte   z.B. VM0
                elif v['DataType'] == 'word':
                    #self.logger.debug('read_cycle() h{0} : l{1} '.format(resVM[v['VMaddr']-self._vm], resVM[v['VMaddr']+1-self._vm]))
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
                    raise LOGO('{0} invalid DataType in reads: {1}'.format(k, v['DataType']))

                if 'old' in v:  # Variable wurde schon einmal gelesen
                    if v['old'] != new_value:   # Variable hat sich geändert
                        self.logger.debug("read_cycle():{0} newV:{1} oldV:{2} item:{3} ".format(k, new_value, v['old'], v['item']))
                        item(new_value)   # aktualisiere das Item
                        v.update({'old': new_value})    # speichere den aktuellen Zustand
                        if 'read_dt' in v:
                            v['last_read_dt'] = v['read_dt']
                        
                        if 'value' in v:
                            v['last_value'] = v['value']
                    
                        v['read_dt'] = self.shtime.now()
                        v['value'] = new_value

                    #else:   # Variable hat sich nicht geändert
                        #self.logger.debug("read:{0} newV:{1} = oldV:{2} item:{3} ".format(k, new_value, v['old'], v['item']))
                else:   # Variable wurde noch nie gelesen
                    self.logger.debug('read_cycle() first read:{0} value:{1} item:{2}'.format(k, new_value, v['item']))
                    item(new_value)   # aktualisiere das Item zum ersten mal
                    v.update({'old': new_value})    # speichere den aktuellen Zustand
                    v['read_dt'] = self.shtime.now()
                    v['value'] = new_value

        except Exception as e:
            self.logger.error('read_cycle(){0} read error {1} '.format(k, e))
            if 'Connection timed out' in str(e):
                self.logger.error(': read_cycle() Connection timed out!! ')
                self.plc.disconnect()
                self.connected = False
            if 'Other Socket error' in str(e): 
                self.logger.error(': read_cycle() Connection error: Other Socket error!! ')
                self.plc.disconnect()
                self.connected = False
            return
        #self.plc.disconnect()
        return

    # called for each item during startup, items.yaml contains the "attibute: value" entries
    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference

        :param item:    The item to process.
        """
    
        if self.has_iattr(item.conf, 'logo_read'): # if 'logo_read' in item.conf:
            addr = self.get_iattr_value(item.conf, 'logo_read')    #for addr in logo_read:
            self.logger.debug('parse_item {0} {1}'.format(item, addr))
            addressInfo = self.getAddressInfo(addr)
            if addressInfo is not False:
                addressInfo.update({'value': item()})   # Wert des Items hinzufügen
                addressInfo.update({'item': item})      # Item hinzufügen
                self.reads.update({addr: addressInfo})  # zu lesende Items

        if self.has_iattr(item.conf, 'logo_write'):  # if 'logo_write' in item.conf:
            addr = self.get_iattr_value(item.conf, 'logo_write')    #for addr in logo_read:
            self.logger.debug('parse_item {0} {1}'.format(item, addr))
            addressInfo = self.getAddressInfo(addr)
            if addressInfo is not False:
                addressInfo.update({'value': item()})   # Wert des Items hinzufügen
                addressInfo.update({'item': item})      # Item hinzufügen
                self.stat_writes.update({addr: addressInfo})  # zu schreibende Items - Statistik
            return self.update_item
        
    def parse_logic(self, logic):
        pass

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
        if self.has_iattr(item.conf, 'logo_write'):  # if 'logo_write' in item.conf:
            if caller != 'snap7logo':
                addr = self.get_iattr_value(item.conf, 'logo_write')    # for addr in item.conf['logo_write']:
                self.logger.debug('update_item() item:{0} addr:{1}'.format(item, addr))
                addressInfo = self.getAddressInfo(addr)
                if addressInfo is not False:
                    addressInfo.update({'value': item()})  # Wert des Items hinzufügen
                    addressInfo.update({'item': item})
                    self.writes.update({addr: addressInfo})   # zu schreibende Items
                    try:
                        self._write_cycle()
                        self._read_cycle()
                    except Exception as e:
                        self.logger.error('update_item() Expection {0}'.format(e))

                
    def getAddressInfo(self, value):    # I1,Q1,M1, AI1, AQ1, AM1, VM850, VM850.2, VMW0
        try:
            indexDigit = 0
            for c in value:  # indexDigit: ermittle Index der ersten Zahl
                if c.isdigit():
                    break
                else:
                    indexDigit += 1
            indexComma = value.find('.')    # ermittle ob ein Komma vorhanden ist (z.B. VM10.6)
            #self.logger.debug('getAddressInfo() value:{0} iC:{1} iD:{2}'.format(value, indexComma, indexDigit))
            if (len(value) < 2):
                raise LOGO('invalid address {0} indexDigit < 1'.format(value))
            if indexDigit < 1:
                raise LOGO('invalid address {0} indexDigit < 1'.format(value))
            typ = value[0:indexDigit]   # I Q M AI AQ AM VM VMW
            if indexComma == -1:        # kein Komma (z.B. M1)
                address = int(value[indexDigit:len(value)])
            else:               # Komma vorhanden (z.B. VM10.6)
                address = int(value[indexDigit:indexComma])
                bitNr = int(value[indexComma + 1:len(value)])
                if (bitNr < 0) or (bitNr > 8):
                    raise LOGO('invalid address {0} bitNr invalid'.format(value))

            #self.logger.debug('getAddressInfo() typ:{0} address:{1}'.format(typ, address))

            if typ == 'VMW':
                VMaddr = int(self.tableVM_IO['VM']['VMaddr'])   # Startaddresse
            else:
                VMaddr = int(self.tableVM_IO[typ]['VMaddr'])    # Startaddresse

            if typ in ['I', 'Q', 'M', 'NI', 'NQ']:  # I1 Q1 M1
                MaxBits = int(self.tableVM_IO[typ]['bits'])    # Anzahl bits
                if address > MaxBits:
                    raise LOGO('Address out of range. {0}1-{0}{1}'.format(typ, MaxBits))
                q, r = divmod(address - 1, 8)
                VMaddr = VMaddr + q
                bitNr = r
                return {'VMaddr': VMaddr, 'VMbit': bitNr, 'typ': typ, 'DataType': 'bit'}

            elif typ in ['AI', 'AQ', 'AM', 'NAI', 'NAQ']:    # AI1 AQ1 AM1
                MaxWords = int(self.tableVM_IO[typ]['words'])  # Anzahl words
                if address > MaxWords:
                    raise LOGO('Address out of range. {0}1-{0}{1}'.format(typ, MaxWords))
                VMaddr = VMaddr + ((address - 1) * 2)
                return {'VMaddr': VMaddr, 'typ': typ, 'DataType': 'word'}

            elif typ == 'VMW':    # VMW0
                #typ = 'VM'
                MaxBytes = int(self.tableVM_IO['VM']['bytes'])  # Anzahl words
                if address > MaxBytes:
                    raise LOGO('Address out of range. {0}0-{0}{1}'.format(typ, MaxBytes))
                VMaddr = VMaddr + address
                return {'VMaddr': VMaddr, 'typ': typ, 'DataType': 'word'}

            elif (typ == 'VM') and (indexComma == -1):    # VM0
                MaxBytes = int(self.tableVM_IO[typ]['bytes'])  # Anzahl bytes
                if address > MaxBytes:
                    raise LOGO('Address out of range. {0}0-{0}{1}'.format(typ, MaxBytes))
                VMaddr = VMaddr + address
                return {'VMaddr': VMaddr, 'typ': typ, 'DataType': 'byte'}

            elif (typ == 'VM') and (indexComma > 2):    # VM10.6
                MaxBytes = int(self.tableVM_IO[typ]['bytes'])  # Anzahl bytes
                if address > MaxBytes:
                    raise LOGO('Address out of range. {0}0-{0}{1}'.format(typ, MaxBytes))
                VMaddr = VMaddr + address
                return {'VMaddr': VMaddr, 'VMbit': bitNr, 'typ': typ, 'DataType': 'bit'}
            else:
                raise LOGO('invalid typ: {0}'.format(typ))

        except Exception as e:
            self.logger.error('getAddressInfo() {0} : {1} '.format(value, e))
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
