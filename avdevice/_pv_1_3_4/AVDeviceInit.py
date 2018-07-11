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
        self._specialparse = {}
        self._number_of_zones = 0
        self._special_commands = {}

    def _update_dependencies(self, dependencies):
        done = False
        for zone in dependencies['Master_function']:
            self.logger.log(VERBOSE2, "Updating Dependencies {}: Starting for {}.".format(self._name, zone))
            for entry in dependencies['Master_function'][zone]:
                for command in self._functions[zone]:
                    if self._functions[zone][command][1] == entry:
                        for instance in dependencies['Master_function'][zone][entry]:
                            dependingfunction = instance['Function']
                            dependzone = instance['Zone']
                            # self.logger.log(VERBOSE2, "Updating Dependencies {}: Testing depending {}.".format(self._name, dependzone))
                            for command in self._functions[dependzone]:
                                # self.logger.log(VERBOSE2, "Updating Dependencies {}: Command {}.".format(self._name, command))
                                if self._functions[dependzone][command][1] == dependingfunction:
                                    for entrylist in self._items[dependzone][dependingfunction]['Master']:
                                        querycommand = self._functions[dependzone][command][3]
                                        valuetype = self._functions[dependzone][command][9]
                                        splitresponse = self._functions[dependzone][command][4].split('|')
                                        responselist = []
                                        for split in splitresponse:
                                            valuelength = split.count('*')
                                            if valuelength > 0 or 'R' in self._functions[dependzone][command][5]:
                                                toadd = split.strip()
                                                #toadd = re.sub('[*]', '', split.strip())
                                                if split.count('?') == 1 and split.count('*') == 0:
                                                    toadd = re.sub('[?]', '*', toadd)
                                                responselist.append('{},{},{}'.format(toadd, valuetype, valuelength))
                                        responsecommand = "|".join(responselist)
                                        commandlist = '{},{},{}'.format(querycommand, querycommand, responsecommand)
                                        toadd = {'Item': entrylist['Item'], 'Dependvalue': entrylist['Dependvalue'], 'Compare': entrylist['Compare'], 'Zone': entrylist['Zone'], 'Function': entrylist['Function'], 'Group': entrylist['Group']}
                                        if not querycommand == '' and self._functions[dependzone][command][4].find('*') >= 0:
                                            instance['Query'] = commandlist
                                            if dependzone == instance.get('Zone'):
                                                try:
                                                    if not toadd in dependencies['Slave_query'][dependzone][commandlist]:
                                                        dependencies['Slave_query'][dependzone][commandlist].append(toadd)
                                                        self.logger.log(VERBOSE2, "Updating Dependencies {}: Adding {} to {} in {}".format(self._name, commandlist, dependingfunction, dependzone))
                                                except Exception as err:
                                                    dependencies['Slave_query'][dependzone].update({commandlist: [toadd]})
                                    done = True
                                    break
                        if done is True:
                            break
        return dependencies

    def _processitems(self):
        if 'statusupdate' not in self._items['zone0'].keys():
            self._items['zone0']['statusupdate'] = {'Item': ['self._statusupdate'], 'Value': False}
            self.logger.debug("Initializing {}: No statusupdate Item set, creating dummy item.".format(self._name))
        dependson_list = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        finaldepend = {'Slave_function': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}, \
                       'Slave_item': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}, \
                       'Slave_query': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}, \
                       'Master_function': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}, \
                       'Master_item': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}}
        problems = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}
        for zone in self._items.keys():
            for entry in self._items[zone]:
                try:
                    depend = self._items[zone][entry]['Master']
                    if depend is not None:
                        dependson_list[zone].update({entry: depend})
                except Exception:
                    pass
        self.logger.log(VERBOSE2, "Initializing {}: Updating Depends Items for the following item entries: {}.".format(self._name, dependson_list))
        for zone in dependson_list:
            for entry in dependson_list[zone]:
                count = 0
                for entrylist in dependson_list[zone][entry]:
                    sub = dependson_list[zone][entry][count].get('Item')
                    # self.logger.log(VERBOSE2, "Initializing {}: List {}, Entry {}, {}.".format(self._name, entrylist, entry, sub))
                    try:
                        itemzone = dependson_list[zone][entry][count].get('Zone')
                        dependson_list[zone][entry][count].update({'Item': self._items[itemzone][sub].get('Item')})
                        dependson_list[zone][entry][count].update({'Function': sub})
                        self.logger.log(VERBOSE2, "Initializing {}: Updated Dependon entry for {} with entry {}.".format(self._name, sub, entrylist))
                    except Exception as err:
                        if sub == 'init':
                            problems[zone].append("{}=init".format(entry))
                            itemzone = dependson_list[zone][entry][count].get('Zone')
                            dependson_list[zone][entry][count].update({'Item': None})
                            dependson_list[zone][entry][count].update({'Function': sub})
                            self.logger.log(VERBOSE2, "Initializing {}: Item with function {} is set to init. Problems: {}".format(self._name, sub, problems))
                        else:
                            problems[zone].append(sub)
                            self.logger.error("Initializing {}: Item with function {} for dependency does not exist. Entry: {}, Error: {}".format(self._name, sub, entry, err))
                    count += 1

                try:
                    self._items[zone][entry]['Master'] = dependson_list[zone][entry]
                except Exception as err:
                    self.logger.log(VERBOSE2, "Initializing {}: Problems assigning Dependmaster: {}.".format(self._name, err))
        for zone in dependson_list:
            for entry in dependson_list[zone]:
                count = 0
                for entrylist in dependson_list[zone][entry]:
                    if entry not in problems[zone] and '{}=init'.format(entry) not in problems[zone]:
                        item = self._items[zone][entry]['Item']
                        try:
                            self._items[dependson_list[zone][entry][count]['Zone']][dependson_list[zone][entry][count]['Function']]['Slave'].append(\
                            {'Function': entry, 'Item': item, \
                            'Compare': dependson_list[zone][entry][count]['Compare'], \
                            'Zone': zone, \
                            'Group': dependson_list[zone][entry][count]['Group'], \
                            'Dependvalue': dependson_list[zone][entry][count]['Dependvalue']})
                        except Exception:
                            self._items[dependson_list[zone][entry][count]['Zone']][dependson_list[zone][entry][count]['Function']].update({'Slave': \
                            [{'Function': entry, 'Item': item, \
                            'Compare': dependson_list[zone][entry][count]['Compare'], \
                            'Zone': zone, \
                            'Dependvalue': dependson_list[zone][entry][count]['Dependvalue'], \
                            'Group': dependson_list[zone][entry][count]['Group']}]})
                        count += 1
                    else:
                        self.logger.log(VERBOSE2, "Initializing {}: Item {} for dependency function {} does not exist. Ignoring".format(self._name, dependson_list[zone][entry][count].get('Item'), entry))
        for zone in dependson_list:
            for entry in dependson_list[zone]:
                count = 0
                for entrylist in dependson_list[zone][entry]:
                    if entry not in problems[zone] and '{}=init'.format(entry) not in problems[zone]:
                        dependzone = dependson_list[zone][entry][count].get('Zone')
                        item = dependson_list[zone][entry][count].get('Item')
                        try:
                            finaldepend['Slave_function'][zone][entry].append(\
                                                                    {'Item': item, \
                                                                    'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue'), \
                                                                    'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                    'Zone': dependson_list[zone][entry][count].get('Zone'), \
                                                                    'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                    'Function': dependson_list[zone][entry][count].get('Function')})
                        except Exception as err:
                            finaldepend['Slave_function'][zone].update({entry: \
                                                                    [{'Item': item, \
                                                                    'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue'), \
                                                                    'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                    'Zone': dependson_list[zone][entry][count].get('Zone'), \
                                                                    'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                    'Function': dependson_list[zone][entry][count].get('Function')}]})

                        try:
                            finaldepend['Slave_item'][zone][self._items[zone][entry].get('Item').id()].append(\
                                                                    {'Item': item, \
                                                                    'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue'), \
                                                                    'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                    'Zone': dependson_list[zone][entry][count].get('Zone'), \
                                                                    'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                    'Function': dependson_list[zone][entry][count].get('Function')})
                        except Exception as err:
                            finaldepend['Slave_item'][zone].update({self._items[zone][entry].get('Item').id(): \
                                                                    [{'Item': item, \
                                                                    'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue'), \
                                                                    'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                    'Zone': dependson_list[zone][entry][count].get('Zone'), \
                                                                    'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                    'Function': dependson_list[zone][entry][count].get('Function')}]})

                        try:
                            finaldepend['Master_item'][dependzone][self._items[dependzone][dependson_list[zone][entry][count]['Function']].get('Item').id()].append(
                                                                    {'Item': self._items[zone][entry].get('Item'), \
                                                                   'Function': entry, \
                                                                   'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                   'Zone': zone, \
                                                                   'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                   'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue')})
                        except Exception:
                            finaldepend['Master_item'][dependzone].update(
                                                                    {self._items[dependzone][dependson_list[zone][entry][count]['Function']].get('Item').id(): \
                                                                    [{'Item': self._items[zone][entry].get('Item'), \
                                                                   'Function': entry, \
                                                                   'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                   'Zone': zone, \
                                                                   'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                   'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue')}]})
                        try:
                            finaldepend['Master_function'][dependzone][dependson_list[zone][entry][count]['Function']].append(
                                                                    {'Item': self._items[zone][entry].get('Item'), \
                                                                   'Function': entry, \
                                                                   'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                   'Zone': zone, \
                                                                   'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                   'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue')})
                        except Exception:
                            finaldepend['Master_function'][dependzone].update({dependson_list[zone][entry][count]['Function']: \
                                                                    [{'Item': self._items[zone][entry].get('Item'), \
                                                                   'Function': entry, \
                                                                   'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                   'Zone': zone, \
                                                                   'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                   'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue')}]})
                        count += 1
                    elif '{}=init'.format(entry) in problems[zone]:
                        dependzone = dependson_list[zone][entry][count].get('Zone')
                        self.logger.error(finaldepend)
                        try:
                            finaldepend['Master_function'][dependzone][dependson_list[zone][entry][count]['Function']].append(
                                                                    {'Item': self._items[zone][entry].get('Item'), \
                                                                   'Function': entry, \
                                                                   'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                   'Zone': zone, \
                                                                   'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                   'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue')})
                        except Exception:
                            try:
                                finaldepend['Master_function'][dependzone].update({dependson_list[zone][entry][count]['Function']: \
                                                                    [{'Item': self._items[zone][entry].get('Item'), \
                                                                   'Function': entry, \
                                                                   'Compare': dependson_list[zone][entry][count].get('Compare'), \
                                                                   'Zone': zone, \
                                                                   'Group': dependson_list[zone][entry][count].get('Group'), \
                                                                   'Dependvalue': dependson_list[zone][entry][count].get('Dependvalue')}]})
                            except Exception as err:
                                self.logger.error(err)
                                break
                    else:
                        self.logger.error("Initializing {}: Item {} for dependency function {} does not exist. Ignoring".format(self._name, dependson_list[zone][entry][count].get('Item'), entry))
        return self._items, finaldepend

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
            ignoreresponse = self._ignoreresponse = re.sub(', ', ',', value[0]).split(",")
            errorresponse = re.sub(', ', ',', value[1]).split(",")
            force_buffer = re.sub(', ', ',', value[2]).split(",")
            ignoredisplay = re.sub(', ', ',', value[3]).split(",")

            newignore = []
            for ignore in ignoredisplay:
                newignore.append(re.sub('^0', '', ignore))
            ignoredisplay = newignore
            self.logger.debug("Initializing {}: Ignore Display: {}".format(self._name, ignoredisplay))
            return ignoreresponse, errorresponse, force_buffer, ignoredisplay

        elif vartype == 'update_exclude':
            update_exclude = re.sub(', ', ',', value).split(",")
            self.logger.debug("Initializing {}: Special Settings: Exclude updates by {}".format(self._name, update_exclude))
            return update_exclude

    def _create_querycommands(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self._query_zonecommands['zone0'].clear()
            self._query_zonecommands['zone1'].clear()
            self._query_zonecommands['zone2'].clear()
            self._query_zonecommands['zone3'].clear()
            self._query_zonecommands['zone4'].clear()
            self._query_zonecommands = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}
            self._query_commands.clear()
            self.logger.debug("Initializing {}: Starting to create query commands. Lock is {}. Query Commands: {}, Query Zone: {}".format(
                self._name, self._threadlock_standard.locked(), self._query_commands, self._query_zonecommands))
            displaycommand = ''
            length = 0
            for zone in range(0, self._number_of_zones + 1):
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        querycommand = self._functions['zone{}'.format(zone)][command][3]
                        valuetype = self._functions['zone{}'.format(zone)][command][9]
                        responselist = []
                        splitresponse = self._functions['zone{}'.format(zone)][command][4].split("|")
                        for split in splitresponse:
                            valuelength = split.count('*')
                            if valuelength > 0 or 'R' in self._functions['zone{}'.format(zone)][command][5]:
                                # toadd = re.sub('[*]', '', split.strip())
                                toadd = split.strip()
                                if split.count('?') == 1 and split.count('*') == 0:
                                    toadd = re.sub('[?]', '*', toadd)
                                responselist.append('{},{},{}'.format(toadd, valuetype, valuelength))
                        responsecommand = "|".join(responselist)
                        commandlist = '{},{},{}'.format(querycommand, querycommand, responsecommand)
                        if not commandlist in self._query_zonecommands['zone{}'.format(zone)] \
                            and not responsecommand == '' and not responsecommand == ' ' and not responsecommand == 'none' and not querycommand == '' \
                            and not self._functions['zone{}'.format(zone)][command][4] in self._ignoreresponse:
                            if not self._functions['zone{}'.format(zone)][command][4] in self._special_commands['Display']['Command']:
                            #if not re.sub('[*]', '', self._functions['zone{}'.format(zone)][command][4]) in self._special_commands['Display']['Command']:
                                self._query_zonecommands['zone{}'.format(zone)].append(commandlist)
                                self.logger.log(VERBOSE1, "Initializing {}: Added Query Command for zone {}: {}".format(self._name, zone, commandlist))
                            else:
                                displaycommand = commandlist
                                self.logger.debug("Initializing {}: Displaycommand: {}".format(self._name, displaycommand))
                        if not commandlist in self._query_commands \
                            and not responsecommand == '' and not responsecommand == ' ' and not responsecommand == 'none' \
                            and not querycommand == '' and not self._functions['zone{}'.format(zone)][command][4] in self._ignoreresponse:
                            if not self._functions['zone{}'.format(zone)][command][4] in self._special_commands['Display']['Command']:
                            #if not re.sub('[*]', '', self._functions['zone{}'.format(zone)][command][4]) in self._special_commands['Display']['Command']:
                                self._query_commands.append(commandlist)
                                self.logger.log(VERBOSE1, "Initializing {}: Added general Query Command: {}.".format(self._name, commandlist))
                            else:
                                displaycommand = '{},{},{}'.format(querycommand, querycommand, responsecommand)
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

    def create_powercommands(self):
        try:
            self._power_commands.clear()
            self.logger.debug(
                "Initializing {}: Starting to create Powercommands: {}".format(
                    self._name, self._power_commands))
            for zone in range(0, self._number_of_zones + 1):
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        if command.startswith('power on'):
                            valuelist = []
                            valuetype = self._functions['zone{}'.format(zone)][command][9]
                            responselist = []
                            splitresponse = self._functions['zone{}'.format(zone)][command][4].split("|")
                            for response in splitresponse:
                                valuelength = response.count('*')
                                if valuelength > 0 or 'R' in self._functions['zone{}'.format(zone)][command][5]:
                                    value = response.strip()
                                    value = re.sub('[?]', '*', value) if response.count('?') == 1 and response.count('*') == 0 else value
                                    if '**' in response:
                                        value = re.sub('\*\*', 'ON', response)
                                    else:
                                        if self._functions['zone{}'.format(zone)][command][6] == 'yes':
                                            value = re.sub('[*]', '0', response)
                                        else:
                                            value = re.sub('[*]', '1', response)
                                    responselist.append('{},{},{}'.format(value, valuetype, valuelength))
                            responsecommand = "|".join(responselist)

                            value = "|".join(valuelist)
                            combined = '{},{},{}'.format(self._functions['zone{}'.format(zone)][command][2],
                                                         self._functions['zone{}'.format(zone)][command][3], responsecommand)
                            self._power_commands.append(combined)
                    except Exception as err:
                        self.logger.warning(
                            "Initializing {}: Problems searching Powercommands for {} in zone {}. Error: {}".format(
                                self._name, command, zone, err))
        except Exception as err:
            self.logger.warning("Initializing {}: Problems creating Powercommands. Error: {}".format(self._name, err))
        finally:
            self.logger.info("Initializing {}: Created Powercommands, including {} entries.".format(self._name, len(
                self._power_commands)))

            return self._power_commands

    def _create_responsecommands(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self._response_commands.clear()
            self._special_commands.clear()
            self.logger.debug("Initializing {}: Starting to create response commands. Lock is {}. Response Commands: {}".format(
                self._name, self._threadlock_standard.locked(), self._response_commands))
            for zone in range(0, self._number_of_zones + 1):
                for command in self._functions['zone{}'.format(zone)]:
                    if not command == 'init' and not command == 'statusupdate':
                        try:
                            response_to_split = self._functions['zone{}'.format(zone)][command][4].split("|")
                            for response in response_to_split:
                                origresponse = response
                                try:
                                    specialparse = self._functions['zone{}'.format(zone)][command][10]
                                except Exception:
                                    specialparse = ''
                                valuelength = response.count('*')
                                if response.find('?{str}') >= 0:
                                    commandlength = 100
                                    response = re.sub('\?\{str\}', '?', response)
                                else:
                                    commandlength = len(response)
                                if ((response.count('?') == 1 and response.count('*') == 0) or response.count('*') == 1) and \
                                        'str' in self._functions['zone{}'.format(zone)][command][9].split(','):
                                    valuelength = 30
                                    response = re.sub('\*\{str\}', '*', response)
                                    if (response.count('?') == 1 and response.count('*') == 0):
                                        response = re.sub('[?]', '*', response)

                                if response.find('*') >= 0:
                                    position = response.index('*')
                                else:
                                    position = 0
                                response = re.sub('[*]', '', response.split('*')[0])
                                try:
                                    inverse = self._functions['zone{}'.format(zone)][command][6]
                                except Exception:
                                    inverse = 'no'
                                try:
                                    expectedtype = self._functions['zone{}'.format(zone)][command][9]
                                except Exception:
                                    expectedtype = ''
                                function = command.split(" ")[0]
                                try:
                                    functiontype = command.split(" ")[1]
                                except Exception:
                                    functiontype = ''
                                item = self._items['zone{}'.format(zone)][function]['Item']
                                self.logger.log(VERBOSE2, "Initializing {}: Response: {}, Original {}; Function: {}, Item: {}, Type: {}, Valuelength: {}, Commandlength: {}".format(
                                    self._name, response, origresponse, function, item, expectedtype, valuelength, commandlength))
                                if self._functions['zone{}'.format(zone)][command][5].lower() in ['r', 'rw']:
                                    try:
                                        if function == 'display':
                                            if response in self._ignoreresponse and '' not in self._ignoreresponse:
                                                self._special_commands['Display'] = {'Command': response, 'Ignore': 1, 'Item': item}
                                            else:
                                                self._special_commands['Display'] = {'Command': response, 'Ignore': 0, 'Item': item}
                                            self.logger.log(VERBOSE1, "Initializing {}: Found Display Command and updated it: {}".format(self._name, self._special_commands))
                                        elif function == 'input':
                                            if 'Input' not in self._special_commands:
                                                self._special_commands['Input'] = {'Command': [response], 'Ignore': [0], 'Item': item}
                                            else:
                                                self._special_commands['Input']['Command'].append(response)
                                                self._special_commands['Input']['Item'].append(item)
                                                self._special_commands['Input']['Ignore'].append(0)
                                            self.logger.log(VERBOSE2, "Initializing {}: Found Input Command and added it to display commands.".format(self._name))
                                        elif (function == 'title' or function == 'station' or function == 'genre'):
                                            if 'Nowplaying' not in self._special_commands:
                                                self._special_commands['Nowplaying'] = {'Command': [response], 'Item': item}
                                            else:
                                                self._special_commands['Nowplaying']['Command'].append(response)
                                                self._special_commands['Nowplaying']['Item'].append(item)
                                            self.logger.log(VERBOSE1, "Initializing {}: Found Now Playing Command and updated it: {}".format(self._name, self._special_commands))
                                        elif (function == 'speakers'):
                                            if 'Speakers' not in self._special_commands:
                                                self._special_commands['Speakers'] = {'Command': [response], 'Item': item}
                                            else:
                                                self._special_commands['Speakers']['Command'].append(response)
                                                self._special_commands['Speakers']['Item'].append(item)
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
                                                valuelength, commandlength, position, item, function, 'zone{}'.format(zone), inverse, expectedtype, functiontype, specialparse])
                                            self.logger.log(VERBOSE1, "Initializing {}: Adding additional list to function {} for response {} with value {}.".format(
                                                self._name, function, response, self._response_commands[response]))
                                    except Exception as err:
                                        self.logger.log(VERBOSE2, "Initializing {}: Creating response command for: {}. Message: {}".format(self._name, response, err))
                                        self._response_commands[response] = [[
                                            valuelength, commandlength, position, item, function, 'zone{}'.format(zone), inverse, expectedtype, functiontype, specialparse]]
                                    self._response_commands[response] = sorted(self._response_commands[response], key=lambda x: x[0], reverse=True)
                        except Exception as err:
                            self.logger.warning("Initializing {}: Problems searching functions for {} in zone {}. Either it is not in the textfile or wrong instance name defined. Error: {}".format(self._name, command, zone, err))
        except Exception as err:
            self.logger.error(
                "Initializing {}: Problems creating response commands. Error: {}".format(self._name, err))
        finally:
            if 'Display' not in self._special_commands:
                self._special_commands['Display'] = {'Command': '', 'Ignore': 1, 'Item': ''}
            if 'Input' not in self._special_commands:
                self._special_commands['Input'] = {'Command': '', 'Ignore': [1], 'Item': ''}
            if 'Nowplaying' not in self._special_commands:
                self._special_commands['Nowplaying'] = {'Command': '', 'Item': ''}
            if 'Speakers' not in self._special_commands:
                self._special_commands['Speakers'] = {'Command': '', 'Item': ''}
            self.logger.debug("Initializing {}: Special commands for solving Display issues: {}".format(
                self._name, self._special_commands))
            self.logger.info("Initializing {}: Created response commands, including {} entries.".format(
                self._name, len(self._response_commands)))
            if self._threadlock_standard.locked():
                self._lock.release()
            return self._response_commands, self._special_commands

    def _read_parsefile(self, function):
        resulting = {'update': {}, 'parse': {}}
        try:
            self.logger.debug("Initializing {}: Starting to read specialparse file {}. Lock is {}. Special Parse: {}".format(
                self._name, self._model, self._threadlock_standard.locked(), self._specialparse))
            filename = '{}/{}.txt'.format(os.path.abspath(os.path.dirname(__file__)), function)
            parsing = codecs.open(filename, 'r', 'utf-8')
            comment = 0
            for line in parsing:
                try:
                    line = re.sub('[\\n\\r]', '', line)
                    line = re.sub('; ', ';', line)
                    line = re.sub(' ;', ';', line)
                    if line == "'''" and comment == 0:
                        comment += 1
                        code = ''
                    elif line == "'''" and comment == 1:
                        comment -= 1
                        code = ''
                    elif line == '' or line.startswith('#') or line.startswith('CODE;'):
                        code = ''
                    elif comment == 0:
                        code = line.split(";")[0]
                    if not code == '':
                        translation = line.split(";")[1]
                        try:
                            code = code.lower()
                        except Exception:
                            pass
                        try:
                            origtranslation = translation
                            translation = translation.lower()
                        except Exception:
                            origtranslation = translation
                        resulting['update'].update({translation: code})
                        resulting['parse'].update({code: origtranslation})
                except Exception as err:
                    pass
            parsing.close()
        except Exception as err:
            self.logger.error("Initializing {}: Problems reading Special Parse file: {}".format(self._name, err))
        finally:
            return resulting

    def _read_commandfile(self):
        if not self._lock.acquire(timeout=2):
            return
        try:
            self._functions.clear()
            self._functions = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
            self._specialparse.clear()
            self._specialparse = {}
            self.logger.debug("Initializing {}: Starting to read file {}. Lock is {}. Functions: {}".format(
                self._name, self._model, self._threadlock_standard.locked(), self._functions))
            filename = '{}/{}.txt'.format(os.path.abspath(os.path.dirname(__file__)), self._model)

            commands = codecs.open(filename, 'r', 'utf-8')
            zones = [0]
            comment = 0
            for line in commands:
                try:
                    line = re.sub('[\\n\\r]', '', line)
                    line = re.sub('; ', ';', line)
                    line = re.sub(' ;', ';', line)
                    if line == "'''" and comment == 0:
                        comment += 1
                        function = ''
                    elif line == "'''" and comment == 1:
                        comment -= 1
                        function = ''
                    elif line == '' or line.startswith('#') or line.startswith('ZONE;'):
                        function = ''
                    elif comment == 0:
                        row = line.split(";")
                        if row[0] == '':
                            row[0] = '0'
                        origfunction = row[1]
                        if row[2] == '':
                            row[1:3] = [''.join(row[1:3])]
                        else:
                            row[1:3] = [' '.join(row[1:3])]
                        function = row[1]
                        itemtest = re.sub(' set| on| off| increase| decrease| open| close| query', '', function)
                        for i in range(0, 10):
                            try:
                                test = row[i]
                            except IndexError:
                                if i == 5:
                                    row.append('RW')
                                if i == 6:
                                    row.append('no')
                                if i == 9 and "set" in function:
                                    row.append('int,float')
                                elif i == 9 and "display" in function:
                                    row.append('str')
                                elif i == 9 and "open" in function:
                                    row.append('bool')
                                elif i == 9 and "close" in function:
                                    row.append('bool')
                                elif i == 9 and ("on" in function or "off" in function):
                                    row.append('bool')
                                elif i == 9 and ("increase" in function or "decrease" in function):
                                    row.append('int,float')
                                    row[5] = row[5].replace('*', '')
                                else:
                                    row.append('')
                        try:
                            row[9] = row[9].replace('string', 'str')
                            row[9] = row[9].replace('num', 'int,float')
                            row[9] = row[9].replace('|', ',')
                            if row[4].count('*') == 0 and row[4].count('?') == 0 and row[9] == '':
                                row[9] = 'empty'
                            elif row[9] == '':
                                row[9] = 'bool,int,str'
                        except Exception:
                            pass
                        try:
                            itemkeys = self._items['zone{}'.format(row[0])].keys()
                        except Exception:
                            itemkeys = []
                    if function == "FUNCTION" or function == '' or function == "FUNCTION FUNCTIONTYPE":
                        pass
                    elif itemtest in itemkeys:
                        function = function.replace('open', 'on')
                        function = function.replace('close', 'off')
                        row[1] = origfunction
                        #if row[4].find('?{str}') >= 0:
                        #	row[4] = re.sub('\?\{str\}', '?', row[4])
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
                        try:
                            if row[10]:
                                self._specialparse[row[10]] = self._read_parsefile(row[10])
                        except Exception:
                            pass
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
            self._functions['zone0']['statusupdate'] = ['0', 'statusupdate', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone0']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone1']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone2']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone3']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone4']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self.logger.info("Initializing {}: Created functions list, including entries for {} zones.".format(self._name, self._number_of_zones))
            if self._threadlock_standard.locked():
                self._lock.release()
            self.logger.log(VERBOSE1, "Initializing {}: Finishing reading file. Lock is released. Lock is now {}".format(
                self._name, self._threadlock_standard.locked()))
            return self._functions, self._number_of_zones, self._specialparse
