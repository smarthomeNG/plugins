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

import re
import os

from lib.item import Items
from bin.smarthome import VERSION

VERBOSE1 = logging.DEBUG - 1
VERBOSE2 = logging.DEBUG - 2
logging.addLevelName(logging.DEBUG - 1, 'VERBOSE1')
logging.addLevelName(logging.DEBUG - 2, 'VERBOSE2')


class Init(object):

    def __init__(self, name, model, items, logger):
        self._items = items
        self._name = name
        self._model = model
        self._ignoreresponse = []
        self.itemsApi = Items.get_instance()
        self.logger = logger
        self.logger.log(VERBOSE1, "Initializing {}: Started".format(self._name))

        self._functions = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        self._query_zonecommands = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}
        self._query_commands = []
        self._power_commands = []
        self._response_commands = {}
        self._specialparse = {}
        self._number_of_zones = 0
        self._special_commands = {}

    def get_items(self, zone):
        itemlist = []
        sortedlist = []
        finallist = []
        for item in self._items[zone]:
            _result = self._items[zone][item].get('Item')
            itemlist.append(_result)
            if not item == 'dependson':
                try:
                    sortedlist.append(_result.id())
                except Exception:
                    sortedlist.append(_result)
        sortedlist.sort()
        for i in sortedlist:
            finallist.append(self.itemsApi.return_item(i))
        return finallist

    def update_dependencies(self, dependencies):
        done = False
        for zone in dependencies['Master_function']:
            self.logger.log(VERBOSE2, "Updating Dependencies {}: Starting for {}. ".format(self._name, zone))
            for entry in dependencies['Master_function'][zone]:
                for device_function in self._functions[zone]:
                    alreadydone = []
                    if self._functions[zone][device_function][1] == entry:
                        for instance in dependencies['Master_function'][zone][entry]:
                            dependingfunction = instance.get('Function')
                            depend_zone = instance.get('Zone')
                            # self.logger.log(VERBOSE2, "Updating Dependencies {}: Testing depending {}.".format(self._name, depend_zone))
                            for command in self._functions[depend_zone]:
                                # self.logger.log(VERBOSE2, "Updating Dependencies {}: Command {}.".format(self._name, command))
                                if self._functions[depend_zone][command][1] == dependingfunction:
                                    for entrylist in self._items[depend_zone][dependingfunction]['Master']:
                                        querycommand = self._functions[depend_zone][command][3]
                                        valuetype = self._functions[depend_zone][command][9]
                                        splitresponse = self._functions[depend_zone][command][4].split('|')
                                        responselist = []
                                        for splitted in splitresponse:
                                            valuelength = splitted.count('*')
                                            if valuelength > 0 or 'R' in self._functions[depend_zone][command][5]:
                                                response_toadd = splitted.strip()
                                                cond1 = splitted.count('?') == 1 and splitted.count('*') == 0
                                                response_toadd = re.sub('[?]', '*', response_toadd) if cond1 else response_toadd
                                                responselist.append('{},{},{}'.format(response_toadd, valuetype, valuelength))
                                        responsecommand = "|".join(responselist)
                                        commandlist = '{},{},{}'.format(querycommand, querycommand, responsecommand)
                                        try:
                                            if command.split(' ')[1] in ['on', 'off', 'increase', 'decrease']:
                                                for already in dependencies['Slave_query'][depend_zone]:
                                                    if already.split(',')[0] == querycommand:
                                                        alreadylist = ','.join(already.split(',')[2:]).split('|')
                                                        responses = [re.sub('[*]', '', x.split(',')[0]) for x in alreadylist]
                                                        for resp in responselist:
                                                            resp_split = re.sub('[*]', '', resp.split(',')[0])
                                                            cond1 = resp_split in responses
                                                            cond2_1 = set(resp.split(',')[1:-1])
                                                            cond2_2 = set(already.split('|')[0].split(',')[3:-1])
                                                            cond2 = cond2_1 == cond2_2
                                                            self.logger.log(VERBOSE2, "Updating Dependencies {}: Querycommand {} for zone {}"
                                                                            " already in list. Testing -{}- against the responses {}."
                                                                            " Testing type {} against {}".format(
                                                                                self._name, querycommand, zone, resp_split,
                                                                                responses, cond2_1, cond2_2))
                                                            if resp not in alreadylist and cond1 and cond2:
                                                                newquery = already + '|' + resp
                                                                dependencies['Slave_query'][depend_zone][newquery] = \
                                                                    dependencies['Slave_query'][depend_zone].get(already)
                                                                dependencies['Slave_query'][depend_zone].pop(already)
                                                                instance['Query'] = newquery
                                                                self.logger.log(VERBOSE2,
                                                                                "Updating Dependencies {}: Adding {} to {}.".format(
                                                                                    self._name, resp, alreadylist))
                                                                if commandlist not in alreadydone:
                                                                    alreadydone.append(commandlist)
                                                            elif cond1 and cond2:
                                                                if commandlist not in alreadydone:
                                                                    alreadydone.append(commandlist)
                                                                self.logger.log(VERBOSE2, "Updating Dependencies {}: Skipping {}.".format(
                                                                    self._name, commandlist))
                                        except Exception as err:
                                            pass
                                        if commandlist in alreadydone:
                                            self.logger.log(VERBOSE2, "Updating Dependencies {}: Commandlist {} is alreadydone: {}, skipping.".format(
                                                self._name, commandlist, alreadydone))
                                        else:
                                            toadd = {'Item': entrylist['Item'], 'Dependvalue': entrylist['Dependvalue'],
                                                     'Compare': entrylist['Compare'], 'Zone': entrylist['Zone'],
                                                     'Function': entrylist['Function'], 'Group': entrylist['Group']}
                                            if not querycommand == '' and self._functions[depend_zone][command][4].find('*') >= 0:
                                                instance['Query'] = commandlist
                                                try:
                                                    if toadd not in dependencies['Slave_query'][depend_zone][commandlist]:
                                                        dependencies['Slave_query'][depend_zone][commandlist].append(toadd)
                                                        self.logger.log(VERBOSE2,
                                                                        "Updating Dependencies {}: Adding {} to {} in {}".format(
                                                                            self._name, commandlist, dependingfunction,
                                                                            depend_zone))
                                                except Exception:
                                                    dependencies['Slave_query'][depend_zone].update({commandlist: [toadd]})
                                                    self.logger.log(VERBOSE2,
                                                                        "Updating Dependencies {}: Creating {} for {} in {}".format(
                                                                            self._name, commandlist, dependingfunction,
                                                                            depend_zone))
                                    done = True
                                    # break
                        if done is True:
                            break
                            pass
        return dependencies

    def _dependstage1(self, dependson_list, problems):
        self.logger.log(VERBOSE2, "Initializing {}: Starting dependency Init Stage 1.".format(self._name))
        for zone in self._items.keys():
            for entry in self._items[zone]:
                try:
                    depend = self._items[zone][entry]['Master']
                    if depend is not None:
                        dependson_list[zone].update({entry: depend})
                except Exception:
                    pass
        problems_inlist = []
        for zone in dependson_list:
            for entry in dependson_list[zone]:
                for count, entrylist in enumerate(dependson_list[zone][entry]):
                    sub = dependson_list[zone][entry][count].get('Item')
                    try:
                        itemzone = dependson_list[zone][entry][count].get('Zone')
                        dependson_list[zone][entry][count].update({'Item': self._items[itemzone][sub].get('Item')})
                        dependson_list[zone][entry][count].update({'Function': sub})
                        if not dependson_list[zone][entry][count].get('Item'):
                            self.logger.log(VERBOSE2,
                                            "Initializing {}: Updated Dependon entry for {} with entry {}.".format(
                                                self._name, sub, entrylist))
                    except Exception as err:
                        if sub == 'init':
                            problems[zone].append("{}=init".format(entry))
                            dependson_list[zone][entry][count].update({'Item': None})
                            dependson_list[zone][entry][count].update({'Function': sub})
                            self.logger.log(VERBOSE2,
                                            "Initializing {}: Item with function {} is set to init.".format(
                                                self._name, sub))
                        else:
                            problems[zone].append(sub)
                            problems_inlist.append(dependson_list[zone][entry][count])
                            if sub not in problems[zone]:
                                self.logger.error(
                                    "Initializing {}: Item with function {} for dependency does not exist. Entry: {}, Error: {}".format(
                                        self._name, sub, entry, err))
                self._items[zone][entry]['Master'] = [item for item in dependson_list[zone][entry] if item not in problems_inlist]
        self.logger.log(VERBOSE2, "Initializing {}: Finished dependency Init Stage 1.".format(self._name))
        return dependson_list, problems

    def _dependstage2(self, dependson_list, problems):
        self.logger.log(VERBOSE2, "Initializing {}: Starting dependency Init Stage 2.".format(self._name))
        problems_inlist = []
        for zone in dependson_list:
            for entry in dependson_list[zone]:
                for count, _ in enumerate(dependson_list[zone][entry]):
                    if entry not in problems[zone] and '{}=init'.format(entry) not in problems[zone]:
                        item = self._items[zone][entry].get('Item')
                        depend_zone = dependson_list[zone][entry][count].get('Zone')
                        depend_function = dependson_list[zone][entry][count].get('Function')
                        depend_compare = dependson_list[zone][entry][count].get('Compare')
                        depend_group = dependson_list[zone][entry][count].get('Group')
                        depend_value = dependson_list[zone][entry][count].get('Dependvalue')
                        depend_item = dependson_list[zone][entry][count].get('Item')
                        if depend_function:
                            try:
                                self._items[depend_zone][depend_function]['Slave'].append(
                                    {'Function': entry, 'Item': item,
                                     'Compare': depend_compare,
                                     'Zone': zone,
                                     'Group': depend_group,
                                     'Dependvalue': depend_value})
                            except Exception:
                                self._items[depend_zone][depend_function].update(
                                    {'Slave':
                                     [{'Function': entry,
                                       'Item': item,
                                       'Compare': depend_compare,
                                       'Zone': zone,
                                       'Dependvalue': depend_value,
                                       'Group': depend_group}]})
                        else:
                            self.logger.log(VERBOSE2,
                                            "Initializing {}: Dependency Init Stage 2. Ignoring dependency {}"
                                            " for {} because there is no item defined for function {}.".format(
                                                self._name, dependson_list[zone][entry][count], item, depend_item))
                            problems_inlist.append(dependson_list[zone][entry][count])
                if entry not in problems[zone] and '{}=init'.format(entry) not in problems[zone]:
                    dependson_list[zone][entry] = [item for item in dependson_list[zone][entry] if item not in problems_inlist]
                    self.logger.log(VERBOSE2, "Initializing {}: Final dependency list for item {}: {}".format(
                                    self._name, item, dependson_list[zone][entry]))
        self.logger.log(VERBOSE2, "Initializing {}: Finished dependency Init Stage 2.".format(self._name))

    def _dependstage3(self, dependson_list, problems, finaldepend):
        self.logger.log(VERBOSE2, "Initializing {}: Starting dependency Init Stage 3.".format(self._name))
        for zone in dependson_list:
            for entry in dependson_list[zone]:
                for count, _ in enumerate(dependson_list[zone][entry]):
                    if entry not in problems[zone] and '{}=init'.format(entry) not in problems[zone]:
                        depend_zone = dependson_list[zone][entry][count].get('Zone')
                        item = dependson_list[zone][entry][count].get('Item')
                        depend_function = dependson_list[zone][entry][count].get('Function')
                        depend_compare = dependson_list[zone][entry][count].get('Compare')
                        depend_group = dependson_list[zone][entry][count].get('Group')
                        depend_value = dependson_list[zone][entry][count].get('Dependvalue')
                        try:
                            finaldepend['Slave_function'][zone][entry].append(
                                {'Item': item,
                                 'Dependvalue': depend_value,
                                 'Compare': depend_compare,
                                 'Zone': depend_zone,
                                 'Group': depend_group,
                                 'Function': depend_function})
                        except Exception:
                            finaldepend['Slave_function'][zone].update(
                                {entry:
                                 [{'Item': item,
                                   'Dependvalue': depend_value,
                                   'Compare': depend_compare,
                                   'Zone': depend_zone,
                                   'Group': depend_group,
                                   'Function': depend_function}]})
                        try:
                            finaldepend['Slave_item'][zone][self._items[zone][entry].get('Item').id()].append(
                                {'Item': item,
                                 'Dependvalue': depend_value,
                                 'Compare': depend_compare,
                                 'Zone': depend_zone,
                                 'Group': depend_group,
                                 'Function': depend_function})
                        except Exception:
                            finaldepend['Slave_item'][zone].update(
                                {self._items[zone][entry].get('Item').id():
                                 [{'Item': item,
                                   'Dependvalue': depend_value,
                                   'Compare': depend_compare,
                                   'Zone': depend_zone,
                                   'Group': depend_group,
                                   'Function': depend_function}]})
                        try:
                            finaldepend['Master_item'][depend_zone][
                                self._items[depend_zone][dependson_list[zone][entry][count]['Function']].get(
                                    'Item').id()].append(
                                {'Item': self._items[zone][entry].get('Item'),
                                 'Function': entry,
                                 'Compare': depend_compare,
                                 'Zone': zone,
                                 'Group': depend_group,
                                 'Dependvalue': depend_value})
                        except Exception:
                            finaldepend['Master_item'][depend_zone].update(
                                {self._items[depend_zone][dependson_list[zone][entry][count]['Function']].get(
                                    'Item').id():
                                    [{'Item': self._items[zone][entry].get('Item'),
                                      'Function': entry,
                                      'Compare': depend_compare,
                                      'Zone': zone,
                                      'Group': depend_group,
                                      'Dependvalue': depend_value}]})
                        try:
                            finaldepend['Master_function'][depend_zone][
                                dependson_list[zone][entry][count]['Function']].append(
                                {'Item': self._items[zone][entry].get('Item'),
                                 'Function': entry,
                                 'Compare': depend_compare,
                                 'Zone': zone,
                                 'Group': depend_group,
                                 'Dependvalue': depend_value})
                        except Exception:
                            finaldepend['Master_function'][depend_zone].update(
                                {dependson_list[zone][entry][count]['Function']:
                                 [{'Item': self._items[zone][entry].get('Item'),
                                   'Function': entry,
                                   'Compare': depend_compare,
                                   'Zone': zone,
                                   'Group': depend_group,
                                   'Dependvalue': depend_value}]})
        self.logger.log(VERBOSE2, "Initializing {}: Finished dependency Init Stage 3.".format(self._name))
        return finaldepend

    def _dependstage4(self, dependson_list, problems, finaldepend):
        self.logger.log(VERBOSE2, "Initializing {}: Starting dependency Init Stage 4.".format(self._name))
        for zone in dependson_list:
            for entry in dependson_list[zone]:
                for count, _ in enumerate(dependson_list[zone][entry]):
                    if '{}=init'.format(entry) in problems[zone]:
                        depend_zone = dependson_list[zone][entry][count].get('Zone')
                        depend_compare = dependson_list[zone][entry][count].get('Compare')
                        depend_group = dependson_list[zone][entry][count].get('Group')
                        depend_value = dependson_list[zone][entry][count].get('Dependvalue')
                        try:
                            finaldepend['Master_function'][depend_zone][
                                dependson_list[zone][entry][count]['Function']].append(
                                {'Item': self._items[zone][entry].get('Item'),
                                 'Function': entry,
                                 'Compare': depend_compare,
                                 'Zone': zone,
                                 'Group': depend_group,
                                 'Dependvalue': depend_value})
                        except Exception:
                            finaldepend['Master_function'][depend_zone].update(
                                {dependson_list[zone][entry][count]['Function']:
                                 [{'Item': self._items[zone][entry].get('Item'),
                                   'Function': entry,
                                   'Compare': depend_compare,
                                   'Zone': zone,
                                   'Group': depend_group,
                                   'Dependvalue': depend_value}]})
        self.logger.log(VERBOSE2, "Initializing {}: Finished dependency Init Stage 4.".format(self._name))
        return finaldepend

    def process_items(self):
        if 'statusupdate' not in self._items['zone0'].keys():
            self._items['zone0']['statusupdate'] = {'Item': ['self._statusupdate'], 'Value': False}
            self.logger.debug("Initializing {}: No statusupdate Item set, creating dummy item.".format(self._name))
        dependson_list = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        finaldepend = {'Slave_function': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}},
                       'Slave_item': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}},
                       'Slave_query': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}},
                       'Master_function': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}},
                       'Master_item': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}}
        problems = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}

        dependson_list, problems = self._dependstage1(dependson_list, problems)
        self._dependstage2(dependson_list, problems)
        finaldepend = self._dependstage3(dependson_list, problems, finaldepend)
        finaldepend = self._dependstage4(dependson_list, problems, finaldepend)

        return self._items, finaldepend

    def create_querycommands(self):
        length = 0
        try:
            self._query_zonecommands['zone0'].clear()
            self._query_zonecommands['zone1'].clear()
            self._query_zonecommands['zone2'].clear()
            self._query_zonecommands['zone3'].clear()
            self._query_zonecommands['zone4'].clear()
            self._query_zonecommands = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}
            self._query_commands.clear()
            self.logger.debug(
                "Initializing {}: Starting to create query commands. Query Commands: {}, Query Zone: {}".format(
                    self._name, self._query_commands, self._query_zonecommands))
            displaycommand = ''
            for zone in range(0, self._number_of_zones + 1):
                alreadydone = []
                for command in self._functions['zone{}'.format(zone)]:
                    try:
                        querycommand = self._functions['zone{}'.format(zone)][command][3]
                        valuetype = self._functions['zone{}'.format(zone)][command][9]
                        responselist = []
                        splitresponse = self._functions['zone{}'.format(zone)][command][4].split("|")
                        for splitted in splitresponse:
                            valuelength = splitted.count('*')
                            if valuelength > 0 or 'R' in self._functions['zone{}'.format(zone)][command][5]:
                                toadd = splitted.strip()
                                toadd = re.sub('[?]', '*', toadd) if splitted.count('?') == 1 and splitted.count('*') == 0 else toadd
                                responselist.append('{},{},{}'.format(toadd, valuetype, valuelength))
                        responsecommand = "|".join(responselist)
                        commandlist = '{},{},{}'.format(querycommand, querycommand, responsecommand)
                        try:
                            if command.split(' ')[1] in ['on', 'off', 'increase', 'decrease']:
                                for x, already in enumerate(self._query_commands):
                                    if already.split(',')[0] == querycommand:
                                        alreadylist = ','.join(already.split(',')[2:]).split('|')
                                        responses = [re.sub('[*]', '', x.split(',')[0]) for x in alreadylist]
                                        for resp in responselist:
                                            resp_split = re.sub('[*]', '', resp.split(',')[0])
                                            cond1 = resp_split in responses
                                            cond2_1 = set(resp.split(',')[1:-1])
                                            cond2_2 = set(already.split('|')[0].split(',')[3:-1])
                                            cond2 = cond2_1 == cond2_2
                                            self.logger.log(VERBOSE2, "Updating Dependencies {}: Querycommand {} for zone {}"
                                                            " already in list. Testing -{}- against the responses {}."
                                                            " Testing type {} against {}".format(
                                                                self._name, querycommand, zone, resp_split,
                                                                responses, cond2_1, cond2_2))
                                            if resp not in alreadylist and cond1 and cond2:
                                                self.logger.log(VERBOSE2, "Initializing {}: Adding {} to {}.".format(
                                                    self._name, resp, alreadylist))
                                                self._query_commands[x] = already + '|' + resp
                                                idx = self._query_zonecommands['zone{}'.format(zone)].index(already)
                                                self._query_zonecommands['zone{}'.format(zone)][idx] = already + '|' + resp
                                                if commandlist not in alreadydone:
                                                    alreadydone.append(commandlist)
                                            elif cond1 and cond2:
                                                if commandlist not in alreadydone:
                                                    alreadydone.append(commandlist)
                                                self.logger.log(VERBOSE2, "Initializing {}: Skipping {}.".format(
                                                    self._name, commandlist))
                        except Exception:
                            pass
                        if commandlist in alreadydone:
                            self.logger.log(VERBOSE2, "Initializing {}: Commandlist {} is alreadydone: {}, skipping.".format(
                                    self._name, commandlist, alreadydone))
                        else:
                            cond1 = commandlist not in self._query_zonecommands['zone{}'.format(zone)]
                            cond2 = not responsecommand == '' and not responsecommand == ' ' and not responsecommand == 'none'
                            cond3 = not querycommand == ''
                            cond4 = not self._functions['zone{}'.format(zone)][command][4] in self._ignoreresponse
                            cond5 = not self._functions['zone{}'.format(zone)][command][4] in self._special_commands['Display']['Command']
                            if cond1 and cond2 and cond3 and cond4:
                                if cond5:
                                    self._query_zonecommands['zone{}'.format(zone)].append(commandlist)
                                    self.logger.log(VERBOSE1, "Initializing {}: Added Query Command for zone {}: {}".format(
                                        self._name, zone, commandlist))
                                else:
                                    displaycommand = commandlist
                                    self.logger.debug(
                                        "Initializing {}: Displaycommand: {}".format(self._name, displaycommand))
                            cond1 = commandlist not in self._query_commands
                            if cond1 and cond2 and cond3 and cond4:
                                if cond5:
                                    self._query_commands.append(commandlist)
                                    self.logger.log(VERBOSE1,
                                                    "Initializing {}: Added general Query Command: {}.".format(self._name,
                                                                                                               commandlist))
                                else:
                                    displaycommand = '{},{},{}'.format(querycommand, querycommand, responsecommand)
                                    self.logger.log(VERBOSE1, "Initializing {}: Displaycommand: {}".format(self._name,
                                                                                                           displaycommand))
                    except Exception as err:
                        self.logger.error(
                            "Initializing {}: Problems adding query commands for command {}. Error: {}".format(
                                self._name, command, err))
                length += len(self._query_zonecommands['zone{}'.format(zone)])
            if not displaycommand == '':
                self._query_commands.append(displaycommand)
                length += 1
        except Exception as err:
            self.logger.error(
                "Initializing {}: Problems searching for query commands. Error: {}".format(self._name, err))
        finally:
            self.logger.info(
                "Initializing {}: Created query commands, including {} entries.".format(self._name, length))
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

    def create_responsecommands(self):
        try:
            self._response_commands.clear()
            self._special_commands.clear()
            self.logger.debug(
                "Initializing {}: Starting to create response commands. Response Commands: {}".format(
                    self._name, self._response_commands))
            for zone in range(0, self._number_of_zones + 1):
                for command in self._functions['zone{}'.format(zone)]:
                    if not command == 'init' and not command == 'statusupdate':
                        try:
                            response_to_split = self._functions['zone{}'.format(zone)][command][4].split("|")
                            for response in response_to_split:
                                if not response:
                                    self.logger.log(VERBOSE2, "Initializing {}: No response set for {}".format(
                                        self._name, command))
                                    break
                                origresponse = response
                                try:
                                    specialparse = self._functions['zone{}'.format(zone)][command][10]
                                except Exception:
                                    specialparse = ''
                                valuelength = response.count('*')
                                commandlength = 100 if (response.find('?{str}') >= 0 or response.find('*{str}') >= 0) else len(response)
                                response = re.sub('\?\{str\}', '?', response) if response.find('?{str}') >= 0 else response
                                cond1 = response.count('?') == 1 and response.count('*') == 0
                                cond2 = response.count('*') == 1
                                cond3 = 'str' in self._functions['zone{}'.format(zone)][command][9].split(',')
                                if (cond1 or cond2) and cond3:
                                    valuelength = 100
                                    response = re.sub('\*\{str\}', '*', response)
                                    cond1 = response.count('?') == 1 and response.count('*') == 0
                                    response = re.sub('[?]', '*', response) if cond1 else response
                                position = response.index('*') if response.find('*') >= 0 else 0
                                response = re.sub('[*]', '', response.split('*')[0])
                                inverse = self._functions['zone{}'.format(zone)][command][6]
                                expectedtype = self._functions['zone{}'.format(zone)][command][9]
                                device_function = command.split(" ")[0]
                                try:
                                    functiontype = command.split(" ")[1]
                                except Exception:
                                    functiontype = ''
                                item = self._items['zone{}'.format(zone)][device_function]['Item']
                                self.logger.log(VERBOSE2,
                                                "Initializing {}: Response: {}, Original {}; Function: {}, Item: {},"
                                                " Type: {}, Valuelength: {}, Commandlength: {}".format(
                                                    self._name, response, origresponse, device_function, item,
                                                    expectedtype, valuelength, commandlength))
                                if self._functions['zone{}'.format(zone)][command][5].lower() in ['r', 'rw']:
                                    if device_function == 'display':
                                        self._special_commands['Display'] = {'Command': response, 'Ignore': 1, 'Item': item} \
                                            if response in self._ignoreresponse and '' not in self._ignoreresponse \
                                            else {'Command': response, 'Ignore': 0, 'Item': item}
                                    elif device_function == 'input':
                                        if 'Input' not in self._special_commands:
                                            self._special_commands['Input'] = {'Command': [response], 'Ignore': [0],
                                                                               'Item': [item]}
                                        else:
                                            self._special_commands['Input']['Command'].append(response)
                                            self._special_commands['Input']['Item'].append(item)
                                            self._special_commands['Input']['Ignore'].append(0)
                                        self.logger.log(VERBOSE2, "Initializing {}: Found Input Command and added it"
                                                        " to display commands.".format(self._name))
                                    elif device_function == 'title' or device_function == 'station' or device_function == 'genre':
                                        if 'Nowplaying' not in self._special_commands:
                                            self._special_commands['Nowplaying'] = {'Command': [response], 'Item': item}
                                        else:
                                            self._special_commands['Nowplaying']['Command'].append(response)
                                    elif device_function == 'speakers':
                                        if 'Speakers' not in self._special_commands:
                                            self._special_commands['Speakers'] = {'Command': [response], 'Item': item}
                                        else:
                                            self._special_commands['Speakers']['Command'].append(response)

                                    try:
                                        toadd = len(self._response_commands[response])
                                        for entry in self._response_commands[response]:
                                            cond1 = item not in entry and expectedtype in entry
                                            cond2 = valuelength == entry[0] and device_function == entry[4]
                                            cond3 = expectedtype not in entry
                                            cond4 = not valuelength == entry[0]
                                            cond5 = not device_function == entry[4]
                                            if cond1 and cond2:
                                                self.logger.log(VERBOSE1, "Initializing {}: Appending Item to response"
                                                                " {} for function {} with response {}.".format(
                                                                    self._name, response, device_function, entry))
                                                entry[3] = [entry[3]]
                                                entry[3].append(item[0])
                                            elif cond3 or cond4 or cond5:
                                                toadd -= 1
                                            else:
                                                self.logger.log(VERBOSE1, "Initializing {}: Ignoring response {} for function {}"
                                                                " because it is already in list.".format(
                                                                    self._name, response, device_function, entry))
                                        if toadd < len(self._response_commands[response]):
                                            self.logger.log(VERBOSE1, "Initializing {}: Adding additional list to function {}"
                                                            " for response {} with value {}.".format(
                                                                self._name, device_function, response, self._response_commands[response]))
                                            self._response_commands[response].append([
                                                valuelength, commandlength, position, item, device_function,
                                                'zone{}'.format(zone), inverse, expectedtype, functiontype,
                                                specialparse])

                                    except Exception as err:
                                        self.logger.log(VERBOSE2,
                                                        "Initializing {}: Creating response command for: {}. Message: {}".format(
                                                            self._name, response, err))
                                        self._response_commands[response] = [[
                                            valuelength, commandlength, position, item, device_function,
                                            'zone{}'.format(zone),
                                            inverse, expectedtype, functiontype, specialparse]]
                                    self._response_commands[response] = sorted(self._response_commands[response],
                                                                               key=lambda x: x[0], reverse=True)
                        except Exception as err:
                            self.logger.warning(
                                "Initializing {}: Problems searching functions for {} in zone {}. Either it is not in"
                                " the textfile or wrong instance name defined. Error: {}".format(
                                    self._name, command, zone, err))
        except Exception as err:
            self.logger.error("Initializing {}: Problems creating response commands. Error: {}".format(self._name, err))
        finally:
            self._special_commands['Display'] = {'Command': '', 'Ignore': 1, 'Item': ''} \
                if 'Display' not in self._special_commands else self._special_commands['Display']
            self._special_commands['Input'] = {'Command': '', 'Ignore': [1], 'Item': ''} \
                if 'Input' not in self._special_commands else self._special_commands['Input']
            self._special_commands['Nowplaying'] = {'Command': '', 'Item': ''} \
                if 'Nowplaying' not in self._special_commands else self._special_commands['Nowplaying']
            self._special_commands['Speakers'] = {'Command': '', 'Item': ''} \
                if 'Speakers' not in self._special_commands else self._special_commands['Speakers']
            self.logger.debug("Initializing {}: Special commands for solving Display issues: {}".format(
                self._name, self._special_commands))
            self.logger.info("Initializing {}: Created response commands, including {} entries.".format(
                self._name, len(self._response_commands)))
            return self._response_commands, self._special_commands

    def _read_parsefile(self, device_function):
        resulting = {'update': {}, 'parse': {}}
        try:
            self.logger.debug(
                "Initializing {}: Starting to read translation file {}. ".format(self._name, device_function))
            filename = '{}/translations/{}.txt'.format(os.path.abspath(os.path.dirname(__file__)), device_function)
            with open(filename, encoding='utf-8') as parsing:
                comment = 0
                for line in parsing:
                    line = re.sub('[\\n\\r]', '', line)
                    line = re.sub('; ', ';', line)
                    line = re.sub(' ;', ';', line)
                    cond1 = line == "'''" and comment == 0
                    cond2 = line == "'''" and comment == 1
                    cond3 = (line == "'''" or line == '' or line.startswith('#') or line.startswith('CODE;'))
                    comment += 1 if cond1 else -1 if cond2 else 0
                    code = ''
                    if comment == 0 and not cond1 and not cond2 and not cond3:
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
            self.logger.error("Initializing {}: Problems reading Special Parse file: {}".format(self._name, err))
        finally:
            return resulting

    def read_commandfile(self):
        try:
            self._functions.clear()
            self._functions = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
            self._specialparse.clear()
            self._specialparse = {}
            self.logger.debug("Initializing {}: Starting to read file {}. Functions: {}".format(
                self._name, self._model, self._functions))
            filename = '{}/{}.txt'.format(os.path.abspath(os.path.dirname(__file__)), self._model)

            with open(filename, encoding='utf-8') as commands:
                zones = [0]
                comment = 0
                for line in commands:
                    line = re.sub('[\\n\\r]', '', line)
                    line = re.sub('; ', ';', line)
                    line = re.sub(' ;', ';', line)
                    cond1 = line == "'''" and comment == 0
                    cond2 = line == "'''" and comment == 1
                    cond3 = (line == "'''" or line == '' or line.startswith('#') or line.startswith('ZONE;'))
                    comment += 1 if cond1 else -1 if cond2 else 0
                    device_function = ''
                    itemkeys = []
                    itemtest = ''
                    row = [None, None]
                    origfunction = None
                    if comment == 0 and not cond3:
                        row = line.split(";")
                        row[0] = '0' if row[0] == '' else row[0]
                        origfunction = row[1]
                        row[1:3] = [''.join(row[1:3])] if row[2] == '' else [' '.join(row[1:3])]
                        device_function = row[1]
                        itemtest = re.sub(' set| on| off| increase| decrease| open| close| query', '', device_function)
                        for i in range(0, 10):
                            try:
                                row[i]
                            except IndexError:
                                cond1 = (i == 9 and ("set" in device_function or
                                                     "increase" in device_function or
                                                     "decrease" in device_function))
                                cond2 = (i == 9 and ("open" in device_function or
                                                     "close" in device_function or
                                                     "on" in device_function or
                                                     "off" in device_function))
                                row.append('RW' if i == 5
                                           else 'no' if i == 6
                                           else 'int,float' if cond1
                                           else 'str' if (i == 9 and "display" in device_function)
                                           else 'bool' if cond2
                                           else '')
                                cond1 = ("increase" in device_function or "decrease" in device_function)
                                if i == 9 and cond1:
                                    row[5] = row[5].replace('*', '')
                        row[9] = row[9].replace('string', 'str')
                        row[9] = row[9].replace('num', 'int,float')
                        row[9] = row[9].replace('|', ',')
                        row[9] = 'empty' if (row[4].count('*') == 0 and row[4].count('?') == 0 and row[9] == '') \
                            else 'bool,int,str' if row[9] == '' else row[9]
                        row[2] = row[3] if not row[2] else row[2]
                        try:
                            itemkeys = self._items['zone{}'.format(row[0])].keys()
                        except Exception:
                            itemkeys = []
                    if device_function == "FUNCTION" or device_function == '' or device_function == "FUNCTION FUNCTIONTYPE":
                        pass
                    elif itemtest in itemkeys:
                        device_function = device_function.replace('open', 'on')
                        device_function = device_function.replace('close', 'off')
                        row[1] = origfunction
                        rowzone = '0' if row[0] == '' else row[0]
                        self._functions['zone{}'.format(rowzone)][device_function] = row
                        zones.append(int(row[0]) if not int(row[0]) in zones else 0)
                        try:
                            self._specialparse[row[10]] = self._read_parsefile(row[10])
                        except Exception:
                            pass
                    else:
                        self.logger.warning(
                            "Initializing {}: Function {} for zone {} not used by any item. Re-visit items and config file!".format(
                                self._name, device_function, row[0]))
            self._number_of_zones = max(zones)
            self.logger.debug("Initializing {}: Number of zones: {}".format(self._name, self._number_of_zones))
        except Exception as err:
            self.logger.error("Initializing {}: Problems loading command file. Error: {}".format(self._name, err))
        finally:
            self._functions['zone0']['statusupdate'] = ['0', 'statusupdate', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone0']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone1']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone2']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone3']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self._functions['zone4']['init'] = ['0', 'init', '', '', '', 'W', '', '', '', 'bool']
            self.logger.info(
                "Initializing {}: Created functions list, including entries for {} zones.".format(self._name,
                                                                                                  self._number_of_zones))
            self.logger.log(VERBOSE1, "Initializing {}: Finishing reading file. ".format(self._name))
            return self._functions, self._number_of_zones, self._specialparse


