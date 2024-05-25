#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2024      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  hue3 plugin to run with SmartHomeNG
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

import qhue
import requests
import xmltodict

# new for asyncio -->
import threading
import asyncio
from concurrent.futures import CancelledError
import time

from aiohue import HueBridgeV2
# <-- new for asyncio

# for hostname retrieval for registering with the bridge
from socket import getfqdn

from lib.model.smartplugin import *
from lib.item import Items

from .webif import WebInterface

from .discover_bridges import discover_bridges

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory

mapping_delimiter = '|'


class HueApiV2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '3.0.1'    # (must match the version specified in plugin.yaml)

    hue_sensor_state_values          = ['daylight', 'temperature', 'presence', 'lightlevel', 'status']

    v2bridge = None         # Bridge object for communication with the bridge


    def __init__(self, sh):
        """
        Initalizes the plugin.

        If you need the sh object at all, use the method self.get_sh() to get it. There should be almost no need for
        a reference to the sh object any more.

        Plugins have to use the new way of getting parameter values:
        use the SmartPlugin method get_parameter_value(parameter_name). Anywhere within the Plugin you can get
        the configured (and checked) value for a parameter by calling self.get_parameter_value(parameter_name). It
        returns the value in the datatype that is defined in the metadata.
        """

        # Call init code of parent class (SmartPlugin)
        super().__init__()

        # get the parameters for the plugin (as defined in metadata plugin.yaml):
        #self.bridge_type = self.get_parameter_value('bridge_type')
        self.bridge_serial = self.get_parameter_value('bridge_serial')
        self.bridge_ip = self.get_parameter_value('bridge_ip')
        self.bridge_user = self.get_parameter_value('bridge_user')

        # polled for value changes by adding a scheduler entry in the run method of this plugin
        self._default_transition_time = int(float(self.get_parameter_value('default_transitionTime'))*1000)

        self.discovered_bridges = []
        self.bridge = {}

        # dict to store information about items handled by this plugin
        self.plugin_items = {}

        self.init_webinterface(WebInterface)

        return


    def update_plugin_config(self):
        """
        Update the plugin configuration of this plugin in ../etc/plugin.yaml

        Fill a dict with all the parameters that should be changed in the config file
        and call the Method update_config_section()
        """
        conf_dict = {}
        conf_dict['bridge_serial'] = self.bridge.get('serialNumber','')
        conf_dict['bridge_user'] = self.bridge.get('username','')
        conf_dict['bridge_ip'] = self.bridge.get('ip','')
        self.update_config_section(conf_dict)
        self.bridge_ip = conf_dict['bridge_ip']
        return


    # ----------------------------------------------------------------------------------

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")

        # Start the asyncio eventloop in it's own thread
        # and set self.alive to True when the eventloop is running
        self.start_asyncio(self.plugin_coro())

        # self.alive = True     # if using asyncio, do not set self.alive here. Set it in the session coroutine

        while not self.alive:
            time.sleep(0.1)

        if self.bridge_ip != '0.0.0.0':
            self.bridge = self.get_bridge_desciption(self.bridge_ip)
        self.bridge['username'] = self.bridge_user
        if self.bridge.get('ip', '') != self.bridge_ip:
            # if ip address of bridge has changed, store new ip address in configuration data
            self.update_plugin_config()

        return


    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")

        # self.alive = False     # if using asyncio, do not set self.alive here. Set it in the session coroutine

        # Stop the asyncio eventloop and it's thread
        self.stop_asyncio()
        return


    # ----------------------------------------------------------------------------------

    def bridge_is_configured(self):

        if self.bridge_ip == '0.0.0.0' or self.bridge_ip == '':
            return False
        return True
        # return self.v2bridge is not None and self.v2bridge.host != '0.0.0.0'


    async def plugin_coro(self):
        """
        Coroutine for the session that communicates with the hue bridge

        This coroutine opens the session to the hue bridge and
        only terminate, when the plugin ois stopped
        """
        self.logger.info("plugin_coro started")

        self.logger.debug("plugin_coro: Opening session")

        if not self.bridge_is_configured():
            self.logger.notice(f"No bridge configured - waiting until bridge is configured..")
            while not self.bridge_is_configured():
                await asyncio.sleep(1)
            self.logger.notice(f"Connecting to bridge {self.bridge_ip} / {self.bridge_user}")
        else:
            self.logger.info(f"Connecting to bridge {self.bridge_ip} / {self.bridge_user}")

        self.v2bridge = HueBridgeV2(self.bridge_ip, self.bridge_user)

        self.alive = True
        self.logger.info("plugin_coro: Plugin is running (self.alive=True)")

        async with self.v2bridge:
            self.logger.info(f"plugin_coro: Connected to bridge: {self.v2bridge.bridge_id}")
            self.logger.info(f" - device id: {self.v2bridge.config.bridge_device.id}")
            self.logger.info(f" - name     : {self.v2bridge.config.bridge_device.metadata.name}")

            self.unsubscribe_function = self.v2bridge.subscribe(self.handle_event)

            try:
                self.initialize_items_from_bridge()
            except Exception as ex:
                # catch exception to prevent plugin_coro from unwanted termination
                self.logger.exception(f"Exception in initialize_items_from_bridge(): {ex}")

            # block: wait until a stop command is received by the queue
            #queue_item = await self.run_queue.get()
            #queue_item = await self.get_command_from_run_queue()
            await self.wait_for_asyncio_termination()

        self.alive = False
        self.logger.info("plugin_coro: Plugin is stopped (self.alive=False)")

        self.logger.debug("plugin_coro: Closing session")
        # husky2: await self.apiSession.close()
        #self.unsubscribe_function()

        self.logger.info("plugin_coro finished")
        return


    def handle_event(self, event_type, event_item, initialize=False):
        """
        Callback function for bridge.subscribe()
        """
        if isinstance(event_type, str):
            e_type = event_type
        else:
            e_type = str(event_type.value)
        if e_type == 'update':
            if event_item.type.value == 'light':
                self.update_light_items_from_event(event_item, initialize)
            elif event_item.type.value == 'grouped_light':
                self.update_group_items_from_event(event_item, initialize)
            elif event_item.type.value == 'zigbee_connectivity':
                self.update_items_from_zigbee_connectivity_event(event_item, initialize)
            elif event_item.type.value == 'button':
                self.update_button_items_from_event(event_item, initialize=initialize)
            elif event_item.type.value == 'device':
                self.update_device_items_from_event(event_item, initialize=initialize)
            elif event_item.type.value == 'device_power':
                self.update_devicepower_items_from_event(event_item, initialize=initialize)
            elif event_item.type.value == 'homekit':
                self.logger.notice(f"handle_event: 'update': Event-item type '{event_item.type.value}'  -  status '{event_item.status.value}'")
                pass
            elif event_item.type.value == 'geofence_client':
                pass
            elif event_item.type.value == 'entertainment':
                pass
            elif event_item.type.value == 'scene':
                self.logger.info(f"handle_event: 'update': Event-item type '{event_item.type.value}' is unhandled  -  scene '{event_item.metadata.name}'  -  event={event_item}")
                pass
            else:
                self.logger.notice(f"handle_event: 'update': Event-item type '{event_item.type.value}' is unhandled  -  event={event_item}")
        else:
            self.logger.notice(f"handle_event: Eventtype {event_type.value} is unhandled  -  event={event_item}")
        return


    def _get_device(self, device_id):
        device = None
        for d in self.v2bridge.devices:
            if device_id in d.id:
                device = d
                break
        return device

    def _get_device_name(self, device_id):
        device = self._get_device(device_id)
        if device is None:
            return '-'
        return device.metadata.name

    def _get_light_name(self, light_id):
        name = '-'
        for d in self.v2bridge.devices:
            if light_id in d.lights:
                name = d.metadata.name
        return name

    def log_event(self, event_type, event_item):

        if event_item.type.value == 'geofence_client':
            pass
        elif event_item.type.value == 'light':
            mapping = event_item.id + mapping_delimiter + event_item.type.value + mapping_delimiter + 'y'
            self.logger.debug(f"handle_event: {event_type.value} {event_item.type.value}: '{self._get_light_name(event_item.id)}' {event_item.id_v1} {mapping=} {event_item.id}  -  {event_item=}")
        elif event_item.type.value == 'grouped_light':
            self.logger.notice(f"handle_event: {event_type.value} {event_item.type.value}: {event_item.id} {event_item.id_v1}  -  {event_item=}")
        else:
            self.logger.notice(f"handle_event: {event_type.value} {event_item.type.value}: {event_item.id}  -  {event_item=}")
        return


    def update_light_items_from_event(self, event_item, initialize=False):

        mapping_root = event_item.id + mapping_delimiter + event_item.type.value + mapping_delimiter

        if self.get_items_for_mapping(mapping_root + 'on') != []:
            self.logger.info(f"update_light_items_from_event: '{self._get_light_name(event_item.id)}' - {event_item}")

        if initialize:
            self.update_items_with_mapping(event_item, mapping_root, 'name', self._get_light_name(event_item.id), initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'dict', {}, initialize)

        self.update_items_with_mapping(event_item, mapping_root, 'on', event_item.on.on, initialize)
        self.update_items_with_mapping(event_item, mapping_root, 'bri', event_item.dimming.brightness, initialize)
        self.update_items_with_mapping(event_item, mapping_root, 'xy', [event_item.color.xy.x, event_item.color.xy.y], initialize)
        try:
            mirek = event_item.color_temperature.mirek
        except:
            mirek = 0
        self.update_items_with_mapping(event_item, mapping_root, 'ct', mirek, initialize)
        self.update_items_with_mapping(event_item, mapping_root, 'alert', event_item.alert.action_values[0].value, initialize)

        return


    def update_group_items_from_event(self, event_item, initialize=False):
        if event_item.type.value == 'grouped_light':
            mapping_root = event_item.id + mapping_delimiter + 'group' + mapping_delimiter

