#!/usr/bin/env python3
# vim: set encoding=utf-8 tabstop=4 softtabstop=4 shiftwidth=4 expandtab
#########################################################################
#  Copyright 2020-      <AUTHOR>                                  <EMAIL>
#########################################################################
#  This file is part of SmartHomeNG.
#  https://www.smarthomeNG.de
#  https://knx-user-forum.de/forum/supportforen/smarthome-py
#
#  Sample plugin for new plugins to run with SmartHomeNG version 1.5 and
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

import discoverhue
import qhue
import requests
import xmltodict

# for hostname retrieval for registering with the bridge
from socket import getfqdn

from lib.model.smartplugin import *
from lib.item import Items

from .webif import WebInterface


# If a needed package is imported, which might be not installed in the Python environment,
# add it to a requirements.txt file within the plugin's directory


class Hue2(SmartPlugin):
    """
    Main class of the Plugin. Does all plugin specific stuff and provides
    the update functions for the items
    """

    PLUGIN_VERSION = '2.0.0'    # (must match the version specified in plugin.yaml)

    hue_light_state_values          = ['on', 'bri', 'hue', 'sat', 'ct', 'xy', 'colormode', 'reachable']
    hue_light_state_writable_values = ['on', 'bri', 'hue', 'sat', 'ct', 'xy']


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
        self.bridge_user = self.get_parameter_value('bridge_user')

        # polled for value changes by adding a scheduler entry in the run method of this plugin
        self.sensor_items_configured = False   # If no sensor items are configured, the sensor-scheduler is not started
        self.light_items_configured = False   # If no sensor items are configured, the sensor-scheduler is not started
        self._cycle_sensors = self.get_parameter_value('polltime_sensors')
        self._cycle_lights = self.get_parameter_value('polltime_lights')
        self._cycle_bridge = self.get_parameter_value('polltime_bridge')

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
                # if not discovered, use stored ip address
                self.bridge['ip'] = self.bridge_ip
                self.bridge['serialNumber'] = self.bridge_serial
                self.logger.warning("Configured bridge {} is not in the list of discovered bridges, trying stored ip address {}".format(self.bridge_serial, self.bridge_ip))
            self.bridge['username'] = self.bridge_user
            if self.bridge['ip'] != self.bridge_ip:
                # if ip address of bridge has changed, store new ip address in configuration data
                self.update_plugin_config()
        self.get_bridgeinfo()
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
            conf_data['item'] = item
            self.plugin_items[item.path()] = conf_data
            if conf_data['resource'] == 'sensor':
                # ensure that the scheduler for sensors will be started if items use sensor data
                self.sensor_items_configured = True
            if conf_data['resource'] == 'light':
                # ensure that the scheduler for sensors will be started if items use sensor data
                self.light_items_configured = True

            if conf_data['function'] != 'reachable':
                return self.update_item
            return


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
        if self.alive and caller != self.get_shortname():

            # code to execute if the plugin is not stopped
            # and only, if the item has not been changed by this this plugin:
            self.logger.info("update_item: {} has been changed by caller {} outside this plugin".format(item.id(), caller))

            if item.id() in self.plugin_items:
                plugin_item = self.plugin_items[item.id()]
                if plugin_item['resource'] == 'light':
                    self.update_light_from_item(plugin_item, item())

        return


    def update_light_from_item(self, plugin_item, value):

        self.logger.debug("update_item: plugin_item = {}".format(plugin_item))
        light = self.bridge_lights[plugin_item['id']]
        if plugin_item['function'] == 'on':
            self.br.lights(plugin_item['id'], 'state', on=value)
        elif plugin_item['function'] == 'bri':
            self.br.lights[plugin_item['id']]['state'](bri=value)
        elif plugin_item['function'] == 'hue':
            self.br.lights[plugin_item['id']]['state'](hue=value)
        elif plugin_item['function'] == 'sat':
            self.br.lights[plugin_item['id']]['state'](sat=value)
        elif plugin_item['function'] == 'ct':
            self.br.lights[plugin_item['id']]['state'](ct=value)
        elif plugin_item['function'] == 'name':
            self.br.lights[plugin_item['id']](name=value)
        elif plugin_item['function'] == 'xy':
            self.br.lights[plugin_item['id']]['state'](xy=value)

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
                self.bridge_groups = self.br.groups()
                self.bridge_config = self.br.config()
                self.bridge_scenes = self.br.scenes()
                if not self.light_items_configured:
                    self.bridge_lights = self.br.lights()
                if not self.sensor_items_configured:
                    self.bridge_sensors = self.br.sensors()
        #
        # # find the item(s) to update:
        # for item in self.sh.find_items('...'):
        #
        #     # update the item by calling item(value, caller, source=None, dest=None)
        #     # - value and caller must be specified, source and dest are optional
        #     #
        #     # The simple case:
        #     item(device_value, self.get_shortname())
        #     # if the plugin is a gateway plugin which may receive updates from several external sources,
        #     # the source should be included when updating the the value:
        #     item(device_value, self.get_shortname(), source=device_source_id)

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
                self.bridge_lights = self.br.lights()

        # update items with polled data
        src = self.get_instance_name()
        if src == '':
            src = None
        for pi in self.plugin_items:
            plugin_item = self.plugin_items[pi]
            plugin_item['item']( self._get_light_item_value(plugin_item['id'], plugin_item['function']), self.get_shortname(), src)
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
                self.bridge_sensors = self.br.sensors()

        # # update items with polled data
        # src = self.get_instance_name()
        # if src == '':
        #     src = None
        # for pi in self.plugin_items:
        #     plugin_item = self.plugin_items[pi]
        #     plugin_item['item']( self._get_light_item_value(plugin_item['id'], plugin_item['function']), self.get_shortname(), src)
        return


    def _get_light_item_value(self, light_id, function):
        """
        Update item that hat hue_resource == 'light'
        :param id:
        :param function:
        :return:
        """
        result = ''
        light = self.bridge_lights[light_id]
        if function in self.hue_light_state_values:
            result = light['state'][function]
        elif function == 'name':
            result = light['name']
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
        self.br = qhue.Bridge(self.bridge['ip'], self.bridge['username'])
        self.bridge_lights = self.br.lights()
        self.bridge_groups = self.br.groups()
        self.bridge_config = self.br.config()
        self.bridge_scenes = self.br.scenes()
        self.bridge_sensors = self.br.sensors()
        return

    def discover_bridges(self):
        bridges = []
        try:
            discovered_bridges = discoverhue.find_bridges()
        except Exception as e:
            self.logger.error("discover_bridges: Exception in find_bridges(): {}".format(e))
            discovered_bridges = {}

        for br in discovered_bridges:
            br_info = {}
            br_info['mac'] = br
            br_info['ip'] = discovered_bridges[br].split('/')[2].split(':')[0]
            r = requests.get('http://' + br_info['ip'] + '/description.xml')
            if r.status_code == 200:
                xmldict = xmltodict.parse(r.text)
                br_info['friendlyName'] = str(xmldict['root']['device']['friendlyName'])
                br_info['manufacturer'] = str(xmldict['root']['device']['manufacturer'])
                br_info['modelName'] = str(xmldict['root']['device']['modelName'])
                br_info['modelNumber'] = str(xmldict['root']['device']['modelNumber'])
                br_info['serialNumber'] = str(xmldict['root']['device']['serialNumber'])
                br_info['UDN'] = str(xmldict['root']['device']['UDN'])
                br_info['URLBase'] = str(xmldict['root']['URLBase'])
                if br_info['modelName'] == 'Philips hue bridge 2012':
                    br_info['version'] = 'v1'
                elif br_info['modelName'] == 'Philips hue bridge 2015':
                    br_info['version'] = 'v2'
                else:
                    br_info['version'] = 'unknown'
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
        api_url = "http://{}/api".format(ip)
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


    def remove_username(self, ip, username, timeout=5):
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
        api_url = "http://{}/api/{}".format(ip, username)
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

