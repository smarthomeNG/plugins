#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab

#########################################################################
# Copyright 2020 Michael Wenzel
# Copyright 2020 Sebastian Helms
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

import logging
import sys
import time
import re
import json
import serial
import threading
from datetime import datetime
import dateutil.parser
import cherrypy

if __name__ == '__main__':
    # just needed for standalone mode

    class SmartPlugin():
        pass

    class SmartPluginWebIf():
        pass

    import os
    BASE = os.path.sep.join(os.path.realpath(__file__).split(os.path.sep)[:-3])
    sys.path.insert(0, BASE)
    import commands

else:
    from . import commands

    from lib.item import Items
    from lib.model.smartplugin import SmartPlugin, SmartPluginWebIf, Modules

    from bin.smarthome import VERSION


class Viessmann(SmartPlugin):
    '''
    Main class of the plugin. Provides communication with Viessmann heating systems
    via serial / USB-to-serial connections to read values and set operating parameters.

    Supported device types must be defined in ./commands.py.
    '''
    ALLOW_MULTIINSTANCE = False

    PLUGIN_VERSION = '1.2.2'

#
# public methods
#

    def __init__(self, sh, *args, standalone='', logger=None, **kwargs):

        # standalone mode: just setup basic info
        if standalone:
            self._serialport = standalone
            self._timeout = 3
            self.logger = logger
            self._standalone = True

        else:
            # Get plugin parameter
            self._serialport = self.get_parameter_value('serialport')
            self._heating_type = self.get_parameter_value('heating_type')
            self._protocol = self.get_parameter_value('protocol')
            self._timeout = self.get_parameter_value('timeout')
            self._standalone = False

        # Set variables
        self._error_count = 0
        self._params = {}                                                   # Item dict
        self._init_cmds = []                                                # List of command codes for read at init
        self._cyclic_cmds = {}                                              # Dict of command codes with cylce-times for cyclic readings
        self._application_timer = {}                                        # Dict of application timer with command codes and values
        self._timer_cmds = []                                               # List of command codes for timer
        self._viess_timer_dict = {}
        self._last_values = {}
        self._balist_item = None                                # list of last value per command code
        self._lock = threading.Lock()
        self._initread = False
        self._timerread = False
        self._connected = False
        self._initialized = False
        self._lastbyte = b''
        self._lastbytetime = 0
        self._cyclic_update_active = False
        self._wochentage = {
            'MO': ['mo', 'montag', 'monday'],
            'TU': ['di', 'dienstag', 'tuesday'],
            'WE': ['mi', 'mittwoch', 'wednesday'],
            'TH': ['do', 'donnerstag', 'thursday'],
            'FR': ['fr', 'freitag', 'friday'],
            'SA': ['sa', 'samstag', 'saturday'],
            'SU': ['so', 'sonntag', 'sunday']}

        # if running standalone, don't initialize command sets
        if not sh:
            return

        # initialize logger if necessary
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self._config_loaded = False

        if not self._load_configuration():
            return None

        # Init web interface
        self.init_webinterface()

    def run(self):
        '''
        Run method for the plugin
        '''
        if not self._config_loaded:
            if not self._load_configuration():
                return
        self.alive = True
        self._connect()
        self._read_initial_values()
        self._read_timers()

    def stop(self):
        '''
        Stop method for the plugin
        '''
        self.alive = False
        if self.scheduler_get('cyclic'):
            self.scheduler_remove('cyclic')
        self._disconnect()
        # force reload of configuration on restart
        self._config_loaded = False

    def parse_item(self, item):
        '''
        Method for parsing items.
        If the item carries any viess_* field, this item is registered to the plugin.

        :param item:    The item to process.
        :type item:     object

        :return:        The item update method to be triggered if the item is changed, or None.
        :rtype:         object
        '''
        # Process the update config
        if self.has_iattr(item.conf, 'viess_update'):
            self.logger.debug(f'Item for requesting update for all items triggered: {item}')
            return self.update_item

        # Process the timer config and fill timer dict
        if self.has_iattr(item.conf, 'viess_timer'):
            timer_app = self.get_iattr_value(item.conf, 'viess_timer')
            for commandname in self._commandset:
                if commandname.startswith(timer_app):
                    commandconf = self._commandset[commandname]
                    self.logger.debug(f'Process the timer config, commandname: {commandname}')
                    # {'addr': '2100', 'len': 8, 'unit': 'CT', 'set': True}
                    commandcode = (commandconf['addr']).lower()
                    if timer_app not in self._application_timer:
                        self._application_timer[timer_app] = {'item': item, 'commandcodes': []}
                    if commandcode not in self._application_timer[timer_app]['commandcodes']:
                        self._application_timer[timer_app]['commandcodes'].append(commandcode)
                    self._application_timer[timer_app]['commandcodes'].sort()
            self.logger.info(f'Loaded Application Timer {self._application_timer}')
            # self._application_timer: {'Timer_M2': {'item': Item: heizung.heizkreis_m2.schaltzeiten, 'commandcodes': ['3000', '3008', '3010', '3018', '3020', '3028', '3030']}, 'Timer_Warmwasser': {'item': Item: heizung.warmwasser.schaltzeiten, 'commandcodes': ['2100', '2108', '2110', '2118', '2120', '2128', '2130']}}

            for subdict in self._application_timer:
                for commandcode in self._application_timer[subdict]['commandcodes']:
                    if commandcode not in self._timer_cmds:
                        self._timer_cmds.append(commandcode)
            self._timer_cmds.sort()
            self.logger.debug(f'Loaded Timer commands {self._timer_cmds}')
            return self.update_item

        # Process the read config
        if self.has_iattr(item.conf, 'viess_read'):
            commandname = self.get_iattr_value(item.conf, 'viess_read')
            if commandname is None or commandname not in self._commandset:
                self.logger.error(f'Item {item} contains invalid read command {commandname}!')
                return None

            # Remember the read config to later update this item if the configured response comes in
            self.logger.info(f'Item {item} reads by using command {commandname}')
            commandconf = self._commandset[commandname]
            commandcode = (commandconf['addr']).lower()

            # Fill item dict
            self._params[commandcode] = {'item': item, 'commandname': commandname}
            self.logger.debug(f'Loaded params {self._params}')

            # Allow items to be automatically initiated on startup
            if self.has_iattr(item.conf, 'viess_init') and self.get_iattr_value(item.conf, 'viess_init'):
                self.logger.info(f'Item {item} is initialized on startup')
                if commandcode not in self._init_cmds:
                    self._init_cmds.append(commandcode)
                self.logger.debug(f'CommandCodes should be read at init: {self._init_cmds}')

            # Allow items to be cyclically updated
            if self.has_iattr(item.conf, 'viess_read_cycle'):
                cycle = int(self.get_iattr_value(item.conf, 'viess_read_cycle'))
                self.logger.info(f'Item {item} should read cyclic every {cycle} seconds')
                nexttime = time.time() + cycle
                if commandcode not in self._cyclic_cmds:
                    self._cyclic_cmds[commandcode] = {'cycle': cycle, 'nexttime': nexttime}
                else:
                    # If another item requested this command already with a longer cycle, use the shorter cycle now
                    if self._cyclic_cmds[commandcode]['cycle'] > cycle:
                        self._cyclic_cmds[commandcode]['cycle'] = cycle
                self.logger.debug(f'CommandCodes should be read cyclic: {self._cyclic_cmds}')

        # Process the write config
        if self.has_iattr(item.conf, 'viess_send'):
            if self.get_iattr_value(item.conf, 'viess_send'):
                commandname = self.get_iattr_value(item.conf, 'viess_read')
            else:
                commandname = self.get_iattr_value(item.conf, 'viess_send')

            if commandname is None or commandname not in self._commandset:
                self.logger.error(f'Item {item} contains invalid write command {commandname}!')
                return None
            else:
                self.logger.info(f'Item {item} to be written by using command {commandname}')
                return self.update_item

        # get operating modes list
        if self.has_iattr(item.conf, 'viess_ba_list'):
            self._balist_item = item
            self.logger.info(f'Item {item} wants list of operating modes')

    def parse_logic(self, logic):
        pass

    def update_item(self, item, caller=None, source=None, dest=None):
        '''
        Callback method for sending values to the plugin when a registered item has changed

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        '''
        if self.alive and caller != self.get_shortname():
            self.logger.info(f'Update item: {item.id()}, item has been changed outside this plugin')
            self.logger.debug(f'update_item was called with item {item} from caller {caller}, source {source} and dest {dest}')

            if self.has_iattr(item.conf, 'viess_send'):
                # Send write command
                if self.get_iattr_value(item.conf, 'viess_send'):
                    commandname = self.get_iattr_value(item.conf, 'viess_read')
                else:
                    commandname = self.get_iattr_value(item.conf, 'viess_send')
                value = item()
                self.logger.debug(f'Got item value to be written: {value} on command name {commandname}')
                if not self._send_command(commandname, value):
                    # create_write_command() liefert False, wenn das Schreiben fehlgeschlagen ist
                    # -> dann auch keine weitere Verarbeitung
                    self.logger.debug(f'Write for {commandname} with value {value} failed, reverting value, canceling followup actions')
                    item(item.property.last_value, self.get_shortname())
                    return None

                # If a read command should be sent after write
                if self.has_iattr(item.conf, 'viess_read') and self.has_iattr(item.conf, 'viess_read_afterwrite'):
                    readcommandname = self.get_iattr_value(item.conf, 'viess_read')
                    readafterwrite = self.get_iattr_value(item.conf, 'viess_read_afterwrite')
                    self.logger.debug(f'Attempting read after write for item {item}, command {readcommandname}, delay {readafterwrite}')
                    if readcommandname is not None and readafterwrite is not None:
                        aw = float(readafterwrite)
                        time.sleep(aw)
                        self._send_command(readcommandname)

                # If commands should be triggered after this write
                if self.has_iattr(item.conf, 'viess_trigger'):
                    trigger = self.get_iattr_value(item.conf, 'viess_trigger')
                    if trigger is None:
                        self.logger.error(f'Item {item} contains invalid trigger command list {trigger}!')
                    else:
                        tdelay = 5  # default delay
                        if self.has_iattr(item.conf, 'viess_trigger_afterwrite'):
                            tdelay = float(self.get_iattr_value(item.conf, 'viess_trigger_afterwrite'))
                        if type(trigger) != list:
                            trigger = [trigger]
                        for triggername in trigger:
                            triggername = triggername.strip()
                            if triggername is not None and readafterwrite is not None:
                                self.logger.debug(f'Triggering command {triggername} after write for item {item}')
                                time.sleep(tdelay)
                                self._send_command(triggername)

            elif self.has_iattr(item.conf, 'viess_timer'):
                timer_app = self.get_iattr_value(item.conf, 'viess_timer')
                uzsu_dict = item()
                self.logger.debug(f'Got changed UZSU timer: {uzsu_dict} on timer application {timer_app}')
                self._uzsu_dict_to_viess_timer(timer_app, uzsu_dict)

            elif self.has_iattr(item.conf, 'viess_update'):
                if item():
                    self.logger.debug('Reading of all values/items has been requested')
                    self.update_all_read_items()

    def send_cyclic_cmds(self):
        '''
        Recall function for shng scheduler. Reads all values configured to be read cyclically.
        '''
        # check if another cyclic cmd run is still active
        if self._cyclic_update_active:
            self.logger.warning('Triggered cyclic command read, but previous cyclic run is still active. Check device and cyclic configuration (too much/too short?)')
            return
        else:
            self.logger.info('Triggering cyclic command read')

        # set lock
        self._cyclic_update_active = True
        currenttime = time.time()
        read_items = 0
        todo = []
        for commandcode in list(self._cyclic_cmds.keys()):

            entry = self._cyclic_cmds[commandcode]
            # Is the command already due?
            if entry['nexttime'] <= currenttime:
                todo.append(commandcode)

        if self._protocol == 'KW':
            # see if we got to do anything - maybe no items are due to be read?
            if len(todo) > 0:
                self._KW_send_multiple_read_commands(todo)
                for addr in todo:
                    self._cyclic_cmds[addr]['nexttime'] = currenttime + self._cyclic_cmds[addr]['cycle']
                read_items = len(todo)
        else:
            for addr in todo:
                # as this loop can take considerable time, repeatedly check if shng wants to stop
                if not self.alive:
                    self.logger.info('shng issued stop command, canceling cyclic read.')
                    return

                commandname = self._commandname_by_commandcode(addr)
                self.logger.debug(f'Triggering cyclic read command: {commandname}')
                self._send_command(commandname, )
                self._cyclic_cmds[addr]['nexttime'] = currenttime + self._cyclic_cmds[addr]['cycle']
                read_items += 1

        self._cyclic_update_active = False
        if read_items:
            self.logger.debug(f'cyclic command read took {(time.time() - currenttime):.1f} seconds for {read_items} items')

    def update_all_read_items(self):
        '''
        Read all values preset in commands.py as readable
        '''
        for commandcode in list(self._params.keys()):
            commandname = self._commandname_by_commandcode(commandcode)
            self.logger.debug(f'Triggering read command: {commandname} for requested value update')
            self._send_command(commandname)

    def read_addr(self, addr):
        '''
        Tries to read a data point indepently of item config

        :param addr: data point addr (2 byte hex address)
        :type addr: str
        :return: Value if read is successful, None otherwise
        '''
        addr = addr.lower()

        commandname = self._commandname_by_commandcode(addr)
        if commandname is None:
            self.logger.debug(f'Address {addr} not defined in commandset, aborting')
            return None

        self.logger.debug(f'Attempting to read address {addr} for command {commandname}')

        (packet, responselen) = self._build_command_packet(commandname)
        if packet is None:
            return None

        response_packet = self._send_command_packet(packet, responselen)
        if response_packet is None:
            return None

        res = self._parse_response(response_packet, commandname)
        if res is None:
            return None

        (value, commandcode) = res

        return value

    def read_temp_addr(self, addr, length, unit):
        '''
        Tries to read an arbitrary supplied data point indepently of device config

        :param addr: data point addr (2 byte hex address)
        :type addr: str
        :param len: Length (in byte) expected from address read
        :type len: num
        :param unit: Unit code from commands.py
        :type unit: str
        :return: Value if read is successful, None otherwise
        '''
        # as we have no reference whatever concerning the supplied data, we do a few sanity checks...

        addr = addr.lower()

        if len(addr) != 4:              # addresses are 2 bytes
            self.logger.warning(f'temp address: address not 4 digits long: {addr}')
            return None

        for c in addr:                  # addresses are hex strings
            if c not in '0123456789abcdef':
                self.logger.warning(f'temp address: address digit "{c}" is not hex char')
                return None

        if length < 1 or length > 32:          # empiritistical choice
            self.logger.warning(f'temp address: len is not > 0 and < 33: {len}')
            return None

        if unit not in self._unitset:   # units need to be predefined
            self.logger.warning(f'temp address: unit {unit} not in unitset. Cannot use custom units')
            return None

        # addr already known?
        if addr in self._commandset:
            cmd = self._commandname_by_commandcode(addr)
            self.logger.info(f'temp address {addr} already known for command {cmd}')
        else:
            # create temp commandset
            cmd = 'temp_cmd'
            cmdconf = {'addr': addr, 'len': length, 'unit': unit, 'set': False}
            self.logger.debug(f'Adding temporary command config {cmdconf} for command temp_cmd')
            self._commandset[cmd] = cmdconf

        res = self.read_addr(addr)

        if cmd == 'temp_cmd':
            del self._commandset['temp_cmd']

        return res

    def write_addr(self, addr, value):
        '''
        Tries to write a data point indepently of item config

        :param addr: data point addr (2 byte hex address)
        :type addr: str
        :param value: value to write
        :return: Value if read is successful, None otherwise
        '''
        addr = addr.lower()

        commandname = self._commandname_by_commandcode(addr)
        if commandname is None:
            self.logger.debug(f'Address {addr} not defined in commandset, aborting')
            return None

        self.logger.debug(f'Attempting to write address {addr} with value {value} for command {commandname}')

        (packet, responselen) = self._build_command_packet(commandname, value)
        if packet is None:
            return None

        response_packet = self._send_command_packet(packet, responselen)
        if response_packet is None:
            return None

        return self._parse_response(response_packet, commandname)

