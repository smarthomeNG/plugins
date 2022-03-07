#!/usr/bin/env python3
#
#########################################################################
#  Copyright 2016 René Frieß                      rene.friess(a)gmail.com
#            2021 Michael Wenzel                  wenzel_michael(a)web.de
#########################################################################
#
#  This file is part of SmartHomeNG.
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

import hashlib  # for session id generation
import logging
import socket
import threading
import time
import requests

from datetime import datetime
from json.decoder import JSONDecodeError
from time import mktime
from xml.dom import minidom
from requests.auth import HTTPDigestAuth
from requests.packages import urllib3

from lib.model.smartplugin import SmartPlugin
from lib.item import Items
from .webif import WebInterface

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

_aha_attributes = _aha_ro_attributes + _aha_wo_attributes + _aha_rw_attributes

_avm_rw_attributes = ['wlanconfig',
                      'tam',
                      'aha_device',
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

_call_monitor_attributes = _call_monitor_attributes_gen + _call_monitor_attributes_in + _call_monitor_attributes_out

_call_duration_attributes = ['call_duration_incoming',
                             'call_duration_outgoing']

_wan_ip_connection_attributes = ['wan_connection_status',
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

_host_attributes = _host_attribute + _host_child_attributes

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

_aha_attributes_old = ['aha_device',
                       'hkr_device']

_myfritz_attributes = ['myfritz_status']

_deprecated_attributes = ['temperature',
                          'set_temperature_reduced',
                          'set_temperature_comfort',
                          'firmware_version',
                          'aha_device',
                          'hkr_device']


class MonitoringService:
    """
    Class which connects to the FritzBox service of the Callmonitor: http://www.wehavemorefun.de/fritzbox/Callmonitor

    | Can currently handle three items:
    | - avm_data_type = is_call_incoming, type = bool
    | - avm_data_type = last_caller, type = str
    | - avm_data_type = last_call_date, type = str
    """

    def __init__(self, host, port, callback, call_monitor_incoming_filter, plugin_instance):
        self._plugin_instance = plugin_instance
        self._plugin_instance.logger.debug("starting monitoring service")
        self._host = host
        self._port = port
        self._callback = callback
        self._trigger_items = []  # items which can be used to trigger sth, e.g. a logic
        self._items = []  # more general items for the call monitor
        self._items_incoming = []  # items for incoming calls
        self._items_outgoing = []  # items for outgoing calls
        self._duration_item = dict()  # 2 items, one for counting the incoming, one for counting the outgoing call duration
        self._duration_item['call_duration_outgoing'] = None
        self._duration_item['call_duration_incoming'] = None
        self._call_active = dict()
        self._listen_active = False
        self._call_active['incoming'] = False
        self._call_active['outgoing'] = False
        self._call_incoming_cid = dict()
        self._call_outgoing_cid = dict()
        self._call_monitor_incoming_filter = call_monitor_incoming_filter
        self.conn = None
        self._listen_thread = None

        if self._plugin_instance.logger.isEnabledFor(logging.DEBUG):
            self.debug_log = True
        else:
            self.debug_log = False

    def connect(self):
        """
        Connects to the call monitor of the AVM device
        """
        if self._listen_active:
            self._plugin_instance.logger.debug("MonitoringService: Connect called while listen active")
            return

        self.conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.conn.connect((self._host, self._port))
            _name = f'plugins.{self._plugin_instance.get_fullname()}.Monitoring_Service'
            self._listen_thread = threading.Thread(target=self._listen, name=_name).start()
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

    def register_item(self, item):
        """
        Registers an item to the MonitoringService

        :param item: item to register
        """
        if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in _call_monitor_attributes_in:
            self._items_incoming.append(item)
        elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in _call_monitor_attributes_out:
            self._items_outgoing.append(item)
        elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') == 'monitor_trigger':
            self._trigger_items.append(item)
        else:
            self._items.append(item)

    def get_items(self):
        return self._items

    def get_trigger_items(self):
        return self._trigger_items

    def get_items_incoming(self):
        return self._items_incoming

    def get_items_outgoing(self):
        return self._items_outgoing

    def get_item_count_total(self):
        """
        Returns number of added items (all items of MonitoringService service

        :return: number of items hold by the MonitoringService
        """
        return len(self._items) + len(self._trigger_items) + len(self._items_incoming) + len(self._items_outgoing)

    def set_duration_item(self, item):
        """
        Sets specific items which count the duration of an incoming or outgoing call
        """
        self._duration_item[self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type').split("@")[0]] = item

    def _listen(self, recv_buffer=4096):
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
                if self.debug_log:
                    self._plugin_instance.logger.debug(f"Data Received from CallMonitor: {data.decode('utf-8')}")
            buffer += data.decode("utf-8")
            while buffer.find("\n") != -1:
                line, buffer = buffer.split("\n", 1)
                if line:
                    self._parse_line(line)

            # time.sleep(1)
        return

    def _start_counter(self, timestamp, direction):
        """
        Start counter to measure duration of a call
        """
        if direction == 'incoming':
            self._call_connect_timestamp = time.mktime(
                datetime.strptime(timestamp, "%d.%m.%y %H:%M:%S").timetuple())
            self._duration_counter_thread_incoming = threading.Thread(target=self._count_duration_incoming,
                                                                      name=f"MonitoringService_Duration_Incoming_{self._plugin_instance.get_instance_name()}").start()
            self._plugin_instance.logger.debug('Counter incoming - STARTED')
        elif direction == 'outgoing':
            self._call_connect_timestamp = time.mktime(
                datetime.strptime(timestamp, "%d.%m.%y %H:%M:%S").timetuple())
            self._duration_counter_thread_outgoing = threading.Thread(target=self._count_duration_outgoing,
                                                                      name=f"MonitoringService_Duration_Outgoing_{self._plugin_instance.get_instance_name()}").start()
            self._plugin_instance.logger.debug('Counter outgoing - STARTED')

    def _stop_counter(self, direction):
        """
        Stop counter to measure duration of a call, but only stop of thread is active
        """

        if self._call_active[direction]:
            self._call_active[direction] = False
            if self.debug_log:
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
            if not self._duration_item['call_duration_incoming'] is None:
                duration = time.time() - self._call_connect_timestamp
                self._duration_item['call_duration_incoming'](int(duration), self._plugin_instance.get_shortname())
            time.sleep(1)

    def _count_duration_outgoing(self):
        """
        Count duration of outgoing call and set item value
        """
        self._call_active['outgoing'] = True
        while self._call_active['outgoing']:
            if not self._duration_item['call_duration_outgoing'] is None:
                duration = time.time() - self._call_connect_timestamp
                self._duration_item['call_duration_outgoing'](int(duration), self._plugin_instance.get_shortname())
            time.sleep(1)

    def _parse_line(self, line):
        """
        Parses a data set in the form of a line.

        Data Format:
        Ausgehende Anrufe: datum;CALL;ConnectionID;Nebenstelle;GenutzteNummer;AngerufeneNummer;SIP+Nummer
        Eingehende Anrufe: datum;RING;ConnectionID;Anrufer-Nr;Angerufene-Nummer;SIP+Nummer
        Zustandegekommene Verbindung: datum;CONNECT;ConnectionID;Nebenstelle;Nummer;
        Ende der Verbindung: datum;DISCONNECT;ConnectionID;dauerInSekunden;

        :param line: data line which is parsed
        """
        if self.debug_log:
            self._plugin_instance.logger.debug(line)
        line = line.split(";")

        try:
            if line[1] == "RING":
                call_from = line[3]
                call_to = line[4]
                self._trigger(call_from, call_to, line[0], line[2], line[1], '')
            elif line[1] == "CALL":
                call_from = line[4]
                call_to = line[5]
                self._trigger(call_from, call_to, line[0], line[2], line[1], line[3])
            elif line[1] == "CONNECT":
                self._trigger('', '', line[0], line[2], line[1], line[3])
            elif line[1] == "DISCONNECT":
                self._trigger('', '', '', line[2], line[1], '')
        except Exception as e:
            self._plugin_instance.logger.error(
                f"MonitoringService: {type(e).__name__} while handling Callmonitor response: {e}")
            return

    def _trigger(self, call_from, call_to, time, callid, event, branch):
        """
        Triggers the event: sets item values and looks up numbers in the phone book.
        """

        if self.debug_log:
            self._plugin_instance.logger.debug(
                f"Event: {event}, Call From: {call_from}, Call To: {call_to}, Time: {time}, CallID:{callid}")
        # in each case set current call event and direction
        for item in self._items:
            if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') == 'call_event':
                item(event.lower(), self._plugin_instance.get_shortname())
            if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') == 'call_direction':
                if event == 'RING':
                    item("incoming", self._plugin_instance.get_shortname())
                else:
                    item("outgoing", self._plugin_instance.get_shortname())

        # call is incoming
        if event == 'RING':
            # process "trigger items"
            for trigger_item in self._trigger_items:
                if self._plugin_instance.get_iattr_value(trigger_item.conf, 'avm_data_type') == 'monitor_trigger':
                    trigger_item(0, self._plugin_instance.get_shortname())
                    if self.debug_log:
                        self._plugin_instance.logger.debug(
                            f"{self._plugin_instance.get_iattr_value(trigger_item.conf, 'avm_data_type')} {trigger_item.conf['avm_incoming_allowed']} {trigger_item.conf['avm_target_number']}")
                    if 'avm_incoming_allowed' not in trigger_item.conf or 'avm_target_number' not in trigger_item.conf:
                        self._plugin_instance.logger.error(
                            "both 'avm_incoming_allowed' and 'avm_target_number' must be specified as attributes in a trigger item.")
                    elif trigger_item.conf['avm_incoming_allowed'] == call_from and trigger_item.conf['avm_target_number'] == call_to:
                        trigger_item(1, self._plugin_instance.get_shortname())

            if self._call_monitor_incoming_filter in call_to:
                # set call id for incoming call
                self._call_incoming_cid = callid

                # reset duration for incoming calls
                if not self._duration_item['call_duration_incoming'] is None:
                    self._duration_item['call_duration_incoming'](0, self._plugin_instance.get_shortname())

                # process items specific to incoming calls
                for item in self._items_incoming:  # update items for incoming calls
                    if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['is_call_incoming']:
                        if self.debug_log:
                            self._plugin_instance.logger.debug(f"Setting is_call_incoming: {True}")
                        item(True, self._plugin_instance.get_shortname())
                    elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['last_caller_incoming']:
                        if call_from != '' and call_from is not None:
                            name = self._callback(call_from)
                            if name != '' and name is not None:
                                item(name, self._plugin_instance.get_shortname())
                            else:
                                item(call_from, self._plugin_instance.get_shortname())
                        else:
                            item("Unbekannt", self._plugin_instance.get_shortname())
                    elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['last_call_date_incoming']:
                        if self.debug_log:
                            self._plugin_instance.logger.debug(f"Setting last_call_date_incoming: {time}")
                        item(time, self._plugin_instance.get_shortname())
                    elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['call_event_incoming']:
                        if self.debug_log:
                            self._plugin_instance.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_shortname())
                    elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['last_number_incoming']:
                        if self.debug_log:
                            self._plugin_instance.logger.debug(f"Setting last_number_incoming: {call_from}")
                        item(call_from, self._plugin_instance.get_shortname())
                    elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['last_called_number_incoming']:
                        if self.debug_log:
                            self._plugin_instance.logger.debug(f"Setting last_called_number_incoming: {call_to}")
                        item(call_to, self._plugin_instance.get_shortname())

        # call is outgoing
        elif event == 'CALL':
            # set call id for outgoing call
            self._call_outgoing_cid = callid

            # reset duration for outgoing calls
            self._duration_item['call_duration_outgoing'](0)

            # process items specific to outgoing calls
            for item in self._items_outgoing:
                if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['is_call_outgoing']:
                    item(True, self._plugin_instance.get_shortname())
                elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['last_caller_outgoing']:
                    name = self._callback(call_to)
                    if name != '' and name is not None:
                        item(name, self._plugin_instance.get_shortname())
                    else:
                        item(call_to, self._plugin_instance.get_shortname())
                elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['last_call_date_outgoing']:
                    item(time, self._plugin_instance.get_shortname())
                elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['call_event_outgoing']:
                    item(event.lower(), self._plugin_instance.get_shortname())
                elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['last_number_outgoing']:
                    item(call_from, self._plugin_instance.get_shortname())
                elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['last_called_number_outgoing']:
                    item(call_to, self._plugin_instance.get_shortname())

        # connection established
        elif event == 'CONNECT':
            # handle OUTGOING calls
            if callid == self._call_outgoing_cid:
                if not self._duration_item[
                           'call_duration_outgoing'] is None:  # start counter thread only if duration item set and call is outgoing
                    self._stop_counter('outgoing')  # stop potential running counter for parallel (older) outgoing call
                    self._start_counter(time, 'outgoing')
                for item in self._items_outgoing:
                    if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['call_event_outgoing']:
                        item(event.lower(), self._plugin_instance.get_shortname())

            # handle INCOMING calls
            elif callid == self._call_incoming_cid:
                if not self._duration_item[
                           'call_duration_incoming'] is None:  # start counter thread only if duration item set and call is incoming
                    self._stop_counter('incoming')  # stop potential running counter for parallel (older) incoming call
                    if self.debug_log:
                        self._plugin_instance.logger.debug("Starting Counter for Call Time")
                    self._start_counter(time, 'incoming')
                for item in self._items_incoming:
                    if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') in ['call_event_incoming']:
                        if self.debug_log:
                            self._plugin_instance.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_shortname())

        # connection ended
        elif event == 'DISCONNECT':
            # handle OUTGOING calls
            if callid == self._call_outgoing_cid:
                for item in self._items_outgoing:
                    if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') == 'call_event_outgoing':
                        item(event.lower(), self._plugin_instance.get_shortname())
                    elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') == 'is_call_outgoing':
                        item(False, self._plugin_instance.get_shortname())
                if not self._duration_item['call_duration_outgoing'] is None:  # stop counter threads
                    self._stop_counter('outgoing')
                self._call_outgoing_cid = None

            # handle INCOMING calls
            elif callid == self._call_incoming_cid:
                for item in self._items_incoming:
                    if self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') == 'call_event_incoming':
                        if self.debug_log:
                            self._plugin_instance.logger.debug(f"Setting call_event_incoming: {event.lower()}")
                        item(event.lower(), self._plugin_instance.get_shortname())
                    elif self._plugin_instance.get_iattr_value(item.conf, 'avm_data_type') == 'is_call_incoming':
                        if self.debug_log:
                            self._plugin_instance.logger.debug(f"Setting is_call_incoming: {False}")
                        item(False, self._plugin_instance.get_shortname())
                if not self._duration_item['call_duration_incoming'] is None:  # stop counter threads
                    if self.debug_log:
                        self._plugin_instance.logger.debug("Stopping Counter for Call Time")
                    self._stop_counter('incoming')
                self._call_incoming_cid = None


class FritzDevice:
    """
    This class encapsulates information related to a specific FritzDevice, such has host, port, ssl, username, password, or related items
    """

    def __init__(self, host, port, ssl, username, password, identifier='default'):
        self.logger = logging.getLogger(__name__)
        self._host = host
        self._port = port
        self._ssl = ssl
        self._username = username
        self._password = password
        self._identifier = identifier
        self._available = True
        self._items = []
        self._smarthome_items = []
        self._smarthome_devices = {}

    def get_identifier(self):
        """
        Returns the internal identifier of the FritzDevice

        :return: identifier of the device, as set in plugin.conf
        """
        return self._identifier

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

    def get_items(self):
        """
        Returns added items

        :return: array of items hold by the device
        """
        return self._items

    def get_item_count(self):
        """
        Returns number of added items

        :return: number of items hold by the device
        """
        return len(self._items)

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

    def get_smarthome_items(self):
        """
        Returns added items

        :return: array of smarthome items hold by the plugin
        """
        return self._smarthome_items

    def get_smarthome_devices(self):
        """
        Returns added items

        :return: dict of smarthome devices hold by the plugin
        """
        return self._smarthome_devices


class AVM(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the different TR-064 services on the FritzDevice
    """

    PLUGIN_VERSION = "1.6.5"

    _header = {'SOAPACTION': '', 'CONTENT-TYPE': 'text/xml; charset="utf-8"'}

    _envelope = """
        <?xml version="1.0" encoding="utf-8"?>
        <s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/"
            xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">%s
        </s:Envelope>
        """
    _body = """
        <s:Body>
        <u:%(action)s xmlns:u="%(service)s">%(arguments)s
        </u:%(action)s>
        </s:Body>
        """
    _argument = """
        <s:%(name)s>%(value)s</s:%(name)s>"""

    _urn_map = dict([('WLANConfiguration', 'urn:dslforum-org:service:WLANConfiguration:%s'),
                     # index needs to be adjusted from 1 to 3
                     ('WANCommonInterfaceConfig', 'urn:dslforum-org:service:WANCommonInterfaceConfig:1'),
                     ('WANCommonInterfaceConfig_alt', 'urn:schemas-upnp-org:service:WANCommonInterfaceConfig:1'),
                     ('WANIPConnection', 'urn:schemas-upnp-org:service:WANIPConnection:1'),
                     ('TAM', 'urn:dslforum-org:service:X_AVM-DE_TAM:1'),
                     ('OnTel', 'urn:dslforum-org:service:X_AVM-DE_OnTel:1'),
                     ('Homeauto', 'urn:dslforum-org:service:X_AVM-DE_Homeauto:1'),
                     ('Hosts', 'urn:dslforum-org:service:Hosts:1'),
                     ('X_VoIP', 'urn:dslforum-org:service:X_VoIP:1'),
                     ('DeviceConfig', 'urn:dslforum-org:service:DeviceConfig:1'),
                     ('DeviceInfo', 'urn:dslforum-org:service:DeviceInfo:1'),
                     ('WANDSLInterfaceConfig', 'urn:dslforum-org:service:WANDSLInterfaceConfig:1'),
                     ('MyFritz', 'urn:dslforum-org:service:X_AVM-DE_MyFritz:1')])

    _login_sid_route = "/login_sid.lua?version=2"

    def __init__(self, sh):
        """
        Initializes the plugin. The parameters describe for this method are pulled from the entry in plugin.conf.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        self.logger.info('Init AVM Plugin')

        self._session = requests.Session()
        self._lua_session = requests.Session()
        self._timeout = 10
        self._verify = self.get_parameter_value('verify')
        self._response_cache = dict()  # Response Cache: Dictionary for storing the result of requests which is used for several different items, refreshed each update cycle. Please use distinct keys!
        self._calllist_cache = []  #
        self._host_info = dict()  # Dict to hold basic info of that host, gathered at startup

        ssl = self.get_parameter_value('ssl')
        if ssl and not self._verify:
            urllib3.disable_warnings()

        self._fritz_device = FritzDevice(self.get_parameter_value('host'), self.get_parameter_value('port'), ssl,
                                         self.get_parameter_value('username'), self.get_parameter_value('password'),
                                         self.get_instance_name())

        self._call_monitor = self.to_bool(self.get_parameter_value('call_monitor'))
        if self._call_monitor:
            self._monitoring_service = MonitoringService(self._fritz_device.get_host(), 1012,
                                                         self.get_contact_name_by_phone_number,
                                                         self.get_parameter_value('call_monitor_incoming_filter'), self)
            self._monitoring_service.connect()
        else:
            self._monitoring_service = None

        self._call_monitor_incoming_filter = self.get_parameter_value('call_monitor_incoming_filter')

        self.aha_http_interface = self.get_parameter_value('avm_home_automation')
        self._cycle = int(self.get_parameter_value('cycle'))
        self.webif_pagelength = self.get_parameter_value('webif_pagelength')

        # Enable / Disable debug log generation depending on log level
        if self.logger.isEnabledFor(logging.DEBUG):
            self.debug_log = True
        else:
            self.debug_log = False

        if self.debug_log:
            self.logger.debug(
                f"Plugin initialized with host: {self._fritz_device.get_host()}, port: {self._fritz_device.get_port()}, ssl: {self._fritz_device.is_ssl()}, verify: {self._verify}, user: {self._fritz_device.get_user()}, call_monitor: {self._call_monitor}")

        self.alive = False
        self.sid = None

        self.init_webinterface(WebInterface)
        # if not self.init_webinterface():
        #     self._init_complete = False

    def run(self):
        """
        Run method for the plugin
        """

        # add scheduler für update_loop
        self.scheduler_add('update', self._update_loop, prio=5, cycle=self._cycle, offset=2)

        # get infos about host to be able to start methods depending on that (e.g. if Device is Fritzbox, check für AHA-Interface)
        self._get_host_device_info()

        # add scheduler for checking validity of session id
        if self.aha_http_interface:
            self.scheduler_add('check_sid', self._check_sid, prio=5, cycle=900, offset=30)

        # set plugin alive to True
        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """

        if self._call_monitor:
            self._monitoring_service.disconnect()

        self.scheduler_remove('update')

        if self.aha_http_interface:
            self.scheduler_remove('check_sid')

        if self.sid:
            self._http_logout_request()

        self.alive = False

    def _assemble_soap_data(self, action, service, argument=''):
        """
        Builds the soap data set (from body and envelope templates for a given request.

        :param action: string of the action
        :type action: str
        :param service: string of the service
        :type service: str
        :param argument: dictionary (name: value) of arguments
        :type argument: dict
        :return: string of the soap data
        :type return: str
        """

        argument_string = ''
        if argument:
            arguments = [
                self._argument % {'name': name, 'value': value}
                for name, value in argument.items()
            ]
            argument_string = argument_string.join(arguments)
        body = self._body.strip() % {'action': action, 'service': service, 'arguments': argument_string}
        soap_data = self._envelope.strip() % body
        return soap_data

    def _build_url(self, suffix, lua=False):
        """
        Builds a request url

        :param suffix: url suffix, e.g. "/upnp/control/x_tam"
        :return: string of the url, dependent on settings of the FritzDevice
        """

        if self._fritz_device.is_ssl():
            url_prefix = "https"
        else:
            url_prefix = "http"
        if not lua:
            url = f"{url_prefix}://{self._fritz_device.get_host()}:{self._fritz_device.get_port()}{suffix}"
        else:
            url = f"{url_prefix}://{self._fritz_device.get_host()}{suffix}"

        return url

    def _update_loop(self):
        """
        Starts the update loop for all known items.
        """

        if self.debug_log:
            self.logger.debug(f'Starting update loop for instance {self._fritz_device.get_identifier()}')
        # Update item values using TR-064 interface
        for item in self._fritz_device.get_items():
            if self.debug_log:
                self.logger.debug(f'Request Update for {item}')

            if not self.alive:
                return

            avm_data_type = self.get_iattr_value(item.conf, 'avm_data_type')
            if avm_data_type in _wan_ip_connection_attributes:
                self._update_wan_ip_connection(item)
            elif avm_data_type in _tam_attributes:
                self._update_tam(item)
            elif avm_data_type in _aha_attributes_old:
                self._update_home_automation(item)
            elif avm_data_type in _wlan_config_attributes:
                self._update_wlan_config(item)
            elif avm_data_type in _wan_common_interface_attributes:
                self._update_wan_common_interface_configuration(item)
            elif avm_data_type in _host_attribute:
                self._update_host(item)
            elif avm_data_type in _fritz_device_attributes:
                self._update_fritz_device_info(item)
            elif avm_data_type in _wan_dsl_interface_attributes:
                self._update_wan_dsl_interface_config(item)
            elif avm_data_type in _myfritz_attributes:
                self._update_myfritz(item)
            elif avm_data_type in ['number_of_deflections']:
                self._update_number_of_deflections(item)
            elif avm_data_type in ['deflection_details']:
                self._update_deflection(item)
            elif avm_data_type in _deflection_attributes:
                self._update_deflections(item)
            elif avm_data_type in ['deflection']:
                self._update_deflection_status(item)
            elif avm_data_type in ['product_class']:
                item(self._host_info['product_class'], self.get_shortname())
            elif avm_data_type in ['manufacturer']:
                item(self._host_info['manufacturer'], self.get_shortname())
            elif avm_data_type in ['model']:
                item(self._host_info['model'], self.get_shortname())
            elif avm_data_type in ['description']:
                item(self._host_info['description'], self.get_shortname())

        # clean TR-064 response cache
        self._response_cache = dict()

        # update internal dict holding information of smarthome-devices queried via aha-http-interface if host is fritzbox and aha-http_interface is enabled for plugin instance
        if self.aha_http_interface and 'box' in self._host_info['model'].lower():
            self._update_aha_devices()

        if self._call_monitor:
            if not self.alive:
                return
            if self._fritz_device.is_available():
                self._monitoring_service.connect()

    def get_fritz_device(self):
        """
        Return _fritz_device
        """

        return self._fritz_device

    def get_monitoring_service(self):
        """
        Return _monitoring_service
        """

        return self._monitoring_service

    def set_device_availability(self, availability):
        """
        Set device availability
        """

        self._fritz_device.set_available(availability)
        if self.debug_log:
            self.logger.debug(f'Availability for FritzDevice set to {availability}')
        if not availability and self._call_monitor:
            self._monitoring_service.disconnect()
        elif availability and self._call_monitor and self.alive:
            self._monitoring_service.connect()

    def get_calllist_from_cache(self):
        """
        returns the cached calllist when all items are initialized. The filter set by plugin.conf is applied.

        :return: Array of calllist entries
        """

        # request and cache calllist
        if self._calllist_cache is None:
            self._calllist_cache = self.get_calllist(self._call_monitor_incoming_filter)
        elif len(self._calllist_cache) == 0:
            self._calllist_cache = self.get_calllist(self._call_monitor_incoming_filter)
        return self._calllist_cache

    def parse_item(self, item):
        """
        Default plugin parse_item method. Is called when the plugin is initialized. Selects each item corresponding to
        the AVM identifier and adds it to an internal array

        :param item: The item to process.
        """

        # get avm_data_type
        avm_data_type = self.get_iattr_value(item.conf, 'avm_data_type')

        # Deprecated warning for old avm_data_types:
        if avm_data_type in _deprecated_attributes:
            self.logger.warning(
                f"Item {item.id()} uses deprecated avm_data_type attribute. Please consider to switch to avm_data_type for new Fritz AHA interface")

        # handle items specific to call monitor
        if avm_data_type in _call_monitor_attributes:
            # initially - if item empty - get data from calllist
            if avm_data_type == 'last_caller_incoming' and item() == '':
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['1', '2']:
                            if 'Name' in element:
                                item(element['Name'], self.get_shortname())
                            else:
                                item(element['Caller'], self.get_shortname())
                            break
            elif avm_data_type == 'last_number_incoming' and item() == '':
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['1', '2']:
                            if 'Caller' in element:
                                item(element['Caller'], self.get_shortname())
                            else:
                                item("", self.get_shortname())
                            break
            elif avm_data_type == 'last_called_number_incoming' and item() == '':
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['1', '2']:
                            item(element['CalledNumber'], self.get_shortname())
                            break
            elif avm_data_type == 'last_call_date_incoming' and item() == '':
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
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
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['3', '4']:
                            if 'Name' in element:
                                item(element['Name'], self.get_shortname())
                            else:
                                item(element['Called'], self.get_shortname())
                            break
            elif avm_data_type == 'last_number_outgoing' and item() == '':
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['3', '4']:
                            if 'Caller' in element:
                                item(''.join(filter(lambda x: x.isdigit(), element['Caller'])), self.get_shortname())
                            else:
                                item("", self.get_shortname())
                            break
            elif avm_data_type == 'last_called_number_outgoing' and item() == '':
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['3', '4']:
                            item(element['Called'], self.get_shortname())
                            break
            elif avm_data_type == 'last_call_date_outgoing' and item() == '':
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
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
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['1', '2']:
                            item('incoming', self.get_shortname())
                            break
                        if element['Type'] in ['3', '4']:
                            item('outgoing', self.get_shortname())
                            break
            if self._call_monitor:
                if self._monitoring_service is not None:
                    self._monitoring_service.register_item(item)

        # handle items specific to call-duration
        elif avm_data_type in _call_duration_attributes:
            # items specific to call monitor duration calculation
            # initially get data from calllist
            if avm_data_type == 'call_duration_incoming' and item() == 0:
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['1', '2']:
                            duration = element['Duration']
                            duration = int(duration[0:1]) * 3600 + int(duration[2:4]) * 60
                            item(duration, self.get_shortname())
                            break
            elif avm_data_type == 'call_duration_outgoing' and item() == 0:
                if not self.get_calllist_from_cache() is None:
                    for element in self.get_calllist_from_cache():
                        if element['Type'] in ['3', '4']:
                            duration = element['Duration']
                            duration = int(duration[0:1]) * 3600 + int(duration[2:4]) * 60
                            item(duration, self.get_shortname())
                            break
            if self._monitoring_service is not None:
                self._monitoring_service.set_duration_item(item)

        # handle smarthome items using aha-interface (old / new)
        elif avm_data_type in (_aha_attributes + _aha_attributes_old):
            if self._get_item_ain(item) is not None:
                if self.debug_log:
                    self.logger.debug(
                        f"Item {item.id()} with avm smarthome attribute and defined AIN found; append to list.")
                self._fritz_device.get_smarthome_items().append(item)
            else:
                self.logger.warning(
                    f"Item {item.id()} with avm smarthome attribute found, but AIN is not defined; Item will be ignored.")

        # handle network_device related items
        elif avm_data_type in _host_attribute:
            if self.has_iattr(item.conf, 'avm_mac'):
                if self.debug_log:
                    self.logger.debug(
                        f"Item {item.id()} with avm attribute 'network_device' and defined 'avm_mac' found; append to list.")
                self._fritz_device.get_items().append(item)
            else:
                self.logger.warning(
                    f"Item {item.id()} with avm attribute found, but 'avm_mac' is not defined; Item will be ignored.")

        # handle network_device related items (mac address in parent items defined)
        elif avm_data_type in _host_child_attributes:
            avm_mac = self._get_mac(item)
            if avm_mac:
                if self.debug_log:
                    self.logger.debug(
                        f"Item {item.id()} with avm device attribute and defined 'avm_mac' found; append to list.")
                self._fritz_device.get_items().append(item)
            else:
                self.logger.warning(
                    f"Item {item.id()} with avm attribute found, but 'avm_mac' is not defined in parent item; Item will be ignored.")

        # handle wlan related items
        elif avm_data_type in _wlan_config_attributes:
            avm_wlan_index = self._get_wlan_index(item)
            if avm_wlan_index is not None:
                if self.debug_log:
                    self.logger.debug(
                        f"Item {item.id()} with avm device attribute and defined 'avm_wlan_index' found; append to list.")
                self._fritz_device.get_items().append(item)
            else:
                self.logger.warning(
                    f"Item {item.id()} with avm attribute found, but 'avm_wlan_index' is not defined; Item will be ignored.")

        # handle tam related items
        elif avm_data_type in _tam_attributes:
            avm_tam_index = self._get_tam_index(item)
            if avm_tam_index is not None:
                if self.debug_log:
                    self.logger.debug(
                        f"Item {item.id()} with avm device attribute and defined 'avm_tam_index' found; append to list.")
                self._fritz_device.get_items().append(item)
            else:
                self.logger.warning(
                    f"Item {item.id()} with avm attribute found, but 'avm_tam_index' is not defined; Item will be ignored.")

        # handle remaining items not needing further attribute
        elif self.has_iattr(item.conf, 'avm_data_type'):
            if self.debug_log:
                self.logger.debug(f"Item {item.id()} with avm attribute found; append to list")
            self._fritz_device.get_items().append(item)

        # items which can be changed outside the plugin context and need to be submitted to the FritzDevice
        if avm_data_type in (_avm_rw_attributes + _aha_wo_attributes + _aha_rw_attributes):
            return self.update_item

    def _get_sid(self):
        """
        Get a sid by solving the PBKDF2 (or MD5) challenge-response process.
        """

        self.logger.debug(f"HTTP Login requested, getting Session-ID")

        username = self._fritz_device.get_user()
        password = self._fritz_device.get_password()
        url = self._build_url(self._login_sid_route, lua=True)

        try:
            response = self._request(url)
            if self.debug_log:
                self.logger.debug(f"Debug apriori Session request response text: {response}")
            sid, challenge, blocktime = self._get_login_infos_from_http_request(response)
            if self.debug_log:
                self.logger.debug(f"Debug apriori SID: {sid}, Challenge: {challenge}, BlockTime: {blocktime}")
        except Exception as ex:
            self.logger.warning(f"failed to get challenge, error={ex}")
            return

        if challenge.startswith('2$'):
            if self.debug_log:
                self.logger.debug("PBKDF2 supported")
            challenge_response = self._calculate_pbkdf2_response(challenge, password)
        else:
            if self.debug_log:
                self.logger.debug("Falling back to MD5")
            challenge_response = self._calculate_md5_response(challenge, password)
        if blocktime > 0:
            if self.debug_log:
                self.logger.debug(f"Waiting for {blocktime} seconds...")
            time.sleep(blocktime)

        try:
            if self.debug_log:
                self.logger.debug('Sending response...')
            params = {"username": username, "response": challenge_response}
            response = self._request(url, params=params)
            if self.debug_log:
                self.logger.debug(f"Debug posterior Session request response text: {response}")
            sid, challenge, blocktime = self._get_login_infos_from_http_request(response)
            if self.debug_log:
                self.logger.debug(f"Debug posterior SID: {sid}, Challenge: {challenge}, BlockTime: {blocktime}")
        except Exception as ex:
            self.logger.warning(f"failed to login, error={ex}")
            return

        if sid == "0000000000000000":
            self.logger.warning(f"wrong username or password")
            return

        self.sid = sid

    def _get_login_infos_from_http_request(self, response):
        """
        Get login info from http request response
        """

        xml = minidom.parseString(response)
        sid = self._get_value_from_xml_node(xml, 'SID')
        challenge = self._get_value_from_xml_node(xml, 'Challenge')
        blocktime = int(self._get_value_from_xml_node(xml, 'BlockTime'))

        if self.debug_log:
            self.logger.debug(f"_get_login_infos_from_http_request: sid={sid}, challenge={challenge}, blocktime={blocktime}")

        return sid, challenge, blocktime

    def _http_logout_request(self):
        """
        Send a logout request.
        """

        if self.debug_log:
            self.logger.warning(f"_http_logout_request called")

        url = self._build_url(self._login_sid_route, lua=True)
        params = {"logout": "1", "sid": self.sid}
        response = self._request(url, params=params)
        sid, challenge, blocktime = self._get_login_infos_from_http_request(response)

        if self.debug_log:
            self.logger.warning(f"_http_logout_request: SID: {sid}, Challenge: {challenge}, BlockTime: {blocktime}")

        if sid == "0000000000000000":
            self.logger.warning(f"HTTP Logout successful.")
        self.sid = None

    def _check_sid(self):
        """
        Check if knows Session ID is still valid
        """

        if self.debug_log:
            self.logger.debug(f"_check_sid called")

        url = self._build_url(self._login_sid_route, lua=True)
        params = {"sid": self.sid}
        response = self._request(url, params)
        sid, challenge, blocktime = self._get_login_infos_from_http_request(response)
        if self.debug_log:
            self.logger.debug(f"_check_sid: SID: {sid}, Challenge: {challenge}, BlockTime: {blocktime}")

        if sid == "0000000000000000":
            self.logger.warning(f"Session ID is invalid. Try to generate new one.")
            self._get_sid()
        else:
            self.logger.info(f"Session ID is still valid.")

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

    def _get_lua_post_request(self, url, data, headers):
        """
        Do Lua POST request
        """

        try:
            self._lua_session.post(url, data=data, timeout=self._timeout, headers=headers,
                                   auth=HTTPDigestAuth(self._fritz_device.get_user(),
                                                       self._fritz_device.get_password()), verify=self._verify)
        except Exception as e:
            if self._fritz_device.is_available():
                self.logger.error(
                    f"Exception when sending LUA POST request for updating item towards the FritzDevice: {e}")
                self.set_device_availability(False)
            return
        if not self._fritz_device.is_available():
            self.set_device_availability(True)

    def _get_post_request(self, url, data, headers):
        """
        Do POST request
        """

        try:
            response = self._session.post(url, data=data, timeout=self._timeout, headers=headers,
                                          auth=HTTPDigestAuth(self._fritz_device.get_user(),
                                                              self._fritz_device.get_password()),
                                          verify=self._verify)
        except Exception as e:
            self.logger.error(f'Exception while sending POST request: {e}')
            if self._fritz_device.is_available():
                self.set_device_availability(False)
            return
        else:
            if response.status_code == 200:
                self.logger.debug("Sending POST request successful")
                if not self._fritz_device.is_available():
                    self.set_device_availability(True)
                return response
            else:
                try:
                    response.raise_for_status()
                except requests.exceptions.HTTPError as e:
                    status_code = e.response.status_code
                    start = data.find('NewMACAddress') + 14
                    mac = data[start:start + 17]
                    self.logger.warning(
                        f'Error code {status_code} with Exception {e} while sending POST request. Check correctness of MAC-addresses {mac} in item.yaml')
                    if self._fritz_device.is_available():
                        self.set_device_availability(False)
                    return

    def _get_post_request_as_xml(self, url, data, headers):
        """
        Get POST request response as xml
        """

        response = self._get_post_request(url, data, headers)
        if response is None:
            return

        try:
            xml = minidom.parseString(response.content)
        except Exception as e:
            self.logger.error(f'Exception while parsing response: {e}')
            return
        else:
            return xml

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        | Write items values - in case they were changed from somewhere else than the AVM plugin (=the FritzDevice) to
        | the FritzDevice.

        | Uses:
        | - http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_tam.pdf
        | - http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf
        | - http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_homeauto.pdf

        :param item: item to be updated towards the FritzDevice (Supported item avm_data_types: wlanconfig, tam, aha_device)
        :param caller: caller
        :param source: source
        :param dest: destination
        """

        if self.alive and caller != self.get_shortname():

            # get avm_data_type and readafterwrite
            avm_data_type = self.get_iattr_value(item.conf, 'avm_data_type')
            readafterwrite = None
            if self.has_iattr(item.conf, 'avm_read_after_write'):
                readafterwrite = int(self.get_iattr_value(item.conf, 'avm_read_after_write'))
                if self.debug_log:
                    self.logger.debug(
                        f'Attempting read after write for item: {item.id()}, avm_data_type: {avm_data_type}, delay: {readafterwrite}s')

            # handle wlanconfig attributes
            if avm_data_type == 'wlanconfig':
                # get wlan_index
                wlan_index = self._get_wlan_index(item)

                # set wlan config
                self.set_wlan_config(wlan_index, bool(item()))

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_wlan_config(item)

            # handle tam attributes
            elif avm_data_type == 'tam':
                # get tam_index
                tam_index = self._get_tam_index(item)

                # set tam
                if not tam_index or tam_index <= 0:
                    self.logger.error('Parameter <avm_tam_index> for item not defined in item.conf')
                else:
                    self.set_tam(tam_index, bool(item()))

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_tam(item)

            # handle aha_device
            elif avm_data_type == 'aha_device':
                # get ain
                ain = self._get_item_ain(item)

                # set aha-device
                if not ain:
                    self.logger.error('Parameter <ain> or <avm_ain> for item not defined in item.conf')
                else:
                    self.set_aha_device(ain, bool(item()))

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_home_automation(item)

            # handle deflection_enable
            elif avm_data_type == 'deflection_enable':
                # get deflection index
                deflection_index = self._get_deflection_index(item)

                # set deflection
                if not deflection_index or deflection_index <= 0:
                    self.logger.error('Parameter <avm_deflection_index> for item not defined in item.conf')
                else:
                    self.set_deflection(deflection_index, bool(item()))

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_deflection_status(item)

            # handle hkr window_open
            elif avm_data_type in ['set_window_open', 'window_open']:
                new_value = bool(item())
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} caller is: {caller}; new value to be set is {new_value}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # assemble endtimestamp:
                if new_value is False:
                    endtime = 0
                else:
                    now = self.shtime.now()
                    unix_secs = mktime(now.timetuple())
                    # set endtime to now + 12h:
                    endtime = int(unix_secs + 12 * 3600)
                if self.debug_log:
                    self.logger.debug(f"HKR endtimestamp is: {endtime}")

                # write new value
                self.set_hkr_windowopen(ain_device, endtime)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle hkr target temperature
            elif avm_data_type in ['set_target_temperature', 'target_temperature']:
                new_value = float(item())
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} caller is: {caller}; new value to be set is {new_value}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # write new target temp
                self.set_target_temperature(ain_device, new_value)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle hkr boost mode
            elif avm_data_type in ['set_hkr_boost', 'hkr_boost']:
                new_value = bool(item())
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} caller is: {caller}; new value to be set is {new_value}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # Assemble endtimestamp:
                if new_value is False:
                    endtime = 0
                else:
                    now = self.shtime.now()
                    unix_secs = mktime(now.timetuple())
                    # set endtime to now + 12h:
                    endtime = int(unix_secs + 12 * 3600)
                if self.debug_log:
                    self.logger.debug(f"HKR boost endtimestamp is: {endtime}")

                # write new value
                self.set_hkr_boost(ain_device, endtime)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle light on/off
            elif avm_data_type in ['set_simpleonoff', 'simpleonoff']:
                new_value = bool(item())
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} caller is: {caller}; new value to be set is {new_value}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # write value
                self.set_switch_onoff(ain_device, new_value)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle level
            elif avm_data_type in ['set_level', 'level']:
                new_value = int(item())
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} caller is: {caller}; new value to be set is {new_value}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # write value
                self.set_level(ain_device, new_value)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle level percent
            elif avm_data_type in ['set_levelpercentage', 'levelpercentage']:
                cmd_level = int(item())
                if self.debug_log:
                    self.logger.debug(f"set_level caller is: {caller}; switch to be set to level: {cmd_level}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # write value
                self.set_level_percentage(ain_device, cmd_level)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle socket switch/relais on/off
            elif avm_data_type == 'switch_state':
                new_value = bool(item())
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} caller is: {caller}; new value to be set is {new_value}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # write value
                if new_value is True:
                    self.set_switch_on(ain_device)
                else:
                    self.set_switch_off(ain_device)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle socket switch/relais toggle
            elif avm_data_type == 'switch_toggle':
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} caller is: {caller}; switch will be toggled")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # write value
                self.set_switch_toggle(ain_device)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle set hue
            elif avm_data_type in ['set_hue', 'hue']:
                hue_value = int(item())
                if self.debug_log:
                    self.logger.debug(f"{avm_data_type} caller is: {caller}; new value to be set is {hue_value}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # search saturation:
                saturation = -1
                parentItem = item.return_parent()
                for child in parentItem.return_children():
                    if self.has_iattr(child.conf, 'avm_data_type'):
                        if self.get_iattr_value(child.conf, 'avm_data_type') in ['set_saturation', 'saturation']:
                            saturation = int(child())
                            # if self.debug_log:
                            # self.logger.debug(f"Debug hue {hue_value}, saturation {saturation}")
                            # write value
                            self.set_color(ain_device, hue_value, saturation, duration=0)
                if saturation == -1:
                    self.logger.warning(
                        f"Cannot execute hue command because saturation value cannot be found in item tree")

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle set saturation
            elif avm_data_type in ['set_saturation', 'saturation']:
                saturation_value = int(item())
                if self.debug_log:
                    self.logger.debug(
                        f"{avm_data_type} caller is: {caller}; Saturation to be set to: {saturation_value}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # search hue:
                hue = -1
                parentItem = item.return_parent()
                for child in parentItem.return_children():
                    if self.has_iattr(child.conf, 'avm_data_type'):
                        if self.get_iattr_value(child.conf, 'avm_data_type') in ['set_hue', 'hue']:
                            hue = int(child())
                            # if self.debug_log:
                            # self.logger.debug(f"Debug saturation {saturation_value}, hue {hue}")
                            # write value
                            self.set_color(ain_device, hue, saturation_value, duration=0)
                if hue == -1:
                    self.logger.warning(
                        f"Cannot execute saturation command because hue value cannot be found in item tree")

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            # handle set color temperature
            elif avm_data_type in ['set_colortemperature', 'colortemperature']:
                cmd_colortemperature = int(item())
                if self.debug_log:
                    self.logger.debug(
                        f"set_colortemperature caller is: {caller}; colortemperature to be set to: {cmd_colortemperature}")

                # get AIN
                ain_device = self._get_item_ain(item)
                if self.debug_log:
                    self.logger.debug(f"Device AIN is {ain_device}")

                # write value
                self.set_colortemperature(ain_device, cmd_colortemperature)

                # read new value after writing
                if readafterwrite:
                    time.sleep(readafterwrite)
                    self._update_aha_devices()

            else:
                self.logger.error(f"{avm_data_type} is not defined to be updated.")

    def set_wlan_config(self, wlan_index, new_enable=False):
        """
        Set WLAN Config
        """

        param = f"/upnp/control/wlanconfig{wlan_index}"
        url = self._build_url(param)
        headers = self._header.copy()
        action = 'SetEnable'
        headers['SOAPACTION'] = f"{self._urn_map['WLANConfiguration']}"[:43] + f"{wlan_index}#{action}"
        soap_data = self._assemble_soap_data(action, f"{self._urn_map['WLANConfiguration']}"[:43] + f"{wlan_index}",
                                             {'NewEnable': int(new_enable)})

        self._get_lua_post_request(url, soap_data, headers)

        # check if remaining time is set as item
        for citem in self._fritz_device.get_items():  # search for guest time remaining item.
            if self.get_iattr_value(citem.conf, 'avm_data_type') == 'wlan_guest_time_remaining' and int(
                    self.get_iattr_value(citem.conf, 'avm_wlan_index')) == wlan_index:
                self._response_cache.pop(
                    f"wlanconfig_{self.get_iattr_value(citem.conf, 'avm_wlan_index')}_X_AVM-DE_GetWLANExtInfo",
                    None)  # reset response cache
                self._update_wlan_config(citem)  # immediately update remaining guest time

    def set_tam(self, tam_index=0, new_enable=False):
        """
        Set TAM
        """

        url = self._build_url("/upnp/control/x_tam")
        headers = self._header.copy()
        action = 'SetEnable'
        headers['SOAPACTION'] = f"{self._urn_map['TAM']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['TAM'],
                                             {'NewIndex': tam_index, 'NewEnable': int(new_enable)})

        self._get_lua_post_request(url, soap_data, headers)

    def set_aha_device(self, ain='', set_switch=False):
        """
        Set AHA-Device via TR-064 protocol
        """

        url = self._build_url("/upnp/control/x_homeauto")
        headers = self._header.copy()
        action = 'SetSwitch'
        headers['SOAPACTION'] = f"{self._urn_map['Homeauto']}#{action}"
        # SwitchState: OFF, ON, TOGGLE, UNDEFINED
        switch_state = "ON" if set_switch is True else "OFF"
        soap_data = self._assemble_soap_data(action, self._urn_map['Homeauto'],
                                             {'NewAIN': ain.strip(), 'NewSwitchState': switch_state})

        self._get_lua_post_request(url, soap_data, headers)

    def get_contact_name_by_phone_number(self, phone_number='', phonebook_id=0):
        """
        Searches the phonebook for a contact by a given (complete) phone number

        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf
        | Implementation of this method used information from https://www.symcon.de/forum/threads/25745-FritzBox-mit-SOAP-auslesen-und-steuern

        :param phone_number: full phone number of contact
        :param phonebook_id: ID of the phone book (default: 0)
        :return: string of the contact's real name
        """

        url = self._build_url("/upnp/control/x_contact")
        action = "GetPhonebook"
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['OnTel']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'], {'NewPhonebookID': phonebook_id})

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        pb_url_xml = xml.getElementsByTagName('NewPhonebookURL')

        if len(pb_url_xml) > 0:
            pb_url = pb_url_xml[0].firstChild.data
            try:
                pb_result = self._session.get(pb_url, timeout=self._timeout, verify=self._verify)
                pb_xml = minidom.parseString(pb_result.content)
            except Exception as e:
                if self._fritz_device.is_available():
                    self.logger.error(f"Exception when sending GET request or parsing response: {e}")
                    self.set_device_availability(False)
                return
            if not self._fritz_device.is_available():
                self.set_device_availability(True)

            contacts = pb_xml.getElementsByTagName('contact')
            if len(contacts) > 0:
                for contact in contacts:
                    phone_numbers = contact.getElementsByTagName('number')
                    if phone_numbers.length > 0:
                        i = phone_numbers.length
                        while i >= 0:
                            i -= 1
                            if phone_number in phone_numbers[i].firstChild.data:
                                return contact.getElementsByTagName('realName')[0].firstChild.data.strip()
                                # no contact with phone number found, return number only
            return phone_number
        else:
            self.logger.error("Phonebook not available on the FritzDevice")

        return phone_number

    def get_phone_numbers_by_name(self, name='', phonebook_id=0):
        """
        Searches the phonebook for a contact by a given name

        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf
        | CURL for testing which phonebooks exists:
        | curl  --anyauth -u user:'password' 'https://192.168.178.1:49443/upnp/control/x_contact' -H 'Content-Type: text/xml; charset="utf-8"' -H 'SoapAction: urn:dslforum-org:service:X_AVM-DE_OnTel:1#GetPhonebook' -d '<?xml version="1.0" encoding="utf-8"?> <s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"> <s:Body> <u:GetPhonebook xmlns:u="urn:dslforum-org:service:X_AVM-DE_OnTel:1"> <s:NewPhonebookID>0</s:NewPhonebookID> </u:GetPhonebook> </s:Body> </s:Envelope>' -s -k
        | Implementation of this method used information from https://www.symcon.de/forum/threads/25745-FritzBox-mit-SOAP-auslesen-und-steuern

        :param name: partial or full name of contact as defined in the phonebook.
        :param phonebook_id: ID of the phone book (default: 0)
        :return: dict of found contact names (keys) with each containing an array of dicts (keys: type, number)
        """

        url = self._build_url("/upnp/control/x_contact")
        action = "GetPhonebook"
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['OnTel']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'], {'NewPhonebookID': phonebook_id})

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        pb_url_xml = xml.getElementsByTagName('NewPhonebookURL')

        if len(pb_url_xml) > 0:
            pb_url = pb_url_xml[0].firstChild.data
            try:
                pb_result = self._session.get(pb_url, timeout=self._timeout, verify=self._verify)
                pb_xml = minidom.parseString(pb_result.content)
            except Exception as e:
                if self._fritz_device.is_available():
                    self.logger.error(f"Exception when sending GET request or parsing response: {e}")
                    self.set_device_availability(False)
                return
            if not self._fritz_device.is_available():
                self.set_device_availability(True)

            contacts = pb_xml.getElementsByTagName('contact')
            result_numbers = {}
            if name == '':
                return result_numbers
            if len(contacts) > 0:
                for contact in contacts:
                    real_names = contact.getElementsByTagName('realName')
                    if real_names.length > 0:
                        i = 0
                        while i < real_names.length:
                            if name.lower() in real_names[i].firstChild.data.lower():
                                phone_numbers = contact.getElementsByTagName('number')
                                if phone_numbers.length > 0:
                                    result_numbers[real_names[i].firstChild.data] = []
                                    j = 0
                                    while j < phone_numbers.length:
                                        if phone_numbers[j].firstChild.data:
                                            result_number_dict = dict()
                                            result_number_dict['number'] = phone_numbers[j].firstChild.data
                                            result_number_dict['type'] = phone_numbers[j].attributes["type"].value
                                            result_numbers[real_names[i].firstChild.data].append(result_number_dict)
                                        j += 1
                            i += 1
            return result_numbers
        else:
            self.logger.error("Phonebook not available on the FritzDevice")

    def get_calllist(self, filter_incoming='', phonebook_id=0):
        """
        Returns an array of all calllist entries

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf
        Curl for testing if the calllist url is returned:
        curl  --anyauth -u user:'password' 'https://192.168.178.1:49443/upnp/control/x_contact' -H 'Content-Type: text/xml; charset="utf-8"' -H 'SoapAction: urn:dslforum-org:service:X_AVM-DE_OnTel:1#GetCallList' -d '<?xml version="1.0" encoding="utf-8"?> <s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"> <s:Body> <u:GetCallList xmlns:u="urn:dslforum-org:service:X_AVM-DE_OnTel:1"> <s:NewPhonebookID>0</s:NewPhonebookID> </u:GetCallList> </s:Body> </s:Envelope>' -s -k
        :param: Filter to filter incoming calls to a specific destination phone number
        :param: ID of the phone book (default: 0)
        :return: Array of calllist entries with the attributes 'Id','Type','Caller','Called','CalledNumber','Name','Numbertype','Device','Port','Date','Duration' (some optional)
        """

        url = self._build_url("/upnp/control/x_contact")
        action = "GetCallList"
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['OnTel']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'], {'NewPhonebookID': phonebook_id})

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        if xml is not None:
            calllist_url_xml = xml.getElementsByTagName('NewCallListURL')

            if len(calllist_url_xml) > 0:
                calllist_url = calllist_url_xml[0].firstChild.data

                try:
                    calllist_result = self._session.get(calllist_url, timeout=self._timeout, verify=self._verify)
                    calllist_xml = minidom.parseString(calllist_result.content)
                except Exception as e:
                    if self._fritz_device.is_available():
                        self.logger.error(f"Exception when sending GET request or parsing response: {e}")
                        self.set_device_availability(False)
                    return
                if not self._fritz_device.is_available():
                    self.set_device_availability(True)

                calllist_entries = calllist_xml.getElementsByTagName('Call')
                result_entries = []
                if len(calllist_entries) > 0:
                    for calllist_entry in calllist_entries:
                        result_entry = {}

                        progress = True

                        if len(filter_incoming) > 0:
                            type_element = calllist_entry.getElementsByTagName("Type")
                            if len(type_element) > 0:
                                if type_element[0].hasChildNodes():
                                    type = int(type_element[0].firstChild.data)

                                    if type == 1 or type == 2:
                                        called_number_element = calllist_entry.getElementsByTagName("CalledNumber")
                                        if len(called_number_element) > 0:
                                            if called_number_element[0].hasChildNodes():
                                                called_number = called_number_element[0].firstChild.data
                                                # if self.debug_log:
                                                # self.logger.debug(called_number+" "+filter_incoming)
                                                if filter_incoming not in called_number:
                                                    progress = False
                        if progress:
                            attributes = ['Id', 'Type', 'Caller', 'Called', 'CalledNumber', 'Name', 'Numbertype',
                                          'Device',
                                          'Port', 'Date', 'Duration']
                            for attribute in attributes:
                                attribute_value = calllist_entry.getElementsByTagName(attribute)
                                if len(attribute_value) > 0:
                                    if attribute_value[0].hasChildNodes():
                                        if attribute != 'Date':
                                            result_entry[attribute] = attribute_value[0].firstChild.data
                                        else:
                                            result_entry[attribute] = datetime.strptime(
                                                attribute_value[0].firstChild.data, '%d.%m.%y %H:%M')

                            result_entries.append(result_entry)
                    return result_entries
                else:
                    if self.debug_log:
                        self.logger.debug("No calllist entries on the FritzDevice")
            else:
                self.logger.error("Calllist not available on the FritzDevice")

            return

    def reboot(self):
        """
        Reboots the FritzDevice

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceconfigSCPD.pdf
        """

        url = self._build_url("/upnp/control/deviceconfig")
        action = 'Reboot'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['DeviceConfig']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['DeviceConfig'])

        self._get_post_request_as_xml(url, soap_data, headers)

    def wol(self, mac_address):
        """
        Sends a WOL (WakeOnLAN) command to a MAC address

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param mac_address: MAC address of the device to wake up
        """

        url = self._build_url("/upnp/control/hosts")
        action = 'X_AVM-DE_WakeOnLANByMACAddress'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['Hosts']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['Hosts'], {'NewMACAddress': mac_address})

        self._get_post_request_as_xml(url, soap_data, headers)

        return

    def get_hosts(self, only_active):
        """
        Gets the information (host details) of all hosts as an array of dicts

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param only_active: bool, if only active hosts shall be returned
        :return: Array host dicts (see get_host_details)
        """

        url = self._build_url("/upnp/control/hosts")
        action = 'GetHostNumberOfEntries'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['Hosts']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['Hosts'])

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        number_of_hosts = int(self._get_value_from_xml_node(xml, 'NewHostNumberOfEntries'))
        hosts = []
        for i in range(1, number_of_hosts):
            host = self.get_host_details(i)
            if not only_active or (only_active and self.to_bool(host['is_active'])):
                hosts.append(host)
        return hosts

    def get_host_details(self, index):
        """
        Gets the information of a hosts at a specific index

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf

        :param index: index of host in hosts list
        :return: Dict host data: name, interface_type, ip_address, address_source, mac_address, is_active, lease_time_remaining
        """

        url = self._build_url("/upnp/control/hosts")
        action = 'GetGenericHostEntry'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['Hosts']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['Hosts'], {'NewIndex': index})

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        host = {
            'name': self._get_value_from_xml_node(xml, 'NewHostName'),
            'interface_type': self._get_value_from_xml_node(xml, 'NewInterfaceType'),
            'ip_address': self._get_value_from_xml_node(xml, 'NewIPAddress'),
            'address_source': self._get_value_from_xml_node(xml, 'NewAddressSource'),
            'mac_address': self._get_value_from_xml_node(xml, 'NewMACAddress'),
            'is_active': self._get_value_from_xml_node(xml, 'NewActive'),
            'lease_time_remaining': self._get_value_from_xml_node(xml, 'NewLeaseTimeRemaining')
        }
        return host

    def _get_host_device_info(self):
        """
        Gets the detailed information of the host as device

        Uses: https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceinfoSCPD.pdf
        """

        url = self._build_url("/upnp/control/deviceinfo")
        action = 'GetInfo'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['DeviceInfo']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['DeviceInfo'])

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        if not xml:
            return

        host_info = {
            "product_class": self._get_value_from_xml_node(xml, "NewProductClass"),
            "manufacturer": self._get_value_from_xml_node(xml, "NewManufacturerName"),
            "model": self._get_value_from_xml_node(xml, "NewModelName"),
            "description": self._get_value_from_xml_node(xml, "NewDescription"),
            "sw_version": self._get_value_from_xml_node(xml, "NewSoftwareVersion"),
            "hw_version": self._get_value_from_xml_node(xml, "NewHardwareVersion"),
        }

        self._host_info.update(host_info)

    def reconnect(self):
        """
        Reconnects the FritzDevice to the WAN

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wanipconnSCPD.pdf
        """

        url = self._build_url("/igdupnp/control/WANIPConn1")
        action = 'ForceTermination'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['WANIPConnection']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['WANIPConnection'])

        self._get_post_request_as_xml(url, soap_data, headers)

    def get_call_origin(self):
        """
        Gets the phone name, currently set as call_origin.

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        :return: String phone name
        """

        url = self._build_url("/upnp/control/x_voip")
        action = 'X_AVM-DE_DialGetConfig'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['X_VoIP']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['X_VoIP'])

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        phone_name = self._get_value_from_xml_node(xml, 'NewX_AVM-DE_PhoneName')
        if phone_name is not None:
            return phone_name

        self.logger.error("No call origin available.")
        return

    def get_phone_name(self, index=1):
        """
        Get the phone name at a specific index. The returned value can be used as phone_name for set_call_origin.

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param index: Parameter is an INT, starting from 1. In case an index does not exist, an error is logged.
        :return: String phone name
        """

        if not self.is_int(index):
            self.logger.error(f"Index parameter {index} is no INT.")
            return

        url = self._build_url("/upnp/control/x_voip")
        action = 'X_AVM-DE_GetPhonePort'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['X_VoIP']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['X_VoIP'], {'NewIndex': index})

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        phone_name = self._get_value_from_xml_node(xml, 'NewX_AVM-DE_PhoneName')
        if phone_name is not None:
            return phone_name

        self.logger.error(f"No phone name available at provided index {index}")
        return

    def set_call_origin(self, phone_name):
        """
        Sets the call origin, e.g. before running 'start_call'

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param phone_name: full phone identifier, could be e.g. '\*\*610' for an internal device
        """

        url = self._build_url("/upnp/control/x_voip")
        action = 'X_AVM-DE_DialSetConfig'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['X_VoIP']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['X_VoIP'],
                                             {'NewX_AVM-DE_PhoneName': phone_name.strip()})
        self._get_post_request_as_xml(url, soap_data, headers)

    def start_call(self, phone_number):
        """
        Triggers a call for a given phone number

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf

        :param phone_number: full phone number to call
        """

        url = self._build_url("/upnp/control/x_voip")
        action = 'X_AVM-DE_DialNumber'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['X_VoIP']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['X_VoIP'],
                                             {'NewX_AVM-DE_PhoneNumber': phone_number.strip()})
        self._get_post_request_as_xml(url, soap_data, headers)

    def cancel_call(self):
        """
        Cancels an active call

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_voipSCPD.pdf
        """

        url = self._build_url("/upnp/control/x_voip")
        action = 'X_AVM-DE_DialHangup'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['X_VoIP']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['X_VoIP'])
        self._get_post_request_as_xml(url, soap_data, headers)

    def get_device_log_from_lua(self):
        """
        Gets the Device Log from the LUA HTTP Interface via LUA Scripts (more complete than the get_device_log TR-064 version.
        :return: Array of Device Log Entries (text, type, category, timestamp, date, time)
        """

        if not self.sid:
            self._get_sid()
        my_sid = self.sid

        query_string = f"/query.lua?mq_log=logger:status/log&sid={my_sid}"
        try:
            r = self._lua_session.get(self._build_url(query_string, lua=True), timeout=self._timeout, verify=self._verify)
        except requests.exceptions.Timeout:
            self.logger.debug(f"get_device_log_from_lua: get request timed out.")
            return
        except Exception as e:
            self.logger.debug(f"get_device_log_from_lua: Error {e} occurred.")
            return

        status_code = r.status_code
        if status_code == 200:
            if self.debug_log:
                self.logger.debug("get_device_log_from_lua: Sending query.lua command successful")
        else:
            self.logger.error(f"get_device_log_from_lua: query.lua command error code: {status_code}")
            return

        try:
            data = r.json()['mq_log']
            newlog = []

            for text, typ, cat in data:
                l_date = text[:8]
                l_time = text[9:17]
                l_text = text[18:]
                l_cat = int(cat)
                l_type = int(typ)
                l_ts = int(datetime.timestamp(datetime.strptime(text[:17], '%d.%m.%y %H:%M:%S')))
                newlog.append([l_text, l_type, l_cat, l_ts, l_date, l_time])

            return newlog
        except JSONDecodeError:
            self.logger.error('get_device_log_from_web: SID seems invalid.Please try again.')
        return

    def get_device_log_from_tr064(self):
        """
        Gets the Device Log via TR-064
        :return: Array of Device Log Entries (Strings)
        """

        url = self._build_url("/upnp/control/deviceinfo")
        action = 'GetDeviceLog'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['DeviceInfo']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['DeviceInfo'])

        response = self._get_post_request(url, soap_data, headers)
        if response is not None:
            self._response_cache[f"dev_info_{action}"] = response.content

        try:
            xml = minidom.parseString(self._response_cache[f"dev_info_{action}"])
        except Exception as e:
            self.logger.error(f"get_device_log_from_tr064: Exception when parsing response: {e}")
            return

        element_xml = xml.getElementsByTagName('NewDeviceLog')

        if xml is not None:
            if element_xml[0].firstChild is not None:
                return element_xml[0].firstChild.nodeValue.split("\n")
            else:
                return ""

    def is_host_active(self, mac_address):
        """
        Checks if a MAC address is active on the FritzDevice, e.g. the status can be used for simple presence detection

        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf
        | Also reference: https://blog.pregos.info/2015/11/07/anwesenheitserkennung-fuer-smarthome-mit-der-fritzbox-via-tr-064/

        :param: MAC address of the host
        :return: True or False, depending if the host is active on the FritzDevice
        """

        url = self._build_url("/upnp/control/hosts")
        action = 'GetSpecificHostEntry'
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['Hosts']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['Hosts'], {'NewMACAddress': mac_address})

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        if xml is not None:
            tag_content = xml.getElementsByTagName('NewActive')
            if len(tag_content) > 0:
                if tag_content[0].firstChild.data == "1":
                    is_active = True
                else:
                    is_active = False
            else:
                is_active = False
                if self.debug_log:
                    self.logger.debug(
                        f"MAC Address {mac_address} not available on the FritzDevice - ID: {self._fritz_device.get_identifier()}")
            return bool(is_active)

    def _update_myfritz(self, item):
        """
        Retrieves information related to myfritz status of the FritzDevice

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_myfritzSCPD.pdf

        :param item: item to be updated (Supported item avm_data_types: myfritz_status)
        """

        url = self._build_url("/upnp/control/x_myfritz")
        headers = self._header.copy()

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'myfritz_status':
            action = 'GetInfo'
            headers['SOAPACTION'] = f"{self._urn_map['MyFritz']}#{action}"
            soap_data = self._assemble_soap_data(action, self._urn_map['MyFritz'])
        else:
            self.logger.error(
                f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin method (_update_myfritz)")
            return

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        if xml is not None:
            tag_content = xml.getElementsByTagName('NewEnabled')
            if len(tag_content) > 0:
                item(tag_content[0].firstChild.data, self.get_shortname())

    def _update_host(self, item):
        """
        Retrieves information related to a network_device represented by its MAC address, e.g. the status of the network_device can be used for simple presence detection

        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/hostsSCPD.pdf
        | Also reference: https://blog.pregos.info/2015/11/07/anwesenheitserkennung-fuer-smarthome-mit-der-fritzbox-via-tr-064/

        :param item: item to be updated (Supported item avm_data_types: network_device, child item avm_data_types: device_ip, device_connection_type, device_hostname)
        """

        url = self._build_url("/upnp/control/hosts")
        headers = self._header.copy()

        if self.debug_log:
            self.logger.debug(f'_update_host called: item.conf={item.conf}')
        if self.get_iattr_value(item.conf, 'avm_data_type') == 'network_device':
            if not self.has_iattr(item.conf, 'avm_mac'):
                self.logger.error(f"No avm_mac attribute provided in network_device item {item.property.path}")
                return
            action = 'GetSpecificHostEntry'
            headers['SOAPACTION'] = f"{self._urn_map['Hosts']}#{action}"
            soap_data = self._assemble_soap_data(action, self._urn_map['Hosts'],
                                                 {'NewMACAddress': self.get_iattr_value(item.conf, 'avm_mac')})
        else:
            self.logger.error(
                f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin (_update_host)")
            return

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        if xml is not None:
            tag_content = xml.getElementsByTagName('NewActive')
            if len(tag_content) > 0:
                item(tag_content[0].firstChild.data, self.get_shortname())
                for child in item.return_children():
                    data = None
                    if self.has_iattr(child.conf, 'avm_data_type'):
                        if self.get_iattr_value(child.conf, 'avm_data_type') == 'device_ip':
                            device_ip = xml.getElementsByTagName('NewIPAddress')
                            if len(device_ip) > 0:
                                if device_ip[0].firstChild is not None:
                                    data = device_ip[0].firstChild.data
                                else:
                                    data = ''
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'device_connection_type':
                            device_connection_type = xml.getElementsByTagName('NewInterfaceType')
                            if len(device_connection_type) > 0:
                                if device_connection_type[0].firstChild is not None:
                                    data = device_connection_type[0].firstChild.data
                                else:
                                    data = ''
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'device_hostname':
                            data = self._get_value_from_xml_node(xml, 'NewHostName')

                        if data is not None:
                            child(data, self.get_shortname())
                        else:
                            self.logger.info(
                                f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")

        else:
            item(0)
            if self.debug_log:
                self.logger.debug(
                    f"MAC Address {self.get_iattr_value(item.conf, 'avm_mac')} for item {item.property.path} not available on the FritzDevice - ID: {self._fritz_device.get_identifier()}")

    def _update_home_automation(self, item):
        """
        Updates AVM home automation device related information

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_homeauto.pdf
        CURL for testing which data is coming back:
        curl --anyauth -u user:'password' "https://192.168.178.1:49443/upnp/control/x_homeauto" -H "Content-Type: text/xml; charset="utf-8"" -H "SoapAction:urn:dslforum-org:service:X_AVM-DE_Homeauto:1#GetSpecificDeviceInfos" -d "<?xml version='1.0' encoding='utf-8'?><s:Envelope s:encodingStyle='http://schemas.xmlsoap.org/soap/encoding/' xmlns:s='http://schemas.xmlsoap.org/soap/envelope/'><s:Body><u:GetSpecificDeviceInfos xmlns:u='urn:dslforum-org:service:X_AVM-DE_Homeauto:1'><s:NewAIN>xxxxx xxxxxxx</s:NewAIN></u:GetSpecificDeviceInfos></s:Body></s:Envelope>" -s -k

        :param item: item to be updated (Supported item avm_data_types: aha_device, hkr_device)
        """

        url = self._build_url("/upnp/control/x_homeauto")
        headers = self._header.copy()

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'aha_device' or self.get_iattr_value(item.conf,
                                                                                                    'avm_data_type') == 'hkr_device':
            if not self.has_iattr(item.conf, 'ain'):
                self.logger.error(f"Cannot update AVM item {item} as AIN is not specified.")
                return
            ain = self.get_iattr_value(item.conf, 'ain')
            action = 'GetSpecificDeviceInfos'
            headers['SOAPACTION'] = f"{self._urn_map['Homeauto']}#{action}"
            soap_data = self._assemble_soap_data(action, self._urn_map['Homeauto'], {'NewAIN': ain.strip()})
        else:
            self.logger.error(
                f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin method (_update_home_automation)")
            return

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        if not xml:
            return

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'aha_device':
            element_xml = xml.getElementsByTagName('NewSwitchState')
            if len(element_xml) > 0:
                if element_xml[0].firstChild.data not in ['UNDEFINED', 'TOGGLE']:
                    item(element_xml[0].firstChild.data, self.get_shortname())
                elif element_xml[0].firstChild.data in 'TOGGLE':
                    value = item()
                    item(not value, self.get_shortname())
                else:
                    self.logger.error(
                        f'NewSwitchState für AHA Device has a non-supported value of {element_xml[0].firstChild.data}')
                for child in item.return_children():
                    value = None
                    if self.has_iattr(child.conf, 'avm_data_type'):
                        if self.get_iattr_value(child.conf, 'avm_data_type') == 'temperature':
                            temp = xml.getElementsByTagName('NewTemperatureCelsius')
                            if len(temp) > 0:
                                value = int(temp[0].firstChild.data) / 10
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'power':
                            power = xml.getElementsByTagName('NewMultimeterPower')
                            if len(power) > 0:
                                value = int(power[0].firstChild.data) / 100
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'energy':
                            energy = xml.getElementsByTagName('NewMultimeterEnergy')
                            if len(energy) > 0:
                                value = int(energy[0].firstChild.data)

                        if value:
                            child(value, self.get_shortname())
                        else:
                            self.logger.info(
                                f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")
            else:
                self.logger.error(
                    f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not available on the FritzDevice")

        # handling hkr devices (AVM dect 301)
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'hkr_device':
            self.logger.debug('handling hkr device')
            element_xml = xml.getElementsByTagName('NewHkrSetVentilStatus')
            if len(element_xml) > 0:
                # Decoding hrk valve state: open, closed or temp (temperature controlled)
                tempstring = element_xml[0].firstChild.data
                if tempstring == 'OPEN':
                    tempstate = 1
                elif tempstring == 'CLOSED':
                    tempstate = 0
                elif tempstring == 'TEMP':
                    tempstate = 2
                else:
                    tempstate = 3
                item(int(tempstate))
                for child in item.return_children():
                    value = None
                    if self.has_iattr(child.conf, 'avm_data_type'):
                        if self.get_iattr_value(child.conf, 'avm_data_type') == 'temperature':
                            is_temperature = xml.getElementsByTagName('NewTemperatureCelsius')
                            if len(is_temperature) > 0:
                                value = int(is_temperature[0].firstChild.data) / 10
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'set_temperature':
                            set_temperature = xml.getElementsByTagName('NewHkrSetTemperature')
                            if len(set_temperature) > 0:
                                value = int(set_temperature[0].firstChild.data) / 10
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'set_temperature_reduced':
                            set_temperature_reduced = xml.getElementsByTagName('NewHkrReduceTemperature')
                            if len(set_temperature_reduced) > 0:
                                value = int(set_temperature_reduced[0].firstChild.data) / 10
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'set_temperature_comfort':
                            set_temperature_comfort = xml.getElementsByTagName('NewHkrComfortTemperature')
                            if len(set_temperature_comfort) > 0:
                                value = int(set_temperature_comfort[0].firstChild.data) / 10
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'firmware_version':
                            firmware_version = xml.getElementsByTagName('NewFirmwareVersion')
                            if len(firmware_version) > 0:
                                value = str(firmware_version[0].firstChild.data)
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'manufacturer':
                            manufacturer = xml.getElementsByTagName('NewManufacturer')
                            if len(manufacturer) > 0:
                                value = str(manufacturer[0].firstChild.data)
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'product_name':
                            product_name = xml.getElementsByTagName('NewProductName')
                            if len(product_name) > 0:
                                value = str(product_name[0].firstChild.data)
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'device_name':
                            device_name = xml.getElementsByTagName('NewDeviceName')
                            if len(device_name) > 0:
                                value = str(device_name[0].firstChild.data)
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'connection_status':
                            connection_status = xml.getElementsByTagName('NewPresent')
                            if len(connection_status) > 0:
                                value = str(connection_status[0].firstChild.data)
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'device_id':
                            device_id = xml.getElementsByTagName('NewDeviceId')
                            if len(device_id) > 0:
                                value = str(device_id[0].firstChild.data)
                        elif self.get_iattr_value(child.conf, 'avm_data_type') == 'device_function':
                            device_function = xml.getElementsByTagName('NewFunctionBitMask')
                            if len(device_function) > 0:
                                value = str(device_function[0].firstChild.data)

                        if value:
                            child(value, self.get_shortname())
                        else:
                            self.logger.info(
                                f"Argument {self.get_iattr_value(child.conf, 'avm_data_type')} of Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not available on the FritzDevice with AIN {item.conf['ain'].strip()}.")
            else:
                self.logger.error(
                    f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not available on the FritzDevice with AIN {item.conf['ain'].strip()}.")

    def _get_url_prefix(self):
        """
        Choose the correct protocol prefix for the host.
        """

        if self._fritz_device.is_ssl():
            url_prefix = "https"
        else:
            url_prefix = "http"

        return url_prefix

    def _request(self, url, params=None):
        """
        Send a request with parameters.
        """

        try:
            rsp = self._session.get(url, params=params, timeout=self._timeout, verify=self._verify)
        except Exception as e:
            if self._fritz_device.is_available():
                self.logger.error(f"Exception when sending POST request for updating item towards the FritzDevice: {e}")
                self.set_device_availability(False)
        else:
            status_code = rsp.status_code
            if status_code == 200:
                if self.debug_log:
                    self.logger.debug("Sending HTTP request successful")
            elif status_code == 403:
                if self.debug_log:
                    self.logger.debug("HTTP access denied. Try to get new Session ID.")
                self._get_sid()
            else:
                self.logger.error(f"HTTP request error code: {status_code}")
                rsp.raise_for_status()
                if self.debug_log:
                    self.logger.debug(f"Url: {url}")
                    self.logger.debug(f"Params: {params}")

                if not self._fritz_device.is_available():
                    self.set_device_availability(True)

            return rsp.text.strip()

    def _aha_request(self, cmd, ain=None, param=None, rf=str):
        """
        Create an request for AHA-device get response

        :param cmd:     command to be sent
        :type cmd:      str
        :param ain:     ain of device
        :type ain:      str
        :param param:   params for request
        :type param:    dict
        :param rf:      type of returned value
        :type rf:       any
        :return:        response
        :type return:   any
        """

        url = f"{self._get_url_prefix()}://{self._fritz_device.get_host()}/webservices/homeautoswitch.lua"
        if self.debug_log:
            self.logger.debug(f"_aha_request: built request url: {url}")

        if not self.sid:
            self._get_sid()

        # Es wird angenommen, dass die SID noch gültig ist. Wenn nicht, wird bei Fehler 403 eine neue generiert.
        # Alternativ könnte man auch vor jedem Senden prüfen, dass die SID noch gültig ist.
        mySID = self.sid

        try:
            params = {"switchcmd": cmd, "sid": mySID}
            if param:
                params.update(param)
            if ain:
                params["ain"] = ain

            plain = self._request(url, params)
            if self.debug_log:
                self.logger.debug(f"Plain AHA request response is: {plain}")
                self.logger.debug(f"Params were: {params}")

            if plain == "inval":
                self.logger.error(f"Response of AHA request {cmd} was invalid")
                return None
            else:
                if rf == bool:
                    return bool(int(plain))
                return rf(plain)
        except Exception:
            pass

    def _get_aha_device_elements(self):
        """
        Get the DOM elements for the device list.
        """

        devices = None
        plain = self._aha_request("getdevicelistinfos")
        if plain is not None:
            try:
                dom = minidom.parseString(plain)
                devices = dom.getElementsByTagName('device')
            except Exception as e:
                self.logger.error(f'_get_aha_device_elements: error {e} during parsing')
        return devices

    def _update_aha_devices(self):
        """
        Update smarthome devices dict '_smarthome_devices' with DOM elements.
        """

        if self.debug_log:
            self.logger.debug("Updating AHA Devices ...")

        devices = self._get_aha_device_elements()
        if devices is not None:
            for element in devices:
                ain = element.getAttribute('identifier')
                if ain not in self._fritz_device.get_smarthome_devices().keys():
                    if self.debug_log:
                        self.logger.debug(f"Adding new Device with AIN {ain}")
                    self._fritz_device.get_smarthome_devices()[ain] = {}

                # general information of AVM smarthome device
                self._fritz_device.get_smarthome_devices()[ain]['device_id'] = element.getAttribute('id')
                self._fritz_device.get_smarthome_devices()[ain]['fw_version'] = element.getAttribute('fwversion')
                self._fritz_device.get_smarthome_devices()[ain]['product_name'] = element.getAttribute('productname')
                self._fritz_device.get_smarthome_devices()[ain]['manufacturer'] = element.getAttribute('manufacturer')

                # get functions of AVM smarthome device
                functions = []
                functionbitmask = int(element.getAttribute('functionbitmask'))
                functions.append('light') if bool(functionbitmask & (1 << 2) > 0) is True else None
                functions.append('alarm') if bool(functionbitmask & (1 << 4) > 0) is True else None
                functions.append('button') if bool(functionbitmask & (1 << 5) > 0) is True else None
                functions.append('thermostat') if bool(functionbitmask & (1 << 6) > 0) is True else None
                functions.append('powermeter') if bool(functionbitmask & (1 << 7) > 0) is True else None
                functions.append('temperature_sensor') if bool(functionbitmask & (1 << 8) > 0) is True else None
                functions.append('switch') if bool(functionbitmask & (1 << 9) > 0) is True else None
                functions.append('repeater') if bool(functionbitmask & (1 << 10) > 0) is True else None
                functions.append('mic') if bool(functionbitmask & (1 << 11) > 0) is True else None
                functions.append('han_fun') if bool(functionbitmask & (1 << 13) > 0) is True else None
                functions.append('on_off_device') if bool(functionbitmask & (1 << 15) > 0) is True else None
                functions.append('dimmable_device') if bool(functionbitmask & (1 << 16) > 0) is True else None
                functions.append('color_device') if bool(functionbitmask & (1 << 17) > 0) is True else None
                functions.append('blind') if bool(functionbitmask & (1 << 18) > 0) is True else None
                if self.debug_log:
                    self.logger.debug(f'Identified function of device with AIN {ain} are {functions}')

                self._fritz_device.get_smarthome_devices()[ain]['device_functions'] = functions

                # optional general information of AVM smarthome device
                try:
                    self._fritz_device.get_smarthome_devices()[ain]['batterylow'] = bool(
                        int(element.getElementsByTagName('batterylow')[0].firstChild.data))
                except Exception:
                    if self.debug_log:
                        self.logger.debug(
                            f'DECT Smarthome Device with AIN {ain} does not support Attribute {"batterylow"}.')
                try:
                    self._fritz_device.get_smarthome_devices()[ain]['battery_level'] = int(
                        element.getElementsByTagName('battery')[0].firstChild.data)
                except Exception:
                    if self.debug_log:
                        self.logger.debug(f'DECT Smarthome Device with AIN {ain} does not support Attribute "battery".')
                try:
                    self._fritz_device.get_smarthome_devices()[ain]['connected'] = bool(
                        int(element.getElementsByTagName('present')[0].firstChild.data))
                except Exception:
                    if self.debug_log:
                        self.logger.debug(f'DECT Smarthome Device with AIN {ain} does not support Attribute "present".')
                try:
                    self._fritz_device.get_smarthome_devices()[ain]['tx_busy'] = bool(
                        int(element.getElementsByTagName('txbusy')[0].firstChild.data))
                except Exception:
                    if self.debug_log:
                        self.logger.debug(f'DECT Smarthome Device with AIN {ain} does not support Attribute "txbusy".')
                try:
                    self._fritz_device.get_smarthome_devices()[ain]['device_name'] = str(
                        element.getElementsByTagName('name')[0].firstChild.data)
                except Exception:
                    if self.debug_log:
                        self.logger.debug(f'DECT Smarthome Device with AIN {ain} does not support Attribute "name".')

                # information of AVM smarthome device having thermostat
                if 'thermostat' in functions:
                    hkr = element.getElementsByTagName('hkr')
                    if len(hkr) > 0:
                        for child in hkr:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['current_temperature'] = (int(
                                    child.getElementsByTagName('tist')[0].firstChild.data) - 16) / 2 + 8
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['target_temperature'] = (int(
                                    child.getElementsByTagName('tsoll')[0].firstChild.data) - 16) / 2 + 8
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['temperature_comfort'] = (int(
                                    child.getElementsByTagName('komfort')[0].firstChild.data) - 16) / 2 + 8
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['temperature_reduced'] = (int(
                                    child.getElementsByTagName('absenk')[0].firstChild.data) - 16) / 2 + 8
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['battery_level'] = int(
                                    child.getElementsByTagName('battery')[0].firstChild.data)
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['battery_low'] = bool(
                                    int(child.getElementsByTagName('batterylow')[0].firstChild.data))
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['window_open'] = bool(
                                    int(child.getElementsByTagName('windowopenactiv')[0].firstChild.data))
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['summer_active'] = bool(
                                    int(child.getElementsByTagName('summeractive')[0].firstChild.data))
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['holiday_active'] = bool(
                                    int(child.getElementsByTagName('holidayactive')[0].firstChild.data))
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['hkr_boost'] = bool(
                                    int(child.getElementsByTagName('boostactive')[0].firstChild.data))
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['lock'] = bool(
                                    int(child.getElementsByTagName('lock')[0].firstChild.data))
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['device_lock'] = bool(
                                    int(child.getElementsByTagName('devicelock')[0].firstChild.data))
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['errorcode'] = int(
                                    child.getElementsByTagName('errorcode')[0].firstChild.data)
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['windowopenactiveendtime'] = int(
                                    child.getElementsByTagName('windowopenactiveendtime')[0].firstChild.data)
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['boostactiveendtime'] = int(
                                    child.getElementsByTagName('boostactiveendtime')[0].firstChild.data)
                            except AttributeError:
                                pass

                # information of AVM smarthome device having temperature sensor
                if 'temperature_sensor' in functions:
                    temperature_element = element.getElementsByTagName('temperature')
                    if len(temperature_element) > 0:
                        for child in temperature_element:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['current_temperature'] = int(
                                    child.getElementsByTagName('celsius')[0].firstChild.data) / 10
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['temperature_offset'] = int(
                                    child.getElementsByTagName('offset')[0].firstChild.data) / 10
                            except AttributeError:
                                pass

                    humidity_element = element.getElementsByTagName('humidity')
                    if len(humidity_element) > 0:
                        for child in humidity_element:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['humidity'] = int(
                                    child.getElementsByTagName('rel_humidity')[0].firstChild.data)
                            except AttributeError:
                                pass

                # information of AVM smarthome device having switch
                if 'switch' in functions:
                    switch = element.getElementsByTagName('switch')
                    if len(switch) > 0:
                        for child in switch:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['switch_state'] = bool(
                                    int(child.getElementsByTagName('state')[0].firstChild.data))
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['switch_mode'] = str(
                                    child.getElementsByTagName('mode')[0].firstChild.data)
                            except AttributeError:
                                pass

                # information of AVM smarthome device having powermeter
                if 'powermeter' in functions:
                    powermeter = element.getElementsByTagName('powermeter')
                    if len(powermeter) > 0:
                        for child in powermeter:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['power'] = int(
                                    child.getElementsByTagName('power')[0].firstChild.data) / 1000
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['energy'] = int(
                                    child.getElementsByTagName('energy')[0].firstChild.data) / 1000
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['voltage'] = int(
                                    child.getElementsByTagName('voltage')[0].firstChild.data) / 1000
                            except AttributeError:
                                pass

                # information of AVM smarthome device having button
                if 'button' in functions:
                    button_element = element.getElementsByTagName('button')
                    if len(button_element) > 0:
                        for child in button_element:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['lastpressedtimestamp'] = int(
                                    child.getElementsByTagName('lastpressedtimestamp')[0].firstChild.data)
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['identifier'] = str(
                                    child.getElementsByTagName('identifier')[0].firstChild.data)
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['id'] = str(
                                    child.getElementsByTagName('id')[0].firstChild.data)
                            except AttributeError:
                                pass

                # information of AVM smarthome device having alarm
                if 'alarm' in functions:
                    alarm_element = element.getElementsByTagName('alert')
                    if len(alarm_element) > 0:
                        for child in alarm_element:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['alarm'] = int(
                                    child.getElementsByTagName('state')[0].firstChild.data)
                            except AttributeError:
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['lastalertchgtimestamp'] = int(
                                    child.getElementsByTagName('lastalertchgtimestamp')[0].firstChild.data)
                            except AttributeError:
                                pass

                # information of AVM smarthome device having switch state
                if 'on_off_device' in functions:
                    simpleonoff_element = element.getElementsByTagName('simpleonoff')
                    if len(simpleonoff_element) > 0:
                        for child in simpleonoff_element:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['simpleonoff'] = int(
                                    child.getElementsByTagName('state')[0].firstChild.data)
                            except AttributeError:
                                # Set device state to 0 (off) if device is not connected (= no state available in xml)
                                self._fritz_device.get_smarthome_devices()[ain]['simpleonoff'] = 0
                                pass

                # information of AVM smarthome device having dimmer level information
                if 'dimmable_device' in functions:
                    levelcontrol_element = element.getElementsByTagName('levelcontrol')
                    if len(levelcontrol_element) > 0:
                        for child in levelcontrol_element:
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['level'] = int(
                                    child.getElementsByTagName('level')[0].firstChild.data)
                            except AttributeError:
                                # Set dimmer level to 0 (off) if device is not connected (= no state available in xml)
                                self._fritz_device.get_smarthome_devices()[ain]['level'] = 0
                                pass
                            else:
                                # Set Level to zero for consistency, if light is off:
                                try:
                                    onoff = self._fritz_device.get_smarthome_devices()[ain]['simpleonoff']
                                    if onoff == 0:
                                        self._fritz_device.get_smarthome_devices()[ain]['level'] = 0
                                        if self.debug_log:
                                            self.logger.debug(f"Debug: Level set to zero due to onoff state")
                                except AttributeError:
                                    pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['levelpercentage'] = int(
                                    child.getElementsByTagName('levelpercentage')[0].firstChild.data)
                            except AttributeError:
                                # Set dimmer level to 0 (off) if device is not connected (= no state available in xml)
                                self._fritz_device.get_smarthome_devices()[ain]['levelpercentage'] = 0
                                pass
                            else:
                                # Set Level to zero for consistency, if light is off:
                                try:
                                    onoff = self._fritz_device.get_smarthome_devices()[ain]['simpleonoff']
                                    if onoff == 0:
                                        self._fritz_device.get_smarthome_devices()[ain]['levelpercentage'] = 0
                                        if self.debug_log:
                                            self.logger.debug(f"Debug: Level set to zero due to onoff state")
                                except AttributeError:
                                    pass

                # information of AVM smarthome device having color information
                if 'color_device' in functions:
                    colorcontrol_element = element.getElementsByTagName('colorcontrol')
                    if len(colorcontrol_element) > 0:
                        for child in colorcontrol_element:
                            # Hue readout mode: currently not used
                            # try:
                            #    self._fritz_device.get_smarthome_devices()[ain]['current_mode'] = int(child.getAttribute('current_mode'))
                            #    self._fritz_device.get_smarthome_devices()[ain]['supported_modes'] = int(child.getAttribute('supported_modes'))
                            # except AttributeError:
                            #    self._fritz_device.get_smarthome_devices()[ain]['current_mode'] = 0
                            #    self._fritz_device.get_smarthome_devices()[ain]['supported_modes'] = 0
                            #    pass
                            # else:
                            #    self.logger.warning(f"Debug: HanFun current_mode: {self._fritz_device.get_smarthome_devices()[ain]['current_mode']}")
                            #    self.logger.warning(f"Debug: HanFun supported_modes: {self._fritz_device.get_smarthome_devices()[ain]['supported_modes']}")
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['hue'] = int(
                                    child.getElementsByTagName('hue')[0].firstChild.data)
                            except AttributeError:
                                self._fritz_device.get_smarthome_devices()[ain]['hue'] = 0
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['saturation'] = int(
                                    child.getElementsByTagName('saturation')[0].firstChild.data)
                            except AttributeError:
                                self._fritz_device.get_smarthome_devices()[ain]['saturation'] = 0
                                pass
                            try:
                                self._fritz_device.get_smarthome_devices()[ain]['colortemperature'] = int(
                                    child.getElementsByTagName('temperature')[0].firstChild.data)
                            except AttributeError:
                                self._fritz_device.get_smarthome_devices()[ain]['colortemperature'] = 0
                                pass
        else:
            self.logger.warning(f"Debug: _get_aha_device_elements returned no devices")

        # update items
        self._update_smarthome_items()

    def _update_smarthome_items(self):
        """
        Update smarthome item values using information from dict '_smarthome_devices'
        """

        for item in self._fritz_device.get_smarthome_items():
            # get AIN
            ain_device = self._get_item_ain(item)

            # get device sub-dict from dict
            device = self._fritz_device.get_smarthome_devices().get(ain_device, None)

            if device is not None:
                # get avm_data_type of item
                current_avm_data_type = self.get_iattr_value(item.conf, 'avm_data_type')
                # Attributes that are write only commands with no corresponding read commands are excluded from status updates via update black list:
                update_black_list = ['switch_toggle']

                if current_avm_data_type not in update_black_list:
                    # Remove "set_" prefix to set corresponding r/o or r/w item to returned value:
                    if current_avm_data_type.startswith('set_'):
                        current_avm_data_type = current_avm_data_type[len('set_'):]
                    # set item
                    if current_avm_data_type in device:
                        item(device[current_avm_data_type], self.get_shortname())
                    else:
                        self.logger.warning(
                            f'Attribute <{current_avm_data_type}> at device <{ain_device}> to be set to Item <{item}> is not available.')
            else:
                self.logger.warning(f'No values for item {item.id()} with AIN {ain_device} available.')

    def _get_aha_devices_as_dict(self):
        """
        Get the dict of all known devices.
        """

        if self._fritz_device.get_smarthome_devices() == {}:
            self._update_aha_devices()
        return self._fritz_device.get_smarthome_devices()

    def _get_aha_device_by_ain(self, ain):
        """
        Return a device specified by the AIN.
        """

        return self._get_aha_devices_as_dict()[ain]

    def get_devices(self):
        """
        Get the list of all known devices.
        """

        return list(self._get_aha_devices_as_dict().values())

    def get_device_present(self, ain):
        """
        Get the device presence.
        """

        return self._aha_request("getswitchpresent", ain=ain, rf=bool)

    def get_device_name(self, ain):
        """
        Get the device name.
        """

        return self._aha_request("getswitchname", ain=ain)

    def get_switch_state(self, ain):
        """
        Get the switch state.
        """

        return self._aha_request("getswitchstate", ain=ain, rf=bool)

    def set_switch_on(self, ain):
        """
        Set the switch to on state.
        """

        return self._aha_request("setswitchon", ain=ain, rf=bool)

    def set_switch_off(self, ain):
        """
        Set the switch to off state.
        """

        return self._aha_request("setswitchoff", ain=ain, rf=bool)

    def set_switch_toggle(self, ain):
        """
        Toggle the switch state.
        """

        return self._aha_request("setswitchtoggle", ain=ain, rf=bool)

    def get_switch_power(self, ain):
        """
        Get the switch power consumption.
        """

        return self._aha_request("getswitchpower", ain=ain, rf=int)

    def get_switch_energy(self, ain):
        """
        Get the switch energy.
        """

        return self._aha_request("getswitchenergy", ain=ain, rf=int)

    def set_switch_onoff(self, ain, on):
        """
        Set Led on/off.
        """
        return self._aha_request("setsimpleonoff", ain=ain, param={'onoff': int(on)}, rf=bool)

    def set_level(self, ain, level):
        """
        Set level 0-255.
        """

        if not 0 <= int(level) <= 255:
            self.logger.warning(
                f"Value for level={level} not in expected range of 0-255. Value will be limited to min/max.")

        # limit level it is out of range
        level = 0 if level < 0 else 255 if level > 255 else level

        return self._aha_request("setlevel", ain=ain, param={'level': int(level)}, rf=int)

    def set_level_percentage(self, ain, level):
        """
        Set level 0-100.
        """

        if not 0 <= int(level) <= 100:
            self.logger.warning(
                f"Value for level={level} not in expected range of 0%-100%. Value will be limited to min/max.")

        # limit level it is out of range
        level = 0 if level < 0 else 100 if level > 100 else level

        return self._aha_request("setlevelpercentage", ain=ain, param={'level': int(level)}, rf=int)

    def set_colortemperature(self, ain, colortemperature, duration=8):
        """
        Set Led to specific color temperature in Kelvin (2700K-6500K).
        """

        if not 2700 <= int(colortemperature) <= 6500:
            self.logger.warning(
                f"Value for colortemperature={colortemperature} not in expected range of 2700K-6500K. Value will be limited to min/max.")

        # limit colortemperature it is out of range
        colortemperature = 2700 if colortemperature < 2700 else 6500 if colortemperature > 6500 else colortemperature

        return self._aha_request("setcolortemperature", ain=ain,
                                 param={'temperature': int(colortemperature), 'duration': int(duration)}, rf=int)

    def set_color(self, ain, hue, saturation, duration=3):
        """
        Set Led color.
        """

        if not 0 <= int(hue) <= 359 and not 0 <= int(saturation) <= 255:
            self.logger.warning(
                f"Value for hue={hue} and/or saturation={saturation} not in expected range. Values will be limited to min/max.")

        # n = minn if n < minn else maxn if n > maxn else n

        # limit hue and saturation values if they are out of range
        hue = 0 if hue < 0 else 359 if hue > 359 else hue
        saturation = 0 if saturation < 0 else 255 if saturation > 255 else saturation

        return self._aha_request("setcolor", ain=ain,
                                 param={'hue': int(hue), 'saturation': int(saturation), 'duration': int(duration)},
                                 rf=bool)

    def get_temperature(self, ain):
        """
        Get the device temperature sensor value.
        """

        return self._aha_request("gettemperature", ain=ain, rf=float) / 10.0

    def _get_temperature(self, ain, name):
        """
        Get temperature with value correction
        """

        plain = self._aha_request(name, ain=ain, rf=float)
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
        elif temp > max(range(16, 56)):
            temp = 254

        self._aha_request("sethkrtsoll", ain=ain, param={'param': temp})

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

        plain = self._aha_request("getbasicdevicestats", ain=ain)
        return plain

    def set_hkr_boost(self, ain, endtimestamp):
        """
        Set HKR to boost mode.
        """
        self._aha_request("sethkrboost", ain=ain, param={'endtimestamp': endtimestamp})

    def set_hkr_windowopen(self, ain, endtimestamp):
        """
        Set HKR windowopen.
        """
        self._aha_request("sethkrwindowopen", ain=ain, param={'endtimestamp': endtimestamp})

    def set_name(self, ain, name):
        """
        Sets name of device
        """

        self._aha_request("setname", ain=ain, param={'name': name})

    def set_blind(self, ain, cmd):
        """
        Sets blind; Possible cmd „open“, "close“, „stop“
        """

        self._aha_request("setblind", ain=ain, param={'target:': cmd})

    def _get_item_ain(self, item):
        """
        Get AIN of device from item.conf
        """

        ain_device = None

        lookup_item = item
        for i in range(2):
            attribute = 'ain'
            attribute_w_instance = f"{attribute}@{self.get_instance_name()}"

            ain_device = self.get_iattr_value(lookup_item.conf, attribute)
            if ain_device is not None:
                break
            ain_device = self.get_iattr_value(lookup_item.conf, attribute_w_instance)
            if ain_device is not None:
                break
            else:
                lookup_item = lookup_item.return_parent()

        if ain_device:
            # deprecated warning for attribute 'ain'
            self.logger.warning(
                f"Item {item.id()} uses deprecated 'ain' attribute. Please consider to switch to 'avm_ain'.")
        else:
            lookup_item = item
            for i in range(2):
                attribute = 'avm_ain'
                attribute_w_instance = f"{attribute}@{self.get_instance_name()}"

                ain_device = self.get_iattr_value(lookup_item.conf, attribute_w_instance)
                if ain_device is not None:
                    break
                ain_device = self.get_iattr_value(lookup_item.conf, attribute)
                if ain_device is not None:
                    break
                else:
                    lookup_item = lookup_item.return_parent()

        if ain_device is None:
            self.logger.error('Device AIN is not defined or instance not given')
        return str(ain_device)

    def _get_wlan_index(self, item):
        """
        return wlan index for given item
        """

        wlan_index = None
        for i in range(2):
            attribute = 'avm_wlan_index'
            attribute_w_instance = f"{attribute}@{self.get_instance_name()}"

            wlan_index = self.get_iattr_value(item.conf, attribute)
            if wlan_index:
                break
            wlan_index = self.get_iattr_value(item.conf, attribute_w_instance)
            if wlan_index:
                break
            else:
                item = item.return_parent()

        if wlan_index is not None:
            wlan_index = int(wlan_index) - 1
            if not 0 <= wlan_index <= 2:
                wlan_index = None
                self.logger.warning(f"Attribute 'avm_wlan_index' for item {item.id()} not in valid range 1-3.")

        return wlan_index

    def _get_tam_index(self, item):
        """
        return tam index for given item
        """

        tam_index = None
        for i in range(2):
            attribute = 'avm_tam_index'
            attribute_w_instance = f"{attribute}@{self.get_instance_name()}"

            tam_index = self.get_iattr_value(item.conf, attribute)
            if tam_index:
                break
            tam_index = self.get_iattr_value(item.conf, attribute_w_instance)
            if tam_index:
                break
            else:
                item = item.return_parent()

        if tam_index is not None:
            tam_index = int(tam_index) - 1
            if not 0 <= tam_index <= 4:
                tam_index = None
                self.logger.warning(f"Attribute 'avm_tam_index' for item {item.id()} not in valid range 1-5.")

        return tam_index

    def _get_deflection_index(self, item):
        """
        return deflection index for given item
        """

        deflection_index = None
        for i in range(2):
            attribute = 'avm_deflection_index'
            attribute_w_instance = f"{attribute}@{self.get_instance_name()}"

            deflection_index = self.get_iattr_value(item.conf, attribute)
            if deflection_index:
                break
            deflection_index = self.get_iattr_value(item.conf, attribute_w_instance)
            if deflection_index:
                break
            else:
                item = item.return_parent()

        if deflection_index is not None:
            deflection_index = int(deflection_index) - 1
            if not 0 <= deflection_index <= 31:
                deflection_index = None
                self.logger.warning(f"Attribute 'avm_deflection_index' for item {item.id()} not in valid range 1-5.")

        return deflection_index

    def _get_mac(self, item):
        """
        return mac for given item
        """

        mac = None
        for i in range(2):
            attribute = 'avm_mac'
            attribute_w_instance = f"{attribute}@{self.get_instance_name()}"

            mac = self.get_iattr_value(item.conf, attribute)
            if mac:
                break
            mac = self.get_iattr_value(item.conf, attribute_w_instance)
            if mac:
                break
            else:
                item = item.return_parent()

        return mac

    def _update_fritz_device_info(self, item):
        """
        Updates FritzDevice specific information

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/deviceinfoSCPD.pdf
        CURL for testing:
        curl  --anyauth -u user:'password' 'https://192.168.178.1:49443/upnp/control/deviceinfo' -H 'Content-Type: text/xml; charset="utf-8"' -H 'SoapAction: urn:dslforum-org:service:DeviceInfo:1#GetInfo' -d '<?xml version="1.0" encoding="utf-8"?> <s:Envelope s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/" xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"> <s:Body> <u:GetInfo xmlns:u="urn:dslforum-org:service:DeviceInfo:1"> </u:GetInfo> </s:Body> </s:Envelope>' -s -k

        :param item: Item to be updated (Supported item avm_data_types: uptime, software_version, hardware_version,serial_number, description)
        """

        url = self._build_url("/upnp/control/deviceinfo")
        headers = self._header.copy()

        if self.get_iattr_value(item.conf, 'avm_data_type') in ['uptime', 'software_version', 'hardware_version',
                                                                'serial_number']:
            action = 'GetInfo'
        else:
            self.logger.error(f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin")
            return

        headers['SOAPACTION'] = f"{self._urn_map['DeviceInfo']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['DeviceInfo'])

        if f"dev_info_{action}" not in self._response_cache:
            response = self._get_post_request(url, soap_data, headers)
            if response is not None:
                self._response_cache[f"dev_info_{action}"] = response.content
            else:
                return

        else:
            if self.debug_log:
                self.logger.debug(
                    f"Accessing dev_info response cache for action {action} and item {item.property.path}!")

        try:
            xml = minidom.parseString(self._response_cache[f"dev_info_{action}"])
        except Exception as e:
            self.logger.error(f"Exception when parsing response: {e}")
            return

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'uptime':
            element_xml = xml.getElementsByTagName('NewUpTime')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'software_version':
            element_xml = xml.getElementsByTagName('NewSoftwareVersion')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'hardware_version':
            element_xml = xml.getElementsByTagName('NewHardwareVersion')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'serial_number':
            element_xml = xml.getElementsByTagName('NewSerialNumber')
        else:
            element_xml = None

        if len(element_xml) > 0:
            item(element_xml[0].firstChild.data, self.get_shortname())
        else:
            self.logger.info(
                f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")

    def _update_tam(self, item):
        """
        Updates telephone answering machine (TAM) related information

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_tam.pdf

        :param item: item to be updated (Supported item avm_data_types: tam, child item avm_data_types: tam_name)
        """

        url = self._build_url("/upnp/control/x_tam")

        if self.get_iattr_value(item.conf, 'avm_data_type') in ['tam', 'tam_name']:
            action = 'GetInfo'
        elif self.get_iattr_value(item.conf, 'avm_data_type') in ['tam_new_message_number', 'tam_total_message_number']:
            action = 'GetMessageList'
        else:
            self.logger.error(f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin")
            return

        tam_index = self._get_tam_index(item)
        if not tam_index:
            return

        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['TAM']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['TAM'], {'NewIndex': tam_index})

        if f"tam_{action}" not in self._response_cache:
            response = self._get_post_request(url, soap_data, headers)
            if response is not None:
                self._response_cache[f"tam_{action}"] = response.content
        else:
            if self.debug_log:
                self.logger.debug(f"Accessing TAM response cache for action {action} and item {item.property.path}!")

        try:
            xml = minidom.parseString(self._response_cache[f"tam_{action}"])
        except Exception as e:
            self.logger.error(f"Exception when parsing response: {e}")
            return

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'tam':
            element_xml = xml.getElementsByTagName('NewEnable')
            if len(element_xml) > 0:
                item(element_xml[0].firstChild.data, self.get_shortname())
            else:
                self.logger.error(
                    f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not available on the FritzDevice")
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'tam_name':
            element_xml = xml.getElementsByTagName('NewName')
            if len(element_xml) > 0:
                item(element_xml[0].firstChild.data, self.get_shortname())
            else:
                self.logger.error(
                    f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not available on the FritzDevice")
        elif self.get_iattr_value(item.conf, 'avm_data_type') in ['tam_new_message_number', 'tam_total_message_number']:
            message_url_xml = xml.getElementsByTagName('NewURL')
            if len(message_url_xml) > 0:
                message_url = message_url_xml[0].firstChild.data

                if "tam_messages" not in self._response_cache:
                    try:
                        message_result = self._session.get(message_url, timeout=self._timeout, verify=self._verify)
                    except Exception as e:
                        if self._fritz_device.is_available():
                            self.logger.error(f"Exception when sending GET request: {e}")
                            self.set_device_availability(False)
                        return
                    if not self._fritz_device.is_available():
                        self.set_device_availability(True)
                    self._response_cache["tam_messages"] = message_result.content
                else:
                    if self.debug_log:
                        self.logger.debug(
                            f"Accessing tam_messages response cache for action {action} and item {item.property.path}!")

                try:
                    message_xml = minidom.parseString(self._response_cache["tam_messages"])
                except Exception as e:
                    self.logger.error(f"Exception when parsing response: {e}")
                    return

                messages = message_xml.getElementsByTagName('Message')
                message_count = 0
                if len(messages) > 0:
                    if self.get_iattr_value(item.conf, 'avm_data_type') == 'tam_total_message_number':
                        message_count = len(messages)
                    elif self.get_iattr_value(item.conf, 'avm_data_type') == 'tam_new_message_number':
                        for message in messages:
                            is_new = message.getElementsByTagName('New')
                            if int(is_new[0].firstChild.data) == 1:
                                message_count = message_count + 1
                item(message_count, self.get_shortname())
            else:
                self.logger.error(
                    f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not available on the FritzDevice")

    def _update_wlan_config(self, item):
        """
        Updates wlan related information, all items of this method need an numeric avm_wlan_index (typically 1-3)

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wlanconfigSCPD.pdf

        :param item: item to be updated (Supported item avm_data_types: wlanconfig, wlan_guest_time_remaining
        """

        url = None
        wlan_index = self.get_iattr_value(item.conf, 'avm_wlan_index')

        if wlan_index:
            url = self._build_url(f"/upnp/control/wlanconfig{wlan_index}")
        else:
            self.logger.error(f'No or incorrect avm_wlan_index attribute provided for {item}')
        if not url:
            return

        if self.get_iattr_value(item.conf, 'avm_data_type') in ['wlanconfig', 'wlanconfig_ssid']:
            action = 'GetInfo'
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wlan_guest_time_remaining':
            action = 'X_AVM-DE_GetWLANExtInfo'
        else:
            self.logger.error(f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin")
            return

        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['WLANConfiguration']}"[:43] + f"{wlan_index}#{action}"
        soap_data = self._assemble_soap_data(action, f"{self._urn_map['WLANConfiguration']}"[:43] + f"{wlan_index}")

        if f"wlanconfig_{wlan_index}_{action}" not in self._response_cache and url:
            response = self._get_post_request(url, soap_data, headers)
            if response is not None:
                self._response_cache[f"wlanconfig_{wlan_index}_{action}"] = response.content
        else:
            if self.debug_log:
                self.logger.debug(
                    f"Accessing wlanconfig response cache for action {action} and item {item.property.path}!")

        try:
            xml = minidom.parseString(self._response_cache[f"wlanconfig_{wlan_index}_{action}"])
        except Exception as e:
            self.logger.error(f"Exception when parsing response: {e}")
            return

        data = None
        if self.get_iattr_value(item.conf, 'avm_data_type') == 'wlanconfig':
            data = self._get_value_from_xml_node(xml, 'NewEnable')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wlanconfig_ssid':
            data = self._get_value_from_xml_node(xml, 'NewSSID')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wlan_guest_time_remaining':
            data = self._get_value_from_xml_node(xml, 'NewX_AVM-DE_TimeRemain')
            try:
                data = int(data)
            except Exception:
                pass

            # element_xml = xml.getElementsByTagName('NewX_AVM-DE_TimeRemain')
            # if len(element_xml) > 0:
            #     data = int(element_xml[0].firstChild.data)

        if data is not None:
            item(data, self.get_shortname())
        else:
            self.logger.info(
                f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")

    def _update_wan_dsl_interface_config(self, item):
        """
        Updates wide area network (WAN) speed related information

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wandslifconfigSCPD.pdf

        :param item: item to be updated (Supported item avm_data_types: wan_upstream, wan_downstream)
        """

        if self.get_iattr_value(item.conf, 'avm_data_type') in ['wan_upstream', 'wan_downstream']:
            action = 'GetInfo'
        else:
            self.logger.error(f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin")
            return

        url = self._build_url("/upnp/control/wandslifconfig1")

        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['WANDSLInterfaceConfig']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['WANDSLInterfaceConfig'])

        # if action has not been called in a cycle so far, request it and cache response
        if f"wan_dsl_interface_config_{action}" not in self._response_cache:
            response = self._get_post_request(url, soap_data, headers)
            if response is not None:
                self._response_cache[f"wan_dsl_interface_config_{action}"] = response.content
        else:
            if self.debug_log:
                self.logger.debug(
                    f"Accessing wan_dsl_interface_config response cache for action {action} and item {item.property.path}!")

        try:
            xml = minidom.parseString(self._response_cache[f"wan_dsl_interface_config_{action}"])
        except Exception as e:
            self.logger.error(f"Exception when parsing response: {e}")
            return

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_upstream':
            element_xml = xml.getElementsByTagName('NewUpstreamCurrRate')

        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_downstream':
            element_xml = xml.getElementsByTagName('NewDownstreamCurrRate')
        else:
            element_xml = None

        if element_xml is not None and len(element_xml) > 0:
            item(int(element_xml[0].firstChild.data), self.get_shortname())
        else:
            self.logger.info(
                f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")

    def _update_wan_common_interface_configuration(self, item):
        """
        Updates wide area network (WAN) related information

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wancommonifconfigSCPD.pdf
              https://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/IGD1.pdf

        :param item: item to be updated (Supported item avm_data_types: wan_total_packets_sent, wan_total_packets_received, wan_current_packets_sent, wan_current_packets_received, wan_total_bytes_sent, wan_total_bytes_received, wan_current_bytes_sent, wan_current_bytes_received, wan_link)
        """

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_total_packets_sent':
            action = 'GetTotalPacketsSent'
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_total_packets_received':
            action = 'GetTotalPacketsReceived'
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_total_bytes_sent':
            action = 'GetTotalBytesSent'
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_total_bytes_received':
            action = 'GetTotalBytesReceived'
        elif self.get_iattr_value(item.conf, 'avm_data_type') in ['wan_current_packets_sent',
                                                                  'wan_current_packets_received',
                                                                  'wan_current_bytes_sent',
                                                                  'wan_current_bytes_received']:
            action = 'GetAddonInfos'
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_link':
            action = 'GetCommonLinkProperties'
        else:
            self.logger.error(f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin")
            return

        headers = self._header.copy()
        if action != 'GetAddonInfos':
            headers['SOAPACTION'] = f"{self._urn_map['WANCommonInterfaceConfig']}#{action}"
            soap_data = self._assemble_soap_data(action, self._urn_map['WANCommonInterfaceConfig'])
            url = self._build_url("/upnp/control/wancommonifconfig1")
        else:
            headers['SOAPACTION'] = f"{self._urn_map['WANCommonInterfaceConfig_alt']}#{action}"
            soap_data = self._assemble_soap_data(action, self._urn_map['WANCommonInterfaceConfig_alt'])
            url = self._build_url("/igdupnp/control/WANCommonIFC1")
        # if action has not been called in a cycle so far, request it and cache response
        if f"wan_common_interface_configuration_{action}" not in self._response_cache:
            response = self._get_post_request(url, soap_data, headers)
            if response is not None:
                self._response_cache[f"wan_common_interface_configuration_{action}"] = response.content
        else:
            if self.debug_log:
                self.logger.debug(
                    f"Accessing wan_common_interface_configuration response cache for action {action} and item {item.property.path}!")

        try:
            xml = minidom.parseString(self._response_cache[f"wan_common_interface_configuration_{action}"])
        except Exception as e:
            self.logger.error(f"Exception when parsing response: {e}")
            return

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_total_packets_sent':
            data = self._get_value_from_xml_node(xml, 'NewTotalPacketsSent')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_total_packets_received':
            data = self._get_value_from_xml_node(xml, 'NewTotalPacketsReceived')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_current_packets_sent':
            data = self._get_value_from_xml_node(xml, 'NewPacketSendRate')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_current_packets_received':
            data = self._get_value_from_xml_node(xml, 'NewPacketReceiveRate')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_total_bytes_sent':
            data = self._get_value_from_xml_node(xml, 'NewTotalBytesSent')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_total_bytes_received':
            data = self._get_value_from_xml_node(xml, 'NewTotalBytesReceived')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_current_bytes_sent':
            data = self._get_value_from_xml_node(xml, 'NewByteSendRate')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_current_bytes_received':
            data = self._get_value_from_xml_node(xml, 'NewByteReceiveRate')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_link':
            data = self._get_value_from_xml_node(xml, 'NewPhysicalLinkStatus')
            data = True if data == 'Up' else False
        else:
            data = None

        if isinstance(data, str) and data.isdigit():
            data = int(data)

        if data is not None:
            item(data, self.get_shortname())
        else:
            self.logger.info(
                f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")

    def _update_wan_ip_connection(self, item):
        """
        Updates wide area network (WAN) IP related information

        Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/wanipconnSCPD.pdf

        :param item: item to be updated (Supported item avm_data_types: wan_connection_status, wan_is_connected, wan_uptime, wan_ip)
        """

        url = self._build_url("/igdupnp/control/WANIPConn1")

        if self.get_iattr_value(item.conf, 'avm_data_type') in ['wan_connection_status', 'wan_is_connected',
                                                                'wan_uptime', 'wan_connection_error']:
            action = 'GetStatusInfo'
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_ip':
            action = 'GetExternalIPAddress'
        else:
            self.logger.error(f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not supported by plugin")
            return

        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['WANIPConnection']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['WANIPConnection'])

        # if action has not been called in a cycle so far, request it and cache response
        if f"wan_ip_connection_{action}" not in self._response_cache:
            response = self._get_post_request(url, soap_data, headers)
            if response is not None:
                self._response_cache[f"wan_ip_connection_{action}"] = response.content
        else:
            if self.debug_log:
                self.logger.debug(
                    f"Accessing wan_ip_connection response cache for action {action} and item {item.property.path}!")

        try:
            xml = minidom.parseString(self._response_cache[f"wan_ip_connection_{action}"])
        except Exception as e:
            self.logger.error(f"Exception when parsing response: {e}")
            return

        if self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_connection_status':
            data = self._get_value_from_xml_node(xml, 'NewConnectionStatus')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_is_connected':
            data = True if self._get_value_from_xml_node(xml, 'NewConnectionStatus') == 'Connected' else False
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_uptime':
            data = self._get_value_from_xml_node(xml, 'NewUptime')
            if isinstance(data, str) and data.isdigit():
                data = int(data)
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_connection_error':
            data = self._get_value_from_xml_node(xml, 'NewLastConnectionError')
        elif self.get_iattr_value(item.conf, 'avm_data_type') == 'wan_ip':
            data = self._get_value_from_xml_node(xml, 'NewExternalIPAddress')
        else:
            data = None

        if data is not None:
            item(data, self.get_shortname())
        else:
            self.logger.info(
                f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")

    @staticmethod
    def _get_value_from_xml_node(node, tag_name):
        """
        Returns value of tag_name from given xml-node
        """

        data = None
        xml = node.getElementsByTagName(tag_name)
        if len(xml) > 0:
            if not xml[0].firstChild is None:
                data = xml[0].firstChild.data
        return data

    def get_number_of_deflections(self):
        """
        Get the number of deflection entrys
        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf
        :return: number of deflections
        """

        url = self._build_url("/upnp/control/x_contact")
        action = "GetNumberOfDeflections"
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['OnTel']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'])

        xml = self._get_post_request_as_xml(url, soap_data, headers)
        data = self._get_value_from_xml_node(xml, 'NewNumberOfDeflections')
        return data

    def _update_number_of_deflections(self, item):
        """
        Updates the number of acitve deflections
        """

        result = self.get_number_of_deflections()
        if result is not None:
            item(result, self.get_shortname())
        else:
            self.logger.info(
                f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")

    def get_deflection(self, deflection_id=0):
        """
        Get the parameter for a deflection entry.
        DeflectionID is in the range of 0 .. NumberOfDeflections-1.
        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf
        :param: deflection_id (default: 0)
        :return: dict with all deflection details of deflection_id
        """

        url = self._build_url("/upnp/control/x_contact")
        action = "GetDeflection"
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['OnTel']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'], {'NewDeflectionId': deflection_id})

        xml = self._get_post_request_as_xml(url, soap_data, headers)

        deflection = dict()
        deflection[deflection_id] = dict()

        attributes = ['NewEnable', 'NewType', 'NewNumber', 'NewDeflectionToNumber', 'NewMode', 'NewOutgoing',
                      'NewPhonebookID']
        for attribute in attributes:
            data = self._get_value_from_xml_node(xml, attribute)
            if data:
                attribute = attribute[3:]
                deflection[deflection_id][attribute] = data
        return deflection

    def _update_deflection(self, item):
        """
        Updates Item value for deflection
        """

        deflection_index = self._get_deflection_index(item)
        if deflection_index:
            result = self.get_deflection(deflection_index)
            if result is not None:
                item(result, self.get_shortname())
            else:
                self.logger.info(
                    f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")
        else:
            self.logger.error('Deflection Index not given or incorrect in Item Config')

    def _update_deflection_status(self, item):
        """
        Updates Item value for deflection status
        """

        deflection_index = self._get_deflection_index(item)
        if deflection_index:
            deflection = self.get_deflection(deflection_index)
            if deflection is not None:
                status = bool(int(deflection[deflection_index]['Enable']))
                item(status, self.get_shortname())
            else:
                self.logger.info(
                    f"Request of attribute {self.get_iattr_value(item.conf, 'avm_data_type')} returned None. Seems that data are not available/supported.")
        else:
            self.logger.error('Deflection Index not given or incorrect in Item Config')

    def get_deflections(self):
        """
        Returns a list of deflecttions
        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf
        :return: dict with all deflection details
        """

        url = self._build_url("/upnp/control/x_contact")
        action = "GetDeflections"
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['OnTel']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'])

        if f"deflections{action}" not in self._response_cache:
            response = self._get_post_request(url, soap_data, headers)
            if response is not None:
                self._response_cache[f"deflections{action}"] = response.content
        else:
            if self.debug_log:
                self.logger.debug(f'Accessing dev_info response cache for action {action}')

        try:
            xml = minidom.parseString(self._response_cache[f"deflections{action}"])
        except Exception as e:
            self.logger.error(f"Exception when parsing response: {e}")
            return

        deflection_list_xml = minidom.parseString(xml.getElementsByTagName('NewDeflectionList')[0].firstChild.data)
        item_list = deflection_list_xml.getElementsByTagName('Item')

        deflections = {}
        if len(item_list) > 0:
            for item in item_list:
                deflection_id = int(item.getElementsByTagName('DeflectionId')[0].firstChild.data)
                deflections[deflection_id] = {'Enable': '', 'Type': '', 'Number': '', 'DeflectionToNumber': '',
                                              'Mode': '', 'Outgoing': '', 'PhonebookID': ''}

                for attribute in deflections[deflection_id]:
                    attribute_value = item.getElementsByTagName(attribute)
                    if len(attribute_value) > 0:
                        if attribute_value[0].hasChildNodes():
                            deflections[deflection_id][attribute] = attribute_value[0].firstChild.data
        return deflections

    def _update_deflections(self, item):
        """
        Updates Item value for deflections
        """

        result = self.get_deflections()
        if result is not None and dict:
            if self.get_iattr_value(item.conf, 'avm_data_type') == 'deflections_details':
                item(result, self.get_shortname())
            else:
                # Get deflection index from item or parent item
                deflection_index = self._get_deflection_index(item)

                # Set Item values
                if deflection_index is not None:
                    if self.get_iattr_value(item.conf, 'avm_data_type') == 'deflection_enable':
                        item(result[deflection_index]['Enable'], self.get_shortname())
                    elif self.get_iattr_value(item.conf, 'avm_data_type') == 'deflection_type':
                        item(result[deflection_index]['Type'], self.get_shortname())
                    elif self.get_iattr_value(item.conf, 'avm_data_type') == 'deflection_number':
                        item(result[deflection_index]['Number'], self.get_shortname())
                    elif self.get_iattr_value(item.conf, 'avm_data_type') == 'deflection_to_number':
                        item(result[deflection_index]['DeflectionToNumber'], self.get_shortname())
                    elif self.get_iattr_value(item.conf, 'avm_data_type') == 'deflection_mode':
                        item(result[deflection_index]['Mode'], self.get_shortname())
                    elif self.get_iattr_value(item.conf, 'avm_data_type') == 'deflection_outgoing':
                        item(result[deflection_index]['Outgoing'], self.get_shortname())
                    elif self.get_iattr_value(item.conf, 'avm_data_type') == 'deflection_phonebook_id':
                        item(result[deflection_index]['PhonebookID'], self.get_shortname())
                    else:
                        self.logger.error(
                            f"Attribute {self.get_iattr_value(item.conf, 'avm_data_type')} not available on the FritzDevice")
                else:
                    self.logger.error(f"Deflection Index for {item} not defined")

    def set_deflection(self, deflection_id=0, new_enable=False):
        """
        Enable or disable a deflection.
        DeflectionID is in the range of 0 .. NumberOfDeflections-1
        | Uses: http://avm.de/fileadmin/user_upload/Global/Service/Schnittstellen/x_contactSCPD.pdf
        :param deflection_id: deflection id (default: 0)
        :param new_enable: new enable (default: False)
        """

        url = self._build_url("/upnp/control/x_contact")
        action = "SetDeflectionEnable"
        headers = self._header.copy()
        headers['SOAPACTION'] = f"{self._urn_map['OnTel']}#{action}"
        soap_data = self._assemble_soap_data(action, self._urn_map['OnTel'],
                                             {'NewDeflectionId': deflection_id, 'NewEnable': int(new_enable)})

        self._get_post_request_as_xml(url, soap_data, headers)

        # read deflection after setting
        self._update_loop()
