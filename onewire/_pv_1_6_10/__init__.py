#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014 Marcus Popp                         marcus@popp.mx
#  Copyright 2019-2020 Bernd Meiners                Bernd.Meiners@mail.de
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

class OneWire(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.6.10'

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
        """

        from bin.smarthome import VERSION
        if '.'.join(VERSION.split('.', 2)[:2]) <= '1.5':
            self.logger = logging.getLogger(__name__)

        self.logger.debug("init {}".format(__name__))
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
        self._button_wait = self.get_parameter_value('button_wait')
        self._cycle = self.get_parameter_value('cycle')
        self.log_counter_cycle_time = self.get_parameter_value('log_counter_cycle_time')
        self._cycle_discovery = self.get_parameter_value('cycle_discovery')
        self.log_counter_cycle_discovery_time = self.get_parameter_value('log_counter_cycle_discovery_time')
        self.log_counter_io_loop_time = self.get_parameter_value('log_counter_io_loop_time')


        # Initialization code goes here
        self._buses = {}                    # buses reported by owserver
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
        # give some info to the user via webinterface
        self.init_webinterface()

        self.logger.debug("init {} done".format(__name__))
        self._init_complete = True


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
            self.logger.debug("Got an error {} while reading the alias definitions".format(e))
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
        self.logger.debug("1-Wire: Starting I/O detection")
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
                    self.logger.debug("IO loop takes {0:.2f} seconds, now waiting for {1} seconds".format(cycletime,self._io_wait))
                if self.log_counter_io_loop_time == 0:
                    if debugLog:
                        self.logger.debug("Logging counter for cycle I/O detection time reached zero and stops now")
            if self.alive:  # only sleep when not stop is in process
                self.stopevent.wait(self._io_wait)
        self.logger.debug("1-Wire: Leaving I/O detection, self.alive is {}".format(self.alive))

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
        warningLog = self.logger.isEnabledFor(logging.WARNING)
        try:
            for addr in self._ios:
                for key in self._ios[addr]:
                    if key.startswith('O'):  # ignore output
                        continue
                    item = self._ios[addr][key]['item']
                    path = self._ios[addr][key]['path']
                    if path is None:
                        if debugLog:
                            self.logger.debug("1-Wire: path not found for {0}".format(item.property.path))
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
                    except ConnectionError as e:
                        raise
                    except Exception as e:
                        if warningLog:
                            self.logger.warning("1-Wire: problem reading {}, error {}".format(addr,e))
                        continue
                    item(value, self.get_shortname(), path)
        except ConnectionError as e:
            if warningLog:
                self.logger.warning("1-Wire: problem reading {}, error {}".format(addr,e))

    """
    The iButton loop is for iButton devices which are often used as extension to a key ring. 
    Per default called every half second which is sufficient for operating the heating.
    """

    def _ibutton_loop(self):
        """
        This is once called after detection of a iButton busmaster and runs endless until plugin stops
        """
        threading.currentThread().name = 'onewire-ibutton'
        self.logger.debug("1-Wire: Starting iButton detection")
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
                self.logger.error("1-Wire: Self not alive".format(bus))
                break
            path = '/uncached/' + bus + '/'
            name = self._ibutton_buses[bus]
            ignore = ['interface', 'simultaneous', 'alarm'] + self._intruders + list(self._ibutton_masters.keys())
            try:
                entries = self.owbase.dir(path)
            except Exception:
                #time.sleep(0.5)
                self.stopevent.wait(0.5)
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
        warningLog = self.logger.isEnabledFor(logging.WARNING)
        if debugLog:
            self.logger.debug("1-Wire: sensor_cycle called")

        if not self._discovered:
            if debugLog:
                self.logger.debug("Discovery not yet finished, skip this sensor read cycle")
            return

        start = time.time()
        for addr in self._sensors:
            if not self.alive:
                if debugLog:
                    self.logger.debug("1-Wire: Self not alive".format(addr))
                break
            for key in self._sensors[addr]:
                item = self._sensors[addr][key]['item']
                path = self._sensors[addr][key]['path']
                if path is None:
                    if debugLog:
                        self.logger.debug("1-Wire: path not found for {0}".format(item.property.path))
                    continue
                try:
                    value = self.owbase.read('/uncached' + path).decode()
                    value = float(value)
                    if key.startswith('T') and value == 85:
                        if self.logger.isEnabledFor(logging.ERROR):
                            self.logger.error("1-Wire: reading {0} gives error value 85.".format(addr))
                        continue
                except Exception as e:
                    if warningLog:
                        self.logger.warning("1-Wire: problem reading {} {}: {}. Trying to continue with next sensor".format(addr, path, e))
                else:  #only if no exception
                    if key == 'L':  # light lux conversion
                        if value > 0:
                            value = round(10 ** ((float(value) / 47) * 1000))
                        else:
                            value = 0
                    elif key == 'VOC':
                        value = value * 310 + 450
                    item(value, self.get_shortname(), path)
                    
        cycletime = time.time() - start
        if self.log_counter_cycle_time > 0 or self.log_counter_cycle_time == -1:
            if debugLog:
                self.logger.debug("1-Wire: sensor cycle takes {0:.2f} seconds for {1} sensors, average is {2:.2f} per sensor".format(cycletime, len(self._sensors),cycletime/len(self._sensors)))
            if self.log_counter_cycle_time > 0:
                self.log_counter_cycle_time -= 1
            if self.log_counter_cycle_time == 0 and debugLog:
                self.logger.debug("Logging counter for sensor cycle time reached zero and stops now")

    def _discovery(self):
        """
        This is called by scheduler just right after starting the plugin.
        The Items have already been parsed here.
        The result of the first query to the top directory listing is saved for the next discovery.
        If the next call takes places it will be checked if there is something changed in top level directory.
        The rest of the discovery will be skipped if now changes are found.
        """
        # speed up logging for time critical sections only
        debugLog = self.logger.isEnabledFor(logging.DEBUG)

        self.logger.debug("1-Wire: discovery called")
        self._intruders = []  # reset intrusion detection
        try:
            listing = self.owbase.dir('/')
        except Exception as e:
            self.logger.error("1-Wire: listing '/' failed with error '{}'".format(e))
            return
        #if debugLog:
        #    self.logger.debug("1-Wire: got listing for '/' = '{}'  self.alive: {}".format(listing,self.alive))
        if type(listing) != list:
            self.logger.warning("1-Wire: listing '{0}' is not a list.".format(listing))
            return
            
        if self._last_discovery == listing:
            self.logger.debug("1-Wire: listing did not change, no need to proceed, exit discovery")
            return

        self.logger.debug("1-Wire: listing changed: '{}'. Save for next discovery cycle".format(listing))
        self._last_discovery = listing

        for path in listing:
            if not self.alive:
                self.logger.warning("1-Wire: self.alive is False")
                break
            # just examine one bus after the next
            if path.startswith('/bus.'):
                bus = path.split("/")[-2]
                if bus not in self._buses:
                    self._buses[bus] = []
                try:
                    # read one single bus directory
                    sensors = self.owbase.dir(path)
                except Exception as e:
                    if debugLog:
                        self.logger.debug("1-Wire: problem reading bus: {0}: {1}".format(bus, e))
                    continue
                for sensor in sensors:
                    # skip subdirectories alarm, interface and simultaneous
                    if any(['alarm' in sensor, 'interface' in sensor, 'simultaneous' in sensor]):
                        if debugLog:
                            self.logger.debug("1-Wire: Skipping reserved words for bus: {0}".format(bus))
                        continue

                    if debugLog:
                        self.logger.debug("1-Wire: Examine Sensor {}".format(sensor))
                    addr = sensor.split("/")[-2]
                    if addr not in self._buses[bus]:
                        keys = self.owbase.identify_sensor(sensor)
                        
                        if keys is None:
                            if debugLog:
                                self.logger.debug("1-Wire: Skipping sensor {0} for bus: {1}".format(sensor, bus))
                            continue
                        self._buses[bus].append(addr)
                        if self.logger.isEnabledFor(logging.INFO):
                            self.logger.info("1-Wire: {0} with sensors: {1}".format(addr, ', '.join(list(keys.keys()))))
                        
                        # depending on the key, decide which dictionary to put in the device data
                        if 'IA' in keys or 'IB' in keys or 'I0' in keys or 'I1' in keys or 'I2' in keys or 'I3' in keys or 'I4' in keys or 'I5' in keys or 'I6' in keys or 'I7' in keys:
                            table = self._ios
                        elif 'BM' in keys:
                            if addr in self._ibutton_masters:
                                self._ibutton_buses[bus] = self._ibutton_masters[addr]
                            continue
                        else:
                            table = self._sensors
                            
                        if addr in table:
                            if debugLog:
                                self.logger.debug("1-Wire: addr {} was found in lookup {}".format(addr,table[addr]))
                            for ch in ['A', 'B']:
                                if 'I' + ch in table[addr] and 'O' + ch in keys:  # set to 0 and delete output PIO
                                    try:
                                        self.owbase.write(sensor + keys['O' + ch], 0)
                                    except Exception as e:
                                        if self.logger.isEnabledFor(logging.INFO):
                                            self.logger.info("1-Wire: problem setting {0}{1} as input: {2}".format(sensor, keys['O' + ch], e))
                                    del(keys['O' + ch])
                            for key in keys:
                                if key in table[addr]:
                                    table[addr][key]['path'] = sensor + keys[key]
                            for ch in ['A', 'B', '0', '1', '2', '3', '4', '5', '6', '7']:  # init PIO
                                if 'O' + ch in table[addr]:
                                    try:
                                        self.owbase.write(table[addr][key]['path'], self._flip[table[addr][key]['item']()])
                                    except Exception as e:
                                        if self.logger.isEnabledFor(logging.INFO):
                                            self.logger.info("1-Wire: problem setting output {0}{1}: {2}".format(sensor, keys['O' + ch], e))
                        else:
                            if debugLog:
                                self.logger.debug("1-Wire: addr {} was not found in lookup {}".format(addr,table))
                    else:
                        if debugLog:
                            self.logger.debug("1-Wire: Sensor {} was already found in bus ".format(sensor,bus))

        else: # for did not end prematurely with break or something else
            self._discovered = True
            self.logger.debug("1-Wire: discovery finished")

        # get a list of all directory entries from owserver
        # self.devices = self.tree()
        # this gets easily of 6.000 lines for just a handful of sensors so better do not use it.
        
        # now decide wether iButton Master is present and if there are iButtons associated with items
        if self._discovered and not self._iButton_Strategy_set:
            self._iButton_Strategy_set = True
            if self._ibuttons != {} and self._ibutton_masters == {}:
                if self.logger.isEnabledFor(logging.INFO):
                    self.logger.info("1-Wire: iButtons specified but no dedicated iButton master. Using I/O cycle for the iButtons.")
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
        # speed up logging for time critical sections only
        debugLog = self.logger.isEnabledFor(logging.DEBUG)
        warningLog = self.logger.isEnabledFor(logging.WARNING)
        errorLog = self.logger.isEnabledFor(logging.ERROR)
        if not self.has_iattr(item.conf, 'ow_addr'):
            return
        if not self.has_iattr(item.conf, 'ow_sensor'):
            if warningLog:
                self.logger.warning("1-Wire: No ow_sensor for {0} defined".format(item.property.path))
            return
            
        addr = self.get_iattr_value(item.conf,'ow_addr')
        key = self.get_iattr_value(item.conf,'ow_sensor')
        if debugLog:
            self.logger.debug("1-Wire: ow_sensor '{1}' with ow_addr '{2}' for item '{0}' defined".format(item.property.path, key, addr))

        # check the compliance with regular sensor address definitions
        while True:
            # when we found the addr to be an alias it is fine, that should work then.
            if self.is_alias(addr):
                if debugLog:
                    self.logger.debug("1-Wire: ow_addr {} is an alias".format(addr))
                break

            # if a check for the addr turns out that it has an alias, we should then use this
            if self.has_alias(addr):
                old_addr = addr
                addr = self.get_alias(old_addr)
                if debugLog:
                    self.logger.debug("1-Wire: ow_addr {} has an alias {}".format(old_addr, addr))
                break

            if len(addr) == 15 and addr[2] == '.':  # matches 3A.1F8107000000
                break

            if warningLog:
                self.logger.warning("While parsing ow_addr found wrong address definition '{}' for item {}".format(addr, item))
            break

        if key in ['IA', 'IB', 'OA', 'OB', 'I0', 'I1', 'I2', 'I3', 'I4', 'I5', 'I6', 'I7', 'O0', 'O1', 'O2', 'O3', 'O4', 'O5', 'O6', 'O7']:
            table = self._ios
        elif key == 'B':
            table = self._ibuttons
        elif key == 'BM':
            self._ibutton_masters[addr] = item.property.path
            return
        else:
            table = self._sensors

        if key not in self._supported:  # unknown key
            path = '/' + addr + '/' + key
            if self.logger.isEnabledFor(logging.INFO):
                self.logger.info("1-Wire: unknown sensor specified for {0} using path: {1}".format(item.property.path, path))
        else:
            path = None
            if key == 'VOC':
                path = '/' + addr + '/VAD'

        if addr in table:
            if debugLog:
                self.logger.debug("set dict[{}][{}] as item:{} and path:{}".format(addr,key, item, path))
            table[addr][key] = {'item': item, 'path': path}
        else:
            if debugLog:
                self.logger.debug("set dict[{}] as key:{} <item:{} and path:{}>".format(addr,key, item, path))
            table[addr] = {key: {'item': item, 'path': path}}
        if key.startswith('O'):
            item._ow_path = table[addr][key]
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        if caller != self.get_shortname():
            try:
                # code to execute, only if the item has not been changed by this plugin:
                self.logger.debug("Update item: {}, item has been changed outside this plugin".format(item.property.path))
                self.owbase.write(item._ow_path['path'], self._flip[item()])
            except Exception as e:
                self.logger.warning("1-Wire: problem setting output {0}: {1}".format(item._ow_path['path'], e))

    def init_webinterface(self):
        """"
        Initialize the web interface for this plugin

        This method is only needed if the plugin is implementing a web interface
        """
        try:
            self.mod_http = Modules.get_instance().get_module(
                'http')  # try/except to handle running in a core version that does not support modules
        except:
            self.mod_http = None
        if self.mod_http == None:
            self.logger.error("Not initializing the web interface")
            return False

        import sys
        if not "SmartPluginWebIf" in list(sys.modules['lib.model.smartplugin'].__dict__):
            self.logger.warning("Web interface needs SmartHomeNG v1.5 and up. Not initializing the web interface")
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
    def index(self, reload=None):
        """
        Build index.html for cherrypy

        Render the template and return the html file to be delivered to the browser

        :return: contents of the template after beeing rendered
        """
        tmpl = self.tplenv.get_template('index.html')
        # add values to be passed to the Jinja2 template eg: tmpl.render(p=self.plugin, interface=interface, ...)
        return tmpl.render(p=self.plugin)


    @cherrypy.expose
    def get_data_html(self, dataSet=None):
        """
        Return data to update the webpage

        For the standard update mechanism of the web interface, the dataSet to return the data for is None

        :param dataSet: Dataset for which the data should be returned (standard: None)
        :return: dict with the data needed to update the web page.
        """
        if dataSet is None:
            # get the new data
            #self.plugin.beodevices.update_devices_info()

            # return it as json the the web page
            #return json.dumps(self.plugin.beodevices.beodeviceinfo)
            pass
        return