#
# initialization methods
#

    def _load_configuration(self):
        '''
        Load configuration sets from commands.py
        '''

        # Load protocol dependent sets
        if self._protocol in commands.controlset and self._protocol in commands.errorset and self._protocol in commands.unitset and self._protocol in commands.returnstatus and self._protocol in commands.setreturnstatus:
            self._controlset = commands.controlset[self._protocol]
            self.logger.debug(f'Loaded controlset for protocol {self._controlset}')
            self._errorset = commands.errorset[self._protocol]
            self.logger.debug(f'Loaded errors for protocol {self._errorset}')
            self._unitset = commands.unitset[self._protocol]
            self.logger.debug(f'Loaded units for protocol {self._unitset}')
            self._devicetypes = commands.devicetypes
            self.logger.debug(f'Loaded device types for protocol {self._devicetypes}')
            self._returnstatus = commands.returnstatus[self._protocol]
            self.logger.debug(f'Loaded return status for protocol {self._returnstatus}')
            self._setreturnstatus = commands.setreturnstatus[self._protocol]
            self.logger.debug(f'Loaded set return status for protocol {self._setreturnstatus}')
        else:
            self.logger.error(f'Sets for protocol {self._protocol} could not be found or incomplete!')
            return False

        # Load device dependent sets
        if self._heating_type in commands.commandset and self._heating_type in commands.operatingmodes and self._heating_type in commands.systemschemes:
            self._commandset = commands.commandset[self._heating_type]
            self.logger.debug(f'Loaded commands for heating type {self._commandset}')
            self._operatingmodes = commands.operatingmodes[self._heating_type]
            self.logger.debug(f'Loaded operating modes for heating type {self._operatingmodes}')
            self._systemschemes = commands.systemschemes[self._heating_type]
            self.logger.debug(f'Loaded system schemes for heating type {self._systemschemes}')
        else:
            sets = []
            if self._heating_type not in commands.commandset:
                sets += 'command'
            if self._heating_type not in commands.operatingmodes:
                sets += 'operating modes'
            if self._heating_type not in commands.systemschemes:
                sets += 'system schemes'

            self.logger.error(f'Sets {", ".join(sets)} for heating type {self._heating_type} could not be found!')
            return False

        self.logger.info(f'Loaded configuration for heating type {self._heating_type} with protocol {self._protocol}')
        self._config_loaded = True
        return True

    def _connect(self):
        '''
        Tries to establish a connection to the serial reading device. To prevent
        multiple concurrent connection locking is used.

        :return: Returns True if connection was established, False otherwise
        :rtype: bool
        '''
        if not self.alive:
            return False

        if self._connected and self._serial:
            return True

        self._lock.acquire()
        try:
            self.logger.debug(f'Connecting to {self._serialport}..')
            self._serial = serial.Serial()
            self._serial.baudrate = self._controlset['Baudrate']
            self._serial.parity = self._controlset['Parity']
            self._serial.bytesize = self._controlset['Bytesize']
            self._serial.stopbits = self._controlset['Stopbits']
            self._serial.port = self._serialport

            # both of the following timeout values are determined by trial and error
            if self._protocol == 'KW':
                # needed to "capture" the 0x05 sync bytes
                self._serial.timeout = 1.0
            else:
                # not too long to prevent lags in communication.
                self._serial.timeout = 0.5
            self._serial.open()
            self._connected = True
            self.logger.info(f'Connected to {self._serialport}')
            self._connection_attempts = 0
            if not self._standalone and not self.scheduler_get('cyclic'):
                self._create_cyclic_scheduler()
            return True
        except Exception as e:
            self.logger.error(f'Could not _connect to {self._serialport}; Error: {e}')
            return False
        finally:
            self._lock.release()

    def _disconnect(self):
        '''
        Disconnect any connected devices.
        '''
        self._connected = False
        self._initialized = False
        try:
            self._serial.close()
        except IOError:
            pass
        self._serial = None
        try:
            self._lock.release()
        except RuntimeError:
            pass
        self.logger.info('Disconnected')

    def _init_communication(self):
        '''
        After connecting to the device, setup the communication protocol

        :return: Returns True, if communication was established successfully, False otherwise
        :rtype: bool
        '''
        # just try to connect anyway; if connected, this does nothing and no harm, if not, it connects
        if not self._connect():

            self.logger.error('Init communication not possible as connect failed.')
            return False

        # initialization only necessary for P300 protocol...
        if self._protocol == 'P300':

            # init procedure is
            # interface: 0x04 (reset)
            #                           device: 0x05 (repeated)
            # interface: 0x160000 (sync)
            #                           device: 0x06 (sync ok)
            # interface: resume communication, periodically send 0x160000 as keepalive if necessary

            self.logger.debug('Init Communication....')
            is_initialized = False
            initstringsent = False
            self.logger.debug(f'send_bytes: Send reset command {self._int2bytes(self._controlset["Reset_Command"], 1)}')
            self._send_bytes(self._int2bytes(self._controlset['Reset_Command'], 1))
            readbyte = self._read_bytes(1)
            self.logger.debug(f'read_bytes: read {readbyte}, last byte is {self._lastbyte}')

            for i in range(0, 10):
                if initstringsent and self._lastbyte == self._int2bytes(self._controlset['Acknowledge'], 1):
                    is_initialized = True
                    self.logger.debug('Device acknowledged initialization')
                    break
                if self._lastbyte == self._int2bytes(self._controlset['Not_initiated'], 1):
                    self._send_bytes(self._int2bytes(self._controlset['Sync_Command'], 3))
                    self.logger.debug(f'send_bytes: Send sync command {self._int2bytes(self._controlset["Sync_Command"], 3)}')
                    initstringsent = True
                elif self._lastbyte == self._int2bytes(self._controlset['Init_Error'], 1):
                    self.logger.error(f'The interface has reported an error (\x15), loop increment {i}')
                    self._send_bytes(self._int2bytes(self._controlset['Reset_Command'], 1))
                    self.logger.debug(f'send_bytes: Send reset command {self._int2bytes(self._controlset["Reset_Command"], 1)}')
                    initstringsent = False
                else:
                    self._send_bytes(self._int2bytes(self._controlset['Reset_Command'], 1))
                    self.logger.debug(f'send_bytes: Send reset command {self._int2bytes(self._controlset["Reset_Command"], 1)}')
                    initstringsent = False
                readbyte = self._read_bytes(1)
                self.logger.debug(f'read_bytes: read {readbyte}, last byte is {self._lastbyte}')

            self.logger.debug(f'Communication initialized: {is_initialized}')
            self._initialized = is_initialized

        else:  # at the moment the only other supported protocol is 'KW' which is not stateful
            is_initialized = True
            self._initialized = is_initialized

        return is_initialized

    def _create_cyclic_scheduler(self):
        '''
        Setup the scheduler to handle cyclic read commands and find the proper time for the cycle.
        '''
        if not self.alive:
            return

        shortestcycle = -1
        # find shortest cycle
        for commandname in list(self._cyclic_cmds.keys()):
            entry = self._cyclic_cmds[commandname]
            if shortestcycle == -1 or entry['cycle'] < shortestcycle:
                shortestcycle = entry['cycle']
        # Start the worker thread
        if shortestcycle != -1:
            # Balance unnecessary calls and precision
            workercycle = int(shortestcycle / 2)
            # just in case it already exists...
            if self.scheduler_get('cyclic'):
                self.scheduler_remove('cyclic')
            self.scheduler_add('cyclic', self.send_cyclic_cmds, cycle=workercycle, prio=5, offset=0)
            self.logger.info(f'Added cyclic worker thread ({workercycle} sec cycle). Shortest item update cycle found: {shortestcycle} sec')

    def _read_initial_values(self):
        '''
        Read all values configured to be read at startup / connection
        '''
        if self._balist_item is not None:
            balist = list(self._operatingmodes.values())
            self._balist_item(balist, self.get_shortname())
            self.logger.info(f'writing list of operating modes ({len(balist)} entries) to item {self._balist_item}')

        if self._init_cmds != []:
            self.logger.info('Starting initial read commands.')
            if self._protocol == 'KW':
                self._KW_send_multiple_read_commands(self._init_cmds)
            else:
                for commandcode in self._init_cmds:
                    commandname = self._commandname_by_commandcode(commandcode)
                    self.logger.debug(f'send_init_commands {commandname}')
                    self._send_command(commandname)
            self._initread = True
            self.logger.debug(f'self._initread = {self._initread}')

    #
    # send and receive commands
    #

    def _read_timers(self):
        '''
        Read all configured timer values from device and create uzsu timer dict
        '''
        if self._application_timer is not []:
            self.logger.debug('Starting timer read commands.')
            for timer_app in self._application_timer:
                for commandcode in self._application_timer[timer_app]['commandcodes']:
                    commandname = self._commandname_by_commandcode(commandcode)
                    self.logger.debug(f'send_timer_commands {commandname}')
                    self._send_command(commandname)
            self._timerread = True
            self.logger.debug(f'Timer Readout done = {self._timerread}')
            self._viess_dict_to_uzsu_dict()

    def _send_command(self, commandname, value=None):
        '''
        Create formatted command sequence from command name and send to device

        Note: The implementation detail results in "write if value present, read if value is None".
              I have not found anything wrong with this; if any use case needs a specific read/write
              selection, please tell me.

        :param commandname: Command for which to create command sequence as defined in commands.py
        :type commandname: str
        :param value: Value to write to device, None if command is read command
        '''
        if value is not None:
            self.logger.debug(f'Got a new write job: Command {commandname} with value {value}')
        else:
            self.logger.debug(f'Got a new read job: Command {commandname}')

        # Build packet with value bytes for write commands
        (packet, responselen) = self._build_command_packet(commandname, value)

        # quit if no packet (error on packet build)
        if packet is None:
            return False

        if value is not None and self._protocol == 'KW':
            read_response = False
        else:
            read_response = True

        # hand over built packet to send_command_packet
        response_packet = self._send_command_packet(packet, responselen)

        # process response
        if response_packet is None:
            return False

        result = self._process_response(response_packet, commandname, read_response)
        return result

    def _KW_send_multiple_read_commands(self, commandcodes):
        '''
        Takes list of commandnames, builds all command packets and tries to send them in one go.
        This only works for read commands and only with KW protocol.
        On error the whole remaining read process is aborted, no retries or continuation is attempted.

        :param commandnames: List of commands for which to create command sequence as defined in commands.py
        :type commandname: str
        '''
        if self._protocol != 'KW':
            self.logger.error(f'Called _KW_send_multiple_read_commands, but protocol is {self._protocol}. This shouldn\'t happen..')
            return

        self.logger.debug(f'Got a new bulk read job: Commands {commandcodes}')

        bulk = {}

        # Build packets with value bytes for write commands
        for addr in commandcodes:
            commandname = self._commandname_by_commandcode(addr)
            (packet, responselen) = self._build_command_packet(commandname, None, True)

            if packet:
                bulk[addr] = {'packet': packet, 'responselen': responselen, 'command': commandname}

        # quit if no packet (error on packet build)
        if not bulk:
            return

        if not self._connected:
            self.logger.error('Not connected, trying to reconnect.')
            if not self._connect():
                self.logger.error('Could not connect to serial device')
                return

        self._lock.acquire()
        try:
            self._init_communication()

            replies = {}

            if not self._KW_get_sync():
                return

            first_cmd = True
            first_packet = bytearray(self._int2bytes(self._controlset['StartByte'], 1))

            for addr in bulk.keys():

                if first_cmd:
                    # make sure that the first sent packet has the StartByte (0x01) lead byte set
                    # this way the first packet actually sent has the start byte, regardless of bulk.keys() order
                    first_packet.extend(bulk[addr]['packet'])
                    bulk[addr]['packet'] = first_packet
                    first_cmd = False

                # send query
                try:
                    self._send_bytes(bulk[addr]['packet'])
                    self.logger.debug(f'Successfully sent packet: {self._bytes2hexstring(bulk[addr]["packet"])}')
                except IOError as io:
                    raise IOError(f'IO Error: {io}')
                    return
                except Exception as e:
                    raise Exception(f'Exception while sending: {e}')
                    return

                # receive response
                replies[addr] = bytearray()
                try:
                    self.logger.debug(f'Trying to receive {bulk[addr]["responselen"]} bytes of the response')
                    chunk = self._read_bytes(bulk[addr]['responselen'])

                    self.logger.debug(f'Received {len(chunk)} bytes chunk of response as hexstring {self._bytes2hexstring(chunk)} and as bytes {chunk}')
                    if len(chunk) != 0:
                        replies[addr].extend(chunk)
                    else:
                        self.logger.error(f'Received 0 bytes chunk from {addr} - this probably is a communication error, possibly a wrong datapoint address?')
                        return
                except IOError as io:
                    raise IOError(f'IO Error: {io}')
                    return
                except Exception as e:
                    raise Exception(f'Error receiving response: {e}')
                    return

            # sent all read requests, time to parse the replies
            # do this inside the _lock-block so this doesn't interfere with
            # possible cyclic read data assignments
            for addr in bulk.keys():
                if len(replies[addr]) > 0:
                    self._process_response(replies[addr], bulk[addr]['command'], True)

        except IOError as io:
            self.logger.error(f'KW_send_multiple_read_commands failed with IO error: {io}')
            self.logger.error('Trying to reconnect (disconnecting, connecting')
            self._disconnect()
            return
        except Exception as e:
            self.logger.error(f'KW_send_multiple_read_commands failed with error: {e}')
            return
        finally:
            try:
                self._lock.release()
            except RuntimeError:
                pass

    def _KW_get_sync(self):
        '''
        Try to get a sync packet (0x05) from heating system to be able to send commands

        :return: True if sync packet received, False otherwise (after retries)
        :rtype: bool
        '''
        if not self._connected or self._protocol != 'KW':
            return False    # don't even try. We only want to be called by _send_command_packet, which just before executed connect()

        retries = 5

        # try to reset communication, especially if previous P300 comms is still open
        self._send_bytes(self._int2bytes(self._controlset['Reset_Command'], 1))

        attempt = 0
        while attempt < retries:
            self.logger.debug(f'Starting sync loop - attempt {attempt + 1}/{retries}')

            self._serial.reset_input_buffer()
            chunk = self._read_bytes(1)
            # enable for 'raw' debugging
            # self.logger.debug(f'sync loop - got {self._bytes2hexstring(chunk)}')
            if chunk == self._int2bytes(self._controlset['Not_initiated'], 1, False):
                self.logger.debug('Got sync. Commencing command send')
                return True
            time.sleep(.8)
            attempt = attempt + 1
        self.logger.error(f'Sync not acquired after {attempt} attempts')
        self._disconnect()

        return False

    def _send_command_packet(self, packet, packetlen_response):
        '''
        Send command sequence to device

        :param packet: Command sequence to send
        :type packet: bytearray
        :param packetlen_response: number of bytes expected in reply
        :type packetlen_response: int
        :param read_response: True if command was read command and value is expected, False if only status byte is expected (only needed for KW protocol)
        :type read_response: bool
        :return: Response packet (bytearray) if no error occured, None otherwise
        '''
        if not self._connected:
            self.logger.error('Not connected, trying to reconnect.')
            if not self._connect():
                self.logger.error('Could not connect to serial device')
                return None

        self._lock.acquire()
        try:
            if not self._initialized or (time.time() - 500) > self._lastbytetime:
                if self._protocol == 'P300':
                    if self._initialized:
                        self.logger.debug('Communication timed out, trying to reestablish communication.')
                    else:
                        self.logger.info('Communication no longer initialized, trying to reestablish.')
                self._init_communication()

            if self._initialized:
                # send query
                try:
                    if self._protocol == 'KW':
                        # try to get sync, exit if it fails
                        if not self._KW_get_sync():
                            return None

                    self._send_bytes(packet)
                    self.logger.debug(f'Successfully sent packet: {self._bytes2hexstring(packet)}')
                except IOError as io:
                    raise IOError(f'IO Error: {io}')
                    return None
                except Exception as e:
                    raise Exception(f'Exception while sending: {e}')
                    return None

                # receive response
                response_packet = bytearray()
                self.logger.debug(f'Trying to receive {packetlen_response} bytes of the response')
                chunk = self._read_bytes(packetlen_response)

                if self._protocol == 'P300':
                    self.logger.debug(f'Received {len(chunk)} bytes chunk of response as hexstring {self._bytes2hexstring(chunk)} and as bytes {chunk}')
                    if len(chunk) != 0:
                        if chunk[:1] == self._int2bytes(self._controlset['Error'], 1):
                            self.logger.error(f'Interface returned error! response was: {chunk}')
                        elif len(chunk) == 1 and chunk[:1] == self._int2bytes(self._controlset['Not_initiated'], 1):
                            self.logger.error('Received invalid chunk, connection not initialized. Forcing re-initialize...')
                            self._initialized = False
                        elif chunk[:1] != self._int2bytes(self._controlset['Acknowledge'], 1):
                            self.logger.error(f'Received invalid chunk, not starting with ACK! response was: {chunk}')
                            self._error_count += 1
                            if self._error_count >= 5:
                                self.logger.warning('Encountered 5 invalid chunks in sequence. Maybe communication was lost, re-initializing')
                                self._initialized = False
                        else:
                            response_packet.extend(chunk)
                            self._error_count = 0
                            return response_packet
                    else:
                        self.logger.error(f'Received 0 bytes chunk - ignoring response_packet! chunk was: {chunk}')
                elif self._protocol == 'KW':
                    self.logger.debug(f'Received {len(chunk)} bytes chunk of response as hexstring {self._bytes2hexstring(chunk)} and as bytes {chunk}')
                    if len(chunk) != 0:
                        response_packet.extend(chunk)
                        return response_packet
                    else:
                        self.logger.error('Received 0 bytes chunk - this probably is a communication error, possibly a wrong datapoint address?')
            else:
                raise Exception('Interface not initialized!')
        except IOError as io:
            self.logger.error(f'send_command_packet failed with IO error: {io}')
            self.logger.error('Trying to reconnect (disconnecting, connecting')
            self._disconnect()
        except Exception as e:
            self.logger.error(f'send_command_packet failed with error: {e}')
        finally:
            try:
                self._lock.release()
            except RuntimeError:
                pass

        # if we didn't return with data earlier, we hit an error. Act accordingly
        return None

    def _send_bytes(self, packet):
        '''
        Send data to device

        :param packet: Data to be sent
        :type packet: bytearray
        :return: Returns False, if no connection is established or write failed; True otherwise
        :rtype: bool
        '''
        if not self._connected:
            return False

        try:
            self._serial.write(packet)
        except serial.SerialTimeoutException:
            return False

        # self.logger.debug(f'send_bytes: Sent {packet}')
        return True

    def _read_bytes(self, length):
        '''
        Try to read bytes from device

        :param length: Number of bytes to read
        :type length: int
        :return: Number of bytes actually read
        :rtype: int
        '''
        if not self._connected:
            return 0

        totalreadbytes = bytes()
        # self.logger.debug('read_bytes: Start read')
        starttime = time.time()

        # don't wait for input indefinitely, stop after self._timeout seconds
        while time.time() <= starttime + self._timeout:
            readbyte = self._serial.read()
            self._lastbyte = readbyte
            # self.logger.debug(f'read_bytes: Read {readbyte}')
            if readbyte != b'':
                self._lastbytetime = time.time()
            else:
                return totalreadbytes
            totalreadbytes += readbyte
            if len(totalreadbytes) >= length:
                return totalreadbytes

        # timeout reached, did we read anything?
        if not totalreadbytes:

            # just in case, force plugin to reconnect
            self._connected = False
            self._initialized = False

        # return what we got so far, might be 0
        return totalreadbytes

    def _process_response(self, response, commandname='', read_response=True, update_item=True):
        '''
        Process device response data, try to parse type and value and assign value to associated item

        :param response: Data received from device
        :type response: bytearray
        :param commandname: Commandname used for request (only needed for KW protocol)
        :type commandname: str
        :param read_response: True if command was read command and value is expected, False if only status byte is expected (only needed for KW protocol)
        :type read_response: bool
        :param update_item: True if value should be written to corresponding item
        :type update_item: bool
        '''
        res = self._parse_response(response, commandname, read_response)

        # None means error on read/parse or write reponse. Errors are already logged, so no further action necessary
        if res is None:
            return

        # write returns True on success
        if res is True:
            return True

        # assign results
        (value, commandcode) = res

        # get command config
        commandname = self._commandname_by_commandcode(commandcode)
        commandconf = self._commandset[commandname]
        commandunit = commandconf['unit']

        # update items if commandcode is in item-dict
        if commandcode in self._params.keys():

            # Find corresponding item
            item = self._params[commandcode]['item']
            self.logger.debug(f'Corresponding item {item} for command {commandname}')

            # Update item
            if update_item:
                self.logger.debug(f'Updating item {item} with value {value}')
                if commandunit == 'CT':
                    # Split timer list and put it the child items, which were created by struct.timer in iso time format
                    try:
                        for child in item.return_children():
                            child_item = str(child.id())
                            if child_item.endswith('an1'):
                                child(value[0]['An'], self.get_shortname())
                                # child(datetime.strptime(value[0]['An'], '%H:%M').time().isoformat())
                            elif child_item.endswith('aus1'):
                                child(value[0]['Aus'], self.get_shortname())
                            elif child_item.endswith('an2'):
                                child(value[1]['An'], self.get_shortname())
                            elif child_item.endswith('aus2'):
                                child(value[1]['Aus'], self.get_shortname())
                            elif child_item.endswith('an3'):
                                child(value[2]['An'], self.get_shortname())
                            elif child_item.endswith('aus3'):
                                child(value[2]['Aus'], self.get_shortname())
                            elif child_item.endswith('an4'):
                                child(value[3]['An'], self.get_shortname())
                            elif child_item.endswith('aus4'):
                                child(value[3]['Aus'], self.get_shortname())
                    except KeyError:
                        self.logger.debug('No child items for timer found (use timer.structs) or value no valid')

                # save value to item
                item(value, self.get_shortname())
            else:
                self.logger.debug(f'Not updating item {item} as not requested')
        else:
            if (commandcode not in self._timer_cmds) and update_item:
                self.logger.error(f'Should update item with response to a command not in item config: {commandcode}. This shouldn''t happen..')

        # Process response for timers in timer-dict using the commandcode
        if commandcode in self._timer_cmds:
            self.logger.debug(f'process_response_timer: {commandcode}')

            # Find timer application
            for timer in self._application_timer:
                if commandcode in self._application_timer[timer]['commandcodes']:
                    timer_app = timer

            # Fill timer dict
            if timer_app not in self._viess_timer_dict:
                self._viess_timer_dict[timer_app] = {}

            self._viess_timer_dict[timer_app][commandname] = value
            self.logger.debug(f'Viessmann timer dict: {self._viess_timer_dict}')

