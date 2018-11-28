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

from lib.model.smartplugin import *
from lib.item import Items

import io
import time
import datetime
import re
import errno
import itertools
from bin.smarthome import VERSION

from .AVDeviceInit import Init
from .AVDeviceInit import ProcessVariables
from .AVDeviceFunctions import CreateResponse
from .AVDeviceFunctions import Translate
from .AVDeviceFunctions import ConvertValue
from .AVDeviceFunctions import CreateExpectedResponse

VERBOSE1 = logging.DEBUG - 1
VERBOSE2 = logging.DEBUG - 2
logging.addLevelName(logging.DEBUG - 1, 'VERBOSE1')
logging.addLevelName(logging.DEBUG - 2, 'VERBOSE2')


class AVDevice(SmartPlugin):
    ALLOW_MULTIINSTANCE = True
    PLUGIN_VERSION = "1.5.0"


    def __init__(self, smarthome):
        self.itemsApi = Items.get_instance()
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)
        self.init_webinterface()
        try:
            self.alive = False
            self._name = self.get_fullname()
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
            self._send_history = {'query': {}, 'command': {}}
            self._dependencies = {'Slave_function': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}},
                                  'Slave_item': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}},
                                  'Master_function': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}},
                                  'Master_item': {'zone0': {}, 'zone1': {}, 'zone2': {}, 'zone3': {}, 'zone4': {}}}
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
            statusquery = self.get_parameter_value('statusquery')

            # Initializing all variables
            self.logger.debug("Initializing {}: Resendwait: {}. Seconds to keep: {}.".format(self._name, self._resend_wait,
                                                                                             self._secondstokeep))
            self.init = Init(self._name, self._model, self._items, self.logger)
            self._rs232, self._baud, self._timeout = ProcessVariables([rs232_port, rs232_baudrate, rs232_timeout],
                                                                      self._name, self.logger).process_rs232()
            self._tcp, self._port, self._tcp_timeout = ProcessVariables([tcp_ip, tcp_port, tcp_timeout],
                                                                        self._name, self.logger).process_tcp()
            self._dependson, self._dependson_value, self._depend0_power0, self._depend0_volume0 = ProcessVariables(
                [dependson_item, dependson_value, depend0_power0, depend0_volume0],
                self._name, self.logger).process_dependson()

            self._response_buffer = ProcessVariables(responsebuffer, self._name, self.logger).process_responsebuffer()
            self._reset_onerror = ProcessVariables(resetonerror, self._name, self.logger).process_resetonerror()
            self._statusquery = ProcessVariables(statusquery, self._name, self.logger).process_statusquery()
            self._ignore_response, self._error_response, self._force_buffer, self._ignoredisplay = ProcessVariables(
                [ignoreresponse, errorresponse, forcebuffer, inputignoredisplay],
                self._name, self.logger).process_responses()
            self.logger.debug(
                "Initializing {}: Special Settings: Ignoring responses {}.".format(self._name, self._ignore_response))
            self.logger.debug(
                "Initializing {}: Special Settings: Error responses {}.".format(self._name, self._error_response))
            self.logger.debug("Initializing {}: Special Settings: Force buffer {}.".format(self._name, self._force_buffer))
            self.logger.debug(
                "Initializing {}: Special Settings: Ignore Display {}".format(self._name, self._ignoredisplay))
            self.logger.debug(
                "Initializing {}: Querying at plugin init is set to {}".format(self._name, self._statusquery))
            self._update_exclude = ProcessVariables(update_exclude, self._name, self.logger).process_update_exclude()

        except Exception as err:
            self.logger.error(err)
            self._init_complete = False
            return

    # Non-blocking wait function
    @staticmethod
    def _wait(time_lapse):
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
                    try:
                        founditem = self._send_commands[0].split(';')[1]
                    except Exception:
                        self.logger.log(VERBOSE2,
                                        "Resetting {}: Resetting nothing because command is query command only.".format(self._name))
                        return None
            try:
                founditem = self.itemsApi.return_item(founditem)
            except Exception as err:
                self.logger.debug("Resetting {}: {} is no valid item. Message: {}.".format(self._name, founditem, err))
                return None
            self.logger.log(VERBOSE2, "Resetting {}: Item: {}.".format(self._name, founditem))
            speakerfound = True if founditem == self._special_commands['Speakers']['Item'] else False

            for zone in self._items.keys():
                for itemlist in self._items[zone].keys():
                    previousvalue = self._items[zone][itemlist]['Value']
                    if isinstance(self._items[zone][itemlist]['Item'], list):
                        for search in self._items[zone][itemlist]['Item']:
                            self.logger.log(VERBOSE2, "Resetting {}: Search {} in {} with {}.".format(
                                self._name, founditem, self._items[zone][itemlist]['Item'], search))
                            if founditem == search:
                                founditem(previousvalue, 'AVDevice', self._tcp)
                                self.logger.info("Resetting {}: Item {} to {}".format(
                                    self._name, founditem, previousvalue))
                                resetting = founditem
                                break
                    else:
                        compare = self._items[zone][itemlist].get('Item')
                        self.logger.log(VERBOSE2,
                                        "Resetting {}: Search {} in {}.".format(self._name, founditem, compare))
                        if founditem == compare:
                            founditem(previousvalue, 'AVDevice', self._tcp)
                            self.logger.info("Resetting {}: Item {} to {}".format(
                                self._name, founditem, previousvalue))
                            resetting = founditem
                            break
                for speakerlist in self._items_speakers[zone].keys():
                    search = self._items_speakers[zone][speakerlist]['Item']
                    self.logger.log(VERBOSE2, "Resetting {}: Search {} in speakers {}.".format(
                        self._name, founditem, search))
                    speakerfound = True if founditem == search else False
                if speakerfound is True:
                    for itemlist in self._items_speakers[zone].keys():
                        search = self._items_speakers[zone][itemlist]['Item']
                        previousvalue = self._items_speakers[zone][itemlist]['Value']
                        self.logger.info("Resetting {}: Resetting additional speaker item {} to value {}".format(
                            self._name, search, previousvalue))
                        search(previousvalue, 'AVDevice', self._tcp)
                    resetting = founditem
                if resetting is not None:
                    break

            self._trigger_reconnect = False
            self.logger.log(VERBOSE2, "Resetting {}: Finished. Returning value: {}.".format(self._name, resetting))
            return resetting
        except Exception as err:
            self.logger.error("Resetting {}: Problem resetting Item. Error: {}".format(self._name, err))
            return 'ERROR'

    # Resetting items if no connection available
    def _resetondisconnect(self, caller):
        if self._depend0_volume0 is True or self._depend0_power0 is True:
            self.logger.debug('Resetting {}: Starting to reset on disconnect. Called by {}'.format(self._name, caller))
            try:
                for zone in self._items:
                    if 'power' in self._items[zone].keys() and self._depend0_power0 is True:
                        self._items[zone]['power']['Value'] = 0
                        self._items[zone]['power']['Item'](0, 'AVDevice', self._tcp)
                        self.logger.log(VERBOSE1, 'Resetting {}: Power to 0 for item {}'.format(
                            self._name, self._items[zone]['power']['Item']))
                    if 'speakers' in self._items[zone].keys() and self._depend0_power0 is True:
                        self._items[zone]['speakers']['Value'] = 0
                        for itemlist in self._items_speakers[zone].keys():
                            self._items_speakers[zone][itemlist]['Value'] = 0
                            speakeritem = self._items_speakers[zone][itemlist]['Item']
                            speakeritem(0, 'AVDevice', self._tcp)
                            self.logger.log(VERBOSE1,
                                            'Resetting {}: Speakers to 0 for item {}'.format(self._name,
                                                                                             speakeritem))
                        speakeritem = self._items[zone]['speakers']['Item']
                        speakeritem(0, 'AVDevice', self._tcp)
                        self.logger.log(VERBOSE1,
                                        'Resetting {}: Speakers to 0 for item {}'.format(self._name, speakeritem))
                    if 'volume' in self._items[zone].keys() and self._depend0_volume0 is True:
                        self._items[zone]['volume']['Value'] = 0
                        self._items[zone]['volume']['Item'](0, 'AVDevice', self._tcp)
                        self.logger.log(VERBOSE1, 'Resetting {}: Volume to 0 for item {}'.format(
                            self._name, self._items[zone]['volume']['Item']))
                self.logger.debug('Resetting {}: Done.'.format(self._name))
            except Exception as err:
                self.logger.warning('Resetting {}: Problem resetting Item on disconnect. Error: {}'.format(self._name, err))
        else:
            self.logger.log(VERBOSE1,
                            'Resetting {}: Not resetting on disconnect because this feature is disabled in the plugin config.'.format(
                                self._name))

    # Store actual value to a temporary dict for resetting purposes
    def _write_itemsdict(self, data, found):
        zone = updated = 0
        receivedvalue = expectedtype = av_function = 'empty'
        try:
            self.logger.debug(
                "Storing Values {}: Starting to store value for data {} in dictionary. Found expected responses: {}.".format(
                    self._name, data, found))
            sorted_response_commands = sorted(self._response_commands, key=len, reverse=True)
            for i, respo in enumerate(sorted_response_commands):
                try:
                    sorted_response_commands[i] = self._response_wildcards['original'][respo]
                except Exception as err:
                    sorted_response_commands[i] = None
                    self.logger.log(VERBOSE2,
                                    "Storing Values {}: Can not find wildcard equivalent for: {}".format(self._name,
                                                                                                         err))
            for entry in found:
                if entry in sorted_response_commands:
                    sorted_response_commands.insert(0, entry)
            sorted_response_commands = [value for value in sorted_response_commands if value is not None]
            self.logger.log(VERBOSE2, "Storing Values {}: Sorted wildcarded response commands {}.".format(self._name,
                                                                                                          sorted_response_commands))
            for command in sorted_response_commands:
                self.logger.log(VERBOSE2, "Storing Values {}: Comparing command {}.".format(self._name, command))
                if data == command:
                    self.logger.debug(
                        "Storing Values {}: Response is identical to expected response. Skipping Storing: {}".format(
                            self._name, data))
                    break
                for entry in self._response_commands[self._response_wildcards['wildcard'][command]]:
                    self.logger.log(VERBOSE2, "Storing Values {}: Comparing entry {}.".format(self._name, entry))
                    commandstart = entry[0] if entry[2] == 0 else 0
                    commandend = entry[1] if entry[2] == 0 else entry[2]
                    valuestart = entry[2]
                    valueend = entry[2] + entry[0]
                    av_function = entry[4]
                    expectedtype = entry[7]

                    if data[commandstart:commandend] == command:
                        zone = entry[5]
                        value = data[valuestart:valueend]
                        invert = True if entry[6].lower() in ['1', 'true', 'yes', 'on'] else False
                        received = ConvertValue(value, expectedtype, invert, entry[0], command,
                                                self._name, self._special_commands, self.logger).convert_value() \
                            if not value == '' else data[valuestart:valueend]
                        receivedvalue = received[1] if isinstance(received, list) else received
                        try:
                            sametype = True if isinstance(receivedvalue, eval(expectedtype)) else False
                        except Exception as err:
                            self.logger.log(VERBOSE2,
                                            "Storing Values {}: Cannot compare {} with {}. Message: {}".format(
                                                self._name, receivedvalue, expectedtype, err))
                            sametype = True if receivedvalue == '' and expectedtype == 'empty' else False
                        if sametype is True:
                            self._items[zone][av_function]['Value'] = Translate(
                                value, entry[9], self._name, 'writedict', self._specialparse, self.logger).translate()
                            self.logger.debug(
                                "Storing Values {}: Found writeable dict key: {}. Zone: {}. "
                                "Value {} with type {}. Function: {}.".format(
                                    self._name, command, zone, receivedvalue, expectedtype, av_function))
                            updated = 1
                            break
                        else:
                            self.logger.debug(
                                "Storing Values {}: Found writeable dict key: {} with type {}, "
                                "but received value {} is type {}. Not writing value!".format(
                                    self._name, command, expectedtype, receivedvalue, type(receivedvalue)))

                        if updated == 1:
                            self.logger.log(VERBOSE1,
                                            "Storing Values {}: Stored all relevant items from function {}. step 1".format(
                                                self._name, av_function))
                            break
                    if updated == 1:
                        self.logger.log(VERBOSE1,
                                        "Storing Values {}: Stored all relevant items from function {}. step 2".format(
                                            self._name, av_function))
                        break
                if updated == 1:
                    self.logger.log(VERBOSE1,
                                    "Storing Values {}: Stored all relevant items from function {}. step 3".format(
                                        self._name, av_function))
                    break
        except Exception as err:
            self.logger.error(
                "Storing Values {}: Problems creating items dictionary. Error: {}".format(self._name, err))
        finally:
            self.logger.log(VERBOSE1,
                            "Storing Values {}: Finished. Send Commands: {}. Returning: {}, {}".format(
                                self._name, self._send_commands, receivedvalue, expectedtype))
            if updated == 1:
                return self._items[zone][av_function], receivedvalue, expectedtype
            else:
                return 'empty', 'empty', 'empty'

    def _parse_depend_item(self, item, info, zone):
        for dependzone in range(0, 5):
            dependzone = 'zone{}'.format(dependzone)
            cond1 = self.has_iattr(item.conf, 'avdevice_{}_depend'.format(dependzone))
            cond2 = (self.has_iattr(item.conf, 'avdevice_depend') and dependzone == 'zone0')
            if cond1 or cond2:
                liste = self.get_iattr_value(item.conf, 'avdevice_{}_depend'.format(dependzone)) \
                    if cond1 else self.get_iattr_value(item.conf, 'avdevice_depend')
                liste = [liste] if not isinstance(liste, list) else liste
                for entry in liste:
                    splitting = entry.split('>=') if entry.find('>=') >= 0 \
                        else entry.split('<=') if entry.find('<=') >= 0 \
                        else entry.split('==') if entry.find('==') >= 0 \
                        else entry.split('=') if entry.find('=') >= 0 \
                        else entry.split('>') if entry.find('>') >= 0 \
                        else entry.split('<') if entry.find('<') >= 0 \
                        else entry.split('!=') if entry.find('!=') >= 0 or entry.find('<>') >= 0 \
                        else [entry.split(',')[0], '{}, {}'.format(True, entry.split(',')[1])] if entry.find(',') >= 0 \
                        else [entry, True]
                    comparing = '>=' if entry.find('>=') >= 0 \
                        else '<=' if entry.find('<=') >= 0 \
                        else '>' if entry.find('>') >= 0 \
                        else '<' if entry.find('<') >= 0 \
                        else '!=' if entry.find('!=') >= 0 or entry.find('<>') >= 0 \
                        else '=='
                    try:
                        depend = splitting[0].strip().lower()
                    except Exception:
                        depend = None
                    try:
                        dependvalue = splitting[1].split(',')[0].strip()
                        dependvalue = True if re.sub('[ ]', '', str(dependvalue)).lower() in ['yes', 'true', 'on'] \
                            else False if re.sub('[ ]', '', str(dependvalue)).lower() in ['no', 'false', 'off'] \
                            else dependvalue
                    except Exception:
                        dependvalue = None if depend is None else True
                    try:
                        dependgroup = splitting[1].split(',')[1].strip().lower()
                    except Exception:
                        dependgroup = 'a'
                    try:
                        dependvalue = eval(dependvalue)
                    except Exception:
                        pass
                    if splitting is None:
                        return None
                    else:
                        try:
                            self._items[zone][info]['Master'].append(
                                {'Zone': dependzone, 'Item': depend, 'Dependvalue': dependvalue, 'Compare': comparing,
                                 'Group': dependgroup})
                            self.logger.log(VERBOSE1,
                                            "Initializing {}: Adding dependency for {}.".format(self._name, info))
                        except Exception:
                            self._items[zone][info].update({'Master': [
                                {'Zone': dependzone, 'Item': depend, 'Dependvalue': dependvalue, 'Compare': comparing,
                                 'Group': dependgroup}]})
                            self.logger.log(VERBOSE1,
                                            "Initializing {}: Creating dependency for {}.".format(self._name, info))

    # Finding relevant items for the plugin based on the avdevice keyword
    def parse_item(self, item):
        if self._tcp is not None or self._rs232 is not None:
            keywords = ['avdevice', 'avdevice_zone0', 'avdevice_init', 'avdevice_speakers', 'avdevice_zone1',
                        'avdevice_zone1_init', 'avdevice_zone1_speakers', 'avdevice_zone2', 'avdevice_zone2_init',
                        'avdevice_zone2_speakers', 'avdevice_zone3', 'avdevice_zone3_init', 'avdevice_zone3_speakers',
                        'avdevice_zone4', 'avdevice_zone4_init', 'avdevice_zone4_speakers']
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
                    self.logger.debug(
                        "Initializing {}: Dependson Item found: {}".format(self._name, item, self._dependson))
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

    # Processing the response from the AV device, dealing with buffers, etc.
    def _processing_response(self, socket):

        def _sortbuffer(buffer, bufferlist):
            expectedsplit = []
            self._expected_response = CreateExpectedResponse(buffer, self._name,
                                                             self._send_commands, self.logger).create_expected()
            expectedsplit = list(itertools.chain(*[x.split('|') for x in self._expected_response]))
            sortedbuffer = []
            for e in expectedsplit:
                for entry in bufferlist:
                    if entry == e and entry not in self._ignore_response:
                        sortedbuffer.append(entry)
                        self.logger.log(VERBOSE2,
                                        "Processing Response {}: Response is same as expected. adding: {}.".format(
                                            self._name, entry))
                        break
                    elif entry.startswith(e):
                        try:
                            realresponse = self._response_wildcards['original'][e]
                        except Exception:
                            realresponse = e
                        try:
                            for resp in self._response_commands[realresponse]:
                                self.logger.log(VERBOSE2,
                                                "Processing Response {}: realresponse: {}. Length: {}, expected length: {}.".format(
                                                    self._name, realresponse, len(entry), resp[1]))
                                cond1 = len(entry) == resp[1] or resp[1] == 100 or resp[0] == 100
                                cond2 = entry not in sortedbuffer and entry not in self._ignore_response
                                if cond1 and cond2:
                                    self.logger.log(VERBOSE2,
                                                    "Processing Response {}: length is same. adding: {}.".format(
                                                        self._name, entry))
                                    sortedbuffer.append(entry)
                                    break
                        except Exception:
                            pass

            self.logger.log(VERBOSE2,
                            "Processing Response {}: expected response: {}, bufferlist {}. Sortedbuffer: {}".format(
                                self._name, expectedsplit, bufferlist, sortedbuffer))
            bufferlist = [x for x in bufferlist if x not in sortedbuffer]
            buffer = "\r\n".join(sortedbuffer + bufferlist)
            buffer = "{}\r\n".format(buffer)
            return buffer, expectedsplit

        try:
            buffer = ''
            tidy = lambda c: re.sub(
                r'(^\s*[\r\n]+|^\s*\Z)|(\s*\Z|\s*[\r\n]+)',
                lambda m: '\r\n' if m.lastindex == 2 else '',
                c)
            try:
                if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
                    buffer = socket.readline().decode('utf-8') if socket == self._serial else socket.read()
                if self._tcp and socket == self._tcpsocket:
                    buffer = socket.recv(4096).decode('utf-8')
                buffer = tidy(buffer)
                buffering = False
                cond1 = self._response_buffer is not False or self._response_buffer is not 0
                if not buffer == '' and cond1:
                    buffering = True
                elif buffer == '' and not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup':
                    self._resend_on_empty_counter += 1
                    self._wait(0.1)
                    sending = self._send(self._sendingcommand, 'responseprocess')
                    self.logger.log(VERBOSE1,
                                    "Processing Response {}: Received empty response while sending command: {}."
                                    " Return from send is {}. Retry: {}".format(
                                        self._name, self._sendingcommand, sending, self._resend_counter))
                    if self._resend_on_empty_counter >= 2:
                        self.logger.debug(
                            "Processing Response {}: Stop resending command {} and sending back error.".format(
                                self._name, self._sendingcommand))
                        self._resend_on_empty_counter = 0
                        yield 'ERROR'

            except Exception as err:
                buffering = False
                try:
                    cond1 = not self._sendingcommand == 'done' and not self._sendingcommand == 'gaveup'
                    try:
                        cond2 = (self._sendingcommand.split(',')[2] == '' or self._sendingcommand.split(',')[2] == ' ' or
                                 self._sendingcommand.split(',')[2] == 'none')
                    except Exception:
                        cond2 = self._sendingcommand == ''
                    if cond1 and not cond2:
                        buffering = True
                        self._expected_response = CreateExpectedResponse(buffer, self._name,
                                                                         self._send_commands, self.logger).create_expected()
                        self.logger.log(VERBOSE1,
                                        "Processing Response {}: Error reading.. Error: {}. Sending Command: {}.".format(
                                            self._name, err, self._sendingcommand))
                        self.logger.log(VERBOSE2,
                                        "Processing Response {}: Expected response: {}.".format(
                                            self._name, self._expected_response))
                        if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
                            self.logger.log(VERBOSE1,
                                            "Processing Response {}: Problems buffering RS232 response. Error: {}."
                                            " Increasing timeout temporarily.".format(self._name, err))
                            self._wait(1)
                            socket.timeout = 2
                            sending = self._send(self._sendingcommand, 'getresponse')
                            buffer = socket.readline().decode('utf-8') if socket == self._serial else socket.read()
                            socket.timeout = 0.3
                            self.logger.log(VERBOSE1,
                                            "Processing Response {}: Error reading.. Return from send is {}. Error: {}".format(
                                                self._name, sending, err))
                            if not buffer:
                                yield 'ERROR'
                        if self._tcp and socket == self._tcpsocket:
                            self.logger.log(VERBOSE1,
                                            "Processing Response {}: Problems buffering TCP response. Error: {}."
                                            " Increasing timeout temporarily.".format(self._name, err))
                            self._wait(1)
                            socket.settimeout(self._tcp_timeout * 3)
                            sending = self._send(self._sendingcommand, 'getresponse')
                            self.logger.debug(
                                "Processing Response {}: Error reading.. Return from send is {}. Error: {}".format(
                                    self._name, sending, err))
                            buffer = socket.recv(4096).decode('utf-8')
                            socket.settimeout(self._tcp_timeout)
                            if not buffer:
                                yield 'ERROR'
                    elif cond2:
                        # self._sendingcommand = 'done'
                        yield 'none'
                except Exception as err:
                    buffering = False
                    self.logger.error(
                        "Processing Response {}: Connection error. Error: {} Resend Counter: {}. Resend Max: {}".format(
                            self._name, err, self._resend_counter, self._resend_retries))
                    yield 'ERROR'

            while buffering:
                if '\r\n' in buffer:
                    self.logger.log(VERBOSE2,
                                    "Processing Response {}: Buffer before removing duplicates: {}".format(
                                        self._name, re.sub('[\r\n]', ' --- ', buffer)))
                    if self._clearbuffer is True:
                        buffer = '\r\n'
                        self.logger.log(VERBOSE1,
                                        "Processing Response {}: Clearing buffer because clearbuffer set to true. It is now: {}".format(
                                            self._name, re.sub('[\r\n]', ' --- ', buffer)))
                        self._clearbuffer = False
                    bufferlist = buffer.split("\r\n")
                    bufferlist = bufferlist[:-1] if len(bufferlist) > 1 else bufferlist
                    # Removing duplicates
                    buffer_cleaned = []
                    for buff in bufferlist:
                        if buff not in buffer_cleaned or buff in self._force_buffer:
                            buffer_cleaned.append(buff)
                    bufferlist = buffer_cleaned
                    buffer = "\r\n".join(bufferlist) + "\r\n"

                    if self._send_commands:
                        _, expectedsplit = _sortbuffer(buffer, bufferlist)
                        # first entry should be buffer as soon as resorting works perfectly smooth. Problem now: On very short interval settings the sorting results in wrong reponses.
                        self.logger.log(VERBOSE2, "Processing Response {}: Buffer after sorting: {}.".format(
                            self._name, re.sub('[\r\n]', ' --- ', buffer)))

                    (line, buffer) = buffer.split("\r\n", 1)
                    self.logger.log(VERBOSE2,
                                    "Processing Response {}: Buffer: {} Line: {}. Response buffer: {}, force buffer: {}.".format(
                                        self._name, re.sub('\r\n', ' --- ', buffer), re.sub('\r\n', '. ', line),
                                        self._response_buffer, self._force_buffer))
                    cond1 = ('' in self._force_buffer and len(self._force_buffer) == 1)
                    cond2 = (self._response_buffer is False or self._response_buffer == 0)
                    cond3 = (not re.sub('[ ]', '', buffer) == '' and not re.sub('[ ]', '', line) == '')
                    if not cond1 and cond2 and cond3:
                        bufferlist = []
                        for buf in self._force_buffer:
                            try:
                                if buf in buffer and not buf.startswith(
                                        tuple(self._ignore_response)) and '' not in self._ignore_response:
                                    start = buffer.index(buf)
                                    self.logger.log(VERBOSE2,
                                                    "Processing Response {}: Testing forcebuffer {}. Bufferlist: {}. Start: {}".format(
                                                        self._name, buf, bufferlist, start))
                                    if not buffer.find('\r\n', start) == -1:
                                        end = buffer.index('\r\n', start)
                                        if not buffer[start:end] in bufferlist and not buffer[start:end] in line:
                                            bufferlist.append(buffer[start:end])
                                    else:
                                        if not buffer[start:] in bufferlist and not buffer[start:] in line:
                                            bufferlist.append(buffer[start:])
                                    self.logger.debug(
                                        "Processing Response {}: Forcebuffer {} FOUND in buffer. Bufferlist: {}. Buffer: {}".format(
                                            self._name, buf, bufferlist, re.sub('[\r\n]', ' --- ', buffer)))
                            except Exception as err:
                                self.logger.warning(
                                    "Processing Response {}: Problems while buffering. Error: {}".format(self._name,
                                                                                                         err))
                        buffer = tidy('\r\n'.join(bufferlist)) if bufferlist else tidy(buffer)
                        self.logger.log(VERBOSE2, "Processing Response {}: Tidied entry without buffer: {}".format(
                            self._name, buffer))

                    if '{}\r\n'.format(line) == buffer:
                        buffer = ''
                        self.logger.log(VERBOSE1,
                                        "Processing Response {}: Clearing buffer because it's the same as Line: {}".format(
                                            self._name, line))

                    line = re.sub('[\\n\\r]', '', line).strip()
                    responseforsending = False
                    for entry in self._response_commands:
                        newentry = Translate(line, entry, self._name, '', '', self.logger).wildcard()
                        self._response_wildcards['wildcard'].update({newentry: entry})
                        self._response_wildcards['original'].update({entry: newentry})
                    responsecommands = list(self._response_wildcards['wildcard'].keys())
                    responsecommands = [value for value in responsecommands if '?' not in value]
                    self.logger.log(VERBOSE1,
                                    "Processing Response {}: New Response Command list after processing wildcard: {}".format(
                                        self._name, responsecommands))
                    try:
                        for resp in ','.join(self._sendingcommand.split(';')[0].split(',')[2:]).split('|'):
                            resp = resp.split(',')[0]
                            resp = Translate(line, resp, self._name, '', '', self.logger).wildcard() if len(line) == len(
                                resp) else resp
                            self.logger.log(VERBOSE2,
                                            "Processing Response {}: Testing sendingcommand {}. Line: {}, expected response: {}".format(
                                                self._name, self._sendingcommand, line, resp))
                            responseforsending = True if line == resp else False
                    except Exception as err:
                        self.logger.log(VERBOSE2,
                                        "Processing Response {}: Problem comparing line {}. Message {}".format(
                                            self._name, line, err))
                    try:
                        displaycheck = expectedsplit[0] if buffer == '' else 'nodisplaycommandexpectedsofar'
                    except Exception:
                        displaycheck = 'nodisplaycommandexpectedsofar'
                    cond1 = not line.startswith(tuple(responsecommands))
                    cond2 = line not in self._error_response and responseforsending is False
                    cond3 = line.startswith(self._special_commands['Display']['Command'])
                    cond4 = self._response_buffer is not False and not line.startswith(displaycheck)
                    cond5 = not self._special_commands['Display']['Command'] == ''
                    if cond1 and cond2:
                        self.logger.log(VERBOSE1,
                                        "Processing Response {}: Response {} is not in possible responses for items. Sending Command: {}".format(
                                            self._name, line, self._sendingcommand))
                    elif line in self._error_response and '' not in self._error_response:
                        self.logger.debug(
                            "Processing Response {}: Response {} is in Error responses.".format(self._name, line))
                        yield "{}".format(line)
                    elif cond3 and cond4 and cond5:
                        buffering = False
                        buffer = tidy(buffer + '\r\n{}\r\n'.format(line))
                        self.logger.log(VERBOSE1, "Processing Response {}: Append Display info {} to buffer: {}".format(
                            self._name, line, re.sub('[\r\n]', ' --- ', buffer)))
                    elif line.startswith(tuple(self._ignore_response)) and '' not in self._ignore_response:
                        try:
                            keyfound = False
                            compare = ','.join(self._send_commands[0].split(';')[0].split(',')[2:]).split('|')
                            for comp in compare:
                                comp = Translate(line, comp.split(',')[0], self._name, '', '', self.logger).wildcard()
                                keyfound = True if line.startswith(comp) else False
                            if keyfound is True:
                                self.logger.log(VERBOSE1,
                                                "Processing Response {}: Sendcommands: {} Keep command {}".format(
                                                    self._name, self._send_commands, self._keep_commands))
                                for entry in self._keep_commands:
                                    if self._send_commands[0] in self._keep_commands.get(entry):
                                        self._keep_commands.pop(entry)
                                        self.logger.log(VERBOSE1,
                                                        "Processing Response {}: Removed Keep command {} from {}"
                                                        " because command sent successfully".format(
                                                            self._name, entry, self._keep_commands))
                                        break
                                self._send_commands.pop(0)
                                self._sendingcommand = 'done'
                                sending = self._send('command', 'commandremoval')
                                self.logger.debug(
                                    "Processing Response {}: Response {} is same as expected {} and defined as response"
                                    " to be ignored. Removing command from send list. It is now: {}. Ignore responses are: {}."
                                    " Sending return: {}".format(
                                        self._name, line, compare, self._send_commands, self._ignore_response, sending))

                        except Exception as err:
                            self.logger.log(VERBOSE2,
                                            "Processing Response {}: Response {} is ignored because ignore responses is {}."
                                            " Command list is now: {}. Message: {}".format(
                                                self._name, line, self._ignore_response, self._send_commands, err))
                    else:
                        if self._response_buffer is False and not buffer.startswith(
                                tuple(self._force_buffer)) and '' not in self._force_buffer:
                            buffering = False
                            self.logger.log(VERBOSE1, "Processing Response {}: Clearing buffer: {}".format(
                                self._name, re.sub('[\r\n]', ' --- ', buffer)))
                            buffer = '\r\n'
                        self.logger.log(VERBOSE1,
                                        "Processing Response {}: Sending back line: {}.".format(self._name, line))
                        yield "{}".format(line)
                else:
                    try:
                        more = '\r\n'
                        if self._rs232 and (socket == self._serialwrapper or socket == self._serial):
                            more = socket.readline().decode('utf-8') if socket == self._serial else socket.read()
                        if self._tcp and socket == self._tcp:
                            more = socket.recv(4096).decode('utf-8')
                        morelist = more.split("\r\n")
                        buffer += '\r\n' if buffer.find('\r\n') == -1 and len(buffer) > 0 else ''
                        buffer += '\r\n'.join([x[0] for x in itertools.groupby(morelist)])
                    except Exception:
                        pass
                    finally:
                        buffering = False
                        self.logger.log(VERBOSE1, "Processing Response {}: Buffering false. Buffer: {}".format(
                            self._name, re.sub('[\r\n]', ' --- ', buffer)))

            if not buffer == '\r\n' and (self._response_buffer is True or type(self._response_buffer) is int):
                buffer = tidy(buffer)
                bufferlist = buffer.split('\r\n')
                # Removing everything except last x lines
                maximum = abs(self._response_buffer) if type(self._response_buffer) is int else 11
                # Removing empty entries
                bufferlist = list(filter(lambda a: a != '', bufferlist))
                newbuffer = [buf for buf in bufferlist if not buf.startswith(tuple(self._ignore_response)) and
                             '' not in self._ignore_response and
                             buf.startswith(tuple(self._response_commands))]
                bufferlist = newbuffer[-1 * max(min(len(newbuffer), maximum), 0):]
                buffering = False
                if bufferlist:
                    self._expected_response = CreateExpectedResponse('\r\n'.join(bufferlist), self._name,
                                                                     self._send_commands, self.logger).create_expected()
                for buf in bufferlist:
                    cond1 = not re.sub('[ ]', '', buf) == ''
                    cond2 = not buf.startswith(tuple(self._ignore_response))
                    cond3 = '' not in self._ignore_response
                    if cond1 and cond2 and cond3:
                        self.logger.log(VERBOSE1,
                                        "Processing Response {}: Sending back {} from buffer because "
                                        "Responsebuffer is activated. Expected response updated {}.".format(
                                            self._name, buf, self._expected_response))
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
                    if not re.sub('[ ]', '', buf) == '' and not buf.startswith(
                            tuple(self._ignore_response)) and '' not in self._ignore_response:
                        self.logger.debug(
                            "Processing Response {}: Sending back {} from filtered buffer: {}.".format(
                                self._name, buf, re.sub('[\r\n]', ' --- ', buffer)))
                        self._wait(0.2)
                        yield buf
        except Exception as err:
            self.logger.error("Processing Response {}: Problems: {}".format(self._name, err))

    def _clear_history(self, part):
        if part == 'keep':
            self._keep_commands.clear()
        elif part == 'send':
            self._send_commands[:] = []
        else:
            self._send_history[part].clear()

    # init function
    def _initialize(self):
        self._send_commands[:] = []
        self._sendingcommand = 'done'
        self._functions, self._number_of_zones, self._specialparse = self.init.read_commandfile()
        self._response_commands, self._special_commands = self.init.create_responsecommands()
        self._power_commands = self.init.create_powercommands()
        self._query_commands, self._query_zonecommands = self.init.create_querycommands()
        self.logger.log(VERBOSE1,
                        "Initializing {}: Functions: {}, Number of Zones: {}".format(self._name, self._functions,
                                                                                     self._number_of_zones))
        self.logger.log(VERBOSE1, "Initializing {}: Responsecommands: {}.".format(self._name, self._response_commands))
        self.logger.log(VERBOSE1, "Initializing {}: Special Commands: {}".format(self._name, self._special_commands))
        self.logger.log(VERBOSE1, "Initializing {}: Special Parsing: {}".format(self._name, self._specialparse))
        self.logger.log(VERBOSE1, "Initializing {}: Powercommands: {}".format(self._name, self._power_commands))
        self.logger.log(VERBOSE1,
                        "Initializing {}: Querycommands: {}, Query Zone: {}".format(self._name, self._query_commands,
                                                                                    self._query_zonecommands))
        problems = {'zone3': {}, 'zone1': {}, 'zone2': {}, 'zone0': {}}
        new = {'zone3': {}, 'zone1': {}, 'zone2': {}, 'zone0': {}}
        for zone in self._init_commands:
            try:
                for command in self._init_commands[zone]:
                    try:
                        self._init_commands[zone][command]['Item'] = self._items[zone][command]['Item']
                    except Exception as err:
                        problems[zone] = command
                        self.logger.error(
                            "Initializing {}: Problems occured with init command {} for {}.".format(self._name, err,
                                                                                                    zone))
            except Exception as err:
                self.logger.debug("Initializing {}: No init commands set. Message: {}".format(self._name, err))
        for zone in self._init_commands:
            new[zone] = {k: v for k, v in self._init_commands[zone].items() if k not in problems[zone]}
        self._init_commands = new
        self.logger.log(VERBOSE1, "Initializing {}: Initcommands: {}".format(self._name, self._init_commands))
        return True

    # Run function
    def run(self):
        self.logger.debug("Plugin '{}': run method called".format(self.get_fullname()))
        if self._tcp is None and self._rs232 is None:
            self.logger.error(
                "Initializing {}: Neither IP address nor RS232 port given. Not running.".format(self._name))
        else:
            self._items, self._dependencies = self.init.process_items()
            initdone = self._initialize()
            self.logger.log(VERBOSE1, "Initializing {}: Init done: {}".format(self._name, initdone))
            self.logger.log(VERBOSE1, "Initializing {}: Items: {}".format(self._name, self._items))
            self._dependencies = self.init.update_dependencies(self._dependencies)
            self.logger.log(VERBOSE1,
                            "Initializing {}: Updated Dependencies: {}".format(self._name, self._dependencies))
            self.logger.log(VERBOSE1, "Initializing {}: Speaker Items: {}".format(self._name, self._items_speakers))
            try:
                try:
                    self._dependson = self.itemsApi.return_item(self._dependson)
                    self.logger.debug("Initializing {}: Dependson Item: {}.".format(self._name, self._dependson))
                except Exception:
                    self._dependson = None
                    self.logger.warning(
                        "Initializing {}: Dependson Item {} is no valid item.".format(self._name, self._dependson))
                self.logger.debug("Initializing {}: Running".format(self._name))
                self.alive = True
            except Exception as err:
                self.logger.error(
                    "Initializing {}: Problem running and creating items. Error: {}".format(self._name, err))
            finally:
                if self._tcp is not None or self._rs232 is not None:
                    self.connect('run')

    # Triggering TCP or RS232 connection schedulers
    def connect(self, trigger):
        self._trigger_reconnect = True
        if not self._is_connected:
            self._parsinginput = []
            self._is_connected.append('Connecting')
        self.logger.log(VERBOSE1, "Connecting {}: Starting to connect. Triggered by {}. Current Connections: {}".format(
            self._name, trigger, self._is_connected))
        depending = self._checkdependency(self._dependson, 'connect')
        if depending is False:
            if self._tcp is not None and 'TCP' not in self._is_connected:
                self.logger.log(VERBOSE1, "Connecting {}: Starting TCP scheduler".format(self._name))
                try:
                    self.scheduler_add('avdevice-tcp-reconnect', self.connect_tcp, cycle=7)
                except Exception as err:
                    self.logger.error(err)
                self.scheduler_change('avdevice-tcp-reconnect', active=True)
                self.scheduler_trigger('avdevice-tcp-reconnect')
                self._trigger_reconnect = False
            if self._rs232 is not None and 'Serial' not in self._is_connected:
                self.logger.log(VERBOSE1, "Connecting {}: Starting RS232 scheduler".format(self._name))
                self.scheduler_add('avdevice-serial-reconnect', self.connect_serial, cycle=7)
                self.scheduler_change('avdevice-serial-reconnect', active=True)
                self.scheduler_trigger('avdevice-serial-reconnect')
                self._trigger_reconnect = False
        elif depending is True and trigger == 'parse_dataerror':
            self._resetondisconnect('connect')

    # Connect to TCP IP
    def connect_tcp(self):
        try:
            if self._tcp is not None and 'TCP' not in self._is_connected:
                try:
                    socket = __import__('socket')
                    REQUIRED_PACKAGE_IMPORTED = True
                except:
                    REQUIRED_PACKAGE_IMPORTED = False
                if not REQUIRED_PACKAGE_IMPORTED:
                    self.logger.error("{}: Unable to import Python package 'socket'".format(self.get_fullname()))
                    self._init_complete = False
                    return
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
            cond1 = 'TCP' not in self._is_connected and self._tcp is not None
            cond2 = str(self._auto_reconnect).lower() in ['1', 'yes', 'true', 'on']
            cond3 = 'TCP' in self._is_connected and self._tcp is not None
            cond4 = self._reconnect_counter >= self._reconnect_retries
            if cond1 and cond2:
                self._trigger_reconnect = False
                self.logger.warning("Connecting TCP {}: Reconnecting. Command list while connecting: {}.".format(
                    self._name, self._send_commands))
            elif cond3 or cond4:
                self.scheduler_change('avdevice-tcp-reconnect', active=False)
                self._reconnect_counter = 0
                if cond4:
                    self._addorremove_keepcommands('disconnect', 'all')
                else:
                    self._addorremove_keepcommands('connected', 'all')
                self._trigger_reconnect = True
                self.logger.debug(
                    "Connecting TCP {}: Deactivating reconnect schedulerApi. Command list while connecting: {}. "
                    "Keep Commands: {}. Reconnecttrigger: {}".format(
                        self._name, self._send_commands, self._keep_commands, self._trigger_reconnect))
            self._reconnect_counter += 1
            if 'TCP' in self._is_connected:
                self.logger.debug("Connecting TCP {}: TCP is connected.".format(self._name))
                if not self._parsinginput:
                    self.logger.debug("Connecting TCP {}: Starting Parse Input.".format(self._name))
                    self._parse_input_init('tcpconnect')

    # Connect to RS232
    def connect_serial(self):
        try:
            if self._rs232 is not None and 'Serial' not in self._is_connected:
                try:
                    serial = __import__('serial')
                    REQUIRED_PACKAGE_IMPORTED = True
                except:
                    REQUIRED_PACKAGE_IMPORTED = False
                if not REQUIRED_PACKAGE_IMPORTED:
                    self.logger.error("{}: Unable to import Python package 'serial'".format(self.get_fullname()))
                    self._init_complete = False
                    return
                ser = serial.serial_for_url('{}'.format(self._rs232), baudrate=int(self._baud),
                                            timeout=float(self._timeout), write_timeout=float(self._timeout))
                i = 0
                try:
                    command = self._power_commands[0].split(',')[1]
                    self.logger.debug("Connecting Serial {}: Starting to connect to {} with init command {}.".format(
                        self._name, self._rs232, command))
                except Exception:
                    self.logger.warning(
                        "Connecting Serial {}: No Powercommands found. Please check your config files!".format(
                            self._name))
                    command = '?P'
                while ser.in_waiting == 0:
                    i += 1
                    self._wait(0.5)
                    ser.write(bytes('{}\r'.format(command), 'utf-8'))
                    # buffer = bytes()
                    buffer = ser.read().decode('utf-8')
                    self.logger.log(VERBOSE1,
                                    "Connecting Serial {}:  Buffer: {}. Reconnecting Retry: {}.".format(
                                        self._name, re.sub('[\r\n]', ' --- ', buffer), i))
                    if i >= 4:
                        ser.close()
                        self.logger.log(VERBOSE1,
                                        "Connecting Serial {}:  Ran through several retries.".format(self._name))
                        break
                if ser.isOpen():
                    self._serialwrapper = io.TextIOWrapper(io.BufferedRWPair(ser, ser), newline='\r\n',
                                                           encoding='utf-8', line_buffering=True)
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
                    self.logger.warning(
                        "Connecting Serial {}: Serial port is not open. Connection status: {}. Reconnect Counter: {}".format(
                            self._name, self._is_connected, self._reconnect_counter))
        except Exception as err:
            if 'Serial' in self._is_connected:
                self._is_connected.remove('Serial')
            self.logger.warning(
                "Connecting Serial {}: Could not connect to {}, baudrate {}. Error:{}, Counter: {}/{}".format(
                    self._name, self._rs232, self._baud, err, self._reconnect_counter, self._reconnect_retries))

        finally:
            cond1 = 'Serial' not in self._is_connected and self._rs232 is not None
            cond2 = str(self._auto_reconnect).lower() in ['1', 'yes', 'true', 'on']
            cond3 = 'Serial' in self._is_connected and self._rs232 is not None
            cond4 = self._reconnect_counter >= self._reconnect_retries
            if cond1 and cond2:
                self._trigger_reconnect = False
                self.logger.log(VERBOSE1,
                                "Connecting Serial {}: Activating reconnect schedulerApi. Command list while connecting: {}.".format(
                                    self._name, self._send_commands))
            elif cond3 or cond4:
                self.scheduler_change('avdevice-serial-reconnect', active=False)
                self._reconnect_counter = 0
                if cond4:
                    self._addorremove_keepcommands('disconnect', 'all')
                else:
                    self._addorremove_keepcommands('connected', 'all')
                self._trigger_reconnect = True
                self.logger.debug(
                    "Connecting Serial {}: Deactivating reconnect schedulerApi. Command list while connecting: {}. "
                    "Keep commands: {}. Reconnecttrigger: {}".format(
                        self._name, self._send_commands, self._keep_commands, self._trigger_reconnect))
            self._reconnect_counter += 1
            if 'Serial' in self._is_connected:
                self.logger.debug("Connecting Serial {}: Serial is connected.".format(self._name))
                if not self._parsinginput:
                    self.logger.debug("Connecting Serial {}: Starting Parse Input.".format(self._name))
                    self._parse_input_init('serialconnect')

    def _checkdependency(self, dep_function, dep_type):
        depending = False
        self.logger.log(VERBOSE2,
                        "Checking Dependency {}: dep_function: {}, dep_type: {}.".format(self._name, dep_function,
                                                                                         dep_type))
        cond1 = dep_type == 'statusupdate' or dep_type == 'initupdate' or dep_type == 'checkquery' or dep_type == 'keepcommand'
        cond2 = dep_type == 'update' and not dep_function == ''
        if cond1 or cond2:
            totest = queryzone = orig_function = dependitem = stopdepend = None
            if dep_type == 'statusupdate' or dep_type == 'initupdate':
                totest = self._dependencies['Slave_query']
            elif dep_type == 'update':
                totest = self._dependencies['Slave_item']
                dep_function = dep_function.id()
            elif dep_type == 'keepcommand':
                totest = self._dependencies['Slave_item']
                try:
                    dep_function = dep_function.split(';')[1]
                except Exception:
                    return False
            elif dep_type == 'checkquery':
                orig_function = dep_function
                totest = self._dependencies['Master_function']
                queryzone = orig_function.split(', ')[0]
                dep_function = orig_function.split(', ')[1]

            for zone in totest:
                cond1 = dep_function in totest[zone] and not dep_type == 'checkquery'
                cond2 = dep_type == 'checkquery' and zone == queryzone and dep_function in totest[zone]
                if cond1 or cond2:
                    donedependitems = []
                    dependtotal = comparetotal = 0
                    groupcount = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                    grouptotal = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                    dependitems = {'a': {}, 'b': {}, 'c': {}, 'd': {}}
                    for entry in totest[zone][dep_function]:
                        try:
                            func = entry['Function']
                            if func.lower() == 'init' and dep_type == 'initupdate':
                                self.logger.log(VERBOSE2,
                                                "Checking Dependency {}: Adding query because it's init dependency is set to true.".format(
                                                    self._name))
                                return False
                            elif dep_type == 'initupdate' and self._statusquery is False:
                                self.logger.log(VERBOSE2,
                                                "Checking Dependency {}: Not adding query because no init dependency defined.".format(
                                                    self._name))
                                return True
                        except Exception:
                            pass
                        try:
                            dependitem = entry['Item']
                            stopdepend = entry['Item']
                            if not dep_type == 'checkquery':
                                try:
                                    dependvalue = dependitem()
                                except Exception:
                                    dependvalue = None
                            else:
                                dependvalue = orig_function.split(', ')[2]
                                try:
                                    dependvalue = eval(dependvalue.lstrip('0'))
                                except Exception:
                                    pass
                            expectedvalue = entry['Dependvalue']
                            compare = entry['Compare']
                            group = entry['Group']
                            grouptotal[group] += 1 if dependitem not in donedependitems else 0
                            self.logger.log(VERBOSE2,
                                            "Checking Dependency {}: first: dependitem: {} expvalue: {}, dependvalue: {}, compare {}.".format(
                                                self._name, dependitem, expectedvalue, dependvalue, compare))
                            try:
                                expectedvalue = eval(expectedvalue.lstrip('0'))
                            except Exception:
                                pass
                            if type(dependvalue) == type(expectedvalue):
                                groupcount[group] += 1 if (dependvalue == expectedvalue and compare == '==') or \
                                                          (dependvalue >= expectedvalue and compare == '>=') or \
                                                          (dependvalue <= expectedvalue and compare == '<=') or \
                                                          (dependvalue < expectedvalue and compare == '<') or \
                                                          (dependvalue > expectedvalue and compare == '>') or \
                                                          (not dependvalue == expectedvalue and compare == '!=') \
                                    else 0
                            if not dep_type == 'checkquery':
                                try:
                                    dependitems[group][dependitem].append([dependvalue, compare, expectedvalue])
                                except Exception:
                                    dependitems[group].update({dependitem: [[dependvalue, compare, expectedvalue]]})
                        except Exception as err:
                            depending = False
                            self.logger.warning(
                                    "Checking Dependency {}: Adding primary {} (depending on {}) in {} caused problem: {}.".format(
                                        self._name, entry['Function'], dep_function, zone, err))

                        if dep_type == 'checkquery' and dependitem not in donedependitems:
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
                                    self.logger.log(VERBOSE2,
                                                    "Checking Dependency {}: zone: {}, additional: dependitem: {} expvalue: {}, dependvalue: {}, compare {}.".format(
                                                        self._name, additional_zone, dependitem, expectedvalue,
                                                        dependvalue, compare))
                                    try:
                                        expectedvalue = eval(expectedvalue.lstrip('0'))
                                    except Exception:
                                        pass
                                    for x in self._functions[zone]:
                                        if self._functions[zone][x][1] == additional['Function']:
                                            try:
                                                dict_entry = self._functions[zone][x][10]
                                                break
                                            except Exception:
                                                dict_entry = None
                                        else:
                                            dict_entry = None
                                    expectedvalue = Translate(expectedvalue, dict_entry, self._name, 'parse',
                                                              self._specialparse, self.logger).translate() or expectedvalue
                                    self.logger.log(VERBOSE2,
                                                    "Checking Dependency {}: Expectedvalue after Translation {}. Dependitem: {}, expected {}".format(
                                                        self._name, expectedvalue, dependitem, expectedvalue))
                                    if type(dependvalue) == type(expectedvalue):
                                        groupcount[group] += 1 if (dependvalue == expectedvalue and compare == '==') or \
                                                                  (dependvalue >= expectedvalue and compare == '>=') or \
                                                                  (dependvalue <= expectedvalue and compare == '<=') or \
                                                                  (dependvalue < expectedvalue and compare == '<') or \
                                                                  (dependvalue > expectedvalue and compare == '>') or \
                                                                  (not dependvalue == expectedvalue and compare == '!=') \
                                            else 0
                                    try:
                                        dependitems[group][dependitem].append([dependvalue, compare, expectedvalue])
                                    except Exception:
                                        dependitems[group].update({dependitem: [[dependvalue, compare, expectedvalue]]})
                            except Exception as err:
                                depending = False
                                self.logger.warning(
                                    "Checking Dependency {}: Adding {} (depending on {}) in {} caused problem: {}.".format(
                                        self._name, entry['Function'], dep_function, zone, err))
                            self.logger.log(VERBOSE2,
                                            "Checking Dependency {}: Zone: {}, Groupcount: {}, Grouptotal: {}. Primarycount: {}".format(
                                                self._name, additional_zone, groupcount, grouptotal, primarycount))
                            comparetotal = 0
                            dependtotal = 0
                            for group in grouptotal:
                                if grouptotal[group] > 0:
                                    comparetotal += 1
                                    dependtotal += 1 if groupcount.get(group) > 0 else 0
                            try:
                                queryentry = entry['Query']
                            except Exception as err:
                                self.logger.log(VERBOSE2,
                                                "Checking Dependency {}: Dependent functions found for {}. "
                                                "But no Query command for {}. Message: {}".format(
                                                    self._name, dep_function, entry['Function'], err))
                                queryentry = None
                            if dependtotal == comparetotal:
                                if primarycount > 0 and queryentry is not None:
                                    if queryentry not in self._send_commands:
                                        self._send_commands.append(queryentry)
                                        self._send_history['query'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = queryentry
                                        self.logger.debug(
                                            "Checking Dependency {}: Dependent Query command {} added to Send Commands. Dependencies: {}".format(
                                                self._name, queryentry, dependitems))
                                    else:
                                        self.logger.log(VERBOSE2,
                                                        "Checking Dependency {}: Dependent Query command {} already in send commands: {}.".format(
                                                            self._name, queryentry, self._send_commands))
                                else:
                                    self.logger.log(VERBOSE2,
                                                    "Checking Dependency {}: Primary dependency not fullfilled,"
                                                    " not adding or removing query  {}".format(self._name, queryentry))
                            elif primarycount == 0 and queryentry is not None:
                                try:
                                    self._send_commands.remove(queryentry)
                                    self._clearbuffer = True if not self._send_commands else False
                                    self.logger.debug(
                                        "Checking Dependency {}: Dependent Query command {} removed from Send Commands. Dependencies: {}".format(
                                            self._name, queryentry, self._send_commands, dependitems))
                                except Exception:
                                    self.logger.log(VERBOSE2,
                                                    "Checking Dependency {}: Dependent Query command {} not in Send Commands, not removing it."
                                                    " Dependencies: {}".format(self._name, queryentry, dependitems))
                            else:
                                self.logger.log(VERBOSE2,
                                                "Checking Dependency {}: Primary dependency not fullfilled. Doing nothing.".format(
                                                    self._name))
                            donedependitems.append(stopdepend)
                            groupcount = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                            grouptotal = {'a': 0, 'b': 0, 'c': 0, 'd': 0}
                            dependitems = {'a': {}, 'b': {}, 'c': {}, 'd': {}}
                    if not dep_type == 'checkquery':
                        self.logger.log(VERBOSE2,
                                        "Checking Dependency {}: Groupcount: {}, Grouptotal: {}.".format(
                                            self._name, groupcount, grouptotal))
                        comparetotal = 0
                        dependtotal = 0
                        for group in grouptotal:
                            if grouptotal[group] > 0:
                                comparetotal += 1
                                dependtotal += 1 if groupcount.get(group) > 0 else 0
                    if dependtotal == comparetotal and not dep_type == 'checkquery':
                        depending = False
                        self.logger.log(VERBOSE1,
                                        "Checking Dependency {}: Adding function {} because dependency fullfilled: {}.".format(
                                            self._name, dep_function, dependitems))
                    elif not dep_type == 'checkquery':
                        depending = True
                        self.logger.debug(
                            "Checking Dependency {}: Not adding function {} because dependency not fullfilled: {}".format(
                                self._name, dep_function, dependitems))
                    if depending is True and dep_type == 'update':
                        self.logger.log(VERBOSE2,
                                        "Checking Dependency {}: Starting to reset item: {}.".format(self._name,
                                                                                                     dep_function))
                        self._resetitem(dep_function)
                elif dep_type == 'initupdate' and self._statusquery is False:
                    depending = True

        elif dep_type == 'globaldepend' or dep_type == 'parseinput' or dep_type == 'connect' or dep_type == 'dependitem':
            try:
                dependsvalue = self._dependson()
                self.logger.debug(
                    "Checking Dependency {}: Connection depends on {}. It's value is {}, has to be {}. Connections are {}".format(
                        self._name, self._dependson, dependsvalue, self._dependson_value, self._is_connected))
                if dependsvalue == self._dependson_value:
                    depending = False
                    if dep_type == 'dependitem':
                        try:
                            eval(self._items['zone0']['statusupdate']['Item'])(1, 'Depending',
                                                                               self._rs232 or self._tcp)
                        except Exception:
                            try:
                                self._items['zone0']['statusupdate']['Item'](1, 'Depending',
                                                                             self._rs232 or self._tcp)
                            except Exception:
                                pass
                else:
                    depending = True
                    try:
                        item = self.itemsApi.return_item(dep_function).id()
                    except Exception:
                        item = dep_function.id()
                    if not item == self._dependson.id():
                        self.logger.log(VERBOSE2,
                                        "Checking Dependency {}: Starting to reset item: {}.".format(self._name, item))
                        self._resetitem(item)
                    if dep_type == 'connect':
                        self._is_connected = []
                        self._parsinginput = []
                    if dep_type == 'parseinput' or dep_type == 'dependitem':
                        self._resetondisconnect('parseinput')
            except Exception as e:
                depending = False
                self.logger.log(VERBOSE1,
                                "Checking Dependency {}: Globally assigned Dependency is false. Message: {}".format(
                                    self._name, e))
        self.logger.log(VERBOSE2, "Checking Dependency {}: Returning {}".format(self._name, depending))
        return depending

    # Updating Status even if no statusupdate is defined in device text file
    def _statusupdate(self, value, trigger, caller):
        self.logger.debug(
            "Statusupdate {}: Value: {}. Trigger from {}. Caller: {}".format(self._name, value, trigger, caller))
        self.update_item('statusupdate', 'Init')

    # Adding Keep Commands to Send Commands
    def _addorremove_keepcommands(self, trigger, zone):
        self.logger.log(VERBOSE1,
                        "Keep Commands {}: Trigger from {} for zone {}. Send Commands: {}".format(
                            self._name, trigger, zone, self._send_commands))
        if trigger == 'removefromkeep':
            deletekeep = []
            data = zone
            for zeit in self._keep_commands:
                self.logger.log(VERBOSE1,
                                "Parsing Input {}: Testing Keep Command {} with age of {}s".format(
                                    self._name, zeit, int(time.time() - zeit)))
                if data in self._keep_commands.get(zeit).split(',')[2].split('|'):
                    self.logger.debug(
                        "Parsing Input {}: Removing {} from Keep Commands {} because corresponding value received.".format(
                            self._name, zeit, self._keep_commands))
                    deletekeep.append(zeit)
                elif time.time() - zeit >= self._secondstokeep:
                    self.logger.debug(
                        "Parsing Input {}: Removing {} from Keep Commands {} because age is {}s.".format(
                            self._name, zeit, self._keep_commands, int(time.time() - zeit)))
                    deletekeep.append(zeit)
            for todelete in deletekeep:
                self._keep_commands.pop(todelete)
        elif trigger == 'addtokeep' or trigger == 'disconnect':
            for command in self._send_commands:
                self.logger.log(VERBOSE1,
                                "Parsing Input {}: Going to reset in the end because connection is lost: {}.".format(
                                    self._name, command))
                cond1 = command not in self._query_commands
                cond2 = command not in self._special_commands['Display']['Command']
                cond3 = self._sendingcommand == 'gaveup'
                if cond1 and cond2 and not cond3:
                    self._keep_commands[time.time()] = self._sendingcommand = command
                    self.logger.debug(
                        "Parsing Input {}: Removing item {} from send command because not connected, storing in keep commands: {}.".format(
                            self._name, command, self._keep_commands))
                if not self._send_commands[0].split(',')[0] == self._send_commands[0].split(',')[1]:
                    self._resetitem('')
                self._send_commands.pop(0)
                self.logger.debug(
                    'Parsing Input {}: First entry from send_commands removed. Send commands are now: {}'.format(
                        self._name, self._send_commands))
        else:
            keeptemp = []
            for zeit in self._keep_commands:
                keeping = False
                if time.time() - zeit <= self._secondstokeep and not self._keep_commands[zeit] in keeptemp:
                    try:
                        for itemlist in self._query_zonecommands['{}'.format(zone)]:
                            keeping = True if itemlist.split(',')[1] == self._keep_commands[zeit].split(',')[1] else False
                    except Exception:
                        self.logger.log(VERBOSE2, "Keep Commands {}: Zone is set to all.".format(self._name))
                    try:
                        keeping = not self._checkdependency(self._keep_commands[zeit], 'keepcommand')
                    except Exception as err:
                        self.logger.log(VERBOSE2, "Keep Commands {}: Problem checking dependency: {}.".format(self._name, err))
                    if zone == 'all' or keeping is True or trigger == 'powercommand':
                        keeping = True
                        keeptemp.append(self._keep_commands[zeit])
                self.logger.debug("Keep Commands {}: Age {}s of command {}. Secondstokeep: {}. Keeping command: {}".format(
                    self._name, int(time.time() - zeit), self._keep_commands[zeit], self._secondstokeep, keeping))
            self._send_commands = self._send_commands + list(set(keeptemp))
            seen = set()
            self._send_commands = [x for x in self._send_commands if x not in seen and not seen.add(x)]
            self._keep_commands = {}

    # Parsing the response and comparing it with expected response
    def _parse_input_init(self, trigger):
        if not self._is_connected == [] and not self._is_connected == ['Connecting']:
            self._parsinginput.append(trigger)
        else:
            self._parsinginput = []
        self.logger.log(VERBOSE1, "Parsing Input {}: Init Triggerd by these functions so far: {}".format(
            self._name, self._parsinginput))
        if trigger == 'tcpconnect' or trigger == 'serialconnect':
            for zone in self._init_commands:
                if len(self._init_commands[zone].keys()) > 0:
                    for init in self._init_commands[zone]:
                        try:
                            initvalue = self._init_commands[zone][init]['Inititem']()
                            self.logger.log(VERBOSE1,
                                            "Parsing Input {}: Starting eval init: {} for {} with value {}".format(
                                                self._name, init, zone, initvalue))
                            eval(self._init_commands[zone][init]['Item'])(initvalue, 'Init', self._tcp)
                            self.logger.debug(
                                "Parsing Input {}: Updated Item after connection: {} with value {}. Commandlist: {}".format(
                                    self._name, self._init_commands[zone][init]['Item'], initvalue,
                                    self._send_commands))
                        except Exception as err:
                            try:
                                initvalue = self._init_commands[zone][init]['Inititem']()
                                self.logger.log(VERBOSE1,
                                                "Parsing Input {}: Starting exception init: {} for {}. Message: {}".format(
                                                    self._name, init, zone, err))
                                self._init_commands[zone][init]['Item'](initvalue, 'Init', self._tcp)
                                self.logger.debug(
                                    "Parsing Input {}: Updated Item after connection: {} with value {}. Commandlist: {}".format(
                                        self._name, self._init_commands[zone][init]['Item'], initvalue,
                                        self._send_commands))
                            except Exception as err:
                                self.logger.log(VERBOSE1,
                                                "Parsing Input {}: No init defined, not executing command after {}. Message: {}".format(
                                                    self._name, trigger, err))
            try:
                self.logger.log(VERBOSE1, "Parsing Input {}: Starting eval statusupdate.".format(self._name))
                eval(self._items['zone0']['statusupdate']['Item'])(1, 'Init', self._tcp)
                self.logger.debug(
                    "Parsing Input {}: Updated Item after connection: {} with value 1. Commandlist: {}".format(
                        self._name, self._items['zone0']['statusupdate']['Item'], self._send_commands))
            except Exception:
                try:
                    self.logger.log(VERBOSE1, "Parsing Input {}: Starting exception statusupdate.".format(self._name))
                    self._items['zone0']['statusupdate']['Item'](1, 'Init', self._tcp)
                    self.logger.debug(
                        "Parsing Input {}: Updated Item after connection: {} with value 1. Commandlist: {}".format(
                            self._name, self._items['zone0']['statusupdate']['Item'], self._send_commands))
                except Exception as err:
                    self.logger.log(VERBOSE1,
                                    "Parsing Input {}: No statusupdate defined, not querying status after {}. Message: {}".format(
                                        self._name, trigger, err))
        if len(self._parsinginput) == 1:
            self._parse_input(trigger)

    def _checkforerror(self, _data, depending=False):
        if self._resend_counter >= self._resend_retries or depending is True:
            self.logger.warning(
                "Parsing Input {}: Giving up Sending {} and removing from list. Original Commandlist: {}".format(
                    self._name, self._sendingcommand, self._send_commands))
            self._resend_counter = 0
            self.logger.log(VERBOSE1,
                            "Parsing Input {}: Resetting Resend Counter because maximum retries exceeded.".format(self._name))
            try:
                cond1 = self._send_commands[0] not in self._query_commands
                cond2 = self._send_commands[0] not in self._special_commands['Display']['Command']
                if cond1 and cond2:
                    self._sendingcommand = self._send_commands[0]
                    if self._reset_onerror is True:
                        self._resetitem('')
                    self._keep_commands[time.time()] = self._send_commands[0]
                    self.logger.debug(
                        "Parsing Input {}: Giving up and removing item from send command, storing in keep commands: {}.".format(
                            self._name, self._keep_commands))
                self._send_commands.pop(0)
                try:
                    self._expected_response.pop(0)
                except Exception:
                    pass
                if not self._send_commands == []:
                    sending = self._send('command', 'parseinput')
                    self.logger.log(VERBOSE1,
                                    "Parsing Input {}: Command List is now: {}. Sending return is {}.".format(
                                        self._name, self._send_commands, sending))
            except Exception as err:
                self.logger.debug(
                    "Parsing Input {}: Nothing to remove from Send Command List. Error: {}".format(self._name, err))
                if self._reset_onerror is True:
                    self._resetitem('')
            self._sendingcommand = 'gaveup'
            if _data == 'ERROR':
                connectionproblem = True
                if self._trigger_reconnect is True:
                    self.logger.log(VERBOSE1,
                                    "Parsing Input {}: Trying to connect while parsing item".format(self._name))
                    self.connect('parse_input')
            else:
                connectionproblem = False
            return connectionproblem
        else:
            return False

    # Parsing the response and comparing it with expected response
    def _parse_input(self, trigger):
        self.logger.log(VERBOSE1, "Parsing Input {}: Triggerd by {}".format(self._name, trigger))

        def _deletecommands(_del_expectedresponse, _del_data, _del_valuetype):
            self.logger.log(VERBOSE2, "Parsing Input {}: del_expectedresponse: {}, del_data: {}, del_valuetype: {}".format(
                self._name, _del_expectedresponse, _del_data, _del_valuetype))

            def _foundappend(_foundexpected, _data):
                parse_expectedlist = _foundexpected.split('|')
                _found = []
                try:
                    for expectedpart in parse_expectedlist:
                        try:
                            datalength = self._response_commands[expectedpart][0][1]
                            expectedlength = []
                            stringvalue = []

                            for vals in self._response_commands[expectedpart]:
                                stringvalue.append(True if int(vals[0]) == 100 or int(
                                    vals[1]) == 100 else False)
                                expectedlength.append(int(vals[1]))
                                datalength = int(vals[2]) if datalength > int(
                                    vals[2]) > 0 else datalength
                            self.logger.log(VERBOSE2,
                                            "Parsing Input {}: Comparing Data {} (cut: {}) to: {},"
                                            " expectedlength: {}, datalength: {}, string: {}.".format(
                                                self._name, _data, _data[:datalength],
                                                expectedpart, expectedlength, len(_data),
                                                stringvalue))
                            if _data[:datalength].startswith(expectedpart) and (
                                    len(_data) in expectedlength or True in stringvalue):
                                _found.append(expectedpart)
                                self.logger.log(VERBOSE1,
                                                "Parsing Input {}: Expected response edited: {}.".format(
                                                    self._name, _found))
                        except Exception:
                            _found.append(expectedpart)
                            self.logger.log(VERBOSE1,
                                            "Parsing Input {}: Expected response edited 2nd try: {}.".format(
                                                self._name, _found))
                except Exception as depend_err:
                    _found.append(_foundexpected)
                    self.logger.debug(
                        "Parsing Input {}: Expected response after exception: {}. Problem: {}".format(
                            self._name, _found, depend_err))
                self.logger.log(VERBOSE1, "Parsing Input {}: Found: {}.".format(self._name, _found))
                return _found, parse_expectedlist

            runthrough = []
            del_commands = []
            for expected in _del_expectedresponse:
                if expected not in runthrough and not _del_data == 'ERROR':
                    runthrough.append(expected)
                    found, expectedlist = _foundappend(expected, _del_data)
                    try:
                        if _del_data.startswith(tuple(found)):
                            self.logger.log(VERBOSE1,
                                            "Parsing Input {}: Expected response edited {}. Data {} starts with one of the entries."
                                            " Resetting resend counter".format(self._name, found, _del_data))
                            _entry, _value, _del_valuetype = self._write_itemsdict(_del_data, found)
                            self._sendingcommand = 'done'
                            self._resend_counter = 0
                        elif expectedlist[0] in ['', ' ', 'none']:
                            self._sendingcommand = 'done'
                            self._resend_counter = 0
                            self.logger.log(VERBOSE1,
                                            "Parsing Input {}: No response expected. Resend Counter reset.".format(
                                                self._name))
                        if _del_data.startswith(tuple(found)):
                            # only add send command to list again if response doesn't fit to corresponding command
                            expectedindices = _duplicateindex(_del_expectedresponse, expected)
                            self.logger.log(VERBOSE2, "Parsing Input {}: expectedindices {}.".format(
                                self._name, expectedindices))
                            for expectedindex in expectedindices:
                                self.logger.log(VERBOSE2,
                                                "Parsing Input {}: expected {}, deletecommands {}.".format(
                                                    self._name, self._send_commands[expectedindex],
                                                    del_commands))
                                if self._send_commands[expectedindex] not in del_commands:
                                    parse_expectedtype = \
                                        self._send_commands[expectedindex].split(';')[0].split('|')[0].split(',') \
                                        if self._send_commands[expectedindex].split(',', 2)[2].find('|') >= 0 \
                                        else self._send_commands[expectedindex].split(';')[0].split(',')
                                    try:
                                        int(parse_expectedtype[-1])
                                        length = len(parse_expectedtype) - 1
                                    except Exception:
                                        length = len(parse_expectedtype)
                                    try:
                                        parse_expectedtype[3:length] = [','.join(parse_expectedtype[3:length])]
                                        testvalue = parse_expectedtype[3]
                                    except Exception:
                                        testvalue = ''
                                    if not _del_valuetype == testvalue or not found or _del_data == 'ERROR':
                                        self.logger.log(VERBOSE2,
                                                        "Parsing Input {}: Test Value {} of {} is not same as Valuetype:"
                                                        "{} or nothing found {}. Keeping in Sendcommands.".format(
                                                            self._name, testvalue, self._send_commands[expectedindex],
                                                            _del_valuetype, found))
                                    elif not _del_data == 'ERROR':
                                        del_commands.append(self._send_commands[expectedindex])
                                        self.logger.log(VERBOSE1,
                                                        "Parsing Input {}: Test Value {} of {} is same as Valuetype: {}. Removing from Sendcommands.".format(
                                                            self._name, testvalue,
                                                            self._send_commands[expectedindex],
                                                            _del_valuetype))
                        else:
                            self.logger.log(VERBOSE1,
                                            "Parsing Input {}: Expected response edited {}. Data {} is different, not deleting"
                                            " the command from sendcommands.".format(self._name, found, _del_data))
                    except Exception as _err:
                        self.logger.log(VERBOSE1,
                                        "Parsing Input {}: Deleting commands problem: {}".format(self._name, _err))
            return del_commands

        def _duplicateindex(seq, seqitem):
            start_at = -1
            locs = []
            while True:
                try:
                    loc = seq.index(seqitem, start_at + 1)
                except ValueError:
                    break
                else:
                    locs.append(loc)
                    start_at = loc
            return locs

        while self.alive and not self._parsinginput == [] and not self._is_connected == [] and not self._is_connected == ['Connecting']:
            connectionproblem = False
            if self._sendingcommand not in ['', 'done', 'gaveup']:
                self.logger.log(VERBOSE1,
                                "Parsing Input {}: Starting to parse input. Alive: {}. Connected: {}. Parsinginput: {}. Sendcommand: {}".format(
                                    self._name, self.alive, self._is_connected, self._parsinginput, self._sendingcommand))
            to_send = 'command'
            data = 'waiting'
            item = None
            try:
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
                else:
                    self._sendingcommand = 'gaveup'
                    break
                for data_part in databuffer:
                    data = data_part.strip()
                    if data == 'ERROR' and self._sendingcommand not in ['gaveup', 'done']:
                        self._checkforerror(data)

                    sorted_response_commands = sorted(self._response_commands, key=len, reverse=True)
                    for i in range(0, len(sorted_response_commands)):
                        try:
                            sorted_response_commands[i] = self._response_wildcards['original'][sorted_response_commands[i]]
                        except Exception as err:
                            sorted_response_commands[i] = None
                            self.logger.log(VERBOSE2,
                                            "Parsing Input {}: Can not find wildcard equivalent for: {}".format(
                                                self._name, err))
                    sorted_response_commands = [value for value in sorted_response_commands if
                                                (value is not None and '?' not in value)]
                    self.logger.log(VERBOSE2,
                                    "Parsing Input {}: New Response Command list after sorting: {}".format(
                                        self._name, sorted_response_commands))

                    self.logger.debug("Parsing Input {}: Response: {}. Send Commands: {}".format(
                        self._name, data, self._send_commands))
                    updated = 0
                    if (data == 'ERROR' and self._send_commands == []) or data in self._error_response:
                        self._resend_counter += 1
                        updated = 1
                        self.logger.debug(
                            "Parsing Input {}: Response {} is in error responses. Resend counter: {}".format(
                                self._name, data, self._resend_counter))
                        self._checkforerror(data)
                        if not self._sendingcommand == 'gaveup' and not self._send_commands == []:
                            to_send = 'query' if (self._resend_counter % 2 == 1 and not
                                                  self._send_commands[0].split(',')[1] == '') else 'command'
                            self.logger.debug(
                                "Parsing Input {}: Requesting {} from {} because response was {}. Resend Counter: {}".format(
                                    self._name, to_send, self._send_commands[0], data, self._resend_counter))
                            self._wait(self._resend_wait)
                    elif data == 'none' and not self._send_commands:
                        self._sendingcommand = 'done'
                        break
                    elif self._send_commands:
                        self.logger.debug("Parsing Input {}: Expected response while parsing: {}.".format(
                            self._name, self._expected_response))

                        try:
                            to_send = 'command'
                            valuetype = 'empty'
                            deletecommands = []
                            deleteexpected = []
                            if not self._expected_response == []:
                                deletecommands = _deletecommands(self._expected_response, data, valuetype)
                                deleteexpected = [x.split(',')[2].split('*')[0] for x in deletecommands]
                                self.logger.log(VERBOSE2,
                                                "Parsing Input {}: Deleting {} from sendcommands and {} "
                                                "from expected response.".format(self._name, deletecommands, deleteexpected))
                            self._send_commands = [x for x in self._send_commands if x not in set(deletecommands)]
                            self._expected_response = [x for x in self._expected_response if x not in set(deleteexpected)]
                            self.logger.log(VERBOSE1,
                                            "Parsing Input {}: Sendcommands: {}. Sendingcommand: {}. Expected Response: {}.".format(
                                                self._name, self._send_commands, self._sendingcommand, self._expected_response))
                            if self._send_commands and not self._sendingcommand == 'done':
                                self._resend_counter += 1
                                depending = self._checkdependency('', 'parseinput')
                                connectionproblem = self._checkforerror(data, depending)

                                if not self._sendingcommand == 'gaveup':
                                    to_send = 'query' if (self._resend_counter % 2 == 1 and not
                                                          self._send_commands[0].split(',')[1] == '') else 'command'
                                    self.logger.debug(
                                        "Parsing Input {}: Requesting {} from {} because response was {}. Resend Counter: {}".format(
                                            self._name, to_send, self._send_commands[0], data, self._resend_counter))
                                    self._wait(self._resend_wait)
                        except Exception as err:
                            self.logger.warning(
                                "Parsing Input {}: Problems with checking for expected response. Error: {}".format(self._name, err))

                    if not data == 'ERROR' and data not in self._error_response and not data == 'none':
                        self.logger.log(VERBOSE1,
                                        "Parsing Input {}: Starting to compare values for data {} with {}.".format(
                                            self._name, data, sorted_response_commands))

                        for dictkey in sorted_response_commands:
                            comparekey = self._response_wildcards['wildcard'][dictkey]
                            self.logger.log(VERBOSE2,
                                            "Parsing Input {}: Starting to compare values for data {} with key: {} (before wildcard processing: {}).".format(
                                                self._name, data, dictkey, comparekey))
                            if data == comparekey and not self._send_commands == []:
                                self._send_commands = [x for x in self._send_commands if comparekey not in x]
                                self._sendingcommand = self._send_commands[0] if self._sendingcommand not in self._send_commands and \
                                    self._send_commands else self._sendingcommand
                                self.logger.debug(
                                    "Parsing Input {}: Response is identical to expected response. Cleaned Send Commands: {}".format(
                                        self._name, self._send_commands))
                            for entry in self._response_commands[comparekey]:
                                valuelength = entry[0]
                                responseposition = entry[2]
                                item = entry[3]
                                expectedtype = entry[7]
                                index = data.find(dictkey)
                                if index == 0:
                                    av_function = entry[4]
                                    zone = entry[5]
                                    receivedvalue = origvalue = ''
                                    cond1 = data.startswith(self._special_commands['Display']['Command'])
                                    cond2 = not self._special_commands['Display']['Command'] == ''
                                    cond3 = data.startswith(tuple(self._special_commands['Nowplaying']['Command']))
                                    cond4 = not self._special_commands['Nowplaying']['Command'] == ''
                                    cond5 = data.startswith(tuple(self._special_commands['Speakers']['Command']))
                                    cond6 = not self._special_commands['Speakers']['Command'] == ''
                                    if cond1 and cond2:
                                        received = ConvertValue(
                                            data[responseposition:responseposition + valuelength], expectedtype, False,
                                            valuelength, self._special_commands['Display']['Command'],
                                            self._name, self._special_commands, self.logger).convert_value()
                                        self.logger.debug(
                                            "Parsing Input {}: Displaycommand found in response {}. Converted to {}.".format(
                                                self._name, data, receivedvalue))
                                        try:
                                            receivedtype, receivedvalue = received[0], received[1]
                                            if receivedtype == 'nowplaying':
                                                self.logger.info("Parsing Input {}: Now playing {}".format(
                                                    self._name, receivedvalue))
                                                self._special_commands['Nowplaying']['Item'](
                                                    receivedvalue, 'AVDevice', self._tcp)
                                            elif receivedtype == 'station':
                                                for singleitem in self._special_commands['Input']['Item']:
                                                    if singleitem() == 'IRADIO':
                                                        self.logger.info(
                                                            "Parsing Input {}: Internet radio station {}".format(
                                                                self._name, receivedvalue))
                                                        self._items['zone0']['station'](
                                                            receivedvalue, 'AVDevice', self._tcp)
                                            else:
                                                self.logger.info(
                                                    "Parsing Input {}: Found Display information {}".format(
                                                        self._name, receivedvalue))
                                        except Exception:
                                            receivedvalue = received

                                    elif cond3 and cond4:
                                        self.logger.debug(
                                            "Parsing Input {}: Now playing info found in response {}.".format(
                                                self._name, data))
                                        try:
                                            m = re.search('"(.+?)"', data)
                                            receivedvalue = m.group(1) if m else ''
                                        except Exception as err:
                                            self.logger.debug(
                                                "Parsing Input {}: Problems reading Now Playing info. Error:{}".format(
                                                    self._name, err))
                                    elif cond5 and cond6:
                                        self.logger.debug(
                                            "Parsing Input {}: Speakers info found in response {}. Command: {}".format(
                                                self._name, data, self._special_commands['Speakers']['Command']))
                                        receivedvalue = ConvertValue(
                                            data[responseposition:responseposition + valuelength], expectedtype, False,
                                            valuelength, self._special_commands['Speakers']['Command'], self._name,
                                            self._special_commands, self.logger).convert_value()
                                        try:
                                            for _ in self._special_commands['Speakers']['Command']:
                                                for zone in self._items_speakers:
                                                    for speakerlist in self._items_speakers[zone]:
                                                        speaker_ab = sum(map(int, self._items_speakers[zone].keys()))
                                                        self.logger.debug(
                                                            "Parsing Input {}: Received value: {}. Speaker {}. speaker_ab: {}".format(
                                                                self._name, receivedvalue, speakerlist, speaker_ab))
                                                        speaker = self._items_speakers[zone][speakerlist]['Item']
                                                        if receivedvalue == int(speakerlist) or receivedvalue == speaker_ab:
                                                            self.logger.info(
                                                                "Parsing Input {}: Speaker {} is on.".format(
                                                                    self._name, speaker))
                                                            speaker(1, 'AVDevice', self._tcp)
                                                        else:
                                                            self.logger.info(
                                                                "Parsing Input {}: Speaker {} is off.".format(
                                                                    self._name, speaker))
                                                            speaker(0, 'AVDevice', self._tcp)

                                        except Exception as err:
                                            self.logger.warning(
                                                "Parsing Input {}: Problems reading Speakers info. Error:{}".format(
                                                    self._name, err))
                                    else:
                                        origvalue = value = receivedvalue = data[responseposition:responseposition + valuelength]
                                        self.logger.log(VERBOSE1,
                                                        "Parsing Input {}: Neither Display nor Now Playing in response. receivedvalue: {}.".format(
                                                            self._name, receivedvalue))

                                        invert = True if entry[6].lower() in ['1', 'true', 'yes', 'on'] else False
                                        if not receivedvalue == '':
                                            receivedvalue = ConvertValue(value, expectedtype, invert, valuelength,
                                                                         data, self._name,
                                                                         self._special_commands, self.logger).convert_value()
                                    try:
                                        sametype = True if isinstance(receivedvalue, eval(expectedtype)) else False
                                    except Exception:
                                        sametype = True if receivedvalue == '' and expectedtype == 'empty' else False
                                        receivedvalue = True if receivedvalue == '' and expectedtype == 'empty' else receivedvalue
                                    if sametype is False:
                                        self.logger.log(VERBOSE1,
                                                        "Parsing Input {}: Receivedvalue {} does not match type {} - ignoring it.".format(
                                                            self._name, receivedvalue, expectedtype))
                                    else:
                                        self.logger.log(VERBOSE1,
                                                        "Parsing Input {}: Receivedvalue {} does match type {} - going on.".format(
                                                            self._name, receivedvalue, expectedtype))
                                        self._displayignore(data, receivedvalue, 'parsing')
                                        value = receivedvalue
                                        self.logger.debug(
                                            "Parsing Input {}: Found key {} in response at position {} with value {}.".format(
                                                self._name, dictkey, responseposition, value))
                                        self._addorremove_keepcommands('removefromkeep', data)
                                        value = Translate(origvalue, entry[9], self._name, 'parse',
                                                          self._specialparse, self.logger).translate() or value
                                        if av_function in self._items[zone].keys():
                                            self._items[zone][av_function]['Value'] = value
                                            self.logger.log(VERBOSE1,
                                                            "Parsing Input {}: Updated Item dict {} with value {}.".format(
                                                                self._name, av_function, value))

                                        item(value, 'AVDevice', self._tcp)
                                        self.logger.debug("Parsing Input {}: Updated Item {} with {} Value: {}.".format(
                                            self._name, item, expectedtype, value))
                                        if av_function in self._items[zone].keys():
                                            self._checkdependency('{}, {}, {}'.format(zone, av_function, value),
                                                                  'checkquery')

                                        # TOTEST
                                        try:
                                            testcommand = data.split('?')[0]
                                            commandstarts = [x.split('?')[0] for x in self._response_commands if x.split('?')[0] in testcommand and x.split('?')[0]]
                                            self.logger.log(VERBOSE1,
                                                            "Parsing Input {}: Commandstarts {}. testcommand {}".format(
                                                                self._name, commandstarts, testcommand))
                                            updated = 1 if len(commandstarts) >= 1 or testcommand == 'none' else 0
                                        except Exception as err:
                                            self.logger.error(
                                                "Parsing Input {}: Problem with new tests {}".format(self._name, err))
                                        self._wait(0.15)

                                        if updated == 1:
                                            self.logger.log(VERBOSE1,
                                                            "Parsing Input {}: Updated all relevant items from item {}. step 1".format(
                                                                self._name, item))
                                            break
                                    if updated == 1:
                                        self.logger.log(VERBOSE1,
                                                        "Parsing Input {}: Updated all relevant items from {}. step 2".format(
                                                            self._name, item))
                                        break

                                if updated == 1:
                                    self.logger.log(VERBOSE1,
                                                    "Parsing Input {}: Updated all relevant items from {}. step 3".format(
                                                        self._name, item))
                                    break
                            if updated == 1:
                                self.logger.log(VERBOSE1,
                                                "Parsing Input {}: Updated all relevant items from {}. step 4".format(
                                                    self._name, item))
                                break
                        self.logger.log(VERBOSE2, "Parsing Input {}: Finished comparing values.".format(self._name))
                        if not self._send_commands:
                            self._sendingcommand = 'done'
            except Exception as err:
                self.logger.error("Parsing Input {}: Problems parsing input. Error: {}".format(self._name, err))
            finally:
                if not self._send_commands:
                    self._displayignore('', None, 'parsing_final')
                elif not self._send_commands == [] and data == 'waiting':
                    self.logger.log(VERBOSE2, "Parsing Input {}: Waiting for response..".format(self._name))
                elif not self._send_commands == [] and not data == 'waiting':
                    reorderlist = []
                    index = 0
                    for command in self._send_commands:
                        command_split = command.split(';')[0]
                        try:
                            commanditem = command.split(';')[1]
                        except Exception:
                            commanditem = None
                        if commanditem:
                                command = '{};{}'.format(command_split, commanditem)
                        self.logger.log(VERBOSE1,
                                        "Parsing Input {}: Adding command commandsplit {}, commanditem {}. Command: {}".format(
                                                self._name, command_split, commanditem, command))
                        if command_split in self._query_commands:
                            reorderlist.append(command)
                        elif command_split in self._power_commands:
                            self.logger.log(VERBOSE1,
                                            "Parsing Input {}: Adding command and ordering power command {} to first position.".format(
                                                self._name, command))
                            reorderlist.insert(0, command)
                            index += 1
                        else:
                            reorderlist.insert(index, command)
                            self.logger.log(VERBOSE1,
                                            "Parsing Input {}: Adding command {} to position {}.".format(
                                                self._name, command, index))
                            index += 1
                    self._send_commands = reorderlist
                    self.logger.debug(
                        'Parsing Input {}: Newly sorted send commands at end of parsing: {}'.format(self._name,
                                                                                                    self._send_commands))
                    if not self._is_connected:
                        self.logger.log(VERBOSE2,
                                        "Parsing Input {}: Not connected.".format(self._name))
                        self._addorremove_keepcommands('addtokeep', '')
                    else:
                        sending = self._send('{}'.format(to_send), 'parseinput_final')
                        self.logger.log(VERBOSE1,
                                        "Parsing Input {}: Sending again because list is not empty yet. Sending return is {}.".format(
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
                        self.logger.log(VERBOSE1,
                                        "Parsing Input {}: Trying to connect while parsing item".format(self._name))
                        self.connect('parse_dataerror')

    # Updating items based on value changes via Visu, CLI, etc.
    def update_item(self, item, caller=None, source=None, dest=None):

        def _replace_setcommand(replace_commandinfo, replace_dict, replace_command, replace_value, replace_type):
            set_appending = True
            set_removefromkeeping = []
            for sendcommand in replace_dict:
                keepdict = sendcommand
                sendcommand = replace_dict.get(sendcommand) if replace_type == 'keep' else sendcommand
                commandlist = self._keep_commands if replace_type == 'keep' else self._send_commands
                self.logger.log(VERBOSE1, "Updating Item {}: Testing {} command: {}".format(self._name, replace_type, sendcommand))
                if replace_commandinfo[3] in sendcommand:
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
                                        self._name, testvalues, replace_commandinfo[9]))
                    if replace_commandinfo[9] in testvalues:
                        self.logger.log(VERBOSE1,
                                        "Updating Item {}: Command Set {} ({}) already in Commandlist {}."
                                        " Value type: {}, expected type: {}. Replaced. Sendingcommand: {}".format(
                                            self._name, command, replace_commandinfo[3],
                                            commandlist, type(replace_value), replace_commandinfo[9],
                                            self._sendingcommand))
                        if replace_type == 'keep':
                            set_removefromkeeping.append(keepdict)
                        else:
                            commandlist[commandlist.index(sendcommand)] = replace_command
                            self._sendingcommand = replace_command
                        self._resend_counter = 0
                        set_appending = False
                        self.logger.log(VERBOSE1,
                                        "Updating Item {}: Resetting Resend Counter due to replaced command.".format(
                                            self._name))
                        break
                    else:
                        self.logger.log(VERBOSE2,
                                        "Updating Item {}: Command Set {} ({}) already in Commandlist {}"
                                        " but value {} is not same type as {}. Continue...".format(
                                            self._name, command, replace_commandinfo[3], type(replace_value),
                                            replace_commandinfo[9], commandlist))
            self.logger.log(VERBOSE1,
                            "Updating Item {}: Return from replace_setcommand: appending = {}, remove = {}.".format(
                                self._name, set_appending, set_removefromkeeping))
            return set_appending if replace_type == 'append' else set_removefromkeeping

        if self.alive:
            if caller in self._update_exclude:
                self.logger.debug(
                    "Updating Item {}: Not updating {} because caller {} is excluded.".format(self._name, item, caller))
            if not caller == 'AVDevice' and caller not in self._update_exclude:
                emptycommand = False
                commandinfo = command_re = response = ''
                value = item()
                try:
                    self.logger.debug("Updating Item {}: {} trying to update {}. Reconnecttrigger: {}".format(
                        self._name, caller, item, self._trigger_reconnect))
                    self.logger.log(VERBOSE1, "Updating Item {}: Starting to update item {}. "
                                    "Caller: {}, Source: {}. Destination: {}. Value: {}. Reconnecttrigger is {}".format(
                                        self._name, item, caller, source, dest, value, self._trigger_reconnect))
                    try:
                        depending = self._checkdependency(item, 'update')
                    except Exception:
                        depending = False
                    self.logger.log(VERBOSE1, "Updating Item {}: Depending is {}.".format(self._name, depending))
                    condition1 = (self.has_iattr(item.conf, 'avdevice') and
                                  self.get_iattr_value(item.conf, 'avdevice') == 'reload')
                    condition2 = (self.has_iattr(item.conf, 'avdevice_zone0') and
                                  self.get_iattr_value(item.conf, 'avdevice_zone0') == 'reload')
                    if condition1 or condition2:
                        self._initialize()
                        self.logger.info("Initializing {}: Reloaded Text file and functions".format(self._name))
                        depending = False

                    # connect if necessary
                    if self._trigger_reconnect is True:
                        self.logger.log(VERBOSE1,
                                        "Updating Item {}: Trying to connect while updating item".format(self._name))
                        self.connect('update_item')
                    depending = self._checkdependency(self._dependson, 'dependitem') if item == self._dependson else depending

                    for zone in range(0, self._number_of_zones + 1):
                        command = ''
                        letsgo = False
                        try:
                            if self.has_iattr(item.conf, 'avdevice'):
                                command = self.get_iattr_value(item.conf, 'avdevice')
                                zone_x = True if command in self._items['zone{}'.format(zone)].keys() else False
                            elif self.has_iattr(item.conf, 'avdevice_zone{}_speakers'.format(zone)):
                                command = 'speakers'
                                zone_x = True
                            else:
                                zone_x = False
                        except Exception:
                            zone_x = False
                        try:
                            if self.has_iattr(item.conf, 'avdevice_zone{}'.format(zone)) or zone_x is True:
                                letsgo = True
                        except Exception:
                            letsgo = True if item == 'statusupdate' and zone == 0 else False

                        if letsgo is True:
                            if zone_x is False:
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
                                    self.logger.debug(
                                        "Updating Item {}: Skipping command {} with WRITE flag because it's set to False".format(
                                            self._name, command))
                                    break
                                if self._functions['zone{}'.format(zone)][command][2] == '':
                                    emptycommand = True
                                    if command == 'statusupdate':
                                        try:
                                            checkvalue = item()
                                        except Exception:
                                            checkvalue = True
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Statusupdate. Checkvalue: {}. Display Ignore: {}. Caller: {}".format(
                                                            self._name, checkvalue,
                                                            self._special_commands['Display']['Ignore'], caller))
                                        cond1 = checkvalue is True or caller == 'Init'
                                        cond2 = not self._special_commands['Display']['Ignore'] >= 5
                                        if cond1 and cond2:
                                            if not self._is_connected == []:
                                                self._addorremove_keepcommands('statusupdate', 'all')
                                            for query in self._query_commands:
                                                if caller == 'Init':
                                                    depending = self._checkdependency(query, 'initupdate')
                                                else:
                                                    depending = self._checkdependency(query, 'statusupdate')
                                                if query not in self._send_commands and depending is False:
                                                    self._send_commands.append(query)
                                                    self._send_history['query'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = query
                                            self._reconnect_counter = 0
                                            self._trigger_reconnect = True

                                            if not self._is_connected == []:
                                                self.logger.log(VERBOSE1,
                                                                "Updating Item {}: Updating status. Sendcommands: {}. "
                                                                "Reconnecttrigger: {}. Display Ignore: {}".format(
                                                                    self._name, self._send_commands, self._trigger_reconnect,
                                                                    self._special_commands['Display']['Ignore']))
                                        elif checkvalue is False and not self._special_commands['Display']['Ignore'] >= 5:
                                            depending = self._checkdependency(item, 'globaldepend')
                                            if depending is True or self._is_connected == [] or self._is_connected == ['Connecting']:
                                                self._resetondisconnect('statusupdate')
                                    updating = False
                                if self._functions['zone{}'.format(zone)][command][5].lower() == 'r':
                                    updating = False
                                    commandinfo = self._functions['zone{}'.format(zone)][command]
                                    if commandinfo[2] == '' and commandinfo[3] == '':
                                        self.logger.warning(
                                            "Updating Item {}: Function is read only and empty. Doing nothing. Command: {}".format(
                                                self._name, command))
                                    else:
                                        self.logger.info(
                                            "Updating Item {}: Function is read only. Sending query. Command: {}".format(
                                                self._name, command))

                                        responsecommand, _ = CreateResponse(commandinfo, '', '', self._name,
                                                                            self._specialparse, self.logger).response_standard()
                                        appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3],
                                                                             responsecommand, item.id())
                                        cond1 = appendcommand not in self._query_commands
                                        cond2 = appendcommand not in self._special_commands['Display']['Command']
                                        if appendcommand in self._send_commands:
                                            self.logger.debug(
                                                "Updating Item {}: Readonly Command {} already in Commandlist. Ignoring.".format(
                                                    self._name, appendcommand))
                                        elif cond1 and cond2 and depending is True:
                                            self._keep_commands[time.time()] = appendcommand
                                            self.logger.debug(
                                                "Updating Item {}: Not adding readonly command {} because dependency is not fullfilled, storing in keep commands: {}.".format(
                                                    self._name, appendcommand, self._keep_commands))
                                        else:
                                            self.logger.debug(
                                                "Updating Item {}: Readonly. Updating Zone {} Commands {} for {}".format(
                                                    self._name, zone, self._send_commands, item))
                                            self._send_commands.append(appendcommand)
                                            self._send_history['command'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = appendcommand

                            except Exception as err:
                                self.logger.log(VERBOSE2,
                                                "Updating Item {}: Command {} is a standard command. Updating: {}. Message: {}".format(
                                                    self._name, command, updating, err))

                            if updating is True:
                                self.logger.debug("Updating Item {}: {} set {} to {} for {} in zone {}".format(
                                    self._name, caller, command, value, item, zone))
                                self._trigger_reconnect = True
                                setting = False
                                checkquery = False
                                if command in self._functions['zone{}'.format(zone)]:
                                    commandinfo = self._functions['zone{}'.format(zone)][command]
                                    replacedresponse, _ = CreateResponse(commandinfo, '', '', self._name,
                                                                         self._specialparse, self.logger).response_standard()
                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    cond1 = appendcommand not in self._query_commands
                                    cond2 = appendcommand not in self._special_commands['Display']['Command']
                                    if appendcommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Command {} already in Commandlist. Ignoring.".format(
                                                self._name, appendcommand))
                                    elif cond1 and cond2 and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug(
                                            "Updating Item {}: Not adding command {} because dependency is not fullfilled, storing in keep commands: {}.".format(
                                                self._name, appendcommand, self._keep_commands))
                                    else:
                                        self.logger.debug(
                                            "Updating Item {}: Updating Zone {} Commands {} for {}".format(
                                                self._name, zone, self._send_commands, item))
                                        self._send_commands.append(appendcommand)
                                        self._send_history['command'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = appendcommand
                                        checkquery = True
                                elif command_increase in self._functions['zone{}'.format(zone)]:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_increase]
                                    try:
                                        reverseinfo = self._functions['zone{}'.format(zone)][command_decrease]
                                    except Exception:
                                        try:
                                            reverseinfo = self._functions['zone{}'.format(zone)][
                                                '{} decrease'.format(command.replace('+', '-', 1))]
                                        except Exception:
                                            reverseinfo = ''
                                    replacedresponse, replacedreverse = CreateResponse(
                                        commandinfo, reverseinfo, '', self._name,
                                        self._specialparse, self.logger).response_in_decrease()
                                    try:
                                        reverseitem = self._items['zone{}'.format(zone)][command.replace('+', '-', 1)].get('Item')
                                    except Exception:
                                        reverseitem = item.id()

                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    reversecommand = '{},{},{};{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, reverseitem)

                                    self.logger.log(VERBOSE2,
                                                    "Updating Item {}: Appendcommand increase: {}, Reversecommand: {}, Send Commands: {}".format(
                                                        self._name, appendcommand, reversecommand, self._send_commands))
                                    cond1 = appendcommand not in self._query_commands
                                    cond2 = appendcommand not in self._special_commands['Display']['Command']
                                    if appendcommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Increase Command {} already in Commandlist. Ignoring.".format(
                                                self._name, appendcommand))
                                    elif reversecommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Command Decrease {} already in Commandlist {}. Replacing with Command Increase {}.".format(
                                                self._name, reversecommand, self._send_commands, appendcommand))
                                        self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: New Commandlist {}.".format(
                                            self._name, self._send_commands))
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Resetting Resend Counter due to updated command.".format(
                                                            self._name))
                                    elif cond1 and cond2 and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug(
                                            "Updating Item {}: Not adding increase command {} because dependency is not fullfilled, storing in keep commands: {}.".format(
                                                self._name, appendcommand, self._keep_commands))
                                    else:
                                        self.logger.debug(
                                            "Updating Item {}: Updating Zone {} Command Increase {} for {}".format(
                                                self._name, zone, self._send_commands, item))
                                        self._send_commands.append(appendcommand)
                                        self._send_history['command'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = appendcommand
                                elif command_decrease in self._functions['zone{}'.format(zone)]:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_decrease]
                                    try:
                                        reverseinfo = self._functions['zone{}'.format(zone)][command_increase]
                                    except Exception:
                                        try:
                                            reverseinfo = self._functions['zone{}'.format(zone)][
                                                '{} increase'.format(command.replace('-', '+', 1))]
                                        except Exception:
                                            reverseinfo = ''
                                    replacedresponse, replacedreverse = CreateResponse(
                                        commandinfo, reverseinfo, '', self._name,
                                        self._specialparse, self.logger).response_in_decrease()
                                    try:
                                        reverseitem = self._items['zone{}'.format(zone)][command.replace('-', '+', 1)].get('Item')
                                    except Exception:
                                        reverseitem = item.id()

                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    reversecommand = '{},{},{};{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, reverseitem)

                                    self.logger.log(VERBOSE2,
                                                    "Updating Item {}: Appendcommand decrease: {}, Reversecommand: {}, Send Commands: {}".format(
                                                        self._name, appendcommand, reversecommand, self._send_commands))
                                    cond1 = appendcommand not in self._query_commands
                                    cond2 = appendcommand not in self._special_commands['Display']['Command']
                                    if appendcommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Decrease Command {} already in Commandlist. Ignoring.".format(
                                                self._name, appendcommand))
                                    elif reversecommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Command Increase {} already in Commandlist {}. Replacing with Command Decrease {}.".format(
                                                self._name, reversecommand, self._send_commands, appendcommand))
                                        self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: New Commandlist {}.".format(
                                            self._name, self._send_commands))
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Resetting Resend Counter due to updated command.".format(
                                                            self._name))
                                    elif cond1 and cond2 and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug(
                                            "Updating Item {}: Not adding decrease command {} because dependency is not fullfilled, storing in keep commands: {}.".format(
                                                self._name, appendcommand, self._keep_commands))
                                    else:
                                        self.logger.debug(
                                            "Updating Item {}: Updating Zone {} Command Decrease {} for {}".format(
                                                self._name, zone, self._send_commands, item))
                                        self._send_commands.append(appendcommand)
                                        self._send_history['command'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = appendcommand

                                elif command_on in self._functions['zone{}'.format(zone)] and \
                                        isinstance(value, bool) and value == 1:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_on]
                                    reverseinfo = self._functions['zone{}'.format(zone)][command_off]
                                    replacedresponse, replacedreverse = CreateResponse(
                                        commandinfo, reverseinfo, '', self._name, self._specialparse, self.logger).response_on()

                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    reversecommand = '{},{},{};{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, item.id())

                                    self.logger.log(VERBOSE2,
                                                    "Updating Item {}: Appendcommand on: {}, Reversecommand: {}, Send Commands: {}".format(
                                                        self._name, appendcommand, reversecommand, self._send_commands))
                                    removefromkeeping = []
                                    for x in self._keep_commands:
                                        cond1 = appendcommand == self._keep_commands.get(x)
                                        cond2 = reversecommand == self._keep_commands.get(x)
                                        if cond1 or cond2:
                                            removefromkeeping.append(x)
                                    cond1 = appendcommand not in self._query_commands
                                    cond2 = appendcommand not in self._special_commands['Display']['Command']
                                    if appendcommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Command On {} already in Commandlist {}. Ignoring.".format(
                                                self._name, appendcommand, self._send_commands))
                                    elif reversecommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Command Off {} already in Commandlist {}. Replacing with Command On {}.".format(
                                                self._name, reversecommand, self._send_commands, appendcommand))
                                        self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: New Commandlist {}.".format(
                                            self._name, self._send_commands))
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Resetting Resend Counter due to new command.".format(self._name))
                                    elif cond1 and cond2 and depending is True:
                                        for i in removefromkeeping:
                                            self.logger.log(VERBOSE1,
                                                            "Updating Item {}: Removing {} from keepcommands "
                                                            "before storing equivalent command.".format(self._name, self._keep_commands.get(i)))
                                            self._keep_commands.pop(i, None)
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug(
                                            "Updating Item {}: Not adding on command {} because dependency is not fullfilled,"
                                            " storing in keep commands: {}.".format(
                                                self._name, appendcommand, self._keep_commands))
                                    else:
                                        self._send_commands.append(appendcommand)
                                        self._send_history['command'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = appendcommand
                                        self._sendingcommand = appendcommand
                                        checkquery = True
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Update Zone {} Command On {} for {}".format(
                                                            self._name, zone, commandinfo[2], item))
                                    if command_on == 'power on' and checkquery is True:
                                        self._addorremove_keepcommands('powercommand', 'zone{}'.format(zone))
                                        self.logger.debug(
                                            "Updating Item {}: Command Power On for zone: {}. Appending relevant query commands.".format(
                                                self._name, zone))
                                        checkquery = False
                                        for query in self._query_zonecommands['zone{}'.format(zone)]:
                                            depending = self._checkdependency(query, 'statusupdate')
                                            if query not in self._send_commands and depending is False:
                                                self._send_commands.append(query)
                                                self._send_history['query'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = query

                                elif command_off in self._functions['zone{}'.format(zone)] and \
                                        isinstance(value, bool) and value == 0:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_off]
                                    reverseinfo = self._functions['zone{}'.format(zone)][command_on]
                                    replacedresponse, replacedreverse = CreateResponse(
                                        commandinfo, reverseinfo, '', self._name, self._specialparse, self.logger).response_off()

                                    appendcommand = '{},{},{};{}'.format(commandinfo[2], commandinfo[3], replacedresponse, item.id())
                                    reversecommand = '{},{},{};{}'.format(reverseinfo[2], reverseinfo[3], replacedreverse, item.id())

                                    self.logger.log(VERBOSE1,
                                                    "Updating Item {}: Appendcommand off: {}. Reversecommand: {} Send Commands: {}".format(
                                                        self._name, appendcommand, reversecommand, self._send_commands))
                                    removefromkeeping = []
                                    for x in self._keep_commands:
                                        cond1 = appendcommand == self._keep_commands.get(x)
                                        cond2 = reversecommand == self._keep_commands.get(x)
                                        if cond1 or cond2:
                                            removefromkeeping.append(x)
                                    cond1 = appendcommand not in self._query_commands
                                    cond2 = appendcommand not in self._special_commands['Display']['Command']
                                    if appendcommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Command Off {} already in Commandlist {}. Ignoring.".format(
                                                self._name, appendcommand, self._send_commands))
                                    elif reversecommand in self._send_commands:
                                        self.logger.debug(
                                            "Updating Item {}: Command On {} already in Commandlist {}. Replacing with Command Off {}.".format(
                                                self._name, reversecommand, self._send_commands, appendcommand))
                                        self._send_commands[self._send_commands.index(reversecommand)] = self._sendingcommand = appendcommand
                                        self.logger.log(VERBOSE1, "Updating Item {}: New Commandlist {}.".format(
                                            self._name, self._send_commands))
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Resetting Resend Counter due to new command.".format(
                                                            self._name))
                                    elif cond1 and cond2 and depending is True:
                                        for i in removefromkeeping:
                                            self.logger.log(VERBOSE1,
                                                            "Updating Item {}: Removing {} from keepcommands "
                                                            "before storing equivalent command.".format(self._name, self._keep_commands.get(i)))
                                            self._keep_commands.pop(i, None)
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug(
                                            "Updating Item {}: Not adding off command {} because dependency is not fullfilled, storing in keep commands: {}.".format(
                                                self._name, appendcommand, self._keep_commands))
                                    else:
                                        self._send_commands.append(appendcommand)
                                        self._send_history['command'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = appendcommand
                                        self._sendingcommand = appendcommand
                                        checkquery = True
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Update Zone {} Command Off {} for {}".format(
                                                            self._name, zone, commandinfo[2], item))

                                elif command_set in self._functions['zone{}'.format(zone)]:
                                    commandinfo = self._functions['zone{}'.format(zone)][command_set]
                                    newvalue = None
                                    if not command.lower().startswith('speakers'):
                                        response, _ = CreateResponse(commandinfo, '', value, self._name,
                                                                     self._specialparse, self.logger).response_set()
                                    try:
                                        newvalue = value.lower() if isinstance(value, str) else value
                                        newvalue = Translate(newvalue, commandinfo[10], self._name, 'update',
                                                             self._specialparse, self.logger).translate()
                                        self.logger.log(VERBOSE2,
                                                        "Updating Item {}: Translated value: {}".format(self._name,
                                                                                                        newvalue))
                                    except Exception:
                                        pass
                                    value = newvalue or value
                                    try:
                                        value = eval(value.lstrip('0'))
                                    except Exception:
                                        pass
                                    self.logger.log(VERBOSE2,
                                                    "Updating Item {}: Final value: {}".format(self._name,
                                                                                               value))
                                    try:
                                        translatecode = commandinfo[10]
                                    except Exception:
                                        translatecode = None
                                    cond1 = isinstance(value, int) and 'int' in commandinfo[9]
                                    cond2 = isinstance(value, float) and 'float' in commandinfo[9]
                                    if value == 0 and 'bool' in commandinfo[9]:
                                        setting = True
                                        value = 'OFF'
                                        try:
                                            command_re = re.sub('\*+', '{}'.format(value), commandinfo[2])
                                        except Exception:
                                            command_re = commandinfo[2]
                                        self.logger.debug(
                                            "Updating Item {}: Value 0 is converted to OFF. command_re: {}, response: {}".format(
                                                self._name, command_re, response))
                                    elif cond1 or cond2:
                                        setting = True
                                        if commandinfo[2].count('*') == 1 and command.lower().startswith('speakers'):
                                            currentvalue = int(
                                                self._items['zone{}'.format(zone)]['speakers']['Item']())
                                            multiply = -1 if item() == 0 else 1
                                            multiply = 0 if (currentvalue == 0 and item() == 0) else multiply
                                            try:
                                                value = abs(int(self.get_iattr_value(item.conf,
                                                                                     'avdevice_zone{}_speakers'.format(
                                                                                         zone))))
                                            except Exception:
                                                self.logger.warning(
                                                    "Updating Item {}: This speaker item is not supposed to be manipulated directly.".format(
                                                        self._name))
                                                break

                                            powerinfo = self._functions['zone{}'.format(zone)]['power on']
                                            if not currentvalue == value or multiply == -1:
                                                maxvalue = sum(map(int, self._items_speakers['zone{}'.format(zone)].keys()))
                                                value = min(currentvalue + (value * multiply), maxvalue)
                                            self.logger.log(VERBOSE1,
                                                            "Updating Item {}: Speaker {} current value is {}. Item: {} with value {}."
                                                            " Multiply: {}. Value: {}".format(
                                                                self._name, self._items['zone{}'.format(zone)]['speakers']['Item'],
                                                                currentvalue, item, item(), multiply, value))
                                            response, _ = CreateResponse(commandinfo, '', value, self._name,
                                                                         self._specialparse, self.logger).response_set()
                                            command_re = CreateResponse(commandinfo, '', value, self._name,
                                                                        self._specialparse, self.logger).replace_number(
                                                                            commandinfo[2], value, translatecode)
                                            self.logger.log(VERBOSE2,
                                                            "Updating Item {}: Speakers commandinfo 2: {}, value: {}. command_re: {}".format(
                                                                self._name, commandinfo[2], value, command_re))
                                            if value > 0:
                                                replacedresponse, _ = CreateResponse(powerinfo, '', True, self._name,
                                                                                     self._specialparse, self.logger).response_power()
                                                try:
                                                    poweritem = self._items['zone{}'.format(zone)][powerinfo[1]].get('Item')
                                                except Exception:
                                                    poweritem = self._items['zone0'][powerinfo[1]].get('Item')
                                                appendcommand = '{},{},{};{}'.format(powerinfo[2], powerinfo[3],
                                                                                     replacedresponse,
                                                                                     poweritem.id())
                                                self._send_commands.insert(0, appendcommand)
                                                self._sendingcommand = appendcommand
                                                self.logger.debug(
                                                    "Updating Item {}: Turning power on. powercommands is: {}".format(
                                                        self._name, powerinfo))
                                        else:
                                            command_re = CreateResponse(commandinfo, '', value, self._name,
                                                                        self._specialparse, self.logger).replace_number(
                                                                            commandinfo[2], value, translatecode)
                                            self.logger.log(VERBOSE2,
                                                            "Updating Item {}: commandinfo 2: {}, value: {}. command_re: {}".format(
                                                                self._name, commandinfo[2], value, command_re))

                                    elif isinstance(value, str) and 'str' in commandinfo[9]:
                                        setting = True
                                        command_re = CreateResponse(commandinfo, '', value, self._name,
                                                                    self._specialparse, self.logger).replace_string(
                                                                        commandinfo[2], value, translatecode)

                                    else:
                                        setting = False
                                else:
                                    self.logger.error("Updating Item {}: Command {} not in text file or wrong Item type! Valuetype is {}".format(
                                        self._name, command, type(value)))
                                    updating = False

                                if not self._send_commands == [] and setting is True:
                                    appendcommand = '{},{},{};{}'.format(command_re, commandinfo[3], response,
                                                                         item.id())
                                    setting = False
                                    appending = _replace_setcommand(commandinfo, self._send_commands, appendcommand, value, 'append')
                                    removefromkeeping = _replace_setcommand(commandinfo, self._keep_commands, appendcommand, value, 'keep')
                                    for i in removefromkeeping:
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Removing {} from keepcommands "
                                                        "before storing equivalent command.".format(self._name, self._keep_commands.get(i)))
                                        self._keep_commands.pop(i, None)
                                    if appending is True:
                                        cond1 = appendcommand not in self._query_commands
                                        cond2 = appendcommand not in self._special_commands['Display']['Command']
                                        if cond1 and cond2 and depending is True:
                                            self._keep_commands[time.time()] = appendcommand
                                            self.logger.debug(
                                                "Updating Item {}: Not adding set command {} because dependency is not fullfilled, storing in keep commands: {}.".format(
                                                    self._name, appendcommand, self._keep_commands))
                                        else:
                                            self._send_commands.append(appendcommand)
                                            self._send_history['command'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = appendcommand
                                            self._sendingcommand = appendcommand
                                            self._resend_counter = 0
                                            checkquery = True
                                            self.logger.log(VERBOSE1,
                                                            "Updating Item {}: Resetting Resend Counter because appending new set command.".format(
                                                                self._name))
                                            self.logger.log(VERBOSE1,
                                                            "Updating Item {}: Update Zone {} Command Set {} for {}. Command: {}".format(
                                                                self._name, zone, commandinfo[2], item, command_re))
                                elif setting is True:
                                    appendcommand = '{},{},{};{}'.format(command_re, commandinfo[3], response,
                                                                         item.id())
                                    removefromkeeping = _replace_setcommand(commandinfo, self._keep_commands, appendcommand, value, 'keep')
                                    for i in removefromkeeping:
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Removing {} from keepcommands "
                                                        "before storing equivalent command.".format(self._name, self._keep_commands.get(i)))
                                        self._keep_commands.pop(i, None)
                                    cond1 = appendcommand not in self._query_commands
                                    cond2 = appendcommand not in self._special_commands['Display']['Command']
                                    if cond1 and cond2 and depending is True:
                                        self._keep_commands[time.time()] = appendcommand
                                        self.logger.debug(
                                            "Updating Item {}: Not adding set command {} because dependency is not fullfilled, storing in keep commands: {}.".format(
                                                self._name, appendcommand, self._keep_commands))
                                    else:
                                        self._send_commands.append(appendcommand)
                                        self._send_history['command'][datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")] = appendcommand
                                        self._resend_counter = 0
                                        checkquery = True
                                        self.logger.log(VERBOSE1,
                                                        "Updating Item {}: Resetting Resend Counter because adding new set command.".format(
                                                            self._name))
                                        self.logger.debug(
                                            "Updating Item {}: Update Zone {} Command Set, adding to empty Commandlist {} for {}. Command: {}".format(
                                                self._name, zone, self._send_commands, item, command_re))

                                if checkquery is True:
                                    self.logger.debug(
                                        "Updating Item {}: Command {} for zone: {}. Removing relevant query commands.".format(
                                            self._name, command, zone))
                                    self._checkdependency('zone{}, {}, {}'.format(zone, command, value), 'checkquery')
                        else:
                            command = self.get_iattr_value(item.conf, 'avdevice_zone{}'.format(zone))
                            self.logger.log(VERBOSE2,
                                            "Updating Item {}: Did not update item {} with command {} for zone {}".format(
                                                self._name, item, command, zone))
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
                        if self._is_connected and self._send_commands and not self._is_connected == ['Connecting']:
                            self.logger.log(VERBOSE1,
                                            "Updating Item {}: Updating item {}. Command list is {}. Sendingcommand: {}. ".format(
                                                self._name, item, self._send_commands, self._sendingcommand))
                            sending = self._send('command', 'updateitem')
                            self.logger.log(VERBOSE1,
                                            "Updating Item {}: Updating item {}. Command list is {}. Return from send is {}".format(
                                                self._name, item, self._send_commands, sending))
                        cond1 = self._reset_onerror is True and emptycommand is False
                        cond2 = self._send_commands and not self._sendingcommand == 'done' and not self._is_connected
                        if cond1 and cond2:
                            if not self._send_commands[0].split(',')[0] == self._send_commands[0].split(',')[1]:
                                self.logger.log(VERBOSE1,
                                                "Updating Item {}: Sending command {}. Starting to reset".format(
                                                    self._name, self._sendingcommand))
                                resetting = self._resetitem('')
                            else:
                                resetting = ''
                            befehle = [x.split(',')[0] for x in self._send_commands]
                            try:
                                index = self._send_commands.index(self._sendingcommand)
                                self.logger.log(VERBOSE2, "Updating Item {}: Sending command {} "
                                                "index is {}".format(self._name, self._sendingcommand, index))
                            except Exception:
                                index = befehle.index(self._sendingcommand)
                                self.logger.log(VERBOSE1, "Updating Item {}: Sending command {} "
                                                "not in Sendcommands {} list, but found in {}".format(
                                                    self._name, self._sendingcommand, self._send_commands, befehle))
                            cond1 = self._send_commands[index] not in self._query_commands
                            cond2 = self._send_commands[index] not in self._special_commands['Display']['Command']
                            if cond1 and cond2:
                                self._keep_commands[time.time()] = self._send_commands[index]
                            self._send_commands.pop(index)
                            if self._depend0_volume0 is True or self._depend0_power0 is True:
                                self._resetondisconnect('update_end')
                            try:
                                self._sendingcommand = self._send_commands[0]
                            except Exception:
                                self._sendingcommand = 'gaveup'
                            if resetting == '':
                                self.logger.debug(
                                    "Updating Item {}: Connection error. Nothing reset.".format(self._name))
                            else:
                                self.logger.info(
                                    "Updating Item {}: Connection error. Resetting Item {}. "
                                    "Keepcommands: {}. Sendcommands: {} Sendingcommand: {}".format(
                                        self._name, resetting, self._keep_commands,
                                        self._send_commands, self._sendingcommand))
                            self._trigger_reconnect = True

                    except Exception as err:
                        if self._is_connected:
                            self.logger.warning(
                                "Updating Item {}: Problem sending command. It is most likely not in the text file! Error: {}".format(
                                    self._name, err))
                        else:
                            self.logger.warning(
                                "Updating Item {}: Problem sending command - not connected! Error: {}".format(
                                    self._name, err))
                            self._trigger_reconnect = True

    def _displayignore(self, response, receivedvalue, caller):
        if not caller == 'parsing_final':
            self.logger.log(VERBOSE1,
                            "Display Ignore {}: Function called by: {}. Response: {}. Received Value: {}".format(
                                self._name, caller, response, receivedvalue))
        try:
            displaycommand = self._special_commands['Display']['Command']
            displayignore = self._special_commands['Display']['Ignore']
            inputignore = self._special_commands['Input']['Ignore']
            inputcommands = self._special_commands['Input']['Command']
            responseignore = self._ignore_response
        except Exception:
            displaycommand = inputcommands = responseignore = ''
            displayignore = inputignore = 1
        try:
            sending = self._send_commands[0]
        except Exception:
            sending = ''
        if receivedvalue is None:
            try:
                keyfound = False
                for resp in response:
                    keyfound = True if resp in displaycommand and not displaycommand == '' else False
                cond1 = sending in self._query_commands and len(self._send_commands) > 1
                cond2 = keyfound is not True and displayignore < 5
                if cond1 and cond2:
                    self._special_commands['Display']['Ignore'] = displayignore + 5
                    if displaycommand not in self._ignore_response and '' not in self._ignore_response and not displaycommand == '':
                        self._ignore_response.append(displaycommand)
                    self.logger.log(VERBOSE2,
                                    "Display Ignore {}: Command: {}. Display Ignore: {}, Input Ignore: {}".format(
                                        self._name, sending, self._special_commands['Display']['Ignore'], inputignore))

                elif sending not in self._query_commands or len(self._send_commands) <= 1 or keyfound is True:
                    if displayignore >= 5:
                        self._special_commands['Display']['Ignore'] = displayignore - 5
                        self.logger.log(VERBOSE2,
                                        "Display Ignore {}: Init Phase finished, Display Ignore: {}, Input Ignore: {}".format(
                                            self._name, self._special_commands['Display']['Ignore'], inputignore))
                    cond1 = self._special_commands['Display']['Ignore'] == 0
                    cond2 = 1 not in inputignore and not displaycommand == ''
                    if cond1 and cond2:
                        if displaycommand in self._ignore_response:
                            try:
                                self._ignore_response.remove(displaycommand)
                                self.logger.log(VERBOSE2, "Display Ignore {}: Removing {} from ignore.".format(
                                    self._name, displaycommand))
                            except Exception as err:
                                self.logger.log(VERBOSE2,
                                                "Display Ignore {}: Cannot remove {} from ignore. Message: {}".format(
                                                    self._name, displaycommand, err))
                cond1 = self._ignore_response == responseignore
                cond2 = self._special_commands['Display']['Ignore'] == displayignore
                cond3 = self._special_commands['Input']['Ignore'] == inputignore
                if not (cond1 and cond2 and cond3):
                    self.logger.debug(
                        "Display Ignore {}: Ignored responses are now: {}. Display Ignore: {}, Input Ignore: {}".format(
                            self._name, self._ignore_response, self._special_commands['Display']['Ignore'],
                            self._special_commands['Input']['Ignore']))
            except Exception as err:
                self.logger.debug(
                    "Display Ignore {}: Problems: {}".format(self._name, err))
        else:
            try:
                cond1 = response.startswith(tuple(inputcommands))
                cond2 = str(receivedvalue) in self._ignoredisplay
                cond3 = '' not in self._ignoredisplay
                cond4 = str(receivedvalue) not in self._ignoredisplay
                if cond1 and cond2 and cond3:
                    for i in range(0, len(inputcommands)):
                        if response.startswith(inputcommands[i]):
                            self._special_commands['Input']['Ignore'][i] = 1
                    if displaycommand not in self._ignore_response and not displaycommand == '' and '' not in self._ignore_response:
                        self._ignore_response.append(displaycommand)
                    self.logger.debug(
                        "Display Ignore {}: Data {} has value in ignoredisplay {}. Ignorecommands are now: {}."
                        " Display Ignore is {}. Input Ignore is {}".format(self._name, response,
                                                                           self._ignoredisplay, self._ignore_response,
                                                                           displayignore, inputignore))
                elif cond1 and cond4 and cond3:
                    for i in range(0, len(inputcommands)):
                        if response.startswith(inputcommands[i]):
                            self._special_commands['Input']['Ignore'][i] = 0
                    self.logger.log(VERBOSE2,
                                    "Display Ignore {}: Data {} with received value {} has NO value in ignoredisplay {}."
                                    " Ignored responses are now: {}. Display Ignore is {}. Input Ignore is {}".format(
                                        self._name, response, receivedvalue, self._ignoredisplay, self._ignore_response,
                                        displayignore, inputignore))
                    cond1 = displayignore == 0 and 1 not in inputignore
                    cond2 = not displaycommand == '' and displaycommand in self._ignore_response
                    if cond1 and cond2:
                        try:
                            self._ignore_response.remove(displaycommand)
                            self.logger.log(VERBOSE2, "Display Ignore {}: Removing {} from ignore.".format(
                                self._name, displaycommand))
                        except Exception as err:
                            self.logger.log(VERBOSE2,
                                            "Display Ignore {}: Cannot remove {} from ignore. Message: {}".format(
                                                self._name, displaycommand, err))
                cond1 = self._ignore_response == responseignore
                cond2 = self._special_commands['Display']['Ignore'] == displayignore
                cond3 = self._special_commands['Input']['Ignore'] == inputignore
                if not (cond1 and cond2 and cond3):
                    self.logger.debug(
                        "Display Ignore {}: Ignored responses are now: {}. Display Ignore: {}, Input Ignore: {}".format(
                            self._name, self._ignore_response, self._special_commands['Display']['Ignore'],
                            self._special_commands['Input']['Ignore']))
            except Exception as err:
                self.logger.debug("Display Ignore {}: Problems: {}.".format(self._name, err))

    # Sending commands to the device
    def _send(self, command, caller):
        self.logger.log(VERBOSE1,
                        "Sending {}: Sending function called by: {}. Command: {}.".format(self._name, caller, command))
        try:
            if not self._send_commands == []:
                if command == 'command':
                    to_send = self._send_commands[0].split(',')[0]
                    expected_resp = self._send_commands[0].split(',')[2]
                elif command == 'query':
                    to_send = self._send_commands[0].split(',')[1]
                    expected_resp = self._send_commands[0].split(',')[2]
                else:
                    try:
                        to_send = command.split(',')[0]
                        expected_resp = command.split(',')[2]
                    except Exception:
                        to_send = command
                        expected_resp = 'empty'
                    command = 'Resendcommand'
                commandlist = to_send.split('|')
                self.logger.log(VERBOSE1, "Sending {}: Starting to send {} {}. Caller: {}.".format(
                    self._name, command, to_send, caller))
                try:
                    self._sendingcommand = self._send_commands[0]
                except Exception:
                    self._sendingcommand = to_send
                response = self._send_commands[0].split(',')[2].split('|')
                if not self._parsinginput:
                    self.logger.log(VERBOSE1, "Sending {}: Starting Parse Input. Expected response: {}".format(
                        self._name, response))
                    self._parse_input_init('sending')
                self._displayignore(response, None, 'sending')

                if self._trigger_reconnect is True:
                    self.logger.log(VERBOSE1, "Sending {}: Trying to connect while sending command".format(self._name))
                    self.connect('send')
                for cmd, multicommand in enumerate(commandlist):
                    result = None
                    try:
                        multicommand = eval(multicommand)
                    except Exception:
                        pass
                    if isinstance(multicommand, float) or isinstance(multicommand, int):
                        waitingtime = float(multicommand)
                        self.logger.log(VERBOSE1, "Sending {}: Waitingtime between commands: {}".format(self._name, waitingtime))
                        self._wait(waitingtime)
                    else:
                        if self._rs232 is not None:
                            result = self._serialwrapper.write(u'{}\r'.format(multicommand))
                            self._serialwrapper.flush()
                            self.logger.debug(
                                "Sending Serial {}: {} was sent {} from Multicommand-List {}. Returns {}. Sending command: {}".format(
                                    self._name, command, multicommand, commandlist, result, self._sendingcommand))
                            self._wait(0.2)

                        elif self._tcp is not None:
                            result = self._tcpsocket.send(bytes('{}\r'.format(multicommand), 'utf-8'))
                            self.logger.debug(
                                "Sending TCP {}: {} was sent {} from Multicommand-List {}. Returns {}".format(
                                    self._name, command, multicommand, commandlist, result))
                            self._wait(0.2)
                        else:
                            self.logger.error(
                                "Sending {}: Neither IP address nor Serial device definition found".format(self._name))
                    if cmd >= len(commandlist) - 1:
                        if not expected_resp and self._send_commands:
                            self.logger.log(VERBOSE1, "Sending {}: Removing first send command {}"
                                            " because no response is expected".format(self._name, self._send_commands[0]))
                            self._send_commands.pop(0)
                        return result
        except IOError as err:
            if err.errno == 32:
                self.logger.warning(
                    "Sending {}: Problem sending multicommand {}, not connected. Message: {}".format(
                        self._name, self._send_commands[0], err))
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
                self.logger.warning("Sending {}: Problem sending multicommand {}. Message: {}".format(
                    self._name, self._send_commands[0], err))
            except Exception:
                self.logger.warning(
                    "Sending {}: Problem sending multicommand {}. Message: {}".format(
                        self._name, self._send_commands, err))

    # Stopping function when SmarthomeNG is stopped
    def stop(self):
        self.alive = False
        try:
            self.scheduler_change('avdevice-tcp-reconnect', active=False)
            self.scheduler_remove('avdevice-tcp-reconnect')
        except Exception:
            pass
        try:
            self.scheduler_change('avdevice-serial-reconnect', active=False)
            self.scheduler_remove('avdevice-serial-reconnect')
        except Exception:
            pass
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

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module('http')
        except:
            self.mod_http = None
        if self.mod_http is None:
            self.logger.error("Plugin '{}': Not initializing the web interface".format(self.get_shortname()))
            return False

        import sys
        if "SmartPluginWebIf" not in list(sys.modules['lib.model.smartplugin'].__dict__):
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

    @cherrypy.expose
    def index(self, action=None, item_id=None, item_path=None, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        config_reloaded = False
        keep_cleared = False
        command_cleared = False
        query_cleared = False
        send_cleared = False
        if action is not None:
            if action == "reload":
                self.plugin._initialize()
                config_reloaded = True
            if action == "connect":
                self.plugin.connect('webif')
            if action == "clear_query_history":
                self.plugin._clear_history('query')
                query_cleared = True
            if action == "clear_send":
                self.plugin._clear_history('send')
                send_cleared = True
            if action == "clear_command_history":
                self.plugin._clear_history('command')
                command_cleared = True
            if action == "clear_keep_commands":
                self.plugin._clear_history('keep')
                keep_cleared = True

        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin,
                           config_reloaded=config_reloaded, query_cleared=query_cleared,
                           command_cleared=command_cleared, keep_cleared=keep_cleared, send_cleared=send_cleared,
                           language=self.plugin._sh.get_defaultlanguage(), now=self.plugin.shtime.now())
