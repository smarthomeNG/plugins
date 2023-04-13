#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014  Marcus Popp                        marcus@popp.mx
#  Copyright 2019-2021  Bernd Meiners               Bernd.Meiners@mail.de
#  Copyright 2023-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  onewire plugin to run with SmartHomeNG
#
#  SmartHomeNG is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  SmartHomeNG is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with SmartHomeNG. If not, see <http://www.gnu.org/licenses/>.
#########################################################################

from lib.module import Modules
from lib.model.smartplugin import *

import threading
from datetime import timedelta

import logging
import time
from . import owbase

from .webif import WebInterface

class OneWire(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.9.4'

    _flip = {0: '1', False: '1', 1: '0', True: '0', '0': True, '1': False}

    _supported = {
        'T': 'Temperature',
        'H': 'Humidity',
        'V': 'Voltage',
        'BM': 'Busmaster',
        'B': 'iButton',
        'L': 'Light/Lux',
        'IA': 'Input A',
        'IB': 'Input B',
        'OA': 'Output A',
        'OB': 'Output B',
        'I0': 'Input 0',
        'I1': 'Input 1',
        'I2': 'Input 2',
        'I3': 'Input 3',
        'I4': 'Input 4',
        'I5': 'Input 5',
        'I6': 'Input 6',
        'I7': 'Input 7',
        'O0': 'Output 0',
        'O1': 'Output 1',
        'O2': 'Output 2',
        'O3': 'Output 3',
        'O4': 'Output 4',
        'O5': 'Output 5',
        'O6': 'Output 6',
        'O7': 'Output 7',
        'T9': 'Temperature 9Bit',
        'T10': 'Temperature 10Bit',
        'T11': 'Temperature 11Bit',
        'T12': 'Temperature 12Bit',
        'VOC': 'VOC'}
    INPUT_TYPES = ['I0', 'I1', 'I2', 'I3', 'I4', 'I5', 'I6', 'I7']
    OUTPUT_TYPES = ['O0', 'O1', 'O2', 'O3', 'O4', 'O5', 'O6', 'O7']
    TEMP_TYPES = ['T9','T10','T11','T12']
    IO_TYPES = ['IA','IB','OA','OB'] + INPUT_TYPES + OUTPUT_TYPES

    def __init__(self, sh, *args, **kwargs ):
        """
        Initalizes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param *args: **Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!
        :param **kwargs:**Deprecated**: Old way of passing parameter values. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        The parameters *args and **kwargs are the old way of passing parameters. They are deprecated. They are imlemented
        to support oder plugins. Plugins for SmartHomeNG v1.4 and beyond should use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name) instead. Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin or MqttPlugin)
        super().__init__()

        # Initialization code goes here

        self.logger.debug(f"init {__name__}")
        self._sh = self.get_sh()

        # better than time.sleep() is to use an event for threading
        self.stopevent = threading.Event()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.host = self.get_parameter_value('host')
        self.port = self.get_parameter_value('port')

        # init the Communication part which is a parent class we inherited from
        self.owbase = owbase.OwBase(self.host, self.port)

        # need to get a list of sensors with an alias
        self.read_alias_definitions()

        self._io_wait = self.get_parameter_value('io_wait')
        self._parasitic_power_wait = self.get_parameter_value('parasitic_power_wait')
        self._button_wait = self.get_parameter_value('button_wait')
        self._cycle = self.get_parameter_value('cycle')
        self.log_counter_cycle_time = self.get_parameter_value('log_counter_cycle_time')
        self._cycle_discovery = self.get_parameter_value('cycle_discovery')
        self.log_counter_cycle_discovery_time = self.get_parameter_value('log_counter_cycle_discovery_time')
        self.log_counter_io_loop_time = self.get_parameter_value('log_counter_io_loop_time')
        self.warn_after = self.get_parameter_value('warn_after')

        # Initialization code goes here
        self._buses = {}                    # buses reported by owserver (each bus entry consists of a list of device addresses
        self._webif_buses = {}              # buses reported by owserver with additional info for web interface
        self._sensors = {}                  # Temperature, Humidity, etc. populated in parse_item
        self._ios = {}                      # IO Sensors
        self._ibuttons = {}                 # iButtons populated in parse_item
        self._ibutton_buses = {}            # found buses
        self._ibutton_masters = {}          # all found iButton Master
        self._intruders = []                # any unknown sensors found
        self._discovered = False            # set to True after first successful scan of attached owdevices
        self._last_discovery = []           # contains the latest results of discovery. If it does not change
                                            # the listing won't be processed again
        self._iButton_Strategy_set = False  # Will be set to True as soon as first discovery is finished and iButtons and iButton Master are known

        """
        self._sensors will contain something like 
        {'28.16971B030000': 
            {'T': 
                {'item': Item: OneWire.Temperature_Multi, 'path': None}}, 
         'Huelsenfuehler': 
            {'T': 
                {'item': Item: OneWire.Temperature_Single, 'path': '/bus.0/Huelsenfuehler/temperature'}},
         '26.E56727010000': 
            {'L': {'item': Item: OneWire.brightness, 'path': None}}, 
         '26.0D9930010000': 
            {'H': {'item': Item: OneWire.humidity, 'path': '/bus.0/26.0D9930010000/HIH4000/humidity'}}}
        """

        self.init_webinterface(WebInterface)
        self.logger.debug(f"init {__name__} done")
        return


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True
        self.scheduler_add('sensor_discovery', self._discovery, prio=5, cycle=self._cycle_discovery, offset=2, next=self.shtime.now()+timedelta(seconds=5))
        self.scheduler_add('sensor_read', self._sensor_cycle, cycle=self._cycle, prio=5, offset=0,next=self.shtime.now()+timedelta(seconds=15))

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.stopevent.set()    # signal to waiting threads that stop is called
        self.logger.debug("Stop method called")
        self.scheduler_remove('sensor_discovery')
        self.scheduler_remove('sensor_read')
        self.scheduler_remove('sensor-io')          # this can be caused by a trigger in _discovery()
        self.owbase.close()

    """
    Owserver keeps a list of alias definitions. The following are utility functions to handle alias names with item definitions.
    This way either a device_id in form of ``28.16971B030000`` or an alias defined with Owserver can be used with attribute ow_addr
    """

    def read_alias_definitions(self):
        """
        Reads the list of alias definitions by owserver
        Returns a list of tuples containing device_id and alias
        """
        self.alias = [] # map an alias to a sensor id
        try:
            aliaslist = self.owbase.read('/settings/alias/list').decode()
            for line in aliaslist.splitlines():
                sensor,alias = line.split('=')
                sensor=sensor[0:2]+'.'+sensor[2:-2]   # set a dot and remove two hex digits from checksum at the end
                self.alias.append((sensor,alias))

        except Exception as e:
            self.logger.debug(f"Got an error '{e}' while reading the alias definitions")
            pass

    def is_alias(self, device_id):
        """
        If device_id given really is an alias as defined by owserver this function returns True
        """
        for entry in self.alias:
            if device_id in entry[1]:
                return True
        else:
            return False

    def has_alias(self, device_id):
        """
        Check if for a device_id given as ``28.16971B030000`` an alias definition exists in owserver.
        """
        for entry in self.alias:
            if device_id in entry[0]:
                return True
        else:
            return False

    def get_alias(self, device_id):
        """
        Returns the corresponding alias for a device_id given as ``28.16971B030000``
        """
        for entry in self.alias:
            if device_id in entry:
                return entry[1]
        else:
            return None


    """
    The io loop is for binary devices like window opening sensors. By default called
    every 5 seconds which is sufficient for operating the heating.
    """

    def _io_loop(self):
        """
        Will be triggered once by scheduler
        This runs endless until the plugin stops
        """
        threading.currentThread().name = 'onewire-io'
        self.logger.debug("Starting I/O detection")
        while self.alive:
            if self.log_counter_io_loop_time == -1 or self.log_counter_io_loop_time > 0:
                start = time.time()
            self._io_cycle()
            if self.log_counter_io_loop_time == -1 or self.log_counter_io_loop_time > 0:
                # speed up logging for time critical sections only
                debugLog = self.logger.isEnabledFor(logging.DEBUG)
                cycletime = time.time() - start
                if self.log_counter_io_loop_time > 0:
                    self.log_counter_io_loop_time -= 1
                if debugLog:
                    self.logger.debug(f"IO loop takes {cycletime:.2f} seconds, now waiting for {self._io_wait} seconds")
                if self.log_counter_io_loop_time == 0:
                    if debugLog:
                        self.logger.debug("Logging counter for cycle I/O detection time reached zero and stops now")
            if self.alive:  # only sleep when not stop is in process
                self.stopevent.wait(self._io_wait)
        self.logger.debug(f"Leaving I/O detection, self.alive is {self.alive}")

    def _io_cycle(self):
        """
        This reads simple IO Sensors
        _ios contains entries like
        {'3A.1F8107000000':
            {'IA':
                {'item': Item: OneWire.input_sensor, 'path': '/bus.0/3A.1F8107000000/sensed.A'} } }

        """
        if not self.alive:
            return
        # speed up logging for time critical sections only
        debugLog = self.logger.isEnabledFor(logging.DEBUG)
        try:
            for addr in self._ios:
                for key in self._ios[addr]:
                    if key.startswith('O'):  # ignore output
                        continue
                    path = self._ios[addr][key]['path']
                    items = self.get_items_for_mapping(addr + '-' + key)
                    if path is None:
                        if debugLog:
                            self.logger.debug(f"_io_cycle: no item path found for mapping '{addr}-{key}'")
                        continue
                    try:
                        # the following can take a while so if in the meantime the plugin should stop we can abort this process here
                        if not self.alive:
                            return
                        if key == 'B':
                            entries = [entry.split("/")[-2] for entry in self.owbase.dir('/uncached')]
                            value = (addr in entries)
                        else:
                            value = self._flip[self.owbase.read('/uncached' + path).decode()]
                        self.stopevent.wait(self._parasitic_power_wait)
                    except ConnectionError as e:
                        self.logger.warning(f"_io_cycle: 'raise' {self._ios[addr][key]['readerrors']}. problem connecting to {addr}-{key}, error: {e}")
                        raise
                    except Exception as e:
                        # time.sleep(self._parasitic_power_wait)
                        #self.stopevent.wait(self._parasitic_power_wait)
                        self._ios[addr][key]['readerrors'] = self._ios[addr][key].get('readerrors', 0) + 1
                        if self._ios[addr][key]['readerrors'] % self.warn_after == 0:
                            self.logger.warning(f"_io_cycle: {self._ios[addr][key]['readerrors']}. problem reading {addr}-{key}, error: {e}")
                        continue
                    if self._ios[addr][key].get('readerrors', 0) >= self.warn_after:
                        self.logger.notice(f"_io_cycle: Success reading '{addr}-{key}' {value=}, up to now there were {self._ios[addr][key]['readerrors']} consecutive problems")
                        self._ios[addr][key]['readerrors'] = 0
                    for item in items:
                        item(value, self.get_shortname(), path)
        except ConnectionError as e:
            self.logger.warning(f"_io_cycle: Problem reading {addr}, connection-error: {e}")

    """
    The iButton loop is for iButton devices which are often used as extension to a key ring. 
    Per default called every half second which is sufficient for operating the heating.
    """

    def _ibutton_loop(self):
        """
        This is once called after detection of a iButton busmaster and runs endless until plugin stops
        """
        threading.currentThread().name = 'onewire-ibutton'
        self.logger.debug("Starting iButton detection")
        while self.alive:
            self._ibutton_cycle()
            self.stopevent.wait(self._button_wait)

    def _ibutton_cycle(self):
        """
        This queries
        """
        found = []
        error = False
        for bus in self._ibutton_buses:
            if not self.alive:
                self.logger.error(f"Self not alive (bus={bus})")
                break
            path = '/uncached/' + bus + '/'
            name = self._ibutton_buses[bus]
            ignore = ['interface', 'simultaneous', 'alarm'] + self._intruders + list(self._ibutton_masters.keys())
            try:
                entries = self.owbase.dir(path)
            except Exception:
                #time.sleep(self._parasitic_power_wait)
                self.stopevent.wait(self._parasitic_power_wait)
                error = True
                continue
            for entry in entries:
                entry = entry.split("/")[-2]
                if entry in self._ibuttons:
                    found.append(entry)
                    self._ibuttons[entry]['B']['item'](True, '1-Wire', source=name)
                elif entry in ignore:
                    pass
                else:
                    self._intruders.append(entry)
                    self.ibutton_hook(entry, name)
        if not error:
            for ibutton in self._ibuttons:
                if ibutton not in found:
                    self._ibuttons[ibutton]['B']['item'](False, '1-Wire')

    def ibutton_hook(self, ibutton, name):
        pass

    # Sensor

    def _sensor_cycle(self):
        """
        This method gets called by scheduler and queries all sensors defined in items
        """
        # speed up logging for time critical sections only
        debugLog = self.logger.isEnabledFor(logging.DEBUG)
        if debugLog:
            self.logger.debug("sensor_cycle called")

        if not self._discovered:
            if debugLog:
                self.logger.debug("Discovery not yet finished, skip this sensor read cycle")
            return

        start = time.time()
        for addr in self._sensors:
            if not self.alive:
                self.logger.debug(f"'self' not alive (sensor={addr})")
                break
            for key in self._sensors[addr]:
                path = self._sensors[addr][key]['path']
                items = self.get_items_for_mapping(addr+'-'+key)
                if path is None:
                    if debugLog:
                        self.logger.debug(f"_sensor_cycle: no item path found for mapping '{addr}-{key}'")
                    continue
                try:
                    value = self.owbase.read('/uncached' + path).decode()
                    self.stopevent.wait(self._parasitic_power_wait)
                    value = float(value)
                    if key.startswith('T') and value == 85:
                        self.logger.error(f"reading {addr} gives error value 85.")
                        continue
                except Exception as e:
                    # time.sleep(self._parasitic_power_wait)
                    #self.stopevent.wait(self._parasitic_power_wait)
                    self._sensors[addr][key]['readerrors'] = self._sensors[addr][key].get('readerrors', 0) + 1
                    if self._sensors[addr][key]['readerrors'] % self.warn_after == 0:
                        self.logger.warning(f"_sensor_cycle: {self._sensors[addr][key]['readerrors']}. problem reading {addr}-{key}, error: {e}")
                else:  #only if no exception
                    if key == 'L':  # light lux conversion
                        if value > 0:
                            value = round(10 ** ((float(value) / 47) * 1000))
                        else:
                            value = 0
                    elif key == 'VOC':
                        value = value * 310 + 450

                    if self._sensors[addr][key].get('readerrors', 0) >= self.warn_after:
                        self.logger.notice(f"_sensor_cycle: Success reading {addr}-{key}, up to now there were {self._sensors[addr][key]['readerrors']} consecutive problems")
                        self._sensors[addr][key]['readerrors'] = 0
                    for item in items:
                        item(value, self.get_shortname(), path)
                    if len(items) == 0:
                        # Sollte NIE passieren, ist dann ein Programmierfehler im Plugin
                        self.logger.error(f"_sensor_cycle: No associated item found for device {addr} / key {key}")

        cycletime = time.time() - start
        if self.log_counter_cycle_time > 0 or self.log_counter_cycle_time == -1:
            if debugLog:
                self.logger.debug(f"sensor cycle takes {cycletime:.2f} seconds for {len(self._sensors)} sensors, average is {cycletime/len(self._sensors):.2f} per sensor")
            if self.log_counter_cycle_time > 0:
                self.log_counter_cycle_time -= 1
            if self.log_counter_cycle_time == 0 and debugLog:
                self.logger.debug("Logging counter for sensor cycle time reached zero and stops now")


    def _discovery_process_bus(self, path):

        bus = path.split("/")[-2]
        self.logger.info(f"- Processing of data for bus {bus} started")
        if bus not in self._buses:
            self._buses[bus] = []
            self._webif_buses[bus] = {}
            self.logger.info(f"- New bus added: {bus}")

        try:
            # read one single bus directory
            sensors = self.owbase.dir(path)
        except Exception as e:
            self.logger.info(f"_discovery_process_bus: Problem reading {bus}, error: {e}")
            return

        self.logger.info(f"- On bus {bus} found sensors: {sensors}")

        for sensor in sensors:
            # skip subdirectories alarm, interface and simultaneous
            if any(['alarm' in sensor, 'interface' in sensor, 'simultaneous' in sensor]):
                self.logger.debug(f"_discovery_process_bus: Skipping reserved word in {sensor} for {bus}")
                continue

            self.logger.debug(f"_discovery_process_bus: Examine Sensor {sensor}")
            addr = sensor.split("/")[-2]
            if addr not in self._buses[bus]:
                try:
                    keys, sensortype = self.owbase.identify_sensor(sensor)
                except Exception as e:
                    self.logger.warning(f"identify_sensor({sensor}) - Exception: {e}")
                self.logger.debug(f"_discovery_process_bus: Sensor {sensor} - keys {keys}")
                if keys is None:
                    if not addr in self._webif_buses[bus]:
                        self.logger.info(f"_discovery_process_bus: Skipping unsupported sensor {sensor} for {bus}")
                        self._webif_buses[bus][addr] = {}
                        self._webif_buses[bus][addr]['keys'] = {'UN': 'unsupported'}
                        self._webif_buses[bus][addr]['devicetype'] = sensortype
                        self._webif_buses[bus][addr]['deviceclass'] = 'unknown'
                    continue
                self._buses[bus].append(addr)
                self._webif_buses[bus][addr] = {}
                self._webif_buses[bus][addr]['keys'] = keys
                self._webif_buses[bus][addr]['devicetype'] = sensortype
                self.logger.info(f"- {addr} with sensors/datatypes: {', '.join(list(keys.keys()))}")

                # depending on the key, decide which dictionary to put in the device data
                if 'IA' in keys or 'IB' in keys or 'I0' in keys or 'I1' in keys or 'I2' in keys or 'I3' in keys or 'I4' in keys or 'I5' in keys or 'I6' in keys or 'I7' in keys:
                    table = self._ios
                    self._webif_buses[bus][addr]['deviceclass'] = 'IO'
                elif 'BM' in keys:
                    if addr in self._ibutton_masters:
                        self._ibutton_buses[bus] = self._ibutton_masters[addr]
                    self._webif_buses[bus][addr]['deviceclass'] = 'iButton master'
                    items = self.get_items_for_mapping(addr + '-' + 'BM')
                    for item in items:
                        config_dict = self.get_item_config(item)
                        config_dict['bus'] = bus
                    continue
                else:
                    table = self._sensors
                    self._webif_buses[bus][addr]['deviceclass'] = 'sensor'

                if addr in table:
                    self.logger.debug(f"_discovery_process_bus: addr {addr} was found in lookup {table[addr]}")
                    for ch in ['A', 'B']:
                        if 'I' + ch in table[addr] and 'O' + ch in keys:  # set to 0 and delete output PIO
                            try:
                                self.owbase.write(sensor + keys['O' + ch], 0)
                            except Exception as e:
                                self.logger.info(f"_discovery_process_bus: problem setting {sensor}{keys['O' + ch]} as input: {e}")
                            del (keys['O' + ch])
                    for key in keys:
                        if key in table[addr]:
                            table[addr][key]['path'] = sensor + keys[key]
                        items = self.get_items_for_mapping(addr + '-' + key)
                        for item in items:
                            config_dict = self.get_item_config(item)
                            config_dict['sensor_key'] = key
                            config_dict['bus'] = bus
                            config_dict['deviceclass'] = self._webif_buses[bus][addr]['deviceclass']
                            config_dict['devicetype'] = self._webif_buses[bus][addr]['devicetype']
                            if key.startswith('T'):
                                config_dict['unit'] = '°C'
                            elif key == 'H':
                                config_dict['unit'] = '%'
                            elif key.startswith('V'):
                                config_dict['unit'] = 'V'
                            else:
                                config_dict['unit'] = ''

                    for ch in ['A', 'B', '0', '1', '2', '3', '4', '5', '6', '7']:  # init PIO
                        if 'O' + ch in table[addr]:
                            try:
                                self.owbase.write(table[addr][key]['path'], self._flip[table[addr][key]['item']()])
                            except Exception as e:
                                self.logger.info(f"_discovery_process_bus: problem setting output {sensor}{keys['O' + ch]}: {e}")
                else:
                    self.logger.debug(f"_discovery_process_bus: addr {addr} was not found in lookup {table}")
            else:
                self.logger.debug(f"_discovery_process_bus: Sensor {sensor} was already found in bus {bus}")

        self.logger.info(f"- Processing of data for bus {bus} finished")
        return

    def _discovery(self):
        """
        This is called by scheduler just right after starting the plugin.
        The Items have already been parsed here.
        The result of the first query to the top directory listing is saved for the next discovery.
        If the next call takes places it will be checked if there is something changed in top level directory.
        The rest of the discovery will be skipped if now changes are found.
        """
        self.logger.info("discovery started")
        self._intruders = []  # reset intrusion detection
        try:
            listing = self.owbase.dir('/')
        except Exception as e:
            self.logger.error(f"_discovery: listing '/' failed with error '{e}'")
            return
        self.logger.info(f"_discovery: got listing for '/' = '{listing}'  self.alive: {self.alive}")
        if type(listing) != list:
            self.logger.warning(f"_discovery: listing '{listing}' is not a list.")
            return

        if self._last_discovery == sorted(listing):
            self.logger.debug("listing did not change, no need to proceed, exit discovery")
            return

        self.logger.debug(f"listing changed: '{listing}'. Save for next discovery cycle")
        self._last_discovery = sorted(listing)

        for path in listing:
            if not self.alive:
                self.logger.warning("self.alive is False")
                break

            # just examine one bus after the next
            if path.startswith('/bus.'):
                self._discovery_process_bus(path)

        else: # for did not end prematurely with break or something else
            self._discovered = True
            self.logger.info("discovery finished")

        # get a list of all directory entries from owserver
        # self.devices = self.tree()
        # this gets easily of 6.000 lines for just a handful of sensors so better do not use it.

        # now decide wether iButton Master is present and if there are iButtons associated with items
        if self._discovered and not self._iButton_Strategy_set:
            self._iButton_Strategy_set = True
            if self._ibuttons != {} and self._ibutton_masters == {}:
                if self.logger.isEnabledFor(logging.INFO):
                    self.logger.info("iButtons specified but no dedicated iButton master. Using I/O cycle for the iButtons.")
                for addr in self._ibuttons:
                    for key in self._ibuttons[addr]:
                        if key == 'B':
                            if addr in self._ios:
                                self._ios[addr][key] = {'item': self._ibuttons[addr][key]['item'], 'path': '/' + addr}
                            else:
                                self._ios[addr] = {key: {'item': self._ibuttons[addr][key]['item'], 'path': '/' + addr}}
                self._ibuttons = {}
            if self._ibutton_masters == {} and self._ios == {}:
                return
            elif self._ibutton_masters != {} and self._ios != {}:
                self.scheduler_trigger('sensor-io', self._io_loop, '1w', prio=5)
                self._ibutton_loop()
            elif self._ios != {}:
                self._io_loop()
            elif self._ibutton_masters != {}:
                self._ibutton_loop()

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        """
        config_data = {}
        config_data['bus'] = ''
        config_data['unit'] = ''
        if not self.has_iattr(item.conf, 'ow_addr'):
            return
        if not self.has_iattr(item.conf, 'ow_sensor'):
            self.logger.warning(f"parse_item: No ow_sensor for {item.id()} defined")
            return

        addr = self.get_iattr_value(item.conf,'ow_addr')
        key = self.get_iattr_value(item.conf,'ow_sensor')
        config_data['sensor_addr'] = addr
        config_data['sensor_key'] = key
        self.logger.debug(f"parse_item: ow_sensor '{key}' with ow_addr '{addr}' for item '{item.id()}' defined")

        # check the compliance with regular sensor address definitions
        while True:
            # when we found the addr to be an alias it is fine, that should work then.
            if self.is_alias(addr):
                self.logger.debug(f"ow_addr {addr} is an alias")
                break

            # if a check for the addr turns out that it has an alias, we should then use this
            if self.has_alias(addr):
                old_addr = addr
                addr = self.get_alias(old_addr)
                self.logger.debug(f"ow_addr {old_addr} has an alias {addr}")
                break

            if len(addr) == 15 and addr[2] == '.':  # matches 3A.1F8107000000
                break

            self.logger.warning(f"parse_item: found wrong address definition '{addr}' for item {item} while parsing ow_addr")
            break

        if key in ['IA', 'IB', 'OA', 'OB', 'I0', 'I1', 'I2', 'I3', 'I4', 'I5', 'I6', 'I7', 'O0', 'O1', 'O2', 'O3', 'O4', 'O5', 'O6', 'O7']:
            table = self._ios
            config_data['deviceclass'] = 'IO'
        elif key == 'B':
            table = self._ibuttons
            config_data['deviceclass'] = 'iButton'
        elif key == 'BM':
            self._ibutton_masters[addr] = item.id()
            config_data['deviceclass'] = 'iButton master'
            self.add_item(item, mapping=addr+'-'+key, config_data_dict=config_data)
            return
        else:
            table = self._sensors
            config_data['deviceclass'] = 'sensor'

        if key not in self._supported:  # unknown key
            path = '/' + addr + '/' + key
            self.logger.info(f"parse_item: unknown sensor specified for {item.id()} using path: {path}")
        else:
            path = None
            if key == 'VOC':
                path = '/' + addr + '/VAD'

        if addr in table:
            self.logger.debug(f"parse_item: set dict[{addr}][{key}] as item:{item} and path:{path}")
            table[addr][key] = {'item': item, 'path': path}
        else:
            self.logger.debug(f"parse_item: set dict[{addr}] as key:{key} <item:{item} and path:{path}>")
            table[addr] = {key: {'item': item, 'path': path}}
        if key.startswith('O'):
            item._ow_path = table[addr][key]
            self.add_item(item, mapping=addr+'-'+key, config_data_dict=config_data)
            return self.update_item

        self.add_item(item, mapping=addr+'-'+key, config_data_dict=config_data)
        return

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != self.get_shortname():
            try:
                # code to execute, only if the item has not been changed by this plugin:
                self.logger.debug(f"update_item: update item: {item.id()}, item has been changed outside this plugin")
                self.owbase.write(item._ow_path['path'], self._flip[item()])
            except Exception as e:
                self.logger.warning(f"update_item: problem setting output {item._ow_path['path']}: {e}")


    def count_items_for_device(self, addr):
        """
        Count items that are associated with a device
        if counts
        - items using different sensors for the device
        - items using the same sensor (for having the senor data in multiple items)

        :param addr: 1-wire device address
        :type addr: str

        :return: dnumber of items
        :rtype: int
        """
        device_list = self.get_mappings()
        count = 0
        for device in device_list:
            if device.startswith(addr):
                count += 1
        return count