#
# convert data types
#

    def _build_valuebytes_from_value(self, value, commandconf):
        '''
        Convert value to formatted bytearray for write commands
        :param value: Value to send
        :param commandconf: configuration set for requested command
        :type commandconf: dict
        :return: bytearray with value if successful, None if error
        '''
        try:
            commandvaluebytes = commandconf['len']
            commandunit = commandconf['unit']
            set_allowed = bool(commandconf['set'])
            if 'min_value' in commandconf:
                min_allowed_value = commandconf['min_value']
            else:
                min_allowed_value = None
            if 'max_value' in commandconf:
                max_allowed_value = commandconf['max_value']
            else:
                max_allowed_value = None
        except KeyError:
            self.logger.error(f'Error in command configuration {commandconf}, aborting')
            return None

        # unit HEX = hex values as string is only for read requests (debugging). Don't even try...
        if commandunit == 'HEX':

            self.logger.error(f'Error in command configuration {commandconf}: unit HEX is not writable, aborting')
            return None

        if commandunit == 'BA':

            # try to convert BA string to byte value, setting str values will fail
            # this will not work properly if multiple entries have the same value!
            try:
                value = int(dict(map(reversed, self._operatingmodes.items()))[value])
                commandunit = 'IUNON'
            except KeyError:
                # value doesn't exist in operatingmodes. don't know what to do
                self.logger.error(f'Value {value} not defined in operating modes for device {self._heating_type}')
                return None

        try:
            unitconf = self._unitset[commandunit]
        except KeyError:
            self.logger.error(f'Error: unit {commandunit} not found in unit set {self._unitset}')
            return None

        try:
            valuetype = unitconf['type']
            valuereadtransform = unitconf['read_value_transform']
        except KeyError:
            self.logger.error(f'Error in unit configuration {unitconf} for unit {commandunit}, aborting')
            return None

        self.logger.debug(f'Unit defined to {commandunit} with config{unitconf}')

        # check if writing is allowed for this address
        if not set_allowed:
            self.logger.error(f'Command {self._commandname_by_commandcode(commandconf["addr"])} is not configured for writing')
            return None

        # check if value is empty
        if value is None or value == '':
            self.logger.error(f'Command value for command {self._commandname_by_commandcode(commandconf["addr"])} is empty, not possible to send (check item, command and unit configuration')
            return None

        # check if value to be written is in allowed range
        if (min_allowed_value is not None and min_allowed_value > value) or (max_allowed_value is not None and max_allowed_value < value):
            self.logger.error(f'Invalid range - value {value} not in range [{min_allowed_value}, {max_allowed_value}]')
            return None

        try:
            # Create valuebytes
            if valuetype == 'datetime' or valuetype == 'date':
                try:
                    datestring = dateutil.parser.isoparse(value).strftime('%Y%m%d%w%H%M%S')
                    # Viessmann erwartet 2 digits für Wochentag, daher wird hier noch eine 0 eingefügt
                    datestring = datestring[:8] + '0' + datestring[8:]
                    valuebytes = bytes.fromhex(datestring)
                    self.logger.debug(f'Created value bytes for type {valuetype} as bytes: {valuebytes}')
                except Exception as e:
                    self.logger.error(f'Incorrect data format, YYYY-MM-DD expected; Error: {e}')
                    return None
            elif valuetype == 'timer':
                try:
                    times = ''
                    for switching_time in value:
                        an = self._encode_timer(switching_time['An'])
                        aus = self._encode_timer(switching_time['Aus'])
                        times += f'{an:02x}{aus:02x}'
                    valuebytes = bytes.fromhex(times)
                    self.logger.debug(f'Created value bytes for type {valuetype} as hexstring: {self._bytes2hexstring(valuebytes)} and as bytes: {valuebytes}')
                except Exception as e:
                    self.logger.error(f'Incorrect data format, (An: hh:mm Aus: hh:mm) expected; Error: {e}')
                    return None
            # valuetype 'list' is transformed to listentry via index on read, but written directly as int, so numerical transform could apply
            elif valuetype == 'integer' or valuetype == 'list':
                # transform value is numerical -> multiply value with it
                if self._isfloat(valuereadtransform):
                    value = self._value_transform_write(value, valuereadtransform)
                    self.logger.debug(f'Transformed value using method "* {valuereadtransform}" to {value}')
                elif valuereadtransform == 'bool':
                    value = bool(value)
                else:
                    value = int(value)
                valuebytes = self._int2bytes(value, commandvaluebytes)
                self.logger.debug(f'Created value bytes for type {valuetype} as hexstring: {self._bytes2hexstring(valuebytes)} and as bytes: {valuebytes}')
            else:
                self.logger.error(f'Type {valuetype} not definied for creating write command bytes')
                return None
        except Exception as e:
            self.logger.debug(f'_build_valuebytes_from_value failed with unexpected error: {e}')
            return None

        return valuebytes

    def _build_command_packet(self, commandname, value=None, KWFollowUp=False):
        '''
        Create formatted command sequence from command name.
        If value is None, a read packet will be built, a write packet otherwise

        :param commandname: Command for which to create command sequence as defined in commands.py
        :type commandname: str
        :param value: Write value if command is to be written
        :param KWFollowUp: create read sequence for KW protocol if multiple read commands will be sent without individual sync
        :type KWFollowUp: bool
        :return: tuple of (command sequence, expected response len), (None, 0) if error occured
        :rtype: tuple (bytearray, int)
        '''

        # A read_request telegram looks like this:
        # P300: ACK (1 byte), startbyte (1 byte), data length in bytes (1 byte), request/response (1 byte), read/write (1 byte), addr (2 byte), amount of value bytes expected in answer (1 byte), checksum (1 byte)
        # KW: startbyte (1 byte), read/write (1 byte), addr (2 bytes), amount of value bytes expected in answer (1 byte)
        # A write_request telegram looks like this:
        # P300: ACK (1 byte), startbyte (1 byte), data length in bytes (1 byte), request/response (1 byte), read/write (1 byte), addr (2 byte), amount of bytes to be written (1 byte), value (bytes as per last byte), checksum (1 byte)
        # KW: startbyte (1 byte), read/write (1 byte), addr (2 bytes), length of value (1 byte), value bytes (1-4 bytes)

        write = value is not None
        self.logger.debug(f'Build {"write" if write else "read"} packet for command {commandname}')

        # Get command config
        commandconf = self._commandset[commandname]
        commandcode = (commandconf['addr']).lower()
        commandvaluebytes = commandconf['len']

        if write:
            valuebytes = self._build_valuebytes_from_value(value, commandconf)
            # can't write 'no value'...
            if not valuebytes:
                return (None, 0)

            # Calculate length of payload (only needed for P300)
            payloadlength = int(self._controlset.get('Command_bytes_write', 0)) + int(commandvaluebytes)
            self.logger.debug(f'Payload length is: {payloadlength} bytes')

        # Build packet for read commands
        #
        # at the moment this only has to differentiate between protocols P300 and KW
        # these are basically similar, only P300 is an evolution of KW adding
        # stateful connections, command length and checksum
        #
        # so for the time being the easy way is one code path for both protocols which
        # omits P300 elements from the built byte string.
        # Later additions of other protocols (like GWG) might have to bring a second
        # code path for proper processing
        packet = bytearray()
        if not KWFollowUp:
            packet.extend(self._int2bytes(self._controlset['StartByte'], 1))
        if self._protocol == 'P300':
            if write:
                packet.extend(self._int2bytes(payloadlength, 1))
            else:
                packet.extend(self._int2bytes(self._controlset['Command_bytes_read'], 1))
            packet.extend(self._int2bytes(self._controlset['Request'], 1))

        if write:
            packet.extend(self._int2bytes(self._controlset['Write'], 1))
        else:
            packet.extend(self._int2bytes(self._controlset['Read'], 1))
        packet.extend(bytes.fromhex(commandcode))
        packet.extend(self._int2bytes(commandvaluebytes, 1))
        if write:
            packet.extend(valuebytes)
        if self._protocol == 'P300':
            packet.extend(self._int2bytes(self._calc_checksum(packet), 1))

        if self._protocol == 'P300':
            responselen = int(self._controlset['Command_bytes_read']) + 4 + (0 if write else int(commandvaluebytes))
        else:
            responselen = 1 if write else int(commandvaluebytes)

        if write:
            self.logger.debug(f'Created command {commandname} to be sent as hexstring: {self._bytes2hexstring(packet)} and as bytes: {packet} with value {value} (transformed to value byte {self._bytes2hexstring(valuebytes)})')
        else:
            self.logger.debug(f'Created command {commandname} to be sent as hexstring: {self._bytes2hexstring(packet)} and as bytes: {packet}')

        return (packet, responselen)

    def _parse_response(self, response, commandname='', read_response=True):
        '''
        Process device response data, try to parse type and value

        :param response: Data received from device
        :type response: bytearray
        :param commandname: Commandname used for request (only needed for KW protocol)
        :type commandname: str
        :param read_response: True if command was read command and value is expected, False if only status byte is expected (only needed for KW protocol)
        :type read_response: bool
        :return: tuple of (parsed response value, commandcode) or None if error
        '''
        if self._protocol == 'P300':

            # A read_response telegram looks like this: ACK (1 byte), startbyte (1 byte), data length in bytes (1 byte), request/response (1 byte), read/write (1 byte), addr (2 byte), amount of valuebytes (1 byte), value (bytes as per last byte), checksum (1 byte)
            # A write_response telegram looks like this: ACK (1 byte), startbyte (1 byte), data length in bytes (1 byte), request/response (1 byte), read/write (1 byte), addr (2 byte), amount of bytes written (1 byte), checksum (1 byte)

            # Validate checksum
            checksum = self._calc_checksum(response[1:len(response) - 1])  # first, cut first byte (ACK) and last byte (checksum) and then calculate checksum
            received_checksum = response[len(response) - 1]
            if received_checksum != checksum:
                self.logger.error(f'Calculated checksum {checksum} does not match received checksum of {received_checksum}! Ignoring reponse')
                return None

            # Extract command/address, valuebytes and valuebytecount out of response
            commandcode = response[5:7].hex()
            responsetypecode = response[3]  # 0x00 = query, 0x01 = reply, 0x03 = error
            responsedatacode = response[4]  # 0x01 = ReadData, 0x02 = WriteData, 0x07 = Function Call
            valuebytecount = response[7]

            # Extract databytes out of response
            rawdatabytes = bytearray()
            rawdatabytes.extend(response[8:8 + (valuebytecount)])
        elif self._protocol == 'KW':

            # imitate P300 response code data for easier combined handling afterwards
            # a read_response telegram consists only of the value bytes
            # a write_response telegram is 0x00 for OK, 0xXX for error
            if commandname == '':
                self.logger.error('trying to parse KW protocol response, but commandname not set in _parse_response. This should not happen...')
                return None

            responsetypecode = 1
            commandcode = self._commandset[commandname]['addr'].lower()
            valuebytecount = len(response)
            rawdatabytes = response

            if read_response:
                # value response to read request, error detection by empty = no response
                responsedatacode = 1
                if len(rawdatabytes) == 0:
                    # error, no answer means wrong address (?)
                    responsetypecode = 3
            else:
                # status response to write request
                responsedatacode = 2
                if (len(rawdatabytes) == 1 and rawdatabytes[0] != 0) or len(rawdatabytes) == 0:
                    # error if status reply is not 0x00
                    responsetypecode = 3

        self.logger.debug(f'Response decoded to: commandcode: {commandcode}, responsedatacode: {responsedatacode}, valuebytecount: {valuebytecount}, responsetypecode: {responsetypecode}')
        self.logger.debug(f'Rawdatabytes formatted: {self._bytes2hexstring(rawdatabytes)} and unformatted: {rawdatabytes}')

        # Process response for items if read response and not error
        if responsedatacode == 1 and responsetypecode != 3:

            # parse response if command config is available
            commandname = self._commandname_by_commandcode(commandcode)
            if commandname is None:
                self.logger.error(f'Received response for unknown address point {commandcode}')
                return None

            # Get command and respective unit config
            commandconf = self._commandset[commandname]
            commandvaluebytes = commandconf['len']
            commandunit = commandconf['unit']
            unitconf = self._unitset.get(commandunit)
            if not unitconf:
                self.logger.error(f'Unit configuration not found for unit {commandunit} in protocol {self._protocol}. This is a configuration error in commands.py, please fix')
                return None
            commandsigned = unitconf['signed']
            valuetransform = unitconf['read_value_transform']

            # start value decode
            if commandunit == 'CT':
                timer = self._decode_timer(rawdatabytes.hex())
                # fill list
                timer = [{'An': on_time, 'Aus': off_time}
                         for on_time, off_time in zip(timer, timer)]
                value = timer
                self.logger.debug(f'Matched command {commandname} and read transformed timer {value} and byte length {commandvaluebytes}')
            elif commandunit == 'TI':
                # decode datetime
                value = datetime.strptime(rawdatabytes.hex(), '%Y%m%d%W%H%M%S').isoformat()
                self.logger.debug(f'Matched command {commandname} and read transformed datetime {value} and byte length {commandvaluebytes}')
            elif commandunit == 'DA':
                # decode date
                value = datetime.strptime(rawdatabytes.hex(), '%Y%m%d%W%H%M%S').date().isoformat()
                self.logger.debug(f'Matched command {commandname} and read transformed datetime {value} and byte length {commandvaluebytes}')
            elif commandunit == 'ES':
                # erstes Byte = Fehlercode; folgenden 8 Byte = Systemzeit
                errorcode = (rawdatabytes[:1]).hex()
                # errorquerytime = (rawdatabytes[1:8]).hex()
                value = self._error_decode(errorcode)
                self.logger.debug(f'Matched command {commandname} and read transformed errorcode {value} (raw value was {errorcode}) and byte length {commandvaluebytes}')
            elif commandunit == 'SC':
                # erstes Byte = Anlagenschema
                systemschemescode = (rawdatabytes[:1]).hex()
                value = self._systemscheme_decode(systemschemescode)
                self.logger.debug(f'Matched command {commandname} and read transformed system scheme {value} (raw value was {systemschemescode}) and byte length {commandvaluebytes}')
            elif commandunit == 'BA':
                operatingmodecode = (rawdatabytes[:1]).hex()
                value = self._operatingmode_decode(operatingmodecode)
                self.logger.debug(f'Matched command {commandname} and read transformed operating mode {value} (raw value was {operatingmodecode}) and byte length {commandvaluebytes}')
            elif commandunit == 'DT':
                # device type has 8 bytes, but first 4 bytes are device type indicator
                devicetypebytes = rawdatabytes[:2].hex()
                value = self._devicetype_decode(devicetypebytes).upper()
                self.logger.debug(f'Matched command {commandname} and read transformed device type {value} (raw value was {devicetypebytes}) and byte length {commandvaluebytes}')
            elif commandunit == 'SN':
                # serial number has 7 bytes,
                serialnumberbytes = rawdatabytes[:7]
                value = self._serialnumber_decode(serialnumberbytes)
                self.logger.debug(f'Matched command {commandname} and read transformed device type {value} (raw value was {serialnumberbytes}) and byte length {commandvaluebytes}')
            elif commandunit == 'HEX':
                # hex string for debugging purposes
                hexstr = rawdatabytes.hex()
                value = ' '.join([hexstr[i:i + 2] for i in range(0, len(hexstr), 2)])
                self.logger.debug(f'Read hex bytes {value}')
            else:
                rawvalue = self._bytes2int(rawdatabytes, commandsigned)
                value = self._value_transform_read(rawvalue, valuetransform)
                self.logger.debug(f'Matched command {commandname} and read transformed value {value} (integer raw value was {rawvalue}) and byte length {commandvaluebytes}')

            # assign to dict for use by other functions
            self._last_values[commandcode] = value

            return (value, commandcode)

        # Handling of write command response if not error
        elif responsedatacode == 2 and responsetypecode != 3:
            self.logger.debug(f'Write request of adress {commandcode} successfull writing {valuebytecount} bytes')
            return True
        else:
            self.logger.error(f'Write request of adress {commandcode} NOT successfull writing {valuebytecount} bytes')
            return None

    def _viess_dict_to_uzsu_dict(self):
        '''
        Convert data read from device to UZSU compatible struct.
        Input is taken from self._viess_timer_dict, output is written to
        self._uzsu_dict
        '''
        dict_timer = {}
        empty_time = '00:00'
        shitems = Items.get_instance()

        try:
            sunset = shitems.return_item('env.location.sunset')().strftime('%H:%M')
            sunrise = shitems.return_item('env.location.sunrise')().strftime('%H:%M')
        except (AttributeError, ValueError):
            sunset = '21:00'
            sunrise = '06:00'

        # convert all switching times with corresponding app and days to timer-dict
        for application in self._viess_timer_dict:
            if application not in dict_timer:
                dict_timer[application] = {}
            for application_day in self._viess_timer_dict[application]:
                timer = self._viess_timer_dict[application][application_day]
                day = application_day[(application_day.rfind('_') + 1):len(application_day)].lower()

                # normalize days
                for element in self._wochentage:
                    if day in self._wochentage[element]:
                        weekday = element

                for entry in timer:
                    for event, sw_time in entry.items():
                        if sw_time != empty_time:
                            value = 1 if event == 'An' else 0
                            if sw_time not in dict_timer[application]:
                                dict_timer[application][sw_time] = {}
                            if value not in dict_timer[application][sw_time]:
                                dict_timer[application][sw_time][value] = []
                            dict_timer[application][sw_time][value].append(weekday)

        self.logger.debug(f'Viessmann timer dict for UZSU: {dict_timer}')

        # find items, read UZSU-dict, convert to list of switching times, update item
        for application in dict_timer:
            item = self._application_timer[application]['item']

            # read UZSU-dict (or use preset if empty)
            uzsu_dict = item()
            if not item():
                uzsu_dict = {'lastvalue': '0', 'sunset': sunset, 'list': [], 'active': True, 'interpolation': {'initage': '', 'initialized': True, 'itemtype': 'bool', 'interval': '', 'type': 'none'}, 'sunrise': sunrise}

            # create empty list
            uzsu_dict['list'] = []

            # fill list with switching times
            for sw_time in sorted(dict_timer[application].keys()):
                for key in dict_timer[application][sw_time]:
                    rrule = 'FREQ=WEEKLY;BYDAY=' + ','.join(dict_timer[application][sw_time][key])
                    uzsu_dict['list'].append({'time': sw_time, 'rrule': rrule, 'value': str(key), 'active': True})

            # update item
            item(uzsu_dict, self.get_shortname())

    def _uzsu_dict_to_viess_timer(self, timer_app, uzsu_dict):
        '''
        Convert UZSU dict from item/visu for selected application into separate
        on/off time events and write all timers to the device

        :param timer_app: Application for which the timer should be written, as in commands.py
        :type timer_app: str
        :param uzsu_dict: UZSU-compatible dict with timer data
        :type uzsu_dict: dict
        '''
        if self._timerread:

            # set variables
            commandnames = set()
            timer_dict = {}
            an = {}
            aus = {}

            # quit if timer_app not defined
            if timer_app not in self._application_timer:
                return

            commandnames.update([self._commandname_by_commandcode(code) for code in self._application_timer[timer_app]['commandcodes']])
            self.logger.debug(f'Commandnames: {commandnames}')

            # find switching times and create lists for on and off operations
            for sw_time in uzsu_dict['list']:
                myDays = sw_time['rrule'].split(';')[1].split('=')[1].split(',')
                for day in myDays:
                    if sw_time['value'] == '1' and sw_time['active']:
                        if day not in an:
                            an[day] = []
                        an[day].append(sw_time['time'])
                for day in myDays:
                    if sw_time['value'] == '0' and sw_time['active']:
                        if day not in aus:
                            aus[day] = []
                        aus[day].append(sw_time['time'])

            # sort daily lists
            for day in an:
                an[day].sort()
            self.logger.debug(f'An: {an}')
            for day in aus:
                aus[day].sort()
            self.logger.debug(f'Aus: {aus}')

            # create timer dict in Viessmann format for all weekdays
            for commandname in commandnames:
                self.logger.debug(f'Commandname in process: {commandname}')
                # create empty dict
                timer_dict[commandname] = [{'An': '00:00', 'Aus': '00:00'}, {'An': '00:00', 'Aus': '00:00'}, {'An': '00:00', 'Aus': '00:00'}, {'An': '00:00', 'Aus': '00:00'}]
                # get current day
                wday = commandname[(commandname.rfind('_') + 1):len(commandname)].lower()
                # normalize day
                for element in self._wochentage:
                    if wday in self._wochentage[element]:
                        wday = element
                # transfer switching times
                for idx, val in enumerate(an[wday]):
                    timer_dict[commandname][idx]['An'] = val
                for idx, val in enumerate(aus[wday]):
                    timer_dict[commandname][idx]['Aus'] = val
            self.logger.debug(f'Timer-dict for update of items: {timer_dict}')

            # write all timer dicts to device
            for commandname in timer_dict:
                value = timer_dict[commandname]
                self.logger.debug(f'Got item value to be written: {value} on command name {commandname}')
                self._send_command(commandname, value)

    def _calc_checksum(self, packet):
        '''
        Calculate checksum for P300 protocol packets

        :parameter packet: Data packet for which to calculate checksum
        :type packet: bytearray
        :return: Calculated checksum
        :rtype: int
        '''
        checksum = 0
        if len(packet) > 0:
            if packet[:1] == b'\x41':
                packet = packet[1:]
                checksum = sum(packet)
                checksum = checksum - int(checksum / 256) * 256
            else:
                self.logger.error('bytes to calculate checksum from not starting with start byte')
        else:
            self.logger.error('No bytes received to calculate checksum')
        return checksum

    def _int2bytes(self, value, length, signed=False):
        '''
        Convert value to bytearray with respect to defined length and sign format.
        Value exceeding limit set by length and sign will be truncated

        :parameter value: Value to convert
        :type value: int
        :parameter length: number of bytes to create
        :type length: int
        :parameter signed: True if result should be a signed int, False for unsigned
        :type signed: bool
        :return: Converted value
        :rtype: bytearray
        '''
        value = value % (2 ** (length * 8))
        return value.to_bytes(length, byteorder='big', signed=signed)

    def _bytes2int(self, rawbytes, signed):
        '''
        Convert bytearray to value with respect to sign format

        :parameter rawbytes: Bytes to convert
        :type value: bytearray
        :parameter signed: True if result should be a signed int, False for unsigned
        :type signed: bool
        :return: Converted value
        :rtype: int
        '''
        return int.from_bytes(rawbytes, byteorder='little', signed=signed)

    def _bytes2hexstring(self, bytesvalue):
        '''
        Create hex-formatted string from bytearray
        :param bytesvalue: Bytes to convert
        :type bytesvalue: bytearray
        :return: Converted hex string
        :rtype: str
        '''
        return ''.join(f'{c:02x}' for c in bytesvalue)

    def _decode_rawvalue(self, rawdatabytes, commandsigned):
        '''
        Convert little-endian byte sequence to int value

        :param rawdatabytes: Bytes to convert
        :type rawdatabytes: bytearray
        :param commandsigned: 'signed' if value should be interpreted as signed
        :type commandsigned: str
        :return: Converted value
        :rtype: int
        '''
        rawvalue = 0
        for i in range(len(rawdatabytes)):
            leftbyte = rawdatabytes[0]
            value = int(leftbyte * pow(256, i))
            rawvalue += value
            rawdatabytes = rawdatabytes[1:]
        # Signed/Unsigned berücksichtigen
        if commandsigned == 'signed' and rawvalue > int(pow(256, i) / 2 - 1):
            rawvalue = (pow(256, i) - rawvalue) * (-1)
        return rawvalue

    def _decode_timer(self, rawdatabytes):
        '''
        Generator to convert byte sequence to a number of time strings hh:mm

        :param rawdatabytes: Bytes to convert
        :type rawdatabytes: bytearray
        '''
        while rawdatabytes:
            hours, minutes = divmod(int(rawdatabytes[:2], 16), 8)
            if minutes >= 6 or hours >= 24:
                # not a valid time
                yield '00:00'
            else:
                yield f'{hours:02d}:{(minutes * 10):02d}'
            rawdatabytes = rawdatabytes[2:]
        return None

    def _encode_timer(self, switching_time):
        '''
        Convert time string to encoded time value for timer application

        :param switching_time: time value in 'hh:mm' format
        :type switching_time: str
        :return: Encoded time value
        :rtype: int
        '''
        if switching_time == '00:00':
            return 0xff
        clocktime = re.compile(r'(\d\d):(\d\d)')
        mo = clocktime.search(switching_time)
        number = int(mo.group(1)) * 8 + int(mo.group(2)) // 10
        return number

    def _value_transform_read(self, value, transform):
        '''
        Transform value according to protocol specification for writing to device

        :param value: Value to transform
        :param transform: Specification for transforming
        :return: Transformed value
        '''
        if transform == 'bool':
            return bool(value)
        elif self._isfloat(transform):
            return round(value / float(transform), 2)
        else:
            return int(value)

    def _value_transform_write(self, value, transform):
        '''
        Transform value according to protocol requirement after reading from device

        :param value: Value to transform
        :type value: int
        :param transform: Specification for transforming
        :type transform: int
        :return: Transformed value
        :rtype: int
        '''
        # as transform and value can be float and by error possibly str, we try to float both
        return int(float(value) * float(transform))

    def _error_decode(self, value):
        '''
        Decode error value from device if defined, else return error as string
        '''
        value = str(value).upper()
        if value in self._errorset:
            errorstring = str(self._errorset[value])
        else:
            errorstring = str(value)
        return errorstring

    def _systemscheme_decode(self, value):
        '''
        Decode schema value from device if possible, else return schema as string
        '''
        if value in self._systemschemes:
            systemscheme = str(self._systemschemes[value])
        else:
            systemscheme = str(value)
        return systemscheme

    def _operatingmode_decode(self, value):
        '''
        Decode operating mode value from device if possible, else return mode as string
        '''
        if value in self._operatingmodes:
            operatingmode = str(self._operatingmodes[value])
        else:
            operatingmode = str(value)
        return operatingmode

    def _devicetype_decode(self, value):
        '''
        Decode device type value if possible, else return device type as string
        '''
        if value in self._devicetypes:
            devicetypes = str(self._devicetypes[value])
        else:
            devicetypes = str(value)
        return devicetypes

    def _serialnumber_decode(self, serialnumberbytes):
        '''
        Decode serial number from device response
        '''
        serialnumber = 0
        serialnumberbytes.reverse()
        for byte in range(0, len(serialnumberbytes)):
            serialnumber += (serialnumberbytes[byte] - 48) * 10 ** byte
        return hex(serialnumber).upper()

    def _commandname_by_commandcode(self, commandcode):
        '''
        Find matching command name from commands.py for given command address

        :param commandcode: address of command
        :type commandcode: str
        :return: name of matching command or None if not found
        '''
        for commandname in self._commandset.keys():
            if self._commandset[commandname]['addr'].lower() == commandcode.lower():
                return commandname
        return None

    def _isfloat(self, value):
        '''
        Test if string is decimal number

        :param value: expression to test
        :type value: str
        :return: True if value can be converted to a float, False otherwise
        '''
        try:
            float(value)
            return True
        except ValueError:
            return False

