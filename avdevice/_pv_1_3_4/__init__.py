#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2016 <Onkel Andy>					  <onkelandy@hotmail.com>
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
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.	 See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

import logging
from lib.model.smartplugin import SmartPlugin
from itertools import groupby
import io
import time
import re
import errno
#import serial
#import socket
import sys
from .AVDeviceInit import Init

VERBOSE1 = logging.DEBUG - 1
VERBOSE2 = logging.DEBUG - 2
logging.addLevelName(logging.DEBUG - 1, 'VERBOSE1')
logging.addLevelName(logging.DEBUG - 2, 'VERBOSE2')


class AVDevice(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.3.5"

    def __init__(self, smarthome,
                 model='',
                 ignoreresponse='RGB,RGC,RGD,GBH,GHH,VTA,AUA,AUB',
                 errorresponse='E02,E04,E06',
                 forcebuffer='GEH01020, GEH04022, GEH05024',
                 inputignoredisplay='',
                 dependson_item='',
                 dependson_value=True,
                 rs232_port='',
                 rs232_baudrate=9600,
                 rs232_timeout=0.1,
                 tcp_ip='',
                 tcp_port=23,
                 tcp_timeout=1,
                 resetonerror=False,
                 depend0_power0=False,
                 depend0_volume0=False,
                 sendretries=10,
                 resendwait=1.0,
                 reconnectretries=13,
                 secondstokeep=50,
                 responsebuffer='5',
                 autoreconnect=False,
                 update_exclude=''):
        self.logger = logging.getLogger(__name__)
        self._sh = smarthome
        self.alive = False
        self._name = self.get_instance_name()
        self._serialwrapper = None
        self._serial = None
        self._tcpsocket = None
        self._functions = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        self._items = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        self._query_zonecommands = {'zone0': [], 'zone1': [], 'zone2': [], 'zone3': [], 'zone4': []}
        self._items_speakers = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        self._send_commands = []
        self._init_commands = {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}
        self._keep_commands = {}
        self._specialparse = {}
        self._query_commands = []
        self._power_commands = []
        self._expected_response = []
        self._response_commands = {}
        self._response_wildcards = {'wildcard': {}, 'original': {}}
        self._number_of_zones = 0
        self._trigger_reconnect = True
        self._reconnect_counter = 0
        self._resend_counter = 0
        self._resend_on_empty_counter = 0
        self._clearbuffer = False
        self._sendingcommand = 'done'
        self._special_commands = {}
        self._is_connected = []
        self._parsinginput = []
        self._dependencies = {'Slave_function': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}, \
                            'Slave_item': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}, \
                            'Master_function': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}, \
                            'Master_item': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}}

        try:
            self._model = self.get_parameter_value('model')
            self._resend_wait = float(self.get_parameter_value('resendwait'))
            self._secondstokeep = int(self.get_parameter_value('secondstokeep'))
            self._auto_reconnect = self.get_parameter_value('autoreconnect')
            self._resend_retries = int(self.get_parameter_value('sendretries'))
            self._reconnect_retries = int(self.get_parameter_value('reconnectretries'))
            ignoreresponse = self.get_parameter_value('ignoreresponse')
            errorresponse = self.get_parameter_value('errorresponse')
            forcebuffer = self.get_parameter_value('forcebuffer')
            inputignoredisplay = self.get_parameter_value('inputignoredisplay')
            resetonerror = self.get_parameter_value('resetonerror')
            responsebuffer = self.get_parameter_value('responsebuffer')
            depend0_power0 = self.get_parameter_value('depend0_power0')
            depend0_volume0 = self.get_parameter_value('depend0_volume0')
            dependson_item = self.get_parameter_value('dependson_item')
            dependson_value = self.get_parameter_value('dependson_value')
            tcp_ip = self.get_parameter_value('tcp_ip')
            tcp_port = self.get_parameter_value('tcp_port')
            tcp_timeout = self.get_parameter_value('tcp_timeout')
            rs232_port = self.get_parameter_value('rs232_port')
            rs232_baudrate = self.get_parameter_value('rs232_baudrate')
            rs232_timeout = self.get_parameter_value('rs232_timeout')
            update_exclude = self.get_parameter_value('update_exclude')
        except Exception:
            self._model = model
            self._resend_wait = float(resendwait)
            self._secondstokeep = int(secondstokeep)
            self._auto_reconnect = autoreconnect
            self._resend_retries = int(sendretries)
            self._reconnect_retries = int(reconnectretries)
        # Initializing all variables
        self.logger.debug("Initializing {}: Resendwait: {}. Seconds to keep: {}.".format(self._name, self._resend_wait, self._secondstokeep))
        self.init = Init(self._sh, self._name, self._model, self._items)
        self._rs232, self._baud, self._timeout = self.init._process_variables([rs232_port, rs232_baudrate, rs232_timeout], 'rs232')
        self._tcp, self._port, self._tcp_timeout = self.init._process_variables([tcp_ip, tcp_port, tcp_timeout], 'tcp')
        self._dependson, self._dependson_value, self._depend0_power0, self._depend0_volume0 = self.init._process_variables([dependson_item, dependson_value, depend0_power0, depend0_volume0], 'dependson')

        self._response_buffer = self.init._process_variables(responsebuffer, 'responsebuffer')
        self._reset_onerror = self.init._process_variables(resetonerror, 'resetonerror')
        self._ignore_response, self._error_response, self._force_buffer, self._ignoredisplay = self.init._process_variables([ignoreresponse, errorresponse, forcebuffer, inputignoredisplay], 'responses')
        self.logger.debug("Initializing {}: Special Settings: Ignoring responses {}.".format(self._name, self._ignore_response))
        self.logger.debug("Initializing {}: Special Settings: Error responses {}.".format(self._name, self._error_response))
        self.logger.debug("Initializing {}: Special Settings: Force buffer {}.".format(self._name, self._force_buffer))
        self.logger.debug("Initializing {}: Special Settings: Ignore Display {}".format(self._name, self._ignoredisplay))
        self._update_exclude = self.init._process_variables(update_exclude, 'update_exclude')

    # Non-blocking wait function
    def _wait(self, time_lapse):
        time_start = time.time()
        time_end = (time_start + time_lapse)

        while time_end > time.time():
            time.sleep(0.001)

    # Resetting items when send command failed
    def _resetitem(self, founditem):
        try:
            resetting = None
            if founditem == '':
                try:
                    founditem = self._sendingcommand.split(';')[1]
                except Exception:
                    founditem = self._send_commands[0].split(';')[1]
            try:
                founditem = self._sh.return_item(founditem)
            except Exception as err:
                self.logger.debug("Resetting {}: {} is no valid item. Message: {}.".format(self._name, founditem, err))
            self.logger.log(VERBOSE2, "Resetting {}: Item: {}.".format(self._name, founditem.id()))
            speakerfound = False
            for search in self._special_commands['Speakers']['Item']:
                self.logger.log(VERBOSE2, "Resetting {}: Search {} in special {} with {}.".format(self._name, founditem.id(), self._special_commands['Speakers']['Item'], search))
                if isinstance(search, list):
                    for testing in search:
                        self.logger.log(VERBOSE2, "Resetting {}: Search {} in special {} with list {}.".format(self._name, founditem.id(), self._special_commands['Speakers']['Item'], testing))
                        if founditem.id() == testing.id():
                            speakerfound = True
                elif founditem.id() == search.id():
                    speakerfound = True
                    self.logger.log(VERBOSE2, "Resetting {}: Search {} in special {} with {}.".format(self._name, founditem.id(), self._special_commands['Speakers']['Item'], search.id()))

            for zone in self._items.keys():
                for itemlist in self._items[zone].keys():
                    if isinstance(self._items[zone][itemlist]['Item'], list):
                        for search in self._items[zone][itemlist]['Item']:
                            self.logger.log(VERBOSE2, "Resetting {}: Search {} in {} with {}.".format(self._name, founditem.id(), self._items[zone][itemlist]['Item'], search))
                            try:
                                search = search.id()
                            except Exception:
                                pass
                            if founditem.id() == search:
                                previousvalue = self._items[zone][itemlist]['Value']
                                founditem(previousvalue, 'AVDevice', self._tcp)
                                self.logger.info("Resetting {}: Item {} to {}".format(
                                    self._name, founditem, previousvalue))
                                resetting = founditem
                                break
                    else:
                        try:
                            compare = self._items[zone][itemlist].get('Item').id()
                        except Exception:
                            compare = self._items[zone][itemlist].get('Item')
                        self.logger.log(VERBOSE2, "Resetting {}: Search {} in {}.".format(self._name, founditem.id(), compare))
                        if founditem.id() == compare:
                            previousvalue = self._items[zone][itemlist]['Value']
                            founditem(previousvalue, 'AVDevice', self._tcp)
                            self.logger.info("Resetting {}: Item {} to {}".format(
                                self._name, founditem, previousvalue))
                            resetting = founditem
                            break
                for itemlist in self._items_speakers[zone].keys():
                    for search in self._items_speakers[zone][itemlist]['Item']:
                        self.logger.log(VERBOSE2, "Resetting {}: Search {} in speakers {} with {}.".format(self._name, founditem.id(), self._items_speakers[zone][itemlist]['Item'], search.id()))
                        if founditem.id() == search.id():
                            speakerfound = True
                if speakerfound == True:
                    for itemlist in self._items_speakers[zone].keys():
                        for search in self._items_speakers[zone][itemlist]['Item']:
                            previousvalue = self._items_speakers[zone][itemlist]['Value']
                            self.logger.info("Resetting {}: Resetting additional speaker item {} to value {}".format(
                                self._name, search.id(), previousvalue))
                            search(previousvalue, 'AVDevice', self._tcp)
                    resetting = founditem
                    # return resetting
                if resetting is not None:
                    break

            self._trigger_reconnect = False
            self.logger.log(VERBOSE2, "Resetting {}: Finished. Returning value: {}.".format(self._name, resetting))
            return resetting
        except Exception as err:
            self.logger.error("Resetting {}: Problem resetting Item. Error: {}".format(self._name, err))
            return 'ERROR'

    def _translate(self, code, dictentry, caller):
        origcaller = caller
        try:
            code = code.lower()
        except Exception:
            pass
        if caller == 'writedict':
            caller = 'parse'
        try:
            result = self._specialparse[dictentry][caller].get(code)
        except Exception:
            result = None
        self.logger.log(VERBOSE2, "Translating {}: Called by: {}. Dictentry: {}, Code: {}, Result: {}.".format(self._name, origcaller, dictentry, code, result))
        return result

    # Resetting items if no connection available
    def _resetondisconnect(self, caller):
        if self._depend0_volume0 is True or self._depend0_power0 is True:
            self.logger.debug('Resetting {}: Starting to reset on disconnect. Called by {}'.format(self._name, caller))
            try:
                for zone in self._items:
                    if 'power' in self._items[zone].keys() and self._depend0_power0 is True:
                        self._items[zone]['power']['Value'] = 0
                        self._items[zone]['power']['Item'](0, 'AVDevice', self._tcp)
                        self.logger.log(VERBOSE1, 'Resetting {}: Power to 0 for item {}'.format(self._name, self._items[zone]['power']['Item']))
                    if 'speakers' in self._items[zone].keys() and self._depend0_power0 is True:
                        self._items[zone]['speakers']['Value'] = 0
                        for itemlist in self._items_speakers[zone].keys():
                            self._items_speakers[zone][itemlist]['Value'] = 0
                            for singleitem in self._items_speakers[zone][itemlist]['Item']:
                                singleitem(0, 'AVDevice', self._tcp)
                                self.logger.log(VERBOSE1, 'Resetting {}: Speakers to 0 for item {}'.format(self._name, singleitem))
                        for singleitem in self._items[zone]['speakers']['Item']:
                            singleitem(0, 'AVDevice', self._tcp)
                            self.logger.log(VERBOSE1, 'Resetting {}: Speakers to 0 for item {}'.format(self._name, singleitem))
                    if 'volume' in self._items[zone].keys() and self._depend0_volume0 is True:
                        self._items[zone]['volume']['Value'] = 0
                        self._items[zone]['volume']['Item'](0, 'AVDevice', self._tcp)
                        self.logger.log(VERBOSE1, 'Resetting {}: Volume to 0 for item {}'.format(self._name, self._items[zone]['volume']['Item']))
                self.logger.debug('Resetting {}: Done.'.format(self._name))
            except Exception as err:
                self.logger.warning('Resetting {}: Problem resetting Item. Error: {}'.format(self._name, err))
        else:
            self.logger.log(VERBOSE1, 'Resetting {}: Not resetting on disconnect because this feature is disabled in the plugin config.'.format(self._name))

    # Converting received values to bool, string or int to compare the responses with the expected response
    def _convertvalue(self, receivedvalue, expectedtype, invert, valuelength, command):
        command = command[0] if isinstance(command, list) else command
        self.logger.debug("Converting Values {}: Received Value is: {} with expected type {}. Invert: {}. Length: {}. Command: {}".format(self._name, receivedvalue, expectedtype, invert, valuelength, command))
        if command in self._special_commands['Display']['Command']:
            try:
                content = receivedvalue[2:][:28]
                tempvalue = "".join(list(map(lambda i: chr(int(content[2 * i : ][ : 2], 0x10)), range(14)))).strip()
                receivedvalue = re.sub(r'^[^A-Z0-9]*', '', tempvalue)
                self.logger.debug("Converting Values {}: Display Output {}".format(self._name, receivedvalue))
                return receivedvalue
            except Exception as err:
                self.logger.log(VERBOSE1, "Converting Values {}: No display info for Pioneer found. Message: {}".format(self._name, err))
                try:
                    line = receivedvalue[3:4]
                    if line.isdigit():
                        line = int(line)
                        if line == 0:
                            receivedvalue = receivedvalue[4:]
                        elif line == 1:
                            receivedvalue = receivedvalue[5:]
                        else:
                            receivedvalue = receivedvalue[6:]
                        if receivedvalue:
                            # Now playing
                            if line == 1:
                                self.logger.info("Converting Values {}: Now playing {}".format(self._name, receivedvalue))
                                self._special_commands['Nowplaying']['Item'](receivedvalue, 'AVDevice', self._tcp)
                            # Internet radio Station name
                            elif line == 2 and self._special_commands['Input']['Item']() == 'IRADIO':
                                self.logger.info("Converting Values {}: Internet radio station {}".format(self._name, receivedvalue))
                                self._items['zone0']['station'](receivedvalue, 'AVDevice', self._tcp)
                    else:
                        self.logger.debug("Converting Values {}: No digit in data position 4 for Denon: {}".format(self._name, receivedvalue))
                except Exception as err:
                    self.logger.debug("Converting Values {}: Unknown display info for Denon received. Message: {}".format(self._name, err))
        if 'bool' in expectedtype:
            try:
                if invert is True:
                    if (int(receivedvalue) == 1 and len(str(receivedvalue)) <= 1) and valuelength == 1:
                        receivedvalue = False
                    elif (int(receivedvalue) == 0 and len(str(receivedvalue)) <= 1) and valuelength == 1:
                        receivedvalue = True
                    self.logger.log(VERBOSE1, "Converting Values {}: Receivedvalue {} reversed".format(self._name, receivedvalue))
                else:
                    if (int(receivedvalue) == 1 and len(str(receivedvalue)) <= 1) and valuelength == 1:
                        receivedvalue = True
                        self.logger.log(VERBOSE1, "Converting Values {}: Receivedvalue {} converted to bool.".format(self._name, receivedvalue))
                    elif (int(receivedvalue) == 0 and len(str(receivedvalue)) <= 1) and valuelength == 1:
                        receivedvalue = False
                        self.logger.log(VERBOSE1, "Converting Values {}: Receivedvalue {} converted to bool.".format(self._name, receivedvalue))
            except Exception as err:
                self.logger.log(VERBOSE2, "Converting Values {}: Receivedvalue {} not converted further. Message: {}.".format(self._name, receivedvalue, err))
                pass
            try:
                if int(receivedvalue) == 1 and len(str(receivedvalue)) <= 1 and valuelength == 1:
                    receivedvalue = True
                elif int(receivedvalue) == 0 and len(str(receivedvalue)) <= 1 and valuelength == 1:
                    receivedvalue = False
            except Exception:
                pass
        if 'int' in expectedtype:
            try:
                if str(receivedvalue).lower() == 'on' and ('bool' in expectedtype or valuelength == 1):
                    receivedvalue = 1
                elif (str(receivedvalue).lower() == 'off' or str(receivedvalue).lower() == 'standby') and ('bool' in expectedtype or valuelength == 1):
                    receivedvalue = 0
            except Exception:
                pass
            try:
                receivedvalue = int(receivedvalue)
            except Exception:
                pass
        elif not (('bool' in expectedtype and 'int' in expectedtype) or ('str' in expectedtype and 'bool' in expectedtype)):
            try:
                if (str(receivedvalue).lower() == 'on' and (valuelength == 30 or valuelength == 2)) or (str(receivedvalue).lower() == 'open' and (valuelength == 30 or valuelength == 4)):
                    receivedvalue = True
                elif (str(receivedvalue).lower() == 'off' and (valuelength == 30 or valuelength == 3)) or (str(receivedvalue).lower() == 'standby' and (valuelength == 30 or valuelength == 7)) or (str(receivedvalue).lower() == 'close' and (valuelength == 30 or valuelength == 5)) or (str(receivedvalue).lower() == 'clos' and (valuelength == 30 or valuelength == 4)):
                    receivedvalue = False
            except Exception:
                pass
        try:
            receivedvalue = eval(receivedvalue.lstrip('0'))
        except Exception:
            try:
                receivedvalue = eval(receivedvalue)
            except Exception:
                pass
        if not expectedtype == 'str':
            try:
                receivedvalue = float(receivedvalue) if '.' in receivedvalue else int(receivedvalue)
            except Exception:
                pass
        self.logger.debug("Converting Values {}: Received Value is now: {} with type {}.".format(self._name, receivedvalue, type(receivedvalue)))
        return receivedvalue

    # Store actual value to a temporary dict for resetting purposes
    def _write_itemsdict(self, data, found):
        try:
            self.logger.debug("Storing Values {}: Starting to store value for data {} in dictionary. Found expected responses: {}.".format(self._name, data, found))
            sorted_response_commands = sorted(self._response_commands, key=len, reverse=True)
            for i in range(0, len(sorted_response_commands)):
                 try:
                     sorted_response_commands[i] = self._response_wildcards['original'][sorted_response_commands[i]]
                 except Exception as err:
                     sorted_response_commands[i] = None
                     self.logger.log(VERBOSE2, "Storing Values {}: Can not find wildcard equivalent for: {}".format(self._name, err))
            for entry in found:
                if entry in sorted_response_commands:
                    sorted_response_commands.insert(0,entry)
            sorted_response_commands = [value for value in sorted_response_commands if value != None]
            self.logger.log(VERBOSE2, "Storing Values {}: Sorted wildcarded response commands {}.".format(self._name, sorted_response_commands))
            updated = 0
            for command in sorted_response_commands:
                self.logger.log(VERBOSE2, "Storing Values {}: Comparing command {}.".format(self._name, command))
                if data == command:
                    self.logger.debug("Storing Values {}: Response is identical to expected response. Skipping Storing: {}".format(self._name, data))
                    break
                for entry in self._response_commands[self._response_wildcards['wildcard'][command]]:
                    self.logger.log(VERBOSE2, "Storing Values {}: Comparing entry {}.".format(self._name, entry))
                    if entry[2] == 0:
                        commandstart = entry[0]
                        commandend = entry[1]
                    else: # TOTEST
                        commandstart = 0
                        commandend = entry[2]

                    valuestart = entry[2]
                    valueend = entry[2] + entry[0]
                    function = entry[4]
                    expectedtype = entry[7]

                    # replace ? from expected response with actual value from response
                    #if len(data[commandstart:commandend]) == len(command):
                    #	command = self._processing_wildcard(data[commandstart:commandend], command)

                    if data[commandstart:commandend] == command:
                        zone = entry[5]
                        value = data[valuestart:valueend]
                        receivedvalue = data[valuestart:valueend]
                        invert = True if entry[6].lower() in ['1', 'true', 'yes', 'on'] else False
                        if not value == '':
                            self.logger.log(VERBOSE2, "Storing Values {}: Converting {} with expected type {}, Invert {}, Length {}, Command {}".format(
                                self._name, value, expectedtype, invert, entry[0], command))
                            receivedvalue = self._convertvalue(value, expectedtype, invert, entry[0], command)
                        try:
                            if isinstance(receivedvalue, eval(expectedtype)):
                                sametype = True
                            else:
                                sametype = False
                        except Exception as err:
                            self.logger.log(VERBOSE2, "Storing Values {}: Cannot compare {} with {}. Message: {}".format(
                                self._name, receivedvalue, expectedtype, err))
                            if receivedvalue == '' and expectedtype == 'empty':
                                sametype = True
                            else:
                                sametype = False
                        if sametype == True:
                            self._items[zone][function]['Value'] = self._translate(value, entry[9], 'writedict')
                            self.logger.debug("Storing Values {}: Found writeable dict key: {}. Zone: {}. Value {} with type {}. Function: {}.".format(self._name, command, zone, receivedvalue, expectedtype, function))
                            updated = 1
                            break
                        else:
                            self.logger.debug("Storing Values {}: Found writeable dict key: {} with type {}, but received value {} is type {}. Not writing value!".format(self._name, command, expectedtype, receivedvalue, type(receivedvalue)))

                        if updated == 1:
                            self.logger.log(VERBOSE1, "Storing Values {}: Stored all relevant items from function {}. step 1".format(self._name, function))
                            break
                    if updated == 1:
                        self.logger.log(VERBOSE1, "Storing Values {}: Stored all relevant items from function {}. step 2".format(self._name, function))
                        break
                if updated == 1:
                    self.logger.log(VERBOSE1, "Storing Values {}: Stored all relevant items from function {}. step 3".format(self._name, function))
                    break
        except Exception as err:
            self.logger.error("Storing Values {}: Problems creating items dictionary. Error: {}".format(self._name, err))
        finally:
            self.logger.log(VERBOSE1, "Storing Values {}: Finished. Send Commands: {}. Returning: {}, {}, {}".format(self._name, self._send_commands, self._items[zone][function], receivedvalue, expectedtype))
            if updated == 1:
                return self._items[zone][function], receivedvalue, expectedtype
            else:
                return 'empty', 'empty', 'empty'

    def _parse_depend_item(self, item, info, zone):
        for dependzone in range(0, 5):
            dependzone = 'zone{}'.format(dependzone)
            if self.has_iattr(item.conf, 'avdevice_{}_depend'.format(dependzone)) or (self.has_iattr(item.conf, 'avdevice_depend') and dependzone == 'zone0'):
                if self.has_iattr(item.conf, 'avdevice_{}_depend'.format(dependzone)):
                    liste = self.get_iattr_value(item.conf, 'avdevice_{}_depend'.format(dependzone))
                else:
                    liste = self.get_iattr_value(item.conf, 'avdevice_depend')
                if not isinstance(liste, list):
                    liste = [liste]
                for entry in liste:
                    comparing = ''
                    if entry.find('>=') >= 0:
                        splitting = entry.split('>=')
                        comparing = '>='
                    elif entry.find('<=') >= 0:
                        splitting = entry.split('<=')
                        comparing = '<='
                    elif entry.find('==') >= 0:
                        splitting = entry.split('==')
                        comparing = '=='
                    elif entry.find('=') >= 0:
                        splitting = entry.split('=')
                        comparing = '=='
                    elif entry.find('>') >= 0:
                        splitting = entry.split('>')
                        comparing = '>'
                    elif entry.find('<') >= 0:
                        splitting = entry.split('<')
                        comparing = '<'
                    elif entry.find('!=') >= 0:
                        splitting = entry.split('!=')
                        comparing = '!='
                    elif entry.find('<>') >= 0:
                        splitting = entry.split('<>')
                        comparing = '!='
                    elif entry.find(',') >= 0:
                        splitting = [entry.split(',')[0], '{}, {}'.format(True, entry.split(',')[1])]
                        comparing = '=='
                    else:
                        splitting = [entry, True]
                        comparing = '=='
                    try:
                        depend = splitting[0].strip().lower()
                    except Exception:
                        depend = None
                    try:
                        dependvalue = splitting[1].split(',')[0].strip()
                        if re.sub('[ ]', '', str(dependvalue)).lower() in ['yes', 'true', 'on']:
                            dependvalue = True
                        elif re.sub('[ ]', '', str(dependvalue)).lower() in ['no', 'false', 'off']:
                            dependvalue = False
                    except Exception:
                        dependvalue = None if depend == None else True
                    try:
                        dependgroup = splitting[1].split(',')[1].strip().lower()
                    except Exception:
                        dependgroup = 'a'
                    try:
                        dependvalue = eval(dependvalue)
                    except Exception:
                        pass
                    if (splitting is None):
                        return None
                    else:
                        try:
                            self._items[zone][info]['Master'].append({'Zone': dependzone, 'Item': depend, 'Dependvalue': dependvalue, 'Compare': comparing, 'Group': dependgroup})
                            self.logger.log(VERBOSE1, "Initializing {}: Adding dependency for {}.".format(self._name, info))
                        except Exception:
                            self._items[zone][info].update({'Master': [{'Zone': dependzone, 'Item': depend, 'Dependvalue': dependvalue, 'Compare': comparing, 'Group': dependgroup}]})
                            self.logger.log(VERBOSE1, "Initializing {}: Creating dependency for {}.".format(self._name, info))

    # Finding relevant items for the plugin based on the avdevice keyword
    def parse_item(self, item):
        if self._tcp is not None or self._rs232 is not None:
            keywords = ['avdevice', 'avdevice_zone0', 'avdevice_init', 'avdevice_speakers', 'avdevice_zone1', 'avdevice_zone1_init', 'avdevice_zone1_speakers', 'avdevice_zone2', 'avdevice_zone2_init', 'avdevice_zone2_speakers', 'avdevice_zone3', 'avdevice_zone3_init', 'avdevice_zone3_speakers', 'avdevice_zone4', 'avdevice_zone4_init', 'avdevice_zone4_speakers']
            for keyword in keywords:
                try:
                    zone = keyword.split("_")[1]
                except Exception:
                    zone = 'zone0'
                if zone == 'init' or zone == 'speakers' or zone == 'depend':
                    zone = 'zone0'
                if str(item) == self._dependson:
                    self._items[zone]['dependson'] = {'Item': self._dependson, 'Value': self._dependson_value}
                    self._dependencies['General'] = {'Item': self._dependson, 'Value': self._dependson_value}
                    self.logger.debug("Initializing {}: Dependson Item found: {}".format(self._name, item, self._dependson))
                    return self.update_item
                elif self.has_iattr(item.conf, keyword):
                    info = self.get_iattr_value(item.conf, keyword)
                    if info is not None:
                        if '_init' in keyword:
                            self._init_commands[zone][info] = {'Inititem': item, 'Item': item, 'Value': item()}
                            return self.update_item
                        elif '_speakers' in keyword:
                            self._items_speakers[zone][info] = {'Item': item, 'Value': item()}
                            return self.update_item
                        else:
                            self._items[zone][info] = {'Item': item, 'Value': item()}
                            self._parse_depend_item(item, info, zone)
                            return self.update_item
            return None

    def _processing_wildcard(self, data, command):
        if command.find('?') >= 1:
            wildcard_replace = []
            wildcard = []
            command = command.split('*')[0]
            unprocessed = command
            command = realcommand = command.replace('*{str}', '*')
            command = realcommand = command.replace('?{str}', '?')
            for i in range(9,0,-1):
                 command = command.replace('?' * i, '?')
            splitcommand = command.split('?')
            splitreal = unprocessed.split('*')[0].split('?')[1:]
            if splitcommand[len(splitcommand)-1] == '':
                splitcommand = splitcommand[:-1]
                splitreal = splitreal[:-1]
            self.logger.log(VERBOSE2, "Processing Wildcard {}: Command: {} (original: {}), Splitcommand: {}. Splitreal: {}. Data: {}".format(self._name, command, unprocessed, splitcommand, splitreal, data))
            for i in range(0, len(splitcommand)):
                try:
                    data = data.split(splitcommand[i],1)[1]
                except Exception:
                    break
                try:
                    toreplace = data[0:data.find(splitcommand[i+1])] if data.find(splitcommand[i+1]) >= 0 else data
                    wildcard_replace.append(toreplace)
                except:
                    wildcard_replace.append(data)
                try:
                    if i == 0 and not splitcommand[i] == '':
                        start = realcommand.find(splitcommand[i])+len(splitcommand[i])
                    else:
                        start = 0
                    try:
                        end = start+realcommand[start:].find(splitcommand[i+1])
                        newstart = end+len(splitcommand[i+1])
                    except:
                        end = None
                        newstart = 0
                    wildcard.append(realcommand[start:end])
                    realcommand = realcommand[newstart:]
                except Exception as err:
                    pass
            if wildcard_replace:
                self.logger.log(VERBOSE2, "Processing Wildcard {}: Wildcard replace: {}, Wildcard: {}.".format(self._name, wildcard_replace, wildcard))
                newstring = ''
                for i in range(0, len(splitcommand)):
                    try:
                        self.logger.log(VERBOSE2, "Processing Wildcard {}: replace {}, wildcard {}, splitreal {}".format(self._name, wildcard_replace[i], wildcard[i], splitreal[i]))
                        replace = True if ((len(wildcard_replace[i]) == len(wildcard[i]) or '{str}' in splitreal[i]) and not wildcard[i] == '') else False
                    except Exception as err:
                        replace = False
                    try:
                        if replace is True:
                            newstring += splitcommand[i]+wildcard_replace[i]
                            self.logger.log(VERBOSE2, "Processing Wildcard {}: Replace {} by {}.".format(self._name, wildcard[i], wildcard_replace[i]))
                        else:
                            try:
                                newstring += splitcommand[i]+wildcard[i]
                            except Exception:
                                newstring += splitcommand[i]+wildcard_replace[i]
                    except Exception as err:
                        newstring = unprocessed
                        self.logger.log(VERBOSE2, "Processing Wildcard {}: Problem {}.".format(self._name, err))
                        break
            else:
                newstring = unprocessed.split('*')[0]
            self.logger.log(VERBOSE2, "Processing Wildcard {}: Command to compare: {}.".format(self._name, newstring))
        else:
            newstring = command.split('*')[0]
        return newstring

    def _create_expectedresponse(self, buffer):
        expectedresponse = []
        try:
            for resp in self._send_commands:
                if resp.split(',', 2)[2].find('|') >= 0:
                    splitresponse = resp.split(';')[0].split('|')
                else:
                    splitresponse = [resp]
                splitresponse[0] = splitresponse[0].split(',', 2)[2]
                for i in range(0, len(splitresponse)):
                    splitresponse[i] = splitresponse[i].split(',')[0]
                    if not buffer == '':
                        splitresponse[i] = self._processing_wildcard(buffer.split("\r\n")[0], splitresponse[i])
                    self.logger.log(VERBOSE2, "Processing Response {}: Splitresponse after wildcard {}: {}.".format(self._name, i, splitresponse[i]))
                wildcardresponse = []
                for wild in splitresponse:
                    if not '?' in wild:
                        wildcardresponse.append(wild)
                splitresponse = '|'.join(wildcardresponse)
                if not splitresponse == '':
                    expectedresponse.append(splitresponse)
            # self._expected_response = expectedresponse
            #self.logger.debug("Processing Response {}: Expected response: {}.".format(self._name, expectedresponse))
        except Exception as err:
            self.logger.error("Processing Response {}: Problems creating expected response list. Error: {}".format(self._name, err))
        return expectedresponse

    # Processing the response from the AV device, dealing with buffers, etc.
    def _processing_response(self, socket):
        try:
            buffer = ''
            bufferlist = []
            tidy = lambda c: re.sub(
                r'(^\s*[\r\n]+|^\s*\Z)|(\s*\Z|\s*[\r\n]+)',
                lambda m: '\r\n' if m.lastindex == 2 else '',
                c)
            try:
                '''
                if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
                    if socket == self._serial:
                        buffer = socket.readline().decode('utf-8')
                    else:
                        buffer = socket.read()
                if self._tcp and socket == self._tcpsocket:
                    buffer = socket.recv(4096).decode('utf-8')
                '''
                buffering = False
                buffer = tidy(buffer)
                if buffer == '':
                    buffer = 'MV90\r\nMVMAX 98\r\n' # TOTEST
                if not buffer == '' and (self._response_buffer is not False or self._response_buffer is not 0):
                    buffering = True
                elif buffer == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
                    self._resend_on_empty_counter += 1
                    self._wait(0.1)
                    sending = self._send(self._sendingcommand, 'responseprocess')
                    self.logger.log(VERBOSE1, "Processing Response {}: Received empty response while sending command: {}. Return from send is {}. Retry: {}".format(self._name, self._sendingcommand, sending, self._resend_counter))
                    if self._resend_on_empty_counter >= 2:
                        self.logger.debug("Processing Response {}: Stop resending command {} and sending back error.".format(self._name, self._sendingcommand))
                        self._resend_on_empty_counter = 0
                        yield 'ERROR'

            except Exception as err:
                buffering = False
                self._expected_response = self._create_expectedresponse(buffer)
                try:
                    if not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup' and not (self._sendingcommand.split(',')[2] == '' or self._sendingcommand.split(',')[2] == ' ' or self._sendingcommand.split(',')[2] == 'none'):
                        buffering = True
                        self.logger.log(VERBOSE1, "Processing Response {}: Error reading.. Error: {}. Sending Command: {}. RS232: {}, Host: {}, Socket: {}".format(self._name, err, self._sendingcommand, self._rs232, self._tcp, socket))
                        if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
                            self.logger.log(VERBOSE1, "Processing Response {}: Problems buffering RS232 response. Error: {}. Increasing timeout temporarily.".format(self._name, err))
                            self._wait(1)
                            socket.timeout = 2
                            sending = self._send(self._sendingcommand, 'getresponse')
                            if socket == self._serial:
                                buffer = socket.readline().decode('utf-8')
                            else:
                                buffer = socket.read()
                            socket.timeout = 0.3
                            self.logger.log(VERBOSE1, "Processing Response {}: Error reading.. Return from send is {}. Error: {}".format(self._name, sending, err))
                            yield 'ERROR'
                        if self._tcp and socket == self._tcpsocket:
                            self.logger.log(VERBOSE1, "Processing Response {}: Problems buffering TCP response. Error: {}. Increasing timeout temporarily.".format(self._name, err))
                            self._wait(1)
                            socket.settimeout(self._tcp_timeout * 3)
                            sending = self._send(self._sendingcommand, 'getresponse')
                            self.logger.debug("Processing Response {}: Error reading.. Return from send is {}. Error: {}".format(self._name, sending, err))
                            buffer = socket.recv(4096).decode('utf-8')
                            socket.settimeout(self._tcp_timeout)
                            yield 'ERROR'
                except Exception as err:
                    buffering = False
                    self.logger.error("Processing Response {}: Connection error. Error: {} Resend Counter: {}. Resend Max: {}".format(
                        self._name, err, self._resend_counter, self._resend_retries))
                    yield 'ERROR'

            while buffering:
                if '\r\n' in buffer:
                    self.logger.log(VERBOSE2, "Processing Response {}: Buffer before removing duplicates: {}".format(self._name, re.sub('[\r\n]', ' --- ', buffer)))
                    if self._clearbuffer is True:
                        buffer = ''
                        self.logger.log(VERBOSE1, "Processing Response {}: Clearing buffer because clearbuffer set to true. It is now: {}".format(self._name, re.sub('[\r\n]', ' --- ', buffer)))
                        self._clearbuffer = False
                    # remove duplicates
                    # buffer = '\r\n'.join(sorted(set(buffer.split('\r\n')), key=buffer.split('\r\n').index))
                    buffer_cleaned = []
                    bufferlist = buffer.split("\r\n")
                    bufferlist = bufferlist[:-1]
                    for buff in bufferlist:
                        if buff not in buffer_cleaned or buff in self._force_buffer:
                            buffer.cleaned.append(buff)
                    bufferlist = buffer_cleaned
                    buffer = "\r\n".join(bufferlist)
                    if not self._send_commands == []:
                        self._expected_response = self._create_expectedresponse(buffer)
                        expectedsplit = []
                        for entry in self._expected_response:
                            splitting = entry.split('|')
                            for splitted in splitting:
                                expectedsplit.append(splitted)
                        sortedbuffer = []
                        for e in expectedsplit:
                            for entry in bufferlist:
                                if entry.startswith(e):
                                    try:
                                        realresponse = self._response_wildcards['original'][e]
                                    except Exception as err:
                                        realresponse = e
                                    for resp in self._response_commands[realresponse]:
                                        if len(entry) == resp[1]:
                                            self.logger.log(VERBOSE2, "Processing Response {}: length is same. adding: {}.".format(self._name, entry))
                                            sortedbuffer.append(entry)
                        self.logger.log(VERBOSE2, "Processing Response {}: expected response: {}, bufferlist {}. Sortedbuffer: {}".format(self._name, expectedsplit, bufferlist, sortedbuffer))
                        bufferlist = [x for x in bufferlist if x not in sortedbuffer]
                        buffer = "\r\n".join(sortedbuffer+bufferlist)
                        buffer = "{}\r\n".format(buffer)
                        self.logger.log(VERBOSE2, "Processing Response {}: Buffer after sorting: {}.".format(self._name, re.sub('[\r\n]', ' --- ', buffer)))
                    (line, buffer) = buffer.split("\r\n", 1)
                    self.logger.log(VERBOSE2, "Processing Response {}: Buffer: {} Line: {}. Response buffer: {}, force buffer: {}.".format(self._name, re.sub('\r\n', ' --- ', buffer), re.sub('\r\n', '. ', line), self._response_buffer, self._force_buffer))
                    if not ('' in self._force_buffer and len(self._force_buffer) == 1) and (self._response_buffer is False or self._response_buffer == 0):
                        if not re.sub('[ ]', '', buffer) == '' and not re.sub('[ ]', '', line) == '':
                            bufferlist = []
                            for buf in self._force_buffer:
                                try:
                                    if buf in buffer and not buf.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
                                        start = buffer.index(buf)
                                        self.logger.log(VERBOSE2, "Processing Response {}: Testing forcebuffer {}. Bufferlist: {}. Start: {}".format(self._name, buf, bufferlist, start))
                                        if not buffer.find('\r\n', start) == -1:
                                            end = buffer.index('\r\n', start)
                                            if not buffer[start:end] in bufferlist and not buffer[start:end] in line:
                                                bufferlist.append(buffer[start:end])
                                        else:
                                            if not buffer[start:] in bufferlist and not buffer[start:] in line:
                                                bufferlist.append(buffer[start:])
                                        self.logger.debug("Processing Response {}: Forcebuffer {} FOUND in buffer. Bufferlist: {}. Buffer: {}".format(
                                            self._name, buf, bufferlist, re.sub('[\r\n]', ' --- ', buffer)))
                                except Exception as err:
                                    self.logger.warning("Processing Response {}: Problems while buffering. Error: {}".format(self._name, err))
                            if bufferlist:
                                buffer = '\r\n'.join(bufferlist)
                                buffer = tidy(buffer)
                            else:
                                self.logger.log(VERBOSE2, "Processing Response {}: No forced buffer found.".format(self._name))

                    if '{}\r\n'.format(line) == buffer:
                        buffer = ''
                        self.logger.log(VERBOSE1, "Processing Response {}: Clearing buffer because it's the same as Line: {}".format(self._name, line))

                    line = re.sub('[\\n\\r]', '', line).strip()
                    responseforsending = False
                    for entry in self._response_commands:
                        newentry = self._processing_wildcard(line, entry)
                        self._response_wildcards['wildcard'].update({newentry: entry})
                        self._response_wildcards['original'].update({entry: newentry})
                    responsecommands = list(self._response_wildcards['wildcard'].keys())
                    responsecommands = [value for value in responsecommands if not '?' in value]
                    self.logger.log(VERBOSE1, "Processing Response {}: New Response Command list after processing wildcard: {}".format(self._name, responsecommands))
                    try:
                        for resp in ','.join(self._sendingcommand.split(';')[0].split(',')[2:]).split('|'):
                            resp = resp.split(',')[0]
                            self.logger.log(VERBOSE2, "Processing Response {}: Testing sendingcommand {}. Line: {}, expected response: {}".format(self._name, self._sendingcommand, line, resp))
                            if len(line) == len(resp):
                                resp = self._processing_wildcard(line, resp)
                                self.logger.log(VERBOSE2, "Processing Response {}: Comparing line {} to expected response from send {}".format(self._name, line, resp))
                                if line == resp:
                                    responseforsending = True
                                    self.logger.log(VERBOSE2, "Processing Response {}: Line and expected response from send are the same".format(self._name))
                    except Exception as err:
                        self.logger.log(VERBOSE2, "Processing Response {}: Problem comparing line {} with expected {}. Message {}".format(self._name, line, resp, err))
                    if not line.startswith(tuple(responsecommands)) and line not in self._error_response and responseforsending == False:
                        self.logger.log(VERBOSE1, "Processing Response {}: Response {} is not in possible responses for items. Sending Command: {}".format(self._name, line, self._sendingcommand))
                    elif line in self._error_response and '' not in self._error_response:
                        self.logger.debug("Processing Response {}: Response {} is in Error responses.".format(self._name, line))
                        yield "{}".format(line)
                    elif line.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
                        try:
                            compare = ','.join(self._send_commands[0].split(';')[0].split(',')[2:]).split('|')
                            for comp in compare:
                                comp = self._processing_wildcard(line, comp.split(',')[0])
                                if line.startswith(comp):
                                    keyfound = True
                                else:
                                    keyfound = False
                            if keyfound is True:
                                self.logger.log(VERBOSE1, "Processing Response {}: Sending Command: {} Keep command {}".format(self._name, self._send_commands, self._keep_commands))
                                for entry in self._keep_commands:
                                    if self._send_commands[0] in self._keep_commands.get(entry):
                                        self._keep_commands.pop(entry)
                                        self.logger.log(VERBOSE1, "Processing Response {}: Removed Keep command {} from {} because command sent successfully".format(
                                            self._name, entry, self._keep_commands))
                                        break
                                self._send_commands.pop(0)
                                self._sendingcommand = 'done'
                                self.logger.debug("Processing Response {}: Response {} is same as expected {} and defined as response to be ignored. Removing command from send list. It is now: {}. Ignore responses are: {}".format(
                                    self._name, line, compare, self._send_commands, self._ignore_response))
                                sending = self._send('command', 'commandremoval')
                            else:
                                self.logger.log(VERBOSE1, "Processing Response {}: Response {} is in ignore command {} but not same as expected response {}".format(self._name, line, self._ignore_response, compare))
                        except Exception as err:
                            self.logger.log(VERBOSE2, "Processing Response {}: Response {} is ignored because ignore responses is {}. Command list is now: {}. Message: {}".format(self._name, line, self._ignore_response, self._send_commands, err))
                    elif line.startswith(self._special_commands['Display']['Command']) and \
                            self._response_buffer is not False and not self._special_commands['Display']['Command'] == '':
                        self.logger.log(VERBOSE1, "Processing Response {}: Detected Display info {}. buffer: {}".format(self._name, line, re.sub('[\r\n]', ' --- ', buffer)))
                        buffering = False
                        buffer += '\r\n{}\r\n'.format(line)
                        buffer = tidy(buffer)
                        self.logger.log(VERBOSE1, "Processing Response {}: Append Display info {} to buffer: {}".format(self._name, line, re.sub('[\r\n]', ' --- ', buffer)))
                    else:
                        if self._response_buffer is False and not buffer.startswith(tuple(self._force_buffer)) and '' not in self._force_buffer:
                            buffering = False
                            self.logger.log(VERBOSE1, "Processing Response {}: Clearing buffer: {}".format(self._name, re.sub('[\r\n]', ' --- ', buffer)))
                            buffer = '\r\n'
                        self.logger.log(VERBOSE1, "Processing Response {}: Sending back line: {}. Display Command: {}".format(
                            self._name, line, self._special_commands['Display']['Command']))
                        yield "{}".format(line)
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
                        self.logger.log(VERBOSE1, "Processing Response {}: Buffering false.".format(self._name))

            if not buffer == '\r\n' and (self._response_buffer is True or type(self._response_buffer) is int):
                buffer = tidy(buffer)
                bufferlist = buffer.split('\r\n')
                # Removing everything except last x lines
                maximum = abs(self._response_buffer) if type(self._response_buffer) is int else 11
                multiplier = 1 if self._response_buffer >= 0 else -1
                while '' in bufferlist:
                    bufferlist.remove('')
                newbuffer = []
                for buf in bufferlist:
                    if not buf.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response and buf.startswith(tuple(self._response_commands)):
                        newbuffer.append(buf)
                bufferlist = newbuffer[-1 * max(min(len(newbuffer), maximum), 0):]

                if len(bufferlist) > 1:
                    self.logger.log(VERBOSE1, "Bufferlist after: {}".format(bufferlist))
                buffering = False
                for buf in bufferlist:
                    if not re.sub('[ ]', '', buf) == '' and not buf.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
                        self.logger.log(VERBOSE1, "Processing Response {}: Sending back {} from buffer because Responsebuffer is activated.".format(self._name, buf))
                        self._wait(0.2)
                        yield buf

            elif not buffer == '\r\n':
                buffer = tidy(buffer)
                bufferlist = buffer.split('\r\n')
                # Removing everything except last x lines
                maximum = abs(self._response_buffer) if type(self._response_buffer) is int else 11
                multiplier = 1 if self._response_buffer >= 0 else -1
                bufferlist = bufferlist[multiplier * max(min(len(bufferlist), maximum), 0):]
                buffering = False
                for buf in bufferlist:
                    if not re.sub('[ ]', '', buf) == '' and not buf.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
                        self.logger.debug("Processing Response {}: Sending back {} from filtered buffer: {}.".format(self._name, buf, re.sub('[\r\n]', ' --- ', buffer)))
                        self._wait(0.2)
                        yield buf
        except Exception as err:
            self.logger.error("Processing Response {}: Problems occured. Message: {}".format(self._name, err))

    # init function
    def _initialize(self):
        self._send_commands[:] = []
        self._sendingcommand = 'done'
        self._functions, self._number_of_zones, self._specialparse = self.init._read_commandfile()
        self._response_commands, self._special_commands = self.init._create_responsecommands()
        self._power_commands = self.init._create_powercommands()
        self._query_commands, self._query_zonecommands = self.init._create_querycommands()
        self.logger.log(VERBOSE1, "Initializing {}: Functions: {}, Number of Zones: {}".format(self._name, self._functions, self._number_of_zones))
        self.logger.log(VERBOSE1, "Initializing {}: Responsecommands: {}.".format(self._name, self._response_commands))
        self.logger.log(VERBOSE1, "Initializing {}: Special Commands: {}".format(self._name, self._special_commands))
        self.logger.log(VERBOSE1, "Initializing {}: Special Parsing: {}".format(self._name, self._specialparse))
        self.logger.log(VERBOSE1, "Initializing {}: Powercommands: {}".format(self._name, self._power_commands))
        self.logger.log(VERBOSE1, "Initializing {}: Querycommands: {}, Query Zone: {}".format(self._name, self._query_commands, self._query_zonecommands))
        problems = {'zone3': {}, 'zone1': {}, 'zone2': {}, 'zone0': {}}
        new = {'zone3': {}, 'zone1': {}, 'zone2': {}, 'zone0': {}}
        for zone in self._init_commands:
            try:
                for command in self._init_commands[zone]:
                    try:
                        self._init_commands[zone][command]['Item'] = self._items[zone][command]['Item']
                    except Exception as err:
                        problems[zone] = command
                        self.logger.error("Initializing {}: Problems occured with init command {} for {}.".format(self._name, err, zone))
            except Exception as err:
                self.logger.debug("Initializing {}: No init commands set. Message: {}".format(self._name, err))
        for zone in self._init_commands:
            new[zone] = {k:v for k,v in self._init_commands[zone].items() if k not in problems[zone]}
        self._init_commands = new
        self.logger.log(VERBOSE1, "Initializing {}: Initcommands: {}".format(self._name, self._init_commands))
        self.logger.log(VERBOSE1, "Initializing {}: done".format(self._name))
        return True

    # Run function
    def run(self):
        if self._tcp is None and self._rs232 is None:
            self.logger.error("Initializing {}: Neither IP address nor RS232 port given. Not running.".format(self._name))
        else:
            self._items, self._dependencies = self.init._processitems()
            initdone = self._initialize()
            self.logger.log(VERBOSE1, "Initializing {}: Init done: {}".format(self._name, initdone))
            self.logger.log(VERBOSE1, "Initializing {}: Items: {}".format(self._name, self._items))
            self._dependencies = self.init._update_dependencies(self._dependencies)
            self.logger.log(VERBOSE1, "Initializing {}: Updated Dependencies: {}".format(self._name, self._dependencies))
            self.logger.log(VERBOSE1, "Initializing {}: Speaker Items: {}".format(self._name, self._items_speakers))
            try:
                try:
                    self._dependson = self._sh.return_item(self._dependson)
                    self.logger.debug("Initializing {}: Dependson Item: {}.".format(self._name, self._dependson))
                except Exception:
                    self._dependson = None
                    self.logger.warning("Initializing {}: Dependson Item {} is no valid item.".format(self._name, self._dependson))
                self.logger.debug("Initializing {}: Running".format(self._name))
                self.alive = True
            except Exception as err:
                self.logger.error("Initializing {}: Problem running and creating items. Error: {}".format(self._name, err))
            finally:
                if self._tcp is not None or self._rs232 is not None:
                    self.connect('run')

    # Triggering TCP or RS232 connection schedulers
    def connect(self, trigger):
        self._trigger_reconnect = True
        if self._is_connected == []:
            self._parsinginput = []
            self._is_connected.append('Connecting')
        self.logger.log(VERBOSE1, "Connecting {}: Starting to connect. Triggered by {}. Current Connections: {}".format(self._name, trigger, self._is_connected))
        depending = self._checkdependency(self._dependson, 'connect')
        if depending is False:
            if self._tcp is not None and 'TCP' not in self._is_connected:
                self.logger.log(VERBOSE1, "Connecting {}: Starting TCP scheduler".format(self._name))
                self._sh.scheduler.add('avdevice-tcp-reconnect', self.connect_tcp, cycle=7)
                self._sh.scheduler.change('avdevice-tcp-reconnect', active=True)
                self._sh.scheduler.trigger('avdevice-tcp-reconnect')
                self._trigger_reconnect = False
            if self._rs232 is not None and 'Serial' not in self._is_connected:
                self.logger.log(VERBOSE1, "Connecting {}: Starting RS232 scheduler".format(self._name))
                self._sh.scheduler.add('avdevice-serial-reconnect', self.connect_serial, cycle=7)
                self._sh.scheduler.change('avdevice-serial-reconnect', active=True)
                self._sh.scheduler.trigger('avdevice-serial-reconnect')
                self._trigger_reconnect = False
        elif depending is True and trigger == 'parse_dataerror':
            self._resetondisconnect('connect')

    # Connect to TCP IP
    def connect_tcp(self):
        self._is_connected.append('TCP') # TOTEST
        try:
            if self._tcp is not None and 'TCP' not in self._is_connected:
                socket = __import__('socket')
                self.logger.log(VERBOSE1, "Connecting TCP {}: Starting to connect to {}.".format(self._name, self._tcp))
                self._tcpsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self._tcpsocket.setblocking(0)
                self._tcpsocket.settimeout(6)
                self._tcpsocket.connect(('{}'.format(self._tcp), int(self._port)))
                self._tcpsocket.settimeout(self._tcp_timeout)
                self._is_connected.append('TCP')
                try:
                    self._is_connected.remove('Connecting')
                except Exception:
                    pass
                self.logger.info("Connecting TCP {}: Connected to {}:{}".format(
                    self._name, self._tcp, self._port))

        except Exception as err:
            if 'TCP' in self._is_connected:
                self._is_connected.remove('TCP')
            self.logger.warning("Connecting TCP {}: Could not connect to {}:{}. Error:{}. Counter: {}/{}".format(
                self._name, self._tcp, self._port, err, self._reconnect_counter, self._reconnect_retries))

        finally:
            if ('TCP' not in self._is_connected and self._tcp is not None) and str(self._auto_reconnect).lower() in ['1', 'yes', 'true', 'on']:
                self._trigger_reconnect = False
                self.logger.warning("Connecting TCP {}: Reconnecting. Command list while connecting: {}.".format(
                    self._name, self._send_commands))
            elif ('TCP' in self._is_connected and self._tcp is not None) or self._reconnect_counter >= self._reconnect_retries:
                self._sh.scheduler.change('avdevice-tcp-reconnect', active=False)
                self._reconnect_counter = 0
                self._addfrom_keepcommands('connect_tcp', 'all')
                self._trigger_reconnect = True
                self.logger.debug("Connecting TCP {}: Deactivating reconnect scheduler. Command list while connecting: {}. Keep Commands: {}".format(
                    self._name, self._send_commands, self._keep_commands))
            self._reconnect_counter += 1
            if 'TCP' in self._is_connected:
                self.logger.debug("Connecting TCP {}: TCP is connected.".format(self._name))
                if self._parsinginput == []:
                    self.logger.debug("Connecting TCP {}: Starting Parse Input.".format(self._name))
                    self._parse_input_init('tcpconnect')

    # Connect to RS232
    def connect_serial(self):
        try:
            if self._rs232 is not None and 'Serial' not in self._is_connected:
                serial = __import__('serial')
                ser = serial.serial_for_url('{}'.format(self._rs232), baudrate=int(self._baud), timeout=float(self._timeout), write_timeout=float(self._timeout))
                i = 0
                try:
                    command = self._power_commands[0].split(',')[1]
                    self.logger.debug("Connecting Serial {}: Starting to connect to {} with init command {}.".format(self._name, self._rs232, command))
                except Exception as err:
                    self.logger.warning("Connecting Serial {}: No power commands found. Please check your config files!".format(self._name))
                    command = '?P'
                while ser.in_waiting == 0:
                    i += 1
                    self._wait(0.5)
                    ser.write(bytes('{}\r'.format(command), 'utf-8'))
                    buffer = bytes()
                    buffer = ser.read().decode('utf-8')
                    self.logger.log(VERBOSE1, "Connecting Serial {}:  Buffer: {}. Reconnecting Retry: {}.".format(self._name, re.sub('[\r\n]', ' --- ', buffer), i))
                    if i >= 4:
                        ser.close()
                        self.logger.log(VERBOSE1, "Connecting Serial {}:  Ran through several retries.".format(self._name))
                        break
                if ser.isOpen():
                    self._serialwrapper = io.TextIOWrapper(io.BufferedRWPair(ser, ser), newline='\r\n', encoding='utf-8', line_buffering=True, write_through=True)
                    self._serialwrapper.timeout = 0.1
                    self._serial = ser
                    self._trigger_reconnect = False
                    if 'Serial' not in self._is_connected:
                        self._is_connected.append('Serial')
                    try:
                        self._is_connected.remove('Connecting')
                    except Exception:
                        pass
                    self.logger.info("Connecting Serial {}: Connected to {} with baudrate {}.".format(
                        self._name, ser, self._baud))
                else:
                    self.logger.warning("Connecting Serial {}: Serial port is not open. Connection status: {}. Reconnect Counter: {}".format(self._name, self._is_connected, self._reconnect_counter))
        except Exception as err:
            if 'Serial' in self._is_connected:
                self._is_connected.remove('Serial')
            self.logger.warning("Connecting Serial {}: Could not connect to {}, baudrate {}. Error:{}, Counter: {}/{}".format(
                self._name, self._rs232, self._baud, err, self._reconnect_counter, self._reconnect_retries))

        finally:
            if ('Serial' not in self._is_connected and self._rs232 is not None) and str(self._auto_reconnect).lower() in ['1', 'yes', 'true', 'on']:
                self._trigger_reconnect = False
                self.logger.log(VERBOSE1, "Connecting Serial {}: Activating reconnect scheduler. Command list while connecting: {}.".format(
                    self._name, self._send_commands))
            elif ('Serial' in self._is_connected and self._rs232 is not None) or self._reconnect_counter >= self._reconnect_retries:
                self._sh.scheduler.change('avdevice-serial-reconnect', active=False)
                self._reconnect_counter = 0
                self._addfrom_keepcommands('connect_serial', 'all')
                self._trigger_reconnect = True
                self.logger.debug("Connecting Serial {}: Deactivating reconnect scheduler. Command list while connecting: {}. Keep commands: {}".format(
                    self._name, self._send_commands, self._keep_commands))
            self._reconnect_counter += 1
            if 'Serial' in self._is_connected:
                self.logger.debug("Connecting Serial {}: Serial is connected.".format(self._name))
                if self._parsinginput == []:
                    self.logger.debug("Connecting Serial {}: Starting Parse Input.".format(self._name))
                    self._parse_input_init('serialconnect')

    def _checkdependency(self, function, type):
        depending = False
        self.logger.log(VERBOSE2, "Checking Dependency {}: Function: {}, type: {}.".format(self._name, function, type))
        if type == 'statusupdate' or type == 'initupdate' or type == 'checkquery' or (type == 'update' and not function == ''):
            if type == 'statusupdate' or type == 'initupdate':
                totest = self._dependencies['Slave_query']
                queryzone = None
            elif type == 'update':
                totest = self._dependencies['Slave_item']
                function = function.id()
                queryzone = None
            elif type == 'checkquery':
                origfunction = function
                totest = self._dependencies['Master_function']
                queryzone = origfunction.split(', ')[0]
                function = origfunction.split(', ')[1]
            for zone in totest:
                if (function in totest[zone] and not type == 'checkquery') or \
                    (type == 'checkquery' and zone == queryzone and function in totest[zone]):
                    donedependitems = []
                    groupcount = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                    grouptotal = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                    dependitems = {'a': {}, 'b': {}, 'c': {}, 'd': {}}
                    for entry in totest[zone][function]:
                        try:
                            func = entry['Function']
                            if func.lower() == 'init' and type == 'initupdate':
                                self.logger.log(VERBOSE2, "Checking Dependency {}: Adding query because it's init dependency is set to true.".format(self._name))
                                return False
                        except Exception:
                            func = None
                        try:
                            dependitem = stopdepend = entry['Item']
                            if not type == 'checkquery':
                                try:
                                    dependvalue = dependitem()
                                except Exception:
                                    dependvalue = None
                            else:
                                dependvalue = origfunction.split(', ')[2]
                                try:
                                    dependvalue = eval(dependvalue.lstrip('0'))
                                except Exception:
                                    pass
                            expectedvalue = entry['Dependvalue']
                            compare = entry['Compare']
                            group = entry['Group']
                            if dependitem not in donedependitems:
                                grouptotal[group] += 1
                            self.logger.log(VERBOSE2, "Checking Dependency {}: first: dependitem: {} expvalue: {}, dependvalue: {}, compare {}.".format(self._name, dependitem, expectedvalue, dependvalue, compare))
                            try:
                                expectedvalue = eval(expectedvalue.lstrip('0'))
                            except Exception:
                                pass
                            if dependvalue == expectedvalue and compare == '==':
                                groupcount[group] += 1
                            elif dependvalue >= expectedvalue and compare == '>=':
                                groupcount[group] += 1
                            elif dependvalue <= expectedvalue and compare == '<=':
                                groupcount[group] += 1
                            elif dependvalue < expectedvalue and compare == '<':
                                groupcount[group] += 1
                            elif dependvalue > expectedvalue and compare == '>':
                                groupcount[group] += 1
                            elif not dependvalue == expectedvalue and compare == '!=':
                                groupcount[group] += 1
                            if not type == 'checkquery':
                                try:
                                    dependitems[group][dependitem].append([dependvalue, compare, expectedvalue])
                                except Exception:
                                    dependitems[group].update({dependitem: [[dependvalue, compare, expectedvalue]]})
                        except Exception as err:
                            depending = False
                            self.logger.warning( "Checking Dependency {}: Adding function {} caused problem: {}.".format(self._name, function, err))

                        if type == 'checkquery' and dependitem not in donedependitems:
                            primarycount = sum(groupcount.values())
                            groupcount = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                            grouptotal = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                            additional_zone = entry['Zone']
                            try:
                                for additional in self._dependencies['Slave_item'][additional_zone][dependitem.id()]:
                                    dependitem = additional['Item']
                                    dependvalue = dependitem()
                                    expectedvalue = additional['Dependvalue']
                                    compare = additional['Compare']
                                    group = additional['Group']
                                    grouptotal[group] += 1
                                    self.logger.log(VERBOSE2, "Checking Dependency {}: zone: {}, additional: dependitem: {} expvalue: {}, dependvalue: {}, compare {}.".format(self._name, additional_zone, dependitem, expectedvalue, dependvalue, compare))
                                    try:
                                        expectedvalue = eval(expectedvalue.lstrip('0'))
                                    except Exception:
                                        pass
                                    if dependvalue == expectedvalue and compare == '==':
                                        groupcount[group] += 1
                                    elif dependvalue >= expectedvalue and compare == '>=':
                                        groupcount[group] += 1
                                    elif dependvalue <= expectedvalue and compare == '<=':
                                        groupcount[group] += 1
                                    elif dependvalue < expectedvalue and compare == '<':
                                        groupcount[group] += 1
                                    elif dependvalue > expectedvalue and compare == '>':
                                        groupcount[group] += 1
                                    elif not dependvalue == expectedvalue and compare == '!=':
                                        groupcount[group] += 1
                                    try:
                                        dependitems[group][dependitem].append([dependvalue, compare, expectedvalue])
                                    except Exception:
                                        dependitems[group].update({dependitem: [[dependvalue, compare, expectedvalue]]})
                            except Exception as err:
                                depending = False
                                self.logger.warning("Checking Dependency {}: Adding function {} in zone {} caused problem: {}.".format(self._name, function, zone, err))
                            self.logger.log(VERBOSE2, "Checking Dependency {}: Zone: {}, Groupcount: {}, Grouptotal: {}. Primarycount: {}".format(self._name, additional_zone, groupcount, grouptotal, primarycount))
                            comparetotal = 0
                            dependtotal = 0
                            for group in grouptotal:
                                if grouptotal[group] > 0:
                                    comparetotal += 1
                                    if groupcount.get(group) > 0:
                                        dependtotal += 1
                            try:
                                queryentry = entry['Query']
                            except Exception as err:
                                self.logger.log(VERBOSE2, "Checking Dependency {}: Dependent functions found for {}. But no Query command. Message: {}".format(self._name, function, err))
                                queryentry = None
                            if dependtotal == comparetotal:
                                if primarycount > 0 and not queryentry is None:
                                    if queryentry not in self._send_commands:
                                        self._send_commands.append(queryentry)
                                        self.logger.debug("Checking Dependency {}: Dependent Query command {} added to Send Commands. It is now: {}. Dependencies: {}".format(self._name, queryentry, self._send_commands, dependitems))
                                    else:
                                        self.logger.log(VERBOSE2, "Checking Dependency {}: Dependent Query command {} already in send commands: {}.".format(self._name, queryentry, self._send_commands))
                                else:
                                    self.logger.log(VERBOSE2, "Checking Dependency {}: Primary dependency not fullfilled, not adding or removing query  {}".format(self._name, queryentry))
                            elif primarycount == 0 and not queryentry is None:
                                try:
                                    self._send_commands.remove(queryentry)
                                    self._clearbuffer = True
                                    self.logger.debug("Checking Dependency {}: Dependent Query command {} removed from Send Commands. It is now: {}. Dependencies: {}".format(self._name, queryentry, self._send_commands, dependitems))
                                except Exception:
                                    self.logger.log(VERBOSE2, "Checking Dependency {}: Dependent Query command {} not in Send Commands, not removing it. Dependencies: {}".format(self._name, queryentry, dependitems))
                            else:
                                self.logger.log(VERBOSE2, "Checking Dependency {}: Primary dependency not fullfilled. Doing nothing.".format(self._name))
                            donedependitems.append(stopdepend)
                            groupcount = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                            grouptotal = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                            dependitems = {'a': {}, 'b': {}, 'c': {}, 'd': {}}
                    if not type == 'checkquery':
                        self.logger.log(VERBOSE2, "Checking Dependency {}: Groupcount: {}, Grouptotal: {}.".format(self._name, groupcount, grouptotal))
                        comparetotal = 0
                        dependtotal = 0
                        for group in grouptotal:
                            if grouptotal[group] > 0:
                                comparetotal += 1
                                if groupcount.get(group) > 0:
                                    dependtotal += 1
                    if dependtotal == comparetotal and not type == 'checkquery':
                        depending = False
                        self.logger.log(VERBOSE1, "Checking Dependency {}: Adding function {} because dependency fullfilled: {}.".format(self._name, function, dependitems))
                    elif not type == 'checkquery':
                        depending = True
                        self.logger.debug("Checking Dependency {}: Not adding function {} because dependency not fullfilled: {}".format(self._name, function, dependitems))
                    if depending is True and type == 'update':
                        self.logger.log(VERBOSE2, "Checking Dependency {}: Starting to reset item: {}.".format(self._name, function))
                        self._resetitem(function)

        elif type == 'globaldepend' or type == 'parseinput' or type == 'connect' or type == 'dependitem':
            try:
                dependsvalue = self._dependson()
                self.logger.debug("Checking Dependency {}: Connection depends on {}. It's value is {}, has to be {}. Connections are {}".format(self._name, self._dependson, dependsvalue, self._dependson_value, self._is_connected))
                if dependsvalue == self._dependson_value:
                    depending = False
                    if type == 'dependitem':
                        try:
                            eval(self._items['zone0']['statusupdate']['Item'])(1, 'Depending', self._rs232 if self._rs232 is not None else self._tcp)
                        except Exception:
                            try:
                                self._items['zone0']['statusupdate']['Item'](1, 'Depending', self._rs232 if self._rs232 is not None else self._tcp)
                            except Exception as err:
                                pass
                else:
                    depending = True
                    try:
                        item = self._sh.return_item(function).id()
                    except:
                        item = function.id()
                    if not item == self._dependson.id():
                        self.logger.log(VERBOSE2, "Checking Dependency {}: Starting to reset item: {}.".format(self._name, item))
                        self._resetitem(item)
                    if type == 'connect':
                        self._is_connected = []
                        self._parsinginput = []
                    if (type == 'parseinput'  or type == 'dependitem') and (self._depend0_volume0 is True or self._depend0_power0 is True):
                        self._resetondisconnect('parseinput')
            except Exception as e:
                depending = False
                self.logger.log(VERBOSE1, "Checking Dependency {}: Globally assigned Dependency is false. Message: {}".format(self._name, e))
        self.logger.log(VERBOSE2, "Checking Dependency {}: Returning {}".format(self._name, depending))
        return depending

    # Updating Status even if no statusupdate is defined in device text file
    def _statusupdate(self, value, trigger, caller):
        self.logger.debug("Statusupdate {}: Value: {}. Trigger from {}. Caller: {}".format(self._name, value, trigger, caller))
        self.update_item('statusupdate', 'Init')

    # Adding Keep Commands to Send Commands
    def _addfrom_keepcommands(self, trigger, zone):
        self.logger.log(VERBOSE1, "Keep Commands {}: Trigger from {} for zone {}. Send Commands: {}".format(self._name, trigger, zone, self._send_commands))
        keeptemp = []
        for zeit in self._keep_commands:
            keeping = False
            if time.time() - zeit <= self._secondstokeep and not self._keep_commands[zeit] in keeptemp:
                try:
                    for itemlist in self._query_zonecommands['{}'.format(zone)]:
                        if itemlist.split(',')[1] == self._keep_commands[zeit].split(',')[1]:
                            keeping = True
                except:
                    self.logger.log(VERBOSE2, "Keep Commands {}: Zone is set to all.".format(self._name))
                if zone == 'all' or keeping == True or trigger == 'powercommand':
                    keeping = True
                    keeptemp.append(self._keep_commands[zeit])
            self.logger.debug("Keep Commands {}: Age {}s of command {}. Secondstokeep: {}. Keeping command: {}".format(
                self._name, int(time.time() - zeit), self._keep_commands[zeit], self._secondstokeep, keeping))
        self._send_commands = self._send_commands + list(set(keeptemp))
        seen = set()
        self._send_commands = [x for x in self._send_commands if x not in seen and not seen.add(x)]
        self._keep_commands = {}
        keeptemp = []

    # Parsing the response and comparing it with expected response
    def _parse_input_init(self, trigger):
        if not self._is_connected == [] and not self._is_connected == ['Connecting']:
            self._parsinginput.append(trigger)
        else:
            self._parsinginput = []
        self.logger.log(VERBOSE1, "Parsing Input {}: Init Triggerd by these functions so far: {}".format(self._name, self._parsinginput))
        if trigger == 'tcpconnect' or trigger == 'serialconnect':
            for zone in self._init_commands:
                if len(self._init_commands[zone].keys()) > 0:
                    for init in self._init_commands[zone]:
                        try:
                            initvalue = self._init_commands[zone][init]['Inititem']()
                            self.logger.log(VERBOSE1, "Parsing Input {}: Starting eval init: {} for {} with value {}".format(self._name, init, zone, initvalue))
                            eval(self._init_commands[zone][init]['Item'])(initvalue, 'Init', self._tcp)
                            self.logger.debug("Parsing Input {}: Updated Item after connection: {} with value {}. Commandlist: {}".format(
                                self._name, self._init_commands[zone][init]['Item'], initvalue, self._send_commands))
                        except Exception as err:
                            try:
                                initvalue = self._init_commands[zone][init]['Inititem']()
                                self.logger.log(VERBOSE1, "Parsing Input {}: Starting exception init: {} for {}. Message: {}".format(self._name, init, zone, err))
                                self._init_commands[zone][init]['Item'](initvalue, 'Init', self._tcp)
                                self.logger.debug("Parsing Input {}: Updated Item after connection: {} with value {}. Commandlist: {}".format(
                                    self._name, self._init_commands[zone][init]['Item'], initvalue, self._send_commands))
                            except Exception as err:
                                self.logger.log(VERBOSE1, "Parsing Input {}: No init defined, not executing command after {}. Message: {}".format(self._name, trigger, err))
            try:
                self.logger.log(VERBOSE1, "Parsing Input {}: Starting eval statusupdate.".format(self._name))
                eval(self._items['zone0']['statusupdate']['Item'])(1, 'Init', self._tcp)
                self.logger.debug("Parsing Input {}: Updated Item after connection: {} with value 1. Commandlist: {}".format(
                    self._name, self._items['zone0']['statusupdate']['Item'], self._send_commands))
            except Exception:
                try:
                    self.logger.log(VERBOSE1, "Parsing Input {}: Starting exception statusupdate.".format(self._name))
                    self._items['zone0']['statusupdate']['Item'](1, 'Init', self._tcp)
                    self.logger.debug("Parsing Input {}: Updated Item after connection: {} with value 1. Commandlist: {}".format(
                        self._name, self._items['zone0']['statusupdate']['Item'], self._send_commands))
                except Exception as err:
                    self.logger.log(VERBOSE1, "Parsing Input {}: No statusupdate defined, not querying status after {}. Message: {}".format(self._name, trigger, err))
        if len(self._parsinginput) == 1:
            self._parse_input(trigger)

    # Parsing the response and comparing it with expected response
    def _parse_input(self, trigger):
        self.logger.log(VERBOSE1, "Parsing Input {}: Triggerd by {}".format(self._name, trigger))
        def _duplicateindex(seq,item):
            start_at = -1
            locs = []
            while True:
                try:
                    loc = seq.index(item,start_at+1)
                except ValueError:
                    break
                else:
                    locs.append(loc)
                    start_at = loc
            return locs

        while self.alive and not self._parsinginput == [] and not self._is_connected == [] and not self._is_connected == ['Connecting']:
            connectionproblem = False
            if not self._sendingcommand == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
                self.logger.log(VERBOSE1, "Parsing Input {}: Starting to parse input. Alive: {}. Connected: {}. Parsinginput: {}. Sendcommand: {}".format(
                    self._name, self.alive, self._is_connected, self._parsinginput, self._sendingcommand))
            to_send = 'command'
            try:
                data = 'waiting'
                databuffer = []
                if 'Serial' in self._is_connected:
                    try:
                        databuffer = self._processing_response(self._serialwrapper)
                    except Exception as err:
                        self.logger.error("Parsing Input {}: Problem receiving Serial data {}.".format(self._name, err))
                elif 'TCP' in self._is_connected:
                    try:
                        databuffer = self._processing_response(self._tcpsocket)
                    except Exception as err:
                        self.logger.error("Parsing Input {}: Problem receiving TCP data {}.".format(self._name, err))
                for data in databuffer:
                    data = data.strip()
                    if data == '' and not self._sendingcommand == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
                        self.logger.log(VERBOSE1, "Parsing Input {}: Problem with empty response.".format(self._name))
                    if data == 'ERROR' and not self._sendingcommand == 'gaveup' and not self._sendingcommand == 'done':
                        if self._resend_counter >= self._resend_retries:
                            self.logger.warning("Parsing Input {}: Giving up Sending {} and removing from list. Received Data: {}. Original Commandlist: {}".format(
                                self._name, self._sendingcommand, data, self._send_commands))
                            self._resend_counter = 0
                            self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter because maximum retries exceeded.".format(self._name))
                            # Resetting Item if Send not successful
                            if self._reset_onerror is True:
                                self._resetitem('')
                            try:
                                if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._special_commands['Display']['Command']:
                                    self._keep_commands[time.time()] = self._send_commands[0]
                                    self.logger.debug("Parsing Input {}: Removing item from send command, storing in keep commands: {}.".format(self._name, self._keep_commands))
                                elif self._send_commands[0] in self._query_commands:
                                    self.logger.warning("Parsing Input {}: Giving up {}, because no answer received 1.".format(self._name, self._sendingcommand))
                                self._send_commands.pop(0)
                                if not self._send_commands == []:
                                    sending = self._send('command', 'parseinput')
                                    self.logger.log(VERBOSE1, "Parsing Input {}: Command List is now: {}. Sending return is {}.".format(
                                        self._name, self._send_commands, sending))
                            except Exception as err:
                                self.logger.debug("Parsing Input {}: Nothing to remove from Send Command List. Error: {}".format(self._name, err))
                            self._sendingcommand = 'gaveup'
                            if self._trigger_reconnect is True:
                                self.logger.log(VERBOSE1, "Parsing Input {}: Trying to connect while parsing item".format(self._name))
                                self.connect('parse_input')

                    sorted_response_commands = sorted(self._response_commands, key=len, reverse=True)
                    for i in range(0, len(sorted_response_commands)):
                        try:
                            sorted_response_commands[i] = self._response_wildcards['original'][sorted_response_commands[i]]
                        except Exception as err:
                            sorted_response_commands[i] = None
                            self.logger.log(VERBOSE2, "Parsing Input {}: Can not find wildcard equivalent for: {}".format(self._name, err))
                    sorted_response_commands = [value for value in sorted_response_commands if (value != None and not '?' in value)]
                    self.logger.log(VERBOSE2, "Parsing Input {}: New Response Command list after sorting: {}".format(self._name, sorted_response_commands))

                    self.logger.debug("Parsing Input {}: Response: {}. Send Commands: {}".format(self._name, data, self._send_commands))
                    if data == 'ERROR' and self._send_commands == []:
                        self._resend_counter += 1
                        if self._resend_counter >= self._resend_retries:
                            self._resend_counter = 0
                            self.logger.debug("Parsing Input {}: Gave up sending {} because no response received. Is the command WRITEONLY?".format(
                                self._name, self._sendingcommand))
                            self._sendingcommand = 'gaveup'
                    elif not self._send_commands == []:
                        expectedresponse = self._expected_response
                        self.logger.debug("Parsing Input {}: Expected response while parsing: {}.".format(self._name, expectedresponse))

                        try:
                            to_send = 'command'
                            valuetype = 'empty'
                            deletecommands = []
                            runthrough = []
                            if not expectedresponse == []:
                                for expected in expectedresponse:
                                    if expected not in runthrough and not data == 'ERROR':
                                        runthrough.append(expected)
                                        found = []
                                        expectedlist = expected.split('|')
                                        try:
                                            for expectedpart in expectedlist:
                                                try:
                                                    datalength = self._response_commands[expectedpart][0][1]
                                                    expectedlength = []
                                                    stringvalue = []

                                                    for vals in self._response_commands[expectedpart]:
                                                        stringvalue.append(True if int(vals[0]) == 30 or int(vals[1]) == 100 else False)
                                                        expectedlength.append(int(vals[1]))
                                                        if int(vals[2]) < datalength and int(vals[2]) > 0:
                                                            datalength = int(vals[2])
                                                    self.logger.log(VERBOSE2, "Parsing Input {}: Comparing Data {} (cut: {}) to: {}, expectedlength: {}, datalength: {}, string: {}.".format(self._name, data, data[:datalength], expectedpart, expectedlength, len(data), stringvalue))
                                                    if data[:datalength].startswith(expectedpart) and (len(data) in expectedlength or True in stringvalue):
                                                        found.append(expectedpart)
                                                        self.logger.log(VERBOSE1, "Parsing Input {}: Expected response edited: {}.".format(self._name, found))
                                                except Exception:
                                                    found.append(expectedpart)
                                                    self.logger.log(VERBOSE1, "Parsing Input {}: Expected response edited 2nd try: {}.".format(self._name, found))
                                        except Exception as err:
                                            found.append(expected)
                                            self.logger.debug("Parsing Input {}: Expected response after exception: {}. Problem: {}".format(self._name, found, err))
                                        try:
                                            if data.startswith(tuple(found)):
                                                self.logger.log(VERBOSE1, "Parsing Input {}: Expected response edited {}. Data starts with one of the entries.".format(self._name, found))
                                                entry, value, valuetype = self._write_itemsdict(data, found)
                                                self._sendingcommand = 'done'
                                                self._resend_counter = 0
                                                self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter because data is same as expected.".format(self._name))
                                                self.logger.log(VERBOSE1, "Parsing Input {}: Data {} found in {}. Entry: {}, Value: {}. Expected Type: {}".format(self._name, data, found, entry, value, valuetype))
                                            elif (expectedlist[0] == '' or expectedlist[0] == ' ' or expectedlist[0] == 'none'):
                                                self._sendingcommand = 'done'
                                                self._resend_counter = 0
                                                self.logger.log(VERBOSE1, "Parsing Input {}: No response expected. Resend Counter reset.".format(self._name))
                                            elif expectedlist[0].lower() == 'string':
                                                value = data
                                                self.logger.log(VERBOSE1, "Parsing Input {}: String found and testing... ".format(self._name))
                                                if value.startswith(tuple(self._response_commands.keys())):
                                                    self.logger.log(
                                                        VERBOSE1, "Parsing Input {}: Found string but ignored because it is a legit response for another command.".format(self._name))
                                                else:
                                                    entry, value, valuetype = self._write_itemsdict(data, found)
                                                    self.logger.debug("Parsing Input {}: String FOUND. Written to dict: {}. Resend Counter reset.".format(self._name, entry))
                                                    self._sendingcommand = 'done'
                                                    self._resend_counter = 0

                                            # only add send command to list again if response doesn't fit to corresponding command
                                            expectedindices = _duplicateindex(expectedresponse, expected)
                                            self.logger.log(VERBOSE2, "Parsing Input {}: expectedindices {}.".format(
                                                            self._name, expectedindices))
                                            for expectedindex in expectedindices:
                                                self.logger.log(VERBOSE2, "Parsing Input {}: expected {}, deletecommands {}.".format(
                                                            self._name, self._send_commands[expectedindex], deletecommands))
                                                if self._send_commands[expectedindex] not in deletecommands:
                                                    if self._send_commands[expectedindex].split(',', 2)[2].find('|') >= 0:
                                                        expectedtype = self._send_commands[expectedindex].split(';')[0].split('|')[0].split(',')
                                                    else:
                                                        expectedtype = self._send_commands[expectedindex].split(';')[0].split(',')
                                                    try:
                                                        int(expectedtype[-1])
                                                        length = len(expectedtype)-1
                                                    except:
                                                        length = len(expectedtype)
                                                    try:
                                                        expectedtype[3:length] = [','.join(expectedtype[3:length])]
                                                        testvalue = expectedtype[3]
                                                    except Exception:
                                                        testvalue = ''
                                                    if not valuetype == testvalue or not found or data == 'ERROR':
                                                        self.logger.log(VERBOSE2, "Parsing Input {}: Test Value {} of {} is not same as Valuetype: {} or nothing found {}. Keeping in Sendcommands.".format(
                                                            self._name, testvalue, self._send_commands[expectedindex], valuetype, found))
                                                    elif not data == 'ERROR':
                                                        deletecommands.append(self._send_commands[expectedindex])
                                                        self.logger.log(VERBOSE1, "Parsing Input {}: Test Value {} of {} is same as Valuetype: {}. Removing from Sendcommands.".format(
                                                            self._name, testvalue, self._send_commands[expectedindex], valuetype))
                                        except Exception as err:
                                            self.logger.log(VERBOSE1, "Parsing Input {}: Write to dict problems: {}".format(self._name, err))

                                self.logger.log(VERBOSE2, "Parsing Input {}: Deleting {} from sendcommands.".format(self._name, deletecommands))
                            todelete = set(deletecommands)
                            updatedcommands = [x for x in self._send_commands if x not in todelete]
                            self._send_commands = updatedcommands
                            self.logger.log(VERBOSE1, "Parsing Input {}: Sendcommands: {}. Sendingcommand: {}".format(self._name, self._send_commands, self._sendingcommand))
                            if not self._send_commands == [] and not self._sendingcommand == 'done':
                                self._resend_counter += 1
                                depending = self._checkdependency('', 'parseinput')
                                if self._resend_counter >= self._resend_retries:
                                    self._resend_counter = 0
                                    self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter because maximum retries exceeded.".format(self._name))
                                    if not self._send_commands[0] in self._query_commands and not self._send_commands == []:
                                        self._sendingcommand = self._send_commands[0]
                                        self.logger.warning("Parsing Input {}: Going to reset item {}.".format(self._name, self._sendingcommand))
                                        self._resetitem('')
                                    temp_sendcommand = self._sendingcommand
                                    self._sendingcommand = 'gaveup'
                                    if data == 'ERROR':
                                        connectionproblem = True
                                    else:
                                        connectionproblem = False

                                    if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._special_commands['Display']['Command']:
                                        # self._keep_commands[time.time()] = self._send_commands[0]
                                        self.logger.debug("Parsing Input {}: Removing item from send command, not storing in keep commands.".format(self._name))
                                    elif self._send_commands[0] in self._query_commands:
                                        self.logger.warning("Parsing Input {}: Giving up {}, because no answer received.".format(self._name, temp_sendcommand))
                                    self._send_commands.pop(0)
                                    self.logger.log(VERBOSE1, "Parsing Input {}: Send commands are now: {}".format(self._name, self._send_commands))
                                elif depending is True:
                                    self._resend_counter = 0
                                    self.logger.log(VERBOSE1, "Parsing Input {}: Resetting Resend Counter because dependency not fulfilled.".format(self._name))
                                    try:
                                        if not self._send_commands[0] in self._query_commands and not self._send_commands == []:
                                            self._sendingcommand = self._send_commands[0]
                                            self.logger.warning("Parsing Input {}: Reset item {} because dependency not fulfilled.".format(self._name, self._sendingcommand))
                                            self._resetitem('')
                                        self._sendingcommand = 'gaveup'
                                        if self._send_commands[0] not in self._query_commands and not self._send_commands[0] in self._special_commands['Display']['Command'] and not self._sendingcommand == 'gaveup':
                                            self._keep_commands[time.time()] = self._send_commands[0]
                                            self.logger.debug("Parsing Input {}: Removing item from send command, storing in keep commands: {}.".format(self._name, self._keep_commands))
                                        elif self._send_commands[0] in self._query_commands:
                                            self.logger.debug("Parsing Input {}: Giving	 up {}, because no answer received.".format(self._name, self._sendingcommand))
                                        self._send_commands.pop(0)
                                        self.logger.log(VERBOSE1, "Parsing Input {}: Keepcommands: {}. Sendcommands: {}".format(
                                            self._name, self._keep_commands, self._send_commands))
                                    except Exception as err:
                                        self.logger.log(VERBOSE1, "Parsing Input {}: Nothing to reset as send commands is empty: {}. Message: {}".format(self._name, self._send_commands, err))
                                if not self._sendingcommand == 'gaveup':
                                    to_send = 'query' if (self._resend_counter % 2 == 1 and not self._send_commands[0].split(',')[1] == '') else 'command'
                                    self.logger.debug("Parsing Input {}: Requesting {} from {} because response was {}. Resend Counter: {}".format(
                                        self._name, to_send, self._send_commands[0], data, self._resend_counter))
                                    self._wait(self._resend_wait)
                        except Exception as err:
                            self.logger.warning("Parsing Input {}: Problems with checking for expected response. Error: {}".format(self._name, err))

                    updated = 0
                    if not data == 'ERROR' and data not in self._error_response:
                        self.logger.log(VERBOSE1, "Parsing Input {}: Starting to compare values for data {} with {}.".format(self._name, data, sorted_response_commands))

                        for key in sorted_response_commands:
                            comparekey = self._response_wildcards['wildcard'][key]
                            self.logger.log(VERBOSE2, "Parsing Input {}: Starting to compare values for data {} with key: {} (before wildcard processing: {}).".format(self._name, data, key, comparekey))
                            if data == comparekey and not self._send_commands == []:
                                tempcommands = []
                                for entry in self._send_commands:
                                    if comparekey not in entry:
                                        tempcommands.append(entry)
                                self._send_commands = tempcommands
                                if self._sendingcommand not in self._send_commands and not self._send_commands == []:
                                    self._sendingcommand = self._send_commands[0]
                                self.logger.debug("Parsing Input {}: Response is identical to expected response. Cleaned Send Commands: {}".format(self._name, self._send_commands))
                            for entry in self._response_commands[comparekey]:
                                # commandlength = entry[1]
                                valuelength = entry[0]
                                responseposition = entry[2]
                                item = entry[3]
                                expectedtype = entry[7]
                                index = data.find(key)
                                self.logger.log(VERBOSE2, "Parsing Input {}: Entry: {}, Valuelength: {}, Expected Type: {}. ".format(
                                    self._name, entry, valuelength, expectedtype))
                                # if not index == -1:
                                if index == 0:
                                    sametype = False
                                    function = entry[4]
                                    zone = entry[5]
                                    if data.startswith(self._special_commands['Display']['Command']) and not self._special_commands['Display']['Command'] == '':
                                        receivedvalue = self._convertvalue(data[responseposition:responseposition + valuelength], expectedtype, False, valuelength, self._special_commands['Display']['Command'])
                                        self.logger.debug("Parsing Input {}: Displaycommand found in response {}. Converted to {}.".format(self._name, data, receivedvalue))

                                    elif data.startswith(tuple(self._special_commands['Nowplaying']['Command'])) and not self._special_commands['Nowplaying']['Command'] == '':
                                        self.logger.debug("Parsing Input {}: Now playing info found in response {}.".format(self._name, data))
                                        try:
                                            m = re.search('"(.+?)"', data)
                                            if m:
                                                receivedvalue = m.group(1)
                                            else:
                                                receivedvalue = ''
                                        except Exception as err:
                                            self.logger.debug("Parsing Input {}: Problems reading Now Playing info. Error:{}".format(self._name, err))
                                    elif data.startswith(tuple(self._special_commands['Speakers']['Command'])) and not self._special_commands['Speakers']['Command'] == '':
                                        self.logger.debug("Parsing Input {}: Speakers info found in response {}. Command: {}".format(
                                            self._name, data, self._special_commands['Speakers']['Command']))
                                        receivedvalue = self._convertvalue(data[responseposition:responseposition + valuelength], expectedtype, False, valuelength, self._special_commands['Speakers']['Command'])
                                        try:
                                            for speakercommand in self._special_commands['Speakers']['Command']:
                                                for zone in self._items_speakers:
                                                    for speakerlist in self._items_speakers[zone]:
                                                        speakerAB = sum(map(int, self._items_speakers[zone].keys()))
                                                        self.logger.debug("Parsing Input {}: Received value: {}. Speaker {}. SpeakerAB: {}".format(
                                                            self._name, receivedvalue, speakerlist, speakerAB))
                                                        if receivedvalue == int(speakerlist) or receivedvalue == speakerAB:
                                                            for speaker in self._items_speakers[zone][speakerlist]['Item']:
                                                                self.logger.info("Parsing Input {}: Speaker {} is on.".format(self._name, speaker))
                                                                speaker(1, 'AVDevice', self._tcp)
                                                        else:
                                                            for speaker in self._items_speakers[zone][speakerlist]['Item']:
                                                                self.logger.info("Parsing Input {}: Speaker {} is off.".format(self._name, speaker))
                                                                speaker(0, 'AVDevice', self._tcp)

                                        except Exception as err:
                                            self.logger.warning("Parsing Input {}: Problems reading Speakers info. Error:{}".format(self._name, err))
                                    else:
                                        origvalue = value = receivedvalue = data[responseposition:responseposition + valuelength]
                                        self.logger.log(VERBOSE1, "Parsing Input {}: Neither Display nor Now Playing in response. receivedvalue: {}.".format(
                                            self._name, receivedvalue))

                                        invert = True if entry[6].lower() in ['1', 'true', 'yes', 'on'] else False
                                        if not receivedvalue == '':
                                            receivedvalue = self._convertvalue(value, expectedtype, invert, valuelength, 'data')
                                    try:
                                        if isinstance(receivedvalue, eval(expectedtype)):
                                            sametype = True
                                        else:
                                            sametype = False
                                    except Exception as err:
                                        if receivedvalue == '' and expectedtype == 'empty':
                                            sametype = True
                                            receivedvalue = True
                                        else:
                                            sametype = False
                                            self.logger.log(VERBOSE2, "Parsing Input {}: Cannot compare {} with {}. Message: {}.".format(
                                                self._name, receivedvalue, expectedtype, err))
                                    if sametype is False:
                                        self.logger.log(VERBOSE1, "Parsing Input {}: Receivedvalue {} does not match type {} - ignoring it.".format(self._name, receivedvalue, expectedtype))
                                    else:
                                        self.logger.log(VERBOSE1, "Parsing Input {}: Receivedvalue {} does match type {} - going on.".format(self._name, receivedvalue, expectedtype))
                                        self._displayignore(data, receivedvalue, 'parsing')
                                        value = receivedvalue

                                        self.logger.debug("Parsing Input {}: Found key {} in response at position {} with value {}.".format(
                                            self._name, key, responseposition, value))
                                        deletekeep = []
                                        for entry in self._keep_commands:
                                            self.logger.log(VERBOSE1, "Parsing Input {}: Testing Keep Command entry {} with age of {}s".format(
                                                self._name, entry, int(time.time() - entry)))
                                            if data in self._keep_commands.get(entry).split(',')[2].split('|'):
                                                self.logger.debug("Parsing Input {}: Removing {} from Keep Commands {} because corresponding value received.".format(
                                                    self._name, entry, self._keep_commands))
                                                deletekeep.append(entry)
                                            elif time.time() - entry >= self._secondstokeep:
                                                self.logger.debug("Parsing Input {}: Removing {} from Keep Commands {} because age is {}s.".format(
                                                    self._name, entry, self._keep_commands, int(time.time() - entry)))
                                                deletekeep.append(entry)
                                        for todelete in deletekeep:
                                            self._keep_commands.pop(todelete)
                                        newvalue = self._translate(origvalue, entry[9], 'parse')
                                        if not newvalue == '' and not newvalue is None:
                                            value = newvalue
                                        if function in self._items[zone].keys():
                                            self._items[zone][function]['Value'] = value
                                            self.logger.log(VERBOSE1, "Parsing Input {}: Updated Item dict {} with value {}.".format(
                                                self._name, function, value))

                                        item(value, 'AVDevice', self._tcp) #TOTEST
                                        self.logger.debug("Parsing Input {}: Updated Item {} with {} Value: {}.".format(
                                            self._name, item, expectedtype, value))
                                        if function in self._items[zone].keys():
                                            self._checkdependency('{}, {}, {}'.format(zone, function, value), 'checkquery')

                                        # TOTEST
                                        try:
                                            testcommand = data.split('?')[0]
                                            commandstarts = []
                                            for entry in self._response_commands:
                                                if entry.split('?')[0] in testcommand:
                                                    commandstarts.append(entry.split('?')[0])

                                            self.logger.log(VERBOSE1, "Parsing Input {}: Commandstarts {}. testcommand {}".format(self._name, commandstarts, testcommand))
                                            if len(commandstarts) == 1:
                                                updated = 1
                                            elif len(commandstarts) >= 1:
                                                updated = 1
                                            else:
                                                updated = 0
                                        except Exception as err:
                                            self.logger.error("Parsing Input {}: Problem with new tests {}".format(self._name, err))
                                        self._wait(0.15)

                                        if updated == 1:
                                            self.logger.log(VERBOSE1, "Parsing Input {}: Updated all relevant items from item {}. step 1".format(self._name, item))
                                            break
                                    if updated == 1:
                                        self.logger.log(VERBOSE1, "Parsing Input {}: Updated all relevant items from {}. step 2".format(self._name, item))
                                        break
                                elif key.lower() == 'string':
                                    value = data
                                    if value.startswith(tuple(sorted_response_commands)):
                                        self.logger.log(VERBOSE1, "Parsing Input {}: Found string for Item {} with Value {} but ignored because it is a legit response for another command.".format(
                                            self._name, item, value))
                                        pass
                                    else:
                                        item(value, 'AVDevice', self._tcp)
                                        self._wait(0.15)
                                        self.logger.debug("Parsing Input {}: Updating item {} with value {}".format(self._name, item, value))
                                        break
                                if updated == 1:
                                    self.logger.log(VERBOSE1, "Parsing Input {}: Updated all relevant items from {}. step 3".format(self._name, item))
                                    break
                            if updated == 1:
                                self.logger.log(VERBOSE1, "Parsing Input {}: Updated all relevant items from {}. step 4".format(self._name, item))
                                break
                        self.logger.log(VERBOSE2, "Parsing Input {}: Finished comparing values.".format(self._name))
                        if self._send_commands == []:
                            self._sendingcommand = 'done'
            except Exception as err:
                self.logger.error("Parsing Input {}: Problems parsing input. Error: {} on {}".format(self._name, err, sys.exc_info()[-1].tb_lineno))
                # sys.exc_info()[-1].tb_lineno
            finally:
                if self._send_commands == []:
                    self._displayignore('', None, 'parsing_final')
                elif not self._send_commands == [] and data == 'waiting':
                    self.logger.log(VERBOSE2, "Parsing Input {}: Waiting for response..".format(self._name))
                elif not self._send_commands == [] and not data == 'waiting':
                    reorderlist = []
                    index = 0
                    for command in self._send_commands:
                        command = command.split(';')[0]
                        if command in self._query_commands:
                            reorderlist.append(command)
                        elif command in self._power_commands:
                            self.logger.log(VERBOSE1, "Parsing Input {}: Ordering power command {} to first position.".format(self._name, command))
                            reorderlist.insert(0, command)
                            index += 1
                        else:
                            reorderlist.insert(index, command)
                            self.logger.log(VERBOSE1, "Parsing Input {}: Adding command {} to position {}.".format(self._name, command, index))
                            index += 1
                    self._send_commands = reorderlist
                    self.logger.debug('Parsing Input {}: Newly sorted send commands at end of parsing: {}'.format(self._name, self._send_commands))
                    if self._is_connected == []:
                        for command in self._send_commands:
                            self.logger.log(VERBOSE1, "Parsing Input {}: Going to reset in the end because connection is lost: {}.".format(self._name, command))
                            if command not in self._query_commands and command not in self._special_commands['Display']['Command'] and not self._sendingcommand == 'gaveup':
                                self._keep_commands[time.time()] = self._sendingcommand = command
                                self.logger.debug("Parsing Input {}: Removing item {} from send command because not connected, storing in keep commands: {}.".format(
                                    self._name, command, self._keep_commands))
                            self._resetitem('')
                            self._send_commands.pop(0)
                            self.logger.debug('Parsing Input {}: First entry from send_commands removed. Send commands are now: {}'.format(
                                self._name, self._send_commands))
                    else:
                        sending = self._send('{}'.format(to_send), 'parseinput_final')
                        self.logger.log(VERBOSE1, "Parsing Input {}: Sending again because list is not empty yet. Sending return is {}.".format(
                            self._name, sending))
                    if 'Serial' in self._is_connected and connectionproblem is True:
                        self._is_connected.remove('Serial')
                        try:
                            self._is_connected.remove('Connecting')
                        except Exception:
                            pass
                        self._trigger_reconnect = True
                    if 'TCP' in self._is_connected and connectionproblem is True:
                        self._is_connected.remove('TCP')
                        try:
                            self._is_connected.remove('Connecting')
                        except Exception:
                            pass
                        self._trigger_reconnect = True
                    if self._trigger_reconnect is True and self._is_connected == []:
                        self.logger.log(VERBOSE1, "Parsing Input {}: Trying to connect while parsing item".format(self._name))
                        self.connect('parse_dataerror')

    def _createresponsecommand(self, type, commandinfo, reverseinfo, value):
        self.logger.log(VERBOSE1, "Updating Item {}: Create response command with type {}, command {}, reverse {}, value {}".format(self._name, type, commandinfo, reverseinfo, value))
        try:
            splitresponse = commandinfo[4].split('|')
        except Exception:
            splitresponse = commandinfo.split('|')
        try:
            splitreverse = reverseinfo[4].split('|')
        except Exception:
            splitreverse = []
        responselist = []
        reverselist = []
        count = 0
        for splitre in splitresponse:
            valuelength = reverselength = splitre.count('*')
            if valuelength > 0 or 'R' in commandinfo[5]:
                if type == 'off':
                    replacedresponse = ''
                    replacedreverse = ''
                    try:
                        replacedresponse = splitre.replace('*******', 'STANDBY')
                        replacedresponse = replacedresponse.replace('*****', 'CLOSE')
                        replacedresponse = replacedresponse.replace('****', 'CLOS')
                        replacedresponse = replacedresponse.replace('***', 'OFF')
                        if commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
                            replacedvalue = '1'
                            reversevalue = '0'
                        else:
                            replacedvalue = '0'
                            reversevalue = '1'
                    except Exception as err:
                        self.logger.debug("Updating Item {}: Problems replacing * for off command: {}".format(self._name, err))
                    try:
                        reverselength = splitreverse[count].count('*')
                        replacedreverse = splitreverse[count].replace('****', 'OPEN')
                        replacedreverse = replacedreverse.replace('**', 'ON')
                    except Exception as err:
                        self.logger.log(VERBOSE2, "Updating Item {}: Problems replacing * for off reverse command: {}".format(self._name, err))

                    replacedresponse = replacedresponse.replace('*', replacedvalue)
                    replacedreverse = replacedreverse.replace('*', reversevalue)
                    if not replacedresponse == '':
                        responselist.append('{},{},{}'.format(replacedresponse, commandinfo[9], valuelength))
                    if not replacedreverse == '':
                        reverselist.append('{},{},{}'.format(replacedreverse, commandinfo[9], reverselength))
                elif type == 'on':
                    replacedresponse = ''
                    replacedreverse = ''
                    try:
                        replacedresponse = splitre.replace('****', 'OPEN')
                        replacedresponse = replacedresponse.replace('**', 'ON')
                        if commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
                            replacedvalue = '0'
                            reversevalue = '1'
                        else:
                            replacedvalue = '1'
                            reversevalue = '0'
                    except Exception as err:
                        self.logger.debug("Updating Item {}: Problems replacing * for on command: {}".format(self._name, err))
                    try:
                        reverselength = splitreverse[count].count('*')
                        replacedreverse = splitreverse[count].replace('*****', 'CLOSE')
                        replacedreverse = replacedreverse.replace('****', 'CLOS')
                        replacedreverse = replacedreverse.replace('***', 'OFF')
                    except Exception as err:
                        self.logger.log(VERBOSE2, "Updating Item {}: Problems replacing * for on reverse command: {}".format(self._name, err))
                    replacedresponse = replacedresponse.replace('*', replacedvalue)
                    replacedreverse = replacedreverse.replace('*', reversevalue)
                    if not replacedresponse == '':
                        responselist.append('{},{},{}'.format(replacedresponse, commandinfo[9], valuelength))
                    if not replacedreverse == '':
                        reverselist.append('{},{},{}'.format(replacedreverse, commandinfo[9], reverselength))
                elif type == 'in_decrease':
                    replacedresponse = re.sub('[*]', '', splitre.strip())
                    if splitre.count('?') == 1:
                        replacedresponse = re.sub('[?]', '', replacedresponse)
                    try:
                        reverselength = splitreverse[count].count('*')
                        replacedreverse = re.sub('[*]', '', splitreverse[count].strip())
                        if splitreverse[count].count('?') == 1:
                            replacedreverse = re.sub('[?]', '', replacedreverse)
                    except Exception:
                        replacedreverse = ''
                    if not replacedresponse == '':
                        responselist.append('{},{},{}'.format(replacedresponse, commandinfo[9], valuelength))
                    if not replacedreverse == '':
                        reverselist.append('{},{},{}'.format(replacedreverse, commandinfo[9], reverselength))
                elif type == 'set':
                    replacedresponse = ''
                    value
                    try:
                        newvalue = self._translate(value, commandinfo[10], 'update')
                        self.logger.log(VERBOSE2, "Updating Item {}: Translated value: {}".format(self._name, newvalue))
                    except Exception:
                        newvalue = None
                    if not newvalue == '' and not newvalue is None:
                        value = newvalue
                    try:
                        value = eval(value.lstrip('0'))
                    except Exception:
                        pass
                    if value == 0 and 'bool' in commandinfo[9]:
                        value = 'OFF'
                        try:
                            replacedresponse = re.sub('\*+', '{}'.format(value), splitre)
                        except Exception:
                            replacedresponse = splitre
                    elif (isinstance(value, int) and 'int' in commandinfo[9]) or (isinstance(value, float) and 'float' in commandinfo[9]):
                        try:
                            value = max(min(value, int(commandinfo[8])), int(commandinfo[7]))
                        except Exception as err:
                            try:
                                value = min(value, int(commandinfo[8]))
                            except Exception as err:
                                pass
                        if splitre.count('*') > 1:
                            anzahl = splitre.count('*')
                            replacedresponse = re.sub(r'(\*)\1+', '{0:0{1}d}'.format(value, anzahl), splitre)
                        elif splitre.count('*') == 1:
                            value = max(min(value, 9), 0)
                            replacedresponse = splitre.replace('*', '{0:01d}'.format(value))
                        else:
                            replacedresponse = splitre
                    elif isinstance(value, str) and 'str' in commandinfo[9]:
                        value = value.upper()
                        try:
                            replacedresponse = splitre.replace('*', '{}'.format(value), 1)
                            replacedresponse = replacedresponse.replace('*', '')
                        except Exception:
                            replacedresponse = splitre
                    else:
                        self.logger.log(VERBOSE2, "Updating Item {}: There might be something wrong with replacing the response.".format(self._name))
                    if not replacedresponse == '':
                        responselist.append('{},{},{}'.format(replacedresponse, commandinfo[9], valuelength))
                elif type == 'power':
                    if commandinfo[6].lower() in ['1', 'true', 'yes', 'on']:
                        replacedvalue = '0'
                    else:
                        replacedvalue = '1'
                    replacedresponse = splitre.replace('*', replacedvalue)
                    responselist.append('{},{},{}'.format(replacedresponse, commandinfo[9], valuelength))
                else:
                    replacedresponse = splitre.split('*')[0].strip()
                    if splitre.count('?') == 1:
                        replacedresponse = re.sub('[?]', '', replacedresponse)
                    responselist.append('{},{},{}'.format(replacedresponse, commandinfo[9], valuelength))
            else:
                replacedresponse = splitre
                try:
                    replacedreverse = splitreverse[count]
                    reverselength = splitreverse[count].count('*')
                except Exception:
                    replacedreverse = ''
                if not replacedresponse == '':
                    responselist.append('{},{},{}'.format(replacedresponse, commandinfo[9], valuelength))
                if not replacedreverse == '':
                    reverselist.append('{},{},{}'.format(replacedreverse, commandinfo[9], reverselength))
            count += 1

        replacedresponse = "|".join(responselist)
        replacedreverse = "|".join(reverselist)

        if not replacedreverse == '':
            self.logger.log(VERBOSE2, "Updating Item {}: Replaced response: {}, replaced reverse: {}. Type: {}".format(self._name, replacedresponse, replacedreverse, type))
            return replacedresponse, replacedreverse
        else:
            self.logger.log(VERBOSE2, "Updating Item {}: Replaced response: {}. Type: {}".format(self._name, replacedresponse, type))
            return replacedresponse

    # Updating items based on value changes via Visu, CLI, etc.
    def update_item(self, item, caller=None, source=None, dest=None):
        if self.alive:
            if caller in self._update_exclude:
                self.logger.debug("Updating Item {}: Not updating {} because caller {} is excluded.".format(self._name, item, caller))
            if not caller == 'AVDevice' and not caller in self._update_exclude:
                try:
                    emptycommand = False
                    depending = True
                    value = item()
                    self.logger.debug("Updating Item {}: {} trying to update {}".format(self._name, caller, item))
                    self.logger.log(VERBOSE1, "Updating Item {}: Starting to update item {}. Caller: {}, Source: {}. Destination: {}. Reconnectrigger is {}".format(self._name, item, caller, source, dest, self._trigger_reconnect))
                    try:
                        depending = self._checkdependency(item, 'update')
                    except Exception:
                        depending = False
                    self.logger.log(VERBOSE1, "Updating Item {}: Depending is {}.".format(self._name, depending))
                    if (self.has_iattr(item.conf, 'avdevice') and self.get_iattr_value(item.conf, 'avdevice') == 'reload') or (self.has_iattr(item.conf, 'avdevice_zone0') and self.get_iattr_value(item.conf, 'avdevice_zone0') == 'reload'):
                        self._initialize()
                        self.logger.info("Initializing {}: Reloaded Text file and functions".format(self._name))
                        depending = False

                    # connect if necessary
                    if self._trigger_reconnect is True:
                        self.logger.log(VERBOSE1, "Updating Item {}: Trying to connect while updating item".format(self._name))
                        self.connect('update_item')
                    if item == self._dependson:
                        depending = self._checkdependency('', 'dependitem')

                    for zone in range(0, self._number_of_zones + 1):
                        command = ''
                        letsgo = False
                        try:
                            if self.has_iattr(item.conf, 'avdevice'):
                                command = self.get_iattr_value(item.conf, 'avdevice')
                                if command in self._items['zone{}'.format(zone)].keys():
                                    zoneX = True
                                else:
                                    self.logger.debug("Updating Item {}: Corresponding Item for command {} in zone {} does not exist. Skipping.".format(self._name, command, zone))
                                    zoneX = False
                            elif self.has_iattr(item.conf, 'avdevice_zone{}_speakers'.format(zone)):
                                command = 'speakers'
                                zoneX = True
                                self.logger.debug("Updating Item {}: Command is {}. Zone is {}".format(self._name, command, zone))
                            else:
                                zoneX = False
                        except Exception:
                            zoneX = False
                        try:
                            if self.has_iattr(item.conf, 'avdevice_zone{}'.format(zone)) or zoneX is True:
                                letsgo = True
                        except Exception:
                            if item == 'statusupdate' and zone == 0:
                                letsgo = True
                            else:
                                letsgo = False

                        if letsgo is True:
                            if zoneX is False:
                                try:
                                    command = self.get_iattr_value(item.conf, 'avdevice_zone{}'.format(zone))
                                except Exception:
                                    command = 'statusupdate'
                                    value = True
                            command_on = '{} on'.format(command)
                            command_off = '{} off'.format(command)
                            command_set = '{} set'.format(command)
                            command_increase = '{} increase'.format(command)
                            command_decrease = '{} decrease'.format(command)
                            updating = True
                            sending = True

                            try:
                                if command is None:
                                    command = '{} on'.format(command)
                                if command is None or command == 'None on':
                                    command = '{} off'.format(command)
                                if command is None or command == 'None off':
                                    command = '{} set'.format(command)
                                if command is None or command == 'None set':
                                    command = '{} increase'.format(command)
                                if command is None or command == 'None increase':
                                    command = '{} decrease'.format(command)
                                cond1 = self._functions['zone{}'.format(zone)][command][5].lower() == 'w'
                                cond2 = value in [False, '0', 0, 'False']
                                if cond1 and cond2:
                                    self.logger.debug("Updating Item {}: Skipping command {} with WRITE flag because it's set to False".format(
                                        self._name, command))
                                    break
                                if self._functions['zone{}'.format(zone)][command][2] == '':
                                    emptycommand = True
                                    if not self._is_connected == []:
                                        self.logger.log(VERBOSE1, "Updating Item {}: Function is empty. Command: {} Item: {}".format(
                                            self._name, command, item))
                                    if command == 'statusupdate':
                                        try:
                                            checkvalue = item()
                                        except Exception:
                                            checkvalue = True
                                        self.logger.log(VERBOSE1, "Updating Item {}: Statusupdate. Checkvalue: {}. Display Ignore: {}".format(
                                            self._name, checkvalue, self._special_commands['Display']['Ignore']))
                                        if (checkvalue is True or caller == 'Init') and not self._special_commands['Display']['Ignore'] >= 5:
                                            if not self._is_connected == []:
                                                self._addfrom_keepcommands('statusupdate', 'all')
                                            for query in self._query_commands:
                                                if caller == 'Init':
                                                    depending = self._checkdependency(query, 'initupdate')
                                                else:
                                                    depending = self._checkdependency(query, 'statusupdate')
                                                if query not in self._send_commands and depending is False:
                                                    self._send_commands.append(query)
                                            self._reconnect_counter = 0
                                            self._trigger_reconnect = True

                                            if not self._is_connected == []:
                                                self.logger.log(VERBOSE1, "Updating Item {}: Updating status. Sendcommands: {}. Reconnecttrigger: {}. Display Ignore: {}".format(self._name, self._send_commands, self._trigger_reconnect, self._special_commands['Display']['Ignore']))
                                        elif checkvalue is False and not self._special_commands['Display']['Ignore'] >= 5:
                                            depending = self._checkdependency(item, 'globaldepend')
                                            if depending is True or self._is_connected == [] or self._is_connected == ['Connecting'] and (self._depend0_volume0 is True or self._depend0_power0 is True):
                                                self._resetondisconnect('statusupdate')
                                        elif self._special_commands['Display']['Ignore'] >= 5:
                                            sending = False

                                    updating = False
                                if self._functions['zone{}'.format(zone)][command][5].lower() == 'r':
                                    updating = False
                                    commandinfo = self._functions['zone{}'.format(zone)][command]
                                    if commandinfo[2] == '' and commandinfo[3] == '':
                                        self.logger.warning("Updating Item {}: Function is read only and empty. Doing nothing. Command: {}".format(self._name, command))
                                    else:
                                        self.logger.info("Updating Item {}: Function is read only. Sending query. Command: {}".format(
                                            self._name, command))

                                        responsecommand = self._createresponsecommand('readonly', commandinfo, '', '')
                                        appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], responsecommand, item.id())
                                        if appendcommand in self._send_commands:
                                            self.logger.debug("Updating Item {}: Readonly Command {} already in Commandlist. Ignoring.".format(self._name, appendcommand))
                                        elif appendcommand not in self._query_commands and not appendcommand in self._special_commands['Display']['Command'] and depending is True:
                                            self._keep_commands[time.time()] = appendcommand
                                            self.logger.debug("Updating Item {}: Not adding readonly command {} because dependency is not fullfilled, storing in keep commands: {}.".format(self._name, appendcommand, self._keep_commands))
                                        else:
                                            self.logger.debug("Updating Item {}: Readonly. Updating Zone {} Commands {} for {}".format(
                                                self._name, zone, self._send_commands, item))
                                            self._send_commands.append(appendcommand)

                            except Exception as err:
                                self.logger.log(VERBOSE2, "Updating Item {}: Command {} is a standard command. Updating: {}. Message: {}".format(self._name, command, updating, err))

                            if updating is True:
                                self.logger.debug("Updating Item {}: {} set {} to {} for {} in zone {}".format(
                                    self._name, caller, command, value, item, zone))
                                self._trigger_reconnect = True
                                setting = False
                                checkquery = False
                                if command in self._functions['zone{}'.format(zone)]:
                                    commandinfo = self._functions['zone{}'.format(zone)][command]
                                    replacedresponse = self._createresponsecommand('standard', commandinfo, '', '')
                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    if appendcommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Command {} already in Commandlist. Ignoring.".format(
                                            self._name, appendcommand))
                                    elif appendcommand not in self._query_commands and not appendcommand in self._special_commands['Display']['Command'] and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug("Updating Item {}: Not adding command {} because dependency is not fullfilled, storing in keep commands: {}.".format(self._name, appendcommand, self._keep_commands))
                                    else:
                                        self.logger.debug("Updating Item {}: Updating Zone {} Commands {} for {}".format(
                                            self._name, zone, self._send_commands, item))
                                        self._send_commands.append(appendcommand)
                                        checkquery = True
                                elif command_increase in self._functions['zone{}'.format(zone)]:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_increase]
                                    try:
                                        reverseinfo = self._functions['zone{}'.format(zone)][command_decrease]
                                    except Exception:
                                        try:
                                            reverseinfo = self._functions['zone{}'.format(zone)]['{} decrease'.format(command.replace('+', '-', 1))]
                                        except Exception:
                                            reverseinfo = ''
                                    replacedresponse, replacedreverse = self._createresponsecommand('in_decrease', commandinfo, reverseinfo, '')
                                    try:
                                        reverseitem = self._items['zone{}'.format(zone)][command.replace('+', '-', 1)].get('Item')
                                    except Exception:
                                        reverseitem = item.id()

                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    reversecommand = '{},{},{};{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, reverseitem)

                                    self.logger.log(VERBOSE2, "Updating Item {}: Appendcommand increase: {}, Reversecommand: {}, Send Commands: {}".format(
                                        self._name, appendcommand, reversecommand, self._send_commands))
                                    if appendcommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Increase Command {} already in Commandlist. Ignoring.".format(
                                            self._name, appendcommand))
                                    elif reversecommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Command Decrease {} already in Commandlist {}. Replacing with Command Increase {}.".format(
                                            self._name, reversecommand, self._send_commands, appendcommand))
                                        self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: New Commandlist {}.".format(
                                            self._name, self._send_commands))
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1, "Updating Item {}: Resetting Resend Counter due to updated command.".format(self._name))
                                    elif appendcommand not in self._query_commands and not appendcommand in self._special_commands['Display']['Command'] and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug("Updating Item {}: Not adding increase command {} because dependency is not fullfilled, storing in keep commands: {}.".format(self._name, appendcommand, self._keep_commands))
                                    else:
                                        self.logger.debug("Updating Item {}: Updating Zone {} Command Increase {} for {}".format(
                                            self._name, zone, self._send_commands, item))
                                        self._send_commands.append(appendcommand)
                                elif command_decrease in self._functions['zone{}'.format(zone)]:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_decrease]
                                    try:
                                        reverseinfo = self._functions['zone{}'.format(zone)][command_increase]
                                    except Exception:
                                        try:
                                            reverseinfo = self._functions['zone{}'.format(zone)]['{} increase'.format(command.replace('-', '+', 1))]
                                        except Exception:
                                            reverseinfo = ''
                                    replacedresponse, replacedreverse = self._createresponsecommand('in_decrease', commandinfo, reverseinfo, '')
                                    try:
                                        reverseitem = self._items['zone{}'.format(zone)][command.replace('-', '+', 1)].get('Item')
                                    except Exception:
                                        reverseitem = item.id()

                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    reversecommand = '{},{},{};{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, reverseitem)

                                    self.logger.log(VERBOSE2, "Updating Item {}: Appendcommand decrease: {}, Reversecommand: {}, Send Commands: {}".format(
                                        self._name, appendcommand, reversecommand, self._send_commands))
                                    if appendcommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Decrease Command {} already in Commandlist. Ignoring.".format(
                                            self._name, appendcommand))
                                    elif reversecommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Command Increase {} already in Commandlist {}. Replacing with Command Decrease {}.".format(
                                            self._name, reversecommand, self._send_commands, appendcommand))
                                        self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: New Commandlist {}.".format(
                                            self._name, self._send_commands))
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1, "Updating Item {}: Resetting Resend Counter due to updated command.".format(self._name))
                                    elif appendcommand not in self._query_commands and not appendcommand in self._special_commands['Display']['Command'] and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug("Updating Item {}: Not adding decrease command {} because dependency is not fullfilled, storing in keep commands: {}.".format(self._name, appendcommand, self._keep_commands))
                                    else:
                                        self.logger.debug("Updating Item {}: Updating Zone {} Command Decrease {} for {}".format(
                                            self._name, zone, self._send_commands, item))
                                        self._send_commands.append(appendcommand)

                                elif command_on in self._functions['zone{}'.format(zone)] and isinstance(value, bool) and value == 1:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_on]
                                    reverseinfo = self._functions['zone{}'.format(zone)][command_off]
                                    replacedresponse, replacedreverse = self._createresponsecommand('on', commandinfo, reverseinfo, '')

                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    reversecommand = '{},{},{};{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, item.id())

                                    self.logger.log(VERBOSE2, "Updating Item {}: Appendcommand on: {}, Reversecommand: {}, Send Commands: {}".format(
                                        self._name, appendcommand, reversecommand, self._send_commands))
                                    if appendcommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Command On {} already in Commandlist {}. Ignoring.".format(
                                            self._name, appendcommand, self._send_commands))
                                    elif reversecommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Command Off {} already in Commandlist {}. Replacing with Command On {}.".format(
                                            self._name, reversecommand, self._send_commands, appendcommand))
                                        self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: New Commandlist {}.".format(
                                            self._name, self._send_commands))
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1, "Updating Item {}: Resetting Resend Counter due to new command.".format(self._name))
                                    elif appendcommand not in self._query_commands and not appendcommand in self._special_commands['Display']['Command'] and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug("Updating Item {}: Not adding on command {} because dependency is not fullfilled, storing in keep commands: {}.".format(self._name, appendcommand, self._keep_commands))
                                    else:
                                        self._send_commands.append(appendcommand)
                                        self._sendingcommand = appendcommand
                                        checkquery = True
                                        self.logger.log(VERBOSE1, "Updating Item {}: Update Zone {} Command On {} for {}".format(
                                            self._name, zone, commandinfo[2], item))
                                    if command_on == 'power on' and checkquery == True:
                                        self._addfrom_keepcommands('powercommand', 'zone{}'.format(zone))
                                        self.logger.debug("Updating Item {}: Command Power On for zone: {}. Appending relevant query commands.".format(self._name, zone))
                                        checkquery = False
                                        for query in self._query_zonecommands['zone{}'.format(zone)]:
                                            depending = self._checkdependency(query, 'statusupdate')
                                            if query not in self._send_commands and depending is False:
                                                self._send_commands.append(query)

                                elif command_off in self._functions['zone{}'.format(zone)] and isinstance(value, bool) and value == 0:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_off]
                                    reverseinfo = self._functions['zone{}'.format(zone)][command_on]
                                    replacedresponse, replacedreverse = self._createresponsecommand('off', commandinfo, reverseinfo, '')

                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    reversecommand = '{},{},{};{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, item.id())

                                    self.logger.log(VERBOSE1, "Updating Item {}: Appendcommand off: {}. Reversecommand: {} Send Commands: {}".format(
                                        self._name, appendcommand, reversecommand, self._send_commands))
                                    if appendcommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Command Off {} already in Commandlist {}. Ignoring.".format(
                                            self._name, appendcommand, self._send_commands))
                                    elif reversecommand in self._send_commands:
                                        self.logger.debug("Updating Item {}: Command On {} already in Commandlist {}. Replacing with Command Off {}.".format(
                                            self._name, reversecommand, self._send_commands, appendcommand))
                                        self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: New Commandlist {}.".format(
                                            self._name, self._send_commands))
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1, "Updating Item {}: Resetting Resend Counter due to new command.".format(self._name))
                                    elif appendcommand not in self._query_commands and not appendcommand in self._special_commands['Display']['Command'] and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug("Updating Item {}: Not adding off command {} because dependency is not fullfilled, storing in keep commands: {}.".format(self._name, appendcommand, self._keep_commands))
                                    else:
                                        self._send_commands.append(appendcommand)
                                        self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: Update Zone {} Command Off {} for {}".format(
                                            self._name, zone, commandinfo[2], item))
                                        checkquery = True

                                elif command_set in self._functions['zone{}'.format(zone)]:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_set]
                                    newvalue = None
                                    if not command.lower().startswith('speakers'):
                                        response = self._createresponsecommand('set', commandinfo, '', value)
                                    try:
                                        if isinstance(value, str):
                                            newvalue = value.lower()
                                        newvalue = self._translate(newvalue, commandinfo[10], 'update')
                                        self.logger.log(VERBOSE2, "Updating Item {}: Translated value: {}".format(self._name, value))
                                    except Exception:
                                        pass
                                    if not newvalue is None and not newvalue == '':
                                        value = newvalue
                                    try:
                                        value = eval(value.lstrip('0'))
                                    except Exception:
                                        pass
                                    if value == 0 and 'bool' in commandinfo[9]:
                                        setting = True
                                        value = 'OFF'
                                        try:
                                            command_re = re.sub('\*+', '{}'.format(value), commandinfo[2])
                                        except Exception:
                                            command_re = commandinfo[2]
                                        self.logger.debug("Updating Item {}: Value 0 is converted to OFF. command_re: {}, response: {}".format(self._name, command_re, response))

                                    elif (isinstance(value, int) and 'int' in commandinfo[9]) or (isinstance(value, float) and 'float' in commandinfo[9]):
                                        setting = True
                                        try:
                                            value = max(min(value, int(commandinfo[8])), int(commandinfo[7]))
                                            self.logger.debug("Updating Item {}: value limited to min {} and max {}.".format(
                                                self._name, commandinfo[7], commandinfo[8]))
                                        except Exception as err:
                                            try:
                                                value = min(value, int(commandinfo[8]))
                                                self.logger.debug("Updating Item {}: value limited to max {}.".format(
                                                    self._name, commandinfo[8]))
                                            except Exception as err:
                                                self.logger.debug(
                                                "Updating Item {}: Value limited to specific number of digits".format(self._name))
                                        if commandinfo[2].count('*') > 1:
                                            anzahl = commandinfo[2].count('*')
                                            self.logger.log(
                                                VERBOSE1, "Updating Item {}: Value has to be {} digits.".format(self._name, anzahl))
                                            value = max(min(value, int(re.sub('[^0-9]', '', re.sub('\*', '9', commandinfo[2])))), 0)
                                            command_re = re.sub(r'(\*)\1+', '{0:0{1}d}'.format(value, anzahl), commandinfo[2])
                                        elif commandinfo[2].count('*') == 1:
                                            if command.lower().startswith('speakers'):
                                                if isinstance(self._items['zone{}'.format(zone)]['speakers']['Item'], list):
                                                    currentvalue = int(self._items['zone{}'.format(zone)]['speakers']['Item']())
                                                else:
                                                    currentvalue = int(self._items['zone{}'.format(zone)]['speakers']['Item']())
                                                    self.logger.log(VERBOSE1, "Updating Item {}: Speaker Command. Only one item.".format(self._name))
                                                multiply = -1 if item() == 0 else 1
                                                multiply = 0 if (currentvalue == 0 and item() == 0) else multiply
                                                try:
                                                    value = abs(int(self.get_iattr_value(item.conf, 'avdevice_zone{}_speakers'.format(zone))))
                                                except Exception as err:
                                                    self.logger.warning("Updating Item {}: This speaker item is not supposed to be manipulated directly.".format(self._name))
                                                    break

                                                powerinfo = self._functions['zone{}'.format(zone)]['power on']
                                                self.logger.log(VERBOSE1, "Updating Item {}: Speaker {} current value is {}. Item: {} with value {}. Multiply: {}. Value: {}".format(self._name, self._items['zone{}'.format(zone)]['speakers']['Item'], currentvalue, item, item(), multiply, value))
                                                if not currentvalue == value or multiply == -1:
                                                    value = currentvalue + (value * multiply)
                                                response = self._createresponsecommand('set', commandinfo, '', value)
                                                if value > 0:
                                                    replacedresponse = self._createresponsecommand('power', powerinfo, '', True)
                                                    try:
                                                        poweritem = self._items['zone{}'.format(zone)][powerinfo[1]].get('Item')
                                                    except Exception:
                                                        poweritem = self._items['zone0'][powerinfo[1]].get('Item')
                                                    appendcommand = '{},{},{};{}'.format(powerinfo[2], powerinfo[3], replacedresponse, poweritem.id())
                                                    self._send_commands.insert(0, appendcommand)
                                                    self._sendingcommand = appendcommand
                                                    self.logger.debug("Updating Item {}: Turning power on. powercommands is: {}".format(self._name, powerinfo))
                                            else:
                                                value = max(min(value, 9), 0)
                                            command_re = commandinfo[2].replace('*', '{0:01d}'.format(value))
                                            self.logger.log(VERBOSE1, "Updating Item {}: Value has to be 1 digit. Value is {}".format(self._name, value))

                                        elif commandinfo[2].count('*') == 0:
                                            self.logger.error("Updating Item {}: Set command {} does not have any placeholder *.".format(self._name, commandinfo))

                                    elif isinstance(value, str) and 'str' in commandinfo[9]:
                                        setting = True
                                        value = value.upper()
                                        self.logger.debug("Updating Item {}: Value has to be string. Value is {}".format(self._name, value))
                                        try:
                                            command_re = commandinfo[2].replace('*', '{}'.format(value), 1)
                                            command_re = command_re.replace('*', '')
                                        except Exception:
                                            command_re = commandinfo[2]
                                    else:
                                        setting = False
                                else:
                                    self.logger.error("Updating Item {}: Command {} not in text file!".format(
                                        self._name, command))
                                    updating = False

                                if not self._send_commands == [] and setting is True:
                                    appendcommand = '{},{},{};{}'.format(command_re, commandinfo[3], response, item.id())
                                    appending = True
                                    setting = False
                                    for sendcommand in self._send_commands:
                                        self.logger.log(VERBOSE1, "Updating Item {}: Testing send command: {}".format(self._name, sendcommand))
                                        if commandinfo[3] in sendcommand:
                                            splitfind = sendcommand.split(',', 2)[2]
                                            before = sendcommand.split(',', 2)[0:2]
                                            testvalues = []
                                            for after in splitfind.split('|'):
                                                after = [after]
                                                sendcommand_temp = ','.join(before + after)
                                                valuetype = sendcommand_temp.split(';')[0].split(',')
                                                if valuetype[len(valuetype) - 1].isdigit():
                                                    valuetype.pop(len(valuetype) - 1)
                                                try:
                                                    valuetype[3:] = [','.join(valuetype[3:])]
                                                    testvalues.append(valuetype[3])
                                                except Exception:
                                                    pass
                                            self.logger.log(VERBOSE2,
                                                            "Updating Item {}: Is expected type {} in testvalues {}?".format(
                                                                self._name, testvalues, commandinfo[9]))
                                            if commandinfo[9] in testvalues:
                                                self._sendingcommand = appendcommand
                                                self.logger.log(VERBOSE1, "Updating Item {}: Command Set {} ({}) already in Commandlist {}. Value type: {}, expected type: {}. Replaced. Sendingcommand: {}".format(self._name, command, commandinfo[3], self._send_commands, type(value), commandinfo[9], self._sendingcommand))
                                                self._send_commands[self._send_commands.index(sendcommand)] = appendcommand
                                                self._resend_counter = 0
                                                appending = False
                                                self.logger.log(VERBOSE1, "Updating Item {}: Resetting Resend Counter due to replaced command.".format(self._name))
                                                break
                                            else:
                                                self.logger.log(VERBOSE2, "Updating Item {}: Command Set {} ({}) already in Commandlist {} but value {} is not same type as {}. Continue...".format(
                                                    self._name, command, commandinfo[3], type(value), commandinfo[9], self._send_commands))
                                    if appending is True:
                                        # EINFUEGEN DEPEND TOTEST

                                        if appendcommand not in self._query_commands and not appendcommand in self._special_commands['Display']['Command'] and depending is True:
                                            self._keep_commands[time.time()] = appendcommand
                                            self.logger.debug("Updating Item {}: Not adding set command {} because dependency is not fullfilled, storing in keep commands: {}.".format(self._name, appendcommand, self._keep_commands))
                                        else:
                                            self._send_commands.append(appendcommand)
                                            self._sendingcommand = appendcommand
                                            self._resend_counter = 0
                                            checkquery = True
                                            self.logger.log(VERBOSE1, "Updating Item {}: Resetting Resend Counter because appending new set command.".format(self._name))
                                            self.logger.log(VERBOSE1, "Updating Item {}: Update Zone {} Command Set {} for {}. Command: {}".format(
                                                self._name, zone, commandinfo[2], item, command_re))
                                elif setting is True:
                                    appendcommand = '{},{},{};{}'.format(command_re, commandinfo[3], response, item.id())
                                    if appendcommand not in self._query_commands and not appendcommand in self._special_commands['Display']['Command'] and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug("Updating Item {}: Not adding set command {} because dependency is not fullfilled, storing in keep commands: {}.".format(self._name, appendcommand, self._keep_commands))
                                    else:
                                        self._send_commands.append(appendcommand)
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1, "Updating Item {}: Resetting Resend Counter because adding new set command.".format(self._name))
                                        self.logger.debug("Updating Item {}: Update Zone {} Command Set, adding to empty Commandlist {} for {}. Command: {}".format(
                                            self._name, zone, self._send_commands, item, command_re))

                                if checkquery is True:
                                    self.logger.debug("Updating Item {}: Command {} for zone: {}. Removing relevant query commands.".format(self._name, command_off, zone))
                                    self._checkdependency('zone{}, {}, {}'.format(zone, command, value), 'checkquery')
                        else:
                            command = self.get_iattr_value(item.conf, 'avdevice_zone{}'.format(zone))
                            self.logger.log(VERBOSE2, "Updating Item {}: Did not update item {} with command {} for zone {}".format(self._name, item, command, zone))
                except Exception as err:
                    self.logger.error("Updating Item {}: Problem updating item. Error: {}. Does the item exist?".format(
                        self._name, err))
                finally:
                    if not self._send_commands == []:
                        reorderlist = []
                        index = 0
                        for command in self._send_commands:
                            if command in self._query_commands:
                                reorderlist.append(command)
                            else:
                                reorderlist.insert(index, command)
                                index += 1
                        self._send_commands = reorderlist
                        self._sendingcommand = self._send_commands[0]

                    try:
                        if not self._is_connected == [] and not self._send_commands == [] and not self._is_connected == ['Connecting']:
                            self.logger.log(VERBOSE1, "Updating Item {}: Updating item {}. Command list is {}. Sendingcommand: {}. ".format(
                                self._name, item, self._send_commands, self._sendingcommand))
                            sending = self._send('command', 'updateitem')
                            self.logger.log(VERBOSE1, "Updating Item {}: Updating item {}. Command list is {}. Return from send is {}".format(
                                self._name, item, self._send_commands, sending))

                        if self._reset_onerror is True and emptycommand is False and not self._send_commands == [] and not self._sendingcommand == 'done' and self._is_connected == []:
                            if not self._send_commands[0].split(',')[0] == self._send_commands[0].split(',')[1]:
                                self.logger.log(VERBOSE1, "Updating Item {}: Sending command {}. Starting to reset".format(self._name, self._sendingcommand))
                                resetting = self._resetitem('')
                            else:
                                resetting = ''
                            befehle = []
                            for eintrag in self._send_commands:
                                befehle.append(eintrag.split(',')[0])
                            try:
                                index = self._send_commands.index(self._sendingcommand)
                            except Exception:
                                index = befehle.index(self._sendingcommand)
                                self.logger.log(VERBOSE1, "Updating Item {}: Sending command {} not in Sendcommands {} list, but found in {}".format(self._name, self._sendingcommand, self._send_commands, befehle))
                            if self._send_commands[index] not in self._query_commands and not self._send_commands[index] in self._special_commands['Display']['Command']:
                                self._keep_commands[time.time()] = self._send_commands[index]
                            self._send_commands.pop(index)
                            if self._depend0_volume0 is True or self._depend0_power0 is True:
                                self._resetondisconnect('update_end')
                            if resetting == '':
                                self.logger.debug("Updating Item {}: Connection error while trying to query info.".format(self._name))
                            else:
                                self.logger.info("Updating Item {}: Connection error. Resetting Item {}. Keepcommands: {}. Sendcommands: {} Sendingcommand: {}".format(
                                    self._name, resetting, self._keep_commands, self._send_commands, self._sendingcommand))
                            self._sendingcommand = 'done'

                    except Exception as err:
                        if not self._is_connected == []:
                            self.logger.warning("Updating Item {}: Problem sending command. It is most likely not in the text file! Error: {}".format(self._name, err))
                        else:
                            self.logger.warning(
                                "Updating Item {}: Problem sending command - not connected! Error: {}".format(self._name, err))

    def _displayignore(self, response, receivedvalue, caller):
        if not caller == 'parsing_final':
            self.logger.log(VERBOSE1, "Display Ignore {}: Function called by: {}. Response: {}. Received Value: {}".format(self._name, caller, response, receivedvalue))
        try:
            displaycommand = self._special_commands['Display']['Command']
            displayignore = self._special_commands['Display']['Ignore']
            inputignore = self._special_commands['Input']['Ignore']
            inputcommands = self._special_commands['Input']['Command']
            responseignore = self._ignore_response
        except:
            displaycommand = inputcommands = responseignore = ''
            displayignore = inputignore = 1
        try:
            sending = self._send_commands[0]
        except Exception:
            sending = ''
        if receivedvalue is None:
            try:
                for resp in response:
                    if resp in displaycommand and not displaycommand == '':
                        keyfound = True
                    else:
                        keyfound = False
                if sending in self._query_commands and len(self._send_commands) > 1 and keyfound is not True and displayignore < 5:
                    self._special_commands['Display']['Ignore'] = displayignore + 5
                    if displaycommand not in self._ignore_response and '' not in self._ignore_response and not displaycommand == '':
                        self._ignore_response.append(displaycommand)
                    self.logger.log(VERBOSE2, "Display Ignore {}: Command: {}. Display Ignore: {}, Input Ignore: {}".format(
                        self._name, sending, self._special_commands['Display']['Ignore'], inputignore))

                elif sending not in self._query_commands or len(self._send_commands) <= 1 or keyfound is True:
                    if displayignore >= 5:
                        self._special_commands['Display']['Ignore'] = displayignore - 5
                        self.logger.log(VERBOSE2, "Display Ignore {}: Init Phase finished, Display Ignore: {}, Input Ignore: {}".format(
                            self._name, self._special_commands['Display']['Ignore'], inputignore))
                    if self._special_commands['Display']['Ignore'] == 0 and 1 not in inputignore and not displaycommand == '':
                        if displaycommand in self._ignore_response:
                            try:
                                self._ignore_response.remove(displaycommand)
                                self.logger.log(VERBOSE2, "Display Ignore {}: Removing {} from ignore.".format(
                                    self._name, displaycommand))
                            except Exception as err:
                                self.logger.log(VERBOSE2, "Display Ignore {}: Cannot remove {} from ignore. Message: {}".format(
                                    self._name, displaycommand, err))
                if not (self._ignore_response == responseignore and self._special_commands['Display']['Ignore'] == displayignore and self._special_commands['Input']['Ignore'] == inputignore):
                    self.logger.debug("Display Ignore {}: Ignored responses are now: {}. Display Ignore: {}, Input Ignore: {}".format(self._name, self._ignore_response, self._special_commands['Display']['Ignore'], self._special_commands['Input']['Ignore']))
            except Exception as err:
                self.logger.debug("Display Ignore {}: Problems: {} in line {}.".format(self._name, err, sys.exc_info()[-1].tb_lineno))
        else:
            try:
                if response.startswith(tuple(inputcommands)) and str(receivedvalue) in self._ignoredisplay and '' not in self. _ignoredisplay:
                    for i in range(0, len(inputcommands)):
                        if response.startswith(inputcommands[i]):
                            self._special_commands['Input']['Ignore'][i] = 1
                    if displaycommand not in self._ignore_response and not displaycommand == '' and '' not in self._ignore_response:
                        self._ignore_response.append(displaycommand)
                    self.logger.debug("Display Ignore {}: Data {} has value in ignoredisplay {}. Ignorecommands are now: {}. Display Ignore is {}. Input Ignore is {}".format(self._name, response, self._ignoredisplay, self._ignore_response, displayignore, inputignore))
                elif response.startswith(tuple(inputcommands)) and str(receivedvalue) not in self._ignoredisplay and '' not in self. _ignoredisplay:
                    for i in range(0, len(inputcommands)):
                        if response.startswith(inputcommands[i]):
                            self._special_commands['Input']['Ignore'][i] = 0
                    self.logger.log(VERBOSE2, "Display Ignore {}: Data {} with received value {} has NO value in ignoredisplay {}. Ignored responses are now: {}. Display Ignore is {}. Input Ignore is {}".format(self._name, response, receivedvalue, self._ignoredisplay, self._ignore_response, displayignore, inputignore))
                    if displayignore == 0 and 1 not in inputignore and not displaycommand == '':
                        if displaycommand in self._ignore_response:
                            try:
                                self._ignore_response.remove(displaycommand)
                                self.logger.log(VERBOSE2, "Display Ignore {}: Removing {} from ignore.".format(
                                    self._name, displaycommand))
                            except Exception as err:
                                self.logger.log(VERBOSE2, "Display Ignore {}: Cannot remove {} from ignore. Message: {}".format(
                                    self._name, displaycommand, err))
                if not (self._ignore_response == responseignore and self._special_commands['Display']['Ignore'] == displayignore and self._special_commands['Input']['Ignore'] == inputignore):
                    self.logger.debug("Display Ignore {}: Ignored responses are now: {}. Display Ignore: {}, Input Ignore: {}".format(self._name, self._ignore_response, self._special_commands['Display']['Ignore'], self._special_commands['Input']['Ignore']))
            except Exception as err:
                self.logger.debug("Display Ignore {}: Problems: {}.".format(self._name, err))

    # Sending commands to the device
    def _send(self, command, caller):
        self.logger.log(VERBOSE1, "Sending {}: Sending function called by: {}. Command: {}.".format(self._name, caller, command))
        try:
            if not self._send_commands == []:
                if command == 'command':
                    to_send = self._send_commands[0].split(',')[0]
                elif command == 'query':
                    to_send = self._send_commands[0].split(',')[1]
                else:
                    try:
                        to_send = command.split(',')[0]
                    except Exception:
                        to_send = command
                    command = 'Resendcommand'
                commandlist = to_send.split('|')
                self.logger.log(VERBOSE1, "Sending {}: Starting to send {} {}. Caller: {}.".format(self._name, command, to_send, caller))
                try:
                    self._sendingcommand = self._send_commands[0]
                except Exception:
                    self._sendingcommand = to_send
                response = self._send_commands[0].split(',')[2].split('|')
                if self._parsinginput == []:
                    self.logger.log(VERBOSE1, "Sending {}: Starting Parse Input. Expected response: {}".format(self._name, response))
                    self._parse_input_init('sending')
                self._displayignore(response, None, 'sending')

                if self._trigger_reconnect is True:
                    self.logger.log(VERBOSE1, "Sending {}: Trying to connect while sending command".format(self._name))
                    self.connect('send')
                cmd = 0
                for multicommand in commandlist:
                    cmd += 1
                    if self._rs232 is not None:
                        # result = self._serial.write(bytes('{}\r'.format(multicommand), 'utf-8'))
                        result = self._serialwrapper.write(u'{}\r'.format(multicommand))
                        self._serialwrapper.flush()
                        self.logger.debug("Sending Serial {}: {} was sent {} from Multicommand-List {}. Returns {}. Sending command: {}".format(self._name, command, multicommand, commandlist, result, self._sendingcommand))
                        self._wait(0.2)
                    elif self._tcp is not None:
                        result = self._tcpsocket.send(bytes('{}\r'.format(multicommand), 'utf-8'))
                        self.logger.debug("Sending TCP {}: {} was sent {} from Multicommand-List {}. Returns {}".format(self._name, command, multicommand, commandlist, result))
                        self._wait(0.2)
                    else:
                        self.logger.error("Sending {}: Neither IP address nor Serial device definition found".format(self._name))
                        result = None
                    if cmd >= len(commandlist) - 1:
                        return result
        except IOError as err:
            if err.errno == 32:
                self.logger.warning(
                    "Sending {}: Problem sending multicommand {}, not connected. Message: {}".format(self._name, self._send_commands[0], err))
                if self._tcp is not None:
                    try:
                        self._tcpsocket.shutdown(2)
                        self._tcpsocket.close()
                        self.logger.debug("Sending {}: TCP socket closed".format(self._name))
                    except Exception:
                        self.logger.log(VERBOSE1, "Sending {}: No TCP socket to close.".format(self._name))
                    try:
                        if 'TCP' in self._is_connected:
                            self._is_connected.remove('TCP')
                        if 'Connecting' in self._is_connected:
                            self._is_connected.remove('Connecting')
                        self.logger.log(VERBOSE1, "Sending {}: reconnect TCP started.".format(self._name))
                        self.connect('send_IOError_TCP')
                    except Exception as err:
                        self.logger.debug("Sending {}: Cannot reconnect TCP. Error: {}".format(self._name, err))
                elif self._rs232 is not None:
                    try:
                        self._serialwrapper.close()
                        self.logger.debug("Sending {}: Serial socket closed".format(self._name))
                    except Exception:
                        self.logger.log(VERBOSE1, "Sending {}: No Serial socket to close.".format(self._name))
                    try:
                        if 'Serial' in self._is_connected:
                            self._is_connected.remove('Serial')
                        if 'Connecting' in self._is_connected:
                            self._is_connected.remove('Connecting')
                        self.logger.log(VERBOSE1, "Sending {}: reconnect Serial started.".format(self._name))
                        self.connect('send_IOError_RS232')
                    except Exception as err:
                        self.logger.debug("Sending {}: Cannot reconnect Serial. Error: {}".format(self._name, err))
        except Exception as err:
            try:
                self.logger.warning("Sending {}: Problem sending multicommand {}. Message: {}".format(self._name, self._send_commands[0], err))
            except Exception:
                self.logger.warning("Sending {}: Problem sending multicommand {}. Message: {}".format(self._name, self._send_commands, err))

    # Stopping function when SmarthomeNG is stopped
    def stop(self):
        self.alive = False
        self._sh.scheduler.change('avdevice-tcp-reconnect', active=False)
        self._sh.scheduler.remove('avdevice-tcp-reconnect')
        self._sh.scheduler.change('avdevice-serial-reconnect', active=False)
        self._sh.scheduler.remove('avdevice-serial-reconnect')

        try:
            self._tcpsocket.shutdown(2)
            self._tcpsocket.close()
            self.logger.debug("Stopping {}: closed".format(self._name))
        except Exception:
            self.logger.log(VERBOSE1, "Stopping {}: No TCP socket to close.".format(self._name))
        try:
            self._serialwrapper.close()
        except Exception:
            self.logger.log(VERBOSE1, "Stopping {}: No Serial socket to close.".format(self._name))


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.DEBUG, format='%(relativeCreated)6d %(threadName)s %(message)s')
    PluginClassName(AVDevice).run()
