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

from inspect import Attribute
import threading
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
from collections.abc import Callable
from typing import (Union, Any)

from . import dlms
from . import sml
from .conversion import Conversion
try:
    from .webif import WebInterface
except ImportError:
    pass

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

    PLUGIN_VERSION = '0.0.1'

    def __init__(self, sh):
        """
        Initializes the plugin. The parameters described for this method are pulled from the entry in plugin.conf.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # load parameters from config
        self._protocol = None
        self._proto_detect = False
        self.load_parameters()

        # quit if errors on parameter read
        if not self._init_complete:
            return

        self.connected = False
        self.alive = False

        self._items = {}            # all items by obis code by obis prop
        self._readout_items = []    # all readout items
        self.obis_codes = []

        self._lock = threading.Lock()

        # self.init_webinterface(WebInterface)

    def load_parameters(self):

        #
        # connection configuration
        #
        self._config = {}

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
        self._protocol = self.get_parameter_value('protocol').upper()

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

        if not (self.cycle or self.crontab):
            self.logger.warning(f'{self.get_fullname()}: no update cycle or crontab set. The smartmeter will not be queried automatically')

    def _get_module(self):
        """ return module reference for SML/DMLS module """
        name = __name__ + '.' + str(self._protocol).lower()
        ref = sys.modules.get(name)
        if not ref:
            self.logger.warning(f"couldn't get reference for module {name}...")
        return ref

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug('run method called')

        # TODO: reload parameters - why?
        self.load_parameters()

        if not self._protocol:
            # TODO: call DLMS/SML discovery routines to find protocol
            if sml.discover(self._config):
                self._protocol = 'SML'
                self._proto_detect = True
            elif dlms.discover(self._config):
                self._protocol = 'DLMS'
                self._proto_detect = True

        self.alive = True
        if self._protocol:
            self.logger.info(f'{"detected" if self._proto_detect else "set"} protocol {self._protocol}')
        else:
            self.logger.error('unable to auto-detect device protocol (SML/DLMS). Try manual disconvery via standalone mode or Web Interface.')
            # skip cycle / crontab scheduler if no protocol set (only manual control from web interface)
            return

        # Setup scheduler for device poll loop, if protocol set
        if (self.cycle or self.crontab) and self._protocol:
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
        try:
            self.scheduler_remove(self.get_fullname())
        except Exception:
            pass

    def to_mapping(self, obis: str, index: Any) -> str:
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

            self.add_item(item, {'property': prop, 'index': index, 'vtype': vtype}, self.to_mapping(obis, index))
            self.obis_codes.append(obis)
            self.logger.debug(f'Attach {item.property.path} with obis={obis}, prop={prop} and index={index}')

        if self.has_iattr(item.conf, OBIS_READOUT):
            self.add_item(item)
            self._readout_items.append(item)
            self.logger.debug(f'Attach {item.property.path} for readout')

    def _is_obis_code_wanted(self, code: str) -> bool:
        """
        this stub function detects whether code is in the list of user defined OBIS codes to scan for
        """
        return code in self.obis_codes

    def poll_device(self):
        """
        This function aquires a lock, calls the 'query device' method of the
        respective module and upon successful data readout it calls the update function
        If it is not possible it passes on, issuing a warning about increasing the query interval
        """
        self.logger.debug(f'poll_device called, module is {self._get_module()}')
        if not self._get_module():
            return

        if self._lock.acquire(blocking=False):
            self.logger.debug('lock acquired')
            try:
                result = self._get_module().query(self._config)
                if not result:
                    self.logger.warning('no results from smartmeter query received')
                else:
                    self.logger.debug(f'got result: {result}')
                    self._update_values(result)
            except Exception as e:
                self.logger.error(f'error: {e}', exc_info=True)
            finally:
                self._lock.release()
                self.logger.debug('lock released')
        else:
            self.logger.warning('device query is alrady running. Check connection and/or use longer query interval time.')

    def _update_values(self, result: dict):
        """
        this function takes the OBIS Code as text and accepts a list of dictionaries with Values
        :param Code: OBIS Code
        :param Values: list of dictionaries with Value / Unit entries
        """
        # self.logger.debug(f'running _update_values with {result}')
        if 'readout' in result:
            for item in self._readout_items:
                item(result['readout'], self.get_fullname())
                self.logger.debug(f'set item {item} to readout {result["readout"]}')
            del result['readout']

        # check all obis codes
        for obis, vlist in result.items():
            if not self._is_obis_code_wanted(obis):
                continue
            for idx, vdict in enumerate(vlist):
                for item in self.get_items_for_mapping(self.to_mapping(obis, idx)):
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
                                self.logger.debug(f'set item {item} for obis code {obis}:{prop} to value {itemValue}')
                            except ValueError as e:
                                self.logger.error(f'error while converting value {val} for item {item}, obis code {obis}: {e}')
                        else:
                            self.logger.debug(f'for item {item} and obis code {obis}:{prop} no content was received')

    @property
    def item_list(self):
        return self.get_item_list()

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()