class ProcessVariables(Init):
    def __init__(self, value, name, logger):
        self._value = value
        self._name = name
        self.logger = logger

    def process_rs232(self):
        baud = serial_timeout = None
        try:
            rs232 = re.sub('[ ]', '', self._value[0])
            rs232 = None if rs232 == 'None' or rs232 == '' else rs232
            self.logger.debug("Initializing Serial {}: Serial port is {}.".format(self._name, rs232))
        except Exception as err:
            rs232 = None
            self.logger.warning(
                "Initializing Serial {}: Serial Port is {}. Error: {}.".format(self._name, baud, err))
        if rs232 is not None:
            try:
                baud = int(self._value[1])
                self.logger.debug("Initializing Serial {}: Baud rate is {}.".format(self._name, baud))
            except Exception as err:
                baud = 9600
                self.logger.debug(
                    "Initializing Serial {}: Using standard baud rate {} because: {}.".format(self._name, baud, err))
            try:
                serial_timeout = float(self._value[2])
                self.logger.debug("Initializing Serial {}: Timeout is {}.".format(self._name, serial_timeout))
            except Exception as err:
                serial_timeout = 0.1
                self.logger.debug(
                    "Initializing Serial {}: Using standard timeout {}. Because: {}.".format(self._name,
                                                                                             serial_timeout, err))
        return rs232, baud, serial_timeout

    def process_tcp(self):
        port = tcp_timeout = None
        try:
            tcp = re.sub('[ ]', '', self._value[0])
            tcp = None if tcp == 'None' or tcp == '' or tcp == '0.0.0.0' else tcp
            self.logger.debug("Initializing TCP {}: IP is {}.".format(self._name, tcp))
        except Exception as err:
            tcp = None
            self.logger.warning("Initializing TCP {}: Problem setting IP: {}.".format(self._name, err))
        if tcp is not None:
            try:
                port = int(self._value[1])
                self.logger.debug("Initializing TCP {}: Port is {}.".format(self._name, port))
            except Exception as err:
                port = None
                self.logger.warning("Initializing TCP {}: Port is {} because: {}.".format(self._name, port, err))
            try:
                tcp_timeout = int(self._value[2])
                self.logger.debug("Initializing TCP {}: Timeoout is {}.".format(self._name, tcp_timeout))
            except Exception as err:
                tcp_timeout = 1
                self.logger.warning(
                    "Initializing TCP {}: Timeout is set to standard (1) because: {}.".format(self._name, err))
        return tcp, port, tcp_timeout

    def process_dependson(self):
        depend = None
        try:
            depend = re.sub('[ ]', '', self._value[0])
            depend = None if depend == 'None' or depend == '' else depend
            dependson_value = True if re.sub('[ ]', '', str(self._value[1])).lower() in ['1', 'yes', 'true', 'on'] \
                else False if re.sub('[ ]', '', str(self._value[1])).lower() in ['0', 'no', 'false', 'off'] \
                else None
            self.logger.debug(
                "Initializing {}: Dependson Item: {}. Value: {}".format(self._name, depend, dependson_value))
        except Exception:
            dependson_value = True if depend is not None else None
        depend0_power0 = True if re.sub('[ ]', '', str(self._value[2])).lower() in ['1', 'yes', 'true', 'on'] and depend else False
        depend0_volume0 = True if re.sub('[ ]', '', str(self._value[3])).lower() in ['1', 'yes', 'true', 'on'] and depend else False
        self.logger.debug(
            "Initializing {}: Resetting volume after dependson is off: {}. Resetting power: {}.".format(
                self._name, depend0_volume0, depend0_power0))
        return depend, dependson_value, depend0_power0, depend0_volume0

    def process_responsebuffer(self):
        buffer = True if str(self._value).lower() in ['1', 'yes', 'true', 'on'] \
            else False if str(self._value).lower() in ['0', 'no', 'false', 'off'] \
            else abs(int(self._value)) * -1
        return buffer

    def process_resetonerror(self):
        reset = True if str(self._value).lower() in ['1', 'yes', 'true', 'on'] else False
        return reset

    def process_statusquery(self):
        statusquery = True if str(self._value).lower() in ['1', 'yes', 'true', 'on'] else False
        return statusquery

    def process_responses(self):
        ignoreresponse = self._ignoreresponse = re.sub(', ', ',', self._value[0]).split(",")
        errorresponse = re.sub(', ', ',', self._value[1]).split(",")
        force_buffer = re.sub(', ', ',', self._value[2]).split(",")
        ignoredisplay = re.sub(', ', ',', self._value[3]).split(",")
        newignore = []
        for ignore in ignoredisplay:
            newignore.append(re.sub('^0', '', ignore))
        ignoredisplay = newignore
        self.logger.debug("Initializing {}: Ignore Display: {}".format(self._name, ignoredisplay))
        return ignoreresponse, errorresponse, force_buffer, ignoredisplay

    def process_update_exclude(self):
        exclude = re.sub(', ', ',', self._value).split(",")
        self.logger.debug(
            "Initializing {}: Special Settings: Exclude updates by {}".format(self._name, exclude))
        return exclude
