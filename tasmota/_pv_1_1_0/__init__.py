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

import json

from datetime import datetime, timedelta

from lib.module import Modules
from lib.model.mqttplugin import *
from lib.item import Items

from .webif import WebInterface


class Tasmota(MqttPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.1.0'

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
        self.tasmota_devices = {}            # to hold device information for web interface
        self.tasmota_items = []              # to hold item information for web interface
        self.tasmota_meta = {}               # to hold meta information for web interface

        # add subscription to get device announces
        # ('tele' topics are sent every 5 minutes)
        self.add_tasmota_subscription('tele', '+', 'LWT', 'bool', bool_values=['Offline', 'Online'], callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'STATE', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'SENSOR', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'INFO1', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'INFO2', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'INFO3', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'RESULT', 'dict', callback=self.on_mqtt_announce)
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

        for topic in self.tasmota_devices:
            # ask for status info of each known tasmota_topic, collected during parse_item
            self.logger.debug(f"run: publishing 'cmnd/{topic}/STATUS'") 
            self.publish_topic(f"cmnd/{topic}/STATUS", 0)
            self.logger.debug(f"run: publishing 'cmnd/{topic}/Module'")
            self.publish_topic(f"cmnd/{topic}/Module", "")
            
            # set telemetry period for each known tasmota_topic, collected during parse_item
            self.logger.info(f"run: Setting telemetry period to {self.telemetry_period} seconds")
            self.logger.debug(f"run: publishing 'cmnd/{topic}/teleperiod'")
            self.publish_topic(f"cmnd/{topic}/teleperiod", self.telemetry_period)

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
        if self.has_iattr(item.conf, 'tasmota_topic'):
            self.logger.debug(f"parsing item: {item.property.path}")

            tasmota_topic = self.get_iattr_value(item.conf, 'tasmota_topic')
            tasmota_attr = self.get_iattr_value(item.conf, 'tasmota_attr')
            tasmota_relay = self.get_iattr_value(item.conf, 'tasmota_relay')
            if not tasmota_relay:
                tasmota_relay = '1'
            #self.logger.debug(f" - tasmota_topic={tasmota_topic}, tasmota_attr={tasmota_attr}, tasmota_relay={tasmota_relay}")
            #self.logger.debug(f" - tasmota_topic={tasmota_topic}, item.conf={item.conf}")

            if not self.tasmota_devices.get(tasmota_topic):
                self.tasmota_devices[tasmota_topic] = {}
                self.tasmota_devices[tasmota_topic]['connected_to_item'] = False        # is tasmota_topic connected to any item?
                self.tasmota_devices[tasmota_topic]['connected_items'] = {}
                self.tasmota_devices[tasmota_topic]['uptime'] = '-'
                self.tasmota_devices[tasmota_topic]['lights'] = {}
                self.tasmota_devices[tasmota_topic]['rf'] = {}
                self.tasmota_devices[tasmota_topic]['sensors'] = {}
                self.tasmota_devices[tasmota_topic]['relais'] = {}

            # handle the different topics from Tasmota devices
            topic = None
            bool_values = None
            if tasmota_attr:
                tasmota_attr = tasmota_attr.lower()
                
            if tasmota_attr != '':
                self.tasmota_devices[tasmota_topic]['connected_to_item'] = True
                if tasmota_attr == 'relay':
                    self.tasmota_devices[tasmota_topic]['connected_items']['item_'+tasmota_attr+str(tasmota_relay)] = item
                else:
                    self.tasmota_devices[tasmota_topic]['connected_items']['item_'+tasmota_attr] = item
                if tasmota_attr == 'online':
                    self.tasmota_devices[tasmota_topic]['online'] = False
                # append to list used for web interface
                if not item in self.tasmota_items:
                    self.tasmota_items.append(item)
            else:
                self.logger.warning(f"parse_item: attribute tasmota_attr = {tasmota_attr} not in valid list; standard attribut used, but item not processed.")

            return self.update_item


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
        self.logger.debug(f"update_item: {item.property.path}")

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped  AND only, if the item has not been changed by this this plugin:

            # get tasmota attributes of item
            tasmota_topic = self.get_iattr_value(item.conf, 'tasmota_topic')
            tasmota_attr = self.get_iattr_value(item.conf, 'tasmota_attr')
            tasmota_relay = self.get_iattr_value(item.conf, 'tasmota_relay')

            if tasmota_attr in ['relay', 'hsb', 'rf_send', 'rf_key_send']:
                self.logger.info(f"update_item: {item.property.path}, item has been changed in SmartHomeNG outside of this plugin in {caller} with value {item()}")
                value = None
                
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
                    # Format aus dem Item ist eine Liste mit 2 int Werten bspw. [299, 100, 94]
                    # Format zum Senden ist ein String mit kommagetrennten Werten
                    bool_values = None
                    topic = tasmota_topic
                    detail = 'HsbColor'
                    hsb = item()
                    if type(hsb) is list and len(hsb) == 3:
                        hsb = list(map(int, hsb))
                        value = ','.join(str(v) for v in hsb)
                    else:
                        self.logger.debug(f"update_item: hsb value received but not in correct format/content; expected format is list like [299, 100, 94]")
                    
                elif tasmota_attr == 'rf_send':
                    # publish topic with new rf data
                    # Format aus dem Item ist ein dict in folgendem Format: {'RfSync': 12220, 'RfLow': 440, 'RfHigh': 1210, 'RfCode':'#F06104'}
                    # Format zum Senden ist: "RfSync 12220; RfLow 440; RfHigh 1210; RfCode #F06104"
                    bool_values = None
                    topic = tasmota_topic
                    detail = 'Backlog'
                    rf_send = item()
                    if type(rf_send) is dict:
                        rf_send_lower = eval(repr(rf_send).lower())
                        #rf_send_lower = {k.lower(): v for k, v in rf_send.items()}
                        if 'rfsync' and 'rflow' and 'rfhigh' and 'rfcode' in rf_send_lower: 
                            value = 'RfSync'+' '+str(rf_send_lower['rfsync'])+'; '+'RfLow'+' '+str(rf_send_lower['rflow'])+'; '+'RfHigh'+' '+str(rf_send_lower['rfhigh'])+'; '+'RfCode'+' '+str(rf_send_lower['rfcode'])
                        else:
                            self.logger.debug(f"update_item: rf_send received but not with correct content; expected content is: {'RfSync': 12220, 'RfLow': 440, 'RfHigh': 1210, 'RfCode':'#F06104'}")
                    else:
                        self.logger.debug(f"update_item: rf_send received but not in correct format; expected format is: {'RfSync': 12220, 'RfLow': 440, 'RfHigh': 1210, 'RfCode':'#F06104'}")
                        
                elif tasmota_attr == 'rf_key_send':
                    # publish topic for rf_keyX Default send
                    bool_values = None
                    topic = tasmota_topic
                    try:
                      rf_key = int(item())
                    except:
                      self.logger.debug(f"update_item: rf_key_send received but with correct format; expected format integer or string 1-16")
                    else:  
                      if rf_key in range(1, 17):
                        detail = 'RfKey'+str(rf_key)
                        value = 1
                      else:
                        self.logger.debug(f"update_item: rf_key_send received but with correct content; expected format value 1-16")

                if value is not None:
                    #self.publish_topic('cmnd', topic, detail, item(), item, bool_values=['off','on'])
                    self.publish_tasmota_topic('cmnd', topic, detail, value, item, bool_values=bool_values)

            else:
                self.logger.warning(f"update_item: {item.property.path}, trying to change item in SmartHomeNG that is readonly in tasmota device (by {caller})")

    def poll_device(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        self.logger.info("poll_device: Checking online status and update status of reconnected devices")
        for tasmota_topic in self.tasmota_devices:
            if self.tasmota_devices[tasmota_topic].get('online') is True and self.tasmota_devices[tasmota_topic].get('online_timeout') is True:
                if self.tasmota_devices[tasmota_topic]['online_timeout'] < datetime.now():
                    self.tasmota_devices[tasmota_topic]['online'] = False
                    self._set_item_value(tasmota_topic, 'item_online', False, 'poll_device')
                    self.logger.info(f"poll_device: {tasmota_topic} is not online any more - online_timeout={self.tasmota_devices[tasmota_topic]['online_timeout']}, now={datetime.now()}")
                    # delete data from WebIF dict
                    self.tasmota_devices[tasmota_topic]['lights'] = {}
                    self.tasmota_devices[tasmota_topic]['rf'] = {}
                    self.tasmota_devices[tasmota_topic]['sensors'] = {}
                    self.tasmota_devices[tasmota_topic]['relais'] = {}
                
                # ask for status info of reconnected tasmota_topic (which was not connected during plugin start)
                if not self.tasmota_devices[tasmota_topic].get('mac'):
                    self.logger.debug(f"poll_device: reconnected device discovered, publishing 'cmnd/{tasmota_topic}/STATUS'")
                    self.publish_topic(f"cmnd/{tasmota_topic}/STATUS", 0)
                    self.logger.debug(f"poll_device: reconnected device discovered, publishing 'cmnd/{tasmota_topic}/Module'")
                    self.publish_topic(f"cmnd/{tasmota_topic}/Module", "")


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

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        
        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
            self.logger.info(f"on_mqtt_announce: type={topic_type}, device={tasmota_topic}, info_topic={info_topic}, payload={payload}")
        except Exception as e:
            self.logger.error(f"received topic {topic} is not in correct format. Error was: {e}")
        else:
            # ask for status info of this newly discovered device
            if not self.tasmota_devices.get(tasmota_topic):
                self.tasmota_devices[tasmota_topic] = {}
                self.tasmota_devices[tasmota_topic]['connected_to_item'] = False
                self.tasmota_devices[tasmota_topic]['uptime'] = '-'
                self.tasmota_devices[tasmota_topic]['lights'] = {}
                self.tasmota_devices[tasmota_topic]['rf'] = {}
                self.tasmota_devices[tasmota_topic]['sensors'] = {}
                self.tasmota_devices[tasmota_topic]['relais'] = {}
                self.logger.debug(f"on_mqtt_announce: new device discovered, publishing 'cmnd/{topic}/STATUS'")
                self.publish_topic(f"cmnd/'{tasmota_topic}/STATUS", 0)
                
            # handle different info_topics
            if info_topic == 'LWT':
                self.logger.debug(f"LWT: info_topic: {info_topic} datetime: {datetime.now()} payload: {payload}")
                self.tasmota_devices[tasmota_topic]['online'] = payload
                self._set_item_value(tasmota_topic, 'item_online', payload, info_topic)
                if payload is True:
                    self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now()+timedelta(seconds=self.telemetry_period+5)
                    #self.logger.info(f" - new 'online_timeout'={self.tasmota_devices[tasmota_topic]['online_timeout']}")
            
            
            elif info_topic == 'STATE' or info_topic == 'RESULT':

                if type(payload) is dict and ('HSBColor' or 'Dimmer' or 'Color' or 'CT' or 'Scheme' or 'Fade' or 'Speed' or 'LedTable') in payload:
                    hsb = payload['HSBColor']
                    if hsb:
                        if hsb.count(',') == 2:
                            hsb = hsb.split(",")
                            try:
                                hsb = [int(element) for element in hsb]
                            except Exception as e:
                                self.logger.info(f"Received Data for HSBColor do not contain in values for HSB. Payload was {hsb}. Error was {e}.")
                        else:
                            self.logger.info(f"Received Data for HSBColor do not contain values for HSB. Payload was {hsb}.")
                        self.tasmota_devices[tasmota_topic]['lights']['hsb'] = hsb
                        self._set_item_value(tasmota_topic, 'item_hsb', hsb, info_topic)

                    dimmer = payload.get('Dimmer')
                    if dimmer:
                        self.tasmota_devices[tasmota_topic]['lights']['dimmer'] = int(dimmer)
                    
                    color = payload.get('Color')
                    if color:
                        self.tasmota_devices[tasmota_topic]['lights']['color'] = str(color)
                        
                    ct = payload.get('CT')
                    if ct:
                        self.tasmota_devices[tasmota_topic]['lights']['ct'] = int(ct)
                        
                    scheme = payload.get('Scheme')
                    if scheme:
                        self.tasmota_devices[tasmota_topic]['lights']['scheme'] = int(scheme)
                    
                    fade = payload.get('Fade')
                    if fade:
                        self.tasmota_devices[tasmota_topic]['lights']['fade'] = bool(fade)
                    
                    speed = payload.get('Speed')
                    if speed:
                        self.tasmota_devices[tasmota_topic]['lights']['speed'] = int(speed)
                        
                    ledtable = payload.get('LedTable')
                    if ledtable:
                        self.tasmota_devices[tasmota_topic]['lights']['ledtable'] = bool(ledtable)
                        
                if {key:val for key, val in payload.items() if key.startswith('POWER')} is not None:
                        power_dict = {key:val for key, val in payload.items() if key.startswith('POWER')}
                        self.tasmota_devices[tasmota_topic]['relais'].update(power_dict)
                        
                        for power in power_dict:
                            item_relay = 'item_relay'+str(power[5:])
                            self._set_item_value(tasmota_topic, item_relay, power_dict[power], info_topic)

                if info_topic == 'STATE':
                    self.tasmota_devices[tasmota_topic]['uptime'] = payload.get('Uptime', '-')

                    if payload['Wifi'].get('Signal'):
                        self.tasmota_devices[tasmota_topic]['wifi_signal'] = int(payload['Wifi']['Signal'])
                
                else:
                    rfreceived = payload.get('RfReceived')
                    if rfreceived:
                        self.tasmota_devices[tasmota_topic]['rf']['rf_received'] = rfreceived
                        self._set_item_value(tasmota_topic, 'item_rf_recv', rfreceived['Data'], info_topic)
                        
                    elif type(payload) is dict and ('RfSync' or 'RfLow' or 'RfHigh' or 'RfCode') in payload:
                        if not self.tasmota_devices[tasmota_topic]['rf'].get('rf_send_result'):
                            self.tasmota_devices[tasmota_topic]['rf']['rf_send_result'] = payload
                        else:
                            self.tasmota_devices[tasmota_topic]['rf']['rf_send_result'].update(payload)
                        
                    elif any(item.startswith("RfKey") for item in payload.keys()):
                        self.tasmota_devices[tasmota_topic]['rf']['rfkey_result'] = payload
                    
                    module_list = payload.get('Module')
                    if module_list:
                        template, module = list(module_list.items())[0]
                        self.tasmota_devices[tasmota_topic]['module'] = module
                        self.tasmota_devices[tasmota_topic]['tasmota_template'] = template
                        
                    zb_state = payload.get('ZbState')
                    if zb_state:
                        self.tasmota_devices[tasmota_topic]['zigbee'] = payload
                
                
                self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now()+timedelta(seconds=self.telemetry_period+5)
                self._set_item_value(tasmota_topic, 'item_online', True, info_topic)

            
            elif info_topic == 'SENSOR':
                energy = payload.get('ENERGY')
                if energy:
                    if not self.tasmota_devices[tasmota_topic]['sensors'].get('ENERGY'):
                        self.tasmota_devices[tasmota_topic]['sensors']['ENERGY'] = {}
                    if type(energy) is dict:
                        self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['period'] = energy.get('Period', None)
                        if 'Voltage' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['voltage'] = energy['Voltage']
                            self._set_item_value(tasmota_topic, 'item_voltage', energy['Voltage'], info_topic)
                        if 'Current' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['current'] = energy['Current']
                            self._set_item_value(tasmota_topic, 'item_current', energy['Current'], info_topic)
                        if 'Power' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['power'] = energy['Power']
                            self._set_item_value(tasmota_topic, 'item_power', energy['Power'], info_topic)
                        if 'ApparentPower' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['apparent_power'] = energy['ApparentPower']
                        if 'ReactivePower' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['reactive_power'] = energy['ReactivePower']
                        if 'Factor' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['factor'] = energy['Factor']
                        if 'TotalStartTime' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['total_starttime'] = energy['TotalStartTime']
                        if 'Total' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['total'] = energy['Total']
                            self._set_item_value(tasmota_topic, 'item_power_total', energy['Total'], info_topic)
                        if 'Yesterday' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['yesterday'] = energy['Yesterday']
                            self._set_item_value(tasmota_topic, 'item_power_yesterday', energy['Yesterday'], info_topic)
                        if 'Today' in energy:
                            self.tasmota_devices[tasmota_topic]['sensors']['ENERGY']['today'] = energy['Today']
                            self._set_item_value(tasmota_topic, 'item_power_today', energy['Today'], info_topic)
                
                ds18b20 = payload.get('DS18B20')
                if ds18b20:
                    if not self.tasmota_devices[tasmota_topic]['sensors'].get('DS18B20'):
                        self.tasmota_devices[tasmota_topic]['sensors']['DS18B20'] = {}
                    if type(ds18b20) is dict:
                        if 'Id' in ds18b20:
                            self.tasmota_devices[tasmota_topic]['sensors']['DS18B20']['id'] = ds18b20['Id']
                            self._set_item_value(tasmota_topic, 'item_id', ds18b20['Id'], info_topic)
                        if 'Temperature' in ds18b20:
                            self.tasmota_devices[tasmota_topic]['sensors']['DS18B20']['temp'] = ds18b20['Temperature']
                            self._set_item_value(tasmota_topic, 'item_temp', ds18b20['Temperature'], info_topic)
                
                am2301 = payload.get('AM2301')
                if am2301:
                    if not self.tasmota_devices[tasmota_topic]['sensors'].get('AM2301'):
                        self.tasmota_devices[tasmota_topic]['sensors']['AM2301'] = {}
                    if type(am2301) is dict:
                        if 'Humidity' in am2301:
                            self.tasmota_devices[tasmota_topic]['sensors']['AM2301']['hum'] = am2301['Humidity']
                            self._set_item_value(tasmota_topic, 'item_hum', am2301['Humidity'], info_topic)
                        if 'Temperature' in am2301:
                            self.tasmota_devices[tasmota_topic]['sensors']['AM2301']['temp'] = am2301['Temperature']
                            self._set_item_value(tasmota_topic, 'item_temp', am2301['Temperature'], info_topic)
                        if 'DewPoint' in am2301:
                            self.tasmota_devices[tasmota_topic]['sensors']['AM2301']['dewpoint'] = am2301['DewPoint']
                            self._set_item_value(tasmota_topic, 'item_dewpoint', am2301['DewPoint'], info_topic)

                self.tasmota_devices[tasmota_topic]['online_timeout'] = datetime.now()+timedelta(seconds=self.telemetry_period+5)
                self._set_item_value(tasmota_topic, 'item_online', True, info_topic)


            elif info_topic == 'STATUS':
                fn = payload['Status'].get('FriendlyName', '')
                if fn != '':
                    if fn[0] == '[' and fn[-1] == ']':
                        fn = fn[1:-1]
                self.tasmota_devices[tasmota_topic]['friendly_name'] = fn


            elif info_topic == 'STATUS2':
                self.tasmota_devices[tasmota_topic]['fw_ver'] = payload['StatusFWR'].get('Version', '')
                
            
            elif info_topic == 'STATUS5':
                self.tasmota_devices[tasmota_topic]['ip'] = payload['StatusNET'].get('IPAddress', '')
                self.tasmota_devices[tasmota_topic]['mac'] = payload['StatusNET'].get('Mac', '')

            
            elif info_topic == 'STATUS9':
                #self.logger.info(f"Topic={topic}, tasmota_topic={tasmota_topic}, info_topic={info_topic}")
                StatusPTH = payload.get('StatusPTH', {})
                #self.logger.info(f" - StatusPTH={StatusPTH}")


            elif info_topic == 'INFO1':
                self.tasmota_devices[tasmota_topic]['fw_ver'] = payload.get('Version', '')
                self.tasmota_devices[tasmota_topic]['module'] = payload.get('Module', '')
            
            
            elif info_topic == 'INFO2':
                self.tasmota_devices[tasmota_topic]['ip'] = payload.get('IPAddress', '')
            
            
            elif info_topic == 'INFO3':
                restart_reason = payload.get('RestartReason', '')
                self.logger.warning(f"Device {tasmota_topic} (IP={self.tasmota_devices[tasmota_topic]['ip']}) just startet. Reason={restart_reason}")
                
            else:
                self.logger.info(f"Topic {info_topic} not handled in plugin.")
                
            # update tasmota_meta auf Basis von tasmota_devices
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
            return


    def on_mqtt_message(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        
        try:
            (topic_type, tasmota_topic, info_topic) = topic.split('/')
            self.logger.info(f"on_mqtt_message: type={topic_type}, tasmota_topic={tasmota_topic}, info_topic={info_topic}, payload={payload}")
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
        item = self.tasmota_devices[tasmota_topic]['connected_items'].get(itemtype, None)
        self.logger.debug(item)
        topic = ''
        src = ''
        if info_topic != '':
            topic = "  (from info_topic '" + info_topic + "'}"
            src = self.get_instance_name()
            if src != '':
                src += ':'
            src += tasmota_topic + ':' + info_topic

        if item is not None:
            item(value, self.get_shortname(), src)
            self.logger.info(f"{tasmota_topic}: Item '{item.property.path}' set to value {value}{topic}")
        else:
            self.logger.info(f"{tasmota_topic}: No item for '{itemtype}' defined to set to {value}{topic}")
        return