#
# webinterface
#

    def init_webinterface(self):
        '''
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        '''
        try:
            self.mod_http = Modules.get_instance().get_module('http')  # try/except to handle running in a core version that does not support modules
        except NameError:
            self.mod_http = None
        if self.mod_http is None:
            self.logger.warning('Not initializing the web interface')
            return False

        if 'SmartPluginWebIf' not in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning('Web interface needs SmartHomeNG v1.5 or later. Not initializing the web interface')
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
        self.mod_http.register_webif(WebInterface(webif_dir, self, self._commandset),
                                     self.get_shortname(),
                                     config,
                                     self.get_classname(), self.get_instance_name(),
                                     description='')

        return True


# ------------------------------------------
#    Webinterface of the plugin
# ------------------------------------------

class WebInterface(SmartPluginWebIf):

    def __init__(self, webif_dir, plugin, cmdset):
        '''
        Initialization of instance of class WebInterface

        :param webif_dir: directory where the webinterface of the plugin resides
        :param plugin: instance of the plugin
        :type webif_dir: str
        :type plugin: object
        '''
        self.logger = logging.getLogger(__name__)
        self.webif_dir = webif_dir
        self.plugin = plugin
        self.tplenv = self.init_template_environment()

        self.items = Items.get_instance()

        self.cmdset = cmdset

        self._last_read = {}
        self._last_read['last'] = {'addr': None, 'val': '', 'cmd': ''}

        self._read_addr = None
        self._read_cmd = ''
        self._read_val = ''

    @cherrypy.expose
    def index(self, reload=None):
        '''
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        '''
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)

        return tmpl.render(p=self.plugin,
                           items=sorted(self.items.return_items(), key=lambda k: str.lower(k['_path'])),
                           cmds=self.cmdset,
                           units=sorted(list(self.plugin._unitset.keys())),
                           last_read_addr=self._last_read['last']['addr'],
                           last_read_value=self._last_read['last']['val'],
                           last_read_cmd=self._last_read['last']['cmd']
                           )

    @cherrypy.expose
    def submit(self, button=None, addr=None, length=0, unit=None, clear=False):
        '''
        Submit handler for Ajax
        '''
        if button is not None:

            read_val = self.plugin.read_addr(button)
            if read_val is None:
                self.logger.debug(f'Error trying to read addr {button} submitted by WebIf')
                read_val = 'Fehler beim Lesen'
            else:
                read_cmd = self.plugin._commandname_by_commandcode(button)
                if read_cmd is not None:
                    self._last_read[button] = {'addr': button, 'cmd': read_cmd, 'val': read_val}
                    self._last_read['last'] = self._last_read[button]

        elif addr is not None and unit is not None and length.isnumeric():

            read_val = self.plugin.read_temp_addr(addr, int(length), unit)
            if read_val is None:
                self.logger.debug(f'Error trying to read custom addr {button} submitted by WebIf')
                read_val = 'Fehler beim Lesen'
            else:
                self._last_read[addr] = {'addr': addr, 'cmd': f'custom ({addr})', 'val': read_val}
                self._last_read['last'] = self._last_read[addr]

        elif clear:
            for addr in self._last_read:
                self._last_read[addr]['val'] = ''
            self._last_read['last'] = {'addr': None, 'val': '', 'cmd': ''}

        cherrypy.response.headers['Content-Type'] = 'application/json'
        return json.dumps(self._last_read).encode('utf-8')


