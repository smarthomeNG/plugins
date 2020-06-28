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

from lib.module import Modules
from lib.model.mqttplugin import *
from lib.item import Items

from .webif import WebInterface


class Tasmota(MqttPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '0.1.0'


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
        if self._init_complete == False:
            return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        self.full_topic = self.get_parameter_value('full_topic').lower()
        if self.full_topic.find('%prefix%') == -1 or self.full_topic.find('%topic%') == -1:
            self.full_topic = '%prefix%/%topic%/'
        if self.full_topic[-1] != '/':
            self.full_topic += '/'

        # Initialization code goes here
        self.tasmota_devices = {}
        self.tasmota_items = []              # to hold item information for web interface

        # add subscription to get device announces
        self.add_tasmota_subscription('tele', '+', 'LWT', 'bool', bool_values=['Offline', 'Online'], callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'INFO1', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('tele', '+', 'INFO2', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'STATUS', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'STATUS2', 'dict', callback=self.on_mqtt_announce)
        self.add_tasmota_subscription('stat', '+', 'STATUS5', 'dict', callback=self.on_mqtt_announce)

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
            # ask for status info of this newly discovered tasmota device
            self.publish_topic('cmnd/' + topic + '/STATUS', 0)



        self.alive = True
        return


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        self.alive = False

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
            self.logger.debug("parsing item: {0}".format(item.id()))

            tasmota_topic = self.get_iattr_value(item.conf, 'tasmota_topic')

            tasmota_attr = self.get_iattr_value(item.conf, 'tasmota_attr')
            tasmota_relay = self.get_iattr_value(item.conf, 'tasmota_relay')
            if not tasmota_relay:
                tasmota_relay = '1'

            if not self.tasmota_devices.get(tasmota_topic, None):
                self.tasmota_devices[tasmota_topic] = {}
                self.tasmota_devices[tasmota_topic]['relay'] = tasmota_relay
                self.tasmota_devices[tasmota_topic]['connected_to_item'] = False

                # ask for status info of this newly discovered tasmota device
                self.publish_topic('cmnd/' + tasmota_topic + '/STATUS', 0)

            # handle the different topics from Tasmota device
            topic = None
            bool_values = None
            if tasmota_attr:
                tasmota_attr = tasmota_attr.lower()
            if tasmota_attr in ['relay', None]:
                topic = tasmota_topic
                detail = 'POWER'
                if tasmota_relay > '1':
                    detail += tasmota_relay
                bool_values = ['OFF', 'ON']
#            elif tasmota_attr == 'energy':
#                topic = 'shellies/' + tasmota_topic + '/relay/' + tasmota_relay + '/energy'
#            elif tasmota_attr == 'online':
#                topic = 'shellies/' + tasmota_topic + '/online'
#                bool_values = ['false', 'true']
#            elif tasmota_attr == 'temp':
#                topic = 'shellies/' + tasmota_topic + '/temperature'
#            elif tasmota_attr == 'temp_f':
#                topic = 'shellies/' + tasmota_topic + '/temperature_f'
            else:
                self.logger.warning("parse_item: unknown attribute tasmota_attr = {}".format(tasmota_attr))

            if topic:
                # append to list used for web interface
                if not item in self.tasmota_items:
                    self.tasmota_items.append(item)

                # subscribe to topic for relay state
                payload_type = item.property.type
                self.add_tasmota_subscription('stat', topic, detail, payload_type, bool_values=bool_values, item=item)

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
        self.logger.debug("update_item: {}".format(item.id()))

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info("update_item: {}, item has been changed in SmartHomeNG outside of this plugin in {}".format(item.id(), caller))

            # publish topic with new relay state
            tasmota_topic = self.get_iattr_value(item.conf, 'tasmota_topic')
            #tasmota_type = self.get_iattr_value(item.conf, 'tasmota_type').lower()
            tasmota_relay = self.get_iattr_value(item.conf, 'tasmota_relay')
            if not tasmota_relay:
                tasmota_relay = '1'

            bool_values = None
            topic = tasmota_topic
            detail = 'POWER'
            if tasmota_relay > '1':
                detail += tasmota_relay
            bool_values = ['OFF', 'ON']

            #self.publish_topic('cmnd', topic, detail, item(), item, bool_values=['off','on'])
            self.publish_tasmota_topic('cmnd', topic, detail, item(), item, bool_values=bool_values)


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
        self.logger.info("tasmota.on_mqtt_announce: topic = '{}', payload = '{}'".format(topic, payload))
        wrk = topic.split('/')
        tasmota_topic = wrk[1]
        info_topic = wrk[2]

        if not self.tasmota_devices.get(tasmota_topic, None):
            self.tasmota_devices[tasmota_topic] = {}
            self.tasmota_devices[tasmota_topic]['connected_to_item'] = False

            # ask for status info of this newly discovered tasmota device
            self.publish_topic('cmnd/' + tasmota_topic + '/STATUS', 0)

        if info_topic == 'LWT':
            self.tasmota_devices[tasmota_topic]['online'] = payload

        if info_topic == 'STATUS':
            fn = payload['Status'].get('FriendlyName', '')
            if fn != '':
                if fn[0] == '[' and fn[-1] == ']':
                    fn = fn[1:-1]
            self.tasmota_devices[tasmota_topic]['friendly_name'] = fn
        if info_topic == 'STATUS2':
            self.tasmota_devices[tasmota_topic]['fw_ver'] = payload['StatusFWR'].get('Version', '')
        if info_topic == 'STATUS5':
            self.tasmota_devices[tasmota_topic]['ip'] = payload['StatusNET'].get('IPAddress', '')
            self.tasmota_devices[tasmota_topic]['mac'] = payload['StatusNET'].get('Mac', '')

        # Get info direct after boot of client
        if info_topic == 'INFO1':
            self.tasmota_devices[tasmota_topic]['fw_ver'] = payload.get('Version', '')
        if info_topic == 'INFO2':
            self.tasmota_devices[tasmota_topic]['ip'] = payload.get('IPAddress', '')

        return

