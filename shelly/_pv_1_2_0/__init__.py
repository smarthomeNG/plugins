#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019-      Martin Sinn                         m.sinn@gmx.de
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


class Shelly(MqttPlugin):
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
        if self._init_complete == False:
            return

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        # self.param1 = self.get_parameter_value('param1')

        # Initialization code goes here
        self.shelly_devices = {}
        self.shelly_items = []              # to hold item information for web interface

        # add subscription to get device announces
        self.add_subscription('shellies/announce', 'dict', callback=self.on_mqtt_announce)

        # start subscription to all topics
        self.add_subscription('shellies/+/online', 'bool', bool_values=['false', 'true'], callback=self.on_mqtt_online)

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)

        return


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        self.alive = True

        self.start_subscriptions()

        self.publish_topic('shellies/command', 'announce')

        for shelly_id in self.shelly_devices:
            topic = 'shellies/' + shelly_id + '/command'
            self.publish_topic(topic, 'update')
            #self.publish_topic(topic, 'announce')
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
        if self.has_iattr(item.conf, 'shelly_id'):
            self.logger.debug("parsing item: {0}".format(item.property.path))

            shelly_macid = self.get_iattr_value(item.conf, 'shelly_id').upper()
            shelly_type = self.get_iattr_value(item.conf, 'shelly_type').lower()
            shelly_id = shelly_type + '-' + shelly_macid

            shelly_attr = self.get_iattr_value(item.conf, 'shelly_attr')
            shelly_relay = self.get_iattr_value(item.conf, 'shelly_relay')
            if not shelly_relay:
                shelly_relay = '0'

            if not self.shelly_devices.get(shelly_id, None):
                self.shelly_devices[shelly_id] = {}
            self.shelly_devices[shelly_id]['connected_to_item'] = True

            # handle the different topics from Shelly device
            topic = None
            bool_values = None
            if shelly_attr:
                shelly_attr = shelly_attr.lower()

            # shellyht, shellydw2 and shellyflood needs another topic path than the relay devices:
            if shelly_type == 'shellyht' or shelly_type == 'shellydw2' or shelly_type == 'shellyflood':
                if shelly_attr == 'humidity':
                    topic = 'shellies/' + shelly_id + '/sensor/humidity'
                elif shelly_attr == 'state':
                    topic = 'shellies/' + shelly_id + '/sensor/state'
                elif shelly_attr == 'tilt':
                    topic = 'shellies/' + shelly_id + '/sensor/tilt'
                elif shelly_attr == 'vibration':
                    topic = 'shellies/' + shelly_id + '/sensor/vibration'
                elif shelly_attr == 'lux':
                    topic = 'shellies/' + shelly_id + '/sensor/lux'
                elif shelly_attr == 'illumination':
                    topic = 'shellies/' + shelly_id + '/sensor/illumination'
                elif shelly_attr == 'flood':
                    topic = 'shellies/' + shelly_id + '/sensor/flood'
                elif shelly_attr == 'battery':
                    topic = 'shellies/' + shelly_id + '/sensor/battery'
                elif shelly_attr == 'temp':
                    topic = 'shellies/' + shelly_id + '/sensor/temperature'
                elif shelly_attr == 'error':
                    topic = 'shellies/' + shelly_id + '/sensor/error'
                elif shelly_attr == 'online':
                    topic = 'shellies/' + shelly_id + '/online'
                else:
                    self.logger.warning("parse_item: unknown attribute shelly_attr = {} for type {}".format(shelly_attr, shelly_type))
            elif shelly_attr in ['relay', None]:
                topic = 'shellies/' + shelly_id + '/relay/' + shelly_relay
                bool_values = ['off', 'on']
            elif shelly_attr == 'power':
                topic = 'shellies/' + shelly_id + '/relay/' + shelly_relay + '/power'
            elif shelly_attr == 'energy':
                topic = 'shellies/' + shelly_id + '/relay/' + shelly_relay + '/energy'
            elif shelly_attr == 'online':
                topic = 'shellies/' + shelly_id + '/online'
                bool_values = ['false', 'true']
            elif shelly_attr == 'temp':
                topic = 'shellies/' + shelly_id + '/temperature'
            elif shelly_attr == 'temp_f':
                topic = 'shellies/' + shelly_id + '/temperature_f'
            else:
                self.logger.warning("parse_item: unknown attribute shelly_attr = {} for type {}".format(shelly_attr, shelly_type))

            if topic:
                # append to list used for web interface
                if not item in self.shelly_items:
                    self.shelly_items.append(item)

                # subscribe to topic for relay state
                payload_type = item.property.type       # should be bool
                self.add_subscription(topic, payload_type, bool_values, item=item)

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
        self.logger.debug("update_item: {}".format(item.property.path))

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info("update_item: {}, item has been changed in SmartHomeNG outside of this plugin in {}".format(item.property.path, caller))

            # publish topic with new relay state
            shelly_id = self.get_iattr_value(item.conf, 'shelly_id').upper()
            shelly_type = self.get_iattr_value(item.conf, 'shelly_type').lower()
            shelly_relay = self.get_iattr_value(item.conf, 'shelly_relay')
            if not shelly_relay:
                shelly_relay = '0'
            topic = 'shellies/' + shelly_type + '-' + shelly_id + '/relay/' + shelly_relay + '/command'
            self.publish_topic(topic, item(), item, bool_values=['off','on'])


    def on_mqtt_announce(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        self.logger.info("on_mqtt_announce: announce = {}".format(payload))
        shelly_id = payload['id']

        if not self.shelly_devices.get(shelly_id, None):
            self.shelly_devices[shelly_id] = {}
            self.shelly_devices[shelly_id]['connected_to_item'] = False

        self.shelly_devices[shelly_id]['mac'] = payload['mac']
        self.shelly_devices[shelly_id]['ip'] = payload['ip']
        self.shelly_devices[shelly_id]['new_fw'] = payload['new_fw']
        self.shelly_devices[shelly_id]['fw_ver'] = payload['fw_ver']

        return


    def on_mqtt_online(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        self.logger.info("on_mqtt_online: topic {} = {}".format(topic, payload))
        shelly_id = topic.split('/')[1]

        if not self.shelly_devices.get(shelly_id, None):
            self.shelly_devices[shelly_id] = {}
            self.shelly_devices[shelly_id]['connected_to_item'] = False

        self.shelly_devices[shelly_id]['online'] = payload

        return

