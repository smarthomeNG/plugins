#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-      Michael Wenzel              wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
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

import datetime
import hashlib
import logging
import socket
import threading
import time
import functools

from abc import ABC
from enum import IntFlag
from json.decoder import JSONDecodeError
from typing import Dict
from typing import Union
from xml.etree import ElementTree
import lxml.etree as ET
import requests
from requests.packages import urllib3

from lib.model.smartplugin import SmartPlugin
from .webif import WebInterface
from .item_attributes import \
    ALL_ATTRIBUTES_SUPPORTED_BY_REPEATER, ALL_ATTRIBUTES_WRITEABLE, AHA_ATTRIBUTES, \
    TR064_ATTRIBUTES, CALL_MONITOR_ATTRIBUTES, CALL_MONITOR_ATTRIBUTES_TRIGGER, \
    CALL_MONITOR_ATTRIBUTES_GEN, CALL_MONITOR_ATTRIBUTES_IN, CALL_MONITOR_ATTRIBUTES_OUT, \
    CALL_MONITOR_ATTRIBUTES_DURATION, TAM_ATTRIBUTES, WLAN_CONFIG_ATTRIBUTES, \
    HOST_ATTRIBUTES_CHILD, DEFLECTION_ATTRIBUTES, ALL_ATTRIBUTES_WRITEONLY


