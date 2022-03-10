#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2022-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.8 and
#  upwards.
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

import socket
import threading
import datetime
import logging
import requests
import hashlib
import time
import lxml.etree as etree

from typing import Union
from requests.packages import urllib3
from requests.auth import HTTPDigestAuth
from io import BytesIO
from xml.etree import ElementTree
from typing import Dict
from enum import IntFlag
from abc import ABC
from json.decoder import JSONDecodeError

from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from .webif import WebInterface

"""
Definition of TR-064 details
"""

FRITZ_TR64_DESC_FILE = "tr64desc.xml"
FRITZ_IGD_DESC_FILE = "igddesc.xml"
FRITZ_IGD2_DESC_FILE = "igd2desc.xml"
FRITZ_L2TPV3_FILE = "l2tpv3.xml"
FRITZ_FBOX_DESC_FILE = "fboxdesc.xml"

IGD_DEVICE_NAMESPACE = {'': 'urn:schemas-upnp-org:device-1-0'}
IGD_SERVICE_NAMESPACE = {'': 'urn:schemas-upnp-org:service-1-0'}
TR064_DEVICE_NAMESPACE = {'': 'urn:dslforum-org:device-1-0'}
TR064_SERVICE_NAMESPACE = {'': 'urn:dslforum-org:service-1-0'}


"""
Definition DeviceGroupDicts
"""

InternetGatewayDevice = {
    'DeviceInfo': {
        'GetInfo': {},
        'GetSecurityPort': {},
    },
    'DeviceConfig': {
        'GetPersistentData': {},
    },
    'X_AVM_DE_MyFritz': {
        'GetInfo': {},
        'GetNumberOfServices': {},
    },
    'X_VoIP': {
        'GetInfoEx': {},
    },
    'X_AVM_DE_OnTel': {
        'GetInfo': {},
        'GetInfoByIndex': {},
        'GetNumberOfEntries': {},
        'GetCallList': {},
        'GetPhonebookList': {},
        'GetPhonebook': {},
        'GetNumberOfDeflections': {},
        'GetDeflection': {},
        'GetDeflections': {},
        'GetDECTHandsetList': {},
    },
    'X_AVM_DE_Dect': {
        'GetNumberOfDectEntries': {},
        'GetGenericDectEntry': {},
        'GetSpecificDectEntry': {},
    },
    'X_AVM_DE_TAM': {
        'GetInfo': {},
        'GetMessageList': {},
        'GetList': {},
    },
    'X_AVM_DE_Homeauto': {
        'GetInfo': {},
        'GetGenericDeviceInfos': {},
        'GetSpecificDeviceInfos': {},
    },
}

LANDevice = {
    'WLANConfiguration': {
        'GetInfo': {},
        'GetGenericAssociatedDeviceInfo': {},
        'X_AVM_DE_GetSpecificAssociatedDeviceInfoByIp': {},
        'GetStatistics': {},
        'GetPacketStatistics': {},
        'X_AVM_DE_GetWLANHybridMode': {},
        'X_AVM_DE_GetWLANExtInfo': {},
    },
    'Hosts': {
        'GetHostNumberOfEntries': {},
        'GetSpecificHostEntry': {},
        'GetGenericHostEntry': {},
        'X_AVM_DE_GetSpecificHostEntryByIp': {},
    },
    'LANEthernetInterfaceConfig': {
        'GetInfo': {},
        'GetStatistics': {},
    },
    'LANHostConfigManagement': {
        'GetInfo': {},
    },
}

WANDevice = {
    'WANCommonInterfaceConfig': {
        'GetCommonLinkProperties': {},
        'GetTotalBytesSent': {},
        'GetTotalBytesReceived': {},
        'GetTotalPacketsSent': {},
        'GetTotalPacketsReceived': {},
        'X_AVM_DE_GetOnlineMonitor': {},
    },
    'WANDSLInterfaceConfig': {
        'GetInfo': {},
        'GetStatisticsTotal': {},
        'X_AVM_DE_GetDSLDiagnoseInfo': {},
    },
}

WANConnectionDevice = {
    'WANDSLLinkConfig': {
        'GetInfo': {},
        'GetDSLLinkInfo': {},
        'GetDestinationAddress': {}
    },
    'WANEthernetLinkConfig': {
        'GetEthernetLinkStatus': {}
    },
    'WANPPPConnection': {
        'GetInfo': {},
        'GetConnectionTypeInfo': {},
        'GetStatusInfo': {},
        'GetGenericPortMappingEntry': {},
        'GetSpecificPortMappingEntry': {},
        'GetExternalIPAddress': {}
    },
    'WANIPConnection': {
        'GetInfo': {},
        'GetConnectionTypeInfo': {},
        'GetStatusInfo': {},
        'GetGenericPortMappingEntry': {},
        'GetSpecificPortMappingEntry': {},
        'GetExternalIPAddress': {}
    },
}

"""
Definition of attribute value groups of avm_data_type
"""
_aha_ro_attributes = ['device_id',
                      'manufacturer',
                      'product_name',
                      'fw_version',
                      'connected',
                      'device_name',
                      'tx_busy',
                      'device_functions',
                      'current_temperature',
                      'temperature_reduced',
                      'temperature_comfort',
                      'temperature_offset',
                      'windowopenactiveendtime',
                      'boost_active',
                      'boostactiveendtime',
                      'summer_active',
                      'holiday_active',
                      'battery_low',
                      'lock',
                      'device_lock',
                      'errorcode',
                      'switch_mode',
                      'power', 'energy',
                      'voltage',
                      'humidity',
                      'alert_state']

_aha_wo_attributes = ['set_target_temperature',
                      'set_window_open',
                      'set_hkr_boost',
                      'battery_level',
                      'set_simpleonoff',
                      'set_level',
                      'set_levelpercentage',
                      'set_hue',
                      'set_saturation',
                      'set_colortemperature',
                      'switch_toggle']

_aha_rw_attributes = ['target_temperature',
                      'window_open',
                      'hkr_boost',
                      'simpleonoff',
                      'level',
                      'levelpercentage',
                      'hue',
                      'saturation',
                      'colortemperature',
                      'switch_state']

_aha_attributes = [*_aha_ro_attributes,
                   *_aha_wo_attributes,
                   *_aha_rw_attributes]

_avm_rw_attributes = ['wlanconfig',
                      'tam',
                      'deflection_enable']

_call_monitor_attributes_gen = ['call_event',
                                'call_direction',
                                'monitor_trigger']

_call_monitor_attributes_in = ['is_call_incoming',
                               'last_caller_incoming',
                               'last_call_date_incoming',
                               'call_event_incoming',
                               'last_number_incoming',
                               'last_called_number_incoming']

_call_monitor_attributes_out = ['is_call_outgoing',
                                'last_caller_outgoing',
                                'last_call_date_outgoing',
                                'call_event_outgoing',
                                'last_number_outgoing',
                                'last_called_number_outgoing']

_call_monitor_attributes = [*_call_monitor_attributes_gen,
                            *_call_monitor_attributes_in,
                            *_call_monitor_attributes_out]

_call_duration_attributes = ['call_duration_incoming',
                             'call_duration_outgoing']

_trigger_attributes = ['monitor_trigger']

_wan_connection_attributes = ['wan_connection_status',
                              'wan_connection_error',
                              'wan_is_connected',
                              'wan_uptime',
                              'wan_ip']

_tam_attributes = ['tam',
                   'tam_name',
                   'tam_new_message_number',
                   'tam_total_message_number']

_wlan_config_attributes = ['wlanconfig',
                           'wlanconfig_ssid',
                           'wlan_guest_time_remaining']

_wan_common_interface_attributes = ['wan_total_packets_sent',
                                    'wan_total_packets_received',
                                    'wan_current_packets_sent',
                                    'wan_current_packets_received',
                                    'wan_total_bytes_sent',
                                    'wan_total_bytes_received',
                                    'wan_current_bytes_sent',
                                    'wan_current_bytes_received',
                                    'wan_link']

_fritz_device_attributes = ['uptime',
                            'software_version',
                            'hardware_version',
                            'serial_number']

_host_attribute = ['network_device']

_host_child_attributes = ['device_ip',
                          'device_connection_type',
                          'device_hostname'
                          'connection_status']

_host_attributes = [*_host_attribute,
                    *_host_child_attributes]

_deflection_attributes = ['deflections_details',
                          'deflection_enable',
                          'deflection_type',
                          'deflection_number',
                          'deflection_to_number',
                          'deflection_mode',
                          'deflection_outgoing',
                          'deflection_phonebook_id']

_wan_dsl_interface_attributes = ['wan_upstream',
                                 'wan_downstream']

_homeauto_ro_attributes = ['hkr_device',
                           'set_temperature',
                           'temperature',
                           'set_temperature_reduced',
                           'set_temperature_comfort',
                           'firmware_version']

_homeauto_rw_attributes = ['aha_device']

_homeauto_attributes = [*_homeauto_ro_attributes,
                        *_homeauto_rw_attributes]

_myfritz_attributes = ['myfritz_status']

_deprecated_attributes = ['temperature',
                          'set_temperature_reduced',
                          'set_temperature_comfort',
                          'firmware_version',
                          'aha_device',
                          'hkr_device']

_tr064_attributes = [*_wan_connection_attributes,
                     *_tam_attributes,
                     *_wlan_config_attributes,
                     *_wan_common_interface_attributes,
                     *_fritz_device_attributes,
                     *_host_attributes,
                     *_deflection_attributes,
                     *_wan_dsl_interface_attributes,
                     *_homeauto_attributes,
                     *_myfritz_attributes,
                     *_avm_rw_attributes]


