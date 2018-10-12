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

import codecs
import re
import os
import threading
VERBOSE1 = logging.DEBUG - 1
VERBOSE2 = logging.DEBUG - 2
logging.addLevelName(logging.DEBUG - 1, 'VERBOSE1')
logging.addLevelName(logging.DEBUG - 2, 'VERBOSE2')


class Init():

    def __init__(self, smarthome, name, model, items):
        self._items = items
        self._name = name
        self._model = model
        self._sh = smarthome
        self._ignoreresponse = []

        self.logger = logging.getLogger(__name__)
        self.logger.log(VERBOSE1, "Initializing {}: Started".format(self._name))
        self._threadlock_standard = threading.Lock()
        self._lock = threading.Condition(self._threadlock_standard)

        self._functions = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        self._query_zonecommands = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}
        self._query_commands = []
        self._power_commands = []
        self._response_commands = {}
        self._number_of_zones = 0
        self._special_commands = {}

    def _addstatusupdate(self):
        if 'statusupdate' not in self._items['zone0'].keys():
            self._items['zone0']['statusupdate'] = {'Item': ['self._statusupdate'], 'Value': False}
            self.logger.debug("Initializing {}: No statusupdate Item set, creating dummy item.".format(self._name))
        return self._items

    def _process_variables(self, value, vartype):
        self.logger.debug("Initializing Serial {}: Converting {} as type {}.".format(self._name, value, vartype))
        if vartype == 'rs232':
            try:
                rs232 = re.sub('[ ]', '', value[0])
                if rs232 == 'None' or rs232 == '':
                    rs232 = baud = serial_timeout = None
                self.logger.debug("Initializing Serial {}: Serialport is {}.".format(self._name, rs232))
            except Exception as err:
                rs232 = baud = serial_timeout = None
                self.logger.warning("Initializing Serial {}: Serial Port is {}. Error: {}.".format(self._name, baud, err))
            if rs232 is not None:
                try:
                    baud = int(value[1])
                    self.logger.debug("Initializing Serial {}: Baudrate is {}.".format(self._name, baud))
                except Exception as err:
                    baud = 9600
                    self.logger.debug("Initializing Serial {}: Using standard baudrate {} because: {}.".format(self._name, baud, err))
                try:
                    serial_timeout = float(value[2])
                    self.logger.debug("Initializing Serial {}: Timeout is {}.".format(self._name, serial_timeout))
                except Exception as err:
                    serial_timeout = 0.1
                    self.logger.debug("Initializing Serial {}: Using standard timeout {}. Because: {}.".format(self._name, serial_timeout, err))
            return rs232, baud, serial_timeout
        elif vartype == 'tcp':
            try:
                tcp = re.sub('[ ]', '', value[0])
                if tcp == 'None' or tcp == '' or tcp == '0.0.0.0':
                    tcp = port = tcp_timeout = None
                self.logger.debug("Initializing TCP {}: IP is {}.".format(self._name, tcp))
            except Exception as err:
                tcp = port = tcp_timeout = None
                self.logger.warning("Initializing TCP {}: Problem setting IP: {}.".format(self._name, err))
            if tcp is not None:
                try:
                    port = int(value[1])
                    self.logger.debug("Initializing TCP {}: Port is {}.".format(self._name, port))
                except Exception as err:
                    port = None
                    self.logger.warning("Initializing TCP {}: Port is {} because: {}.".format(self._name, port, err))
                try:
                    tcp_timeout = int(value[2])
                    self.logger.debug("Initializing TCP {}: Timeoout is {}.".format(self._name, tcp_timeout))
                except Exception as err:
                    tcp_timeout = 1
                    self.logger.warning("Initializing TCP {}: Timeout is set to standard (1) because: {}.".format(self._name, err))
            return tcp, port, tcp_timeout

        elif vartype == 'dependson':
            try:
                dependson = re.sub('[ ]', '', value[0])
                if dependson == 'None' or dependson == '':
                    dependson = None
                if dependson is None:
                    dependson_value = None
                else:
                    if re.sub('[ ]', '', str(value[1])).lower() in ['1', 'yes', 'true', 'on']:
                        dependson_value = True
                    elif re.sub('[ ]', '', str(value[1])).lower() in ['0', 'no', 'false', 'off']:
                        dependson_value = False
                self.logger.debug("Initializing {}: Dependson Item: {}. Value: {}".format(self._name, dependson, dependson_value))
            except Exception:
                if dependson is not None:
                    dependson_value = True
                    self.logger.debug("Initializing {}: Dependson Item: {}. No value for item given, assuming True.".format(self._name, dependson))
                else:
                    dependson_value = None
                    self.logger.debug("Initializing {}: No Dependson Item.".format(self._name))
            if dependson is not None:
                if re.sub('[ ]', '', str(value[2])).lower() in ['1', 'yes', 'true', 'on'] and dependson:
                    depend0_power0 = True
                elif re.sub('[ ]', '', str(value[2])).lower() in ['0', 'no', 'false', 'off'] or not dependson:
                    depend0_power0 = False
                if re.sub('[ ]', '', str(value[3])).lower() in ['1', 'yes', 'true', 'on'] and dependson:
                    depend0_volume0 = True
                elif re.sub('[ ]', '', str(value[3])).lower() in ['0', 'no', 'false', 'off'] or not dependson:
                    depend0_volume0 = False
                self.logger.debug("Initializing {}: Resetting volume after dependson is off: {}. Resetting power: {}.".format(self._name, depend0_volume0, depend0_power0))
            else:
                depend0_power0 = depend0_volume0 = None
            return dependson, dependson_value, depend0_power0, depend0_volume0

        elif vartype == 'responsebuffer':
            if str(value).lower() in ['1', 'yes', 'true', 'on']:
                response_buffer = True
            elif str(value).lower() in ['0', 'no', 'false', 'off']:
                response_buffer = False
            else:
                response_buffer = abs(int(value)) * -1
            return response_buffer

        elif vartype == 'resetonerror':
            if str(value).lower() in ['1', 'yes', 'true', 'on']:
                reset_onerror = True
            elif str(value).lower() in ['0', 'no', 'false', 'off']:
                reset_onerror = False
            return reset_onerror

        elif vartype == 'responses':
            ignoreresponse = self._ignoreresponse = re.sub('[ ]', '', value[0]).split(",")
            errorresponse = re.sub('[ ]', '', value[1]).split(",")
            force_buffer = re.sub('[ ]', '', value[2]).split(",")
            ignoredisplay = re.sub('[ ]', '', value[3]).split(",")
            self.logger.debug("Initializing {}: Special Settings: Ignoring responses {}.".format(self._name, ignoreresponse))
            self.logger.debug("Initializing {}: Special Settings: Error responses {}.".format(self._name, errorresponse))
            self.logger.debug("Initializing {}: Special Settings: Force buffer {}.".format(self._name, force_buffer))
            self.logger.debug("Initializing {}: Special Settings: Ignore Display {}".format(self._name, ignoredisplay))
            return ignoreresponse, errorresponse, force_buffer, ignoredisplay

    def _create_querycommands(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self.logger.debug("Initializing {}: Starting to create query commands. Lock is {}".format(
                self._name, self._threadlock_standard.locked()))
            displaycommand = ''
            length = 0
            for zone in range(0, self._number_of_zones + 1):
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        querycommand = self._functions['zone{}'.format(zone)][command][3]
                        valuetype = self._functions['zone{}'.format(zone)][command][8]
                        responselist = []
                        splitresponse = self._functions['zone{}'.format(zone)][command][4].split("|")
                        for split in splitresponse:
                            if split.count('*') > 0 or 'R' in self._functions['zone{}'.format(zone)][command][5]:
                                responselist.append(split.strip())
                        responsestring = "|".join(responselist)
                        responsecommand = re.sub('[*]', '', responsestring)
                        if not '{},{},{},{}'.format(querycommand, querycommand, responsecommand, valuetype) in self._query_zonecommands['zone{}'.format(zone)] \
                            and not responsecommand == '' and not responsecommand == ' ' and not responsecommand == 'none' and not querycommand == '' \
                            and not self._functions['zone{}'.format(zone)][command][4] in self._ignoreresponse:
                            if not re.sub('[*]', '', self._functions['zone{}'.format(zone)][command][4]) in self._special_commands['Display']['Command']:
                                self._query_zonecommands['zone{}'.format(zone)].append('{},{},{},{}'.format(
                                    querycommand, querycommand, responsecommand, valuetype))
                            else:
                                displaycommand = '{},{},{},{}'.format(querycommand, querycommand, responsecommand, valuetype)
                                self.logger.debug("Initializing {}: Displaycommand: {}".format(self._name, displaycommand))
                        if not '{},{},{},{}'.format(querycommand, querycommand, responsecommand, valuetype) in self._query_commands \
                            and not responsecommand == '' and not responsecommand == ' ' and not responsecommand == 'none' \
                            and not querycommand == '' and not self._functions['zone{}'.format(zone)][command][4] in self._ignoreresponse:
                            if not re.sub('[*]', '', self._functions['zone{}'.format(zone)][command][4]) in self._special_commands['Display']['Command']:
                                self._query_commands.append('{},{},{},{}'.format(querycommand, querycommand, responsecommand, valuetype))
                            else:
                                displaycommand = '{},{},{},{}'.format(querycommand, querycommand, responsecommand, self._functions['zone{}'.format(zone)][command][8])
                                self.logger.log(VERBOSE1, "Initializing {}: Displaycommand: {}".format(self._name, displaycommand))
                    except Exception as err:
                        self.logger.error("Initializing {}: Problems adding query commands for command {}. Error: {}".format(
                            self._name, command, err))
                length += len(self._query_zonecommands['zone{}'.format(zone)])
            if not displaycommand == '':
                self._query_commands.append(displaycommand)
                length += 1
        except Exception as err:
            self.logger.error("Initializing {}: Problems searching for query commands. Error: {}".format(self._name, err))
        finally:
            if self._threadlock_standard.locked():
                self._lock.release()
            self.logger.info("Initializing {}: Created query commands, including {} entries.".format(self._name, length))
            return self._query_commands, self._query_zonecommands

    def _create_powercommands(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self.logger.debug("Initializing {}: Starting to create power commands. Lock is {}".format(
                self._name, self._threadlock_standard.locked()))
            for zone in range(0, self._number_of_zones + 1):
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        if command.startswith('power on'):
                            if '**' in self._functions['zone{}'.format(zone)][command][4]:
                                value = re.sub('\*\*', 'ON', self._functions['zone{}'.format(zone)][command][4])
                            else:
                                if self._functions['zone{}'.format(zone)][command][6] == 'yes':
                                    value = re.sub('[*]', '0', self._functions['zone{}'.format(zone)][command][4])
                                else:
                                    value = re.sub('[*]', '1', self._functions['zone{}'.format(zone)][command][4])
                            combined = '{},{},{},{}'.format(self._functions['zone{}'.format(zone)][command][2], self._functions['zone{}'.format(zone)][command][3], value, self._functions['zone{}'.format(zone)][command][8])
                            self._power_commands.append(combined)
                    except Exception as err:
                        self.logger.warning("Initializing {}: Problems searching power commands for {} in zone {}. Error: {}".format(self._name, command, zone, err))
        except Exception as err:
            self.logger.warning("Initializing {}: Problems creating power commands. Error: {}".format(self._name, err))
        finally:
            if self._threadlock_standard.locked():
                self._lock.release()
            self.logger.info("Initializing {}: Created power commands, including {} entries.".format(self._name, len(self._power_commands)))

            return self._power_commands

    def _create_responsecommands(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self.logger.debug("Initializing {}: Starting to create response commands. Lock is {}".format(
                self._name, self._threadlock_standard.locked()))
            for zone in range(0, self._number_of_zones + 1):
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        response_to_split = self._functions['zone{}'.format(zone)][command][4].split("|")
                        for response in response_to_split:
                            valuelength = response.count('*')
                            if response.count('*') == 1 and self._functions['zone{}'.format(zone)][command][8].startswith('str'):
                                valuelength = 30

                            if response.find('*') >= 0:
                                position = response.index('*')
                            else:
                                position = 0
                            response = re.sub('[*]', '', response)
                            commandlength = len(response)
                            try:
                                inverse = self._functions['zone{}'.format(zone)][command][6]
                            except Exception:
                                inverse = 'no'
                            try:
                                expectedtype = self._functions['zone{}'.format(zone)][command][8]
                            except Exception:
                                expectedtype = ''
                            function = self._functions['zone{}'.format(zone)][command][1].split(" ")[0]
                            try:
                                functiontype = self._functions['zone{}'.format(zone)][command][1].split(" ")[1]
                            except Exception:
                                functiontype = ''
                            item = self._items['zone{}'.format(zone)][function]['Item']
                            self.logger.log(VERBOSE2, "Initializing {}: Response: {}, Function: {}, Item: {}, Type: {}".format(
                                self._name, response, function, item, expectedtype))
                            if self._functions['zone{}'.format(zone)][command][5].lower() in ['r', 'rw']:
                                try:
                                    if function == 'display':
                                        if response in self._ignoreresponse and '' not in self._ignoreresponse:
                                            self._special_commands['Display'] = {'Command': response, 'Ignore': 1}
                                        else:
                                            self._special_commands['Display'] = {'Command': response, 'Ignore': 0}
                                        self.logger.log(VERBOSE1, "Initializing {}: Found Display Command and updated it: {}".format(self._name, self._special_commands))
                                    elif function == 'input':
                                        if 'Input' not in self._special_commands:
                                            self._special_commands['Input'] = {'Command': [response], 'Ignore': [0]}
                                        else:
                                            self._special_commands['Input']['Command'].append(response)
                                            self._special_commands['Input']['Ignore'].append(0)
                                        self.logger.log(VERBOSE2, "Initializing {}: Found Input Command and added it to display commands.".format(self._name))
                                    elif (function == 'title' or function == 'station' or function == 'genre'):
                                        if 'Nowplaying' not in self._special_commands:
                                            self._special_commands['Nowplaying'] = {'Command': [response]}
                                        else:
                                            self._special_commands['Nowplaying']['Command'].append(response)
                                        self.logger.log(VERBOSE1, "Initializing {}: Found Now Playing Command and updated it: {}".format(self._name, self._special_commands))
                                    elif (function == 'speakers'):
                                        if 'Speakers' not in self._special_commands:
                                            self._special_commands['Speakers'] = {'Command': [response]}
                                        else:
                                            self._special_commands['Speakers']['Command'].append(response)
                                        self.logger.log(VERBOSE1, "Initializing {}: Found Speakers Command and updated it: {}".format(self._name, self._special_commands))
                                except Exception as err:
                                    self.logger.debug("Initializing {}: No Special Commands set. Message: {}".format(self._name, err))

                                try:
                                    toadd = len(self._response_commands[response])
                                    for entry in self._response_commands[response]:
                                        if (item not in entry and expectedtype in entry and valuelength == entry[0]) and function == entry[4]:
                                            entry[3].append(item[0])
                                            self.logger.log(VERBOSE1, "Initializing {}: Appending Item to response {} for function {} with response {}.".format(
                                                self._name, response, function, entry))
                                        elif expectedtype not in entry or not valuelength == entry[0] or not function == entry[4]:
                                            toadd -= 1
                                        else:
                                            pass
                                            self.logger.log(VERBOSE1, "Initializing {}: Ignoring response {} for function {} because it is already in list.".format(
                                                self._name, response, function, entry))
                                    if toadd < len(self._response_commands[response]):
                                        self._response_commands[response].append([
                                            valuelength, commandlength, position, item, function, 'zone{}'.format(zone), inverse, expectedtype, functiontype])
                                        self.logger.log(VERBOSE1, "Initializing {}: Adding additional list to function {} for response {} with value {}.".format(
                                            self._name, function, response, self._response_commands[response]))
                                except Exception as err:
                                    self.logger.log(VERBOSE2, "Initializing {}: Creating response command for: {}. Message: {}".format(self._name, response, err))
                                    self._response_commands[response] = [[
                                        valuelength, commandlength, position, item, function, 'zone{}'.format(zone), inverse, expectedtype, functiontype]]
                                self._response_commands[response] = sorted(self._response_commands[response], key=lambda x: x[0], reverse=True)
                    except Exception as err:
                        self.logger.warning("Initializing {}: Problems searching functions for {} in zone {}. Either it is not in the textfile or wrong instance name defined. Error: {}".format(self._name, command, zone, err))
        except Exception as err:
            self.logger.error(
                "Initializing {}: Problems creating response commands. Error: {}".format(self._name, err))
        finally:
            if 'Display' not in self._special_commands:
                self._special_commands['Display'] = {'Command': '', 'Ignore': 1}
            if 'Input' not in self._special_commands:
                self._special_commands['Input'] = {'Command': '', 'Ignore': 1}
            if 'Nowplaying' not in self._special_commands:
                self._special_commands['Nowplaying'] = {'Command': ''}
            if 'Speakers' not in self._special_commands:
                self._special_commands['Speakers'] = {'Command': ''}
            self.logger.debug("Initializing {}: Special commands for solving Display issues: {}".format(
                self._name, self._special_commands))
            self.logger.info("Initializing {}: Created response commands, including {} entries.".format(
                self._name, len(self._response_commands)))
            if self._threadlock_standard.locked():
                self._lock.release()
            return self._response_commands, self._special_commands

    def _read_commandfile(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self.logger.debug("Initializing {}: Starting to read file {}. Lock is {}".format(
                self._name, self._model, self._threadlock_standard.locked()))
            filename = '{}/{}.txt'.format(os.path.abspath(os.path.dirname(__file__)), self._model)

            commands = codecs.open(filename, 'r', 'utf-8')
            zones = [0]
            for line in commands:
                try:
                    line = re.sub('[!@#$\\n\\r]', '', line)
                    line = re.sub('; ', ';', line)
                    line = re.sub(' ;', ';', line)
                    if line == '':
                        function = ''
                    else:
                        row = line.split(";")
                        if row[0] == '':
                            row[0] = '0'
                        if row[2] == '':
                            row[1:3] = [''.join(row[1:3])]
                        else:
                            row[1:3] = [' '.join(row[1:3])]
                        function = row[1]
                        itemtest = re.sub(' set| on| off| increase| decrease', '', function)
                        for i in range(0, 9):
                            try:
                                test = row[i]
                            except IndexError:
                                if i == 5:
                                    row.append('RW')
                                if i == 6:
                                    row.append('no')
                                if i == 8 and "set" in function:
                                    row.append('int,float')
                                elif i == 8 and ("on" in function or "off" in function):
                                    row.append('bool')
                                elif i == 8 and ("increase" in function or "decrease" in function):
                                    row.append('int,float')
                                    row[5] = row[5].replace('*', '')
                                else:
                                    row.append('')
                        try:
                            row[8] = row[8].replace('string', 'str')
                            row[8] = row[8].replace('num', 'int,float')
                            row[8] = row[8].replace('|', ',')
                            if row[8] == '':
                                row[8] = 'bool,int,str'
                        except Exception:
                            pass
                        try:
                            itemkeys = self._items['zone{}'.format(row[0])].keys()
                        except Exception:
                            itemkeys = []
                    if function == "FUNCTION" or function == '' or function == "FUNCTION FUNCTIONTYPE":
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
                            self.logger.error("Initializing {}: Error in Commandfile on line: {}".format(self._name, line))
                        if not int(row[0]) in zones:
                            zones.append(int(row[0]))
                    else:
                        self.logger.warning("Initializing {}: Function {} for zone {} not used by any item. Re-visit items and config file!".format(
                            self._name, function, row[0]))
                except Exception as err:
                    self.logger.error("Initializing {}: Problems parsing command file. Error: {}".format(self._name, err))
            self._number_of_zones = max(zones)
            self.logger.debug("Initializing {}: Number of zones: {}".format(self._name, self._number_of_zones))
            commands.close()
        except Exception as err:
            self.logger.error("Initializing {}: Problems loading command file. Error: {}".format(self._name, err))
        finally:
            self._functions['zone0']['statusupdate'] = ['0', 'statusupdate', '', '', '', 'W', '', '', 'bool']
            self.logger.info("Initializing {}: Created functions list, including entries for {} zones.".format(self._name, self._number_of_zones))
            if self._threadlock_standard.locked():
                self._lock.release()
            self.logger.log(VERBOSE1, "Initializing {}: Finishing reading file. Lock is released. Lock is now {}".format(
                self._name, self._threadlock_standard.locked()))
            return self._functions, self._number_of_zones