def NoAttributeError(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except AttributeError:
            pass
    return wrapper


def NoKeyOrAttributeError(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (KeyError, AttributeError):
            pass
    return wrapper


def to_str(arg) -> str:
    if arg is not None:
        return str(arg)
    else:
        return ''


def to_int(arg) -> int:
    try:
        return int(arg)
    except (ValueError, TypeError):
        return 0


def walk_nodes(root, nodes: list):
    data = root
    for atype, arg in nodes:
        if atype == 'attr':
            data = getattr(data, arg)
        elif atype == 'sub':
            data = data[arg]
        elif atype == 'arg':
            if arg is None:
                data = data()
            else:
                if isinstance(arg, dict):
                    data = data(**arg)
                else:
                    data = data(arg)
    return data


class AVM(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff
    """
    PLUGIN_VERSION = '2.0.2'

    # ToDo: FritzHome.handle_updated_item: implement 'saturation'
    # ToDo: FritzHome.handle_updated_item: implement 'unmapped_hue'
    # ToDo: FritzHome.handle_updated_item: implement 'unmapped_saturation'
    # ToDo: FritzHome.handle_updated_item: implement 'hsv'
    # ToDo: FritzHome.handle_updated_item: implement 'hs'

    def __init__(self, sh):
        """Initializes the plugin."""
        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.logger.info('Init AVM Plugin')

        # Enable / Disable debug log generation depending on log level
        self.debug_log = self.logger.isEnabledFor(logging.DEBUG)

        # Get/Define Properties
        _host = self.get_parameter_value('host')
        _port = self.get_parameter_value('port')
        _verify = self.get_parameter_value('verify')
        _username = self.get_parameter_value('username')
        _passwort = self.get_parameter_value('password')
        _call_monitor_incoming_filter = self.get_parameter_value('call_monitor_incoming_filter')
        _log_entry_count = self.get_parameter_value('log_entry_count')
        _use_tr064_backlist = self.get_parameter_value('tr064_item_blacklist')
        self._call_monitor = self.get_parameter_value('call_monitor')
        self._aha_http_interface = self.get_parameter_value('avm_home_automation')
        self._cycle = self.get_parameter_value('cycle')
        self.alive = False
        ssl = self.get_parameter_value('ssl')
        if ssl and not _verify:
            urllib3.disable_warnings()

        # init FritzDevice
        try:
            self.fritz_device = FritzDevice(_host, _port, ssl, _verify, _username, _passwort, _call_monitor_incoming_filter, _use_tr064_backlist, self)
        except Exception as e:
            self.logger.warning(f"Error '{e!r}' establishing connection to Fritzdevice via TR064-Interface.")
            self.fritz_device = None
        else:
            self.logger.debug("Connection to FritzDevice established.")

        # init FritzHome
        try:
            self.fritz_home = FritzHome(_host, ssl, _verify, _username, _passwort, _log_entry_count, self)
        except Exception as e:
            self.logger.warning(f"Error '{e!r}' establishing connection to Fritzdevice via AHA-HTTP-Interface.")
            self.fritz_home = None
        else:
            self.logger.debug("Connection to FritzDevice via AHA-HTTP-Interface established.")

        # init Call Monitor
        if self._call_monitor and self.fritz_device and self.fritz_device.connected:
            try:
                self.monitoring_service = Callmonitor(_host, 1012, self.fritz_device.get_contact_name_by_phone_number, _call_monitor_incoming_filter, self)
            except Exception as e:
                self.logger.warning(f"Error '{e!r}' establishing connection to Fritzdevice CallMonitor.")
                self.monitoring_service = None
            else:
                self.logger.debug("Connection to FritzDevice CallMonitor established.")
        else:
            self.monitoring_service = None

        # init WebIF
        self.init_webinterface(WebInterface)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        if self.fritz_device is not None:
            self.create_cyclic_scheduler(target='tr064', items=self.fritz_device.items, fct=self.fritz_device.cyclic_item_update, offset=2)
            self.fritz_device.cyclic_item_update(read_all=True)

        if self._aha_http_interface and self.fritz_device is not None and self.fritz_device.is_fritzbox():
            # add scheduler for updating items
            self.create_cyclic_scheduler(target='aha', items=self.fritz_home.items, fct=self.fritz_home.cyclic_item_update, offset=4)
            self.fritz_home.cyclic_item_update(read_all=True)
            # add scheduler for checking validity of session id
            self.scheduler_add('check_sid', self.fritz_home.check_sid, prio=5, cycle=900, offset=30)

        if self.monitoring_service:
            self.monitoring_service.set_callmonitor_item_values_initially()

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_tr064')
        if self._aha_http_interface:
            self.scheduler_remove('poll_aha')
            self.scheduler_remove('check_sid')
            self.fritz_home.logout()
        if self.monitoring_service:
            self.monitoring_service.disconnect()
        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in the future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, 'avm_data_type'):
            self.logger.debug(f"parse item: {item}")

            # get avm_data_type and avm_data_cycle
            avm_data_type = self.get_iattr_value(item.conf, 'avm_data_type')
            avm_data_cycle = self.get_iattr_value(item.conf, 'avm_data_cycle')
            if avm_data_cycle is None:
                avm_data_cycle = self._cycle
            if 0 < avm_data_cycle < 30:
                avm_data_cycle = 30

            # define item_config
            item_config = {'avm_data_type': avm_data_type, 'avm_data_cycle': avm_data_cycle, 'next_update': time.time()}

            # handle items specific to call monitor
            if avm_data_type in CALL_MONITOR_ATTRIBUTES:
                if self.monitoring_service:
                    self.monitoring_service.register_item(item, item_config)
                else:
                    self.logger.warning(f"Items with avm attribute {avm_data_type!r} found, which needs Call-Monitoring-Service. This is not available/enabled for that plugin; Item will be ignored.")

            # handle smarthome items using aha-interface (new)
            elif avm_data_type in AHA_ATTRIBUTES:
                if self.fritz_home:
                    self.fritz_home.register_item(item, item_config)
                else:
                    self.logger.warning(f"Items with avm attribute {avm_data_type!r} found, which needs aha-http-interface. This is not available/enabled for that plugin; Item will be ignored.")

            # handle items updated by tr-064 interface
            elif avm_data_type in TR064_ATTRIBUTES:
                if self.fritz_device:
                    self.fritz_device.register_item(item, item_config)
                else:
                    self.logger.warning(f"Items with avm attribute {avm_data_type!r} found, which needs tr064 interface. This is not available/enabled; Item will be ignored.")
            # handle anything else
            else:
                self.logger.warning(f"Item={item.path()} has unknown avm_data_type {avm_data_type!r}. Item will be ignored.")

            # items which can be changed outside the plugin context
            if avm_data_type in ALL_ATTRIBUTES_WRITEABLE:
                return self.update_item

    def unparse_item(self, item):
        """ remove item bindings from plugin """
        super().unparse_item(item)

        # handle items specific to call monitor
        if self.monitoring_service:
            self.monitoring_service.unregister_item(item)

        if self.fritz_home:
            self.fritz_home.unregister_item(item)

        # handle items updated by tr-064 interface
        if self.fritz_device:
            self.fritz_device.unregister_item(item)

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the destination
        """
        if self.alive and caller != self.get_fullname():

            # get avm_data_type
            avm_data_type = to_str(self.get_iattr_value(item.conf, 'avm_data_type'))

            self.logger.info(f"Updated item: {item.path()} with avm_data_type={avm_data_type} item has been changed outside this plugin from caller={caller}")

            readafterwrite = 0
            if self.has_iattr(item.conf, 'avm_read_after_write'):
                readafterwrite = to_int(self.get_iattr_value(item.conf, 'avm_read_after_write'))
                if self.debug_log:
                    self.logger.debug(f'Attempting read after write for item: {item.path()}, avm_data_type: {avm_data_type}, delay: {readafterwrite}s')

            # handle items updated by tr-064 interface
            if avm_data_type in TR064_ATTRIBUTES:
                if self.debug_log:
                    self.logger.debug(f"Updated item={item.path()} with avm_data_type={avm_data_type} identified as part of 'TR064_ATTRIBUTES'")
                self.fritz_device.handle_updated_item(item, avm_data_type, readafterwrite)

            # handle items updated by AHA_ATTRIBUTES
            elif avm_data_type in AHA_ATTRIBUTES:
                if self.fritz_home:
                    if self.debug_log:
                        self.logger.debug(f"Updated item={item.path()} with avm_data_type={avm_data_type} identified as part of 'AHA_ATTRIBUTES'")
                    self.fritz_home.handle_updated_item(item, avm_data_type, readafterwrite)
                else:
                    self.logger.warning(f"AVM Homeautomation Interface not activated or not available. Update for {avm_data_type} will not be executed.")

    def create_cyclic_scheduler(self, target: str, items: dict, fct, offset: int):
        """Create the scheduler to handle cyclic read commands and find the proper time for the cycle."""
        # find the shortest cycle
        shortestcycle = -1
        for item in items:
            item_cycle = items[item]['avm_data_cycle']
            if item_cycle != 0 and (shortestcycle == -1 or item_cycle < shortestcycle):
                shortestcycle = item_cycle

        # Start the worker thread
        if shortestcycle != -1:
            # Balance unnecessary calls and precision
            workercycle = int(shortestcycle / 2)
            # just in case it already exists...
            if self.scheduler_get(f'poll_{target}'):
                self.scheduler_remove(f'poll_{target}')
            dt = self.shtime.now() + datetime.timedelta(seconds=workercycle)
            self.scheduler_add(f'poll_{target}', fct, cycle=workercycle, prio=5, offset=offset, next=dt)
            self.logger.info(f'{target}: Added cyclic worker thread ({workercycle} sec cycle). Shortest item update cycle found: {shortestcycle} sec')
            return True
        else:
            return False

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()

    def monitoring_service_connect(self):
        self.monitoring_service.connect()

    def monitoring_service_disconnect(self):
        self.monitoring_service.disconnect()

    @NoAttributeError
    def start_call(self, phone_number):
        return self.fritz_device.start_call(phone_number)

    @NoAttributeError
    def cancel_call(self):
        return self.fritz_device.cancel_call()

    @NoAttributeError
    def get_call_origin(self):
        return self.fritz_device.get_call_origin()

    @NoAttributeError
    def set_call_origin(self, phone_name: str):
        return self.fritz_device.set_call_origin(phone_name)

    @NoAttributeError
    def get_calllist(self):
        return self.fritz_device.get_calllist_from_cache()

    @NoAttributeError
    def get_phone_name(self, index: int = 1):
        return self.fritz_device.get_phone_name(index)

    @NoAttributeError
    def get_phone_numbers_by_name(self, name: str = '', phonebook_id: int = 0):
        return self.fritz_device.get_phone_numbers_by_name(name, phonebook_id)

    @NoAttributeError
    def get_contact_name_by_phone_number(self, phone_number: str = '', phonebook_id: int = 0):
        return self.fritz_device.get_phone_numbers_by_name(phone_number, phonebook_id)

    @NoAttributeError
    def get_device_log_from_lua(self):
        return self.fritz_home.get_device_log_from_lua()

    @NoAttributeError
    def get_device_log_from_lua_separated(self):
        return self.fritz_home.get_device_log_from_lua_separated()

    @NoAttributeError
    def get_device_log_from_tr064(self):
        return self.fritz_device.get_device_log_from_tr064()

    @NoAttributeError
    def get_host_details(self, index: int):
        return self.fritz_device.get_host_details(index)

    @NoAttributeError
    def get_hosts(self, only_active: bool = False):
        return self.fritz_device.get_hosts(only_active)

    @NoAttributeError
    def get_hosts_dict(self):
        return self.fritz_device.get_hosts_dict()

    @NoAttributeError
    def get_mesh_topology(self):
        return self.fritz_device.get_mesh_topology()

    @NoAttributeError
    def is_host_active(self, mac_address: str):
        return self.fritz_device.is_host_active(mac_address)

    @NoAttributeError
    def reboot(self):
        return self.fritz_device.reboot()

    @NoAttributeError
    def reconnect(self):
        return self.fritz_device.reconnect()

    @NoAttributeError
    def wol(self, mac_address: str):
        return self.fritz_device.wol(mac_address)

    @NoAttributeError
    def get_number_of_deflections(self):
        return self.fritz_device.get_number_of_deflections()

    @NoAttributeError
    def get_deflection(self, deflection_id: int = 0):
        return self.fritz_device.get_deflection(deflection_id)

    @NoAttributeError
    def get_deflections(self):
        return self.fritz_device.get_deflections()

    @NoAttributeError
    def set_deflection_enable(self, deflection_id: int = 0, new_enable: bool = False):
        return self.fritz_device.set_deflection(deflection_id, new_enable)

    @NoAttributeError
    def set_tam(self, tam_index: int = 0, new_enable: bool = False):
        return self.fritz_device.set_tam(tam_index, new_enable)


class FritzDevice:
    """
    This class encapsulates information related to a specific FritzDevice using TR-064
    """

    from .tr064.client import Client as Tr064_Client

    """
    Definition of TR-064 Error Codes
    """
    ERROR_CODES = {401: 'Unable to connect to FritzDevice. Invalid user and/or password.',
                   402: 'Invalid arguments',
                   500: 'Internal Server Error',
                   501: 'Action failed',
                   600: 'Argument invalid',
                   713: 'Invalid array index',
                   714: 'No such array entry in array',
                   820: 'Internal Error',
                   403: 'SIP_FORBIDDEN, Beschreibung steht in der Hilfe (Webinterface)',
                   404: 'SIP_NOT_FOUND, Gegenstelle nicht erreichbar (local part der SIP-URL nicht erreichbar (Host schon))',
                   405: 'SIP_METHOD_NOT_ALLOWED',
                   406: 'SIP_NOT_ACCEPTED',
                   408: 'SIP_NO_ANSWER',
                   484: 'SIP_ADDRESS_INCOMPLETE, Beschreibung steht in der Hilfe (Webinterface)',
                   485: 'SIP_AMBIGUOUS, Beschreibung steht in der Hilfe (Webinterface)',
                   486: 'SIP_BUSY_HERE, Ziel besetzt (vermutlich auch andere Gründe bei der Gegenstelle)',
                   487: 'SIP_REQUEST_TERMINATED, Anrufversuch beendet (Gegenstelle nahm nach ca. 30 Sek. nicht ab)',
                   866: 'second factor authentication required',
                   867: 'second factor authentication blocked',
                   }

    """
    Definition of TR-064 details
    """
    FRITZ_TR64_DESC_FILE = "tr64desc.xml"
    FRITZ_IGD_DESC_FILE = "igddesc.xml"
    FRITZ_IGD2_DESC_FILE = "igd2desc.xml"
    FRITZ_L2TPV3_FILE = "l2tpv3.xml"
    FRITZ_FBOX_DESC_FILE = "fboxdesc.xml"

    ERROR_COUNT_TO_BE_BLACKLISTED = 2

    def __init__(self, host, port, ssl, verify, username, password, call_monitor_incoming_filter, use_tr064_backlist, plugin_instance=None):
        """
        Init class FritzDevice
        """
        self._plugin_instance = plugin_instance
        self.logger = self._plugin_instance.logger
        self.debug_log = self._plugin_instance.debug_log
        self.logger.debug("Init FritzDevice")

        self.host = host
        self.port = port
        self.ssl = ssl
        self.verify = verify
        self.username = username
        self.password = password
        self.use_tr064_blacklist = use_tr064_backlist
        self._call_monitor_incoming_filter = call_monitor_incoming_filter
        self._data_cache = {}
        self._calllist_cache = []
        self._timeout = 10
        self.items = {}
        self._session = requests.Session()
        self.connected = False
        self.default_connection_service = None
        self.client = None
        self.client_igd = None

        # get client objects
        try:
            self.client = FritzDevice.Tr064_Client(username=self.username, password=self.password, base_url=self._build_url(), description_file=self.FRITZ_TR64_DESC_FILE, verify=self.verify)
        except Exception as e:
            self.logger.error(f"Init TR064 Client for {self.FRITZ_TR64_DESC_FILE} caused error {e!r}.")
        else:
            self.connected = True
            if self.is_fritzbox():
                # get GetDefaultConnectionService
                self.default_connection_service = self._get_default_connection_service()

                # init client for InternetGatewayDevice
                try:
                    self.client_igd = FritzDevice.Tr064_Client(username=self.username, password=self.password, base_url=self._build_url(), description_file=self.FRITZ_IGD_DESC_FILE, verify=self.verify)
                except Exception as e:
                    self.logger.error(f"Init TR064 Client for {self.FRITZ_IGD_DESC_FILE} caused error {e!r}.")
                    pass

    def register_item(self, item, item_config: dict):
        """
        Parsed items valid for that class will be registered
        """
        index = None
        avm_data_type = item_config['avm_data_type']

        # if fritz device is repeater and avm_data_type is not supported by repeater, return
        if self.is_repeater() and avm_data_type not in ALL_ATTRIBUTES_SUPPORTED_BY_REPEATER:
            self.logger.warning(f"Item {item.path()} with avm attribute {avm_data_type!r} found, which is not supported by Repeaters; Item will be ignored.")
            return

        # handle wlan items
        if avm_data_type in WLAN_CONFIG_ATTRIBUTES:
            index = self._get_wlan_index(item)
            if index is not None:
                self.logger.debug(f"Item {item.path()} with avm device attribute {avm_data_type!r} and defined 'avm_wlan_index' with {index!r} found; append to list.")
            else:
                self.logger.warning(f"Item {item.path()} with avm attribute {avm_data_type!r} found, but 'avm_wlan_index' is not defined; Item will be ignored.")
                return

        # handle network_device / host child related items
        elif avm_data_type in HOST_ATTRIBUTES_CHILD:
            index = self._get_mac(item)
            if index is not None:
                self.logger.debug(f"Item {item.path()} with avm device attribute {avm_data_type!r} and defined 'avm_mac' with {index!r} found; append to list.")
            else:
                self.logger.warning(f"Item {item.path()} with avm attribute {avm_data_type!r} found, but 'avm_mac' is not defined; Item will be ignored.")
                return

        # handle tam related items
        elif avm_data_type in TAM_ATTRIBUTES:
            index = self._get_tam_index(item)
            if index is not None:
                self.logger.debug(f"Item {item.path()} with avm device attribute {avm_data_type!r} and defined 'avm_tam_index' with {index!r} found; append to list.")
            else:
                self.logger.warning(f"Item {item.path()} with avm attribute {avm_data_type!r} found, but 'avm_tam_index' is not defined; Item will be ignored.")
                return

        # handle deflection related items
        elif avm_data_type in DEFLECTION_ATTRIBUTES:
            index = self._get_deflection_index(item)
            if index is not None:
                self.logger.debug(f"Item {item.path()} with avm device attribute {avm_data_type!r} and defined 'avm_tam_index' with {index!r} found; append to list.")
            else:
                self.logger.warning(f"Item {item.path()} with avm attribute {avm_data_type!r} found, but 'avm_tam_index' is not defined; Item will be ignored.")
                return

        # update item config
        item_config.update({'interface': 'tr064', 'index': index, 'error_count': 0})

        # register item
        self.items[item] = item_config

    def unregister_item(self, item):
        """ remove item from instance """
        try:
            del self.items[item]
        except KeyError:
            pass

    def handle_updated_item(self, item, avm_data_type: str, readafterwrite: int):
        """Updated Item will be processed and value communicated to AVM Device"""
        # get index
        index = self.items[item]['index']

        # to be set value
        to_be_set_value = item()

        # define command per avm_data_type
        _dispatcher = {'wlanconfig':        ('set_wlan',       {'NewEnable': int(to_be_set_value)},                                index),
                       'wps_active':        ('set_wps',        {'NewX_AVM_DE_WPSEnable': int(to_be_set_value)},                    index),
                       'tam':               ('set_tam',        {'NewIndex': int(index), 'NewEnable': int(to_be_set_value)},        None),
                       'deflection_enable': ('set_deflection', {'NewDeflectionId': int(index), 'NewEnable': int(to_be_set_value)}, None),
                       }

        # do logging
        if self.debug_log:
            self.logger.debug(f"Item {item.path()} with avm_data_type={avm_data_type} has changed for index {index}; New value={to_be_set_value}")

        # call setting method
        cmd, args, wlan_index = _dispatcher[avm_data_type]
        self._set_fritz_device(cmd, args, wlan_index)
        if self.debug_log:
            self.logger.debug(f"Setting AVM Device with successful.")

        # handle readafterwrite
        if readafterwrite:
            self._read_after_write(item, avm_data_type, index, readafterwrite, to_be_set_value)

    def _read_after_write(self, item, avm_data_type, _index, delay, to_be_set_value):
        """read the new item value and compares with to_be_set_value, update item to confirm correct value"""
        # do logging
        if self.debug_log:
            self.logger.debug(f"_readafterwrite called with: item={item.path()}, avm_data_type={avm_data_type}, index={_index}; delay={delay}, to_be_set_value={to_be_set_value}")

        # sleep
        time.sleep(delay)

        # get current value from AVM device
        current_value = self._poll_fritz_device(avm_data_type, _index, enforce_read=True)

        # write current value back to item
        item(current_value, self._plugin_instance.get_fullname())

        # do logging
        if current_value != to_be_set_value:
            self.logger.warning(f"Setting AVM Device defined in Item={item.path()} with avm_data_type={avm_data_type} to value={to_be_set_value} FAILED!")
        else:
            if self.debug_log:
                self.logger.debug(f"Setting AVM Device defined in Item={item.path()} with avm_data_type={avm_data_type} to value={to_be_set_value} successful!")

    def _build_url(self) -> str:
        """
        Builds a request url

         :return: string of the url, dependent on settings of the FritzDevice
        """
        if self.ssl:
            url_prefix = "https"
        else:
            url_prefix = "http"
        url = f"{url_prefix}://{self.host}:{self.port}"

        return url

    def _get_wlan_index(self, item):
        """
        return wlan index for given item
        """
        wlan_index = None
        for _ in range(2):
            attribute = 'avm_wlan_index'

            wlan_index = self._plugin_instance.get_iattr_value(item.conf, attribute)
            if wlan_index:
                break
            else:
                item = item.return_parent()

        if wlan_index is not None:
            wlan_index = int(wlan_index) - 1
            if not 0 <= wlan_index <= 2:
                wlan_index = None
                self.logger.warning(f"Attribute 'avm_wlan_index' for item {item.path()} not in valid range 1-3.")

        return wlan_index

    def _get_tam_index(self, item):
        """
        return tam index for given item
        """
        tam_index = None
        for _ in range(2):
            attribute = 'avm_tam_index'

            tam_index = self._plugin_instance.get_iattr_value(item.conf, attribute)
            if tam_index:
                break
            else:
                item = item.return_parent()

        if tam_index is not None:
            tam_index = int(tam_index) - 1
            if not 0 <= tam_index <= 4:
                tam_index = None
                self.logger.warning(f"Attribute 'avm_tam_index' for item {item.path()} not in valid range 1-5.")

        return tam_index

    def _get_deflection_index(self, item):
        """
        return deflection index for given item
        """
        deflection_index = None
        for _ in range(2):
            attribute = 'avm_deflection_index'

            deflection_index = self._plugin_instance.get_iattr_value(item.conf, attribute)
            if deflection_index:
                break
            else:
                item = item.return_parent()

        if deflection_index is not None:
            deflection_index = int(deflection_index) - 1
            if not 0 <= deflection_index <= 31:
                deflection_index = None
                self.logger.warning(f"Attribute 'avm_deflection_index' for item {item.path()} not in valid range 1-5.")

        return deflection_index

    def _get_mac(self, item) -> Union[str, None]:
        """
        return mac for given item
        """
        mac = None
        for _ in range(2):
            attribute = 'avm_mac'

            mac = self._plugin_instance.get_iattr_value(item.conf, attribute)
            if mac:
                break
            else:
                item = item.return_parent()

        return mac

    def _get_default_connection_service(self):

        _default_connection_service = self._poll_fritz_device('default_connection_service', enforce_read=True)

        if isinstance(_default_connection_service, int):
            self.logger.error(f"Unable to determine default_connection_service. Error {_default_connection_service}.")
            return
        elif isinstance(_default_connection_service, str):
            if 'PPP' in _default_connection_service:
                return 'PPP'
            elif 'IP' in _default_connection_service:
                return 'IP'

    def item_list(self):
        return list(self.items.keys())

    def manufacturer_name(self):
        return self._poll_fritz_device('manufacturer')

    def manufacturer_oui(self):
        return self._poll_fritz_device('manufacturer_oui')

    def model_name(self):
        return self._poll_fritz_device('model_name')

    def product_class(self):
        return self._poll_fritz_device('product_class')

    def desciption(self):
        return self._poll_fritz_device('description')

    def safe_port(self):
        return self._poll_fritz_device('security_port')

    def is_fritzbox(self):
        try:
            return 'box' in self.model_name().lower()
        except AttributeError as e:
            self.logger.error(f'Could now find out if {self.product_class()} represents a Fritzbox. Error {e!r} occurred.')
            return False

    def is_repeater(self):
        try:
            return 'repeater' in self.product_class().lower()
        except AttributeError as e:
            self.logger.error(f'Could now find out if {self.product_class()} represents a Repeater. Error {e!r} occurred.')
            return False

    def wlan_devices_count(self):
        wlan_devices = self.get_wlan_devices()
        if wlan_devices:
            return wlan_devices.get('TotalAssociations')
        else:
            return 0

    # ----------------------------------
    # Update methods
    # ----------------------------------
    def cyclic_item_update(self, read_all: bool = False):
        """Updates Item Values"""
        if not self.connected:
            self.logger.warning("FritzDevice not connected. No update of item values possible.")
            return

        current_time = int(time.time())

        # iterate over items and get data
        for item in self.items:

            # get item config
            item_config = self.items[item]
            avm_data_type = item_config['avm_data_type']
            index = item_config['index']
            cycle = item_config['avm_data_cycle']
            next_time = item_config['next_update']
            error_count = item_config['error_count']

            # check if item is blacklisted
            if error_count >= self.ERROR_COUNT_TO_BE_BLACKLISTED:
                self.logger.info(f"Item {item.path()} is blacklisted due to exceptions in former update cycles. Item will be ignored.")
                continue

            # read items with cycle == 0 just at init
            if not read_all and cycle == 0:
                self.logger.debug(f"Item {item.path()} just read at init. No further update.")
                continue

            # check if item is already due
            if next_time > current_time and not read_all:
                self.logger.debug(f"Item {item.path()} is not due yet.")
                continue

            # check, if client_igd exists when avm_data_type startswith 'wan_current' are due
            if avm_data_type.startswith('wan_current') and self.client_igd is None:
                self.logger.debug(f"Skipping item {item} with wan_current and no client_igd")
                continue

            self.logger.debug(f"Item={item.path()} with avm_data_type={avm_data_type} and index={index} will be updated")

            # get data and set item value

            if not self._update_item_value(item, avm_data_type, index) and self.use_tr064_blacklist:
                error_count += 1
                self.logger.debug(f"{item.path()} caused error. New error_count: {error_count}. Item will be blacklisted after more than 2 errors.")
                item_config.update({'error_count': error_count})

            # set next due date
            self.items[item].update({'next_update': current_time + cycle})

        # clear data cache dict after update cycle
        self._clear_data_cache()

    def _update_item_value(self, item, avm_data_type: str, index: str) -> bool:
        """ Polls data and set item value; Return True if action was successful, else False"""

        try:
            data = self._poll_fritz_device(avm_data_type, index)
        except Exception as e:
            self.logger.error(f"Error {e!r} occurred during update of item={item} with avm_data_type={avm_data_type} and index={index}. Check item configuration regarding supported/activated function of AVM device. ")
            return False

        if isinstance(data, int) and data in self.ERROR_CODES:
            self.logger.warning(f"Error {data} '{self.ERROR_CODES.get(data, None)}' occurred during update of item={item} with avm_data_type={avm_data_type} and index={index}. Check item configuration regarding supported/activated function of AVM device. ")
            return False
        else:
            item(data, self._plugin_instance.get_fullname())
            return True

    def _poll_fritz_device(self, avm_data_type: str, index=None, enforce_read: bool = False):
        """
        Poll Fritz Device, feed dictionary and return data

        :param avm_data_type:   data item to be called
        :param index:           index or avm_data_type
        :param enforce_read:    reading of data from fritz device will be enforced (currently cached data will not be used)
        """
        link_ppp = {
            'wan_connection_status':        ('WANConnectionDevice',   'WANPPPConnection',         'GetInfo',                       None,               'NewConnectionStatus'),
            'wan_connection_error':         ('WANConnectionDevice',   'WANPPPConnection',         'GetInfo',                       None,               'NewLastConnectionError'),
            'wan_is_connected':             ('WANConnectionDevice',   'WANPPPConnection',         'GetInfo',                       None,               'NewConnectionStatus'),
            'wan_uptime':                   ('WANConnectionDevice',   'WANPPPConnection',         'GetInfo',                       None,               'NewUptime'),
            'wan_ip':                       ('WANConnectionDevice',   'WANPPPConnection',         'GetExternalIPAddress',          None,               'NewExternalIPAddress'),
        }

        link_ip = {
            'wan_connection_status':        ('WANConnectionDevice',   'WANIPConnection',          'GetInfo',                       None,               'NewConnectionStatus'),
            'wan_connection_error':         ('WANConnectionDevice',   'WANIPConnection',          'GetInfo',                       None,               'NewLastConnectionError'),
            'wan_is_connected':             ('WANConnectionDevice',   'WANIPConnection',          'GetInfo',                       None,               'NewConnectionStatus'),
            'wan_uptime':                   ('WANConnectionDevice',   'WANIPConnection',          'GetInfo',                       None,               'NewUptime'),
            'wan_ip':                       ('WANConnectionDevice',   'WANIPConnection',          'GetExternalIPAddress',          None,               'NewExternalIPAddress'),
        }

        link = {
            # 'avm_data_type':              ('Device',                'Service',                  'Action',                        'In_Argument',      'Out_Argument'),
            'manufacturer':                 ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewManufacturerName'),
            'product_class':                ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewProductClass'),
            'manufacturer_oui':             ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewManufacturerOUI'),
            'model_name':                   ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewModelName'),
            'description':                  ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewDescription'),
            'uptime':                       ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewUpTime'),
            'serial_number':                ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewSerialNumber'),
            'software_version':             ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewSoftwareVersion'),
            'hardware_version':             ('InternetGatewayDevice', 'DeviceInfo',               'GetInfo',                        None,              'NewHardwareVersion'),
            'device_log':                   ('InternetGatewayDevice', 'DeviceInfo',               'GetDeviceLog',                   None,              'NewDeviceLog'),
            'security_port':                ('InternetGatewayDevice', 'DeviceInfo',               'GetSecurityPort',                None,              'NewSecurityPort'),
            'myfritz_status':               ('InternetGatewayDevice', 'X_AVM_DE_MyFritz',         'GetInfo',                        None,              'NewEnabled'),
            'tam':                          ('InternetGatewayDevice', 'X_AVM_DE_TAM',             'GetInfo',                        'NewIndex',        'NewEnable'),
            'tam_name':                     ('InternetGatewayDevice', 'X_AVM_DE_TAM',             'GetInfo',                        'NewIndex',        'NewName'),
            'tamlist_url':                  ('InternetGatewayDevice', 'X_AVM_DE_TAM',             'GetMessageList',                 'NewIndex',        'NewURL'),
            'aha_device':                   ('InternetGatewayDevice', 'X_AVM_DE_Homeauto',        'GetSpecificDeviceInfos',         'NewAIN',          'NewSwitchState'),
            'hkr_device':                   ('InternetGatewayDevice', 'X_AVM_DE_Homeauto',        'GetSpecificDeviceInfos',         'NewAIN',          'NewHkrSetVentilStatus'),
            'set_temperature':              ('InternetGatewayDevice', 'X_AVM_DE_Homeauto',        'GetSpecificDeviceInfos',         'NewAIN',          'NewFirmwareVersion'),
            'temperature':                  ('InternetGatewayDevice', 'X_AVM_DE_Homeauto',        'GetSpecificDeviceInfos',         'NewAIN',          'NewTemperatureCelsius'),
            'set_temperature_reduced':      ('InternetGatewayDevice', 'X_AVM_DE_Homeauto',        'GetSpecificDeviceInfos',         'NewAIN',          'NewHkrReduceTemperature'),
            'set_temperature_comfort':      ('InternetGatewayDevice', 'X_AVM_DE_Homeauto',        'GetSpecificDeviceInfos',         'NewAIN',          'NewHkrComfortTemperature'),
            'firmware_version':             ('InternetGatewayDevice', 'X_AVM_DE_Homeauto',        'GetSpecificDeviceInfos',         'NewAIN',          'NewFirmwareVersion'),
            'number_of_deflections':        ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetNumberOfDeflections',         None,              'NewNumberOfDeflections'),
            'deflection_details':           ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflection',                  'NewDeflectionId',  None),
            'deflections_details':          ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflections',                 None,              'NewDeflectionList'),
            'deflection_enable':            ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflection',                  'NewDeflectionId', 'NewEnable'),
            'deflection_type':              ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflection',                  'NewDeflectionId', 'NewType'),
            'deflection_number':            ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflection',                  'NewDeflectionId', 'NewNumber'),
            'deflection_to_number':         ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflection',                  'NewDeflectionId', 'NewDeflectionToNumber'),
            'deflection_mode':              ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflection',                  'NewDeflectionId', 'NewMode'),
            'deflection_outgoing':          ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflection',                  'NewDeflectionId', 'NewOutgoing'),
            'deflection_phonebook_id':      ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetDeflection',                  'NewDeflectionId', 'NewPhonebookID'),
            'calllist_url':                 ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetCallList',                    None,              'NewCallListURL'),
            'phonebook_url':                ('InternetGatewayDevice', 'X_AVM_DE_OnTel',           'GetPhonebook',                   'NewPhonebookID',  'NewPhonebookURL'),
            'call_origin':                  ('InternetGatewayDevice', 'X_VoIP',                   'X_AVM_DE_DialGetConfig',         None,              'NewX_AVM_DE_PhoneName'),
            'phone_name':                   ('InternetGatewayDevice', 'X_VoIP',                   'X_AVM_DE_GetPhonePort', '        NewIndex',         'NewX_AVM_DE_PhoneName'),
            'default_connection_service':   ('InternetGatewayDevice', 'Layer3Forwarding',         'GetDefaultConnectionService',    None,              'NewDefaultConnectionService'),
            'wan_upstream':                 ('WANDevice',             'WANDSLInterfaceConfig',    'GetInfo',                        None,              'NewUpstreamCurrRate'),
            'wan_downstream':               ('WANDevice',             'WANDSLInterfaceConfig',    'GetInfo',                        None,              'NewDownstreamCurrRate'),
            'wan_total_packets_sent':       ('WANDevice',             'WANCommonInterfaceConfig', 'GetTotalPacketsSent',            None,              'NewTotalPacketsSent'),
            'wan_total_packets_received':   ('WANDevice',             'WANCommonInterfaceConfig', 'GetTotalPacketsReceived',        None,              'NewTotalPacketsReceived'),
            'wan_current_packets_sent':     ('WANDevice',             'WANCommonInterfaceConfig', 'GetAddonInfos',                  None,              'NewPacketSendRate'),
            'wan_current_packets_received': ('WANDevice',             'WANCommonInterfaceConfig', 'GetAddonInfos',                  None,              'NewPacketReceiveRate'),
            'wan_total_bytes_sent':         ('WANDevice',             'WANCommonInterfaceConfig', 'GetTotalBytesSent',              None,              'NewTotalBytesSent'),
            'wan_total_bytes_received':     ('WANDevice',             'WANCommonInterfaceConfig', 'GetTotalBytesReceived',          None,              'NewTotalBytesReceived'),
            'wan_current_bytes_sent':       ('WANDevice',             'WANCommonInterfaceConfig', 'GetAddonInfos',                  None,              'NewByteSendRate'),
            'wan_current_bytes_received':   ('WANDevice',             'WANCommonInterfaceConfig', 'GetAddonInfos',                  None,              'NewByteReceiveRate'),
            'wan_link':                     ('WANDevice',             'WANCommonInterfaceConfig', 'GetCommonLinkProperties',        None,              'NewPhysicalLinkStatus'),
            'wlanconfig':                   ('LANDevice',             'WLANConfiguration',        'GetInfo',                        'NewWLAN',         'NewEnable'),
            'wlanconfig_ssid':              ('LANDevice',             'WLANConfiguration',        'GetInfo',                        'NewWLAN',         'NewSSID'),
            'wlan_guest_time_remaining':    ('LANDevice',             'WLANConfiguration',        'X_AVM_DE_GetWLANExtInfo',        'NewWLAN',         'NewX_AVM_DE_TimeRemain'),
            'wlan_associates':              ('LANDevice',             'WLANConfiguration',        'GetTotalAssociations',           'NewWLAN',         'NewTotalAssociations'),
            'wps_status':                   ('LANDevice',             'WLANConfiguration',        'X_AVM_DE_GetWPSInfo',            'NewWLAN',         'NewX_AVM_DE_WPSStatus'),
            'wps_mode':                     ('LANDevice',             'WLANConfiguration',        'X_AVM_DE_GetWPSInfo',            'NewWLAN',         'NewX_AVM_DE_WPSMode'),
            'wps_active':                   ('LANDevice',             'WLANConfiguration',        'X_AVM_DE_GetWPSInfo',            'NewWLAN',         'NewX_AVM_DE_WPSMode'),
            'wlandevice_url':               ('LANDevice',             'WLANConfiguration',        'X_AVM_DE_GetWLANDeviceListPath', 'NewWLAN',         'NewX_AVM_DE_WLANDeviceListPath'),
            'device_ip':                    ('LANDevice',             'Hosts',                    'GetSpecificHostEntry',           'NewMACAddress',   'NewIPAddress'),
            'device_connection_type':       ('LANDevice',             'Hosts',                    'GetSpecificHostEntry',           'NewMACAddress',   'NewInterfaceType'),
            'device_hostname':              ('LANDevice',             'Hosts',                    'GetSpecificHostEntry',           'NewMACAddress',   'NewHostName'),
            'network_device':               ('LANDevice',             'Hosts',                    'GetSpecificHostEntry',           'NewMACAddress',   'NewActive'),
            'connection_status':            ('LANDevice',             'Hosts',                    'GetSpecificHostEntry',           'NewMACAddress',   'NewActive'),
            'is_host_active':               ('LANDevice',             'Hosts',                    'GetSpecificHostEntry',           'NewMACAddress',   'NewActive'),
            'number_of_hosts':              ('LANDevice',             'Hosts',                    'GetHostNumberOfEntries',         None,              'NewHostNumberOfEntries'),
            'host_info':                    ('LANDevice',             'Hosts',                    'GetGenericHostEntry',            'NewIndex',        None),
            'hosts_url':                    ('LANDevice',             'Hosts',                    'X_AVM_DE_GetHostListPath',       None,              'NewX_AVM_DE_HostListPath'),
            'mesh_url':                     ('LANDevice',             'Hosts',                    'X_AVM_DE_GetMeshListPath',       None,              'NewX_AVM_DE_MeshListPath'),
        }

        link2 = {
            'tam_total_message_number': ('get_tam_message_count', {'count_type': 'total'}),
            'tam_new_message_number': ('get_tam_message_count', {'count_type': 'new'}),
            'tam_old_message_number': ('get_tam_message_count', {'count_type': 'old'}),
            'wlan_total_associates': ('wlan_devices_count', None),
            'hosts_info': ('get_hosts_dict', None),
            'hosts_count': ('get_hosts_count', None),
            'mesh_topology': ('get_mesh_topology', None)
        }

        # turn data to True of string is as listed
        str_to_bool = {
            'wan_is_connected': 'Connected',
            'wan_link': 'Up',
            'wps_active': 'active',
            'wlanconfig': '1',
            'tam': '1',
            'deflection_enable': '1',
            'myfritz_status': '1'
        }

        # Update link dict depending on connection type
        if self.default_connection_service == 'PPP':
            link.update(link_ppp)
        elif self.default_connection_service == 'IP':
            link.update(link_ip)

        # define client
        client = 'client'
        if avm_data_type.startswith('wan_current'):
            client = 'client_igd'

        # check if avm_data_type is linked and gather data
        if avm_data_type in link:
            device, service, action, in_arg, out_arg = link[avm_data_type]
            if in_arg is not None and index is None:
                self.logger.warning(f"avm_data_type={avm_data_type} used but required index '{in_arg[3:]}' not given. Request will be aborted.")
                return
            data = self._poll_data(client, device, service, action, in_arg, out_arg, index, enforce_read)
        elif avm_data_type in link2:
            attr, arg = link2[avm_data_type]
            if not arg and index is not None:
                arg = {'index': index}
                data = getattr(self, attr)(**arg)
            elif arg and index is not None:
                arg.update({'index': index})
                data = getattr(self, attr)(**arg)
            elif arg and index is None:
                data = getattr(self, attr)(**arg)
            else:
                data = getattr(self, attr)()
        else:
            return

        # correct data / adapt type of data
        if avm_data_type in str_to_bool:
            data = data == str_to_bool[avm_data_type]

        # return result
        return data

    def _poll_data(self, client: str, device: str, service: str, action: str, in_argument=None, out_argument=None, in_argument_value=None, enforce_read: bool = False):
        """
        Get update data for cache dict; poll data if not yet cached from fritz device
        """
        # self.logger.debug(f"_get_update_data called with device={device}, service={service}, action={action}, in_argument={in_argument}, out_argument={out_argument}, in_argument_value={in_argument_value}, enforce_read={enforce_read}")

        data_args = []
        cache_dict_key = f"{device}_{service}_{action}_{in_argument}_{in_argument_value}"

        # create data_string for polling data from tr064 client
        if in_argument is None:
            data_args = [('attr', client), ('attr', device), ('attr', service), ('attr', action), ('arg', None)]
        elif in_argument_value is not None:
            if service.lower().startswith('wlan'):
                data_args = [('attr', client), ('attr', device), ('attr', service), ('sub', in_argument_value), ('attr', action), ('arg', None)]
            else:
                data_args = [('attr', client), ('attr', device), ('attr', service), ('attr', action), ('arg', {in_argument: in_argument_value})]

        if not data_args:
            return

        # poll data from tr064 client
        if cache_dict_key not in self._data_cache or enforce_read:
            try:
                data = walk_nodes(self, data_args)
            except Exception as e:
                self.logger.warning(f"Poll data from TR064 Client caused Error '{e}'")
                return
            else:
                self._data_cache[cache_dict_key] = data
        else:
            data = self._data_cache.get(cache_dict_key)

        # return data
        if isinstance(data, int) and 99 < data < 1000:
            self.logger.info(f"Response was ErrorCode: {data} '{self.ERROR_CODES.get(data, 'unknown')}' for self.{client}.{device}.{service}.{action}()")
            return data
        elif out_argument:
            try:
                return data.get(out_argument)
            except Exception as e:
                self.logger.warning(f"Poll data from TR064 Client caused Error '{e}'")
        else:
            return data

    def _set_fritz_device(self, avm_data_type: str, args=None, wlan_index=None):
        """Set AVM Device based on avm_data_type and args"""
        if self.debug_log:
            self.logger.debug(f"_set_fritz_device called: avm_data_type={avm_data_type}, args={args}, wlan_index{wlan_index}")

        link = {
            'set_call_origin': ('InternetGatewayDevice', 'X_VoIP',              'X_AVM_DE_DialSetConfig'),
            'set_tam':         ('InternetGatewayDevice', 'X_AVM_DE_TAM',        'SetEnable'),
            'set_aha_device':  ('InternetGatewayDevice', 'X_AVM_DE_Homeauto',   'SetSwitch'),
            'set_deflection':  ('InternetGatewayDevice', 'X_AVM_DE_OnTel',      'SetDeflectionEnable'),
            'set_wlan':        ('LANDevice',             'WLANConfiguration',   'SetEnable'),
            'set_wps':         ('LANDevice',             'WLANConfiguration',   'X_AVM_DE_SetWPSEnable'),
            'reboot':          ('InternetGatewayDevice', 'DeviceConfig',        'Reboot'),
            'wol':             ('LanDevice',             'Hosts',               'X_AVM_DE_GetAutoWakeOnLANByMACAddress'),
            'reconnect_ppp':   ('WANConnectionDevice',   'WANPPPConnection',    'ForceTermination'),
            'reconnect_ipp':   ('WANConnectionDevice',   'WANIPPConnection',    'ForceTermination'),
            'start_call':      ('InternetGatewayDevice', 'X_VoIP',              'X_AVM_DE_DialNumber'),
            'cancel_call':     ('InternetGatewayDevice', 'X_VoIP',              'X_AVM_DE_DialHangup'),
        }

        if avm_data_type not in link:
            return

        device, service, action = link[avm_data_type]
        if self.debug_log:
            self.logger.debug(f"avm_data_type={avm_data_type} -> {device}.{service}.{action}")

        if service.lower().startswith('wlan'):
            if wlan_index is None:
                return
            cmd_args = [('attr', 'client'), ('attr', device), ('attr', service), ('sub', wlan_index), ('attr', action), ('arg', args)]
        elif args is None:
            cmd_args = [('attr', 'client'), ('attr', device), ('attr', service), ('attr', action), ('arg', None)]
        else:
            cmd_args = [('attr', 'client'), ('attr', device), ('attr', service), ('attr', action), ('arg', args)]

        try:
            response = walk_nodes(self, cmd_args)
        except Exception as e:
            self.logger.warning(f"Set FritzDevice with TR064 Client caused Error '{e}'")
            return

        if self.debug_log:
            self.logger.debug(f"response={response} for cmd={cmd_args}.")

        # return response
        if isinstance(response, int) and 99 < response < 1000:
            self.logger.info(f"Response was ErrorCode: {response} '{self.ERROR_CODES.get(response, None)}' for cmd={cmd_args}")
            return
        return response

    def _clear_data_cache(self):
        """
        Clears _data_cache dict and put needed content back
        """
        self._data_cache.clear()

    def _request(self, url: str, timeout: int, verify: bool):
        """
        Do get request and return response
        """
        request = requests.get(url, timeout=timeout, verify=verify)
        if request.status_code == 200:
            return request
        else:
            self.logger.error(f"Request to URL={url} failed with {request.status_code}")
            request.raise_for_status()

    def reset_item_blacklist(self):
        """
        Clean/reset item blacklist
        """
        for item in self.items:
            self.items[item]['error_count'] = 0
        self.logger.info(f"Item Blacklist reset. item_blacklist={self.get_tr064_items_blacklisted()}")

    def get_tr064_items_blacklisted(self) -> list:
        item_list = []
        for item in self.items:
            if self.items[item].get('error_count', 0) >= self.ERROR_COUNT_TO_BE_BLACKLISTED:
                item_list.append(item)
        return item_list

    # ----------------------------------
    # Fritz Device methods, reboot, wol, reconnect
    # ----------------------------------

    def reboot(self):
        """
        Reboots the FritzDevice

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceconfigSCPD.pdf
        """
        # self.client.InternetGatewayDevice.DeviceConfig.Reboot()
        return self._set_fritz_device('reboot')

    def reconnect(self):
        """
        Reconnects the FritzDevice to the WAN

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wanipconnSCPD.pdf
              http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wanpppconnSCPD.pdf
        """
        # default_connection_service can be None, e.g. for repeaters
        try:
            if 'PPP' in self.default_connection_service:
                # self.client.WANConnectionDevice.WANPPPConnection.ForceTermination()
                return self._set_fritz_device('reconnect_ppp')
        except TypeError:
            pass

        # self.client.WANConnectionDevice.WANIPPConnection.ForceTermination()
        return self._set_fritz_device('reconnect_ipp')

    def wol(self, mac_address: str):
        """
        Sends a WOL (WakeOnLAN) command to a MAC address

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param mac_address: MAC address of the device to wake up
        """
        # self.client.LanDevice.Hosts.X_AVM_DE_GetAutoWakeOnLANByMACAddress(NewMACAddress=mac_address)
        return self._set_fritz_device('wol', f"NewMACAddress='{mac_address}'")

    # ----------------------------------
    # caller methods
    # ----------------------------------
    def get_call_origin(self):
        """
        Gets the phone name, currently set as call_origin.

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        :return: String phone name
        """
        # phone_name = self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_DialGetConfig()['NewX_AVM_DE_PhoneName']
        phone_name = self._poll_fritz_device('call_origin', enforce_read=True)

        if not phone_name:
            self.logger.error("No call origin available.")
        return phone_name

    def get_phone_name(self, index: int = 1):
        """
        Get the phone name at a specific index. The returned value can be used as phone_name for set_call_origin.

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param index: Parameter is an INT, starting from 1. In case an index does not exist, an error is logged.
        :return: String phone name
        """
        # phone_name = self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_GetPhonePort()['NewX_AVM_DE_PhoneName']
        phone_name = self._poll_fritz_device('phone_name', index, enforce_read=True)

        if not phone_name:
            self.logger.error(f"No phone name available at provided index {index}")
        return phone_name

    def set_call_origin(self, phone_name: str):
        """
        Sets the call origin, e.g. before running 'start_call'

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param phone_name: full phone identifier, could be e.g. '**610' for an internal device
        """
        # self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_DialSetConfig(NewX_AVM_DE_PhoneName=phone_name.strip())
        return self._set_fritz_device('set_call_origin', f"NewX_AVM_DE_PhoneName='{phone_name.strip()}'")

    def start_call(self, phone_number: str):
        """
        Triggers a call for a given phone number

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param phone_number: full phone number to call
        """
        # self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_DialNumber(NewX_AVM_DE_PhoneNumber=phone_number.strip())
        return self._set_fritz_device('start_call', f"NewX_AVM_DE_PhoneNumber='{phone_number.strip()}'")

    def cancel_call(self):
        """
        Cancels an active call

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        """
        # self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_DialHangup()
        return self._set_fritz_device('cancel_call')

    def get_contact_name_by_phone_number(self, phone_number: str = '', phonebook_id: int = 0) -> str:
        """Get contact from phone book by phone number"""
        if phone_number.endswith('#'):
            phone_number = phone_number.strip('#')

        # phonebook_url = self.client.InternetGatewayDevice.X_AVM_DE_OnTel.GetPhonebook(NewPhonebookID=phonebook_id)['NewPhonebookURL']
        phonebook_url = to_str(self._poll_fritz_device('phonebook_url', phonebook_id, enforce_read=True))
        if not phonebook_url:
            return ''

        phonebooks = request_response_to_xml(self._request(phonebook_url, self._timeout, self.verify))
        if phonebooks:
            for phonebook in phonebooks.iter('phonebook'):
                for contact in phonebook.iter('contact'):
                    for number in contact.findall('.//number'):
                        if number.text:
                            nr = number.text.strip()
                            if phone_number in nr:
                                return contact.find('.//realName').text
        else:
            self.logger.error("Phonebook not available on the FritzDevice")

        return ''

    def get_phone_numbers_by_name(self, name: str = '', phonebook_id: int = 0) -> dict:
        """Get phone number from phone book by contact"""
        tel_type = {"mobile": "CELL", "work": "WORK", "home": "HOME"}
        result_numbers = {}

        # phonebook_url = self.client.InternetGatewayDevice.X_AVM_DE_OnTel.GetPhonebook(NewPhonebookID=phonebook_id)['NewPhonebookURL']
        phonebook_url = to_str(self._poll_fritz_device('phonebook_url', phonebook_id, enforce_read=True))
        if not phonebook_url:
            return {}

        phonebooks = request_response_to_xml(self._request(phonebook_url, self._timeout, self.verify))
        if phonebooks is not None:
            for phonebook in phonebooks.iter('phonebook'):
                for contact in phonebook.iter('contact'):
                    for real_name in contact.findall('.//realName'):
                        if name.lower() in real_name.text.lower():
                            result_numbers[real_name.text] = []
                            for number in contact.findall('.//number'):
                                if number.text:
                                    result_number_dict = dict()
                                    result_number_dict['number'] = number.text.strip()
                                    # result_number_dict['type'] = tel_type[number.attrib["type"]]
                                    result_number_dict['type'] = number.attrib["type"]
                                    result_numbers[real_name.text].append(result_number_dict)
            return result_numbers
        else:
            self.logger.error("Phonebook not available on the FritzDevice")
            return {}

    def get_calllist_from_cache(self) -> list:
        """returns the cached calllist when all items are initialized. The filter set by plugin.yaml is applied."""
        if not self._calllist_cache:
            self._calllist_cache = self.get_calllist(self._call_monitor_incoming_filter)
        return self._calllist_cache

    def get_calllist(self, filter_incoming: str = '') -> list:
        """request calllist from AVM Device"""
        calllist_url = to_str(self._poll_fritz_device('calllist_url', enforce_read=True))

        if not calllist_url:
            return []

        calllist = request_response_to_xml(self._request(calllist_url, self._timeout, self.verify))

        if calllist is not None:
            result_entries = []
            for calllist_entry in calllist.iter('Call'):
                result_entry = {}
                progress = True
                if len(filter_incoming) > 0:
                    call_type_element = calllist_entry.find('Type')
                    call_type = call_type_element.text
                    if call_type == '1' or call_type == '2':
                        called_number = calllist_entry.find('CalledNumber').text
                        if filter_incoming not in called_number:
                            progress = False

                if progress:
                    attributes = ['Id', 'Type', 'Caller', 'Called', 'CalledNumber', 'Name', 'Numbertype', 'Device', 'Port',
                                  'Date', 'Duration']
                    for attribute in attributes:
                        attribute_value = calllist_entry.find(attribute)
                        if attribute_value is not None:
                            if attribute != 'Date':
                                result_entry[attribute] = attribute_value.text
                            else:
                                result_entry[attribute] = datetime.datetime.strptime(attribute_value.text, '%d.%m.%y %H:%M')
                    result_entries.append(result_entry)
            return result_entries
        else:
            self.logger.error("Calllist not available on the FritzDevice")
            return []

    # ----------------------------------
    # logs methods
    # ----------------------------------
# TODO: rewrite to -> list[str]?
# --> das ist Bestandscode und diente zur Anzeige von "Fließtext" in der Visu
    def get_device_log_from_tr064(self):
        """
        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceinfoSCPD.pdf

        Gets the Device Log via TR-064
        :return: Array of Device Log Entries (Strings)
        """
        # device_log = self.client.InternetGatewayDevice.DeviceInfo.GetDeviceLog()['NewDeviceLog']
        device_log = self._poll_fritz_device('device_log', enforce_read=True)

        if device_log is None:
            return ""
        if isinstance(device_log, str):
            return device_log.split("\n")
        else:
            return device_log

    # ----------------------------------
    # wlan methods
    # ----------------------------------
    def set_wlan(self, wlan_index: int, new_enable: bool = False):
        """
        Set WLAN to ON/OFF

        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
        """
        if self.debug_log:
            self.logger.debug(f"set_wlan called: wlan_index={wlan_index}, new_enable={new_enable}")

        # self.client.LANDevice.WLANConfiguration[wlan_index].SetEnable(NewEnable=int(new_enable))
        response = self._set_fritz_device('set_wlan', f"NewEnable='{int(new_enable)}'", wlan_index)

        # check if remaining time is set as item
        self.set_wlan_time_remaining(wlan_index)

        return response

    def set_wlan_time_remaining(self, wlan_index: int):
        """look for item and set time remaining"""
        for item in self.items:  # search for guest time remaining item.
            if self.items[item][0] == 'wlan_guest_time_remaining' and self.items[item][1] == wlan_index:
                data = self._poll_fritz_device('wlan_guest_time_remaining', wlan_index, enforce_read=True)
                if data is not None:
                    item(data, self._plugin_instance.get_fullname())

    def get_wlan(self, wlan_index: int):
        """
        Get WLAN ON/OFF State

        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
        """
        if self.debug_log:
            self.logger.debug(f"get_wlan called: wlan_index={wlan_index}")

        return self._poll_fritz_device('wlanconfig', wlan_index, enforce_read=True)

    def get_wlan_devices(self, wlan_index: int = 0):
        """Get all WLAN Devices connected to AVM-Device"""
        # wlandevice_url = self.client.LANDevice.WLANConfiguration[wlan_index].X_AVM_DE_GetWLANDeviceListPath()['NewX_AVM_DE_WLANDeviceListPath']
        wlandevice_url = self._poll_fritz_device('wlandevice_url', wlan_index, enforce_read=True)

        if not wlandevice_url:
            return

        url = f"{self._build_url()}{wlandevice_url}"
        wlandevices_xml = request_response_to_xml(self._request(url, self._timeout, self.verify))
        if wlandevices_xml is None:
            return

        return lxml_element_to_dict(wlandevices_xml)

    def set_wps(self, wlan_index: int, wps_enable: bool = False):
        """
        Sets WPS at AVM device ON/OFF

        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
        """
        if self.debug_log:
            self.logger.debug(f"set_wps called: wlan_index={wlan_index}, wps_enable={wps_enable}")

        # self.client.LANDevice.WLANConfiguration[wlan_index].X_AVM_DE_SetWPSEnable(NewX_AVM_DE_WPSEnable=int(wps_enable))
        return self._set_fritz_device('set_wps', f"NewX_AVM_DE_WPSEnable='{int(wps_enable)}'", wlan_index)

    def get_wps(self, wlan_index: int):
        """
        Get WPS state

        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
        """
        if self.debug_log:
            self.logger.debug(f"get_wps called: wlan_index={wlan_index}")

        status = self._poll_fritz_device('wps_status', wlan_index, enforce_read=True)

        return status == 'active'

    # ----------------------------------
    # tam methods
    # ----------------------------------
    def set_tam(self, tam_index: int = 0, new_enable: bool = False):
        """
        Set TAM

        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_tam.pdf
        """
        # self.client.InternetGatewayDevice.X_AVM_DE_TAM.SetEnable(NewIndex=tam_index, NewEnable=int(new_enable))
        return self._set_fritz_device('set_tam', f"NewIndex={tam_index}, NewEnable='{int(new_enable)}'")

    def get_tam(self, tam_index: int = 0):
        """
        Get TAM

        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_tam.pdf
        """
        # return self.client.InternetGatewayDevice.X_AVM_DE_TAM.GetInfo(NewIndex=tam_index)['NewEnable']
        return self._poll_fritz_device('tam', tam_index, enforce_read=True)

    def get_tam_list(self, tam_index: int = 0):
        """
        Get TAM Message list

        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_tam.pdf
        """
        # tamlist_url = self.client.InternetGatewayDevice.X_AVM_DE_TAM.GetMessageList(NewIndex=tam_index)['NewURL']
        tamlist_url = to_str(self._poll_fritz_device('tamlist_url', tam_index, enforce_read=True))

        if tamlist_url:
            return request_response_to_xml(self._request(tamlist_url, self._timeout, self.verify))

    def get_tam_message_count(self, index: int = 0, count_type: str = ''):
        """Return count to tam messages"""
        tam_list = self.get_tam_list(index)
        total_count = 0
        new_count = 0

        if tam_list is not None:
            for root in tam_list.iter('Root'):
                for message in root.iter('Message'):
                    for new in message.findall('.//New'):
                        if new.text:
                            total_count += 1
                            if new.text.strip() == '1':
                                new_count += 1

        if count_type == 'total':
            return total_count
        elif count_type == 'new':
            return new_count
        elif count_type == 'old':
            return total_count - new_count
        else:
            return total_count, new_count

    # ----------------------------------
    # set home automation switch
    # ----------------------------------
    def set_aha_device(self, ain: str = '', set_switch: bool = False):
        """Set AHA-Device via TR-064 protocol"""
        # SwitchState: OFF, ON, TOGGLE, UNDEFINED
        switch_state = "OFF"
        if set_switch:
            switch_state = "ON"

        # self.client.InternetGatewayDevice.X_AVM_DE_Homeauto.SetSwitch(NewAIN=ain, NewSwitchState=switch_state)
        return self._set_fritz_device('set_aha_device', f"NewAIN={ain}, NewSwitchState='{switch_state}'")

    # ----------------------------------
    # deflection
    # ----------------------------------
    def set_deflection(self, deflection_id: int = 0, new_enable: bool = False):
        """
        Enable or disable a deflection.
        DeflectionID is in the range of 0 .. NumberOfDeflections-1
        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf

        :param deflection_id: deflection id (default: 0)
        :param new_enable: new enable (default: False)
        """
        # self.client.InternetGatewayDevice.X_AVM_DE_OnTel.SetDeflectionEnable(NewDeflectionId=deflection_id, NewEnable=int(new_enable))
        return self._set_fritz_device('set_deflection', f"NewDeflectionId='{deflection_id}', NewEnable='{int(new_enable)}'")

    def get_deflection(self, deflection_id: int = 0):
        """Get Deflection state of deflection_id"""
        # return self.client.InternetGatewayDevice.X_AVM_DE_OnTel.GetDeflection(NewDeflectionId=deflection_id)['NewEnable']
        return self._poll_fritz_device('deflection_enable', deflection_id, enforce_read=True)

    def get_number_of_deflections(self):
        """Get number of deflections """
        # return self.client.InternetGatewayDevice.X_AVM_DE_OnTel.GetNumberOfDeflections()['NewNumberOfDeflections']
        return self._poll_fritz_device('number_of_deflections', enforce_read=True)

    def get_deflections(self):
        """Get deflections as dict"""
        # return self.client.InternetGatewayDevice.X_AVM_DE_OnTel.GetDeflections()['NewDeflectionList']
        return self._poll_fritz_device('deflections_details', enforce_read=True)

    # ----------------------------------
    # Host
    # ----------------------------------
    def is_host_active(self, mac_address: str) -> bool:
        """
        Checks if a MAC address is active on the FritzDevice, e.g. the status can be used for simple presence detection

        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf
        | Also reference: https://blog.pregos.info/2015/11/07/anwesenheitserkennung-fuer-smarthome-mit-der-fritzbox-via-tr-064/

        :param: MAC address of the host
        :return: True or False, depending if the host is active on the FritzDevice
        """
        # is_active = self.client.LANDevice.Hosts.GetSpecificHostEntry(NewMACAddress=mac_address)['NewActive']
        return bool(self._poll_fritz_device('is_host_active', mac_address, enforce_read=True))

    def get_hosts(self, only_active: bool = False) -> list:
        """
        Gets the information (host details) of all hosts as an array of dicts

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param only_active: bool, if only active hosts shall be returned
        :return: Array host dicts (see get_host_details)
        """
        # number_of_hosts = int(self.client.LANDevice.Hosts.GetHostNumberOfEntries()['NewHostNumberOfEntries'])
        number_of_hosts = to_int(self._poll_fritz_device('number_of_hosts', enforce_read=True))

        hosts = []
        for i in range(1, number_of_hosts):
            host = self.get_host_details(i)
            if not host:
                continue
            if not only_active or host['is_active']:
                hosts.append(host)
        return hosts

    def get_host_details(self, index: int):
        """
        Gets the information of a hosts at a specific index

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param index: index of host in hosts list
        :return: Dict host data: name, interface_type, ip_address, address_source, mac_address, is_active, lease_time_remaining
        """
        # host_info = self.client.LANDevice.Hosts.GetGenericHostEntry(NewIndex=index)
        host_info = self._poll_fritz_device('host_info', index, enforce_read=True)

        if host_info is None:
            return
        elif isinstance(host_info, int):
            self.logger.info(f"Error {host_info} '{self.ERROR_CODES.get(host_info)}' occurred during getting details of host #{index}.")
            return
        elif isinstance(host_info, dict) and len(host_info) == 7:
            host = {
                'name': host_info.get('NewHostName'),
                'interface_type': host_info.get('NewInterfaceType'),
                'ip_address': host_info.get('NewIPAddress'),
                'address_source': host_info.get('NewAddressSource'),
                'mac_address': host_info.get('NewMACAddress'),
                'is_active': bool(host_info.get('NewActive')),
                'lease_time_remaining': to_int(host_info.get('NewLeaseTimeRemaining'))
            }
            return host

    def get_hosts_dict(self) -> Union[dict, None]:
        """Get all Hosts connected to AVM device as dict"""
        # hosts_url = self.client.LANDevice.Hosts.X_AVM_DE_GetHostListPath()['NewX_AVM_DE_HostListPath']
        hosts_url = self._poll_fritz_device('hosts_url', enforce_read=True)

        if not hosts_url:
            return

        url = self._build_url() + str(hosts_url)

        hosts_xml = request_response_to_xml(self._request(url, self._timeout, self.verify))

        hosts_dict = {}
        for item in hosts_xml:
            host_dict = {}
            index = None
            for attr in item:
                if attr.tag == 'Index':
                    index = int(attr.text)
                key = str(attr.tag)
                value = str(attr.text)
                if key.startswith('X_AVM-DE_'):
                    key = key[9:]
                if value.isdigit():
                    value = int(value)
                if key in ['Active', 'Guest', 'Disallow', 'UpdateAvailable', 'VPN']:
                    value = bool(value)
                host_dict[key] = value
            if index:
                hosts_dict[index] = host_dict

        return hosts_dict

    def get_hosts_count(self) -> int:
        """Returns count of hosts"""
        try:
            return len(self.get_hosts_dict())
        except TypeError:
            return 0

    def get_mesh_topology(self) -> Union[dict, None]:
        """Get mesh topology information as dict"""
        # mesh_url = self.client.LANDevice.Hosts.X_AVM_DE_GetMeshListPath()['NewX_AVM_DE_MeshListPath']
        mesh_url = self._poll_fritz_device('mesh_url', enforce_read=True)

        if not mesh_url:
            return

        url = self._build_url() + str(mesh_url)
        mesh_response = self._request(url, self._timeout, self.verify)

        if mesh_response:
            try:
                mesh = mesh_response.json()
            except Exception:
                mesh = None

            return mesh


class FritzHome:
    """
    Fritzhome object to communicate with the device via AHA-HTTP Interface.
    """
    """
    Definition of AHA Routes
    """
    LOGIN_ROUTE = '/login_sid.lua?version=2'
    LOG_ROUTE = '/query.lua?mq_log=logger:status/log'
    LOG_SEPARATE_ROUTE = '/query.lua?mq_log=logger:status/log_separate'
    HOMEAUTO_ROUTE = '/webservices/homeautoswitch.lua'
    INTERNET_STATUS_ROUTE = '/internet/inetstat_monitor.lua?sid='

    def __init__(self, host, ssl, verify, user, password, log_entry_count, plugin_instance):
        """
        Init the Class FritzHome
        """
        self._plugin_instance = plugin_instance
        self.logger = self._plugin_instance.logger
        self.debug_log = self._plugin_instance.debug_log
        self.logger.debug("Init Fritzhome")

        self.host = host
        self.ssl = ssl
        self.verify = verify
        self.user = user
        self.password = password

        self._sid = None
        self._devices: Dict[str, FritzHome.FritzhomeDevice] = {}
        self._templates: Dict[str, FritzHome.FritzhomeTemplate] = {}
        self._logged_in = False
        self._session = requests.Session()
        self.items = dict()
        self.connected = False
        self.last_request = None
        self.log_entry_count = log_entry_count

        # Login
        self.login()

    def register_item(self, item, item_config: dict):
        """
        Parsed items valid fpr that class will be registered
        """
        # handle aha items
        index = self._get_item_ain(item)
        if index:
            self.logger.debug(f"Item {item.path()} with avm device attribute and defined avm_ain={index} found; append to list.")
        else:
            self.logger.warning(f"Item {item.path()} with avm attribute found, but 'avm_ain' is not defined; Item will be ignored.")
            return

        # update item config
        item_config.update({'interface': 'aha', 'index': index})

        # register item
        self.items[item] = item_config

    def unregister_item(self, item):
        """ remove item from instance """
        try:
            del self.items[item]
        except KeyError:
            pass

    def cyclic_item_update(self, read_all: bool = False):
        """
        Update smarthome item values using information from dict '_aha_devices'
        """
        if not self._logged_in:
            self.logger.warning("No connection to FritzDevice via AHA-HTTP-Interface. No update of item values possible.")
            return

        # first update aha device data
        if not self.update_devices():
            self.logger.warning("Update of AHA-Devices not successful. No update of item values possible.")
            return

        # get current_time
        current_time = int(time.time())

        # iterate over items and get data
        for item in self.items:
            # get item config
            item_config = self.items[item]
            avm_data_type = item_config['avm_data_type']
            ain = item_config['index']
            cycle = item_config['avm_data_cycle']
            next_time = item_config['next_update']

            # Just read items with cycle == 0 at init
            if not read_all and not cycle:
                # self.logger.debug(f"Item={item.path()} just read at init. No further update.")
                continue

            # check if item is already due
            if next_time > current_time:
                # self.logger.debug(f"Item={item.path()} is not due, yet.")
                continue

            self.logger.debug(f"Item={item.path()} with avm_data_type={avm_data_type} and ain={ain} will be updated")

            # Attributes that are write-only commands with no corresponding read commands are excluded from status updates via update black list:
            update_black_list = ALL_ATTRIBUTES_WRITEONLY
            if avm_data_type in update_black_list:
                self.logger.info(f"avm_data_type '{avm_data_type}' is in update blacklist. Item will not be updated")
                continue

            # Remove "set_" prefix to set corresponding r/o or r/w item to returned value:
            if avm_data_type.startswith('set_'):
                avm_data_type = avm_data_type[len('set_'):]

            # get value
            value = self.get_value_by_ain_and_avm_data_type(ain, avm_data_type)
            if value is None:
                self.logger.debug(f'Value for attribute={avm_data_type} at device with AIN={ain} to set Item={item.path()} is not available/None.')
                continue

            # set item
            item(value, self._plugin_instance.get_fullname())

            # set next due date
            self.items[item].update({'next_update': current_time + cycle})

    def handle_updated_item(self, item, avm_data_type: str, readafterwrite: int):
        """
        Updated Item will be processed and value communicated to AVM Device
        """
        # define set method per avm_data_type
        _dispatcher = {'window_open':        (self.set_window_open, self.get_window_open),
                       'target_temperature': (self.set_target_temperature, self.get_target_temperature),
                       'hkr_boost':          (self.set_boost, self.get_boost),
                       'simpleonoff':        (self.set_state, self.get_state),
                       'level':              (self.set_level, self.get_level),
                       'levelpercentage':    (self.set_level_percentage, self.get_level_percentage),
                       'switch_state':       (self.set_switch_state, self.get_switch_state),
                       'switch_toggle':      (self.set_switch_state_toggle, self.get_switch_state),
                       'colortemperature':   (self.set_color_temp, self.get_color_temp),
                       'hue':                (self.set_color_discrete, self.get_hue),
                       }

        # get AIN
        _ain = self.items[item]['index']

        # adapt avm_data_type by removing 'set_'
        if avm_data_type.startswith('set_'):
            avm_data_type = avm_data_type[4:]

        # logs message for upcoming/limited functionality
        if avm_data_type == 'hue' or avm_data_type == 'saturation':
            # Full RGB hue will be supported by Fritzbox approximately from Q2 2022 on:
            # Currently, only use default RGB colors that are supported by default (getcolordefaults)
            # These default colors have given saturation values.
            self.logger.info("Full RGB hue will be supported by Fritzbox approximately from Q2 2022. Limited functionality.")

        # Call set method per avm_data_type
        to_be_set_value = item()
        try:
            _dispatcher[avm_data_type][0](_ain, to_be_set_value)
        except KeyError:
            self.logger.error(f"{avm_data_type} is not defined to be updated.")

        # handle readafterwrite
        if readafterwrite:
            wait = float(readafterwrite)
            time.sleep(wait)
            try:
                set_value = _dispatcher[avm_data_type][1](_ain)
            # only handle avm_data_type not present in _dispatcher
            except KeyError:
                self.logger.error(f"{avm_data_type} is not defined to be read.")
            else:
                item(set_value, self._plugin_instance.get_fullname())
                if set_value != to_be_set_value:
                    self.logger.warning(f"Setting AVM Device defined in Item={item.path()} with avm_data_type={avm_data_type} to value={to_be_set_value} FAILED!")
                else:
                    if self.debug_log:
                        self.logger.debug(f"Setting AVM Device defined in Item={item.path()} with avm_data_type={avm_data_type} to value={to_be_set_value} successful!")

    def get_value_by_ain_and_avm_data_type(self, ain, avm_data_type):
        """
        get value for given ain and avm_data_type
        """

        # get device sub-dict from dict
        device = self.get_device_by_ain(ain)
        # device = self._devices.get(ain, None)

        if device is None:
            self.logger.warning(f'No values for device with AIN={ain} available.')
            return

        # return value
        return getattr(device, avm_data_type, None)

    def _get_item_ain(self, item) -> Union[str, None]:
        """
        Get AIN of device from item.conf
        """
        ain_device = None

        lookup_item = item
        for i in range(2):
            attribute = 'ain'
            ain_device = self._plugin_instance.get_iattr_value(lookup_item.conf, attribute)
            if ain_device:
                break
            else:
                lookup_item = lookup_item.return_parent()

        if ain_device:
            # deprecated warning for attribute 'ain'
            self.logger.warning(f"Item {item.path()} uses deprecated 'ain' attribute. Please consider to switch to 'avm_ain'.")
        else:
            lookup_item = item
            for i in range(2):
                attribute = 'avm_ain'
                ain_device = self._plugin_instance.get_iattr_value(lookup_item.conf, attribute)
                if ain_device is not None:
                    break
                else:
                    lookup_item = lookup_item.return_parent()

        if ain_device is None:
            self.logger.error(f'Device AIN for {item.path()} is not defined or instance not given')
            return None

        return ain_device

    def item_list(self):
        return list(self.items.keys())

    def _request(self, url: str, params=None, timeout: int = 10, result: str = 'text'):
        """
        Send a request with parameters.

        :param url:          URL to be requested
        :param params:       params for request
        :param timeout:      timeout
        :param result:       type of result
        :return:             request response
        """
        try:
            rsp = self._session.get(url, params=params, timeout=timeout, verify=self.verify)
        except Exception as e:
            self.logger.error(f"Error during GET request {e} occurred.")
        else:
            status_code = rsp.status_code
            if status_code == 200:
                if self.debug_log:
                    self.logger.debug("Sending HTTP request successful")
                if result == 'json':
                    try:
                        data = rsp.json()
                    except JSONDecodeError:
                        self.logger.error('Error occurred during parsing request response to json')
                    else:
                        return data
                else:
                    return rsp.text.strip()
            elif status_code == 403:
                if self.debug_log:
                    self.logger.debug("HTTP access denied. Try to get new Session ID.")
            else:
                self.logger.error(f"HTTP request error code: {status_code}")
                rsp.raise_for_status()
                if self.debug_log:
                    self.logger.debug(f"Url: {url}")
                    self.logger.debug(f"Params: {params}")

    def _login_request(self, username=None, challenge_response=None):
        """
        Send a login request with parameters.
        """
        url = self._get_prefixed_host() + self.LOGIN_ROUTE
        params = {}
        if username:
            params["username"] = username
        if challenge_response:
            params["response"] = challenge_response
        plain = self._request(url, params)
        dom = ElementTree.fromstring(to_str(plain))
        sid = dom.findtext("SID")
        challenge = dom.findtext("Challenge")
        blocktime = to_int(dom.findtext("BlockTime"))

        return sid, challenge, blocktime

    def _logout_request(self):
        """
        Send a logout request.
        """
        url = self._get_prefixed_host() + self.LOGIN_ROUTE
        params = {"logout": "1", "sid": self._sid}

        self._request(url, params)

    @staticmethod
    def _calculate_md5_response(challenge: str, password: str) -> str:
        """
        Calculate the response for a challenge using legacy MD5
        """
        response = challenge + "-" + password
        # the legacy response needs utf_16_le encoding
        response = response.encode("utf_16_le")
        md5_sum = hashlib.md5()
        md5_sum.update(response)
        response = challenge + "-" + md5_sum.hexdigest()
        return response

    @staticmethod
    def _calculate_pbkdf2_response(challenge: str, password: str) -> str:
        """
        Calculate the response for a given challenge via PBKDF2
        """
        challenge_parts = challenge.split("$")
        # Extract all necessary values encoded into the challenge
        iter1 = int(challenge_parts[1])
        salt1 = bytes.fromhex(challenge_parts[2])
        iter2 = int(challenge_parts[3])
        salt2 = bytes.fromhex(challenge_parts[4])
        # Hash twice, once with static salt...
        hash1 = hashlib.pbkdf2_hmac("sha256", password.encode(), salt1, iter1)
        # Once with dynamic salt.
        hash2 = hashlib.pbkdf2_hmac("sha256", hash1, salt2, iter2)
        return f"{challenge_parts[4]}${hash2.hex()}"

    def _aha_request(self, cmd, ain=None, param=None, rf='str'):
        """
        Send an AHA request.
        """
        url = self._get_prefixed_host() + self.HOMEAUTO_ROUTE
        params = {"switchcmd": cmd, "sid": self._sid}
        if param:
            params.update(param)
        if ain:
            params["ain"] = ain

        plain = self._request(url, params)

        if plain == "inval":
            self.logger.error("InvalidError")
            return

        if plain is None:
            self.logger.debug("Plain is None")
            return

        if rf == 'bool':
            return bool(plain)
        elif rf == 'str':
            return str(plain)
        elif rf == 'int':
            return int(plain)
        elif rf == 'float':
            return float(plain)
        else:
            return plain

    def login(self):
        """Login and get a valid session ID."""
        self.logger.debug("AHA login called")
        try:
            (sid, challenge, blocktime) = self._login_request()
            if blocktime > 0:
                self.logger.debug(f"Waiting for {blocktime} seconds...")
                time.sleep(blocktime)

            if sid == "0000000000000000":
                if challenge.startswith('2$'):
                    self.logger.debug("PBKDF2 supported")
                    challenge_response = self._calculate_pbkdf2_response(challenge, self.password)
                else:
                    self.logger.debug("Falling back to MD5")
                    challenge_response = self._calculate_md5_response(challenge, self.password)
                (sid2, challenge, blocktime) = self._login_request(username=self.user, challenge_response=challenge_response)
                if sid2 == "0000000000000000":
                    self.logger.warning(f"login failed {sid2}")
                    self.logger.error(f"LoginError for User {self.user}")
                    return
                self._sid = sid2
        except Exception as e:
            self.logger.error(f"LoginError {e} occurred for User {self.user}")
        else:
            self._logged_in = True

    def logout(self):
        """
        Logout.
        """
        self.logger.debug("AHA logout called")
        self._logout_request()
        self._sid = None
        self._logged_in = False

    def check_sid(self):
        """
        Check if known Session ID is still valid
        """
        self.logger.debug("check_sid called")
        url = self._get_prefixed_host() + self.LOGIN_ROUTE
        params = {"sid": self._sid}
        plain = self._request(url, params)
        dom = ElementTree.fromstring(to_str(plain))
        sid = dom.findtext("SID")

        if sid == "0000000000000000":
            self.logger.warning("Session ID is invalid. Try to generate new one.")
            self.login()
        else:
            self.logger.info("Session ID is still valid.")

    def _get_prefixed_host(self):
        """
        Choose the correct protocol prefix for the host.

        Supports three input formats:
        - https://<host>(requests use strict certificate validation by default)
        - http://<host> (unecrypted)
        - <host> (unencrypted)
        """
        host = self.host
        if not host.startswith("https://") and not host.startswith("http://"):
            if self.ssl:
                host = "https://" + host
            else:
                host = "http://" + host
        return host

    # device-related commands

    def update_devices(self):
        """
        Updating AHA Devices respective dictionary
        """

        self.logger.info("Updating AHA Devices ...")
        elements = self.get_device_elements()

        if elements is None:
            return False

        for element in elements:
            if element.attrib["identifier"] in self._devices.keys():
                self.logger.debug("Updating already existing Device " + element.attrib["identifier"])
                self._devices[element.attrib["identifier"]].update_from_node(element)
            else:
                self.logger.info("Adding new Device " + element.attrib["identifier"])
                device = FritzHome.FritzhomeDevice(self, node=element)
                self._devices[device.ain] = device
        return True

    def _get_listinfo_elements(self, entity_type):
        """
        Get the DOM elements for the entity list.
        """
        plain = self._aha_request("get" + entity_type + "listinfos")

        if plain is None:
            return
        self.last_request = to_str(plain)
        dom = ElementTree.fromstring(to_str(plain))
        return dom.findall(entity_type)

    def get_device_elements(self):
        """
        Get the DOM elements for the device list.
        """
        return self._get_listinfo_elements("device")

    def get_device_element(self, ain):
        """
        Get the DOM element for the specified device.
        """
        elements = self.get_device_elements()
        try:
            for element in elements:
                if element.attrib["identifier"] == ain:
                    return element
        except TypeError:
            pass
        return None

    def get_devices(self):
        """
        Get the list of all known devices.
        """
        return list(self.get_devices_as_dict().values())

    def get_devices_as_dict(self):
        """
        Get the list of all known devices.
        """
        self.logger.debug("get_devices_as_dict called and forces update_devices")
        if not self._devices:
            self.update_devices()
        return self._devices

    def get_device_by_ain(self, ain):
        """
        Return a device specified by the AIN.
        """
        return self.get_devices_as_dict().get(ain)

    def get_device_present(self, ain):
        """
        Get the device presence.
        """
        return self._aha_request("getswitchpresent", ain=ain, rf='bool')

    def get_device_name(self, ain):
        """
        Get the device name.
        """
        return self._aha_request("getswitchname", ain=ain)

    # switch-related commands

    def get_switch_state(self, ain):
        """
        Get the switch state.
        """
        return self._aha_request("getswitchstate", ain=ain, rf='bool')

    def set_switch_state_on(self, ain):
        """
        Set the switch to on state.
        """
        return self._aha_request("setswitchon", ain=ain, rf='bool')

    def set_switch_state_off(self, ain):
        """
        Set the switch to off state.
        """
        return self._aha_request("setswitchoff", ain=ain, rf='bool')

    def set_switch_state_toggle(self, ain):
        """
        Toggle the switch state.
        """
        return self._aha_request("setswitchtoggle", ain=ain, rf='bool')

    def set_switch_state(self, ain, state):
        """
        Set the switch to on state.
        """
        if state:
            return self.set_switch_state_on(ain)
        else:
            return self.set_switch_state_off(ain)

    def get_switch_power(self, ain):
        """
        Get the switch power consumption in W.
        """
        value = self._aha_request("getswitchpower", ain=ain, rf='int')
        try:
            return value / 1000  # value in 0.001W
        except TypeError:
            pass

    def get_switch_energy(self, ain):
        """
        Get the switch energy in Wh.
        """
        return self._aha_request("getswitchenergy", ain=ain, rf='int')

    # thermostat-related commands

    def get_temperature(self, ain):
        """
        Get the device temperature sensor value.
        """
        value = self._aha_request("gettemperature", ain=ain, rf='int')
        try:
            return value / 10.0
        except TypeError:
            pass

    def _get_temperature(self, ain, name):
        """
        Get temperature raw value
        """
        plain = to_int(self._aha_request(name, ain=ain, rf='int'))
        return (plain - 16) / 2 + 8

    def get_target_temperature(self, ain):
        """
        Get the thermostate target temperature.
        """
        return self._get_temperature(ain, "gethkrtsoll")

    def set_target_temperature(self, ain, temperature):
        """
        Set the thermostate target temperature.
        """
        temp = int(16 + ((float(temperature) - 8) * 2))

        if temp < min(range(16, 56)):
            temp = 253
        elif (temp > max(range(16, 56))) and (temp != 253):
            temp = 254

        self._aha_request("sethkrtsoll", ain=ain, param={'param': temp})

    def set_window_open(self, ain, seconds):
        """
        Set windows open.
        """
        endtimestamp = -1
        if isinstance(seconds, bool):
            endtimestamp = 0
            if seconds:
                endtimestamp = int(time.time() + 43200)
        elif isinstance(seconds, int):
            endtimestamp = 0
            if seconds > 0:
                endtimestamp = int(time.time() + seconds)
        if endtimestamp >= 0:
            self._aha_request("sethkrwindowopen", ain=ain, param={'endtimestamp': endtimestamp})

    @NoAttributeError
    def get_window_open(self, ain):
        """
        Get windows open.
        """
        return self.get_devices_as_dict()[ain].window_open

    def set_boost(self, ain, seconds):
        """
        Set the thermostate to boost.
        """
        endtimestamp = -1
        if isinstance(seconds, bool):
            endtimestamp = 0
            if seconds:
                endtimestamp = int(time.time() + 43200)
        elif isinstance(seconds, int):
            endtimestamp = 0
            if seconds > 0:
                endtimestamp = int(time.time() + seconds)
        if endtimestamp >= 0:
            self._aha_request("sethkrboost", ain=ain, param={'endtimestamp': endtimestamp})

    @NoKeyOrAttributeError
    def get_boost(self, ain):
        """
        Get boost status.
        """
        return self.get_devices_as_dict()[ain].hkr_boost

    def get_comfort_temperature(self, ain):
        """
        Get the thermostate comfort temperature.
        """
        return self._get_temperature(ain, "gethkrkomfort")

    def get_eco_temperature(self, ain):
        """
        Get the thermostate eco temperature.
        """
        return self._get_temperature(ain, "gethkrabsenk")

    def get_device_statistics(self, ain):
        """
        Get device statistics.
        """
        return self._aha_request("getbasicdevicestats", ain=ain)

    # Switch-related commands

    def set_state_off(self, ain):
        """
        Set the switch/actuator/lightbulb to on state.
        """
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 0})

    def set_state_on(self, ain):
        """
        Set the switch/actuator/lightbulb to on state.
        """
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 1})

    def set_state_toggle(self, ain):
        """
        Toggle the switch/actuator/lightbulb state.
        """
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 2})

    def set_state(self, ain, state):
        """
        Set the switch/actuator/lightbulb to a state.
        """
        if state:
            self.set_state_on(ain)
        else:
            self.set_state_off(ain)

    @NoKeyOrAttributeError
    def get_state(self, ain):
        """
        Get the switch/actuator/lightbulb to a state.
        """
        return self.get_devices_as_dict()[ain].switch_state

    # Level/Dimmer-related commands

    def set_level(self, ain, level):
        """
        Set level/brightness/height in interval [0,255].
        """
        if level < 0:
            level = 0  # 0%
        elif level > 255:
            level = 255  # 100 %

        self._aha_request("setlevel", ain=ain, param={'level': int(level)})

    @NoKeyOrAttributeError
    def get_level(self, ain):
        """
        get level/brightness/height in interval [0,255].
        """
        return self.get_devices_as_dict()[ain].level

    def set_level_percentage(self, ain, level):
        """
        Set level/brightness/height in interval [0,100].
        """
        # Scale percentage to [0,255] interval
        self.set_level(ain, int(level * 2.55))

    @NoKeyOrAttributeError
    def get_level_percentage(self, ain):
        """
        get level/brightness/height in interval [0,100].
        """
        return self.get_devices_as_dict()[ain].levelpercentage

    # Color-related commands

    def _get_colordefaults(self, ain):
        """
        Get colour defaults
        """
        plain = self._aha_request("getcolordefaults", ain=ain)
        return ElementTree.fromstring(to_str(plain))

    def get_colors(self, ain):
        """
        Get colors (HSV-space) supported by this lightbulb.
        """
        colordefaults = self._get_colordefaults(ain)
        colors = {}
        for hs in colordefaults.iter('hs'):
            name = hs.find("name").text.strip()
            values = []
            for st in hs.iter("color"):
                values.append(
                    (
                        st.get("hue"),
                        st.get("sat"),
                        st.get("val")
                    )
                )
            colors[name] = values
        return colors

    def set_color(self, ain, hsv, duration=0, mapped=True):
        """
        Set hue and saturation.
        hsv: HUE colorspace element obtained from get_colors()
        duration: Speed of change in seconds, 0 = instant
        """
        params = {
            'hue': int(hsv[0]),
            'saturation': int(hsv[1]),
            "duration": int(duration) * 10
        }
        if mapped:
            self._aha_request("setcolor", ain=ain, param=params)
        else:
            # undocumented API method for free color selection
            self._aha_request("setunmappedcolor", ain=ain, param=params)

    def set_color_discrete(self, ain, hue, duration=0):
        """
        Set Led color to the closest discrete hue value. Currently, only those are supported for FritzDect500 RGB LED bulbs
        """
        if hue <= 20:
            # self.logger.debug(f'setcolor to red (hue={hue})')
            param = {'hue': 358, 'saturation': 180, 'duration': int(duration)}
        elif hue <= 45:
            # self.logger.debug(f'setcolor to orange (hue={hue})')
            param = {'hue': 35, 'saturation': 214, 'duration': int(duration)}
        elif hue <= 55:
            # self.logger.debug(f'setcolor to yellow (hue={hue})')
            param = {'hue': 52, 'saturation': 153, 'duration': int(duration)}
        elif hue <= 100:
            # self.logger.debug(f'setcolor to grasgreen (hue={hue})')
            param = {'hue': 92, 'saturation': 123, 'duration': int(duration)}
        elif hue <= 135:
            # self.logger.debug(f'setcolor to green (hue={hue})')
            param = {'hue': 120, 'saturation': 160, 'duration': int(duration)}
        elif hue <= 175:
            # self.logger.debug(f'setcolor to turquoise (hue={hue})')
            param = {'hue': 160, 'saturation': 145, 'duration': int(duration)}
        elif hue <= 210:
            # self.logger.debug(f'setcolor to cyan (hue={hue})')
            param = {'hue': 195, 'saturation': 179, 'duration': int(duration)}
        elif hue <= 240:
            # self.logger.debug(f'setcolor to blue (hue={hue})')
            param = {'hue': 225, 'saturation': 204, 'duration': int(duration)}
        elif hue <= 280:
            # self.logger.debug(f'setcolor to violett (hue={hue})')
            param = {'hue': 266, 'saturation': 169, 'duration': int(duration)}
        elif hue <= 310:
            # self.logger.debug(f'setcolor to magenta (hue={hue})')
            param = {'hue': 296, 'saturation': 140, 'duration': int(duration)}
        elif hue <= 350:
            # self.logger.debug(f'setcolor to pink (hue={hue})')
            param = {'hue': 335, 'saturation': 180, 'duration': int(duration)}
        elif hue <= 360:
            # self.logger.debug(f'setcolor to red (hue={hue})')
            param = {'hue': 358, 'saturation': 180, 'duration': int(duration)}
        else:
            self.logger.error(f'setcolor hue out of range (hue={hue})')
            return

        return self._aha_request("setcolor", ain=ain, param=param, rf='bool')

    @NoKeyOrAttributeError
    def get_hue(self, ain):
        """
        Get Hue value.
        """
        return self.get_devices_as_dict()[ain].hue

    def get_color_temps(self, ain):
        """
        Get temperatures supported by this lightbulb.
        """
        colordefaults = self._get_colordefaults(ain)
        temperatures = []
        for temp in colordefaults.iter('temp'):
            temperatures.append(temp.get("value"))
        return temperatures

    def set_color_temp(self, ain, temperature, duration=1):
        """
        Set color temperature.
        temperature: temperature element obtained from get_temperatures()
        duration: Speed of change in seconds, 0 = instant
        """
        params = {
            'temperature': int(temperature),
            'duration': int(duration) * 10
            }
        self._aha_request("setcolortemperature", ain=ain, param=params)

    @NoKeyOrAttributeError
    def get_color_temp(self, ain):
        """
        Get color temperature.
        """
        return self.get_devices_as_dict()[ain].colortemperature

    # Template-related commands

    def update_templates(self):
        """
        Update templates
        """
        self.logger.info("Updating Templates ...")
        if self._templates is None:
            self._templates = {}

        try:
            for element in self.get_template_elements():
                if element.attrib["identifier"] in self._templates.keys():
                    self.logger.info(f"Updating already existing Template {element.attrib['identifier']}")
                    self._templates[element.attrib["identifier"]]._update_from_node(element)
                else:
                    self.logger.info("Adding new Template " + element.attrib["identifier"])
                    template = FritzHome.FritzhomeTemplate(self, node=element)
                    self._templates[template.ain] = template
        except TypeError:
            pass
        return True

    def get_template_elements(self):
        """
        Get the DOM elements for the template list.
        """
        return self._get_listinfo_elements("template")

    def get_templates(self):
        """
        Get the list of all known templates.
        """
        return list(self.get_templates_as_dict().values())

    def get_templates_as_dict(self):
        """
        Get the list of all known templates.
        """
        if self._templates is None:
            self.update_templates()
        return self._templates

    @NoAttributeError
    def get_template_by_ain(self, ain):
        """
        Return a template specified by the AIN.
        """
        return self.get_templates_as_dict()[ain]

    def apply_template(self, ain):
        """
        Applies a template.
        """
        self._aha_request("applytemplate", ain=ain)

    # Log-related commands

    def get_device_log_from_lua(self):
        """
        Gets the Device Log from the LUA HTTP Interface via LUA Scripts (more complete than the get_device_log TR-064 version).

        :return: Array of Device Log Entries (text, type, category, timestamp, date, time)
        """
        if not self._logged_in:
            self.login()

        url = self._get_prefixed_host() + self.LOG_ROUTE
        params = {"sid": self._sid}

        # get data
        try:
            data = self._request(url, params, result='json')
        except JSONDecodeError:
            return

        if isinstance(data, dict):
            data = data.get('mq_log')
            if data and isinstance(data, list):
                # cut data if needed
                if self.log_entry_count:
                    data = data[:self.log_entry_count]

                # bring data to needed format
                newlog = []
                for text, typ, cat in data:
                    l_date = text[:8]
                    l_time = text[9:17]
                    l_text = text[18:]
                    l_cat = int(cat)
                    l_type = int(typ)
                    l_ts = int(datetime.datetime.timestamp(datetime.datetime.strptime(text[:17], '%d.%m.%y %H:%M:%S')))
                    newlog.append([l_text, l_type, l_cat, l_ts, l_date, l_time])
                return newlog

    def get_device_log_from_lua_separated(self):
        """
        Gets the Device Log from the LUA HTTP Interface via LUA Scripts (more complete than the get_device_log TR-064 version).

        :return: list of device logs list (datetime, log, type, category)
        """
        if not self._logged_in:
            self.login()

        url = self._get_prefixed_host() + self.LOG_SEPARATE_ROUTE
        params = {"sid": self._sid}

        try:
            data = self._request(url, params, result='json')
        except JSONDecodeError:
            return

        if isinstance(data, dict):
            data = data.get('mq_log')
            if data and isinstance(data, list):
                if self.log_entry_count:
                    data = data[:self.log_entry_count]

                # bring data to needed format
                data_formated = []
                for entry in data:
                    dt = datetime.datetime.strptime(f"{entry[0]} {entry[1]}", '%d.%m.%y %H:%M:%S').strftime('%d.%m.%Y %H:%M:%S')
                    data_formated.append([dt, entry[2], entry[3], entry[4]])
                return data_formated

    # FritzhomeDevice classes

    class FritzhomeDeviceFeatures(IntFlag):

        HANFUN_DEVICE = 0x0001  # Bit 0: HAN-FUN Gerät
        LIGHT = 0x0002  # Bit 2: Licht / Lampe
        ALARM = 0x0010  # Bit 4: Alarm-Sensor
        BUTTON = 0x0020  # Bit 5: AVM-Button
        THERMOSTAT = 0x0040  # Bit 6: Heizkörperregler
        POWER_METER = 0x0080  # Bit 7: Energie Messgerät
        TEMPERATURE = 0x0100  # Bit 8: Temperatursensor
        SWITCH = 0x0200  # Bit 9: Schaltsteckdose
        DECT_REPEATER = 0x0400  # Bit 10: AVM DECT Repeater
        MICROPHONE = 0x0800  # Bit 11: Mikrofon
        HANFUN = 0x2000  # Bit 13: HAN-FUN-Unit
        SWITCHABLE = 0x8000  # Bit 15: an-/ausschaltbares Gerät/Steckdose/Lampe/Aktor
        LEVEL = 0x10000  # Bit 16: Gerät mit einstellbarem Dimm-, Höhen- bzw. Niveau-Level
        COLOR = 0x20000  # Bit 17: Lampe mit einstellbarer Farbe/Farbtemperatur
        BLIND = 0x40000  # Bit 18: Rollladen(Blind) - hoch, runter, stop und level 0% bis 100%
        HUM_SENSOR = 0x100000  # Bit 20: Luftfeuchtigkeitssensor

        # FRITZ!DECT 100    FBM: 1280       -> 10100000000              -> bit 8, 10
        # FRITZ!DECT 200    FBM: 35712      -> 1000101110000000         -> bit 7, 8, 9, 11, 15
        # FRITZ!DECT 210    FBM: 35712      -> 1000101110000000         -> bit 7, 8, 9, 11, 15
        # FRITZ!DECT 300    FBM: 320        -> 101000000                -> bit 6, 8
        # FRITZ!DECT 301    FBM: 320        -> 101000000                -> bit 6, 8
        # Comet DECT        FBM: 320        -> 101000000                -> bit 6, 8
        # FRITZ!DECT 440    FBM: 1048864    -> 100000000000100100000    -> bit 5, 8, 20
        # FRITZ!DECT 500    FBM: 237572     -> 111010000000000100       -> bit 2, 13, 15, 16, 17

    class FritzhomeEntityBase(ABC):
        """The Fritzhome Entity class."""

        def __init__(self, fritz=None, node=None):
            # init logger
            self.logger = logging.getLogger(__name__)

            self._fritz = None
            self.ain = ''
            self._functionsbitmask = None
            self.device_functions = []

            if not fritz:
                raise RuntimeError(f'passed object fritz is type {type(fritz)}, not type FritzHome. Aborting.')
            else:
                self._fritz = fritz
            if node is not None:
                self._update_from_node(node)
                self.logger.debug(f'node="{node}"')
            if not self.device_functions:
                self._update_device_functions()

        def __repr__(self):
            """Return a string."""
            return f"{self.ain} {self.name}"

        def _has_feature(self, feature) -> bool:
            return feature in FritzHome.FritzhomeDeviceFeatures(self._functionsbitmask)

        def _update_from_node(self, node):
            self.ain = node.attrib["identifier"]
            self._functionsbitmask = int(node.attrib["functionbitmask"])
            self.name = node.findtext("name").strip()

        def _update_device_functions(self):
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.HANFUN_DEVICE):
                self.device_functions.append('hanfun_device')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.LIGHT):
                self.device_functions.append('light')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.ALARM):
                self.device_functions.append('alarm')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.BUTTON):
                self.device_functions.append('button')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.THERMOSTAT):
                self.device_functions.append('thermostat')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.POWER_METER):
                self.device_functions.append('powermeter')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.TEMPERATURE):
                self.device_functions.append('temperature_sensor')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.SWITCH):
                self.device_functions.append('switch')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.DECT_REPEATER):
                self.device_functions.append('repeater')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.MICROPHONE):
                self.device_functions.append('mic')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.HANFUN):
                self.device_functions.append('hanfun_unit')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.SWITCHABLE):
                self.device_functions.append('on_off_device')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.LEVEL):
                self.device_functions.append('dimmable_device')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.COLOR):
                self.device_functions.append('color_device')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.BLIND):
                self.device_functions.append('blind')
            if self._has_feature(FritzHome.FritzhomeDeviceFeatures.HUM_SENSOR):
                self.device_functions.append('humidity_sensor')

    class FritzhomeTemplate(FritzhomeEntityBase):
        """The Fritzhome Template class."""

        devices = None
        features = None
        apply_hkr_summer = None
        apply_hkr_temperature = None
        apply_hkr_holidays = None
        apply_hkr_time_table = None
        apply_relay_manual = None
        apply_relay_automatic = None
        apply_level = None
        apply_color = None
        apply_dialhelper = None

        def _update_from_node(self, node):
            super()._update_from_node(node)

            self.features = FritzHome.FritzhomeDeviceFeatures(self._functionsbitmask)

            applymask = node.find("applymask")
            self.apply_hkr_summer = applymask.find("hkr_summer") is not None
            self.apply_hkr_temperature = applymask.find("hkr_temperature") is not None
            self.apply_hkr_holidays = applymask.find("hkr_holidays") is not None
            self.apply_hkr_time_table = applymask.find("hkr_time_table") is not None
            self.apply_relay_manual = applymask.find("relay_manual") is not None
            self.apply_relay_automatic = applymask.find("relay_automatic") is not None
            self.apply_level = applymask.find("level") is not None
            self.apply_color = applymask.find("color") is not None
            self.apply_dialhelper = applymask.find("dialhelper") is not None

            self.devices = []
            for device in node.find("devices").findall("device"):
                self.devices.append(device.attrib["identifier"])

    class FritzhomeDeviceBase(FritzhomeEntityBase):
        """The Fritzhome Device class."""

        device_id = None
        fw_version = None
        manufacturer = None
        product_name = None
        connected = None
        device_name = None
        tx_busy = None
        battery_low = None
        battery_level = None

        def __repr__(self):
            """Return a string."""
            return f"{self.ain} {self.device_id} {self.manufacturer} {self.product_name} {self.device_name}"

        def update(self):
            """Update the device values."""
            self.logger.warning("update @ FritzhomeDeviceBase called")
            self._fritz.update_devices()

        def _update_from_node(self, node):
            super()._update_from_node(node)
            self.ain = node.attrib["identifier"]
            self.device_id = node.attrib["id"]
            self.fw_version = node.attrib["fwversion"]
            self.manufacturer = node.attrib["manufacturer"]
            self.product_name = node.attrib["productname"]

            self.device_name = node.findtext("name")
            self.connected = get_node_value_as_int_as_bool(node, "present")
            self.tx_busy = get_node_value_as_int_as_bool(node, "txbusy")

            try:
                self.battery_low = get_node_value_as_int_as_bool(node, "batterylow")
            except AttributeError:
                pass

            try:
                self.battery_level = get_node_value_as_int(node, "battery")
            except AttributeError:
                pass

        # General
        def get_present(self):
            """Check if the device is present."""
            return self._fritz.get_device_present(self.ain)

    class FritzhomeDeviceAlarm(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        alert_state = None
        last_alert_chgtimestamp = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_alarm():
                self._update_alarm_from_node(node)

        def has_alarm(self):
            """Check if the device has alarm function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.ALARM)

        def _update_alarm_from_node(self, node):
            alarm_element = node.find("alert")
            if alarm_element is not None:
                self.alert_state = get_node_value_as_int_as_bool(alarm_element, "state")
                self.last_alert_chgtimestamp = get_node_value_as_int(alarm_element, "lastalertchgtimestamp")

    class FritzhomeDeviceButton(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        battery_low = None
        battery_level = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_button():
                self._update_button_from_node(node)

        def has_button(self):
            """Check if the device has button function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.BUTTON)

        def _update_button_from_node(self, node):
            self.buttons = {}

            for element in node.findall("button"):
                button = FritzHome.FritzhomeButton(element)
                self.buttons[button.button_identifier] = button

            try:
                self.battery_low = get_node_value_as_int_as_bool(node, "batterylow")
            except AttributeError:
                pass

            try:
                self.battery_level = get_node_value_as_int(node, "battery")
            except AttributeError:
                pass

        def get_button_by_ain(self, ain):
            return self.buttons[ain]

    class FritzhomeButton(object):
        """The Fritzhome Button Device class."""

        # {'device_id': '17', 'fw_version': '05.21', 'product_name': 'FRITZ!DECT 440', 'manufacturer': 'AVM', 'device_functions': ['button', 'temperature_sensor'], 'batterylow': False, 'battery_level': 100, 'connected': False, 'tx_busy': False, 'device_name': 'Balkonzimmer',
        # 'button_1': {'button_identifier': '09995 0882724-1', 'id': '5000', 'name': 'Balkonzimmer: Oben rechts'}, 'button_2': {'button_identifier': '09995 0882724-3', 'id': '5001', 'name': 'Balkonzimmer: Unten rechts'}, 'button_3': {'button_identifier': '09995 0882724-5', 'id': '5002', 'name': 'Balkonzimmer: Unten links'}, 'button_4': {'button_identifier': '09995 0882724-7', 'id': '5003', 'name': 'Balkonzimmer: Oben links'}}

        button_identifier = None
        button_id = None
        button_name = None
        last_pressed = None

        def __init__(self, node=None):
            # init logger
            self.logger = logging.getLogger(__name__)

            if node is not None:
                self._update_from_node(node)

        def _update_from_node(self, node):

            self.button_identifier = node.attrib["identifier"]
            self.button_id = node.attrib["id"]

            self.button_name = get_node_value(node, "name")
            self.last_pressed = get_node_value(node, "lastpressedtimestamp")

        @staticmethod
        def get_node_value(elem, node):
            return elem.findtext(node)

    class FritzhomeDeviceLightBulb(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

        @property
        def has_light(self):
            """Check if the device has LightBulb function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.LIGHT)

    class FritzhomeDevicePowermeter(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        power = None
        energy = None
        voltage = None
        current = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_powermeter:
                self._update_powermeter_from_node(node)

        @property
        def has_powermeter(self):
            """Check if the device has powermeter function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.POWER_METER)

        def _update_powermeter_from_node(self, node):
            powermeter_element = node.find("powermeter")

            if powermeter_element is not None:
                self.power = get_node_value_as_float_1000(powermeter_element, "power")  # raw value in 0.001W
                self.voltage = get_node_value_as_float_1000(powermeter_element, "voltage")  # raw value in 0.001V
                self.energy = get_node_value_as_int(powermeter_element, "energy")   # raw value in 1Wh

                if self.power and self.voltage:
                    self.current = round(self.power / self.voltage, 1)  # value in A
                else:
                    self.current = 0.0

        def get_switch_power(self):
            """The switch state."""
            return self._fritz.get_switch_power(self.ain)

        def get_switch_energy(self):
            """Get the switch energy."""
            return self._fritz.get_switch_energy(self.ain)

    class FritzhomeDeviceRepeater(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

        def has_repeater(self):
            """Check if the device has repeater function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.DECT_REPEATER)

    class FritzhomeDeviceSwitch(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        switch_state = None
        switch_mode = None
        lock = None
        device_lock = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_switch():
                self._update_switch_from_node(node)

        def has_switch(self):
            """Check if the device has switch function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.SWITCH)

        def _update_switch_from_node(self, node):
            switch_element = node.find("switch")

            if switch_element is not None:
                self.switch_state = get_node_value_as_int_as_bool(switch_element, "state")
                self.switch_mode = get_node_value(switch_element, "mode")
                self.lock = get_node_value_as_int_as_bool(switch_element, "lock")
                self.device_lock = get_node_value_as_int_as_bool(switch_element, "devicelock")

        def get_switch_state(self):
            """Get the switch state."""
            return self._fritz.get_switch_state(self.ain)

        def set_switch_state_on(self):
            """Set the switch state to on."""
            return self._fritz.set_switch_state_on(self.ain)

        def set_switch_state_off(self):
            """Set the switch state to off."""
            return self._fritz.set_switch_state_off(self.ain)

        def set_switch_state_toggle(self):
            """Toggle the switch state."""
            return self._fritz.set_switch_state_toggle(self.ain)

    class FritzhomeDeviceTemperature(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        temperature_offset = None
        current_temperature = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_temperature_sensor():
                self._update_temperature_from_node(node)

        def has_temperature_sensor(self):
            """Check if the device has temperature function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.TEMPERATURE)

        def _update_temperature_from_node(self, node):
            temperature_element = node.find("temperature")
            if temperature_element is not None:
                self.temperature_offset = get_node_value_as_float_10(temperature_element, "offset")  # value in 0.1 °C
                self.current_temperature = get_node_value_as_float_10(temperature_element, "celsius")  # value in 0.1 °C

        def get_temperature(self):
            """Get the device temperature value."""
            return self._fritz.get_temperature(self.ain)

    class FritzhomeDeviceThermostat(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        current_temperature = None
        target_temperature = None
        temperature_reduced = None
        temperature_comfort = None
        device_lock = None
        lock = None
        errorcode = None
        battery_low = None
        battery_level = None
        window_open = None
        summer_active = None
        holiday_active = None
        nextchange_endperiod = None
        nextchange_temperature = None
        hkr_boost = None
        windowopenactiveendtime = None
        boostactiveendtime = None
        adaptiveHeatingActive = None
        adaptiveHeatingRunning = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_thermostat():
                self._update_hkr_from_node(node)

        def has_thermostat(self):
            """Check if the device has thermostat function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.THERMOSTAT)

        def _update_hkr_from_node(self, node):
            hkr_element = node.find("hkr")
            if hkr_element is not None:
                self.current_temperature = get_temp_from_node(hkr_element, "tist")
                self.target_temperature = get_temp_from_node(hkr_element, "tsoll")
                self.temperature_comfort = get_temp_from_node(hkr_element, "komfort")
                self.temperature_reduced = get_temp_from_node(hkr_element, "absenk")
                self.battery_low = get_node_value_as_int_as_bool(hkr_element, "batterylow")
                self.battery_level = get_node_value_as_int(hkr_element, "battery")
                self.window_open = get_node_value_as_int_as_bool(hkr_element, "windowopenactiv")
                self.windowopenactiveendtime = get_node_value_as_int(hkr_element, "windowopenactiveendtime")
                self.hkr_boost = get_node_value_as_int_as_bool(hkr_element, "boostactive")
                self.boostactiveendtime = get_node_value_as_int(hkr_element, "boostactiveendtime")
                self.adaptiveHeatingActive = get_node_value_as_int_as_bool(hkr_element, "adaptiveHeatingActive")
                self.adaptiveHeatingRunning = get_node_value_as_int(hkr_element, "adaptiveHeatingRunning")
                self.holiday_active = get_node_value_as_int_as_bool(hkr_element, "holidayactive")
                self.summer_active = get_node_value_as_int_as_bool(hkr_element, "summeractive")
                self.lock = get_node_value_as_int_as_bool(hkr_element, "lock")
                self.device_lock = get_node_value_as_int_as_bool(hkr_element, "devicelock")
                self.errorcode = get_node_value_as_int(hkr_element, "errorcode")

            nextchange_element = hkr_element.find("nextchange")
            if nextchange_element:
                self.nextchange_endperiod = get_node_value_as_int(nextchange_element, "endperiod")
                self.nextchange_temperature = get_temp_from_node(nextchange_element, "tchange")

        def get_temperature(self):
            """Get the device temperature value."""
            return self._fritz.get_temperature(self.ain)

        def get_target_temperature(self):
            """Get the thermostate target temperature."""
            return self._fritz.get_target_temperature(self.ain)

        def set_target_temperature(self, temperature):
            """Set the thermostate target temperature."""
            return self._fritz.set_target_temperature(self.ain, temperature)

        def set_window_open(self, seconds):
            """Set the thermostate to window open."""
            return self._fritz.set_window_open(self.ain, seconds)

        def set_boost(self, seconds):
            """Set the thermostate to window open."""
            return self._fritz.set_boost(self.ain, seconds)

        def get_comfort_temperature(self):
            """Get the thermostate comfort temperature."""
            return self._fritz.get_comfort_temperature(self.ain)

        def get_eco_temperature(self):
            """Get the thermostate eco temperature."""
            return self._fritz.get_eco_temperature(self.ain)

        def get_hkr_state(self):
            """Get the thermostate state."""
            return {126.5: "off",
                    127.0: "on",
                    self.temperature_reduced: "eco",
                    self.temperature_comfort: "comfort",
                    }.get(self.target_temperature, "manual")

        def set_hkr_state(self, state):
            """Set the state of the thermostat.
            Possible values for state are: 'on', 'off', 'comfort', 'eco'.
            """
            value = {"off": 0,
                     "on": 100,
                     "eco": self.temperature_reduced,
                     "comfort": self.temperature_comfort,
                     }.get(state)

            # check for None as value can be 0
            if value is not None:
                self.set_target_temperature(value)

    class FritzhomeDeviceBlind(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        blind_mode = None
        endpositionsset = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_blind():
                self._update_blind_from_node(node)

        def has_blind(self):
            """Check if the device has blind function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.BLIND)

        def _update_blind_from_node(self, node):

            blind_element = node.find("blind")

            if blind_element:
                self.endpositionsset = get_node_value_as_int_as_bool(blind_element, "endpositionsset")
                self.blind_mode = get_node_value(blind_element, "mode")

        def set_blind_open(self):
            """Open the blind."""
            self._fritz.set_blind_open(self.ain)

        def set_blind_close(self):
            """Close the blind."""
            self._fritz.set_blind_close(self.ain)

        def set_blind_stop(self):
            """Stop the blind."""
            self._fritz.set_blind_stop(self.ain)

    class FritzhomeDeviceSwitchable(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        simpleonoff = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                self.simpleonoff = False
                return

            if self.has_switchable():
                self._update_switchable_from_node(node)

        def has_switchable(self):
            """Check if the device has switch function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.SWITCHABLE)

        def _update_switchable_from_node(self, node):
            state_element = node.find("simpleonoff")

            if state_element:
                self.simpleonoff = get_node_value_as_int_as_bool(state_element, "state")

        def set_state_off(self):
            """Switch light bulb off."""
            self.simpleonoff = False
            self._fritz.set_state_off(self.ain)

        def set_state_on(self):
            """Switch light bulb on."""
            self.simpleonoff = True
            self._fritz.set_state_on(self.ain)

        def set_state_toggle(self):
            """Toggle light bulb state."""
            self.simpleonoff = not self.simpleonoff
            self._fritz.set_state_toggle(self.ain)

    class FritzhomeDeviceDimmable(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        level = None
        levelpercentage = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                self.level = 0
                self.levelpercentage = 0
                return

            if self.has_level():
                self._update_level_from_node(node)

        def has_level(self):
            """Check if the device has dimmer function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.LEVEL)

        def _update_level_from_node(self, node):
            levelcontrol_element = node.find("levelcontrol")

            if levelcontrol_element is not None:
                self.level = get_node_value_as_int(levelcontrol_element, "level")
                self.levelpercentage = get_node_value_as_int(levelcontrol_element, "levelpercentage")

            state_element = node.find("simpleonoff")
            if state_element is not None:
                simpleonoff = get_node_value_as_int_as_bool(state_element, "state")
                if not simpleonoff:
                    self.level = 0
                    self.levelpercentage = 0

    class FritzhomeDeviceColor(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        color_mode = None
        supported_color_mode = None
        fullcolorsupport = None
        mapped = None

        hue = None
        saturation = None
        unmapped_hue = None
        unmapped_saturation = None
        colortemperature = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_color():
                self._update_color_from_node(node)

        def has_color(self):
            """Check if the device has LightBulb function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.COLOR)

        def _update_color_from_node(self, node):
            colorcontrol_element = node.find("colorcontrol")

            if colorcontrol_element:

                try:
                    self.color_mode = int(colorcontrol_element.attrib.get("current_mode"))
                except ValueError:
                    pass

                try:
                    self.supported_color_mode = int(colorcontrol_element.attrib.get("supported_modes"))
                except ValueError:
                    pass

                self.fullcolorsupport = bool(colorcontrol_element.attrib.get("fullcolorsupport"))
                self.mapped = bool(colorcontrol_element.attrib.get("mapped"))
                self.hue = get_node_value_as_int(colorcontrol_element, "hue")
                self.saturation = get_node_value_as_int(colorcontrol_element, "saturation")
                self.unmapped_hue = get_node_value_as_int(colorcontrol_element, "unmapped_hue")
                self.unmapped_saturation = get_node_value_as_int(colorcontrol_element, "unmapped_saturation")
                self.colortemperature = get_node_value_as_int(colorcontrol_element, "temperature")

        def get_colors(self):
            """Get the supported colors."""
            if self.has_color():
                return self._fritz.get_colors(self.ain)
            else:
                return {}

        def set_color(self, hsv, duration=0):
            """Set HSV color."""
            if self.has_color():
                self._fritz.set_color(self.ain, hsv, duration, True)

        def set_unmapped_color(self, hsv, duration=0):
            """Set unmapped HSV color (Free color selection)."""
            if self.has_color():
                self._fritz.set_color(self.ain, hsv, duration, False)

        def get_color_temps(self):
            """Get the supported color temperatures energy."""
            if self.has_color():
                return self._fritz.get_color_temps(self.ain)
            else:
                return []

        def set_color_temp(self, temperature, duration=0):
            """Set white color temperature."""
            if self.has_color:
                self._fritz.set_color_temp(self.ain, temperature, duration)

    class FritzhomeDeviceHumidity(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        humidity = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_humidity_sensor():
                self._update_humidity_from_node(node)

        def has_humidity_sensor(self):
            """Check if the device has humidity function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.HUM_SENSOR)

        def _update_humidity_from_node(self, node):
            humidity_element = node.find("humidity")
            if humidity_element:
                self.humidity = get_node_value_as_int(humidity_element, "rel_humidity")

    class FritzhomeDeviceHanFunUnit(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        etsideviceid = None
        unittype = None
        interfaces = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if not self.connected:
                return

            if self.has_han_fun_unit():
                self._update_han_fun_unit_from_node(node)

        def has_han_fun_unit(self):
            """Check if the device has humidity function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.HANFUN)

        def _update_han_fun_unit_from_node(self, node):
            hanfun_element = node.find("etsiunitinfo>")
            if hanfun_element:
                self.etsideviceid = get_node_value(hanfun_element, "etsideviceid")
                self.unittype = get_node_value_as_int(hanfun_element, "unittype>")
                self.interfaces = get_node_value_as_int(hanfun_element, "interfaces>")

    class FritzhomeDevice(
        FritzhomeDeviceAlarm,
        FritzhomeDeviceButton,
        FritzhomeDevicePowermeter,
        FritzhomeDeviceRepeater,
        FritzhomeDeviceSwitch,
        FritzhomeDeviceTemperature,
        FritzhomeDeviceThermostat,
        FritzhomeDeviceLightBulb,
        FritzhomeDeviceBlind,
        FritzhomeDeviceSwitchable,
        FritzhomeDeviceDimmable,
        FritzhomeDeviceColor,
        FritzhomeDeviceHumidity
    ):
        """The Fritzhome Device class."""

        def __init__(self, fritz=None, node=None):
            super().__init__(fritz, node)

        def update_from_node(self, node):
            super()._update_from_node(node)