class AVM2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.0.0'

    def __init__(self, sh):
        """
        Initializes the plugin.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.logger.info('Init AVM2 Plugin')

        # Get/Define Properties
        _host = self.get_parameter_value('host')
        _port = self.get_parameter_value('port')
        _verify = self.get_parameter_value('verify')
        _username = self.get_parameter_value('username')
        _passwort = self.get_parameter_value('password')
        _call_monitor_incoming_filter = self.get_parameter_value('call_monitor_incoming_filter')
        self._call_monitor = self.get_parameter_value('call_monitor')
        self._aha_http_interface = self.get_parameter_value('avm_home_automation')
        self._cycle = self.get_parameter_value('cycle')
        self.alive = False
        ssl = self.get_parameter_value('ssl')
        if ssl and not _verify:
            urllib3.disable_warnings()

        # init FritzDevice
        self._fritz_device = FritzDevice(_host, _port, ssl, _verify, _username, _passwort, _call_monitor_incoming_filter, self)

        # init FritzHome
        if self._aha_http_interface:
            self._fritz_home = FritzHome(_host, ssl, _verify, _username, _passwort, self)

        # init Call Monitor
        if self._call_monitor:
            self._monitoring_service = Callmonitor(_host,
                                                   1012,
                                                   self._fritz_device.get_contact_name_by_phone_number,
                                                   _call_monitor_incoming_filter,
                                                   self)

        # init WebIF
        self.init_webinterface(WebInterface)

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.scheduler_add('poll_tr064', self._fritz_device.update_items, prio=5, cycle=self._cycle, offset=4)
        if self._aha_http_interface:
            # add scheduler for updating items
            self.scheduler_add('poll_aha', self._fritz_home.update_items, prio=5, cycle=self._cycle, offset=2)
            # add scheduler for checking validity of session id
            self.scheduler_add('check_sid', self._fritz_home.check_sid, prio=5, cycle=900, offset=30)

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
            self._fritz_home.logout()
        if self._call_monitor:
            self._monitoring_service.disconnect()

        self.alive = False

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized.
        The plugin can, corresponding to its attribute keywords, decide what to do with
        the item in future, like adding it to an internal array for future reference
        :param item:    The item to process.
        :return:        If the plugin needs to be informed of an items change you should return a call back function
                        like the function update_item down below. An example when this is needed is the knx plugin
                        where parse_item returns the update_item function when the attribute knx_send is found.
                        This means that when the items value is about to be updated, the call back function is called
                        with the item, caller, source and dest as arguments and in case of the knx plugin the value
                        can be sent to the knx with a knx write function within the knx plugin.
        """
        if self.has_iattr(item.conf, 'avm2_data_type'):
            self.logger.debug(f"parse item: {item}")

            # get avm_data_type
            avm_data_type = self.get_iattr_value(item.conf, 'avm2_data_type')

            # handle items specific to call monitor
            if avm_data_type in _call_monitor_attributes:
                # initially - if item empty - get data from calllist
                if avm_data_type == 'last_caller_incoming' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['1', '2']:
                                if 'Name' in element:
                                    item(element['Name'], self.get_shortname())
                                else:
                                    item(element['Caller'], self.get_shortname())
                                break
                elif avm_data_type == 'last_number_incoming' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['1', '2']:
                                if 'Caller' in element:
                                    item(element['Caller'], self.get_shortname())
                                else:
                                    item("", self.get_shortname())
                                break
                elif avm_data_type == 'last_called_number_incoming' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['1', '2']:
                                item(element['CalledNumber'], self.get_shortname())
                                break
                elif avm_data_type == 'last_call_date_incoming' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['1', '2']:
                                date = str(element['Date'])
                                date = date[8:10] + "." + date[5:7] + "." + date[2:4] + " " + date[11:19]
                                item(date, self.get_shortname())
                                break
                elif avm_data_type == 'call_event_incoming' and item() == '':
                    item('disconnect', self.get_shortname())
                elif avm_data_type == 'is_call_incoming' and item() == '':
                    item(0, self.get_shortname())
                elif avm_data_type == 'last_caller_outgoing' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['3', '4']:
                                if 'Name' in element:
                                    item(element['Name'], self.get_shortname())
                                else:
                                    item(element['Called'], self.get_shortname())
                                break
                elif avm_data_type == 'last_number_outgoing' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['3', '4']:
                                if 'Caller' in element:
                                    item(''.join(filter(lambda x: x.isdigit(), element['Caller'])), self.get_shortname())
                                else:
                                    item("", self.get_shortname())
                                break
                elif avm_data_type == 'last_called_number_outgoing' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['3', '4']:
                                item(element['Called'], self.get_shortname())
                                break
                elif avm_data_type == 'last_call_date_outgoing' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['3', '4']:
                                date = str(element['Date'])
                                date = date[8:10] + "." + date[5:7] + "." + date[2:4] + " " + date[11:19]
                                item(date, self.get_shortname())
                                break
                elif avm_data_type == 'call_event_outgoing' and item() == '':
                    item('disconnect', self.get_shortname())
                elif avm_data_type == 'is_call_outgoing' and item() == '':
                    item(0, self.get_shortname())
                elif avm_data_type == 'call_event' and item() == '':
                    item('disconnect', self.get_shortname())
                elif avm_data_type == 'call_direction' and item() == '':
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['1', '2']:
                                item('incoming', self.get_shortname())
                                break
                            if element['Type'] in ['3', '4']:
                                item('outgoing', self.get_shortname())
                                break
                if self._call_monitor:
                    if self._monitoring_service is not None:
                        self._monitoring_service.register_item(item, avm_data_type)

            # handle items specific to call-duration
            elif avm_data_type in _call_duration_attributes:
                # initially get data from calllist
                if avm_data_type == 'call_duration_incoming' and item() == 0:
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['1', '2']:
                                duration = element['Duration']
                                duration = int(duration[0:1]) * 3600 + int(duration[2:4]) * 60
                                item(duration, self.get_shortname())
                                break
                elif avm_data_type == 'call_duration_outgoing' and item() == 0:
                    if self._fritz_device.get_calllist_from_cache() is not None:
                        for element in self._fritz_device.get_calllist_from_cache():
                            if element['Type'] in ['3', '4']:
                                duration = element['Duration']
                                duration = int(duration[0:1]) * 3600 + int(duration[2:4]) * 60
                                item(duration, self.get_shortname())
                                break
                if self._call_monitor:
                    if self._monitoring_service is not None:
                        self._monitoring_service.register_item(item, avm_data_type)

            # handle smarthome items using aha-interface (old / new)
            elif avm_data_type in _aha_attributes:
                if self._aha_http_interface:
                    self._fritz_home.register_item(item, avm_data_type)
                else:
                    self.logger.warning(f"Items with avm attribute found, which needs aha-http-interface. This is not enabled for that plugin; Item will be ignored.")

            # handle items updated by tr-064 interface
            elif avm_data_type in _tr064_attributes:
                self._fritz_device.register_item(item, avm_data_type)
            else:
                self.logger.warning(f"avm_data_type={avm_data_type} if item={item.id()} unknown. Item will be ignored.")

            # items which can be changed outside the plugin context and need to be submitted to the FritzDevice
            if avm_data_type in (_avm_rw_attributes + _aha_wo_attributes + _aha_rw_attributes + _homeauto_rw_attributes):
                return self.update_item

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info(f"Update item: {item.property.path}, item has been changed outside this plugin")

            if self.has_iattr(item.conf, 'foo_itemtag'):
                self.logger.debug(
                    f"update_item was called with item {item.property.path} from caller {caller}, source {source} and dest {dest}")
            pass

    @property
    def get_callmonitor(self):
        return self._call_monitor

    def monitoring_service_connect(self):
        self._monitoring_service.connect()

    def monitoring_service_disconnect(self):
        self._monitoring_service.disconnect()