# ------------------------------------------
# The following code is for standalone use of the plugin to identify the device
# ------------------------------------------

def get_device_type(v, protocol):

    # try to connect and read device type info from 0x00f8
    print(f'Trying protocol {protocol} on device {serialport}')

    # first, initialize Viessmann object for use
    v.alive = True
    v._protocol = protocol

    # setup protocol controlset
    v._controlset = commands.controlset[protocol]
    res = v._connect()
    if not res:
        logger.info(f'Connection to {serialport} failed. Please check connection.')
        return None

    res = v._init_communication()
    if not res:
        logger.info(f'Could not initialize communication using protocol {protocol}.')
        return False

    # we are connected to the IR head

    # set needed unit
    v._unitset = {
        'DT': {'unit_de': 'DeviceType', 'type': 'list', 'signed': False, 'read_value_transform': 'non'}
    }

    # set needed command. DeviceType command is (hopefully) the same in all devices...
    v._commandset = {
        'DT': {'addr': '00f8', 'len': 2, 'unit': 'DT', 'set': False},
    }

    # we leave this empty so we get the DT code back
    v._devicetypes = {}

    # this is protocol dependent, so easier to let the Class work this out...
    (packet, responselen) = v._build_command_packet('DT')
    if packet is None:
        raise ValueError('No command packet received for address 00f8. This shouldn\'t happen...')

    # send it
    response_packet = v._send_command_packet(packet, responselen)
    if response_packet is None:
        raise ValueError('Error on communicating with the device, no response received. Unknown error.')

    # let it go...
    v._disconnect()

    (val, code) = v._parse_response(response_packet, 'DT')

    if val is not None:
        return val
    else:
        return None


