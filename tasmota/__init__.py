#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
#  Copyright 2021-      Michael Wenzel              wenzel_michael@web.de
#########################################################################
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

from datetime import datetime, timedelta

from lib.model.mqttplugin import *
from .webif import WebInterface


class Tasmota(MqttPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides the update functions for the items
    """

    PLUGIN_VERSION = '1.4.0'

    LIGHT_MSG = ['HSBColor', 'Dimmer', 'Color', 'CT', 'Scheme', 'Fade', 'Speed', 'LedTable', 'White']

    RF_MSG = ['RfSync', 'RfLow', 'RfHigh', 'RfCode']

    ZIGBEE_BRIDGE_DEFAULT_OPTIONS = {'SetOption89':  'OFF',
                                     'SetOption101': 'OFF',
                                     'SetOption120': 'OFF',
                                     'SetOption83':  'ON',
                                     'SetOption112': 'OFF',
                                     'SetOption110': 'OFF',
                                     'SetOption119': 'OFF',
                                     'SetOption118': 'OFF',
                                     'SetOption125': 'ON',
                                     }
    TASMOTA_ATTR_R_W = ['relay', 'hsb', 'white', 'ct', 'rf_send', 'rf_key_send', 'zb_permit_join', 'zb_forget', 'zb_ping', 'rf_key']

    TASMOTA_ZB_ATTR_R_W = ['power', 'hue', 'sat', 'ct', 'dimmer', 'ct_k']

    ENERGY_SENSOR_KEYS = {'Voltage':        'item_voltage',
                          'Current':        'item_current',
                          'Power':          'item_power',
                          'ApparentPower':  'item_apparent_power',
                          'ReactivePower':  'item_reactive_power',
                          'Factor':         'item_power_factor',
                          'TotalStartTime': 'item_total_starttime',
                          'Total':          'item_power_total',
                          'Yesterday':      'item_power_yesterday',
                          'Today':          'item_power_today'}

    ENV_SENSOR = ['DS18B20', 'AM2301', 'SHT3X', 'BMP280', 'DHT11']

    ENV_SENSOR_KEYS = {'Temperature': 'item_temp',
                       'Humidity':    'item_hum',
                       'DewPoint':    'item_dewpoint',
                       'Pressure':    'item_pressure',
                       'Id':          'item_1wid'}

    ANALOG_SENSOR_KEYS = {'Temperature':  'item_analog_temp',
                          'Temperature1': 'item_analog_temp1',
                          'A0':           'item_analog_a0',
                          'Range':        'item_analog_range'}

    ESP32_SENSOR_KEYS = {'Temperature': 'item_esp32_temp'}

    SENSORS = [*ENV_SENSOR,
               'ENERGY',
               ]

    def __init__(self, sh):
        """
        Initializes the plugin.
        """

        # Call init code of parent class (MqttPlugin)
        super().__init__()
        if not self._init_complete:
            return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.telemetry_period = self.get_parameter_value('telemetry_period')
        self.full_topic = self.get_parameter_value('full_topic').lower()

        # crate full_topic
        if self.full_topic.find('%prefix%') == -1 or self.full_topic.find('%topic%') == -1:
            self.full_topic = '%prefix%/%topic%/'
        if self.full_topic[-1] != '/':
            self.full_topic += '/'

        # Define properties
        self.tasmota_devices = {}                   # to hold tasmota device information for web interface
        self.tasmota_zigbee_devices = {}            # to hold tasmota zigbee device information for web interface
        self.tasmota_items = []                     # to hold item information for web interface
        self.topics_of_retained_messages = []       # to hold all topics of retained messages

        self.alive = None

        # Add subscription to get device discovery
        self.add_subscription(        'tasmota/discovery/#',  'dict',                                    callback=self.on_mqtt_discovery_message)
        # Add subscription to get device LWT
        self.add_tasmota_subscription('tele', '+', 'LWT',     'bool', bool_values=['Offline', 'Online'], callback=self.on_mqtt_lwt_message)
        # Add subscription to get device status
        self.add_tasmota_subscription('stat', '+', 'STATUS0', 'dict',                                    callback=self.on_mqtt_status0_message)
        # Add subscription to get device actions result
        self.add_tasmota_subscription('stat', '+', 'RESULT',  'dict',                                    callback=self.on_mqtt_message)

        # Init WebIF
        self.init_webinterface(WebInterface)
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        # start subscription to all defined topics
        self.start_subscriptions()

        self.logger.debug(f"Scheduler: 'check_online_status' created")
        dt = self.shtime.now() + timedelta(seconds=(self.telemetry_period - 3))
        self.scheduler_add('check_online_status', self.check_online_status, cycle=self.telemetry_period, next=dt)

        self.logger.debug(f"Scheduler: 'add_tasmota_subscriptions' created")
        self.scheduler_add('add_tasmota_subscriptions', self.add_tasmota_subscriptions, cron='init+20')

        self.alive = True

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.logger.debug("Stop method called")
        self.scheduler_remove('check_online_status')

        # stop subscription to all topics
        self.stop_subscriptions()

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

        if self.has_iattr(item.conf, 'tasmota_topic'):
            tasmota_topic = self.get_iattr_value(item.conf, 'tasmota_topic')
            self.logger.info(f"parsing item: {item.id()} with tasmota_topic={tasmota_topic}")

            tasmota_attr = self.get_iattr_value(item.conf, 'tasmota_attr')
            tasmota_relay = self.get_iattr_value(item.conf, 'tasmota_relay')
            tasmota_rf_details = self.get_iattr_value(item.conf, 'tasmota_rf_key')
            tasmota_zb_device = self.get_iattr_value(item.conf, 'tasmota_zb_device')
            tasmota_zb_group = self.get_iattr_value(item.conf, 'tasmota_zb_group')
            tasmota_zb_attr = self.get_iattr_value(item.conf, 'tasmota_zb_attr')
            tasmota_zb_attr = tasmota_zb_attr.lower() if tasmota_zb_attr else None
            tasmota_sml_device = self.get_iattr_value(item.conf, 'tasmota_sml_device')
            tasmota_sml_attr = self.get_iattr_value(item.conf, 'tasmota_sml_attr')
            tasmota_sml_attr = tasmota_sml_attr.lower() if tasmota_sml_attr else None

            # handle tasmota devices without zigbee
            if tasmota_attr:
                self.logger.info(f"Item={item.id()} identified for Tasmota with tasmota_attr={tasmota_attr}")
                tasmota_attr = tasmota_attr.lower()
                tasmota_relay = 1 if not tasmota_relay else tasmota_relay

                if tasmota_rf_details and '=' in tasmota_rf_details:
                    tasmota_rf_details, tasmota_rf_key_param = tasmota_rf_details.split('=')

            # handle tasmota zigbee devices
            elif tasmota_zb_device and tasmota_zb_attr:
                self.logger.info(f"Item={item.id()} identified for Tasmota Zigbee with tasmota_zb_device={tasmota_zb_device} and tasmota_zb_attr={tasmota_zb_attr}")

                # check if zigbee device short name has been used without parentheses; if so this will be normally parsed to a number and therefore mismatch with definition
                try:
                    tasmota_zb_device = int(tasmota_zb_device)
                    self.logger.warning(f"Probably for item {item.id()} the device short name as been used for attribute 'tasmota_zb_device'. Trying to make that work but it will cause exceptions. To prevent this, the short name need to be defined as string by using parentheses")
                    tasmota_zb_device = str(hex(tasmota_zb_device))
                    tasmota_zb_device = tasmota_zb_device[0:2] + tasmota_zb_device[2:len(tasmota_zb_device)].upper()
                except Exception:
                    pass

            # handle tasmota zigbee groups
            elif tasmota_zb_group and tasmota_zb_attr:
                self.logger.info(f"Item={item.id()} identified for Tasmota Zigbee with tasmota_zb_group={tasmota_zb_group} and tasmota_zb_attr={tasmota_zb_attr}")

            # handle tasmota smartmeter devices
            elif tasmota_sml_device and tasmota_sml_attr:
                self.logger.info(f"Item={item.id()} identified for Tasmota SML with tasmota_sml_device={tasmota_sml_device} and tasmota_sml_attr={tasmota_sml_attr}")

            # handle everything else
            else:
                self.logger.info(f"Definition of attributes for item={item.id()} incomplete. Item will be ignored.")
                return

            # setup dict for new device
            if not self.tasmota_devices.get(tasmota_topic):
                self._add_new_device_to_tasmota_devices(tasmota_topic)
                self.tasmota_devices[tasmota_topic]['status'] = 'item.conf'

            # fill tasmota_device dict
            self.tasmota_devices[tasmota_topic]['connected_to_item'] = True
            if tasmota_attr == 'relay' and tasmota_relay:
                item_type = f'item_{tasmota_attr}{tasmota_relay}'
            elif tasmota_attr == 'rf_key' and tasmota_rf_details:
                item_type = f'item_{tasmota_attr}{tasmota_rf_details}'
            elif tasmota_zb_device and tasmota_zb_attr:
                item_type = f'item_{tasmota_zb_device}.{tasmota_zb_attr}'
            elif tasmota_sml_device and tasmota_sml_attr:
                item_type = f'item_{tasmota_sml_device}.{tasmota_sml_attr}'
            else:
                item_type = f'item_{tasmota_attr}'
            self.tasmota_devices[tasmota_topic]['connected_items'][item_type] = item

            # append to list used for web interface
            if item not in self.tasmota_items:
                self.tasmota_items.append(item)

            return self.update_item

        elif self.has_iattr(item.conf, 'tasmota_admin'):
            self.logger.debug(f"parsing item: {item.id()} for tasmota admin attribute")

            return self.update_item

    def update_item(self, item, caller: str = None, source: str = None, dest: str = None):
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
            # code to execute if the plugin is not stopped  AND only, if the item has not been changed by this plugin:

            # get tasmota attributes of item
            tasmota_admin = self.get_iattr_value(item.conf, 'tasmota_admin')
            tasmota_topic = self.get_iattr_value(item.conf, 'tasmota_topic')
            tasmota_attr = self.get_iattr_value(item.conf, 'tasmota_attr')
            tasmota_relay = self.get_iattr_value(item.conf, 'tasmota_relay')
            tasmota_relay = '1' if not tasmota_relay else None
            tasmota_rf_details = self.get_iattr_value(item.conf, 'tasmota_rf_details')
            tasmota_zb_device = self.get_iattr_value(item.conf, 'tasmota_zb_device')
            tasmota_zb_group = self.get_iattr_value(item.conf, 'tasmota_zb_group')
            tasmota_zb_attr = self.get_iattr_value(item.conf, 'tasmota_zb_attr')
            tasmota_zb_cluster = self.get_iattr_value(item.conf, 'tasmota_zb_cluster')
            tasmota_zb_attr = tasmota_zb_attr.lower() if tasmota_zb_attr else None

            # handle tasmota_admin
            if tasmota_admin:
                if tasmota_admin == 'delete_retained_messages' and bool(item()):
                    self.clear_retained_messages()
                    item(False, self.get_shortname())

            # handle tasmota_attr
            elif tasmota_attr and tasmota_attr in self.TASMOTA_ATTR_R_W:
                self.logger.info(f"update_item: {item.id()}, item has been changed in SmartHomeNG outside of this plugin in {caller} with value {item()}")

                value = item()
                link = {
                      # 'attribute':      (detail,         data_type, bool_values,   min_value, max_value)
                        'relay':          (f'Power',       bool,      ['OFF', 'ON'], None,      None),
                        'hsb':            ('HsbColor',     list,      None,          None,      None),
                        'white':          ('White',        int,       None,          0,         120),
                        'ct':             ('CT',           int,       None,          153,       500),
                        'rf_send':        ('Backlog',      dict,      None,          None,      None),
                        'rf_key_send':    (f'RfKey',       int,       None,          1,         16),
                        'rf_key':         (f'RfKey',       bool,      None,          None,      None),
                        'zb_permit_join': ('ZbPermitJoin', bool,      ['0', '1'],    None,      None),
                        'zb_forget':      ('ZbForget',     bool,      ['0', '1'],    None,      None),
                        'zb_ping':        ('ZbPing',       bool,      ['0', '1'],    None,      None),
                        }

                if tasmota_attr not in link:
                    return

                (detail, data_type, bool_values, min_value, max_value) = link[tasmota_attr]

                # check data type
                if not isinstance(value, data_type):
                    self.logger.warning(f"update_item: type of value {type(value)} for tasmota_attr={tasmota_attr} to be published, does not fit with expected type '{data_type}'. Abort publishing.")
                    return

                # check and correct if value is in allowed range
                if min_value and value < min_value:
                    self.logger.info(f'Commanded value for {tasmota_attr} below min value; set to allowed min value.')
                    value = min_value
                elif max_value and value > max_value:
                    self.logger.info(f'Commanded value for {tasmota_attr} above max value; set to allowed max value.')
                    value = max_value

                # do tasmota_attr specific checks and adaptations
                if tasmota_attr == 'relay':
                    detail = f"{detail}{tasmota_relay}" if tasmota_relay > '1' else detail

                elif tasmota_attr == 'hsb':
                    if not len(value) == 3:
                        return
                    new_value = f"{value[0]},{value[1]},{value[2]}"
                    value = new_value

                elif tasmota_attr == 'rf_send':
                    # Input: {'RfSync': 12220, 'RfLow': 440, 'RfHigh': 1210, 'RfCode':'#F06104'}  / Output: "RfSync 12220; RfLow 440; RfHigh 1210; RfCode #F06104"
                    rf_cmd = {k.lower(): v for k, v in value.items()}
                    if all(k in rf_cmd for k in [x.lower() for x in self.RF_MSG]):
                        value = f"RfSync {value['rfsync']}; RfLow {value['rflow']}; RfHigh {value['rfhigh']}; RfCode #{value['rfcode']}"
                    else:
                        self.logger.debug(f"update_item: rf_send received but not with correct content; expected content is: {'RfSync': 12220, 'RfLow': 440, 'RfHigh': 1210, 'RfCode':'#F06104'}")
                        return

                elif tasmota_attr == 'rf_key_send':
                    detail = f"{detail}{value}"
                    value = 1

                elif tasmota_attr == 'rf_key':
                    if not tasmota_rf_details:
                        self.logger.warning(f"tasmota_rf_details not specified, no action taken.")
                        return

                    if tasmota_rf_details and '=' in tasmota_rf_details:
                        tasmota_rf_details, tasmota_rf_key_param = tasmota_rf_details.split('=')

                    detail = f"{detail}{tasmota_rf_details}"
                    value = 1

                elif tasmota_attr == 'zb_forget':
                    if value not in self.tasmota_zigbee_devices:
                        self.logger.error(f"Device {value} not known by plugin, no action taken.")
                        return

                elif tasmota_attr == 'zb_ping':
                    if value not in self.tasmota_zigbee_devices:
                        self.logger.error(f"Device {value} not known by plugin, no action taken.")
                        return

                if value is not None:
                    self.publish_tasmota_topic('cmnd', tasmota_topic, detail, value, item, bool_values=bool_values)

            # handle tasmota_zb_attr
            elif tasmota_zb_attr and tasmota_zb_attr in self.TASMOTA_ZB_ATTR_R_W:
                self.logger.info(f"update_item: item={item.id()} with tasmota_zb_attr={tasmota_zb_attr} has been changed from {caller} with value={item()}")
                self.logger.info(f"update_item: tasmota_zb_device={tasmota_zb_device}; tasmota_zb_group={tasmota_zb_group}")

                if tasmota_zb_device is None and tasmota_zb_group is None:
                    return

                value = int(item())
                detail = 'ZbSend'
                link = {
                      # 'attribute': (send_cmd, bool_values,   min_value, max_value, cluster,  convert)
                        'power':     ('Power',  ['OFF', 'ON'],      None,      None, '0x0006', None),
                        'dimmer':    ('Dimmer', None,                  0,       100, '0x0008', _100_to_254),
                        'hue':       ('Hue',    None,                  0,       360, '0x0300', _360_to_254),
                        'sat':       ('Sat',    None,                  0,       100, '0x0300', _100_to_254),
                        'ct':        ('CT',     None,                150,       500, '0x0300', None),
                        'ct_k':      ('CT',     None,               2000,      6700, '0x0300', _kelvin_to_mired),
                        }

                if tasmota_zb_attr not in link:
                    return

                (send_cmd, bool_values, min_value, max_value, cluster, convert) = link[tasmota_zb_attr]

                # check and correct if value is in allowed range
                if min_value and value < min_value:
                    self.logger.info(f'Commanded value for {tasmota_zb_attr} below min value; set to allowed min value.')
                    value = min_value
                elif max_value and value > max_value:
                    self.logger.info(f'Commanded value for {tasmota_zb_attr} above max value; set to allowed max value.')
                    value = max_value
                    
                # Konvertiere Wert
                if convert:
                    value = convert(value)

                # build payload
                payload = {'Device': tasmota_zb_device} if tasmota_zb_device else {'group': tasmota_zb_group}
                payload['Send'] = {send_cmd: value}
                if tasmota_zb_cluster:
                    payload['Cluster'] = cluster

                self.logger.debug(f"payload={payload}")

                # publish command
                self.publish_tasmota_topic('cmnd', tasmota_topic, detail, payload, item, bool_values=bool_values)

            else:
                self.logger.warning(f"update_item: {item.id()}, trying to change item in SmartHomeNG that is read only in tasmota device (by {caller})")

    ############################################################
    #   Callbacks
    ############################################################

    # ToDo: 2023-01-20  17:21:04 ERROR    modules.mqtt                             _on_log: Caught exception in on_message: 'ip'

    def on_mqtt_discovery_message(self, topic: str, payload: dict, qos: int = None, retain: bool = None) -> None:
        """
        Callback function to handle received discovery messages

        :param topic:       MQTT topic
        :param payload:     MQTT message payload
        :param qos:         qos for this message (optional)
        :param retain:      retain flag for this message (optional)

        """

        self._handle_retained_message(topic, retain)

        try:
            (tasmota, discovery, device_id, msg_type) = topic.split('/')
            self.logger.info(f"on_mqtt_discovery_message: device_id={device_id}, type={msg_type}, payload={payload}")
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")
        else:
            if msg_type == 'config':
                """
                device_id = 2CF432CC2FC5

                payload =
                {
                    'ip': '192.168.2.33',                                                                                                   // IP address
                    'dn': 'NXSM200_01',                                                                                                     // Device name
                    'fn': ['NXSM200_01', None, None, None, None, None, None, None],                                                         // List of friendly names
                    'hn': 'NXSM200-01-4037',                                                                                                // Hostname
                    'mac': '2CF432CC2FC5',                                                                                                  // MAC Adresse ohne :
                    'md': 'NXSM200',                                                                                                        // Module
                    'ty': 0,                                                                                                                // Tuya
                    'if': 0,                                                                                                                // ifan
                    'ofln': 'Offline',                                                                                                      // LWT-offline
                    'onln': 'Online',                                                                                                       // LWT-online
                    'state': ['OFF', 'ON', 'TOGGLE', 'HOLD'],                                                                               // StateText[0..3]
                    'sw': '12.1.1',                                                                                                         // Firmware Version
                    't': 'NXSM200_01',                                                                                                      // Topic
                    'ft': '%prefix%/%topic%/',                                                                                              // Full Topic
                    'tp': ['cmnd', 'stat', 'tele'],                                                                                         // Topic [SUB_PREFIX, PUB_PREFIX, PUB_PREFIX2]
                    'rl': [1, 0, 0, 0, 0, 0, 0, 0],                                                                                         // Relays, 0: disabled, 1: relay, 2.. future extension (fan, shutter?)
                    'swc': [-1, -1, -1, -1, -1, -1, -1, -1],                                                                                // SwitchMode
                    'swn': [None, None, None, None, None, None, None, None],                                                                // SwitchName
                    'btn': [0, 0, 0, 0, 0, 0, 0, 0],                                                                                        // Buttons
                    'so': {'4': 0, '11': 0, '13': 0, '17': 0, '20': 0, '30': 0, '68': 0, '73': 0, '82': 0, '114': 0, '117': 0},             // SetOption needed by HA to map Tasmota devices to HA entities and triggers
                    'lk': 0,                                                                                                                // ctrgb
                    'lt_st': 0,                                                                                                             // Light subtype
                    'sho': [0, 0, 0, 0],
                    'sht': [[0, 0, 48], [0, 0, 46], [0, 0, 110], [0, 0, 108]],
                    'ver': 1                                                                                                                // Discovery protocol version
                }
                """

                tasmota_topic = payload['t']
                if tasmota_topic:

                    device_name = payload['dn']
                    self.logger.info(f"Discovered Tasmota Device with topic={tasmota_topic} and device_name={device_name}")

                    # if device is unknown, add it to dict
                    if tasmota_topic not in self.tasmota_devices:
                        self.logger.info(f"New device based on Discovery Message found.")
                        self._add_new_device_to_tasmota_devices(tasmota_topic)

                    # process decoding message and set device to status 'discovered'
                    self.tasmota_devices[tasmota_topic]['ip'] = payload['ip']
                    self.tasmota_devices[tasmota_topic]['friendly_name'] = payload['fn'][0]
                    self.tasmota_devices[tasmota_topic]['fw_ver'] = payload['sw']
                    self.tasmota_devices[tasmota_topic]['device_id'] = device_id
                    self.tasmota_devices[tasmota_topic]['module'] = payload['md']
                    self.tasmota_devices[tasmota_topic]['mac'] = ':'.join(device_id[i:i + 2] for i in range(0, 12, 2))
                    self.tasmota_devices[tasmota_topic]['discovery_config'] = self._rename_discovery_keys(payload)
                    self.tasmota_devices[tasmota_topic]['status'] = 'discovered'

                    # start device interview
                    self._interview_device(tasmota_topic)

                    if payload['ft'] != self.full_topic:
                        self.logger.warning(f"Device {device_name} discovered, but FullTopic of device does not match plugin setting!")

                    # if zigbee bridge, process those
                    if 'zigbee_bridge' in device_name.lower():
                        self.logger.info(f"Zigbee_Bridge discovered")
                        self.tasmota_devices[tasmota_topic]['zigbee']['status'] = 'discovered'
                        self._configure_zigbee_bridge_settings(tasmota_topic)
                        self._discover_zigbee_bridge_devices(tasmota_topic)

            elif msg_type == 'sensors':
                """
                device_id = 2CF432CC2FC5

                payload = {'sn': {'Time': '2022-11-19T13:35:59',
                                  'ENERGY': {'TotalStartTime': '2019-12-23T17:02:03', 'Total': 85.314, 'Yesterday': 0.0,
                                             'Today': 0.0, 'Power': 0, 'ApparentPower': 0, 'ReactivePower': 0, 'Factor': 0.0,
                                             'Voltage': 0, 'Current': 0.0}}, 'ver': 1}
                """

                # get payload with Sensor information
                sensor_payload = payload['sn']
                if 'Time' in sensor_payload:
                    sensor_payload.pop('Time')

                # find matching tasmota_topic
                tasmota_topic = None
                for entry in self.tasmota_devices:
                    if self.tasmota_devices[entry].get('device_id') == device_id:
                        tasmota_topic = entry
                        break

                # hand over sensor information payload for parsing
                if sensor_payload and tasmota_topic:
                    self.logger.info(f"Discovered Tasmota Device with topic={tasmota_topic} and SensorInformation")
                    self._handle_sensor(tasmota_topic, '', sensor_payload)

    def on_mqtt_lwt_message(self, topic: str, payload: bool, qos: int = None, retain: bool = None) -> None:
        """
        Callback function to handle received lwt messages

        :param topic:       MQTT topic
        :param payload:     MQTT message payload
        :param qos:         qos for this message (optional)
        :param retain:      retain flag for this message (optional)

        """
        self._handle_retained_message(topic, retain)

        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")
        else:
            self.logger.info(f"Received LWT Message for {tasmota_topic} with value={payload} and retain={retain}")

            if payload:
                if tasmota_topic not in self.tasmota_devices:
                    self.logger.debug(f"New online device based on LWT Message discovered.")
                    self._handle_new_discovered_device(tasmota_topic)
                self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now() + timedelta(seconds=self.telemetry_period + 5)

            if tasmota_topic in self.tasmota_devices:
                self.tasmota_devices[tasmota_topic]['online'] = payload
                self._set_item_value(tasmota_topic, 'item_online', payload, info_topic)

    def on_mqtt_status0_message(self, topic: str, payload: dict, qos: int = None, retain: bool = None) -> None:
        """
        Callback function to handle received messages

        :param topic:       MQTT topic
        :param payload:     MQTT message payload
        :param qos:         qos for this message
        :param retain:      retain flag for this message

        """

        """ 
        Example payload 
        
        payload = {'Status': {'Module': 75, 'DeviceName': 'ZIGBEE_Bridge01', 'FriendlyName': ['SONOFF_ZB1'],
                              'Topic': 'SONOFF_ZB1', 'ButtonTopic': '0', 'Power': 0, 'PowerOnState': 3, 'LedState': 1,
                              'LedMask': 'FFFF', 'SaveData': 1, 'SaveState': 1, 'SwitchTopic': '0',
                              'SwitchMode': [0, 0, 0, 0, 0, 0, 0, 0], 'ButtonRetain': 0, 'SwitchRetain': 0,
                              'SensorRetain': 0, 'PowerRetain': 0, 'InfoRetain': 0, 'StateRetain': 0},
                   'StatusPRM': {'Baudrate': 115200, 'SerialConfig': '8N1', 'GroupTopic': 'tasmotas',
                                 'OtaUrl': 'http://ota.tasmota.com/tasmota/release/tasmota-zbbridge.bin.gz',
                                 'RestartReason': 'Software/System restart', 'Uptime': '0T23:18:30',
                                 'StartupUTC': '2022-11-19T12:10:15', 'Sleep': 50, 'CfgHolder': 4617, 'BootCount': 116,
                                 'BCResetTime': '2021-04-28T08:32:10', 'SaveCount': 160, 'SaveAddress': '1FB000'},
                   'StatusFWR': {'Version': '12.1.1(zbbridge)', 'BuildDateTime': '2022-08-25T11:37:17', 'Boot': 31,
                                 'Core': '2_7_4_9', 'SDK': '2.2.2-dev(38a443e)', 'CpuFrequency': 160,
                                 'Hardware': 'ESP8266EX', 'CR': '372/699'},
                   'StatusLOG': {'SerialLog': 0, 'WebLog': 2, 'MqttLog': 0, 'SysLog': 0, 'LogHost': '', 'LogPort': 514,
                                 'SSId': ['WLAN-Access', ''], 'TelePeriod': 300, 'Resolution': '558180C0',
                                 'SetOption': ['00008009', '2805C80001000600003C5A0A002800000000', '00000080',
                                               '40046002', '00004810', '00000000']},
                   'StatusMEM': {'ProgramSize': 685, 'Free': 1104, 'Heap': 25, 'ProgramFlashSize': 2048,
                                 'FlashSize': 2048, 'FlashChipId': '1540A1', 'FlashFrequency': 40, 'FlashMode': 3,
                                 'Features': ['00000809', '0F1007C6', '04400001', '00000003', '00000000', '00000000',
                                              '00020080', '00200000', '04000000', '00000000'],
                                 'Drivers': '1,2,4,7,9,10,12,20,23,38,41,50,62', 'Sensors': '1'},
                   'StatusNET': {'Hostname': 'SONOFF-ZB1-6926', 'IPAddress': '192.168.2.24', 'Gateway': '192.168.2.1',
                                 'Subnetmask': '255.255.255.0', 'DNSServer1': '192.168.2.1', 'DNSServer2': '0.0.0.0',
                                 'Mac': '84:CC:A8:AA:1B:0E', 'Webserver': 2, 'HTTP_API': 1, 'WifiConfig': 0,
                                 'WifiPower': 17.0},
                   'StatusMQT': {'MqttHost': '192.168.2.12', 'MqttPort': 1883, 'MqttClientMask': 'DVES_%06X',
                                 'MqttClient': 'DVES_AA1B0E', 'MqttUser': 'DVES_USER', 'MqttCount': 1,
                                 'MAX_PACKET_SIZE': 1200, 'KEEPALIVE': 30, 'SOCKET_TIMEOUT': 4},
                   'StatusTIM': {'UTC': '2022-11-20T11:28:45', 'Local': '2022-11-20T12:28:45',
                                 'StartDST': '2022-03-27T02:00:00', 'EndDST': '2022-10-30T03:00:00',
                                 'Timezone': '+01:00', 'Sunrise': '08:07', 'Sunset': '17:04'},
                   'StatusSNS': {'Time': '2022-11-20T12:28:45'},
                   'StatusSTS': {'Time': '2022-11-20T12:28:45', 'Uptime': '0T23:18:30', 'UptimeSec': 83910, 'Vcc': 3.41,
                                 'Heap': 24, 'SleepMode': 'Dynamic', 'Sleep': 50, 'LoadAvg': 19, 'MqttCount': 1,
                                 'Wifi': {'AP': 1, 'SSId': 'WLAN-Access', 'BSSId': '38:10:D5:15:87:69', 'Channel': 1,
                                          'Mode': '11n', 'RSSI': 50, 'Signal': -75, 'LinkCount': 1,
                                          'Downtime': '0T00:00:03'}}}
        
        """

        self._handle_retained_message(topic, retain)

        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
            self.logger.info(f"on_mqtt_status0_message: topic_type={topic_type}, tasmota_topic={tasmota_topic}, info_topic={info_topic}, payload={payload}")
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")

        else:
            self.logger.info(f"Received Status0 Message for {tasmota_topic} with value={payload} and retain={retain}")
            self.tasmota_devices[tasmota_topic]['status'] = 'interviewed'

            # handle teleperiod
            self._handle_teleperiod(tasmota_topic, payload['StatusLOG'])

            if self.tasmota_devices[tasmota_topic]['status'] != 'interviewed':
                if self.tasmota_devices[tasmota_topic]['status'] != 'discovered':
                    # friendly name
                    self.tasmota_devices[tasmota_topic]['friendly_name'] = payload['Status']['FriendlyName'][0]

                    # IP Address
                    ip = payload['StatusNET']['IPAddress']
                    ip_eth = payload['StatusNET'].get('Ethernet', {}).get('IPAddress')
                    ip = ip_eth if ip == '0.0.0.0' else None
                    self.tasmota_devices[tasmota_topic]['ip'] = ip

                    # Firmware
                    self.tasmota_devices[tasmota_topic]['fw_ver'] = payload['StatusFWR']['Version'].split('(')[0]

                    # MAC
                    self.tasmota_devices[tasmota_topic]['mac'] = payload['StatusNET']['Mac']

                # Module No
                self.tasmota_devices[tasmota_topic]['template'] = payload['Status']['Module']

            # get detailed status using payload['StatusSTS']
            status_sts = payload['StatusSTS']

            # Handling Lights and Dimmer
            if any([i in status_sts for i in self.LIGHT_MSG]):
                self._handle_lights(tasmota_topic, info_topic, status_sts)

            # Handling of Power
            if any(item.startswith("POWER") for item in status_sts.keys()):
                self._handle_power(tasmota_topic, info_topic, status_sts)

            # Handling of RF messages
            if any(item.startswith("Rf") for item in status_sts.keys()):
                self._handle_rf(tasmota_topic, info_topic, status_sts)

            # Handling of Wi-Fi
            if 'Wifi' in status_sts:
                self._handle_wifi(tasmota_topic, status_sts['Wifi'])

            # Handling of Uptime
            if 'Uptime' in status_sts:
                self._handle_uptime(tasmota_topic, status_sts['Uptime'])

            # Handling of UptimeSec
            if 'UptimeSec' in status_sts:
                self.logger.info(f"Received Message contains UptimeSec information.")
                self._handle_uptime_sec(tasmota_topic, status_sts['UptimeSec'])

    def on_mqtt_info_message(self, topic: str, payload: dict, qos: int = None, retain: bool = None) -> None:
        """
        Callback function to handle received messages

        :param topic:       MQTT topic
        :param payload:     MQTT message payload
        :param qos:         qos for this message (optional)
        :param retain:      retain flag for this message (optional)

        """

        self._handle_retained_message(topic, retain)

        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
            self.logger.debug(f"on_mqtt_message: topic_type={topic_type}, tasmota_topic={tasmota_topic}, info_topic={info_topic}, payload={payload}")
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")
        else:
            if info_topic == 'INFO1':
                # payload={'Info1': {'Module': 'Sonoff Basic', 'Version': '11.0.0(tasmota)', 'FallbackTopic': 'cmnd/DVES_2EB8AE_fb/', 'GroupTopic': 'cmnd/tasmotas/'}}
                self.logger.debug(f"Received Message decoded as INFO1 message.")
                self.tasmota_devices[tasmota_topic]['fw_ver'] = payload['Info1']['Version'].split('(')[0]
                self.tasmota_devices[tasmota_topic]['module_no'] = payload['Info1']['Module']

            elif info_topic == 'INFO2':
                # payload={'Info2': {'WebServerMode': 'Admin', 'Hostname': 'SONOFF-B1-6318', 'IPAddress': '192.168.2.25'}}
                self.logger.debug(f"Received Message decoded as INFO2 message.")
                self.tasmota_devices[tasmota_topic]['ip'] = payload['Info2']['IPAddress']

            elif info_topic == 'INFO3':
                # payload={'Info3': {'RestartReason': 'Software/System restart', 'BootCount': 1395}}
                self.logger.debug(f"Received Message decoded as INFO3 message.")
                restart_reason = payload['Info3']['RestartReason']
                self.logger.warning(f"Device {tasmota_topic} (IP={self.tasmota_devices[tasmota_topic]['ip']}) just startet. Reason={restart_reason}")

    def on_mqtt_message(self, topic: str, payload: dict, qos: int = None, retain: bool = None) -> None:
        """
        Callback function to handle received messages

        :param topic:       MQTT topic
        :param payload:     MQTT message payload
        :param qos:         qos for this message (optional)
        :param retain:      retain flag for this message (optional)

        """

        self._handle_retained_message(topic, retain)

        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
            self.logger.info(f"on_mqtt_message: topic_type={topic_type}, tasmota_topic={tasmota_topic}, info_topic={info_topic}, payload={payload}")
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")
        else:

            # handle unknown device
            if tasmota_topic not in self.tasmota_devices:
                self._handle_new_discovered_device(tasmota_topic)

            # handle message
            if isinstance(payload, dict) and info_topic in ['STATE', 'RESULT']:

                # Handling of TelePeriod
                if 'TelePeriod' in payload:
                    self.logger.info(f"Received Message decoded as teleperiod message.")
                    self._handle_teleperiod(tasmota_topic, payload['TelePeriod'])

                elif 'Module' in payload:
                    self.logger.info(f"Received Message decoded as Module message.")
                    self._handle_module(tasmota_topic, payload['Module'])

                # Handling of Light messages
                elif any([i in payload for i in self.LIGHT_MSG]):
                    self.logger.info(f"Received Message decoded as light message.")
                    self._handle_lights(tasmota_topic, info_topic, payload)

                # Handling of Power messages
                elif any(item.startswith("POWER") for item in payload.keys()):
                    self.logger.info(f"Received Message decoded as power message.")
                    self._handle_power(tasmota_topic, info_topic, payload)

                # Handling of RF messages payload={'Time': '2022-11-21T11:22:55', 'RfReceived': {'Sync': 10120, 'Low': 330, 'High': 980, 'Data': '3602B8', 'RfKey': 'None'}}
                elif 'RfReceived' in payload:
                    self.logger.info(f"Received Message decoded as RF message.")
                    self._handle_rf(tasmota_topic, info_topic, payload['RfReceived'])

                # Handling of Setting messages
                elif next(iter(payload)).startswith("SetOption"):
                    # elif any(item.startswith("SetOption") for item in payload.keys()):
                    self.logger.info(f"Received Message decoded as Tasmota Setting message.")
                    self._handle_setting(tasmota_topic, payload)

                # Handling of Zigbee Bridge Config messages
                elif 'ZbConfig' in payload:
                    self.logger.info(f"Received Message decoded as Zigbee Config message.")
                    self._handle_zbconfig(tasmota_topic, payload['ZbConfig'])

                # Handling of Zigbee Bridge Status messages
                elif any(item.startswith("ZbStatus") for item in payload.keys()):
                    self.logger.info(f"Received Message decoded as Zigbee ZbStatus message.")
                    self._handle_zbstatus(tasmota_topic, payload)

                # Handling of Wi-Fi
                if 'Wifi' in payload:
                    self.logger.info(f"Received Message contains Wifi information.")
                    self._handle_wifi(tasmota_topic, payload['Wifi'])

                # Handling of Uptime
                if 'Uptime' in payload:
                    self.logger.info(f"Received Message contains Uptime information.")
                    self._handle_uptime(tasmota_topic, payload['Uptime'])

                # Handling of UptimeSec
                if 'UptimeSec' in payload:
                    self.logger.info(f"Received Message contains UptimeSec information.")
                    self._handle_uptime_sec(tasmota_topic, payload['UptimeSec'])

            elif isinstance(payload, dict) and info_topic == 'SENSOR':
                self.logger.info(f"Received Message contains sensor information.")
                self._handle_sensor(tasmota_topic, info_topic, payload)

            else:
                self.logger.warning(f"Received Message '{payload}' not handled within plugin.")

            # setting new online-timeout
            self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now() + timedelta(seconds=self.telemetry_period + 5)

            # setting online_item to True
            self._set_item_value(tasmota_topic, 'item_online', True, info_topic)

    def on_mqtt_power_message(self,  topic: str, payload: dict, qos: int = None, retain: bool = None) -> None:
        """
        Callback function to handle received messages

        :param topic:       MQTT topic
        :param payload:     MQTT message payload
        :param qos:         qos for this message (optional)
        :param retain:      retain flag for this message (optional)

        """

        self._handle_retained_message(topic, retain)

        # check for retained message and handle it
        if bool(retain):
            if topic not in self.topics_of_retained_messages:
                self.topics_of_retained_messages.append(topic)
        else:
            if topic in self.topics_of_retained_messages:
                self.topics_of_retained_messages.remove(topic)

        # handle incoming message
        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
            self.logger.info(f"on_mqtt_power_message: topic_type={topic_type}, tasmota_topic={tasmota_topic}, info_topic={info_topic}, payload={payload}")
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")
        else:
            device = self.tasmota_devices.get(tasmota_topic, None)
            if device:
                if info_topic.startswith('POWER'):
                    tasmota_relay = str(info_topic[5:])
                    tasmota_relay = '1' if not tasmota_relay else None
                    item_relay = f'item_relay{tasmota_relay}'
                    self._set_item_value(tasmota_topic, item_relay, payload == 'ON', info_topic)
                    self.tasmota_devices[tasmota_topic]['relais'][info_topic] = payload

    ############################################################
    #   Parse detailed messages
    ############################################################

    def _handle_sensor(self, device: str, function: str, payload: dict) -> None:
        """

        :param device:
        :param function:
        :param payload:
        :return:
        """
        # Handling of Zigbee Device Messages
        if 'ZbReceived' in payload:
            self.logger.info(f"Received Message decoded as Zigbee Sensor message.")
            self._handle_sensor_zigbee(device, function, payload['ZbReceived'])

        # Handling of Energy Sensors
        elif 'ENERGY' in payload:
            self.logger.info(f"Received Message decoded as Energy Sensor message.")
            self._handle_sensor_energy(device, function, payload['ENERGY'])

        # Handling of Environmental Sensors
        elif any([i in payload for i in self.ENV_SENSOR]):
            self._handle_sensor_env(device, function, payload)

        # Handling of Analog Sensors
        elif 'ANALOG' in payload:
            self.logger.info(f"Received Message decoded as ANALOG Sensor message.")
            self._handle_sensor_analog(device, function, payload['ANALOG'])

        # Handling of Sensors of ESP32
        elif 'ESP32' in payload:
            self.logger.info(f"Received Message decoded as ESP32 Sensor message.")
            self._handle_sensor_esp32(device, function, payload['ESP32'])

        # Handling of any other Sensor e.g. all SML devices
        else:
            if len(payload) == 2 and isinstance(payload[list(payload.keys())[1]], dict):  # wenn payload 2 Einträge und der zweite Eintrag vom Typ dict
                self.logger.info(f"Received Message decoded as other Sensor message (e.g. smartmeter).")
                sensor = list(payload.keys())[1]
                self._handle_sensor_other(device, sensor, function, payload[sensor])

    def _handle_sensor_zigbee(self, device: str, function: str, payload: dict) -> None:
        """
        Handles Zigbee Sensor information and set items

        :param payload: payload containing zigbee sensor infos
        :return:
        """

        """
        payload = {'Fenster_01': {'Device': '0xD4F3', 'Name': 'Fenster_01', 'Contact': 0, 'Endpoint': 1, 'LinkQuality': 92}}
        """

        # self.logger.debug(f"_handle_sensor_zigbee: {device=}, {function=}, {payload=}")

        for zigbee_device in payload:
            if zigbee_device != '0x0000' and zigbee_device not in self.tasmota_zigbee_devices:
                self.logger.info(f"New Zigbee Device '{zigbee_device}'based on {function}-Message from {device} discovered")
                self.tasmota_zigbee_devices[zigbee_device] = {}

            # Make all keys of Zigbee-Device Payload Dict lowercase to match itemtype from parse_item
            zigbee_device_dict = {k.lower(): v for k, v in payload[zigbee_device].items()}

            # Korrigieren der Werte für (HSB) Dimmer (0-254 -> 0-100), Hue(0-254 -> 0-360), Saturation (0-254 -> 0-100)
            if 'dimmer' in zigbee_device_dict:
                zigbee_device_dict.update({'dimmer': _254_to_100(zigbee_device_dict['dimmer'])})
            if 'sat' in zigbee_device_dict:
                zigbee_device_dict.update({'sat': _254_to_100(zigbee_device_dict['sat'])})
            if 'hue' in zigbee_device_dict:
                zigbee_device_dict.update({'hue': _254_to_360(zigbee_device_dict['hue'])})
            if 'ct' in zigbee_device_dict:
                zigbee_device_dict['ct_k'] = _mired_to_kelvin(zigbee_device_dict['ct'])

            # Korrektur des LastSeenEpoch von Timestamp zu datetime
            if 'lastseenepoch' in zigbee_device_dict:
                zigbee_device_dict.update({'lastseenepoch': datetime.fromtimestamp(zigbee_device_dict['lastseenepoch'])})
            if 'batterylastseenepoch' in zigbee_device_dict:
                zigbee_device_dict.update({'batterylastseenepoch': datetime.fromtimestamp(zigbee_device_dict['batterylastseenepoch'])})

            # Udpate des Sub-Dicts
            self.tasmota_zigbee_devices[zigbee_device].update(zigbee_device_dict)

            # Iterate over payload and set corresponding items
            for element in zigbee_device_dict:
                itemtype = f"item_{zigbee_device}.{element.lower()}"
                value = zigbee_device_dict[element]
                self._set_item_value(device, itemtype, value, function)

    def _handle_sensor_energy(self, device: str, function: str, energy: dict):
        """
        Handle Energy Sensor Information
        :param device:
        :param energy:
        :param function:
        """

        if 'ENERGY' not in self.tasmota_devices[device]['sensors']:
            self.tasmota_devices[device]['sensors']['ENERGY'] = {}

        self.tasmota_devices[device]['sensors']['ENERGY']['period'] = energy.get('Period', None)

        for key in self.ENERGY_SENSOR_KEYS:
            if key in energy:
                self.tasmota_devices[device]['sensors']['ENERGY'][key.lower()] = energy[key]
                self._set_item_value(device, self.ENERGY_SENSOR_KEYS[key], energy[key], function)

    def _handle_sensor_env(self, device: str, function: str, payload: dict):
        """
        Handle Environmental Sensor Information
        :param device:
        :param function:
        :param payload:
        """

        for sensor in self.ENV_SENSOR:
            data = payload.get(sensor)

            if data and isinstance(data, dict):
                self.logger.debug(f"Received Message decoded as {sensor} Sensor message.")
                if sensor not in self.tasmota_devices[device]['sensors']:
                    self.tasmota_devices[device]['sensors'][sensor] = {}

                for key in self.ENV_SENSOR_KEYS:
                    if key in data:
                        self.tasmota_devices[device]['sensors'][sensor][key.lower()] = data[key]
                        self._set_item_value(device, self.ENV_SENSOR_KEYS[key], data[key], function)

    def _handle_sensor_analog(self, device: str, function: str, analog: dict):
        """
        Handle Analog Sensor Information
        :param device:
        :param function:
        :param analog:
        """

        if 'ANALOG' not in self.tasmota_devices[device]['sensors']:
            self.tasmota_devices[device]['sensors']['ANALOG'] = {}

        for key in self.ANALOG_SENSOR_KEYS:
            if key in analog:
                self.tasmota_devices[device]['sensors']['ANALOG'][key.lower()] = analog[key]
                self._set_item_value(device, self.ANALOG_SENSOR_KEYS[key], analog[key], function)

    def _handle_sensor_esp32(self, device: str, function: str, esp32: dict):
        """
        Handle ESP32 Sensor Information
        :param device:
        :param function:
        :param esp32:
        """

        if 'ESP32' not in self.tasmota_devices[device]['sensors']:
            self.tasmota_devices[device]['sensors']['ESP32'] = {}

        for key in self.ESP32_SENSOR_KEYS:
            if key in esp32:
                self.tasmota_devices[device]['sensors']['ESP32'][key.lower()] = esp32[key]
                self._set_item_value(device, self.ESP32_SENSOR_KEYS[key], esp32[key], function)

    def _handle_sensor_other(self, device: str, sensor: str, function: str, payload: dict):
        """
        Handle Other Sensor Information
        :param device: Tasmota Device
        :param sensor: Sensor Device
        :param function: Messages Information will be taken from
        :param payload: dict with infos
        """

        self.logger.debug(f"Received Message decoded as {sensor} Sensor message with payload={payload}.")

        if sensor not in self.tasmota_devices[device]['sensors']:
            self.tasmota_devices[device]['sensors'][sensor] = {}

        # Make all keys of SML-Device Payload Dict lowercase to match itemtype from parse_item
        sensor_dict = {k.lower(): v for k, v in payload.items()}

        # Udpate des Sub-Dicts
        self.tasmota_devices[device]['sensors'][sensor].update(sensor_dict)

        # Iterate over payload and set corresponding items
        for element in sensor_dict:
            itemtype = f"item_{sensor}.{element.lower()}"
            value = sensor_dict[element]
            self._set_item_value(device, itemtype, value, function)

    def _handle_lights(self, device: str, function: str, payload: dict) -> None:
        """
        Extracts Light information out of payload and updates plugin dict

        :param device:          Device, the Light information shall be handled (equals tasmota_topic)
        :param function:        Function of Device (equals info_topic)
        :param payload:         MQTT message payload

        """
        hsb = payload.get('HSBColor')
        if hsb:
            if hsb.count(',') == 2:
                hsb = hsb.split(",")
                try:
                    hsb = [int(element) for element in hsb]
                except Exception as e:
                    self.logger.info(f"Received Data for HSBColor do not contain in values for HSB. Payload was {hsb}. Error was {e}.")
            else:
                self.logger.info(f"Received Data for HSBColor do not contain values for HSB. Payload was {hsb}.")
            self.tasmota_devices[device]['lights']['hsb'] = hsb
            self._set_item_value(device, 'item_hsb', hsb, function)

        dimmer = payload.get('Dimmer')
        if dimmer:
            self.tasmota_devices[device]['lights']['dimmer'] = dimmer
            self._set_item_value(device, 'item_dimmer', dimmer, function)

        color = payload.get('Color')
        if color:
            self.tasmota_devices[device]['lights']['color'] = str(color)

        ct = payload.get('CT')
        if ct:
            self.tasmota_devices[device]['lights']['ct'] = ct
            self._set_item_value(device, 'item_ct', ct, function)

        white = payload.get('White')
        if white:
            self.tasmota_devices[device]['lights']['white'] = white
            self._set_item_value(device, 'item_white', white, function)

        scheme = payload.get('Scheme')
        if scheme:
            self.tasmota_devices[device]['lights']['scheme'] = scheme

        fade = payload.get('Fade')
        if fade:
            self.tasmota_devices[device]['lights']['fade'] = bool(fade)

        speed = payload.get('Speed')
        if speed:
            self.tasmota_devices[device]['lights']['speed'] = speed

        ledtable = payload.get('LedTable')
        if ledtable:
            self.tasmota_devices[device]['lights']['ledtable'] = bool(ledtable)

    def _handle_power(self, device: str, function: str, payload: dict) -> None:
        """
        Extracts Power information out of payload and updates plugin dict

        :param device:          Device, the Power information shall be handled (equals tasmota_topic)
        :param function:        Function of Device (equals info_topic)
        :param payload:         MQTT message payload

        """
        # payload = {"Time": "2022-11-21T12:56:34", "Uptime": "0T00:00:11", "UptimeSec": 11, "Heap": 27, "SleepMode": "Dynamic", "Sleep": 50, "LoadAvg": 19, "MqttCount": 0, "POWER1": "OFF", "POWER2": "OFF", "POWER3": "OFF", "POWER4": "OFF", "Wifi": {"AP": 1, "SSId": "WLAN-Access", "BSSId": "38:10:D5:15:87:69", "Channel": 1, "Mode": "11n", "RSSI": 82, "Signal": -59, "LinkCount": 1, "Downtime": "0T00:00:03"}}

        power_dict = {key: val for key, val in payload.items() if key.startswith('POWER')}
        self.tasmota_devices[device]['relais'].update(power_dict)
        for power in power_dict:
            relay_index = 1 if len(power) == 5 else str(power[5:])
            item_relay = f'item_relay{relay_index}'
            self._set_item_value(device, item_relay, power_dict[power], function)

    def _handle_module(self, device: str, payload: dict) -> None:
        """
        Extracts Module information out of payload and updates plugin dict payload = {"0":"ZB-GW03-V1.3"}}

        :param device:          Device, the Module information shall be handled
        :param payload:         MQTT message payload

        """
        template = next(iter(payload))
        module = payload[template]
        self.tasmota_devices[device]['module'] = module
        self.tasmota_devices[device]['tasmota_template'] = template

    def _handle_rf(self, device: str, function: str, payload: dict) -> None:
        """
        Extracts RF information out of payload and updates plugin dict

        :param device:          Device, the RF information shall be handled
        :param function:        Function of Device (equals info_topic)
        :param payload:         MQTT message payload

        """

        # payload = {'Sync': 10120, 'Low': 330, 'High': 980, 'Data': '3602B8', 'RfKey': 'None'}

        self.logger.info(f"Received Message decoded as RF message.")
        self.tasmota_devices[device]['rf']['rf_received'] = payload
        self._set_item_value(device, 'item_rf_recv', payload['Data'], function)

        rf_key = 0 if payload["RfKey"] == 'None' else int(payload["RfKey"])
        self._set_item_value(device, 'item_rf_key_recv', rf_key, function)
        self._set_item_value(device, f'item_rf_key{rf_key}', True, function)

    def _handle_zbconfig(self, device: str, payload: dict) -> None:
        """
        Extracts ZigBee Config information out of payload and updates plugin dict

        :param device:          Device, the Zigbee Config information shall be handled
        :param payload:         MQTT message payload

        """
        # stat/SONOFF_ZB1/RESULT = {"ZbConfig":{"Channel":11,"PanID":"0x0C84","ExtPanID":"0xCCCCCCCCAAA8CC84","KeyL":"0xAAA8CC841B1F40A1","KeyH":"0xAAA8CC841B1F40A1","TxRadio":20}}
        self.tasmota_devices[device]['zigbee']['zbconfig'] = payload

    def _handle_zbstatus(self, device: str, payload: dict) -> None:
        """
        Extracts ZigBee Status information out of payload and updates plugin dict

        :param device:          Device, the Zigbee Status information shall be handled
        :param payload:         MQTT message payload

        """

        zbstatus1 = payload.get('ZbStatus1')
        if zbstatus1:
            self.logger.info(f"Received Message decoded as Zigbee ZbStatus1 message for device {device}.")
            self._handle_zbstatus1(device, zbstatus1)

        zbstatus23 = payload.get('ZbStatus2')
        if not zbstatus23:
            zbstatus23 = payload.get('ZbStatus3')

        if zbstatus23:
            self.logger.info(f"Received Message decoded as Zigbee ZbStatus2 or ZbStatus3 message for device {device}.")
            self._handle_zbstatus23(device, zbstatus23)

    def _handle_zbstatus1(self, device: str, zbstatus1: list) -> None:
        """
        Extracts ZigBee Status1 information out of payload and updates plugin dict

        :param device:          Device, the Zigbee Status information shall be handled
        :param zbstatus1:       List of status information out mqtt payload

        """
        """
        zbstatus1 = [{'Device': '0x676D', 'Name': 'SNZB-02_01'}, 
                     {'Device': '0xD4F3', 'Name': 'Fenster_01'}
                     ]
        """

        for element in zbstatus1:
            zigbee_device = element.get('Name')
            if not zigbee_device:
                zigbee_device = element['Device']

            if zigbee_device != '0x0000' and zigbee_device not in self.tasmota_zigbee_devices:
                self.logger.info(f"New Zigbee Device '{zigbee_device}'based on 'ZbStatus1'-Message from {device} discovered")
                self.tasmota_zigbee_devices[zigbee_device] = {}

        # request detailed information of all discovered zigbee devices
        self._poll_zigbee_devices(device)

    def _handle_zbstatus23(self, device: str, zbstatus23: dict) -> None:
        """
        Extracts ZigBee Status 2 and 3 information out of payload and updates plugin dict

        :param device:          Device, the Zigbee Status information shall be handled
        :param zbstatus23:   ZbStatus2 or ZbStatus 3 part of MQTT message payload

        """

        """
        zbstatus23 = [{'Device': '0xD4F3', 'Name': 'Fenster_01', 'IEEEAddr': '0x00158D0007005B59',
                       'ModelId': 'lumi.sensor_magnet.aq2', 'Manufacturer': 'LUMI', 'Endpoints': [1],
                       'Config': ['A01'], 'ZoneStatus': 29697, 'Reachable': True, 'BatteryPercentage': 100,
                       'BatteryLastSeenEpoch': 1668953504, 'LastSeen': 238, 'LastSeenEpoch': 1668953504,
                       'LinkQuality': 81}]
                       
        zbstatus23 =  [{'Device': '0x676D', 'Name': 'SNZB-02_01', 'IEEEAddr': '0x00124B00231E45B8',
                        'ModelId': 'TH01', 'Manufacturer': 'eWeLink', 'Endpoints': [1], 'Config': ['T01'], 
                        'Temperature': 19.27, 'Humidity': 58.12, 'Reachable': True, 'BatteryPercentage': 73, 
                        'BatteryLastSeenEpoch': 1668953064, 'LastSeen': 610, 'LastSeenEpoch': 1668953064, 'LinkQuality': 66}]

        zbstatus23 = [{'Device': '0x0A22', 'IEEEAddr': '0xF0D1B800001571C5', 'ModelId': 'CLA60 RGBW Z3',
                       'Manufacturer': 'LEDVANCE', 'Endpoints': [1], 'Config': ['L01', 'O01'], 'Dimmer': 100,
                       'Hue': 200, 'Sat': 254, 'X': 1, 'Y': 1, 'CT': 350, 'ColorMode': 0, 'RGB': 'B600FF',
                       'RGBb': '480064', 'Power': 1, 'Reachable': False, 'LastSeen': 30837743,
                       'LastSeenEpoch': 1638132192, 'LinkQuality': 13}]
        """

        for element in zbstatus23:
            zigbee_device = element.get('Name')
            if not zigbee_device:
                zigbee_device = element['Device']

            payload = dict()
            payload[zigbee_device] = element

            self._handle_sensor_zigbee(device, 'ZbStatus', payload)

    def _handle_wifi(self, device: str, payload: dict) -> None:
        """
        Extracts Wi-Fi information out of payload and updates plugin dict

        :param device:          Device, the Zigbee Status information shall be handled
        :param payload:         MQTT message payload

        """
        self.logger.debug(f"_handle_wifi: received payload={payload}")
        wifi_signal = payload.get('Signal')
        if wifi_signal:
            if isinstance(wifi_signal, str) and wifi_signal.isdigit():
                wifi_signal = int(wifi_signal)
            self.tasmota_devices[device]['wifi_signal'] = wifi_signal

    def _handle_setting(self, device: str, payload: dict) -> None:
        """
        Extracts Zigbee Bridge Setting information out of payload and updates dict
        :param device:
        :param payload:     MQTT message payload
        """

        # handle Setting listed in Zigbee Bridge Settings (wenn erster Key des Payload-Dict in Zigbee_Bridge_Default_Setting...)
        if next(iter(payload)) in self.ZIGBEE_BRIDGE_DEFAULT_OPTIONS:
            if not self.tasmota_devices[device]['zigbee'].get('setting'):
                self.tasmota_devices[device]['zigbee']['setting'] = {}
            self.tasmota_devices[device]['zigbee']['setting'].update(payload)

            if self.tasmota_devices[device]['zigbee']['setting'] == self.ZIGBEE_BRIDGE_DEFAULT_OPTIONS:
                self.tasmota_devices[device]['zigbee']['status'] = 'set'
                self.logger.info(f'_handle_setting: Setting of Tasmota Zigbee Bridge successful.')

    def _handle_teleperiod(self, tasmota_topic: str, teleperiod: dict) -> None:

        self.tasmota_devices[tasmota_topic]['teleperiod'] = teleperiod
        if teleperiod != self.telemetry_period:
            self._set_telemetry_period(tasmota_topic)

    def _handle_uptime(self, tasmota_topic: str, uptime: str) -> None:
        self.logger.debug(f"Received Message contains Uptime information. uptime={uptime}")
        self.tasmota_devices[tasmota_topic]['uptime'] = uptime

    def _handle_uptime_sec(self, tasmota_topic: str, uptime_sec: int) -> None:
        self.logger.debug(f"Received Message contains UptimeSec information. uptime={uptime_sec}")
        self.tasmota_devices[tasmota_topic]['uptime_sec'] = int(uptime_sec)

    ############################################################
    #   MQTT Settings & Config
    ############################################################

    def add_tasmota_subscriptions(self):
        self.logger.info(f"Further tasmota_subscriptions for regular/cyclic messages will be added")

        self.add_tasmota_subscription('tele', '+', 'STATE',  'dict', callback=self.on_mqtt_message)
        self.add_tasmota_subscription('tele', '+', 'SENSOR', 'dict', callback=self.on_mqtt_message)
        self.add_tasmota_subscription('tele', '+', 'RESULT', 'dict', callback=self.on_mqtt_message)
      # self.add_tasmota_subscription('tele', '+', 'INFO1',  'dict', callback=self.on_mqtt_message)
      # self.add_tasmota_subscription('tele', '+', 'INFO2',  'dict', callback=self.on_mqtt_message)
        self.add_tasmota_subscription('tele', '+', 'INFO3',  'dict', callback=self.on_mqtt_info_message)
        self.add_tasmota_subscription('stat', '+', 'POWER',  'num',  callback=self.on_mqtt_power_message)
        self.add_tasmota_subscription('stat', '+', 'POWER1', 'num',  callback=self.on_mqtt_power_message)
        self.add_tasmota_subscription('stat', '+', 'POWER2', 'num',  callback=self.on_mqtt_power_message)
        self.add_tasmota_subscription('stat', '+', 'POWER3', 'num',  callback=self.on_mqtt_power_message)
        self.add_tasmota_subscription('stat', '+', 'POWER4', 'num',  callback=self.on_mqtt_power_message)

    def check_online_status(self):
        """
        checks all tasmota topics, if last message is with telemetry period. If not set tasmota_topic offline

        """

        self.logger.info("check_online_status: Checking online status of connected devices")
        for tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic].get('online') is True and self.tasmota_devices[tasmota_topic].get('online_timeout'):
                if self.tasmota_devices[tasmota_topic]['online_timeout'] < datetime.now():
                    self._set_device_offline(tasmota_topic)
                else:
                    self.logger.debug(f'check_online_status: Checking online status of {tasmota_topic} successful')

    def add_tasmota_subscription(self, prefix: str, topic: str, detail: str, payload_type: str, bool_values: list = None, item=None, callback=None) -> None:
        """
        build the topic in Tasmota style and add the subscription to mqtt

        :param prefix:          prefix of topic to subscribe to
        :param topic:           unique part of topic to subscribe to
        :param detail:          detail of topic to subscribe to
        :param payload_type:    payload type of the topic (for this subscription to the topic)
        :param bool_values:     bool values (for this subscription to the topic)
        :param item:            item that should receive the payload as value. Used by the standard handler (if no callback function is specified)
        :param callback:        a plugin can provide an own callback function, if special handling of the payload is needed

        """

        tpc = self.full_topic.replace("%prefix%", prefix)
        tpc = tpc.replace("%topic%", topic)
        tpc += detail
        self.add_subscription(tpc, payload_type, bool_values=bool_values, callback=callback)

    def publish_tasmota_topic(self, prefix: str, topic: str, detail: str, payload, item=None, qos: int = None, retain: bool = False, bool_values: list = None) -> None:
        """
        build the topic in Tasmota style and publish to mqtt

        :param prefix:          prefix of topic to publish
        :param topic:           unique part of topic to publish
        :param detail:          detail of topic to publish
        :param payload:         payload to publish
        :param item:            item (if relevant)
        :param qos:             qos for this message (optional)
        :param retain:          retain flag for this message (optional)
        :param bool_values:     bool values (for publishing this topic, optional)

        """
        tpc = self.full_topic.replace("%prefix%", prefix)
        tpc = tpc.replace("%topic%", topic)
        tpc += detail

        self.publish_topic(tpc, payload, item, qos, retain, bool_values)

    def interview_all_devices(self):

        """
        Interview known Tasmota Devices (defined in item.yaml and self discovered)
        """

        self.logger.info(f"Interview of all known tasmota devices started.")

        tasmota_device_list = list(set(list(self.tasmota_device + self.discovered_device)))

        for device in tasmota_device_list:
            self.logger.debug(f"Interview {device}.")
            self._interview_device(device)
            self.logger.debug(f"Set Telemetry period for {device}.")
            self._set_telemetry_period(device)

    def clear_retained_messages(self, retained_msg=None):
        """
        Method to clear all retained messages
        """

        if not retained_msg:
            retained_msg = self.topics_of_retained_messages

        for topic in retained_msg:
            try:
                self.logger.warning(f"Clearing retained message for topic={topic}")
                self.publish_topic(topic=topic, payload="", retain=True)
            except Exception as e:
                self.logger.warning(f"Clearing retained message for topic={topic}, caused error {e}")
                pass

    def _interview_device(self, topic: str) -> None:
        """
        ask for status info of each known tasmota_topic

        :param topic:          tasmota Topic
        """

        # self.logger.debug(f"run: publishing 'cmnd/{topic}/Status0'")
        self.publish_tasmota_topic('cmnd', topic, 'Status0', '')

        # self.logger.debug(f"run: publishing 'cmnd/{topic}/State'")
        # self.publish_tasmota_topic('cmnd', topic, 'State', '')

        # self.logger.debug(f"run: publishing 'cmnd/{topic}/Module'")
        # self.publish_tasmota_topic('cmnd', topic, 'Module', '')

    def _set_telemetry_period(self, topic: str) -> None:
        """
        sets telemetry period for given topic/device

        :param topic:          tasmota Topic
        """

        self.logger.info(f"run: Setting telemetry period to {self.telemetry_period} seconds")
        self.publish_tasmota_topic('cmnd', topic, 'teleperiod', self.telemetry_period)

    ############################################################
    #   Helper
    ############################################################

    def _set_item_value(self, tasmota_topic: str, itemtype: str, value, info_topic: str = '') -> None:
        """
        Sets item value

        :param tasmota_topic:   MQTT message payload
        :param itemtype:        itemtype to be set
        :param value:           value to be set
        :param info_topic:      MQTT info_topic
        """

        if tasmota_topic in self.tasmota_devices:

            # create source of item value
            src = f"{tasmota_topic}:{info_topic}" if info_topic != '' else f"{tasmota_topic}"

            if itemtype in self.tasmota_devices[tasmota_topic]['connected_items']:
                # get item to be set
                item = self.tasmota_devices[tasmota_topic]['connected_items'][itemtype]

                tasmota_rf_details = self.get_iattr_value(item.conf, 'tasmota_rf_key')
                if tasmota_rf_details and '=' in tasmota_rf_details:
                    tasmota_rf_key, tasmota_rf_key_param = tasmota_rf_details.split('=')

                    if tasmota_rf_key_param.lower() == 'true':
                        value = True
                    elif tasmota_rf_key_param.lower() == 'false':
                        value = True
                    elif tasmota_rf_key_param.lower() == 'toggle':
                        value = not(item())
                    else:
                        self.logger.warning(f"Paramater of tasmota_rf_key unknown, Need to be True, False, Toggle")
                        return

                # set item value
                self.logger.info(f"{tasmota_topic}: Item '{item.id()}' via itemtype '{itemtype}' set to value '{value}' provided by '{src}'.")
                item(value, self.get_shortname(), src)

            else:
                self.logger.debug(f"{tasmota_topic}: No item for itemtype '{itemtype}' defined to set to '{value}' provided by '{src}'.")
        else:
            self.logger.debug(f"{tasmota_topic} unknown.")

    def _handle_new_discovered_device(self, tasmota_topic):

        self._add_new_device_to_tasmota_devices(tasmota_topic)
        self.tasmota_devices[tasmota_topic]['status'] = 'discovered'
        self._interview_device(tasmota_topic)

    def _add_new_device_to_tasmota_devices(self, tasmota_topic):
        self.tasmota_devices[tasmota_topic] = self._get_device_dict_1_template()
        self.tasmota_devices[tasmota_topic].update(self._get_device_dict_2_template())

    def _set_device_offline(self, tasmota_topic):

        self.tasmota_devices[tasmota_topic]['online'] = False
        self._set_item_value(tasmota_topic, 'item_online', False, 'check_online_status')
        self.logger.info(f"{tasmota_topic} is not online any more - online_timeout={self.tasmota_devices[tasmota_topic]['online_timeout']}, now={datetime.now()}")

        # clean data from dict to show correct status
        self.tasmota_devices[tasmota_topic].update(self._get_device_dict_2_template())

    @staticmethod
    def _rename_discovery_keys(payload: dict) -> dict:

        link = {'ip':    'IP',
                'dn':    'DeviceName',
                'fn':    'FriendlyNames',  # list
                'hn':    'HostName',
                'mac':   'MAC',
                'md':    'Module',
                'ty':    'Tuya',
                'if':    'ifan',
                'ofln':  'LWT-offline',
                'onln':  'LWT-online',
                'state': 'StateText',  # [0..3]
                'sw':    'FirmwareVersion',
                't':     'Topic',
                'ft':    'FullTopic',
                'tp':    'Prefix',
                'rl':    'Relays',    # 0: disabled, 1: relay, 2.. future extension (fan, shutter?)
                'swc':   'SwitchMode',
                'swn':   'SwitchName',
                'btn':   'Buttons',
                'so':    'SetOption',  # needed by HA to map Tasmota devices to HA entities and triggers
                'lk':    'ctrgb',
                'lt_st': 'LightSubtype',
                'sho':   'sho',
                'sht':   'sht',
                'ver':   'ProtocolVersion',
                }

        new_payload = {}
        for k_old in payload:
            k_new = link.get(k_old)
            if k_new:
                new_payload[k_new] = payload[k_old]

        return new_payload

    @staticmethod
    def _get_device_dict_1_template():
        return {'connected_to_item': False,
                'online': False,
                'status': None,
                'connected_items': {},
                'uptime': '-',
                }

    @staticmethod
    def _get_device_dict_2_template():
        return {'lights': {},
                'rf': {},
                'sensors': {},
                'relais': {},
                'zigbee': {},
                'sml': {},
                }

    ############################################################
    #   Zigbee
    ############################################################

    def _poll_zigbee_devices(self, device: str) -> None:
        """
        Polls information of all discovered zigbee devices from dedicated Zigbee bridge

        :param device:          Zigbee bridge, where all Zigbee Devices shall be polled (equal to tasmota_topic)

        """
        self.logger.info(f"_poll_zigbee_devices: Polling information of all discovered Zigbee devices for zigbee_bridge {device}")
        for zigbee_device in self.tasmota_zigbee_devices:
            # self.logger.debug(f"_poll_zigbee_devices: publishing 'cmnd/{device}/ZbStatus3 {zigbee_device}'")
            self.publish_tasmota_topic('cmnd', device, 'ZbStatus3', zigbee_device)

    def _configure_zigbee_bridge_settings(self, device: str) -> None:
        """
        Configures Zigbee Bridge settings

        :param device:          Zigbee bridge to be set to get MQTT Messages in right format")
        """

        self.logger.info(f"_configure_zigbee_bridge_settings: Do settings of ZigbeeBridge {device}")
        bridge_setting_backlog = '; '.join(f"{key} {value}" for key, value in self.ZIGBEE_BRIDGE_DEFAULT_OPTIONS.items())
        self.publish_tasmota_topic('cmnd', device, 'Backlog', bridge_setting_backlog)

    def _request_zigbee_bridge_config(self, device: str) -> None:
        """
        Request Zigbee Bridge configuration

        :param device:          Zigbee bridge to be requested (equal to tasmota_topic)
        """

        self.logger.info(f"_request_zigbee_bridge_config: Request configuration of Zigbee bridge {device}")
        # self.logger.debug(f"_discover_zigbee_bridge: publishing 'cmnd/{device}/ZbConfig'")
        self.publish_tasmota_topic('cmnd', device, 'ZbConfig', '')

    def _discover_zigbee_bridge_devices(self, device: str) -> None:
        """
        Discovers all connected Zigbee devices

        :param device:          Zigbee bridge where connected devices shall be discovered (equal to tasmota_topic)
        """

        self.logger.info(f"_discover_zigbee_bridge_devices: Discover all connected Zigbee devices for ZigbeeBridge {device}")
        self.publish_tasmota_topic('cmnd', device, 'ZbStatus1', '')

    def _handle_retained_message(self, topic: str, retain: bool) -> None:
        """
        check for retained message and handle it

        :param topic:
        :param retain:
        """

        if bool(retain):
            if topic not in self.topics_of_retained_messages:
                self.topics_of_retained_messages.append(topic)
        else:
            if topic in self.topics_of_retained_messages:
                self.topics_of_retained_messages.remove(topic)

    ############################################################
    #   Plugin Properties
    ############################################################

    @property
    def log_level(self):
        return self.logger.getEffectiveLevel()

    @property
    def retained_msg_count(self):
        return self._broker.retained_messages

    @property
    def tasmota_device(self):
        return list(self.tasmota_devices.keys())

    @property
    def has_zigbee(self):
        for tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic]['zigbee']:
                return True
        return False

    @property
    def has_lights(self):
        for tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic]['lights']:
                return True
        return False

    @property
    def has_rf(self):
        for tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic]['rf']:
                return True
        return False

    @property
    def has_relais(self):
        for tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic]['relais']:
                return True
        return False

    @property
    def has_energy_sensor(self):
        for tasmota_topic in self.tasmota_devices:
            if 'ENERGY' in self.tasmota_devices[tasmota_topic]['sensors']:
                return True
        return False

    @property
    def has_env_sensor(self):
        for tasmota_topic in self.tasmota_devices:
            if any([i in self.tasmota_devices[tasmota_topic]['sensors'] for i in self.ENV_SENSOR]):
                return True
        return False

    @property
    def has_ds18b20_sensor(self):
        for tasmota_topic in self.tasmota_devices:
            if 'DS18B20' in self.tasmota_devices[tasmota_topic]['sensors']:
                return True
        return False

    @property
    def has_am2301_sensor(self):
        for tasmota_topic in self.tasmota_devices:
            if 'AM2301' in self.tasmota_devices[tasmota_topic]['sensors']:
                return True
        return False

    @property
    def has_sht3x_sensor(self):
        for tasmota_topic in self.tasmota_devices:
            if 'SHT3X' in self.tasmota_devices[tasmota_topic]['sensors']:
                return True
        return False

    @property
    def has_other_sensor(self):
        for tasmota_topic in self.tasmota_devices:
            for sensor in self.tasmota_devices[tasmota_topic]['sensors']:
                if sensor not in self.SENSORS:
                    return True
        return False

##################################################################
#    Utilities
##################################################################


def _254_to_100(value):
    return int(round(value * 100 / 254, 0))


def _254_to_360(value):
    return int(round(value * 360 / 254, 0))


def _100_to_254(value):
    return int(round(value * 254 / 100, 0))


def _360_to_254(value):
    return int(round(value * 254 / 360, 0))


def _kelvin_to_mired(value):
    """Umrechnung der Farbtemperatur von Kelvin auf "mired scale" (Reziproke Megakelvin)"""
    return int(round(1000000 / value, 0))


def _mired_to_kelvin(value):
    """Umrechnung der Farbtemperatur von "mired scale" (Reziproke Megakelvin) auf Kelvin"""
    return int(round(10000 / int(value), 0)) * 100
