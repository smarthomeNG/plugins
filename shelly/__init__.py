#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2019-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#
#  Plugin to support Shelly devices
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

import inspect


class Shelly(MqttPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '1.5.5'


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
        self.shelly_devices = {}    # dict to store information about discovered shelly devices

        # add subscription to get Gen 1 device announces (gets Gen2 announces, if device is configured correctly)
        self.add_subscription('shellies/announce', 'dict', callback=self.on_mqtt_announce)
        # not all Gen1 devices answer to 'shellies/announce', so we need another subscription 'shellies/<shelly_id>/announce'
        self.add_subscription('shellies/+/announce', 'dict', callback=self.on_mqtt_announce)

        # start subscription to all topics:

        # Get online status of Gen1 devices
        self.add_subscription('shellies/+/online', 'bool', bool_values=['false', 'true'], callback=self.on_mqtt_online)
        # Get online status of Gen2 devices
        self.add_subscription('shellies/gen2/+/online', 'bool', bool_values=['false', 'true'], callback=self.on_mqtt_online)

        # start subscription to events (for Gen2)
        #self.add_subscription('shellies/events/rpc', 'dict', callback=self.on_mqtt_gen2_events)
        # start subscription to events (for Gen2)
        self.add_subscription('shellies/gen2/+/events/#', 'dict', callback=self.on_mqtt_gen2_events)

        # start subscription to status (for Gen2)
        self.add_subscription('shellies/gen2/status/rpc', 'dict', callback=self.on_mqtt_gen2_status)


        # start subscription to all shellies topics (handles only messages for Gen1)
        self.add_subscription('shellies/#', 'dict/str', callback=self.on_mqtt_shellies)

        # if plugin should start even without web interface
        self.init_webinterface(WebInterface)

        return


    def run(self):
        """
        Run method for the plugin
        """
        self.logger.dbghigh(self.translate("Methode '{method}' aufgerufen", {'method': 'run()'}))
        self.alive = True

        self.start_subscriptions()

        # Gen1 & Gen2 API
        self.publish_topic('shellies/command', 'announce')

        # Gen 1 API
        for shelly_id in list(self.shelly_devices):
            # for Gen1 devices
            topic = 'shellies/' + shelly_id + '/command'
            self.publish_topic(topic, 'update')
            #self.publish_topic(topic, 'announce')
        return


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.dbghigh(self.translate("Methode '{method}' aufgerufen", {'method': 'stop()'}))
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
        if not self.has_iattr(item.conf, 'shelly_id'):
            return

        config_data = {}

        if self.has_iattr(item.conf, 'shelly_type') and self.get_iattr_value(item.conf, 'shelly_type') != '':
            result = self.parse_item_old(item)
            config_data['shelly_conf_id'] = self.get_iattr_value(item.conf, 'shelly_id').lower()
            config_data['shelly_type'] = self.get_iattr_value(item.conf, 'shelly_type')
            config_data['shelly_list_attrs'] = self.get_iattr_value(item.conf, 'shelly_list_attrs', False)
            self.add_item(item, config_data_dict=config_data)
            return result

        self.logger.debug(f"parsing item: {item.id()}")

        shelly_conf_id = self.get_iattr_value(item.conf, 'shelly_id').upper()

        shelly_group = self.get_iattr_value(item.conf, 'shelly_group', 'global').lower()
        shelly_attr = self.get_iattr_value(item.conf, 'shelly_attr', '').lower()

        # fill configuraton data for item
        config_data['shelly_group'] = shelly_group
        config_data['shelly_conf_id'] = shelly_conf_id.lower()

        if shelly_attr == '' or shelly_attr == 'relay':
            config_data['shelly_attr'] = 'output'
        else:
            config_data['shelly_attr'] = shelly_attr
        config_data['shelly_list_attrs'] = self.get_iattr_value(item.conf, 'shelly_list_attrs', False)

        # build mapping
        item_mapping = config_data['shelly_conf_id'] + '-' + config_data['shelly_group'] + '-' + config_data['shelly_attr']
        self.add_item(item, mapping=item_mapping, config_data_dict=config_data)

        return self.update_item


    def parse_item_old(self, item):
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
            self.logger.debug("parsing item: {0}".format(item.id()))

            if not self.has_iattr(item.conf, 'shelly_type'):
                return

            shelly_macid = self.get_iattr_value(item.conf, 'shelly_id').upper()
            shelly_type = self.get_iattr_value(item.conf, 'shelly_type').lower()
            shelly_id = shelly_type + '-' + shelly_macid

            shelly_attr = self.get_iattr_value(item.conf, 'shelly_attr')
            shelly_relay = self.get_iattr_value(item.conf, 'shelly_relay')
            if not shelly_relay:
                shelly_relay = '0'

            #if not self.shelly_devices.get(shelly_id, None):
            #    self.shelly_devices[shelly_id] = {}
            #self.shelly_devices[shelly_id]['connected_to_item'] = True

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
                #if not item in self.shelly_items:
                #    self.shelly_items.append(item)

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
        self.logger.debug("update_item: {}".format(item.id()))

        if self.alive and caller != self.get_shortname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            config_data = self.get_item_config(item)
            device_data = self.shelly_devices.get(config_data['shelly_id'], None)
            self.logger.dbghigh(f"update_item: '{item.id()}' setting device to '{item()}' - config_data={config_data} - device_data={device_data}")

            if config_data.get('gen', None) == '1':
                # Handle Gen1 device
                # publish topic with new relay state
                shelly_id = self.get_iattr_value(item.conf, 'shelly_id').upper()
                shelly_type = self.get_iattr_value(item.conf, 'shelly_type', '').lower()
                if shelly_type != '':
                    # old configuration type
                    shelly_relay = self.get_iattr_value(item.conf, 'shelly_relay')
                    if not shelly_relay:
                        shelly_relay = '0'
                    topic = 'shellies/' + shelly_type + '-' + shelly_id + '/relay/' + shelly_relay + '/command'
                    self.publish_topic(topic, item(), item, bool_values=['off', 'on'])
                else:
                    # new configuration type
                    topic = 'shellies/' + config_data.get('shelly_id', '')
                    shelly_group = config_data['shelly_group']
                    if shelly_group.startswith('switch:'):
                        topic += '/relay/' + shelly_group.split(':')[1] + '/command'
                        self.publish_topic(topic, item(), bool_values=['off', 'on'])
                    else:
                        self.logger.warning(f"update_item: Output to group {shelly_group} is not supported")
            elif config_data.get('gen', None) == '2':
                # Handle Gen2 device
                self.request_gen2_switch(config_data['shelly_id'], config_data['shelly_group'], item())
            else:
                shelly_id = self.get_iattr_value(item.conf, 'shelly_id')
                self.logger.notice(f"Device with id {shelly_id} was not discovered yet (for {item.id()}")


    def get_shelly_device_from_conf_id(self, conf_id):
        """
        Get the shelly device data for a device specified by the configuration shelly_id from items.yaml

        :param conf_id:
        :return:
        """
        conf_id = conf_id.lower()
        for shelly_id in list(self.shelly_devices.keys()):
            if self.shelly_devices[shelly_id].get('mac', '-').endswith(conf_id):
                return self.shelly_devices[shelly_id]
            # if self.shelly_devices[shelly_id]['gen'] == '1':
            #     if self.shelly_devices[shelly_id]['mac'].endswith(conf_id):
            #         return self.shelly_devices[shelly_id]
            # elif self.shelly_devices[shelly_id]['gen'] == '2':
            #     if self.shelly_devices[shelly_id]['mac'] == conf_id:
            #         return self.shelly_devices[shelly_id]
        return {}


    def isolate_version(self, version_str: str) -> str:
        try:
            wrk = version_str.split('/')[1]
            if wrk.find('@') >= 0:
                fw_ver = wrk.split('@')[0]
            else:
                fw_ver = wrk.split('-')[0]
                if len(wrk) > 1 and wrk.split('-')[1].lower().startswith('rc'):
                    fw_ver += '-' + wrk.split('-')[1]
            if fw_ver == '?':
                raise ValueError
        except:
            fw_ver = version_str
        return fw_ver


    def on_mqtt_announce(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        try:
            shelly_id = payload.get('id', None)

            #self.logger.notice(f"on_mqtt_announce: topic='{topic}', payload={payload}, qos={qos}, retain={retain}")
            #self.logger.notice(f"on_mqtt_announce: topic='{topic}', payload={payload} -> shelly_id={shelly_id} - shelly_devices[shelly_id]={self.shelly_devices.get(shelly_id, None)}")

            if shelly_id is None:
                if payload == {}:
                    self.logger.dbgmed(f"Got announce message without shelly_id: {topic}={payload}")
                else:
                    self.logger.warning(f"Got announce message without shelly_id: {topic}={payload}")
                return

            already_discovered = self.shelly_devices.get(shelly_id, {}).get('mac', None) is not None
            if not already_discovered:
                self.logger.dbghigh(f"on_mqtt_announce: payload={payload} - topic='{topic}'-> shelly_id={shelly_id} - shelly_devices[shelly_id]={self.shelly_devices.get(shelly_id, None)}")

            if self.shelly_devices.get(shelly_id, None) is None:
                self.shelly_devices[shelly_id] = {}
            if self.shelly_devices[shelly_id].get('gen', None) is None:
                self.shelly_devices[shelly_id]['gen'] = str(payload.get('gen', '1'))

            if self.shelly_devices[shelly_id]['gen'] == '1':
                self.shelly_devices[shelly_id]['mac'] = payload['mac'].lower()
                self.shelly_devices[shelly_id]['ip'] = payload['ip']
                self.shelly_devices[shelly_id]['new_fw'] = payload['new_fw']
                self.shelly_devices[shelly_id]['fw_ver'] = self.isolate_version(payload['fw_ver'])
                self.shelly_devices[shelly_id]['model'] = payload.get('model', '?')
                parts = shelly_id.split('-')
                parts = parts[:-1]
                configured_shelly_type = None
                for item in self.get_item_list():
                    if self.shelly_devices[shelly_id]['mac'].endswith(item.conf['shelly_id'].lower()):
                        self.shelly_devices[shelly_id]['connected_to_item'] = True
                        if item.conf.get('shelly_type', None) is not None:
                            configured_shelly_type = item.conf['shelly_type']
                if configured_shelly_type is None or configured_shelly_type == '':
                    self.shelly_devices[shelly_id]['app'] = '-'.join(parts)
                else:
                    self.shelly_devices[shelly_id]['app'] = '(' + configured_shelly_type + ')'
                self.shelly_devices[shelly_id]['last_contact'] = self.shtime.now().strftime('%Y-%m-%d %H:%M')
                if not already_discovered:
                    self.logger.info(f"Discovered new Shelly Gen1 device with id '{shelly_id}'")

            elif self.shelly_devices[shelly_id]['gen'] == '2':
                self.shelly_devices[shelly_id]['mac'] = payload['mac'].lower()
                self.shelly_devices[shelly_id]['ip'] = ''
                self.shelly_devices[shelly_id]['new_fw'] = '?'
                self.shelly_devices[shelly_id]['fw_ver'] = payload['ver']    # payload['fw_id']
                self.shelly_devices[shelly_id]['model'] = payload.get('model', '?')
                self.shelly_devices[shelly_id]['app'] = payload['app']
                for item in self.get_item_list():
                    if item.conf['shelly_id'].lower() == self.shelly_devices[shelly_id]['mac']:
                        self.shelly_devices[shelly_id]['connected_to_item'] = True
                self.shelly_devices[shelly_id]['last_contact'] = self.shtime.now().strftime('%Y-%m-%d %H:%M')
                if not already_discovered:
                    self.logger.info(f"Discovered new Shelly Gen2 device with id '{shelly_id}'")
                self.request_gen2_status(shelly_id)     # Requesting device status to get ip address

            else:
                if not already_discovered:
                    self.logger.notice(f"Discovered new Shelly device with unknown API version (id '{shelly_id}') - Gen={self.shelly_devices[shelly_id]['gen']}")

            self.shelly_devices[shelly_id]['connected_to_item'] = self.shelly_devices[shelly_id].get('connected_to_item', False)

            # add device info to item config_data
            item_list = self.get_item_list(filter_key='shelly_conf_id', filter_value=self.shelly_devices[shelly_id]['mac'], mode='end')
            self.shelly_devices[shelly_id]['list_attrs'] = False
            for item in item_list:
                config_data = self.get_item_config(item)
                config_data['shelly_id'] = shelly_id
                config_data['shelly_macid'] = self.shelly_devices[shelly_id]['mac']
                config_data['gen'] = self.shelly_devices[shelly_id]['gen']
                self.shelly_devices[shelly_id]['conf_id'] = config_data['shelly_conf_id']
                if config_data['shelly_list_attrs']:
                    self.shelly_devices[shelly_id]['list_attrs'] = config_data['shelly_list_attrs']

        except Exception as e:
            self.logger.exception(f"{inspect.stack()[0][3]}: Exception {e.__class__.__name__}: {e}\n- mqtt-topic={topic}\n- mqtt-payload={payload}")

        return


    def on_mqtt_online(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        try:
            topic_split =  topic.split('/')
            if topic_split[1] == 'gen2':
                shelly_id = topic.split('/')[2]
            else:
                shelly_id = topic.split('/')[1]

            if retain == 1:
                self.logger.dbghigh(f"on_mqtt_online: topic {topic} = {payload}, qos={qos} ignored because retain-flag was set -> shelly_id={shelly_id}")
                return

            if not self.shelly_devices.get(shelly_id, None):
                self.shelly_devices[shelly_id] = {}
                self.shelly_devices[shelly_id]['online'] = payload
                self.logger.dbghigh(f"on_mqtt_online: topic {topic} = {payload}, qos={qos} -> not yet discovered shelly_id={shelly_id}")
                # Gen1 & Gen2 API call for announce data
                self.publish_topic('shellies/command', 'announce')
                return

            self.logger.dbghigh(f"on_mqtt_online: topic {topic} = {payload}, qos={qos} -> shelly_id={shelly_id}")
            self.shelly_devices[shelly_id]['online'] = payload

        except Exception as e:
            self.logger.exception(f"{inspect.stack()[0][3]}: Exception {e.__class__.__name__}: {e}\n- mqtt-topic={topic}\n- mqtt-payload={payload}")

        return

    # ----------------------------- Handling for Gen2 API -----------------------------

    def handle_gen2_event(self, shelly_id: str, event: dict):
        """
        Handle event information received from a Shelly device with Gen2 API

        :param shelly_id: Id of the shelly device
        :param event: Event information

        :return:
        """
        #if shelly_devices.get('shelly_id')
        self.logger.notice(f"handle_gen2_event: NO action {shelly_id} event={event}")

    logged_attrs = []

    def update_items_from_status(self, shelly_id, group, attr, value, source=None):

        if group == '':
            mapping = '-global-' + attr
        else:
            mapping = '-' + group + '-' + attr

        if self.shelly_devices[shelly_id]['gen'] == '1':
            # get the given part of the mac address (complete mac address is not given in config for Gen1 devices)
            parts = shelly_id.split('-')
            item_mapping = parts[-1:][0].lower() + mapping
        elif self.shelly_devices[shelly_id]['gen'] == '2':
            item_mapping = self.shelly_devices[shelly_id]['mac'] + mapping
        else:
            self.logger.error(f"update_items_from_status: Unknown API version for {shelly_id}")
            return

        if self.shelly_devices[shelly_id]['list_attrs']:
            # List attributes which are sent by a device, if configuration requests it
            if not shelly_id+'-'+group+'-'+attr in self.logged_attrs:
                if value is None:
                    typ = "'None' (" + self.translate("Empfangener Wert ist 'null'") + ")"
                else:
                    typ = str(type(value)).split(chr(39))[1]
                    if typ in ['float', 'int']:
                        typ = f"'num' ({typ})"
                    else:
                        typ = f"'{typ}'"

                msg = f"list_attrs '{self.shelly_devices[shelly_id]['conf_id']}' ({self.shelly_devices[shelly_id]['app']}): "
                if group == '':
                    self.logger.info(msg + f"shelly_attr='{attr}' type={typ}")
                else:
                    self.logger.info(msg + f"shelly_attr='{attr}' shelly_group='{group}' type={typ}")
                self.logged_attrs.append(shelly_id+'-'+group+'-'+attr)

        gen = self.shelly_devices[shelly_id]['gen']
        items = self.get_items_for_mapping(item_mapping)
        for item in items:
            # Update all items with the same mapping
            if gen == '2' or (item.conf.get('shelly_type', None) is None or item.conf['shelly_type'] == ''):
                self.logger.dbghigh(f"update_items_from_status: Gen{gen} '{item.id()}', value={value}")
                if source:
                    source = self.shelly_devices[shelly_id]['app'] + ':' + source
                else:
                    source = self.shelly_devices[shelly_id]['app']
                item(value, self.get_shortname(), source)


    def handle_gen2_device_status(self, shelly_id, group, status):
        """
        Handle ststus information for switches

        :param shelly_id:
        :param status_type:
        :param status:
        :return:
        """
        group = group
        self.logger.dbgmed(f"handle_gen2_device_status: '{shelly_id}' {group} = {status}")
        for property in status.keys():
            logged = False
            source = status.get('source', None)
            sub_status = status[property]
            # properties for any group
            if property in ['id', 'source']:
                self.logger.dbgmed(f"handle_gen2_device_status: Ignored '{property}'={sub_status} - (for shelly_id={shelly_id})")
                logged = True

            elif group.startswith('switch:'):
                if property == 'temperature':
                    self.update_items_from_status(shelly_id, group, 'temp', sub_status['tC'])
                    self.update_items_from_status(shelly_id, group, 'temp_f', sub_status['tF'])
                elif property == 'output':
                    self.update_items_from_status(shelly_id, group, property, sub_status, source)
                elif property in ['apower', 'voltage', 'current', 'pf']:
                    self.update_items_from_status(shelly_id, group, property, sub_status)
                elif property == 'aenergy':
                    self.update_items_from_status(shelly_id, group, 'energy', sub_status['total'])
                    # Energy consumption by minute (in Milliwatt-hours) for the last three minutes (the lower the index of the element in the array, the closer to the current moment the minute)
                    if sub_status.get('by_minute', None) is not None:
                        self.update_items_from_status(shelly_id, group, 'energy_by_minute', sub_status['by_minute'][0])
                else:
                    self.log_unhandled_status(shelly_id, property, sub_status, params=status, group=group, position='*ds1')
                    logged = True

            elif group.startswith('input:'):
                if property == 'state':
                    self.update_items_from_status(shelly_id, group, property, sub_status, source)
                elif property == 'percent':    # Analog input of ShellyPlus 2PM ADD-ON
                    self.update_items_from_status(shelly_id, group, property, sub_status, source)
                else:
                    self.log_unhandled_status(shelly_id, property, sub_status, params=status, group=group, position='*ds2')
                    logged = True

            elif group.startswith('humidity:'):
                if property == 'rh':           # Humidity (DHT22) of ShellyPlus 2PM ADD-ON
                    self.update_items_from_status(shelly_id, group, property, sub_status, source)
                elif property == 'errors':
                    self.update_items_from_status(shelly_id, group, property, sub_status, source)
                else:
                    self.log_unhandled_status(shelly_id, property, sub_status, params=status, group=group, position='*ds3')
                    logged = True

            elif group.startswith('devicepower:'):
                if property == 'battery':
                    self.update_items_from_status(shelly_id, group, 'battery', sub_status['percent'])
                    self.update_items_from_status(shelly_id, group, 'voltage', sub_status['V'])
                if property == 'external':
                    self.update_items_from_status(shelly_id, group, 'external_power', sub_status['present'])

            elif group.startswith('temperature:'):
                if property == 'tC':
                    self.update_items_from_status(shelly_id, group, 'temp', sub_status)
                if property == 'tF':
                    self.update_items_from_status(shelly_id, group, 'temp_f', sub_status)

            elif group.startswith('voltmeter:'):
                if property == 'voltage':  # Voltmeter of ShellyPlus 2PM ADD-ON
                    self.update_items_from_status(shelly_id, group, property, sub_status, source)
                else:
                    self.log_unhandled_status(shelly_id, property, sub_status, params=status, group=group, position='*sw1')
                    logged = True

            # properties pf, freq, errors are not yet implemented
            else:
                self.log_unhandled_status(shelly_id, property, sub_status, params=status, group=group, position='*sw1')
                logged = True
            if not logged:
                self.logger.dbghigh(f"handle_gen2_device_status: Handled '{property}'={sub_status} - (for shelly_id={shelly_id})")


    short_log = False
    devices_with_unhandled_status = []
    unhandled_status_logged = []

    def log_unhandled_status(self, shelly_id, param_name, param_content, params=None, topic=None, payload=None, group='', position=''):

        calling_method = inspect.stack()[1][3]
        gen = 'Gen' + self.shelly_devices[shelly_id].get('gen', '?')
        if gen == 'Gen?':
            self.logger.warning(f"log_unhandled_status: Unknown API version for '{shelly_id}' device data = {self.shelly_devices[shelly_id]}")

        if not shelly_id in self.devices_with_unhandled_status:
            self.logger.notice(self.translate("Unbekannter Status empfangen von '{shelly_id}' - Loglevel des Plugin-Loggers auf INFO setzen und das Details-Log beobachten", {'shelly_id': shelly_id}))
            self.devices_with_unhandled_status.append(shelly_id)

        if shelly_id + '-' + group + '-' + param_name in self.unhandled_status_logged:
            return

        msg = self.translate("Unbehandelter {gen} Status", {'gen', gen})
        if self.short_log:
            if group != '':
                group = "Group '" + group + "' "
            if payload is None:
                self.logger.info(f"{gen}: {group}Parameter='{param_name}'={param_content}  ---  params={params} - für {shelly_id} {position}")
            else:
                self.logger.info(f"{gen}: {group}Parameter='{param_name}'={param_content}  ---  payload={payload} - für {shelly_id} {position}")
            return

        msg += f" für {shelly_id}:"
        if self.shelly_devices[shelly_id].get('model', '?') != '?':
            msg += f"\n - Model='{self.shelly_devices[shelly_id]['model']}'"
        msg += f"\n - API: {gen}"
        if self.shelly_devices[shelly_id].get('app', '?') != '?':
            msg += f"\n - App={self.shelly_devices[shelly_id]['app']}"
        msg += f"\n - Client_ID={shelly_id}"
        msg += f"\n - Parameter: '{param_name}'={param_content}"
        if group is not None:
            msg += f"\n - Group='{group}'"
            if group == param_name:
                msg += " (unimplemented)"
        if params is not None:
            msg += f"\n - Params={params}"
        if topic is not None:
            msg += f"\n - Topic={topic}"
        if payload is not None:
            msg += f"\n - Payload={payload}"
        msg += f"\n - Calling method={calling_method}"
        if position != '':
            msg += f" (pos='{position}')"

        self.logger.info(msg)
        self.unhandled_status_logged.append(shelly_id + '-' + group + '-' + param_name)


    def handle_gen2_status(self, shelly_id: str, params: dict):
        """
        Handle status information received from a Shelly device with Gen2 API

        :param shelly_id: Id of the shelly device
        :param event: Event information

        :return:
        """
        self.logger.dbgmed(f"handle_gen2_status: {shelly_id} params={params}")
        for group in params.keys():
            sub_status = params[group]
            if group in ['ts', 'ble', 'cloud', 'mqtt', 'ws', 'plugs_ui', 'ht_ui']:
                pass
            elif group == 'sys':
                available_updates = sub_status.get('available_updates', None)
                if available_updates is None or available_updates == {}:
                    self.shelly_devices[shelly_id]['new_fw'] = False
                else:
                    keys = list(available_updates.keys())
                    if 'stable' in keys:
                        self.shelly_devices[shelly_id]['new_fw'] = available_updates['stable']['version']
                    elif 'beta' in keys:
                        self.shelly_devices[shelly_id]['new_fw'] = available_updates['beta']['version']
                    elif keys == []:
                        pass
                    else:
                        self.logger.notice("handle_gen2_status: " + self.translate("Unbekannte(r) Software Type(en)") + f": {keys} - from {shelly_id}")

            elif group == 'wifi':
                # status, ssid
                self.shelly_devices[shelly_id]['ip'] = sub_status.get('sta_ip', '')
                self.shelly_devices[shelly_id]['rssi'] = sub_status.get('rssi', '')


            elif group.find(':') > 0:
                self.handle_gen2_device_status(shelly_id, group, sub_status)

            elif group == 'was_on':
                # ignore receipt status messages
                pass
            else:
                #self.logger.notice("handle_gen2_status: " + self.translate("Unbehandelter Parameter") + f" '{status_type}'={sub_status}  ---  params={status} - from {shelly_id}")
                self.log_unhandled_status(shelly_id, group, sub_status, params=params, group=group, position='*g2s1')


    def on_mqtt_gen2_events(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        try:
            if payload == {}:
                self.logger.dbgmed(f"Got event message without payload: {topic}={payload}")
                return

            shelly_id = payload.get('src', None)
            if shelly_id is None:
                self.logger.notice(f"on_mqtt_gen2_events: Message without shelly_id in the payload - {topic}, {payload}")
                return
            if self.shelly_devices.get(shelly_id) is None:
                self.logger.notice(f"on_mqtt_gen2_events: From undiscovered device - {topic}, {payload}")
                self.publish_topic('shellies/command', 'announce')
                return
            if self.shelly_devices[shelly_id].get('mac', None) is None:
                self.logger.dbgmed(f"on_mqtt_gen2_events: Message before discovery of '{shelly_id}' ignored - {topic}, {payload}")
                return

            self.shelly_devices[shelly_id]['last_contact'] = self.shtime.now().strftime('%Y-%m-%d %H:%M')

            topic_parts = topic.split('/')
            if len(topic_parts) == 5:
                shelly_id = payload['src']
                self.logger.dbghigh(f"on_mqtt_gen2_events: {topic} payload={payload} -> shelly_id={shelly_id}")
                if payload['method'] == 'NotifyEvent':
                    if payload.get('params', None) is not None:
                        self.handle_gen2_event(shelly_id, payload['params'])
                    else:
                        self.logger.notice(f"on_mqtt_gen2_events: Unexpected NotifyEvent: topic {topic} payload={payload}")
                elif payload['method'] in ['NotifyStatus', 'NotifyFullStatus']:   # NotifyFullStatus is used by Shelly PlusHT
                    if payload.get('params', None) is not None:
                        self.handle_gen2_status(shelly_id, payload['params'])
                    else:
                        self.logger.notice(f"on_mqtt_gen2_events: Unexpected NotifyStatus (no 'param' present): topic {topic} payload={payload}")
                else:
                    self.logger.notice(f"on_mqtt_gen2_events: Unexpected method '{payload['method']}': topic {topic} payload={payload}")
            else:
                self.logger.notice(f"on_mqtt_gen2_events: Unexpected message: topic {topic} payload={payload}")

        except Exception as e:
            self.logger.exception(f"{inspect.stack()[0][3]}: Exception {e.__class__.__name__}: {e}\n- mqtt-topic={topic}\n- mqtt-payload={payload}")
        return


    def send_gen2_request(self, shelly_id, payload):
        """
        Send a request to a Gen2 device
        :param shelly_id:
        :param payload:

        :return:
        """
        self.logger.dbgmed(f"send_gen2_request: topic={'shellies/gen2/' + shelly_id + '/rpc'} - payload={payload}")
        self.publish_topic('shellies/gen2/' + shelly_id + '/rpc', payload)
        return


    def request_gen2_status(self, shelly_id):
        """
        Request status information from a shelly Gen2 device
        :param shelly_id:

        :return:
        """
        payload = {'id': 4711, 'src': 'shellies/gen2/status', 'method': 'Shelly.GetStatus'}
        self.send_gen2_request(shelly_id, payload)
        self.logger.dbghigh(f"request_gen2_status: Status requested for {shelly_id}, payload={payload}")
        return


    from typing import Union

    def request_gen2_switch(self, shelly_id: str, group: Union[int, str], onoff: bool):
        """
        Request status information from a shelly Gen2 device

        :param shelly_id: Id of the shelly device
        :param switch: Switch number on the device
        :param onoff: New state
        """
        if group.split(':')[0] != 'switch':
            self.logger.error(f"request_gen2_switch: Unexpected shelly_group '{group}'")
            return

        switch = int(group.split(':')[1])
        payload = {'id': 4712, 'src': 'shellies/gen2/status', 'method': 'Switch.Set', "params": {"id": switch, "on": onoff}}
        self.send_gen2_request(shelly_id, payload)
        self.logger.notice(f"request_gen2_switch: Requested switch {onoff} for {shelly_id} switch{switch} - payload={payload}")
        return


    def on_mqtt_gen2_status(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle received messages

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        try:
            if payload == {}:
                self.logger.dbgmed(f"Got event message without payload: {topic}={payload}")
                return

            self.logger.dbgmed(f"on_mqtt_gen2_status: topic {topic} = {payload}")
            if payload.get('src', None) is None:
                self.logger.warning("on_mqtt_gen2_status: " + self.translate("Unbekannter status, Quelle 'src' fehlt") + f" - topic={topic}, payload={payload}")
            else:
                shelly_id = payload['src']
                self.shelly_devices[shelly_id]['last_contact'] = self.shtime.now().strftime('%Y-%m-%d %H:%M')
                self.handle_gen2_status(shelly_id, payload['result'])

        except Exception as e:
            self.logger.exception(f"{inspect.stack()[0][3]}: Exception {e.__class__.__name__}: {e}\n- mqtt-topic={topic}\n- mqtt-payload={payload}")
        return


    def handle_gen1_status(self, shelly_id: str, property, topic, payload, group=None):
        """
        Handle status information received from a Shelly device with Gen1 API

        :param shelly_id: Id of the shelly device
        :param event: Event information

        :return:
        """
        self.logger.dbgmed(f"handle_gen1_status: {shelly_id} payload={payload}")

        if group is None:
            property_mapping = {'temperature': 'temp', 'temperature_f': 'temp_f'}
            if property.startswith('command'):
                pass
            elif property == 'online':
                #mapping = 'global-' + property
                self.update_items_from_status(shelly_id, '', property, payload)
            elif property in ['temperature', 'temperature_f', 'overtemperature']:
                if property in property_mapping:
                    property = property_mapping[property]
                #mapping = 'global-' + property
                self.update_items_from_status(shelly_id, '', property, payload)
            elif property == 'info' and isinstance(payload, dict):
                for property in payload.keys():
                    sub_status = payload[property]
                    if property in ['accel', 'lux', 'cloud', 'mqtt', 'time', 'unixtime', 'serial', 'mac', 'cfg_changed_cnt',
                                    'actions_stats', 'inputs', 'is_valid', 'act_reasons', 'connect_retries',
                                    'sensor_error', 'update', 'ram_total', 'ram_free', 'fs_size', 'fs_free', 'uptime']:
                        # sub types for 'info' (shellysw2):
                        #  - 'accel' ('tilt', 'vibration')
                        #  - 'lux' ('value', 'illumination')
                        # are handled throuh sensor group
                        pass
                    elif property == 'has_update':
                        pass

                    elif property == 'sensor':
                        self.update_items_from_status(shelly_id, 'sensor', 'state', sub_status['state'], 'info')

                    elif property == 'bat':
                        self.update_items_from_status(shelly_id, 'sensor', 'battery', sub_status['value'], 'info')
                        self.update_items_from_status(shelly_id, 'sensor', 'voltage', sub_status['voltage'], 'info')

                    elif property == 'tmp':    # from Shelly Door/Window2
                        # use temp value from 'sensor' group for °C
                        #self.update_items_from_status(shelly_id, '', 'temp', sub_status['tC'], 'info')
                        self.update_items_from_status(shelly_id, '', 'temp_f', sub_status['tF'], 'info')

                    elif property == 'charger':
                        self.update_items_from_status(shelly_id, 'sensor', property, sub_status, 'info')

                    elif property == 'wifi_sta':
                        self.shelly_devices[shelly_id]['ip'] = sub_status.get('ip', '')
                        self.shelly_devices[shelly_id]['rssi'] = sub_status.get('rssi', '')

                    else:
                        #self.logger.notice("handle_gen1_status: " + self.translate("Unbehandelter Status") + f" '{property}'={sub_status} - payload={payload} from {shelly_id} *1")
                        self.log_unhandled_status(shelly_id, property, sub_status, topic=topic, payload=payload, position='*1')


        elif group.startswith('switch:'):
            if property in ['output', 'power', 'energy']:
                self.update_items_from_status(shelly_id, group, property, payload)
                self.logger.dbghigh(f"handle_gen1_status: {shelly_id} {group} - {property}={payload}  -  (mapping={group + '-' + property})")
            else:
                self.logger.notice(f"handle_gen1_status: {shelly_id} {group} - {property}={payload}")

        elif group == 'sensor':
            if property in ['state', 'tilt', 'vibration', 'lux', 'illumination', 'battery',
                            'error', 'charger', 'act_reasons']:
                self.update_items_from_status(shelly_id, 'sensor', property, payload)
            elif property == 'temperature':
                self.update_items_from_status(shelly_id, '', 'temp', payload)
            else:
                self.logger.notice("handle_gen1_status: " + self.translate("Unbehandelter Status") + f"main_property={group} - {property}={payload} - from {shelly_id} *2")
                self.log_unhandled_status(shelly_id, property, payload, payload=payload, group=group, position='*2')

        elif group == 'input_event':
            group += ':' + property
            for property in payload.keys():
                sub_status = payload[property]
                if property == 'event_cnt':
                    pass
                elif property == 'event':
                    self.update_items_from_status(shelly_id, group, property, sub_status)
                else:
                    self.logger.notice("handle_gen1_status: " + self.translate("Unbehandelter Status") + f" '{property}'={sub_status} - payload={payload} from {shelly_id} *3")
                    self.log_unhandled_status(shelly_id, property, sub_status, payload=payload, position='*3')

        else:
            self.logger.notice("handle_gen1_status: " + self.translate("Unbehandelter Status") + f" property='{property}'={payload} - from {shelly_id} *4")
            self.log_unhandled_status(shelly_id, property, payload, payload=payload, position='*4')


    def on_mqtt_shellies(self, topic, payload, qos=None, retain=None):
        """
        Callback function to handle all received messages from shellies to support Gen1 devices

        :param topic:
        :param payload:
        :param qos:
        :param retain:
        """
        try:
            if payload == {}:
                self.logger.dbgmed(f"on_mqtt_shellies: Received empty payload (dict) with topic {topic}")
                return

            #self.logger.notice(f"on_mqtt_shellies: Entry {topic=}, {payload=} ({type(payload)=})")
            if topic.endswith('/rpc'):
                return
            topic_parts = topic.split('/')
            if topic_parts[1].lower() in ['gen2', 'command', 'announce']:
                return
            if 'announce' in topic_parts:
                return

            shelly_id = topic_parts[1]
            if not self.shelly_devices.get(shelly_id, None) or self.shelly_devices[shelly_id].get('gen', None) is None:
                self.logger.dbghigh(f"on_mqtt_shellies: not discovered Gen1 device {shelly_id} - {topic}={payload}")
                return

            self.shelly_devices[shelly_id]['last_contact'] = self.shtime.now().strftime('%Y-%m-%d %H:%M')
            property = topic_parts[2]

            if property == 'relay':
                relay = topic_parts[3]
                switch = 'switch:' + relay
                if len(topic_parts) == 5:
                    property = topic_parts[4]
                else:
                    property = 'output'
                    payload = (payload == 'on')
                self.handle_gen1_status(shelly_id, property, topic, payload, switch)
            elif property == 'sensor':
                if len(topic_parts) == 4:
                    property = topic_parts[3]
                self.handle_gen1_status(shelly_id, property, topic, payload, 'sensor')
            elif property == 'input_event':
                if len(topic_parts) == 4:
                    property = topic_parts[3]
                self.handle_gen1_status(shelly_id, property, topic, payload, 'input_event')
            else:
                #self.logger.notice(f"on_mqtt_shellies: {shelly_id} - {property}={payload}")
                self.handle_gen1_status(shelly_id, property, topic, payload)

        except Exception as e:
            self.logger.exception(f"{inspect.stack()[0][3]}: Exception {e.__class__.__name__}: {e}\n- mqtt-topic={topic}\n- mqtt-payload={payload}")
        return

# --------------------  for the web interface  --------------------

    def ja_nein(self, value) -> str:
        """
        Bool Wert in Ja/Nein String wandeln

        :param value:
        :return:
        """
        if isinstance(value, bool):
            if value:
                return self.translate('Ja')
            return self.translate('Nein')
        return value