if __name__ == '__main__':

    usage = '''
    Usage:
    ----------------------------------------------------------------------------------

    This plugin is meant to be used inside SmartHomeNG.

    For diagnostic purposes, you can run it as a standalone Python program from the
    command line. It will try to communicate with a connected Viessmann heating system
    and return the device type and the necessary protocol for setting up your plugin
    in SmartHomeNG.

    You need to call this plugin with the serial interface as the first parameter, e.g.

    ./__init__.py /dev/ttyUSB0

    If you call it with -v as a second parameter, you get additional debug information:

    ./__init__.py /dev/ttyUSB0 -v

    '''

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.CRITICAL)
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # create formatter and add it to the handlers
    formatter = logging.Formatter('%(asctime)s - %(message)s  @ %(lineno)d')
    ch.setFormatter(formatter)

    # add the handlers to the logger
    logger.addHandler(ch)

    serialport = ""

    if len(sys.argv) == 2:
        serialport = sys.argv[1]
    elif len(sys.argv) == 3 and sys.argv[2] == '-v':
        serialport = sys.argv[1]
        logger.setLevel(logging.DEBUG)
    else:
        print(usage)
        exit()

    print("This is Viessmann plugin running in standalone mode")
    print("===================================================")

    v = Viessmann(None, standalone=serialport, logger=logger)

    for proto in ('P300', 'KW'):

        res = get_device_type(v, proto)
        if res is None:

            # None means no connection, no further tries
            print(f'Connection could not be established to {serialport}. Please check connection.')
            break

        if res is False:

            # False means no comm init (only P300), go on
            print(f'Communication could not be established using protocol {proto}.')
        else:

            # anything else should be the devices answer, try to decode and quit
            print(f'Device ID is {res}, device type is {commands.devicetypes.get(res, "unknown")} using protocol {proto}')
            # break

    print('Done.')