#            if self.get_items_for_mapping(mapping_root + 'on') != []:
#                room = self.v2bridge.groups.grouped_light.get_zone(event_item.id)
#                name = room.metadata.name
#                if event_item.id_v1 == '/groups/0':
#                    name = '(All lights)'
#                self.logger.notice(f"update_group_items_from_event: '{name}' - {event_item}")

            if initialize:
                self.update_items_with_mapping(event_item, mapping_root, 'name', self._get_light_name(event_item.id), initialize)
                self.update_items_with_mapping(event_item, mapping_root, 'dict', {}, initialize)

            self.update_items_with_mapping(event_item, mapping_root, 'on', event_item.on.on, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'bri', event_item.dimming.brightness, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'alert', event_item.alert.action_values[0].value, initialize)

        return


    def update_items_from_zigbee_connectivity_event(self, event_item, initialize=False):

        lights = self.v2bridge.devices.get_lights(event_item.owner.rid)
        sensors = self.v2bridge.devices.get_sensors(event_item.owner.rid)
        if len(lights) > 0:
            for light in lights:
                mapping_root = light.id + mapping_delimiter + 'light' + mapping_delimiter
                self.update_items_with_mapping(light, mapping_root, 'reachable', str(event_item.status.value) == 'connected', initialize)
                self.update_items_with_mapping(light, mapping_root, 'connectivity', event_item.status.value, initialize)
            mapping_root = event_item.id + mapping_delimiter + 'sensor' + mapping_delimiter
            self.update_items_with_mapping(event_item, mapping_root, 'connectivity', event_item.status.value, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'reachable',
                                           str(event_item.status.value) == 'connected', initialize)
        elif len(sensors) > 0:
            sensors = self.v2bridge.devices.get_sensors(event_item.owner.rid)
            for sensor in sensors:
                if sensor.type.value == 'button':
                    mapping_root = sensor.id + mapping_delimiter + 'button' + mapping_delimiter
                    self.update_items_with_mapping(event_item, mapping_root, 'connectivity', event_item.status.value, initialize)
                    self.update_items_with_mapping(event_item, mapping_root, 'reachable', str(event_item.status.value) == 'connected', initialize)
                    break
            else:  # no button found
                status = event_item.status.value
                device = self._get_device(event_item.owner.rid)
                device_name = self._get_device_name(event_item.owner.rid)
                if device.product_data.product_archetype.value == 'bridge_v2':
                    mapping_root = device.id + mapping_delimiter + 'bridge' + mapping_delimiter
                    self.update_items_with_mapping(event_item, mapping_root, 'connectivity', event_item.status.value, initialize)
                    self.update_items_with_mapping(event_item, mapping_root, 'reachable', str(event_item.status.value) == 'connected', initialize)
                else:
                    self.logger.notice(f"update_items_from_zigbee_connectivity_event: '{event_item.type.value}' is unhandled - device '{device_name}', {status=}   -   event={event_item}")
                    self.logger.notice(f" - device: {device.product_data.product_archetype.value=}  -  {device=}")
                    self.logger.notice(f" - {sensors=}")

        else:
            # zigbee_connectivity for unknown device
            mapping_root = event_item.id + mapping_delimiter + 'unknown' + mapping_delimiter
            self.update_items_with_mapping(event_item, mapping_root, 'connectivity', event_item.status.value, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'reachable', str(event_item.status.value) == 'connected', initialize)

            device_name = self._get_device_name(event_item.owner.rid)
            status = event_item.status.value
            self.logger.notice(f"update_items_from_zigbee_connectivity_event: '{event_item.type.value}' is unhandled - device '{device_name}', {status=}   -   event={event_item}")
            device = self._get_device(event_item.owner.rid)
            self.logger.notice(f" - {device=}")
            sensors = self.v2bridge.devices.get_sensors(event_item.owner.rid)
            self.logger.notice(f" - {sensors=}")

        return


    def update_button_items_from_event(self, event_item, initialize=False):

        mapping_root = event_item.id + mapping_delimiter + event_item.type.value + mapping_delimiter

        if initialize:
            self.update_items_with_mapping(event_item, mapping_root, 'name', self._get_device_name(event_item.owner.rid) )

        try:
            last_event = event_item.button.last_event.value
        except Exception as ex:
            last_event = ''

        self.update_items_with_mapping(event_item, mapping_root, 'event', last_event, initialize)
        if last_event == 'initial_press':
            self.update_items_with_mapping(event_item, mapping_root, 'initial_press', True, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'repeat', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'short_release', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'long_release', False, initialize)
        if last_event == 'repeat':
            self.update_items_with_mapping(event_item, mapping_root, 'initial_press', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'repeat', True, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'short_release', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'long_release', False, initialize)
        if last_event == 'short_release':
            self.update_items_with_mapping(event_item, mapping_root, 'initial_press', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'repeat', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'short_release', True, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'long_release', False, initialize)
        if last_event == 'long_release':
            self.update_items_with_mapping(event_item, mapping_root, 'initial_press', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'repeat', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'short_release', False, initialize)
            self.update_items_with_mapping(event_item, mapping_root, 'long_release', True, initialize)

        return


    def update_device_items_from_event(self, event_item, initialize=False):

        mapping_root = event_item.id + mapping_delimiter + event_item.type.value + mapping_delimiter

        if initialize:
