#!/usr/bin/env python
#########################################################################
# Copyright 2013 Stefan Kals
#########################################################################
#  Viessmann-Plugin for SmartHomeNG.  https://github.com/smarthomeNG//
#
#  This plugin is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This plugin is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this plugin. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

#ToDos / Remarks
    # addr in commands.py muessen lowercase sein
    # viess_init ohne Hochkommas lesen (bool)
    # beim Setzen von Werten prüfen, ob der zu setzende Wert innerhalb des zulässigen Bereiches ist
    # signed für 4 byte value implementieren

import logging
import socket
import time
import serial
import re
import threading
import binascii
from . import commands

from lib.module import Modules
from lib.model.smartplugin import *

from bin.smarthome import VERSION
if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
    self.logger = logging.getLogger(__name__)

class Viessmann(SmartPlugin):

    ALLOW_MULTIINSTANCE = False
    PLUGIN_VERSION = '1.6.2'

    def __init__(self, sh, *args, **kwargs):
    
        # Get plugin parameter
        self._cycle = self.get_parameter_value('cycle')              # 300
        self._serialport = self.get_parameter_value('serialport')    # /dev/optolink
        heating_type = self.get_parameter_value('heating_type')      # V200KO1B
        protocol = self.get_parameter_value('protocol')              # P300
        # Set variables
        self.connected = False
        self._sh = smarthome
        self._params = {}
        self._init_cmds = []
        self._cyclic_cmds = {}
        self._lock = threading.Lock()
        self._connection_attempts = 0
        self._connection_errorlog = 60
        self._initread = False
        self._serial = False
        self._lastbyte = b''
        smarthome.connections.monitor(self)
        self._lastbytetime = time.time()
        self._initialized = False
        # Load controlset and commandset
        if protocol in commands.controlset and heating_type in commands.commandset:
            self._controlset = commands.controlset[protocol]
            self._commandset = commands.commandset[heating_type]
            self.log_info('Loaded commands for Heating type \'{}\''.format(heating_type))
        else:
            self.log_err('Commands for Heating type \'{}\' could not be found!'.format(heating_type))
            return None
        # Remember protocol config
        self._startbyte = self.int2bytes(self._controlset['StartByte'], 1)
        self._request = self.int2bytes(self._controlset['Request'], 1)
        self._response = self.int2bytes(self._controlset['Response'], 1)
        self._error = self.int2bytes(self._controlset['Error'], 1)
        self._read = self.int2bytes(self._controlset['Read'], 1)
        self._write = self.int2bytes(self._controlset['Write'], 1)
        self._functioncall = self.int2bytes(self._controlset['Function_Call'], 1)
        self._acknowledge = self.int2bytes(self._controlset['Acknowledge'], 1)
        self._notinitiated = self.int2bytes(self._controlset['Not_initiated'], 1)
        self._initerror = self.int2bytes(self._controlset['Init_Error'], 1)
        self._resetcommand = self.int2bytes(self._controlset['Reset_Command'], 1)
        self._resetcommandresponse = self.int2bytes(self._controlset['Reset_Command_Response'], 1)
        self._synccommand = self.int2bytes(self._controlset['Sync_Command'], 3)
        self._synccommandresponse = self.int2bytes((self._controlset['Sync_Command_Response']), 1)
        self._commandbytesread = self.int2bytes(self._controlset['Command_bytes_read'], 1)
        self._commandbyteswrite = self.int2bytes(self._controlset['Command_bytes_write'], 1)
        self._commandlength = self._controlset['Command_length']
        self._checksumlength = self._controlset['Checksum_length']

    def connect(self):
        self._lock.acquire()
        try:
            self._serialconnection = serial.Serial(
                    self._serialport, 4800, serial.EIGHTBITS, serial.PARITY_EVEN, serial.STOPBITS_TWO, timeout=1)
        except Exception as e:
            self._connection_attempts -= 1
            if self._connection_attempts <= 0:
                self.log_err('could not connect to {}: {}'.format(self._serialport, e))
                self._connection_attempts = self._connection_errorlog
            self._lock.release()
            return
        else:
            self.connected = True
            self.log_info('connected to {}'.format(self._serialport))
            self._connection_attempts = 0
            self._lock.release()    

    def disconnect(self):
        self.connected = False
        try:
            self._serialconnection.close()
            self._serialconnection = None
            self.log_debug('disconnected')
        except:
            pass
            
    def send_bytes(self, packet):
        self.log_debug('Write byte(string): {}'.format(packet))
        # Sendepuffer leeren (Sicherheitsfunktion)
        self._serialconnection.flushInput()
        # Übergebenen Bytestring senden
        self._serialconnection.write(packet)
        # Sendepuffer leeren
        self._serialconnection.flushInput()
        
    def read_bytes(self, length):
        self._lastbytetime = time.time()
        return self._serialconnection.read(length)
        
    def read_byte(self):
        # Standard Rückgabewert definieren (leeres Byte)
        readbyte = self._serialconnection.read(1)
        self.log_debug('Read byte: {}'.format(readbyte))
        # Ein Byte wurde empfangen. Dieses wird gespeichert
        self._lastbyte = readbyte
        # Prüfung, ob ein Byte empfangen wurde
        if (readbyte != b''):
            # Ein Byte wurde empfangen. Dieses wird gespeichert
            self._lastbyte = readbyte
            # Zeit des Empfangs ebenfalls speichern
            self._lastbytetime = time.time()
 
    def parse_item(self, item):
        # self.log_debug('Item {} parsed!'.format(item))
        # item = Wert des Attributes "name" aus der item.conf
        
        # Process the read config
        if self.has_iattr(item.conf, 'viess_read'):
            commandname = self.get_iattr_value(item.conf, 'viess_read')
            if (commandname == None or commandname not in self._commandset):
                self.log_err('Item {} contains invalid read command \'{}\'!'.format(item, commandname))
                return None
            
            # Remember the read config to later update this item if the configured response comes in
            self.log_info('Item {} reads by using command \'{}\'.'.format(item, commandname))
            commandconf = self._commandset[commandname]
            commandcode = (commandconf['addr'])

            if not commandcode in self._params:
                self._params[commandcode] = {'commandname': [commandname], 'items': [item]}
            elif not item in self._params[commandcode]['items']:
                self._params[commandcode]['commandname'].append(commandname)
                self._params[commandcode]['items'].append(item)

            # Allow items to be automatically initiated on startup
            if (self.has_iattr(item.conf, 'viess_init') and self.get_iattr_value(item.conf, 'viess_init') == 'true'):
                self.log_info('Item {} is initialized on startup.'.format(item))
                # Only add the item to the initial commands if it is not cyclic. Cyclic commands get called on init because this is the first cycle...
                if not commandcode in self._init_cmds and not self.has_iattr(item.conf, 'viess_read_cycle'):
                    self._init_cmds.append(commandcode)
                self.log_debug('Items should read at init: {}'.format(self._init_cmds))

            # Allow items to be cyclically updated
            if (self.has_iattr(item.conf, 'viess_read_cycle')):
                cycle = int(self.get_iattr_value(item.conf, 'viess_read_cycle'))
                self.log_info('Item {} should read cyclic every {} seconds.'.format(item, cycle))
                if not commandcode in self._cyclic_cmds:
                    self._cyclic_cmds[commandcode] = {'cycle': cycle, 'nexttime': 0}
                else:
                    # If another item requested this command already with a longer cycle, use the shorter cycle now
                    if self._cyclic_cmds[commandcode]['cycle'] > cycle:
                        self._cyclic_cmds[commandcode]['cycle'] = cycle
                self.log_debug('Items should read cyclic: {}'.format(self._cyclic_cmds))

        # Process the send config
        if self.has_iattr(item.conf, 'viess_send'):
            commandname = self.get_iattr_value(item.conf, 'viess_send')
            if commandname == None:
                return None
            elif commandname not in self._commandset:
                self.log_err('Item {} contains invalid write command \'{}\'!'.format(item, commandname))
                return None
            
            self.log_info('Item {} writes by using command \'{}\''.format(item, commandname))
            return self.update_item
        else:
            return None

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != 'viessmann' and self.has_iattr(item.conf, 'viess_send'):
            commandname = self.get_iattr_value(item.conf, 'viess_send')

            if type(item) != int:
                value = int(item())
            else:
                value = item()
            self.log_debug('Got item_value: {}'.format(value))

            # Send write command
            self.send_command(commandname, value)

            # If a read command should be sent after write
            if self.has_iattr(item.conf, 'viess_read') and self.has_iattr(item.conf, 'viess_read_afterwrite'):
                readcommandname = self.get_iattr_value(item.conf, 'viess_read')
                readafterwrite = self.get_iattr_value(item.conf, 'viess_read_afterwrite')
                self.log_debug('Attempting read after write for item {}, command {}, delay {}'.format(item, readcommandname, readafterwrite))
                if readcommandname is not None and readafterwrite is not None:
                    aw = float(readafterwrite)
                    time.sleep(aw)
                    self.send_command(readcommandname)
            
            # If commands should be triggered after this write        
            if self.has_iattr(item.conf, 'viess_trigger'):
                trigger = self.get_iattr_value(item.conf, 'viess_trigger')
                if trigger == None:
                    self.log_err('Item {} contains invalid trigger command list \'{}\'!'.format(item, trigger))
                else:
                    tdelay = 5 # default delay
                    if self.has_iattr(item.conf, 'viess_trigger_afterwrite'):
                        tdelay = float(self.get_iattr_value(item.conf, 'viess_trigger_afterwrite'))
                    if type(trigger) != list:
                        trigger = [trigger] 
                    for triggername in trigger:
                        triggername = triggername.strip()
                        if triggername is not None and readafterwrite is not None:
                            self.log_debug('Triggering command {} after write for item {}'.format(triggername, item))
                            time.sleep(tdelay)
                            self.send_command(triggername)

    def handle_cyclic_cmds(self):
        # Read all cyclic commands
        currenttime = time.time()
        for commandcode in list(self._cyclic_cmds.keys()):
            entry = self._cyclic_cmds[commandcode]
            # Is the command already due?
            if entry['nexttime'] <= currenttime:
                commandname = self.commandname_by_commandcode(commandcode)
                self.log_debug('Triggering cyclic read command: {}'.format(commandname))
                self.send_command(commandname)
                entry['nexttime'] = currenttime + entry['cycle']
        
    def send_command(self, commandname, value=None):
        # A read_request telegram looks like this: ACK (1 byte), startbyte (1 byte), data length in bytes (1 byte), request/response (1 byte), read/write (1 byte), addr (2 byte), amount of value bytes expected in answer (1 byte), checksum (1 byte)
        # A write_request telegram looks like this: ACK (1 byte), startbyte (1 byte), data length in bytes (1 byte), request/response (1 byte), read/write (1 byte), addr (2 byte), amount of bytes to be written (1 byte), value (bytes as per last byte), checksum (1 byte)
    
        try:
            self.log_debug('Got a new send job: Command {} with value {}'.format(commandname, value))

            # Get command config
            commandconf = self._commandset[commandname]
            commandcode = (commandconf['addr'])
            commandtype = commandconf['type']
            commandvaluebytes = commandconf['len']
            self.log_debug('commandconf: {}'.format(commandconf))
            
            if commandtype == 'write'and value is not None and value != '':
                              
                # optional check, if value to be send is acceptable range
                # if ('min_value' in commandconf) and ('max_value' in commandconf) and (self.value_check(value) == True)

                # Transform value
                if 'valuetransform' in commandconf:
                    commandtransform = commandconf['valuetransform']
                    value = self.value_transform(value, commandtype, commandtransform)
                    self.log_debug('Transformed value using method {} to {}'.format(commandtransform, value))
         
                # Create Payload / Valuebytes 
                valuebytes = self.int2bytes(value, commandvaluebytes)
                self.log_debug('Created value bytes: {}'.format(self.bytes2hexstring(valuebytes)))
                
                # Build packet1 with valuebytes for write commands
                packet = bytearray()
                packet.extend(self._startbyte)
                packet.extend(self._commandbyteswrite)
                packet.extend(self._request)
                packet.extend(self._write)
                packet.extend(bytes.fromhex(commandcode))
                packet.extend(self.int2bytes(commandvaluebytes,1))
                packet.extend(valuebytes)
                self.log_debug('Preparing command {} with value {} (transformed to value byte \'{}\') to be sent as packet {}.'.format(commandname, value, self.bytes2hexstring(valuebytes), self.bytes2hexstring(packet)))

            if commandtype == 'read':
                # Build packet1
                packet = bytearray()
                packet.extend(self._startbyte)
                packet.extend(self._commandbytesread)
                packet.extend(self._request)
                packet.extend(self._read)
                packet.extend(bytes.fromhex(commandcode))
                packet.extend(self.int2bytes(commandvaluebytes,1))
                self.log_debug('packet: {}'.format(self.bytes2hexstring(packet)))

            # Calculate the checksum
            checksum = self.calc_checksum(packet)
            self.log_debug('Checksum: {}'.format(checksum))
            
            #Add checksum to packet
            packet.extend(self.int2bytes(checksum, 1))
            self.log_debug('packet with checksum: {}'.format(self.bytes2hexstring(packet)))
            
            # Use a lock to allow only one sender at a time
            self._lock.acquire()

            if not self.connected:
                raise Exception("No connection to Viessmann.")
            
            # initiate communication, wenn die letzte Kommunikation länger als 500ms her ist.
            if (self._initialized == False) or ((time.time() - 500) > self._lastbytetime):
                self._initCommunication()
            
            if self._initialized == True:
                try:
                    self.send_bytes(packet)
                    self.log_debug('Successfully sent packet: {}'.format(self.bytes2hexstring(packet)))
                except Exception as e:
                    raise Exception('Exception while sending: {}'.format(e))

                if commandtype == 'read':
                    # Try to receive a packet response with packetlen(gth)
                    packetlen = int(self._commandlength) + int(commandvaluebytes)
                elif commandtype == 'write':
                    packetlen = int(self._commandlength)
                    
                packet = bytearray()
                while self.alive and len(packet) < packetlen:
                    #self.log_debug('packet length current: {}'.format(len(packet)))
                    #self.log_debug('packet length soll: {}'.format(packetlen))
                    try:
                        bytestoreceive = packetlen - len(packet)
                        self.log_debug('Trying to receive {} bytes of the response.'.format(bytestoreceive))
                        chunk = self.read_bytes(bytestoreceive)
                        self.log_debug('Received {} bytes chunk of response: {}'.format(len(chunk), self.bytes2hexstring(chunk)))
                        if len(chunk)  == 0:
                            raise Exception('Received 0 bytes chunk - ignoring packet!')
                        if chunk[:1] != (self._acknowledge):
                            raise Exception('Received invalid chunk, not starting with ACK - ignoring packet!')
                        packet.extend(chunk)
                    except socket.timeout:
                        raise Exception("error receiving reponse: timeout")
                    except Exception as e:
                        raise Exception("error receiving response: {}".format(e))
                # Parse response
                self.parse_response(packet)
            else:
                self.log_debug('Interface not initialized!')
                
        except Exception as e:
            self.disconnect()
            self.log_err("send_command failed: {}".format(e))

        finally:            
            # At the end, release the lock
            self._lock.release()

    def parse_response(self, response):
        self.log_debug('Successfully received response: {}'.format(self.bytes2hexstring(response)))
        # A read_response telegram looks like this: ACK (1 byte), startbyte (1 byte), data length in bytes (1 byte), request/response (1 byte), read/write (1 byte), addr (2 byte), amount of valuebytes (1 byte), value (bytes as per last byte), checksum (1 byte)
        # A write_response telegram looks like this: ACK (1 byte), startbyte (1 byte), data length in bytes (1 byte), request/response (1 byte), read/write (1 byte), addr (2 byte), amount of bytes written (1 byte), checksum (1 byte)

        # Validate checksum
        packetpart = bytearray()
        packetpart.extend(response[1:len(response) - 1]) # cut first byte (ACK) und last byte (checksum)
        self.log_debug('packetpart: {}'.format(self.bytes2hexstring(packetpart)))
        receivedchecksum = response[len(response) - 1]
        self.log_debug('receivedchecksum: {}'.format(receivedchecksum))
        checksum = self.calc_checksum(packetpart)
        self.log_debug('checksum: {}'.format(checksum))
        self.log_debug('receivedchecksum: {}'.format(receivedchecksum))
        if (receivedchecksum != checksum):
            self.log_err('Calculated checksum of {} does not match received checksum of {}! Ignoring reponse.'.format(checksum, receivedchecksum))
            return
        
        # Extract command/adress out of response
        commandcodebytes = response[5:7]
        commandcode = self.bytes2hexstring(commandcodebytes)
        self.log_debug('commandcode: {}'.format(commandcode))
        
        # Extract read / write response
        responsetypecode = response[4]
        self.log_debug('responsetypecode in response package: {}'.format(responsetypecode))
        
        # Extract amount of valuebytes out of response
        valuebytecount = response[7]
        self.log_debug('valuebytecount: {}'.format(valuebytecount))

        # Find items using this response command if not write response
        if commandcode in self._params.keys() and responsetypecode == 1:
            # Extract databytes out of response
            rawdatabytes = bytearray()
            rawdatabytes.extend(response[8:8 + (valuebytecount)])
            self.log_debug('rawdatabytes: {}'.format(self.bytes2hexstring(rawdatabytes)))
            self.log_debug('rawdatabytes: {}'.format(rawdatabytes))
        
            # Iterate over all corresponding items
            for i in range(0, len(self._params[commandcode]['items'])):
                item = self._params[commandcode]['items'][i]
                commandname = self._params[commandcode]['commandname'][i]

                # Get command config
                commandconf = self._commandset[commandname]
                commandtype = commandconf['type']
                commandvaluebytes = commandconf['len']
                commandsignage = commandconf['signage']
                commandvalueresult = commandconf['result']
                commandtransform = commandconf['valuetransform']

                # Extract rawvalue
                rawvalue = self.decode_rawvalue(rawdatabytes, valuebytecount, commandsignage)
                self.log_debug('rawvalue: {}'.format(rawvalue))
           
                # Tranform value
                value = self.value_transform(rawvalue, commandtype, commandtransform)
                value = self.value_form(value, commandvalueresult)
                self.log_debug('Matched command {} and read transformed value {} (raw value was {}) and byte length {}.'.format(commandname, value, rawvalue, commandvaluebytes))

                # Update item
                item(value, 'viessmann')

        elif responsetypecode == 2:
            self.log_info('Write request of adress {} successfull writing {} bytes.'.format(commandcode, valuebytecount))
        else:
            self.log_err('Write request of adress {} NOT successfull writing {} bytes.'.format(commandcode, valuebytecount))

    def run(self):
        self.alive = True
        self._sh.scheduler.add('viessmann-init', self.send_init_commands, prio=5, cycle=600, offset=2)
        maxloops = 20
        loops = 0 
        while self.alive and not self._initread and loops < maxloops:  # wait for init read to finish
            time.sleep(0.5)
            loops += 1
        self._sh.scheduler.remove('viessmann-init')
                
    def stop(self):
        self._sh.scheduler.remove('viessmann-cyclic')
        self.alive = False
        self.disconnect()
       
    def send_init_commands(self):
        try:
            # Do the init read commands
            if self._init_cmds != []:
                if self.connected:
                    self.log_info('Starting initial read commands.')
                    for commandcode in self._init_cmds:
                        commandname = self.commandname_by_commandcode(commandcode)
                        self.send_command(commandname)
                        self.log_debug('send_init_commands {}.'.format(commandname))
    
            # Find the shortest cycle
            shortestcycle = -1
            for commandname in list(self._cyclic_cmds.keys()):
                entry = self._cyclic_cmds[commandname]
                if shortestcycle == -1 or entry['cycle'] < shortestcycle:
                    shortestcycle = entry['cycle']
    
            # Start the worker thread
            if shortestcycle != -1:
                # Balance unnecessary calls and precision
                workercycle = int(shortestcycle / 2)
                self._sh.scheduler.add('viessmann-cyclic', self.handle_cyclic_cmds, cycle=workercycle, prio=5, offset=0)
                self.log_info('Added cyclic worker thread ({} sec cycle). Shortest item update cycle found: {} sec.'.format(workercycle, shortestcycle))
        finally:
            self._initread = True

    def calc_checksum(self, packet):
        # Berechnung der Checksumme aus dem zu schreibenden Daten in DEZ
        checksum = 0
        # Standard Rückgabewert definieren (Lesen nicht erfolgreich)
        returnvalue = False
        # Es wurde das Startbyte gefunden
        startbytefound = False
        # Sofern die Länge vom bytestring größer als die Mindestlänge 2 ist, kann die Aktion ausgeführt werden.
        packetpartwork = packet
        #self.log_debug('bytestringwork: {}'.format(packetpartwork))
        if ((len(packetpartwork)) > 0):
        # Bytestring Byte für Byte auswerten. Wenn nur noch ein Byte übrig ist, dann stoppen. Dies ist dann das Checksummen Byte
            while ((len(packetpartwork)) > 0):
                # Erstes Byte zwischenspeichern
                leftbyte = packetpartwork[:1]
                #self.log_debug('leftbyte: {}'.format(leftbyte))
                # Sofern das Startbyte gefunden wurde, muss das aktuelle Byte mit in die Berechnung einbezogen werden.
                if (startbytefound == True):
                    # Checksumme berechnen. Sie bildet sich aus der Aufsummierung der einzelenen Bytes
                    checksum = checksum + ord(leftbyte)
                    #self.log_debug('checksum: {}'.format(checksum))
                # Suche nach dem Startbyte b'\x41'
                elif (leftbyte == b'\x41'):
                    # Es handelt sich um das Startbyte. Ab dem nächsten Byte handelt es sich um Nutzdaten, die mit in die Checksumme einfließen.
                    startbytefound = True
                # Bytestring um das erste Byte verkürzen
                packetpartwork = packetpartwork[1:]
        else:
            self.log_err('Checksumme kann nicht berechnet werden.')
        
        if (checksum >= 512):
            checksum = checksum - 512
        elif (checksum >= 256):
            checksum = checksum - 256
        return checksum
    
    def log_debug(self, text):    
        self.logger.debug('viessmann: {}'.format(text))

    def log_info(self, text):    
        self.logger.info('viessmann: {}'.format(text))

    def log_err(self, text):    
        self.logger.error('viessmann: {}'.format(text))
    
    def int2bytes(self, value, length):
        # Limit value to the passed byte length
        value = value % (2 ** (length * 8))
        return value.to_bytes(length, byteorder='big')
    
    def bytes2int(self, bytesvalue):
        return int.from_bytes(bytesvalue, byteorder='big', signed=False)
    
    def bytes2hexstring(self, bytesvalue):
        return "".join("{:02x}".format(c) for c in bytesvalue)
                
    def encode_specialchars(self, packet):
        specialchar = self._controlset['SpecialCharacter']
        encodedpacket = bytearray()
        for count in range(len(packet)):
            char = packet[count]
            encodedpacket.append(char)
            if char == specialchar:
                # Encoding works by doubling the special char
                self.log_debug('Encoded special char at position {} of data bytes {}.'.format(count, self.bytes2hexstring(packet)))
                encodedpacket.append(char)
        #self.log_debug('Encoded data bytes: {}.'.format(encodedpacket))
        return encodedpacket
    
    def decode_rawvalue(self, rawdatabytes, valuebytecount, commandsignage):
        byteindex = 0
        rawvalue = 0
        while (len(rawdatabytes) > 0):
            # Erstes Byte zwischenspeichern
            leftbyte = rawdatabytes[:1]
            # Wert des Bytes ermitteln
            value = int(ord(leftbyte))
            # Gewichten / Multiplizieren
            if (byteindex > 0):
                value = int(value * pow(256, byteindex))
            # Aufaddieren der einzelnen Bytes
            rawvalue = rawvalue + value
            # Byteindex hochzählen, damit das Byte mit entsprechend mit 1, 256, 65536, 16777216, usw. multipliziert werden kann
            byteindex = byteindex + 1
            # Bytestring um das erste Byte verkürzen
            rawdatabytes = rawdatabytes[1:]
        # Signed/Unsigned berücksichtigen
        if (commandsignage == 'signed'):
            if ((byteindex == 1) and (rawvalue > 127)):
                rawvalue = (256 - rawvalue) * (-1)
            elif ((byteindex == 2) and (rawvalue > 32767)):
                rawvalue = (65536 - rawvalue) * (-1)
            #elif ((byteindex == 4) and (rawvalue > 2147483647‬)):
            #    rawvalue = (4294967296‬ - rawvalue) * (-1)
        return rawvalue
    
    def value_check(self, value):
        returnvalue = False
        # get min value
        item_min_value = float(commandconf['min_value'])
        # get max value
        item_max_value = float(commandconf['max_value'])
        if ((value >= item_min_value) and (value <= item_max_value)):
            returnvalue = True
        return returnvalue
        
    def value_transform(self, value, commandtype, transformmethod):
        if transformmethod == 'non':
            if commandtype == 'read':
                return value
            elif commandtype == 'write':
                return value
        elif transformmethod == 'div10':
            if commandtype == 'read':
                return int(value) / 10
            elif commandtype == 'write':
                return int(int(value) * 10)
        elif transformmethod == 'div3600':
            if commandtype == 'read':
                return int(value) / 3600
            elif commandtype == 'write':
                return int(int(value) * 3600)

    def value_form(self, value, commandvalueresult):        
        if commandvalueresult == 'int':
            value = int(value)
        elif commandvalueresult == 'bool':
            value = bool(value)
        elif commandvalueresult == 'float':
            value = round(value, 2)
        return value
    
    def commandname_by_commandcode(self, commandcode):
        for commandname in self._commandset.keys():
            if self._commandset[commandname]['addr'] == commandcode:
                return commandname
        return None

    def _initCommunication(self):
        self.log_info('Init Communication')
        # Standard Rückgabewert definieren (Initialisierung fehlgeschlagen)
        returnvalue = False
        
        # Merker: Wurde der Initialisierungsstring b'\x16\x00\x00' gesendet.
        # Wird hierauf dann mit b'\x06' geantwortet ist die Komunikation aufgebaut.
        initstringsent = False
        
        # Schnittstelle zurücksetzen
        self.send_bytes(self._resetcommand)
        # Lesen des Antwortbytes
        self.read_byte()
        
        # Initialisierung ca. 10mal probieren
        i = 0
        while (i < 10):
            if ((initstringsent == True) and (self._lastbyte == self._acknowledge)):
                # Schnittstelle hat auf den Initialisierungsstring mit OK geantwortet. Die Abfrage von Werten kann beginnen. Diese Funktion meldet hierzu True zurück.
                returnvalue = True
                # Schleife abbrechen, da Initialisierung erfolgreich
                break
            if ((self._lastbyte == self._acknowledge) or (self._lastbyte == self._notinitiated)):
                # Schnittstelle ist zurückgesetzt und wartet auf Daten
                # b'\x05' = Warten auf Initialisierungsstring
                # b'\x06' = Schnittstelle initialisiert
                # In beiden Fällen wird zur Sicherheit der Initialisierungsstring gesendet.
                self.send_bytes(self._synccommand)
                # Merker setzen: Initialisierungstring wurde zuletzt gesendet
                initstringsent = True
                
            elif (self._lastbyte == self._initerror):
                # Die Schnittstelle hat einen Fehler zurückgemeldet.
                self.log_err('Die Schnittstelle hat einen Fehler zurückgemeldet (\x15), Schleifenindex {}'.format(i))
                # Schnittstelle zurücksetzen
                self.send_bytes(self._resetcommand)
                # Merker rücksetzen: Initialisierungstring wurde nicht zuletzt gesendet
                initstringsent = False
            else:
                # Letzter Wert ist undefiniert
                # Schnittstelle zurücksetzen
                self.send_bytes(self._resetcommand)
                # Merker rücksetzen: Initialisierungstring wurde nicht zuletzt gesendet
                initstringsent = False
            # Lesen eines Bytes
            self.read_byte()
            # Counter hochzählen
            i = i + 1
        # Zurückgeben, ob die Initialisierung erfolgreich war
        # True  = Initialisierung erfolgreich. Letztes Byte war \x06 und nicht zu lange her
        # False = Initialisierung fehlgeschlagen.
        self.log_debug('Communication initialized: {}'.format(returnvalue))
        self._initialized = returnvalue