class Callmonitor:

    def __init__(self, host, port, callback, call_monitor_incoming_filter, plugin_instance):
        """
        Init the Callmonitor class
        """
        self._plugin_instance = plugin_instance
        self.logger = self._plugin_instance.logger
        self.debug_log = self._plugin_instance.debug_log

        self.logger.debug("Init Callmonitor")

        self.host = host
        self.port = port

        self._call_monitor_incoming_filter = call_monitor_incoming_filter
        self._callback = callback
        self.items = dict()                # item dict
        self._call_active = dict()
        self._listen_active = False
        self._call_active['incoming'] = False
        self._call_active['outgoing'] = False
        self._call_incoming_cid = dict()
        self._call_outgoing_cid = dict()
        self.conn = None
        self._listen_thread = None

        self.connect()

    def connect(self):
        """
        Connects to the call monitor of the AVM device
        """
        if self._listen_active:
            if self.debug_log:
                self.logger.debug("MonitoringService: Connect called while listen active")
            return

        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.conn.connect((self.host, self.port))
            _name = f'plugins.{self._plugin_instance.get_fullname()}.Monitoring_Service'
            self._listen_thread = threading.Thread(target=self._listen, name=_name).start()
        except Exception as e:
            self.conn = None
            self.logger.error(
                f"MonitoringService: Cannot connect to {self.host} on port: {self.port}, CallMonitor activated by #96*5*? - Error: {e}")
        else:
            if self.debug_log:
                self.logger.debug("MonitoringService: connection established")

    def disconnect(self):
        """
        Disconnects from the call monitor of the AVM device
        """
        self.logger.debug("MonitoringService: disconnecting")
        self._listen_active = False
        self._stop_counter('incoming')
        self._stop_counter('outgoing')

        try:
            self._listen_thread.join(1)
        except Exception:
            pass

        try:
            self.conn.shutdown(2)
        except Exception:
            pass

    def reconnect(self):
        """
        Reconnects to the call monitor of the AVM device
        """
        self.disconnect()
        self.connect()

    def register_item(self, item, item_config: dict):
        """
        Registers an item to the CallMonitoringService

        :param item: item to register
        :param item_config: item config dict of item to be registered
        """
        avm_data_type = item_config['avm_data_type']

        # handle CALL_MONITOR_ATTRIBUTES_IN
        if avm_data_type in CALL_MONITOR_ATTRIBUTES_IN:
            item_config.update({'monitor_item_type': 'incoming'})

        elif avm_data_type in CALL_MONITOR_ATTRIBUTES_OUT:
            item_config.update({'monitor_item_type': 'outgoing'})

        elif avm_data_type in CALL_MONITOR_ATTRIBUTES_GEN:
            item_config.update({'monitor_item_type': 'generic'})

        elif avm_data_type in CALL_MONITOR_ATTRIBUTES_TRIGGER:
            avm_incoming_allowed = self._plugin_instance.get_iattr_value(item.conf, 'avm_incoming_allowed')
            avm_target_number = self._plugin_instance.get_iattr_value(item.conf, 'avm_target_number')

            if not avm_incoming_allowed or not avm_target_number:
                self.logger.error(f"For Trigger-item={item.path()} both 'avm_incoming_allowed' and 'avm_target_number' must be specified as attributes. Item will be ignored.")
            else:
                item_config.update({'monitor_item_type': 'trigger', 'avm_incoming_allowed': avm_incoming_allowed, 'avm_target_number': avm_target_number})

        elif avm_data_type in CALL_MONITOR_ATTRIBUTES_DURATION:
            if avm_data_type == 'call_duration_incoming':
                item_config.update({'monitor_item_type': 'duration_in'})
            else:
                item_config.update({'monitor_item_type': 'duration_out'})

        else:
            item_config.update({'monitor_item_type': 'generic'})

        # register item
        self.items[item] = item_config

    def unregister_item(self, item):
        """ remove item from instance """
        try:
            del self.items[item]
        except KeyError:
            pass

    def set_callmonitor_item_values_initially(self):
        """
        Set callmonitor related item values after startup
        """
        _calllist = self._plugin_instance.get_calllist()

        if not _calllist:
            return

        for item in self.items:
            avm_data_type = self.items[item]['avm_data_type']

            if avm_data_type == 'last_caller_incoming':
                for element in _calllist:
                    if element['Type'] in ['1', '2']:
                        if 'Name' in element:
                            item(element['Name'], self._plugin_instance.get_fullname())
                        else:
                            item(element['Caller'], self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'last_number_incoming':
                for element in _calllist:
                    if element['Type'] in ['1', '2']:
                        if 'Caller' in element:
                            item(element['Caller'], self._plugin_instance.get_fullname())
                        else:
                            item("", self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'last_called_number_incoming':
                for element in _calllist:
                    if element['Type'] in ['1', '2']:
                        item(element['CalledNumber'], self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'last_call_date_incoming':
                for element in _calllist:
                    if element['Type'] in ['1', '2']:
                        date = str(element['Date'])
                        date_str = f"{date[8:10]}.{date[5:7]}.{date[2:4]} {date[11:19]}"
                        item(date_str, self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'call_event_incoming':
                item('disconnect', self._plugin_instance.get_fullname())

            elif avm_data_type == 'is_call_incoming':
                item(False, self._plugin_instance.get_fullname())

            elif avm_data_type == 'last_caller_outgoing':
                for element in _calllist:
                    if element['Type'] in ['3', '4']:
                        if 'Name' in element:
                            item(element['Name'], self._plugin_instance.get_fullname())
                        else:
                            item(element['Called'], self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'last_number_outgoing':
                for element in _calllist:
                    if element['Type'] in ['3', '4']:
                        if 'Caller' in element:
                            item(''.join(filter(lambda x: x.isdigit(), element['Caller'])), self._plugin_instance.get_fullname())
                        else:
                            item("", self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'last_called_number_outgoing':
                for element in _calllist:
                    if element['Type'] in ['3', '4']:
                        item(element['Called'], self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'last_call_date_outgoing':
                for element in _calllist:
                    if element['Type'] in ['3', '4']:
                        date = str(element['Date'])
                        date_str = f"{date[8:10]}.{date[5:7]}.{date[2:4]} {date[11:19]}"
                        item(date_str, self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'call_event_outgoing':
                item('disconnect', self._plugin_instance.get_fullname())

            elif avm_data_type == 'is_call_outgoing':
                item(False, self._plugin_instance.get_fullname())

            elif avm_data_type == 'call_event':
                item('disconnect', self._plugin_instance.get_fullname())

            elif avm_data_type == 'call_direction':
                for element in _calllist:
                    if element['Type'] in ['1', '2']:
                        item('incoming', self._plugin_instance.get_fullname())
                        break
                    if element['Type'] in ['3', '4']:
                        item('outgoing', self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'call_duration_incoming':
                for element in _calllist:
                    if element['Type'] in ['1', '2']:
                        duration = element['Duration']
                        duration = int(duration[0:1]) * 3600 + int(duration[2:4]) * 60
                        item(duration, self._plugin_instance.get_fullname())
                        break

            elif avm_data_type == 'call_duration_outgoing':
                for element in _calllist:
                    if element['Type'] in ['3', '4']:
                        duration = element['Duration']
                        duration = int(duration[0:1]) * 3600 + int(duration[2:4]) * 60
                        item(duration, self._plugin_instance.get_fullname())
                        break

    def item_list(self):
        return list(self.items.keys())

    def item_list_gen(self) -> list:
        return self._get_item_list({'monitor_item_type': 'generic'})

    def item_list_incoming(self) -> list:
        return self._get_item_list({'monitor_item_type': 'incoming'})

    def item_list_outgoing(self) -> list:
        return self._get_item_list({'monitor_item_type': 'outgoing'})

    def item_list_trigger(self) -> list:
        return self._get_item_list({'monitor_item_type': 'trigger'})

    def duration_item_in(self):
        item_list = self._get_item_list({'monitor_item_type': 'duration_in'})
        if item_list:
            return item_list[0]

    def duration_item_out(self):
        item_list = self._get_item_list({'monitor_item_type': 'duration_out'})
        if item_list:
            return item_list[0]

    def _get_item_list(self, sub_dict: dict) -> list:
        item_list = []
        for item in self.items:
            if sub_dict.items() <= self.items[item].items():
                item_list.append(item)
        return item_list

    def item_count_total(self):
        """
        Returns number of added items (all items of MonitoringService service)

        :return: number of items hold by the MonitoringService
        """
        return len(self.items)

    def _listen(self, recv_buffer: int = 4096):
        """
        Function which listens to the established connection.
        """
        self._listen_active = True
        buffer = ""
        while self._listen_active:
            data = self.conn.recv(recv_buffer)
            if data == "":
                self.logger.error("CallMonitor connection not open anymore.")
            else:
                if self.debug_log:
                    self.logger.debug(f"Data Received from CallMonitor: {data.decode('utf-8').strip()}")
            buffer += data.decode("utf-8")
            while buffer.find("\n") != -1:
                line, buffer = buffer.split("\n", 1)
                if line:
                    self._parse_line(line)

    def _start_counter(self, timestamp: str, direction: str):
        """
        Start counter to measure duration of a call
        """
        if direction == 'incoming':
            self._call_connect_timestamp = time.mktime(datetime.datetime.strptime(timestamp, "%d.%m.%y %H:%M:%S").timetuple())
            self._duration_counter_thread_incoming = threading.Thread(target=self._count_duration_incoming,
                                                                      name=f"MonitoringService_Duration_Incoming_{self._plugin_instance.get_instance_name()}").start()
            self.logger.debug('Counter incoming - STARTED')
        elif direction == 'outgoing':
            self._call_connect_timestamp = time.mktime(datetime.datetime.strptime(timestamp, "%d.%m.%y %H:%M:%S").timetuple())
            self._duration_counter_thread_outgoing = threading.Thread(target=self._count_duration_outgoing,
                                                                      name=f"MonitoringService_Duration_Outgoing_{self._plugin_instance.get_instance_name()}").start()
            self.logger.debug('Counter outgoing - STARTED')

    def _stop_counter(self, direction: str):
        """
        Stop counter to measure duration of a call, but only stop of thread is active
        """
        if self._call_active[direction]:
            self._call_active[direction] = False
            if self.debug_log:
                self.logger.debug(f'STOPPING {direction}')
            try:
                if direction == 'incoming':
                    self._duration_counter_thread_incoming.join(1)
                elif direction == 'outgoing':
                    self._duration_counter_thread_outgoing.join(1)
            except Exception:
                pass

    def _count_duration_incoming(self):
        """
        Count duration of incoming call and set item value
        """
        self._call_active['incoming'] = True
        while self._call_active['incoming']:
            if self.duration_item_in():
                duration = time.time() - self._call_connect_timestamp
                self.duration_item_in()(int(duration), self._plugin_instance.get_fullname())
            time.sleep(1)

    def _count_duration_outgoing(self):
        """
        Count duration of outgoing call and set item value
        """
        self._call_active['outgoing'] = True
        while self._call_active['outgoing']:
            if self.duration_item_out():
                duration = time.time() - self._call_connect_timestamp
                self.duration_item_out()(int(duration), self._plugin_instance.get_fullname())
            time.sleep(1)

    def _parse_line(self, line: str):
        """
        Parses a data set in the form of a line.

        Data Format:
        Ausgehende Anrufe: datum;CALL;ConnectionID;Nebenstelle;GenutzteNummer;AngerufeneNummer;SIP+Nummer
        Eingehende Anrufe: datum;RING;ConnectionID;Anrufer-Nr;Angerufene-Nummer;SIP+Nummer
        Zustandegekommene Verbindung: datum;CONNECT;ConnectionID;Nebenstelle;Nummer;
        Ende der Verbindung: datum;DISCONNECT;ConnectionID;dauerInSekunden;

        :param line: data line which is parsed
        """
        lines = line.split(";")
        if self.debug_log:
            self.logger.debug(f"_parse_line: line={line} to be parsed")

        try:
            if lines[1] == "RING":
                self._trigger(lines[3], lines[4], lines[0], lines[2], lines[1], '')
            elif lines[1] == "CALL":
                self._trigger(lines[4], lines[5], lines[0], lines[2], lines[1], lines[3])
            elif lines[1] == "CONNECT":
                self._trigger('', '', lines[0], lines[2], lines[1], lines[3])
            elif lines[1] == "DISCONNECT":
                self._trigger('', '', '', lines[2], lines[1], '')
        except Exception as e:
            self.logger.error(f"MonitoringService: {type(e).__name__} while handling Callmonitor response: {e}")
            self.logger.error(f"Callmonitor response: {lines}")

    def _trigger(self, call_from: str, call_to: str, dt: str, callid: str, event: str, branch: str):
        """
        Triggers the event: sets item values and looks up numbers in the phone book.
        """
        if self.debug_log:
            self.logger.debug(f"_trigger: Event={event}, Call from={call_from}, Call to={call_to}, Time={dt}, CallID={callid}, Branch={branch}")

        # set generic item value
        for item in self.item_list_gen():
            avm_data_type = self.items[item]['avm_data_type']
            if avm_data_type == 'call_event':
                item(event.lower(), self._plugin_instance.get_fullname())
            if avm_data_type == 'call_direction':
                if event == 'RING':
                    item("incoming", self._plugin_instance.get_fullname())
                else:
                    item("outgoing", self._plugin_instance.get_fullname())

        # handle incoming call
        if event == 'RING':
            # process "trigger items"
            for trigger_item in self.item_list_trigger():
                avm_data_type = self.items[trigger_item]['avm_data_type']
                avm_incoming_allowed = self.items[trigger_item]['avm_incoming_allowed']
                avm_target_number = self.items[trigger_item]['avm_target_number']
                trigger_item(0, self._plugin_instance.get_fullname())
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} {call_from} {call_to}")
                if avm_incoming_allowed == call_from and avm_target_number == call_to:
                    trigger_item(1, self._plugin_instance.get_fullname())

            # process incoming call, if caller not in _call_monitor_incoming_filter
            if self._call_monitor_incoming_filter in call_to:
                # set call id for incoming call
                self._call_incoming_cid = callid

                # reset duration for incoming calls
                if self.duration_item_in():
                    self.duration_item_in()(0, self._plugin_instance.get_fullname())

                # process items specific to incoming calls
                for item in self.item_list_incoming():
                    avm_data_type = self.items[item]['avm_data_type']
                    if avm_data_type == 'is_call_incoming':
                        if self.debug_log:
                            self.logger.debug("Setting is_call_incoming: True")
                        item(True, self._plugin_instance.get_fullname())
                    elif avm_data_type == 'last_caller_incoming':
                        if call_from:
                            name = self._callback(call_from)
                            if name:
                                item(name, self._plugin_instance.get_fullname())
                            else:
                                item(call_from, self._plugin_instance.get_fullname())
                        else:
                            item("Unbekannt", self._plugin_instance.get_fullname())
                    elif avm_data_type == 'last_call_date_incoming':
                        if self.debug_log:
                            self.logger.debug(f"Setting last_call_date_incoming: {time}")
                        item(str(dt), self._plugin_instance.get_fullname())
                    elif avm_data_type == 'call_event_incoming':
                        if self.debug_log:
                            self.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_fullname())
                    elif avm_data_type == 'last_number_incoming':
                        if self.debug_log:
                            self.logger.debug(f"Setting last_number_incoming: {call_from}")
                        item(call_from, self._plugin_instance.get_fullname())
                    elif avm_data_type == 'last_called_number_incoming':
                        if self.debug_log:
                            self.logger.debug(f"Setting last_called_number_incoming: {call_to}")
                        item(call_to, self._plugin_instance.get_fullname())

        # handle outgoing call
        elif event == 'CALL':
            # set call id for outgoing call
            self._call_outgoing_cid = callid

            # reset duration for outgoing calls
            if self.duration_item_out():
                self.duration_item_out()(0, self._plugin_instance.get_fullname())

            # process items specific to outgoing calls
            for item in self.item_list_outgoing():
                avm_data_type = self.items[item]['avm_data_type']
                if avm_data_type == 'is_call_outgoing':
                    item(True, self._plugin_instance.get_fullname())
                elif avm_data_type == 'last_caller_outgoing':
                    name = self._callback(call_to)
                    if name:
                        item(name, self._plugin_instance.get_fullname())
                    else:
                        item(call_to, self._plugin_instance.get_fullname())
                elif avm_data_type == 'last_call_date_outgoing':
                    item(str(dt), self._plugin_instance.get_fullname())
                elif avm_data_type == 'call_event_outgoing':
                    item(event.lower(), self._plugin_instance.get_fullname())
                elif avm_data_type == 'last_number_outgoing':
                    item(call_from, self._plugin_instance.get_fullname())
                elif avm_data_type == 'last_called_number_outgoing':
                    item(call_to, self._plugin_instance.get_fullname())

        # handle established connection
        elif event == 'CONNECT':
            # handle OUTGOING calls
            if callid == self._call_outgoing_cid:
                if self.duration_item_out() is not None:  # start counter thread only if duration item set and call is outgoing
                    self._stop_counter('outgoing')  # stop potential running counter for parallel (older) outgoing call
                    self._start_counter(dt, 'outgoing')
                for item in self.item_list_outgoing():
                    avm_data_type = self.items[item]['avm_data_type']
                    if avm_data_type == 'call_event_outgoing':
                        item(event.lower(), self._plugin_instance.get_fullname())
                        break

            # handle INCOMING calls
            elif callid == self._call_incoming_cid:
                if self.duration_item_in() is not None:  # start counter thread only if duration item set and call is incoming
                    self._stop_counter('incoming')  # stop potential running counter for parallel (older) incoming call
                    if self.debug_log:
                        self.logger.debug("Starting Counter for Call Time")
                    self._start_counter(dt, 'incoming')
                for item in self.item_list_incoming():
                    avm_data_type = self.items[item]['avm_data_type']
                    if avm_data_type == 'call_event_incoming':
                        if self.debug_log:
                            self.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_fullname())

        # handle ended connection
        elif event == 'DISCONNECT':
            # handle OUTGOING calls
            if callid == self._call_outgoing_cid:
                for item in self.item_list_outgoing():
                    avm_data_type = self.items[item]['avm_data_type']
                    if avm_data_type == 'call_event_outgoing':
                        item(event.lower(), self._plugin_instance.get_fullname())
                    elif avm_data_type == 'is_call_outgoing':
                        item(False, self._plugin_instance.get_fullname())
                if self.duration_item_out() is not None:  # stop counter threads
                    self._stop_counter('outgoing')
                self._call_outgoing_cid = None

            # handle INCOMING calls
            elif callid == self._call_incoming_cid:
                for item in self.item_list_incoming():
                    avm_data_type = self.items[item]['avm_data_type']
                    if avm_data_type == 'call_event_incoming':
                        if self.debug_log:
                            self.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_fullname())
                    elif avm_data_type == 'is_call_incoming':
                        if self.debug_log:
                            self.logger.debug("Setting is_call_incoming: False")
                        item(False, self._plugin_instance.get_fullname())
                if self.duration_item_in() is not None:  # stop counter threads
                    if self.debug_log:
                        self.logger.debug("Stopping Counter for Call Time")
                    self._stop_counter('incoming')
                self._call_incoming_cid = None


#
# static XML helpers
#

def get_node_value(elem, node):
    return elem.findtext(node)


def get_node_value_as_int(elem, node) -> int:
    value = get_node_value(elem, node)
    try:
        return int(value)
    except TypeError:
        return 0


def get_node_value_as_int_as_bool(elem, node) -> bool:
    value = get_node_value_as_int(elem, node)
    return bool(value)


def get_temp_from_node(elem, node) -> float:
    value = get_node_value_as_int(elem, node)
    return float(value) / 2


def get_node_value_as_float_1000(elem, node) -> float:
    value = get_node_value_as_int(elem, node)
    return float(value) / 1000


def get_node_value_as_float_10(elem, node) -> float:
    value = get_node_value_as_int(elem, node)
    return float(value) / 10


def lxml_element_to_dict(node):
    """Parse lxml Element to dictionary"""
    result = {}

    for element in node.iterchildren():
        # Remove namespace prefix
        key = element.tag.split('}')[1] if '}' in element.tag else element.tag

        # Process element as tree element if the inner XML contains non-whitespace content
        if element.text and element.text.strip():
            value = element.text
        else:
            value = lxml_element_to_dict(element)
        if key in result:

            if type(result[key]) is list:
                result[key].append(value)
            else:
                tempvalue = result[key].copy()
                result[key] = [tempvalue, value]
        else:
            result[key] = value
    return result


def request_response_to_xml(request):
    """
    Parse request response to element object
    """
    return ET.fromstring(request.content)
