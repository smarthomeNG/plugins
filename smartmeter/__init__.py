#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2012-2014 Oliver Hinckel                  github@ollisnet.de
#  Copyright 2018-2024 Bernd Meiners                Bernd.Meiners@mail.de
#  Copyright 2022- Michael Wenzel                   wenzel_michael@web.de
#  Copyright 2024- Sebastian Helms               morg @ knx-user-forum.de
#########################################################################
#
#  This file is part of SmartHomeNG.    https://github.com/smarthomeNG//
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
#########################################################################

__license__ = 'GPL'
__version__ = '2.0'
__revision__ = '0.1'
__docformat__ = 'reStructuredText'

import asyncio
import os
import threading
import time
import sys

# find out if we can import serial - if not, the plugin might not start anyway
# serial is not needed in the plugin itself, but in the modules SML and DLMS,
# which will import the serial module by themselves, if serial is configured
try:
    import serial  # noqa
    REQUIRED_PACKAGE_IMPORTED = True
except Exception:
    REQUIRED_PACKAGE_IMPORTED = False

from lib.model.smartplugin import SmartPlugin
from lib.item.item import Item
from lib.shtime import Shtime
from lib.shyaml import yaml_save
from collections.abc import Callable
from typing import (Union, Any)

from . import dlms  # noqa
from . import sml  # noqa
from .conversion import Conversion
from .webif import WebInterface

shtime = Shtime.get_instance()

# item attributes handled by this plugin
OBIS_CODE = 'obis_code'          # single code, '1-1:1.8.0' or '1.8.0'
OBIS_INDEX = 'obis_index'        # optional: index of obis value, default 0
OBIS_PROPERTY = 'obis_property'  # optional: property to read ('value', 'unit', ...) default 'value''
OBIS_VTYPE = 'obis_vtype'        # optional: type of value (str, num, int, float, ZST12, ZST10, D6, Z6, Z4, '') default ''
OBIS_READOUT = 'obis_readout'    # complete readout (dlms only)

ITEM_ATTRS = (OBIS_CODE, OBIS_INDEX, OBIS_PROPERTY, OBIS_VTYPE, OBIS_READOUT)

# obis properties
PROPS = [
    'value', 'unit', 'name', 'valueRaw', 'scaler', 'status', 'valTime', 'actTime', 'signature', 'unitCode',
    'statRun', 'statFraudMagnet', 'statFraudCover', 'statEnergyTotal', 'statEnergyL1', 'statEnergyL2', 'statEnergyL3',
    'statRotaryField', 'statBackstop', 'statCalFault', 'statVoltageL1', 'statVoltageL2', 'statVoltageL3', 'obis'
]

# mapping separator. set to something not probable to be in obis, index or prop
SEP = '-#-'


