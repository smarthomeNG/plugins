#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2021-      Michael Wenzel              wenzel_michael@web.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  This plugin connect Zigbee2MQTT to SmartHomeNG.
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

from datetime import datetime
import logging
from lib.module import Modules
from lib.model.mqttplugin import *
from lib.item import Items
from lib.utils import Utils

from .webif import WebInterface


class Zigbee2Mqtt(MqttPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.0.0'

    def __init__(self, sh):
        """
        Initalizes the plugin.

        :param sh:  **Deprecated**: The instance of the smarthome object. For SmartHomeNG versions 1.4 and up: **Don't use it**!

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (MqttPlugin)
        super().__init__()
        if not self._init_complete:
            return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.topic_level1 = self.get_parameter_value('base_topic').lower()
        self._cycle = self.get_parameter_value('poll_period')

        # Initialization code goes here
        self.zigbee2mqtt_devices = {}            # to hold device information for web interface; contains data of all found devices
        self.zigbee2mqtt_plugin_devices = {}     # to hold device information for web interface; contains data of all devices addressed in items
        self.zigbee2mqtt_items = []              # to hold item information for web interface; contains list of all items

        # add subscription to get device announces
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', '', '', '', 'dict', callback=self.on_mqtt_announce)
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', 'state', '', '', 'bool', bool_values=['offline', 'online'], callback=self.on_mqtt_announce)
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', 'config', '', '', 'dict', callback=self.on_mqtt_announce)
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', 'config', '+', '', 'dict', callback=self.on_mqtt_announce)
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', 'info', '', '', 'dict', callback=self.on_mqtt_announce)
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', 'info', '#', '', 'dict', callback=self.on_mqtt_announce)
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', 'response', '', '', 'dict', callback=self.on_mqtt_announce)
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', 'response', '#', '', 'dict', callback=self.on_mqtt_announce)
        self.add_zigbee2mqtt_subscription(self.topic_level1, '+', 'log', '', '', 'dict', callback=self.on_mqtt_announce)

        self.local_ip = ''

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        # get local ip
        self.local_ip = Utils.get_local_ipv4_address()
        self.logger.info(f"local ip adress is {self.local_ip}")

        # start subscription to all topics
        self.start_subscriptions()

        self.scheduler_add('poll_bridge', self.poll_bridge, cycle=self._cycle)
        self.publish_zigbee2mqtt_topic(self.topic_level1, 'bridge', 'config', 'devices', 'get', '')

        # restart bridge to get all data by restarting
        # self.publish_zigbee2mqtt_topic(self.topic_level1, 'bridge', 'request', 'restart', '', '')

        self.alive = True
        
        self._get_current_status_of_all_devices_linked_to_items()
        return

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_bridge')

        # stop subscription to all topics
        self.stop_subscriptions()
        return

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
        if self.has_iattr(item.conf, 'zigbee2mqtt_topic'):
            if self.logger.isEnabledFor(logging.DEBUG):
                self.logger.debug(f"parsing item: {item.id()}")

            topic_level2 = self.get_iattr_value(item.conf, 'zigbee2mqtt_topic')
            topic_level2 = self._handle_hex_in_topic_level2(topic_level2, item)
            
            zigbee2mqtt_attr = self.get_iattr_value(item.conf, 'zigbee2mqtt_attr')

            if not self.zigbee2mqtt_plugin_devices.get(topic_level2):
                self.zigbee2mqtt_plugin_devices[topic_level2] = {}
                self.zigbee2mqtt_plugin_devices[topic_level2]['connected_to_item'] = False
                self.zigbee2mqtt_plugin_devices[topic_level2]['connected_items'] = {}

            # handle the different topics from zigbee2mqtt devices
            if zigbee2mqtt_attr:
                zigbee2mqtt_attr = zigbee2mqtt_attr.lower()

            if zigbee2mqtt_attr != '':
                self.zigbee2mqtt_plugin_devices[topic_level2]['connected_to_item'] = True
                self.zigbee2mqtt_plugin_devices[topic_level2]['connected_items']['item_'+zigbee2mqtt_attr] = item
                if zigbee2mqtt_attr == 'online':
                    self.zigbee2mqtt_plugin_devices[topic_level2]['online'] = False
                # append to list used for web interface
                if item not in self.zigbee2mqtt_items:
                    self.zigbee2mqtt_items.append(item)
            else:
                self.logger.warning(f"parse_item: attribute zigbee2mqtt_attr = {zigbee2mqtt_attr} not in valid list; standard attribut used, but item not processed.")
            return self.update_item

    def update_item(self, item, caller=None, source=None, dest=None):
        """
        Item has been updated

        This method is called, if the value of an item has been updated by SmartHomeNG.
        It should write the changed value out to the device (hardware/interface) that
        is managed by this plugin.

        :param item:    item to be updated towards the plugin
        :param caller:  if given it represents the callers name
        :param source:  if given it represents the source
        :param dest:    if given it represents the dest
        """
        if self.logger.isEnabledFor(logging.DEBUG):
            self.logger.debug(f"update_item: {item.id()} called by {caller} and source {source}")

        if self.alive and self.get_shortname() not in caller:
        # code to execute if the plugin is not stopped  AND only, if the item has not been changed for this plugin

            # get zigbee2mqtt attributes of caller item
            topic_level2 = self.get_iattr_value(item.conf, 'zigbee2mqtt_topic')
            topic_level2 = self._handle_hex_in_topic_level2(topic_level2, item)
            
            zigbee2mqtt_attr = self.get_iattr_value(item.conf, 'zigbee2mqtt_attr')

            if zigbee2mqtt_attr in ['bridge_permit_join', 'bridge_health_check', 'bridge_restart', 'bridge_networkmap_raw', 'device_remove', 
                                    'device_ota_update_check', 'device_ota_update_update', 'device_configure', 'device_options', 'device_rename', 
                                    'device_bind', 'device_unbind', 'device_configure_reporting', 'state', 'color_temp', 'brightness', 'hue', 'saturation']:
                
                self.logger.info(f"update_item: {item.id()}, item has been changed in SmartHomeNG outside of this plugin in {caller} with value {item()}")
                payload = None
                bool_values = None
                topic_level3 = topic_level4 = topic_level5 = ''

                if zigbee2mqtt_attr == 'bridge_permit_join':
                    topic_level3 = 'request'
                    topic_level4 = 'permit_join'
                    payload = item()
                    bool_values = ['false', 'true']
                elif zigbee2mqtt_attr == 'bridge_health_check':
                    topic_level3 = 'request'
                    topic_level4 = 'health_check'
                    payload = ''
                elif zigbee2mqtt_attr == 'bridge_restart':
                    topic_level3 = 'request'
                    topic_level4 = 'restart'
                    payload = ''
                elif zigbee2mqtt_attr == 'bridge_networkmap_raw':
                    topic_level3 = 'request'
                    topic_level4 = 'networkmap'
                    payload = 'raw'
                elif zigbee2mqtt_attr == 'device_remove':
                    topic_level3 = 'request'
                    topic_level4 = 'device'
                    topic_level5 = 'remove'
                    payload = str(item())
                # elif zigbee2mqtt_attr == 'device_ota_update_check':
                    # topic_level3 = 'request'
                    # topic_level4 = 'device'
                    # payload = 'raw'
                    # bool_values = None
                # elif zigbee2mqtt_attr == 'device_ota_update_update':
                    # topic_level3 = 'request'
                    # topic_level4 = 'device'
                    # payload = 'raw'
                    # bool_values = None
                elif zigbee2mqtt_attr == 'device_configure':
                    topic_level3 = 'request'
                    topic_level4 = 'device'
                    topic_level5 = 'configure'
                    payload = str(item())
                elif zigbee2mqtt_attr == 'device_options':
                    topic_level3 = 'request'
                    topic_level4 = 'device'
                    topic_level5 = 'options'
                    payload = str(item())
                elif zigbee2mqtt_attr == 'device_rename':
                    topic_level3 = 'request'
                    topic_level4 = 'device'
                    topic_level5 = 'rename'
                    payload = str(item())
                elif zigbee2mqtt_attr == 'state':
                    topic_level3 = 'set'
                    payload = '{' + f'"state" : "{self._bool2str(item(), 1)}"' + '}'
                elif zigbee2mqtt_attr == 'brightness':
                    topic_level3 = 'set'
                    value = int(round(item() * 255 / 100, 0))      # Umrechnung von 0-100% in 0-254
                    if value < 0 or value > 255:
                        self.logger.warning(f'commanded value for brightness not within allowed range; set to next valid value')
                        value = 0 if value < 0 else 255
                    payload = '{' + f'"brightness" : "{value}"' + '}'
                elif zigbee2mqtt_attr == 'color_temp':
                    topic_level3 = 'set'
                    value = int(round(1000000 / item(), 0))
                    # mired scale
                    if value < 150 or value > 500:
                        self.logger.warning(f' commanded value for brightness not within allowed range; set to next valid value')
                        value = 150 if value < 150 else 500
                    payload = '{' + f'"color_temp" : "{value}"' + '}'
                elif zigbee2mqtt_attr == 'hue':
                    topic_level3 = 'set'
                    hue = item()
                    saturation_item = self.zigbee2mqtt_plugin_devices[topic_level2]['connected_items']['item_saturation']
                    saturation = saturation_item()
                    if hue < 0 or hue > 359:
                        self.logger.warning(f'commanded value for hue not within allowed range; set to next valid value')
                        hue = 0 if hue < 0 else 359
                    payload = '{"color":{' + f'"hue":{hue}, "saturation":{saturation}' + '}}'
                elif zigbee2mqtt_attr == 'saturation':
                    topic_level3 = 'set'
                    saturation = item()
                    hue_item = self.zigbee2mqtt_plugin_devices[topic_level2]['connected_items']['item_hue']
                    hue = hue_item()
                    if saturation < 0 or saturation > 100:
                        self.logger.warning(f'commanded value for hue not within allowed range; set to next valid value')
                        saturation = 0 if saturation < 0 else 100
                    payload = '{"color":{' + f'"hue":{hue}, "saturation":{saturation}' + '}}'
                else:
                    self.logger.warning(f"update_item: {item.id()}, attribut {zigbee2mqtt_attr} not implemented yet (by {caller})")

                if payload is not None:
                    self.publish_zigbee2mqtt_topic(self.topic_level1, topic_level2, topic_level3, topic_level4, topic_level5, payload, item, bool_values=bool_values)
                else:
                    self.logger.warning(f"update_item: {item.id()}, no value/payload defined (by {caller})")
            else:
                self.logger.warning(f"update_item: {item.id()}, trying to change item in SmartHomeNG that is readonly (by {caller})")

    def poll_bridge(self):
        """
        Polls for health state of the bridge

        """
        self.logger.info("poll_bridge: Checking online and health status of bridge")
        self.publish_zigbee2mqtt_topic(self.topic_level1, 'bridge', 'request', 'health_check', '', '')

        for topic_level2 in self.zigbee2mqtt_plugin_devices:
            if self.zigbee2mqtt_plugin_devices[topic_level2].get('online') is True and self.zigbee2mqtt_plugin_devices[topic_level2].get('online_timeout') is True:
                if self.zigbee2mqtt_plugin_devices[topic_level2]['online_timeout'] < datetime.now():
                    self.zigbee2mqtt_plugin_devices[topic_level2]['online'] = False
                    self._set_item_value(topic_level2, 'item_online', False, 'poll_device')
                    self.logger.info(f"poll_device: {topic_level2} is not online any more - online_timeout={self.zigbee2mqtt_plugin_devices[topic_level2]['online_timeout']}, now={datetime.now()}")

    def add_zigbee2mqtt_subscription(self, topic_level1, topic_level2, topic_level3, topic_level4, topic_level5, payload_type, bool_values=None, item=None, callback=None):
        """
        build the topic in zigbee2mqtt style and add the subscription to mqtt

        :param topic_level1:    basetopic of topic to subscribe to
        :param topic_level2:    unique part of topic to subscribe to
        :param topic_level3:    level3 of topic to subscribe to
        :param topic_level4:    level4 of topic to subscribe to
        :param topic_level5:    level5 of topic to subscribe to
        :param payload_type:    payload type of the topic (for this subscription to the topic)
        :param bool_values:     bool values (for this subscription to the topic)
        :param item:            item that should receive the payload as value. Used by the standard handler (if no callback function is specified)
        :param callback:        a plugin can provide an own callback function, if special handling of the payload is needed
        :return:                None
        """
        tpc = self._build_topic_str(topic_level1, topic_level2, topic_level3, topic_level4, topic_level5)
        self.add_subscription(tpc, payload_type, bool_values=bool_values, callback=callback)

    def publish_zigbee2mqtt_topic(self, topic_level1, topic_level2, topic_level3, topic_level4, topic_level5, payload, item=None, qos=None, retain=False, bool_values=None):
        """
        build the topic in zigbee2mqtt style and publish to mqtt

        :param topic_level1:    basetopic of topic to publish
        :param topic_level2:    unique part of topic to publish; ZigbeeDevice
        :param topic_level3:    level3 of topic to publish
        :param topic_level4:    level4 of topic to publish
        :param topic_level5:    level5 of topic to publish
        :param payload:         payload to publish
        :param item:            item (if relevant)
        :param qos:             qos for this message (optional)
        :param retain:          retain flag for this message (optional)
        :param bool_values:     bool values (for publishing this topic, optional)
        :return:                None    
        """
        tpc = self._build_topic_str(topic_level1, topic_level2, topic_level3, topic_level4, topic_level5)
        # self.logger.debug(f"Publish to topic <{tpc}> with payload <{payload}>")
        self.publish_topic(tpc, payload, item, qos, retain, bool_values)

    def on_mqtt_announce(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:           mqtt topic
        :param payload:         mqtt message payload
        :param qos:             qos for this message (optional)
        :param retain:          retain flag for this message (optional)
        """
        wrk = topic.split('/')
        topic_level1 = wrk[0]
        topic_level2 = wrk[1]
        topic_level3 = ''
        topic_level4 = ''
        topic_level5 = ''
        if len(wrk) > 2:
            topic_level3 = wrk[2]
            if len(wrk) > 3:
                topic_level4 = wrk[3]
                if len(wrk) > 4:
                    topic_level5 = wrk[4]
        
        if self.logger.isEnabledFor(logging.DEBUG):
            debug_logger = True
        else:
            debug_logger = False
        
        if debug_logger is True:
            self.logger.debug(f"on_mqtt_announce: topic_level1={topic_level1}, topic_level2={topic_level2}, topic_level3={topic_level3}, topic_level4={topic_level4}, topic_level5={topic_level5}, payload={payload}")

        # handle different received mqtt messages
        if topic_level2 == 'bridge':
            if topic_level3 == 'state':
                # Payloads are 'online' and 'offline'; equal to LWT
                self.logger.debug(f"LWT: detail: {topic_level3} datetime: {datetime.now()} payload: {payload}")
                self.zigbee2mqtt_plugin_devices[topic_level2]['online'] = bool(payload)
            elif topic_level3 == 'response':
                if topic_level4 == 'health_check':
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=response, topic_level4=health_check, topic_level5=, payload={'data': {'healthy': True}, 'status': 'ok'}
                    if type(payload) is dict:
                        self.zigbee2mqtt_plugin_devices[topic_level2]['health_status'] = payload
                        self.zigbee2mqtt_plugin_devices[topic_level2]['online'] = bool(payload['data']['healthy'])
                    else:
                        if debug_logger is True:
                            self.logger.debug(f"(Received payload {payload} on topic {topic} is not of type dict")
                elif topic_level4 == 'permit_join':
                    # {"data":{"value":true},"status":"ok"}
                    if type(payload) is dict:
                        self.zigbee2mqtt_plugin_devices[topic_level2]['permit_join'] = payload
                        self.zigbee2mqtt_plugin_devices[topic_level2]['online'] = True
                    else:
                        if debug_logger is True:
                            self.logger.debug(f"(Received payload {payload} on topic {topic} is not of type dict")
                elif topic_level4 == 'networkmap':
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=None, topic_level4=networkmap, topic_level5=None, payload={'data': {'routes': False, 'type': 'raw', 'value': {'links': [{'depth': 1, 'linkquality': 5, 'lqi': 5, 'relationship': 1, 'routes': [], 'source': {'ieeeAddr': '0x588e81fffe28dec5', 'networkAddress': 39405}, 'sourceIeeeAddr': '0x588e81fffe28dec5', 'sourceNwkAddr': 39405, 'target': {'ieeeAddr': '0x00124b001cd4bbf0', 'networkAddress': 0}, 'targetIeeeAddr': '0x00124b001cd4bbf0'}, {'depth': 1, 'linkquality': 155, 'lqi': 155, 'relationship': 1, 'routes': [], 'source': {'ieeeAddr': '0x00124b00231e45b8', 'networkAddress': 18841}, 'sourceIeeeAddr': '0x00124b00231e45b8', 'sourceNwkAddr': 18841, 'target': {'ieeeAddr': '0x00124b001cd4bbf0', 'networkAddress': 0}, 'targetIeeeAddr': '0x00124b001cd4bbf0'}, {'depth': 1, 'linkquality': 1, 'lqi': 1, 'relationship': 1, 'routes': [], 'source': {'ieeeAddr': '0x00158d00067a0c2d', 'networkAddress': 60244}, 'sourceIeeeAddr': '0x00158d00067a0c2d', 'sourceNwkAddr': 60244, 'target': {'ieeeAddr': '0x00124b001cd4bbf0', 'networkAddress': 0}, 'targetIeeeAddr': '0x00124b001cd4bbf0'}], 'nodes': [{'definition': None, 'failed': [], 'friendlyName': 'Coordinator', 'ieeeAddr': '0x00124b001cd4bbf0', 'lastSeen': None, 'networkAddress': 0, 'type': 'Coordinator'}, {'definition': {'description': 'TRADFRI open/close remote', 'model': 'E1766', 'supports': 'battery, action, linkquality', 'vendor': 'IKEA'}, 'friendlyName': 'TRADFRI E1766_01', 'ieeeAddr': '0x588e81fffe28dec5', 'lastSeen': 1618408062253, 'manufacturerName': 'IKEA of Sweden', 'modelID': 'TRADFRI open/close remote', 'networkAddress': 39405, 'type': 'EndDevice'}, {'definition': {'description': 'Temperature and humidity sensor', 'model': 'SNZB-02', 'supports': 'battery, temperature, humidity, voltage, linkquality', 'vendor': 'SONOFF'}, 'friendlyName': 'SNZB02_01', 'ieeeAddr': '0x00124b00231e45b8', 'lastSeen': 1618407530272, 'manufacturerName': 'eWeLink', 'modelID': 'TH01', 'networkAddress': 18841, 'type': 'EndDevice'}, {'definition': {'description': 'Aqara vibration sensor', 'model': 'DJT11LM', 'supports': 'battery, action, strength, sensitivity, voltage, linkquality', 'vendor': 'Xiaomi'}, 'friendlyName': 'DJT11LM_01', 'ieeeAddr': '0x00158d00067a0c2d', 'lastSeen': 1618383303863, 'manufacturerName': 'LUMI', 'modelID': 'lumi.vibration.aq1', 'networkAddress': 60244, 'type': 'EndDevice'}]}}, 'status': 'ok', 'transaction': 'q15of-1'}
                    if type(payload) is dict:
                        self.zigbee2mqtt_plugin_devices[topic_level2]['networkmap'] = payload
                        self.zigbee2mqtt_plugin_devices[topic_level2]['online'] = True
                    else:
                        if debug_logger is True:
                            self.logger.debug(f"(Received payload {payload} on topic {topic} is not of type dict")
            
            elif topic_level3 == 'config':
                if topic_level4 == '':
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=config, topic_level4=, topic_level5=, payload={'commit': 'abd8a09', 'coordinator': {'meta': {'maintrel': 3, 'majorrel': 2, 'minorrel': 6, 'product': 0, 'revision': 20201127, 'transportrev': 2}, 'type': 'zStack12'}, 'log_level': 'info', 'network': {'channel': 11, 'extendedPanID': '0xdddddddddddddddd', 'panID': 6754}, 'permit_join': False, 'version': '1.18.2'}
                    if type(payload) is dict:
                        self.zigbee2mqtt_plugin_devices[topic_level2]['config'] = payload
                    else:
                        if debug_logger is True:
                            self.logger.debug(f"(Received payload {payload} on topic {topic} is not of type dict")

                elif topic_level4 == 'devices':
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=config, topic_level4=devices, topic_level5=, payload=[{'dateCode': '20201127', 'friendly_name': 'Coordinator', 'ieeeAddr': '0x00124b001cd4bbf0', 'lastSeen': 1618861562211, 'networkAddress': 0, 'softwareBuildID': 'zStack12', 'type': 'Coordinator'}, {'dateCode': '20190311', 'description': 'TRADFRI open/close remote', 'friendly_name': 'TRADFRI E1766_01', 'hardwareVersion': 1, 'ieeeAddr': '0x588e81fffe28dec5', 'lastSeen': 1618511300581, 'manufacturerID': 4476, 'manufacturerName': 'IKEA of Sweden', 'model': 'E1766', 'modelID': 'TRADFRI open/close remote', 'networkAddress': 39405, 'powerSource': 'Battery', 'softwareBuildID': '2.2.010', 'type': 'EndDevice', 'vendor': 'IKEA'}, {'dateCode': '20201026', 'description': 'Temperature and humidity sensor', 'friendly_name': 'SNZB02_01', 'hardwareVersion': 1, 'ieeeAddr': '0x00124b00231e45b8', 'lastSeen': 1618861025534, 'manufacturerID': 0, 'manufacturerName': 'eWeLink', 'model': 'SNZB-02', 'modelID': 'TH01', 'networkAddress': 18841, 'powerSource': 'Battery', 'type': 'EndDevice', 'vendor': 'SONOFF'}, {'description': 'Aqara vibration sensor', 'friendly_name': 'DJT11LM_01', 'ieeeAddr': '0x00158d00067a0c2d', 'lastSeen': 1618383303863, 'manufacturerID': 4151, 'manufacturerName': 'LUMI', 'model': 'DJT11LM', 'modelID': 'lumi.vibration.aq1', 'networkAddress': 60244, 'powerSource': 'Battery', 'type': 'EndDevice', 'vendor': 'Xiaomi'}]
                    if type(payload) is list:
                        self._get_zigbee_meta_data(payload)
            
            elif topic_level3 == 'log':
                if topic_level4 == '':
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=log, topic_level4=, topic_level5=, payload={"message":[{"dateCode":"20201127","friendly_name":"Coordinator","ieeeAddr":"0x00124b001cd4bbf0","lastSeen":1617961599543,"networkAddress":0,"softwareBuildID":"zStack12","type":"Coordinator"},{"dateCode":"20190311","description":"TRADFRI open/close remote","friendly_name":"TRADFRI E1766_01","hardwareVersion":1,"ieeeAddr":"0x588e81fffe28dec5","lastSeen":1617873345111,"manufacturerID":4476,"manufacturerName":"IKEA of Sweden","model":"E1766","modelID":"TRADFRI open/close remote","networkAddress":39405,"powerSource":"Battery","softwareBuildID":"2.2.010","type":"EndDevice","vendor":"IKEA"},{"dateCode":"20201026","description":"Temperature and humidity sensor","friendly_name":"SNZB02_01","hardwareVersion":1,"ieeeAddr":"0x00124b00231e45b8","lastSeen":1617961176234,"manufacturerID":0,"manufacturerName":"eWeLink","model":"SNZB-02","modelID":"TH01","networkAddress":18841,"powerSource":"Battery","type":"EndDevice","vendor":"SONOFF"}],"type":"devices"}'
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=log, topic_level4=, topic_level5=, payload={'message': {'friendly_name': '0x00158d00067a0c2d'}, 'type': 'device_connected'}
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=log, topic_level4=, topic_level5=, payload={'message': 'Publish \'set\' \'sensitivity\' to \'DJT11LM_01\' failed: \'Error: Write 0x00158d00067a0c2d/1 genBasic({"65293":{"value":21,"type":32}}, {"timeout":35000,"disableResponse":false,"disableRecovery":false,"disableDefaultResponse":true,"direction":0,"srcEndpoint":null,"reservedBits":0,"manufacturerCode":4447,"transactionSequenceNumber":null,"writeUndiv":false}) failed (Data request failed with error: \'MAC transaction expired\' (240))\'', 'meta': {'friendly_name': 'DJT11LM_01'}, 'type': 'zigbee_publish_error'}
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=log, topic_level4=, topic_level5=, payload={'message': 'announce', 'meta': {'friendly_name': 'DJT11LM_01'}, 'type': 'device_announced'}
                    # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=log, topic_level4=, topic_level5=, payload={'message': {'cluster': 'genOnOff', 'from': 'TRADFRI E1766_01', 'to': 'default_bind_group'}, 'type': 'device_bind_failed'}
                    if type(payload) is dict and 'message' in payload:
                        payload = payload['message']
                        if type(payload) is list:
                            self._get_zigbee_meta_data(payload)
            elif topic_level3 == 'info':
                # topic_level1=zigbee2mqtt, topic_level2=bridge, topic_level3=info, topic_level4=, topic_level5=, payload={'commit': 'abd8a09', 'config': {'advanced': {'adapter_concurrent': None, 'adapter_delay': None, 'availability_blacklist': [], 'availability_blocklist': [], 'availability_passlist': [], 'availability_timeout': 0, 'availability_whitelist': [], 'cache_state': True, 'cache_state_persistent': True, 'cache_state_send_on_startup': True, 'channel': 11, 'elapsed': False, 'ext_pan_id': [221, 221, 221, 221, 221, 221, 221, 221], 'homeassistant_discovery_topic': 'homeassistant', 'homeassistant_legacy_triggers': True, 'homeassistant_status_topic': 'hass/status', 'last_seen': 'disable', 'legacy_api': True, 'log_directory': '/opt/zigbee2mqtt/data/log/%TIMESTAMP%', 'log_file': 'log.txt', 'log_level': 'info', 'log_output': ['console', 'file'], 'log_rotation': True, 'log_syslog': {}, 'pan_id': 6754, 'report': False, 'soft_reset_timeout': 0, 'timestamp_format': 'YYYY-MM-DD HH:mm:ss'}, 'ban': [], 'blocklist': [], 'device_options': {}, 'devices': {'0x00124b00231e45b8': {'friendly_name': 'SNZB02_01'}, '0x00158d00067a0c2d': {'friendly_name': 'DJT11LM_01'}, '0x588e81fffe28dec5': {'friendly_name': 'TRADFRI E1766_01'}}, 'experimental': {'output': 'json'}, 'external_converters': [], 'frontend': {'host': '0.0.0.0', 'port': 8082}, 'groups': {}, 'homeassistant': False, 'map_options': {'graphviz': {'colors': {'fill': {'coordinator': '#e04e5d', 'enddevice': '#fff8ce', 'router': '#4ea3e0'}, 'font': {'coordinator': '#ffffff', 'enddevice': '#000000', 'router': '#ffffff'}, 'line': {'active': '#009900', 'inactive': '#994444'}}}}, 'mqtt': {'base_topic': 'zigbee2mqtt', 'force_disable_retain': False, 'include_device_information': True, 'keepalive': 60, 'reject_unauthorized': True, 'server': 'mqtt://localhost:1883', 'version': 4}, 'ota': {'disable_automatic_update_check': True, 'update_check_interval': 1440}, 'passlist': [], 'permit_join': False, 'serial': {'disable_led': False, 'port': '/dev/ttyACM0'}, 'whitelist': []}, 'config_schema': {'definitions': {'device': {'properties': {'debounce': {'description': 'Debounces messages of this device', 'title': 'Debounce', 'type': 'number'}, 'debounce_ignore': {'description': 'Protects unique payload values of specified payload properties from overriding within debounce time', 'examples': ['action'], 'items': {'type': 'string'}, 'title': 'Ignore debounce', 'type': 'array'}, 'filtered_attributes': {'description': 'Allows to prevent certain attributes from being published', 'examples': ['temperature', 'battery', 'action'], 'items': {'type': 'string'}, 'title': 'Filtered attributes', 'type': 'array'}, 'friendly_name': {'description': 'Used in the MQTT topic of a device. By default this is the device ID', 'readOnly': True, 'title': 'Friendly name', 'type': 'string'}, 'optimistic': {'description': 'Publish optimistic state after set (default true)', 'title': 'Optimistic', 'type': 'boolean'}, 'qos': {'descritption': 'QoS level for MQTT messages of this device', 'title': 'QoS', 'type': 'number'}, 'retain': {'description': 'Retain MQTT messages of this device', 'title': 'Retain', 'type': 'boolean'}, 'retention': {'description': 'Sets the MQTT Message Expiry in seconds, Make sure to set mqtt.version to 5', 'title': 'Retention', 'type': 'number'}}, 'required': ['friendly_name'], 'type': 'object'}, 'group': {'properties': {'devices': {'items': {'type': 'string'}, 'type': 'array'}, 'filtered_attributes': {'items': {'type': 'string'}, 'type': 'array'}, 'friendly_name': {'type': 'string'}, 'optimistic': {'type': 'boolean'}, 'qos': {'type': 'number'}, 'retain': {'type': 'boolean'}}, 'required': ['friendly_name'], 'type': 'object'}}, 'properties': {'advanced': {'properties': {'adapter_concurrent': {'description': 'Adapter concurrency (e.g. 2 for CC2531 or 16 for CC26X2R1) (default: null, uses recommended value)', 'requiresRestart': True, 'title': 'Adapter concurrency', 'type': ['number', 'null']}, 'adapter_delay': {'description': 'Adapter delay', 'requiresRestart': True, 'title': 'Adapter delay', 'type': ['number', 'null']}, 'availability_blacklist': {'items': {'type': 'string'}, 'readOnly': True, 'requiresRestart': True, 'title': 'Availability blacklist (deprecated, use availability_blocklist)', 'type': 'array'}, 'availability_blocklist': {'description': 'Prevent devices from being checked for availability', 'items': {'type': 'string'}, 'requiresRestart': True, 'title': 'Availability Blocklist', 'type': 'array'}, 'availability_passlist': {'description': 'Only enable availability check for certain devices', 'items': {'type': 'string'}, 'requiresRestart': True, 'title': 'Availability passlist', 'type': 'array'}, 'availability_timeout': {'default': 0, 'description': 'Availability timeout in seconds when enabled, devices will be checked if they are still online. Only AC powered routers are checked for availability', 'minimum': 0, 'requiresRestart': True, 'title': 'Availability Timeout', 'type': 'number'}, 'availability_whitelist': {'items': {'type': 'string'}, 'readOnly': True, 'requiresRestart': True, 'title': 'Availability whitelist (deprecated, use passlist)', 'type': 'array'}, 'baudrate': {'description': 'Baudrate for serial port, default: 115200 for Z-Stack, 38400 for Deconz', 'examples': [38400, 115200], 'requiresRestart': True, 'title': 'Baudrate', 'type': 'number'}, 'cache_state': {'default': True, 'description': 'MQTT message payload will contain all attributes, not only changed ones. Has to be true when integrating via Home Assistant', 'title': 'Cache state', 'type': 'boolean'}, 'cache_state_persistent': {'default': True, 'description': 'Persist cached state, only used when cache_state: true', 'title': 'Persist cache state', 'type': 'boolean'}, 'cache_state_send_on_startup': {'default': True, 'description': 'Send cached state on startup, only used when cache_state: true', 'title': 'Send cached state on startup', 'type': 'boolean'}, 'channel': {'default': 11, 'description': 'Zigbee channel, changing requires repairing all devices! (Note: use a ZLL channel: 11, 15, 20, or 25 to avoid Problems)', 'examples': [11, 15, 20, 25], 'maximum': 26, 'minimum': 11, 'requiresRestart': True, 'title': 'ZigBee channel', 'type': 'number'}, 'elapsed': {'default': False, 'description': 'Add an elapsed attribute to MQTT messages, contains milliseconds since the previous msg', 'title': 'Elapsed', 'type': 'boolean'}, 'ext_pan_id': {'description': 'Zigbee extended pan ID, changing requires repairing all devices!', 'items': {'type': 'number'}, 'requiresRestart': True, 'title': 'Ext Pan ID', 'type': 'array'}, 'homeassistant_discovery_topic': {'description': 'Home Assistant discovery topic', 'examples': ['homeassistant'], 'requiresRestart': True, 'title': 'Homeassistant discovery topic', 'type': 'string'}, 'homeassistant_legacy_triggers': {'default': True, 'description': "Home Assistant legacy triggers, when enabled Zigbee2mqt will send an empty 'action' or 'click' after one has been send. A 'sensor_action' and 'sensor_click' will be discoverd", 'title': 'Home Assistant legacy triggers', 'type': 'boolean'}, 'homeassistant_status_topic': {'description': 'Home Assistant status topic', 'examples': ['homeassistant/status'], 'requiresRestart': True, 'title': 'Home Assistant status topic', 'type': 'string'}, 'ikea_ota_use_test_url': {'default': False, 'description': 'Use IKEA TRADFRI OTA test server, see OTA updates documentation', 'requiresRestart': True, 'title': 'IKEA TRADFRI OTA use test url', 'type': 'boolean'}, 'last_seen': {'default': 'disable', 'description': 'Add a last_seen attribute to MQTT messages, contains date/time of last Zigbee message', 'enum': ['disable', 'ISO_8601', 'ISO_8601_local', 'epoch'], 'title': 'Last seen', 'type': 'string'}, 'legacy_api': {'default': True, 'description': 'Disables the legacy api (false = disable)', 'requiresRestart': True, 'title': 'Legacy API', 'type': 'boolean'}, 'log_directory': {'description': 'Location of log directory', 'examples': ['data/log/%TIMESTAMP%'], 'requiresRestart': True, 'title': 'Log directory', 'type': 'string'}, 'log_file': {'default': 'log.txt', 'description': 'Log file name, can also contain timestamp', 'examples': ['zigbee2mqtt_%TIMESTAMP%.log'], 'requiresRestart': True, 'title': 'Log file', 'type': 'string'}, 'log_level': {'default': 'info', 'description': 'Logging level', 'enum': ['info', 'warn', 'error', 'debug'], 'title': 'Log level', 'type': 'string'}, 'log_output': {'description': 'Output location of the log, leave empty to supress logging', 'items': {'enum': ['console', 'file', 'syslog'], 'type': 'string'}, 'requiresRestart': True, 'title': 'Log output', 'type': 'array'}, 'log_rotation': {'default': True, 'description': 'Log rotation', 'requiresRestart': True, 'title': 'Log rotation', 'type': 'boolean'}, 'log_syslog': {'properties': {'app_name': {'default': 'Zigbee2MQTT', 'description': 'The name of the application (Default: Zigbee2MQTT).', 'title': 'Localhost', 'type': 'string'}, 'eol': {'default': '/n', 'description': 'The end of line character to be added to the end of the message (Default: Message without modifications).', 'title': 'eol', 'type': 'string'}, 'host': {'default': 'localhost', 'description': 'The host running syslogd, defaults to localhost.', 'title': 'Host', 'type': 'string'}, 'localhost': {'default': 'localhost', 'description': 'Host to indicate that log messages are coming from (Default: localhost).', 'title': 'Localhost', 'type': 'string'}, 'path': {'default': '/dev/log', 'description': 'The path to the syslog dgram socket (i.e. /dev/log or /var/run/syslog for OS X).', 'examples': ['/dev/log', '/var/run/syslog'], 'title': 'Path', 'type': 'string'}, 'pid': {'default': 'process.pid', 'description': 'PID of the process that log messages are coming from (Default process.pid).', 'title': 'PID', 'type': 'string'}, 'port': {'default': 123, 'description': "The port on the host that syslog is running on, defaults to syslogd's default port.", 'title': 'Port', 'type': 'number'}, 'protocol': {'default': 'tcp4', 'description': 'The network protocol to log over (e.g. tcp4, udp4, tls4, unix, unix-connect, etc).', 'examples': ['tcp4', 'udp4', 'tls4', 'unix', 'unix-connect'], 'title': 'Protocol', 'type': 'string'}, 'type': {'default': '5424', 'description': 'The type of the syslog protocol to use (Default: BSD, also valid: 5424).', 'title': 'Type', 'type': 'string'}}, 'title': 'syslog', 'type': 'object'}, 'network_key': {'description': 'Network encryption key, changing requires repairing all devices!', 'oneOf': [{'title': 'Network key(string)', 'type': 'string'}, {'items': {'type': 'number'}, 'title': 'Network key(array)', 'type': 'array'}], 'requiresRestart': True, 'title': 'Network key'}, 'pan_id': {'description': 'ZigBee pan ID, changing requires repairing all devices!', 'oneOf': [{'title': 'Pan ID (string)', 'type': 'string'}, {'title': 'Pan ID (number)', 'type': 'number'}], 'requiresRestart': True, 'title': 'Pan ID'}, 'report': {'description': 'Enables report feature (deprecated)', 'readOnly': True, 'requiresRestart': True, 'title': 'Reporting', 'type': 'boolean'}, 'rtscts': {'description': 'RTS / CTS Hardware Flow Control for serial port', 'requiresRestart': True, 'title': 'RTS / CTS', 'type': 'boolean'}, 'soft_reset_timeout': {'description': 'Soft reset ZNP after timeout', 'minimum': 0, 'readOnly': True, 'requiresRestart': True, 'title': 'Soft reset timeout (deprecated)', 'type': 'number'}, 'timestamp_format': {'description': 'Log timestamp format', 'examples': ['YYYY-MM-DD HH:mm:ss'], 'requiresRestart': True, 'title': 'Timestamp format', 'type': 'string'}}, 'title': 'Advanced', 'type': 'object'}, 'ban': {'items': {'type': 'string'}, 'readOnly': True, 'requiresRestart': True, 'title': 'Ban (deprecated, use blocklist)', 'type': 'array'}, 'blocklist': {'description': 'Block devices from the network (by ieeeAddr)', 'items': {'type': 'string'}, 'requiresRestart': True, 'title': 'Blocklist', 'type': 'array'}, 'device_options': {'type': 'object'}, 'devices': {'patternProperties': {'^.*$': {'$ref': '#/definitions/device'}}, 'propertyNames': {'pattern': '^0x[\\d\\w]{16}$'}, 'type': 'object'}, 'experimental': {'properties': {'output': {'description': 'Examples when \'state\' of a device is published json: topic: \'zigbee2mqtt/my_bulb\' payload \'{"state": "ON"}\' attribute: topic \'zigbee2mqtt/my_bulb/state\' payload \'ON\' attribute_and_json: both json and attribute (see above)', 'enum': ['attribute_and_json', 'attribute', 'json'], 'title': 'MQTT output type', 'type': 'string'}, 'transmit_power': {'description': 'Transmit power of adapter, only available for Z-Stack (CC253*/CC2652/CC1352) adapters, CC2652 = 5dbm, CC1352 max is = 20dbm (5dbm default)', 'requiresRestart': True, 'title': 'Transmit power', 'type': ['number', 'null']}}, 'title': 'Experimental', 'type': 'object'}, 'external_converters': {'description': 'You can define external converters to e.g. add support for a DiY device', 'examples': ['DIYRuZ_FreePad.js'], 'items': {'type': 'string'}, 'requiresRestart': True, 'title': 'External converters', 'type': 'array'}, 'frontend': {'properties': {'auth_token': {'description': 'Enables authentication, disabled by default', 'requiresRestart': True, 'title': 'Auth token', 'type': ['string', 'null']}, 'host': {'default': ' 0.0.0.0', 'description': 'Frontend binding host', 'requiresRestart': True, 'title': 'Bind host', 'type': 'string'}, 'port': {'default': 8080, 'description': 'Frontend binding port', 'requiresRestart': True, 'title': 'Port', 'type': 'number'}}, 'title': 'Frontend', 'type': 'object'}, 'groups': {'patternProperties': {'^.*$': {'$ref': '#/definitions/group'}}, 'propertyNames': {'pattern': '^[\\w].*$'}, 'type': 'object'}, 'homeassistant': {'default': False, 'description': 'Home Assistant integration (MQTT discovery)', 'title': 'Home Assistant integration', 'type': 'boolean'}, 'map_options': {'properties': {'graphviz': {'properties': {'colors': {'properties': {'fill': {'properties': {'coordinator': {'type': 'string'}, 'enddevice': {'type': 'string'}, 'router': {'type': 'string'}}, 'type': 'object'}, 'font': {'properties': {'coordinator': {'type': 'string'}, 'enddevice': {'type': 'string'}, 'router': {'type': 'string'}}, 'type': 'object'}, 'line': {'properties': {'active': {'type': 'string'}, 'inactive': {'type': 'string'}}, 'type': 'object'}}, 'type': 'object'}}, 'type': 'object'}}, 'title': 'Networkmap', 'type': 'object'}, 'mqtt': {'properties': {'base_topic': {'description': 'MQTT base topic for Zigbee2MQTT MQTT messages', 'examples': ['zigbee2mqtt'], 'requiresRestart': True, 'title': 'Base topic', 'type': 'string'}, 'ca': {'description': 'Absolute path to SSL/TLS certificate of CA used to sign server and client certificates', 'examples': ['/etc/ssl/mqtt-ca.crt'], 'requiresRestart': True, 'title': 'Certificate authority', 'type': 'string'}, 'cert': {'description': 'Absolute path to SSL/TLS certificate for client-authentication', 'examples': ['/etc/ssl/mqtt-client.crt'], 'requiresRestart': True, 'title': 'SSL/TLS certificate', 'type': 'string'}, 'client_id': {'description': 'MQTT client ID', 'examples': ['MY_CLIENT_ID'], 'requiresRestart': True, 'title': 'Client ID', 'type': 'string'}, 'force_disable_retain': {'default': False, 'description': "Disable retain for all send messages. ONLY enable if you MQTT broker doesn't support retained message (e.g. AWS IoT core, Azure IoT Hub, Google Cloud IoT core, IBM Watson IoT Platform). Enabling will break the Home Assistant integration", 'requiresRestart': True, 'title': 'Force disable retain', 'type': 'boolean'}, 'include_device_information': {'default': False, 'description': 'Include device information to mqtt messages', 'title': 'Include device information', 'type': 'boolean'}, 'keepalive': {'default': 60, 'description': 'MQTT keepalive in second', 'requiresRestart': True, 'title': 'Keepalive', 'type': 'number'}, 'key': {'description': 'Absolute path to SSL/TLS key for client-authentication', 'examples': ['/etc/ssl/mqtt-client.key'], 'requiresRestart': True, 'title': 'SSL/TLS key', 'type': 'string'}, 'password': {'description': 'MQTT server authentication password', 'examples': ['ILOVEPELMENI'], 'requiresRestart': True, 'title': 'Password', 'type': 'string'}, 'reject_unauthorized': {'default': True, 'description': 'Disable self-signed SSL certificate', 'requiresRestart': True, 'title': 'Reject unauthorized', 'type': 'boolean'}, 'server': {'description': 'MQTT server URL (use mqtts:// for SSL/TLS connection)', 'examples': ['mqtt://localhost:1883'], 'requiresRestart': True, 'title': 'MQTT server', 'type': 'string'}, 'user': {'description': 'MQTT server authentication user', 'examples': ['johnnysilverhand'], 'requiresRestart': True, 'title': 'User', 'type': 'string'}, 'version': {'default': 4, 'description': 'MQTT protocol version', 'examples': [4, 5], 'requiresRestart': True, 'title': 'Version', 'type': ['number', 'null']}}, 'required': ['base_topic', 'server'], 'title': 'MQTT', 'type': 'object'}, 'ota': {'properties': {'disable_automatic_update_check': {'default': False, 'description': 'Zigbee devices may request a firmware update, and do so frequently, causing Zigbee2MQTT to reach out to third party servers. If you disable these device initiated checks, you can still initiate a firmware update check manually.', 'title': 'Disable automatic update check', 'type': 'boolean'}, 'update_check_interval': {'default': 1440, 'description': 'Your device may request a check for a new firmware update. This value determines how frequently third party servers may actually be contacted to look for firmware updates. The value is set in minutes, and the default is 1 day.', 'title': 'Update check interval', 'type': 'number'}}, 'title': 'OTA updates', 'type': 'object'}, 'passlist': {'description': 'Allow only certain devices to join the network (by ieeeAddr). Note that all devices not on the passlist will be removed from the network!', 'items': {'type': 'string'}, 'requiresRestart': True, 'title': 'Passlist', 'type': 'array'}, 'permit_join': {'default': False, 'description': 'Allow new devices to join (re-applied at restart)', 'title': 'Permit join', 'type': 'boolean'}, 'serial': {'properties': {'adapter': {'description': 'Adapter type, not needed unless you are experiencing problems', 'enum': ['deconz', 'zstack', 'zigate', 'ezsp'], 'requiresRestart': True, 'title': 'Adapter', 'type': ['string', 'null']}, 'disable_led': {'default': False, 'description': 'Disable LED of the adapter if supported', 'requiresRestart': True, 'title': 'Disable led', 'type': 'boolean'}, 'port': {'description': 'Location of the adapter. To autodetect the port, set null', 'examples': ['/dev/ttyACM0'], 'requiresRestart': True, 'title': 'Port', 'type': ['string', 'null']}}, 'title': 'Serial', 'type': 'object'}, 'whitelist': {'items': {'type': 'string'}, 'readOnly': True, 'requiresRestart': True, 'title': 'Whitelist (deprecated, use passlist)', 'type': 'array'}}, 'required': ['mqtt'], 'type': 'object'}, 'coordinator': {'meta': {'maintrel': 3, 'majorrel': 2, 'minorrel': 6, 'product': 0, 'revision': 20201127, 'transportrev': 2}, 'type': 'zStack12'}, 'log_level': 'info', 'network': {'channel': 11, 'extended_pan_id': '0xdddddddddddddddd', 'pan_id': 6754}, 'permit_join': False, 'restart_required': False, 'version': '1.18.2'}
                if topic_level4 == '':
                    if type(payload) is dict:
                        self.zigbee2mqtt_plugin_devices[topic_level2]['info'] = payload
                        self.zigbee2mqtt_plugin_devices[topic_level2]['online'] = True
                    else:
                        if debug_logger is True:
                            self.logger.debug(f"(Received payload {payload} on topic {topic} is not of type dict")
            
            elif topic_level3 == 'event':
                # {"type":"device_joined","data":{"friendly_name":"0x90fd9ffffe6494fc","ieee_address":"0x90fd9ffffe6494fc"}}
                # {"type":"device_announce","data":{"friendly_name":"0x90fd9ffffe6494fc","ieee_address":"0x90fd9ffffe6494fc"}}
                # {"type":"device_interview","data":{"friendly_name":"0x90fd9ffffe6494fc","status":"started","ieee_address":"0x90fd9ffffe6494fc"}}
                # {"type":"device_interview","data":{"friendly_name":"0x90fd9ffffe6494fc","status":"successful","ieee_address":"0x90fd9ffffe6494fc","supported":true,"definition":{"model":"LED1624G9","vendor":"IKEA","description":"TRADFRI LED bulb E14/E26/E27 600 lumen, dimmable, color, opal white"}}}
                # {"type":"device_interview","data":{"friendly_name":"0x90fd9ffffe6494fc","status":"failed","ieee_address":"0x90fd9ffffe6494fc"}}
                # {"type":"device_leave","data":{"ieee_address":"0x90fd9ffffe6494fc"}}
                if topic_level4 == '':
                    event_type = payload.get('type')
                    if debug_logger is True:
                        self.logger.debug(f"event info message not implemented yet.")
            
            else:
                if debug_logger is True:
                    self.logger.debug(f"Function type message not implemented yet.")
        
        elif (topic_level3 + topic_level4 + topic_level5) == '':
            # topic_level1=zigbee2mqtt, topic_level2=SNZB02_01, topic_level3=, topic_level4=, topic_level5=, payload '{"battery":100,"device":{"applicationVersion":5,"dateCode":"20201026","friendlyName":"SNZB02_01","hardwareVersion":1,"ieeeAddr":"0x00124b00231e45b8","manufacturerID":0,"manufacturerName":"eWeLink","model":"SNZB-02","networkAddress":18841,"powerSource":"Battery","type":"EndDevice","zclVersion":1},"humidity":45.12,"linkquality":157,"temperature":16.26,"voltage":3200}'
            # topic_level1=zigbee2mqtt, topic_level2=TRADFRI E1766_01, topic_level3=, topic_level4=, topic_level5=, payload={'battery': 74, 'device': {'applicationVersion': 33, 'dateCode': '20190311', 'friendlyName': 'TRADFRI E1766_01', 'hardwareVersion': 1, 'ieeeAddr': '0x588e81fffe28dec5', 'manufacturerID': 4476, 'manufacturerName': 'IKEA of Sweden', 'model': 'E1766', 'networkAddress': 39405, 'powerSource': 'Battery', 'softwareBuildID': '2.2.010', 'stackVersion': 98, 'type': 'EndDevice', 'zclVersion': 3}, 'linkquality': 141}
            # topic_level1=zigbee2mqtt, topic_level2=LEDVANCE_E27_TW_01, topic_level3=, topic_level4=, topic_level5=, payload={'brightness': 254, 'color': {'x': 0.4599, 'y': 0.4106}, 'color_mode': 'color_temp', 'color_temp': 370, 'color_temp_startup': 65535, 'last_seen': 1632943562477, 'linkquality': 39, 'state': 'ON', 'update': {'state': 'idle'}, 'update_available': False}
            # topic_level1=zigbee2mqtt, topic_level2=0xf0d1b800001574df, topic_level3=, topic_level4=, topic_level5=, payload={'brightness': 166, 'color': {'hue': 296, 'saturation': 69}, 'color_mode': 'hs', 'color_temp': 405, 'last_seen': 1638183778409, 'linkquality': 159, 'state': 'ON', 'update': {'state': 'idle'}, 'update_available': False}
            
            if type(payload) is dict:
                # Wenn Geräte zur Laufzeit des Plugins hinzugefügt werden, werden diese im dict ergänzt
                if not self.zigbee2mqtt_devices.get(topic_level2):
                    self.zigbee2mqtt_devices[topic_level2] = {}
                    self.logger.info(f"New device discovered: {topic_level2}")
                    
                ## Korrekturen in der Payload
                
                # Umbenennen des Key 'friendlyName' in 'friendly_name', damit er identisch zu denen aus den Log und Config Topics ist
                if 'device' in payload:
                    meta = payload['device']
                    if 'friendlyName' in meta:
                        meta['friendly_name'] = meta.pop('friendlyName')
                    del payload['device']

                    if not self.zigbee2mqtt_devices[topic_level2].get('meta'):
                        self.zigbee2mqtt_devices[topic_level2]['meta'] = {}
                    self.zigbee2mqtt_devices[topic_level2]['meta'].update(meta)
                
                # Korrektur des Lastseen von Timestamp zu datetime
                if 'last_seen' in payload:
                    payload.update({'last_seen': datetime.fromtimestamp(payload['last_seen'] / 1000)})
                    
                # Korrektur der Brightness von 0-254 auf 0-100%
                if 'brightness' in payload:
                    payload.update({'brightness': int(round(payload['brightness'] * 100 / 255, 0))})
                    
                # Korrektur der Farbtemperatur von "mired scale" (Reziproke Megakelvin) auf Kelvin
                if 'color_temp' in payload:
                    payload.update({'color_temp': int(round(10000 / int(payload['color_temp']), 0)) * 100})
                    
                # Verarbeitung von Farbdaten
                if 'color_mode' in payload and 'color' in payload:
                    color_mode = payload['color_mode']
                    color = payload.pop('color')
                    
                    if color_mode == 'hs':
                        payload['hue'] = color['hue']
                        payload['saturation'] = color['saturation']
                        
                    if color_mode == 'xy':
                        payload['color_x'] = color['x']
                        payload['color_y']  = color['y']
                
                if not self.zigbee2mqtt_devices[topic_level2].get('data'):
                    self.zigbee2mqtt_devices[topic_level2]['data'] = {}
                self.zigbee2mqtt_devices[topic_level2]['data'].update(payload)

                ## Setzen des Itemwertes
                if topic_level2 in list(self.zigbee2mqtt_plugin_devices.keys()):
                    if debug_logger is True:
                        self.logger.debug(f"Item to be checked for update and to be updated")
                    for element in payload:
                        itemtype = f"item_{element}"
                        value = payload[element]
                        item = self.zigbee2mqtt_plugin_devices[topic_level2]['connected_items'].get(itemtype, None)
                        src = self.get_shortname() + ':' + topic_level2
                        if debug_logger is True:
                            self.logger.debug(f"element: {element}, itemtype: {itemtype}, value: {value}, item: {item}")

                        if item is not None:
                            old_value = item()
                            if value != old_value:
                                item(value, src)
                                self.logger.info(f"{topic_level2}: Item '{item.id()}' set to value {value}")
                            else:
                                self.logger.info(f"{topic_level2}: Item '{item.id()}' has already value {value} as set to be set to. No change of Item value")
                        else:
                            self.logger.info(f"{topic_level2}: No item for itemtype '{itemtype}' defined to set to {value}")

        # self.zigbee2mqtt_plugin_devices[topic_level2]['online_timeout'] = datetime.now()+timedelta(seconds=self._cycle+5)

    def _build_topic_str(self, topic_level1, topic_level2, topic_level3, topic_level4, topic_level5):
        """
        Build the mqtt topic as string

        :param topic_level1:    basetopic of topic to publish
        :param topic_level2:    unique part of topic to publish
        :param topic_level3:    level3 of topic to publish
        :param topic_level4:    level4 of topic to publish
        :param topic_level5:    level5 of topic to publish
        """
    
        tpc = f"{topic_level1}/{topic_level2}"
        if topic_level3 != '':
            tpc = f"{tpc}/{topic_level3}"
            if topic_level4 != '':
                tpc = f"{tpc}/{topic_level4}"
                if topic_level5 != '':
                    tpc = f"{tpc}/{topic_level5}"
        return tpc
        
    def _get_zigbee_meta_data(self, device_data):
        """
        Extrtact the Zigbee Meta-Data for a certain device out of the device_data

        :param device_data:     Payload of the bridge config message
        :return:                None    
        """
        for element in device_data:
            if type(element) is dict:
                device = element.get('friendly_name')
                if device:
                    if 'lastSeen' in element:
                        element.update({'lastSeen': datetime.fromtimestamp(element['lastSeen']/1000)})
                    if not self.zigbee2mqtt_devices.get(device):
                        self.zigbee2mqtt_devices[device] = {}
                    if not self.zigbee2mqtt_devices[device].get('meta'):
                        self.zigbee2mqtt_devices[device]['meta'] = {}
                    self.zigbee2mqtt_devices[device]['meta'].update(element)
            else:
                if self.logger.isEnabledFor(logging.DEBUG):
                    self.logger.debug(f"(Received payload {device_data} is not of type dict")
                 
    def _bool2str(self, bool_value, typus):
        """
        Turns bool value to string

        :param bool_value:      bool value
        :param typus:           type of string the bool_value will be transfered to
        :return:                string containing bool expressions    
        """
        if type(bool_value) is bool:
            if typus == 1:
                result = 'ON' if bool_value is True else 'OFF'
            elif typus == 2:
                result = 'an' if bool_value is True else 'aus'
            elif typus == 3:
                result = 'ja' if bool_value is True else 'nein'
            else:
                result = 'typus noch nicht definiert'
        else:
            result = 'Wert ist nicht vom Type bool'
        return result
        
    def _get_current_status_of_all_devices_linked_to_items(self):
        """
        Get current status of all devices linked to items

        :return:                None 
        """
        for device in self.zigbee2mqtt_plugin_devices:
            attribut = (list(self.zigbee2mqtt_plugin_devices[device]['connected_items'].keys())[0])[5:]
            payload = '{"' + str(attribut) + '" : ""}'
            self.publish_zigbee2mqtt_topic(self.topic_level1, str(device), 'get', '', '', payload)
            
    def _handle_hex_in_topic_level2(self, topic_level2, item):
        """
        check if zigbee device short name has been used without parentheses; if so this will be normally parsed to a number and therefore mismatch with defintion
        """
        try:
            topic_level2 = int(topic_level2)
            self.logger.warning(f"Probably for item {item.id()} the IEEE Adress has been used for item attribute 'zigbee2mqtt_topic'. Trying to make that work but it will cause exceptions. To prevent this, the short name need to be defined as string by using parentheses")
            topic_level2 = str(hex(topic_level2))
        except:
            pass
        return topic_level2