class FritzDevice:
    """
    This class encapsulates information related to a specific FritzDevice

    # Devices / Services
         InternetGatewayDevice
            DeviceInfo
                GetInfo
                SetProvisioningCode
                GetDeviceLog
                GetSecurityPort
            DeviceConfig
            Layer3Forwarding
            LANConfigSecurity
            ManagementServer
            Time
            UserInterface
            X_AVM-DE_Storage
            X_AVM-DE_WebDAVClient
            X_AVM-DE_UPnP
            X_AVM-DE_Speedtest
            X_AVM-DE_RemoteAccess
            X_AVM-DE_MyFritz
            X_VoIP
            X_AVM-DE_OnTel
            X_AVM-DE_Dect
            X_AVM-DE_TAM
            X_AVM-DE_AppSetup
            X_AVM-DE_Homeauto
            X_AVM-DE_Homeplug
            X_AVM-DE_Filelinks
            X_AVM-DE_Auth
            X_AVM-DE_HostFilter
        LANDevice
            WLANConfiguration
            Hosts
            LANEthernetInterfaceConfig
            LANHostConfigManagement
        WANDevice
            WANCommonInterfaceConfig
            WANDSLInterfaceConfig
        WANConnectionDevice
            WANDSLLinkConfig
            WANEthernetLinkConfig
            WANPPPConnection
            WANIPConnection
    """

    def __init__(self, host, port, ssl, verify, username, password, call_monitor_incoming_filter, plugin_instance=None):

        self._plugin_instance = plugin_instance
        self._plugin_instance.logger.debug("Init FritzDevice")

        self._host = host
        self._port = port
        self._ssl = ssl
        self._verify = verify
        self._username = username
        self._password = password
        self._call_monitor_incoming_filter = call_monitor_incoming_filter
        self._available = True
        self._data_cache = {}
        self._calllist_cache = []
        self._timeout = 10
        self._items = {}
        self._session = requests.Session()

        self.items = Items.get_instance()

        # get client objects
        self.client = FritzDevice.Client(self._username, self._password, self._verify, base_url=self._build_url(), description_file=FRITZ_TR64_DESC_FILE, plugin_instance=plugin_instance)
        self.client_igd = FritzDevice.Client(self._username, self._password, self._verify, base_url=self._build_url(), description_file=FRITZ_IGD_DESC_FILE, plugin_instance=plugin_instance)

        # get GetDefaultConnectionService
        self._data_cache['InternetGatewayDevice'] = {'DeviceInfo': {'GetInfo': {}, 'GetSecurityPort': {}}, 'Layer3Forwarding': {}}
        self._data_cache['InternetGatewayDevice']['Layer3Forwarding']['GetDefaultConnectionService'] = self.client.InternetGatewayDevice.Layer3Forwarding.GetDefaultConnectionService()

    def register_item(self, item, avm_data_type: str):

        # handle wlan items
        if avm_data_type in _wlan_config_attributes:
            avm_wlan_index = self._get_wlan_index(item)
            if avm_wlan_index is not None:
                self._plugin_instance.logger.debug(f"Item {item.id()} with avm device attribute and defined 'avm_wlan_index' found; append to list.")
                self._items[item] = (avm_data_type, avm_wlan_index)
            else:
                self._plugin_instance.logger.warning(f"Item {item.id()} with avm attribute found, but 'avm_wlan_index' is not defined; Item will be ignored.")

        # handle network_device related items
        elif avm_data_type in (_host_attribute + _host_child_attributes):
            avm_mac = self._get_mac(item)
            if avm_mac is not None:
                if avm_mac is not None:
                    self._plugin_instance.logger.debug(f"Item {item.id()} with avm device attribute and defined 'avm_mac' found; append to list.")
                    self._items[item] = (avm_data_type, avm_mac)
                else:
                    self._plugin_instance.logger.warning("Item {item.id()} with avm attribute found, but 'avm_mac' is not defined; Item will be ignored.")

        # handle tam related items
        elif avm_data_type in _tam_attributes:
            avm_tam_index = self._get_tam_index(item)
            if avm_tam_index is not None:
                self._plugin_instance.logger.debug(f"Item {item.id()} with avm device attribute and defined 'avm_tam_index' found; append to list.")
                self._items[item] = (avm_data_type, avm_tam_index)
            else:
                self._plugin_instance.logger.warning(f"Item {item.id()} with avm attribute found, but 'avm_tam_index' is not defined; Item will be ignored.")

        else:
            self._items[item] = (avm_data_type, None)

    def _build_url(self) -> str:
        """
        Builds a request url

         :return: string of the url, dependent on settings of the FritzDevice
        """
        if self.is_ssl():
            url_prefix = "https"
        else:
            url_prefix = "http"
        url = f"{url_prefix}://{self._host}:{self._port}"

        return url

    def _get_wlan_index(self, item) -> int:
        """
        return wlan index for given item
        """

        wlan_index = None
        for i in range(2):
            attribute = 'avm2_wlan_index'
            attribute_w_instance = f"{attribute}@{self._plugin_instance.get_instance_name()}"

            wlan_index = self._plugin_instance.get_iattr_value(item.conf, attribute)
            if wlan_index:
                break
            wlan_index = self._plugin_instance.get_iattr_value(item.conf, attribute_w_instance)
            if wlan_index:
                break
            else:
                item = item.return_parent()

        if wlan_index is not None:
            wlan_index = int(wlan_index) - 1
            if not 0 <= wlan_index <= 2:
                wlan_index = None
                self._plugin_instance.logger.warning(f"Attribute 'avm2_wlan_index' for item {item.id()} not in valid range 1-3.")

        return wlan_index

    def _get_tam_index(self, item) -> int:
        """
        return tam index for given item
        """

        tam_index = None
        for i in range(2):
            attribute = 'avm2_tam_index'
            attribute_w_instance = f"{attribute}@{self._plugin_instance.get_instance_name()}"

            tam_index = self._plugin_instance.get_iattr_value(item.conf, attribute)
            if tam_index:
                break
            tam_index = self._plugin_instance.get_iattr_value(item.conf, attribute_w_instance)
            if tam_index:
                break
            else:
                item = item.return_parent()

        if tam_index is not None:
            tam_index = int(tam_index) - 1
            if not 0 <= tam_index <= 4:
                tam_index = None
                self._plugin_instance.logger.warning(f"Attribute 'avm_tam_index' for item {item.id()} not in valid range 1-5.")

        return tam_index

    def _get_deflection_index(self, item) -> int:
        """
        return deflection index for given item
        """

        deflection_index = None
        for i in range(2):
            attribute = 'avm2_deflection_index'
            attribute_w_instance = f"{attribute}@{self._plugin_instance.get_instance_name()}"

            deflection_index = self._plugin_instance.get_iattr_value(item.conf, attribute)
            if deflection_index:
                break
            deflection_index = self._plugin_instance.get_iattr_value(item.conf, attribute_w_instance)
            if deflection_index:
                break
            else:
                item = item.return_parent()

        if deflection_index is not None:
            deflection_index = int(deflection_index) - 1
            if not 0 <= deflection_index <= 31:
                deflection_index = None
                self._plugin_instance.logger.warning(f"Attribute 'avm_deflection_index' for item {item.id()} not in valid range 1-5.")

        return deflection_index

    def _get_mac(self, item) -> str:
        """
        return mac for given item
        """

        mac = None
        for i in range(2):
            attribute = 'avm_mac'
            attribute_w_instance = f"{attribute}@{self._plugin_instance.get_instance_name()}"

            mac = self._plugin_instance.get_iattr_value(item.conf, attribute)
            if mac:
                break
            mac = self._plugin_instance.get_iattr_value(item.conf, attribute_w_instance)
            if mac:
                break
            else:
                item = item.return_parent()

        return mac

    # --------------------------------------
    # Properties of FritzDevice
    # --------------------------------------

    def get_host(self):
        """
        Returns the hostname / IP of the FritzDevice

        :return: hostname of the device, as set in plugin.conf
        """
        return self._host

    def get_port(self):
        """
        Returns the port of the FritzDevice

        :return: port of the device, as set in plugin.conf
        """
        return self._port

    def get_verify(self):
        """
        Returns the wether to verify or not

        :return: verify
        """
        return self._verify

    def is_ssl(self):
        """
        Returns information if SSL is enabled

        :return: is ssl enabled, as set in plugin.conf
        """
        return self._ssl

    def is_available(self):
        """
        Returns information if the device is currently available

        :return: boolean, if device is available
        """
        return self._available

    def set_available(self, is_available):
        """
        Sets the boolean, if the device is available

        :param is_available: boolean of the availability status
        """
        self._available = is_available

    def get_user(self):
        """
        Returns the user for the FritzDevice

        :return: user, as set in plugin.conf
        """
        return self._username

    def get_password(self):
        """
        Returns the password for the FritzDevice

        :return: password, as set in plugin.conf
        """
        return self._password

    @property
    def default_connection_service(self):
        return self._data_cache['InternetGatewayDevice']['Layer3Forwarding']['GetDefaultConnectionService']['NewDefaultConnectionService']

    @property
    def manufacturer_name(self):
        if not self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo']:
            self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo'] = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo']['NewManufacturerName']

    @property
    def manufacturer_oui(self):
        if not self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo']:
            self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo'] = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo']['NewManufacturerOUI']

    @property
    def model_name(self):
        if not self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo']:
            self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo'] = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo']['NewModelName']

    @property
    def desciption(self):
        if not self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo']:
            self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo'] = self.client.InternetGatewayDevice.DeviceInfo.GetInfo()
        return self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetInfo']['NewDescription']

    @property
    def safe_port(self):
        if not self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetSecurityPort']:
            self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetSecurityPort'] = self.client.InternetGatewayDevice.DeviceInfo.GetSecurityPort()
        return self._data_cache['InternetGatewayDevice']['DeviceInfo']['GetSecurityPort']['NewSecurityPort']

    # ----------------------------------
    # TBD
    # ----------------------------------
    def update_items(self):

        for item in self._items:
            avm_data_type = self._items[item][0]
            index = self._items[item][1]
            self._plugin_instance.logger.debug(f"FritzDevice: _update_items called: item={item} with avm_data_type={avm_data_type} and index={index}")

            data = self._poll_fritz_device(avm_data_type, index)

            if data is not None:
                item(data, self._plugin_instance.get_shortname())

    def _poll_fritz_device(self, avm_data_type: str, index: int):

        link_ppp = {
            'wan_connection_status': ('WANConnectionDevice', 'WANPPPConnection', 'GetInfo', 'NewConnectionStatus'),
            'wan_connection_error': ('WANConnectionDevice', 'WANPPPConnection', 'GetInfo', 'NewLastConnectionError'),
            'wan_is_connected': ('WANConnectionDevice', 'WANPPPConnection', 'GetInfo', 'NewConnectionStatus'),
            'wan_uptime': ('WANConnectionDevice', 'WANPPPConnection', 'GetInfo', 'NewUptime'),
            'wan_ip': ('WANConnectionDevice', 'WANPPPConnection', 'GetExternalIPAddress', 'NewExternalIPAddress'),
        }

        link_ip = {
            'wan_connection_status': ('WANConnectionDevice', 'WANIPConnection', 'GetInfo', 'NewConnectionStatus'),
            'wan_connection_error': ('WANConnectionDevice', 'WANIPConnection', 'GetInfo', 'NewLastConnectionError'),
            'wan_is_connected': ('WANConnectionDevice', 'WANIPConnection', 'GetInfo', 'NewConnectionStatus'),
            'wan_uptime': ('WANConnectionDevice', 'WANIPConnection', 'GetInfo', 'NewUptime'),
            'wan_ip': ('WANConnectionDevice', 'WANIPConnection', 'GetExternalIPAddress', 'NewExternalIPAddress'),
        }

        link = {
            'uptime': ('InternetGatewayDevice', 'DeviceInfo', 'GetInfo', 'NewUpTime'),
            'serial_number': ('InternetGatewayDevice', 'DeviceInfo', 'GetInfo', 'NewSerialNumber'),
            'software_version': ('InternetGatewayDevice', 'DeviceInfo', 'GetInfo', 'NewSoftwareVersion'),
            'hardware_version': ('InternetGatewayDevice', 'DeviceInfo', 'GetInfo', 'NewHardwareVersion'),
            'myfritz_status': ('InternetGatewayDevice', 'X_AVM_DE_MyFritz', 'GetInfo', 'NewEnabled'),
            'tam': ('InternetGatewayDevice', 'X_AVM_DE_TAM', 'GetInfo', 'NewEnable'),
            'tam_name': ('InternetGatewayDevice', 'X_AVM_DE_TAM', 'GetInfo', 'NewName'),
            'wan_upstream': ('WANDevice', 'WANDSLInterfaceConfig', 'GetInfo', 'NewUpstreamCurrRate'),
            'wan_downstream': ('WANDevice', 'WANDSLInterfaceConfig', 'GetInfo', 'NewDownstreamCurrRate'),
            'wan_total_packets_sent': ('WANDevice', 'WANCommonInterfaceConfig', 'GetTotalPacketsSent', 'NewTotalPacketsSent'),
            'wan_total_packets_received': ('WANDevice', 'WANCommonInterfaceConfig', 'GetTotalPacketsReceived', 'NewTotalPacketsReceived'),
            'wan_current_packets_sent': ('WANDevice', 'WANCommonInterfaceConfig', 'GetAddonInfos', 'NewPacketSendRate'),
            'wan_current_packets_received': ('WANDevice', 'WANCommonInterfaceConfig', 'GetAddonInfos', 'NewPacketReceiveRate'),
            'wan_total_bytes_sent': ('WANDevice', 'WANCommonInterfaceConfig', 'GetTotalBytesSent', 'NewTotalBytesSent'),
            'wan_total_bytes_received': ('WANDevice', 'WANCommonInterfaceConfig', 'GetTotalBytesReceived', 'NewTotalBytesReceived'),
            'wan_current_bytes_sent': ('WANDevice', 'WANCommonInterfaceConfig', 'GetAddonInfos', 'NewByteSendRate'),
            'wan_current_bytes_received': ('WANDevice', 'WANCommonInterfaceConfig', 'GetAddonInfos', 'NewByteReceiveRate'),
            'wan_link': ('WANDevice', 'WANCommonInterfaceConfig', 'GetCommonLinkProperties', 'NewPhysicalLinkStatus'),
            'wlanconfig': ('LANDevice', 'WLANConfiguration', 'GetInfo', 'NewEnable'),
            'wlanconfig_ssid': ('LANDevice', 'WLANConfiguration', 'GetInfo', 'NewSSID'),
            'wlan_guest_time_remaining': ('LANDevice', 'WLANConfiguration', 'X_AVM_DE_GetWLANExtInfo', 'NewX_AVM_DE_TimeRemain'),
            # '':: ('', '', '', ''),
        }

        # Create link dict depending on connection type
        if 'PPP' in self.default_connection_service:
            link.update(link_ppp)
        else:
            link.update(link_ip)

        # define client
        client = 'client'
        if avm_data_type.startswith('wan_current'):
            client = 'client_igd'

        # check if avm_data_type is linked
        if avm_data_type not in link:
            return

        # gather data
        data = self._update_data_cache(client, link[avm_data_type][0], link[avm_data_type][1], link[avm_data_type][2], link[avm_data_type][3], index)

        # correct data
        if avm_data_type == 'wan_is_connected':
            data = True if data == 'Connected' else False
        elif avm_data_type == 'wan_link':
            data = True if data == 'Up' else False

        # return result
        return data

    def _update_data_cache(self, client: str, device: str, service: str, action: str, argument: str = None, index: int = None) -> dict:
        # self._plugin_instance.logger.debug(f"_data_cache called with device={device}, service={service}, action={action}, argument={argument} index={index}")
        if device not in self._data_cache:
            self._data_cache[device] = {}
        if service not in self._data_cache[device]:
            self._data_cache[device][service] = {}
        if action not in self._data_cache[device][service]:
            self._data_cache[device][service][action] = {}

        if index is None:
            if not self._data_cache[device][service][action]:
                self._data_cache[device][service][action] = eval(f"self.{client}.{device}.{service}.{action}()")
            if not argument:
                return self._data_cache[device][service][action]
            else:
                return self._data_cache[device][service][action][argument]
        else:
            if not self._data_cache[device][service][action]:
                self._data_cache[device][service][action] = {}
            if index not in self._data_cache[device][service][action]:
                self._data_cache[device][service][action][index] = eval(f"self.{client}.{device}.{service}[{index}].{action}()")
            if not argument:
                return self._data_cache[device][service][action][index]
            else:
                return self._data_cache[device][service][action][index][argument]

    def _request(self, url: str, timeout: int, verify: bool):
        request = requests.get(url, timeout=timeout, verify=verify)
        if request.status_code == 200:
            return request

    def _request_response_to_xml(self, request):
        root = etree.fromstring(request.content)
        return root

    # ----------------------------------
    # Fritz Device methods, reboot, wol, reconnect
    # ----------------------------------

    def reboot(self):
        """
        Reboots the FritzDevice

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceconfigSCPD.pdf
        """

        self.client.InternetGatewayDevice.DeviceConfig.Reboot()

    def reconnect(self):
        """
        Reconnects the FritzDevice to the WAN

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wanipconnSCPD.pdf
              http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wanpppconnSCPD.pdf
        """

        if 'PPP' in self.default_connection_service:
            self.client.WANConnectionDevice.WANPPPConnection.ForceTermination()
        else:
            self.client.WANConnectionDevice.WANIPPConnection.ForceTermination()

    def wol(self, mac_address: str):
        """
        Sends a WOL (WakeOnLAN) command to a MAC address

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param mac_address: MAC address of the device to wake up
        """

        self.client.LanDevice.Hosts.X_AVM_DE_GetAutoWakeOnLANByMACAddress(NewMACAddress=mac_address)

    # ----------------------------------
    # caller methods
    # ----------------------------------
    def get_call_origin(self) -> str:
        """
        Gets the phone name, currently set as call_origin.

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        :return: String phone name
        """

        phone_name = self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_DialGetConfig()['NewX_AVM-DE_PhoneName']
        if phone_name is None:
            self._plugin_instance.logger.error("No call origin available.")
        return phone_name

    def get_phone_name(self, index: int = 1) -> str:
        """
        Get the phone name at a specific index. The returned value can be used as phone_name for set_call_origin.

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param index: Parameter is an INT, starting from 1. In case an index does not exist, an error is logged.
        :return: String phone name
        """

        phone_name = self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_GetPhonePort()['NewX_AVM-DE_PhoneName']
        if phone_name is None:
            self._plugin_instance.logger.error(f"No phone name available at provided index {index}")
        return phone_name

    def set_call_origin(self, phone_name: str):
        """
        Sets the call origin, e.g. before running 'start_call'

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param phone_name: full phone identifier, could be e.g. '\*\*610' for an internal device
        """

        self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_DialSetConfig(NewX_AVM_DE_PhoneName=phone_name.strip())

    def start_call(self, phone_number: str):
        """
        Triggers a call for a given phone number

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param phone_number: full phone number to call
        """

        self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_DialNumber(NewX_AVM_DE_PhoneNumber=phone_number.strip())

    def cancel_call(self):
        """
        Cancels an active call

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        """

        self.client.InternetGatewayDevice.X_VoIP.X_AVM_DE_DialHangup()

    def get_contact_name_by_phone_number(self, phone_number: str = '', phonebook_id: int = 0) -> str:
        """
        """

        if phone_number.endswith('#'):
            phone_number = phone_number.strip('#')

        phonebook_url = self.client.InternetGatewayDevice.X_AVM_DE_OnTel.GetPhonebook(NewPhonebookID=phonebook_id)[
            'NewPhonebookURL']
        phonebooks = self._request_response_to_xml(self._request(phonebook_url, self._timeout, self._verify))
        if phonebooks is not None:
            for phonebook in phonebooks.iter('phonebook'):
                for contact in phonebook.iter('contact'):
                    for number in contact.findall('.//number'):
                        if number.text:
                            nr = number.text.strip()
                            if phone_number in nr:
                                return contact.find('.//realName').text
        else:
            self._plugin_instance.logger.error("Phonebook not available on the FritzDevice")

    def get_phone_numbers_by_name(self, name: str = '', phonebook_id: int = 0) -> dict:
        """
        """
        tel_type = {"mobile": "CELL", "work": "WORK", "home": "HOME"}
        result_numbers = {}
        phonebook_url = self.client.InternetGatewayDevice.X_AVM_DE_OnTel.GetPhonebook(NewPhonebookID=phonebook_id)[
            'NewPhonebookURL']
        phonebooks = self._request_response_to_xml(self._request(phonebook_url, self._timeout, self._verify))
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
                                    result_number_dict['type'] = tel_type[number.attrib["type"]]
                                    result_numbers[real_name.text].append(result_number_dict)
            return result_numbers
        else:
            self._plugin_instance.logger.error("Phonebook not available on the FritzDevice")

    def get_calllist_from_cache(self) -> list:
        """
        returns the cached calllist when all items are initialized. The filter set by plugin.conf is applied.

        :return: Array of calllist entries
        """

        if not self._calllist_cache:
            self._calllist_cache = self.get_calllist(self._call_monitor_incoming_filter)
        elif len(self._calllist_cache) == 0:
            self._calllist_cache = self.get_calllist(self._call_monitor_incoming_filter)
        return self._calllist_cache

    def get_calllist(self, filter_incoming: str = '') -> list:
        """
        """

        calllist_url = self.client.InternetGatewayDevice.X_AVM_DE_OnTel.GetCallList()['NewCallListURL']
        calllist = self._request_response_to_xml(self._request(calllist_url, self._timeout, self._verify))

        if calllist:
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
            self._plugin_instance.logger.error("Calllist not available on the FritzDevice")

    # ----------------------------------
    # get logs methods
    # ----------------------------------
    def get_device_log_from_tr064(self) -> str:
        """
        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceinfoSCPD.pdf

        Gets the Device Log via TR-064
        :return: Array of Device Log Entries (Strings)
        """

        device_log = self.client.InternetGatewayDevice.DeviceInfo.GetDeviceLog()['NewDeviceLog']
        if device_log is None:
            return ""
        return device_log.split("\n")

    # ----------------------------------
    # set wlan methods
    # ----------------------------------
    def set_wlan_config(self, wlan_index: int, new_enable: bool = False):
        """
        Set WLAN Config

        uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
        """

        # set WLAN to ON/OFF
        self.client.LANDevice.WLANConfiguration[wlan_index].SetEnable(NewEnable=int(new_enable))
        # check if remaining time is set as item
        for item in self._items:  # search for guest time remaining item.
            if self._items[item][0] == 'wlan_guest_time_remaining' and self._items[item][1] == wlan_index:
                data = self._poll_fritz_device('wlan_guest_time_remaining', wlan_index)
                if data is not None:
                    item(data, self._plugin_instance.get_shortname())

    # ----------------------------------
    # set tam methods
    # ----------------------------------
    def set_tam(self, tam_index: int = 0, new_enable: bool = False):
        """
        Set TAM
        """

        self.client.InternetGatewayDevice.X_AVM_DE_TAM.SetEnable(NewIndex=tam_index, NewEnable=int(new_enable))

    # ----------------------------------
    # set home automation switch
    # ----------------------------------
    def set_aha_device(self, ain: str = '', set_switch: bool = False):
        """
        Set AHA-Device via TR-064 protocol
        """

        # SwitchState: OFF, ON, TOGGLE, UNDEFINED
        switch_state = "ON" if set_switch is True else "OFF"
        self.client.InternetGatewayDevice.X_AVM_DE_Homeauto.SetSwitch(NewAIN=ain, NewSwitchState=switch_state)

    # ----------------------------------
    # set deflection
    # ----------------------------------
    def set_deflection(self, deflection_id: int = 0, new_enable: bool = False):
        """
        Enable or disable a deflection.
        DeflectionID is in the range of 0 .. NumberOfDeflections-1
        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf

        :param deflection_id: deflection id (default: 0)
        :param new_enable: new enable (default: False)
        """

        self.client.InternetGatewayDevice.X_AVM_DE_OnTel.SetDeflectionEnable(NewDeflectionId=deflection_id, NewEnable=int(new_enable))

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

        is_active = self.client.InternetGatewayDevice.Hosts.GetSpecificHostEntry(NewMACAddress=mac_address)['NewActive']
        return bool(is_active)

    def get_hosts(self, only_active: bool = False) -> list:
        """
        Gets the information (host details) of all hosts as an array of dicts

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param only_active: bool, if only active hosts shall be returned
        :return: Array host dicts (see get_host_details)
        """

        number_of_hosts = self.client.InternetGatewayDevice.Hosts.GetHostNumberOfEntries()['NewHostNumberOfEntries']
        hosts = []
        for i in range(1, number_of_hosts):
            host = self.get_host_details(i)
            if not only_active or (only_active and host['is_active']):
                hosts.append(host)
        return hosts

    def get_host_details(self, index: int):
        """
        Gets the information of a hosts at a specific index

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param index: index of host in hosts list
        :return: Dict host data: name, interface_type, ip_address, address_source, mac_address, is_active, lease_time_remaining
        """

        host_info = self.client.InternetGatewayDevice.Hosts.GetGenericHostEntry(NewIndex=index)
        host = {
            'name': host_info['NewHostName'],
            'interface_type': host_info['NewInterfaceType'],
            'ip_address': host_info['NewIPAddress'],
            'address_source': host_info['NewAddressSource'],
            'mac_address': host_info['NewMACAddress'],
            'is_active': bool(host_info['NewActive']),
            'lease_time_remaining': host_info['NewLeaseTimeRemaining']
        }
        return host

    class Client:
        """TR-064 client.
        :param str username:    Username with access to router.
        :param str password:    Passwort to access router.
        :param str base_url:    URL to router.
        """

        def __init__(self, username, password, verify, base_url='https://192.168.178.1:49443', description_file=FRITZ_TR64_DESC_FILE, plugin_instance=None):

            # handle plugin instance
            self._plugin_instance = plugin_instance

            self.base_url = base_url
            self.auth = HTTPDigestAuth(username, password)
            self.verify = verify
            self.description_file = description_file

            self.devices = {}
            self._plugin_instance.logger.debug(f"Init Client for description file={self.description_file}")

        def __getattr__(self, name):
            if name not in self.devices:
                self._fetch_devices(self.description_file)

            if name in self.devices:
                return self.devices[name]

        def _fetch_devices(self, description_file):

            """Fetch device description."""

            self._plugin_instance.logger.debug(f"_fetch_devices called for description file={description_file}")

            request = requests.get(f'{self.base_url}/{description_file}', verify=self.verify)

            if description_file == 'igddesc.xml':
                namespaces = IGD_DEVICE_NAMESPACE
            else:
                namespaces = TR064_DEVICE_NAMESPACE

            if request.status_code == 200:
                xml = etree.parse(BytesIO(request.content))

                for device in xml.findall('.//device', namespaces=namespaces):
                    name = device.findtext('deviceType', namespaces=namespaces).split(':')[-2]
                    if name not in self.devices:
                        self.devices[name] = FritzDevice.Device(device, self.auth, self.verify, self.base_url, description_file)

            self._plugin_instance.logger.debug(f"Client: {self.description_file} devices={self.devices}")

    class Device:
        """TR-064 device.
        :param lxml.etree.Element xml:          XML device element
        :param HTTPBasicAuthHandler auth:       HTTPBasicAuthHandler object, e.g. HTTPDigestAuth
        :param str base_url:                    URL to router.
        """

        def __init__(self, xml, auth, verify, base_url, description_file):
            # init logger
            self.logger = logging.getLogger(__name__)
            self.services = {}
            self.verify = verify

            if description_file == 'igddesc.xml':
                namespaces = IGD_DEVICE_NAMESPACE
            else:
                namespaces = TR064_DEVICE_NAMESPACE

            for service in xml.findall('./serviceList/service', namespaces=namespaces):
                service_type = service.findtext('serviceType', namespaces=namespaces)
                service_id = service.findtext('serviceId', namespaces=namespaces)
                control_url = service.findtext('controlURL', namespaces=namespaces)
                event_sub_url = service.findtext('eventSubURL', namespaces=namespaces)
                scpdurl = service.findtext('SCPDURL', namespaces=namespaces)

                name = service_type.split(':')[-2].replace('-', '_')
                if name not in self.services:
                    self.services[name] = FritzDevice.ServiceList()

                self.services[name].append(
                    FritzDevice.Service(
                        auth,
                        self.verify,
                        base_url,
                        service_type,
                        service_id,
                        scpdurl,
                        control_url,
                        event_sub_url,
                        description_file
                    )
                )

            # self.logger.debug(f"Device: {description_file} services={self.services}")

        def __getattr__(self, name: str):
            if name in self.services:
                return self.services[name]

    class ServiceList(list):
        """Service list."""

        def __getattr__(self, name: str):
            """Direct access to first list entry if brackets omit."""
            return self[0].__getattr__(name)

        def __getitem__(self, index):
            """Override bracket operator to return TR-064 exception."""
            if len(self) > index:
                return super().__getitem__(index)

    class Service:
        """TR-064 service."""

        def __init__(self, auth, verify, base_url, service_type, service_id, scpdurl, control_url, event_sub_url, description_file):
            # init logger
            self.logger = logging.getLogger(__name__)

            self.auth = auth
            self.verify = verify
            self.base_url = base_url
            self.service_type = service_type
            self.service_id = service_id
            self.scpdurl = scpdurl
            self.control_url = control_url
            self.event_sub_url = event_sub_url
            self.actions = {}
            self.description_file = description_file

            if description_file == 'igddesc.xml':
                self.namespaces = IGD_SERVICE_NAMESPACE
            else:
                self.namespaces = TR064_SERVICE_NAMESPACE

        def __getattr__(self, name: str):
            if name not in self.actions:
                self._fetch_actions(self.scpdurl)

            if name in self.actions:
                return self.actions[name]

        def _fetch_actions(self, scpdurl: str):
            """Fetch action description."""
            request = requests.get(f'{self.base_url}{scpdurl}', verify=self.verify)
            if request.status_code == 200:
                xml = etree.parse(BytesIO(request.content))

                for action in xml.findall('./actionList/action', namespaces=self.namespaces):
                    name = action.findtext('name', namespaces=self.namespaces)
                    canonical_name = name.replace('-', '_')
                    self.actions[canonical_name] = FritzDevice.Action(
                        action,
                        self.auth,
                        self.base_url,
                        name,
                        self.service_type,
                        self.service_id,
                        self.control_url,
                        self.verify,
                        self.namespaces
                    )

                # self.logger.debug(f"Service: {self.description_file} scpdurl={self.scpdurl} with actions={self.actions}")

    class Action:
        """TR-064 action.
        :param lxml.etree.Element xml:      XML action element
        :param HTTPBasicAuthHandler auth:   HTTPBasicAuthHandler object, e.g. HTTPDigestAuth
        :param str base_url:                URL to router.
        :param str name:                    Action name
        :param str service_type:            Service type
        :param str service_id:              Service ID
        :param str control_url:             Control URL
        """

        def __init__(self, xml, auth, base_url, name, service_type, service_id, control_url, verify, namespaces):

            # init logger
            self.logger = logging.getLogger(__name__)

            self.auth = auth
            self.verify = verify
            self.base_url = base_url
            self.name = name
            self.service_type = service_type
            self.service_id = service_id
            self.control_url = control_url

            etree.register_namespace('s', 'http://schemas.xmlsoap.org/soap/envelope/')
            etree.register_namespace('h', 'http://soap-authentication.org/digest/2001/10/')

            self.headers = {'content-type': 'text/xml; charset="utf-8"'}
            self.envelope = etree.Element(
                '{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
                attrib={
                    '{http://schemas.xmlsoap.org/soap/envelope/}encodingStyle':
                        'http://schemas.xmlsoap.org/soap/encoding/'})
            self.body = etree.SubElement(self.envelope, '{http://schemas.xmlsoap.org/soap/envelope/}Body')

            self.in_arguments = {}
            self.out_arguments = {}

            for argument in xml.findall('./argumentList/argument', namespaces=namespaces):
                name = argument.findtext('name', namespaces=namespaces)
                direction = argument.findtext('direction', namespaces=namespaces)

                if direction == 'in':
                    self.in_arguments[name.replace('-', '_')] = name

                if direction == 'out':
                    self.out_arguments[name] = name.replace('-', '_')

        def __call__(self, **kwargs):
            missing_arguments = self.in_arguments.keys() - kwargs.keys()
            if missing_arguments:
                self.logger.warning('Missing argument(s) \'' + "', '".join(missing_arguments) + '\'')

            unknown_arguments = kwargs.keys() - self.in_arguments.keys()
            if unknown_arguments:
                self.logger.warning('Unknown argument(s) \'' + "', '".join(unknown_arguments) + '\'')

            # Add SOAP action to header
            self.headers['soapaction'] = '"{}#{}"'.format(self.service_type, self.name)
            etree.register_namespace('u', self.service_type)

            # Prepare body for request
            self.body.clear()
            action = etree.SubElement(self.body, '{{{}}}{}'.format(self.service_type, self.name))
            for key in kwargs:
                arg = etree.SubElement(action, self.in_arguments[key])
                arg.text = str(kwargs[key])

            # soap._InitChallenge(header)
            data = etree.tostring(self.envelope, encoding='utf-8', xml_declaration=True).decode()
            request = requests.post(f'{self.base_url}{self.control_url}',
                                    headers=self.headers,
                                    auth=self.auth,
                                    data=data,
                                    verify=self.verify)
            if request.status_code != 200:
                return request.status_code

            # Translate response and prepare dict
            xml = etree.parse(BytesIO(request.content))
            response = FritzDevice.AttributeDict()
            for arg in list(xml.find('.//{{{}}}{}Response'.format(self.service_type, self.name))):
                name = self.out_arguments[arg.tag]
                response[name] = arg.text
            # self.logger.debug(f"__call__: control_url={self.control_url} response={response}")
            return response

    class AttributeDict(dict):
        """Direct access dict entries like attributes."""

        def __getattr__(self, name):
            return self[name]