class Smartmeter(SmartPlugin, Conversion):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '0.9.0'

    def __init__(self, sh):
        """
        Initializes the plugin. The parameters described for this method are pulled from the entry in plugin.conf.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.connected = False
        self._autoreconnect = self.get_parameter_value('autoreconnect')
        self.alive = False
        self._lock = threading.Lock()

        # store "wanted" obis codes
        self.obis_codes = []

        # store last response(s)
        self.obis_results = {}

        # set or discovered protocol (SML/DLMS)
        self.protocol = None

        # protocol auto-detected?
        self.proto_detected = False

        self.use_asyncio = False

        # update items only every x seconds
        self.timefilter = -1
        self._last_item_update = -1

        # load parameters from config
        self._load_parameters()

        # quit if errors on parameter read
        if not self._init_complete:
            return

        self.init_webinterface(WebInterface)

    def discover(self, protocol=None) -> bool:
        """
        try to identify protocol of smartmeter

        if protocol is given, only test this protocol
        otherwise, test DLMS and SML
        """
        if not protocol:
            disc_protos = ['DLMS', 'SML']
        else:
            disc_protos = [protocol]

        for proto in disc_protos:
            if self._get_module(proto).discover(self._config):
                self.logger.info(f'discovery of {protocol} was successful')
                self.protocol = proto
                if len(disc_protos) > 1:
                    self.proto_detected = True
                return True
            else:
                self.logger.info(f'discovery of {protocol} was unsuccessful')

        return False

    def query(self, assign_values: bool = True, protocol=None) -> dict:
        """
        query smartmeter resp. listen for data

        if protocol is given, try to use the given protocol
        otherwise, use self._protocol as default

        if assign_values is set, assign received values to items
        if assign_values is not set, just return the results
        """
        if not protocol:
            protocol = self.protocol
        ref = self._get_module(protocol)
        if not ref:
            self.logger.error(f'could not get module for protocol {protocol}, aborting.')
            return {}

        result = {}
        try:
            result = ref.query(self._config)
            if not result:
                self.logger.warning('no results from smartmeter query received')
            else:
                self.logger.debug(f'got result: {result}')
                if assign_values:
                    self._update_values(result)
        except Exception as e:
            self.logger.error(f'error: {e}', exc_info=True)

        return result

    def create_items(self, data: dict = {}, file: str = '') -> bool:
        """ 
        create itemdefinitions from read obis numbers

        dict should be the result dict, or (if empty) self.obis_results will be used
        file is the filename to write. default is:
        <items_dir>/smartmeter-<meter id>.yaml

        return indicates success or error
        """
        if not data:
            data = self.obis_results
        if not data:
            return False

        try:
            id = data['1-0:96.1.0*255'][0]['value']
        except (KeyError, IndexError, AttributeError):
            try:
                id = data['1-0:0.0.9*255'][0]['value']
            except (KeyError, IndexError, AttributeError):
                id = int(time.time())

        if not file:
            dir = self._sh._items_dir
            file = os.path.join(dir, f'smartmeter-{id}.yaml')

        if os.path.exists(file):
            self.logger.warning(f'output file {file} exists, not overwriting.')
            return False

        result = {}
        for nr, code in enumerate(data):
            item = f'item_{nr}'
            if len(data[code]) == 0:
                continue
            d = data[code][0]
            name = d.get('name', '')
            unit = d.get('unit')
            if isinstance(d['value'], str):
                typ = 'str'
            elif type(d['value']) in (int, float):
                typ = 'num'
            else:
                typ = 'foo'

            result[item] = {
                'type': typ,
                'cache': True,
                'remark': name,
                'obis_code': code,
            }

            if unit:
                result[item]['unit'] = {
                    'type': 'str',
                    'cache': True,
                    'obis_code': '..:.',
                    'obis_property': 'unit'
                }

        try:
            yaml_save(file, {id: result})
        except Exception as e:
            self.logger.warning(f'saving item file {file} failed with error: {e}')
            return False

        return True

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug('run method called')

        # TODO: reload parameters - why?
        self._load_parameters()

        if not self.protocol:
            self.discover()

        self.alive = True
        if self.protocol:
            self.logger.info(f'{"detected" if self.proto_detected else "set"} protocol {self.protocol}')
        else:
            # skip cycle / crontab scheduler if no protocol set (only manual control from web interface)
            self.logger.error('unable to auto-detect device protocol (SML/DLMS). Try manual disconvery via standalone mode or Web Interface.')
            return

        # Setup scheduler for device poll loop, if protocol set
        if self.use_asyncio:
            self.start_asyncio(self.plugin_coro())
        else:
            if (self.cycle or self.crontab) and self.protocol:
                if self.crontab:
                    next = None  # adhere to the crontab
                else:
                    # no crontab given so we might just query immediately
                    next = shtime.now()
                self.scheduler_add(self.get_fullname(), self.poll_device, prio=5, cycle=self.cycle, cron=self.crontab, next=next)
        self.logger.debug('run method finished')

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug('stop method called')
        self.alive = False
        if self.use_asyncio:
            self.stop_asyncio()
        else:
            try:
                self.scheduler_remove(self.get_fullname())
            except Exception:
                pass

    def _load_parameters(self):

        #
        # connection configuration
        #
        self._config = {}

        # not really a config value, but easier than having another parameter everywhere
        self._config['lock'] = self._lock

        # first try connections; abort loading plugin if no connection is configured
        self._config['serial_port'] = self.get_parameter_value('serialport')
        if self._config['serial_port'] and not REQUIRED_PACKAGE_IMPORTED:
            self.logger.error('serial port requested but package "pyserial" could not be imported.')
            self._init_complete = False
            return

        # serial has priority, as DLMS only uses serial
        if self._config['serial_port']:
            self._config['connection'] = 'serial'
        else:
            host = self.get_parameter_value('host')
            port = self.get_parameter_value('port')
            if host and port:
                self._config['host'] = host
                self._config['port'] = port
                self._config['connection'] = 'network'
            else:
                self.logger.error('neither serial nor network connection configured.')
                self._init_complete = False
                return

        # there is a possibility of using a named device
        # normally this will be empty since only one meter will be attached
        # to one serial interface but the standard allows for it and we honor that.
        self._config['timeout'] = self.get_parameter_value('timeout')
        self._config['baudrate'] = self.get_parameter_value('baudrate')

        # get mode (SML/DLMS) if set by user
        # if not set, try to get at runtime
        if not self.protocol:
            self.protocol = self.get_parameter_value('protocol').upper()

        # DLMS only
        self._config['dlms'] = {}
        self._config['dlms']['device'] = self.get_parameter_value('device_address')
        self._config['dlms']['querycode'] = self.get_parameter_value('querycode')
        self._config['dlms']['baudrate_min'] = self.get_parameter_value('baudrate_min')
        self._config['dlms']['use_checksum'] = self.get_parameter_value('use_checksum')
        self._config['dlms']['only_listen'] = self.get_parameter_value('only_listen')
        self._config['dlms']['normalize'] = self.get_parameter_value('normalize')

        # SML only
        self._config['sml'] = {}
        self._config['sml']['buffersize'] = self.get_parameter_value('buffersize')            # 1024
        self._config['sml']['device'] = self.get_parameter_value('device_type')
        self._config['sml']['date_offset'] = self.get_parameter_value('date_offset')          # 0

        #
        # general plugin parameters
        #
        self.cycle = self.get_parameter_value('cycle')
        if self.cycle == 0:
            self.cycle = None

        self.crontab = self.get_parameter_value('crontab')  # the more complex way to specify the device query frequency
        if self.crontab == '':
            self.crontab = None

        self._config['poll'] = True
        poll = self.get_parameter_value('poll')
        if not poll:
            self.use_asyncio = True
            self._config['poll'] = False

        if self.use_asyncio:
            self.timefilter = self.get_parameter_value('time_filter')
            if self.timefilter == -1 and self.cycle is not None:
                self.timefilter = self.cycle
            if self.timefilter < 0:
                self.timefilter = 0
        self._config['timefilter'] = self.timefilter

        if not self.use_asyncio and not (self.cycle or self.crontab):
            self.logger.warning(f'{self.get_fullname()}: no update cycle or crontab set. The smartmeter will not be queried automatically')

    def _get_module(self, protocol=None):
        """ return module reference for SML/DMLS module """
        if not protocol:
            protocol = self.protocol
        name = __name__ + '.' + str(protocol).lower()
        ref = sys.modules.get(name)
        if not ref:
            self.logger.warning(f"couldn't get reference for module {name}...")
        return ref

    def _to_mapping(self, obis: str, index: Any) -> str:
        return f'{obis}{SEP}{index}'

    def parse_item(self, item: Item) -> Union[Callable, None]:
        """
        Default plugin parse_item method. Is called when the plugin is initialized.

        :param item:    The item to process.
        :return:        returns update_item function if changes are to be watched
        """
        if self.has_iattr(item.conf, OBIS_CODE):
            obis = self.get_iattr_value(item.conf, OBIS_CODE)
            prop = self.get_iattr_value(item.conf, OBIS_PROPERTY, default='value')
            if prop not in PROPS:
                self.logger.warning(f'item {item}: invalid property {prop} requested for obis {obis}, setting default "value"')
                prop = 'value'
            vtype = self.get_iattr_value(item.conf, OBIS_VTYPE, default='')
            if vtype:
                if prop.startswith('value'):
                    if vtype in ('int', 'num', 'float', 'str') and vtype != item.type():
                        self.logger.warning(f'item {item}: item type is {item.type()}, but obis_vtype is "{vtype}", please fix item definition')
                        vtype = None
                else:
                    self.logger.warning(f'item {item} has obis_vtype set, which is only valid for "value" property, not "{prop}", ignoring.')
                    vtype = None
            index = self.get_iattr_value(item.conf, OBIS_INDEX, default=0)

            self.add_item(item, {'property': prop, 'index': index, 'vtype': vtype}, self._to_mapping(obis, index))
            self.obis_codes.append(obis)
            self.logger.debug(f'Attach {item.property.path} with obis={obis}, prop={prop} and index={index}')

        if self.has_iattr(item.conf, OBIS_READOUT):
            self.add_item(item, mapping='readout')
            self.logger.debug(f'Attach {item.property.path} for readout')

    def _is_obis_code_wanted(self, code: str) -> bool:
        """
        this stub function detects whether code is in the list of user defined OBIS codes to scan for
        """
        return code in self.obis_codes

    def poll_device(self):
        """
        This function just calls the 'query device' method of the
        respective module
        """
        self.query()

    def _update_values(self, result: dict):
        """
        this function takes the OBIS Code as text and accepts a list of dictionaries with Values
        :param Code: OBIS Code
        :param Values: list of dictionaries with Value / Unit entries
        """
        # self.logger.debug(f'running _update_values with {result}')
        self.obis_results.update(result)

        # if "update items only every x seconds" is set:
        if self.timefilter > 0 and self._last_item_update + self.timefilter > time.time():
            self.logger.debug(f'timefilter active, {int(self._last_item_update + self.timefilter - time.time())} seconds remaining')
            return

        if 'readout' in result:
            for item in self.get_items_for_mapping('readout'):
                item(result['readout'], self.get_fullname())
                self.logger.debug(f'set item {item} to readout {result["readout"]}')
            del result['readout']

        update = -1
        # check all obis codes
        for obis, vlist in result.items():
            if not self._is_obis_code_wanted(obis):
                continue
            for idx, vdict in enumerate(vlist):
                for item in self.get_items_for_mapping(self._to_mapping(obis, idx)):
                    conf = self.get_item_config(item)
                    # self.logger.debug(f'processing item {item} with {conf} for index {idx}...')
                    if conf.get('index', 0) == idx:
                        prop = conf.get('property', 'value')
                        val = None
                        try:
                            val = vdict[prop]
                        except KeyError:
                            self.logger.warning(f'item {item} wants property {prop} which has not been recceived')
                            continue

                        # skip processing if val is None, save cpu cycles
                        if val is not None:
                            try:
                                converter = conf['vtype']
                                itemValue = self._convert_value(val, converter)
                                # self.logger.debug(f'conversion yielded {itemValue} from {val} for converter "{converter}"')
                                item(itemValue, self.get_fullname())
                                if update < 0:
                                    update = time.time()
                                self.logger.debug(f'set item {item} for obis code {obis}:{prop} to value {itemValue}')
                            except ValueError as e:
                                self.logger.error(f'error while converting value {val} for item {item}, obis code {obis}: {e}')
                        else:
                            self.logger.debug(f'for item {item} and obis code {obis}:{prop} no content was received')
        if update > 0:
            self._last_item_update = update

    async def plugin_coro(self):
        """
        Coroutine for the session that starts the serial connection and listens
        """
        self.logger.info("plugin_coro started")
        try:
            self.reader = self._get_module().AsyncReader(self.logger, self, self._config)
        except ImportError as e:
            # serial_asyncio not loaded/present
            self.logger.error(e)
            return

        # start listener and queue listener in parallel
        await asyncio.gather(self.reader.stop_on_queue(), self._run_listener())

        # reader quit, exit loop
        self.alive = False
        self.logger.info("plugin_coro finished")

    async def _run_listener(self):
        """ call async listener and restart if requested """
        while self.alive:
            # reader created, run reader
            try:
                await self.reader.listen()
            except Exception as e:
                self.logger.warning(f'while running listener, the following error occured: {e}')

            if not self._autoreconnect:
                self.logger.debug('listener quit, autoreconnect not set, exiting')
                break

            self.logger.debug('listener quit, autoreconnecting after 2 seconds...')
            await asyncio.sleep(2)

    @property
    def item_list(self):
        return self.get_item_list()

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()