#            self.logger.notice(f"update_device_items_from_event: {event_item.id=}  -  {event_item}  -  {initialize=}")
            self.update_items_with_mapping(event_item, mapping_root, 'name', self._get_device_name(event_item.id) )

#        self.update_items_with_mapping(event_item, mapping_root, 'power_status', event_item.power_state.battery_state.value, initialize)
#        self.update_items_with_mapping(event_item, mapping_root, 'battery_level', event_item.power_state.battery_level, initialize)

        return


    def update_devicepower_items_from_event(self, event_item, initialize=False):

        mapping_root = event_item.id + mapping_delimiter + event_item.type.value + mapping_delimiter

        if initialize:
#            self.logger.notice(f"update_devicepower_items_from_event: {event_item.owner.rid=}  -  {event_item}")
            self.update_items_with_mapping(event_item, mapping_root, 'name', self._get_device_name(event_item.owner.rid) )

        self.update_items_with_mapping(event_item, mapping_root, 'power_status', event_item.power_state.battery_state.value, initialize)
        self.update_items_with_mapping(event_item, mapping_root, 'battery_level', event_item.power_state.battery_level, initialize)

        return


    def update_items_with_mapping(self, event_item, mapping_root, function, value, initialize=False):

        update_items = self.get_items_for_mapping(mapping_root + function)

        for item in update_items:
            #if initialize:
            #    # set v2 id in config data
            #    config_data = self.get_item_config(item)
            #    self.logger.debug(f"update_items_with_mapping: setting config_data for id_v1={config_data['id_v1']} -> Setting id to {event_item.id}")
            #    config_data['id'] = event_item.id
            item(value, self.get_fullname())


    def initialize_items_from_bridge(self):
        """
        Initializing the item values with data from the hue bridge after connecting to in
        """
        self.logger.debug('initialize_items_from_bridge: Start')
        #self.v2bridge.lights.initialize(None)
        for event_item in self.v2bridge.devices:
            self.update_device_items_from_event(event_item, initialize=True)
        for event_item in self.v2bridge.lights:
            self.update_light_items_from_event(event_item, initialize=True)
        for event_item in self.v2bridge.groups:
            self.update_group_items_from_event(event_item, initialize=True)
        for event_item in self.v2bridge.sensors:
            #self.update_button_items_from_event(event_item, initialize=True)
            self.handle_event('update', event_item, initialize=True)

        self.logger.debug('initialize_items_from_bridge: End')
        return