class FritzHome:
    """Fritzhome object to communicate with the device."""

    _login_route = "/login_sid.lua?version=2"
    _event_route = '/query.lua?mq_log=logger:status/log&sid='
    _homeauto_route = '/webservices/homeautoswitch.lua'
    _internet_status_route = '/internet/inetstat_monitor.lua?sid='

    def __init__(self, host, ssl, verify, user, password, plugin_instance):

        self._plugin_instance = plugin_instance
        self._plugin_instance.logger.debug("Init Fritzhome")

        self._host = host
        self._ssl = ssl
        self._verify = verify
        self._user = user
        self._password = password

        self._sid = None
        self._devices: Dict[str, FritzHome.FritzhomeDevice] = {}
        self._templates: Dict[str, FritzHome.FritzhomeTemplate] = {}
        self._logged_in = False
        self._items = dict()
        self._aha_devices = dict()
        self._session = requests.Session()

    def register_item(self, item, avm_data_type: str):

        # handle aha items
        avm_ain = self._get_item_ain(item)
        if avm_ain is not None:
            self._plugin_instance.logger.debug(f"Item {item.id()} with avm device attribute and defined 'avm_ain' found; append to list.")
            self._items[item] = (avm_data_type, avm_ain)
        else:
            self._plugin_instance.logger.warning(f"Item {item.id()} with avm attribute found, but 'avm_ain' is not defined; Item will be ignored.")

    def _get_item_ain(self, item) -> str:
        """
        Get AIN of device from item.conf
        """

        ain_device = None

        lookup_item = item
        for i in range(2):
            attribute = 'ain'
            attribute_w_instance = f"{attribute}@{self._plugin_instance.get_instance_name()}"

            ain_device = self._plugin_instance.get_iattr_value(lookup_item.conf, attribute)
            if ain_device is not None:
                break
            ain_device = self._plugin_instance.get_iattr_value(lookup_item.conf, attribute_w_instance)
            if ain_device is not None:
                break
            else:
                lookup_item = lookup_item.return_parent()

        if ain_device:
            # deprecated warning for attribute 'ain'
            self._plugin_instance.logger.warning(
                f"Item {item.id()} uses deprecated 'ain' attribute. Please consider to switch to 'avm_ain'.")
        else:
            lookup_item = item
            for i in range(2):
                attribute = 'avm2_ain'
                attribute_w_instance = f"{attribute}@{self._plugin_instance.get_instance_name()}"

                ain_device = self._plugin_instance.get_iattr_value(lookup_item.conf, attribute_w_instance)
                if ain_device is not None:
                    break
                ain_device = self._plugin_instance.get_iattr_value(lookup_item.conf, attribute)
                if ain_device is not None:
                    break
                else:
                    lookup_item = lookup_item.return_parent()

        if ain_device is not None:
            self._plugin_instance.logger.error('Device AIN is not defined or instance not given')
        return str(ain_device)

    def _poll_aha(self):

        self._plugin_instance.logger.debug(f'Starting AHA update loop for instance {self._plugin_instance.get_instance_name()}.')

        # update devices
        self.update_devices()

        # get device dict
        _device_dict = self.get_devices_as_dict()

        for ain in _device_dict:
            if not self._aha_devices.get(ain):
                self._aha_devices[ain] = {}
                self._aha_devices[ain]['connected_to_item'] = False
                self._aha_devices[ain]['switch'] = {}
                self._aha_devices[ain]['temperature_sensor'] = {}
                self._aha_devices[ain]['thermostat'] = {}
                self._aha_devices[ain]['alarm'] = {}

            self._aha_devices[ain]['online'] = bool(_device_dict[ain].present)
            self._aha_devices[ain]['name'] = _device_dict[ain].name
            self._aha_devices[ain]['productname'] = _device_dict[ain].productname
            self._aha_devices[ain]['manufacturer'] = _device_dict[ain].manufacturer
            self._aha_devices[ain]['fw_version'] = _device_dict[ain].fw_version
            self._aha_devices[ain]['lock'] = bool(_device_dict[ain].lock)
            self._aha_devices[ain]['device_lock'] = bool(_device_dict[ain].device_lock)
            self._aha_devices[ain]['functions'] = []

            if _device_dict[ain].has_thermostat:
                self._aha_devices[ain]['functions'].append('thermostat')
                self._aha_devices[ain]['thermostat']['actual_temperature'] = _device_dict[ain].actual_temperature
                self._aha_devices[ain]['thermostat']['target_temperature'] = _device_dict[ain].target_temperature
                self._aha_devices[ain]['thermostat']['comfort_temperature'] = _device_dict[ain].comfort_temperature
                self._aha_devices[ain]['thermostat']['eco_temperature'] = _device_dict[ain].eco_temperature
                self._aha_devices[ain]['thermostat']['battery_low'] = bool(_device_dict[ain].battery_low)
                self._aha_devices[ain]['thermostat']['battery_level'] = _device_dict[ain].battery_level
                self._aha_devices[ain]['thermostat']['window_open'] = bool(_device_dict[ain].window_open)
                self._aha_devices[ain]['thermostat']['summer_active'] = bool(_device_dict[ain].summer_active)
                self._aha_devices[ain]['thermostat']['holiday_active'] = bool(_device_dict[ain].holiday_active)

            if _device_dict[ain].has_switch:
                self._aha_devices[ain]['functions'].append('switch')
                self._aha_devices[ain]['switch']['switch_state'] = bool(_device_dict[ain].switch_state)
                self._aha_devices[ain]['switch']['power'] = _device_dict[ain].power
                self._aha_devices[ain]['switch']['energy'] = _device_dict[ain].energy
                self._aha_devices[ain]['switch']['voltage'] = _device_dict[ain].voltage

            if _device_dict[ain].has_temperature_sensor:
                self._aha_devices[ain]['functions'].append('temperature_sensor')
                self._aha_devices[ain]['temperature_sensor']['temperature'] = _device_dict[ain].temperature
                self._aha_devices[ain]['temperature_sensor']['offset'] = _device_dict[ain].offset

            if _device_dict[ain].has_alarm:
                self._aha_devices[ain]['functions'].append('alarm')
                self._aha_devices[ain]['alarm']['alert_state'] = bool(_device_dict[ain].alert_state)

    def update_items(self):
        """
        Update smarthome item values using information from dict '_aha_devices'
        """

        # first poll current data
        self._poll_aha()

        for item in self._items:
            # get avm_data_type and ain
            _avm_data_type = self._items[item][0]
            _ain = self._items[item][1]

            # get device sub-dict from dict
            device = self._items.get(_ain, None)

            if device is not None:
                # Attributes that are write only commands with no corresponding read commands are excluded from status updates via update black list:
                update_black_list = ['switch_toggle']

                if _avm_data_type not in update_black_list:
                    # Remove "set_" prefix to set corresponding r/o or r/w item to returned value:
                    if _avm_data_type.startswith('set_'):
                        _avm_data_type = _avm_data_type[len('set_'):]
                    # set item
                    if _avm_data_type in device:
                        item(device[_avm_data_type], self._plugin_instance.get_shortname())
                    else:
                        self._plugin_instance.logger.warning(f'Attribute <{_avm_data_type}> at device <{_ain}> to be set to Item <{item}> is not available.')
            else:
                self._plugin_instance.logger.warning(f'No values for item {item.id()} with AIN {_ain} available.')

    def _request(self, url: str, params: dict = None, timeout: int = 10, result: str = 'text') -> Union[str, dict]:
        """Send a request with parameters.
        :param url          URL to be requested
        :param params       params for request
        :param timeout      timeout
        :param result       type of result
        :return             request response
        :type return
        """

        rsp = self._session.get(url, params=params, timeout=timeout, verify=self._verify)

        status_code = rsp.status_code
        if status_code == 200:
            self._plugin_instance.logger.debug("Sending HTTP request successful")
            if result == 'json':
                try:
                    data = rsp.json()
                except JSONDecodeError:
                    self._plugin_instance.logger.error('Error occurred during parsing request response to json')
                else:
                    self._plugin_instance.logger.error(type(data))
                    return data
            else:
                return rsp.text.strip()
        elif status_code == 403:
            self._plugin_instance.logger.debug("HTTP access denied. Try to get new Session ID.")
        else:
            self._plugin_instance.logger.error(f"HTTP request error code: {status_code}")
            rsp.raise_for_status()
            self._plugin_instance.logger.debug(f"Url: {url}")
            self._plugin_instance.logger.debug(f"Params: {params}")

    def _login_request(self, username=None, challenge_response=None):
        """Send a login request with parameters."""
        url = self.get_prefixed_host() + self._login_route
        # self._plugin_instance.logger.debug(f"_login_request: url={url}")
        params = {}
        if username:
            params["username"] = username
        if challenge_response:
            params["response"] = challenge_response
        # self._plugin_instance.logger.debug(f"_login_request: params={params}")
        plain = self._request(url, params)
        # self._plugin_instance.logger.debug(f"_login_request: plain={plain}")
        dom = ElementTree.fromstring(plain)
        sid = dom.findtext("SID")
        challenge = dom.findtext("Challenge")
        blocktime = int(dom.findtext("BlockTime"))

        # self._plugin_instance.logger.debug(f"_login_request: sid={sid}, challenge={challenge}, blocktime={blocktime}")
        return sid, challenge, blocktime

    def _logout_request(self):
        """Send a logout request."""
        url = self.get_prefixed_host() + self._login_route
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
        """Send an AHA request."""

        if not self._logged_in:
            self.login()

        url = self.get_prefixed_host() + self._homeauto_route
        params = {"switchcmd": cmd, "sid": self._sid}
        if param:
            params.update(param)
        if ain:
            params["ain"] = ain

        plain = self._request(url, params)

        if plain == "inval":
            self._plugin_instance.logger.error("InvalidError")
            return

        if rf == 'bool':
            return bool(int(plain))
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
        self._plugin_instance.logger.debug("AHA login called")
        try:
            (sid, challenge, blocktime) = self._login_request()
            if blocktime > 0:
                self._plugin_instance.logger.debug(f"Waiting for {blocktime} seconds...")
                time.sleep(blocktime)

            if sid == "0000000000000000":
                if challenge.startswith('2$'):
                    self._plugin_instance.logger.debug("PBKDF2 supported")
                    challenge_response = self._calculate_pbkdf2_response(challenge, self._password)
                else:
                    self._plugin_instance.logger.debug("Falling back to MD5")
                    challenge_response = self._calculate_md5_response(challenge, self._password)
                (sid2, challenge, blocktime) = self._login_request(username=self._user, challenge_response=challenge_response)
                if sid2 == "0000000000000000":
                    self._plugin_instance.logger.warning(f"login failed {sid2}")
                    self._plugin_instance.logger.error(f"LoginError for {self._user}")
                    return
                self._sid = sid2
        except Exception as e:
            self._plugin_instance.logger.error(f"LoginError {e} occurred for {self._user}")
        else:
            self._logged_in = True

    def logout(self):
        """Logout."""
        self._plugin_instance.logger.debug("AHA logout called")
        self._logout_request()
        self._sid = None
        self._logged_in = False

    def check_sid(self):
        """
        Check if knows Session ID is still valid
        """

        self._plugin_instance.logger.debug(f"check_sid called")
        url = self.get_prefixed_host() + self._login_route
        params = {"sid": self._sid}
        plain = self._request(url, params)
        dom = ElementTree.fromstring(plain)
        sid = dom.findtext("SID")

        if sid == "0000000000000000":
            self._plugin_instance.logger.warning(f"Session ID is invalid. Try to generate new one.")
            self.login()
        else:
            self._plugin_instance.logger.info(f"Session ID is still valid.")

    def get_prefixed_host(self):
        """Choose the correct protocol prefix for the host.
        Supports three input formats:
        - https://<host>(requests use strict certificate validation by default)
        - http://<host> (unecrypted)
        - <host> (unencrypted)
        """
        host = self._host
        if not host.startswith("https://") or not host.startswith("http://"):
            if self._ssl:
                host = "https://" + host
            else:
                host = "http://" + host
        return host

    def update_devices(self):
        self._plugin_instance.logger.info("Updating Devices ...")
        if self._devices is None:
            self._devices = {}

        for element in self.get_device_elements():
            if element.attrib["identifier"] in self._devices.keys():
                self._plugin_instance.logger.info("Updating already existing Device " + element.attrib["identifier"])
                self._devices[element.attrib["identifier"]]._update_from_node(element)
            else:
                self._plugin_instance.logger.info("Adding new Device " + element.attrib["identifier"])
                device = FritzHome.FritzhomeDevice(self, node=element)
                self._devices[device.ain] = device
        return True

    def _get_listinfo_elements(self, entity_type):
        """Get the DOM elements for the entity list."""
        plain = self._aha_request("get" + entity_type + "listinfos")

        if plain is None:
            return

        dom = ElementTree.fromstring(plain)
        return dom.findall(entity_type)

    def get_device_elements(self):
        """Get the DOM elements for the device list."""
        return self._get_listinfo_elements("device")

    def get_device_element(self, ain):
        """Get the DOM element for the specified device."""
        elements = self.get_device_elements()
        for element in elements:
            if element.attrib["identifier"] == ain:
                return element
        return None

    def get_devices(self):
        """Get the list of all known devices."""
        return list(self.get_devices_as_dict().values())

    def get_devices_as_dict(self):
        """Get the list of all known devices."""
        if self._devices is None:
            self.update_devices()
        return self._devices

    def get_device_by_ain(self, ain):
        """Return a device specified by the AIN."""
        return self.get_devices_as_dict()[ain]

    def get_device_present(self, ain):
        """Get the device presence."""
        return self._aha_request("getswitchpresent", ain=ain, rf='bool')

    def get_device_name(self, ain):
        """Get the device name."""
        return self._aha_request("getswitchname", ain=ain)

    def get_switch_state(self, ain):
        """Get the switch state."""
        return self._aha_request("getswitchstate", ain=ain, rf='bool')

    def set_switch_state_on(self, ain):
        """Set the switch to on state."""
        return self._aha_request("setswitchon", ain=ain, rf='bool')

    def set_switch_state_off(self, ain):
        """Set the switch to off state."""
        return self._aha_request("setswitchoff", ain=ain, rf='bool')

    def set_switch_state_toggle(self, ain):
        """Toggle the switch state."""
        return self._aha_request("setswitchtoggle", ain=ain, rf='bool')

    def get_switch_power(self, ain):
        """Get the switch power consumption."""
        return self._aha_request("getswitchpower", ain=ain, rf='int')

    def get_switch_energy(self, ain):
        """Get the switch energy."""
        return self._aha_request("getswitchenergy", ain=ain, rf='int')

    def get_temperature(self, ain):
        """Get the device temperature sensor value."""
        return self._aha_request("gettemperature", ain=ain, rf='float') / 10.0

    def _get_temperature(self, ain, name):
        plain = self._aha_request(name, ain=ain, rf='float')
        return (plain - 16) / 2 + 8

    def get_target_temperature(self, ain):
        """Get the thermostate target temperature."""
        return self._get_temperature(ain, "gethkrtsoll")

    def set_target_temperature(self, ain, temperature):
        """Set the thermostate target temperature."""
        temp = int(16 + ((float(temperature) - 8) * 2))

        if temp < min(range(16, 56)):
            temp = 253
        elif temp > max(range(16, 56)):
            temp = 254

        self._aha_request("sethkrtsoll", ain=ain, param={'param': temp})

    def set_window_open(self, ain, seconds):
        """Set the thermostate target temperature."""
        endtimestamp = int(time.time() + seconds)

        self._aha_request("sethkrwindowopen", ain=ain, param={'endtimestamp': endtimestamp})

    def get_comfort_temperature(self, ain):
        """Get the thermostate comfort temperature."""
        return self._get_temperature(ain, "gethkrkomfort")

    def get_eco_temperature(self, ain):
        """Get the thermostate eco temperature."""
        return self._get_temperature(ain, "gethkrabsenk")

    def get_device_statistics(self, ain):
        """Get device statistics."""
        plain = self._aha_request("getbasicdevicestats", ain=ain)
        return plain

    # Lightbulb-related commands

    def set_state_off(self, ain):
        """Set the switch/actuator/lightbulb to on state."""
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 0})

    def set_state_on(self, ain):
        """Set the switch/actuator/lightbulb to on state."""
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 1})

    def set_state_toggle(self, ain):
        """Toggle the switch/actuator/lightbulb state."""
        self._aha_request("setsimpleonoff", ain=ain, param={'onoff': 2})

    def set_level(self, ain, level):
        """Set level/brightness/height in interval [0,255]."""
        if level < 0:
            level = 0  # 0%
        elif level > 255:
            level = 255  # 100 %

        self._aha_request("setlevel", ain=ain, param={'level': int(level)})

    def set_level_percentage(self, ain, level):
        """Set level/brightness/height in interval [0,100]."""
        # Scale percentage to [0,255] interval
        self.set_level(ain, int(level * 2.55))

    def _get_colordefaults(self, ain):
        plain = self._aha_request("getcolordefaults", ain=ain)
        return ElementTree.fromstring(plain)

    def get_colors(self, ain):
        """Get colors (HSV-space) supported by this lightbulb."""
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
        """Set hue and saturation.
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

    def get_color_temps(self, ain):
        """Get temperatures supported by this lightbulb."""
        colordefaults = self._get_colordefaults(ain)
        temperatures = []
        for temp in colordefaults.iter('temp'):
            temperatures.append(temp.get("value"))
        return temperatures

    def set_color_temp(self, ain, temperature, duration=0):
        """Set color temperature.
        temperature: temperature element obtained from get_temperatures()
        duration: Speed of change in seconds, 0 = instant
        """
        params = {
            'temperature': int(temperature),
            "duration": int(duration) * 10
        }
        self._aha_request("setcolortemperature", ain=ain, param=params)

    # Template-related commands

    def update_templates(self):
        self._plugin_instance.logger.info("Updating Templates ...")
        if self._templates is None:
            self._templates = {}

        for element in self.get_template_elements():
            if element.attrib["identifier"] in self._templates.keys():
                self._plugin_instance.logger.info(
                    "Updating already existing Template " + element.attrib["identifier"]
                )
                self._templates[element.attrib["identifier"]]._update_from_node(element)
            else:
                self._plugin_instance.logger.info("Adding new Template " + element.attrib["identifier"])
                template = FritzHome.FritzhomeTemplate(self, node=element)
                self._templates[template.ain] = template
        return True

    def get_template_elements(self):
        """Get the DOM elements for the template list."""
        return self._get_listinfo_elements("template")

    def get_templates(self):
        """Get the list of all known templates."""
        return list(self.get_templates_as_dict().values())

    def get_templates_as_dict(self):
        """Get the list of all known templates."""
        if self._templates is None:
            self.update_templates()
        return self._templates

    def get_template_by_ain(self, ain):
        """Return a template specified by the AIN."""
        return self.get_templates_as_dict()[ain]

    def apply_template(self, ain):
        """Applies a template."""
        self._aha_request("applytemplate", ain=ain)

    def get_device_log_from_lua(self):
        """
        Gets the Device Log from the LUA HTTP Interface via LUA Scripts (more complete than the get_device_log TR-064 version.
        :return: Array of Device Log Entries (text, type, category, timestamp, date, time)
        """

        if not self._logged_in:
            self.login()

        url = self.get_prefixed_host() + self._event_route
        params = {"sid": self._sid}
        data = self._request(url, params, result='json')['mq_log']
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

    class FritzhomeDeviceFeatures(IntFlag):
        ALARM = 0x0010
        UNKNOWN = 0x0020
        BUTTON = 0x0020
        THERMOSTAT = 0x0040
        POWER_METER = 0x0080
        TEMPERATURE = 0x0100
        SWITCH = 0x0200
        DECT_REPEATER = 0x0400
        MICROPHONE = 0x0800
        HANFUN = 0x2000
        SWITCHABLE = 0x8000
        DIMMABLE = 0x10000
        LIGHTBULB = 0x20000

    class FritzhomeEntityBase(ABC):
        """The Fritzhome Entity class."""

        def __init__(self, fritz=None, node=None):
            # init logger
            self.logger = logging.getLogger(__name__)

            self._fritz = None
            self.ain: str = ''
            self._functionsbitmask = None

            if fritz is not None:
                self._fritz = fritz
            if node is not None:
                self._update_from_node(node)

        def __repr__(self):
            """Return a string."""
            return f"{self.ain} {self.name}"

        def _has_feature(self, feature) -> bool:
            return feature in FritzHome.FritzhomeDeviceFeatures(self._functionsbitmask)

        def _update_from_node(self, node):
            # self.logger.debug(ElementTree.tostring(node))
            self.ain = node.attrib["identifier"]
            self._functionsbitmask = int(node.attrib["functionbitmask"])

            self.name = node.findtext("name").strip()

        # XML Helpers

        def get_node_value(self, elem, node):
            return elem.findtext(node)

        def get_node_value_as_int(self, elem, node) -> int:
            return int(self.get_node_value(elem, node))

        def get_node_value_as_int_as_bool(self, elem, node) -> bool:
            return bool(self.get_node_value_as_int(elem, node))

        def get_temp_from_node(self, elem, node):
            return float(self.get_node_value(elem, node)) / 2

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

        identifier = None
        fw_version = None
        manufacturer = None
        productname = None
        present = None

        def __repr__(self):
            """Return a string."""
            return "{ain} {identifier} {manuf} {prod} {name}".format(
                ain=self.ain,
                identifier=self.identifier,
                manuf=self.manufacturer,
                prod=self.productname,
                name=self.name,
            )

        def update(self):
            """Update the device values."""
            self._fritz.update_devices()

        def _update_from_node(self, node):
            super()._update_from_node(node)
            self.ain = node.attrib["identifier"]
            self.identifier = node.attrib["id"]
            self.fw_version = node.attrib["fwversion"]
            self.manufacturer = node.attrib["manufacturer"]
            self.productname = node.attrib["productname"]

            self.present = bool(int(node.findtext("present")))

        # General
        def get_present(self):
            """Check if the device is present."""
            return self._fritz.get_device_present(self.ain)

    class FritzhomeDeviceAlarm(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        alert_state = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_alarm:
                self._update_alarm_from_node(node)

        # Alarm
        @property
        def has_alarm(self):
            """Check if the device has alarm function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.ALARM)

        def _update_alarm_from_node(self, node):
            val = node.find("alert")
            try:
                self.alert_state = self.get_node_value_as_int_as_bool(val, "state")
            except (Exception, ValueError):
                pass

    class FritzhomeDeviceButton(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_button:
                self._update_button_from_node(node)

        # Button
        @property
        def has_button(self):
            """Check if the device has button function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.BUTTON)

        def _update_button_from_node(self, node):
            self.buttons = {}

            for element in node.findall("button"):
                button = FritzHome.FritzhomeButton(element)
                self.buttons[button.ain] = button

            try:
                self.tx_busy = self.get_node_value_as_int_as_bool(node, "txbusy")
                self.battery_low = self.get_node_value_as_int_as_bool(node, "batterylow")
                self.battery_level = int(self.get_node_value_as_int(node, "battery"))
            except Exception:
                pass

        def get_button_by_ain(self, ain):
            return self.buttons[ain]

    class FritzhomeButton(object):
        """The Fritzhome Button Device class."""

        ain = None
        identifier = None
        name = None
        last_pressed = None

        def __init__(self, node=None):
            # init logger
            self.logger = logging.getLogger(__name__)

            if node is not None:
                self._update_from_node(node)

        def _update_from_node(self, node):
            # self.logger.debug(ElementTree.tostring(node))
            self.ain = node.attrib["identifier"]
            self.identifier = node.attrib["id"]
            self.name = node.findtext("name")
            try:
                self.last_pressed = self.get_node_value_as_int(node, "lastpressedtimestamp")
            except ValueError:
                pass

        def get_node_value(self, elem, node):
            return elem.findtext(node)

        def get_node_value_as_int(self, elem, node) -> int:
            return int(self.get_node_value(elem, node))

    class FritzhomeDeviceLightBulb(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        state = None
        level = None
        hue = None
        saturation = None
        unmapped_hue = None
        unmapped_saturation = None
        color_temp = None
        color_mode = None
        supported_color_mode = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_lightbulb:
                self._update_lightbulb_from_node(node)

        # Light Bulb
        @property
        def has_lightbulb(self):
            """Check if the device has LightBulb function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.LIGHTBULB)

        def _update_lightbulb_from_node(self, node):
            state_element = node.find("simpleonoff")
            try:
                self.state = self.get_node_value_as_int_as_bool(state_element, "state")

            except ValueError:
                pass

            level_element = node.find("levelcontrol")
            try:
                self.level = self.get_node_value_as_int(level_element, "level")

                self.level_percentage = int(self.level / 2.55)
            except ValueError:
                pass

            colorcontrol_element = node.find("colorcontrol")
            try:
                self.color_mode = colorcontrol_element.attrib.get("current_mode")

                self.supported_color_mode = colorcontrol_element.attrib.get(
                    "supported_modes")

            except ValueError:
                pass

            try:
                self.hue = self.get_node_value_as_int(colorcontrol_element, "hue")

                self.saturation = self.get_node_value_as_int(colorcontrol_element,
                                                             "saturation")

                self.unmapped_hue = self.get_node_value_as_int(colorcontrol_element, "unmapped_hue")

                self.unmapped_saturation = self.get_node_value_as_int(colorcontrol_element,
                                                                      "unmapped_saturation")
            except ValueError:
                # reset values after color mode changed
                self.hue = None
                self.saturation = None
                self.unmapped_hue = None
                self.unmapped_saturation = None

            try:
                self.color_temp = self.get_node_value_as_int(colorcontrol_element,
                                                             "temperature")

            except ValueError:
                # reset values after color mode changed
                self.color_temp = None

        def set_state_off(self):
            """Switch light bulb off."""
            self.state = True
            self._fritz.set_state_off(self.ain)

        def set_state_on(self):
            """Switch light bulb on."""
            self.state = True
            self._fritz.set_state_on(self.ain)

        def set_state_toggle(self):
            """Toogle light bulb state."""
            self.state = True
            self._fritz.set_state_toggle(self.ain)

        def set_level(self, level):
            """Set HSV color."""
            self._fritz.set_level(self.ain, level)

        def get_colors(self):
            """Get the supported colors."""
            return self._fritz.get_colors(self.ain)

        def set_color(self, hsv, duration=0):
            """Set HSV color."""
            self._fritz.set_color(self.ain, hsv, duration, True)

        def set_unmapped_color(self, hsv, duration=0):
            """Set unmapped HSV color (Free color selection)."""
            self._fritz.set_color(self.ain, hsv, duration, False)

        def get_color_temps(self):
            """Get the supported color temperatures energy."""
            return self._fritz.get_color_temps(self.ain)

        def set_color_temp(self, temperature, duration=0):
            """Set white color temperature."""
            self._fritz.set_color_temp(self.ain, temperature, duration)

    class FritzhomeDevicePowermeter(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        power = None
        energy = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_powermeter:
                self._update_powermeter_from_node(node)

        # Power Meter
        @property
        def has_powermeter(self):
            """Check if the device has powermeter function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.POWER_METER)

        def _update_powermeter_from_node(self, node):
            val = node.find("powermeter")
            self.power = int(val.findtext("power"))
            self.energy = int(val.findtext("energy"))
            try:
                self.voltage = float(int(val.findtext("voltage")) / 1000)
            except Exception:
                pass

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
            if self.present is False:
                return

        # Repeater
        @property
        def has_repeater(self):
            """Check if the device has repeater function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.DECT_REPEATER)

    class FritzhomeDeviceSwitch(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        switch_state = None
        switch_mode = None
        lock = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_switch:
                self._update_switch_from_node(node)

        # Switch
        @property
        def has_switch(self):
            """Check if the device has switch function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.SWITCH)

        def _update_switch_from_node(self, node):
            val = node.find("switch")
            self.switch_state = self.get_node_value_as_int_as_bool(val, "state")
            self.switch_mode = self.get_node_value(val, "mode")
            self.lock = bool(self.get_node_value(val, "lock"))
            # optional value
            try:
                self.device_lock = self.get_node_value_as_int_as_bool(val, "devicelock")
            except Exception:
                pass

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

        offset = None
        temperature = None
        rel_humidity = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_temperature_sensor:
                self._update_temperature_from_node(node)

        # Temperature
        @property
        def has_temperature_sensor(self):
            """Check if the device has temperature function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.TEMPERATURE)

        def _update_temperature_from_node(self, node):
            temperature_element = node.find("temperature")
            try:
                self.offset = (
                        self.get_node_value_as_int(temperature_element, "offset") / 10.0
                )
            except ValueError:
                pass

            try:
                self.temperature = (
                        self.get_node_value_as_int(temperature_element, "celsius") / 10.0
                )
            except ValueError:
                pass

            humidity_element = node.find("humidity")
            if humidity_element is not None:
                try:
                    self.rel_humidity = self.get_node_value_as_int(humidity_element,
                                                                   "rel_humidity")
                except ValueError:
                    pass

    class FritzhomeDeviceThermostat(FritzhomeDeviceBase):
        """The Fritzhome Device class."""

        actual_temperature = None
        target_temperature = None
        eco_temperature = None
        comfort_temperature = None
        device_lock = None
        lock = None
        error_code = None
        battery_low = None
        battery_level = None
        window_open = None
        summer_active = None
        holiday_active = None
        nextchange_endperiod = None
        nextchange_temperature = None

        def _update_from_node(self, node):
            super()._update_from_node(node)
            if self.present is False:
                return

            if self.has_thermostat:
                self._update_hkr_from_node(node)

        # Thermostat
        @property
        def has_thermostat(self):
            """Check if the device has thermostat function."""
            return self._has_feature(FritzHome.FritzhomeDeviceFeatures.THERMOSTAT)

        def _update_hkr_from_node(self, node):
            hkr_element = node.find("hkr")

            try:
                self.actual_temperature = self.get_temp_from_node(hkr_element, "tist")
            except ValueError:
                pass

            self.target_temperature = self.get_temp_from_node(hkr_element, "tsoll")
            self.eco_temperature = self.get_temp_from_node(hkr_element, "absenk")
            self.comfort_temperature = self.get_temp_from_node(hkr_element, "komfort")

            # optional value
            try:
                self.device_lock = self.get_node_value_as_int_as_bool(
                    hkr_element, "devicelock"
                )
                self.lock = self.get_node_value_as_int_as_bool(hkr_element, "lock")
                self.error_code = self.get_node_value_as_int(hkr_element, "errorcode")
                self.battery_low = self.get_node_value_as_int_as_bool(
                    hkr_element, "batterylow"
                )
                self.battery_level = int(self.get_node_value_as_int(hkr_element, "battery"))
                self.window_open = self.get_node_value_as_int_as_bool(
                    hkr_element, "windowopenactiv"
                )
                self.summer_active = self.get_node_value_as_int_as_bool(
                    hkr_element, "summeractive"
                )
                self.holiday_active = self.get_node_value_as_int_as_bool(
                    hkr_element, "holidayactive"
                )
                nextchange_element = hkr_element.find("nextchange")
                self.nextchange_endperiod = int(
                    self.get_node_value_as_int(nextchange_element, "endperiod")
                )
                self.nextchange_temperature = self.get_temp_from_node(
                    nextchange_element, "tchange"
                )
            except Exception:
                pass

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

        def get_comfort_temperature(self):
            """Get the thermostate comfort temperature."""
            return self._fritz.get_comfort_temperature(self.ain)

        def get_eco_temperature(self):
            """Get the thermostate eco temperature."""
            return self._fritz.get_eco_temperature(self.ain)

        def get_hkr_state(self):
            """Get the thermostate state."""
            try:
                return {
                    126.5: "off",
                    127.0: "on",
                    self.eco_temperature: "eco",
                    self.comfort_temperature: "comfort",
                }[self.target_temperature]
            except KeyError:
                return "manual"

        def set_hkr_state(self, state):
            """Set the state of the thermostat.
            Possible values for state are: 'on', 'off', 'comfort', 'eco'.
            """
            try:
                value = {
                    "off": 0,
                    "on": 100,
                    "eco": self.eco_temperature,
                    "comfort": self.comfort_temperature,
                }[state]
            except KeyError:
                return

            self.set_target_temperature(value)

    class FritzhomeDevice(
        FritzhomeDeviceAlarm,
        FritzhomeDeviceButton,
        FritzhomeDevicePowermeter,
        FritzhomeDeviceRepeater,
        FritzhomeDeviceSwitch,
        FritzhomeDeviceTemperature,
        FritzhomeDeviceThermostat,
        FritzhomeDeviceLightBulb,
    ):
        """The Fritzhome Device class."""

        def __init__(self, fritz=None, node=None):
            super().__init__(fritz, node)

        def _update_from_node(self, node):
            super()._update_from_node(node)


