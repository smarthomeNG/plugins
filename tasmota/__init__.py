#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.4 and
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

from datetime import datetime, timedelta
import logging

from lib.module import Modules
from lib.model.mqttplugin import *
from lib.item import Items

from .webif import WebInterface


class Tasmota(MqttPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.2.0'

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

        # cycle time in seconds, only needed, if hardware/interface needs to be
        # polled for value changes by adding a scheduler entry in the run method of this plugin
        # (maybe you want to make it a plugin parameter?)
        self._cycle = 60

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.full_topic = self.get_parameter_value('full_topic').lower()
        self.telemetry_period = self.get_parameter_value('telemetry_period')
        if self.full_topic.find('%prefix%') == -1 or self.full_topic.find('%topic%') == -1:
            self.full_topic = '%prefix%/%topic%/'
        if self.full_topic[-1] != '/':
            self.full_topic += '/'

        # Initialization code goes here
        self.tasmota_devices = {}                   # to hold tasmota device information for web interface
        self.tasmota_zigbee_devices = {}            # to hold tasmota zigbee device information for web interface
        self.tasmota_items = []                     # to hold item information for web interface
        self.tasmota_meta = {}                      # to hold meta information for web interface
        self.tasmota_zigbee_bridge = {}             # to hold tasmota zigbee bridge status

        self.tasmota_zigbee_bridge_stetting = {'SetOption89': 'OFF',     # SetOption89   Configure MQTT topic for Zigbee devices (also see SensorRetain); 0 = single tele/%topic%/SENSOR topic (default), 1 = unique device topic based on Zigbee device ShortAddr, Example: tele/Zigbee/5ADF/SENSOR = {"ZbReceived":{"0x5ADF":{"Dimmer":254,"Endpoint":1,"LinkQuality":70}}}
                                               'SetOption83': 'ON',      # SetOption83   Uses Zigbee device friendly name instead of 16 bits short addresses as JSON key when reporting values and commands; 0 = JSON key as short address, 1 = JSON key as friendly name
                                               'SetOption100': 'ON',     # SetOption100  Remove Zigbee ZbReceived value from {"ZbReceived":{xxx:yyy}} JSON message; 0 = disable (default), 1 = enable
                                               'SetOption125': 'ON',     # SetOption125	 ZbBridge only Hide bridge topic from zigbee topic (use with SetOption89) 1 = enable
                                               'SetOption118': 'ON',     # SetOption118  Move ZbReceived from JSON message into the subtopic replacing "SENSOR" default; 0 = disable (default); 1 = enable
                                               'SetOption112': 'ON',     # SetOption112  0 = (default); 1 = use friendly name in Zigbee topic (use with ZbDeviceTopic)
                                               'SetOption119': 'OFF'}    # SetOption119  Remove device addr from JSON payload; 0 = disable (default); 1 = enable

        # add subscription to get device announces
        self.add_tasmota_subscription('tele', '+', 'LWT', 'bool', bool_values=['Offline', 'Online'], callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'STATE', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'SENSOR', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'INFO1', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'INFO2', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'INFO3', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'RESULT', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'ZbReceived', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'STATUS', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'STATUS2', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'STATUS5', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'STATUS9', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'RESULT', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'POWER', 'num', callback=self.on_mqtt_message)
        self.add_tasmota_subscription('stat', '+', 'POWER1', 'num', callback=self.on_mqtt_message)
        self.add_tasmota_subscription('stat', '+', 'POWER2', 'num', callback=self.on_mqtt_message)
        self.add_tasmota_subscription('stat', '+', 'POWER3', 'num', callback=self.on_mqtt_message)
        self.add_tasmota_subscription('stat', '+', 'POWER4', 'num', callback=self.on_mqtt_message)

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        # start subscription to all topics
        self.start_subscriptions()

        # Discover Tasmota Device
        key_list = list(self.tasmota_devices.keys())        # use copy of keys to iterate to prevent changing dict during iteration
        for topic in key_list:
            # ask for status info of each known tasmota_topic, collected during parse_item
            self.logger.debug(f"run: publishing 'cmnd/{topic}/STATUS'")
            self.publish_tasmota_topic('cmnd', topic, 'STATUS', '0')

            self.logger.debug(f"run: publishing 'cmnd/{topic}/Module'")
            self.publish_tasmota_topic('cmnd', topic, 'Module', '')

            # set telemetry period for each known tasmota_topic, collected during parse_item
            self.logger.info(f"run: Setting telemetry period to {self.telemetry_period} seconds")
            self.logger.debug(f"run: publishing 'cmnd/{topic}/teleperiod'")
            self.publish_tasmota_topic('cmnd', topic, 'teleperiod', self.telemetry_period)

        # Update tasmota_meta auf Basis von tasmota_devices
        self._update_tasmota_meta()

        self.scheduler_add('poll_device', self.poll_device, cycle=self._cycle)
        self.alive = True
        return

    def stop(self):
        """
        Stop method for the plugin
        """
        self.alive = False
        self.logger.debug("Stop method called")
        self.scheduler_remove('poll_device')

        # stop subscription to all topics
        self.stop_subscriptions()

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
        if self.has_iattr(item.conf, 'tasmota_topic'):
            self.logger.debug(f"parsing item: {item.id()}")

            tasmota_topic = self.get_iattr_value(item.conf, 'tasmota_topic')
            tasmota_attr = self.get_iattr_value(item.conf, 'tasmota_attr')
            tasmota_relay = self.get_iattr_value(item.conf, 'tasmota_relay')
            tasmota_zb_device = self.get_iattr_value(item.conf, 'tasmota_zb_device')
            if tasmota_zb_device is not None:
                # check if zigbee device short name has been used without parentheses; if so this will be normally parsed to a number and therefore mismatch with defintion
                try:
                    tasmota_zb_device = int(tasmota_zb_device)
                    self.logger.warning(f"Probably for item {item.id()} the device short name as been used for attribute 'tasmota_zb_device'. Trying to make that work but it will cause exceptions. To prevent this, the short name need to be defined as string by using parentheses")
                    tasmota_zb_device = str(hex(tasmota_zb_device))
                    tasmota_zb_device = tasmota_zb_device[0:2]+tasmota_zb_device[2:len(tasmota_zb_device)].upper()
                except:
                    pass
            tasmota_zb_attr = str(self.get_iattr_value(item.conf, 'tasmota_zb_attr')).lower()

            if not tasmota_relay:
                tasmota_relay = '1'
            # self.logger.debug(f" - tasmota_topic={tasmota_topic}, tasmota_attr={tasmota_attr}, tasmota_relay={tasmota_relay}")
            # self.logger.debug(f" - tasmota_topic={tasmota_topic}, item.conf={item.conf}")

            if not self.tasmota_devices.get(tasmota_topic):
                self.tasmota_devices[tasmota_topic] = {}
                self.tasmota_devices[tasmota_topic]['connected_to_item'] = False        # is tasmota_topic connected to any item?
                self.tasmota_devices[tasmota_topic]['connected_items'] = {}
                self.tasmota_devices[tasmota_topic]['uptime'] = '-'
                self.tasmota_devices[tasmota_topic]['lights'] = {}
                self.tasmota_devices[tasmota_topic]['rf'] = {}
                self.tasmota_devices[tasmota_topic]['sensors'] = {}
                self.tasmota_devices[tasmota_topic]['relais'] = {}
                self.tasmota_devices[tasmota_topic]['zigbee'] = {}

            # handle the different topics from Tasmota devices
            if tasmota_attr:
                tasmota_attr = tasmota_attr.lower()

            self.tasmota_devices[tasmota_topic]['connected_to_item'] = True
            if tasmota_attr == 'relay':
                self.tasmota_devices[tasmota_topic]['connected_items']['item_'+tasmota_attr+str(tasmota_relay)] = item
            elif tasmota_zb_device and tasmota_zb_attr:
                self.tasmota_devices[tasmota_topic]['connected_items']['item_'+str(tasmota_zb_device)+'.'+str(tasmota_zb_attr.lower())] = item
            else:
                self.tasmota_devices[tasmota_topic]['connected_items']['item_'+tasmota_attr] = item

            if tasmota_attr == 'online':
                self.tasmota_devices[tasmota_topic]['online'] = False
            elif (tasmota_attr and tasmota_attr.startswith('zb')) or tasmota_zb_device:
                self.tasmota_devices[tasmota_topic]['zigbee']['active'] = True

            # append to list used for web interface
            if item not in self.tasmota_items:
                self.tasmota_items.append(item)

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
        self.logger.debug(f"update_item: {item.id()}")

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped  AND only, if the item has not been changed by this this plugin:

            # get tasmota attributes of item
            tasmota_topic = self.get_iattr_value(item.conf, 'tasmota_topic')
            tasmota_attr = self.get_iattr_value(item.conf, 'tasmota_attr')
            tasmota_relay = self.get_iattr_value(item.conf, 'tasmota_relay')
            tasmota_zb_device = self.get_iattr_value(item.conf, 'tasmota_zb_device')
            tasmota_zb_attr = self.get_iattr_value(item.conf, 'tasmota_zb_attr').lower()

            if tasmota_attr in ['relay', 'hsb', 'white', 'ct', 'rf_send', 'rf_key_send', 'zb_permit_join']:
                self.logger.info(f"update_item: {item.id()}, item has been changed in SmartHomeNG outside of this plugin in {caller} with value {item()}")
                value = None
                bool_values = None
                if tasmota_attr == 'relay':
                    # publish topic with new relay state
                    if not tasmota_relay:
                        tasmota_relay = '1'
                    topic = tasmota_topic
                    detail = 'POWER'
                    if tasmota_relay > '1':
                        detail += str(tasmota_relay)
                    bool_values = ['OFF', 'ON']
                    value = item()

                elif tasmota_attr == 'hsb':
                    # publish topic with new hsb value
                    # Format aus dem Item ist eine Liste mit drei int Werten bspw. [299, 100, 94]
                    # Format zum Senden ist ein String mit kommagetrennten Werten '299,100,94'
                    topic = tasmota_topic
                    detail = 'HsbColor'
                    hsb = item()
                    if type(hsb) is list and len(hsb) == 3:
                        hsb = list(map(int, hsb))
                        value = ','.join(str(v) for v in hsb)
                    else:
                        self.logger.debug(f"update_item: hsb value received but not in correct format/content; expected format is list like [299, 100, 94]")

                elif tasmota_attr == 'white':
                    # publish topic with new white value
                    topic = tasmota_topic
                    detail = 'White'
                    white = item()
                    if type(white) is int and 0 <= white <= 100:
                        value = white
                    else:
                        self.logger.debug(f"update_item: white value received but not in correct format/content; expected format is integer value between 0 and 100")

                elif tasmota_attr == 'ct':
                    # publish topic with new ct value
                    topic = tasmota_topic
                    detail = 'CT'
                    ct = item()
                    if type(ct) is int and 153 <= ct <= 500:
                        value = ct
                    else:
                        self.logger.debug(f"update_item: ct value received but not in correct format/content; expected format is integer value between 153 for cold white and 500 for warm white")

                elif tasmota_attr == 'rf_send':
                    # publish topic with new rf data
                    # Format aus dem Item ist ein dict in folgendem Format: {'RfSync': 12220, 'RfLow': 440, 'RfHigh': 1210, 'RfCode':'#F06104'}
                    # Format zum Senden ist: "RfSync 12220; RfLow 440; RfHigh 1210; RfCode #F06104"
                    topic = tasmota_topic
                    detail = 'Backlog'
                    rf_send = item()
                    if type(rf_send) is dict:
                        rf_send_lower = eval(repr(rf_send).lower())
                        # rf_send_lower = {k.lower(): v for k, v in rf_send.items()}
                        if 'rfsync' and 'rflow' and 'rfhigh' and 'rfcode' in rf_send_lower:
                            value = 'RfSync'+' '+str(rf_send_lower['rfsync'])+'; '+'RfLow'+' '+str(rf_send_lower['rflow'])+'; '+'RfHigh'+' '+str(rf_send_lower['rfhigh'])+'; '+'RfCode'+' '+str(rf_send_lower['rfcode'])
                        else:
                            self.logger.debug(f"update_item: rf_send received but not with correct content; expected content is: {'RfSync': 12220, 'RfLow': 440, 'RfHigh': 1210, 'RfCode':'#F06104'}")
                    else:
                        self.logger.debug(f"update_item: rf_send received but not in correct format; expected format is: {'RfSync': 12220, 'RfLow': 440, 'RfHigh': 1210, 'RfCode':'#F06104'}")

                elif tasmota_attr == 'rf_key_send':
                    # publish topic for rf_keyX Default send
                    topic = tasmota_topic
                    try:
                        rf_key = int(item())
                    except Exception:
                        self.logger.debug(f"update_item: rf_key_send received but with correct format; expected format integer or string 1-16")
                    else:
                        if rf_key in range(1, 17):
                            detail = 'RfKey'+str(rf_key)
                            value = 1
                        else:
                            self.logger.debug(f"update_item: rf_key_send received but with correct content; expected format value 1-16")

                elif tasmota_attr == 'ZbPermitJoin':
                    # publish topic for ZbPermitJoin
                    topic = tasmota_topic
                    detail = 'ZbPermitJoin'
                    bool_values = ['0', '1']
                    value = item()

                elif tasmota_attr == 'ZbForget':
                    # publish topic for ZbForget
                    topic = tasmota_topic
                    detail = 'ZbForget'
                    value = item()
                    if item() in self.tasmota_zigbee_devices:
                        value = item()
                    else:
                        self.logger.error(f"Device {item()} not known by plugin, no action taken.")

                elif tasmota_attr == 'ZbPing':
                    # publish topic for ZbPing
                    topic = tasmota_topic
                    detail = 'ZbPing'
                    if item() in self.tasmota_zigbee_devices:
                        value = item()
                    else:
                        self.logger.error(f"Device {item()} not known by plugin, no action taken.")

                if value is not None:
                    self.publish_tasmota_topic('cmnd', topic, detail, value, item, bool_values=bool_values)
                    
            elif tasmota_zb_attr in ['power', 'hue', 'sat', 'ct', 'dimmer']:
                self.logger.info(f"update_item: {item.id()}, item has been changed in SmartHomeNG outside of this plugin in {caller} with value {item()}")
                payload = {}
                bool_values = None
                # Topic: cmnd/<your_device_topic>/ZbSend  //  Payload: {"Device":"0x0A22","Send":{"Power":0}}
                if tasmota_zb_device and tasmota_zb_attr == 'power':
                    topic = tasmota_topic
                    detail = 'ZbSend'
                    bool_values = ['OFF', 'ON']
                    payload = {'Device':tasmota_zb_device,'Send':{'Power':int(item())}}
                    
                elif tasmota_zb_device and tasmota_zb_attr == 'dimmer':
                    topic = tasmota_topic
                    detail = 'ZbSend'
                    value = int(item())
                    if value < 0 or value > 254:
                        self.logger.warning(f' commanded value for brightness not within allowed range; set to next valid value')
                        value = 0 if (value < 0) else 254
                    payload = {'Device':tasmota_zb_device,'Send':{'Dimmer':value}}
                    
                elif tasmota_zb_device and tasmota_zb_attr == 'hue':
                    topic = tasmota_topic
                    detail = 'ZbSend'
                    value = int(item())
                    if value < 0 or value > 254:
                        self.logger.warning(f' commanded value for hue not within allowed range; set to next valid value')
                        value = 0 if (value < 0) else 254
                    payload = {'Device':tasmota_zb_device,'Send':{'Hue':value}}
                    
                elif tasmota_zb_device and tasmota_zb_attr == 'sat':
                    topic = tasmota_topic
                    detail = 'ZbSend'
                    value = int(item())
                    if value < 0 or value > 254:
                        self.logger.warning(f' commanded value for saturation not within allowed range; set to next valid value')
                        value = 0 if (value < 0) else 254
                    payload = {'Device':tasmota_zb_device,'Send':{'Sat':value}}
                    
                elif tasmota_zb_device and tasmota_zb_attr == 'ct':
                    topic = tasmota_topic
                    detail = 'ZbSend'
                    value = int(item())
                    if value < 0 or value > 65534:
                        self.logger.warning(f' commanded value for saturation not within allowed range; set to next valid value')
                        value = 0 if (value < 0) else 65534
                    payload = {'Device':tasmota_zb_device,'Send':{'CT':value}}
                    
                if payload:
                    self.publish_tasmota_topic('cmnd', topic, detail, payload, item, bool_values=bool_values)

            else:
                self.logger.warning(f"update_item: {item.id()}, trying to change item in SmartHomeNG that is read only in tasmota device (by {caller})")

    def poll_device(self):
        """
        Polls for updates of the tasmota device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        # check if Tasmota Zigbee Bridge needs to be configured
        tasmota_zigbee_bridge_status = self.tasmota_zigbee_bridge.get('status')
        if tasmota_zigbee_bridge_status == 'discovered':
            self.logger.info(f'poll_device: Tasmota Zigbee Bridge discovered; Configuration will be adapted.')
            zigbee_device = self.tasmota_zigbee_bridge.get('device')
            if zigbee_device:
                self._discover_zigbee_bridge(zigbee_device)

        self.logger.info("poll_device: Checking online status of connected devices")
        for tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic].get('online') is True and self.tasmota_devices[tasmota_topic].get('online_timeout'):
                if self.tasmota_devices[tasmota_topic]['online_timeout'] < datetime.now():
                    self.tasmota_devices[tasmota_topic]['online'] = False
                    self._set_item_value(tasmota_topic, 'item_online', False, 'poll_device')
                    self.logger.info(f"poll_device: {tasmota_topic} is not online any more - online_timeout={self.tasmota_devices[tasmota_topic]['online_timeout']}, now={datetime.now()}")
                    # delete data from WebIF dict
                    self.tasmota_devices[tasmota_topic]['lights'] = {}
                    self.tasmota_devices[tasmota_topic]['rf'] = {}
                    self.tasmota_devices[tasmota_topic]['sensors'] = {}
                    self.tasmota_devices[tasmota_topic]['relais'] = {}
                    self.tasmota_devices[tasmota_topic]['zigbee'] = {}
                else:
                    self.logger.debug(f'poll_device: Checking online status of {tasmota_topic} successfull')

                # ask for status info of reconnected tasmota_topic (which was not connected during plugin start)
                if not self.tasmota_devices[tasmota_topic].get('mac'):
                    self.logger.debug(f"poll_device: reconnected device discovered, publishing 'cmnd/{tasmota_topic}/STATUS'")
                    self.publish_topic(f"cmnd/{tasmota_topic}/STATUS", 0)
                    self.logger.debug(f"poll_device: reconnected device discovered, publishing 'cmnd/{tasmota_topic}/Module'")
                    self.publish_topic(f"cmnd/{tasmota_topic}/Module", "")

        # update tasmota_meta auf Basis von tasmota_devices
        self._update_tasmota_meta()

    def add_tasmota_subscription(self, prefix, topic, detail, payload_type, bool_values=None, item=None, callback=None):
        """
        build the topic in Tasmota style and add the subscription to mqtt

        :param prefix:       prefix of topic to subscribe to
        :param topic:        unique part of topic to subscribe to
        :param detail:       detail of topic to subscribe to
        :param payload_type: payload type of the topic (for this subscription to the topic)
        :param bool_values:  bool values (for this subscription to the topic)
        :param item:         item that should receive the payload as value. Used by the standard handler (if no callback function is specified)
        :param callback:     a plugin can provide an own callback function, if special handling of the payload is needed
        :return:
        """
        tpc = self.full_topic.replace("%prefix%", prefix)
        tpc = tpc.replace("%topic%", topic)
        tpc += detail
        self.add_subscription(tpc, payload_type, bool_values=bool_values, callback=callback)

    def publish_tasmota_topic(self, prefix, topic, detail, payload, item=None, qos=None, retain=False, bool_values=None):
        """
        build the topic in Tasmota style and publish to mqtt

        :param prefix:       prefix of topic to publish
        :param topic:        unique part of topic to publish
        :param detail:       detail of topic to publish
        :param payload:      payload to publish
        :param item:         item (if relevant)
        :param qos:          qos for this message (optional)
        :param retain:       retain flag for this message (optional)
        :param bool_values:  bool values (for publishing this topic, optional)
        :return:
        """
        tpc = self.full_topic.replace("%prefix%", prefix)
        tpc = tpc.replace("%topic%", topic)
        tpc += detail
        self.publish_topic(tpc, payload, item, qos, retain, bool_values)

    def on_mqtt_announce(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:       MQTT topic
        :param payload:     MQTT message payload
        :param qos:         qos for this message (optional)
        :param retain:      retain flag for this message (optional)
        """
        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
            self.logger.info(f"on_mqtt_announce: topic_type={topic_type}, tasmota_topic={tasmota_topic}, info_topic={info_topic}, payload={payload}")
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")
        else:
            # ask for status info of this newly discovered device
            if info_topic != 'ZbReceived' and not self.tasmota_devices.get(tasmota_topic):
                self.tasmota_devices[tasmota_topic] = {}
                self.tasmota_devices[tasmota_topic]['connected_to_item'] = False
                self.tasmota_devices[tasmota_topic]['uptime'] = '-'
                self.tasmota_devices[tasmota_topic]['lights'] = {}
                self.tasmota_devices[tasmota_topic]['rf'] = {}
                self.tasmota_devices[tasmota_topic]['sensors'] = {}
                self.tasmota_devices[tasmota_topic]['relais'] = {}
                self.tasmota_devices[tasmota_topic]['zigbee'] = {}
                self.logger.debug(f"on_mqtt_announce: new device discovered, publishing 'cmnd/{topic}/STATUS'")
                self.publish_topic(f"cmnd/'{tasmota_topic}/STATUS", 0)

            if info_topic == 'LWT':
                ## Handling of LWT ##
                self.logger.debug(f"LWT: info_topic: {info_topic} datetime: {datetime.now()} payload: {payload}")
                self.tasmota_devices[tasmota_topic]['online'] = payload
                self._set_item_value(tasmota_topic, 'item_online', payload, info_topic)
                if payload is True:
                    self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now()+timedelta(seconds=self.telemetry_period+5)
                    #self.logger.info(f" - new 'online_timeout'={self.tasmota_devices[tasmota_topic]['online_timeout']}")

            elif info_topic == 'STATE' or info_topic == 'RESULT':
                ## Handling of Light messages ##
                if type(payload) is dict and ('HSBColor' or 'Dimmer' or 'Color' or 'CT' or 'Scheme' or 'Fade' or 'Speed' or 'LedTable' or 'White') in payload:
                    self.logger.info(f"Received Message decoded as light message.")
                    self._handle_lights(tasmota_topic, info_topic, payload)

                ## Handling of Power messages ##
                elif any(item.startswith("POWER") for item in payload.keys()):
                    self.logger.info(f"Received Message decoded as power message.")
                    self._handle_power(tasmota_topic, info_topic, payload)

                ## Handling of RF messages ##
                elif any(item.startswith("Rf") for item in payload.keys()):
                    self.logger.info(f"Received Message decoded as RF type message.")
                    self._handle_rf(tasmota_topic, info_topic, payload)

                ## Handling of Module messages ##
                elif type(payload) is dict and 'Module' in payload:
                    self.logger.info(f"Received Message decoded as Module type message.")
                    self._handle_module(tasmota_topic, payload)

                ## Handling of Zigbee Bridge Setting messages ##
                elif type(payload) is dict and any(item.startswith("SetOption") for item in payload.keys()):
                    self.logger.info(f"Received Message decoded as Zigbee Bridge Setting message.")
                    self._handle_zbbridge_setting(payload)

                ## Handling of Zigbee Bridge Config messages ##
                elif type(payload) is dict and any(item.startswith("ZbConfig") for item in payload.keys()):
                    self.logger.info(f"Received Message decoded as Zigbee Config message.")
                    self._handle_zbconfig(tasmota_topic, payload)

                ## Handling of Zigbee Bridge Status messages ##
                elif any(item.startswith("ZbStatus") for item in payload.keys()):
                    self.logger.info(f"Received Message decoded as Zigbee ZbStatus message.")
                    self._handle_zbstatus(tasmota_topic, payload)

                ## Handling of WIFI ##
                if type(payload) is dict and 'Wifi' in payload:
                    self.logger.info(f"Received Message contains Wifi information.")
                    self._handle_wifi(tasmota_topic, payload)

                ## Handling of Uptime ##
                if tasmota_topic in self.tasmota_devices:
                    self.logger.info(f"Received Message will be checked for Uptime.")
                    self.tasmota_devices[tasmota_topic]['uptime'] = payload.get('Uptime', '-')

                ## setting new online-timeout ##
                self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now()+timedelta(seconds=self.telemetry_period+5)

                ## setting online_item to True ##
                self._set_item_value(tasmota_topic, 'item_online', True, info_topic)

            elif info_topic == 'SENSOR':
                self.logger.info(f"Received Message contain sensor information.")
                self._handle_sensor(tasmota_topic, info_topic, payload)

                ## setting new online-timeout ##
                self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now() + timedelta(
                    seconds=self.telemetry_period + 5)

                ## setting online_item to True ##
                self._set_item_value(tasmota_topic, 'item_online', True, info_topic)

            elif info_topic == 'STATUS':
                self.logger.info(f"Received Message decoded as STATUS message.")
                fn = payload['Status'].get('FriendlyName', '')
                if fn != '':
                    if fn[0] == '[' and fn[-1] == ']':
                        fn = fn[1:-1]
                self.tasmota_devices[tasmota_topic]['friendly_name'] = fn

            elif info_topic == 'STATUS2':
                # topic_type=stat, tasmota_topic=SONOFF_B2, info_topic=STATUS2, payload={'StatusFWR': {'Version': '9.4.0(tasmota)', 'BuildDateTime': '2021-04-23T10:07:22', 'Boot': 31, 'Core': '2_7_4_9', 'SDK': '2.2.2-dev(38a443e)', 'CpuFrequency': 80, 'Hardware': 'ESP8266EX', 'CR': '422/699'}}
                # topic_type=stat, tasmota_topic=SONOFF_ZB1, info_topic=STATUS2, payload={'StatusFWR': {'Version': '9.4.0(zbbridge)', 'BuildDateTime': '2021-04-23T10:07:24', 'Boot': 31, 'Core': '2_7_4_9', 'SDK': '2.2.2-dev(38a443e)', 'CpuFrequency': 160, 'Hardware': 'ESP8266EX', 'CR': '405/699'}}
                self.logger.info(f"Received Message decoded as STATUS2 message.")
                self.tasmota_devices[tasmota_topic]['fw_ver'] = payload['StatusFWR'].get('Version', '')

            elif info_topic == 'STATUS5':
                self.logger.info(f"Received Message decoded as STATUS5 message.")
                self.tasmota_devices[tasmota_topic]['ip'] = payload['StatusNET'].get('IPAddress', '')
                self.tasmota_devices[tasmota_topic]['mac'] = payload['StatusNET'].get('Mac', '')

            elif info_topic == 'STATUS9':
                self.logger.info(f"Received Message decoded as STATUS9 message.")
                StatusPTH = payload.get('StatusPTH', {})
                #self.logger.info(f" - StatusPTH={StatusPTH}")

            elif info_topic == 'INFO1':
                self.logger.info(f"Received Message decoded as INFO1 message.")
                self.tasmota_devices[tasmota_topic]['fw_ver'] = payload.get('Version', '')
                self.tasmota_devices[tasmota_topic]['module'] = payload.get('Module', '')

            elif info_topic == 'INFO2':
                self.logger.info(f"Received Message decoded as INFO2 message.")
                self.tasmota_devices[tasmota_topic]['ip'] = payload.get('IPAddress', '')

            elif info_topic == 'INFO3':
                self.logger.info(f"Received Message decoded as INFO3 message.")
                restart_reason = payload.get('RestartReason', '')
                self.logger.warning(f"Device {tasmota_topic} (IP={self.tasmota_devices[tasmota_topic]['ip']}) just startet. Reason={restart_reason}")

            elif info_topic == 'ZbReceived':
                self.logger.info(f"Received Message decoded as ZbReceived message.")
                self._handle_ZbReceived(payload)

                ## setting new online-timeout ##
                self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now() + timedelta(seconds=self.telemetry_period + 5)

                ## setting online_item to True ##
                self._set_item_value(tasmota_topic, 'item_online', True, info_topic)
            else:
                self.logger.info(f"Topic {info_topic} not handled in plugin.")

    def on_mqtt_message(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:       MQTT topic
        :param payload:     MQTT message payload
        :param qos:         qos for this message (optional)
        :param retain:      retain flag for this message (optional)
        """

        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
            self.logger.info(f"on_mqtt_message: topic_type={topic_type}, tasmota_topic={tasmota_topic}, info_topic={info_topic}, payload={payload}")
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")

        device = self.tasmota_devices.get(tasmota_topic, None)
        if device:
            if info_topic.startswith('POWER'):
                tasmota_relay = str(info_topic[5:])
                if not tasmota_relay:
                    tasmota_relay = '1'
                item_relay = 'item_relay'+tasmota_relay
                self._set_item_value(tasmota_topic, item_relay, payload == 'ON', info_topic)
                self.tasmota_devices[tasmota_topic]['relais'][info_topic] = payload
                self.tasmota_meta['relais'] = True
        return

    def _set_item_value(self, tasmota_topic, itemtype, value, info_topic=''):
        """
        Sets item value

        :param tasmota_topic:   MQTT message payload
        :param itemtype:        itemtype to be set
        :param value:           value to be set
        :param info_topic:      MQTT info_topic
        :return:
        """
        if tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic].get('connected_items'):
                item = self.tasmota_devices[tasmota_topic]['connected_items'].get(itemtype)
                topic = ''
                src = ''
                if info_topic != '':
                    topic = f"from info_topic '{info_topic}'"
                    src = self.get_instance_name()
                    if src != '':
                        src += ':'
                    src += tasmota_topic + ':' + info_topic

                if item is not None:
                    item(value, self.get_shortname(), src)
                    self.logger.info(f"{tasmota_topic}: Item '{item.id()}' via itemtype '{itemtype} set to value {value} provided by {src} '.")
                else:
                    self.logger.info(f"{tasmota_topic}: No item for itemtype '{itemtype}' defined to set to {value} provided by {src}.")
            else:
                self.logger.info(f"{tasmota_topic}: No items connected to {tasmota_topic}.")
        else:
            self.logger.info(f"Tasmota Device {tasmota_topic} unknown.")

    def _handle_ZbReceived(self, payload):
        """
        Extracts Zigbee Received information out of payload and updates plugin dict

        :param payload:   MQTT message payload
        :return:
        """
        # topic_type=tele, tasmota_topic=SONOFF_ZB1, info_topic=ZbReceived, payload={'snzb-02_01': {'Device': '0x67FE', 'Name': 'snzb-02_01', 'Humidity': 31.94, 'Endpoint': 1, 'LinkQuality': 157}}
        for zigbee_device in payload:
            if not zigbee_device in self.tasmota_zigbee_devices:
                self.logger.info(f"New Zigbee Device {zigbee_device} connected to Tasmota Zigbee Bridge discovered")
                self.tasmota_zigbee_devices[zigbee_device] = {}
            else:
                if not self.tasmota_zigbee_devices[zigbee_device].get('data'):
                    self.tasmota_zigbee_devices[zigbee_device]['data'] = {}
                if 'Device' in payload[zigbee_device]:
                    del payload[zigbee_device]['Device']
                if 'Name' in payload[zigbee_device]:
                    del payload[zigbee_device]['Name']
                self.tasmota_zigbee_devices[zigbee_device]['data'].update(payload[zigbee_device])

    def _handle_sensor(self, device, function, payload):
        """
        Extracts Sensor information out of payload and updates plugin dict

        :param device:          Device, the Sensor information shall be handled (equals tasmota_topic)
        :param function:        Function of Device (equals info_topic)
        :param payload:         MQTT message payload
        :return:
        """
        # topic_type=tele, tasmota_topic=SONOFF_B1, info_topic=SENSOR, payload={"Time":"2021-04-28T09:42:50","DS18B20":{"Id":"00000938355C","Temperature":18.4},"TempUnit":"C"}
        # topic_type=tele, tasmota_topic=SONOFF_ZB1, info_topic=SENSOR, payload={'0x67FE': {'Device': '0x67FE', 'Humidity': 41.97, 'Endpoint': 1, 'LinkQuality': 55}}
        # topic_type=tele, tasmota_topic=SONOFF_ZB1, info_topic=SENSOR, payload={"0x54EB":{"Device":"0x54EB","MultiInValue":2,"Click":"double","click":"double","Endpoint":1,"LinkQuality":173}}
        # topic_type=tele, tasmota_topic=SONOFF_ZB1, info_topic=SENSOR, payload={"0x54EB":{"Device":"0x54EB","MultiInValue":255 ,"Click":"release","action":"release","Endpoint":1,"LinkQuality":175}}

        ## Handling of Zigbee Device Messages ##
        if self.tasmota_devices[device]['zigbee'] != {}:
            self.logger.info(f"Received Message decoded as Zigbee Device message.")
            if type(payload) is dict:
                for zigbee_device in payload:
                    if zigbee_device not in self.tasmota_zigbee_devices:
                        self.logger.info(f"New Zigbee Device {zigbee_device} connected to Tasmota Zigbee Bridge discovered")
                        self.tasmota_zigbee_devices[zigbee_device] = {}
                    if not self.tasmota_zigbee_devices[zigbee_device].get('data'):
                        self.tasmota_zigbee_devices[zigbee_device]['data'] = {}
                    if 'Device' in payload[zigbee_device]:
                        del payload[zigbee_device]['Device']
                    if 'Name' in payload[zigbee_device]:
                        del payload[zigbee_device]['Name']

                    self.tasmota_zigbee_devices[zigbee_device]['data'].update(payload[zigbee_device])

                    # Check and correct payload, if there is the same dict key used with different cases (upper and lower case)
                    new_dict = {}
                    for k in payload[zigbee_device]:
                        keys = [each_string.lower() for each_string in list(new_dict.keys())]
                        if k not in keys:
                            new_dict[k] = payload[zigbee_device][k]
                    payload[zigbee_device] = new_dict

                    # Delete keys from 'meta', if in 'data'
                    for key in payload[zigbee_device]:
                        if self.tasmota_zigbee_devices[zigbee_device].get('meta'):
                            if key in self.tasmota_zigbee_devices[zigbee_device]['meta']:
                                self.tasmota_zigbee_devices[zigbee_device]['meta'].pop(key)

                    # Iterate over payload and set corresponding items
                    self.logger.debug(f"Item to be checked for update based in Zigbee Message and updated")
                    for element in payload[zigbee_device]:
                        itemtype = f"item_{zigbee_device}.{element.lower()}"
                        value = payload[zigbee_device][element]
                        self._set_item_value(device, itemtype, value, function)

        else:
        ## Handling of Tasmota Device Sensor Messages ##
            # Energy sensors
            energy = payload.get('ENERGY')
            if energy:
                self.logger.info(f"Received Message decoded as Energy Sensor message.")
                if not self.tasmota_devices[device]['sensors'].get('ENERGY'):
                    self.tasmota_devices[device]['sensors']['ENERGY'] = {}
                if type(energy) is dict:
                    self.tasmota_devices[device]['sensors']['ENERGY']['period'] = energy.get('Period', None)
                    if 'Voltage' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['voltage'] = energy['Voltage']
                        self._set_item_value(device, 'item_voltage', energy['Voltage'], function)
                    if 'Current' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['current'] = energy['Current']
                        self._set_item_value(device, 'item_current', energy['Current'], function)
                    if 'Power' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['power'] = energy['Power']
                        self._set_item_value(device, 'item_power', energy['Power'], function)
                    if 'ApparentPower' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['apparent_power'] = energy['ApparentPower']
                        self._set_item_value(device, 'item_apparent_power', energy['ApparentPower'], function)
                    if 'ReactivePower' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['reactive_power'] = energy['ReactivePower']
                        self._set_item_value(device, 'item_reactive_power', energy['ReactivePower'], function)
                    if 'Factor' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['factor'] = energy['Factor']
                        self._set_item_value(device, 'item_power_factor', energy['Factor'], function)
                    if 'TotalStartTime' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['total_starttime'] = energy['TotalStartTime']
                        self._set_item_value(device, 'item_total_starttime', energy['TotalStartTime'], function)
                    if 'Total' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['total'] = energy['Total']
                        self._set_item_value(device, 'item_power_total', energy['Total'], function)
                    if 'Yesterday' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['yesterday'] = energy['Yesterday']
                        self._set_item_value(device, 'item_power_yesterday', energy['Yesterday'], function)
                    if 'Today' in energy:
                        self.tasmota_devices[device]['sensors']['ENERGY']['today'] = energy['Today']
                        self._set_item_value(device, 'item_power_today', energy['Today'], function)

            # DS18B20 sensors
            ds18b20 = payload.get('DS18B20')
            if ds18b20:
                self.logger.info(f"Received Message decoded as DS18B20 Sensor message.")
                if not self.tasmota_devices[device]['sensors'].get('DS18B20'):
                    self.tasmota_devices[device]['sensors']['DS18B20'] = {}
                if type(ds18b20) is dict:
                    if 'Id' in ds18b20:
                        self.tasmota_devices[device]['sensors']['DS18B20']['id'] = ds18b20['Id']
                        self._set_item_value(device, 'item_id', ds18b20['Id'], function)
                    if 'Temperature' in ds18b20:
                        self.tasmota_devices[device]['sensors']['DS18B20']['temp'] = ds18b20['Temperature']
                        self._set_item_value(device, 'item_temp', ds18b20['Temperature'], function)

            # AM2301 sensors
            am2301 = payload.get('AM2301')
            if am2301:
                self.logger.info(f"Received Message decoded as AM2301 Sensor message.")
                if not self.tasmota_devices[device]['sensors'].get('AM2301'):
                    self.tasmota_devices[device]['sensors']['AM2301'] = {}
                if type(am2301) is dict:
                    if 'Humidity' in am2301:
                        self.tasmota_devices[device]['sensors']['AM2301']['hum'] = am2301['Humidity']
                        self._set_item_value(device, 'item_hum', am2301['Humidity'], function)
                    if 'Temperature' in am2301:
                        self.tasmota_devices[device]['sensors']['AM2301']['temp'] = am2301['Temperature']
                        self._set_item_value(device, 'item_temp', am2301['Temperature'], function)
                    if 'DewPoint' in am2301:
                        self.tasmota_devices[device]['sensors']['AM2301']['dewpoint'] = am2301['DewPoint']
                        self._set_item_value(device, 'item_dewpoint', am2301['DewPoint'], function)

    def _handle_lights(self, device, function, payload):
        """
        Extracts Light information out of payload and updates plugin dict

        :param device:          Device, the Light information shall be handled (equals tasmota_topic)
        :param function:        Function of Device (equals info_topic)
        :param payload:         MQTT message payload
        :return:
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
            self.tasmota_devices[device]['lights']['dimmer'] = int(dimmer)
            self._set_item_value(device, 'item_dimmer', dimmer, function)

        color = payload.get('Color')
        if color:
            self.tasmota_devices[device]['lights']['color'] = str(color)

        ct = payload.get('CT')
        if ct:
            self.tasmota_devices[device]['lights']['ct'] = int(ct)
            self._set_item_value(device, 'item_ct', ct, function)

        white = payload.get('White')
        if white:
            self.tasmota_devices[device]['lights']['white'] = int(white)
            self._set_item_value(device, 'item_white', white, function)

        scheme = payload.get('Scheme')
        if scheme:
            self.tasmota_devices[device]['lights']['scheme'] = int(scheme)

        fade = payload.get('Fade')
        if fade:
            self.tasmota_devices[device]['lights']['fade'] = bool(fade)

        speed = payload.get('Speed')
        if speed:
            self.tasmota_devices[device]['lights']['speed'] = int(speed)

        ledtable = payload.get('LedTable')
        if ledtable:
            self.tasmota_devices[device]['lights']['ledtable'] = bool(ledtable)

    def _handle_power(self, device, function, payload):
        """
        Extracts Power information out of payload and updates plugin dict

        :param device:          Device, the Power information shall be handled (equals tasmota_topic)
        :param function:        Function of Device (equals info_topic)
        :param payload:         MQTT message payload
        :return:
        """
        power_dict = {key:val for key, val in payload.items() if key.startswith('POWER')}
        self.tasmota_devices[device]['relais'].update(power_dict)
        for power in power_dict:
            item_relay = 'item_relay'+str(power[5:])
            self._set_item_value(device, item_relay, power_dict[power], function)

    def _handle_module(self, device, payload):
        """
        Extracts Module information out of payload and updates plugin dict

        :param device:    Device, the Module information shall be handled
        :param payload:   MQTT message payload
        :return:
        """
        module_list = payload.get('Module')
        if module_list:
            template, module = list(module_list.items())[0]
            self.tasmota_devices[device]['module'] = module
            self.tasmota_devices[device]['tasmota_template'] = template

            # Zigbee Bridge erkennen und Status setzen
            if template == '75':
                self.tasmota_zigbee_bridge['status'] = 'discovered'
                self.tasmota_zigbee_bridge['device'] = device
            self.logger.debug(f"_handle_module, ZigbeeBridge Status is: {self.tasmota_zigbee_bridge}")

    def _handle_zbstatus1(self, device, zbstatus1):
        """
        Extracts ZigBee Status1 information out of payload and updates plugin dict

        :param device:    Device, the Zigbee Status information shall be handled
        :param zbstatus1:       List of status information out out mqtt payload
        :return:
        """
        # stat/SONOFF_ZB1/RESULT = {"ZbStatus1":[{"Device":"0x5A45","Name":"DJT11LM_01"},{"Device":"0x67FE","Name":"snzb-02_01"},{"Device":"0x892A","Name":"remote_mini_bl"},{"Device":"0x1FB1"}]}
        if type(zbstatus1) is list:
            for element in zbstatus1:
                friendly_name = element.get('Name')
                if friendly_name:
                    self.tasmota_zigbee_devices[friendly_name] = {}
                else:
                    self.tasmota_zigbee_devices[element['Device']] = {}
            # request detailed informatin of all discovered zigbee devices
            self._poll_zigbee_devices(device)
        else:
            self.logger.debug(f"ZbStatus1 with {zbstatus1} received but not processed. since data was not of type list.")

    def _handle_zbstatus23(self, device, zbstatus23):
        """
        Extracts ZigBee Status 2 and 3 information out of payload and updates plugin dict

        :param zbstatus23:   ZbStatus2 or ZbStatus 3 part of MQTT message payload
        :return:
        """
        # [{"Device":"0xD1B8","Name":"E1766_01","IEEEAddr":"0x588E81FFFE28DEC5","ModelId":"TRADFRIopen/closeremote","Manufacturer":"IKEA","Endpoints":[1],"Config":[]}]}
        # [{'Device': '0x67FE', 'Name': 'snzb-02_01', 'IEEEAddr': '0x00124B00231E45B8', 'ModelId': 'TH01', 'Manufacturer': 'eWeLink', 'Endpoints': [1], 'Config': ['T01'], 'Temperature': 21.29, 'Humidity': 30.93, 'Reachable': True, 'BatteryPercentage': 100, 'LastSeen': 39, 'LastSeenEpoch': 1619350835, 'LinkQuality': 157}]}
        # [{'Device': '0x9EFE', 'IEEEAddr': '0x00158D00067AA8BD', 'ModelId': 'lumi.vibration.aq1', 'Manufacturer': 'LUMI', 'Endpoints': [1, 2], 'Config': [], 'Reachable': True, 'BatteryPercentage': 100, 'LastSeen': 123, 'LastSeenEpoch': 1637134779, 'LinkQuality': 154}]
        # [{'Device': '0x0A22', 'IEEEAddr': '0xF0D1B800001571C5', 'ModelId': 'CLA60 RGBW Z3', 'Manufacturer': 'LEDVANCE', 'Endpoints': [1], 'Config': ['L01', 'O01'], 'Dimmer': 128, 'Hue': 253, 'Sat': 250, 'X': 1, 'Y': 1, 'CT': 370, 'ColorMode': 0, 'RGB': 'FF0408', 'RGBb': '810204', 'Power': 1, 'Reachable': True, 'LastSeen': 11, 'LastSeenEpoch': 1638110831, 'LinkQuality': 18}]

        self.logger.debug(f'zbstatus23: {zbstatus23}')
        if type(zbstatus23) is list:
            for element in zbstatus23:
                zigbee_device = element.get('Name')
                if not zigbee_device:
                    zigbee_device = element.get('Device')
                if zigbee_device in self.tasmota_zigbee_devices:
                    if not self.tasmota_zigbee_devices[zigbee_device].get('meta'):
                        self.tasmota_zigbee_devices[zigbee_device]['meta'] = {}

                    # Korrektur des LastSeenEpoch von Timestamp zu datetime
                    if 'LastSeenEpoch' in element:
                        element.update({'LastSeenEpoch': datetime.fromtimestamp(element['LastSeenEpoch']/1000)})
                    self.tasmota_zigbee_devices[zigbee_device]['meta'].update(element)
                    
                    # Übertragen der Werte aus der Statusmeldung in Data
                    bulb = ['Power','Dimmer','Hue','Sat','X','Y','CT','ColorMode']
                    data = {}
                    for key in bulb:
                        x = element.get(key)
                        if x is not None:
                            data[key] = x
                    if data:
                        self.logger.debug(f"ZbStatus2 or ZbStatus3 received and Bulb detected. Data <{data}> extracted")
                        if not self.tasmota_zigbee_devices[zigbee_device].get('data'):
                            self.tasmota_zigbee_devices[zigbee_device]['data'] = {}
                        self.tasmota_zigbee_devices[zigbee_device]['data'].update(data)
                        
                        # Iterate over data and set corresponding items
                        self.logger.debug(f"Item to be checked for update based in Zigbee Status Message")
                        for entry in data:
                            itemtype = f"item_{zigbee_device}.{entry.lower()}"
                            value = data[entry]
                            self._set_item_value(device, itemtype, value, 'ZbStatus')                        
        else:
            self.logger.debug(f"ZbStatus2 or ZbStatus3 with {zbstatus23} received but not processed. since data was not of type list.")

    def _handle_rf(self, device, function, payload):
        """
        Extracts RF information out of payload and updates plugin dict

        :param device:          Device, the RF information shall be handled
        :param function:        Function of Device (equals info_topic)
        :param payload:         MQTT message payload
        :return:
        """
        rfreceived = payload.get('RfReceived')
        if rfreceived:
            self.logger.info(f"Received Message decoded as RF message.")
            self.tasmota_devices[device]['rf']['rf_received'] = rfreceived
            self._set_item_value(device, 'item_rf_recv', rfreceived['Data'], function)
        if type(payload) is dict and ('RfSync' or 'RfLow' or 'RfHigh' or 'RfCode') in payload:
            self.logger.info(f"Received Message decoded as RF message.")
            if not self.tasmota_devices[device]['rf'].get('rf_send_result'):
                self.tasmota_devices[device]['rf']['rf_send_result'] = payload
            else:
                self.tasmota_devices[device]['rf']['rf_send_result'].update(payload)
        if any(item.startswith("RfKey") for item in payload.keys()):
            self.logger.info(f"Received Message decoded as RF message.")
            self.tasmota_devices[device]['rf']['rfkey_result'] = payload

    def _handle_zbconfig(self, device, payload):
        """
        Extracts ZigBee Config information out of payload and updates plugin dict

        :param device:          Device, the Zigbee Config information shall be handled
        :param payload:         MQTT message payload
        :return:
        """
        # stat/SONOFF_ZB1/RESULT = {"ZbConfig":{"Channel":11,"PanID":"0x0C84","ExtPanID":"0xCCCCCCCCAAA8CC84","KeyL":"0xAAA8CC841B1F40A1","KeyH":"0xAAA8CC841B1F40A1","TxRadio":20}}
        zbconfig = payload.get('ZbConfig')
        if zbconfig:
            self.tasmota_devices[device]['zigbee']['zbconfig'] = payload

    def _handle_zbstatus(self, device, payload):
        """
        Extracts ZigBee Status information out of payload and updates plugin dict

        :param device:    Device, the Zigbee Status information shall be handled
        :param payload:   MQTT message payload
        :return:
        """
        zbstatus1 = payload.get('ZbStatus1')
        if zbstatus1:
            self.logger.info(f"Received Message decoded as Zigbee ZbStatus1 message.")
            self._handle_zbstatus1(device, zbstatus1)
        zbstatus23 = payload.get('ZbStatus2')
        if not zbstatus23:
            zbstatus23 = payload.get('ZbStatus3')
        if zbstatus23:
            self.logger.info(f"Received Message decoded as Zigbee ZbStatus2 or ZbStatus3 message.")
            self._handle_zbstatus23(device, zbstatus23)

    def _handle_wifi(self, device, payload):
        """
        Extracts Wifi information out of payload and updates plugin dict

        :param device:          Device, the Wifi information shall be handled
        :param payload:         MQTT message payload
        :return:
        """
        wifi_signal = int(payload['Wifi'].get('Signal'))
        if wifi_signal:
            self.logger.info(f"Received Message decoded as Wifi message.")
            self.tasmota_devices[device]['wifi_signal'] = wifi_signal

    def _handle_zbbridge_setting(self, payload):
        """
        Extracts Zigbee Bridge Setting information out of payload and updates dict

        :param payload:         MQTT message payload
        :return:
        """
        if not self.tasmota_zigbee_bridge.get('setting'):
            self.tasmota_zigbee_bridge['setting'] = {}
        self.tasmota_zigbee_bridge['setting'].update(payload)

        if self.tasmota_zigbee_bridge['setting'] == self.tasmota_zigbee_bridge_stetting:
            self.tasmota_zigbee_bridge['status'] = 'set'
            self.logger.info(f'_handle_zbbridge_setting: Setting of Tasmota Zigbee Bridge successful.')

    def _update_tasmota_meta(self):
        """
        Updates the tasmota meta information in plugin dict
        """
        self.tasmota_meta = {}
        for tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic]['relais']:
                self.tasmota_meta['relais'] = True
            if self.tasmota_devices[tasmota_topic]['rf']:
                self.tasmota_meta['rf'] = True
            if self.tasmota_devices[tasmota_topic]['lights']:
                self.tasmota_meta['lights'] = True
            if self.tasmota_devices[tasmota_topic]['sensors'].get('DS18B20'):
                self.tasmota_meta['ds18b20'] = True
            if self.tasmota_devices[tasmota_topic]['sensors'].get('AM2301'):
                self.tasmota_meta['am2301'] = True
            if self.tasmota_devices[tasmota_topic]['sensors'].get('ENERGY'):
                self.tasmota_meta['energy'] = True
            if self.tasmota_devices[tasmota_topic]['zigbee']:
                self.tasmota_meta['zigbee'] = True

    def _poll_zigbee_devices(self, device):
        """
        Polls information of all discovered zigbee devices from dedicated Zigbee bridge

        :param device:   Zigbee bridge, where all Zigbee Devices shall be polled (equal to tasmota_topic)
        :return:
        """
        self.logger.info("_poll_zigbee_devices: Polling informatiopn of all discovered Zigbee devices")
        for zigbee_device in self.tasmota_zigbee_devices:
            self.logger.debug(f"_poll_zigbee_devices: publishing 'cmnd/{device}/ZbStatus3 {zigbee_device}'")
            self.publish_tasmota_topic('cmnd', device, 'ZbStatus3', zigbee_device)

    def _discover_zigbee_bridge(self, device):
        """
        Configures and discovers Zigbee Bridge and all connected zigbee devices

        :param device:      Zigbee bridge to be discovered (equal to tasmota_topic)
        :return:            None
        """
        self.logger.info("Zigbee Bridge discovered: Prepare Settings and polling information of all connected zigbee devices")

        ###### Configure ZigBeeBridge ######
        self.logger.debug(f"Configuration of Tasmota Zigbee Bridge to get MQTT Messages in right format")
        for setting in self.tasmota_zigbee_bridge_stetting:
            self.publish_tasmota_topic('cmnd', device, setting, self.tasmota_zigbee_bridge_stetting[setting])
            self.logger.debug(f"_discover_zigbee_bridge: publishing to 'cmnd/{device}/setting' with payload {self.tasmota_zigbee_bridge_stetting[setting]}")

        ###### Request ZigBee Konfiguration ######
        self.logger.info("_discover_zigbee_bridge: Request configuration of Zigbee bridge")
        self.logger.debug(f"_discover_zigbee_bridge: publishing 'cmnd/{device}/ZbConfig'")
        self.publish_tasmota_topic('cmnd', device, 'ZbConfig', '')

        ###### Discovery all ZigBee Devices ######
        self.logger.info("_discover_zigbee_bridge: Discover all connected Zigbee devices")
        self.logger.debug(f"_discover_zigbee_bridge: publishing 'cmnd/{device}/ZbStatus1'")
        self.publish_tasmota_topic('cmnd', device, 'ZbStatus1', '')