# ----------------------------------------------------------------------------------

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
        resource = self.get_iattr_value(item.conf, 'hue3_resource')
        function = self.get_iattr_value(item.conf, 'hue3_function')
        if self.has_iattr(item.conf, 'hue3_id') and self.has_iattr(item.conf, 'hue3_function') or \
           resource == 'scene' and function == 'activate_scene':
            config_data = {}
            id = self.get_iattr_value(item.conf, 'hue3_id')
            if id is None:
                id = 'None'
            config_data['id'] = id
            #config_data['id_v1'] = id
            config_data['resource'] = self.get_iattr_value(item.conf, 'hue3_resource')
            config_data['function'] = self.get_iattr_value(item.conf, 'hue3_function')
            config_data['transition_time'] = self.get_iattr_value(item.conf, 'hue3_transition_time')

            config_data['name'] = ''    # to be filled during initialization of v2bridge

            config_data['item'] = item

#            mapping = config_data['id_v1'] + mapping_delimiter + config_data['resource'] + mapping_delimiter + config_data['function']
            mapping = config_data['id'] + mapping_delimiter + config_data['resource'] + mapping_delimiter + config_data['function']

            # alt:
            self.logger.debug("parse item: {}".format(item))
            conf_data = {}
            conf_data['id'] = self.get_iattr_value(item.conf, 'hue3_id')
            conf_data['resource'] = self.get_iattr_value(item.conf, 'hue3_resource')
            conf_data['function'] = self.get_iattr_value(item.conf, 'hue3_function')

            conf_data['item'] = item
            # store config in plugin_items
            self.plugin_items[item.property.path] = conf_data

            if conf_data['resource'] == 'group':
                # bridge updates are allways scheduled
                self.logger.debug("parse_item: configured group item = {}".format(conf_data))
            # Ende alt

            self.add_item(item, mapping=mapping, config_data_dict=config_data, updating=True)
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

        To prevent a loop, the changed value should only be written to the device, if the plugin is running and
        the value was changed outside of this plugin(-instance). That is checked by comparing the caller parameter
        with the fullname (plugin name & instance) of the plugin.

        :param item: item to be updated towards the plugin
        :param caller: if given it represents the callers name
        :param source: if given it represents the source
        :param dest: if given it represents the dest
        """
        if self.alive and caller != self.get_fullname():
            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this plugin:
            self.logger.info(f"update_item: '{item.property.path}' has been changed outside this plugin by caller '{self.callerinfo(caller, source)}'")

            config_data = self.get_item_config(item)
            self.logger.info(f"update_item: Sending '{item()}' of '{config_data['item']}' to bridge  ->  {config_data=}")

            if config_data['resource'] == 'light':
                self.update_light_from_item(config_data, item)
            elif config_data['resource'] == 'group':
                self.update_group_from_item(config_data, item)
            elif config_data['resource'] == 'scene':
                self.update_scene_from_item(config_data, item)
            elif config_data['resource'] == 'sensor':
                self.update_sensor_from_item(config_data, item)
            elif config_data['resource'] == 'button':
                pass
                # self.update_button_from_item(config_data, item)
            else:
                self.logger.error(f"Resource '{config_data['resource']}' is not implemented")

        return


    def update_light_from_item(self, config_data, item):
        value = item()
        self.logger.debug(f"update_light_from_item: config_data = {config_data}")
        hue_transition_time = self._default_transition_time
        if config_data['transition_time'] is not None:
            hue_transition_time = int(float(config_data['transition_time']) * 1000)

        if config_data['function'] == 'on':
            try:
                if value:
                    self.run_asyncio_coro(self.v2bridge.lights.turn_on(config_data['id'], hue_transition_time), return_exeption=True)
                else:
                    self.run_asyncio_coro(self.v2bridge.lights.turn_off(config_data['id'], hue_transition_time), return_exeption=True)
            except Exception as ex:
                self.logger.error(f"update_light_from_item: id={config_data['id']}, {config_data['function']}, {value=} - Exception {ex}")
        elif config_data['function'] == 'bri':
            if float(value) <= 100:
                try:
                    self.run_asyncio_coro(self.v2bridge.lights.set_brightness(config_data['id'], float(value), hue_transition_time), return_exeption=True)
                except Exception as ex:
                    self.logger.error(f"update_light_from_item: id={config_data['id']}, {config_data['function']}, {value=} - Exception {ex}")
            else:
                self.logger.error(f"{item.property.path}: Can't set brightness of light {config_data['id']} to {value} - out of range")
        elif config_data['function'] == 'xy' and isinstance(value, list) and len(value) == 2:
            try:
                self.run_asyncio_coro(self.v2bridge.lights.set_color(config_data['id'], value[0], value[1], hue_transition_time), return_exeption=True)
            except Exception as ex:
                self.logger.error(f"update_light_from_item: id={config_data['id']}, {config_data['function']}, {value=} - Exception {ex}")
        elif config_data['function'] == 'ct':
            if float(value) >= 153 and float(value) <= 500:
                try:
                    self.run_asyncio_coro(self.v2bridge.lights.set_color_temperature(config_data['id'], value, hue_transition_time), return_exeption=True)
                except Exception as ex:
                    self.logger.error(f"update_light_from_item: id={config_data['id']}, {config_data['function']}, {value=} - Exception {ex}")
            else:
                self.logger.error(f"{item.property.path}: Can't set color temperature of light {config_data['id']} to {value} - out of range")
        elif config_data['function'] == 'dict':
            if value != {}:
                on = value.get('on', None)
                bri = value.get('bri', None)
                xy = value.get('xy', None)
                if xy is not None:
                    xy = (xy[0], xy[1])
                ct = value.get('ct', None)
                if bri or xy or ct:
                    on = True
                transition_time = value.get('transition_time', None)
                if transition_time is None:
                    transition_time = hue_transition_time
                else:
                    transition_time = int(float(transition_time)*1000)
                try:
                    self.run_asyncio_coro(self.v2bridge.lights.set_state(config_data['id'], on, bri, xy, ct, transition_time=transition_time), return_exeption=True)
                except Exception as ex:
                    self.logger.error(f"update_light_from_item: id={config_data['id']}, {config_data['function']}, {on=}, {bri=}, {xy=}, {ct=} - Exception {ex}")
        elif config_data['function'] == 'bri_inc':
            if float(value) >= -100 and float(value) <= 100:
                if float(value) < 0:
                    action = 'down'
                    value = -1 * float(value)
                elif float(value) > 0:
                    action = 'up'
                else:
                    action = 'stop'

                # TODO: bri_inc implementieren (ist in aiohue nicht implememntiert)
                self.logger.warning(f"Lights: {config_data['function']} not implemented in aiohue")
            else:
                self.logger.error(f"{item.property.path}: Can't set relative brightness of light {config_data['id']} with {value} - out of range")
        elif config_data['function'] == 'alert':
            self.logger.warning(f"Lights: {config_data['function']} not implemented")
        elif config_data['function'] == 'effect':
            self.logger.warning(f"Lights: {config_data['function']} not implemented")
        else:
            # The following functions from the api v1 are not supported by the api v2:
            # - hue, sat, ct
            # - name (for display, reading is done from the device-name)
            self.logger.notice(f"update_light_from_item: The function {config_data['function']} is not supported/implemented")
        return


    def update_scene_from_item(self, config_data, item):

        value = item()
        self.logger.debug(f"update_scene_from_item: config_data = {config_data}")
        hue_transition_time = self._default_transition_time
        if config_data['transition_time'] is not None:
            hue_transition_time = int(float(config_data['transition_time']) * 1000)

        if config_data['function'] == 'activate':
            self.run_asyncio_coro(self.v2bridge.scenes.recall(id=config_data['id']))
        elif config_data['function'] == 'activate_scene':
            #self.v2bridge.scenes.recall(id=value, dynamic=False, duration=hue_transition_time, brightness=float(bri))
            self.run_asyncio_coro(self.v2bridge.scenes.recall(id=value))
        elif config_data['function'] == 'name':
            self.logger.warning(f"Scenes: {config_data['function']} not implemented")
        return


    def update_group_from_item(self, config_data, item):
        value = item()
        self.logger.debug(f"update_group_from_item: config_data = {config_data} -> value = {value}")

        hue_transition_time = self._default_transition_time
        if config_data['transition_time'] is not None:
            hue_transition_time = int(float(config_data['transition_time']) * 1000)

        #self.logger.notice(f"update_group_from_item: function={config_data['function']}, hue_transition_time={hue_transition_time}, id={config_data['id']}")
        if config_data['function'] == 'on':
            self.run_asyncio_coro(self.v2bridge.groups.grouped_light.set_state(config_data['id'], on=value, transition_time=hue_transition_time))
        elif config_data['function'] == 'bri':
            self.run_asyncio_coro(self.v2bridge.groups.grouped_light.set_state(config_data['id'], on=True, brightness=float(value), transition_time=hue_transition_time))
        elif config_data['function'] == 'xy' and isinstance(value, list) and len(value) == 2:
            self.run_asyncio_coro(self.v2bridge.groups.grouped_light.set_state(config_data['id'], on=True, color_xy=value, transition_time=hue_transition_time))
        elif config_data['function'] == 'ct':
            self.run_asyncio_coro(self.v2bridge.groups.grouped_light.set_state(config_data['id'], on=True, color_temp=value, transition_time=hue_transition_time))
        elif config_data['function'] == 'dict':
            if value != {}:
                on = value.get('on', None)
                bri = value.get('bri', None)
                xy_in = value.get('xy', None)
                xy = None
                if xy_in is not None:
                    xy = (xy_in[0], xy_in[1])
                self.logger.notice(f"update_group_from_item: {xy_in=}, {xy=}, {type(xy)=}")
                ct = value.get('ct', None)
                if bri or xy or ct:
                    on = True
                transition_time = value.get('transition_time', None)
                if transition_time is None:
                    transition_time = hue_transition_time
                else:
                    transition_time = int(float(transition_time)*1000)
                self.run_asyncio_coro(self.v2bridge.groups.grouped_light.set_state(config_data['id'], on, bri, xy, ct, transition_time=transition_time))
        elif config_data['function'] == 'bri_inc':
            self.logger.warning(f"Groups: {config_data['function']} not implemented in aiohue")
        elif config_data['function'] == 'alert':
            self.logger.warning(f"Groups: {config_data['function']} not implemented")
        elif config_data['function'] == 'effect':
            self.logger.warning(f"Groups: {config_data['function']} not implemented")
        else:
            # The following functions from the api v1 are not supported by the api v2:
            # - hue, sat, ct, name
            self.logger.notice(f"update_group_from_item: The function {config_data['function']} is not supported/implemented")

        return


    def update_sensor_from_item(self, config_data, value):

        self.logger.debug(f"update_sensor_from_item: config_data = {config_data}")
        if config_data['function'] == 'name':
            self.logger.warning(f"Sensors: {config_data['function']} not implemented")
        return


    def get_data_from_discovered_bridges(self, serialno):
        """
        Get data from discovered bridges for a given serial number

        :param serialno: serial number of the bridge to look for
        :return: bridge info
        """
        result = {}
        for db in self.discovered_bridges:
            if db['serialNumber'] == serialno:
                result = db
                break
        if result == {}:
            # if bridge is not in list of discovered bridges, rediscover bridges and try again
            self.discovered_bridges = self.discover_bridges()
            for db in self.discovered_bridges:
                if db['serialNumber'] == serialno:
                    result = db
                    break

        return result

    # ============================================================================================

    def get_bridge_desciption(self, ip):
        """
        Get description of bridge

        :param ip:
        :param port:
        :return:

        # TODO: Change from requests to aiohttp
        """
        br_info = {}
        if ip == '0.0.0.0' or ip == '':
            return br_info

        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)

        r = requests.get('https://' + ip + '/description.xml', verify=False)
        if r.status_code != 200:
            r = requests.get('http://' + ip + '/description.xml', verify=False)
        if r.status_code == 200:
            xmldict = xmltodict.parse(r.text)
            br_info['ip'] = ip
            br_info['friendlyName'] = str(xmldict['root']['device']['friendlyName'])
            br_info['manufacturer'] = str(xmldict['root']['device']['manufacturer'])
            br_info['manufacturerURL'] = str(xmldict['root']['device']['manufacturerURL'])
            br_info['modelDescription'] = str(xmldict['root']['device']['modelDescription'])
            br_info['modelName'] = str(xmldict['root']['device']['modelName'])
            br_info['modelURL'] = str(xmldict['root']['device']['modelURL'])
            br_info['modelNumber'] = str(xmldict['root']['device']['modelNumber'])
            br_info['serialNumber'] = str(xmldict['root']['device']['serialNumber'])
            br_info['UDN'] = str(xmldict['root']['device']['UDN'])
            br_info['gatewayName'] = str(xmldict['root']['device'].get('gatewayName', ''))

            br_info['URLBase'] = str(xmldict['root']['URLBase'])
            if br_info['modelName'] == 'Philips hue bridge 2012':
                br_info['version'] = 'v1'
            elif br_info['modelName'] == 'Philips hue bridge 2015':
                br_info['version'] = 'v2'
            else:
                br_info['version'] = 'unknown'

            # get config information (short info without app_key)
            api_config = self.get_bridge_config(br_info['ip'])
            br_info['datastoreversion'] = api_config.get('datastoreversion', '')
            br_info['apiversion'] = api_config.get('apiversion', '')
            br_info['swversion'] = api_config.get('swversion', '')
            br_info['modelid'] = api_config.get('modelid', '')

        return br_info


    def discover_bridges(self):
        bridges = []
        try:
            discovered_bridges = discover_bridges(upnp=False)
            #discovered_bridges = discover_bridges(upnp=True, httponly=True)

        except Exception as e:
            self.logger.error("discover_bridges: Exception in discover_bridges(): {}".format(e))
            discovered_bridges = {}

        self.logger.info(f"discover_bridges: {discovered_bridges=}")
        for br in discovered_bridges:
            ip = discovered_bridges[br].split('/')[2].split(':')[0]
            br_info = self.get_bridge_desciption(ip)
            bridges.append(br_info)

        for bridge in bridges:
            self.logger.info("Discoverd bridge = {}".format(bridge))

        return bridges

    # --------------------------------------------------------------------------------------------

    def create_new_username(self, ip, devicetype=None, timeout=5):
        """
        Helper function to generate a new anonymous username on a hue bridge

        This method is a copy from the queue package without keyboard input

        :param ip:          ip address of the bridge
        :param devicetype:  (optional) devicetype to register with the bridge. If unprovided, generates a device
                            type based on the local hostname.
        :param timeout:     (optional, default=5) request timeout in seconds

        :return:            username/application key

        Raises:
            QhueException if something went wrong with username generation (for
                example, if the bridge button wasn't pressed).
        """
        from aiohue import create_app_key

        # api_key = await create_app_key(host, "authentication_example")

        devicetype = "authentication_example"
        devicetype = f"{self.get_fullname()}#{getfqdn()}"


        try:
            app_key = self.run_asyncio_coro(create_app_key(ip, devicetype), return_exeption=True)
        except Exception as ex:
            self.logger.error(f"create_new_username: {ex}")
            return ''

        self.logger.notice(f"app_key created '{app_key}'")

        self.logger.info(f"create_new_username: Generated username = {app_key}")
        return app_key


    def disconnect_bridge(self):
        """
        Disconnect the plugin from the bridge

        :param disconnect:
        :return:
        """
        if not self.bridge_is_configured():
            # There is no bridge to disconnect from
            return

        self.logger.notice(f"Disconnect: Disconnecting bridge")
        self.stop()
        self.bridge_ip = '0.0.0.0'

        self.logger.notice(f"disconnect_bridge: self.bridge = {self.bridge}")

        self.bridge = {}

        # update the plugin section in ../etc/plugin.yaml
        self.update_plugin_config()

        self.run()


    # --------------------------------------------------------------------------------------------

    def get_bridge_config(self, host: str = None) -> dict:
        """
        Get configuration info of a bridge

        :param host: IP Address of the bridge
        :return: configuration info
        """
        if host is None:
            if not self.bridge_is_configured():
                return {}
            host = self.bridge_ip

        if self.bridge_user == '':
            user = None
        else:
            user = self.bridge_user

        try:
            bridge_config = self.run_asyncio_coro(self.get_config(host, user), return_exeption=False)
        except Exception as ex:
            bridge_config = {}
            self.logger.error(f"get_bridge_config: {ex}")
        return bridge_config


    from aiohttp import ClientSession

    async def get_config(self, host: str, app_key: str = None, websession: ClientSession | None = None ) -> dict:
        """
        Get configuration of the Hue bridge using aiohue and return it's whitelist.

        :param host: the hostname or IP-address of the bridge as string.
        :param app_key: provide a name/type for your app for identification.
        :param websession: optionally provide a aiohttp ClientSession.
        :return:
        """
        # https://developers.meethue.com/develop/hue-api/7-configuration-api/#72_get_configuration
        # this can be used for both V1 and V2 bridges (for now).

        websession_provided = websession is not None
        if websession is None:
            from aiohttp import ClientSession
            websession = ClientSession()
        try:
            # try both https and http
            for proto in ["https", "http"]:
                try:
                    if app_key is None:
                        url = f"{proto}://{host}/api/config"
                    else:
                        url = f"{proto}://{host}/api/{app_key}/config"
                    async with websession.get(url, ssl=False) as resp:
                        resp.raise_for_status()
                        result = await resp.json()
                        if "error" in result:
                            self.logger.error(f"get_config: {result=}")
                            #raise_from_error(result["error"])
                        return result
                except Exception as exc:  # pylint: disable=broad-except
                    self.logger.error(f"get_config: proto={proto}, exc={exc}")
                    if proto == "http":
                        raise exc
        finally:
            if not websession_provided:
                await websession.close()

