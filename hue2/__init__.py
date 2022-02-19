#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      Martin Sinn                         m.sinn@gmx.de
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  hue plugin for new plugins to run with SmartHomeNG version 1.8 and
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

import qhue
import requests
import xmltodict

# for hostname retrieval for registering with the bridge
from socket import getfqdn

from lib.model.smartplugin import *
from lib.item import Items

from .webif import WebInterface

from .discover_bridges import discover_bridges

# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class Hue2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '2.2.0'    # (must match the version specified in plugin.yaml)

    hue_group_action_values          = ['on', 'bri', 'hue', 'sat', 'ct', 'xy', 'bri_inc', 'colormode', 'alert', 'effect']
    hue_light_action_writable_values = ['on', 'bri', 'hue', 'sat', 'ct', 'xy', 'bri_inc']
    hue_light_state_values           = ['on', 'bri', 'hue', 'sat', 'ct', 'xy', 'colormode', 'reachable', 'alert', 'effect']
    hue_light_state_writable_values  = ['on', 'bri', 'hue', 'sat', 'ct', 'xy', 'alert', 'effect']


    br = None               # Bridge object for communication with the bridge
    bridge_lights = {}
    bridge_groups = {}
    bridge_config = {}
    #bridge_schedules = {}
    bridge_scenes = {}
    #bridge_rules = {}
    bridge_sensors = {}
    #bridge_resourcelinks = {}


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
        self.bridge_serial = self.get_parameter_value('bridge_serial')
        self.bridge_ip = self.get_parameter_value('bridge_ip')
        self.bridge_port = self.get_parameter_value('bridge_port')
        self.bridge_user = self.get_parameter_value('bridge_user')

        # polled for value changes by adding a scheduler entry in the run method of this plugin
        self.sensor_items_configured = False   # If no sensor items are configured, the sensor-scheduler is not started
        self.light_items_configured = False   # If no sensor items are configured, the sensor-scheduler is not started
        self._cycle_sensors = self.get_parameter_value('polltime_sensors')
        self._cycle_lights = self.get_parameter_value('polltime_lights')
        self._cycle_bridge = self.get_parameter_value('polltime_bridge')
        self._default_transition_time = int(float(self.get_parameter_value('default_transitionTime'))*10)

        self.discovered_bridges = []
        self.bridge = self.get_bridge_desciption(self.bridge_ip, self.bridge_port)
        if self.bridge == {}:
            # discover hue bridges on the network
            self.discovered_bridges = self.discover_bridges()

            # self.bridge = self.get_parameter_value('bridge')
            # self.get_bridgeinfo()
            # self.logger.warning("Configured Bridge={}, type={}".format(self.bridge, type(self.bridge)))

            if self.bridge_serial == '':
                self.bridge = {}
            else:
                # if a bridge is configured
                # find bridge using its serial number
                self.bridge = self.get_data_from_discovered_bridges(self.bridge_serial)
                if self.bridge.get('serialNumber', '') == '':
                    self.logger.warning("Configured bridge {} is not in the list of discovered bridges, starting second discovery")
                    self.discovered_bridges = self.discover_bridges()

                    if self.bridge.get('serialNumber', '') == '':
                        # if not discovered, use stored ip address
                        self.bridge['ip'] = self.bridge_ip
                        self.bridge['port'] = self.bridge_port
                        self.bridge['serialNumber'] = self.bridge_serial
                        self.logger.warning("Configured bridge {} is still not in the list of discovered bridges, trying with stored ip address {}:{}".format(self.bridge_serial, self.bridge_ip, self.bridge_port))

                        api_config = self.get_api_config_of_bridge('http://'+self.bridge['ip']+':'+str(self.bridge['port'])+'/')
                        self.bridge['datastoreversion'] = api_config.get('datastoreversion', '')
                        self.bridge['apiversion'] = api_config.get('apiversion', '')
                        self.bridge['swversion'] = api_config.get('swversion', '')


        self.bridge['username'] = self.bridge_user
        if self.bridge['ip'] != self.bridge_ip:
            # if ip address of bridge has changed, store new ip address in configuration data
            self.update_plugin_config()

        if not self.get_bridgeinfo():
            self.bridge = {}
            self.logger.warning("Bridge '{}' is treated as unconfigured".format(self.bridge_serial))
        else:
            self.logger.info("Bridgeinfo for configured bridge '{}' = {}".format(self.bridge_serial, self.bridge))


        # dict to store information about items handled by this plugin
        self.plugin_items = {}

        self.init_webinterface(WebInterface)

        # read lights info from bridge
        self.poll_bridge_lights()
        return

    def run(self):
        """
        Run method for the plugin
        """
        self.logger.debug("Run method called")
        # setup scheduler for device poll loop   (disable the following line, if you don't need to poll the device. Rember to comment the self_cycle statement in __init__ as well)
        if self.sensor_items_configured:
            self.scheduler_add('update_sensors', self.poll_bridge_sensors, cycle=self._cycle_sensors)
        if self.light_items_configured:
            self.scheduler_add('update_lights', self.poll_bridge_lights, cycle=self._cycle_lights)
        self.scheduler_add('update_bridge', self.poll_bridge, cycle=self._cycle_bridge)

        self.alive = True
        # if you need to create child threads, do not make them daemon = True!
        # They will not shutdown properly. (It's a python bug)

    def stop(self):
        """
        Stop method for the plugin
        """
        self.logger.debug("Stop method called")
        if self.sensor_items_configured:
            self.scheduler_remove('update_sensors')
        if self.light_items_configured:
            self.scheduler_remove('update_lights')
        self.scheduler_remove('update_bridge')
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
        if self.has_iattr(item.conf, 'hue2_id') and self.has_iattr(item.conf, 'hue2_function'):
            self.logger.debug("parse item: {}".format(item))
            conf_data = {}
            conf_data['id'] = self.get_iattr_value(item.conf, 'hue2_id')
            conf_data['resource'] = self.get_iattr_value(item.conf, 'hue2_resource')
            conf_data['function'] = self.get_iattr_value(item.conf, 'hue2_function')
            if self.has_iattr(item.conf, 'hue2_refence_light_id'):
                if conf_data['resource'] == "group":
                    conf_data['hue2_refence_light_id'] = self.get_iattr_value(item.conf, 'hue2_refence_light_id')

            conf_data['item'] = item
            self.plugin_items[item.path()] = conf_data
            if conf_data['resource'] == 'sensor':
                # ensure that the scheduler for sensors will be started if items use sensor data
                self.sensor_items_configured = True
            if conf_data['resource'] == 'light':
                # ensure that the scheduler for sensors will be started if items use sensor data
                self.light_items_configured = True

            if conf_data['resource'] == 'group':
                # bridge updates are allways scheduled
                self.logger.debug("parse_item: configured group item = {}".format(conf_data))

            if conf_data['function'] != 'reachable':
                return self.update_item
            return

        if 'dpt3_dim' in item.conf:
            return self.dimDPT3

    def parse_logic(self, logic):
        """
        Default plugin parse_logic method
        """
        if 'xxx' in logic.conf:
            # self.function(logic['name'])
            pass

    def dimDPT3(self, item, caller=None, source=None, dest=None):
        # Evaluation of the list values for the KNX data
        # [1] for dimming
        # [0] for direction
        parent = item.return_parent()

        if item()[1] == 1:
            # dimmen
            if item()[0] == 1:
                # up
                parent(254, self.get_shortname()+"dpt3")
            else:
                # down
                parent(-254, self.get_shortname()+"dpt3")
        else:
            parent(0, self.get_shortname()+"dpt3")

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
            self.logger.info("update_item: {} has been changed by caller {} outside this plugin".format(item.id(), caller))

            if item.id() in self.plugin_items:
                plugin_item = self.plugin_items[item.id()]
                if plugin_item['resource'] == 'light':
                    self.update_light_from_item(plugin_item, item)
                elif plugin_item['resource'] == 'scene':
                    self.update_scene_from_item(plugin_item, item())
                elif plugin_item['resource'] == 'group':
                    self.update_group_from_item(plugin_item, item)
                elif plugin_item['resource'] == 'sensor':
                    self.update_sensor_from_item(plugin_item, item())

        return


    def update_light_from_item(self, plugin_item, item):
        value = item()
        self.logger.debug("update_light_from_item: plugin_item = {}".format(plugin_item))
        hue_transition_time = self._default_transition_time
        if 'hue2_transitionTime' in item.conf:
            hue_transition_time = int(float(item.conf['hue2_transitionTime']) * 10)
        try:
            if plugin_item['function'] == 'on':
                self.br.lights(plugin_item['id'], 'state', on=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'bri':
                if value > 0:
                    self.br.lights[plugin_item['id']]['state'](on=True, bri=value, transitiontime=hue_transition_time)
                else:
                    self.br.lights[plugin_item['id']]['state'](bri=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'bri_inc':
                self.br.lights[plugin_item['id']]['state'](on=True, bri_inc=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'hue':
                self.br.lights[plugin_item['id']]['state'](hue=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'sat':
                self.br.lights[plugin_item['id']]['state'](sat=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'ct':
                self.br.lights[plugin_item['id']]['state'](ct=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'name':
                self.br.lights[plugin_item['id']](name=value)
            elif plugin_item['function'] == 'xy':
                self.br.lights[plugin_item['id']]['state'](xy=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'alert':
                self.br.lights[plugin_item['id']]['state'](alert=value)
            elif plugin_item['function'] == 'effect':
                self.br.lights[plugin_item['id']]['state'](effect=value)
        except qhue.qhue.QhueException as e:
            self.logger.error(f"update_light_from_item: item {plugin_item['item'].id()} - qhue exception '{e}'")
        return


    def update_scene_from_item(self, plugin_item, value):

        self.logger.debug("update_scene_from_item: plugin_item = {}".format(plugin_item))
        if plugin_item['function'] == 'name':
            self.br.scenes[plugin_item['id']](name=value)

        return


    def update_group_from_item(self, plugin_item, item):
        value = item()
        self.logger.debug("update_group_from_item: plugin_item = {} -> value = {}".format(plugin_item, value))
        hue_transition_time = self._default_transition_time
        if 'hue2_transitionTime' in item.conf:
            hue_transition_time = int(float(item.conf['hue2_transitionTime']) * 10)
        try:
            if plugin_item['function'] == 'on':
                self.br.groups(plugin_item['id'], 'action', on=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'bri':
                if value > 0:
                    self.br.groups[plugin_item['id']]['action'](on=True, bri=value, transitiontime=hue_transition_time)
                else:
                    self.br.groups[plugin_item['id']]['action'](bri=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'bri_inc':
                self.br.groups[plugin_item['id']]['action'](bri_inc=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'hue':
                self.br.groups[plugin_item['id']]['action'](hue=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'sat':
                self.br.groups[plugin_item['id']]['action'](sat=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'ct':
                self.br.groups[plugin_item['id']]['action'](ct=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'name':
                self.br.groups[plugin_item['id']](name=value)
            elif plugin_item['function'] == 'xy':
                self.br.groups[plugin_item['id']]['action'](xy=value, transitiontime=hue_transition_time)
            elif plugin_item['function'] == 'activate_scene':
                self.br.groups(plugin_item['id'], 'action', scene=value, transitiontime=hue_transition_time)

        except qhue.qhue.QhueException as e:
            self.logger.error(f"update_group_from_item: item {plugin_item['item'].id()} - qhue exception '{e}'")

        return


    def update_sensor_from_item(self, plugin_item, value):

        self.logger.debug("update_sensor_from_item: plugin_item = {}".format(plugin_item))
        if plugin_item['function'] == 'name':
            self.br.sensors[plugin_item['id']](name=value)

        return


    def get_api_config_of_bridge(self, urlbase):

        url = urlbase + 'api/config'
        api_config = {}
        try:
            r = requests.get(url)
            if r.status_code == 200:
                api_config = r.json()
        except Exception as e:
            self.logger.error(f"get_api_config_of_bridge: url='{url}' - Exception {e}")
        return api_config


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

        if result != {}:
            api_config = self.get_api_config_of_bridge(result.get('URLBase',''))
            result['datastoreversion'] = api_config.get('datastoreversion', '')
            result['apiversion'] = api_config.get('apiversion', '')
            result['swversion'] = api_config.get('swversion', '')

        return result


    def poll_bridge(self):
        """
        Polls for updates of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        # # get the value from the device
        # device_value = ...
        #self.get_lights_info()
        if self.bridge.get('serialNumber','') == '':
            self.bridge_groups = {}
            self.bridge_config = {}
            self.bridge_scenes = {}
            self.bridge_sensors = {}
            return
        else:
            if self.br is not None:
                try:
                    self.bridge_groups = self.br.groups()
                    if not self.light_items_configured:
                        self.bridge_lights = self.br.lights()
                    if not self.sensor_items_configured:
                        self.bridge_sensors = self.br.sensors()
                except Exception as e:
                    self.logger.error(f"poll_bridge: Exception {e}")

                try:
                    self.bridge_config = self.br.config()
                except Exception as e:
                    self.logger.info(f"poll_bridge: Bridge-config not supported - Exception {e}")

                try:
                    self.bridge_scenes = self.br.scenes()
                except Exception as e:
                    self.logger.info(f"poll_bridge: Scenes not supported - Exception {e}")

        # update items with polled data
        src = self.get_instance_name()
        if src == '':
            src = None
        for pi in self.plugin_items:
            plugin_item = self.plugin_items[pi]
            if plugin_item['resource'] == 'scene':
                value = self._get_scene_item_value(plugin_item['id'], plugin_item['function'], plugin_item['item'].id())
                if value is not None:
                    plugin_item['item'](value, self.get_shortname(), src)
            if plugin_item['resource'] == 'group':
                if not "hue2_refence_light_id" in plugin_item:
                    value = self._get_group_item_value(plugin_item['id'], plugin_item['function'], plugin_item['item'].id())
                    plugin_item['item'](value, self.get_shortname(), src)
        return


    def poll_bridge_lights(self):
        """
        Polls for updates of lights of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        # get the value from the device: poll data from bridge
        if self.bridge.get('serialNumber','') == '':
            self.bridge_lights = {}
            return
        else:
            if self.br is not None:
                try:
                    self.bridge_lights = self.br.lights()
                except Exception as e:
                    self.logger.error(f"poll_bridge_lights: Exception {e}")

        # update items with polled data
        src = self.get_instance_name()
        if src == '':
            src = None
        for pi in self.plugin_items:
            plugin_item = self.plugin_items[pi]
            if plugin_item['resource'] == 'light':
                value = self._get_light_item_value(plugin_item['id'], plugin_item['function'], plugin_item['item'].id())
                if value is not None:
                    plugin_item['item'](value, self.get_shortname(), src)

            if plugin_item['resource'] == 'group':
                if "hue2_refence_light_id" in plugin_item:
                    reference_light_id = plugin_item["hue2_refence_light_id"]
                    value = self._get_light_item_value(reference_light_id, plugin_item['function'], plugin_item['item'].id())
                    if value is not None:
                        plugin_item['item'](value, self.get_shortname(), src)

        return


    def poll_bridge_sensors(self):
        """
        Polls for updates of sensors of the device

        This method is only needed, if the device (hardware/interface) does not propagate
        changes on it's own, but has to be polled to get the actual status.
        It is called by the scheduler which is set within run() method.
        """
        # get the value from the device: poll data from bridge
        if self.bridge.get('serialNumber','') == '':
            self.bridge_sensors = {}
            return
        else:
            if self.br is not None:
                try:
                    self.bridge_sensors = self.br.sensors()
                except Exception as e:
                    self.logger.error(f"poll_bridge_sensors: Exception {e}")

        # update items with polled data
        src = self.get_instance_name()
        if src == '':
            src = None
        for pi in self.plugin_items:
            plugin_item = self.plugin_items[pi]
            if  plugin_item['resource'] == 'sensor':
                value = self._get_sensor_item_value(plugin_item['id'], plugin_item['function'], plugin_item['item'].id())
                if value is not None:
                    plugin_item['item'](value, self.get_shortname(), src)
        return


    def _get_light_item_value(self, light_id, function, item_path):
        """
        Update item that hat hue_resource == 'light'
        :param id:
        :param function:
        :return:
        """
        result = ''
        try:
            light = self.bridge_lights[light_id]
        except KeyError:
            self.logger.error(f"poll_bridge_lights: Light '{light_id}' not defined on bridge (item '{item_path}')")
            return None
        except Exception as e :
            self.logger.exception(f"poll_bridge_lights: Light '{light_id}' on bridge (item '{item_path}') - exception: {e}")
            return None

        if function in self.hue_light_state_values:
            try:
                result = light['state'][function]
            except KeyError:
                self.logger.warning(f"poll_bridge_lights: Function {function} not supported by light '{light_id}' (item '{item_path}')")
                result = ''
        elif function == 'name':
            result = light['name']
        elif function == 'type':
            result = light['type']
        elif function == 'modelid':
            result = light['modelid']
        elif function == 'swversion':
            result = light['swversion']
        return result


    def _get_group_item_value(self, group_id, function, item_path):
        """
        Update item that hat hue_resource == 'light'
        :param id:
        :param function:
        :return:
        """
        result = ''
        if group_id != '0':
            # group_id 0 is a special group for "all groups" and can not be polled
            try:
                group = self.bridge_groups[group_id]
            except KeyError:
                self.logger.error(f"poll_bridge: Group '{group_id}' not defined on bridge (item '{item_path}')")
                return None

            if function in self.hue_group_action_values:
                result = group['action'].get(function, '')
            elif function == 'name':
                result = group['name']
        return result


    def _get_scene_item_value(self, scene_id, function, item_path):
        """
        Update item that hat hue_resource == 'light'
        :param id:
        :param function:
        :return:
        """
        result = ''
        try:
            scene = self.bridge_scenes[scene_id]
        except KeyError:
            self.logger.error(f"poll_bridge: Scene '{scene_id}' not defined on bridge (item '{item_path}')")
            return None

        if function == 'name':
            result = scene['name']
        return result


    def _get_sensor_item_value(self, sensor_id, function, item_path):
        """
        Update item that hat hue_resource == 'light'
        :param id:
        :param function:
        :return:
        """
        result = ''
        try:
            sensor = self.bridge_sensors[sensor_id]
        except KeyError:
            self.logger.error(f"poll_bridge_sensors: Sensor '{sensor_id}' not defined on bridge (item '{item_path}')")
            return None
        except Exception as e :
            self.logger.exception(f"poll_bridge_sensors: Sensor '{sensor_id}' on bridge (item '{item_path}') - exception: {e}")
            return None

        if function == 'name':
            result = sensor['name']
        return result


    def update_plugin_config(self):
        """
        Update the plugin configuration of this plugin in ../etc/plugin.yaml

        Fill a dict with all the parameters that should be changed in the config file
        and call the Method update_config_section()
        """
        conf_dict = {}
        # conf_dict['bridge'] = self.bridge
        conf_dict['bridge_serial'] = self.bridge.get('serialNumber','')
        conf_dict['bridge_user'] = self.bridge.get('username','')
        conf_dict['bridge_ip'] = self.bridge.get('ip','')
        conf_dict['bridge_port'] = self.bridge.get('port','')
        self.update_config_section(conf_dict)
        return

    # ============================================================================================

    def get_bridgeinfo(self):
        if self.bridge.get('serialNumber','') == '':
            self.br = None
            self.bridge_lights = {}
            self.bridge_groups = {}
            self.bridge_config = {}
            self.bridge_scenes = {}
            self.bridge_sensors = {}
            return
        self.logger.info("get_bridgeinfo: self.bridge = {}".format(self.bridge))
        self.br = qhue.Bridge(self.bridge['ip']+':'+str(self.bridge['port']), self.bridge['username'])
        try:
            self.bridge_lights = self.br.lights()
            self.bridge_groups = self.br.groups()
            self.bridge_config = self.br.config()
            self.bridge_scenes = self.br.scenes()
            self.bridge_sensors = self.br.sensors()
        except Exception as e:
            self.logger.error(f"Bridge '{self.bridge.get('serialNumber','')}' returned exception {e}")
            self.br = None
            self.bridge_lights = {}
            self.bridge_groups = {}
            self.bridge_config = {}
            self.bridge_scenes = {}
            self.bridge_sensors = {}
            return False

        return True


    def get_bridge_desciption(self, ip, port):
        """
        Get description of bridge

        :param ip:
        :param port:
        :return:
        """
        br_info = {}

        protocol = 'http'
        if str(port) == '443':
            protocol = 'https'

        requests.packages.urllib3.disable_warnings(requests.packages.urllib3.exceptions.InsecureRequestWarning)
        r = requests.get(protocol + '://' + ip + ':' + str(port) + '/description.xml', verify=False)
        if r.status_code == 200:
            xmldict = xmltodict.parse(r.text)
            br_info['ip'] = ip
            br_info['port'] = str(port)
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

            # get API information
            api_config = self.get_api_config_of_bridge(br_info['URLBase'])
            br_info['datastoreversion'] = api_config.get('datastoreversion', '')
            br_info['apiversion'] = api_config.get('apiversion', '')
            br_info['swversion'] = api_config.get('swversion', '')

        return br_info


    def discover_bridges(self):
        bridges = []
        try:
            #discovered_bridges = discover_bridges(mdns=True, upnp=True, httponly=True)
            discovered_bridges = discover_bridges(upnp=True, httponly=True)

        except Exception as e:
            self.logger.error("discover_bridges: Exception in discover_bridges(): {}".format(e))
            discovered_bridges = {}

        for br in discovered_bridges:
            ip = discovered_bridges[br].split('/')[2].split(':')[0]
            port = discovered_bridges[br].split('/')[2].split(':')[1]
            br_info = self.get_bridge_desciption(ip, port)

            bridges.append(br_info)

        for bridge in bridges:
            self.logger.info("Discoverd bridge = {}".format(bridge))

        return bridges

    # --------------------------------------------------------------------------------------------

    def create_new_username(self, ip, port, devicetype=None, timeout=5):
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
        api_url = "http://{}/api".format(ip+':'+port)
        try:
            # for qhue versions v2.0.0 and up
            session = requests.Session()
            res = qhue.qhue.Resource(api_url, session, timeout)
        except:
            # for qhue versions prior to v2.0.0
            res = qhue.qhue.Resource(api_url, timeout)
            res = qhue.qhue.Resource(api_url, timeout)

        if devicetype is None:
            devicetype = "SmartHomeNG#{}".format(getfqdn())

        # raises QhueException if something went wrong
        try:
            response = res(devicetype=devicetype, http_method="post")
        except Exception as e:
            self.logger.warning("create_new_username: Exception {}".format(e))
            return ''
        else:
            self.logger.info("create_new_username: Generated username = {}".format(response[0]["success"]["username"]))
            return response[0]["success"]["username"]


    def remove_username(self, ip, port, username, timeout=5):
        """
        Remove the username/application key from the bridge

        This function works only up to api version 1.3.0 of the bridge. Afterwards Philips/Signify disbled
        the removal of users through the api. It is now only possible through the portal (cloud serivce).

        :param ip:          ip address of the bridge
        :param username:
        :param timeout:     (optional, default=5) request timeout in seconds
        :return:

        Raises:
            QhueException if something went wrong with username deletion
        """
        api_url = "http://{}/api/{}".format(ip+':'+port, username)
        url = api_url + "/config/whitelist/{}".format(username)
        self.logger.info("remove_username: url = {}".format(url))
        res = qhue.qhue.Resource(url, timeout)

        devicetype = "SmartHomeNG#{}".format(getfqdn())

        # raises QhueException if something went wrong
        try:
            response = res(devicetype=devicetype, http_method="delete")
        except Exception as e:
            self.logger.error("remove_username: res-delete exception {}".format(e))
            response = [{'error': str(e)}]

        if not('success' in response[0]):
            self.logger.warning("remove_username: Error removing username/application key {} - {}".format(username, response[0]))
        else:
            self.logger.info("remove_username: username/application key {} removed".format(username))

