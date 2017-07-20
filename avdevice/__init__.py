#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <Onkel Andy>                    <onkelandy@hotmail.com>
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Plugin to control AV Devices via TCP and/or RS232
#  Tested with Pioneer AV Receivers.
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

import logging
from lib.model.smartplugin import SmartPlugin
import threading
import os
import io
import time
import re
import codecs
import errno
from itertools import groupby

import serial
import socket


class AVDevice(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.3.0"

    def __init__(self,
                 smarthome,
                 model,
                 manufacturer='',
                 ignoreresponse='',
                 forcebuffer='',
                 inputignoredisplay='',
                 dependson=None,
                 rs232=None,
                 tcp=None,
                 errorresponse='E02,E04,E06',
                 resetonerror=False,
                 depend0_power0=False,
                 depend0_volume0=False,
                 sendretries=10,
                 resendwait=1.0,
                 reconnectretries=13,
                 secondstokeep=50,
                 reconnectcycle=10,
                 responsebuffer='-5',
                 autoreconnect=False
                 ):
        self.logger = logging.getLogger(__name__)
        self._sh = smarthome
        self._model = model
        self._manufacturer = manufacturer
        self._name = self.get_instance_name()
        self._serialwrapper = None
        self._serial = None

        try:
            self._rs232 = re.sub('[ ]', '', str(rs232)).split(",")[0]
            if self._rs232 == 'None': self._rs232 = None
            self.logger.debug("Initializing Serial {}: Serialport is {}.".format(self._name,self._rs232))
        except:
            self._rs232 = None
            self.logger.warning("Initializing Serial {}: Serial Port is {}. Error: {}.".format(self._name,self._baud,err))
        if self._rs232 is not None:
            try:
                self._baud = int(re.sub('[ ]', '', str(rs232)).split(",")[1])
                self.logger.debug("Initializing Serial {}: Baudrate is {}.".format(self._name,self._baud))
            except Exception as err:
                self._baud = 9600            
                self.logger.debug("Initializing Serial {}: Using standard Baudrate {}. Because: {}.".format(self._name,self._baud,err))
            try:
                self._timeout = re.sub('[ ]', '', str(rs232)).split(",")[2]
                self.logger.debug("Initializing Serial {}: Timeout is {}.".format(self._name,self._timeout))
            except Exception as err:
                self._timeout = 0.1           
                self.logger.debug("Initializing Serial {}: Using standard timeout {}. Because: {}.".format(self._name,self._timeout,err))
            try:
                self._writetimeout = re.sub('[ ]', '', str(rs232)).split(",")[3]
                self.logger.debug("Initializing Serial {}: write_timeout is {}.".format(self._name,self._writetimeout))
            except Exception as err:
                self._writetimeout = 0.1           
                self.logger.debug("Initializing Serial {}: Using standard write_timeout {}. Because: {}.".format(self._name,self._writetimeout,err))


        try:
            self._tcp = re.sub('[ ]', '', str(tcp)).split(",")[0]
            if self._tcp == 'None': self._tcp = None
            self.logger.debug("Initializing TCP {}: IP is {}.".format(self._name,self._tcp))
        except Exception as err:
            self._tcp = None
            self.logger.warning("Initializing TCP {}: Host is {}. Because: {}.".format(self._name,self._baud,err))
        if self._tcp is not None:
            try:
                self._port = int(re.sub('[ ]', '', str(tcp)).split(",")[1])
                self.logger.debug("Initializing TCP {}: Port is {}.".format(self._name,self._port))
            except Exception as err:
                self._port = None
                self.logger.warning("Initializing TCP {}: Port is {}. Because: {}.".format(self._name,self._port,err))

            
        self._threadlock_standard = threading.Lock()        
        self._threadlock_send = threading.Lock()
        self._threadlock_buffer = threading.Lock()
        self._threadlock_dict = threading.Lock()
        self._threadlock_parse = threading.Lock()
        self._threadlock_reset = threading.Lock()
        self._threadlock_update = threading.Lock()
        self._lock = threading.Condition(self._threadlock_standard)
        self._sendlock = threading.Condition(self._threadlock_send)
        self._bufferlock = threading.Condition(self._threadlock_buffer)        
        self._dictlock = threading.Condition(self._threadlock_dict)
        self._parselock = threading.Condition(self._threadlock_parse)
        self._resetlock = threading.Condition(self._threadlock_reset)
        self._updatelock = threading.Condition(self._threadlock_update)
        self.alive = False
        self._functions = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        self._items = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        self._query_zonecommands = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}
        self._items_speakers = {'zone1': {}, 'zone2': {}, 'zone3': {}}
        self._send_commands = []
        self._keep_commands = {}
        self._query_commands = []
        self._power_commands = []
        self._response_commands = {}
        self._number_of_zones = 0
        self._trigger_reconnect = True
        self._reconnect_counter = 0
        self._resend_counter = 0
        self._resend_wait = float(resendwait)
        self._secondstokeep = int(secondstokeep)
        self._requery_counter = 0
        self._sendingcommand = 'done'
        self._auto_reconnect = autoreconnect
        self._resend_retries = int(sendretries)
        self._reconnect_retries = int(reconnectretries)
        self._specialcommands = {}        
        self._is_connected = []

        try:
            self._dependson = re.sub('[ ]', '', dependson).split(",")[0]
            self.logger.debug("Initializing {}: Dependson Item: {}.".format(self._name, self._dependson))            
        except:
            self._dependson = dependson
            self.logger.debug("Initializing {}: Dependson Item: {}. No value for item given, assuming True.".format(self._name, self._dependson))
        try:
            self._dependson_value = re.sub('[ ]', '', dependson).split(",")[1]
            if str(self._dependson_value).lower() in ['1', 'yes', 'true', 'on']:
                self._dependson_value = True
            elif str(self._dependson_value).lower() in ['0', 'no', 'false', 'off']:
                self._dependson_value = False
        except:
            self._dependson_value = True
        
        if str(depend0_power0).lower() in ['1', 'yes', 'true', 'on'] and self._dependson:
            self._depend0_power0 = True
        elif str(depend0_power0).lower() in ['0', 'no', 'false', 'off'] or not self._dependson:
            self._depend0_power0 = False
        if str(depend0_volume0).lower() in ['1', 'yes', 'true', 'on'] and self._dependson:
            self._depend0_volume0 = True
        elif str(depend0_volume0).lower() in ['0', 'no', 'false', 'off'] or not self._dependson:
            self._depend0_volume0 = False
            
        
        if str(responsebuffer).lower() in ['1', 'yes', 'true', 'on']:
            self._response_buffer = True
        elif str(responsebuffer).lower() in ['0', 'no', 'false', 'off']:
            self._response_buffer = False
        elif responsebuffer.lstrip("-").isdigit():
            self._response_buffer = int(responsebuffer)
        if str(resetonerror).lower() in ['1', 'yes', 'true', 'on']:
            self._reset_onerror = True
        elif str(resetonerror).lower() in ['0', 'no', 'false', 'off']:
            self._reset_onerror = False
        self._ignoreresponse = re.sub('[ ]', '', ignoreresponse).split(",")
        self._errorresponse = re.sub('[ ]', '', errorresponse).split(",")
        self._force_buffer = re.sub('[ ]', '', forcebuffer).split(",")
        self._ignoredisplay = re.sub('[ ]', '', inputignoredisplay).split(",")
        self.logger.debug("Initializing {}: Special Settings: Ignoring responses {}.".format(self._name, self._ignoreresponse))
        self.logger.debug("Initializing {}: Special Settings: Error responses {}.".format(self._name, self._errorresponse))
        self.logger.debug("Initializing {}: Special Settings: Force buffer {}.".format(self._name, self._force_buffer))
        self.logger.debug("Initializing {}: Special Settings: Ignore Display {}".format(self._name, self._ignoredisplay))
        
        smarthome.scheduler.add('avdevice-serial-reconnect',self.connect_serial, cycle=reconnectcycle)
        smarthome.scheduler.change('avdevice-serial-reconnect', active=False)
        smarthome.scheduler.add('avdevice-tcp-reconnect',self.connect_tcp, cycle=reconnectcycle)
        smarthome.scheduler.change('avdevice-tcp-reconnect', active=False)        
        

    def _create_querycommands(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self.logger.debug("Initializing {}: Starting to create query commands. Lock is {}".format(
                self._name, self._threadlock_standard.locked()))
            displaycommand = ''
            length = 0
            for zone in range(0, self._number_of_zones+1):                
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        querycommand = self._functions['zone{}'.format(zone)][command][3]
                        responselist = []
                        splitresponse = self._functions['zone{}'.format(zone)][command][4].split("|")
                        for split in splitresponse:
                            if split.count('*') > 0:
                                responselist.append(split.strip())
                        responsestring = "|".join(responselist)        
                        responsecommand = re.sub('[*]', '', responsestring)
                        if not '{},{},{}'.format(querycommand, querycommand, responsecommand) in self._query_zonecommands['zone{}'.format(zone)] and not responsecommand == '' and not responsecommand == ' ' and not responsecommand == 'none' and not querycommand == '' and not self._functions['zone{}'.format(zone)][command][4] in self._ignoreresponse:
                            if not re.sub('[*]', '', self._functions['zone{}'.format(zone)][command][4]) in self._specialcommands['Display']['Command']:
                                self._query_zonecommands['zone{}'.format(zone)].append('{},{},{}'.format(
                                    querycommand, querycommand, responsecommand))
                            else:
                                displaycommand = '{},{},{}'.format(querycommand, querycommand, responsecommand)
                                self.logger.debug("Initializing {}: Displaycommand: {}".format(self._name, displaycommand))
                        if not '{},{},{}'.format(querycommand, querycommand, responsecommand) in self._query_commands and not responsecommand == '' and not responsecommand == ' ' and not responsecommand == 'none' and not querycommand == '' and not self._functions['zone{}'.format(zone)][command][4] in self._ignoreresponse:
                            if not re.sub('[*]', '', self._functions['zone{}'.format(zone)][command][4]) in self._specialcommands['Display']['Command']:
                                self._query_commands.append('{},{},{}'.format(
                                    querycommand, querycommand, responsecommand))
                            else:
                                displaycommand = '{},{},{}'.format(querycommand, querycommand, responsecommand)
                                #self.logger.debug("Initializing {}: Displaycommand: {}".format(self._name, displaycommand))
                    except Exception as err:
                        self.logger.error("Initializing {}: Problems adding query commands for command {}. Error: {}".format(
                            self._name, command, err))
                length += len(self._query_zonecommands['zone{}'.format(zone)])
            if not displaycommand == '': 
                self._query_commands.append(displaycommand)
                length += 1                            
        except Exception as err:
            self.logger.error(
                "Initializing {}: Problems searching for query commands. Error: {}".format(self._name, err))
        finally:            
            if self._threadlock_standard.locked():  self._lock.release()
            self._query_commands_count = length
            self.logger.debug("Initializing {}: Created query commands: {}. Created query zone commands: {}. Lock is now {}".format(
                self._name, self._query_commands, self._query_zonecommands, self._threadlock_standard.locked()))
            self.logger.info("Initializing {}: Created query commands, including {} entries.".format(
                self._name, self._query_commands_count))            
            self.connect()

    def _create_powercommands(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self.logger.debug("Initializing {}: Starting to create power commands. Lock is {}".format(
                self._name, self._threadlock_standard.locked()))
            for zone in range(0, self._number_of_zones+1):
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        if command.startswith('power on'):
                            try:
                                value = re.sub('\*\*', 'ON', self._functions['zone{}'.format(zone)][command][4])
                            except:
                                if self._functions['zone{}'.format(zone)][command][6] == 'yes':
                                    value = re.sub('[*]', '0', self._functions['zone{}'.format(zone)][command][4])
                                else:
                                    value = re.sub('[*]', '1', self._functions['zone{}'.format(zone)][command][4])
                            
                            combined = '{},{},{}'.format(self._functions['zone{}'.format(zone)][command][2], self._functions['zone{}'.format(zone)][command][3], value) 
                            self._power_commands.append(combined)
                    except Exception as err:
                        self.logger.warning("Initializing {}: Problems searching power commands for {} in zone {}. Error: {}".format(self._name, command, zone, err))
        except Exception as err:
            self.logger.warning("Initializing {}: Problems creating power commands. Error: {}".format(self._name, err))
        finally:
            if self._threadlock_standard.locked():  self._lock.release()
            self.logger.debug("Initializing {}: Finished creating power commands: {}. Lock is released. Lock is now {}".format(
                self._name, self._power_commands, self._threadlock_standard.locked()))
            self._create_querycommands()

    def _create_responsecommands(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self.logger.debug("Initializing {}: Starting to create response commands. Lock is {}".format(
                self._name, self._threadlock_standard.locked()))
            for zone in range(0, self._number_of_zones+1):
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        response_to_split = self._functions['zone{}'.format(zone)][command][4].split("|")
                        for response in response_to_split:
                            valuelength = response.count('*')
                                
                            if response.find('*') >= 0:
                                position = response.index('*')
                            else:
                                position = 0
                            response = re.sub('[*]', '', response)
                            commandlength = len(response)
                            try:
                                inverse = self._functions['zone{}'.format(zone)][command][6]
                            except:
                                inverse = 'no'
                            try:
                                type = self._functions['zone{}'.format(zone)][command][8]
                            except:
                                type = '' 
                            function = self._functions['zone{}'.format(zone)][command][1].split(" ")[0]
                            item = self._items['zone{}'.format(zone)][function]['Item']                                                           
                            self.logger.debug("Initializing {}: Response: {}, Function: {}, Item: {}, Type: {}".format(self._name, response, function, item, type))
                            if self._functions['zone{}'.format(zone)][command][5].lower() in ['r', 'rw']:
                                try:
                                    if function == 'display':                   
                                        if response in self._ignoreresponse and not '' in self._ignoreresponse:
                                            self._specialcommands['Display'] = {'Command': response, 'Ignore': 1}
                                        else:
                                            self._specialcommands['Display'] = {'Command': response, 'Ignore': 0}
                                        #self.logger.debug("Initializing {}: Found Display Command and updated it: {}".format(self._name, self._specialcommands))
                                    elif function == 'input':              
                                        if 'Input' not in self._specialcommands:
                                            self._specialcommands['Input'] = {'Command': [response], 'Ignore': [0]}
                                        else:
                                            self._specialcommands['Input']['Command'].append(response)
                                            self._specialcommands['Input']['Ignore'].append(0)
                                        #self.logger.debug("Initializing {}: Found Input Command and added it to display commands.".format(self._name))
                                    elif (function == 'title' or function == 'station' or function == 'genre'):                 
                                         if 'Nowplaying' not in self._specialcommands:
                                            self._specialcommands['Nowplaying'] = {'Command': [response]}
                                         else:
                                            self._specialcommands['Nowplaying']['Command'].append(response)
                                         #self.logger.debug("Initializing {}: Found Now Playing Command and updated it: {}".format(self._name, self._specialcommands))
                                    elif (function == 'speakers'):                 
                                         if 'Speakers' not in self._specialcommands:
                                            self._specialcommands['Speakers'] = {'Command': [response]}
                                         else:
                                            self._specialcommands['Speakers']['Command'].append(response)
                                         #self.logger.debug("Initializing {}: Found Speakers Command and updated it: {}".format(self._name, self._specialcommands))
                                except Exception as err:
                                    self.logger.debug("Initializing {}: No Special Commands set. Message: {}".format(self._name, err))
                                try:
                                    if not item in self._response_commands[response]:
                                        self._response_commands[response][3].append(item[0])
                                except Exception as err:
                                    self._response_commands[response] = [
                                        valuelength, commandlength, position, item, function, 'zone{}'.format(zone), inverse, type]
                        else:
                            #self.logger.debug("Initializing {}: Item {} is not set to readable, ignoring.".format(self._name, item))
                            pass
                    except Exception as err:
                        self.logger.warning("Initializing {}: Problems searching functions for {} in zone {}. Either it is not in the textfile or wrong instance name defined. Error: {}".format(self._name, command, zone, err))
        except Exception as err:
            self.logger.error(
                "Initializing {}: Problems creating response commands. Error: {}".format(self._name, err))
        finally:
            self.logger.debug("Initializing {}: Response commands: {}".format(
                self._name, self._response_commands))
            if not 'Display' in self._specialcommands:
                self._specialcommands['Display'] = {'Command': '', 'Ignore': 1}
            if not 'Input' in self._specialcommands:
                self._specialcommands['Input'] = {'Command': '', 'Ignore': 1}
            if not 'Nowplaying' in self._specialcommands:
                self._specialcommands['Nowplaying'] = {'Command': ''}
            if not 'Speakers' in self._specialcommands:
                self._specialcommands['Speakers'] = {'Command': ''}
            self.logger.debug("Initializing {}: Special commands for solving Display issues: {}".format(
                self._name, self._specialcommands))
            self.logger.info("Initializing {}: Created response commands, including {} entries.".format(
                self._name, len(self._response_commands)))
            if self._threadlock_standard.locked():  self._lock.release()
            self.logger.debug("Initializing {}: Finished creating response commands. Lock is released. Lock is now {}".format(
                self._name, self._threadlock_standard.locked()))
            self._create_powercommands()
            
            
    def _read_commandfile(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self.logger.debug("Initializing {}: Starting to read file for model {}. Lock is {}".format(
                self._name, self._model, self._threadlock_standard.locked()))
            filename = '{}/plugins/avdevice/{}.txt'.format(
                self._sh.base_dir, self._model)

            commands = codecs.open(filename, 'r', 'utf-8')
            zones = [0]
            for line in commands:
                try:
                    line = re.sub('[!@#$\\n\\r]', '', line)
                    if line == '':
                        function = ''
                    else:
                        row = line.split(";")
                        if row[0] == '': row[0] = '0'
                        function = row[1]
                        itemtest = re.sub(' set| on| off','', function)  
                        for i in range(0,9):
                            try:
                                test = row[i]
                            except IndexError:
                                if i == 5:
                                    row.append('RW')
                                if i == 6:
                                    row.append('no')
                                if i == 8 and "set" in function:
                                    row.append('num')
                                elif i == 8 and ("on" in function or "off" in function):
                                    row.append('bool')
                                elif i == 8 and ("+" in function or "-" in function):
                                    row.append('bool')
                                else:
                                    row.append('')
                        try:
                            itemkeys = self._items['zone{}'.format(row[0])].keys()
                        except:
                            itemkeys = []
                    if (function == "FUNCTION") or function == '':
                        pass
                    elif itemtest in itemkeys:
                        if row[0] == '0' or row[0] == '':                            
                            self._functions['zone0'][function] = row
                        elif row[0] == '1':
                            self._functions['zone1'][function] = row
                        elif row[0] == '2':
                            self._functions['zone2'][function] = row
                        elif row[0] == '3':
                            self._functions['zone3'][function] = row
                        elif row[0] == '4':
                            self._functions['zone4'][function] = row
                        else:
                            self.logger.error(
                                "Initializing {}: Error in Commandfile on line: {}".format(self._name, line))
                        if not int(row[0]) in zones:
                            zones.append(int(row[0]))
                    else:
                        self.logger.warning("Initializing {}: Function {} for zone {} not used by any item. Re-visit items and config file!".format(self._name, function, row[0]))
                except Exception as err:
                    self.logger.error(
                        "Initializing {}: Problems parsing command file. Error: {}".format(self._name, err))
            self._number_of_zones = max(zones)
            self.logger.debug("Initializing {}: Number of zones: {}".format(
                self._name, self._number_of_zones))
            commands.close()
        except Exception as err:
            self.logger.error(
                "Initializing {}: Problems loading command file. Error: {}".format(self._name, err))
        finally:
            self.logger.info("Initializing {}: Created functions list, including entries for {} zones.".format(
                self._name, self._number_of_zones))
            self.logger.debug("Initializing {}: Functions: {}".format(
                self._name, self._functions))
            if self._threadlock_standard.locked():  self._lock.release()
            self.logger.debug("Initializing {}: Finishing reading file. Lock is released. Lock is now {}".format(
                self._name, self._threadlock_standard.locked()))
            self._create_responsecommands()

    def _wait(self, time_lapse):
        time_start = time.time()
        time_end = (time_start + time_lapse)

        while time_end > time.time():
            pass

    def _resetitem(self):
        self._resetlock.acquire(timeout=2)
        try:
            resetting = None
            try:
                response = self._sendingcommand.split(",")[2].split("|")  
                self.logger.debug("Resetting {}: Searching for suiting command for sendingcommand response: {}.".format(self._name, response))  
            except Exception as e:                    
                response = self._send_commands[0].split(",")[2].split("|")                
                self.logger.warning("Resetting {}: Cannot find Sendingcommand. Using first Command in queue: {}.".format(self._name, response))
            for key in self._response_commands:                                
                #self.logger.debug("Resetting {}: Trying to reset Item. Comparing: {} with {}".format(self._name, key,response))
                for resp in response:
                    if resp.startswith(key, 0, self._response_commands[key][1]):
                        keyfound = True
                    else:
                        keyfound = False                
                if keyfound == True:
                    zone = self._response_commands[key][5]
                    previousvalue = self._items[zone][self._response_commands[key][4]]['Value']
                    for item in self._response_commands[key][3]:
                        self.logger.info("Resetting {}: Resetting Item {} to {}".format(
                            self._name, item, previousvalue))
                        item(previousvalue, 'AVDevice', self._tcp)
                    if key in self._specialcommands['Speakers']['Command']:
                        for speaker in self._items_speakers[zone]:
                            previousvalue = self._items_speakers[zone][speaker]['Value']
                            for item in self._items_speakers[zone][speaker]['Item']:
                                item(previousvalue, 'AVDevice', self._tcp)
                                self.logger.info("Resetting {}: Resetting additional speaker item {} to value {}".format(self._name, item, previousvalue))
                    resetting = self._response_commands[key][3]
                    return resetting
                    if self._threadlock_reset.locked(): self._resetlock.notify()
                    break
            self._trigger_reconnect = False
            return resetting
            self.logger.debug("Resetting {}: Deleted first entry of Send Commands. They are now: {}".format(
                self._name, self._send_commands))
        except Exception as err:
            self.logger.error(
                "Resetting {}: Problem resetting Item. Error: {}".format(self._name, err))
            return 'ERROR'
        finally:
            if self._threadlock_reset.locked(): self._resetlock.release()

    def _resetondisconnect(self, caller):
        self._resetlock.acquire(timeout=2)
        self.logger.debug('Resetting {}: Starting to reset. Called by {}'.format(self._name, caller))
        try:
            for zone in self._items:
                if 'power' in self._items[zone].keys() and self._depend0_power0 == True:
                    self._items[zone]['power']['Value'] = 0
                    for singleitem in self._items[zone]['power']['Item']:
                        singleitem(0, 'AVDevice', self._tcp)                        
                        self.logger.debug('Resetting {}: Power to 0 for item {}'.format(self._name, singleitem))
                if 'speakers' in self._items[zone].keys() and self._depend0_power0 == True:
                    self._items[zone]['speakers']['Value'] = 0
                    for item in self._items_speakers[zone].keys():
                        self._items_speakers[zone][item]['Value'] = 0
                        for singleitem in self._items_speakers[zone][item]['Item']:
                            singleitem(0, 'AVDevice', self._tcp)
                            self.logger.debug('Resetting {}: Speakers to 0 for item {}'.format(self._name, singleitem))
                    for singleitem in self._items[zone]['speakers']['Item']:
                        singleitem(0, 'AVDevice', self._tcp)
                        self.logger.debug('Resetting {}: Speakers to 0 for item {}'.format(self._name, singleitem))
                if 'volume' in self._items[zone].keys() and self._depend0_volume0 == True:
                    self._items[zone]['volume']['Value'] = 0
                    for singleitem in self._items[zone]['volume']['Item']:
                        singleitem(0, 'AVDevice', self._tcp)
                        self.logger.debug('Resetting {}: Volume to 0 for item {}'.format(self._name, singleitem))
            self.logger.debug('Resetting {}: Done.'.format(self._name))
        except Exception as err:
            self.logger.warning(
                'Resetting {}: Problem resetting Item. Error: {}'.format(self._name, err))
            return None
        finally:
            if self._threadlock_reset.locked():  self._resetlock.release()
            
    def _write_itemsdict(self, data):
        self._dictlock.acquire(timeout=2)
        try:                       
            self.logger.debug("Storing Values {}: Starting to store value in dictionary. Lock is: {}.".format(self._name, self._threadlock_dict.locked()))
            for command in self._response_commands.keys():                
                if self._response_commands[command][1] == self._response_commands[command][2]:
                    commandstart = 0
                    commandend = self._response_commands[command][2]
                else:
                    commandstart = self._response_commands[command][0]
                    commandend = self._response_commands[command][0] + self._response_commands[command][1]

                valuestart = self._response_commands[command][2]
                valueend = self._response_commands[command][2] + self._response_commands[command][0]
                function = self._response_commands[command][4]
                
                if data[commandstart:commandend] == command:
                    zone = self._response_commands[command][5]
                    value = receivedvalue = data[valuestart:valueend]
                    if self._response_commands[command][7] == 'bool' and not value == '':
                        self.logger.debug("Storing Values {}: Limiting bool value for received data.".format(self._name))
                        if self._manufacturer.lower() == 'epson':
                            try:
                                value = max(min(int(value), 1), 0)
                                self.logger.debug("Parsing Input {}: Limiting bool value for {} with received value {} to {}.".format(
                                    self._name, self._items[zone][function], receivedvalue, value))  
                            except:
                                pass
                        if receivedvalue.lower() == 'on' or receivedvalue == 1:
                            value = True
                        if receivedvalue.lower() == 'off' or receivedvalue == 0:
                            value = False
                        
                    if self._response_commands[command][6].lower() in ['1', 'true', 'yes', 'on']:
                        value = False if int(receivedvalue) > 0 else True
                               
                    self._items[zone][function]['Value'] = value
                    self.logger.debug("Storing Values {}: Found writeable dict key: {}. Zone: {}. Value: {}. Function: {}.".format(self._name, command, zone, value, function))
                    return self._items[zone][function], value
                    if self._threadlock_dict.locked(): self._dictlock.notify()                    
                    break                   
        except Exception as err:
            self.logger.error(
                "Storing Values {}: Problems creating items dictionary. Error: {}".format(self._name, err))
        finally:
            if self._threadlock_dict.locked(): self._dictlock.release()
            self.logger.debug("Storing Values {}: Finished. Lock is: {}.".format(self._name, self._threadlock_dict.locked()))

    def parse_item(self, item):        
        if self._tcp is not None or self._rs232 is not None:
            #self.logger.debug("Initializing {}: Parsing item: {}. Dependson: {}".format(self._name, item, self._dependson))
            if self.has_iattr(item.conf, 'avdevice'):
                info = self.get_iattr_value(item.conf, 'avdevice')                
                if (info is None):
                    return None
                else:
                    self._items['zone0'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif self.has_iattr(item.conf, 'avdevice_zone0'):
                info = self.get_iattr_value(item.conf, 'avdevice_zone0')
                if (info is None):
                    return None
                else:
                    self._items['zone0'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif self.has_iattr(item.conf, 'avdevice_zone1'):
                info = self.get_iattr_value(item.conf, 'avdevice_zone1')
                if (info is None):
                    return None
                else:
                    self._items['zone1'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif self.has_iattr(item.conf, 'avdevice_zone2'):
                info = self.get_iattr_value(item.conf, 'avdevice_zone2')
                if (info is None):
                    return None
                else:
                    self._items['zone2'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif self.has_iattr(item.conf, 'avdevice_zone3'):
                info = self.get_iattr_value(item.conf, 'avdevice_zone3')
                if (info is None):
                    return None
                else:
                    self._items['zone3'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif self.has_iattr(item.conf, 'avdevice_zone4'):
                info = self.get_iattr_value(item.conf, 'avdevice_zone4')
                if (info is None):
                    return None
                else:
                    self._items_['zone4'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif self.has_iattr(item.conf, 'avdevice_zone1_speakers'):
                info = self.get_iattr_value(item.conf, 'avdevice_zone1_speakers')
                if (info is None):
                    return None
                else:
                    self._items_speakers['zone1'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif self.has_iattr(item.conf, 'avdevice_zone2_speakers'):
                info = self.get_iattr_value(item.conf, 'avdevice_zone2_speakers')
                if (info is None):
                    return None
                else:
                    self._items_speakers['zone2'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif self.has_iattr(item.conf, 'avdevice_zone3_speakers'):
                info = self.get_iattr_value(item.conf, 'avdevice_zone3_speakers')
                if (info is None):
                    return None
                else:
                    self._items_speakers['zone3'][info] = {'Item': [item], 'Value': item()}
                    return self.update_item
            elif str(item) == self._dependson:
                self._items['zone0']['dependson'] = {'Item': self._dependson, 'Value': self._dependson_value}
                self.logger.debug("Initializing {}: Dependson Item found: {}".format(self._name, item, self._dependson))
                return self.update_item
            else:
                return None
                self.logger.warning(
                    "Parsing Items {}: No items parsed".format(self._name))
            

    def _processing_response(self, socket):
        self._bufferlock.acquire(timeout=2)
        try:
            buffer = ''
            bufferlist = []
            tidy = lambda c: re.sub(
                r'(^\s*[\r\n]+|^\s*\Z)|(\s*\Z|\s*[\r\n]+)',
                lambda m: '\r\n' if m.lastindex == 2 else '',
                c)
            try:
                if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
                    #self.logger.debug("Processing Response {}: Starting to read RS232".format(self._name))
                    if socket == self._serial:
                        buffer = socket.readline().decode('utf-8')
                    else:
                        buffer = socket.read()
                if self._tcp and socket == self._socket:
                    buffer = socket.recv(4096).decode('utf-8')
                    #self.logger.debug("Processing Response {}: Starting to read TCP".format(self._name))
                buffering = False
                buffer = tidy(buffer)
                if not buffer == '' and (not self._response_buffer == False or not self._response_buffer == 0): 
                    buffering = True
                elif buffer == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
                    self._resend_counter +=1
                    self._wait(0.1)
                    sending = self._send(self._sendingcommand, 'responseprocess')
                    while sending is None:
                        self._sendlock.wait(2)
                        self.logger.warning("Waiting for sending")
                    self.logger.debug("Processing Response {}: Received empty response while sending command: {}. Return from send is {}. Retry: {}".format(self._name, self._sendingcommand, sending, self._resend_counter))
                    if self._resend_counter >= 2:
                        self.logger.debug("Processing Response {}: Stop resending command {} and sending back error.".format(self._name, self._sendingcommand))
                        self._resend_counter = 0
                        yield 'ERROR'
                        if self._threadlock_buffer.locked(): self._bufferlock.notify()

            except Exception as err:
                buffering = False
                try:
                    if not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup' and not (self._sendingcommand.split(",")[2] == '' or self._sendingcommand.split(",")[2] == ' ' or self._sendingcommand.split(",")[2] == 'none'):
                        buffering = True
                        self.logger.debug("Processing Response {}: Error reading.. Error: {}. Sending Command: {}. RS232: {}, Host: {}, Socket: {}".format(self._name, err, self._sendingcommand, self._rs232, self._tcp, socket))
                        if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
                            self.logger.warning("Processing Response {}: Problems buffering RS232 response. Error: {}. Increasing timeout temporarily.".format(self._name, err))
                            self._wait(1)
                            socket.timeout = 2
                            sending = self._send(self._sendingcommand, 'getresponse')  
                            while sending is None:
                                self._sendlock.wait(2)
                                self.logger.warning("Waiting for sending")
                            if socket == self._serial:
                                buffer = socket.readline().decode('utf-8')
                            else:
                                buffer = socket.read()
                            socket.timeout = 0.3
                            self.logger.debug("Processing Response {}: Error reading.. Return from send is {}. Error: {}".format(self._name, sending, err)) 
                        if self._tcp and socket == self._socket:
                            self.logger.warning("Processing Response {}: Problems buffering TCP response. Error: {}. Increasing timeout temporarily.".format(self._name, err))
                            self._wait(1)
                            socket.settimeout(4)
                            sending = self._send(self._sendingcommand, 'getresponse') 
                            while sending is None:
                                self._sendlock.wait(2)
                                self.logger.warning("Waiting for sending")
                            self.logger.debug("Processing Response {}: Error reading.. Return from send is {}. Error: {}".format(self._name, sending, err))
                            buffer = socket.recv(4096).decode('utf-8')
                            socket.settimeout(1)
                except Exception as err:
                    buffering = False
                    self.logger.error("Processing Response {}: Connection error. Error: {} Resend Counter: {}. Resend Max: {}".format(
                        self._name, err, self._resend_counter, self._resend_retries))
                    yield 'ERROR'
                    if self._threadlock_buffer.locked(): self._bufferlock.notify()
    
            while buffering:            
                if '\r\n' in buffer:
                    (line, buffer) = buffer.split("\r\n", 1)
                    #self.logger.debug("Processing Response {}: \r\nBuffer: {}Line: {}. Response buffer: {}, force buffer: {}".format(self._name, buffer, line,self._response_buffer, self._force_buffer))
                    if not ('' in self._force_buffer and len(self._force_buffer) == 1) and (self._response_buffer == False or self._response_buffer == 0):
                        if not re.sub('[ ]','', buffer) == '' and not re.sub('[ ]','', line) == '':
                            bufferlist = []
                            for buf in self._force_buffer:                            
                                try:
                                    if buf in buffer and not buf.startswith(tuple(self._ignoreresponse)) and not '' in self._ignoreresponse:
                                        start = buffer.index(buf)
                                        #self.logger.debug("Processing Response {}: Testing forcebuffer {}. Bufferlist: {}. Start: {}".format(self._name, buf,bufferlist, start))
                                        if not buffer.find('\r\n', start) == -1:
                                            end = buffer.index('\r\n', start)
                                            if not buffer[start:end] in bufferlist and not buffer[start:end] in line:
                                                bufferlist.append(buffer[start:end])
                                        else:
                                            if not buffer[start:] in bufferlist and not buffer[start:] in line:
                                                bufferlist.append(buffer[start:])
                                        self.logger.debug("Processing Response {}: Forcebuffer {} FOUND in buffer. Bufferlist: {}. Buffer: {}".format(
                                            self._name, buf, bufferlist, buffer))
                                except Exception as err:
                                    self.logger.warning(
                                        "Processing Response {}: Problems while buffering. Error: {}".format(self._name, err))
                            if bufferlist:
                                buffer = '\r\n'.join(bufferlist)
                                buffer = tidy(buffer)
                            else:
                                self.logger.debug("Processing Response {}: No forced buffer found.".format(self._name))
                                pass
                    # Delete consecutive duplicates
                    buffer = '\r\n'.join([x[0] for x in groupby(buffer.split("\r\n"))])
                    if '{}\r\n'.format(line) == buffer:
                        buffer = ''
                        self.logger.debug(
                            "Processing Response {}: Clearing buffer because it's the same as Line: {}".format(self._name, line))
                    line = re.sub('[\\n\\r]', '', line).strip()
                    if not line.startswith(tuple(self._response_commands)) and not line.startswith(tuple(self._errorresponse)) and not '' in self._errorresponse:
                        #self.logger.debug("Processing Response {}: Response {} is not in possible responses for items. Sending Command: {}".format(self._name, line, self._sendingcommand))
                        pass
                    elif line.startswith(tuple(self._ignoreresponse)) and not '' in self._ignoreresponse:
                        try:
                            compare = self._send_commands[0].split(",")[2].split("|")
                            for comp in compare:
                                if line.startswith(comp):
                                    keyfound = True
                                else:
                                    keyfound = False 
                            if keyfound == True:
                                self._send_commands.pop(0)
                                self._sendingcommand = 'done'
                                self.logger.debug("Processing Response {}: Response {} is same as expected {}. Removing command from send list. It is now: {}. Ignore responses are: {}".format(self._name, line, compare, self._send_commands, self._ignoreresponse))
                                sending = self._send('command', 'commandremoval')
                                while sending is None:
                                    self._sendlock.wait(2)
                                    self.logger.warning("Waiting for sending")
                                #self.logger.debug("Processing Response {}: Return from send is {}.".format(self._name, sending))
                        except Exception as err:
                            #self.logger.debug("Processing Response {}: Response {} is ignored. Command list is now: {}. Error: {}".format(self._name, line, self._send_commands, err))
                            pass
                    elif not line.startswith(tuple(self._ignoreresponse)) and line.startswith(self._specialcommands['Display']['Command']) and not self._response_buffer == False and not '' in self._ignoreresponse and not self._specialcommands['Display']['Command'] == '':
                        #self.logger.debug(
                        #    "Processing Response {}: Detected Display info {}. buffer: \r\n{}".format(self._name, line, buffer))
                        buffering = False
                        buffer += '\r\n{}\r\n'.format(line)
                        buffer = tidy(buffer)
                        #self.logger.debug(
                        #    "Processing Response {}: Append Display info {} to buffer: \r\n{}".format(self._name, line, buffer))                    
                    else:
                        if self._response_buffer == False and not buffer.startswith(tuple(self._force_buffer)) and not '' in self._force_buffer:
                            buffering = False
                            self.logger.debug(
                                "Processing Response {}: Clearing buffer: {}".format(self._name, buffer))
                            buffer = '\r\n'
                        #self.logger.debug("Processing Response {}: Sending back line: {}. Display Command: {}".format(self._name, line, self._specialcommands['Display']['Command']))
                        yield "{}".format(line)
                        if self._threadlock_buffer.locked(): self._bufferlock.notify()
                else:
                    try:
                        if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
                            if socket == self._serial:
                                more = socket.readline().decode('utf-8')
                            else:
                                more = socket.read()
                        if self._tcp and socket == self._tcp:
                            more = socket.recv(4096).decode('utf-8')
                        morelist = more.split("\r\n")
                        if buffer.find('\r\n') == -1 and len(buffer) > 0:
                            buffer += '\r\n'
                        buffer += '\r\n'.join([x[0] for x in groupby(morelist)])
                    except Exception as err:
                        buffering = False 
                    finally:
                        buffering = False 
                        #self.logger.debug("Processing Response {}: Buffering false.".format(self._name))
    
            if not buffer == '\r\n' and self._response_buffer == True or type(self._response_buffer) is int:            
                buffer = tidy(buffer)
                bufferlist = buffer.split('\r\n')
                # Removing everything except last x lines           
                maximum = abs(self._response_buffer) if type(self._response_buffer) is int else 11
                multiplier = 1 if self._response_buffer >= 0 else -1 
                #if len(bufferlist) > 1: self.logger.debug("Bufferlist before: {}. Max: {}, Multiply: {}".format(bufferlist, maximum, multiplier))
                while '' in bufferlist: bufferlist.remove('')
                newbuffer = []
                for buf in bufferlist:
                     if not buf.startswith(tuple(self._ignoreresponse)) and not '' in self._ignoreresponse and buf.startswith(tuple(self._response_commands)):
                        newbuffer.append(buf)
                bufferlist = newbuffer[-1 * max(min(len(newbuffer), maximum), 0):]
                
                if len(bufferlist) > 1: self.logger.debug("Bufferlist after: {}".format(bufferlist))
                buffering = False
                for buf in bufferlist:
                    if not re.sub('[ ]','',buf) == '' and not buf.startswith(tuple(self._ignoreresponse)) and not '' in self._ignoreresponse:
                        self.logger.debug(
                        "Processing Response {}: Sending back {} from buffer because Responsebuffer is activated.".format(self._name, buf))
                        if self._threadlock_buffer.locked(): self._bufferlock.notify()
                        self._wait(0.2)
                        yield buf   
                        
            elif not buffer == '\r\n': # and self._force_buffer:
                buffer = tidy(buffer)
                bufferlist = buffer.split('\r\n')
                # Removing everything except last 3 lines
                maximum = abs(self._response_buffer) if type(self._response_buffer) is int else 11
                multiplier = 1 if self._response_buffer >= 0 else -1 
                bufferlist = bufferlist[multiplier * max(min(len(bufferlist), maximum), 0):]
                buffering = False
                for buf in bufferlist:
                    if not re.sub('[ ]','',buf) == '' and not buf.startswith(tuple(self._ignoreresponse)) and not '' in self._ignoreresponse:
                        self.logger.debug(
                        "Processing Response {}: Sending back {} from filtered buffer: {}.".format(self._name, buf, buffer))                        
                        if self._threadlock_buffer.locked(): self._bufferlock.notify()
                        self._wait(0.2)
                        yield buf
        except Exception as err:
            self.logger.error(
                "Processing Response {}: Problems occured. Message: {}".format(self._name, err))
        finally:
            if self._threadlock_buffer.locked(): self._bufferlock.release()


    def run(self):
        if self._tcp is None and self._rs232 is None:
            self.logger.error("Initializing {}: Neither IP address nor RS232 port given. Not running.".format(self._name))
        else:
            if not self._lock.acquire(timeout=2):
                return
            try:
                try:
                    self._dependson = self._sh.return_item(self._dependson)
                    self.logger.debug("Initializing {}: Dependson Item: {}.".format(self._name, self._dependson))
                except:
                    self._dependson = None
                    self.logger.warning("Initializing {}: Dependson Item {} is no valid item.".format(self._name, self._dependson))
                self.logger.debug("Initializing {}: Running. Lock is {}".format(
                    self._name, self._threadlock_standard.locked()))
                self.alive = True
                self.logger.debug("Initializing {}: Items: {}".format(self._name, self._items))
                self.logger.debug("Initializing {}: Speaker Items: {}".format(self._name, self._items_speakers))
            except Exception as err:
                self.logger.error(
                    "Initializing {}: Problem running and creating items. Error: {}".format(self._name, err))
            finally:
                if self._threadlock_standard.locked(): self._lock.release()
                self.logger.debug("Initializing {}: Running. Lock is released. Now it is {}".format(
                    self._name, self._threadlock_standard.locked()))
                if not self._tcp is None or not self._rs232 is None:
                    self._read_commandfile()
                

    def connect(self):
        self._trigger_reconnect = True
        self.logger.debug("Connecting {}: Starting to connect. Current Connections: {}".format(self._name, self._is_connected))
        if not self._lock.acquire(timeout=2):
            return
        try:
            dependsvalue = self._dependson()
            
            if dependsvalue == self._dependson_value: depending = False
            else: 
                depending = True
                self._is_connected = []
            self.logger.debug("Connecting {}: Connection depends on {}. It's value is {}, has to be {}. Connections are {}".format(self._name, self._dependson, dependsvalue, self._dependson_value, self._is_connected))
        except Exception as e:
            depending = False
            self.logger.debug("Connecting {}: Depending is false. Message: {}".format(self._name, e))
        finally:
            if self._threadlock_standard.locked(): self._lock.release()    
            if depending == False:
                if self._tcp is not None and 'TCP' not in self._is_connected: 
                    self._sh.scheduler.change('avdevice-tcp-reconnect', active=True)
                    self._sh.scheduler.trigger('avdevice-tcp-reconnect')
                    self._trigger_reconnect = False
                if self._rs232 is not None and 'Serial' not in self._is_connected: 
                    self._sh.scheduler.change('avdevice-serial-reconnect', active=True)
                    self._sh.scheduler.trigger('avdevice-serial-reconnect')
                    self._trigger_reconnect = False

    def connect_tcp(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            if self._tcp is not None and 'TCP' not in self._is_connected: 
                self.logger.debug("Connecting TCP {}: Starting to connect to {}.".format(self._name, self._tcp))
                self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._socket.setblocking(0)
                self._socket.settimeout(6)
                self._socket.connect(('{}'.format(self._tcp), int(self._port)))
                self._socket.settimeout(1)
                self._is_connected.append('TCP')
                self.logger.info("Connecting TCP {}: Connected to {}:{}".format(
                    self._name, self._tcp, self._port))
                    
        except Exception as err:
            if 'TCP' in self._is_connected:
                self._is_connected.remove('TCP')
            self.logger.warning("Connecting TCP {}: Could not connect to {}:{}. Error:{}. Counter: {}/{}".format(
                self._name, self._tcp, self._port, err, self._reconnect_counter, self._reconnect_retries))
                    
        finally:
            if self._threadlock_standard.locked(): self._lock.release()
            if ('TCP' not in self._is_connected and self._tcp is not None) and str(self._auto_reconnect.lower()) in ['1', 'yes', 'true', 'on']:
                #self._sh.scheduler.change('avdevice-tcp-reconnect', active=True)
                self.connect()
                self._trigger_reconnect = False
                self.logger.warning("Connecting TCP {}: Reconnecting. Command list while connecting: {}.".format(
                    self._name, self._send_commands))
            elif ('TCP' in self._is_connected and self._tcp is not None) or self._reconnect_counter >= self._reconnect_retries:
                self._sh.scheduler.change('avdevice-tcp-reconnect', active=False)
                self._reconnect_counter = 0
                self._trigger_reconnect = True
                keeptemp = []
                for zeit in self._keep_commands:
                    keeping = False
                    if time.time() - zeit <= self._secondstokeep and self._keep_commands[zeit] not in keeptemp:
                        keeptemp.append(self._keep_commands[zeit])
                        keeping = True
                    self.logger.info("Connecting TCP {}: Age {}s of command {}. Secondstokeep: {}. Keeping command: {}".format(
                        self._name, int(time.time()-zeit), self._keep_commands[zeit], self._secondstokeep, keeping))
                self._send_commands = list(set(keeptemp)) + self._send_commands
                seen = set()
                self._send_commands = [x for x in self._send_commands if x not in seen and not seen.add(x)]
                self.keep_commands = {}
                keeptemp = [] 
                self.logger.debug("Connecting TCP {}: Deactivating reconnect scheduler. Command list while connecting: {}. Keep Commands: {}".format(
                    self._name, self._send_commands, self.keep_commands))
            self._reconnect_counter += 1
            if 'TCP' in self._is_connected:
                self._wait(1)                
                self._items['zone0']['statusupdate']['Item'][0](1, 'Init', self._tcp)
                self.logger.debug("Connecting TCP {}: Updated Item after connection: {} with value 1. Commandlist: {}".format(
                    self._name, self._items['zone0']['statusupdate']['Item'][0], self._send_commands))
                self.parse_input()


    def connect_serial(self):
        if not self._lock.acquire(timeout=2):
            return                
        try:
            if self._rs232 is not None and 'Serial' not in self._is_connected:        
                self.logger.debug("Connecting Serial {}: Starting to connect to {}.".format(self._name, self._rs232))
                ser = serial.serial_for_url('{}'.format(self._rs232), baudrate=int(self._baud), timeout=float(self._timeout), write_timeout=float(self._writetimeout))
                i = 0
                while ser.in_waiting == 0:
                    i += 1
                    self._wait(1)
                    ser.write(bytes('?P\r', 'utf-8'))
                    buffer = bytes()
                    buffer = ser.read().decode('utf-8') 
                    self.logger.warning("Connecting Serial {}: Reconnecting Retry: {}".format(self._name, i))
                    if i >= self._reconnect_retries or (i >= 4 and self._trigger_reconnect == False): 
                        ser.close()
                        break
                if ser.isOpen():
                    self._serialwrapper = io.TextIOWrapper(io.BufferedRWPair(ser, ser), newline='\r\n', encoding='utf-8', line_buffering=True, write_through=True)
                    self._serialwrapper.timeout = 0.1
                    self._serial = ser
                    self._trigger_reconnect = False
                    self._is_connected.append('Serial')
                    self.logger.info("Connecting Serial {}: Connected to {} with baudrate {}.".format(
                        self._name, ser, self._baud))
                else:
                    self.logger.warning("Connecting Serial {}: Serial port is not open. Connection status: {}. Reconnect Counter: {}".format(self._name, self._is_connected, self._reconnect_counter))
        except Exception as err:
            if 'Serial' in self._is_connected:
                self._is_connected.remove('Serial')
            self.logger.warning("Connecting Serial {}: Could not connect to {}, baudrate {}. Error:{}".format(
                self._name, self._rs232, self._baud, err))
                    
        finally:
            if self._threadlock_standard.locked(): self._lock.release()
            if ('Serial' not in self._is_connected and self._rs232 is not None) and str(self._auto_reconnect.lower()) in ['1', 'yes', 'true', 'on']:
                #self._sh.scheduler.change('avdevice-serial-reconnect', active=True)
                self.connect()
                self._trigger_reconnect = False
                self.logger.debug("Connecting Serial {}: Activating reconnect scheduler. Command list while connecting: {}.".format(
                    self._name, self._send_commands))
            elif ('Serial' in self._is_connected and self._rs232 is not None) or self._reconnect_counter >= self._reconnect_retries:
                self._sh.scheduler.change('avdevice-serial-reconnect', active=False)
                self._reconnect_counter = 0
                self._trigger_reconnect = True  
                keeptemp = []                       
                for zeit in self._keep_commands:
                    keeping = False
                    if time.time() - zeit <= self._secondstokeep and self._keep_commands[zeit] not in keeptemp:
                        keeptemp.append(self._keep_commands[zeit])
                        keeping = True                        
                    self.logger.info("Connecting Serial {}: Age {}s of command {}. Secondstokeep: {}. Keeping command: {}".format(
                        self._name, int(time.time()-zeit), self._keep_commands[zeit], self._secondstokeep, keeping))
                self._send_commands = list(set(keeptemp)) + self._send_commands
                seen = set()
                self._send_commands = [x for x in self._send_commands if x not in seen and not seen.add(x)]
                self.keep_commands = {}
                keeptemp = [] 
                self.logger.debug("Connecting Serial {}: Deactivating reconnect scheduler. Command list while connecting: {}. Keep commands: {}".format(
                    self._name, self._send_commands, self.keep_commands))
            #self.logger.debug("Connecting {}: Tried to connect. Lock is released. Now it is {}. Reconnect Retries: {}".format(self._name, self._threadlock_standard.locked(), self._reconnect_counter))
            self._reconnect_counter += 1
            if 'Serial' in self._is_connected:
                self._wait(1)                
                self._items['zone0']['statusupdate']['Item'][0](1, 'Init', self._rs232)
                self.logger.debug("Connecting Serial {}: Updated Item after connection: {} with value 1. Sendcommands: {}".format(
                    self._name, self._items['zone0']['statusupdate']['Item'][0], self._send_commands))
                self.parse_input()


    def parse_input(self):        
        while self.alive and not self._is_connected == []:
            if not self._parselock.acquire(timeout=2):
                return
            #self.logger.debug("Parsing Input {}: Starting to parse input. Lock is: {}. Alive: {}. Connected: {}. Sendcommand:{}".format(
            #    self._name, self._threadlock_standard.locked(), self.alive, self._is_connected, self._sendingcommand))
            to_send = 'command'
            try:
                data = 'waiting'
                databuffer = []
                if 'Serial' in self._is_connected:
                    try:
                        databuffer = self._processing_response(self._serialwrapper)
                        while databuffer is None:
                            self._bufferlock.wait(2)
                            self.logger.warning("Waiting for databuffer")
                    except Exception as err:
                        self.logger.error(
                            "Parsing Input {}: Problem receiving Serial data {}.".format(self._name, err))               
                elif 'TCP' in self._is_connected:
                    try:
                        databuffer = self._processing_response(self._socket)
                        while databuffer is None:
                            self._bufferlock.wait(2)
                            self.logger.warning("Waiting for databuffer")
                    except Exception as err:
                        self.logger.error(
                            "Parsing Input {}: Problem receiving TCP data {}.".format(self._name, err))
                #self.logger.warning('DATABUFFER: {}. Data: {}'.format(databuffer, data))
                for data in databuffer:                    
                    data = data.strip()
                    if data == '' and not self._sendingcommand == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
                        self.logger.warning('Problem')
                    if data == 'ERROR' and not self._sendingcommand == 'gaveup' and not self._sendingcommand == 'done':
                        if self._resend_counter >= self._resend_retries:
                            self.logger.warning("Parsing Input {}: Giving up Sending {} and removing from list. Received Data: {}. Original Commandlist: {}".format(
                                self._name, self._sendingcommand, data, self._send_commands))
                            self._resend_counter = 0
                            self._requery_counter = 0                            
                            # Resetting Item if Send not successful
                            if self._reset_onerror == True:
                                resetting = self._resetitem()
                                while resetting is None:
                                    self._resetlock.wait(2)
                                    self.logger.warning("Waiting for resetting")
                                self.logger.warning("Parsing Input {}: Connection Error: {}. Resetting Item: {}.".format(
                                    self._name, data, resetting))
                            try:
                                if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._specialcommands['Display']['Command']:
                                    self._keep_commands[time.time()] = self._send_commands[0]
                                    self.logger.debug("Parsing Input {}: Removing item from send command, storing in keep commands: {}.".format(self._name, self._keep_commands))
                                self._send_commands.pop(0)                         
                                if not self._send_commands == []:
                                    sending = self._send('command', 'parseinput')
                                    while sending is None:
                                        self._sendlock.wait(2)
                                        self.logger.warning("Waiting for sending")
                                    self.logger.debug("Parsing Input {}: Command List is now: {}. Sending return is {}.".format(
                                    self._name, self._send_commands, sending))
                            except Exception as err:
                                self.logger.debug(
                                    "Parsing Input {}: Nothing to remove from Send Command List. Error: {}".format(self._name, err))
                            self._sendingcommand = 'gaveup'
                            if self._trigger_reconnect == True:
                                self.connect()
                                self.logger.debug("Parsing Input {}: Trying to connect while parsing item".format(self._name))
                        else:
                            self._resend_counter += 1

                    sorted_response_commands = sorted(self._response_commands, key=len, reverse=True)
                    self.logger.debug("Parsing Input {}: Response: {}.".format(self._name, data))
                    if not self._send_commands == []:
                        expectedresponse = []
                        self.logger.debug("Parsing Input {}: Parsing input while waiting for response. Lock is: {}".format(self._name, self._threadlock_parse.locked()))
                        try:
                            for response in self._send_commands:
                                if not response.split(",")[2] == '': expectedresponse.append(response.split(",")[2])                                
                            self.logger.debug("Parsing Input {}: Expected response while parsing: {}.".format(self._name, expectedresponse))
                        except Exception as err:
                            self.logger.error("Parsing Input {}: Problems creating expected response list. Error: {}".format(self._name, err))
                        try:
                            to_send = 'command'
                            updatedcommands = []
                            for expected in expectedresponse:
                                expectedlist = expected.split("|")
                                
                                if self._manufacturer == 'epson' and (data == ':PWR=02' or data == 'PWR=02'):
                                    data = 'PWR=01'                                
                                data = re.sub('ON$', '1', data)
                                data = re.sub('OFF$', '0', data)
                                
                                if data.startswith(tuple(expectedlist)):
                                    entry, value = self._write_itemsdict(data)
                                    self.logger.debug("Parsing Input {}: got entry {}. Value: {}".format(
                                        self._name, entry, value))
                                    while value is None or entry is None:
                                        self.logger.debug("Parsing Input {}: waiting for dict writing.".format(self._name))
                                        self._dictlock.wait(2)                                        
                                    self.logger.debug("Parsing Input {}: FOUND {}. Written to dict: {}".format(
                                        self._name, expectedlist, entry))
                                    self._sendingcommand = 'done'
                                    self._requery_counter = 0
                                    self._resend_counter = 0
                                elif expectedlist[0] == '' or expectedlist[0] == ' ' or expectedlist[0] == 'none':
                                    self._sendingcommand = 'done'
                                    self._requery_counter = 0
                                    self._resend_counter = 0 
                                    self.logger.debug(
                                        "Parsing Input {}: No response expected".format(self._name))
                                elif expectedlist[0].lower() == 'string':
                                    value = data
                                    self.logger.debug(
                                        "Parsing Input {}: String found and testing... ".format(self._name))
                                    if value.startswith(tuple(self._response_commands.keys())):
                                        self.logger.debug(
                                            "Parsing Input {}: Found string but ignored because it is a legit response for another command.".format(self._name))                                       
                                    else:
                                        entry, value = self._write_itemsdict(data)
                                        self.logger.debug(
                                            "Parsing Input {}: String FOUND. Written to dict: {}.".format(self._name, entry))
                                        self._sendingcommand = 'done'
                                        self._requery_counter = 0
                                        self._resend_counter = 0                                
                                else:
                                    expectedindex = expectedresponse.index(expected)
                                    updatedcommands.append(self._send_commands[expectedindex])

                            self._send_commands = updatedcommands
                            #self.logger.debug("Parsing Input {}: Sendcommands: {}. Sendingcommand: {}".format(self._name, self._send_commands, self._sendingcommand))
                            
                            if not self._send_commands == [] and not self._sendingcommand == 'done':
                                self._requery_counter += 1
                                try:
                                    dependsvalue = self._dependson()
                                    self.logger.debug("Parsing Input {}: Parsing depends on {}. It's value is {}, has to be {}.".format(self._name, self._dependson, dependsvalue, self._dependson_value))
                                    if dependsvalue == self._dependson_value: 
                                        depending = False
                                    else: 
                                        depending = True
                                        self._resetondisconnect('parseinput')                                         
                                except Exception as err:
                                    depending = False
                                    self.logger.debug("Parsing Input {}: Depending is false. Message {}.".format(self._name, err))
                                    
                                if self._requery_counter >= self._resend_retries:
                                    self._requery_counter = 0
                                    self._resend_counter = 0
                                    if not self._send_commands[0] in self._query_commands and not self._send_commands == []:
                                        self._sendingcommand = self._send_commands[0]
                                        self.logger.warning("Parsing Input {}: Going to reset item {}.".format(self._name, self._sendingcommand))
                                        resetting = self._resetitem()
                                        while resetting is None:
                                            self.logger.warning("Parsing Input {}: Waiting for resetting".format(self._name))
                                            self._resetlock.wait(2)
                                        self.logger.debug("Parsing Input {}: Giving up Re-Query: {}. Resetting Item: {}".format(
                                            self._name, self._sendingcommand, resetting))
                                    self._sendingcommand = 'gaveup'
                                    if data == 'ERROR':                                           
                                        if 'Serial' in self._is_connected:
                                            self._is_connected.remove('Serial')
                                            self._trigger_reconnect = True
                                        if 'TCP' in self._is_connected:
                                            self._is_connected.remove('TCP')
                                            self._trigger_reconnect = True
                                        if self._trigger_reconnect == True:
                                            self.connect()
                                            self.logger.debug("Parsing Input {}: Trying to connect while parsing item".format(self._name))
                                    if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._specialcommands['Display']['Command']:
                                        self._keep_commands[time.time()] = self._send_commands[0]
                                        self.logger.debug("Parsing Input {}: Removing item from send command, storing in keep commands: {}.".format(self._name, self._keep_commands))
                                    self._send_commands.pop(0)
                                    #self.logger.debug("Parsing Input {}: Send commands are now: {}".format(self._name, self._send_commands))
                                elif depending == True:
                                    self._requery_counter = 0
                                    self._resend_counter = 0
                                    if not self._send_commands[0] in self._query_commands and not self._send_commands == []:
                                        self._sendingcommand = self._send_commands[0]
                                        self.logger.warning("Parsing Input {}: Reset item {} because dependency not fulfilled.".format(self._name, self._sendingcommand))
                                        resetting = self._resetitem()
                                        while resetting is None:
                                            self.logger.warning("Parsing Input {}: Waiting for resetting".format(self._name))
                                            self._resetlock.wait(2)
                                        self.logger.debug("Parsing Input {}: Giving up Re-Query: {}. Resetting Item: {}".format(
                                            self._name, self._sendingcommand, resetting))
                                    self._sendingcommand = 'gaveup'
                                    if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._specialcommands['Display']['Command']:
                                        self._keep_commands[time.time()] = self._send_commands[0]
                                        self.logger.debug("Parsing Input {}: Removing item from send command, storing in keep commands: {}.".format(self._name, self._keep_commands))
                                    self._send_commands.pop(0)
                                    self.logger.debug("Parsing Input {}: Keepcommands: {}. Sendcommands: {}".format(
                                        self._name, self._keep_commands, self._send_commands))
                                elif not self._sendingcommand == 'gaveup':
                                    # self._send(self._send_commands[0].split(",")[1])
                                    # self._send('query','parseinput')
                                    to_send = 'query' if self._requery_counter % 2 == 1 else 'command'
                                    self._wait(self._resend_wait)
                                    self.logger.debug("Parsing Input {}: Requesting {} from {} because response was {}. Requery Counter: {}".format(self._name, to_send, self._send_commands[0], data, self._requery_counter))
                        except Exception as err:
                            self.logger.warning("Parsing Input {}: Problems with checking for expected response. Error: {}".format(self._name, err))

                    #self.logger.debug("Parsing Input {}: Starting comparing values".format(self._name))
                    for key in sorted_response_commands:
                        commandlength = self._response_commands[key][1]
                        valuelength = self._response_commands[key][0]
                        item = self._response_commands[key][3]
                        title = ''
                        station = ''
                        index = data.find(key)
                        if not index == -1:
                            inputcommands = self._specialcommands['Input']['Command']
                            function = self._response_commands[key][4]
                            zone = self._response_commands[key][5]
                            if data.startswith(self._specialcommands['Display']['Command']) and not self._specialcommands['Display']['Command'] == '':
                                self.logger.debug(
                                    "Parsing Input {}: Displaycommand found in response {}.".format(self._name, data))
                                try:
                                    content = data[2:][:28]
                                    self.logger.debug("AVDevice {}: Display Data {}. Item: {}".format(
                                        self._name, content, item))
                                    tempvalue = "".join(
                                        list(map(lambda i: chr(int(content[2 * i:][: 2], 0x10)), range(14)))).strip()
                                    receivedvalue = re.sub(r'^[^A-Z0-9]*', '', tempvalue)
                                    self.logger.debug("AVDevice {}: Display Output {}".format(
                                        self._name, receivedvalue))
                                except Exception as err:
                                    self.logger.warning("AVDevice {}: Problems getting display info. Error: {}".format(self._name, err))

                            elif data.startswith(tuple(self._specialcommands['Nowplaying']['Command'])) and not self._specialcommands['Nowplaying']['Command'] == '':
                                self.logger.debug("AVDevice {}: Now playing info found in response {}.".format(self._name, data))
                                try:
                                    m = re.search('"(.+?)"', data)
                                    if m:
                                        receivedvalue = m.group(1)
                                    else:
                                        receivedvalue = ''
                                except Exception as err:
                                    self.logger.debug("AVDevice {}: Problems reading Now Playing info. Error:{}".format(self._name, err))
                            elif data.startswith(tuple(self._specialcommands['Speakers']['Command'])) and not self._specialcommands['Speakers']['Command'] == '':
                                self.logger.debug("AVDevice {}: Speakers info found in response {}. Command: {}".format(self._name, data, self._specialcommands['Speakers']['Command']))
                                receivedvalue = data[index + commandlength:index + commandlength + valuelength]                                
                                try:
                                    for speakercommand in self._specialcommands['Speakers']['Command']:
                                        for zone in self._items_speakers:
                                            for speakerlist in self._items_speakers[zone]: 
                                                speakerAB = sum(map(int, self._items_speakers[zone].keys()))
                                                self.logger.debug("AVDevice {}: Received value: {}. Speaker {}. SpeakerAB: {}".format(
                                                    self._name, receivedvalue, speakerlist, speakerAB))
                                                if receivedvalue == '{}'.format(speakerlist) or receivedvalue == '{}'.format(speakerAB):                                                
                                                    for speaker in self._items_speakers[zone][speakerlist]['Item']:
                                                        self.logger.info("AVDevice {}: Speaker {} is on.".format(self._name, speaker))
                                                        speaker(1, 'AVDevice', self._tcp)
                                                else:                                                
                                                    for speaker in self._items_speakers[zone][speakerlist]['Item']:
                                                        self.logger.info("AVDevice {}: Speaker {} is off.".format(self._name, speaker))
                                                        speaker(0, 'AVDevice', self._tcp)
                                               
                                except Exception as err:
                                    self.logger.warning("AVDevice {}: Problems reading Speakers info. Error:{}".format(self._name, err))
                            else:
                                if self._manufacturer == 'pioneer':
                                    receivedvalue = data[index + commandlength:index + commandlength + valuelength]
                                else:
                                    receivedvalue = data[index + commandlength:]
                                self.logger.debug("Parsing Input {}: Neither Display nor Now Playing in response. receivedvalue: {}.".format(self._name, receivedvalue))
                                if not receivedvalue.isdigit() and self._response_commands[key][7] == 'num':
                                    self.logger.warning("Parsing Input {}: Receivedvalue {} is not num as defined in the txt-file.".format(self._name, receivedvalue))   
                                    
                            
                            if data.startswith(tuple(inputcommands)) and receivedvalue in self._ignoredisplay and not '' in self. _ignoredisplay:
                                for i in range(0,len(inputcommands)):
                                    if data.startswith(inputcommands[i]):
                                        self._specialcommands['Input']['Ignore'][i] = 1
                                if not self._specialcommands['Display']['Command'] in self._ignoreresponse and not self._specialcommands['Display']['Command'] == '' and not '' in self._ignoreresponse:
                                    self._ignoreresponse.append(self._specialcommands['Display']['Command'])                                        
                                self.logger.error("Parsing Input {}: Data {} has value in ignoredisplay {}. Ignorecommands are now: {}. Display Ignore is {}. Input Ignore is {}".format(self._name, data, self._ignoredisplay, self._ignoreresponse, self._specialcommands['Display']['Ignore'], self._specialcommands['Input']['Ignore']))
                            elif data.startswith(tuple(inputcommands)) and not receivedvalue in self._ignoredisplay and not '' in self. _ignoredisplay:
                                for i in range(0,len(inputcommands)):
                                    if data.startswith(inputcommands[i]):
                                        self._specialcommands['Input']['Ignore'][i] = 0
                                #self.logger.debug("Parsing Input {}: Data {} has NO value in ignoredisplay {}. Ignorecommands are now: {}. Display Ignore is {}. Input Ignore is {}".format(self._name, data, self._ignoredisplay, self._ignoreresponse, self._specialcommands['Display']['Ignore'], self._specialcommands['Input']['Ignore']))
                                if self._specialcommands['Display']['Ignore'] == 0 and not 1 in self._specialcommands['Input']['Ignore']:
                                    while self._specialcommands['Display']['Command'] in self._ignoreresponse:
                                        self._ignoreresponse.remove(self._specialcommands['Display']['Command'])
                                    #self.logger.warning("Parsing Input {}: Removing {} from ignore.".format(self._name, self._specialcommands['Display']['Command']))
                            value = receivedvalue
                            if self._response_commands[key][6].lower() in ['1', 'true', 'yes', 'on']:
                                value = False if int(receivedvalue) > 0 else True
                                self.logger.debug("Parsing Input {}: Inverting value for item {}. Original Value: {}, New Value: {}".format(
                                    self._name, item, receivedvalue, value))
                                                                                               
                            self.logger.debug("Parsing Input {}: Found key {} in response at position {} with value {}.".format(
                                self._name, key, index, value))
                            # for weird situations where the device sends back a higher value than 1 even it is bool.
                            if self._response_commands[key][7] == 'bool':
                                if self._manufacturer.lower() == 'epson':
                                    try:
                                        value = max(min(int(value), 1), 0) 
                                        self.logger.debug("Parsing Input {}: Limiting bool value for {} with received value {} to {}.".format(
                                            self._name, self._items[zone][function], receivedvalue, value))  
                                    except:
                                        pass  
                                if receivedvalue.lower() == 'on' or receivedvalue == 1:
                                    value = True
                                if receivedvalue.lower() == 'off' or receivedvalue == 0:
                                    value = False  
                                                                                           
                            
                            if function in self._items[zone].keys():                                
                                if self._response_commands[key][7] == 'bool' and (value == True or value == False):
                                    self._items[zone][function]['Value'] = value
                                if self._response_commands[key][7] == 'num' and value.isdigit():
                                    self._items[zone][function]['Value'] = value
                                if self._response_commands[key][7] == 'string' and isinstance(value, str):
                                    self._items[zone][function]['Value'] = value

                            for singleitem in item:
                                if self._response_commands[key][7] == 'bool' and (value == True or value == False):
                                    singleitem(value, 'AVDevice', self._tcp)
                                    self.logger.debug("Parsing Input {}: Updating Item {} with Boolean Value: {}.".format(
                                        self._name, item, value))
                                    self._wait(0.15)
                                elif self._response_commands[key][7] == 'num' and value.isdigit():
                                    singleitem(value, 'AVDevice', self._tcp)
                                    self.logger.debug("Parsing Input {}: Updating Item {} with number Value: {}.".format(
                                        self._name, item, value))
                                    self._wait(0.15)
                                elif self._response_commands[key][7] == 'string' and isinstance(value, str):
                                    singleitem(value, 'AVDevice', self._tcp)
                                    self.logger.debug("Parsing Input {}: Updating Item {} with string Value: {}.".format(
                                        self._name, item, value))
                                    self._wait(0.15)
                                
                            break
                        elif key.lower() == 'string':
                            value = data
                            if value.startswith(tuple(sorted_response_commands)):
                                self.logger.debug("Parsing Input {}: Found string for Item {} with Value {} but ignored because it is a legit response for another command.".format(
                                    self._name, item, value))
                                pass                                
                            else:
                                for singleitem in item:
                                    singleitem(value, 'AVDevice', self._tcp)
                                    self._wait(0.15)
                                    self.logger.debug("Parsing Input {}: Updating item {} with value {}".format(
                                        self._name, singleitem, value))
                                break
                    #self.logger.debug("Parsing Input {}: Finished comparing values".format(self._name))
            except Exception as err:
                self.logger.error(
                    "Parsing Input {}: Problems parsing input. Error: {}".format(self._name, err))
            finally:
                if self._threadlock_parse.locked(): self._parselock.release()
                if not self._send_commands == [] and data == 'waiting':  
                    pass
                    #self.logger.warning('Vermutlich ein Verbindungsproblem!')  
                if not self._send_commands == [] and not data == 'waiting':                    
                    reorderlist = []
                    index = 0                    
                    for command in self._send_commands:
                        if command in self._query_commands:
                            reorderlist.append(command)
                        elif command in self._power_commands:
                            self.logger.debug("Parsing Input {}: Ordering power command {} to first position.".format(
                                    self._name, command))                        
                            reorderlist.insert(0,command)
                            index +=1
                        else:                            
                            reorderlist.insert(index,command)
                            index +=1
                    self._send_commands = reorderlist
                    
                    self.logger.debug('Parsing Input {}: Newly sorted send commands at end of parsing: {}'.format(self._name, self._send_commands))
                    if self._is_connected == []:
                        for command in self._send_commands:
                            self.logger.warning("Parsing Input {}: Going to reset {}.".format(self._name, command))
                            if command not in self._query_commands and not command in self._specialcommands['Display']['Command']:
                                self._keep_commands[time.time()] = self._sendingcommand = command
                                self.logger.debug("Parsing Input {}: Removing item {} from send command because not connected, storing in keep commands: {}.".format(
                                    self._name, command, self._keep_commands))
                            resetting = self._resetitem()
                            while resetting is None:
                                self._resetlock.wait(2)
                                self.logger.warning("Waiting for resetting")                            
                            self._send_commands.pop(0)
                    else:
                        sending = self._send('{}'.format(to_send),'parseinput_final')
                        while sending is None:
                            self._sendlock.wait(2)
                            self.logger.warning("Waiting for sending")
                        self.logger.debug("Parsing Input {}: Sending again because list is not empty yet. Sending return is {}. Lock is released. Now it is {}.".format(
                            self._name, sending, self._threadlock_parse.locked()))
                                       
    def update_item(self, item, caller=None, source=None, dest=None):        
        if self.alive:
            if caller != 'AVDevice':
                if not self._updatelock.acquire(timeout=2):
                    return
                try:                   
                    emptycommand = False
                    self.logger.debug("Updating Item for avdevice_{}: Starting to update item {}. Lock is: {}. Reconnectrigger is {}".format(
                        self._name.lower(), item.id(), self._threadlock_update.locked(), self._trigger_reconnect))
                    # connect if necessary
                    if self._trigger_reconnect == True:
                            self.logger.debug("Updating Item for avdevice_{}: Trying to connect while updating item".format(self._name.lower()))
                            self.connect()
                            
                    if 'a' == 'a':
                        self.logger.debug("Updating Item for avdevice_{}: {} trying to update {}".format(
                            self._name.lower(), caller, item.id()))
                        # looping through all zones and testing for keyword avdevice_zone[n]
                        if item == self._dependson:
                            try:
                                dependsvalue = self._dependson()
                                if dependsvalue == self._dependson_value: depending = False
                                else: depending = True
                            except Exception as e:
                                depending = False
                            if depending == False:
                                self._items['zone0']['statusupdate']['Item'][0](1, 'Depending', self._rs232)
                                self.logger.debug("Updating Item for avdevice_{}: Depend value is same as set up, statusupdate starting {}.".format(self._name.lower(), self._items['zone0']['statusupdate']['Item'][0]))
                            elif depending == True:    
                                self.logger.debug("Updating Item for avdevice_{}: Depend value is false.".format(self._name.lower()))
                                self._resetondisconnect('updateitem') 
                        for zone in range(0, self._number_of_zones+1):
                            if self.has_iattr(item.conf, 'avdevice'):
                                command = self.get_iattr_value(item.conf, 'avdevice')
                                zoneX = True                            
                            elif self.has_iattr(item.conf, 'avdevice_zone{}_speakers'.format(zone)):
                                command = 'speakers'
                                zoneX = True
                                self.logger.debug("Updating Item for avdevice_{}: Command is {}. Zone is {}".format(self._name.lower(), command, zone))
                            else:
                                zoneX = False
                            if self.has_iattr(item.conf, 'avdevice_zone{}'.format(zone)) or zoneX == True:
                                if zoneX == False:
                                    command = self.get_iattr_value(item.conf, 'avdevice_zone{}'.format(zone))
                                command_on = '{} on'.format(command)
                                command_off = '{} off'.format(command)
                                command_set = '{} set'.format(command)
                                value = item()
                                updating = True
                                sending = True

                                try:
                                    if command is None:
                                        command = '{} on'.format(command)
                                    if command is None or command == 'None on':
                                        command = '{} off'.format(command)
                                    if command is None or command == 'None off':
                                        command = '{} set'.format(command)
                                    if self._functions['zone{}'.format(zone)][command][2] == '':
                                        emptycommand = True
                                        self.logger.debug("Updating Item for avdevice_{}: Function is empty. Sending nothing. Command: {} value: {}".format(
                                            self._name.lower(), command, item()))
                                        if command == 'statusupdate':
                                            if (item() == True or caller == 'Init') and not self._specialcommands['Display']['Ignore'] >= 5:
                                                if not self._is_connected == []:
                                                    keeptemp = []
                                                    for zeit in self._keep_commands:
                                                        keeping = False
                                                        if time.time() - zeit <= self._secondstokeep and not self._keep_commands[zeit] in keeptemp:
                                                            keeptemp.append(self._keep_commands[zeit])
                                                            keeping = True
                                                        self.logger.debug("Updating Item for avdevice_{}: Age {}s of command {}. Secondstokeep: {}. Keeping command: {}".format(
                                                            self._name.lower(), int(time.time()-zeit), self._keep_commands[zeit], self._secondstokeep, keeping))
                                                    self._send_commands = list(set(keeptemp)) + self._send_commands
                                                    seen = set()
                                                    self._send_commands = [x for x in self._send_commands if x not in seen and not seen.add(x)]
                                                    self._keep_commands = {}
                                                    keeptemp = [] 
                                                for query in self._query_commands:
                                                    if not query in self._send_commands:
                                                        self._send_commands.append(query)
                                                self._reconnect_counter = 0
                                                self._requery_counter = 0
                                                self._trigger_reconnect = True
                                                self.logger.debug("Updating Item for avdevice_{}: Updating status. Querycommands: {}. Reconnecttrigger: {}. Display Ignore: {}".format(self._name.lower(), self._send_commands, self._trigger_reconnect, self._specialcommands['Display']['Ignore']))
                                            elif item() == False and not self._specialcommands['Display']['Ignore'] >= 5:
                                                try:
                                                    dependsvalue = self._dependson()
                                                    self.logger.debug("Updating Item for avdevice_{}: Connection depends on {}. It's value is {}, has to be {}. Connections are {}".format(self._name.lower(), self._dependson, dependsvalue, self._dependson_value, self._is_connected))
                                                    if dependsvalue == self._dependson_value: depending = False
                                                    else: depending = True
                                                except Exception as e:
                                                    depending = False
                                                    self.logger.debug("Updating Item for avdevice_{}: Depending is false. Message: {}".format(self._name.lower(), e))
                                                if depending == True or self._is_connected == []:                                                
                                                    self._resetondisconnect('statusupdate')
                                            elif self._specialcommands['Display']['Ignore'] >= 5:                                                
                                                sending = False
                                                
                                        updating = False
                                        
                                    elif self._functions['zone{}'.format(zone)][command][5].lower() == 'r':
                                        self.logger.warning("Updating Item for avdevice_{}: Function is read only. Not updating. Command: {}".format(
                                            self._name.lower(), command))
                                        updating = False
                                        # Re-query Item to update value
                                        commandinfo = self._functions['zone{}'.format(zone)][command]
                                        self._send_commands.append('{},{},{}'.format(
                                                commandinfo[2], commandinfo[3], commandinfo[4]))                                                                          

                                except Exception as err:
                                    self.logger.debug("Updating Item for avdevice_{}: Command {} is a standard command. Message: {}".format(
                                        self._name.lower(), command, err))
                                                
                                if updating == True:
                                    self.logger.debug("Updating Item for avdevice_{}: {} set {} to {} for {} in zone {}".format(
                                        self._name.lower(), caller, command, value, item.id(), zone))
                                    self._trigger_reconnect = True
                                    if command in self._functions['zone{}'.format(zone)] and isinstance(value, bool):
                                        commandinfo = self._functions['zone{}'.format(zone)][command]
                                        if commandinfo[2] in self._send_commands:
                                            self.logger.debug("Updating Item for avdevice_{}: Command {} already in Commandlist. Ignoring.".format(
                                                self._name.lower(), commandinfo[2]))
                                        else:
                                            self.logger.debug("Updating Item for avdevice_{}: Updating Zone {} Commands {} for {}".format(
                                                self._name.lower(), zone, self._send_commands, item))
                                            self._send_commands.append('{},{},{}'.format(
                                                commandinfo[2], commandinfo[3], commandinfo[4]))
                                    elif command_on in self._functions['zone{}'.format(zone)] and isinstance(value, bool) and value == 1:
                                        commandinfo = self._functions['zone{}'.format(zone)][command_on]
                                        if commandinfo[2] in self._send_commands:
                                            self.logger.debug("Updating Item for avdevice_{}: Command On {} already in Commandlist {}. Ignoring.".format(
                                                self._name.lower(), commandinfo[2], self._send_commands))
                                        else:
                                            try:                                            
                                                replacedvalue = '1'  
                                                self._send_commands.append('{},{},{}'.format(
                                                    commandinfo[2], commandinfo[3], commandinfo[4].replace('**', replacedvalue)))
                                                self._sendingcommand = '{},{},{}'.format(
                                                    commandinfo[2], commandinfo[3], commandinfo[4].replace('**', replacedvalue))
                                            except:
                                                if commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
                                                    replacedvalue = '0'
                                                else:
                                                    replacedvalue = '1'
                                                self._send_commands.append('{},{},{}'.format(
                                                    commandinfo[2], commandinfo[3], commandinfo[4].replace('*', replacedvalue)))
                                                self._sendingcommand = '{},{},{}'.format(
                                                    commandinfo[2], commandinfo[3], commandinfo[4].replace('*', replacedvalue)) 
                                            self.logger.debug("Updating Item for avdevice_{}: Update Zone {} Command On {} for {}".format(
                                                self._name.lower(), zone, commandinfo[2], item))
                                            if command_on == 'power on':
                                                self.logger.debug("Updating Item for avdevice_{}: Command Power On for zone: {}. Appending relevant query commands: {}".format(
                                                    self._name.lower(), zone, self._query_zonecommands['zone{}'.format(zone)]))
                                                for query in self._query_zonecommands['zone{}'.format(zone)]:
                                                    if not query in self._send_commands:
                                                        self._send_commands.append(query)  
                                            
                                    elif command_off in self._functions['zone{}'.format(zone)] and isinstance(value, bool) and value == 0:
                                        commandinfo = self._functions['zone{}'.format(zone)][command_off]
                                        if commandinfo[2] in self._send_commands:
                                            self.logger.debug("Updating Item for avdevice_{}: Command Off {} already in Commandlist {}. Ignoring.".format(
                                                self._name.lower(), commandinfo[2], self._send_commands))
                                            #self._send_commands[self._send_commands.index(sendcommand)] = commandinfo
                                        else:
                                            try:                                            
                                                replacedvalue = '0'  
                                                self._send_commands.append('{},{},{}'.format(
                                                    commandinfo[2], commandinfo[3], commandinfo[4].replace('***', replacedvalue)))
                                                self._sendingcommand = '{},{},{}'.format(
                                                    commandinfo[2], commandinfo[3], commandinfo[4].replace('***', replacedvalue))
                                            except:
                                                if commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
                                                    replacedvalue = '1'
                                                else:
                                                    replacedvalue = '0'
                                                self._send_commands.append('{},{},{}'.format(
                                                    commandinfo[2], commandinfo[3], commandinfo[4].replace('*', replacedvalue)))
                                                self._sendingcommand = '{},{},{}'.format(
                                                    commandinfo[2], commandinfo[3], commandinfo[4].replace('*', replacedvalue))                                            
                                            self.logger.debug("Updating Item for avdevice_{}: Update Zone {} Command Off {} for {}".format(
                                                self._name.lower(), zone, commandinfo[2], item))
                                    elif command_set in self._functions['zone{}'.format(zone)] and isinstance(value, int):
                                        commandinfo = self._functions['zone{}'.format(zone)][command_set]
                                        try:
                                            value = max(min(value, int(commandinfo[7])), 0)
                                            self.logger.debug("Updating Item for avdevice_{}: value limited to {}.".format(
                                                self._name.lower(), commandinfo[7]))
                                        except:
                                            self.logger.debug(
                                                "Updating Item for avdevice_{}: Value limited to specific number of digits".format(self._name.lower()))
                                        if commandinfo[2].count('*') > 1:
                                        	anzahl = commandinfo[2].count('*')
                                        	self.logger.debug(
                                                "Updating Item for avdevice_{}: Value has to be {} digits.".format(self._name.lower(), anzahl))
                                        	value = max(min(value, int(re.sub('[^0-9]', '', re.sub('\*', '9', commandinfo[2])))), 0)
                                        	command_re = re.sub(r'(\*)\1+', '{0:0{1}d}'.format(value, anzahl), commandinfo[2])
                                        	response = re.sub(r'(\*)\1+', '{0:0{1}d}'.format(value, anzahl), commandinfo[4])
                                        elif commandinfo[2].count('*') == 1:                                            
                                            if command.startswith('speakers'):                
                                                currentvalue = int(self._items['zone{}'.format(zone)]['speakers']['Item'][0]())
                                                multiply = -1 if item() == 0 else 1
                                                value = abs(int(self.get_iattr_value(item.conf, 'avdevice_zone{}_speakers'.format(zone))))
                                                powercommands = self._functions['zone{}'.format(zone)]['power on']
                                                self.logger.debug(
                                                    "Updating Item for avdevice_{}: Speaker current value is {}. Multiply: {}. Value: {}".format(self._name.lower(), currentvalue, multiply, value))
                                                if not currentvalue == value or multiply == -1:
                                                    value = currentvalue + (value * multiply)
                                                if value > 0: 
                                                    if powercommands[6].lower() in ['1', 'true', 'yes', 'on']:
                                                        replacedvalue = '0'
                                                    else:
                                                        replacedvalue = '1'
                                                    self._send_commands.insert(0, '{},{},{}'.format(powercommands[2],powercommands[3],powercommands[4].replace('*', replacedvalue)))
                                                    self._sendingcommand = '{},{},{}'.format(powercommands[2],powercommands[3],powercommands[4].replace('*', replacedvalue))
                                                    self.logger.debug("Updating Item for avdevice_{}: Turning power on. powercommands is: {}".format(self._name.lower(), powercommands))

                                            else:
                                                value = max(min(value, 9), 0)
                                            command_re = commandinfo[2].replace('*', '{0:01d}'.format(value))
                                            response = commandinfo[4].replace('*', '{0:01d}'.format(value))
                                            self.logger.debug(
                                                "Updating Item for avdevice_{}: Value has to be 1 digit. Value is {}".format(self._name.lower(), value))
                                        
                                        elif commandinfo[2].count('*') == 0:
                                        	self.logger.error("Updating Item for avdevice_{}: Set command {} does not have any placeholder *.".format(self._name.lower(), commandinfo))

                                        if not self._send_commands == []:
                                            appending = True
                                            for sendcommand in self._send_commands:
                                                self.logger.debug("Updating Item for avdevice_{}: Testing send command: {}".format(
                                                    self._name.lower(), sendcommand))
                                                if commandinfo[3] in sendcommand:
                                                    self._send_commands[self._send_commands.index(sendcommand)] = self._sendingcommand = '{},{},{}'.format(
                                                        command_re, commandinfo[3], response)                                                    
                                                    self._requery_counter = 0
                                                    self.logger.debug("Updating Item for avdevice_{}: Command Set {} already in Commandlist {}. Replaced. Sendingcommand: {}".format(
                                                        self._name.lower(), command, self._send_commands, self._sendingcommand))
                                                    appending = False
                                                    break
                                            if appending == True:
                                                self._send_commands.append('{},{},{}'.format(command_re, commandinfo[3], response))
                                                self._sendingcommand = '{},{},{}'.format(command_re, commandinfo[3], response)
                                                self._requery_counter = 0
                                                self.logger.debug("Updating Item for avdevice_{}: Update Zone {} Command Set {} for {}. Command: {}".format(
                                                    self._name.lower(), zone, commandinfo[2], item, command_re))
                                        else:
                                            self._send_commands.append('{},{},{}'.format(
                                                command_re, commandinfo[3], response))
                                            self._requery_counter = 0
                                            self.logger.debug("Updating Item for avdevice_{}: Update Zone {} Command Set, adding to empty Commandlist {} for {}. Command: {}".format(
                                                self._name.lower(), zone, self._send_commands, item, command_re))
                                    else:
                                        self.logger.error("Updating Item for avdevice_{}: Command {} not in text file!".format(
                                            self._name.lower(), command))
                                        updating = False
                except Exception as err:
                    self.logger.error("Updating Item for avdevice_{}: Problem updating item. Error: {}".format(
                        self._name.lower(), err))
                finally:
                    if self._threadlock_update.locked(): self._updatelock.release()
                    if not self._send_commands == []:                         
                        reorderlist = []
                        index = 0
                        for command in self._send_commands:
                            if command in self._query_commands:
                                reorderlist.append(command)
                            else:                            
                                reorderlist.insert(index,command)
                                index +=1
                        self._send_commands = reorderlist
                        self._sendingcommand = self._send_commands[0]
                    self.logger.debug("Updating Item for avdevice_{}: Updating item. Command list is {}. Sendingcommand: {}. Lock is released. Now it is {}".format(
                                self._name.lower(), self._send_commands, self._sendingcommand, self._threadlock_update.locked()))
                    try:
                        if not self._is_connected == [] and not self._send_commands == []: # and sending == True:
                            sending = self._send('command', 'updateitem')
                            while sending is None:
                                self._sendlock.wait(2)
                                self.logger.warning("Waiting for sending")
                            self.logger.debug("Updating Item for avdevice_{}: Updating item. Command list is {}. Return from send is {}. Lock is released. Now it is {}".format(
                                self._name.lower(), self._send_commands, sending, self._threadlock_update.locked()))
                                

                        if self._reset_onerror == True and emptycommand == False and not self._send_commands == [] and not self._sendingcommand == 'done' and self._is_connected == []: #and self._trigger_reconnect == True and updating == True and self._is_connected == []:
                            self.logger.warning("Updating Item for avdevice_{}: Sending command {}. Starting to reset".format(self._name.lower(),self._sendingcommand))
                            resetting = self._resetitem()
                            
                            while resetting is None:
                                self._resetlock.wait(2)
                                self.logger.warning("Waiting for resetting")
                            befehle=[]
                            for eintrag in self._send_commands:
                                befehle.append(eintrag.split(',')[0])
                            try:
                                index = self._send_commands.index(self._sendingcommand)
                            except:
                                index = befehle.index(self._sendingcommand)
                                self.logger.debug("Updating Item for avdevice_{}: Sending command {} not in Sendcommands {} list, but found in {}".format(self._name.lower(),self._sendingcommand, self._send_commands, befehle))
                            if self._send_commands[index] not in self._query_commands and not self._send_commands[index] in self._specialcommands['Display']['Command']:
                                self._keep_commands[time.time()] = self._send_commands[index]                           
                            self._send_commands.pop(index)
                            self._resetondisconnect('update_end')
                            self.logger.info("Updating Item for avdevice_{}: Connection error. Resetting Item {}. Keepcommands: {}. Sendcommands: {} Sendingcommand: {}".format(
                                self._name.lower(), resetting, self._keep_commands, self._send_commands, self._sendingcommand))
                            self._sendingcommand = 'done'

                    except Exception as err:
                        if not self._is_connected == []:
                            self.logger.warning("Updating Item for avdevice_{}: Problem sending command. It is most likely not in the text file! Error: {}".format(self._name.lower(), err))
                        else:
                            self.logger.warning(
                                "Updating Item for avdevice_{}: Problem sending command - not connected! Error: {}".format(self._name.lower(), err))

    def _send(self, command, caller):
        if not self._sendlock.acquire(timeout=2):
            return
        try:
            if not self._send_commands == []:
                if command == 'command':
                    to_send = self._send_commands[0].split(",")[0]
                elif command == 'query':
                    to_send = self._send_commands[0].split(",")[1]
                else:
                    to_send = command
                    command = 'Resendcommand'
                commandlist = to_send.split("|")
                self.logger.debug("Sending {}: Starting to send {} {} from list {}. Caller: {}. Lock is: {}".format(self._name, command, to_send, self._send_commands, caller, self._threadlock_send.locked()))
                try:
                    self._sendingcommand = self._send_commands[0]
                except:
                    self._sendingcommand = to_send
                response = self._send_commands[0].split(",")[2].split("|")
                for resp in response:
                    if resp in self._specialcommands['Display']['Command']:
                        keyfound = True
                    else:
                        keyfound = False 
                if self._send_commands[0] in self._query_commands and len(self._send_commands) >1 and not keyfound == True and self._specialcommands['Display']['Ignore'] < 5:
                    self._specialcommands['Display']['Ignore'] = self._specialcommands['Display']['Ignore'] + 5
                    if self._specialcommands['Display']['Command'] not in self._ignoreresponse  and not '' in self._ignoreresponse and not self._specialcommands['Display']['Command'] == '':
                        self._ignoreresponse.append(self._specialcommands['Display']['Command'])
                    #self.logger.debug("Sending {}: Querycommand. Command: {}. Querycommand: {}, Display Ignore: {}, Input Ignore: {}".format(self._name, self._send_commands[0],self._query_commands, self._specialcommands['Display']['Ignore'], self._specialcommands['Input']['Ignore']))
                    
                elif self._send_commands[0] not in self._query_commands or len(self._send_commands) <=1 or keyfound == True:
                    if self._specialcommands['Display']['Ignore'] >= 5:
                        self._specialcommands['Display']['Ignore'] = self._specialcommands['Display']['Ignore'] - 5
                    #self.logger.debug("Sending {}: No Querycommand. Command: {}. Querycommand: {}. Display Ignore: {}. Input Ignore:{}".format(self._name, self._send_commands[0],self._query_commands,self._specialcommands['Display']['Ignore'],self._specialcommands['Input']['Ignore']))
                    
                    if self._specialcommands['Display']['Ignore'] == 0 and not 1 in self._specialcommands['Input']['Ignore']:
                        while self._specialcommands['Display']['Command'] in self._ignoreresponse:
                            self._ignoreresponse.remove(self._specialcommands['Display']['Command'])
                        #self.logger.debug("Sending {}: Removing {} from ignore. Ignored responses are now: {}".format(self._name, self._specialcommands['Display']['Command'], self._ignoreresponse))

                if self._trigger_reconnect == True:
                        self.logger.debug("Sending {}: Trying to connect while sending command".format(self._name))
                        self.connect()
                cmd = 0
                for multicommand in commandlist:
                    cmd += 1
                    if not self._rs232 is None:
                        #result = self._serial.write(bytes('{}\r'.format(multicommand), 'utf-8'))                        
                        result = self._serialwrapper.write(u'{}\r'.format(multicommand))
                        self._serialwrapper.flush()
                        self.logger.debug("Sending Serial {}: {} was sent {} from Multicommand-List {}. Returns {}. Sending command: {}".format(self._name, command, multicommand, commandlist, result, self._sendingcommand))
                        self._wait(0.2)
                        if cmd >= len(commandlist) and self._threadlock_send.locked():
                            self._sendlock.notify()
                        return result
                        

                    elif not self._tcp is None:
                        result = self._socket.send(bytes('{}\r'.format(multicommand), 'utf-8'))
                        self.logger.debug("Sending TCP {}: {} was sent {} from Multicommand-List {}. Returns {}".format(self._name, command, multicommand, commandlist, result))
                        self._wait(0.2)
                        if cmd >= len(commandlist) and self._threadlock_send.locked():
                            self._sendlock.notify()
                        return result
                        
                    else:
                        self.logger.error("Sending {}: Neither IP address nor Serial device definition found".format(self._name))
        except IOError as err:
            if err.errno == 32:
                self.logger.warning(
                    "Sending {}: Problem sending multicommand {}, not connected. Message: {}".format(self._name, self._send_commands[0], err))
                try:
                    self._socket.shutdown(2)
                    self._socket.close()
                    self.logger.debug("Sending {}: TCP socket closed".format(self._name))
                except:
                    self.logger.debug(
                        "Sending {}: No TCP socket to close.".format(self._name))
                try:
                    self._is_connected.remove('TCP')
                    self.connect()
                    self.logger.debug("Sending {}: reconnect TCP started.".format(self._name))
                except:
                    self.logger.debug(
                        "Sending {}: Cannot reconnect TCP.".format(self._name))
                try:
                    self._serialwrapper.close()
                    self.logger.debug("Sending {}: Serial socket closed".format(self._name))
                except:
                    self.logger.debug(
                        "Sending {}: No Serial socket to close.".format(self._name))
                try:
                    self._is_connected.remove('Serial')
                    self.connect()
                    self.logger.debug("Sending {}: reconnect Serial started.".format(self._name))
                except:
                    self.logger.debug(
                        "Sending {}: Cannot reconnect Serial.".format(self._name))


        except Exception as err:
            try:
                self.logger.warning(
                    "Sending {}: Problem sending multicommand {}. Message: {}".format(self._name, self._send_commands[0], err))
            except:
                self.logger.warning(
                    "Sending {}: Problem sending multicommand {}. Message: {}".format(self._name, self._send_commands, err))
        finally:
            if self._threadlock_send.locked(): self._sendlock.release()
            #self.logger.debug("Sending {}: Finished sending command. Lock is released. Now it is {}".format(self._name, self._threadlock_send.locked()))

    # Close connection to receiver and set alive to false
    def stop(self):
        self.alive = False
        self._sh.scheduler.change('avdevice-tcp-reconnect', active=False)
        self._sh.scheduler.remove('avdevice-tcp-reconnect')
        self._sh.scheduler.change('avdevice-serial-reconnect', active=False)
        self._sh.scheduler.remove('avdevice-serial-reconnect')

        try:
            self._socket.shutdown(2)
            self._socket.close()
            self.logger.debug("Stopping {}: closed".format(self._name))
        except:
            self.logger.debug(
                "Stopping {}: No TCP socket to close.".format(self._name))
        try:
            self._serialwrapper.close()
        except:
            self.logger.debug(
                "Stopping {}: No Serial socket to close.".format(self._name))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    # todo
    # change PluginClassName appropriately
    PluginClassName(Arduino).run()