class Callmonitor:
    def __init__(self, host, port, callback, call_monitor_incoming_filter, plugin_instance):

        self._plugin_instance = plugin_instance
        self._plugin_instance.logger.debug("Init Callmonitor")

        self._host = host
        self._port = port

        self._call_monitor_incoming_filter = call_monitor_incoming_filter
        self._callback = callback
        self._items = dict()                # more general items for the call monitor
        self._trigger_items = dict()        # items which can be used to trigger sth, e.g. a logic
        self._items_incoming = dict()       # items for incoming calls
        self._items_outgoing = dict()       # items for outgoing calls
        self._duration_item_in = dict()        # 2 items, one for counting the incoming, one for counting the outgoing call duration
        self._duration_item_out = dict()
        self._call_active = dict()
        self._listen_active = False
        self._call_active['incoming'] = False
        self._call_active['outgoing'] = False
        self._call_incoming_cid = dict()
        self._call_outgoing_cid = dict()
        self._call_monitor_incoming_filter = call_monitor_incoming_filter
        self.conn = None
        self._listen_thread = None

        self.connect()

    def connect(self):
        """
        Connects to the call monitor of the AVM device
        """

        if self._listen_active:
            if self._plugin_instance.debug_log:
                self._plugin_instance.logger.debug("MonitoringService: Connect called while listen active")
            return

        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.conn.connect((self._host, self._port))
            _name = f'plugins.{self._plugin_instance.get_fullname()}.Monitoring_Service'
            self._listen_thread = threading.Thread(target=self._listen, name=_name).start()
            if self._plugin_instance.debug_log:
                self._plugin_instance.logger.debug("MonitoringService: connection established")
        except Exception as e:
            self.conn = None
            self._plugin_instance.logger.error(
                f"MonitoringService: Cannot connect to {self._host} on port: {self._port}, CallMonitor activated by #96*5*? - Error: {e}")
            return

    def disconnect(self):
        """
        Disconnects from the call monitor of the AVM device
        """
        if self._plugin_instance.debug_log:
            self._plugin_instance.logger.debug("MonitoringService: disconnecting")
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

    def register_item(self, item, avm_data_type: str):
        """
        Registers an item to the CallMonitoringService

        :param item: item to register
        :param avm_data_type: avm_data_type of item to be registered
        """

        # handle _call_monitor_attributes_in
        if avm_data_type in _call_monitor_attributes_in:
            self._items_incoming[item] = (avm_data_type, None)
        elif avm_data_type in _call_monitor_attributes_out:
            self._items_outgoing[item] = (avm_data_type, None)
        elif avm_data_type in _trigger_attributes:
            avm_incoming_allowed = self._plugin_instance.get_iattr_value(item.conf, 'avm2_incoming_allowed')
            avm_target_number = self._plugin_instance.get_iattr_value(item.conf, 'avm2_target_number')
            if not avm_incoming_allowed or not avm_target_number:
                self._plugin_instance.logger.error(f"For Trigger-item={item.id()} both 'avm2_incoming_allowed' and 'avm2_target_number' must be specified as attributes. Item will be ignored.")
            else:
                self._trigger_items[item] = (avm_data_type, avm_incoming_allowed, avm_target_number)
        elif avm_data_type in _call_duration_attributes:
            if 'in' in avm_data_type:
                self._duration_item_in[item] = (avm_data_type, None)
            else:
                self._duration_item_out[item] = (avm_data_type, None)
        else:
            self._items[item] = (avm_data_type, None)

    def get_items(self):
        return list(self._items.keys())

    def get_trigger_items(self):
        return list(self._trigger_items.keys())

    def get_items_incoming(self):
        return list(self._items_incoming.keys())

    def get_items_outgoing(self):
        return list(self._items_outgoing.keys())

    @property
    def get_item_count_total(self):
        """
        Returns number of added items (all items of MonitoringService service

        :return: number of items hold by the MonitoringService
        """

        return len(self._items) + len(self._trigger_items) + len(self._items_incoming) + len(self._items_outgoing) + len(self._duration_item_in) + len(self._duration_item_out)

    def _listen(self, recv_buffer: int = 4096):
        """
        Function which listens to the established connection.
        """

        self._listen_active = True
        buffer = ""
        while self._listen_active:
            data = self.conn.recv(recv_buffer)
            if data == "":
                self._plugin_instance.logger.error("CallMonitor connection not open anymore.")
            else:
                if self._plugin_instance.debug_log:
                    self._plugin_instance.logger.debug(f"Data Received from CallMonitor: {data.decode('utf-8')}")
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
            self._plugin_instance.logger.debug('Counter incoming - STARTED')
        elif direction == 'outgoing':
            self._call_connect_timestamp = time.mktime(datetime.datetime.strptime(timestamp, "%d.%m.%y %H:%M:%S").timetuple())
            self._duration_counter_thread_outgoing = threading.Thread(target=self._count_duration_outgoing,
                                                                      name=f"MonitoringService_Duration_Outgoing_{self._plugin_instance.get_instance_name()}").start()
            self._plugin_instance.logger.debug('Counter outgoing - STARTED')

    def _stop_counter(self, direction: str):
        """
        Stop counter to measure duration of a call, but only stop of thread is active
        """

        if self._call_active[direction]:
            self._call_active[direction] = False
            if self._plugin_instance.debug_log:
                self._plugin_instance.logger.debug(f'STOPPING {direction}')
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
            if self._duration_item_in is not None:
                duration = time.time() - self._call_connect_timestamp
                duration_item = list(self._duration_item_in.keys())[0]
                duration_item(int(duration), self._plugin_instance.get_shortname())
            time.sleep(1)

    def _count_duration_outgoing(self):
        """
        Count duration of outgoing call and set item value
        """

        self._call_active['outgoing'] = True
        while self._call_active['outgoing']:
            if self._duration_item_out is not None:
                duration = time.time() - self._call_connect_timestamp
                duration_item = list(self._duration_item_out.keys())[0]
                duration_item(int(duration), self._plugin_instance.get_shortname())
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

        if self._plugin_instance.debug_log:
            self._plugin_instance.logger.debug(line)
        line = line.split(";")

        try:
            if line[1] == "RING":
                self._trigger(line[3], line[4], line[0], line[2], line[1], '')
            elif line[1] == "CALL":
                self._trigger(line[4], line[5], line[0], line[2], line[1], line[3])
            elif line[1] == "CONNECT":
                self._trigger('', '', line[0], line[2], line[1], line[3])
            elif line[1] == "DISCONNECT":
                self._trigger('', '', '', line[2], line[1], '')
        except Exception as e:
            self._plugin_instance.logger.error(f"MonitoringService: {type(e).__name__} while handling Callmonitor response: {e}")

    def _trigger(self, call_from: str, call_to: str, time: str, callid: str, event: str, branch: str):
        """
        Triggers the event: sets item values and looks up numbers in the phone book.
        """

        if self._plugin_instance.debug_log:
            self._plugin_instance.logger.debug(f"Event: {event}, Call From: {call_from}, Call To: {call_to}, Time: {time}, CallID: {callid}, Branch: {branch}")

        # set generic item value
        for item in self._items:
            avm_data_type = self._items[item][0]
            if avm_data_type == 'call_event':
                item(event.lower(), self._plugin_instance.get_shortname())
            if avm_data_type == 'call_direction':
                if event == 'RING':
                    item("incoming", self._plugin_instance.get_shortname())
                else:
                    item("outgoing", self._plugin_instance.get_shortname())

        # handle incoming call
        if event == 'RING':
            # process "trigger items"
            for trigger_item in self._trigger_items:
                avm_data_type = self._trigger_items[trigger_item][0]
                avm_incoming_allowed = self._trigger_items[trigger_item][1]
                avm_target_number = self._trigger_items[trigger_item][2]
                trigger_item(0, self._plugin_instance.get_shortname())
                if self._plugin_instance.debug_log:
                    self._plugin_instance.logger.debug(f"{avm_data_type} {call_from} {call_to}")
                if avm_incoming_allowed == call_from and avm_target_number == call_to:
                    trigger_item(1, self._plugin_instance.get_shortname())

            if self._call_monitor_incoming_filter in call_to:
                # set call id for incoming call
                self._call_incoming_cid = callid

                # reset duration for incoming calls
                if self._duration_item_in is not None:
                    duration_item = list(self._duration_item_in.keys())[0]
                    duration_item(0, self._plugin_instance.get_shortname())

                # process items specific to incoming calls
                for item in self._items_incoming:  # update items for incoming calls
                    avm_data_type = self._items[item][0]
                    if avm_data_type == 'is_call_incoming':
                        if self._plugin_instance.debug_log:
                            self._plugin_instance.logger.debug(f"Setting is_call_incoming: True")
                        item(True, self._plugin_instance.get_shortname())
                    elif avm_data_type == 'last_caller_incoming':
                        if call_from != '' and call_from is not None:
                            name = self._callback(call_from)
                            if name != '' and name is not None:
                                item(name, self._plugin_instance.get_shortname())
                            else:
                                item(call_from, self._plugin_instance.get_shortname())
                        else:
                            item("Unbekannt", self._plugin_instance.get_shortname())
                    elif avm_data_type == 'last_call_date_incoming':
                        if self._plugin_instance.debug_log:
                            self._plugin_instance.logger.debug(f"Setting last_call_date_incoming: {time}")
                        item(time, self._plugin_instance.get_shortname())
                    elif avm_data_type == 'call_event_incoming':
                        if self._plugin_instance.debug_log:
                            self._plugin_instance.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_shortname())
                    elif avm_data_type == 'last_number_incoming':
                        if self._plugin_instance.debug_log:
                            self._plugin_instance.logger.debug(f"Setting last_number_incoming: {call_from}")
                        item(call_from, self._plugin_instance.get_shortname())
                    elif avm_data_type == 'last_called_number_incoming':
                        if self._plugin_instance.debug_log:
                            self._plugin_instance.logger.debug(f"Setting last_called_number_incoming: {call_to}")
                        item(call_to, self._plugin_instance.get_shortname())

        # handle outgoing call
        elif event == 'CALL':
            # set call id for outgoing call
            self._call_outgoing_cid = callid

            # reset duration for outgoing calls
            if self._duration_item_out is not None:
                duration_item = list(self._duration_item_out.keys())[0]
                duration_item(0, self._plugin_instance.get_shortname())

            # process items specific to outgoing calls
            for item in self._items_outgoing:
                avm_data_type = self._items[item][0]
                if avm_data_type == 'is_call_outgoing':
                    item(True, self._plugin_instance.get_shortname())
                elif avm_data_type == 'last_caller_outgoing':
                    name = self._callback(call_to)
                    if name != '' and name is not None:
                        item(name, self._plugin_instance.get_shortname())
                    else:
                        item(call_to, self._plugin_instance.get_shortname())
                elif avm_data_type == 'last_call_date_outgoing':
                    item(time, self._plugin_instance.get_shortname())
                elif avm_data_type == 'call_event_outgoing':
                    item(event.lower(), self._plugin_instance.get_shortname())
                elif avm_data_type == 'last_number_outgoing':
                    item(call_from, self._plugin_instance.get_shortname())
                elif avm_data_type == 'last_called_number_outgoing':
                    item(call_to, self._plugin_instance.get_shortname())

        # handle established connection
        elif event == 'CONNECT':
            # handle OUTGOING calls
            if callid == self._call_outgoing_cid:
                if self._duration_item_out is not None:  # start counter thread only if duration item set and call is outgoing
                    self._stop_counter('outgoing')  # stop potential running counter for parallel (older) outgoing call
                    self._start_counter(time, 'outgoing')
                for item in self._items_outgoing:
                    avm_data_type = self._items[item][0]
                    if avm_data_type == 'call_event_outgoing':
                        item(event.lower(), self._plugin_instance.get_shortname())

            # handle INCOMING calls
            elif callid == self._call_incoming_cid:
                if self._duration_item_in is not None:  # start counter thread only if duration item set and call is incoming
                    self._stop_counter('incoming')  # stop potential running counter for parallel (older) incoming call
                    if self._plugin_instance.debug_log:
                        self._plugin_instance.logger.debug("Starting Counter for Call Time")
                    self._start_counter(time, 'incoming')
                for item in self._items_incoming:
                    avm_data_type = self._items[item][0]
                    if avm_data_type == 'call_event_incoming':
                        if self._plugin_instance.debug_log:
                            self._plugin_instance.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_shortname())

        # handle ended connection
        elif event == 'DISCONNECT':
            # handle OUTGOING calls
            if callid == self._call_outgoing_cid:
                for item in self._items_outgoing:
                    avm_data_type = self._items[item][0]
                    if avm_data_type == 'call_event_outgoing':
                        item(event.lower(), self._plugin_instance.get_shortname())
                    elif avm_data_type == 'is_call_outgoing':
                        item(False, self._plugin_instance.get_shortname())
                if self._duration_item_out is not None:  # stop counter threads
                    self._stop_counter('outgoing')
                self._call_outgoing_cid = None

            # handle INCOMING calls
            elif callid == self._call_incoming_cid:
                for item in self._items_incoming:
                    avm_data_type = self._items[item][0]
                    if avm_data_type == 'call_event_incoming':
                        if self._plugin_instance.debug_log:
                            self._plugin_instance.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_shortname())
                    elif avm_data_type == 'is_call_incoming':
                        if self._plugin_instance.debug_log:
                            self._plugin_instance.logger.debug(f"Setting is_call_incoming: {False}")
                        item(False, self._plugin_instance.get_shortname())
                if self._duration_item_in is not None:  # stop counter threads
                    if self._plugin_instance.debug_log:
                        self._plugin_instance.logger.debug("Stopping Counter for Call Time")
                    self._stop_counter('incoming')
                self._call_incoming_cid = None
